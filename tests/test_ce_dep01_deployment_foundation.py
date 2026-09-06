"""CE-DEP01 tests for the backend deployment foundation.

Covers, without touching analytical code, schema, seed, source data, or the
existing API contracts:

* the canonical database is present and unignored so a repo clone (i.e. a
  Render build) has it, with its content still matching the anchored SHA-256;
* opt-in, narrowly scoped CORS driven purely by ``CHIA_ALLOWED_ORIGINS`` --
  and proof that the default (unset) behaviour is unchanged;
* ``CHIA_DATABASE_PATH`` overrides the database location without code changes;
* the minimal ``/health`` liveness endpoint;
* the Render blueprint / Python pin are present and internally consistent.

unittest-based, matching the existing CE-A/CE-B/CE-E suites.
"""

from __future__ import annotations

import hashlib
import importlib
import os
from pathlib import Path
import shutil
import subprocess
import unittest

from fastapi.testclient import TestClient

import app.config
import app.main


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CANONICAL_DATABASE = PROJECT_ROOT / "Data" / "Model" / "chia_v01.sqlite"
EXPECTED_PRODUCTION_SHA256 = (
    "12b3525e77cdc85ba7fedbb463fcc75f21c489825c0e81d98cdf71a2b7c7174c"
)
PAGES_ORIGIN = "https://ksprinkle.github.io"


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class _ReloadedAppMixin(unittest.TestCase):
    """Rebuild ``app.config`` / ``app.main`` under a chosen environment.

    Other test modules bind ``app`` at import time (``from app.main import
    app``), so reloading the module here cannot disturb them; ``tearDown``
    still restores the canonical, CORS-free module state.
    """

    _CONTROLLED_KEYS = ("CHIA_ALLOWED_ORIGINS", "CHIA_DATABASE_PATH")

    def _reload_with_env(self, **env: str):
        saved = {key: os.environ.get(key) for key in self._CONTROLLED_KEYS}
        try:
            for key in self._CONTROLLED_KEYS:
                os.environ.pop(key, None)
            for key, value in env.items():
                os.environ[key] = value
            importlib.reload(app.config)
            importlib.reload(app.main)
        finally:
            for key, value in saved.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
        return app.main

    def tearDown(self):
        for key in self._CONTROLLED_KEYS:
            os.environ.pop(key, None)
        importlib.reload(app.config)
        importlib.reload(app.main)


class AllowedOriginParsingTest(unittest.TestCase):
    def test_none_and_empty_yield_no_origins(self):
        self.assertEqual(app.config.parse_allowed_origins(None), [])
        self.assertEqual(app.config.parse_allowed_origins(""), [])
        self.assertEqual(app.config.parse_allowed_origins("   "), [])
        self.assertEqual(app.config.parse_allowed_origins(" , ,"), [])

    def test_single_origin(self):
        self.assertEqual(
            app.config.parse_allowed_origins(PAGES_ORIGIN), [PAGES_ORIGIN]
        )

    def test_comma_separated_list_is_trimmed(self):
        self.assertEqual(
            app.config.parse_allowed_origins(
                f" {PAGES_ORIGIN} , http://localhost:5173 "
            ),
            [PAGES_ORIGIN, "http://localhost:5173"],
        )


class HealthEndpointTest(unittest.TestCase):
    def test_health_returns_ok_without_touching_the_database(self):
        before = file_sha256(CANONICAL_DATABASE)
        with TestClient(app.main.app) as client:
            response = client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        self.assertEqual(file_sha256(CANONICAL_DATABASE), before)


class DefaultCorsBehaviourTest(_ReloadedAppMixin):
    def test_no_cors_headers_emitted_when_unconfigured(self):
        module = self._reload_with_env()  # CHIA_ALLOWED_ORIGINS unset
        self.assertEqual(app.config.ALLOWED_ORIGINS, [])
        with TestClient(module.app) as client:
            response = client.get("/health", headers={"Origin": PAGES_ORIGIN})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("access-control-allow-origin", response.headers)

    def test_no_cors_middleware_object_is_installed_when_unconfigured(self):
        module = self._reload_with_env()
        installed = [m.cls.__name__ for m in module.app.user_middleware]
        self.assertNotIn("CORSMiddleware", installed)


