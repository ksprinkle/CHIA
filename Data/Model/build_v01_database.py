from pathlib import Path
import hashlib
import sqlite3
import pandas as pd


# ============================================================
# CHIA v0.1 — Build Canonical Database
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = PROJECT_ROOT / "Data"
PROCESSED_DIR = DATA_DIR / "Processed"
MODEL_DIR = DATA_DIR / "Model"

DATABASE_PATH = MODEL_DIR / "chia_v01.sqlite"


# ------------------------------------------------------------
# Source files
# ------------------------------------------------------------

SOURCE_FILES = {
    "primary_care": (
        PROCESSED_DIR
        / "CHIA_Primary_Care_HPSA_Spatial_Coverage_Validated_FINAL.xlsx"
    ),
    "dental": (
        PROCESSED_DIR
        / "CHIA_Dental_HPSA_Spatial_Coverage_Validated_FINAL.xlsx"
    ),
    "mental_health": (
        PROCESSED_DIR
        / "CHIA_Mental_Health_HPSA_Spatial_Coverage_Validated_FINAL.xlsx"
    ),
    "mua_p": (
        PROCESSED_DIR
        / "CHIA_MUA_P_Spatial_Coverage_Validated.xlsx"
    ),
}


# ------------------------------------------------------------
# Exact source-column mappings
# ------------------------------------------------------------

VARIABLES = {
    "primary_care": {
        "primary": (
            "PC_HPSA_GEOGRAPHIC_COVERAGE",
            "PC_HPSA_Geographic_Coverage_Pct",
        ),
        "supporting": {
            "PC_HPSA_AREA_WEIGHTED_SCORE":
                "PC_HPSA_AreaWeighted_Score",
            "PC_HPSA_MAX_SCORE":
                "PC_HPSA_Max_Score",
            "PC_HPSA_DESIGNATION_COUNT":
                "PC_HPSA_Geographic_Designation_Count",
        },
    },
    "dental": {
        "primary": (
            "DENTAL_HPSA_GEOGRAPHIC_COVERAGE",
            "Dental_HPSA_Geographic_Coverage_Pct",
        ),
        "supporting": {
            "DENTAL_HPSA_AREA_WEIGHTED_SCORE":
                "Dental_HPSA_AreaWeighted_Score",
            "DENTAL_HPSA_MAX_SCORE":
                "Dental_HPSA_Max_Score",
            "DENTAL_HPSA_DESIGNATION_COUNT":
                "Dental_HPSA_Geographic_Designation_Count",
        },
    },
    "mental_health": {
        "primary": (
            "MH_HPSA_GEOGRAPHIC_COVERAGE",
            "MH_HPSA_Geographic_Coverage_Pct",
        ),
        "supporting": {
            "MH_HPSA_AREA_WEIGHTED_SCORE":
                "MH_HPSA_AreaWeighted_Score",
            "MH_HPSA_MAX_SCORE":
                "MH_HPSA_Max_Score",
            "MH_HPSA_DESIGNATION_COUNT":
                "MH_HPSA_Geographic_Designation_Count",
        },
    },
    "mua_p": {
        "primary": (
            "MUAP_GEOGRAPHIC_COVERAGE",
            "MUA_P_Geographic_Coverage_Pct",
        ),
        "supporting": {
            "MUAP_MEAN_SCORE":
                "MUA_P_Mean_Score",
            "MUAP_MAX_SCORE":
                "MUA_P_Max_Score",
            "MUAP_FEATURE_COUNT":
                "MUA_P_Intersection_Features",
            "MUA_FEATURE_COUNT":
                "MUA_Feature_Count",
            "MUP_FEATURE_COUNT":
                "MUP_Feature_Count",
            "MUAP_UNIQUE_SOURCE_COUNT":
                "MUA_P_Unique_Source_Count",
        },
    },
}


# ------------------------------------------------------------
# Database schema
# ------------------------------------------------------------

