"""CE-A02 atomic persistence of approved v0.1 normalized measures."""

from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
import sqlite3
from typing import Optional

from app.services.normalization import (
    METHODOLOGY_VERSION,
    NORMALIZATION_METHOD,
    zero_preserving_percentile,
)
from app.services.observation_processing import load_canonical_observation_universe


TARGET_VARIABLES = (
    "PC_HPSA_GEOGRAPHIC_COVERAGE",
    "DENTAL_HPSA_GEOGRAPHIC_COVERAGE",
    "MH_HPSA_GEOGRAPHIC_COVERAGE",
)
ABSOLUTE_TOLERANCE = 1e-12


@dataclass(frozen=True)
class NormalizationRebuildSummary:
    """Committed target-row counts for one CE-A02 rebuild."""

    counts_by_variable: dict[str, int]


def rebuild_normalized_measures(
    database_path: str | Path,
    period: str = METHODOLOGY_VERSION,
) -> NormalizationRebuildSummary:
    """Atomically replace approved target-variable normalized measures.

    Only the three CE-A02 target variables are replaced. Raw observations,
    MUA/P, schema, and all non-target normalized measures remain untouched.
    """

    connection = sqlite3.connect(database_path)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("BEGIN IMMEDIATE")

        _require_methodology(connection)
        records_by_variable = {
            variable_id: _prepare_variable_records(connection, variable_id, period)
            for variable_id in TARGET_VARIABLES
        }
        _replace_target_records(connection, records_by_variable, period)
        _validate_persisted_records(connection, records_by_variable, period)

        connection.commit()
        return NormalizationRebuildSummary(
            counts_by_variable={
                variable_id: len(records)
                for variable_id, records in records_by_variable.items()
            }
        )
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _require_methodology(connection: sqlite3.Connection) -> None:
    row = connection.execute(
        "SELECT 1 FROM methodology WHERE methodology_version = ?",
        (METHODOLOGY_VERSION,),
    ).fetchone()
    if row is None:
        raise ValueError(f"Methodology {METHODOLOGY_VERSION!r} does not exist.")


def _prepare_variable_records(
    connection: sqlite3.Connection,
    variable_id: str,
    period: str,
) -> list[tuple[int, str, Optional[float], str]]:
    universe = load_canonical_observation_universe(connection, variable_id, period)
    observation_ids = _observation_ids_by_county_period(
        connection, variable_id, period
    )
    if len(observation_ids) != len(universe):
        raise ValueError(
            f"Canonical observation mapping is incomplete for {variable_id!r}."
        )

    scores = zero_preserving_percentile(record.raw_value for record in universe)
    records = []
    for observation, score in zip(universe, scores):
        observation_id = observation_ids.get(observation.county_period_id)
        if observation_id is None:
            raise ValueError(
                f"No observation ID mapped for county period "
                f"{observation.county_period_id}."
            )
        _validate_score(observation.raw_value, score)
        records.append(
            (
                observation_id,
                METHODOLOGY_VERSION,
                score,
                NORMALIZATION_METHOD,
            )
        )

    _validate_scale_invariants(universe, scores)
    return records


def _observation_ids_by_county_period(
    connection: sqlite3.Connection,
    variable_id: str,
    period: str,
) -> dict[int, int]:
    rows = connection.execute(
        """
        SELECT o.county_period_id, o.observation_id
        FROM observation AS o
        JOIN county_period AS cp
          ON cp.county_period_id = o.county_period_id
        WHERE o.variable_id = ?
          AND cp.period = ?
        """,
        (variable_id, period),
    ).fetchall()
    mapping = {county_period_id: observation_id for county_period_id, observation_id in rows}
    if len(mapping) != len(rows):
        raise ValueError(f"Duplicate observation mapping for {variable_id!r}.")
    return mapping


def _validate_score(raw_value: Optional[float], score: Optional[float]) -> None:
    if raw_value is None:
        if score is not None:
            raise ValueError("Missing observations must not receive a normalized score.")
        return
    if raw_value == 0:
        if score != 0.0:
            raise ValueError("Valid zero observations must remain exactly zero.")
        return
    if score is None or not 0.0 <= score <= 100.0:
        raise ValueError("Positive observations require a normalized score in 0--100.")