class ConfiguredCorsBehaviourTest(_ReloadedAppMixin):
    def test_allowed_origin_receives_cors_header(self):
        module = self._reload_with_env(CHIA_ALLOWED_ORIGINS=PAGES_ORIGIN)
        with TestClient(module.app) as client:
            response = client.get("/health", headers={"Origin": PAGES_ORIGIN})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers.get("access-control-allow-origin"), PAGES_ORIGIN
        )
        # Credentials are never allowed.
        self.assertNotEqual(
            response.headers.get("access-control-allow-credentials"), "true"
        )

    def test_unlisted_origin_receives_no_cors_header(self):
        module = self._reload_with_env(CHIA_ALLOWED_ORIGINS=PAGES_ORIGIN)
        with TestClient(module.app) as client:
            response = client.get(
                "/health", headers={"Origin": "https://evil.example"}
            )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("access-control-allow-origin", response.headers)

    def test_preflight_advertises_get_only(self):
        module = self._reload_with_env(CHIA_ALLOWED_ORIGINS=PAGES_ORIGIN)
        with TestClient(module.app) as client:
            response = client.options(
                "/api/v1/counties",
                headers={
                    "Origin": PAGES_ORIGIN,
                    "Access-Control-Request-Method": "GET",
                },
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers.get("access-control-allow-origin"), PAGES_ORIGIN
        )
        allow_methods = response.headers.get("access-control-allow-methods", "")
        self.assertIn("GET", allow_methods)
        self.assertNotIn("POST", allow_methods)
        self.assertNotIn("PUT", allow_methods)
        self.assertNotIn("DELETE", allow_methods)

    def test_multiple_origins_are_each_honoured(self):
        module = self._reload_with_env(
            CHIA_ALLOWED_ORIGINS=f"{PAGES_ORIGIN}, http://localhost:5173"
        )
        with TestClient(module.app) as client:
            for origin in (PAGES_ORIGIN, "http://localhost:5173"):
                response = client.get("/health", headers={"Origin": origin})
                self.assertEqual(
                    response.headers.get("access-control-allow-origin"), origin
                )


class DatabasePathOverrideTest(_ReloadedAppMixin):
    def test_default_path_is_the_canonical_database(self):
        self._reload_with_env()  # neither override env var set
        self.assertEqual(app.config.DATABASE_PATH, CANONICAL_DATABASE)

    def test_env_var_overrides_the_database_path(self):
        override = str(PROJECT_ROOT / "some" / "other" / "place.sqlite")
        self._reload_with_env(CHIA_DATABASE_PATH=override)
        self.assertEqual(app.config.DATABASE_PATH, Path(override))


class CanonicalDatabaseAvailabilityTest(unittest.TestCase):
    def test_canonical_database_exists_with_anchored_hash(self):
        self.assertTrue(
            CANONICAL_DATABASE.exists(),
            f"canonical database missing: {CANONICAL_DATABASE}",
        )
        self.assertEqual(
            file_sha256(CANONICAL_DATABASE), EXPECTED_PRODUCTION_SHA256
        )

    def test_canonical_database_is_not_git_ignored(self):
        git = shutil.which("git")
        if git is None:
            self.skipTest("git not available")
        result = subprocess.run(
            [git, "check-ignore", "-q", str(CANONICAL_DATABASE)],
            cwd=PROJECT_ROOT,
            capture_output=True,
        )
        # exit code 1 => path is NOT ignored (what we require); 0 => ignored.
        self.assertEqual(
            result.returncode,
            1,
            "Data/Model/chia_v01.sqlite is still git-ignored; the deployed "
            "backend would not receive it.",
        )


class RenderBlueprintTest(unittest.TestCase):
    def test_runtime_pin_matches_local_interpreter(self):
        runtime = (PROJECT_ROOT / "runtime.txt").read_text(encoding="utf-8").strip()
        self.assertEqual(runtime, "python-3.11.9")

    def test_render_yaml_declares_the_expected_service(self):
        blueprint = (PROJECT_ROOT / "render.yaml").read_text(encoding="utf-8")
        self.assertIn("startCommand: uvicorn app.main:app --host 0.0.0.0 --port $PORT", blueprint)
        self.assertIn("buildCommand: pip install -r requirements.txt", blueprint)
        self.assertIn("healthCheckPath: /health", blueprint)
        self.assertIn("CHIA_ALLOWED_ORIGINS", blueprint)


if __name__ == "__main__":
    unittest.main()
