"""CE-E12B -- source-vintage metadata migration: reproducibility guarantees.

These tests run against the migrated canonical database
(``Data/Model/chia_v01.sqlite``) and prove that CE-E12B:

* established complete, authoritative source-vintage / provenance metadata on
  every ``source`` row;
* recorded the exact build-input artifact (filename + SHA-256) and that the
  recorded hash matches both the on-disk file and the authoritative
  documentation;
* changed **no** analytical value -- ``observation``, ``normalized_measure``,
  ``dimension_score``, and ``composite_score`` are byte-identical to the
  pre-migration (ce-e12a) database, captured in
  ``Data.Model.migrate_v12_source_vintage.PRE_MIGRATION_ANALYTICAL``;
* left ``county_period.period`` and ``methodology.methodology_version`` at
  ``v0.1``;
* keeps every existing v0.1 analytical validator green;
* is idempotent.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
import sqlite3
import subprocess
import sys
import unittest

from fastapi.testclient import TestClient

from app.main import app
import Data.Model.migrate_v12_source_vintage as mig


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DATABASE = PROJECT_ROOT / "Data" / "Model" / "chia_v01.sqlite"
PROCESSED_DIR = PROJECT_ROOT / "Data" / "Processed"
ANALYTICAL_DATA_SOURCES_DOC = (
    PROJECT_ROOT / "Documentation" / "ANALYTICAL_DATA_SOURCES.md.txt"
)

# New canonical database identity after the CE-E12B migration
# (SQLite library 3.45.1). Also the value re-based into the six backend
# EXPECTED_PRODUCTION_SHA256 anchors.
NEW_CANONICAL_SHA256 = (
    "12b3525e77cdc85ba7fedbb463fcc75f21c489825c0e81d98cdf71a2b7c7174c"
)
NEW_CANONICAL_MD5 = "1ff3f2731c96d7dcab4491b8ac53765d"

REQUIRED_SOURCE_FIELDS = (
    "reference_period",
    "url",
    "accessed_at",
    "artifact_filename",
    "content_sha256",
)

V01_VALIDATORS = (
    "validate_v01_database.py",
    "validate_v01_normalization.py",
    "validate_v01_dimension_scores.py",
    "validate_v01_composite.py",
    "validate_v01_county_explorer.py",
)


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def file_md5(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


class SourceVintageMigrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not SOURCE_DATABASE.exists():
            raise unittest.SkipTest(f"Canonical database not found: {SOURCE_DATABASE}")
        cls.connection = sqlite3.connect(
            f"{SOURCE_DATABASE.resolve().as_uri()}?mode=ro", uri=True
        )
        cls.source_rows = {
            row["source_name"]: row
            for row in cls._dict_rows(
                cls.connection,
                "SELECT source_id, source_name, publisher, dataset_name, "
                "reference_period, url, accessed_at, artifact_filename, "
                "content_sha256 FROM source ORDER BY source_id",
            )
        }

    @classmethod
    def tearDownClass(cls):
        cls.connection.close()

    @staticmethod
    def _dict_rows(connection: sqlite3.Connection, query: str) -> list[dict]:
        cursor = connection.execute(query)
        columns = [c[0] for c in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    # --- database identity ------------------------------------------------

    def test_database_is_the_new_canonical_hash(self):
        self.assertEqual(file_sha256(SOURCE_DATABASE), NEW_CANONICAL_SHA256)
        self.assertEqual(file_md5(SOURCE_DATABASE), NEW_CANONICAL_MD5)

    def test_new_hash_is_re_based_into_every_backend_anchor(self):
        anchors = (
            "test_ce_a06_county_explorer_validation.py",
            "test_ce_b01_county_api.py",
            "test_ce_b02_county_explorer.py",
            "test_ce_d01_concurrent_connection.py",
            "test_ce_d01_county_reference_correction.py",
            "test_ce_e09_state_dimension_scores.py",
        )
        for name in anchors:
            text = (PROJECT_ROOT / "tests" / name).read_text(encoding="utf-8")
            self.assertIn(NEW_CANONICAL_SHA256, text, name)
            self.assertNotIn(
                "0d8bb417ccf72acf0cef7d17bcca15627900d0df419fc259de553a95b9aa2966",
                text,
                f"{name} still carries the pre-CE-E12B hash",
            )

    # --- source-vintage metadata completeness ---------------------------

    def test_exactly_four_source_rows(self):
        self.assertEqual(len(self.source_rows), 4)
        self.assertEqual(
            sorted(self.source_rows),
            ["Dental HPSA", "MUA/P", "Mental Health HPSA", "Primary Care HPSA"],
        )

    def test_every_source_has_complete_vintage_and_provenance_metadata(self):
        for name, row in self.source_rows.items():
            for field in REQUIRED_SOURCE_FIELDS:
                value = row[field]
                self.assertIsNotNone(value, f"{name}.{field} is NULL")
                self.assertNotEqual(str(value).strip(), "", f"{name}.{field} is blank")

    def test_reference_period_url_accessed_at_are_the_authoritative_values(self):
        for name, row in self.source_rows.items():
            self.assertEqual(row["reference_period"], mig.REFERENCE_PERIOD, name)
            self.assertEqual(row["url"], mig.URL, name)
            self.assertEqual(row["accessed_at"], mig.ACCESSED_AT, name)

    def test_source_name_to_artifact_mapping_matches_migration_config(self):
        actual = {
            name: (row["artifact_filename"], row["content_sha256"])
            for name, row in self.source_rows.items()
        }
        self.assertEqual(actual, mig.SOURCES)

    def test_content_sha256_matches_on_disk_artifact(self):
        for name, row in self.source_rows.items():
            artifact = PROCESSED_DIR / row["artifact_filename"]
            if not artifact.exists():
                self.skipTest(f"gitignored build-input artifact absent: {artifact}")
            self.assertEqual(
                file_sha256(artifact),
                row["content_sha256"],
                f"{name}: recorded content_sha256 != on-disk {artifact.name}",
            )

    def test_metadata_matches_authoritative_documentation(self):
        if not ANALYTICAL_DATA_SOURCES_DOC.exists():
            self.skipTest("ANALYTICAL_DATA_SOURCES.md.txt not found")
        doc = ANALYTICAL_DATA_SOURCES_DOC.read_text(encoding="utf-8")
        self.assertIn(mig.REFERENCE_PERIOD, doc)
        for name, row in self.source_rows.items():
            self.assertIn(row["artifact_filename"], doc, f"{name} filename not documented")
            self.assertIn(row["content_sha256"], doc, f"{name} sha-256 not documented")

    # --- analytical invariance (before/after equality) -----------------

    def test_analytical_values_unchanged_since_ce_e12a(self):
        after = mig.analytical_fingerprint(self.connection)
        for table, expected in mig.PRE_MIGRATION_ANALYTICAL.items():
            self.assertEqual(
                after[table],
                expected,
                f"{table}: analytical fingerprint changed by CE-E12B",
            )

    def test_period_and_methodology_still_v01(self):
        periods = [
            r[0] for r in self.connection.execute(
                "SELECT DISTINCT period FROM county_period"
            )
        ]
        self.assertEqual(periods, ["v0.1"])
        versions = [
            r[0] for r in self.connection.execute(
                "SELECT methodology_version FROM methodology ORDER BY methodology_version"
            )
        ]
        self.assertEqual(versions, ["v0.1"])

    # --- validators + API + idempotency -------------------------------

    def test_all_v01_analytical_validators_pass(self):
        for script in V01_VALIDATORS:
            result = subprocess.run(
                [sys.executable, str(PROJECT_ROOT / "Data" / "Model" / script)],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                result.returncode,
                0,
                f"{script} failed:\n{result.stdout}\n{result.stderr}",
            )

    def test_api_exposes_new_source_vintage_metadata(self):
        with TestClient(app) as client:
            response = client.get("/api/v1/counties/01001/explorer")
        self.assertEqual(response.status_code, 200)
        sources = {s["source_name"]: s for s in response.json()["provenance"]["sources"]}
        self.assertEqual(len(sources), 4)
        for name, source in sources.items():
            self.assertEqual(source["reference_period"], mig.REFERENCE_PERIOD, name)
            self.assertEqual(source["url"], mig.URL, name)
            self.assertEqual(source["accessed_at"], mig.ACCESSED_AT, name)
            expected_filename, expected_sha = mig.SOURCES[name]
            self.assertEqual(source["artifact_filename"], expected_filename, name)
            self.assertEqual(source["content_sha256"], expected_sha, name)

    def test_read_only_digest_unchanged_after_api_reads(self):
        before = file_sha256(SOURCE_DATABASE)
        with TestClient(app) as client:
            client.get("/api/v1/counties/01001/explorer")
            client.get("/api/v1/counties/10001/explorer")
        self.assertEqual(file_sha256(SOURCE_DATABASE), before)
        self.assertEqual(before, NEW_CANONICAL_SHA256)

    def test_migration_is_idempotent(self):
        before = file_sha256(SOURCE_DATABASE)
        returned = mig.migrate(SOURCE_DATABASE)
        self.assertEqual(returned, NEW_CANONICAL_SHA256)
        self.assertEqual(file_sha256(SOURCE_DATABASE), before)


if __name__ == "__main__":
    unittest.main()
