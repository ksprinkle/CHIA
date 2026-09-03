from pathlib import Path
import sqlite3


# ============================================================
# CHIA v0.1 — Database Validation
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATABASE_PATH = PROJECT_ROOT / "Data" / "Model" / "chia_v01.sqlite"


PRIMARY_VARIABLES = [
    "PC_HPSA_GEOGRAPHIC_COVERAGE",
    "DENTAL_HPSA_GEOGRAPHIC_COVERAGE",
    "MH_HPSA_GEOGRAPHIC_COVERAGE",
    "MUAP_GEOGRAPHIC_COVERAGE",
]


def check(label, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}")

    if detail:
        print(f"       {detail}")

    return condition


def main():

    print("=" * 70)
    print("CHIA v0.1 DATABASE VALIDATION")
    print("=" * 70)

    if not DATABASE_PATH.exists():
        raise FileNotFoundError(
            f"Database not found:\n{DATABASE_PATH}"
        )

    connection = sqlite3.connect(DATABASE_PATH)

    try:

        connection.execute("PRAGMA foreign_keys = ON")

        failures = 0

        # ----------------------------------------------------
        # 1. Basic record counts
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

        observation_count = connection.execute(
            "SELECT COUNT(*) FROM observation"
        ).fetchone()[0]

        if not check(
            "County count",
            county_count == 3143,
            f"Found {county_count:,}; expected 3,143."
        ):
            failures += 1

        if not check(
            "County-period count",
            county_period_count == 3143,
            f"Found {county_period_count:,}; expected 3,143."
        ):
            failures += 1

        if not check(
            "Variable count",
            variable_count == 19,
            f"Found {variable_count:,}; expected 19."
        ):
            failures += 1

        if not check(
            "Observation count",
            observation_count == 59717,
            f"Found {observation_count:,}; expected 59,717."
        ):
            failures += 1

        # ----------------------------------------------------
        # 2. Duplicate county FIPS
        # ----------------------------------------------------

        duplicate_counties = connection.execute(
            """
            SELECT COUNT(*)
            FROM (
                SELECT county_fips
                FROM county
                GROUP BY county_fips
                HAVING COUNT(*) > 1
            )
            """
        ).fetchone()[0]

        if not check(
            "Duplicate county FIPS",
            duplicate_counties == 0,
            f"Duplicate county IDs: {duplicate_counties}"
        ):
            failures += 1

        # ----------------------------------------------------
        # 3. Duplicate observations
        # ----------------------------------------------------

        duplicate_observations = connection.execute(
            """
            SELECT COUNT(*)
            FROM (
                SELECT county_period_id, variable_id
                FROM observation
                GROUP BY county_period_id, variable_id
                HAVING COUNT(*) > 1
            )
            """
        ).fetchone()[0]

        if not check(
            "Duplicate observations",
            duplicate_observations == 0,
            f"Duplicate observation groups: {duplicate_observations}"
        ):
            failures += 1

        # ----------------------------------------------------
        # 4. Required primary variables
        # ----------------------------------------------------

        print("\nPrimary access dimensions:")

        for variable_id in PRIMARY_VARIABLES:

            count = connection.execute(
                """
                SELECT COUNT(*)
                FROM observation
                WHERE variable_id = ?
                """,
                (variable_id,)
            ).fetchone()[0]

            if not check(
                variable_id,
                count == 3143,
                f"{count:,} observations; expected 3,143."
            ):
                failures += 1

        # ----------------------------------------------------
        # 5. Missing primary values
        # ----------------------------------------------------

        print("\nPrimary-variable completeness:")

        for variable_id in PRIMARY_VARIABLES:

            total = connection.execute(
                """
                SELECT COUNT(*)
                FROM observation
                WHERE variable_id = ?
                """,
                (variable_id,)
            ).fetchone()[0]

            missing = connection.execute(
                """
                SELECT COUNT(*)
                FROM observation
                WHERE variable_id = ?
                  AND raw_value IS NULL
                """,
                (variable_id,)
            ).fetchone()[0]

            present = total - missing

            print(
                f"    {variable_id}: "
                f"{present:,} present / "
                f"{missing:,} missing"
            )

        # ----------------------------------------------------
        # 6. Invalid FIPS
        # ----------------------------------------------------

        invalid_fips = connection.execute(
            """
            SELECT COUNT(*)
            FROM county
            WHERE LENGTH(county_fips) != 5
               OR county_fips GLOB '*[^0-9]*'
            """
        ).fetchone()[0]

        if not check(
            "FIPS format",
            invalid_fips == 0,
            f"Invalid FIPS records: {invalid_fips}"
        ):
            failures += 1

        # ----------------------------------------------------
        # 7. Foreign-key integrity
        # ----------------------------------------------------

        foreign_key_errors = connection.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()

        if not check(
            "Foreign-key integrity",
            len(foreign_key_errors) == 0,
            f"Foreign-key errors: {len(foreign_key_errors)}"
        ):
            failures += 1

        # ----------------------------------------------------
        # 8. County completeness status
        # ----------------------------------------------------

        complete_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM county_period
            WHERE completeness_status = 'complete'
            """
        ).fetchone()[0]

        print(
            f"\nCounty-period completeness: "
            f"{complete_count:,} / {county_period_count:,}"
        )

        # ----------------------------------------------------
        # Final result
        # ----------------------------------------------------

        print()
        print("=" * 70)

        if failures == 0:
            print("VALIDATION PASSED")
            print("The v0.1 database passed all structural checks.")
        else:
            print("VALIDATION FAILED")
            print(f"Checks failed: {failures}")

        print("=" * 70)

        if failures:
            raise SystemExit(1)

    finally:
        connection.close()


if __name__ == "__main__":
    main()