"""CE-D01 Issue 2 regression: canonical county_name/state_name correction.

Before this correction, every one of the canonical database's 3,143 `county`
rows had `county_name = '0'` and `state_name = ''` (a placeholder from the
Primary Care HPSA source file's own broken `CountyName` column; see the
CE-D01 Issue 2 investigation). `Data/Model/build_v01_database.py` now
resolves both fields from the U.S. Census Bureau's 2020 PL 94-171
redistricting geoheader files (`county_name` from the county-level AREANAME,
already correctly suffixed per entity type -- County / Parish / Borough /
Census Area / Municipality / independent city -- with no suffix appended or
guessed here), except the 9 Connecticut planning-region FIPS that scheme
predates, which use the already-validated PLACES base name normalized to the
approved "<Name> Planning Region" form. `state_abbr` is untouched.

This file is the dedicated regression coverage for that correction. It is a
guarded production-integration suite (skipped if the canonical database is
not present), matching the pattern already used by
`CountyExplorerProductionTest` / `CountyApiEndpointTest`.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
import sqlite3
import unittest

from fastapi.testclient import TestClient

from app.main import app
from app.schemas.county import CountyListResponse
from app.schemas.explorer import ExplorerResponse


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DATABASE = PROJECT_ROOT / "Data" / "Model" / "chia_v01.sqlite"
EXPECTED_PRODUCTION_SHA256 = (
    "0d8bb417ccf72acf0cef7d17bcca15627900d0df419fc259de553a95b9aa2966"
)
EXPECTED_COUNTY_COUNT = 3143

# One representative FIPS per entity type the Census AREANAME must resolve
# correctly, spanning every suffix category found in the canonical universe.
REPRESENTATIVE_NAMES = {
    "01001": ("Autauga County", "Alabama"),          # ordinary county
    "06075": ("San Francisco County", "California"),  # ordinary county, well-known
    "22001": ("Acadia Parish", "Louisiana"),           # Louisiana parish
    "02020": ("Anchorage Municipality", "Alaska"),     # Alaska municipality
    "02013": ("Aleutians East Borough", "Alaska"),     # Alaska borough
    "02016": ("Aleutians West Census Area", "Alaska"),  # Alaska census area
    "51710": ("Norfolk city", "Virginia"),              # Virginia independent city
    "29510": ("St. Louis city", "Missouri"),            # Missouri independent city
    "24510": ("Baltimore city", "Maryland"),            # Maryland independent city
    "11001": ("District of Columbia", "District of Columbia"),  # DC
}

# The 9 Connecticut planning-region FIPS the 2020 Census geoheader predates
# (patched from the already-validated PLACES dataset; see
# Data/Model/build_v01_database.py::CONNECTICUT_PLANNING_REGION_BASE_NAMES).
CONNECTICUT_PLANNING_REGIONS = {
    "09110": "Capitol Planning Region",
    "09120": "Greater Bridgeport Planning Region",
    "09130": "Lower Connecticut River Valley Planning Region",
    "09140": "Naugatuck Valley Planning Region",
    "09150": "Northeastern Connecticut Planning Region",
    "09160": "Northwest Hills Planning Region",
    "09170": "South Central Connecticut Planning Region",
    "09180": "Southeastern Connecticut Planning Region",
    "09190": "Western Connecticut Planning Region",
}

# county_fips -> (dimension_id, PRIMARY_CARE score) / composite_value that
# were true before this correction and must remain true after it: this
# section of the fix only ever touches `county.county_name` /
# `county.state_name` / `county.state_fips` -- never analytical tables.
UNCHANGED_ANALYTICAL_SPOT_CHECKS = {
    "01001": {
        "primary_care_score": 88.75776397515529,
        "composite_value": 60.33982168297841,
    },
}

# Row counts for every analytical table, unaffected by this correction.
EXPECTED_ANALYTICAL_ROW_COUNTS = {
    "observation": 59717,
    "normalized_measure": 9429,
    "dimension_score": 12572,
    "composite_score": 3143,
    "county_period": 3143,
    "variable_definition": 19,
    "dimension_definition": 4,
    "source": 4,
    "methodology": 1,
}


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class CountyReferenceCorrectionTest(unittest.TestCase):
    def setUp(self):
        if not SOURCE_DATABASE.exists():
            self.skipTest(f"Canonical database not found: {SOURCE_DATABASE}")

    def _connection(self) -> sqlite3.Connection:
        uri = SOURCE_DATABASE.resolve().as_uri() + "?mode=ro"
        return sqlite3.connect(uri, uri=True)

    def test_full_3143_row_coverage_with_no_duplicates(self):
        connection = self._connection()
        try:
            rows = connection.execute(
                "SELECT county_fips, county_name, state_name, state_abbr FROM county"
            ).fetchall()
        finally:
            connection.close()

        self.assertEqual(len(rows), EXPECTED_COUNTY_COUNT)
        fips_values = [row[0] for row in rows]
        self.assertEqual(len(set(fips_values)), EXPECTED_COUNTY_COUNT)

        for fips, county_name, state_name, state_abbr in rows:
            self.assertTrue(county_name, f"{fips}: empty county_name")
            self.assertNotEqual(county_name, "0", f"{fips}: still the placeholder")
            self.assertTrue(state_name, f"{fips}: empty state_name")
            self.assertTrue(state_abbr, f"{fips}: empty state_abbr")

    def test_representative_entity_type_names(self):
        connection = self._connection()
        try:
            rows = {
                row[0]: (row[1], row[2])
                for row in connection.execute(
                    "SELECT county_fips, county_name, state_name FROM county "
                    "WHERE county_fips IN ({})".format(
                        ",".join("?" for _ in REPRESENTATIVE_NAMES)
                    ),
                    tuple(REPRESENTATIVE_NAMES),
                )
            }
        finally:
            connection.close()

        for fips, expected in REPRESENTATIVE_NAMES.items():
            self.assertEqual(rows.get(fips), expected, f"mismatch for {fips}")

    def test_connecticut_planning_regions(self):
        connection = self._connection()
        try:
            rows = {
                row[0]: row[1]
                for row in connection.execute(
                    "SELECT county_fips, county_name FROM county "
                    "WHERE county_fips IN ({})".format(
                        ",".join("?" for _ in CONNECTICUT_PLANNING_REGIONS)
                    ),
                    tuple(CONNECTICUT_PLANNING_REGIONS),
                )
            }
            state_names = {
                row[0]
                for row in connection.execute(
                    "SELECT DISTINCT state_name FROM county WHERE state_fips = '09'"
                )
            }
        finally:
            connection.close()

        self.assertEqual(len(rows), len(CONNECTICUT_PLANNING_REGIONS))
        for fips, expected_name in CONNECTICUT_PLANNING_REGIONS.items():
            self.assertEqual(rows.get(fips), expected_name, f"mismatch for {fips}")
        self.assertEqual(state_names, {"Connecticut"})

    def test_state_abbr_unchanged_state_fips_unchanged(self):
        connection = self._connection()
        try:
            rows = connection.execute(
                "SELECT county_fips, state_fips, state_abbr FROM county"
            ).fetchall()
        finally:
            connection.close()

        for fips, state_fips, state_abbr in rows:
            self.assertEqual(state_fips, fips[:2], f"{fips}: state_fips mismatch")
            self.assertTrue(state_abbr, f"{fips}: empty state_abbr")
            self.assertEqual(
                state_abbr, state_abbr.upper(), f"{fips}: state_abbr not USPS form"
            )
            self.assertEqual(len(state_abbr), 2, f"{fips}: state_abbr not 2 characters")

    def test_state_name_is_full_name_not_abbreviation(self):
        connection = self._connection()
        try:
            distinct_states = connection.execute(
                "SELECT DISTINCT state_abbr, state_name FROM county ORDER BY state_abbr"
            ).fetchall()
        finally:
            connection.close()

        self.assertEqual(len(distinct_states), 51)  # 50 states + DC
        for state_abbr, state_name in distinct_states:
            self.assertGreater(
                len(state_name),
                len(state_abbr),
                f"{state_abbr}: state_name {state_name!r} is not a full name",
            )
            self.assertNotEqual(state_name, state_abbr)

    def test_analytical_row_counts_unaffected(self):
        connection = self._connection()
        try:
            for table, expected_count in EXPECTED_ANALYTICAL_ROW_COUNTS.items():
                actual = connection.execute(
                    f"SELECT COUNT(*) FROM {table}"  # noqa: S608 (fixed, trusted table names)
                ).fetchone()[0]
                self.assertEqual(
                    actual, expected_count, f"{table}: row count changed"
                )
        finally:
            connection.close()

    def test_analytical_values_unaffected_spot_check(self):
        connection = self._connection()
        try:
            for fips, expected in UNCHANGED_ANALYTICAL_SPOT_CHECKS.items():
                primary_care_score = connection.execute(
                    """
                    SELECT ds.score
                    FROM county_period cp
                    JOIN dimension_score ds ON ds.county_period_id = cp.county_period_id
                    WHERE cp.county_fips = ? AND ds.dimension_id = 'PRIMARY_CARE'
                    """,
                    (fips,),
                ).fetchone()[0]
                composite_value = connection.execute(
                    """
                    SELECT cs.composite_value
                    FROM county_period cp
                    JOIN composite_score cs ON cs.county_period_id = cp.county_period_id
                    WHERE cp.county_fips = ?
                    """,
                    (fips,),
                ).fetchone()[0]

                self.assertEqual(primary_care_score, expected["primary_care_score"])
                self.assertEqual(composite_value, expected["composite_value"])
        finally:
            connection.close()

    def test_county_api_returns_corrected_names(self):
        before = file_sha256(SOURCE_DATABASE)
        with TestClient(app) as client:
            response = client.get("/api/v1/counties")
        after = file_sha256(SOURCE_DATABASE)

        self.assertEqual(response.status_code, 200)
        model = CountyListResponse.model_validate(response.json())
        by_fips = {county.county_fips: county for county in model.counties}

        for fips, (expected_name, expected_state) in REPRESENTATIVE_NAMES.items():
            self.assertEqual(by_fips[fips].county_name, expected_name)
            self.assertEqual(by_fips[fips].state_name, expected_state)

        self.assertEqual(before, after)
        self.assertEqual(after, EXPECTED_PRODUCTION_SHA256)

    def test_county_explorer_api_returns_corrected_names(self):
        before = file_sha256(SOURCE_DATABASE)
        with TestClient(app) as client:
            response = client.get("/api/v1/counties/22001/explorer")
        after = file_sha256(SOURCE_DATABASE)

        self.assertEqual(response.status_code, 200)
        model = ExplorerResponse.model_validate(response.json())
        self.assertEqual(model.county.county_name, "Acadia Parish")
        self.assertEqual(model.county.state_name, "Louisiana")

        self.assertEqual(before, after)
        self.assertEqual(after, EXPECTED_PRODUCTION_SHA256)

    def test_database_sha_matches_new_baseline(self):
        self.assertEqual(file_sha256(SOURCE_DATABASE), EXPECTED_PRODUCTION_SHA256)


if __name__ == "__main__":
    unittest.main()
