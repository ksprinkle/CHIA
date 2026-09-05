"""CE-E09 tests for GET /api/v1/states/{state_fips}/dimension-scores.

unittest, matching the existing CE-B01 / CE-B02 suites: an in-memory
canonical-schema subset backed to a temp file, FastAPI ``TestClient`` with a
dependency override, digest-based read-only checks, and a guarded production
integration test. No copy or mutation of the canonical ``chia_v01.sqlite``.

This endpoint returns persisted ``dimension_score`` values verbatim; it
performs no analytical calculation and never writes to the database.
"""

from __future__ import annotations

from collections.abc import Iterator
import hashlib
from pathlib import Path
import sqlite3
import tempfile
import unittest

from fastapi.testclient import TestClient

import app.api.v1.state_scores as state_scores_module
from app.db import open_readonly_connection
from app.main import app
from app.schemas.state_scores import StateDimensionScoresResponse
from app.services.state_scores import (
    StateNotFoundError,
    load_state_dimension_scores,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DATABASE = PROJECT_ROOT / "Data" / "Model" / "chia_v01.sqlite"
EXPECTED_PRODUCTION_SHA256 = (
    "12b3525e77cdc85ba7fedbb463fcc75f21c489825c0e81d98cdf71a2b7c7174c"
)
EXPECTED_COUNTY_COUNT = 3143

MV = "v0.1"
DIMENSION_IDS = ("PRIMARY_CARE", "DENTAL", "MENTAL_HEALTH", "MUA_P")
RESPONSE_KEYS = ("primary_care", "dental", "mental_health", "mua_p")

# Minimal subset of Data/Model/schema.sql needed by this endpoint.
SCHEMA_SQL = """
CREATE TABLE county (
    county_fips TEXT PRIMARY KEY, state_fips TEXT NOT NULL, county_name TEXT NOT NULL,
    state_name TEXT NOT NULL, state_abbr TEXT NOT NULL
);
CREATE TABLE county_period (
    county_period_id INTEGER PRIMARY KEY, county_fips TEXT NOT NULL, period TEXT NOT NULL,
    completeness_status TEXT
);
CREATE TABLE dimension_score (
    county_period_id INTEGER NOT NULL, dimension_id TEXT NOT NULL, score REAL,
    methodology_version TEXT NOT NULL, status TEXT,
    PRIMARY KEY (county_period_id, dimension_id, methodology_version)
);
"""

# state 01: two counties, fully scored, inserted out of FIPS order.
# state 06: one county, DENTAL score missing entirely + no MUA_P row.
# state 12: one county with a county_period but zero dimension_score rows.
# state 20: one county with NO county_period row at all.
BASE_SCORES = {"PRIMARY_CARE": 12.5, "DENTAL": 0.0, "MENTAL_HEALTH": 88.0, "MUA_P": 99.75}


def file_sha256(path: Path | str) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build_db(path: Path) -> None:
    connection = sqlite3.connect(":memory:")
    connection.executescript(SCHEMA_SQL)

    rows = [
        # (county_fips, state_fips, county_period_id, completeness_status, scored_dims)
        ("01003", "01", 3, "complete", DIMENSION_IDS),
        ("01001", "01", 1, "complete", DIMENSION_IDS),
        ("06075", "06", 5, "partial", ("PRIMARY_CARE", "MENTAL_HEALTH")),
        ("12086", "12", 8, "complete", ()),        # county_period, no scores
        ("20001", "20", None, None, ()),           # no county_period at all
    ]
    for county_fips, state_fips, cp_id, completeness, scored in rows:
        connection.execute(
            "INSERT INTO county VALUES (?, ?, ?, ?, ?)",
            (county_fips, state_fips, "0", "", "XX"),
        )
        if cp_id is not None:
            connection.execute(
                "INSERT INTO county_period VALUES (?, ?, ?, ?)",
                (cp_id, county_fips, MV, completeness),
            )
            for dimension_id in scored:
                connection.execute(
                    "INSERT INTO dimension_score VALUES (?, ?, ?, ?, ?)",
                    (cp_id, dimension_id, BASE_SCORES[dimension_id], MV, "calculated"),
                )
    connection.commit()
    disk = sqlite3.connect(path)
    connection.backup(disk)
    disk.close()
    connection.close()


def override_factory(database_path: Path):
    def _dependency() -> Iterator[sqlite3.Connection]:
        connection = open_readonly_connection(database_path)
        try:
            yield connection
        finally:
            connection.close()

    return _dependency


class StateScoresServiceTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.directory.name) / "state_scores.sqlite"
        build_db(self.database_path)

    def tearDown(self):
        self.directory.cleanup()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.database_path)

    def test_returns_all_counties_for_state_fips_ascending(self):
        connection = self._connect()
        try:
            model = load_state_dimension_scores(connection, "01")
        finally:
            connection.close()

        self.assertIsInstance(model, StateDimensionScoresResponse)
        self.assertEqual(model.state_fips, "01")
        self.assertEqual(model.period, "v0.1")
        self.assertEqual(model.count, 2)
        self.assertEqual([c.county_fips for c in model.counties], ["01001", "01003"])

    def test_scores_and_statuses_are_verbatim(self):
        connection = self._connect()
        try:
            model = load_state_dimension_scores(connection, "01")
        finally:
            connection.close()

        county = model.counties[0]
        self.assertEqual(county.completeness_status, "complete")
        for response_key, dimension_id in zip(RESPONSE_KEYS, DIMENSION_IDS):
            entry = getattr(county, response_key)
            self.assertEqual(entry.dimension_id, dimension_id)
            self.assertTrue(entry.available)
            self.assertEqual(entry.score, BASE_SCORES[dimension_id])
            self.assertEqual(entry.score_status, "calculated")

    def test_genuine_zero_is_available_not_missing(self):
        connection = self._connect()
        try:
            model = load_state_dimension_scores(connection, "01")
        finally:
            connection.close()
        dental = model.counties[0].dental
        self.assertTrue(dental.available)
        self.assertEqual(dental.score, 0.0)

    def test_absent_dimension_score_row_is_unavailable(self):
        connection = self._connect()
        try:
            model = load_state_dimension_scores(connection, "06")
        finally:
            connection.close()

        county = model.counties[0]
        self.assertEqual(county.county_fips, "06075")
        self.assertEqual(county.completeness_status, "partial")
        self.assertTrue(county.primary_care.available)
        self.assertTrue(county.mental_health.available)
        for missing in (county.dental, county.mua_p):
            self.assertFalse(missing.available)
            self.assertIsNone(missing.score)
            self.assertIsNone(missing.score_status)

    def test_county_period_present_but_no_scores(self):
        connection = self._connect()
        try:
            model = load_state_dimension_scores(connection, "12")
        finally:
            connection.close()
        county = model.counties[0]
        self.assertEqual(county.completeness_status, "complete")
        for response_key in RESPONSE_KEYS:
            entry = getattr(county, response_key)
            self.assertFalse(entry.available)
            self.assertIsNone(entry.score)

    def test_county_without_county_period_is_still_returned(self):
        connection = self._connect()
        try:
            model = load_state_dimension_scores(connection, "20")
        finally:
            connection.close()
        self.assertEqual(model.count, 1)
        county = model.counties[0]
        self.assertEqual(county.county_fips, "20001")
        self.assertIsNone(county.completeness_status)
        for response_key in RESPONSE_KEYS:
            self.assertFalse(getattr(county, response_key).available)

    def test_unknown_state_raises_state_not_found(self):
        connection = self._connect()
        try:
            with self.assertRaises(StateNotFoundError):
                load_state_dimension_scores(connection, "99")
        finally:
            connection.close()

    def test_service_does_not_mutate_the_database(self):
        before = file_sha256(self.database_path)
        load_state_dimension_scores(str(self.database_path), "01")
        load_state_dimension_scores(Path(self.database_path), "06")
        self.assertEqual(file_sha256(self.database_path), before)


class StateScoresApiTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.directory.name) / "state_scores_api.sqlite"
        build_db(self.database_path)
        app.dependency_overrides[state_scores_module.get_state_scores_connection] = (
            override_factory(self.database_path)
        )

    def tearDown(self):
        app.dependency_overrides.clear()
        self.directory.cleanup()

    def test_known_state_returns_200_and_valid_model(self):
        with TestClient(app) as client:
            response = client.get("/api/v1/states/01/dimension-scores")
        self.assertEqual(response.status_code, 200)
        model = StateDimensionScoresResponse.model_validate(response.json())
        self.assertEqual(model.state_fips, "01")
        self.assertEqual(model.count, len(model.counties))
        self.assertEqual(model.count, 2)
        self.assertEqual([c.county_fips for c in model.counties], ["01001", "01003"])
        for county in model.counties:
            for response_key in RESPONSE_KEYS:
                self.assertTrue(getattr(county, response_key).available)

    def test_preserves_fips_as_strings(self):
        with TestClient(app) as client:
            payload = client.get("/api/v1/states/01/dimension-scores").json()
        self.assertIsInstance(payload["state_fips"], str)
        for county in payload["counties"]:
            self.assertIsInstance(county["county_fips"], str)
            self.assertRegex(county["county_fips"], r"^\d{5}$")

    def test_malformed_state_fips_returns_422(self):
        with TestClient(app) as client:
            for value in ("1", "123", "ab", "1a", "0"):
                response = client.get(f"/api/v1/states/{value}/dimension-scores")
                self.assertEqual(response.status_code, 422, value)

    def test_well_formed_unknown_state_returns_404(self):
        with TestClient(app) as client:
            response = client.get("/api/v1/states/99/dimension-scores")
        self.assertEqual(response.status_code, 404)
        self.assertIn("detail", response.json())

    def test_ordering_is_deterministic_and_idempotent(self):
        with TestClient(app) as client:
            first = client.get("/api/v1/states/01/dimension-scores").json()
            second = client.get("/api/v1/states/01/dimension-scores").json()
        fips = [c["county_fips"] for c in first["counties"]]
        self.assertEqual(fips, sorted(fips))
        self.assertEqual(first, second)

    def test_endpoint_is_read_only_database_digest_unchanged(self):
        before = file_sha256(self.database_path)
        with TestClient(app) as client:
            client.get("/api/v1/states/01/dimension-scores")
            client.get("/api/v1/states/06/dimension-scores")
        self.assertEqual(file_sha256(self.database_path), before)

    def test_structurally_unusable_database_returns_503(self):
        broken_path = Path(self.directory.name) / "broken.sqlite"
        connection = sqlite3.connect(":memory:")
        connection.executescript(
            "CREATE TABLE county (county_fips TEXT PRIMARY KEY, state_fips TEXT, "
            "county_name TEXT, state_name TEXT, state_abbr TEXT);"
        )
        connection.execute("INSERT INTO county VALUES ('01001','01','0','','XX')")
        connection.commit()
        disk = sqlite3.connect(broken_path)
        connection.backup(disk)
        disk.close()
        connection.close()

        app.dependency_overrides[state_scores_module.get_state_scores_connection] = (
            override_factory(broken_path)
        )
        with TestClient(app) as client:
            response = client.get("/api/v1/states/01/dimension-scores")
        self.assertEqual(response.status_code, 503)


