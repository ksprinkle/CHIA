from pathlib import Path
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

 # Primary Care HPSA defines the canonical U.S. county universe.
    primary_care = sources["primary_care"]

    counties = primary_care[
        ["FIPS", "StateAbbr", "CountyName"]
    ].copy()

    counties["county_fips"] = normalize_fips(
        counties["FIPS"]
    )

    counties = counties[
        ["county_fips", "StateAbbr", "CountyName"]
    ].drop_duplicates(
        subset=["county_fips"]
    )

    print(f"County records identified: {len(counties):,}")

    # --------------------------------------------------------
    # Create database
    # --------------------------------------------------------

    if DATABASE_PATH.exists():
        DATABASE_PATH.unlink()

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

        for _, row in counties.iterrows():

            fips = row["county_fips"]

            state_abbr = (
                None
                if pd.isna(row["StateAbbr"])
                else str(row["StateAbbr"]).strip()
            )

            county_name = (
                None
                if pd.isna(row["CountyName"])
                else str(row["CountyName"]).strip()
            )

            connection.execute(
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
                (
                    fips,
                    fips[:2],
                    county_name or f"FIPS {fips}",
                    "",
                    state_abbr or "",
                ),
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
                        reference_period
                    )
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        name,
                        publisher,
                        dataset,
                        period,
                    ),
                )

                source_ids[key] = cursor.lastrowid

            else:
                source_ids[key] = result[0]

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