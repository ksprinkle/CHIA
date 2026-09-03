"""CHIA County Explorer API application entry point.

Run with the conventional::

    uvicorn app.main:app

CE-B01 exposes only the County API (``GET /api/v1/counties``). The County
Explorer endpoint (``/api/v1/counties/{county_fips}/explorer``) is CE-B02 and is
intentionally not implemented here.
"""

from __future__ import annotations

from fastapi import FastAPI

from app.api.v1 import api_v1_router


app = FastAPI(
    title="CHIA County Explorer API",
    version="0.1.0",
    description=(
        "Read-only County API over the validated canonical CHIA v0.1 data "
        "model (CE-B01). No analytical calculation is performed on request; "
        "the canonical database is never modified."
    ),
)

app.include_router(api_v1_router)
