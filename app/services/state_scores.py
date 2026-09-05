"""CE-E09 read-only assembly of per-county dimension scores for one state.

This service returns every county in a state with its four persisted CHIA
access-dimension scores for the v0.1 period, read directly from
``county`` / ``county_period`` / ``dimension_score``. It performs no
analytical calculation, no normalization, no averaging, and never mutates the
database -- it follows the same read-only pattern as
``app/services/county_directory.py`` and ``app/services/county_explorer.py``.

A dimension score that has no persisted row (or a persisted NULL) is reported
as ``available=False`` / ``score=None`` -- exactly how CE-B02's
``DimensionProfile.available`` already models an absent score. A county with no
``county_period`` row for the period is still returned (its dimensions all
unavailable, ``completeness_status=None``) so the county set always matches the
canonical universe for the state.
"""

from __future__ import annotations

from pathlib import Path
import sqlite3
from typing import Union

from app.schemas.state_scores import (
    CountyDimensionScores,
    DimensionScoreEntry,
    StateDimensionScoresResponse,
)


DatabaseSource = Union[sqlite3.Connection, str, Path]

METHODOLOGY_VERSION = "v0.1"

# dimension_id -> response key, in canonical order. Mirrors
# app.services.county_explorer.DIMENSION_KEYS (kept local, matching the
# module-local convention already used there).
DIMENSION_KEYS: tuple[tuple[str, str], ...] = (
    ("PRIMARY_CARE", "primary_care"),
    ("DENTAL", "dental"),
    ("MENTAL_HEALTH", "mental_health"),
    ("MUA_P", "mua_p"),
)


class StateNotFoundError(LookupError):
    """The requested (well-formed) state FIPS has no counties in the canonical
    county universe."""


def load_state_dimension_scores(
    database: DatabaseSource,
    state_fips: str,
    period: str = METHODOLOGY_VERSION,
) -> StateDimensionScoresResponse:
    """Return every county in ``state_fips`` with its four persisted dimension
    scores for ``period``, ordered by ``county_fips`` ascending.

    Raises :class:`StateNotFoundError` if the state has no counties. Raw
    ``sqlite3.Error`` propagates unchanged (the route maps it to HTTP 503).
    """

    connection, close_connection = _connection_for_read(database)
    try:
        rows = connection.execute(
            """
            SELECT c.county_fips,
                   cp.completeness_status,
                   ds.dimension_id,
                   ds.score,
                   ds.status
            FROM county c
            LEFT JOIN county_period cp
                ON cp.county_fips = c.county_fips
               AND cp.period = ?
            LEFT JOIN dimension_score ds
                ON ds.county_period_id = cp.county_period_id
               AND ds.methodology_version = ?
            WHERE c.state_fips = ?
            ORDER BY c.county_fips ASC
            """,
            (period, period, state_fips),
        ).fetchall()
    finally:
        if close_connection:
            connection.close()

    if not rows:
        raise StateNotFoundError(state_fips)

    # Group the flat (county, dimension) rows by county, preserving the SQL
    # county_fips-ascending order.
    ordered_fips: list[str] = []
    completeness: dict[str, str | None] = {}
    scores_by_county: dict[str, dict[str, tuple[float | None, str | None]]] = {}

    for county_fips, completeness_status, dimension_id, score, status in rows:
        if county_fips not in scores_by_county:
            ordered_fips.append(county_fips)
            completeness[county_fips] = completeness_status
            scores_by_county[county_fips] = {}
        if dimension_id is not None:
            scores_by_county[county_fips][dimension_id] = (score, status)

    counties = [
        CountyDimensionScores(
            county_fips=county_fips,
            completeness_status=completeness[county_fips],
            **{
                response_key: _entry(
                    dimension_id, scores_by_county[county_fips].get(dimension_id)
                )
                for dimension_id, response_key in DIMENSION_KEYS
            },
        )
        for county_fips in ordered_fips
    ]

    return StateDimensionScoresResponse(
        state_fips=state_fips,
        period=period,
        count=len(counties),
        counties=counties,
    )


def _entry(
    dimension_id: str, score_row: tuple[float | None, str | None] | None
) -> DimensionScoreEntry:
    score = score_row[0] if score_row is not None else None
    status = score_row[1] if score_row is not None else None
    return DimensionScoreEntry(
        dimension_id=dimension_id,
        available=score is not None,
        score=score,
        score_status=status,
    )


def _connection_for_read(database: DatabaseSource) -> tuple[sqlite3.Connection, bool]:
    if isinstance(database, sqlite3.Connection):
        return database, False
    database_uri = Path(database).resolve().as_uri() + "?mode=ro"
    return sqlite3.connect(database_uri, uri=True), True
