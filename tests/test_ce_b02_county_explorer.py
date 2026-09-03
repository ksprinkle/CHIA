"""CE-B02 tests for GET /api/v1/counties/{county_fips}/explorer.

unittest, matching the existing suites: in-memory canonical-schema-subset
fixtures backed to a temp file, FastAPI ``TestClient`` with a dependency
override, digest-based read-only checks, and a guarded production integration
test. No copy or mutation of the canonical ``chia_v01.sqlite``.
"""

from __future__ import annotations

from collections.abc import Iterator
import hashlib
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest import mock

from fastapi.testclient import TestClient

import app.api.v1.explorer as explorer_module
from app.db import open_readonly_connection
from app.main import app
from app.schemas.explorer import ExplorerResponse
from app.services.county_explorer import (
    CountyNotFoundError,
    ExplorerDataError,
    load_county_explorer,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DATABASE = PROJECT_ROOT / "Data" / "Model" / "chia_v01.sqlite"
EXPECTED_PRODUCTION_SHA256 = (
    "db493c131e3c573e98236e17bda856b683cd50d4bd4ab19c7fd3fde15b8b72c4"
)
EXPECTED_COUNTY_COUNT = 3143

SCHEMA_SQL = """
CREATE TABLE county (
    county_fips TEXT PRIMARY KEY, state_fips TEXT NOT NULL, county_name TEXT NOT NULL,
    state_name TEXT NOT NULL, state_abbr TEXT NOT NULL
);
CREATE TABLE county_period (
    county_period_id INTEGER PRIMARY KEY, county_fips TEXT NOT NULL, period TEXT NOT NULL,
    completeness_status TEXT
);
CREATE TABLE source (
    source_id INTEGER PRIMARY KEY, source_name TEXT NOT NULL, publisher TEXT,
    dataset_name TEXT, reference_period TEXT, url TEXT, accessed_at TEXT
);
CREATE TABLE methodology (
    methodology_version TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT,
    status TEXT, created_at TEXT
);
CREATE TABLE variable_definition (
    variable_id TEXT PRIMARY KEY, variable_name TEXT NOT NULL, display_name TEXT NOT NULL,
    description TEXT, unit TEXT, source_id INTEGER, direction TEXT
);
CREATE TABLE observation (
    observation_id INTEGER PRIMARY KEY, county_period_id INTEGER NOT NULL,
    variable_id TEXT NOT NULL, raw_value REAL, raw_text TEXT, quality_flag TEXT, notes TEXT,
    UNIQUE (county_period_id, variable_id)
);
CREATE TABLE normalized_measure (
    observation_id INTEGER NOT NULL, methodology_version TEXT NOT NULL,
    normalized_value REAL, normalization_method TEXT NOT NULL,
    PRIMARY KEY (observation_id, methodology_version)
);
CREATE TABLE dimension_definition (
    dimension_id TEXT PRIMARY KEY, dimension_name TEXT NOT NULL, description TEXT,
    primary_variable_id TEXT NOT NULL, supporting_variables TEXT, calculation_method TEXT,
    methodology_version TEXT NOT NULL
);
CREATE TABLE dimension_score (
    county_period_id INTEGER NOT NULL, dimension_id TEXT NOT NULL, score REAL,
    methodology_version TEXT NOT NULL, status TEXT,
    PRIMARY KEY (county_period_id, dimension_id, methodology_version)
);
CREATE TABLE composite_score (
    county_period_id INTEGER NOT NULL, methodology_version TEXT NOT NULL,
    composite_value REAL, status TEXT, missing_dimensions TEXT,
    PRIMARY KEY (county_period_id, methodology_version)
);
"""

MV = "v0.1"

# dimension_id -> (name, description, primary_var, [supporting], source_id, normalized)
DIMENSIONS = [
    ("PRIMARY_CARE", "Primary Care Access",
     "Geographic primary care shortage coverage at the county level.",
     "PC_HPSA_GEOGRAPHIC_COVERAGE",
     ["PC_HPSA_AREA_WEIGHTED_SCORE", "PC_HPSA_MAX_SCORE", "PC_HPSA_DESIGNATION_COUNT"],
     1, True),
    ("DENTAL", "Dental Access",
     "Geographic dental shortage coverage at the county level.",
     "DENTAL_HPSA_GEOGRAPHIC_COVERAGE",
     ["DENTAL_HPSA_AREA_WEIGHTED_SCORE", "DENTAL_HPSA_MAX_SCORE", "DENTAL_HPSA_DESIGNATION_COUNT"],
     2, True),
    ("MENTAL_HEALTH", "Mental Health Access",
     "Geographic mental health shortage coverage at the county level.",
     "MH_HPSA_GEOGRAPHIC_COVERAGE",
     ["MH_HPSA_AREA_WEIGHTED_SCORE", "MH_HPSA_MAX_SCORE", "MH_HPSA_DESIGNATION_COUNT"],
     3, True),
    ("MUA_P", "MUA/P Access",
     "Geographic medically underserved area/population coverage at the county level.",
     "MUAP_GEOGRAPHIC_COVERAGE",
     ["MUAP_MEAN_SCORE", "MUAP_MAX_SCORE", "MUAP_FEATURE_COUNT", "MUA_FEATURE_COUNT",
      "MUP_FEATURE_COUNT", "MUAP_UNIQUE_SOURCE_COUNT"],
     4, False),
]
DIMENSION_ORDER = [d[0] for d in DIMENSIONS]

# Verbatim calculation_method text -- deliberately keeps the pre-existing,
# analytically inaccurate "normalized using county percentile rank" wording for
# MUA/P (CE-B02 must not "correct" it).
CALC_METHOD = {
    "PRIMARY_CARE": "Primary variable normalized using county percentile rank; supporting HPSA severity and designation measures displayed separately.",
    "DENTAL": "Primary variable normalized using county percentile rank; supporting HPSA severity and designation measures displayed separately.",
    "MENTAL_HEALTH": "Primary variable normalized using county percentile rank; supporting HPSA severity and designation measures displayed separately.",
    "MUA_P": "Primary variable normalized using county percentile rank; supporting MUA/P measures displayed separately.",
}

BASE_SCORE = {"PRIMARY_CARE": 80.0, "DENTAL": 30.0, "MENTAL_HEALTH": 45.0, "MUA_P": 90.0}


def file_sha256(path: Path | str) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build_explorer_db(path: Path, counties: list[dict]) -> None:
    connection = sqlite3.connect(":memory:")
    connection.executescript(SCHEMA_SQL)

    connection.execute(
        "INSERT INTO methodology VALUES (?, ?, ?, ?, ?)",
        (MV, "CHIA Access Profile v0.1", "Four-domain county-level healthcare access profile.",
         "prototype", "2026-09-02 00:09:27"),
    )
    for source_id in (1, 2, 3, 4):
        connection.execute(
            "INSERT INTO source VALUES (?, ?, ?, ?, ?, ?, ?)",
            (source_id, f"Source {source_id}", "HRSA", f"Dataset {source_id}",
             "v0.1 source period", None, None),
        )
    for dimension_id, name, description, primary_var, supporting, source_id, _norm in DIMENSIONS:
        for variable_id in (primary_var, *supporting):
            unit = "percent" if variable_id.endswith("GEOGRAPHIC_COVERAGE") else "score"
            connection.execute(
                "INSERT OR IGNORE INTO variable_definition VALUES (?, ?, ?, ?, ?, ?, ?)",
                (variable_id, variable_id.lower(), f"{variable_id} display",
                 f"{variable_id} description", unit, source_id, "higher_burden"),
            )
        connection.execute(
            "INSERT INTO dimension_definition VALUES (?, ?, ?, ?, ?, ?, ?)",
            (dimension_id, name, description, primary_var, ", ".join(supporting),
             CALC_METHOD[dimension_id], MV),
        )

    observation_id = 1
    for index, spec in enumerate(counties, start=1):
        fips = spec["county_fips"]
        missing = set(spec.get("missing", ()))
        connection.execute(
            "INSERT INTO county VALUES (?, ?, ?, ?, ?)",
            (fips, fips[:2], spec.get("county_name", "0"),
             spec.get("state_name", ""), spec.get("state_abbr", "AL")),
        )
        county_period_id = index
        connection.execute(
            "INSERT INTO county_period VALUES (?, ?, ?, ?)",
            (county_period_id, fips, MV, spec.get("completeness_status", "complete")),
        )

        scores: dict[str, float | None] = {}
        for dimension_id, _n, _d, primary_var, supporting, _s, normalized in DIMENSIONS:
            is_missing = dimension_id in missing
            base = BASE_SCORE[dimension_id]

            if normalized:
                raw_value = None if is_missing else base + 1000.0
            else:
                raw_value = None if is_missing else base
            connection.execute(
                "INSERT INTO observation VALUES (?, ?, ?, ?, ?, ?, ?)",
                (observation_id, county_period_id, primary_var, raw_value, None,
                 "source_validated", None),
            )
            if normalized and not is_missing:
                connection.execute(
                    "INSERT INTO normalized_measure VALUES (?, ?, ?, ?)",
                    (observation_id, MV, base, "county_percentile_rank_average"),
                )
            observation_id += 1

            for offset, supporting_id in enumerate(supporting):
                connection.execute(
                    "INSERT INTO observation VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (observation_id, county_period_id, supporting_id,
                     10.0 + offset, None, "source_validated", None),
                )
                observation_id += 1

            score = None if is_missing else base
            scores[dimension_id] = score
            connection.execute(
                "INSERT INTO dimension_score VALUES (?, ?, ?, ?, ?)",
                (county_period_id, dimension_id, score, MV, "calculated"),
            )

        if missing:
            missing_list = ", ".join(d for d in DIMENSION_ORDER if d in missing)
            connection.execute(
                "INSERT INTO composite_score VALUES (?, ?, ?, ?, ?)",
                (county_period_id, MV, None, "experimental_provisional_incomplete", missing_list),
            )
        else:
            composite_value = sum(scores[d] for d in DIMENSION_ORDER) / 4.0
            connection.execute(
                "INSERT INTO composite_score VALUES (?, ?, ?, ?, ?)",
                (county_period_id, MV, composite_value, "experimental_provisional", None),
            )

    connection.commit()
    disk = sqlite3.connect(path)
    connection.backup(disk)
    disk.close()
    connection.close()


