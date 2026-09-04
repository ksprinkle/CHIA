import json
from pathlib import Path
import sqlite3


# ============================================================
# CHIA v0.2 UX — Geographic Foundation Validation (CE-E01)
# ============================================================
#
# Validates the FIPS/GEOID join between CHIA's canonical county universe
# (chia_v01.sqlite) and the generated Census-derived TopoJSON boundary
# assets. Performs no analytical calculation and mutates nothing.
#
# Validation rule (governing v0.2 UX specification, section 11.2/11.9):
#
#     Every CHIA county must resolve to valid Census geometry.
#
# The reverse is NOT required: Census's boundary files include entities
# (Puerto Rico, other territories, and county-equivalents CHIA's canonical
# universe does not include) that have no CHIA counterpart. Those are
# expected and are not failures.

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATABASE_PATH = PROJECT_ROOT / "Data" / "Model" / "chia_v01.sqlite"
GEO_DIR = PROJECT_ROOT / "Data" / "Model" / "geo"
US_STATES_TOPOJSON = GEO_DIR / "us-states.topojson"
COUNTY_GEO_DIR = GEO_DIR / "counties"

EXPECTED_COUNTY_COUNT = 3143
EXPECTED_STATE_COUNT = 51

CONNECTICUT_PLANNING_REGION_GEOIDS = [
    "09110", "09120", "09130", "09140", "09150",
    "09160", "09170", "09180", "09190",
]

# One representative FIPS per notable county-equivalent type already present
# in CHIA (governing v0.1 canonical naming correction, CE-D01).
REPRESENTATIVE_COUNTY_EQUIVALENTS = {
    "11001": "District of Columbia",
    "02020": "Anchorage Municipality",
    "02170": "Matanuska-Susitna Borough",
    "02282": "Yakutat City and Borough",
    "51600": "Fairfax city",
    "51770": "Roanoke city",
    "29510": "St. Louis city",
    "09110": "Capitol Planning Region",
}


def check(label, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}")
    if detail:
        print(f"       {detail}")
    return condition


def load_chia_counties():
    if not DATABASE_PATH.exists():
        raise FileNotFoundError(f"Canonical database not found:\n{DATABASE_PATH}")

    connection = sqlite3.connect(DATABASE_PATH)
    try:
        rows = connection.execute(
            "SELECT county_fips, state_fips FROM county"
        ).fetchall()
    finally:
        connection.close()

    return {fips: state_fips for fips, state_fips in rows}


def load_topojson_geometries(path: Path):
    """Return {feature_id: geometry_dict} for every geometry in a TopoJSON file."""

    with path.open(encoding="utf-8") as f:
        data = json.load(f)

    geometries = {}
    for obj in data.get("objects", {}).values():
        for geometry in obj.get("geometries", []):
            geometries[geometry.get("id")] = geometry
    return geometries


