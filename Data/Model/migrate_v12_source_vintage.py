"""CE-E12B -- scoped, transactional ``source``-table migration.

Establishes authoritative source-vintage and reproducibility metadata on the
existing canonical database WITHOUT touching any analytical value:

* adds two nullable columns -- ``source.artifact_filename`` and
  ``source.content_sha256``;
* populates all four ``source`` rows with the HRSA Data Warehouse snapshot
  vintage (``reference_period`` / ``url`` / ``accessed_at``) and the exact
  ``Data/Processed`` build-input workbook (filename + SHA-256 of its bytes).

Authoritative catalogue and verification: ``Documentation/ANALYTICAL_DATA_SOURCES.md.txt``.

Why a scoped migration and not a full ``build_v01_database.py`` rebuild: no
script in this pipeline regenerates MUA/P's ``dimension_score`` rows (see the
``_replace_county_reference`` docstring in ``build_v01_database.py``), so a full
wipe/rebuild would silently discard otherwise-irreplaceable analytical data.

Safety: the migration captures an exact fingerprint of ``observation``,
``normalized_measure``, ``dimension_score``, and ``composite_score`` before the
change, applies the schema + ``source`` updates inside a single transaction,
re-computes the fingerprint, and refuses to commit unless it is byte-identical.
``PRAGMA foreign_key_check`` must also be clean. Any failure rolls the whole
change back.

Idempotent: re-running after a successful migration is a no-op.

Run once, locally, where ``Data/Processed`` is present:

    python Data/Model/migrate_v12_source_vintage.py
"""

from __future__ import annotations

from pathlib import Path
import hashlib
import sqlite3
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATABASE_PATH = PROJECT_ROOT / "Data" / "Model" / "chia_v01.sqlite"
PROCESSED_DIR = PROJECT_ROOT / "Data" / "Processed"

# --- Authoritative CE-E12B vintage metadata (see ANALYTICAL_DATA_SOURCES.md.txt)
REFERENCE_PERIOD = "HRSA Data Warehouse snapshot 2026-08-29"
URL = "https://data.hrsa.gov/data/download"
ACCESSED_AT = "2026-08-29"

# source_name -> (artifact_filename, expected content SHA-256)
SOURCES: dict[str, tuple[str, str]] = {
    "Primary Care HPSA": (
        "CHIA_Primary_Care_HPSA_Spatial_Coverage_Validated_FINAL.xlsx",
        "709e9ed6070f71e466b65b0928d1dbe23d3dd685ecfb81d4cb1cc0ee637c2d93",
    ),
    "Dental HPSA": (
        "CHIA_Dental_HPSA_Spatial_Coverage_Validated_FINAL.xlsx",
        "3334807f5cd7ecbd2002e2a672705dfd1a7f2a36df43d313db0b234332c61065",
    ),
    "Mental Health HPSA": (
        "CHIA_Mental_Health_HPSA_Spatial_Coverage_Validated_FINAL.xlsx",
        "72e6b52fa73247e6975ccb47bd09368bfc1f56f7a7f5ac14f95b8def67bb430b",
    ),
    "MUA/P": (
        "CHIA_MUA_P_Spatial_Coverage_Validated.xlsx",
        "7e8b0fd83bed93f0a8d1f0939b79e7302a96fa218775dd7d7b41597ab922f218",
    ),
}

NEW_COLUMNS = ("artifact_filename", "content_sha256")

# --- Pre-migration analytical fingerprint (captured from the ce-e12a database,
#     sha-256 0d8bb417...a2966). The migration must reproduce this exactly.
EXPECTED_PRE_MIGRATION_DB_SHA256 = (
    "0d8bb417ccf72acf0cef7d17bcca15627900d0df419fc259de553a95b9aa2966"
)
PRE_MIGRATION_ANALYTICAL = {
    "observation": {
        "count": 59717,
        "hash": "ebdc90c1207e11593712837160ca93dfb350a477a083331561f51d9fdc31b86c",
    },
    "normalized_measure": {
        "count": 9429,
        "hash": "11d8cb362ff63ee9833eaa8505be2704bdd304650052a3de4e58be66032da952",
    },
    "dimension_score": {
        "count": 12572,
        "hash": "798094bb6b6a1d81d87fe1f3d2eb0694f6bab44b7c2ea1cf70994ea3d24eed70",
    },
    "composite_score": {
        "count": 3143,
        "hash": "56b50546c687bd6545cd514468b2d1d740e8e1b63b2616ae199cb6da36e7f9b8",
    },
}