COMPLETE_COUNTY = {"county_fips": "10001", "county_name": "0", "state_name": "", "state_abbr": "AL"}
INCOMPLETE_COUNTY = {"county_fips": "20002", "county_name": "0", "state_name": "",
                     "state_abbr": "AL", "missing": {"DENTAL"}}


def override_factory(database_path: Path):
    def _dependency() -> Iterator[sqlite3.Connection]:
        connection = open_readonly_connection(database_path)
        try:
            yield connection
        finally:
            connection.close()

    return _dependency


class CountyExplorerServiceTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.directory.name) / "explorer.sqlite"
        build_explorer_db(self.database_path, [COMPLETE_COUNTY, INCOMPLETE_COUNTY])

    def tearDown(self):
        self.directory.cleanup()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.database_path)

    def test_assembles_complete_county(self):
        connection = self._connect()
        try:
            model = load_county_explorer(connection, "10001")
        finally:
            connection.close()

        self.assertIsInstance(model, ExplorerResponse)
        self.assertEqual(model.county.county_fips, "10001")
        self.assertEqual(model.county.county_name, "0")
        self.assertEqual(model.county.state_name, "")
        self.assertEqual(model.county.state_abbr, "AL")
        self.assertEqual(model.period.value, "v0.1")
        self.assertEqual(model.period.completeness_status, "complete")

        profile = model.access_profile
        for dimension in (profile.primary_care, profile.dental, profile.mental_health, profile.mua_p):
            self.assertTrue(dimension.available)
            self.assertEqual(dimension.score_status, "calculated")
        self.assertEqual(profile.primary_care.score, 80.0)
        self.assertEqual(profile.dental.score, 30.0)
        self.assertEqual(profile.mental_health.score, 45.0)
        self.assertEqual(profile.mua_p.score, 90.0)

        # Normalized dimensions carry a normalized measure; MUA/P does not.
        self.assertTrue(profile.primary_care.normalized)
        self.assertEqual(profile.primary_care.primary_measure.normalized_value, 80.0)
        self.assertEqual(
            profile.primary_care.primary_measure.normalization_method,
            "county_percentile_rank_average",
        )
        self.assertFalse(profile.mua_p.normalized)
        self.assertIsNone(profile.mua_p.primary_measure.normalized_value)
        self.assertIsNone(profile.mua_p.primary_measure.normalization_method)
        self.assertEqual(profile.mua_p.primary_measure.raw_value, 90.0)

        self.assertEqual(len(profile.primary_care.supporting_evidence), 3)
        self.assertEqual(len(profile.mua_p.supporting_evidence), 6)
        self.assertEqual(
            profile.mua_p.supporting_evidence[0].variable_id, "MUAP_MEAN_SCORE"
        )

        composite = model.experimental_composite
        self.assertEqual(composite.label, "Experimental / Provisional")
        self.assertEqual(composite.status, "experimental_provisional")
        self.assertEqual(composite.missing_dimensions, [])
        self.assertAlmostEqual(composite.composite_value, (80.0 + 30.0 + 45.0 + 90.0) / 4.0)

        self.assertEqual([s.source_id for s in model.provenance.sources], [1, 2, 3, 4])
        self.assertEqual(model.methodology.methodology_version, "v0.1")
        self.assertEqual(
            model.methodology.normalization_method, "county_percentile_rank_average"
        )

    def test_calculation_method_is_returned_verbatim_including_mua_p(self):
        connection = self._connect()
        try:
            model = load_county_explorer(connection, "10001")
        finally:
            connection.close()
        self.assertEqual(
            model.access_profile.mua_p.calculation_method, CALC_METHOD["MUA_P"]
        )

    def test_incomplete_county_no_partial_average(self):
        connection = self._connect()
        try:
            model = load_county_explorer(connection, "20002")
        finally:
            connection.close()

        self.assertEqual(model.county.county_fips, "20002")
        self.assertEqual(model.period.completeness_status, "complete")

        dental = model.access_profile.dental
        self.assertFalse(dental.available)
        self.assertIsNone(dental.score)
        self.assertIsNone(dental.primary_measure.raw_value)
        self.assertIsNone(dental.primary_measure.normalized_value)
        self.assertTrue(model.access_profile.primary_care.available)
        self.assertTrue(model.access_profile.mental_health.available)
        self.assertTrue(model.access_profile.mua_p.available)

        composite = model.experimental_composite
        self.assertIsNone(composite.composite_value)  # no partial averaging
        self.assertEqual(composite.status, "experimental_provisional_incomplete")
        self.assertEqual(composite.missing_dimensions, ["DENTAL"])
        self.assertEqual(composite.label, "Experimental / Provisional")

    def test_unknown_fips_raises_county_not_found(self):
        connection = self._connect()
        try:
            with self.assertRaises(CountyNotFoundError):
                load_county_explorer(connection, "99999")
        finally:
            connection.close()

    def test_missing_county_period_raises_data_error(self):
        connection = self._connect()
        try:
            connection.execute("DELETE FROM county_period WHERE county_fips = '10001'")
            connection.commit()
            with self.assertRaises(ExplorerDataError):
                load_county_explorer(connection, "10001")
        finally:
            connection.close()

    def test_missing_dimension_definition_raises_data_error(self):
        connection = self._connect()
        try:
            connection.execute("DELETE FROM dimension_definition WHERE dimension_id = 'DENTAL'")
            connection.commit()
            with self.assertRaises(ExplorerDataError):
                load_county_explorer(connection, "10001")
        finally:
            connection.close()

    def test_declared_supporting_variable_without_definition_raises(self):
        connection = self._connect()
        try:
            connection.execute(
                "UPDATE dimension_definition SET supporting_variables = 'NOT_A_REAL_VARIABLE' WHERE dimension_id = 'PRIMARY_CARE'"
            )
            connection.commit()
            with self.assertRaises(ExplorerDataError):
                load_county_explorer(connection, "10001")
        finally:
            connection.close()

    def test_missing_composite_row_raises_data_error(self):
        connection = self._connect()
        try:
            connection.execute(
                "DELETE FROM composite_score WHERE county_period_id = (SELECT county_period_id FROM county_period WHERE county_fips='10001')"
            )
            connection.commit()
            with self.assertRaises(ExplorerDataError):
                load_county_explorer(connection, "10001")
        finally:
            connection.close()

    def test_service_does_not_mutate_database_and_score_is_persisted_value(self):
        before = file_sha256(self.database_path)
        connection = self._connect()
        try:
            persisted = connection.execute(
                """
                SELECT ds.score FROM dimension_score ds
                JOIN county_period cp ON cp.county_period_id = ds.county_period_id
                WHERE cp.county_fips = '10001' AND ds.dimension_id = 'PRIMARY_CARE'
                """
            ).fetchone()[0]
            model = load_county_explorer(connection, "10001")
            persisted_after = connection.execute(
                """
                SELECT ds.score FROM dimension_score ds
                JOIN county_period cp ON cp.county_period_id = ds.county_period_id
                WHERE cp.county_fips = '10001' AND ds.dimension_id = 'PRIMARY_CARE'
                """
            ).fetchone()[0]
        finally:
            connection.close()

        self.assertEqual(model.access_profile.primary_care.score, persisted)
        self.assertEqual(persisted_after, persisted)  # supporting evidence did not alter it
        self.assertEqual(file_sha256(self.database_path), before)


class CountyExplorerApiTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.directory.name) / "explorer_api.sqlite"
        build_explorer_db(self.database_path, [COMPLETE_COUNTY, INCOMPLETE_COUNTY])
        app.dependency_overrides[explorer_module.get_explorer_connection] = override_factory(
            self.database_path
        )

    def tearDown(self):
        app.dependency_overrides.clear()
        self.directory.cleanup()

    def test_complete_county_returns_200_and_valid_model(self):
        with TestClient(app) as client:
            response = client.get("/api/v1/counties/10001/explorer")
        self.assertEqual(response.status_code, 200)
        model = ExplorerResponse.model_validate(response.json())
        self.assertEqual(model.county.county_fips, "10001")
        self.assertEqual(model.county.county_name, "0")
        self.assertEqual(model.county.state_name, "")
        self.assertEqual(model.period.value, "v0.1")
        self.assertEqual(model.period.completeness_status, "complete")
        self.assertTrue(model.access_profile.primary_care.available)
        self.assertFalse(model.access_profile.mua_p.normalized)
        self.assertEqual(model.experimental_composite.label, "Experimental / Provisional")
        self.assertEqual(model.experimental_composite.status, "experimental_provisional")
        self.assertEqual(len(model.provenance.sources), 4)
        self.assertEqual(model.methodology.methodology_version, "v0.1")

    def test_incomplete_county_returns_200_with_incomplete_status(self):
        with TestClient(app) as client:
            response = client.get("/api/v1/counties/20002/explorer")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertFalse(payload["access_profile"]["dental"]["available"])
        self.assertIsNone(payload["access_profile"]["dental"]["score"])
        self.assertIsNone(payload["experimental_composite"]["composite_value"])
        self.assertEqual(
            payload["experimental_composite"]["status"], "experimental_provisional_incomplete"
        )
        self.assertEqual(
            payload["experimental_composite"]["missing_dimensions"], ["DENTAL"]
        )

    def test_unknown_but_well_formed_fips_returns_404(self):
        with TestClient(app) as client:
            response = client.get("/api/v1/counties/99999/explorer")
        self.assertEqual(response.status_code, 404)
        self.assertIn("detail", response.json())

    def test_malformed_fips_returns_422(self):
        with TestClient(app) as client:
            for value in ("abcde", "123", "123456", "1234a", "0100"):
                response = client.get(f"/api/v1/counties/{value}/explorer")
                self.assertEqual(response.status_code, 422, value)

    def test_database_unusable_returns_503_not_404(self):
        # Fixture DB missing the county_period table -> sqlite3.Error during
        # assembly (county row present) -> route maps to 503.
        broken_path = Path(self.directory.name) / "broken.sqlite"
        connection = sqlite3.connect(":memory:")
        connection.executescript(
            "CREATE TABLE county (county_fips TEXT PRIMARY KEY, state_fips TEXT, "
            "county_name TEXT, state_name TEXT, state_abbr TEXT);"
        )
        connection.execute("INSERT INTO county VALUES ('10001','10','0','','AL')")
        connection.commit()
        disk = sqlite3.connect(broken_path)
        connection.backup(disk)
        disk.close()
        connection.close()

        app.dependency_overrides[explorer_module.get_explorer_connection] = override_factory(
            broken_path
        )
        with TestClient(app) as client:
            response = client.get("/api/v1/counties/10001/explorer")
        self.assertEqual(response.status_code, 503)

    def test_structural_data_gap_returns_503(self):
        connection = sqlite3.connect(self.database_path)
        try:
            connection.execute("DELETE FROM dimension_definition")
            connection.commit()
        finally:
            connection.close()
        with TestClient(app) as client:
            response = client.get("/api/v1/counties/10001/explorer")
        self.assertEqual(response.status_code, 503)

    def test_database_open_failure_returns_503(self):
        app.dependency_overrides.clear()
        with mock.patch.object(
            explorer_module,
            "open_readonly_connection",
            side_effect=sqlite3.OperationalError("unable to open database file"),
        ):
            with TestClient(app) as client:
                response = client.get("/api/v1/counties/10001/explorer")
        self.assertEqual(response.status_code, 503)

    def test_read_only_database_digest_unchanged(self):
        before = file_sha256(self.database_path)
        with TestClient(app) as client:
            client.get("/api/v1/counties/10001/explorer")
            client.get("/api/v1/counties/20002/explorer")
            client.get("/api/v1/counties/99999/explorer")
        self.assertEqual(file_sha256(self.database_path), before)

    def test_repeated_requests_are_deterministic(self):
        with TestClient(app) as client:
            first = client.get("/api/v1/counties/10001/explorer").json()
            second = client.get("/api/v1/counties/10001/explorer").json()
        self.assertEqual(first, second)


