"""CE-E09 state dimension-scores API router.

``GET /api/v1/states/{state_fips}/dimension-scores`` -- read-only. Returns
every county in a state with its four persisted CHIA access-dimension scores
for the v0.1 period, straight from ``dimension_score`` / ``county_period``. No
analytical calculation, no normalization, no averaging, no database writes.

Error semantics (mirroring the CE-B02 Explorer router):
* malformed ``state_fips`` (not exactly two digits) -> 422 (before any query)
* well-formed but unknown state (no counties)       -> 404
* state exists, some analytical data absent         -> 200 (per-county
                                                      ``available``/``score``
                                                      reflect the persisted
                                                      state)
* database unavailable / structurally unusable      -> 503
"""

from __future__ import annotations

from collections.abc import Iterator
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Path

from app.db import open_readonly_connection
from app.schemas.state_scores import (
    StateDimensionScoresResponse,
    StateScoresErrorResponse,
)
from app.services.state_scores import StateNotFoundError, load_state_dimension_scores


router = APIRouter(tags=["state-dimension-scores"])

_DB_UNAVAILABLE = "The canonical database is currently unavailable."


def get_state_scores_connection() -> Iterator[sqlite3.Connection]:
    """Yield a request-scoped read-only connection.

    A failure to *open* the canonical database is an infrastructure failure and
    surfaces as HTTP 503 (never as 404).
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
    "/states/{state_fips}/dimension-scores",
    response_model=StateDimensionScoresResponse,
    summary="Per-county access-dimension scores for one state",
    responses={
        404: {"model": StateScoresErrorResponse, "description": "State FIPS not found"},
        422: {"model": StateScoresErrorResponse, "description": "Malformed state FIPS"},
        503: {"model": StateScoresErrorResponse, "description": "Canonical data unavailable"},
    },
)
def get_state_dimension_scores(
    state_fips: str = Path(
        ...,
        min_length=2,
        max_length=2,
        pattern=r"^\d{2}$",
        description="Exactly two numeric characters.",
    ),
    connection: sqlite3.Connection = Depends(get_state_scores_connection),
) -> StateDimensionScoresResponse:
    """Return every county in ``state_fips`` with its four persisted access
    dimension scores for the v0.1 period.

    Every score and status is the value persisted by the CE-A00..A06 analytical
    pipeline; nothing is recomputed in the request.
    """

    try:
        return load_state_dimension_scores(connection, state_fips)
    except StateNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=f"State FIPS {state_fips} has no counties in the canonical county universe.",
        ) from exc
    except sqlite3.Error as exc:
        raise HTTPException(status_code=503, detail=_DB_UNAVAILABLE) from exc
