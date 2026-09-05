"""CE-A06 tests for the read-only full analytical-pipeline validator.

The validator itself performs no writes. These tests:

* confirm the production database passes and stays byte-identical;
* tamper with temporary copies to prove each reconciliation layer
  (observation -> normalized -> dimension -> composite, plus MUA/P-raw,
  metadata, counts, lineage, integrity) is actually checked;
* exercise the all-four-available composite rule's incomplete path on a
  temporary copy, using the approved CE-A02/CE-A04/CE-A05 rebuilds to
  produce a genuinely (and consistently) incomplete pipeline.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest

import Data.Model.build_v01_composite_scores as composite_module
import Data.Model.build_v01_dimension_scores as dimension_module
import Data.Model.validate_v01_county_explorer as cev
from app.services.normalization_processing import rebuild_normalized_measures


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DATABASE = PROJECT_ROOT / "Data" / "Model" / "chia_v01.sqlite"

EXPECTED_PRODUCTION_SHA256 = (
    "12b3525e77cdc85ba7fedbb463fcc75f21c489825c0e81d98cdf71a2b7c7174c"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class CountyExplorerProductionValidationTest(unittest.TestCase):
    def setUp(self):
        if not SOURCE_DATABASE.exists():
            self.skipTest(f"Canonical database not found: {SOURCE_DATABASE}")

    def test_production_passes_full_validation(self):
        summary = cev.run_full_validation(SOURCE_DATABASE, verbose=False)
        self.assertEqual(summary["county_periods"], 3143)
        self.assertEqual(summary["observations"], 59717)
        self.assertEqual(summary["normalized_measures"], 9429)
        self.assertEqual(summary["dimension_scores"], 12572)
        self.assertEqual(summary["composite_scores"], 3143)
        self.assertEqual(summary["composite_complete"], 3143)
        self.assertEqual(summary["composite_incomplete"], 0)

    def test_production_database_is_byte_identical_after_validation(self):
        before = sha256(SOURCE_DATABASE)
        cev.run_full_validation(SOURCE_DATABASE, verbose=False)
        after = sha256(SOURCE_DATABASE)
        self.assertEqual(before, after)
        self.assertEqual(after, EXPECTED_PRODUCTION_SHA256)


class CountyExplorerTamperDetectionTest(unittest.TestCase):
    def setUp(self):
        if not SOURCE_DATABASE.exists():
            self.skipTest(f"Canonical database not found: {SOURCE_DATABASE}")
        self.directory = tempfile.TemporaryDirectory()
        self._counter = 0

    def tearDown(self):
        self.directory.cleanup()

    def _copy(self) -> Path:
        self._counter += 1
        path = Path(self.directory.name) / f"copy_{self._counter}.sqlite"
        shutil.copy2(SOURCE_DATABASE, path)
        return path

    def _apply(self, path: Path, statements: list[str]) -> None:
        connection = sqlite3.connect(path)
        try:
            connection.execute("PRAGMA foreign_keys = OFF")
            for statement in statements:
                connection.execute(statement)
            connection.commit()
        finally:
            connection.close()

    def _assert_rejected(self, path: Path):
        with self.assertRaises(cev.CountyExplorerValidationError):
            cev.run_full_validation(path, verbose=False)

    def test_unmodified_copy_still_passes(self):
        path = self._copy()
        summary = cev.run_full_validation(path, verbose=False)
        self.assertEqual(summary["composite_complete"], 3143)

    def test_detects_normalized_measure_drift_from_ce_a00(self):
        path = self._copy()
        self._apply(
            path,
            [
                """
                UPDATE normalized_measure
                SET normalized_value = normalized_value + 1e-6
                WHERE rowid = (
                    SELECT nm.rowid FROM normalized_measure nm
                    JOIN observation o ON o.observation_id = nm.observation_id
                    WHERE o.variable_id = 'PC_HPSA_GEOGRAPHIC_COVERAGE'
                    LIMIT 1
                )
                """
            ],
        )
        self._assert_rejected(path)

    def test_detects_dimension_score_not_identity_copy(self):
        path = self._copy()
        self._apply(
            path,
            [
                """
                UPDATE dimension_score
                SET score = score + 0.5
                WHERE dimension_id = 'PRIMARY_CARE'
                  AND county_period_id = (SELECT MIN(county_period_id) FROM dimension_score)
                """
            ],
        )
        self._assert_rejected(path)

    def test_detects_mua_p_dimension_not_equal_to_raw(self):
        path = self._copy()
        self._apply(
            path,
            [
                """
                UPDATE dimension_score
                SET score = score + 1.0
                WHERE dimension_id = 'MUA_P'
                  AND county_period_id = (SELECT MIN(county_period_id) FROM dimension_score)
                """
            ],
        )
        self._assert_rejected(path)

    def test_detects_mua_p_being_normalized(self):
        path = self._copy()
        self._apply(
            path,
            [
                # Keep the total row count at 9,429 so the MUA/P-specific check fires.
                """
                DELETE FROM normalized_measure
                WHERE rowid = (
                    SELECT nm.rowid FROM normalized_measure nm
                    JOIN observation o ON o.observation_id = nm.observation_id
                    WHERE o.variable_id = 'PC_HPSA_GEOGRAPHIC_COVERAGE'
                    LIMIT 1
                )
                """,
                """
                INSERT INTO normalized_measure (observation_id, methodology_version, normalized_value, normalization_method)
                SELECT o.observation_id, 'v0.1', 50.0, 'county_percentile_rank_average'
                FROM observation o
                WHERE o.variable_id = 'MUAP_GEOGRAPHIC_COVERAGE'
                LIMIT 1
                """,
            ],
        )
        self._assert_rejected(path)

    def test_detects_composite_not_equal_weight_mean(self):
        path = self._copy()
        self._apply(
            path,
            [
                """
                UPDATE composite_score
                SET composite_value = composite_value + 0.001
                WHERE county_period_id = (SELECT MIN(county_period_id) FROM composite_score)
                """
            ],
        )
        self._assert_rejected(path)

    def test_detects_dimension_score_row_loss(self):
        path = self._copy()
        self._apply(
            path,
            [
                """
                DELETE FROM dimension_score
                WHERE rowid = (SELECT rowid FROM dimension_score WHERE dimension_id = 'DENTAL' LIMIT 1)
                """
            ],
        )
        self._assert_rejected(path)

    def test_detects_observation_row_loss(self):
        path = self._copy()
        self._apply(
            path,
            [
                """
                DELETE FROM observation
                WHERE rowid = (SELECT rowid FROM observation WHERE variable_id = 'PC_HPSA_MAX_SCORE' LIMIT 1)
                """
            ],
        )
        self._assert_rejected(path)

    def test_detects_structure_break(self):
        path = self._copy()
        self._apply(
            path,
            ["DELETE FROM county_period WHERE county_period_id = (SELECT MAX(county_period_id) FROM county_period)"],
        )
        self._assert_rejected(path)

    def test_detects_metadata_drift(self):
        path = self._copy()
        self._apply(
            path,
            [
                """
                UPDATE normalized_measure
                SET normalization_method = 'something_else'
                WHERE rowid = (SELECT rowid FROM normalized_measure LIMIT 1)
                """
            ],
        )
        self._assert_rejected(path)

    def test_detects_duplicate_composite_row(self):
        path = self._copy()
        self._apply(
            path,
            [
                """
                INSERT INTO composite_score (county_period_id, methodology_version, composite_value, status, missing_dimensions)
                SELECT county_period_id, 'v0.1-dupe', composite_value, status, missing_dimensions
                FROM composite_score LIMIT 1
                """
            ],
        )
        # A second methodology_version row breaks the "exactly v0.1" / one-per-county expectations.
        self._assert_rejected(path)


class CountyExplorerIncompletePathTest(unittest.TestCase):
    def setUp(self):
        if not SOURCE_DATABASE.exists():
            self.skipTest(f"Canonical database not found: {SOURCE_DATABASE}")
        self.directory = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.directory.cleanup()

    def _incomplete_copy(self, dropped_dimension_variable: str) -> tuple[Path, int]:
        """Make a temp copy where one county-period is genuinely missing one
        primary observation, then regenerate the whole pipeline with the
        approved rebuilds so the gap propagates consistently."""

        path = Path(self.directory.name) / "incomplete.sqlite"
        shutil.copy2(SOURCE_DATABASE, path)

        connection = sqlite3.connect(path)
        try:
            county_period_id = connection.execute(
                "SELECT MIN(county_period_id) FROM county_period"
            ).fetchone()[0]
            connection.execute(
                """
                UPDATE observation
                SET raw_value = NULL
                WHERE county_period_id = ?
                  AND variable_id = ?
                """,
                (county_period_id, dropped_dimension_variable),
            )
            connection.commit()
        finally:
            connection.close()

        rebuild_normalized_measures(path)
        dimension_module.rebuild_dimension_scores(path)
        composite_module.rebuild_composite_scores(path)
        return path, county_period_id

    def test_consistent_incomplete_composite_passes_validation(self):
        path, county_period_id = self._incomplete_copy("DENTAL_HPSA_GEOGRAPHIC_COVERAGE")

        summary = cev.run_full_validation(path, verbose=False)
        self.assertEqual(summary["composite_incomplete"], 1)
        self.assertEqual(summary["composite_complete"], 3142)

        connection = sqlite3.connect(path)
        try:
            row = connection.execute(
                "SELECT composite_value, status, missing_dimensions FROM composite_score WHERE county_period_id = ?",
                (county_period_id,),
            ).fetchone()
        finally:
            connection.close()
        self.assertEqual(row, (None, "experimental_provisional_incomplete", "DENTAL"))

    def test_incomplete_composite_rejects_zero_substitution(self):
        path, county_period_id = self._incomplete_copy("DENTAL_HPSA_GEOGRAPHIC_COVERAGE")

        connection = sqlite3.connect(path)
        try:
            # Substitute a partial/zeroed average where the rule demands NULL.
            connection.execute(
                """
                UPDATE composite_score
                SET composite_value = (
                    SELECT SUM(COALESCE(score, 0)) / 4.0
                    FROM dimension_score
                    WHERE county_period_id = ? AND methodology_version = 'v0.1'
                ),
                    status = 'experimental_provisional'
                WHERE county_period_id = ?
                """,
                (county_period_id, county_period_id),
            )
            connection.commit()
        finally:
            connection.close()

        with self.assertRaises(cev.CountyExplorerValidationError):
            cev.run_full_validation(path, verbose=False)

    def test_incomplete_composite_rejects_wrong_missing_dimension_list(self):
        path, county_period_id = self._incomplete_copy("DENTAL_HPSA_GEOGRAPHIC_COVERAGE")

        connection = sqlite3.connect(path)
        try:
            connection.execute(
                "UPDATE composite_score SET missing_dimensions = 'MUA_P' WHERE county_period_id = ?",
                (county_period_id,),
            )
            connection.commit()
        finally:
            connection.close()

        with self.assertRaises(cev.CountyExplorerValidationError):
            cev.run_full_validation(path, verbose=False)


if __name__ == "__main__":
    unittest.main()
