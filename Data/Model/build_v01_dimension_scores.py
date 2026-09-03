"""CE-A04 rebuild of the approved CHIA v0.1 dimension scores.

Each of the three normalized access dimensions takes an *identity copy* of the
CE-A03 ``normalized_measure.normalized_value`` (0-100 county percentile rank)
for its canonical primary variable:

    PRIMARY_CARE   <- PC_HPSA_GEOGRAPHIC_COVERAGE
    DENTAL         <- DENTAL_HPSA_GEOGRAPHIC_COVERAGE
    MENTAL_HEALTH  <- MH_HPSA_GEOGRAPHIC_COVERAGE

No transformation, rescaling, weighting, inversion, or supporting-variable
contribution is applied. A NULL normalized value is copied through as NULL; a
valid zero stays exactly ``0.0``; tied values keep whatever CE-A00/CE-A03
produced.

The MUA/P dimension is deliberately NOT rebuilt here: its primary variable is
not percentile-normalized in v0.1, so its existing ``dimension_score`` rows are
left byte-for-byte unchanged.

The rebuild runs in one explicit transaction, validates the complete result
before committing, rolls the whole transaction back on any failure, and is
idempotent (a successful rerun reproduces the identical desired state).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATABASE_PATH = PROJECT_ROOT / "Data" / "Model" / "chia_v01.sqlite"

METHODOLOGY_VERSION = "v0.1"
DIMENSION_STATUS = "calculated"

# dimension_id -> canonical primary variable_id (approved CE-A04 mapping).
TARGET_DIMENSIONS = {
    "PRIMARY_CARE": "PC_HPSA_GEOGRAPHIC_COVERAGE",
    "DENTAL": "DENTAL_HPSA_GEOGRAPHIC_COVERAGE",
    "MENTAL_HEALTH": "MH_HPSA_GEOGRAPHIC_COVERAGE",
}

# Left completely untouched by this rebuild (unnormalized primary variable in
# v0.1). Never deleted, inserted, or referenced.
UNTOUCHED_DIMENSION = "MUA_P"


@dataclass(frozen=True)
class DimensionScoreRebuildSummary:
    """Committed dimension-score row counts for one CE-A04 rebuild."""

    counts_by_dimension: dict[str, int]


def rebuild_dimension_scores(
    database_path: str | Path = DATABASE_PATH,
    period: str = METHODOLOGY_VERSION,
) -> DimensionScoreRebuildSummary:
    """Atomically rebuild the three normalized dimension scores.

    ``dimension_score.score`` becomes an identity copy of the matching
    ``normalized_measure.normalized_value``. Only PRIMARY_CARE / DENTAL /
    MENTAL_HEALTH rows for ``methodology_version = 'v0.1'`` are replaced;
    MUA/P and every other table are untouched. Commits only if all post-write
    validation passes; any failure rolls back the entire transaction.
    """

    connection = sqlite3.connect(database_path)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("BEGIN IMMEDIATE")

        _require_methodology(connection)
        _require_dimension_definitions(connection)

        universe_size = connection.execute(
            "SELECT COUNT(*) FROM county_period WHERE period = ?",
            (period,),
        ).fetchone()[0]
        if universe_size == 0:
            raise ValueError(f"No county-period universe for period {period!r}.")

        records_by_dimension = {
            dimension_id: _prepare_dimension_records(
                connection, dimension_id, variable_id, period, universe_size
            )
            for dimension_id, variable_id in TARGET_DIMENSIONS.items()
        }

        untouched_before = _untouched_dimension_rows(connection)
        total_before = _dimension_score_total(connection)

        deleted = _replace_target_records(connection, records_by_dimension)
        inserted = sum(len(records) for records in records_by_dimension.values())

        _validate_persisted_records(connection, records_by_dimension, universe_size)
        _validate_untouched_and_totals(
            connection, untouched_before, total_before, deleted, inserted
        )

        connection.commit()
        return DimensionScoreRebuildSummary(
            counts_by_dimension={
                dimension_id: len(records)
                for dimension_id, records in records_by_dimension.items()
            }
        )
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _require_methodology(connection: sqlite3.Connection) -> None:
    row = connection.execute(
        "SELECT 1 FROM methodology WHERE methodology_version = ?",
        (METHODOLOGY_VERSION,),
    ).fetchone()
    if row is None:
        raise ValueError(f"Methodology {METHODOLOGY_VERSION!r} does not exist.")


def _require_dimension_definitions(connection: sqlite3.Connection) -> None:
    for dimension_id, variable_id in TARGET_DIMENSIONS.items():
        row = connection.execute(
            "SELECT primary_variable_id FROM dimension_definition WHERE dimension_id = ?",
            (dimension_id,),
        ).fetchone()
        if row is None:
            raise ValueError(f"dimension_definition {dimension_id!r} is missing.")
        if row[0] != variable_id:
            raise ValueError(
                f"dimension_definition {dimension_id!r} primary_variable_id is "
                f"{row[0]!r}, expected {variable_id!r}."
            )


def _prepare_dimension_records(
    connection: sqlite3.Connection,
    dimension_id: str,
    variable_id: str,
    period: str,
    universe_size: int,
) -> list[tuple]:
    rows = connection.execute(
        """
        SELECT o.county_period_id, nm.normalized_value
        FROM county_period AS cp
        JOIN observation AS o
          ON o.county_period_id = cp.county_period_id
        JOIN normalized_measure AS nm
          ON nm.observation_id = o.observation_id
         AND nm.methodology_version = ?
        WHERE o.variable_id = ?
          AND cp.period = ?
        ORDER BY o.county_period_id
        """,
        (METHODOLOGY_VERSION, variable_id, period),
    ).fetchall()

    county_period_ids = [county_period_id for county_period_id, _ in rows]
    if len(county_period_ids) != universe_size:
        raise ValueError(
            f"{dimension_id}: expected {universe_size} normalized measures for "
            f"{variable_id!r} (complete {period!r} county universe), found "
            f"{len(county_period_ids)}."
        )
    if len(set(county_period_ids)) != len(county_period_ids):
        raise ValueError(
            f"{dimension_id}: duplicate county_period_id in source measures."
        )

    # Identity copy: score IS the normalized value (NULL passes through as NULL).
    return [
        (
            county_period_id,
            dimension_id,
            normalized_value,
            METHODOLOGY_VERSION,
            DIMENSION_STATUS,
        )
        for county_period_id, normalized_value in rows
    ]


def _untouched_dimension_rows(connection: sqlite3.Connection) -> list[tuple]:
    return connection.execute(
        """
        SELECT county_period_id, dimension_id, score, methodology_version, status
        FROM dimension_score
        WHERE dimension_id = ?
        ORDER BY county_period_id, methodology_version
        """,
        (UNTOUCHED_DIMENSION,),
    ).fetchall()


def _dimension_score_total(connection: sqlite3.Connection) -> int:
    return connection.execute("SELECT COUNT(*) FROM dimension_score").fetchone()[0]


def _replace_target_records(
    connection: sqlite3.Connection,
    records_by_dimension: dict[str, list[tuple]],
) -> int:
    dimension_ids = tuple(TARGET_DIMENSIONS)
    placeholders = ", ".join("?" for _ in dimension_ids)

    count_before = connection.execute(
        f"""
        SELECT COUNT(*)
        FROM dimension_score
        WHERE methodology_version = ?
          AND dimension_id IN ({placeholders})
        """,
        (METHODOLOGY_VERSION, *dimension_ids),
    ).fetchone()[0]

    deleted = connection.execute(
        f"""
        DELETE FROM dimension_score
        WHERE methodology_version = ?
          AND dimension_id IN ({placeholders})
        """,
        (METHODOLOGY_VERSION, *dimension_ids),
    ).rowcount

    if deleted != count_before:
        raise ValueError(
            f"Expected to delete {count_before} target dimension-score rows; "
            f"deleted {deleted}."
        )

    records = [
        record
        for dimension_records in records_by_dimension.values()
        for record in dimension_records
    ]
    connection.executemany(
        """
        INSERT INTO dimension_score (
            county_period_id,
            dimension_id,
            score,
            methodology_version,
            status
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        records,
    )
    return deleted


