"""CE-B02 read-only assembly of the County Explorer read model.

This service assembles one :class:`~app.schemas.explorer.ExplorerResponse` for a
county and the v0.1 period entirely from already-persisted canonical and
analytical tables:

    county, county_period, observation, normalized_measure,
    dimension_definition, dimension_score, composite_score, source, methodology

It performs no writes, no analytical recalculation, and no composite averaging.
Dimension scores and the composite are returned exactly as persisted by
CE-A00..A06. County / state display names are returned verbatim from the
canonical ``county`` table (no external enrichment).
"""

from __future__ import annotations

from pathlib import Path
import sqlite3
from typing import Union

from app.schemas.explorer import (
    AccessProfile,
    CountyBlock,
    DimensionProfile,
    ExperimentalComposite,
    ExplorerResponse,
    MethodologyBlock,
    PeriodBlock,
    PrimaryMeasure,
    Provenance,
    SourceRef,
    SupportingEvidenceItem,
)


DatabaseSource = Union[sqlite3.Connection, str, Path]

METHODOLOGY_VERSION = "v0.1"

# dimension_id -> access_profile response key, in canonical order.
DIMENSION_KEYS: tuple[tuple[str, str], ...] = (
    ("PRIMARY_CARE", "primary_care"),
    ("DENTAL", "dental"),
    ("MENTAL_HEALTH", "mental_health"),
    ("MUA_P", "mua_p"),
)


class CountyNotFoundError(LookupError):
    """The requested (well-formed) county FIPS is not in the canonical universe."""


class ExplorerDataError(RuntimeError):
    """The canonical/analytical data required to assemble the view is missing
    or structurally inconsistent (distinct from an incomplete-but-valid county).
    """


def load_county_explorer(
    database: DatabaseSource,
    county_fips: str,
    period: str = METHODOLOGY_VERSION,
) -> ExplorerResponse:
    """Assemble and return the Explorer read model for ``county_fips``.

    Raises :class:`CountyNotFoundError` if the county does not exist, and
    :class:`ExplorerDataError` if the county exists but its canonical/analytical
    context cannot be assembled. Raw ``sqlite3.Error`` propagates unchanged.
    """

    connection, close_connection = _connection_for_read(database)
    try:
        return _assemble(connection, county_fips, period)
    finally:
        if close_connection:
            connection.close()


# ---------------------------------------------------------------------------
def _connection_for_read(database: DatabaseSource) -> tuple[sqlite3.Connection, bool]:
    if isinstance(database, sqlite3.Connection):
        return database, False
    database_uri = Path(database).resolve().as_uri() + "?mode=ro"
    return sqlite3.connect(database_uri, uri=True), True


def _assemble(
    connection: sqlite3.Connection, county_fips: str, period: str
) -> ExplorerResponse:
    county_row = connection.execute(
        """
        SELECT county_fips, county_name, state_abbr, state_name
        FROM county
        WHERE county_fips = ?
        """,
        (county_fips,),
    ).fetchone()
    if county_row is None:
        raise CountyNotFoundError(county_fips)

    county = CountyBlock(
        county_fips=county_row[0],
        county_name=county_row[1],
        state_abbr=county_row[2],
        state_name=county_row[3],
    )

    period_row = connection.execute(
        """
        SELECT county_period_id, period, completeness_status
        FROM county_period
        WHERE county_fips = ? AND period = ?
        """,
        (county_fips, period),
    ).fetchone()
    if period_row is None:
        raise ExplorerDataError(
            f"No {period!r} county_period record for county {county_fips!r}."
        )
    county_period_id, period_value, completeness_status = period_row

    definitions = _load_dimension_definitions(connection, period)
    dimension_scores = _load_dimension_scores(connection, county_period_id, period)

    source_ids: set[int] = set()
    profiles: dict[str, DimensionProfile] = {}
    for dimension_id, response_key in DIMENSION_KEYS:
        definition = definitions.get(dimension_id)
        if definition is None:
            raise ExplorerDataError(
                f"dimension_definition {dimension_id!r} is missing for {period!r}."
            )
        profile = _build_dimension_profile(
            connection,
            county_period_id,
            period,
            dimension_id,
            definition,
            dimension_scores.get(dimension_id),
            source_ids,
        )
        profiles[response_key] = profile

    access_profile = AccessProfile(**profiles)
    composite = _load_composite(connection, county_period_id, period)
    provenance = _load_provenance(connection, source_ids)
    methodology = _load_methodology(connection, period)

    return ExplorerResponse(
        county=county,
        period=PeriodBlock(value=period_value, completeness_status=completeness_status),
        access_profile=access_profile,
        experimental_composite=composite,
        provenance=provenance,
        methodology=methodology,
    )


