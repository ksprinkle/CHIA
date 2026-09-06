"""CE-E14a national (per-state) dimension-scores API router.

``GET /api/v1/states/dimension-scores`` -- read-only. Returns, for every state,
a **display-only** per-dimension median of that state's counties' persisted
CHIA access-dimension scores for the v0.1 period.

The median is computed at request time from the already persisted, versioned
county ``dimension_score`` rows. It is a presentational aggregate for the
national map's measure view (governing v0.2 UX specification section 4.6 /
7.2); it is not a validated state-level CHIA score, is never persisted, and
does not extend or version the CHIA v0.1 analytical methodology. See
``Documentation/NATIONAL_MAP_STATE_SUMMARY.md.txt``.

Error semantics (mirroring CE-E09):
* database unavailable / structurally unusable -> 503
* otherwise -> 200 (all 51 states; per-state/dimension ``median``/``available``
  reflect the persisted state)

This path (``/states/dimension-scores``, two segments) does not collide with
CE-E09's ``/states/{state_fips}/dimension-scores`` (three segments).
"""

from __future__ import annotations

from collections.abc import Iterator
import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from app.db import open_readonly_connection
from app.schemas.national_scores import (
    NationalDimensionScoresResponse,
    NationalScoresErrorResponse,
)
from app.services.national_scores import load_national_dimension_scores


router = APIRouter(tags=["national-dimension-scores"])

_DB_UNAVAILABLE = "The canonical database is currently unavailable."


def get_national_scores_connection() -> Iterator[sqlite3.Connection]:
    """Yield a request-scoped read-only connection.

    A failure to *open* the canonical database is an infrastructure failure and
    surfaces as HTTP 503.
    """

    try:
        connection = open_readonly_connection()
    except sqlite3.Error as exc:  # pragma: no cover - exercised via dependency override
        raise HTTPException(status_code=503, detail=_DB_UNAVAILABLE) from exc

    try:
        yield connection
    finally:
        connection.close()


@router.get(
    "/states/dimension-scores",
    response_model=NationalDimensionScoresResponse,
    summary="Display-only per-state median of county access-dimension scores",
    responses={
        503: {
            "model": NationalScoresErrorResponse,
            "description": "Canonical data unavailable",
        },
    },
)
def get_national_dimension_scores(
    connection: sqlite3.Connection = Depends(get_national_scores_connection),
) -> NationalDimensionScoresResponse:
    """Return every state's per-dimension display-only median for the v0.1 period.

    Each median is the median of that state's counties' persisted
    ``dimension_score.score`` values (NULLs excluded); nothing is recomputed in
    the CHIA analytical sense and the database is never modified.
    """

    try:
        return load_national_dimension_scores(connection)
    except sqlite3.Error as exc:
        raise HTTPException(status_code=503, detail=_DB_UNAVAILABLE) from exc