# Canonical row orderings for the analytical-table fingerprint.
_FINGERPRINT_QUERIES = {
    "observation": (
        "SELECT observation_id, county_period_id, variable_id, raw_value, "
        "raw_text, quality_flag, notes FROM observation ORDER BY observation_id"
    ),
    "normalized_measure": (
        "SELECT observation_id, methodology_version, normalized_value, "
        "normalization_method FROM normalized_measure "
        "ORDER BY observation_id, methodology_version"
    ),
    "dimension_score": (
        "SELECT county_period_id, dimension_id, score, methodology_version, "
        "status FROM dimension_score "
        "ORDER BY county_period_id, dimension_id, methodology_version"
    ),
    "composite_score": (
        "SELECT county_period_id, methodology_version, composite_value, status, "
        "missing_dimensions FROM composite_score "
        "ORDER BY county_period_id, methodology_version"
    ),
}


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def analytical_fingerprint(connection: sqlite3.Connection) -> dict[str, dict[str, object]]:
    """Return ``{table: {'count': int, 'hash': hex}}`` for the four analytical
    tables, over a fixed row ordering. Any change to a persisted analytical
    value, or a row added/removed, changes the hash.
    """

    fingerprint: dict[str, dict[str, object]] = {}
    for table, query in _FINGERPRINT_QUERIES.items():
        digest = hashlib.sha256()
        count = 0
        for row in connection.execute(query):
            digest.update(repr(row).encode())
            digest.update(b"\x1e")
            count += 1
        fingerprint[table] = {"count": count, "hash": digest.hexdigest()}
    return fingerprint


def _column_names(connection: sqlite3.Connection, table: str) -> list[str]:
    return [row[1] for row in connection.execute(f"PRAGMA table_info({table})")]


def already_migrated(connection: sqlite3.Connection) -> bool:
    columns = _column_names(connection, "source")
    if not all(column in columns for column in NEW_COLUMNS):
        return False
    unpopulated = connection.execute(
        """
        SELECT COUNT(*) FROM source
        WHERE reference_period IS NULL OR url IS NULL OR accessed_at IS NULL
           OR artifact_filename IS NULL OR content_sha256 IS NULL
        """
    ).fetchone()[0]
    return unpopulated == 0


def _resolve_artifact_hashes() -> dict[str, tuple[str, str]]:
    """source_name -> (artifact_filename, sha256-from-disk). Raises if any file
    is missing or its bytes do not match the documented SHA-256.
    """

    resolved: dict[str, tuple[str, str]] = {}
    for source_name, (filename, expected_sha) in SOURCES.items():
        path = PROCESSED_DIR / filename
        if not path.exists():
            raise FileNotFoundError(
                f"Required build-input artifact not found: {path}\n"
                "Run this migration where Data/Processed is present."
            )
        actual_sha = file_sha256(path)
        if actual_sha != expected_sha:
            raise ValueError(
                f"{filename}: on-disk SHA-256 {actual_sha} does not match the "
                f"documented value {expected_sha} "
                "(Documentation/ANALYTICAL_DATA_SOURCES.md.txt)."
            )
        resolved[source_name] = (filename, actual_sha)
    return resolved


