"""CE-E14a read-only assembly of per-state, display-only dimension medians.

For every state this service returns the median of that state's counties'
persisted CHIA access-dimension scores for the v0.1 period, per dimension.

It is strictly read-only (same pattern as ``app/services/state_scores.py``):
one ``SELECT`` over ``county`` / ``county_period`` / ``dimension_score`` and a
median computed in Python. It performs **no** analytical calculation in the
CHIA sense, writes nothing, and creates no persisted state-level artifact. The
median is a presentational aggregate of already-persisted, versioned county
scores -- see ``Documentation/NATIONAL_MAP_STATE_SUMMARY.md.txt``.

Rules:
* a county with no ``county_period`` row, no ``dimension_score`` row, or a NULL
  score for a dimension does not contribute to that dimension's median;
* a state with no contributing county for a dimension -> ``median = None`` /
  ``available = False`` / ``available_county_count = 0``;
* every state / state-equivalent in the canonical ``county`` table is
  represented (all 51), ordered by ``state_fips`` ascending;
* ``statistics.median`` semantics: for an even number of values the median is
  the mean of the two central values.
"""

from __future__ import annotations

from pathlib import Path
import sqlite3
from statistics import median as _median
from typing import Union

from app.schemas.national_scores import (
    NationalDimensionScoresResponse,
    StateDimensionMedian,
    StateDimensionMedians,
)


DatabaseSource = Union[sqlite3.Connection, str, Path]

METHODOLOGY_VERSION = "v0.1"

# dimension_id -> response key, canonical order. Mirrors
# app.services.state_scores.DIMENSION_KEYS.
DIMENSION_KEYS: tuple[tuple[str, str], ...] = (
    ("PRIMARY_CARE", "primary_care"),
    ("DENTAL", "dental"),
    ("MENTAL_HEALTH", "mental_health"),
    ("MUA_P", "mua_p"),
)

AGGREGATION_RULE = (
    "Per state, per dimension: the median (statistics.median; mean of the two "
    "central values when the count is even) of that state's counties' persisted "
    "v0.1 dimension_score.score. NULL scores excluded; no available county -> "
    "null. Display-only presentational aggregate; not a persisted or validated "
    "state score."
)


def load_national_dimension_scores(
    database: DatabaseSource,
    period: str = METHODOLOGY_VERSION,
) -> NationalDimensionScoresResponse:
    """Return every state's per-dimension display-only median for ``period``.

    Raw ``sqlite3.Error`` propagates unchanged (the route maps it to HTTP 503).
    """

    connection, close_connection = _connection_for_read(database)
    try:
        county_counts: dict[str, int] = {
            state_fips: count
            for state_fips, count in connection.execute(
                "SELECT state_fips, COUNT(*) FROM county GROUP BY state_fips"
            )
        }

        # Only rows with a real, non-null persisted score contribute.
        score_rows = connection.execute(
            """
            SELECT c.state_fips, ds.dimension_id, ds.score
            FROM county AS c
            JOIN county_period AS cp
                ON cp.county_fips = c.county_fips
               AND cp.period = ?
            JOIN dimension_score AS ds
                ON ds.county_period_id = cp.county_period_id
               AND ds.methodology_version = ?
            WHERE ds.score IS NOT NULL
            """,
            (period, period),
        ).fetchall()
    finally:
        if close_connection:
            connection.close()

    values: dict[tuple[str, str], list[float]] = {}
    for state_fips, dimension_id, score in score_rows:
        values.setdefault((state_fips, dimension_id), []).append(float(score))

    states = [
        StateDimensionMedians(
            state_fips=state_fips,
            **{
                response_key: _entry(
                    dimension_id,
                    values.get((state_fips, dimension_id), []),
                    county_counts[state_fips],
                )
                for dimension_id, response_key in DIMENSION_KEYS
            },
        )
        for state_fips in sorted(county_counts)
    ]

    return NationalDimensionScoresResponse(
        period=period,
        aggregation=AGGREGATION_RULE,
        count=len(states),
        states=states,
    )


def _entry(
    dimension_id: str, scores: list[float], county_count: int
) -> StateDimensionMedian:
    available_county_count = len(scores)
    return StateDimensionMedian(
        dimension_id=dimension_id,
        available=available_county_count > 0,
        median=_median(scores) if scores else None,
        county_count=county_count,
        available_county_count=available_county_count,
    )


def _connection_for_read(database: DatabaseSource) -> tuple[sqlite3.Connection, bool]:
    if isinstance(database, sqlite3.Connection):
        return database, False
    database_uri = Path(database).resolve().as_uri() + "?mode=ro"
    return sqlite3.connect(database_uri, uri=True), True
