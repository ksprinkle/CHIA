"""CE-B01 read-only access to the canonical CHIA county universe.

This service returns the canonical county directory used by the County API. It
performs no analytical calculation, derives no scores, and never mutates the
database. It follows the same read-only pattern as
``app/services/observation_processing.py``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3
from typing import Union


DatabaseSource = Union[sqlite3.Connection, str, Path]


@dataclass(frozen=True)
class CountyRecord:
    """One canonical U.S. county / county-equivalent, exactly as stored.

    ``county_fips`` is preserved as a five-character string. ``county_name`` and
    ``state_name`` are returned verbatim from the canonical database (they are
    intentionally not enriched from any external dataset in CE-B01).
    """

    county_fips: str
    state_fips: str
    state_abbr: str
    county_name: str
    state_name: str


class CountyDirectoryError(ValueError):
    """Raised when the canonical county universe is structurally invalid."""


def load_county_directory(database: DatabaseSource) -> list[CountyRecord]:
    """Return the complete canonical county universe, ``county_fips`` ascending.

    A path/str is opened through SQLite's read-only URI mode. A supplied
    connection is only queried; this function performs no data-definition or
    data-manipulation statement and never commits.
    """

    connection, close_connection = _connection_for_read(database)
    try:
        rows = connection.execute(
            """
            SELECT county_fips, state_fips, state_abbr, county_name, state_name
            FROM county
            ORDER BY county_fips ASC
            """
        ).fetchall()
    finally:
        if close_connection:
            connection.close()

    _validate_rows(rows)

    return [
        CountyRecord(
            county_fips=row[0],
            state_fips=row[1],
            state_abbr=row[2],
            county_name=row[3],
            state_name=row[4],
        )
        for row in rows
    ]


def _connection_for_read(database: DatabaseSource) -> tuple[sqlite3.Connection, bool]:
    if isinstance(database, sqlite3.Connection):
        return database, False

    database_uri = Path(database).resolve().as_uri() + "?mode=ro"
    return sqlite3.connect(database_uri, uri=True), True


def _validate_rows(rows: list[tuple]) -> None:
    if not rows:
        raise CountyDirectoryError("Canonical county universe is empty.")

    fips_values = [row[0] for row in rows]
    if len(set(fips_values)) != len(fips_values):
        raise CountyDirectoryError("Duplicate county_fips in the canonical county table.")

    if fips_values != sorted(fips_values):
        raise CountyDirectoryError("Canonical county rows are not ordered by county_fips.")

    for fips in fips_values:
        if not isinstance(fips, str) or len(fips) != 5 or not fips.isdigit():
            raise CountyDirectoryError(
                f"county_fips {fips!r} is not a five-character numeric string."
            )
