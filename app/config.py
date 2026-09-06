"""Application configuration for the CHIA County Explorer API.

Paths resolve relative to the repository in the same style already used by the
project's ``Data/Model`` scripts and ``app/services`` modules.
"""

from __future__ import annotations

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Canonical, validated CHIA v0.1 database. Opened READ-ONLY by the API.
# The deployed application ships this file inside its build; an operator may
# override the location with CHIA_DATABASE_PATH without touching code.
DATABASE_PATH = Path(
    os.environ.get(
        "CHIA_DATABASE_PATH",
        PROJECT_ROOT / "Data" / "Model" / "chia_v01.sqlite",
    )
)

# Versioned API mount point (governing specification, section 11).
API_V1_PREFIX = "/api/v1"


def parse_allowed_origins(raw: str | None) -> list[str]:
    """Split a comma-separated CORS allowlist into exact origin strings.

    Whitespace is trimmed and empty entries dropped. ``None`` or an empty
    string yields an empty list, i.e. cross-origin browser access stays
    disabled (no CORS headers are emitted at all -- see ``app.main``).
    """

    if not raw:
        return []
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


# Cross-origin browser access is OFF by default. A split-origin deployment
# (e.g. the GitHub Pages frontend) sets CHIA_ALLOWED_ORIGINS to a
# comma-separated list of exact ``scheme://host`` origins, e.g.
# ``https://ksprinkle.github.io``.
ALLOWED_ORIGINS = parse_allowed_origins(os.environ.get("CHIA_ALLOWED_ORIGINS"))
