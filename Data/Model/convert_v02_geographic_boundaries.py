import os
from pathlib import Path
import shutil
import subprocess
import sys


# ============================================================
# CHIA v0.2 UX — Geographic Boundary Conversion (CE-E01)
# ============================================================
#
# Converts sourced U.S. Census Bureau Cartographic Boundary shapefiles into
# web-deliverable TopoJSON for the future County Explorer map-first UX.
#
# This script performs no analytical calculation and touches no part of the
# CE-A00..D01 analytical pipeline. It is a presentation/navigation-asset
# build step only (governing v0.2 UX specification, section 11.13).
#
# Requires: raw Census shapefiles already present under
# Data/Raw/GIS/Census Cartographic Boundary Files/ (see Step 2 of the CE-E01
# implementation; not committed to Git -- see .gitignore).
#
# Uses mapshaper as a build-time-only tool, invoked via `npx` so that no
# project manifest (requirements.txt, frontend/package.json,
# frontend/package-lock.json) is modified to accommodate it. mapshaper is
# never imported or required at application runtime.

PROJECT_ROOT = Path(__file__).resolve().parents[2]

RAW_CENSUS_DIR = (
    PROJECT_ROOT / "Data" / "Raw" / "GIS" / "Census Cartographic Boundary Files"
)
STATE_SHAPEFILE = (
    RAW_CENSUS_DIR / "state_20m" / "cb_2025_us_state_20m.shp"
)
COUNTY_SHAPEFILE = (
    RAW_CENSUS_DIR / "county_500k" / "cb_2025_us_county_500k.shp"
)

GEO_DIR = PROJECT_ROOT / "Data" / "Model" / "geo"
GEO_COUNTIES_DIR = GEO_DIR / "counties"
US_STATES_TOPOJSON = GEO_DIR / "us-states.topojson"

FRONTEND_GEO_DIR = PROJECT_ROOT / "frontend" / "public" / "geo"
FRONTEND_COUNTIES_DIR = FRONTEND_GEO_DIR / "counties"

# mapshaper is invoked as a pinned version via `npx --yes` -- a build-time-only
# CLI invocation, not a project dependency. See Documentation/
# GEOGRAPHIC_DATA_SOURCES.md.txt for the exact version and rationale.
MAPSHAPER_PACKAGE = "mapshaper@0.7.58"

# CHIA's 51 state-equivalents: the 50 states + DC. No U.S. territories.
# (Data/Model/build_v01_database.py encodes the same canonical county/state
# universe; this list is the state-level projection of that universe.)
CHIA_STATE_FIPS = [
    "01", "02", "04", "05", "06", "08", "09", "10", "11", "12",
    "13", "15", "16", "17", "18", "19", "20", "21", "22", "23",
    "24", "25", "26", "27", "28", "29", "30", "31", "32", "33",
    "34", "35", "36", "37", "38", "39", "40", "41", "42", "44",
    "45", "46", "47", "48", "49", "50", "51", "53", "54", "55", "56",
]

# Additional topology-preserving simplification applied on top of Census's
# own cartographic generalization (Census cartographic boundary files are
# already generalized for their resolution tier; this is a modest further
# reduction for web file size, not a resolution change).
SIMPLIFY_PCT = "10%"


def _npx_executable() -> str:
    """Resolve the `npx` executable across platforms.

    On Windows, `npx` is a `.cmd` shim; `shutil.which("npx")` resolves it
    correctly, but a bare "npx" string is not directly executable via
    ``subprocess.run(..., shell=False)``.
    """

    resolved = shutil.which("npx")
    if resolved is None:
        raise FileNotFoundError(
            "`npx` was not found on PATH. Node.js/npm is required to run "
            "mapshaper as a build-time tool (see Documentation/"
            "GEOGRAPHIC_DATA_SOURCES.md.txt)."
        )
    return resolved


def _run_mapshaper(args: list[str]) -> None:
    command = [_npx_executable(), "--yes", MAPSHAPER_PACKAGE, *args]
    print("+", " ".join(command))
    result = subprocess.run(command, cwd=PROJECT_ROOT, shell=False)
    if result.returncode != 0:
        raise RuntimeError(
            f"mapshaper invocation failed (exit {result.returncode}): {args}"
        )


