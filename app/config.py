"""Application configuration for the CHIA County Explorer API.

Paths resolve relative to the repository in the same style already used by the
project's ``Data/Model`` scripts and ``app/services`` modules.
"""

from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Canonical, validated CHIA v0.1 database. Opened READ-ONLY by the API.
DATABASE_PATH = PROJECT_ROOT / "Data" / "Model" / "chia_v01.sqlite"

# Versioned API mount point (governing specification, section 11).
API_V1_PREFIX = "/api/v1"
