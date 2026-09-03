"""CE-A05 rebuild of the experimental CHIA v0.1 composite access-burden scores.

Per specification section 9, the experimental composite is the EQUAL-WEIGHT
arithmetic mean of the four v0.1 access-dimension scores:

    composite_value = (PRIMARY_CARE + DENTAL + MENTAL_HEALTH + MUA_P) / 4

Rules (all from section 9):

* All four dimension scores must be available. A dimension is "unavailable" when
  it has no ``dimension_score`` row for the county-period at
  ``methodology_version = 'v0.1'`` OR that row's ``score`` is NULL.
* If any dimension is unavailable, ``composite_value`` is NULL and the missing
  dimension(s) are named in ``missing_dimensions`` (canonical order, comma
  separated). No partial averaging and no zero substitution are performed.
* The composite is always labelled Experimental / Provisional via ``status``.
* No rounding or other transformation is applied to the mean.

Exactly one ``composite_score`` row is produced per county-period in the v0.1
universe. The rebuild runs in one explicit transaction, validates the complete
result before committing, rolls the whole transaction back on any failure, and
is idempotent (a successful rerun reproduces the identical desired state).
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
import sqlite3


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATABASE_PATH = PROJECT_ROOT / "Data" / "Model" / "chia_v01.sqlite"

METHODOLOGY_VERSION = "v0.1"

# Canonical order of the four access dimensions contributing 25% each.
COMPOSITE_DIMENSIONS = ("PRIMARY_CARE", "DENTAL", "MENTAL_HEALTH", "MUA_P")

# Every composite row is explicitly Experimental / Provisional.
COMPOSITE_STATUS_COMPLETE = "experimental_provisional"
COMPOSITE_STATUS_INCOMPLETE = "experimental_provisional_incomplete"

# Persisted mean must match an independent recomputation within this tolerance.
ABSOLUTE_TOLERANCE = 1e-12


@dataclass(frozen=True)
class CompositeScoreRebuildSummary:
    """Committed composite-score row counts for one CE-A05 rebuild."""

    total_rows: int
    complete_rows: int
    incomplete_rows: int


def rebuild_composite_scores(
    database_path: str | Path = DATABASE_PATH,
    period: str = METHODOLOGY_VERSION,
) -> CompositeScoreRebuildSummary:
    """Atomically rebuild the experimental v0.1 composite scores.

    All existing ``composite_score`` rows for ``methodology_version = 'v0.1'``
    are replaced with one row per county-period in the ``period`` universe.
    Commits only if the full post-write validation passes; any failure rolls
    back the entire transaction.
    """

    connection = sqlite3.connect(database_path)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("BEGIN IMMEDIATE")

        _require_methodology(connection)

        universe = _county_period_universe(connection, period)
        if not universe:
            raise ValueError(f"No county-period universe for period {period!r}.")

        dimension_scores = _dimension_scores_by_county_period(connection, period)
        records = _build_records(universe, dimension_scores)

        total_before = _composite_total(connection)
        deleted = _replace_composite_records(connection, records)
        inserted = len(records)

        _validate_persisted_records(connection, records, universe, period)
        _validate_totals(connection, total_before, deleted, inserted)

        connection.commit()

        complete_rows = sum(1 for _, _, value, _, _ in records if value is not None)
        return CompositeScoreRebuildSummary(
            total_rows=len(records),
            complete_rows=complete_rows,
            incomplete_rows=len(records) - complete_rows,
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


def _county_period_universe(connection: sqlite3.Connection, period: str) -> list[int]:
    return [
        county_period_id
        for (county_period_id,) in connection.execute(
            """
            SELECT county_period_id
            FROM county_period
            WHERE period = ?
            ORDER BY county_period_id
            """,
            (period,),
        )
    ]


def _dimension_scores_by_county_period(
    connection: sqlite3.Connection,
    period: str,
) -> dict[int, dict[str, float | None]]:
    placeholders = ", ".join("?" for _ in COMPOSITE_DIMENSIONS)
    rows = connection.execute(
        f"""
        SELECT ds.county_period_id, ds.dimension_id, ds.score
        FROM dimension_score AS ds
        JOIN county_period AS cp
          ON cp.county_period_id = ds.county_period_id
        WHERE ds.methodology_version = ?
          AND cp.period = ?
          AND ds.dimension_id IN ({placeholders})
        """,
        (METHODOLOGY_VERSION, period, *COMPOSITE_DIMENSIONS),
    ).fetchall()

    mapping: dict[int, dict[str, float | None]] = {}
    for county_period_id, dimension_id, score in rows:
        per_county = mapping.setdefault(county_period_id, {})
        if dimension_id in per_county:
            raise ValueError(
                f"Duplicate dimension_score row for county-period "
                f"{county_period_id} dimension {dimension_id!r}."
            )
        per_county[dimension_id] = score
    return mapping


def _build_records(
    universe: list[int],
    dimension_scores: dict[int, dict[str, float | None]],
) -> list[tuple]:
    records = []
    for county_period_id in universe:
        available = dimension_scores.get(county_period_id, {})
        present = {
            dimension_id: available[dimension_id]
            for dimension_id in COMPOSITE_DIMENSIONS
            if dimension_id in available and available[dimension_id] is not None
        }
        missing = [
            dimension_id
            for dimension_id in COMPOSITE_DIMENSIONS
            if dimension_id not in present
        ]

        if missing:
            # No partial averaging, no zero substitution: value is NULL and the
            # missing dimension(s) are named.
            records.append(
                (
                    county_period_id,
                    METHODOLOGY_VERSION,
                    None,
                    COMPOSITE_STATUS_INCOMPLETE,
                    ", ".join(missing),
                )
            )
        else:
            composite_value = (
                sum(present[dimension_id] for dimension_id in COMPOSITE_DIMENSIONS)
                / len(COMPOSITE_DIMENSIONS)
            )
            records.append(
                (
                    county_period_id,
                    METHODOLOGY_VERSION,
                    composite_value,
                    COMPOSITE_STATUS_COMPLETE,
                    None,
                )
            )
    return records


def _composite_total(connection: sqlite3.Connection) -> int:
    return connection.execute("SELECT COUNT(*) FROM composite_score").fetchone()[0]


def _replace_composite_records(
    connection: sqlite3.Connection,
    records: list[tuple],
) -> int:
    count_before = connection.execute(
        "SELECT COUNT(*) FROM composite_score WHERE methodology_version = ?",
        (METHODOLOGY_VERSION,),
    ).fetchone()[0]

    deleted = connection.execute(
        "DELETE FROM composite_score WHERE methodology_version = ?",
        (METHODOLOGY_VERSION,),
    ).rowcount

    if deleted != count_before:
        raise ValueError(
            f"Expected to delete {count_before} v0.1 composite-score rows; "
            f"deleted {deleted}."
        )

    connection.executemany(
        """
        INSERT INTO composite_score (
            county_period_id,
            methodology_version,
            composite_value,
            status,
            missing_dimensions
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        records,
    )
    return deleted


