"""CE-A02 tests for atomic approved normalized-measure persistence.

Acceptance wording follows the approved option (b): the normalized scale is
0--100, an *untied* maximum positive observation receives exactly 100, and a
tied maximum keeps the value produced by the approved average-rank CE-A00
formula (it is never special-cased upward to 100). Every persisted value is
reconciled against CE-A00 ``zero_preserving_percentile`` within 1e-12.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest
from unittest import mock

import app.services.normalization_processing as normalization_processing
from app.services.normalization import zero_preserving_percentile
from app.services.normalization_processing import (
    ABSOLUTE_TOLERANCE,
    METHODOLOGY_VERSION,
    NORMALIZATION_METHOD,
    TARGET_VARIABLES,
    rebuild_normalized_measures,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DATABASE = PROJECT_ROOT / "Data" / "Model" / "chia_v01.sqlite"

EXCLUDED_MUA_P_VARIABLE = "MUAP_GEOGRAPHIC_COVERAGE"
EXPECTED_ROWS_PER_VARIABLE = 3143
EXPECTED_TARGET_ROWS = EXPECTED_ROWS_PER_VARIABLE * len(TARGET_VARIABLES)


def normalized_measure_digest(connection: sqlite3.Connection) -> tuple[int, str]:
    digest = hashlib.sha256()
    count = 0
    for row in connection.execute(
        """
        SELECT observation_id, methodology_version, normalized_value,
               normalization_method
        FROM normalized_measure
        ORDER BY observation_id, methodology_version
        """
    ):
        digest.update(repr(row).encode("utf-8"))
        count += 1
    return count, digest.hexdigest()


def observation_digest(connection: sqlite3.Connection) -> tuple[int, str]:
    digest = hashlib.sha256()
    count = 0
    for row in connection.execute(
        """
        SELECT observation_id, county_period_id, variable_id, raw_value,
               raw_text, quality_flag, notes
        FROM observation
        ORDER BY observation_id
        """
    ):
        digest.update(repr(row).encode("utf-8"))
        count += 1
    return count, digest.hexdigest()


def create_test_database() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.executescript(
        """
        CREATE TABLE county (county_fips TEXT PRIMARY KEY);
        CREATE TABLE county_period (
            county_period_id INTEGER PRIMARY KEY,
            county_fips TEXT NOT NULL,
            period TEXT NOT NULL
        );
        CREATE TABLE observation (
            observation_id INTEGER PRIMARY KEY,
            county_period_id INTEGER NOT NULL,
            variable_id TEXT NOT NULL,
            raw_value REAL,
            quality_flag TEXT
        );
        CREATE TABLE methodology (methodology_version TEXT PRIMARY KEY);
        CREATE TABLE normalized_measure (
            observation_id INTEGER NOT NULL,
            methodology_version TEXT NOT NULL,
            normalized_value REAL,
            normalization_method TEXT NOT NULL,
            PRIMARY KEY (observation_id, methodology_version)
        );
        """
    )
    connection.execute("INSERT INTO methodology VALUES (?)", (METHODOLOGY_VERSION,))
    connection.executemany(
        "INSERT INTO county VALUES (?)", [("01001",), ("01003",), ("01005",)]
    )
    connection.executemany(
        "INSERT INTO county_period VALUES (?, ?, ?)",
        [(1, "01001", "v0.1"), (2, "01003", "v0.1"), (3, "01005", "v0.1")],
    )
    observation_id = 1
    for variable_id in TARGET_VARIABLES:
        for county_period_id, raw_value in [(1, 0.0), (2, 1.0), (3, 2.0)]:
            connection.execute(
                "INSERT INTO observation VALUES (?, ?, ?, ?, ?)",
                (observation_id, county_period_id, variable_id, raw_value, "source_validated"),
            )
            connection.execute(
                "INSERT INTO normalized_measure VALUES (?, ?, ?, ?)",
                (observation_id, METHODOLOGY_VERSION, 0.5, NORMALIZATION_METHOD),
            )
            observation_id += 1
    connection.commit()
    return connection


def build_scenario_database(path: Path, raw_values: list[float | None]) -> None:
    """Create an on-disk database applying ``raw_values`` to every target var.

    ``None`` is stored as an observation row with a NULL ``raw_value`` (the
    canonical "missing" representation for a county that is still part of the
    complete universe). A legacy 0.5 normalized row is seeded for every
    observation so replacement and roll-back can be observed.
    """

    connection = create_test_database()
    connection.execute("DELETE FROM normalized_measure")
    connection.execute("DELETE FROM observation")
    connection.execute("DELETE FROM county_period")
    connection.execute("DELETE FROM county")

    fips = [f"01{2 * index + 1:03d}" for index in range(len(raw_values))]
    connection.executemany("INSERT INTO county VALUES (?)", [(code,) for code in fips])
    connection.executemany(
        "INSERT INTO county_period VALUES (?, ?, ?)",
        [(index + 1, code, "v0.1") for index, code in enumerate(fips)],
    )

    observation_id = 1
    for variable_id in TARGET_VARIABLES:
        for county_period_id, raw_value in enumerate(raw_values, start=1):
            connection.execute(
                "INSERT INTO observation VALUES (?, ?, ?, ?, ?)",
                (observation_id, county_period_id, variable_id, raw_value, "source_validated"),
            )
            connection.execute(
                "INSERT INTO normalized_measure VALUES (?, ?, ?, ?)",
                (observation_id, METHODOLOGY_VERSION, 0.5, NORMALIZATION_METHOD),
            )
            observation_id += 1
    connection.commit()

    disk_connection = sqlite3.connect(path)
    connection.backup(disk_connection)
    disk_connection.close()
    connection.close()


def target_normalized_rows(connection: sqlite3.Connection) -> list[tuple]:
    return connection.execute(
        f"""
        SELECT o.variable_id, o.observation_id, nm.normalized_value,
               nm.methodology_version, nm.normalization_method
        FROM normalized_measure AS nm
        JOIN observation AS o ON o.observation_id = nm.observation_id
        WHERE o.variable_id IN ({", ".join("?" for _ in TARGET_VARIABLES)})
        ORDER BY o.variable_id, o.observation_id
        """,
        TARGET_VARIABLES,
    ).fetchall()


class NormalizationProcessingUnitTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.directory.name) / "test.sqlite"
        connection = create_test_database()
        disk_connection = sqlite3.connect(self.database_path)
        connection.backup(disk_connection)
        disk_connection.close()
        connection.close()

    def tearDown(self):
        self.directory.cleanup()

    def test_rebuild_replaces_target_rows_and_is_idempotent(self):
        summary = rebuild_normalized_measures(self.database_path)
        self.assertEqual(summary.counts_by_variable, {variable: 3 for variable in TARGET_VARIABLES})

        connection = sqlite3.connect(self.database_path)
        try:
            rows = connection.execute(
                "SELECT normalized_value FROM normalized_measure ORDER BY observation_id"
            ).fetchall()
            self.assertEqual(rows, [(0.0,), (0.0,), (100.0,)] * 3)
            first_digest = normalized_measure_digest(connection)
        finally:
            connection.close()

        rebuild_normalized_measures(self.database_path)
        connection = sqlite3.connect(self.database_path)
        try:
            self.assertEqual(normalized_measure_digest(connection), first_digest)
        finally:
            connection.close()

    def test_missing_methodology_rolls_back_without_replacing_legacy_rows(self):
        connection = sqlite3.connect(self.database_path)
        try:
            before = normalized_measure_digest(connection)
            connection.execute("DELETE FROM methodology")
            connection.commit()
        finally:
            connection.close()

        with self.assertRaisesRegex(ValueError, "Methodology"):
            rebuild_normalized_measures(self.database_path)

        connection = sqlite3.connect(self.database_path)
        try:
            self.assertEqual(normalized_measure_digest(connection), before)
        finally:
            connection.close()

    def test_failure_after_delete_rolls_back_entire_transaction(self):
        connection = sqlite3.connect(self.database_path)
        try:
            before = normalized_measure_digest(connection)
        finally:
            connection.close()

        with mock.patch.object(
            normalization_processing,
            "_validate_persisted_records",
            side_effect=RuntimeError("post-write validation failure"),
        ):
            with self.assertRaises(RuntimeError):
                rebuild_normalized_measures(self.database_path)

        connection = sqlite3.connect(self.database_path)
        try:
            self.assertEqual(normalized_measure_digest(connection), before)
        finally:
            connection.close()

    def test_missing_zero_and_positive_values_are_handled_distinctly(self):
        raw_values = [None, 0.0, 4.0, 4.0, 4.0, 9.0]
        build_scenario_database(self.database_path, raw_values)

        rebuild_normalized_measures(self.database_path)

        connection = sqlite3.connect(self.database_path)
        try:
            rows = connection.execute(
                """
                SELECT o.county_period_id, o.raw_value, nm.normalized_value
                FROM normalized_measure AS nm
                JOIN observation AS o ON o.observation_id = nm.observation_id
                WHERE o.variable_id = ?
                ORDER BY o.county_period_id
                """,
                (TARGET_VARIABLES[0],),
            ).fetchall()
        finally:
            connection.close()

        by_cp = {county_period_id: value for county_period_id, _, value in rows}
        self.assertIsNone(by_cp[1])  # missing stays NULL, no normalized score
        self.assertEqual(by_cp[2], 0.0)  # valid zero stays exactly zero
        tie_scores = {by_cp[3], by_cp[4], by_cp[5]}  # identical values -> average rank
        self.assertEqual(len(tie_scores), 1)
        self.assertAlmostEqual(tie_scores.pop(), (100.0 / 3.0), places=9)
        self.assertEqual(by_cp[6], 100.0)  # untied maximum positive -> 100
        for value in by_cp.values():
            if value is not None:
                self.assertGreaterEqual(value, 0.0)
                self.assertLessEqual(value, 100.0)

    def test_tied_maximum_positive_is_not_forced_to_100(self):
        raw_values = [0.0, 2.0, 7.0, 7.0]
        build_scenario_database(self.database_path, raw_values)

        rebuild_normalized_measures(self.database_path)

        connection = sqlite3.connect(self.database_path)
        try:
            values = [
                row[0]
                for row in connection.execute(
                    """
                    SELECT nm.normalized_value
                    FROM normalized_measure AS nm
                    JOIN observation AS o ON o.observation_id = nm.observation_id
                    WHERE o.variable_id = ?
                    ORDER BY o.county_period_id
                    """,
                    (TARGET_VARIABLES[0],),
                )
            ]
        finally:
            connection.close()

        self.assertEqual(values[0], 0.0)
        self.assertEqual(values[1], 0.0)  # smallest positive collides with zero
        self.assertEqual(values[2], values[3])  # tied maximum -> equal average rank
        self.assertEqual(values[2], 75.0)
        self.assertLess(max(values), 100.0)  # tied maximum stays below the ceiling


class NormalizationProcessingIntegrationTest(unittest.TestCase):
    def setUp(self):
        if not SOURCE_DATABASE.exists():
            self.skipTest(f"Canonical database not found: {SOURCE_DATABASE}")

    def _mua_p_normalized_count(self, connection: sqlite3.Connection) -> int:
        return connection.execute(
            """
            SELECT COUNT(*)
            FROM normalized_measure AS nm
            JOIN observation AS o ON o.observation_id = nm.observation_id
            WHERE o.variable_id = ?
            """,
            (EXCLUDED_MUA_P_VARIABLE,),
        ).fetchone()[0]

    def _expected_scores_from_ce_a00(
        self, connection: sqlite3.Connection
    ) -> dict[int, float | None]:
        expected: dict[int, float | None] = {}
        for variable_id in TARGET_VARIABLES:
            rows = connection.execute(
                """
                SELECT o.observation_id, o.raw_value
                FROM county_period AS cp
                JOIN county AS c ON c.county_fips = cp.county_fips
                LEFT JOIN observation AS o
                  ON o.county_period_id = cp.county_period_id
                 AND o.variable_id = ?
                WHERE cp.period = ?
                ORDER BY c.county_fips
                """,
                (variable_id, METHODOLOGY_VERSION),
            ).fetchall()
            scores = zero_preserving_percentile(raw_value for _, raw_value in rows)
            for (observation_id, _), score in zip(rows, scores):
                expected[observation_id] = score
        return expected

    def test_production_shaped_rebuild_matches_ce_a00_and_preserves_everything_else(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "chia_v01.sqlite"
            shutil.copy2(SOURCE_DATABASE, database_path)

            connection = sqlite3.connect(database_path)
            try:
                observations_before = observation_digest(connection)
                full_normalized_before = normalized_measure_digest(connection)
                mua_p_before = self._mua_p_normalized_count(connection)
                non_target_before = connection.execute(
                    f"""
                    SELECT COUNT(*)
                    FROM normalized_measure AS nm
                    JOIN observation AS o ON o.observation_id = nm.observation_id
                    WHERE o.variable_id NOT IN ({", ".join("?" for _ in TARGET_VARIABLES)})
                    """,
                    TARGET_VARIABLES,
                ).fetchone()[0]
                legacy_target_before = len(target_normalized_rows(connection))
                expected_scores = self._expected_scores_from_ce_a00(connection)
            finally:
                connection.close()

            self.assertEqual(legacy_target_before, EXPECTED_TARGET_ROWS)  # legacy 9,429
            self.assertEqual(mua_p_before, 0)

            summary = rebuild_normalized_measures(database_path)
            self.assertEqual(
                summary.counts_by_variable,
                {variable: EXPECTED_ROWS_PER_VARIABLE for variable in TARGET_VARIABLES},
            )

            connection = sqlite3.connect(database_path)
            try:
                # Raw observations are untouched.
                self.assertEqual(observation_digest(connection), observations_before)

                # MUA/P is never normalized, inserted, or deleted.
                self.assertEqual(self._mua_p_normalized_count(connection), 0)

                # Non-target normalized rows are untouched.
                non_target_after = connection.execute(
                    f"""
                    SELECT COUNT(*)
                    FROM normalized_measure AS nm
                    JOIN observation AS o ON o.observation_id = nm.observation_id
                    WHERE o.variable_id NOT IN ({", ".join("?" for _ in TARGET_VARIABLES)})
                    """,
                    TARGET_VARIABLES,
                ).fetchone()[0]
                self.assertEqual(non_target_after, non_target_before)

                target_rows = target_normalized_rows(connection)
                self.assertEqual(len(target_rows), EXPECTED_TARGET_ROWS)  # exactly 9,429

                # Exactly 3,143 canonical records per variable, covering the
                # complete v0.1 county universe with no subset filtering.
                per_variable = connection.execute(
                    f"""
                    SELECT o.variable_id,
                           COUNT(*),
                           COUNT(DISTINCT o.county_period_id)
                    FROM normalized_measure AS nm
                    JOIN observation AS o ON o.observation_id = nm.observation_id
                    WHERE o.variable_id IN ({", ".join("?" for _ in TARGET_VARIABLES)})
                    GROUP BY o.variable_id
                    """,
                    TARGET_VARIABLES,
                ).fetchall()
                self.assertEqual(len(per_variable), len(TARGET_VARIABLES))
                universe_size = connection.execute(
                    "SELECT COUNT(*) FROM county_period WHERE period = ?",
                    (METHODOLOGY_VERSION,),
                ).fetchone()[0]
                self.assertEqual(universe_size, EXPECTED_ROWS_PER_VARIABLE)
                for _, row_count, distinct_cp in per_variable:
                    self.assertEqual(row_count, EXPECTED_ROWS_PER_VARIABLE)
                    self.assertEqual(distinct_cp, universe_size)

                # Exact method / version metadata on every persisted row.
                for _, _, _, methodology_version, method in target_rows:
                    self.assertEqual(methodology_version, METHODOLOGY_VERSION)
                    self.assertEqual(method, NORMALIZATION_METHOD)

                # No duplicate (observation_id, methodology_version).
                duplicates = connection.execute(
                    """
                    SELECT observation_id, methodology_version, COUNT(*)
                    FROM normalized_measure
                    GROUP BY observation_id, methodology_version
                    HAVING COUNT(*) > 1
                    """
                ).fetchall()
                self.assertEqual(duplicates, [])

                # Every persisted value equals CE-A00 within 1e-12, stays on the
                # 0--100 scale, and an untied per-variable maximum receives 100.
                observed_values = [value for _, _, value, _, _ in target_rows]
                self.assertEqual(min(v for v in observed_values if v is not None), 0.0)
                self.assertLessEqual(max(v for v in observed_values if v is not None), 100.0)
                for _, observation_id, value, _, _ in target_rows:
                    expected = expected_scores[observation_id]
                    if expected is None:
                        self.assertIsNone(value)
                    else:
                        self.assertIsNotNone(value)
                        self.assertLessEqual(abs(value - expected), ABSOLUTE_TOLERANCE)
                        self.assertGreaterEqual(value, 0.0)
                        self.assertLessEqual(value, 100.0)

                self._assert_untied_maxima_reach_100(connection, expected_scores)

                # Foreign-key integrity holds.
                self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])

                # The canonical source database already holds the approved
                # CE-A02 0--100 normalized state, so a production-shaped rebuild
                # is idempotent: rebuilding a copy that is already in the
                # approved state leaves the normalized-measure digest unchanged.
                rebuilt_digest = normalized_measure_digest(connection)
                self.assertEqual(rebuilt_digest, full_normalized_before)
            finally:
                connection.close()

            # Rebuilding again still reconstructs the identical desired state.
            rebuild_normalized_measures(database_path)
            connection = sqlite3.connect(database_path)
            try:
                self.assertEqual(normalized_measure_digest(connection), rebuilt_digest)
            finally:
                connection.close()

    def _assert_untied_maxima_reach_100(self, connection, expected_scores):
        """Opportunistic check: where a target variable's maximum positive raw
        value is unique, CE-A00 assigns it exactly 100. Canonical data may have
        only tied maxima (raw 100.0 shared by many counties); that case is
        covered by the unit tests and is a no-op here.
        """

        for variable_id in TARGET_VARIABLES:
            rows = connection.execute(
                """
                SELECT o.observation_id, o.raw_value
                FROM observation AS o
                JOIN county_period AS cp ON cp.county_period_id = o.county_period_id
                WHERE o.variable_id = ? AND cp.period = ?
                """,
                (variable_id, METHODOLOGY_VERSION),
            ).fetchall()
            positives = [(oid, value) for oid, value in rows if value is not None and value > 0]
            if not positives:
                continue
            max_value = max(value for _, value in positives)
            observation_ids_at_max = [oid for oid, value in positives if value == max_value]
            if len(observation_ids_at_max) == 1:
                self.assertEqual(expected_scores[observation_ids_at_max[0]], 100.0)


if __name__ == "__main__":
    unittest.main()
