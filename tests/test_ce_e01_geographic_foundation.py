"""CE-E01 tests for the County Explorer v0.2 geographic foundation.

unittest-based, matching the existing CE-A00..D01 suites. Read-only: this
suite performs no analytical calculation and mutates nothing.

Guard policy (intentionally asymmetric, and this asymmetry is deliberate):

* ``chia_v01.sqlite`` remains gitignored (unchanged CE-A00..D01 convention),
  so its absence is a legitimate "not present in this environment" case and
  is skipped, exactly like every other CE-A/B/D test file.
* The generated geographic assets (``Data/Model/geo/`` and
  ``frontend/public/geo/``) are, per the CE-E01 decision, committed to Git.
  Their absence after CE-E01 is not a legitimate skip condition -- it would
  let this suite silently pass without ever validating the geographic
  foundation it exists to validate. A missing geographic asset is therefore
  an explicit, non-skippable test failure.
"""

from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DATABASE = PROJECT_ROOT / "Data" / "Model" / "chia_v01.sqlite"

GEO_DIR = PROJECT_ROOT / "Data" / "Model" / "geo"
US_STATES_TOPOJSON = GEO_DIR / "us-states.topojson"
COUNTY_GEO_DIR = GEO_DIR / "counties"

FRONTEND_GEO_DIR = PROJECT_ROOT / "frontend" / "public" / "geo"
FRONTEND_US_STATES_TOPOJSON = FRONTEND_GEO_DIR / "us-states.topojson"
FRONTEND_COUNTY_GEO_DIR = FRONTEND_GEO_DIR / "counties"

EXPECTED_COUNTY_COUNT = 3143
EXPECTED_STATE_COUNT = 51

CONNECTICUT_PLANNING_REGION_GEOIDS = [
    "09110", "09120", "09130", "09140", "09150",
    "09160", "09170", "09180", "09190",
]

REPRESENTATIVE_COUNTY_EQUIVALENTS = {
    "11001": "District of Columbia",
    "02020": "Anchorage Municipality",
    "02170": "Matanuska-Susitna Borough",
    "02282": "Yakutat City and Borough",
    "51600": "Fairfax city",
    "51770": "Roanoke city",
    "29510": "St. Louis city",
}