SCHEMA_PATH = MODEL_DIR / "schema.sql"
SEED_PATH = MODEL_DIR / "seed_v01.sql"


# ------------------------------------------------------------
# CE-E12B source-vintage / reproducibility metadata
# ------------------------------------------------------------
#
# The v0.1 analytical sources are one HRSA Data Warehouse snapshot (every raw
# record carries a uniform Data Warehouse Record Create Date of 2026-08-29).
# artifact_filename / content_sha256 pin the exact Data/Processed build-input
# workbook. Authoritative catalogue and verification snippet:
# Documentation/ANALYTICAL_DATA_SOURCES.md.txt. These fields are presentation /
# provenance only -- no analytical script reads the source table.

SOURCE_REFERENCE_PERIOD = "HRSA Data Warehouse snapshot 2026-08-29"
SOURCE_URL = "https://data.hrsa.gov/data/download"
SOURCE_ACCESSED_AT = "2026-08-29"


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ------------------------------------------------------------
# County reference data (CE-D01 Issue 2 correction)
# ------------------------------------------------------------
#
# The Primary Care HPSA file's own `CountyName` column is a placeholder
# (literal 0 for every row; see the CE-D01 Issue 2 investigation) and never
# carried a `StateName` column at all. `county_name` / `state_name` are
# instead resolved from the U.S. Census Bureau's 2020 PL 94-171 redistricting
# geoheader files, already present in this repository. `state_abbr` is
# unaffected -- it continues to come from the Primary Care HPSA file exactly
# as before.

RAW_DIR = DATA_DIR / "Raw"
CENSUS_GEOHEADER_DIR = RAW_DIR / "Census" / "PL94_171_2020" / "Unzipped"
PLACES_PATH = (
    RAW_DIR / "PLACES__County_Data_(GIS_Friendly_Format),_2025_release_20260829.csv"
)

# SUMLEV "050" (state-county) rows carry the county-level AREANAME; "040"
# (state) rows carry the state-level one. Both fields sit at fixed offsets
# from the end of every row in this fixed-format, pipe-delimited file,
# confirmed against all 51 state/DC geoheader files during the CE-D01 Issue 2
# investigation (field 87 of 97, i.e. index -10; the GEOID in field 9, index
# 8, ends with the 5-digit FIPS).
_CENSUS_SUMLEV_COUNTY = "050"
_CENSUS_SUMLEV_STATE = "040"
_CENSUS_AREANAME_INDEX = -10
_CENSUS_GEOID_INDEX = 8
_CENSUS_STATE_ABBR_INDEX = 1
_CENSUS_SUMLEV_INDEX = 2

# The 2020 PL 94-171 geoheader files predate Connecticut's 2022 FIPS
# reassignment from 8 counties to 9 planning regions, so they supply no
# AREANAME for these 9 (verified missing during the CE-D01 Issue 2
# investigation). The canonical county universe already uses the new codes
# (sourced from the Primary Care HPSA file), and the already-validated
# PLACES dataset has the current code -> base name for each. Per the
# approved CE-D01 Issue 2 decision, these base names are normalized to the
# region's established "<Name> Planning Region" designation -- documented
# here, not derived automatically, so the substitution stays explicit and
# auditable. `load_connecticut_planning_region_names` re-reads PLACES and
# raises if its name for any of these 9 has since drifted from what was
# verified, rather than silently trusting a hardcoded name.
CONNECTICUT_PLANNING_REGION_BASE_NAMES = {
    "09110": "Capitol",
    "09120": "Greater Bridgeport",
    "09130": "Lower Connecticut River Valley",
    "09140": "Naugatuck Valley",
    "09150": "Northeastern Connecticut",
    "09160": "Northwest Hills",
    "09170": "South Central Connecticut",
    "09180": "Southeastern Connecticut",
    "09190": "Western Connecticut",
}


