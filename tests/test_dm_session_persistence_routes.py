"""Tests for the backend-owned DM session persistence routes.

These routes expose the existing `_save_session_to_path` /
`_load_session_from_path` / quick-save / quick-load machinery to the DM
web console so saves and loads can run from the browser without going
through Tk file dialogs. The route-behavior tests stand up a real
`LanController` with a minimal app stub backed by a temp saves
directory; the HTML-surface test reads `assets/web/dm/index.html`
directly so it remains runnable in minimal environments that do not
have fastapi/httpx available.
"""
import json
import tempfile
import threading
import types
import unittest
from pathlib import Path
from unittest import mock

try:
    import httpx  # noqa: F401  (required by fastapi.testclient)
    from fastapi.testclient import TestClient
    _HTTP_AVAILABLE = True
except Exception:
    TestClient = None  # type: ignore[assignment]
    _HTTP_AVAILABLE = False

import dnd_initative_tracker as tracker_mod

_DM_HTML_PATH = Path(__file__).resolve().parent.parent / "assets" / "web" / "dm" / "index.html"


class _SessionAppStub:
    """Minimal tracker stand-in exposing the helpers the persistence routes use."""

    def __init__(self, saves_dir: Path) -> None:
        self._saves_dir = saves_dir
        self.combatants = {}
        self.save_calls: list = []
        self.load_calls: list = []
        self.broadcast_calls = 0
        self.default_filename = "session_20260417_120000.json"
        # Snapshot helpers consumed by /api/dm/... routes outside the
        # persistence slice; present so other routes do not 500 if they
        # happen to run in the same client.
        self.snapshot = {"in_combat": False, "combatants": [], "battle_log": []}

    # ── Tracker helpers used by the new persistence routes ────────────
    def _session_saves_dir(self) -> Path:
        self._saves_dir.mkdir(parents=True, exist_ok=True)
        return self._saves_dir

    def _session_quicksave_path(self) -> Path:
        return self._session_saves_dir() / "quick_save.json"

    def _session_default_filename(self) -> str:
        return self.default_filename

    def _save_session_to_path(self, path: Path, label=None) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"schema_version": 2, "label": label, "combatants": []}
        path.write_text(json.dumps(payload), encoding="utf-8")
        self.save_calls.append({"path": str(path), "label": label})

    def _load_session_from_path(self, path: Path) -> None:
        data = json.loads(path.read_text(encoding="utf-8"))
        self.load_calls.append({"path": str(path), "payload": data})

    def _lan_force_state_broadcast(self) -> None:
        self.broadcast_calls += 1

    # ── Misc hooks other routes may touch if wired up ─────────────────
    def _oplog(self, *_args, **_kwargs):
        return None

    def _lan_snapshot(self):
        return {"grid": None, "obstacles": [], "units": [], "active_cid": None, "round_num": 0}

    def _lan_pcs(self):
        return []

    def after(self, *_args, **_kwargs):
        return None


