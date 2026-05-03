import os
import threading
import types
import unittest
from unittest import mock

try:
    import httpx  # noqa: F401
except ImportError as exc:  # pragma: no cover - environment guard
    raise unittest.SkipTest("httpx not installed") from exc

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
    def _build_lan_controller(self, admin_password_configured: bool = True):
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
        lan._admin_password_hash = b"configured" if admin_password_configured else None
        lan._admin_password_salt = b"salt" if admin_password_configured else None
        lan._admin_tokens = {}
        lan._admin_token_ttl_seconds = 900
        lan._save_push_subscription = lambda *_args, **_kwargs: True
        lan._admin_password_matches = lambda password: password == "pw"
        return lan

    def _build_client(self, admin_password_configured: bool = True):
        lan = self._build_lan_controller(admin_password_configured=admin_password_configured)
        with mock.patch("threading.Thread.start", return_value=None):
            lan.start(quiet=True)
        return TestClient(lan._fastapi_app)

    def _build_client_with_lan(self, admin_password_configured: bool = True):
        lan = self._build_lan_controller(admin_password_configured=admin_password_configured)
        with mock.patch("threading.Thread.start", return_value=None):
            lan.start(quiet=True)
        return TestClient(lan._fastapi_app), lan

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

    def test_admin_token_refresh_rejects_expired_token(self):
        client, lan = self._build_client_with_lan()
        login = client.post("/api/admin/login", json={"password": "pw"})
        self.assertEqual(200, login.status_code)
        token = login.json()["token"]
        lan._admin_tokens[token] = 0

        refreshed = client.post("/api/admin/refresh", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(401, refreshed.status_code)

    def test_dm_console_html_contains_proactive_token_refresh_wiring(self):
        client = self._build_client()
        response = client.get("/dm")
        self.assertEqual(200, response.status_code)
        self.assertIn('data-dm-auth-required="true"', response.text)
        self.assertIn('id="authOverlay" class=""', response.text)
        self.assertIn("/api/admin/refresh", response.text)
        self.assertIn("const DM_AUTH_REQUIRED = document.body.dataset.dmAuthRequired === 'true';", response.text)
        self.assertIn("function setAdminToken(token, expiresInSeconds)", response.text)
        self.assertIn("const ADMIN_REFRESH_MAX_RETRY_ATTEMPTS = 2;", response.text)
        self.assertIn("const ADMIN_REFRESH_REASON_TOKEN_EXPIRED = 'token_expired';", response.text)
        self.assertIn("const ADMIN_REFRESH_REASON_REQUEST_FAILED = 'request_failed';", response.text)
        self.assertIn("const ADMIN_REFRESH_REASON_BACKEND_REJECTED = 'backend_rejected';", response.text)
        self.assertIn("const ADMIN_REFRESH_REASON_RETRY_EXHAUSTED = 'retry_exhausted';", response.text)
        self.assertIn("scheduleAdminTokenRefresh(refreshDelayMs);", response.text)
        self.assertIn("clearAdminAuthState(ADMIN_REAUTH_REQUIRED_MESSAGE);", response.text)
        self.assertIn("await tryAutoLogin();", response.text)

    def test_dm_console_html_hides_auth_overlay_and_bootstraps_when_passwordless(self):
        client = self._build_client(admin_password_configured=False)
        response = client.get("/dm")
        self.assertEqual(200, response.status_code)
        self.assertIn('data-dm-auth-required="false"', response.text)
        self.assertIn('id="authOverlay" class="hidden"', response.text)
        self.assertIn("async function bootstrapPasswordlessDmConsole()", response.text)
        self.assertIn("overlay.classList.add('hidden');", response.text)
        self.assertIn("await fetchSnapshot();", response.text)
        self.assertIn("if (overlay.classList.contains('hidden')) startAutoRefresh();", response.text)
        self.assertIn("await bootstrapPasswordlessDmConsole();", response.text)

    def test_passwordless_admin_login_rejects_configured_password_flow(self):
        client = self._build_client(admin_password_configured=False)
        response = client.post("/api/admin/login", json={"password": "pw"})
        self.assertEqual(403, response.status_code)

    def test_password_protected_dm_combat_requires_valid_admin_token(self):
        client = self._build_client()
        unauthenticated = client.get("/api/dm/combat")
        invalid = client.get("/api/dm/combat", headers={"Authorization": "Bearer nope"})
        self.assertEqual(401, unauthenticated.status_code)
        self.assertEqual(401, invalid.status_code)


class LanConfigAdminPasswordTests(unittest.TestCase):
    def test_empty_env_admin_password_is_treated_as_unconfigured(self):
        with mock.patch.dict(os.environ, {"INITTRACKER_ADMIN_PASSWORD": ""}, clear=True):
            cfg = tracker_mod.LanConfig()
        self.assertIsNone(cfg.admin_password)


if __name__ == "__main__":
    unittest.main()
