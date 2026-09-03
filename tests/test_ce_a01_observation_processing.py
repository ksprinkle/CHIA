"""CE-A01 tests for read-only canonical observation processing."""

from __future__ import annotations

import hashlib
from pathlib import Path
import sqlite3
import unittest

from app.services.observation_processing import (
    ObservationStructureError,
    load_canonical_observation_universe,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = PROJECT_ROOT / "Data" / "Model" / "chia_v01.sqlite"
PERIOD = "v0.1"
PRIMARY_VARIABLES = [
    "PC_HPSA_GEOGRAPHIC_COVERAGE",
    "DENTAL_HPSA_GEOGRAPHIC_COVERAGE",
    "MH_HPSA_GEOGRAPHIC_COVERAGE",
    "MUAP_GEOGRAPHIC_COVERAGE",
]


def create_test_database() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.executescript(
        """
        CREATE TABLE county (
            county_fips TEXT NOT NULL,
            county_name TEXT NOT NULL
        );
        CREATE TABLE county_period (
            county_period_id INTEGER NOT NULL,
            county_fips TEXT NOT NULL,
            period TEXT NOT NULL
        );
        CREATE TABLE observation (
            observation_id INTEGER NOT NULL,
            county_period_id INTEGER NOT NULL,
            variable_id TEXT NOT NULL,
            raw_value REAL,
            quality_flag TEXT
        );
        """
    )
    return connection


def normalized_measure_digest(connection: sqlite3.Connection) -> tuple[int, str]:
    digest = hashlib.sha256()
    rows = connection.execute(
        """
        SELECT observation_id, methodology_version, normalized_value,
               normalization_method
        FROM normalized_measure
        ORDER BY observation_id, methodology_version
        """
    )
    count = 0
    for row in rows:
        digest.update(repr(row).encode("utf-8"))
        count += 1
    return count, digest.hexdigest()


class ObservationProcessingUnitTest(unittest.TestCase):
    def setUp(self):
        self.connection = create_test_database()
        self.connection.executemany(
            "INSERT INTO county VALUES (?, ?)",
            [("01003", "Baldwin"), ("01001", "Autauga"), ("01005", "Barbour")],
        )
        self.connection.executemany(
            "INSERT INTO county_period VALUES (?, ?, ?)",
            [(3, "01003", PERIOD), (1, "01001", PERIOD), (5, "01005", PERIOD)],
        )
        self.connection.executemany(
            "INSERT INTO observation VALUES (?, ?, ?, ?, ?)",
            [
                (1, 1, "TEST", None, "missing_source_value"),
                (3, 3, "TEST", 0.0, "source_validated"),
            ],
        )
        self.connection.commit()

    def tearDown(self):
        self.connection.close()

    def test_complete_universe_preserves_missing_zero_and_quality_flags(self):
        records = load_canonical_observation_universe(
            self.connection, "TEST", PERIOD
        )

        self.assertEqual([record.county_fips for record in records], ["01001", "01003", "01005"])
        self.assertIsNone(records[0].raw_value)
        self.assertEqual(records[0].quality_flag, "missing_source_value")
        self.assertEqual(records[1].raw_value, 0.0)
        self.assertEqual(records[1].quality_flag, "source_validated")
        self.assertIsNone(records[2].raw_value)
        self.assertIsNone(records[2].quality_flag)

    def test_loader_does_not_mutate_a_supplied_connection(self):
        changes_before = self.connection.total_changes
        load_canonical_observation_universe(self.connection, "TEST", PERIOD)
        self.assertEqual(self.connection.total_changes, changes_before)

    def test_duplicate_observations_are_rejected(self):
        self.connection.execute(
            "INSERT INTO observation VALUES (?, ?, ?, ?, ?)",
            (2, 1, "TEST", 5.0, "source_validated"),
        )

        with self.assertRaisesRegex(ObservationStructureError, "Duplicate observations"):
            load_canonical_observation_universe(self.connection, "TEST", PERIOD)


class ObservationProcessingIntegrationTest(unittest.TestCase):
    def test_primary_variables_match_canonical_database_and_do_not_mutate_it(self):
        connection = sqlite3.connect(DATABASE_PATH)
        try:
            normalized_before = normalized_measure_digest(connection)

            for variable_id in PRIMARY_VARIABLES:
                records = load_canonical_observation_universe(
                    connection, variable_id, PERIOD
                )
                self.assertEqual(len(records), 3143)
                self.assertEqual(
                    [record.county_fips for record in records],
                    sorted(record.county_fips for record in records),
                )
                self.assertTrue(
                    all(
                        len(record.county_fips) == 5
                        and record.county_fips.isdigit()
                        for record in records
                    )
                )

                expected_rows = connection.execute(
                    """
                    SELECT cp.county_period_id, c.county_fips,
                           o.raw_value, o.quality_flag
                    FROM county_period AS cp
                    JOIN county AS c
                      ON c.county_fips = cp.county_fips
                    LEFT JOIN observation AS o
                      ON o.county_period_id = cp.county_period_id
                     AND o.variable_id = ?
                    WHERE cp.period = ?
                    ORDER BY c.county_fips
                    """,
                    (variable_id, PERIOD),
                ).fetchall()
                actual_rows = [
                    (
                        record.county_period_id,
                        record.county_fips,
                        record.raw_value,
                        record.quality_flag,
                    )
                    for record in records
                ]
                self.assertEqual(actual_rows, expected_rows)

            self.assertEqual(normalized_measure_digest(connection), normalized_before)
        finally:
            connection.close()


if __name__ == "__main__":
    unittest.main()
