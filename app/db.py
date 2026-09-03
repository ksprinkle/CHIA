"""Read-only database access for the CHIA County Explorer API.

The API never writes to the canonical data model. This module mirrors the
read-only SQLite URI pattern already used by
``app/services/observation_processing.py`` -- no ORM, no session, no pool.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
import sqlite3

from app.config import DATABASE_PATH


def open_readonly_connection(
    database_path: str | Path = DATABASE_PATH,
) -> sqlite3.Connection:
    """Open the canonical database in SQLite read-only URI mode (``mode=ro``)."""

    database_uri = Path(database_path).resolve().as_uri() + "?mode=ro"
    return sqlite3.connect(database_uri, uri=True)


def get_readonly_connection() -> Iterator[sqlite3.Connection]:
    """FastAPI dependency: yield a request-scoped read-only connection."""

    connection = open_readonly_connection()
    try:
        yield connection
    finally:
        connection.close()
