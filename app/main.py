"""CHIA County Explorer API application entry point.

Run with the conventional::

    uvicorn app.main:app

CE-B01 exposes only the County API (``GET /api/v1/counties``). The County
Explorer endpoint (``/api/v1/counties/{county_fips}/explorer``) is CE-B02 and is
intentionally not implemented here.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import api_v1_router
from app.config import ALLOWED_ORIGINS


app = FastAPI(
    title="CHIA County Explorer API",
    version="0.1.0",
    description=(
        "Read-only County API over the validated canonical CHIA v0.1 data "
        "model (CE-B01). No analytical calculation is performed on request; "
        "the canonical database is never modified."
    ),
)

# CE-DEP01: opt-in, narrowly scoped CORS. With no CHIA_ALLOWED_ORIGINS set
# (the default, and every test run) no middleware is added and responses are
# byte-identical to before. When configured, only the listed origins may read
# the API from a browser, only GET, no credentials.
if ALLOWED_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_methods=["GET"],
        allow_headers=["Accept"],
        allow_credentials=False,
    )

app.include_router(api_v1_router)


@app.get("/health", tags=["operations"], summary="Liveness probe")
def health() -> dict[str, str]:
    """Minimal liveness check for the deployment platform.

    Does not touch the database or perform any analytical work; a 200 means
    the process is up and importable.
    """

    return {"status": "ok"}
