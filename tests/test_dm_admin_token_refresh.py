import pytest

pytest.importorskip("httpx")

import threading
import types
import unittest
from unittest import mock

from fastapi.testclient import TestClient

import dnd_initative_tracker as tracker_mod


class _AppStub:
    combatants = {}

    def _oplog(self, *_args, **_kwargs):
        return None

    def _lan_snapshot(self):
        return {"grid": None, "obstacles": [], "units": [], "active_cid": None, "round_num": 0}

    def _lan_pcs(self):
        return []

    def after(self, *_args, **_kwargs):
        return None


class DmAdminTokenRefreshTests(unittest.TestCase):
    def _build_lan_controller(self):
        lan = object.__new__(tracker_mod.LanController)
        lan._tracker = _AppStub()
        lan.cfg = types.SimpleNamespace(host="127.0.0.1", port=0, vapid_public_key=None, allowlist=[], denylist=[], admin_password=None)
        lan._server_thread = None
        lan._fastapi_app = None
        lan._polling = False
        lan._cached_snapshot = {}
        lan._cached_pcs = []
        lan._clients_lock = threading.RLock()
        lan._actions = None
        lan._best_lan_url = lambda: "http://127.0.0.1:0"
        lan._tick = lambda: None
        lan._append_lan_log = lambda *_args, **_kwargs: None
        lan._init_admin_auth = lambda: None
        lan._admin_password_hash = b"configured"
        lan._admin_password_salt = b"salt"
        lan._admin_tokens = {}
        lan._admin_token_ttl_seconds = 900
        lan._save_push_subscription = lambda *_args, **_kwargs: True
        lan._admin_password_matches = lambda password: password == "pw"
        return lan

    def _build_client(self):
        lan = self._build_lan_controller()
        with mock.patch("threading.Thread.start", return_value=None):
            lan.start(quiet=True)
        return TestClient(lan._fastapi_app)

    def test_admin_token_refresh_requires_active_admin_token(self):
        client = self._build_client()
        response = client.post("/api/admin/refresh")
        self.assertEqual(401, response.status_code)

    def test_admin_token_refresh_issues_new_token_and_expiry(self):
        client = self._build_client()
        login = client.post("/api/admin/login", json={"password": "pw"})
        self.assertEqual(200, login.status_code)
        old_token = login.json()["token"]

        refreshed = client.post("/api/admin/refresh", headers={"Authorization": f"Bearer {old_token}"})
        self.assertEqual(200, refreshed.status_code)
        refreshed_payload = refreshed.json()
        self.assertEqual(900, refreshed_payload["expires_in"])
        self.assertNotEqual(old_token, refreshed_payload["token"])

    def test_dm_console_html_contains_proactive_token_refresh_wiring(self):
        client = self._build_client()
        response = client.get("/dm")
        self.assertEqual(200, response.status_code)
        self.assertIn("/api/admin/refresh", response.text)
        self.assertIn("function setAdminToken(token, expiresInSeconds)", response.text)
        self.assertIn("adminTokenRefreshTimer = setTimeout(refreshAdminToken, refreshDelayMs);", response.text)
        self.assertIn("clearAdminAuthState('Session expired. Please log in again.')", response.text)


if __name__ == "__main__":
    unittest.main()