def main():
    print("=" * 70)
    print("CHIA v0.2 UX — GEOGRAPHIC FOUNDATION VALIDATION (CE-E01)")
    print("=" * 70)

    for required in (US_STATES_TOPOJSON,):
        if not required.exists():
            raise FileNotFoundError(f"Required geographic asset not found:\n{required}")

    if not COUNTY_GEO_DIR.exists():
        raise FileNotFoundError(f"Required geographic asset directory not found:\n{COUNTY_GEO_DIR}")

    county_files = sorted(COUNTY_GEO_DIR.glob("*.topojson"))
    if not county_files:
        raise FileNotFoundError(f"No county TopoJSON files found in:\n{COUNTY_GEO_DIR}")

    failures = 0

    # ----------------------------------------------------
    # 1. Canonical CHIA county universe
    # ----------------------------------------------------

    chia_counties = load_chia_counties()

    if not check(
        "CHIA county count",
        len(chia_counties) == EXPECTED_COUNTY_COUNT,
        f"Found {len(chia_counties):,}; expected {EXPECTED_COUNTY_COUNT:,}.",
    ):
        failures += 1

    # ----------------------------------------------------
    # 2. Load all generated county geometry (all states)
    # ----------------------------------------------------

    census_geometries = {}
    duplicate_geoids = []
    for path in county_files:
        for feature_id, geometry in load_topojson_geometries(path).items():
            if feature_id in census_geometries:
                duplicate_geoids.append(feature_id)
            census_geometries[feature_id] = geometry

    if not check(
        "No duplicate GEOIDs across generated county assets",
        not duplicate_geoids,
        f"Duplicates: {duplicate_geoids}" if duplicate_geoids else "",
    ):
        failures += 1

    # ----------------------------------------------------
    # 3. Every CHIA county resolves to Census geometry
    # ----------------------------------------------------

    missing = sorted(fips for fips in chia_counties if fips not in census_geometries)

    if not check(
        "Every CHIA county_fips has a matching Census GEOID",
        not missing,
        f"Missing {len(missing)}: {missing[:20]}" if missing else
        f"{len(chia_counties):,}/{len(chia_counties):,} matched.",
    ):
        failures += 1

    unmatched_census = sorted(set(census_geometries) - set(chia_counties))
    check(
        "Census features with no CHIA counterpart (informational; not a failure)",
        True,
        f"{len(unmatched_census)} extra feature(s): {unmatched_census}",
    )

    # ----------------------------------------------------
    # 4. State-FIPS prefix consistency
    # ----------------------------------------------------

    state_mismatches = []
    empty_geometries = []
    for fips, state_fips in chia_counties.items():
        geometry = census_geometries.get(fips)
        if geometry is None:
            continue
        if fips[:2] != state_fips:
            state_mismatches.append((fips, fips[:2], state_fips))
        if not geometry.get("arcs") and geometry.get("type") != "GeometryCollection":
            empty_geometries.append(fips)

    if not check(
        "GEOID state prefix matches stored state_fips",
        not state_mismatches,
        f"Mismatches: {state_mismatches[:20]}" if state_mismatches else "",
    ):
        failures += 1

    if not check(
        "No CHIA county has empty geometry",
        not empty_geometries,
        f"Empty: {empty_geometries}" if empty_geometries else "",
    ):
        failures += 1

    # ----------------------------------------------------
    # 5. National state coverage
    # ----------------------------------------------------

    state_geometries = load_topojson_geometries(US_STATES_TOPOJSON)
    chia_states = set(chia_counties.values())

    if not check(
        "CHIA state count",
        len(chia_states) == EXPECTED_STATE_COUNT,
        f"Found {len(chia_states)}; expected {EXPECTED_STATE_COUNT}.",
    ):
        failures += 1

    missing_states = sorted(chia_states - set(state_geometries))
    if not check(
        "All CHIA state_fips values represented in national state TopoJSON",
        not missing_states,
        f"Missing: {missing_states}" if missing_states else
        f"{len(chia_states)}/{len(chia_states)} matched.",
    ):
        failures += 1

    # ----------------------------------------------------
    # 6. Connecticut planning regions
    # ----------------------------------------------------

    ct_missing = [
        geoid for geoid in CONNECTICUT_PLANNING_REGION_GEOIDS
        if geoid not in census_geometries or geoid not in chia_counties
    ]
    if not check(
        "All 9 Connecticut planning-region GEOIDs represented",
        not ct_missing,
        f"Missing: {ct_missing}" if ct_missing else "9/9 verified.",
    ):
        failures += 1

    # ----------------------------------------------------
    # 7. Representative county-equivalent types
    # ----------------------------------------------------

    rep_failures = [
        fips for fips in REPRESENTATIVE_COUNTY_EQUIVALENTS
        if fips not in census_geometries or fips not in chia_counties
    ]
    if not check(
        "Representative county-equivalent types resolve correctly",
        not rep_failures,
        f"Failed: {rep_failures}" if rep_failures else
        f"{len(REPRESENTATIVE_COUNTY_EQUIVALENTS)}/{len(REPRESENTATIVE_COUNTY_EQUIVALENTS)} verified "
        f"({', '.join(REPRESENTATIVE_COUNTY_EQUIVALENTS.values())}).",
    ):
        failures += 1

    # ----------------------------------------------------
    # Summary
    # ----------------------------------------------------

    print("=" * 70)
    if failures == 0:
        print("ALL CHECKS PASSED.")
    else:
        print(f"{failures} CHECK(S) FAILED.")
    print("=" * 70)

    return failures


if __name__ == "__main__":
    raise SystemExit(1 if main() else 0)
