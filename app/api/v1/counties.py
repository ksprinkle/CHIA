"""CE-B01 County API router: the canonical county universe.

``GET /api/v1/counties`` -- read-only. No analytical calculation, no database
writes, deterministic ``county_fips`` ascending order.
"""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends

from app.db import get_readonly_connection
from app.schemas.county import County, CountyListResponse
from app.services.county_directory import load_county_directory


router = APIRouter(tags=["counties"])


@router.get(
    "/counties",
    response_model=CountyListResponse,
    summary="Canonical county universe",
)
def list_counties(
    connection: sqlite3.Connection = Depends(get_readonly_connection),
) -> CountyListResponse:
    """Return the complete canonical CHIA county universe.

    FIPS is always a five-character string. This endpoint performs no analytical
    calculation and never writes to the database.
    """

    records = load_county_directory(connection)
    counties = [
        County(
            county_fips=record.county_fips,
            state_fips=record.state_fips,
            state_abbr=record.state_abbr,
            county_name=record.county_name,
            state_name=record.state_name,
        )
        for record in records
    ]
    return CountyListResponse(count=len(counties), counties=counties)
