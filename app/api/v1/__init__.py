"""Version 1 of the CHIA County Explorer API (mounted at /api/v1)."""

from __future__ import annotations

from fastapi import APIRouter

from app.config import API_V1_PREFIX
from app.api.v1.counties import router as counties_router


api_v1_router = APIRouter(prefix=API_V1_PREFIX)
api_v1_router.include_router(counties_router)