class StateScoresProductionTest(unittest.TestCase):
    """Guarded integration test against the real canonical database."""

    def test_production_state_matches_direct_read_and_is_read_only(self):
        if not SOURCE_DATABASE.exists():
            self.skipTest(f"Canonical database not found: {SOURCE_DATABASE}")

        connection = sqlite3.connect(
            Path(SOURCE_DATABASE).resolve().as_uri() + "?mode=ro", uri=True
        )
        try:
            expected_count = connection.execute(
                "SELECT COUNT(*) FROM county WHERE state_fips = '01'"
            ).fetchone()[0]
            direct = {
                (row[0], row[1]): (row[2], row[3])
                for row in connection.execute(
                    """
                    SELECT c.county_fips, ds.dimension_id, ds.score, ds.status
                    FROM county c
                    JOIN county_period cp ON cp.county_fips = c.county_fips AND cp.period = 'v0.1'
                    JOIN dimension_score ds ON ds.county_period_id = cp.county_period_id
                                            AND ds.methodology_version = 'v0.1'
                    WHERE c.state_fips = '01'
                    """
                ).fetchall()
            }
        finally:
            connection.close()

        before = file_sha256(SOURCE_DATABASE)
        # No dependency override: exercise the real app against production.
        with TestClient(app) as client:
            response = client.get("/api/v1/states/01/dimension-scores")
        after = file_sha256(SOURCE_DATABASE)

        self.assertEqual(response.status_code, 200)
        model = StateDimensionScoresResponse.model_validate(response.json())
        self.assertEqual(model.state_fips, "01")
        self.assertEqual(model.period, "v0.1")
        self.assertEqual(model.count, expected_count)
        self.assertEqual(len(model.counties), expected_count)

        fips = [c.county_fips for c in model.counties]
        self.assertEqual(fips, sorted(fips))
        self.assertEqual(len(set(fips)), expected_count)

        for county in model.counties:
            self.assertEqual(len(county.county_fips), 5)
            self.assertTrue(county.county_fips.isdigit())
            for response_key, dimension_id in zip(RESPONSE_KEYS, DIMENSION_IDS):
                entry = getattr(county, response_key)
                self.assertEqual(entry.dimension_id, dimension_id)
                expected = direct.get((county.county_fips, dimension_id))
                if expected is None:
                    self.assertFalse(entry.available)
                    self.assertIsNone(entry.score)
                else:
                    self.assertEqual(entry.score, expected[0])
                    self.assertEqual(entry.score_status, expected[1])
                    self.assertEqual(entry.available, expected[0] is not None)

        # Read-only, byte-identical.
        self.assertEqual(before, after)
        self.assertEqual(after, EXPECTED_PRODUCTION_SHA256)

    def test_production_full_universe_across_all_states(self):
        if not SOURCE_DATABASE.exists():
            self.skipTest(f"Canonical database not found: {SOURCE_DATABASE}")

        connection = sqlite3.connect(
            Path(SOURCE_DATABASE).resolve().as_uri() + "?mode=ro", uri=True
        )
        try:
            state_fips_values = [
                row[0]
                for row in connection.execute(
                    "SELECT DISTINCT state_fips FROM county ORDER BY state_fips"
                ).fetchall()
            ]
        finally:
            connection.close()

        before = file_sha256(SOURCE_DATABASE)
        total = 0
        seen: set[str] = set()
        with TestClient(app) as client:
            for state_fips in state_fips_values:
                payload = client.get(
                    f"/api/v1/states/{state_fips}/dimension-scores"
                ).json()
                total += payload["count"]
                seen.update(c["county_fips"] for c in payload["counties"])
        after = file_sha256(SOURCE_DATABASE)

        self.assertEqual(len(state_fips_values), 51)
        self.assertEqual(total, EXPECTED_COUNTY_COUNT)
        self.assertEqual(len(seen), EXPECTED_COUNTY_COUNT)
        self.assertEqual(before, after)
        self.assertEqual(after, EXPECTED_PRODUCTION_SHA256)


if __name__ == "__main__":
    unittest.main()
