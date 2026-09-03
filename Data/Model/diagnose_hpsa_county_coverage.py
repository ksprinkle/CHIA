from pathlib import Path
import sqlite3
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATABASE = PROJECT_ROOT / "Data" / "Model" / "chia_v01.sqlite"
PROCESSED = PROJECT_ROOT / "Data" / "Processed"


HPSA_FILES = {
    "Primary Care": (
        PROCESSED
        / "CHIA_Primary_Care_HPSA_Spatial_Coverage_Validated_FINAL.xlsx"
    ),
    "Dental": (
        PROCESSED
        / "CHIA_Dental_HPSA_Spatial_Coverage_Validated_FINAL.xlsx"
    ),
    "Mental Health": (
        PROCESSED
        / "CHIA_Mental_Health_HPSA_Spatial_Coverage_Validated_FINAL.xlsx"
    ),
}


def normalize_fips(value):
    if pd.isna(value):
        return None

    text = str(value).strip()

    if text.endswith(".0"):
        text = text[:-2]

    return text.zfill(5)


def main():

    print("=" * 70)
    print("CHIA v0.1 — HPSA COUNTY COVERAGE DIAGNOSTIC")
    print("=" * 70)

    # --------------------------------------------------------
    # Database county universe
    # --------------------------------------------------------

    connection = sqlite3.connect(DATABASE)

    db_counties = pd.read_sql_query(
        """
        SELECT county_fips, state_abbr, county_name
        FROM county
        ORDER BY county_fips
        """,
        connection,
    )

    connection.close()

    db_counties["county_fips"] = db_counties["county_fips"].map(normalize_fips)

    print(f"\nDatabase counties: {len(db_counties):,}")

    # --------------------------------------------------------
    # Read HPSA source county universes
    # --------------------------------------------------------

    source_fips = {}

    for name, path in HPSA_FILES.items():

        df = pd.read_excel(
            path,
            sheet_name="County Coverage"
        )

        df["FIPS"] = df["FIPS"].map(normalize_fips)

        source_fips[name] = set(df["FIPS"].dropna())

        print(
            f"{name} source counties: "
            f"{len(source_fips[name]):,}"
        )

    # --------------------------------------------------------
    # Compare coverage
    # --------------------------------------------------------

    db_fips = set(db_counties["county_fips"])

    print("\nCoverage by source:")

    for name, fips in source_fips.items():

        missing = db_fips - fips

        print(
            f"  {name}: "
            f"{len(db_fips & fips):,} covered / "
            f"{len(missing):,} missing"
        )

    # --------------------------------------------------------
    # Counties missing from ALL THREE HPSA sources
    # --------------------------------------------------------

    missing_all = (
        db_fips
        - source_fips["Primary Care"]
        - source_fips["Dental"]
        - source_fips["Mental Health"]
    )

    missing_all_df = db_counties[
        db_counties["county_fips"].isin(missing_all)
    ].copy()

    print("\n" + "=" * 70)
    print(
        f"COUNTIES MISSING FROM ALL THREE HPSA SOURCES: "
        f"{len(missing_all_df):,}"
    )
    print("=" * 70)

    print(
        missing_all_df[
            ["county_fips", "state_abbr", "county_name"]
        ].to_string(index=False)
    )

    # --------------------------------------------------------
    # Save diagnostic output
    # --------------------------------------------------------

    output_path = (
        PROJECT_ROOT
        / "Data"
        / "Processed"
        / "hpsa_county_coverage_diagnostic.csv"
    )

    missing_all_df.to_csv(output_path, index=False)

    print("\nDiagnostic saved:")
    print(output_path)


if __name__ == "__main__":
    main()