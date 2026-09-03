from pathlib import Path
import sqlite3


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATABASE_PATH = PROJECT_ROOT / "Data" / "Model" / "chia_v01.sqlite"

# These must match Data/Model/build_v01_composite_scores.py.
METHODOLOGY_VERSION = "v0.1"
COMPOSITE_DIMENSIONS = ("PRIMARY_CARE", "DENTAL", "MENTAL_HEALTH", "MUA_P")
STATUS_COMPLETE = "experimental_provisional"
STATUS_INCOMPLETE = "experimental_provisional_incomplete"
TOLERANCE = 1e-12
EXPECTED_ROWS = 3143


def main():
    print("=" * 70)
    print("CHIA v0.1 EXPERIMENTAL COMPOSITE VALIDATION")
    print("=" * 70)

    connection = sqlite3.connect(DATABASE_PATH)

    try:
        # ------------------------------------------------------------------
        # 1. Universe and row count.
        # ------------------------------------------------------------------
        universe = [
            row[0]
            for row in connection.execute(
                """
                SELECT county_period_id
                FROM county_period
                WHERE period = ?
                ORDER BY county_period_id
                """,
                (METHODOLOGY_VERSION,),
            )
        ]

        print(f"\nCounty-period universe (v0.1): {len(universe):,}")

        if len(universe) != EXPECTED_ROWS:
            raise AssertionError(
                f"Expected {EXPECTED_ROWS:,} county-periods, found {len(universe):,}."
            )

        total = connection.execute(
            """
            SELECT COUNT(*)
            FROM composite_score
            WHERE methodology_version = ?
            """,
            (METHODOLOGY_VERSION,),
        ).fetchone()[0]

        print(f"Composite score rows (v0.1):   {total:,}")

        if total != EXPECTED_ROWS:
            raise AssertionError(
                f"Expected {EXPECTED_ROWS:,} composite rows, found {total:,}."
            )

        # ------------------------------------------------------------------
        # 2. Exactly one row per county-period; no duplicates or orphans.
        # ------------------------------------------------------------------
        distinct_county_periods = connection.execute(
            """
            SELECT COUNT(DISTINCT county_period_id)
            FROM composite_score
            WHERE methodology_version = ?
            """,
            (METHODOLOGY_VERSION,),
        ).fetchone()[0]

        if distinct_county_periods != EXPECTED_ROWS:
            raise AssertionError(
                "composite_score is not exactly one row per county-period."
            )

        duplicates = connection.execute(
            """
            SELECT county_period_id, methodology_version, COUNT(*)
            FROM composite_score
            GROUP BY county_period_id, methodology_version
            HAVING COUNT(*) > 1
            """
        ).fetchall()

        if duplicates:
            raise AssertionError(f"{len(duplicates)} duplicate composite_score keys.")

        orphans = connection.execute(
            """
            SELECT COUNT(*)
            FROM composite_score AS cs
            LEFT JOIN county_period AS cp
              ON cp.county_period_id = cs.county_period_id
             AND cp.period = ?
            WHERE cs.methodology_version = ?
              AND cp.county_period_id IS NULL
            """,
            (METHODOLOGY_VERSION, METHODOLOGY_VERSION),
        ).fetchone()[0]

        if orphans:
            raise AssertionError(
                f"{orphans} composite rows not mapped to a v0.1 county-period."
            )

        print("One row per county-period: PASS")

        # ------------------------------------------------------------------
        # 3. All four dimensions participate in the composite.
        # ------------------------------------------------------------------
        dimension_ids = [
            row[0]
            for row in connection.execute(
                """
                SELECT DISTINCT dimension_id
                FROM dimension_score
                WHERE methodology_version = ?
                ORDER BY dimension_id
                """,
                (METHODOLOGY_VERSION,),
            )
        ]

        print(f"Dimensions available:          {', '.join(dimension_ids)}")

        for dimension_id in COMPOSITE_DIMENSIONS:
            count = connection.execute(
                """
                SELECT COUNT(*)
                FROM dimension_score
                WHERE methodology_version = ?
                  AND dimension_id = ?
                """,
                (METHODOLOGY_VERSION, dimension_id),
            ).fetchone()[0]

            if count != EXPECTED_ROWS:
                raise AssertionError(
                    f"Dimension {dimension_id} has {count:,} scores; "
                    f"expected {EXPECTED_ROWS:,}."
                )

        print("All four dimensions present:   PASS")

        # ------------------------------------------------------------------
        # 4. Independent per-record validation.
        # ------------------------------------------------------------------
        grouped = {}
        for county_period_id, dimension_id, score in connection.execute(
            """
            SELECT county_period_id, dimension_id, score
            FROM dimension_score
            WHERE methodology_version = ?
              AND dimension_id IN (?, ?, ?, ?)
            """,
            (METHODOLOGY_VERSION, *COMPOSITE_DIMENSIONS),
        ):
            grouped.setdefault(county_period_id, {})[dimension_id] = score

        rows = connection.execute(
            """
            SELECT county_period_id, composite_value, status, missing_dimensions
            FROM composite_score
            WHERE methodology_version = ?
            """,
            (METHODOLOGY_VERSION,),
        ).fetchall()

        complete = 0
        incomplete = 0
        minimum = None
        maximum = None

        for county_period_id, value, status, missing_dimensions in rows:
            available = grouped.get(county_period_id, {})
            unavailable = [
                dimension_id
                for dimension_id in COMPOSITE_DIMENSIONS
                if dimension_id not in available or available[dimension_id] is None
            ]

            if not unavailable:
                complete += 1
                expected_value = (
                    sum(available[dimension_id] for dimension_id in COMPOSITE_DIMENSIONS)
                    / len(COMPOSITE_DIMENSIONS)
                )

                if status != STATUS_COMPLETE:
                    raise AssertionError(
                        f"county_period {county_period_id}: complete composite status "
                        f"is {status!r}, expected {STATUS_COMPLETE!r}."
                    )
                if missing_dimensions is not None:
                    raise AssertionError(
                        f"county_period {county_period_id}: complete composite must not "
                        "name missing dimensions."
                    )
                if value is None:
                    raise AssertionError(
                        f"county_period {county_period_id}: complete composite value is NULL."
                    )
                if abs(value - expected_value) > TOLERANCE:
                    raise AssertionError(
                        f"county_period {county_period_id}: composite {value!r} does not "
                        f"equal the equal-weight four-dimension mean {expected_value!r}."
                    )
                if not (0.0 <= value <= 100.0 + TOLERANCE):
                    raise AssertionError(
                        f"county_period {county_period_id}: composite {value!r} is outside 0-100."
                    )

                minimum = value if minimum is None else min(minimum, value)
                maximum = value if maximum is None else max(maximum, value)
            else:
                incomplete += 1
                if value is not None:
                    raise AssertionError(
                        f"county_period {county_period_id}: incomplete composite must be "
                        "NULL (no partial averaging, no zero substitution)."
                    )
                if status != STATUS_INCOMPLETE:
                    raise AssertionError(
                        f"county_period {county_period_id}: incomplete composite status "
                        f"is {status!r}, expected {STATUS_INCOMPLETE!r}."
                    )
                expected_missing = ", ".join(
                    dimension_id
                    for dimension_id in COMPOSITE_DIMENSIONS
                    if dimension_id in unavailable
                )
                if not missing_dimensions or missing_dimensions != expected_missing:
                    raise AssertionError(
                        f"county_period {county_period_id}: missing_dimensions is "
                        f"{missing_dimensions!r}, expected {expected_missing!r}."
                    )

        # ------------------------------------------------------------------
        # 5. Status label is explicitly Experimental / Provisional.
        # ------------------------------------------------------------------
        for label in {row[2] for row in rows}:
            if "experimental" not in label or "provisional" not in label:
                raise AssertionError(
                    f"Composite status {label!r} is not explicitly Experimental/Provisional."
                )

        print(f"\nComplete composites (all four dimensions): {complete:,}")
        print(f"Incomplete composites (value NULL):        {incomplete:,}")
        if complete:
            print(f"Composite value range:                    {minimum} .. {maximum}")

        foreign_key_errors = connection.execute("PRAGMA foreign_key_check").fetchall()
        if foreign_key_errors:
            raise AssertionError(f"Foreign-key errors: {len(foreign_key_errors)}")

        print("Foreign-key integrity:                     PASS")

        print("\n" + "=" * 70)
        print("EXPERIMENTAL COMPOSITE VALIDATION PASSED (Experimental / Provisional)")
        print("=" * 70)

    finally:
        connection.close()


if __name__ == "__main__":
    main()