def _validate_persisted_records(
    connection: sqlite3.Connection,
    records_by_dimension: dict[str, list[tuple]],
    universe_size: int,
) -> None:
    expected = {
        (county_period_id, dimension_id): (score, methodology_version, status)
        for dimension_records in records_by_dimension.values()
        for county_period_id, dimension_id, score, methodology_version, status in dimension_records
    }

    dimension_ids = tuple(TARGET_DIMENSIONS)
    placeholders = ", ".join("?" for _ in dimension_ids)
    rows = connection.execute(
        f"""
        SELECT county_period_id, dimension_id, score, methodology_version, status
        FROM dimension_score
        WHERE methodology_version = ?
          AND dimension_id IN ({placeholders})
        """,
        (METHODOLOGY_VERSION, *dimension_ids),
    ).fetchall()

    if len(rows) != len(expected):
        raise ValueError(
            "Persisted dimension-score count does not match expectation."
        )

    for county_period_id, dimension_id, score, methodology_version, status in rows:
        key = (county_period_id, dimension_id)
        if key not in expected:
            raise ValueError(f"Unexpected persisted dimension-score row {key}.")
        expected_score, expected_version, expected_status = expected[key]
        if methodology_version != expected_version or status != expected_status:
            raise ValueError(f"Dimension-score metadata mismatch for {key}.")
        if expected_score is None:
            if score is not None:
                raise ValueError(
                    f"Missing normalized value must persist as NULL for {key}."
                )
        elif score is None or score != expected_score:
            raise ValueError(
                f"Dimension score is not an exact identity copy for {key}."
            )

    per_dimension = connection.execute(
        f"""
        SELECT dimension_id, COUNT(*)
        FROM dimension_score
        WHERE methodology_version = ?
          AND dimension_id IN ({placeholders})
        GROUP BY dimension_id
        """,
        (METHODOLOGY_VERSION, *dimension_ids),
    ).fetchall()
    if len(per_dimension) != len(dimension_ids) or any(
        count != universe_size for _, count in per_dimension
    ):
        raise ValueError(
            f"Each rebuilt dimension must have exactly {universe_size} rows "
            "(one per county in the universe)."
        )

    duplicates = connection.execute(
        """
        SELECT county_period_id, dimension_id, methodology_version, COUNT(*)
        FROM dimension_score
        GROUP BY county_period_id, dimension_id, methodology_version
        HAVING COUNT(*) > 1
        """
    ).fetchall()
    if duplicates:
        raise ValueError("Duplicate dimension-score rows detected.")

    foreign_key_errors = connection.execute("PRAGMA foreign_key_check").fetchall()
    if foreign_key_errors:
        raise ValueError(
            "Foreign-key validation failed during dimension-score rebuild."
        )