def _require_source_files() -> None:
    missing = [p for p in (STATE_SHAPEFILE, COUNTY_SHAPEFILE) if not p.exists()]
    if missing:
        joined = "\n".join(f"  - {p}" for p in missing)
        raise FileNotFoundError(
            "Required raw Census shapefile(s) not found:\n"
            f"{joined}\n\n"
            "Download the U.S. Census Bureau Cartographic Boundary Files "
            "(2025 vintage) into Data/Raw/GIS/Census Cartographic Boundary "
            "Files/ before running this script. See Documentation/"
            "GEOGRAPHIC_DATA_SOURCES.md.txt for exact source URLs."
        )


def convert_national_states() -> None:
    """Convert the national state boundary layer.

    All 51 CHIA state-equivalents, simplified for national-scale display.
    Puerto Rico (the only non-CHIA feature in the source file) is dropped.
    """

    GEO_DIR.mkdir(parents=True, exist_ok=True)
    state_filter = repr(CHIA_STATE_FIPS).replace("'", '"')

    _run_mapshaper([
        str(STATE_SHAPEFILE),
        "-filter", f"{state_filter}.includes(STATEFP)",
        "-simplify", SIMPLIFY_PCT, "keep-shapes",
        "-clean",
        "-o", str(US_STATES_TOPOJSON),
        "format=topojson", "id-field=GEOID", "force",
    ])


def convert_state_county_layers() -> None:
    """Convert county boundaries, filtered to CHIA states and split by state.

    Produces one TopoJSON file per state FIPS
    (Data/Model/geo/counties/<state_fips>.topojson) so the frontend never
    has to load more than one state's county geometry at a time (governing
    v0.2 UX specification, section 11.7/11.8).
    """

    GEO_COUNTIES_DIR.mkdir(parents=True, exist_ok=True)
    for existing in GEO_COUNTIES_DIR.glob("*.topojson"):
        existing.unlink()

    state_filter = repr(CHIA_STATE_FIPS).replace("'", '"')

    _run_mapshaper([
        str(COUNTY_SHAPEFILE),
        "-filter", f"{state_filter}.includes(STATEFP)",
        "-simplify", SIMPLIFY_PCT, "keep-shapes",
        "-clean",
        "-split", "STATEFP",
        "-o", f"{GEO_COUNTIES_DIR}{os.sep}",
        "format=topojson", "extension=topojson", "id-field=GEOID",
        "singles", "force",
    ])


def copy_to_frontend() -> None:
    """Copy the generated Data/Model/geo assets to frontend/public/geo.

    These are the final, committed, runtime-served assets. This is a plain
    file copy -- no further conversion or simplification occurs here.
    """

    FRONTEND_GEO_DIR.mkdir(parents=True, exist_ok=True)
    FRONTEND_COUNTIES_DIR.mkdir(parents=True, exist_ok=True)

    shutil.copyfile(US_STATES_TOPOJSON, FRONTEND_GEO_DIR / US_STATES_TOPOJSON.name)

    for existing in FRONTEND_COUNTIES_DIR.glob("*.topojson"):
        existing.unlink()
    for source in sorted(GEO_COUNTIES_DIR.glob("*.topojson")):
        shutil.copyfile(source, FRONTEND_COUNTIES_DIR / source.name)


def main() -> None:
    print("=" * 70)
    print("CHIA v0.2 UX — GEOGRAPHIC BOUNDARY CONVERSION (CE-E01)")
    print("=" * 70)

    _require_source_files()

    print("\n[1/3] Converting national state boundaries...")
    convert_national_states()

    print("\n[2/3] Converting + splitting county boundaries by state...")
    convert_state_county_layers()

    print("\n[3/3] Copying generated assets to frontend/public/geo...")
    copy_to_frontend()

    state_count = len(list(FRONTEND_COUNTIES_DIR.glob("*.topojson")))
    print("\nDone.")
    print(f"  {US_STATES_TOPOJSON.relative_to(PROJECT_ROOT)}")
    print(f"  {GEO_COUNTIES_DIR.relative_to(PROJECT_ROOT)}/ ({state_count} files)")
    print(f"  Copied to frontend/public/geo/ ({state_count} county files + 1 state file)")


if __name__ == "__main__":
    sys.exit(main())
