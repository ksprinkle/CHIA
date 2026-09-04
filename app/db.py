"""Read-only database access for the CHIA County Explorer API.

The API never writes to the canonical data model. This module mirrors the
read-only SQLite URI pattern already used by
``app/services/observation_processing.py`` -- no ORM, no session, no pool.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
import sqlite3

from app.config import DATABASE_PATH


def open_readonly_connection(
    database_path: str | Path = DATABASE_PATH,
) -> sqlite3.Connection:
    """Open the canonical database in SQLite read-only URI mode (``mode=ro``).

    ``check_same_thread=False`` (CE-D01): a FastAPI *synchronous* generator
    dependency is invoked through two independent ``run_in_threadpool``
    calls -- one for the code before ``yield`` (open), one for the
    ``finally`` block (close) -- and AnyIO's worker thread pool does not
    guarantee the same OS thread services both. Under concurrent requests
    the close call can land on a different thread than the open call, and
    Python's default ``check_same_thread=True`` then raises
    ``sqlite3.ProgrammingError: SQLite objects created in a thread can only
    be used in that same thread.`` on ``connection.close()``.

    This is safe to disable here because:

    1. ``sqlite3.threadsafety == 3`` in this environment (verified via
       ``python -c "import sqlite3; print(sqlite3.threadsafety)"``), i.e.
       the linked SQLite library was compiled with ``SQLITE_THREADSAFE=1``
       (confirmed via ``PRAGMA compile_options``) -- SQLite's "serialized"
       mode, which its own documentation states is safe for a single
       connection to be used by multiple threads, including literally
       concurrently, because SQLite serializes access internally.
    2. Even so, this codebase never shares a connection across *concurrent*
       operations: ``open_readonly_connection`` is called fresh for every
       request, and each connection is opened, queried, and closed strictly
       sequentially within that one request's lifecycle (never touched by
       two threads at the same instant) -- a materially weaker requirement
       than what SQLite's serialized mode already guarantees. Only the
       *identity* of the OS thread performing each sequential phase can
       change; two phases are never in flight at once.
    3. No Python-level, non-thread-safe SQLite feature is used anywhere in
       this codebase (no ``create_function``, no ``set_trace_callback``, no
       shared cursors across requests) that would introduce a hazard beyond
       what the C library's serialized mode already covers.

    See ``tests/test_ce_d01_concurrent_connection.py`` for the regression
    test that reproduces the pre-fix failure under genuine concurrency and
    verifies this fix.
    """

    database_uri = Path(database_path).resolve().as_uri() + "?mode=ro"
    return sqlite3.connect(database_uri, uri=True, check_same_thread=False)


def get_readonly_connection() -> Iterator[sqlite3.Connection]:
    """FastAPI dependency: yield a request-scoped read-only connection."""

    connection = open_readonly_connection()
    try:
        yield connection
    finally:
        connection.close()