def migrate(database_path: Path = DATABASE_PATH) -> str:
    """Apply the CE-E12B source-vintage migration. Returns the post-migration
    database SHA-256. Idempotent.
    """

    if not database_path.exists():
        raise FileNotFoundError(f"Database not found: {database_path}")

    before_db_sha = file_sha256(database_path)

    connection = sqlite3.connect(database_path)
    try:
        connection.execute("PRAGMA foreign_keys = ON")

        if already_migrated(connection):
            print("Already migrated -- no change.")
            print(f"Database SHA-256: {before_db_sha}")
            return before_db_sha

        if before_db_sha != EXPECTED_PRE_MIGRATION_DB_SHA256:
            raise RuntimeError(
                "Unexpected pre-migration database state.\n"
                f"  expected SHA-256 {EXPECTED_PRE_MIGRATION_DB_SHA256}\n"
                f"  actual   SHA-256 {before_db_sha}\n"
                "This migration only applies to the ce-e12a canonical database."
            )

        artifacts = _resolve_artifact_hashes()

        before = analytical_fingerprint(connection)
        _require_fingerprint(before, PRE_MIGRATION_ANALYTICAL, "pre-migration")

        connection.execute("BEGIN IMMEDIATE")
        try:
            for column in NEW_COLUMNS:
                connection.execute(f"ALTER TABLE source ADD COLUMN {column} TEXT")

            for source_name, (filename, sha) in artifacts.items():
                cursor = connection.execute(
                    """
                    UPDATE source
                    SET reference_period = ?, url = ?, accessed_at = ?,
                        artifact_filename = ?, content_sha256 = ?
                    WHERE source_name = ?
                    """,
                    (REFERENCE_PERIOD, URL, ACCESSED_AT, filename, sha, source_name),
                )
                if cursor.rowcount != 1:
                    raise RuntimeError(
                        f"UPDATE matched {cursor.rowcount} rows for source "
                        f"{source_name!r}; expected exactly 1."
                    )

            after = analytical_fingerprint(connection)
            if after != before:
                raise RuntimeError(
                    "Analytical fingerprint changed during migration -- aborting.\n"
                    f"  before: {before}\n  after:  {after}"
                )

            fk_errors = connection.execute("PRAGMA foreign_key_check").fetchall()
            if fk_errors:
                raise RuntimeError(f"foreign_key_check failed: {fk_errors}")

            source_count = connection.execute("SELECT COUNT(*) FROM source").fetchone()[0]
            if source_count != 4:
                raise RuntimeError(f"source row count is {source_count}; expected 4.")
            if not already_migrated(connection):
                raise RuntimeError("source rows not fully populated after UPDATE.")

            connection.commit()
        except Exception:
            connection.rollback()
            raise
    finally:
        connection.close()

    after_db_sha = file_sha256(database_path)

    # Post-commit read-only re-check.
    ro = sqlite3.connect(f"{database_path.resolve().as_uri()}?mode=ro", uri=True)
    try:
        _require_fingerprint(
            analytical_fingerprint(ro), PRE_MIGRATION_ANALYTICAL, "post-migration"
        )
    finally:
        ro.close()

    md5 = hashlib.md5(database_path.read_bytes()).hexdigest()
    print("=" * 70)
    print("CE-E12B SOURCE-VINTAGE MIGRATION COMPLETE")
    print("=" * 70)
    print(f"Database:            {database_path}")
    print(f"SQLite library:      {sqlite3.sqlite_version}")
    print(f"Before SHA-256:      {before_db_sha}")
    print(f"After  SHA-256:      {after_db_sha}")
    print(f"After  MD5:          {md5}")
    print("Analytical tables:   byte-identical (observation / normalized_measure /")
    print("                     dimension_score / composite_score fingerprints match)")
    print("=" * 70)
    return after_db_sha


def _require_fingerprint(actual: dict, expected: dict, label: str) -> None:
    for table, want in expected.items():
        got = actual.get(table)
        if got != want:
            raise RuntimeError(
                f"{label} fingerprint mismatch for {table!r}:\n"
                f"  expected {want}\n  actual   {got}"
            )


def main() -> int:
    try:
        migrate()
    except Exception as exc:  # noqa: BLE001 -- surface the reason and fail loudly
        print(f"MIGRATION FAILED: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