def _load_dimension_definitions(
    connection: sqlite3.Connection, period: str
) -> dict[str, dict]:
    rows = connection.execute(
        """
        SELECT dimension_id, dimension_name, description, primary_variable_id,
               supporting_variables, calculation_method
        FROM dimension_definition
        WHERE methodology_version = ?
        """,
        (period,),
    ).fetchall()
    return {
        row[0]: {
            "dimension_name": row[1],
            "description": row[2],
            "primary_variable_id": row[3],
            "supporting_variables": row[4],
            "calculation_method": row[5],
        }
        for row in rows
    }


def _load_dimension_scores(
    connection: sqlite3.Connection, county_period_id: int, period: str
) -> dict[str, tuple[float | None, str | None]]:
    rows = connection.execute(
        """
        SELECT dimension_id, score, status
        FROM dimension_score
        WHERE county_period_id = ? AND methodology_version = ?
        """,
        (county_period_id, period),
    ).fetchall()
    return {row[0]: (row[1], row[2]) for row in rows}


def _build_dimension_profile(
    connection: sqlite3.Connection,
    county_period_id: int,
    period: str,
    dimension_id: str,
    definition: dict,
    score_row: tuple[float | None, str | None] | None,
    source_ids: set[int],
) -> DimensionProfile:
    score = score_row[0] if score_row is not None else None
    score_status = score_row[1] if score_row is not None else None

    primary_variable_id = definition["primary_variable_id"]
    variable = connection.execute(
        """
        SELECT display_name, unit, direction, source_id
        FROM variable_definition
        WHERE variable_id = ?
        """,
        (primary_variable_id,),
    ).fetchone()
    if variable is None:
        raise ExplorerDataError(
            f"variable_definition {primary_variable_id!r} is missing."
        )
    primary_display_name, primary_unit, primary_direction, primary_source_id = variable
    if primary_source_id is not None:
        source_ids.add(primary_source_id)

    observation = connection.execute(
        """
        SELECT observation_id, raw_value, quality_flag
        FROM observation
        WHERE county_period_id = ? AND variable_id = ?
        """,
        (county_period_id, primary_variable_id),
    ).fetchone()

    normalized_value: float | None = None
    normalization_method: str | None = None
    if observation is not None:
        normalized = connection.execute(
            """
            SELECT normalized_value, normalization_method
            FROM normalized_measure
            WHERE observation_id = ? AND methodology_version = ?
            """,
            (observation[0], period),
        ).fetchone()
        if normalized is not None:
            normalized_value, normalization_method = normalized

    primary_measure = PrimaryMeasure(
        variable_id=primary_variable_id,
        display_name=primary_display_name,
        unit=primary_unit,
        raw_value=observation[1] if observation is not None else None,
        normalized_value=normalized_value,
        normalization_method=normalization_method,
        quality_flag=observation[2] if observation is not None else None,
    )

    supporting_evidence = _load_supporting_evidence(
        connection, county_period_id, definition["supporting_variables"], source_ids
    )

    return DimensionProfile(
        dimension_id=dimension_id,
        dimension_name=definition["dimension_name"],
        description=definition["description"],
        primary_variable_id=primary_variable_id,
        calculation_method=definition["calculation_method"],
        direction=primary_direction,
        normalized=normalization_method is not None,
        available=score is not None,
        score=score,
        score_status=score_status,
        source_id=primary_source_id,
        primary_measure=primary_measure,
        supporting_evidence=supporting_evidence,
    )


