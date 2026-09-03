"""CE-B02 County Explorer API router.

``GET /api/v1/counties/{county_fips}/explorer`` -- read-only. Assembles the
County Explorer read model from persisted canonical + analytical data. No
analytical calculation, no composite averaging, no database writes.

Error semantics (locked):
* malformed ``county_fips`` (not exactly five digits) -> 422 (before any query)
* well-formed but unknown county                       -> 404
* county exists, analytical data incomplete            -> 200 (persisted status)
* database unavailable / structurally unusable         -> 503
"""

from __future__ import annotations

from collections.abc import Iterator
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Path

from app.db import open_readonly_connection
from app.schemas.explorer import ExplorerErrorResponse, ExplorerResponse
from app.services.county_explorer import (
    CountyNotFoundError,
    ExplorerDataError,
    load_county_explorer,
)


router = APIRouter(tags=["county-explorer"])

_DB_UNAVAILABLE = "The canonical database is currently unavailable."


def get_explorer_connection() -> Iterator[sqlite3.Connection]:
    """Yield a request-scoped read-only connection.

    A failure to *open* the canonical database is an infrastructure failure and
    surfaces as HTTP 503 (never as 404 or an incomplete-data 200).
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
    "/counties/{county_fips}/explorer",
    response_model=ExplorerResponse,
    summary="Assembled County Explorer read model",
    responses={
        404: {"model": ExplorerErrorResponse, "description": "County FIPS not found"},
        422: {"model": ExplorerErrorResponse, "description": "Malformed county FIPS"},
        503: {"model": ExplorerErrorResponse, "description": "Canonical data unavailable"},
    },
)
def get_county_explorer(
    county_fips: str = Path(
        ...,
        min_length=5,
        max_length=5,
        pattern=r"^\d{5}$",
        description="Exactly five numeric characters.",
    ),
    connection: sqlite3.Connection = Depends(get_explorer_connection),
) -> ExplorerResponse:
    """Return the complete County Explorer read model for the v0.1 period.

    Every score, status, and composite figure is the value persisted by the
    CE-A00..A06 analytical pipeline; nothing is recomputed in the request.
    """

    try:
        return load_county_explorer(connection, county_fips)
    except CountyNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=f"County FIPS {county_fips} is not in the canonical county universe.",
        ) from exc
    except ExplorerDataError as exc:
        raise HTTPException(
            status_code=503,
            detail="The canonical analytical data for this county could not be assembled.",
        ) from exc
    except sqlite3.Error as exc:
        raise HTTPException(status_code=503, detail=_DB_UNAVAILABLE) from exc
