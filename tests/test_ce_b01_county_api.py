"""CE-B01 tests for the read-only County API (GET /api/v1/counties).

unittest-based, matching the existing CE-A00..A06 suites: in-memory SQLite
schema builders, temporary on-disk copies, digest-based read-only checks, and
a production-database existence guard for the full-universe integration checks.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
import sqlite3
import tempfile
import unittest

from fastapi.testclient import TestClient

from app.db import get_readonly_connection, open_readonly_connection
from app.main import app
from app.schemas.county import CountyListResponse
from app.services.county_directory import (
    CountyDirectoryError,
    CountyRecord,
    load_county_directory,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DATABASE = PROJECT_ROOT / "Data" / "Model" / "chia_v01.sqlite"

EXPECTED_COUNTY_COUNT = 3143
EXPECTED_PRODUCTION_SHA256 = (
    "12b3525e77cdc85ba7fedbb463fcc75f21c489825c0e81d98cdf71a2b7c7174c"
)

# Exact canonical `county` schema (Data/Model/schema.sql).
COUNTY_SCHEMA_SQL = """
CREATE TABLE county (
    county_fips TEXT PRIMARY KEY,
    state_fips TEXT NOT NULL,
    county_name TEXT NOT NULL,
    state_name TEXT NOT NULL,
    state_abbr TEXT NOT NULL
);
"""

# Placeholder names mirror the current canonical database (county_name='0',
# state_name=''); intentionally inserted out of FIPS order.
PLACEHOLDER_ROWS = [
    ("01003", "01", "0", "", "AL"),
    ("01001", "01", "0", "", "AL"),
    ("06075", "06", "0", "", "CA"),
    ("02013", "02", "0", "", "AK"),
]
PLACEHOLDER_FIPS_SORTED = ["01001", "01003", "02013", "06075"]

# Real-looking names to prove verbatim passthrough (not just the '0' placeholder).
NAMED_ROWS = [
    ("12086", "12", "Miami-Dade County", "Florida", "FL"),
    ("36061", "36", "New York County", "New York", "NY"),
]


def file_sha256(path: Path | str) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build_memory_county_db(rows) -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.executescript(COUNTY_SCHEMA_SQL)
    connection.executemany(
        "INSERT INTO county (county_fips, state_fips, county_name, state_name, state_abbr) VALUES (?, ?, ?, ?, ?)",
        rows,
    )
    connection.commit()
    return connection


def write_to_disk(connection: sqlite3.Connection, path: Path) -> None:
    disk_connection = sqlite3.connect(path)
    connection.backup(disk_connection)
    disk_connection.close()
    connection.close()


def synthetic_rows(count: int) -> list[tuple]:
    return [
        (f"{index + 1:05d}", f"{(index % 99) + 1:02d}", "0", "", "XX")
        for index in range(count)
    ]


class CountyDirectoryServiceTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.directory.cleanup()

    def _disk_db(self, rows) -> Path:
        path = Path(self.directory.name) / "county.sqlite"
        write_to_disk(build_memory_county_db(rows), path)
        return path

    def test_service_returns_expected_canonical_shape(self):
        connection = build_memory_county_db(PLACEHOLDER_ROWS)
        try:
            records = load_county_directory(connection)
        finally:
            connection.close()

        self.assertEqual(len(records), len(PLACEHOLDER_ROWS))
        self.assertTrue(all(isinstance(record, CountyRecord) for record in records))
        first = records[0]
        self.assertEqual(
            set(vars(first)),
            {"county_fips", "state_fips", "state_abbr", "county_name", "state_name"},
        )
        for record in records:
            for value in vars(record).values():
                self.assertIsInstance(value, str)

    def test_service_orders_by_county_fips_ascending(self):
        connection = build_memory_county_db(PLACEHOLDER_ROWS)
        try:
            records = load_county_directory(connection)
        finally:
            connection.close()
        self.assertEqual([r.county_fips for r in records], PLACEHOLDER_FIPS_SORTED)

    def test_service_preserves_fips_as_five_char_numeric_strings(self):
        connection = build_memory_county_db(PLACEHOLDER_ROWS)
        try:
            records = load_county_directory(connection)
        finally:
            connection.close()
        for record in records:
            self.assertIsInstance(record.county_fips, str)
            self.assertEqual(len(record.county_fips), 5)
            self.assertTrue(record.county_fips.isdigit())

    def test_service_preserves_state_fips_and_abbr(self):
        connection = build_memory_county_db(PLACEHOLDER_ROWS)
        try:
            records = load_county_directory(connection)
        finally:
            connection.close()
        by_fips = {r.county_fips: r for r in records}
        self.assertEqual(by_fips["06075"].state_fips, "06")
        self.assertEqual(by_fips["06075"].state_abbr, "CA")
        self.assertEqual(by_fips["02013"].state_fips, "02")
        self.assertEqual(by_fips["02013"].state_abbr, "AK")

    def test_service_returns_names_exactly_as_stored(self):
        placeholder_connection = build_memory_county_db(PLACEHOLDER_ROWS)
        try:
            placeholder = load_county_directory(placeholder_connection)
        finally:
            placeholder_connection.close()
        for record in placeholder:
            self.assertEqual(record.county_name, "0")
            self.assertEqual(record.state_name, "")

        named_connection = build_memory_county_db(NAMED_ROWS)
        try:
            named = load_county_directory(named_connection)
        finally:
            named_connection.close()
        by_fips = {r.county_fips: r for r in named}
        self.assertEqual(by_fips["12086"].county_name, "Miami-Dade County")
        self.assertEqual(by_fips["12086"].state_name, "Florida")
        self.assertEqual(by_fips["36061"].county_name, "New York County")
        self.assertEqual(by_fips["36061"].state_name, "New York")

    def test_service_does_not_mutate_the_database(self):
        path = self._disk_db(PLACEHOLDER_ROWS)
        before = file_sha256(path)
        load_county_directory(str(path))
        load_county_directory(Path(path))
        self.assertEqual(file_sha256(path), before)

    def test_service_rejects_non_five_character_fips(self):
        connection = build_memory_county_db([("0100", "01", "0", "", "AL")])
        try:
            with self.assertRaises(CountyDirectoryError):
                load_county_directory(connection)
        finally:
            connection.close()

    def test_service_rejects_empty_universe(self):
        connection = build_memory_county_db([])
        try:
            with self.assertRaises(CountyDirectoryError):
                load_county_directory(connection)
        finally:
            connection.close()

    def test_service_returns_full_universe_from_production_database(self):
        if not SOURCE_DATABASE.exists():
            self.skipTest(f"Canonical database not found: {SOURCE_DATABASE}")

        before = file_sha256(SOURCE_DATABASE)
        records = load_county_directory(str(SOURCE_DATABASE))
        after = file_sha256(SOURCE_DATABASE)

        self.assertEqual(len(records), EXPECTED_COUNTY_COUNT)
        fips = [r.county_fips for r in records]
        self.assertEqual(fips, sorted(fips))
        self.assertEqual(len(set(fips)), EXPECTED_COUNTY_COUNT)
        for record in records:
            self.assertIsInstance(record.county_fips, str)
            self.assertEqual(len(record.county_fips), 5)
            self.assertTrue(record.county_fips.isdigit())
            self.assertIsInstance(record.state_fips, str)
            self.assertIsInstance(record.state_abbr, str)
        # Names come back exactly as stored. CE-D01 Issue 2 corrected the
        # canonical county_name/state_name from a placeholder to real,
        # Census-sourced values (see
        # tests/test_ce_d01_county_reference_correction.py for the full
        # naming-convention regression coverage); this test only re-asserts
        # that every row now has *some* non-placeholder name, still verbatim.
        self.assertTrue(all(r.county_name != "0" for r in records))
        self.assertTrue(all(r.state_name != "" for r in records))
        # Read-only.
        self.assertEqual(before, after)
        self.assertEqual(after, EXPECTED_PRODUCTION_SHA256)


class CountyApiEndpointTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.directory.name) / "county_api.sqlite"

    def tearDown(self):
        app.dependency_overrides.clear()
        self.directory.cleanup()

    def _use_database(self, rows) -> None:
        write_to_disk(build_memory_county_db(rows), self.database_path)

        def _override():
            connection = open_readonly_connection(self.database_path)
            try:
                yield connection
            finally:
                connection.close()

        app.dependency_overrides[get_readonly_connection] = _override

    def test_endpoint_returns_http_200(self):
        self._use_database(PLACEHOLDER_ROWS)
        with TestClient(app) as client:
            response = client.get("/api/v1/counties")
        self.assertEqual(response.status_code, 200)

    def test_response_is_valid_against_pydantic_model(self):
        self._use_database(PLACEHOLDER_ROWS)
        with TestClient(app) as client:
            payload = client.get("/api/v1/counties").json()

        model = CountyListResponse.model_validate(payload)
        self.assertEqual(model.count, len(model.counties))
        self.assertEqual(model.count, len(PLACEHOLDER_ROWS))
        self.assertEqual(
            [county.county_fips for county in model.counties], PLACEHOLDER_FIPS_SORTED
        )

    def test_endpoint_returns_expected_county_count(self):
        rows = synthetic_rows(250)
        self._use_database(rows)
        with TestClient(app) as client:
            payload = client.get("/api/v1/counties").json()
        self.assertEqual(payload["count"], 250)
        self.assertEqual(len(payload["counties"]), 250)

    def test_endpoint_preserves_fips_as_strings(self):
        self._use_database(PLACEHOLDER_ROWS)
        with TestClient(app) as client:
            payload = client.get("/api/v1/counties").json()
        for county in payload["counties"]:
            self.assertIsInstance(county["county_fips"], str)
            self.assertRegex(county["county_fips"], r"^\d{5}$")

    def test_endpoint_ordering_is_deterministic(self):
        self._use_database(PLACEHOLDER_ROWS)
        with TestClient(app) as client:
            first = client.get("/api/v1/counties").json()
            second = client.get("/api/v1/counties").json()
        fips = [county["county_fips"] for county in first["counties"]]
        self.assertEqual(fips, sorted(fips))
        self.assertEqual(first, second)

    def test_endpoint_returns_names_exactly_as_stored(self):
        self._use_database(PLACEHOLDER_ROWS)
        with TestClient(app) as client:
            payload = client.get("/api/v1/counties").json()
        for county in payload["counties"]:
            self.assertEqual(county["county_name"], "0")
            self.assertEqual(county["state_name"], "")

    def test_endpoint_is_read_only_database_digest_unchanged(self):
        self._use_database(synthetic_rows(50))
        before = file_sha256(self.database_path)
        with TestClient(app) as client:
            client.get("/api/v1/counties")
            client.get("/api/v1/counties")
        self.assertEqual(file_sha256(self.database_path), before)

    def test_production_endpoint_returns_full_canonical_universe(self):
        if not SOURCE_DATABASE.exists():
            self.skipTest(f"Canonical database not found: {SOURCE_DATABASE}")

        # No dependency override: exercises the real app against production.
        before = file_sha256(SOURCE_DATABASE)
        with TestClient(app) as client:
            response = client.get("/api/v1/counties")
        after = file_sha256(SOURCE_DATABASE)

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        model = CountyListResponse.model_validate(payload)
        self.assertEqual(model.count, EXPECTED_COUNTY_COUNT)
        self.assertEqual(len(model.counties), EXPECTED_COUNTY_COUNT)
        fips = [county.county_fips for county in model.counties]
        self.assertEqual(fips, sorted(fips))
        self.assertEqual(len(set(fips)), EXPECTED_COUNTY_COUNT)
        for county in model.counties:
            self.assertEqual(len(county.county_fips), 5)
            self.assertTrue(county.county_fips.isdigit())

        self.assertEqual(before, after)
        self.assertEqual(after, EXPECTED_PRODUCTION_SHA256)


if __name__ == "__main__":
    unittest.main()
