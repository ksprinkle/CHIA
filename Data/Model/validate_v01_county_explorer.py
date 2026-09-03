"""CE-A06 -- full analytical validation of the CHIA v0.1 County Explorer pipeline.

This validator is strictly READ-ONLY. It opens the database in SQLite
``mode=ro`` and never writes, alters schema, or touches seeds / raw data.

It independently reconciles every layer of the analytical pipeline across the
complete 3,143 county-period universe:

    observation  ->  normalized_measure   (recomputed via the approved CE-A00
                                            zero-preserving percentile formula)
    normalized_measure  ->  dimension_score   (identity copy; MUA/P is the raw
                                               coverage value, never normalized)
    four dimension scores  ->  composite_score   (equal-weight mean, or NULL +
                                                  named missing dimensions)

plus metadata, row counts, uniqueness, lineage, foreign-key and database
integrity. Numeric reconciliation uses an absolute tolerance of 1e-12; exact
identity copies are compared exactly.
"""

from __future__ import annotations

from pathlib import Path
import sqlite3
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATABASE_PATH = PROJECT_ROOT / "Data" / "Model" / "chia_v01.sqlite"

# The approved CE-A00 percentile formula is imported (never re-implemented) so
# the observation -> normalized_measure reconciliation has a single source of
# methodology truth.
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from app.services.normalization import zero_preserving_percentile  # noqa: E402


# --- constants (must match the A00-A05 implementations) ----------------------
METHODOLOGY_VERSION = "v0.1"
NORMALIZATION_METHOD = "county_percentile_rank_average"
DIMENSION_STATUS = "calculated"
COMPOSITE_STATUS_COMPLETE = "experimental_provisional"
COMPOSITE_STATUS_INCOMPLETE = "experimental_provisional_incomplete"
TOLERANCE = 1e-12

EXPECTED_COUNTY_PERIODS = 3143
EXPECTED_VARIABLES = 19
EXPECTED_OBSERVATIONS = 59717

# dimension_id -> canonical primary variable_id, for the three normalized
# dimensions. MUA/P is handled separately as a raw (unnormalized) measure.
NORMALIZED_DIMENSIONS = {
    "PRIMARY_CARE": "PC_HPSA_GEOGRAPHIC_COVERAGE",
    "DENTAL": "DENTAL_HPSA_GEOGRAPHIC_COVERAGE",
    "MENTAL_HEALTH": "MH_HPSA_GEOGRAPHIC_COVERAGE",
}
RAW_DIMENSION = "MUA_P"
RAW_DIMENSION_VARIABLE = "MUAP_GEOGRAPHIC_COVERAGE"
COMPOSITE_DIMENSIONS = ("PRIMARY_CARE", "DENTAL", "MENTAL_HEALTH", "MUA_P")

NORMALIZED_VARIABLES = tuple(NORMALIZED_DIMENSIONS.values())


