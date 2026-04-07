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

    def _load_shop_catalog_normalized(self):
        return []


class ShopPlayerResolutionUiTests(unittest.TestCase):
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
        lan._admin_password_hash = None
        lan._admin_token_ttl_seconds = 900
        lan._save_push_subscription = lambda *_args, **_kwargs: True
        lan._admin_password_matches = lambda *_args, **_kwargs: False
        lan._issue_admin_token = lambda: "token"
        return lan

    def _build_test_client(self):
        lan = self._build_lan_controller()
        with mock.patch("threading.Thread.start", return_value=None):
            lan.start(quiet=True)
        return TestClient(lan._fastapi_app)

    def test_shop_html_contains_fallback_player_picker_shell(self):
        client = self._build_test_client()

        response = client.get("/shop")

        self.assertEqual(response.status_code, 200)
        self.assertIn('id="player-picker-shell"', response.text)
        self.assertIn('id="player-picker-select"', response.text)
        self.assertIn('id="player-picker-load-button"', response.text)
        self.assertIn("No assigned player was detected. Select who you are to continue.", response.text)

    def test_shop_js_contains_auto_and_manual_resolution_paths(self):
        client = self._build_test_client()

        response = client.get("/assets/web/shop/app.js")

        self.assertEqual(response.status_code, 200)
        self.assertIn('/api/shop/me', response.text)
        self.assertIn('/api/shop/players/${encodeURIComponent(name)}', response.text)
        self.assertIn('/api/characters', response.text)
        self.assertIn('setPlayerPickerVisible(true);', response.text)
        self.assertIn('playerPickerLoadButtonEl.addEventListener("click"', response.text)


if __name__ == "__main__":
    unittest.main()
