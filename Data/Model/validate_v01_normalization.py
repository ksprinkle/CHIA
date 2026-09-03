from pathlib import Path
import sqlite3


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATABASE_PATH = PROJECT_ROOT / "Data" / "Model" / "chia_v01.sqlite"

METHOD = "county_percentile_rank_average"

# CHIA v0.1 normalized measures use the approved county percentile-rank scale
# of 0-100 (CE-A00 formula, CE-A02 persistence), not the legacy 0-1 pandas
# ``rank(pct=True)`` scale.
SCALE_MIN = 0.0
SCALE_MAX = 100.0
SCALE_TOLERANCE = 1e-9

VARIABLES = [
    "PC_HPSA_GEOGRAPHIC_COVERAGE",
    "DENTAL_HPSA_GEOGRAPHIC_COVERAGE",
    "MH_HPSA_GEOGRAPHIC_COVERAGE",
]


def main():
    print("=" * 70)
    print("CHIA v0.1 NORMALIZATION VALIDATION")
    print("=" * 70)

    connection = sqlite3.connect(DATABASE_PATH)

    try:
        total = connection.execute(
            """
            SELECT COUNT(*)
            FROM normalized_measure
            WHERE methodology_version = ?
            """,
            ("v0.1",),
        ).fetchone()[0]

        print(f"\nTotal normalized records: {total:,}")

        expected_total = 3 * 3143

        if total != expected_total:
            raise AssertionError(
                f"Expected {expected_total:,}, found {total:,}"
            )

        for variable_id in VARIABLES:
            row = connection.execute(
                """
                SELECT
                    COUNT(*) AS total,
                    SUM(CASE WHEN o.raw_value IS NULL THEN 1 ELSE 0 END),
                    SUM(CASE WHEN o.raw_value = 0 THEN 1 ELSE 0 END),
                    SUM(CASE WHEN o.raw_value > 0 THEN 1 ELSE 0 END),
                    SUM(CASE WHEN nm.normalized_value IS NULL THEN 1 ELSE 0 END),
                    MIN(nm.normalized_value),
                    MAX(nm.normalized_value)
                FROM normalized_measure nm
                JOIN observation o
                  ON o.observation_id = nm.observation_id
                WHERE nm.methodology_version = ?
                  AND o.variable_id = ?
                """,
                ("v0.1", variable_id),
            ).fetchone()

            (
                total_rows,
                raw_missing,
                raw_zero,
                raw_positive,
                normalized_missing,
                min_value,
                max_value,
            ) = row

            print(f"\n{variable_id}")
            print(f"  Records:              {total_rows:,}")
            print(f"  Raw missing:          {raw_missing:,}")
            print(f"  Raw zero:             {raw_zero:,}")
            print(f"  Raw positive:         {raw_positive:,}")
            print(f"  Normalized missing:   {normalized_missing:,}")
            print(f"  Normalized minimum:   {min_value}")
            print(f"  Normalized maximum:   {max_value}")

            if total_rows != 3143:
                raise AssertionError("Expected 3,143 records.")

            # Every persisted row for a target variable must carry the approved
            # normalization method (methodology_version = v0.1 is already
            # enforced by the WHERE clause on every query in this validator).
            method_errors = connection.execute(
                """
                SELECT COUNT(*)
                FROM normalized_measure nm
                JOIN observation o
                  ON o.observation_id = nm.observation_id
                WHERE nm.methodology_version = ?
                  AND o.variable_id = ?
                  AND nm.normalization_method != ?
                """,
                ("v0.1", variable_id, METHOD),
            ).fetchone()[0]

            if method_errors:
                raise AssertionError(
                    f"{method_errors} rows do not use "
                    f"normalization_method = {METHOD!r}."
                )

            # Missing raw observations remain NULL and receive no normalized
            # score; every present raw observation receives one.
            missing_with_score = connection.execute(
                """
                SELECT COUNT(*)
                FROM normalized_measure nm
                JOIN observation o
                  ON o.observation_id = nm.observation_id
                WHERE nm.methodology_version = ?
                  AND o.variable_id = ?
                  AND o.raw_value IS NULL
                  AND nm.normalized_value IS NOT NULL
                """,
                ("v0.1", variable_id),
            ).fetchone()[0]

            if missing_with_score:
                raise AssertionError(
                    f"{missing_with_score} missing observations received a "
                    "normalized score."
                )

            present_without_score = connection.execute(
                """
                SELECT COUNT(*)
                FROM normalized_measure nm
                JOIN observation o
                  ON o.observation_id = nm.observation_id
                WHERE nm.methodology_version = ?
                  AND o.variable_id = ?
                  AND o.raw_value IS NOT NULL
                  AND nm.normalized_value IS NULL
                """,
                ("v0.1", variable_id),
            ).fetchone()[0]

            if present_without_score:
                raise AssertionError(
                    f"{present_without_score} present observations have no "
                    "normalized score."
                )

            if min_value != 0.0:
                raise AssertionError(
                    "Expected minimum normalized value to be 0.0."
                )

            if raw_positive and not (0 < max_value <= SCALE_MAX + SCALE_TOLERANCE):
                raise AssertionError(
                    "Expected maximum normalized value to be greater than 0 "
                    f"and at most {SCALE_MAX}."
                )

            # Zero raw values must remain exactly zero.
            zero_errors = connection.execute(
                """
                SELECT COUNT(*)
                FROM normalized_measure nm
                JOIN observation o
                  ON o.observation_id = nm.observation_id
                WHERE nm.methodology_version = ?
                  AND o.variable_id = ?
                  AND o.raw_value = 0
                  AND nm.normalized_value != 0
                """,
                ("v0.1", variable_id),
            ).fetchone()[0]

            if zero_errors:
                raise AssertionError(
                    f"{zero_errors} zero values were not preserved."
                )

            # Positive raw values must receive a (non-NULL) normalized score.
            # The CE-A00 formula legitimately assigns exactly 0.0 to the
            # smallest positive observation, so a normalized value of 0.0 for a
            # positive raw value is NOT an error and is no longer checked.
            positive_errors = connection.execute(
                """
                SELECT COUNT(*)
                FROM normalized_measure nm
                JOIN observation o
                  ON o.observation_id = nm.observation_id
                WHERE nm.methodology_version = ?
                  AND o.variable_id = ?
                  AND o.raw_value > 0
                  AND nm.normalized_value IS NULL
                """,
                ("v0.1", variable_id),
            ).fetchone()[0]

            if positive_errors:
                raise AssertionError(
                    f"{positive_errors} positive raw values have no normalized score."
                )

            # Every non-NULL normalized value must fall within the 0-100 scale.
            range_errors = connection.execute(
                """
                SELECT COUNT(*)
                FROM normalized_measure nm
                JOIN observation o
                  ON o.observation_id = nm.observation_id
                WHERE nm.methodology_version = ?
                  AND o.variable_id = ?
                  AND nm.normalized_value IS NOT NULL
                  AND (
                      nm.normalized_value < ? - ?
                      OR nm.normalized_value > ? + ?
                  )
                """,
                (
                    "v0.1",
                    variable_id,
                    SCALE_MIN,
                    SCALE_TOLERANCE,
                    SCALE_MAX,
                    SCALE_TOLERANCE,
                ),
            ).fetchone()[0]

            if range_errors:
                raise AssertionError(
                    f"{range_errors} normalized values are outside "
                    f"{SCALE_MIN}-{SCALE_MAX}."
                )

            print("  Status:               PASS")

        print("\n" + "=" * 70)
        print("NORMALIZATION VALIDATION PASSED")
        print("=" * 70)

    finally:
        connection.close()


if __name__ == "__main__":
    main()