def _load_topojson_geometries(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        data = json.load(f)

    geometries = {}
    for obj in data.get("objects", {}).values():
        for geometry in obj.get("geometries", []):
            geometries[geometry.get("id")] = geometry
    return geometries


class GeographicAssetsPresentTest(unittest.TestCase):
    """The committed geographic assets must exist -- never silently skipped."""

    def test_data_model_geo_assets_exist(self):
        self.assertTrue(
            US_STATES_TOPOJSON.exists(),
            f"Required geographic asset missing: {US_STATES_TOPOJSON}. "
            "This is a CE-E01 regression, not a legitimate skip condition -- "
            "these assets are committed to Git.",
        )
        self.assertTrue(
            COUNTY_GEO_DIR.exists() and any(COUNTY_GEO_DIR.glob("*.topojson")),
            f"Required geographic asset directory missing or empty: {COUNTY_GEO_DIR}",
        )

    def test_frontend_public_geo_assets_exist(self):
        self.assertTrue(
            FRONTEND_US_STATES_TOPOJSON.exists(),
            f"Required frontend geographic asset missing: {FRONTEND_US_STATES_TOPOJSON}",
        )
        self.assertTrue(
            FRONTEND_COUNTY_GEO_DIR.exists()
            and any(FRONTEND_COUNTY_GEO_DIR.glob("*.topojson")),
            f"Required frontend geographic asset directory missing or empty: "
            f"{FRONTEND_COUNTY_GEO_DIR}",
        )

    def test_data_model_and_frontend_county_assets_match(self):
        model_files = {p.name for p in COUNTY_GEO_DIR.glob("*.topojson")}
        frontend_files = {p.name for p in FRONTEND_COUNTY_GEO_DIR.glob("*.topojson")}
        self.assertEqual(
            model_files,
            frontend_files,
            "Data/Model/geo/counties and frontend/public/geo/counties must "
            "contain the same set of per-state files.",
        )


class GeographicFipsJoinTest(unittest.TestCase):
    """Validates the FIPS/GEOID join against the canonical CHIA county universe."""

    @classmethod
    def setUpClass(cls):
        if not SOURCE_DATABASE.exists():
            raise unittest.SkipTest(
                f"Canonical database not found: {SOURCE_DATABASE}"
            )

        connection = sqlite3.connect(SOURCE_DATABASE)
        try:
            rows = connection.execute(
                "SELECT county_fips, state_fips FROM county"
            ).fetchall()
        finally:
            connection.close()

        cls.chia_counties = {fips: state_fips for fips, state_fips in rows}
        cls.chia_states = set(cls.chia_counties.values())

        cls.census_county_geometries = {}
        for path in sorted(COUNTY_GEO_DIR.glob("*.topojson")):
            cls.census_county_geometries.update(_load_topojson_geometries(path))

        cls.census_state_geometries = _load_topojson_geometries(US_STATES_TOPOJSON)

    def test_chia_county_universe_is_3143(self):
        self.assertEqual(len(self.chia_counties), EXPECTED_COUNTY_COUNT)

    def test_every_chia_county_has_exactly_one_matching_geoid(self):
        missing = sorted(
            fips for fips in self.chia_counties if fips not in self.census_county_geometries
        )
        self.assertEqual(missing, [], f"CHIA counties with no Census match: {missing}")

    def test_no_duplicate_geoids_across_generated_assets(self):
        seen = set()
        duplicates = []
        for path in sorted(COUNTY_GEO_DIR.glob("*.topojson")):
            for feature_id in _load_topojson_geometries(path):
                if feature_id in seen:
                    duplicates.append(feature_id)
                seen.add(feature_id)
        self.assertEqual(duplicates, [], f"Duplicate GEOIDs found: {duplicates}")

    def test_geoid_state_prefix_matches_stored_state_fips(self):
        mismatches = [
            (fips, fips[:2], state_fips)
            for fips, state_fips in self.chia_counties.items()
            if fips in self.census_county_geometries and fips[:2] != state_fips
        ]
        self.assertEqual(mismatches, [], f"State-prefix mismatches: {mismatches}")

    def test_no_chia_county_has_empty_geometry(self):
        empty = [
            fips
            for fips in self.chia_counties
            if fips in self.census_county_geometries
            and not self.census_county_geometries[fips].get("arcs")
        ]
        self.assertEqual(empty, [], f"CHIA counties with empty geometry: {empty}")

    def test_all_51_chia_states_represented(self):
        self.assertEqual(len(self.chia_states), EXPECTED_STATE_COUNT)
        missing = sorted(self.chia_states - set(self.census_state_geometries))
        self.assertEqual(missing, [], f"Missing state GEOIDs: {missing}")

    def test_connecticut_planning_regions_represented(self):
        for geoid in CONNECTICUT_PLANNING_REGION_GEOIDS:
            with self.subTest(geoid=geoid):
                self.assertIn(geoid, self.chia_counties)
                self.assertIn(geoid, self.census_county_geometries)

    def test_representative_county_equivalent_types_represented(self):
        for fips, label in REPRESENTATIVE_COUNTY_EQUIVALENTS.items():
            with self.subTest(fips=fips, label=label):
                self.assertIn(fips, self.chia_counties, f"{label} ({fips}) missing from CHIA")
                self.assertIn(
                    fips, self.census_county_geometries,
                    f"{label} ({fips}) missing from generated Census geometry",
                )

    def test_census_extras_do_not_include_any_chia_county(self):
        """Census features with no CHIA counterpart are expected, not a failure --
        but every one of them must genuinely be absent from CHIA, not a
        mis-join hiding as an 'extra'."""
        extras = set(self.census_county_geometries) - set(self.chia_counties)
        for geoid in extras:
            with self.subTest(geoid=geoid):
                self.assertNotIn(geoid, self.chia_counties)


if __name__ == "__main__":
    unittest.main()
