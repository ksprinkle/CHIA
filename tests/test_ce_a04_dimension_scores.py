"""CE-A04 tests for the atomic v0.1 dimension-score rebuild.

Approved methodology under test:

* PRIMARY_CARE / DENTAL / MENTAL_HEALTH dimension scores are an *identity copy*
  of the CE-A03 ``normalized_measure.normalized_value`` (0-100 scale) for the
  canonical primary variable -- no transform, rescale, weight, or inversion.
* NULL normalized values stay NULL; valid zero stays exactly ``0.0``; ties keep
  whatever CE-A00/CE-A03 produced.
* ``methodology_version = 'v0.1'``, ``status = 'calculated'``.
* MUA/P dimension-score rows are never deleted, inserted, or modified.
* The rebuild is one explicit transaction: validate before commit, roll back
  completely on any failure, and remain idempotent.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest
from unittest import mock

import Data.Model.build_v01_dimension_scores as dimension_module
from Data.Model.build_v01_dimension_scores import (
    METHODOLOGY_VERSION,
    TARGET_DIMENSIONS,
    UNTOUCHED_DIMENSION,
    rebuild_dimension_scores,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DATABASE = PROJECT_ROOT / "Data" / "Model" / "chia_v01.sqlite"

TARGET_DIMENSION_IDS = tuple(TARGET_DIMENSIONS)
EXPECTED_ROWS_PER_DIMENSION = 3143
EXPECTED_DIMENSION_SCORE_TOTAL = 12572  # 4 dimensions x 3,143 county-periods

SCHEMA_SQL = """
CREATE TABLE county (county_fips TEXT PRIMARY KEY);
CREATE TABLE county_period (
    county_period_id INTEGER PRIMARY KEY,
    county_fips TEXT NOT NULL,
    period TEXT NOT NULL,
    FOREIGN KEY (county_fips) REFERENCES county(county_fips)
);
CREATE TABLE methodology (methodology_version TEXT PRIMARY KEY);
CREATE TABLE variable_definition (
    variable_id TEXT PRIMARY KEY,
    direction TEXT
);
CREATE TABLE observation (
    observation_id INTEGER PRIMARY KEY,
    county_period_id INTEGER NOT NULL,
    variable_id TEXT NOT NULL,
    raw_value REAL,
    raw_text TEXT,
    quality_flag TEXT,
    notes TEXT,
    FOREIGN KEY (county_period_id) REFERENCES county_period(county_period_id),
    FOREIGN KEY (variable_id) REFERENCES variable_definition(variable_id),
    UNIQUE (county_period_id, variable_id)
);
CREATE TABLE normalized_measure (
    observation_id INTEGER NOT NULL,
    methodology_version TEXT NOT NULL,
    normalized_value REAL,
    normalization_method TEXT NOT NULL,
    PRIMARY KEY (observation_id, methodology_version),
    FOREIGN KEY (observation_id) REFERENCES observation(observation_id),
    FOREIGN KEY (methodology_version) REFERENCES methodology(methodology_version)
);
CREATE TABLE dimension_definition (
    dimension_id TEXT PRIMARY KEY,
    primary_variable_id TEXT NOT NULL,
    methodology_version TEXT NOT NULL,
    FOREIGN KEY (primary_variable_id) REFERENCES variable_definition(variable_id),
    FOREIGN KEY (methodology_version) REFERENCES methodology(methodology_version)
);
CREATE TABLE dimension_score (
    county_period_id INTEGER NOT NULL,
    dimension_id TEXT NOT NULL,
    score REAL,
    methodology_version TEXT NOT NULL,
    status TEXT,
    PRIMARY KEY (county_period_id, dimension_id, methodology_version),
    FOREIGN KEY (county_period_id) REFERENCES county_period(county_period_id),
    FOREIGN KEY (dimension_id) REFERENCES dimension_definition(dimension_id),
    FOREIGN KEY (methodology_version) REFERENCES methodology(methodology_version)
);
CREATE TABLE composite_score (
    county_period_id INTEGER NOT NULL,
    methodology_version TEXT NOT NULL,
    composite_value REAL,
    PRIMARY KEY (county_period_id, methodology_version)
);
"""

DEFAULT_NORMALIZED = {
    "PC_HPSA_GEOGRAPHIC_COVERAGE": [0.0, 25.0, 100.0],   # ascending -> direction
    "DENTAL_HPSA_GEOGRAPHIC_COVERAGE": [0.0, 50.0, 50.0],  # tie at max
    "MH_HPSA_GEOGRAPHIC_COVERAGE": [0.0, 0.0, 40.0],       # repeated zero
}


def _digest(cursor) -> tuple[int, str]:
    digest = hashlib.sha256()
    count = 0
    for row in cursor:
        digest.update(repr(row).encode("utf-8"))
        count += 1
    return count, digest.hexdigest()


def dimension_score_digest(connection: sqlite3.Connection) -> tuple[int, str]:
    return _digest(
        connection.execute(
            """
            SELECT county_period_id, dimension_id, score, methodology_version, status
            FROM dimension_score
            ORDER BY county_period_id, dimension_id, methodology_version
            """
        )
    )


def mua_p_digest(connection: sqlite3.Connection) -> tuple[int, str]:
    return _digest(
        connection.execute(
            """
            SELECT county_period_id, dimension_id, score, methodology_version, status
            FROM dimension_score
            WHERE dimension_id = ?
            ORDER BY county_period_id, methodology_version
            """,
            (UNTOUCHED_DIMENSION,),
        )
    )


def observation_digest(connection: sqlite3.Connection) -> tuple[int, str]:
    return _digest(
        connection.execute(
            """
            SELECT observation_id, county_period_id, variable_id, raw_value,
                   raw_text, quality_flag, notes
            FROM observation
            ORDER BY observation_id
            """
        )
    )


def normalized_measure_digest(connection: sqlite3.Connection) -> tuple[int, str]:
    return _digest(
        connection.execute(
            """
            SELECT observation_id, methodology_version, normalized_value,
                   normalization_method
            FROM normalized_measure
            ORDER BY observation_id, methodology_version
            """
        )
    )


def create_test_database(normalized_by_variable=None) -> sqlite3.Connection:
    normalized_by_variable = normalized_by_variable or {
        key: list(value) for key, value in DEFAULT_NORMALIZED.items()
    }
    lengths = {len(values) for values in normalized_by_variable.values()}
    assert len(lengths) == 1, "every target variable needs the same county count"
    county_count = lengths.pop()

    connection = sqlite3.connect(":memory:")
    connection.executescript(SCHEMA_SQL)

    connection.execute("INSERT INTO methodology VALUES (?)", (METHODOLOGY_VERSION,))
    for variable_id in (
        "PC_HPSA_GEOGRAPHIC_COVERAGE",
        "DENTAL_HPSA_GEOGRAPHIC_COVERAGE",
        "MH_HPSA_GEOGRAPHIC_COVERAGE",
        "MUAP_GEOGRAPHIC_COVERAGE",
    ):
        connection.execute(
            "INSERT INTO variable_definition VALUES (?, ?)",
            (variable_id, "higher_burden"),
        )

    fips = [f"01{2 * index + 1:03d}" for index in range(county_count)]
    connection.executemany("INSERT INTO county VALUES (?)", [(code,) for code in fips])
    connection.executemany(
        "INSERT INTO county_period VALUES (?, ?, ?)",
        [(index + 1, fips[index], "v0.1") for index in range(county_count)],
    )

    for dimension_id, variable_id in TARGET_DIMENSIONS.items():
        connection.execute(
            "INSERT INTO dimension_definition VALUES (?, ?, ?)",
            (dimension_id, variable_id, "v0.1"),
        )
    connection.execute(
        "INSERT INTO dimension_definition VALUES (?, ?, ?)",
        (UNTOUCHED_DIMENSION, "MUAP_GEOGRAPHIC_COVERAGE", "v0.1"),
    )

    observation_id = 1
    for variable_id, normalized_values in normalized_by_variable.items():
        for index, normalized_value in enumerate(normalized_values):
            county_period_id = index + 1
            raw_value = None if normalized_value is None else normalized_value + 1000.0
            connection.execute(
                "INSERT INTO observation VALUES (?, ?, ?, ?, ?, ?, ?)",
                (observation_id, county_period_id, variable_id, raw_value, None,
                 "source_validated", None),
            )
            connection.execute(
                "INSERT INTO normalized_measure VALUES (?, ?, ?, ?)",
                (observation_id, "v0.1", normalized_value,
                 "county_percentile_rank_average"),
            )
            observation_id += 1

    # MUA/P: raw observation only, NO normalized_measure row.
    mua_p_raw = [(index + 1) * 10.0 for index in range(county_count)]
    for index, raw_value in enumerate(mua_p_raw):
        connection.execute(
            "INSERT INTO observation VALUES (?, ?, ?, ?, ?, ?, ?)",
            (observation_id, index + 1, "MUAP_GEOGRAPHIC_COVERAGE", raw_value, None,
             "source_validated", None),
        )
        observation_id += 1

    # Pre-existing (stale) dimension_score rows for all four dimensions.
    for dimension_id in TARGET_DIMENSION_IDS:
        for index in range(county_count):
            connection.execute(
                "INSERT INTO dimension_score VALUES (?, ?, ?, ?, ?)",
                (index + 1, dimension_id, 0.5, "v0.1", "calculated"),
            )
    for index in range(county_count):
        connection.execute(
            "INSERT INTO dimension_score VALUES (?, ?, ?, ?, ?)",
            (index + 1, UNTOUCHED_DIMENSION, mua_p_raw[index], "v0.1", "calculated"),
        )

    connection.commit()
    return connection


class DimensionScoreProcessingUnitTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.directory.name) / "test.sqlite"
        self._write(create_test_database())

    def tearDown(self):
        self.directory.cleanup()

    def _write(self, connection: sqlite3.Connection) -> None:
        disk_connection = sqlite3.connect(self.database_path)
        connection.backup(disk_connection)
        disk_connection.close()
        connection.close()

    def _reseed(self, normalized_by_variable) -> None:
        if self.database_path.exists():
            self.database_path.unlink()
        self._write(create_test_database(normalized_by_variable))

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.database_path)

    def test_rebuild_is_exact_identity_copy_and_idempotent(self):
        summary = rebuild_dimension_scores(self.database_path)
        self.assertEqual(
            summary.counts_by_dimension,
            {dimension_id: 3 for dimension_id in TARGET_DIMENSION_IDS},
        )

        connection = self._connect()
        try:
            rows = connection.execute(
                """
                SELECT ds.dimension_id, ds.county_period_id, ds.score,
                       nm.normalized_value, ds.methodology_version, ds.status
                FROM dimension_score AS ds
                JOIN dimension_definition AS dd
                  ON dd.dimension_id = ds.dimension_id
                JOIN observation AS o
                  ON o.county_period_id = ds.county_period_id
                 AND o.variable_id = dd.primary_variable_id
                JOIN normalized_measure AS nm
                  ON nm.observation_id = o.observation_id
                 AND nm.methodology_version = 'v0.1'
                WHERE ds.dimension_id IN ('PRIMARY_CARE', 'DENTAL', 'MENTAL_HEALTH')
                """
            ).fetchall()
            self.assertEqual(len(rows), 9)
            for _, _, score, normalized_value, version, status in rows:
                self.assertEqual(score, normalized_value)  # exact identity
                self.assertEqual(version, "v0.1")
                self.assertEqual(status, "calculated")
            first_digest = dimension_score_digest(connection)
        finally:
            connection.close()

        rebuild_dimension_scores(self.database_path)
        connection = self._connect()
        try:
            self.assertEqual(dimension_score_digest(connection), first_digest)
        finally:
            connection.close()

    def test_mua_p_rows_are_never_touched(self):
        connection = self._connect()
        try:
            before = connection.execute(
                """
                SELECT county_period_id, dimension_id, score, methodology_version, status
                FROM dimension_score WHERE dimension_id = ?
                ORDER BY county_period_id
                """,
                (UNTOUCHED_DIMENSION,),
            ).fetchall()
            digest_before = mua_p_digest(connection)
        finally:
            connection.close()

        rebuild_dimension_scores(self.database_path)

        connection = self._connect()
        try:
            after = connection.execute(
                """
                SELECT county_period_id, dimension_id, score, methodology_version, status
                FROM dimension_score WHERE dimension_id = ?
                ORDER BY county_period_id
                """,
                (UNTOUCHED_DIMENSION,),
            ).fetchall()
            self.assertEqual(after, before)
            self.assertEqual(mua_p_digest(connection), digest_before)
            mismatches = connection.execute(
                """
                SELECT COUNT(*)
                FROM dimension_score AS ds
                JOIN observation AS o
                  ON o.county_period_id = ds.county_period_id
                 AND o.variable_id = 'MUAP_GEOGRAPHIC_COVERAGE'
                WHERE ds.dimension_id = ? AND ds.score IS NOT o.raw_value
                """,
                (UNTOUCHED_DIMENSION,),
            ).fetchone()[0]
            self.assertEqual(mismatches, 0)
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM dimension_score WHERE dimension_id = ?",
                    (UNTOUCHED_DIMENSION,),
                ).fetchone()[0],
                3,
            )
        finally:
            connection.close()

    def test_missing_methodology_rolls_back(self):
        connection = self._connect()
        try:
            before = dimension_score_digest(connection)
            connection.execute("DELETE FROM methodology")
            connection.commit()
        finally:
            connection.close()

        with self.assertRaisesRegex(ValueError, "Methodology"):
            rebuild_dimension_scores(self.database_path)

        connection = self._connect()
        try:
            self.assertEqual(dimension_score_digest(connection), before)
        finally:
            connection.close()

    def test_failure_after_delete_rolls_back_entire_transaction(self):
        connection = self._connect()
        try:
            before = dimension_score_digest(connection)
        finally:
            connection.close()

        with mock.patch.object(
            dimension_module,
            "_validate_persisted_records",
            side_effect=RuntimeError("post-write validation failure"),
        ):
            with self.assertRaises(RuntimeError):
                rebuild_dimension_scores(self.database_path)

        connection = self._connect()
        try:
            self.assertEqual(dimension_score_digest(connection), before)
        finally:
            connection.close()

    def test_dimension_definition_mismatch_rolls_back(self):
        connection = self._connect()
        try:
            before = dimension_score_digest(connection)
            connection.execute(
                """
                UPDATE dimension_definition
                SET primary_variable_id = 'MH_HPSA_GEOGRAPHIC_COVERAGE'
                WHERE dimension_id = 'PRIMARY_CARE'
                """
            )
            connection.commit()
        finally:
            connection.close()

        with self.assertRaisesRegex(ValueError, "primary_variable_id"):
            rebuild_dimension_scores(self.database_path)

        connection = self._connect()
        try:
            self.assertEqual(dimension_score_digest(connection), before)
        finally:
            connection.close()

    def test_incomplete_source_measures_roll_back(self):
        connection = self._connect()
        try:
            before = dimension_score_digest(connection)
            connection.execute(
                """
                DELETE FROM normalized_measure
                WHERE observation_id IN (
                    SELECT observation_id FROM observation
                    WHERE variable_id = 'PC_HPSA_GEOGRAPHIC_COVERAGE'
                      AND county_period_id = 1
                )
                """
            )
            connection.commit()
        finally:
            connection.close()

        with self.assertRaisesRegex(ValueError, "expected 3 normalized measures"):
            rebuild_dimension_scores(self.database_path)

        connection = self._connect()
        try:
            self.assertEqual(dimension_score_digest(connection), before)
        finally:
            connection.close()

    def test_missing_normalized_value_maps_to_null_score(self):
        self._reseed(
            {
                "PC_HPSA_GEOGRAPHIC_COVERAGE": [0.0, None, 100.0],
                "DENTAL_HPSA_GEOGRAPHIC_COVERAGE": [0.0, 50.0, 50.0],
                "MH_HPSA_GEOGRAPHIC_COVERAGE": [0.0, 0.0, 40.0],
            }
        )

        rebuild_dimension_scores(self.database_path)

        connection = self._connect()
        try:
            primary_care = connection.execute(
                """
                SELECT county_period_id, score FROM dimension_score
                WHERE dimension_id = 'PRIMARY_CARE'
                ORDER BY county_period_id
                """
            ).fetchall()
            self.assertEqual(primary_care, [(1, 0.0), (2, None), (3, 100.0)])
            self.assertEqual(
                connection.execute(
                    "SELECT DISTINCT status FROM dimension_score WHERE dimension_id = 'PRIMARY_CARE'"
                ).fetchall(),
                [("calculated",)],
            )
        finally:
            connection.close()

    def test_zero_and_ties_are_preserved_exactly(self):
        rebuild_dimension_scores(self.database_path)

        connection = self._connect()
        try:
            dental = connection.execute(
                "SELECT score FROM dimension_score WHERE dimension_id = 'DENTAL' ORDER BY county_period_id"
            ).fetchall()
            self.assertEqual(dental, [(0.0,), (50.0,), (50.0,)])  # zero exact, ties equal

            mental_health = connection.execute(
                "SELECT score FROM dimension_score WHERE dimension_id = 'MENTAL_HEALTH' ORDER BY county_period_id"
            ).fetchall()
            self.assertEqual(mental_health, [(0.0,), (0.0,), (40.0,)])

            self.assertIsInstance(dental[0][0], float)
            self.assertEqual(dental[0][0], 0.0)
        finally:
            connection.close()

    def test_direction_is_preserved_no_inversion(self):
        rebuild_dimension_scores(self.database_path)

        connection = self._connect()
        try:
            primary_care = [
                row[0]
                for row in connection.execute(
                    "SELECT score FROM dimension_score WHERE dimension_id = 'PRIMARY_CARE' ORDER BY county_period_id"
                )
            ]
            normalized = [
                row[0]
                for row in connection.execute(
                    """
                    SELECT nm.normalized_value
                    FROM normalized_measure AS nm
                    JOIN observation AS o ON o.observation_id = nm.observation_id
                    WHERE o.variable_id = 'PC_HPSA_GEOGRAPHIC_COVERAGE'
                      AND nm.methodology_version = 'v0.1'
                    ORDER BY o.county_period_id
                    """
                )
            ]
            self.assertEqual(primary_care, normalized)              # identical, in order
            self.assertEqual(primary_care, [0.0, 25.0, 100.0])
            self.assertEqual(primary_care, sorted(primary_care))    # higher burden -> higher score
            self.assertLess(primary_care[0], primary_care[1])
            self.assertLess(primary_care[1], primary_care[2])
        finally:
            connection.close()

    def test_bootstrap_when_no_target_rows_exist(self):
        connection = self._connect()
        try:
            connection.execute(
                "DELETE FROM dimension_score WHERE dimension_id IN ('PRIMARY_CARE', 'DENTAL', 'MENTAL_HEALTH')"
            )
            connection.commit()
        finally:
            connection.close()

        summary = rebuild_dimension_scores(self.database_path)
        self.assertEqual(
            summary.counts_by_dimension,
            {dimension_id: 3 for dimension_id in TARGET_DIMENSION_IDS},
        )

        connection = self._connect()
        try:
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM dimension_score WHERE dimension_id = ?",
                    (UNTOUCHED_DIMENSION,),
                ).fetchone()[0],
                3,
            )
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM dimension_score").fetchone()[0], 12
            )
        finally:
            connection.close()

    def test_mua_p_is_not_recreated_when_absent(self):
        connection = self._connect()
        try:
            connection.execute(
                "DELETE FROM dimension_score WHERE dimension_id = ?", (UNTOUCHED_DIMENSION,)
            )
            connection.commit()
        finally:
            connection.close()

        rebuild_dimension_scores(self.database_path)

        connection = self._connect()
        try:
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM dimension_score WHERE dimension_id = ?",
                    (UNTOUCHED_DIMENSION,),
                ).fetchone()[0],
                0,
            )
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM dimension_score").fetchone()[0], 9
            )
        finally:
            connection.close()


class DimensionScoreProcessingIntegrationTest(unittest.TestCase):
    def setUp(self):
        if not SOURCE_DATABASE.exists():
            self.skipTest(f"Canonical database not found: {SOURCE_DATABASE}")

    def test_production_shaped_rebuild_on_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "chia_v01.sqlite"
            shutil.copy2(SOURCE_DATABASE, database_path)

            connection = sqlite3.connect(database_path)
            try:
                total_before = connection.execute(
                    "SELECT COUNT(*) FROM dimension_score"
                ).fetchone()[0]
                per_dimension_before = dict(
                    connection.execute(
                        "SELECT dimension_id, COUNT(*) FROM dimension_score GROUP BY dimension_id"
                    )
                )
                mua_p_digest_before = mua_p_digest(connection)
                normalized_digest_before = normalized_measure_digest(connection)
                observation_digest_before = observation_digest(connection)
                composite_before = connection.execute(
                    "SELECT COUNT(*) FROM composite_score"
                ).fetchone()[0]
            finally:
                connection.close()

            self.assertEqual(total_before, EXPECTED_DIMENSION_SCORE_TOTAL)
            self.assertEqual(per_dimension_before.get(UNTOUCHED_DIMENSION), EXPECTED_ROWS_PER_DIMENSION)

            summary = rebuild_dimension_scores(database_path)
            self.assertEqual(
                summary.counts_by_dimension,
                {dimension_id: EXPECTED_ROWS_PER_DIMENSION for dimension_id in TARGET_DIMENSION_IDS},
            )

            connection = sqlite3.connect(database_path)
            try:
                self.assertEqual(
                    connection.execute("SELECT COUNT(*) FROM dimension_score").fetchone()[0],
                    EXPECTED_DIMENSION_SCORE_TOTAL,
                )
                per_dimension_after = dict(
                    connection.execute(
                        "SELECT dimension_id, COUNT(*) FROM dimension_score GROUP BY dimension_id"
                    )
                )
                for dimension_id in (*TARGET_DIMENSION_IDS, UNTOUCHED_DIMENSION):
                    self.assertEqual(per_dimension_after[dimension_id], EXPECTED_ROWS_PER_DIMENSION)

                # Identity mapping: every rebuilt score == its normalized measure exactly.
                identity_mismatches = connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM dimension_score AS ds
                    JOIN dimension_definition AS dd
                      ON dd.dimension_id = ds.dimension_id
                    JOIN observation AS o
                      ON o.county_period_id = ds.county_period_id
                     AND o.variable_id = dd.primary_variable_id
                    JOIN normalized_measure AS nm
                      ON nm.observation_id = o.observation_id
                     AND nm.methodology_version = 'v0.1'
                    WHERE ds.dimension_id IN ('PRIMARY_CARE', 'DENTAL', 'MENTAL_HEALTH')
                      AND ds.methodology_version = 'v0.1'
                      AND ds.score IS NOT nm.normalized_value
                    """
                ).fetchone()[0]
                self.assertEqual(identity_mismatches, 0)

                # Production has no missing primary observations -> no NULL scores.
                null_scores = connection.execute(
                    """
                    SELECT COUNT(*) FROM dimension_score
                    WHERE dimension_id IN ('PRIMARY_CARE', 'DENTAL', 'MENTAL_HEALTH')
                      AND methodology_version = 'v0.1' AND score IS NULL
                    """
                ).fetchone()[0]
                self.assertEqual(null_scores, 0)

                # Exact metadata.
                self.assertEqual(
                    connection.execute(
                        """
                        SELECT DISTINCT methodology_version, status FROM dimension_score
                        WHERE dimension_id IN ('PRIMARY_CARE', 'DENTAL', 'MENTAL_HEALTH')
                        """
                    ).fetchall(),
                    [("v0.1", "calculated")],
                )

                # MUA/P dimension-score rows unchanged and still equal to raw coverage.
                self.assertEqual(mua_p_digest(connection), mua_p_digest_before)
                mua_p_mismatches = connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM dimension_score AS ds
                    JOIN observation AS o
                      ON o.county_period_id = ds.county_period_id
                     AND o.variable_id = 'MUAP_GEOGRAPHIC_COVERAGE'
                    WHERE ds.dimension_id = 'MUA_P'
                      AND ds.methodology_version = 'v0.1'
                      AND ds.score IS NOT o.raw_value
                    """
                ).fetchone()[0]
                self.assertEqual(mua_p_mismatches, 0)

                # Raw observations, normalized measures and composite untouched.
                self.assertEqual(observation_digest(connection), observation_digest_before)
                self.assertEqual(normalized_measure_digest(connection), normalized_digest_before)
                self.assertEqual(
                    connection.execute("SELECT COUNT(*) FROM composite_score").fetchone()[0],
                    composite_before,
                )

                # Every county-period still carries exactly four dimensions.
                self.assertEqual(
                    connection.execute(
                        """
                        SELECT county_period_id FROM dimension_score
                        WHERE methodology_version = 'v0.1'
                        GROUP BY county_period_id HAVING COUNT(*) != 4
                        """
                    ).fetchall(),
                    [],
                )

                # No duplicate (county_period_id, dimension_id, methodology_version).
                self.assertEqual(
                    connection.execute(
                        """
                        SELECT county_period_id, dimension_id, methodology_version, COUNT(*)
                        FROM dimension_score
                        GROUP BY county_period_id, dimension_id, methodology_version
                        HAVING COUNT(*) > 1
                        """
                    ).fetchall(),
                    [],
                )

                # Integrity.
                self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])
                self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone()[0], "ok")

                rebuilt_digest = dimension_score_digest(connection)
            finally:
                connection.close()

            # Idempotent rerun reproduces the identical dimension_score state.
            rebuild_dimension_scores(database_path)
            connection = sqlite3.connect(database_path)
            try:
                self.assertEqual(dimension_score_digest(connection), rebuilt_digest)
            finally:
                connection.close()


if __name__ == "__main__":
    unittest.main()
