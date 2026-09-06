"""CE-E14a tests for GET /api/v1/states/dimension-scores.

The endpoint returns, per state, a display-only median of that state's
counties' persisted ``dimension_score.score`` for the v0.1 period. It performs
no CHIA analytical calculation, persists nothing, and never writes to the
database.

unittest, matching CE-E09: an in-memory canonical-schema subset backed to a
temp file, FastAPI ``TestClient`` with a dependency override, digest-based
read-only checks, and a guarded production integration test that cross-checks
the medians against a direct read. No copy or mutation of the canonical
``chia_v01.sqlite``; the six existing production SHA-256 anchors are untouched.
"""

from __future__ import annotations

from collections.abc import Iterator
import hashlib
from pathlib import Path
from statistics import median
import sqlite3
import tempfile
import unittest

from fastapi.testclient import TestClient

import app.api.v1.national_scores as national_scores_module
from app.db import open_readonly_connection
from app.main import app
from app.schemas.national_scores import NationalDimensionScoresResponse
from app.services.national_scores import load_national_dimension_scores


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DATABASE = PROJECT_ROOT / "Data" / "Model" / "chia_v01.sqlite"
EXPECTED_PRODUCTION_SHA256 = (
    "12b3525e77cdc85ba7fedbb463fcc75f21c489825c0e81d98cdf71a2b7c7174c"
)
EXPECTED_STATE_COUNT = 51
EXPECTED_COUNTY_COUNT = 3143

MV = "v0.1"
DIMENSION_IDS = ("PRIMARY_CARE", "DENTAL", "MENTAL_HEALTH", "MUA_P")
RESPONSE_KEYS = ("primary_care", "dental", "mental_health", "mua_p")

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

# state 01: 3 counties, PRIMARY_CARE [10, 20, 90] -> median 20 (odd n)
# state 02: 2 counties, PRIMARY_CARE [40, 60]     -> median 50 (even n -> mean)
# state 04: 1 county,   PRIMARY_CARE [77]         -> median 77 (n == 1)
# state 05: 2 counties, PRIMARY_CARE [null, 30]   -> median 30, available_county_count 1
# state 06: 1 county, county_period but NO dimension_score rows -> all dims null
# state 07: 1 county, no county_period at all                   -> all dims null
_FIXTURE = {
    "01": [
        {"cp": 11, "scores": {"PRIMARY_CARE": 10.0, "DENTAL": 0.0, "MENTAL_HEALTH": 5.0, "MUA_P": 100.0}},
        {"cp": 12, "scores": {"PRIMARY_CARE": 20.0, "DENTAL": 0.0, "MENTAL_HEALTH": 5.0, "MUA_P": 50.0}},
        {"cp": 13, "scores": {"PRIMARY_CARE": 90.0, "DENTAL": 0.0, "MENTAL_HEALTH": 5.0, "MUA_P": 0.0}},
    ],
    "02": [
        {"cp": 21, "scores": {"PRIMARY_CARE": 40.0, "DENTAL": 1.0, "MENTAL_HEALTH": 2.0, "MUA_P": 3.0}},
        {"cp": 22, "scores": {"PRIMARY_CARE": 60.0, "DENTAL": 3.0, "MENTAL_HEALTH": 4.0, "MUA_P": 5.0}},
    ],
    "04": [
        {"cp": 41, "scores": {"PRIMARY_CARE": 77.0, "DENTAL": 12.0, "MENTAL_HEALTH": 33.0, "MUA_P": 44.0}},
    ],
    "05": [
        {"cp": 51, "scores": {"PRIMARY_CARE": None, "DENTAL": None, "MENTAL_HEALTH": None, "MUA_P": None}},
        {"cp": 52, "scores": {"PRIMARY_CARE": 30.0, "DENTAL": None, "MENTAL_HEALTH": None, "MUA_P": None}},
    ],
    "06": [{"cp": 61, "scores": {}}],   # county_period, zero dimension_score rows
    "07": [{"cp": None, "scores": {}}],  # no county_period
}