def _validate_untouched_and_totals(
    connection: sqlite3.Connection,
    untouched_before: list[tuple],
    total_before: int,
    deleted: int,
    inserted: int,
) -> None:
    untouched_after = _untouched_dimension_rows(connection)
    if untouched_after != untouched_before:
        raise ValueError(
            f"{UNTOUCHED_DIMENSION} dimension-score rows were modified by the rebuild."
        )

    total_after = _dimension_score_total(connection)
    if total_after != total_before - deleted + inserted:
        raise ValueError(
            "dimension_score total changed by more than the target replacement."
        )


def main():
    print("=" * 70)
    print("CHIA v0.1 DIMENSION SCORES (CE-A04 rebuild)")
    print("=" * 70)

    if not Path(DATABASE_PATH).exists():
        raise FileNotFoundError(f"Database not found:\n{DATABASE_PATH}")

    summary = rebuild_dimension_scores(DATABASE_PATH)

    for dimension_id, count in summary.counts_by_dimension.items():
        print(
            f"  {dimension_id}: {count:,} rows "
            f"(identity copy of normalized_measure.normalized_value)"
        )
    print(f"  {UNTOUCHED_DIMENSION}: untouched")

    total = sum(summary.counts_by_dimension.values())
    print("\n" + "=" * 70)
    print("DIMENSION SCORE REBUILD COMPLETE")
    print("=" * 70)
    print(f"Dimension-score records rebuilt: {total:,}")
    print("=" * 70)


if __name__ == "__main__":
    main()