def _load_supporting_evidence(
    connection: sqlite3.Connection,
    county_period_id: int,
    supporting_variables: str | None,
    source_ids: set[int],
) -> list[SupportingEvidenceItem]:
    if not supporting_variables:
        return []

    items: list[SupportingEvidenceItem] = []
    for raw_variable_id in supporting_variables.split(","):
        variable_id = raw_variable_id.strip()
        if not variable_id:
            continue
        variable = connection.execute(
            """
            SELECT display_name, unit, direction, source_id
            FROM variable_definition
            WHERE variable_id = ?
            """,
            (variable_id,),
        ).fetchone()
        if variable is None:
            raise ExplorerDataError(
                f"Declared supporting variable {variable_id!r} has no variable_definition."
            )
        display_name, unit, direction, source_id = variable
        if source_id is not None:
            source_ids.add(source_id)

        observation = connection.execute(
            """
            SELECT raw_value, quality_flag
            FROM observation
            WHERE county_period_id = ? AND variable_id = ?
            """,
            (county_period_id, variable_id),
        ).fetchone()

        items.append(
            SupportingEvidenceItem(
                variable_id=variable_id,
                display_name=display_name,
                unit=unit,
                direction=direction,
                raw_value=observation[0] if observation is not None else None,
                quality_flag=observation[1] if observation is not None else None,
            )
        )
    return items


def _load_composite(
    connection: sqlite3.Connection, county_period_id: int, period: str
) -> ExperimentalComposite:
    row = connection.execute(
        """
        SELECT composite_value, status, missing_dimensions
        FROM composite_score
        WHERE county_period_id = ? AND methodology_version = ?
        """,
        (county_period_id, period),
    ).fetchone()
    if row is None:
        raise ExplorerDataError(
            f"No composite_score record for county_period {county_period_id}."
        )
    composite_value, status, missing_dimensions = row
    missing = (
        [part.strip() for part in missing_dimensions.split(",") if part.strip()]
        if missing_dimensions
        else []
    )
    return ExperimentalComposite(
        composite_value=composite_value,
        status=status,
        missing_dimensions=missing,
    )


def _load_provenance(
    connection: sqlite3.Connection, source_ids: set[int]
) -> Provenance:
    if not source_ids:
        return Provenance(sources=[])

    placeholders = ", ".join("?" for _ in source_ids)
    rows = connection.execute(
        f"""
        SELECT source_id, source_name, publisher, dataset_name, reference_period,
               url, accessed_at, artifact_filename, content_sha256
        FROM source
        WHERE source_id IN ({placeholders})
        ORDER BY source_id
        """,
        tuple(sorted(source_ids)),
    ).fetchall()
    found_ids = {row[0] for row in rows}
    missing_ids = source_ids - found_ids
    if missing_ids:
        raise ExplorerDataError(
            f"source record(s) missing for source_id(s) {sorted(missing_ids)}."
        )
    return Provenance(
        sources=[
            SourceRef(
                source_id=row[0],
                source_name=row[1],
                publisher=row[2],
                dataset_name=row[3],
                reference_period=row[4],
                url=row[5],
                accessed_at=row[6],
                artifact_filename=row[7],
                content_sha256=row[8],
            )
            for row in rows
        ]
    )


def _load_methodology(
    connection: sqlite3.Connection, period: str
) -> MethodologyBlock:
    row = connection.execute(
        """
        SELECT methodology_version, name, description, status, created_at
        FROM methodology
        WHERE methodology_version = ?
        """,
        (period,),
    ).fetchone()
    if row is None:
        raise ExplorerDataError(f"No methodology record for {period!r}.")

    normalization_row = connection.execute(
        """
        SELECT normalization_method
        FROM normalized_measure
        WHERE methodology_version = ?
        LIMIT 1
        """,
        (period,),
    ).fetchone()

    return MethodologyBlock(
        methodology_version=row[0],
        name=row[1],
        description=row[2],
        status=row[3],
        created_at=row[4],
        normalization_method=normalization_row[0] if normalization_row else None,
    )
