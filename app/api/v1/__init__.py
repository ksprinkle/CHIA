"""Version 1 of the CHIA County Explorer API (mounted at /api/v1)."""

from __future__ import annotations

from fastapi import APIRouter

from app.config import API_V1_PREFIX
from app.api.v1.counties import router as counties_router
from app.api.v1.explorer import router as explorer_router
from app.api.v1.national_scores import router as national_scores_router
from app.api.v1.state_scores import router as state_scores_router


api_v1_router = APIRouter(prefix=API_V1_PREFIX)
api_v1_router.include_router(counties_router)
api_v1_router.include_router(explorer_router)
# CE-E14a: the literal ``/states/dimension-scores`` is registered before
# CE-E09's parametrized ``/states/{state_fips}/dimension-scores`` (they cannot
# collide -- two path segments vs three -- but this keeps the ordering obvious).
api_v1_router.include_router(national_scores_router)
api_v1_router.include_router(state_scores_router)