class CountyExplorerProductionTest(unittest.TestCase):
    def setUp(self):
        if not SOURCE_DATABASE.exists():
            self.skipTest(f"Canonical database not found: {SOURCE_DATABASE}")

    def test_known_county_and_universe_intact_without_mutation(self):
        before = file_sha256(SOURCE_DATABASE)
        with TestClient(app) as client:
            explorer = client.get("/api/v1/counties/01001/explorer")
            counties = client.get("/api/v1/counties")
            unknown = client.get("/api/v1/counties/00000/explorer")
            malformed = client.get("/api/v1/counties/abcde/explorer")
        after = file_sha256(SOURCE_DATABASE)

        self.assertEqual(explorer.status_code, 200)
        model = ExplorerResponse.model_validate(explorer.json())
        self.assertEqual(model.county.county_fips, "01001")
        self.assertEqual(model.county.county_name, "0")   # verbatim canonical placeholder
        self.assertEqual(model.county.state_name, "")
        self.assertEqual(model.period.value, "v0.1")
        self.assertEqual(model.period.completeness_status, "complete")
        for dimension in (
            model.access_profile.primary_care,
            model.access_profile.dental,
            model.access_profile.mental_health,
            model.access_profile.mua_p,
        ):
            self.assertTrue(dimension.available)
            self.assertIsInstance(dimension.score, float)
        self.assertTrue(model.access_profile.primary_care.normalized)
        self.assertFalse(model.access_profile.mua_p.normalized)
        self.assertIsNone(model.access_profile.mua_p.primary_measure.normalized_value)
        self.assertEqual(model.experimental_composite.status, "experimental_provisional")
        self.assertEqual(model.experimental_composite.missing_dimensions, [])
        self.assertEqual(len(model.provenance.sources), 4)
        self.assertEqual(model.methodology.methodology_version, "v0.1")
        self.assertEqual(
            model.methodology.normalization_method, "county_percentile_rank_average"
        )

        # CE-B01 endpoint still intact.
        self.assertEqual(counties.status_code, 200)
        self.assertEqual(counties.json()["count"], EXPECTED_COUNTY_COUNT)

        self.assertEqual(unknown.status_code, 404)
        self.assertEqual(malformed.status_code, 422)

        self.assertEqual(before, after)
        self.assertEqual(after, EXPECTED_PRODUCTION_SHA256)


if __name__ == "__main__":
    unittest.main()