def _validate_scale_invariants(universe, scores) -> None:
    """Confirm CE-A00 output honours the approved 0--100 scale.

    Per the approved CE-A02 acceptance wording (option b): the normalized
    scale is 0--100; an *untied* maximum positive observation receives
    exactly 100; tied maxima keep whatever the approved average-rank
    CE-A00 formula produces and are never special-cased upward to 100.
    Every persisted value is additionally reconciled against CE-A00 within
    ABSOLUTE_TOLERANCE in :func:`_validate_persisted_records`.
    """

    positives = [
        (observation.raw_value, score)
        for observation, score in zip(universe, scores)
        if observation.raw_value is not None and observation.raw_value > 0
    ]
    if not positives:
        return

    for _, score in positives:
        if score is None or not 0.0 <= score <= 100.0:
            raise ValueError("Positive normalized scores must fall within 0--100.")

    max_raw_value = max(raw_value for raw_value, _ in positives)
    scores_at_max = [
        score for raw_value, score in positives if raw_value == max_raw_value
    ]
    if len(scores_at_max) == 1 and not math.isclose(
        scores_at_max[0], 100.0, rel_tol=0.0, abs_tol=ABSOLUTE_TOLERANCE
    ):
        raise ValueError("An untied maximum positive observation must receive 100.")


def _replace_target_records(
    connection: sqlite3.Connection,
    records_by_variable: dict[str, list[tuple[int, str, Optional[float], str]]],
    period: str,
) -> None:
    placeholders = ", ".join("?" for _ in TARGET_VARIABLES)
    deleted = connection.execute(
        f"""
        DELETE FROM normalized_measure
        WHERE methodology_version = ?
          AND observation_id IN (
              SELECT o.observation_id
              FROM observation AS o
              JOIN county_period AS cp
                ON cp.county_period_id = o.county_period_id
              WHERE cp.period = ?
                AND o.variable_id IN ({placeholders})
          )
        """,
        (METHODOLOGY_VERSION, period, *TARGET_VARIABLES),
    ).rowcount
    expected_deleted = sum(len(records) for records in records_by_variable.values())
    if deleted != expected_deleted:
        raise ValueError(
            f"Expected to replace {expected_deleted} legacy records; found {deleted}."
        )

    records = [
        record
        for variable_records in records_by_variable.values()
        for record in variable_records
    ]
    connection.executemany(
        """
        INSERT INTO normalized_measure (
            observation_id,
            methodology_version,
            normalized_value,
            normalization_method
        )
        VALUES (?, ?, ?, ?)
        """,
        records,
    )


def _validate_persisted_records(
    connection: sqlite3.Connection,
    records_by_variable: dict[str, list[tuple[int, str, Optional[float], str]]],
    period: str,
) -> None:
    expected_records = {
        observation_id: score
        for records in records_by_variable.values()
        for observation_id, _, score, _ in records
    }
    placeholders = ", ".join("?" for _ in TARGET_VARIABLES)
    rows = connection.execute(
        f"""
        SELECT nm.observation_id, nm.normalized_value, nm.normalization_method
        FROM normalized_measure AS nm
        JOIN observation AS o
          ON o.observation_id = nm.observation_id
        JOIN county_period AS cp
          ON cp.county_period_id = o.county_period_id
        WHERE nm.methodology_version = ?
          AND cp.period = ?
          AND o.variable_id IN ({placeholders})
        """,
        (METHODOLOGY_VERSION, period, *TARGET_VARIABLES),
    ).fetchall()
    if len(rows) != len(expected_records):
        raise ValueError("Persisted normalized-measure count does not match expectation.")

    for observation_id, actual_score, actual_method in rows:
        expected_score = expected_records.get(observation_id)
        if observation_id not in expected_records or actual_method != NORMALIZATION_METHOD:
            raise ValueError("Persisted normalized-measure metadata does not match.")
        if expected_score is None:
            if actual_score is not None:
                raise ValueError("A missing observation received a persisted score.")
        elif actual_score is None or not math.isclose(
            actual_score,
            expected_score,
            rel_tol=0.0,
            abs_tol=ABSOLUTE_TOLERANCE,
        ):
            raise ValueError("Persisted normalized score differs from CE-A00 output.")

    foreign_key_errors = connection.execute("PRAGMA foreign_key_check").fetchall()
    if foreign_key_errors:
        raise ValueError("Foreign-key validation failed during normalization rebuild.")