def load_census_county_names(
    census_dir: Path = CENSUS_GEOHEADER_DIR,
) -> dict[str, str]:
    """Return ``{county_fips: AREANAME}`` from the 2020 PL 94-171 geoheader
    files, e.g. ``'01001' -> 'Autauga County'``, ``'22001' -> 'Acadia
    Parish'``, ``'02020' -> 'Anchorage Municipality'``, ``'51710' ->
    'Norfolk city'``. AREANAME is the Census Bureau's own legal/statistical
    area name, already correctly suffixed per entity type -- no suffix is
    appended or guessed here.
    """

    names: dict[str, str] = {}

    for path in sorted(census_dir.glob("*/*geo2020.pl")):
        with path.open(encoding="latin-1") as handle:
            for line in handle:
                fields = line.rstrip("\n").split("|")
                if fields[_CENSUS_SUMLEV_INDEX] == _CENSUS_SUMLEV_COUNTY:
                    fips = fields[_CENSUS_GEOID_INDEX][-5:]
                    names[fips] = fields[_CENSUS_AREANAME_INDEX]

    return names


def load_census_state_names(
    census_dir: Path = CENSUS_GEOHEADER_DIR,
) -> dict[str, str]:
    """Return ``{state_abbr: full state name}`` from each geoheader file's
    state-level (SUMLEV 040) row, e.g. ``'AL' -> 'Alabama'``.
    """

    names: dict[str, str] = {}

    for path in sorted(census_dir.glob("*/*geo2020.pl")):
        with path.open(encoding="latin-1") as handle:
            for line in handle:
                fields = line.rstrip("\n").split("|")
                if fields[_CENSUS_SUMLEV_INDEX] == _CENSUS_SUMLEV_STATE:
                    names[fields[_CENSUS_STATE_ABBR_INDEX]] = (
                        fields[_CENSUS_AREANAME_INDEX]
                    )

    return names


def load_connecticut_planning_region_names(
    places_path: Path = PLACES_PATH,
) -> dict[str, str]:
    """Return ``{county_fips: "<Name> Planning Region"}`` for the 9
    Connecticut planning-region FIPS the 2020 Census geoheader predates (see
    ``CONNECTICUT_PLANNING_REGION_BASE_NAMES`` above). Raises if PLACES is
    missing any of the 9, or if its base name for any of them has changed
    since the CE-D01 Issue 2 investigation -- this must not silently apply a
    stale normalization.
    """

    import csv

    found: dict[str, str] = {}

    with places_path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            fips = row["CountyFIPS"].strip().zfill(5)
            if fips in CONNECTICUT_PLANNING_REGION_BASE_NAMES:
                found[fips] = row["CountyName"].strip()

    missing = set(CONNECTICUT_PLANNING_REGION_BASE_NAMES) - set(found)
    if missing:
        raise ValueError(
            "PLACES is missing the Connecticut planning-region FIPS: "
            f"{sorted(missing)}"
        )

    drifted = {
        fips: (expected, found[fips])
        for fips, expected in CONNECTICUT_PLANNING_REGION_BASE_NAMES.items()
        if found[fips] != expected
    }
    if drifted:
        raise ValueError(
            "PLACES county name(s) for Connecticut planning regions have "
            f"changed since the CE-D01 Issue 2 investigation: {drifted}"
        )

    return {
        fips: f"{name} Planning Region"
        for fips, name in found.items()
    }


