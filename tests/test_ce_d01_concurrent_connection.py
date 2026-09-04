"""CE-D01 regression: concurrent read-only requests must not raise
``sqlite3.ProgrammingError`` from a cross-thread connection close.

Reproduces, via genuine concurrent ASGI requests (no fixture stub, no real
network -- the same dependency-resolution/threadpool code path a real
``uvicorn`` server uses), the exact failure a real browser produced during
CE-D01's manual end-to-end acceptance pass: a fresh county-page load fires
two near-simultaneous requests to ``GET /counties/{fips}/explorer`` (React
18 StrictMode's development-mode double-effect invocation is one common
trigger; ordinary concurrent traffic is another). Under a *synchronous*
FastAPI generator dependency, ``sqlite3.Connection`` (thread-affine by
default) can be opened on one Starlette/AnyIO worker thread and closed on
another, raising::

    sqlite3.ProgrammingError: SQLite objects created in a thread can only be
    used in that same thread.

which the API surfaces as an HTTP 503. Every other test in this suite issues
requests sequentially (one at a time), which is exactly why none of them
caught this -- the race only exists under real concurrency.

This test exercises the real, unmodified production dependencies
(``app.db.get_readonly_connection`` / ``app.api.v1.explorer.
get_explorer_connection``) against the real canonical database, the same
combination CE-D01's real-browser pass used. It intentionally does not
override the dependency: the whole point is to test the actual production
connection lifecycle under load.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Iterable
import hashlib
from pathlib import Path
import unittest

import httpx

from app.main import app


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DATABASE = PROJECT_ROOT / "Data" / "Model" / "chia_v01.sqlite"
EXPECTED_PRODUCTION_SHA256 = (
    "0d8bb417ccf72acf0cef7d17bcca15627900d0df419fc259de553a95b9aa2966"
)

# AnyIO's default worker-thread-pool capacity is 40 tokens; requesting more
# than that forces thread reuse across in-flight requests, which is exactly
# the condition that produces a cross-thread open/close pairing pre-fix.
CONCURRENT_REQUESTS = 60
KNOWN_FIPS = "01001"


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


async def _fire_concurrent(path: str, count: int) -> list[httpx.Response]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        requests: Iterable[Awaitable[httpx.Response]] = (
            client.get(path) for _ in range(count)
        )
        return await asyncio.gather(*requests)


class ConcurrentExplorerRequestTest(unittest.TestCase):
    """Guarded production integration test (skipped if the canonical database
    is not present), matching the pattern already used by
    ``CountyExplorerProductionTest`` in ``test_ce_b02_county_explorer.py``.
    """

    def setUp(self):
        if not SOURCE_DATABASE.exists():
            self.skipTest(f"Canonical database not found: {SOURCE_DATABASE}")

    def test_concurrent_explorer_requests_succeed_without_thread_errors(self):
        before = file_sha256(SOURCE_DATABASE)

        responses = asyncio.run(
            _fire_concurrent(
                f"/api/v1/counties/{KNOWN_FIPS}/explorer", CONCURRENT_REQUESTS
            )
        )

        after = file_sha256(SOURCE_DATABASE)

        statuses = [response.status_code for response in responses]
        self.assertEqual(
            statuses,
            [200] * CONCURRENT_REQUESTS,
            "Expected every concurrent request to return 200; a 503 here "
            "reproduces sqlite3.ProgrammingError: SQLite objects created in "
            "a thread can only be used in that same thread (see "
            "app.db.get_readonly_connection's docstring).",
        )

        # Every response must be the identical, fully-assembled payload -- not
        # merely a 200 that happens to carry a truncated/partial body.
        first_body = responses[0].json()
        for response in responses[1:]:
            self.assertEqual(response.json(), first_body)

        # Read-only: the canonical database must be byte-for-byte unchanged.
        self.assertEqual(before, after)
        self.assertEqual(after, EXPECTED_PRODUCTION_SHA256)

    def test_concurrent_county_list_requests_succeed_without_thread_errors(self):
        before = file_sha256(SOURCE_DATABASE)

        responses = asyncio.run(
            _fire_concurrent("/api/v1/counties", CONCURRENT_REQUESTS)
        )

        after = file_sha256(SOURCE_DATABASE)

        statuses = [response.status_code for response in responses]
        self.assertEqual(statuses, [200] * CONCURRENT_REQUESTS)

        first_count = responses[0].json()["count"]
        for response in responses[1:]:
            self.assertEqual(response.json()["count"], first_count)

        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