def _validate_persisted_records(
    connection: sqlite3.Connection,
    records: list[tuple],
    universe: list[int],
    period: str,
) -> None:
    expected = {
        county_period_id: (composite_value, status, missing_dimensions)
        for county_period_id, _, composite_value, status, missing_dimensions in records
    }

    rows = connection.execute(
        """
        SELECT county_period_id, methodology_version, composite_value, status,
               missing_dimensions
        FROM composite_score
        WHERE methodology_version = ?
        """,
        (METHODOLOGY_VERSION,),
    ).fetchall()

    if len(rows) != len(expected):
        raise ValueError("Persisted composite-score count does not match expectation.")
    if len(rows) != len(universe):
        raise ValueError(
            "There must be exactly one composite-score row per county-period."
        )

    # Independent recomputation straight from dimension_score.
    recomputed = _dimension_scores_by_county_period(connection, period)

    for county_period_id, methodology_version, composite_value, status, missing_dimensions in rows:
        if methodology_version != METHODOLOGY_VERSION:
            raise ValueError("Composite-score methodology_version must be v0.1.")
        if county_period_id not in expected:
            raise ValueError(
                f"Unexpected persisted composite-score row for {county_period_id}."
            )

        available = recomputed.get(county_period_id, {})
        complete = all(
            dimension_id in available and available[dimension_id] is not None
            for dimension_id in COMPOSITE_DIMENSIONS
        )

        if complete:
            independent_value = (
                sum(available[dimension_id] for dimension_id in COMPOSITE_DIMENSIONS)
                / len(COMPOSITE_DIMENSIONS)
            )
            if status != COMPOSITE_STATUS_COMPLETE:
                raise ValueError(
                    f"Complete composite {county_period_id} must use status "
                    f"{COMPOSITE_STATUS_COMPLETE!r}."
                )
            if missing_dimensions is not None:
                raise ValueError(
                    f"Complete composite {county_period_id} must not name missing "
                    "dimensions."
                )
            if composite_value is None or not math.isclose(
                composite_value,
                independent_value,
                rel_tol=0.0,
                abs_tol=ABSOLUTE_TOLERANCE,
            ):
                raise ValueError(
                    f"Composite value for {county_period_id} is not the equal-weight "
                    "four-dimension mean."
                )
            if not 0.0 <= composite_value <= 100.0 + ABSOLUTE_TOLERANCE:
                raise ValueError(
                    f"Composite value for {county_period_id} is outside 0--100."
                )
        else:
            if composite_value is not None:
                raise ValueError(
                    f"Incomplete composite {county_period_id} must have a NULL value "
                    "(no partial averaging, no zero substitution)."
                )
            if status != COMPOSITE_STATUS_INCOMPLETE:
                raise ValueError(
                    f"Incomplete composite {county_period_id} must use status "
                    f"{COMPOSITE_STATUS_INCOMPLETE!r}."
                )
            expected_missing = ", ".join(
                dimension_id
                for dimension_id in COMPOSITE_DIMENSIONS
                if not (
                    dimension_id in available
                    and available[dimension_id] is not None
                )
            )
            if not missing_dimensions or missing_dimensions != expected_missing:
                raise ValueError(
                    f"Incomplete composite {county_period_id} must name its missing "
                    f"dimensions as {expected_missing!r}."
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
        raise ValueError("Duplicate composite-score rows detected.")

    foreign_key_errors = connection.execute("PRAGMA foreign_key_check").fetchall()
    if foreign_key_errors:
        raise ValueError(
            "Foreign-key validation failed during composite-score rebuild."
        )


def _validate_totals(
    connection: sqlite3.Connection,
    total_before: int,
    deleted: int,
    inserted: int,
) -> None:
    total_after = _composite_total(connection)
    if total_after != total_before - deleted + inserted:
        raise ValueError(
            "composite_score total changed by more than the v0.1 replacement."
        )


def main():
    print("=" * 70)
    print("CHIA v0.1 EXPERIMENTAL COMPOSITE SCORES (CE-A05 rebuild)")
    print("=" * 70)

    if not Path(DATABASE_PATH).exists():
        raise FileNotFoundError(f"Database not found:\n{DATABASE_PATH}")

    summary = rebuild_composite_scores(DATABASE_PATH)

    print(f"  Composite rows written: {summary.total_rows:,}")
    print(f"  Complete (all four dimensions): {summary.complete_rows:,}")
    print(f"  Incomplete (value NULL, dimensions named): {summary.incomplete_rows:,}")
    print("\n" + "=" * 70)
    print("EXPERIMENTAL COMPOSITE REBUILD COMPLETE (Experimental / Provisional)")
    print("=" * 70)


if __name__ == "__main__":
    main()