@unittest.skipUnless(_HTTP_AVAILABLE, "fastapi/httpx not available in this environment")
class DmSessionPersistenceRoutesTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.saves_dir = Path(self._tmp.name) / "sessions"

    def _build_lan_controller(self, admin_password_configured: bool = False):
        lan = object.__new__(tracker_mod.LanController)
        lan._tracker = _SessionAppStub(self.saves_dir)
        lan.cfg = types.SimpleNamespace(
            host="127.0.0.1", port=0, vapid_public_key=None,
            allowlist=[], denylist=[], admin_password=None,
        )
        lan._server_thread = None
        lan._fastapi_app = None
        lan._polling = False
        lan._cached_snapshot = {}
        lan._cached_pcs = []
        lan._clients_lock = threading.RLock()
        lan._dm_ws_clients = {}
        lan._actions = None
        lan._loop = None
        lan._best_lan_url = lambda: "http://127.0.0.1:0"
        lan._tick = lambda: None
        lan._append_lan_log = lambda *_args, **_kwargs: None
        lan._init_admin_auth = lambda: None
        lan._admin_password_hash = b"configured" if admin_password_configured else None
        lan._admin_password_salt = b"salt"
        lan._admin_tokens = {}
        lan._admin_token_ttl_seconds = 900
        lan._save_push_subscription = lambda *_args, **_kwargs: True
        lan._admin_password_matches = lambda password: password == "pw"
        return lan

    def _build_client(self, admin_password_configured: bool = False):
        lan = self._build_lan_controller(admin_password_configured=admin_password_configured)
        with mock.patch("threading.Thread.start", return_value=None):
            lan.start(quiet=True)
        return TestClient(lan._fastapi_app), lan

    def _auth_headers(self, client, lan) -> dict:
        if not lan._admin_password_hash:
            return {}
        login = client.post("/api/admin/login", json={"password": "pw"})
        self.assertEqual(200, login.status_code)
        token = login.json()["token"]
        return {"Authorization": f"Bearer {token}"}

    # ── list snapshots ────────────────────────────────────────────────
    def test_list_sessions_empty_when_no_saves(self):
        client, lan = self._build_client()
        response = client.get("/api/dm/sessions")
        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(str(self.saves_dir), payload["saves_dir"])
        self.assertEqual(lan._tracker.default_filename, payload["default_filename"])
        self.assertEqual([], payload["snapshots"])
        self.assertFalse(payload["quick_save"]["exists"])
        self.assertEqual("quick_save.json", payload["quick_save"]["name"])

    def test_list_sessions_returns_sorted_entries_with_quick_save_flag(self):
        client, lan = self._build_client()
        # Pre-populate the saves dir with two real files + a quick save.
        self.saves_dir.mkdir(parents=True, exist_ok=True)
        older = self.saves_dir / "alpha.json"
        newer = self.saves_dir / "beta.json"
        quick = self.saves_dir / "quick_save.json"
        older.write_text("{}", encoding="utf-8")
        newer.write_text("{}", encoding="utf-8")
        quick.write_text("{}", encoding="utf-8")
        # Force modified order: alpha older than beta older than quick.
        import os
        os.utime(older, (1_000_000_000, 1_000_000_000))
        os.utime(newer, (1_000_000_500, 1_000_000_500))
        os.utime(quick, (1_000_001_000, 1_000_001_000))
        # Also drop a non-json file that should be filtered out.
        (self.saves_dir / "notes.txt").write_text("ignore", encoding="utf-8")

        response = client.get("/api/dm/sessions")
        self.assertEqual(200, response.status_code)
        payload = response.json()
        names = [entry["name"] for entry in payload["snapshots"]]
        self.assertEqual(["quick_save.json", "beta.json", "alpha.json"], names)
        qs_entry = next(e for e in payload["snapshots"] if e["name"] == "quick_save.json")
        self.assertTrue(qs_entry["is_quick_save"])
        self.assertFalse(next(e for e in payload["snapshots"] if e["name"] == "alpha.json")["is_quick_save"])
        self.assertTrue(payload["quick_save"]["exists"])

    def test_list_sessions_requires_admin_when_password_configured(self):
        client, lan = self._build_client(admin_password_configured=True)
        unauthenticated = client.get("/api/dm/sessions")
        self.assertEqual(401, unauthenticated.status_code)
        headers = self._auth_headers(client, lan)
        authenticated = client.get("/api/dm/sessions", headers=headers)
        self.assertEqual(200, authenticated.status_code)

    # ── save ──────────────────────────────────────────────────────────
    def test_save_session_with_default_filename(self):
        client, lan = self._build_client()
        response = client.post("/api/dm/sessions/save", json={})
        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(lan._tracker.default_filename, payload["name"])
        written = self.saves_dir / payload["name"]
        self.assertTrue(written.exists())
        self.assertEqual(1, len(lan._tracker.save_calls))
        self.assertEqual(str(written), lan._tracker.save_calls[0]["path"])
        self.assertIsNone(lan._tracker.save_calls[0]["label"])

    def test_save_session_with_explicit_filename_and_label(self):
        client, lan = self._build_client()
        response = client.post(
            "/api/dm/sessions/save",
            json={"filename": "boss_fight.json", "label": "pre-boss"},
        )
        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertEqual("boss_fight.json", payload["name"])
        self.assertEqual("pre-boss", lan._tracker.save_calls[-1]["label"])
        written = self.saves_dir / "boss_fight.json"
        self.assertTrue(written.exists())
        data = json.loads(written.read_text(encoding="utf-8"))
        self.assertEqual("pre-boss", data["label"])

    def test_save_session_rejects_path_traversal(self):
        client, lan = self._build_client()
        for bad in ["../escape.json", "nested/foo.json", "foo.json.bak", "no_ext", ".hidden.json"]:
            response = client.post("/api/dm/sessions/save", json={"filename": bad})
            self.assertEqual(400, response.status_code, f"expected 400 for {bad!r}, got {response.status_code}")
        self.assertEqual([], lan._tracker.save_calls)

    def test_save_session_requires_admin_when_password_configured(self):
        client, lan = self._build_client(admin_password_configured=True)
        unauthenticated = client.post("/api/dm/sessions/save", json={})
        self.assertEqual(401, unauthenticated.status_code)
        headers = self._auth_headers(client, lan)
        authenticated = client.post("/api/dm/sessions/save", json={}, headers=headers)
        self.assertEqual(200, authenticated.status_code)

    # ── load ──────────────────────────────────────────────────────────
    def test_load_session_reads_file_and_broadcasts(self):
        client, lan = self._build_client()
        # Write a fake session snapshot the stub will consume.
        self.saves_dir.mkdir(parents=True, exist_ok=True)
        sample = self.saves_dir / "boss_fight.json"
        sample.write_text(json.dumps({"schema_version": 2, "combatants": []}), encoding="utf-8")

        response = client.post("/api/dm/sessions/load", json={"filename": "boss_fight.json"})
        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual("boss_fight.json", payload["name"])
        self.assertEqual(1, len(lan._tracker.load_calls))
        self.assertEqual(str(sample), lan._tracker.load_calls[0]["path"])
        # After load, the LAN state broadcast helper should have fired.
        self.assertEqual(1, lan._tracker.broadcast_calls)

    def test_load_session_missing_file_returns_404(self):
        client, lan = self._build_client()
        response = client.post("/api/dm/sessions/load", json={"filename": "nope.json"})
        self.assertEqual(404, response.status_code)
        self.assertEqual([], lan._tracker.load_calls)

    def test_load_session_rejects_invalid_filename(self):
        client, lan = self._build_client()
        response = client.post("/api/dm/sessions/load", json={"filename": "../escape.json"})
        self.assertEqual(400, response.status_code)
        self.assertEqual([], lan._tracker.load_calls)

    def test_load_session_rejects_missing_filename(self):
        client, _lan = self._build_client()
        response = client.post("/api/dm/sessions/load", json={})
        self.assertEqual(400, response.status_code)

    def test_load_session_requires_admin_when_password_configured(self):
        client, lan = self._build_client(admin_password_configured=True)
        self.saves_dir.mkdir(parents=True, exist_ok=True)
        (self.saves_dir / "guarded.json").write_text("{}", encoding="utf-8")
        unauthenticated = client.post("/api/dm/sessions/load", json={"filename": "guarded.json"})
        self.assertEqual(401, unauthenticated.status_code)
        headers = self._auth_headers(client, lan)
        authenticated = client.post(
            "/api/dm/sessions/load", json={"filename": "guarded.json"}, headers=headers
        )
        self.assertEqual(200, authenticated.status_code)

    # ── quick save / quick load ───────────────────────────────────────
    def test_quick_save_writes_quick_save_json(self):
        client, lan = self._build_client()
        response = client.post("/api/dm/sessions/quick-save")
        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual("quick_save.json", payload["name"])
        quick = self.saves_dir / "quick_save.json"
        self.assertTrue(quick.exists())
        self.assertEqual(str(quick), lan._tracker.save_calls[-1]["path"])
        self.assertEqual("quick_save", lan._tracker.save_calls[-1]["label"])

    def test_quick_load_returns_404_when_no_quick_save(self):
        client, lan = self._build_client()
        response = client.post("/api/dm/sessions/quick-load")
        self.assertEqual(404, response.status_code)
        self.assertEqual([], lan._tracker.load_calls)

    def test_quick_load_invokes_tracker_load(self):
        client, lan = self._build_client()
        self.saves_dir.mkdir(parents=True, exist_ok=True)
        quick = self.saves_dir / "quick_save.json"
        quick.write_text(json.dumps({"schema_version": 2, "combatants": []}), encoding="utf-8")

        response = client.post("/api/dm/sessions/quick-load")
        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual("quick_save.json", payload["name"])
        self.assertEqual(1, len(lan._tracker.load_calls))
        self.assertEqual(str(quick), lan._tracker.load_calls[0]["path"])
        self.assertEqual(1, lan._tracker.broadcast_calls)

    def test_quick_routes_require_admin_when_password_configured(self):
        client, lan = self._build_client(admin_password_configured=True)
        self.assertEqual(401, client.post("/api/dm/sessions/quick-save").status_code)
        self.assertEqual(401, client.post("/api/dm/sessions/quick-load").status_code)
        headers = self._auth_headers(client, lan)
        self.assertEqual(200, client.post("/api/dm/sessions/quick-save", headers=headers).status_code)
        self.assertEqual(200, client.post("/api/dm/sessions/quick-load", headers=headers).status_code)


class DmSessionPersistenceHtmlTests(unittest.TestCase):
    """Validate that the DM console page exposes the new persistence controls.

    Kept separate from the route tests so this check can run in minimal
    environments without fastapi/httpx installed.
    """

    def test_dm_console_html_contains_session_persistence_controls(self):
        self.assertTrue(_DM_HTML_PATH.exists(), f"DM console page missing at {_DM_HTML_PATH}")
        html = _DM_HTML_PATH.read_text(encoding="utf-8")
        self.assertIn("Session Persistence", html)
        self.assertIn("quickSaveBtn", html)
        self.assertIn("quickLoadBtn", html)
        self.assertIn("sessionSaveBtn", html)
        self.assertIn("sessionLoadBtn", html)
        self.assertIn("sessionLoadSelect", html)
        self.assertIn("/api/dm/sessions", html)
        self.assertIn("/api/dm/sessions/save", html)
        self.assertIn("/api/dm/sessions/load", html)
        self.assertIn("/api/dm/sessions/quick-save", html)
        self.assertIn("/api/dm/sessions/quick-load", html)


if __name__ == "__main__":
    unittest.main()
