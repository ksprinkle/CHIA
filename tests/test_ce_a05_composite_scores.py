"""CE-A05 tests for the atomic experimental v0.1 composite-score rebuild.

Approved methodology under test (specification section 9):

* ``composite_value`` = (PRIMARY_CARE + DENTAL + MENTAL_HEALTH + MUA_P) / 4,
  equal 25% weights, no rounding or other transformation.
* All four dimension scores must be available (a missing ``dimension_score`` row
  or a NULL score both count as unavailable).
* If any dimension is unavailable: ``composite_value`` is NULL, the missing
  dimension(s) are named in ``missing_dimensions`` in canonical order, and there
  is NO partial averaging and NO zero substitution.
* Every row is explicitly Experimental / Provisional via ``status``.
* Exactly one ``composite_score`` row per county-period, ``methodology_version``
  = 'v0.1'.
* The rebuild is one explicit transaction: validate before commit, roll back
  completely on any failure, idempotent.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest
from unittest import mock

import Data.Model.build_v01_composite_scores as composite_module
from Data.Model.build_v01_composite_scores import (
    ABSOLUTE_TOLERANCE,
    COMPOSITE_DIMENSIONS,
    COMPOSITE_STATUS_COMPLETE,
    COMPOSITE_STATUS_INCOMPLETE,
    METHODOLOGY_VERSION,
    rebuild_composite_scores,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DATABASE = PROJECT_ROOT / "Data" / "Model" / "chia_v01.sqlite"

EXPECTED_COUNTY_PERIODS = 3143

SCHEMA_SQL = """
CREATE TABLE county (county_fips TEXT PRIMARY KEY);
CREATE TABLE county_period (
    county_period_id INTEGER PRIMARY KEY,
    county_fips TEXT NOT NULL,
    period TEXT NOT NULL,
    FOREIGN KEY (county_fips) REFERENCES county(county_fips)
);
CREATE TABLE methodology (methodology_version TEXT PRIMARY KEY);
CREATE TABLE variable_definition (variable_id TEXT PRIMARY KEY);
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
    status TEXT,
    missing_dimensions TEXT,
    PRIMARY KEY (county_period_id, methodology_version),
    FOREIGN KEY (county_period_id) REFERENCES county_period(county_period_id),
    FOREIGN KEY (methodology_version) REFERENCES methodology(methodology_version)
);
"""

# Per county-period: {dimension_id: score}. A dimension key that is ABSENT means
# "no dimension_score row"; a key mapped to None means "row with NULL score".
DEFAULT_DIMENSION_SCORES = [
    {"PRIMARY_CARE": 0.0, "DENTAL": 40.0, "MENTAL_HEALTH": 80.0, "MUA_P": 100.0},   # mean 55.0
    {"PRIMARY_CARE": 25.0, "DENTAL": 25.0, "MENTAL_HEALTH": 25.0, "MUA_P": 25.0},   # mean 25.0
    {"PRIMARY_CARE": 0.1, "DENTAL": 0.2, "MENTAL_HEALTH": 0.3, "MUA_P": 0.4},       # no-rounding case
]


def _digest(cursor) -> tuple[int, str]:
    digest = hashlib.sha256()
    count = 0
    for row in cursor:
        digest.update(repr(row).encode("utf-8"))
        count += 1
    return count, digest.hexdigest()


def composite_score_digest(connection: sqlite3.Connection) -> tuple[int, str]:
    return _digest(
        connection.execute(
            """
            SELECT county_period_id, methodology_version, composite_value, status,
                   missing_dimensions
            FROM composite_score
            ORDER BY county_period_id, methodology_version
            """
        )
    )


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


def create_test_database(dimension_scores_by_cp=None) -> sqlite3.Connection:
    dimension_scores_by_cp = dimension_scores_by_cp or [
        dict(entry) for entry in DEFAULT_DIMENSION_SCORES
    ]
    county_count = len(dimension_scores_by_cp)

    connection = sqlite3.connect(":memory:")
    connection.executescript(SCHEMA_SQL)

    connection.execute("INSERT INTO methodology VALUES (?)", (METHODOLOGY_VERSION,))
    fips = [f"01{2 * index + 1:03d}" for index in range(county_count)]
    connection.executemany("INSERT INTO county VALUES (?)", [(code,) for code in fips])
    connection.executemany(
        "INSERT INTO county_period VALUES (?, ?, ?)",
        [(index + 1, fips[index], "v0.1") for index in range(county_count)],
    )
    for dimension_id in COMPOSITE_DIMENSIONS:
        variable_id = f"{dimension_id}_PRIMARY_VAR"
        connection.execute("INSERT INTO variable_definition VALUES (?)", (variable_id,))
        connection.execute(
            "INSERT INTO dimension_definition VALUES (?, ?, ?)",
            (dimension_id, variable_id, "v0.1"),
        )

    for index, scores in enumerate(dimension_scores_by_cp):
        county_period_id = index + 1
        for dimension_id in COMPOSITE_DIMENSIONS:
            if dimension_id not in scores:
                continue  # absent -> no dimension_score row
            connection.execute(
                "INSERT INTO dimension_score VALUES (?, ?, ?, ?, ?)",
                (county_period_id, dimension_id, scores[dimension_id], "v0.1", "calculated"),
            )

    # Pre-existing (stale) composite rows so replacement / rollback are visible.
    for index in range(county_count):
        connection.execute(
            "INSERT INTO composite_score VALUES (?, ?, ?, ?, ?)",
            (index + 1, "v0.1", 999.0, "stale", "STALE"),
        )

    connection.commit()
    return connection


class CompositeScoreProcessingUnitTest(unittest.TestCase):
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

    def _reseed(self, dimension_scores_by_cp) -> None:
        if self.database_path.exists():
            self.database_path.unlink()
        self._write(create_test_database(dimension_scores_by_cp))

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.database_path)

    def _composite_rows(self, connection):
        return connection.execute(
            """
            SELECT county_period_id, composite_value, status, missing_dimensions
            FROM composite_score
            ORDER BY county_period_id
            """
        ).fetchall()

    def test_complete_composite_is_equal_weight_mean_without_rounding(self):
        summary = rebuild_composite_scores(self.database_path)
        self.assertEqual(summary.total_rows, 3)
        self.assertEqual(summary.complete_rows, 3)
        self.assertEqual(summary.incomplete_rows, 0)

        connection = self._connect()
        try:
            rows = self._composite_rows(connection)
        finally:
            connection.close()

        self.assertEqual(rows[0], (1, 55.0, COMPOSITE_STATUS_COMPLETE, None))
        self.assertEqual(rows[1], (2, 25.0, COMPOSITE_STATUS_COMPLETE, None))
        # The third county-period exercises "no rounding": the persisted value is
        # exactly the IEEE-754 result of the Python mean expression.
        expected_third = (0.1 + 0.2 + 0.3 + 0.4) / 4
        self.assertEqual(rows[2][1], expected_third)
        self.assertEqual(rows[2][2], COMPOSITE_STATUS_COMPLETE)

    def test_missing_dimension_row_yields_null_and_names_dimension(self):
        self._reseed(
            [
                dict(DEFAULT_DIMENSION_SCORES[0]),
                {"PRIMARY_CARE": 25.0, "MENTAL_HEALTH": 25.0, "MUA_P": 25.0},  # DENTAL absent
                dict(DEFAULT_DIMENSION_SCORES[2]),
            ]
        )

        summary = rebuild_composite_scores(self.database_path)
        self.assertEqual((summary.complete_rows, summary.incomplete_rows), (2, 1))

        connection = self._connect()
        try:
            rows = self._composite_rows(connection)
        finally:
            connection.close()

        self.assertEqual(rows[0], (1, 55.0, COMPOSITE_STATUS_COMPLETE, None))
        self.assertEqual(rows[1], (2, None, COMPOSITE_STATUS_INCOMPLETE, "DENTAL"))
        self.assertEqual(rows[2][2], COMPOSITE_STATUS_COMPLETE)

    def test_null_dimension_score_yields_null_and_names_dimension(self):
        self._reseed(
            [
                {"PRIMARY_CARE": 10.0, "DENTAL": 20.0, "MENTAL_HEALTH": None, "MUA_P": 40.0},
                dict(DEFAULT_DIMENSION_SCORES[1]),
                dict(DEFAULT_DIMENSION_SCORES[2]),
            ]
        )

        rebuild_composite_scores(self.database_path)

        connection = self._connect()
        try:
            rows = self._composite_rows(connection)
        finally:
            connection.close()

        self.assertEqual(rows[0], (1, None, COMPOSITE_STATUS_INCOMPLETE, "MENTAL_HEALTH"))

    def test_multiple_missing_dimensions_named_in_canonical_order(self):
        self._reseed(
            [
                {"DENTAL": 20.0, "MENTAL_HEALTH": 30.0},  # PRIMARY_CARE + MUA_P absent
                dict(DEFAULT_DIMENSION_SCORES[1]),
                dict(DEFAULT_DIMENSION_SCORES[2]),
            ]
        )

        rebuild_composite_scores(self.database_path)

        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT composite_value, status, missing_dimensions FROM composite_score WHERE county_period_id = 1"
            ).fetchone()
        finally:
            connection.close()

        self.assertEqual(row, (None, COMPOSITE_STATUS_INCOMPLETE, "PRIMARY_CARE, MUA_P"))

    def test_no_zero_substitution_and_no_partial_averaging(self):
        self._reseed(
            [
                {"PRIMARY_CARE": 0.0, "DENTAL": 100.0, "MENTAL_HEALTH": 100.0},  # MUA_P absent
                dict(DEFAULT_DIMENSION_SCORES[1]),
                dict(DEFAULT_DIMENSION_SCORES[2]),
            ]
        )

        rebuild_composite_scores(self.database_path)

        connection = self._connect()
        try:
            value = connection.execute(
                "SELECT composite_value FROM composite_score WHERE county_period_id = 1"
            ).fetchone()[0]
        finally:
            connection.close()

        self.assertIsNone(value)
        # Not any partial-average or zero-substitution result.
        for forbidden in (50.0, (0.0 + 100.0 + 100.0) / 3, (0.0 + 100.0 + 100.0 + 0.0) / 4):
            self.assertNotEqual(value, forbidden)

    def test_one_row_per_county_period_even_with_no_dimension_rows(self):
        self._reseed(
            [
                {},  # county-period with zero dimension_score rows
                dict(DEFAULT_DIMENSION_SCORES[1]),
                dict(DEFAULT_DIMENSION_SCORES[2]),
            ]
        )

        summary = rebuild_composite_scores(self.database_path)
        self.assertEqual(summary.total_rows, 3)

        connection = self._connect()
        try:
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM composite_score").fetchone()[0], 3
            )
            row = connection.execute(
                "SELECT composite_value, status, missing_dimensions FROM composite_score WHERE county_period_id = 1"
            ).fetchone()
        finally:
            connection.close()

        self.assertEqual(
            row,
            (None, COMPOSITE_STATUS_INCOMPLETE, "PRIMARY_CARE, DENTAL, MENTAL_HEALTH, MUA_P"),
        )

    def test_rebuild_is_idempotent(self):
        rebuild_composite_scores(self.database_path)
        connection = self._connect()
        try:
            first_digest = composite_score_digest(connection)
        finally:
            connection.close()

        rebuild_composite_scores(self.database_path)
        connection = self._connect()
        try:
            self.assertEqual(composite_score_digest(connection), first_digest)
        finally:
            connection.close()

    def test_missing_methodology_rolls_back(self):
        connection = self._connect()
        try:
            before = composite_score_digest(connection)
            connection.execute("DELETE FROM methodology")
            connection.commit()
        finally:
            connection.close()

        with self.assertRaisesRegex(ValueError, "Methodology"):
            rebuild_composite_scores(self.database_path)

        connection = self._connect()
        try:
            self.assertEqual(composite_score_digest(connection), before)
        finally:
            connection.close()

    def test_failure_after_delete_rolls_back_entire_transaction(self):
        connection = self._connect()
        try:
            before = composite_score_digest(connection)
        finally:
            connection.close()

        with mock.patch.object(
            composite_module,
            "_validate_persisted_records",
            side_effect=RuntimeError("post-write validation failure"),
        ):
            with self.assertRaises(RuntimeError):
                rebuild_composite_scores(self.database_path)

        connection = self._connect()
        try:
            self.assertEqual(composite_score_digest(connection), before)
        finally:
            connection.close()

    def test_bootstrap_from_empty_composite_score(self):
        connection = self._connect()
        try:
            connection.execute("DELETE FROM composite_score")
            connection.commit()
        finally:
            connection.close()

        summary = rebuild_composite_scores(self.database_path)
        self.assertEqual(summary.total_rows, 3)

        connection = self._connect()
        try:
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM composite_score").fetchone()[0], 3
            )
        finally:
            connection.close()

    def test_direction_preserved_raising_a_dimension_raises_the_composite(self):
        self._reseed(
            [{dimension_id: 10.0 for dimension_id in COMPOSITE_DIMENSIONS}]
        )
        rebuild_composite_scores(self.database_path)
        connection = self._connect()
        try:
            low = connection.execute(
                "SELECT composite_value FROM composite_score WHERE county_period_id = 1"
            ).fetchone()[0]
        finally:
            connection.close()

        raised = {dimension_id: 10.0 for dimension_id in COMPOSITE_DIMENSIONS}
        raised["PRIMARY_CARE"] = 90.0
        self._reseed([raised])
        rebuild_composite_scores(self.database_path)
        connection = self._connect()
        try:
            high = connection.execute(
                "SELECT composite_value FROM composite_score WHERE county_period_id = 1"
            ).fetchone()[0]
        finally:
            connection.close()

        self.assertEqual(low, 10.0)
        self.assertEqual(high, (90.0 + 10.0 + 10.0 + 10.0) / 4)
        self.assertGreater(high, low)

    def test_status_is_explicitly_experimental_provisional(self):
        for status in (COMPOSITE_STATUS_COMPLETE, COMPOSITE_STATUS_INCOMPLETE):
            self.assertIn("experimental", status)
            self.assertIn("provisional", status)

        self._reseed(
            [
                dict(DEFAULT_DIMENSION_SCORES[0]),
                {"PRIMARY_CARE": 25.0},  # incomplete
                dict(DEFAULT_DIMENSION_SCORES[2]),
            ]
        )
        rebuild_composite_scores(self.database_path)
        connection = self._connect()
        try:
            statuses = {
                row[0]
                for row in connection.execute("SELECT DISTINCT status FROM composite_score")
            }
        finally:
            connection.close()
        self.assertEqual(statuses, {COMPOSITE_STATUS_COMPLETE, COMPOSITE_STATUS_INCOMPLETE})

    def test_composite_value_stays_within_zero_to_hundred(self):
        self._reseed(
            [
                {dimension_id: 100.0 for dimension_id in COMPOSITE_DIMENSIONS},
                {dimension_id: 0.0 for dimension_id in COMPOSITE_DIMENSIONS},
                dict(DEFAULT_DIMENSION_SCORES[0]),
            ]
        )
        rebuild_composite_scores(self.database_path)
        connection = self._connect()
        try:
            values = [
                row[0]
                for row in connection.execute(
                    "SELECT composite_value FROM composite_score ORDER BY county_period_id"
                )
            ]
        finally:
            connection.close()
        self.assertEqual(values[0], 100.0)
        self.assertEqual(values[1], 0.0)
        for value in values:
            self.assertGreaterEqual(value, 0.0)
            self.assertLessEqual(value, 100.0)


class CompositeScoreProcessingIntegrationTest(unittest.TestCase):
    def setUp(self):
        if not SOURCE_DATABASE.exists():
            self.skipTest(f"Canonical database not found: {SOURCE_DATABASE}")

    def test_production_shaped_rebuild_on_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "chia_v01.sqlite"
            shutil.copy2(SOURCE_DATABASE, database_path)

            connection = sqlite3.connect(database_path)
            try:
                dimension_digest_before = dimension_score_digest(connection)
                normalized_digest_before = normalized_measure_digest(connection)
                observation_digest_before = observation_digest(connection)
                universe_size = connection.execute(
                    "SELECT COUNT(*) FROM county_period WHERE period = 'v0.1'"
                ).fetchone()[0]
                dimension_rows = connection.execute(
                    """
                    SELECT ds.county_period_id, ds.dimension_id, ds.score
                    FROM dimension_score AS ds
                    WHERE ds.methodology_version = 'v0.1'
                      AND ds.dimension_id IN ('PRIMARY_CARE', 'DENTAL', 'MENTAL_HEALTH', 'MUA_P')
                    """
                ).fetchall()
            finally:
                connection.close()

            self.assertEqual(universe_size, EXPECTED_COUNTY_PERIODS)

            expected = {}
            grouped: dict[int, dict[str, float | None]] = {}
            for county_period_id, dimension_id, score in dimension_rows:
                grouped.setdefault(county_period_id, {})[dimension_id] = score
            for county_period_id in range(1, universe_size + 1):
                available = grouped.get(county_period_id, {})
                if all(
                    dimension_id in available and available[dimension_id] is not None
                    for dimension_id in COMPOSITE_DIMENSIONS
                ):
                    expected[county_period_id] = (
                        sum(available[d] for d in COMPOSITE_DIMENSIONS) / 4
                    )
                else:
                    expected[county_period_id] = None

            summary = rebuild_composite_scores(database_path)
            self.assertEqual(summary.total_rows, EXPECTED_COUNTY_PERIODS)
            self.assertEqual(summary.complete_rows, EXPECTED_COUNTY_PERIODS)
            self.assertEqual(summary.incomplete_rows, 0)

            connection = sqlite3.connect(database_path)
            try:
                rows = connection.execute(
                    """
                    SELECT county_period_id, methodology_version, composite_value,
                           status, missing_dimensions
                    FROM composite_score
                    """
                ).fetchall()
                self.assertEqual(len(rows), EXPECTED_COUNTY_PERIODS)

                for county_period_id, version, value, status, missing in rows:
                    self.assertEqual(version, "v0.1")
                    self.assertEqual(status, COMPOSITE_STATUS_COMPLETE)
                    self.assertIsNone(missing)
                    self.assertIsNotNone(value)
                    self.assertLessEqual(abs(value - expected[county_period_id]), ABSOLUTE_TOLERANCE)
                    self.assertGreaterEqual(value, 0.0)
                    self.assertLessEqual(value, 100.0)

                # One row per county-period; no duplicates.
                self.assertEqual(
                    connection.execute(
                        "SELECT COUNT(DISTINCT county_period_id) FROM composite_score"
                    ).fetchone()[0],
                    EXPECTED_COUNTY_PERIODS,
                )
                self.assertEqual(
                    connection.execute(
                        """
                        SELECT county_period_id, methodology_version, COUNT(*)
                        FROM composite_score
                        GROUP BY county_period_id, methodology_version
                        HAVING COUNT(*) > 1
                        """
                    ).fetchall(),
                    [],
                )

                # Upstream analytical tables untouched.
                self.assertEqual(dimension_score_digest(connection), dimension_digest_before)
                self.assertEqual(normalized_measure_digest(connection), normalized_digest_before)
                self.assertEqual(observation_digest(connection), observation_digest_before)

                self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])
                self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone()[0], "ok")

                rebuilt_digest = composite_score_digest(connection)
            finally:
                connection.close()

            # Idempotent rerun reproduces the identical composite_score state.
            rebuild_composite_scores(database_path)
            connection = sqlite3.connect(database_path)
            try:
                self.assertEqual(composite_score_digest(connection), rebuilt_digest)
            finally:
                connection.close()


if __name__ == "__main__":
    unittest.main()
