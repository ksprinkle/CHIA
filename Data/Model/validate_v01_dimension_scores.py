from pathlib import Path
import sqlite3


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATABASE_PATH = PROJECT_ROOT / "Data" / "Model" / "chia_v01.sqlite"

METHOD = "v0.1"

DIMENSIONS = {
    "PRIMARY_CARE": "PC_HPSA_GEOGRAPHIC_COVERAGE",
    "DENTAL": "DENTAL_HPSA_GEOGRAPHIC_COVERAGE",
    "MENTAL_HEALTH": "MH_HPSA_GEOGRAPHIC_COVERAGE",
    "MUA_P": "MUAP_GEOGRAPHIC_COVERAGE",
}


def main():
    print("=" * 70)
    print("CHIA v0.1 DIMENSION SCORE VALIDATION")
    print("=" * 70)

    connection = sqlite3.connect(DATABASE_PATH)

    try:
        total = connection.execute(
            """
            SELECT COUNT(*)
            FROM dimension_score
            WHERE methodology_version = ?
            """,
            (METHOD,),
        ).fetchone()[0]

        print(f"\nTotal dimension scores: {total:,}")

        if total != 12572:
            raise AssertionError(
                f"Expected 12,572 dimension scores, found {total:,}"
            )

        # Every county-period must have exactly four dimensions.
        bad_counties = connection.execute(
            """
            SELECT county_period_id
            FROM dimension_score
            WHERE methodology_version = ?
            GROUP BY county_period_id
            HAVING COUNT(*) != 4
            """,
            (METHOD,),
        ).fetchall()

        if bad_counties:
            raise AssertionError(
                f"{len(bad_counties)} county-periods do not have exactly 4 dimensions."
            )

        print("County-period dimension coverage: PASS")

        # Check each dimension.
        for dimension_id, variable_id in DIMENSIONS.items():
            row = connection.execute(
                """
                SELECT
                    COUNT(*),
                    SUM(CASE WHEN score IS NULL THEN 1 ELSE 0 END)
                FROM dimension_score
                WHERE methodology_version = ?
                  AND dimension_id = ?
                """,
                (METHOD, dimension_id),
            ).fetchone()

            count, missing = row

            print(f"\n{dimension_id}")
            print(f"  Records:        {count:,}")
            print(f"  Missing scores: {missing:,}")

            if count != 3143:
                raise AssertionError(
                    f"{dimension_id}: expected 3,143 scores."
                )

            if missing != 0:
                raise AssertionError(
                    f"{dimension_id}: unexpected missing scores."
                )

            # Verify scores against their source measure.
            if dimension_id != "MUA_P":
                mismatches = connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM dimension_score ds
                    JOIN observation o
                      ON o.county_period_id = ds.county_period_id
                     AND o.variable_id = ?
                    JOIN normalized_measure nm
                      ON nm.observation_id = o.observation_id
                     AND nm.methodology_version = ?
                    WHERE ds.methodology_version = ?
                      AND ds.dimension_id = ?
                      AND ds.score != nm.normalized_value
                    """,
                    (
                        variable_id,
                        METHOD,
                        METHOD,
                        dimension_id,
                    ),
                ).fetchone()[0]
            else:
                mismatches = connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM dimension_score ds
                    JOIN observation o
                      ON o.county_period_id = ds.county_period_id
                     AND o.variable_id = ?
                    WHERE ds.methodology_version = ?
                      AND ds.dimension_id = ?
                      AND ds.score != o.raw_value
                    """,
                    (
                        variable_id,
                        METHOD,
                        dimension_id,
                    ),
                ).fetchone()[0]

            if mismatches:
                raise AssertionError(
                    f"{dimension_id}: {mismatches} score/source mismatches."
                )

            print("  Source measure match: PASS")

        # Composite scores are owned and validated by CE-A05
        # (validate_v01_composite.py); this validator only reports the count.
        composite_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM composite_score
            WHERE methodology_version = ?
            """,
            (METHOD,),
        ).fetchone()[0]

        print(f"\nComposite records: {composite_count}")

        print("\n" + "=" * 70)
        print("DIMENSION SCORE VALIDATION PASSED")
        print("=" * 70)

    finally:
        connection.close()


if __name__ == "__main__":
    main()