def resolve_county_reference(
    counties: pd.DataFrame,
) -> list[tuple[str, str, str, str, str]]:
    """Resolve ``(county_fips, state_fips, county_name, state_name,
    state_abbr)`` for the full canonical county universe (approved CE-D01
    Issue 2 naming convention): ``county_name`` from the Census geoheader
    (Connecticut-planning-region-patched), ``state_name`` from the Census
    geoheader's state-level rows, ``state_abbr`` unchanged from the Primary
    Care HPSA file. Raises unless every canonical FIPS resolves to a
    non-empty name, state, and abbreviation, with no duplicates.
    """

    census_names = load_census_county_names()
    census_states = load_census_state_names()
    ct_patch = load_connecticut_planning_region_names()

    records: list[tuple[str, str, str, str, str]] = []
    unresolved: list[tuple[str, str | None, str | None, str | None]] = []

    for _, row in counties.iterrows():
        fips = row["county_fips"]
        state_abbr = (
            None
            if pd.isna(row["StateAbbr"])
            else str(row["StateAbbr"]).strip()
        )

        county_name = census_names.get(fips) or ct_patch.get(fips)
        state_name = census_states.get(state_abbr) if state_abbr else None

        if not county_name or not state_name or not state_abbr:
            unresolved.append((fips, county_name, state_name, state_abbr))
            continue

        records.append((fips, fips[:2], county_name, state_name, state_abbr))

    if unresolved:
        raise ValueError(
            f"{len(unresolved)} canonical FIPS could not be fully resolved "
            f"(fips, county_name, state_name, state_abbr): {unresolved[:10]}"
        )

    fips_seen = [record[0] for record in records]
    if len(fips_seen) != len(counties):
        raise ValueError(
            f"Resolved {len(fips_seen)} county reference records; "
            f"expected {len(counties)}."
        )
    if len(set(fips_seen)) != len(fips_seen):
        raise ValueError("Duplicate county_fips in resolved county reference data.")

    return records


