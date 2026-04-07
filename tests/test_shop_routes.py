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


class ShopRoutesTests(unittest.TestCase):
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

    def test_shop_page_contains_expected_shell_markers_and_asset_path(self):
        client = self._build_test_client()

        response = client.get("/shop")

        self.assertEqual(response.status_code, 200)
        self.assertIn('id="shop-status"', response.text)
        self.assertIn('id="player-name"', response.text)
        self.assertIn('id="player-currency"', response.text)
        self.assertIn('id="catalog-list"', response.text)
        self.assertIn('/assets/web/shop/app.js', response.text)
        self.assertIn('/api/shop/me', response.text)
        self.assertNotIn('/api/characters/by_ip', response.text)

    def test_shop_assets_are_served(self):
        client = self._build_test_client()

        js_response = client.get("/assets/web/shop/app.js")
        css_response = client.get("/assets/web/shop/styles.css")

        self.assertEqual(js_response.status_code, 200)
        self.assertEqual(css_response.status_code, 200)

    def test_shop_frontend_is_wired_to_catalog_and_purchase_api_endpoints(self):
        client = self._build_test_client()

        js_response = client.get("/assets/web/shop/app.js")

        self.assertEqual(js_response.status_code, 200)
        self.assertIn('/api/shop/catalog', js_response.text)
        self.assertIn('/api/shop/me', js_response.text)
        self.assertIn('/api/shop/players/', js_response.text)
        self.assertIn('/purchase', js_response.text)
        self.assertNotIn('/api/characters/by_ip', js_response.text)

    def test_shop_frontend_has_assignment_gap_and_purchase_conflict_messages(self):
        client = self._build_test_client()

        js_response = client.get("/assets/web/shop/app.js")

        self.assertEqual(js_response.status_code, 200)
        self.assertIn("error.status === 404", js_response.text)
        self.assertIn("includes(\"assigned character\")", js_response.text)
        self.assertIn("No player is assigned to this device/IP yet. Ask the DM to assign a character, then refresh.", js_response.text)
        self.assertIn("error.status === 409", js_response.text)
        self.assertIn("currency may be outdated; refresh and retry", js_response.text)


if __name__ == "__main__":
    unittest.main()