class CountyExplorerValidationError(AssertionError):
    """Raised on the first analytical-pipeline inconsistency found."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CountyExplorerValidationError(message)


def _close(actual, expected) -> bool:
    if actual is None or expected is None:
        return actual is None and expected is None
    return abs(actual - expected) <= TOLERANCE


def _connect_readonly(database_path) -> sqlite3.Connection:
    uri = Path(database_path).resolve().as_uri() + "?mode=ro"
    return sqlite3.connect(uri, uri=True)


# ---------------------------------------------------------------------------
# Layer checks
# ---------------------------------------------------------------------------
def _check_structure(connection, log) -> list[int]:
    methodology = connection.execute(
        "SELECT methodology_version FROM methodology"
    ).fetchall()
    _require(
        methodology == [(METHODOLOGY_VERSION,)],
        f"methodology table must contain exactly {METHODOLOGY_VERSION!r}, found {methodology}.",
    )

    county_count = connection.execute("SELECT COUNT(*) FROM county").fetchone()[0]
    _require(
        county_count == EXPECTED_COUNTY_PERIODS,
        f"Expected {EXPECTED_COUNTY_PERIODS} counties, found {county_count}.",
    )

    county_periods = connection.execute(
        """
        SELECT cp.county_period_id, cp.county_fips, cp.period
        FROM county_period AS cp
        ORDER BY cp.county_period_id
        """
    ).fetchall()
    _require(
        len(county_periods) == EXPECTED_COUNTY_PERIODS,
        f"Expected {EXPECTED_COUNTY_PERIODS} county-periods, found {len(county_periods)}.",
    )
    _require(
        all(period == METHODOLOGY_VERSION for _, _, period in county_periods),
        "Every county_period.period must be v0.1.",
    )
    fips_values = [fips for _, fips, _ in county_periods]
    _require(len(set(fips_values)) == len(fips_values), "Duplicate county_fips in county_period.")
    _require(
        all(len(fips) == 5 and fips.isdigit() for fips in fips_values),
        "Every county_fips must be five numeric characters.",
    )
    orphan_cp = connection.execute(
        """
        SELECT COUNT(*)
        FROM county_period AS cp
        LEFT JOIN county AS c ON c.county_fips = cp.county_fips
        WHERE c.county_fips IS NULL
        """
    ).fetchone()[0]
    _require(orphan_cp == 0, f"{orphan_cp} county_period rows have no matching county.")

    variable_count = connection.execute(
        "SELECT COUNT(*) FROM variable_definition"
    ).fetchone()[0]
    _require(
        variable_count == EXPECTED_VARIABLES,
        f"Expected {EXPECTED_VARIABLES} variable_definition rows, found {variable_count}.",
    )
    for variable_id in (*NORMALIZED_VARIABLES, RAW_DIMENSION_VARIABLE):
        row = connection.execute(
            "SELECT direction FROM variable_definition WHERE variable_id = ?",
            (variable_id,),
        ).fetchone()
        _require(row is not None, f"variable_definition missing {variable_id!r}.")
        _require(
            row[0] == "higher_burden",
            f"{variable_id!r} direction is {row[0]!r}, expected 'higher_burden'.",
        )

    for dimension_id, variable_id in {
        **NORMALIZED_DIMENSIONS,
        RAW_DIMENSION: RAW_DIMENSION_VARIABLE,
    }.items():
        row = connection.execute(
            "SELECT primary_variable_id, methodology_version FROM dimension_definition WHERE dimension_id = ?",
            (dimension_id,),
        ).fetchone()
        _require(row is not None, f"dimension_definition missing {dimension_id!r}.")
        _require(
            row[0] == variable_id,
            f"dimension_definition {dimension_id!r} primary_variable_id is {row[0]!r}, expected {variable_id!r}.",
        )
        _require(
            row[1] == METHODOLOGY_VERSION,
            f"dimension_definition {dimension_id!r} methodology_version is {row[1]!r}.",
        )

    log.append(f"structure: {county_count} counties / {len(county_periods)} county-periods / {variable_count} variables")
    return [cp_id for cp_id, _, _ in county_periods]


def _check_observations(connection, universe, log) -> None:
    total = connection.execute("SELECT COUNT(*) FROM observation").fetchone()[0]
    _require(
        total == EXPECTED_OBSERVATIONS,
        f"Expected {EXPECTED_OBSERVATIONS} observations, found {total}.",
    )
    _require(
        total == EXPECTED_VARIABLES * EXPECTED_COUNTY_PERIODS,
        "observation count is not variables x county-periods.",
    )

    duplicate_pairs = connection.execute(
        """
        SELECT county_period_id, variable_id, COUNT(*)
        FROM observation
        GROUP BY county_period_id, variable_id
        HAVING COUNT(*) > 1
        """
    ).fetchall()
    _require(not duplicate_pairs, f"{len(duplicate_pairs)} duplicate (county_period, variable) observations.")

    orphan_cp = connection.execute(
        """
        SELECT COUNT(*)
        FROM observation AS o
        LEFT JOIN county_period AS cp ON cp.county_period_id = o.county_period_id
        WHERE cp.county_period_id IS NULL
        """
    ).fetchone()[0]
    _require(orphan_cp == 0, f"{orphan_cp} observations reference a missing county_period.")
    orphan_var = connection.execute(
        """
        SELECT COUNT(*)
        FROM observation AS o
        LEFT JOIN variable_definition AS v ON v.variable_id = o.variable_id
        WHERE v.variable_id IS NULL
        """
    ).fetchone()[0]
    _require(orphan_var == 0, f"{orphan_var} observations reference an undefined variable.")

    per_variable = dict(
        connection.execute("SELECT variable_id, COUNT(*) FROM observation GROUP BY variable_id")
    )
    for variable_id, count in per_variable.items():
        _require(
            count == EXPECTED_COUNTY_PERIODS,
            f"variable {variable_id!r} has {count} observations, expected {EXPECTED_COUNTY_PERIODS}.",
        )

    universe_set = set(universe)
    for variable_id in (*NORMALIZED_VARIABLES, RAW_DIMENSION_VARIABLE):
        covered = {
            cp_id
            for (cp_id,) in connection.execute(
                "SELECT county_period_id FROM observation WHERE variable_id = ?",
                (variable_id,),
            )
        }
        _require(
            covered == universe_set,
            f"{variable_id!r} observations do not cover the full county-period universe.",
        )

    log.append(f"observations: {total} rows, {len(per_variable)} variables x {EXPECTED_COUNTY_PERIODS}")


def _check_normalization(connection, universe, log) -> None:
    total = connection.execute("SELECT COUNT(*) FROM normalized_measure").fetchone()[0]
    _require(
        total == len(NORMALIZED_VARIABLES) * EXPECTED_COUNTY_PERIODS,
        f"Expected {len(NORMALIZED_VARIABLES) * EXPECTED_COUNTY_PERIODS} normalized_measure rows, found {total}.",
    )

    metadata = connection.execute(
        "SELECT DISTINCT methodology_version, normalization_method FROM normalized_measure"
    ).fetchall()
    _require(
        metadata == [(METHODOLOGY_VERSION, NORMALIZATION_METHOD)],
        f"normalized_measure metadata must be exactly ({METHODOLOGY_VERSION!r}, {NORMALIZATION_METHOD!r}), found {metadata}.",
    )

    measured_variables = {
        variable_id
        for (variable_id,) in connection.execute(
            """
            SELECT DISTINCT o.variable_id
            FROM normalized_measure AS nm
            JOIN observation AS o ON o.observation_id = nm.observation_id
            """
        )
    }
    _require(
        measured_variables == set(NORMALIZED_VARIABLES),
        f"normalized_measure covers {sorted(measured_variables)}, expected {sorted(NORMALIZED_VARIABLES)}.",
    )

    # MUA/P is raw, never normalized.
    mua_p_normalized = connection.execute(
        """
        SELECT COUNT(*)
        FROM normalized_measure AS nm
        JOIN observation AS o ON o.observation_id = nm.observation_id
        WHERE o.variable_id = ?
        """,
        (RAW_DIMENSION_VARIABLE,),
    ).fetchone()[0]
    _require(mua_p_normalized == 0, f"{RAW_DIMENSION_VARIABLE} has {mua_p_normalized} normalized rows; MUA/P must stay raw.")

    orphan_obs = connection.execute(
        """
        SELECT COUNT(*)
        FROM normalized_measure AS nm
        LEFT JOIN observation AS o ON o.observation_id = nm.observation_id
        WHERE o.observation_id IS NULL
        """
    ).fetchone()[0]
    _require(orphan_obs == 0, f"{orphan_obs} normalized_measure rows reference a missing observation.")

    duplicates = connection.execute(
        """
        SELECT observation_id, methodology_version, COUNT(*)
        FROM normalized_measure
        GROUP BY observation_id, methodology_version
        HAVING COUNT(*) > 1
        """
    ).fetchall()
    _require(not duplicates, f"{len(duplicates)} duplicate (observation_id, methodology_version) normalized rows.")

    universe_set = set(universe)
    for variable_id in NORMALIZED_VARIABLES:
        rows = connection.execute(
            """
            SELECT o.observation_id, o.county_period_id, o.raw_value, nm.normalized_value
            FROM observation AS o
            JOIN normalized_measure AS nm
              ON nm.observation_id = o.observation_id
             AND nm.methodology_version = ?
            WHERE o.variable_id = ?
            ORDER BY o.observation_id
            """,
            (METHODOLOGY_VERSION, variable_id),
        ).fetchall()
        _require(
            len(rows) == EXPECTED_COUNTY_PERIODS,
            f"{variable_id!r} has {len(rows)} normalized rows, expected {EXPECTED_COUNTY_PERIODS}.",
        )
        _require(
            {cp_id for _, cp_id, _, _ in rows} == universe_set,
            f"{variable_id!r} normalized rows do not cover the full universe.",
        )

        recomputed = zero_preserving_percentile([raw for _, _, raw, _ in rows])
        for (observation_id, _, raw_value, persisted), expected_value in zip(rows, recomputed):
            _require(
                _close(persisted, expected_value),
                f"{variable_id!r} obs {observation_id}: normalized {persisted!r} != CE-A00 {expected_value!r}.",
            )
            if raw_value is None:
                _require(
                    persisted is None,
                    f"{variable_id!r} obs {observation_id}: missing raw value must stay NULL.",
                )
            elif raw_value == 0:
                _require(
                    persisted == 0.0,
                    f"{variable_id!r} obs {observation_id}: valid zero must normalize to exactly 0.0.",
                )
            if persisted is not None:
                _require(
                    0.0 <= persisted <= 100.0 + TOLERANCE,
                    f"{variable_id!r} obs {observation_id}: normalized {persisted!r} outside 0-100.",
                )

    log.append(f"normalization: {total} rows, 3 variables recomputed against CE-A00 within {TOLERANCE:g}")


def _check_dimension_scores(connection, universe, log) -> None:
    total = connection.execute("SELECT COUNT(*) FROM dimension_score").fetchone()[0]
    _require(
        total == len(COMPOSITE_DIMENSIONS) * EXPECTED_COUNTY_PERIODS,
        f"Expected {len(COMPOSITE_DIMENSIONS) * EXPECTED_COUNTY_PERIODS} dimension_score rows, found {total}.",
    )

    metadata = connection.execute(
        "SELECT DISTINCT methodology_version, status FROM dimension_score"
    ).fetchall()
    _require(
        metadata == [(METHODOLOGY_VERSION, DIMENSION_STATUS)],
        f"dimension_score metadata must be exactly ({METHODOLOGY_VERSION!r}, {DIMENSION_STATUS!r}), found {metadata}.",
    )

    duplicates = connection.execute(
        """
        SELECT county_period_id, dimension_id, methodology_version, COUNT(*)
        FROM dimension_score
        GROUP BY county_period_id, dimension_id, methodology_version
        HAVING COUNT(*) > 1
        """
    ).fetchall()
    _require(not duplicates, f"{len(duplicates)} duplicate dimension_score keys.")

    bad_coverage = connection.execute(
        """
        SELECT COUNT(*) FROM (
            SELECT county_period_id
            FROM dimension_score
            WHERE methodology_version = ?
            GROUP BY county_period_id
            HAVING COUNT(*) != 4
        )
        """,
        (METHODOLOGY_VERSION,),
    ).fetchone()[0]
    _require(bad_coverage == 0, f"{bad_coverage} county-periods do not carry exactly four dimensions.")

    orphan_cp = connection.execute(
        """
        SELECT COUNT(*)
        FROM dimension_score AS ds
        LEFT JOIN county_period AS cp ON cp.county_period_id = ds.county_period_id
        WHERE cp.county_period_id IS NULL
        """
    ).fetchone()[0]
    _require(orphan_cp == 0, f"{orphan_cp} dimension_score rows reference a missing county_period.")
    orphan_dim = connection.execute(
        """
        SELECT COUNT(*)
        FROM dimension_score AS ds
        LEFT JOIN dimension_definition AS dd ON dd.dimension_id = ds.dimension_id
        WHERE dd.dimension_id IS NULL
        """
    ).fetchone()[0]
    _require(orphan_dim == 0, f"{orphan_dim} dimension_score rows reference an undefined dimension.")

    universe_set = set(universe)

    # Normalized dimensions: exact identity copy of normalized_measure.
    for dimension_id, variable_id in NORMALIZED_DIMENSIONS.items():
        rows = connection.execute(
            """
            SELECT ds.county_period_id, ds.score, nm.normalized_value
            FROM dimension_score AS ds
            JOIN observation AS o
              ON o.county_period_id = ds.county_period_id
             AND o.variable_id = ?
            JOIN normalized_measure AS nm
              ON nm.observation_id = o.observation_id
             AND nm.methodology_version = ?
            WHERE ds.dimension_id = ?
              AND ds.methodology_version = ?
            """,
            (variable_id, METHODOLOGY_VERSION, dimension_id, METHODOLOGY_VERSION),
        ).fetchall()
        _require(
            len(rows) == EXPECTED_COUNTY_PERIODS,
            f"{dimension_id}: {len(rows)} rows reconcile to normalized_measure, expected {EXPECTED_COUNTY_PERIODS}.",
        )
        _require(
            {cp_id for cp_id, _, _ in rows} == universe_set,
            f"{dimension_id}: does not cover the full county-period universe.",
        )
        for cp_id, score, normalized_value in rows:
            if normalized_value is None:
                _require(score is None, f"{dimension_id} cp {cp_id}: expected NULL identity copy.")
            else:
                _require(
                    score is not None and score == normalized_value,
                    f"{dimension_id} cp {cp_id}: score {score!r} is not an exact copy of normalized {normalized_value!r}.",
                )
                _require(
                    0.0 <= score <= 100.0 + TOLERANCE,
                    f"{dimension_id} cp {cp_id}: score {score!r} outside 0-100.",
                )

    # MUA/P dimension: exact identity copy of the RAW coverage observation.
    mua_rows = connection.execute(
        """
        SELECT ds.county_period_id, ds.score, o.raw_value
        FROM dimension_score AS ds
        JOIN observation AS o
          ON o.county_period_id = ds.county_period_id
         AND o.variable_id = ?
        WHERE ds.dimension_id = ?
          AND ds.methodology_version = ?
        """,
        (RAW_DIMENSION_VARIABLE, RAW_DIMENSION, METHODOLOGY_VERSION),
    ).fetchall()
    _require(
        len(mua_rows) == EXPECTED_COUNTY_PERIODS,
        f"{RAW_DIMENSION}: {len(mua_rows)} rows reconcile to raw observations, expected {EXPECTED_COUNTY_PERIODS}.",
    )
    _require(
        {cp_id for cp_id, _, _ in mua_rows} == universe_set,
        f"{RAW_DIMENSION}: does not cover the full county-period universe.",
    )
    for cp_id, score, raw_value in mua_rows:
        if raw_value is None:
            _require(score is None, f"{RAW_DIMENSION} cp {cp_id}: expected NULL raw copy.")
        else:
            _require(
                score is not None and score == raw_value,
                f"{RAW_DIMENSION} cp {cp_id}: score {score!r} is not the raw coverage value {raw_value!r}.",
            )

    log.append(f"dimension_score: {total} rows (3 identity-normalized + MUA/P raw) fully reconciled")


def _check_composite(connection, universe, log) -> dict:
    total = connection.execute("SELECT COUNT(*) FROM composite_score").fetchone()[0]
    _require(
        total == EXPECTED_COUNTY_PERIODS,
        f"Expected {EXPECTED_COUNTY_PERIODS} composite_score rows, found {total}.",
    )

    versions = connection.execute(
        "SELECT DISTINCT methodology_version FROM composite_score"
    ).fetchall()
    _require(
        versions == [(METHODOLOGY_VERSION,)],
        f"composite_score methodology_version must be exactly {METHODOLOGY_VERSION!r}, found {versions}.",
    )

    distinct_cp = connection.execute(
        "SELECT COUNT(DISTINCT county_period_id) FROM composite_score"
    ).fetchone()[0]
    _require(distinct_cp == EXPECTED_COUNTY_PERIODS, "composite_score is not one row per county-period.")

    duplicates = connection.execute(
        """
        SELECT county_period_id, methodology_version, COUNT(*)
        FROM composite_score
        GROUP BY county_period_id, methodology_version
        HAVING COUNT(*) > 1
        """
    ).fetchall()
    _require(not duplicates, f"{len(duplicates)} duplicate composite_score keys.")

    orphan_cp = connection.execute(
        """
        SELECT COUNT(*)
        FROM composite_score AS cs
        LEFT JOIN county_period AS cp ON cp.county_period_id = cs.county_period_id
        WHERE cp.county_period_id IS NULL
        """
    ).fetchone()[0]
    _require(orphan_cp == 0, f"{orphan_cp} composite_score rows reference a missing county_period.")

    dimension_scores: dict[int, dict[str, float | None]] = {}
    for cp_id, dimension_id, score in connection.execute(
        """
        SELECT county_period_id, dimension_id, score
        FROM dimension_score
        WHERE methodology_version = ?
          AND dimension_id IN (?, ?, ?, ?)
        """,
        (METHODOLOGY_VERSION, *COMPOSITE_DIMENSIONS),
    ):
        dimension_scores.setdefault(cp_id, {})[dimension_id] = score

    rows = connection.execute(
        """
        SELECT county_period_id, composite_value, status, missing_dimensions
        FROM composite_score
        WHERE methodology_version = ?
        """,
        (METHODOLOGY_VERSION,),
    ).fetchall()
    _require(
        {cp_id for cp_id, _, _, _ in rows} == set(universe),
        "composite_score does not cover the full county-period universe.",
    )

    complete = 0
    incomplete = 0
    for cp_id, value, status, missing_dimensions in rows:
        available = dimension_scores.get(cp_id, {})
        unavailable = [
            dimension_id
            for dimension_id in COMPOSITE_DIMENSIONS
            if dimension_id not in available or available[dimension_id] is None
        ]

        _require(
            "experimental" in (status or "") and "provisional" in (status or ""),
            f"cp {cp_id}: composite status {status!r} is not explicitly Experimental/Provisional.",
        )

        if not unavailable:
            complete += 1
            expected_value = sum(available[d] for d in COMPOSITE_DIMENSIONS) / len(COMPOSITE_DIMENSIONS)
            _require(
                status == COMPOSITE_STATUS_COMPLETE,
                f"cp {cp_id}: complete composite status {status!r} != {COMPOSITE_STATUS_COMPLETE!r}.",
            )
            _require(
                missing_dimensions is None,
                f"cp {cp_id}: complete composite must not name missing dimensions ({missing_dimensions!r}).",
            )
            _require(value is not None, f"cp {cp_id}: complete composite value is NULL.")
            _require(
                _close(value, expected_value),
                f"cp {cp_id}: composite {value!r} != equal-weight mean {expected_value!r}.",
            )
            _require(
                0.0 <= value <= 100.0 + TOLERANCE,
                f"cp {cp_id}: composite {value!r} outside 0-100.",
            )
        else:
            incomplete += 1
            _require(
                value is None,
                f"cp {cp_id}: incomplete composite must be NULL (no partial averaging, no zero substitution); found {value!r}.",
            )
            _require(
                status == COMPOSITE_STATUS_INCOMPLETE,
                f"cp {cp_id}: incomplete composite status {status!r} != {COMPOSITE_STATUS_INCOMPLETE!r}.",
            )
            expected_missing = ", ".join(
                d for d in COMPOSITE_DIMENSIONS if d in unavailable
            )
            _require(
                bool(missing_dimensions) and missing_dimensions == expected_missing,
                f"cp {cp_id}: missing_dimensions {missing_dimensions!r} != {expected_missing!r}.",
            )

    _require(
        complete + incomplete == EXPECTED_COUNTY_PERIODS,
        "composite completeness partition does not sum to the universe.",
    )
    log.append(
        f"composite: {total} rows, {complete} complete / {incomplete} incomplete, "
        f"all-four-available rule reconciled within {TOLERANCE:g}"
    )
    return {"complete": complete, "incomplete": incomplete}


def _check_integrity(connection, log) -> None:
    fk_errors = connection.execute("PRAGMA foreign_key_check").fetchall()
    _require(not fk_errors, f"PRAGMA foreign_key_check reported {len(fk_errors)} error(s): {fk_errors[:5]}")

    integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    _require(integrity == "ok", f"PRAGMA integrity_check returned {integrity!r}.")

    log.append("integrity: foreign_key_check clean, integrity_check ok")


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------
def run_full_validation(database_path=DATABASE_PATH, *, verbose: bool = True) -> dict:
    """Run every CE-A06 check read-only. Raise on the first inconsistency."""

    connection = _connect_readonly(database_path)
    log: list[str] = []
    try:
        universe = _check_structure(connection, log)
        _check_observations(connection, universe, log)
        _check_normalization(connection, universe, log)
        _check_dimension_scores(connection, universe, log)
        composite = _check_composite(connection, universe, log)
        _check_integrity(connection, log)
    finally:
        connection.close()

    summary = {
        "county_periods": EXPECTED_COUNTY_PERIODS,
        "observations": EXPECTED_OBSERVATIONS,
        "normalized_measures": len(NORMALIZED_VARIABLES) * EXPECTED_COUNTY_PERIODS,
        "dimension_scores": len(COMPOSITE_DIMENSIONS) * EXPECTED_COUNTY_PERIODS,
        "composite_scores": EXPECTED_COUNTY_PERIODS,
        "composite_complete": composite["complete"],
        "composite_incomplete": composite["incomplete"],
    }

    if verbose:
        for line in log:
            print(f"  [PASS] {line}")

    return summary


def main():
    print("=" * 70)
    print("CHIA v0.1 COUNTY EXPLORER -- FULL ANALYTICAL VALIDATION (CE-A06)")
    print("=" * 70)
    print()

    summary = run_full_validation(DATABASE_PATH)

    print()
    for key, value in summary.items():
        print(f"    {key:<22} {value:,}")
    print()
    print("=" * 70)
    print("FULL ANALYTICAL VALIDATION PASSED")
    print("=" * 70)


if __name__ == "__main__":
    main()
