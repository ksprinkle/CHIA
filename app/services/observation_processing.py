"""Read-only access to the canonical CHIA observation universe.

This CE-A01 foundation deliberately does not calculate or persist analytical
results. CE-A02 can pass the complete returned universe to its approved
normalization calculation.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3
from typing import Optional, Union


DatabaseSource = Union[sqlite3.Connection, str, Path]


@dataclass(frozen=True)
class CanonicalObservation:
    """One requested variable for one canonical county-period.

    ``raw_value`` and ``quality_flag`` are preserved exactly as stored. An
    absent observation is represented by ``raw_value=None`` and
    ``quality_flag=None`` rather than being omitted from the county universe.
    """

    county_period_id: int
    county_fips: str
    variable_id: str
    raw_value: Optional[float]
    quality_flag: Optional[str]


class ObservationStructureError(ValueError):
    """Raised when canonical county-period or observation mappings are invalid."""


def load_canonical_observation_universe(
    database: DatabaseSource,
    variable_id: str,
    period: str,
) -> list[CanonicalObservation]:
    """Return a complete, FIPS-ordered canonical observation universe.

    A path is opened through SQLite's read-only URI mode. A supplied connection
    is only queried; this function performs no data-definition or data-
    manipulation operation and never commits.
    """

    connection, close_connection = _connection_for_read(database)
    try:
        county_periods = connection.execute(
            """
            SELECT cp.county_period_id, c.county_fips
            FROM county_period AS cp
            JOIN county AS c
              ON c.county_fips = cp.county_fips
            WHERE cp.period = ?
            ORDER BY c.county_fips
            """,
            (period,),
        ).fetchall()

        _validate_county_periods(county_periods, period)

        rows = connection.execute(
            """
            SELECT
                cp.county_period_id,
                c.county_fips,
                o.raw_value,
                o.quality_flag
            FROM county_period AS cp
            JOIN county AS c
              ON c.county_fips = cp.county_fips
            LEFT JOIN observation AS o
              ON o.county_period_id = cp.county_period_id
             AND o.variable_id = ?
            WHERE cp.period = ?
            ORDER BY c.county_fips
            """,
            (variable_id, period),
        ).fetchall()

        _validate_observation_mapping(rows, variable_id)
        return [
            CanonicalObservation(
                county_period_id=row[0],
                county_fips=row[1],
                variable_id=variable_id,
                raw_value=row[2],
                quality_flag=row[3],
            )
            for row in rows
        ]
    finally:
        if close_connection:
            connection.close()


def _connection_for_read(database: DatabaseSource) -> tuple[sqlite3.Connection, bool]:
    if isinstance(database, sqlite3.Connection):
        return database, False

    database_uri = Path(database).resolve().as_uri() + "?mode=ro"
    return sqlite3.connect(database_uri, uri=True), True


def _validate_county_periods(rows: list[tuple[int, str]], period: str) -> None:
    if not rows:
        raise ObservationStructureError(f"No county-period records found for {period!r}.")

    county_period_ids = [row[0] for row in rows]
    county_fips = [row[1] for row in rows]
    if len(set(county_period_ids)) != len(county_period_ids):
        raise ObservationStructureError("Duplicate canonical county-period IDs found.")
    if len(set(county_fips)) != len(county_fips):
        raise ObservationStructureError("Multiple county-periods found for a county FIPS.")
    if any(len(fips) != 5 or not fips.isdigit() for fips in county_fips):
        raise ObservationStructureError("Canonical county FIPS must be five numeric characters.")


def _validate_observation_mapping(
    rows: list[tuple[int, str, Optional[float], Optional[str]]],
    variable_id: str,
) -> None:
    county_period_ids = [row[0] for row in rows]
    if len(set(county_period_ids)) != len(county_period_ids):
        raise ObservationStructureError(
            f"Duplicate observations found for variable {variable_id!r}."
        )