def file_sha256(path: Path | str) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build_db(path: Path) -> None:
    connection = sqlite3.connect(":memory:")
    connection.executescript(SCHEMA_SQL)
    county_seq = 0
    for state_fips, counties in _FIXTURE.items():
        for county in counties:
            county_seq += 1
            county_fips = f"{state_fips}{county_seq:03d}"
            connection.execute(
                "INSERT INTO county VALUES (?, ?, ?, ?, ?)",
                (county_fips, state_fips, "0", "", "XX"),
            )
            cp_id = county["cp"]
            if cp_id is None:
                continue
            connection.execute(
                "INSERT INTO county_period VALUES (?, ?, ?, ?)",
                (cp_id, county_fips, MV, "complete"),
            )
            for dimension_id, score in county["scores"].items():
                connection.execute(
                    "INSERT INTO dimension_score VALUES (?, ?, ?, ?, ?)",
                    (cp_id, dimension_id, score, MV, "calculated"),
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


class NationalScoresServiceTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.directory.name) / "national_scores.sqlite"
        build_db(self.database_path)

    def tearDown(self):
        self.directory.cleanup()

    def _load(self) -> NationalDimensionScoresResponse:
        connection = open_readonly_connection(self.database_path)
        try:
            return load_national_dimension_scores(connection)
        finally:
            connection.close()

    def test_every_state_is_represented_in_ascending_order(self):
        model = self._load()
        self.assertEqual(model.period, "v0.1")
        self.assertEqual(model.count, len(_FIXTURE))
        fips = [s.state_fips for s in model.states]
        self.assertEqual(fips, sorted(_FIXTURE))
        self.assertEqual(len(set(fips)), len(fips))
        self.assertIn("median", model.aggregation.lower())

    def test_primary_care_medians_odd_even_singleton_and_partial_null(self):
        by_fips = {s.state_fips: s for s in self._load().states}

        odd = by_fips["01"].primary_care
        self.assertEqual(odd.median, 20.0)          # median([10, 20, 90])
        self.assertTrue(odd.available)
        self.assertEqual(odd.county_count, 3)
        self.assertEqual(odd.available_county_count, 3)

        even = by_fips["02"].primary_care
        self.assertEqual(even.median, 50.0)         # mean(40, 60)
        self.assertEqual(even.available_county_count, 2)

        singleton = by_fips["04"].primary_care
        self.assertEqual(singleton.median, 77.0)
        self.assertEqual(singleton.available_county_count, 1)

        partial = by_fips["05"].primary_care
        self.assertEqual(partial.median, 30.0)      # the one non-null county
        self.assertTrue(partial.available)
        self.assertEqual(partial.county_count, 2)
        self.assertEqual(partial.available_county_count, 1)

    def test_states_with_no_available_score_report_null(self):
        by_fips = {s.state_fips: s for s in self._load().states}

        # state 05: DENTAL / MENTAL_HEALTH / MUA_P are all NULL for both counties
        for key in ("dental", "mental_health", "mua_p"):
            entry = getattr(by_fips["05"], key)
            self.assertIsNone(entry.median)
            self.assertFalse(entry.available)
            self.assertEqual(entry.available_county_count, 0)
            self.assertEqual(entry.county_count, 2)

        # state 06: county_period present, zero dimension_score rows
        # state 07: no county_period at all
        for state_fips in ("06", "07"):
            state = by_fips[state_fips]
            for key in RESPONSE_KEYS:
                entry = getattr(state, key)
                self.assertIsNone(entry.median)
                self.assertFalse(entry.available)
                self.assertEqual(entry.available_county_count, 0)
                self.assertEqual(entry.county_count, 1)

    def test_mua_p_is_medianed_on_its_own_values_like_any_other_dimension(self):
        by_fips = {s.state_fips: s for s in self._load().states}
        self.assertEqual(by_fips["01"].mua_p.median, 50.0)   # median([100, 50, 0])
        self.assertEqual(by_fips["01"].mua_p.dimension_id, "MUA_P")

    def test_dimension_ids_and_order(self):
        state = self._load().states[0]
        self.assertEqual(
            [getattr(state, key).dimension_id for key in RESPONSE_KEYS],
            list(DIMENSION_IDS),
        )


class NationalScoresApiTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.directory.name) / "national_scores.sqlite"
        build_db(self.database_path)
        app.dependency_overrides[
            national_scores_module.get_national_scores_connection
        ] = override_factory(self.database_path)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.directory.cleanup()

    def test_returns_200_with_the_full_state_set(self):
        with TestClient(app) as client:
            response = client.get("/api/v1/states/dimension-scores")
        self.assertEqual(response.status_code, 200)
        model = NationalDimensionScoresResponse.model_validate(response.json())
        self.assertEqual(model.count, len(_FIXTURE))
        self.assertEqual([s.state_fips for s in model.states], sorted(_FIXTURE))

    def test_does_not_collide_with_the_ce_e09_per_state_route(self):
        with TestClient(app) as client:
            national = client.get("/api/v1/states/dimension-scores")
            # A real 2-digit state still resolves to the CE-E09 shape.
            per_state = client.get("/api/v1/states/01/dimension-scores")
        self.assertEqual(national.status_code, 200)
        self.assertIn("states", national.json())
        self.assertEqual(per_state.status_code, 200)
        self.assertIn("counties", per_state.json())

    def test_structurally_unusable_database_returns_503(self):
        # A database missing the dimension_score table -> sqlite3.Error during
        # assembly -> the router maps it to 503 (mirrors CE-E09).
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

        app.dependency_overrides[
            national_scores_module.get_national_scores_connection
        ] = override_factory(broken_path)
        with TestClient(app) as client:
            response = client.get("/api/v1/states/dimension-scores")
        self.assertEqual(response.status_code, 503)

    def test_read_only_digest_unchanged(self):
        before = file_sha256(self.database_path)
        with TestClient(app) as client:
            client.get("/api/v1/states/dimension-scores")
            client.get("/api/v1/states/dimension-scores")
        self.assertEqual(file_sha256(self.database_path), before)


class NationalScoresProductionTest(unittest.TestCase):
    """Guarded integration test against the real canonical database."""

    def test_production_matches_direct_median_read_and_is_read_only(self):
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
                )
            ]
            county_total = connection.execute("SELECT COUNT(*) FROM county").fetchone()[0]
            direct: dict[tuple[str, str], list[float]] = {}
            for state_fips, dimension_id, score in connection.execute(
                """
                SELECT c.state_fips, ds.dimension_id, ds.score
                FROM county c
                JOIN county_period cp ON cp.county_fips = c.county_fips AND cp.period = 'v0.1'
                JOIN dimension_score ds ON ds.county_period_id = cp.county_period_id
                                        AND ds.methodology_version = 'v0.1'
                WHERE ds.score IS NOT NULL
                """
            ):
                direct.setdefault((state_fips, dimension_id), []).append(float(score))
        finally:
            connection.close()

        before = file_sha256(SOURCE_DATABASE)
        with TestClient(app) as client:  # no dependency override -> real app / real DB
            response = client.get("/api/v1/states/dimension-scores")
        after = file_sha256(SOURCE_DATABASE)

        self.assertEqual(response.status_code, 200)
        model = NationalDimensionScoresResponse.model_validate(response.json())
        self.assertEqual(model.period, "v0.1")
        self.assertEqual(model.count, EXPECTED_STATE_COUNT)
        self.assertEqual(len(state_fips_values), EXPECTED_STATE_COUNT)
        self.assertEqual(county_total, EXPECTED_COUNTY_COUNT)

        returned_fips = [s.state_fips for s in model.states]
        self.assertEqual(returned_fips, sorted(state_fips_values))

        checked = 0
        for state in model.states:
            for response_key, dimension_id in zip(RESPONSE_KEYS, DIMENSION_IDS):
                entry = getattr(state, response_key)
                self.assertEqual(entry.dimension_id, dimension_id)
                values = direct.get((state.state_fips, dimension_id), [])
                self.assertEqual(entry.available_county_count, len(values))
                self.assertEqual(entry.available, bool(values))
                if values:
                    self.assertEqual(entry.median, median(values))
                    self.assertGreaterEqual(entry.median, 0.0)
                    self.assertLessEqual(entry.median, 100.0000001)
                    checked += 1
                else:
                    self.assertIsNone(entry.median)
        self.assertGreater(checked, 0)

        # Read-only, byte-identical, and the canonical hash is unchanged.
        self.assertEqual(before, after)
        self.assertEqual(after, EXPECTED_PRODUCTION_SHA256)


if __name__ == "__main__":
    unittest.main()