def _replace_county_reference(
    database_path: Path,
    records: list[tuple[str, str, str, str, str]],
) -> None:
    """Transactionally replace the ``county`` table's content with
    ``records``, leaving every other table byte-for-byte untouched.

    A full ``build_v01_database.py`` run wipes and recreates the entire
    database file -- but no script in this pipeline currently regenerates
    MUA/P's ``dimension_score`` rows (or any other table) from scratch (see
    the CE-D01 Issue 2 investigation), so that would silently discard
    otherwise-irreplaceable analytical data. When the canonical database
    already exists, this scoped replace is used instead: it deletes and
    reinserts only ``county`` (deferring foreign-key enforcement to commit
    time, since ``county_period.county_fips`` references it), then verifies
    the row count, the FIPS universe, and referential integrity are exactly
    preserved before committing; any failure rolls back the entire change.
    """

    connection = sqlite3.connect(database_path)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA defer_foreign_keys = ON")
        connection.execute("BEGIN IMMEDIATE")

        before_fips = {
            row[0]
            for row in connection.execute("SELECT county_fips FROM county")
        }

        connection.execute("DELETE FROM county")
        connection.executemany(
            """
            INSERT INTO county (
                county_fips,
                state_fips,
                county_name,
                state_name,
                state_abbr
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            records,
        )

        after_rows = connection.execute(
            "SELECT county_fips, county_name, state_name, state_abbr FROM county"
        ).fetchall()
        after_fips = {row[0] for row in after_rows}

        if len(after_rows) != len(before_fips):
            raise ValueError(
                f"county row count changed: {len(before_fips)} -> {len(after_rows)}."
            )
        if after_fips != before_fips:
            raise ValueError(
                "county_fips universe changed; it must be preserved exactly."
            )
        if len(after_fips) != len(after_rows):
            raise ValueError("Duplicate county_fips after replacement.")
        for fips, county_name, state_name, state_abbr in after_rows:
            if not county_name or not state_name or not state_abbr:
                raise ValueError(
                    f"{fips}: empty county_name/state_name/state_abbr after "
                    "replacement."
                )

        foreign_key_errors = connection.execute("PRAGMA foreign_key_check").fetchall()
        if foreign_key_errors:
            raise ValueError(
                f"Foreign-key validation failed: {foreign_key_errors}"
            )

        connection.commit()

        print()
        print("=" * 70)
        print("COUNTY REFERENCE DATA REPLACED (CE-D01 Issue 2 correction)")
        print("=" * 70)
        print(f"Database:        {database_path}")
        print(f"Rows replaced:   {len(after_rows):,}")
        print(f"FIPS universe:   preserved ({len(after_fips):,} unchanged)")
        print("=" * 70)
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------

def require_file(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Required file not found:\n{path}")


def read_source(path: Path, config: dict) -> pd.DataFrame:
    print(f"Reading: {path.name}")

    df = pd.read_excel(path, sheet_name="County Coverage")

    required_columns = [
        "FIPS",
        "StateAbbr",
        "CountyName",
        config["primary"][1],
    ]

    required_columns.extend(config["supporting"].values())

    missing = [
        column
        for column in required_columns
        if column not in df.columns
    ]

    if missing:
        print("\nActual columns found:")
        for column in df.columns:
            print(f"  {column!r}")

        raise ValueError(
            f"{path.name}: missing required columns:\n"
            + "\n".join(f"  - {column}" for column in missing)
        )

    return df


def normalize_fips(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")

    if numeric.isna().any():
        bad_count = int(numeric.isna().sum())
        raise ValueError(
            f"Found {bad_count} rows with invalid or missing FIPS."
        )

    fips = numeric.astype("int64").astype(str).str.zfill(5)

    if not fips.str.fullmatch(r"\d{5}").all():
        raise ValueError("One or more FIPS values are not five digits.")

    return fips


def clean_numeric(value):
    if pd.isna(value):
        return None

    return float(value)


# ------------------------------------------------------------
# Main build
# ------------------------------------------------------------

def main():

    print("=" * 70)
    print("CHIA v0.1 DATABASE BUILD")
    print("=" * 70)

    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    require_file(SCHEMA_PATH)
    require_file(SEED_PATH)

    for path in SOURCE_FILES.values():
        require_file(path)

    # --------------------------------------------------------
    # Read and validate all sources
    # --------------------------------------------------------

    sources = {}

    for key, path in SOURCE_FILES.items():
        sources[key] = read_source(path, VARIABLES[key])

    print("\nAll source files passed column validation.")

    # --------------------------------------------------------
    # Build canonical county universe
    # --------------------------------------------------------

 # Primary Care HPSA defines the canonical U.S. county universe (FIPS +
    # state_abbr only -- this file's own CountyName column is a placeholder
    # and is not used; see resolve_county_reference / CE-D01 Issue 2).
    primary_care = sources["primary_care"]

    counties = primary_care[
        ["FIPS", "StateAbbr"]
    ].copy()

    counties["county_fips"] = normalize_fips(
        counties["FIPS"]
    )

    counties = counties[
        ["county_fips", "StateAbbr"]
    ].drop_duplicates(
        subset=["county_fips"]
    )

    print(f"County records identified: {len(counties):,}")

    county_records = resolve_county_reference(counties)
    print(
        "County reference records resolved (Census-primary, "
        f"Connecticut-patched): {len(county_records):,}"
    )

    # --------------------------------------------------------
    # Create or update database
    # --------------------------------------------------------

    if DATABASE_PATH.exists():
        # See _replace_county_reference's docstring: a full wipe here would
        # also discard analytical data (most notably MUA/P's
        # dimension_score) that no script in this pipeline currently
        # regenerates from scratch. When the canonical database already
        # exists, only the `county` table's reference fields are replaced.
        _replace_county_reference(DATABASE_PATH, county_records)
        return

    connection = sqlite3.connect(DATABASE_PATH)

    try:

        connection.execute("PRAGMA foreign_keys = ON")

        # Load schema
        schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
        connection.executescript(schema_sql)

        # Load methodology / definitions
        seed_sql = SEED_PATH.read_text(encoding="utf-8")
        connection.executescript(seed_sql)

        # ----------------------------------------------------
        # County
        # ----------------------------------------------------

        connection.executemany(
            """
            INSERT INTO county (
                county_fips,
                state_fips,
                county_name,
                state_name,
                state_abbr
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            county_records,
        )

        # ----------------------------------------------------
        # County period
        # ----------------------------------------------------

        period = "v0.1"

        for _, row in counties.iterrows():

            connection.execute(
                """
                INSERT INTO county_period (
                    county_fips,
                    period,
                    completeness_status
                )
                VALUES (?, ?, ?)
                """,
                (
                    row["county_fips"],
                    period,
                    "pending",
                ),
            )

        # ----------------------------------------------------
        # Source records
        # ----------------------------------------------------

        source_ids = {}

        source_metadata = {
            "primary_care": (
                "Primary Care HPSA",
                "HRSA",
                "Primary Care HPSA Spatial Coverage",
            ),
            "dental": (
                "Dental HPSA",
                "HRSA",
                "Dental HPSA Spatial Coverage",
            ),
            "mental_health": (
                "Mental Health HPSA",
                "HRSA",
                "Mental Health HPSA Spatial Coverage",
            ),
            "mua_p": (
                "MUA/P",
                "HRSA",
                "MUA/P Spatial Coverage",
            ),
        }

        for key, metadata in source_metadata.items():

            name, publisher, dataset = metadata

            artifact_filename = SOURCE_FILES[key].name
            content_sha256 = file_sha256(SOURCE_FILES[key])

            cursor = connection.execute(
                """
                SELECT source_id
                FROM source
                WHERE source_name = ?
                """,
                (name,),
            )

            result = cursor.fetchone()

            if result is None:
                cursor = connection.execute(
                    """
                    INSERT INTO source (
                        source_name,
                        publisher,
                        dataset_name,
                        reference_period,
                        url,
                        accessed_at,
                        artifact_filename,
                        content_sha256
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        name,
                        publisher,
                        dataset,
                        SOURCE_REFERENCE_PERIOD,
                        SOURCE_URL,
                        SOURCE_ACCESSED_AT,
                        artifact_filename,
                        content_sha256,
                    ),
                )

                source_ids[key] = cursor.lastrowid

            else:
                source_ids[key] = result[0]

            # Converge the row on the CE-E12B vintage metadata regardless of
            # whether it was created here or by seed_v01.sql, and recompute the
            # content hash from the file actually consumed by this build.
            connection.execute(
                """
                UPDATE source
                SET reference_period = ?,
                    url = ?,
                    accessed_at = ?,
                    artifact_filename = ?,
                    content_sha256 = ?
                WHERE source_name = ?
                """,
                (
                    SOURCE_REFERENCE_PERIOD,
                    SOURCE_URL,
                    SOURCE_ACCESSED_AT,
                    artifact_filename,
                    content_sha256,
                    name,
                ),
            )

        # ----------------------------------------------------
        # Update variable source IDs
        # ----------------------------------------------------

        variable_source_map = {}

        for key, config in VARIABLES.items():

            primary_variable_id = config["primary"][0]

            variable_source_map[primary_variable_id] = (
                source_ids[key]
            )

            for variable_id in config["supporting"]:
                variable_source_map[variable_id] = (
                    source_ids[key]
                )

        for variable_id, source_id in variable_source_map.items():

            connection.execute(
                """
                UPDATE variable_definition
                SET source_id = ?
                WHERE variable_id = ?
                """,
                (source_id, variable_id),
            )

        # ----------------------------------------------------
        # Variable descriptions
        # ----------------------------------------------------

        variable_descriptions = {
            "PC_HPSA_AREA_WEIGHTED_SCORE":
                "Area-weighted Primary Care HPSA severity score.",
            "PC_HPSA_MAX_SCORE":
                "Maximum Primary Care HPSA severity score.",
            "PC_HPSA_DESIGNATION_COUNT":
                "Count of Primary Care geographic HPSA designations.",
            "DENTAL_HPSA_AREA_WEIGHTED_SCORE":
                "Area-weighted Dental HPSA severity score.",
            "DENTAL_HPSA_MAX_SCORE":
                "Maximum Dental HPSA severity score.",
            "DENTAL_HPSA_DESIGNATION_COUNT":
                "Count of Dental geographic HPSA designations.",
            "MH_HPSA_AREA_WEIGHTED_SCORE":
                "Area-weighted Mental Health HPSA severity score.",
            "MH_HPSA_MAX_SCORE":
                "Maximum Mental Health HPSA severity score.",
            "MH_HPSA_DESIGNATION_COUNT":
                "Count of Mental Health geographic HPSA designations.",
            "MUAP_MEAN_SCORE":
                "Mean MUA/P score among intersecting validated features.",
            "MUAP_MAX_SCORE":
                "Maximum MUA/P score among intersecting validated features.",
            "MUAP_FEATURE_COUNT":
                "Number of intersecting MUA/P features.",
            "MUA_FEATURE_COUNT":
                "Number of MUA features.",
            "MUP_FEATURE_COUNT":
                "Number of MUP features.",
            "MUAP_UNIQUE_SOURCE_COUNT":
                "Number of unique MUA/P source designations.",
        }

        for variable_id, description in variable_descriptions.items():

            connection.execute(
                """
                UPDATE variable_definition
                SET description = ?
                WHERE variable_id = ?
                """,
                (description, variable_id),
            )

        # ----------------------------------------------------
        # Observations
        # ----------------------------------------------------

        county_period_lookup = {
            row[0]: row[1]
            for row in connection.execute(
                """
                SELECT county_fips, county_period_id
                FROM county_period
                WHERE period = ?
                """,
                (period,),
            )
        }

        observation_count = 0

        for key, df in sources.items():

            df = df.copy()
            df["county_fips"] = normalize_fips(df["FIPS"])

            config = VARIABLES[key]

            variable_mappings = {
                config["primary"][0]:
                    config["primary"][1],
                **config["supporting"],
            }

            for _, row in df.iterrows():

                fips = row["county_fips"]

                if fips not in county_period_lookup:
                    continue

                county_period_id = county_period_lookup[fips]

                for variable_id, source_column in variable_mappings.items():

                    value = clean_numeric(row[source_column])

                    connection.execute(
                        """
                        INSERT INTO observation (
                            county_period_id,
                            variable_id,
                            raw_value,
                            quality_flag
                        )
                        VALUES (?, ?, ?, ?)
                        """,
                        (
                            county_period_id,
                            variable_id,
                            value,
                            "source_validated",
                        ),
                    )

                    observation_count += 1

        # ----------------------------------------------------
        # Basic completeness status
        # ----------------------------------------------------

        primary_variables = [
            "PC_HPSA_GEOGRAPHIC_COVERAGE",
            "DENTAL_HPSA_GEOGRAPHIC_COVERAGE",
            "MH_HPSA_GEOGRAPHIC_COVERAGE",
            "MUAP_GEOGRAPHIC_COVERAGE",
        ]

        placeholders = ",".join("?" * len(primary_variables))

        connection.execute(
            f"""
            UPDATE county_period
            SET completeness_status = 'complete'
            WHERE county_period_id IN (
                SELECT county_period_id
                FROM observation
                WHERE variable_id IN ({placeholders})
                GROUP BY county_period_id
                HAVING COUNT(DISTINCT variable_id) = 4
            )
            """,
            primary_variables,
        )

        # ----------------------------------------------------
        # Commit
        # ----------------------------------------------------

        connection.commit()

        # ----------------------------------------------------
        # Validation summary
        # ----------------------------------------------------

        county_count = connection.execute(
            "SELECT COUNT(*) FROM county"
        ).fetchone()[0]

        county_period_count = connection.execute(
            "SELECT COUNT(*) FROM county_period"
        ).fetchone()[0]

        variable_count = connection.execute(
            "SELECT COUNT(*) FROM variable_definition"
        ).fetchone()[0]

        print()
        print("=" * 70)
        print("BUILD COMPLETE")
        print("=" * 70)
        print(f"Database:              {DATABASE_PATH}")
        print(f"Counties:              {county_count:,}")
        print(f"County-periods:        {county_period_count:,}")
        print(f"Variables defined:     {variable_count:,}")
        print(f"Observations loaded:   {observation_count:,}")
        print("=" * 70)

    finally:
        connection.close()


if __name__ == "__main__":
    main()