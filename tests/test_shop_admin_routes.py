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


class ShopAdminRoutesTests(unittest.TestCase):
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

    def test_shop_admin_page_contains_expected_shell_and_api_wiring_markers(self):
        client = self._build_test_client()

        response = client.get("/shop_admin")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Shop Catalog Admin", response.text)
        self.assertIn('id="catalog-rows"', response.text)
        self.assertIn('id="status-banner"', response.text)
        self.assertIn('id="reload-button"', response.text)
        self.assertIn('id="add-row-button"', response.text)
        self.assertIn('id="validate-button"', response.text)
        self.assertIn('id="save-button"', response.text)
        self.assertIn('id="dirty-state"', response.text)
        self.assertIn('id="wealth-rows"', response.text)
        self.assertIn('id="wealth-summary-status"', response.text)
        self.assertIn('id="party-total-gp"', response.text)
        self.assertIn('id="party-total-sp"', response.text)
        self.assertIn('id="party-total-cp"', response.text)
        self.assertIn('id="party-total-cp-value"', response.text)
        self.assertIn('/assets/web/shop_admin/app.js', response.text)
        self.assertNotIn('API wiring:', response.text)

    def test_shop_admin_assets_are_served(self):
        client = self._build_test_client()

        js_response = client.get("/assets/web/shop_admin/app.js")
        css_response = client.get("/assets/web/shop_admin/styles.css")

        self.assertEqual(js_response.status_code, 200)
        self.assertEqual(css_response.status_code, 200)

    def test_shop_admin_frontend_includes_dirty_state_conflict_and_revision_wiring(self):
        client = self._build_test_client()

        js_response = client.get("/assets/web/shop_admin/app.js")

        self.assertEqual(js_response.status_code, 200)
        self.assertIn("window.addEventListener(\"beforeunload\", warnOnUnload)", js_response.text)
        self.assertIn("state.dirty ? \"Unsaved changes — save to publish\" : \"All changes saved\"", js_response.text)
        self.assertIn("expected_revision: state.revision || undefined", js_response.text)
        self.assertIn("error.status === 409", js_response.text)
        self.assertIn("Save blocked: catalog changed on host. Reload the latest catalog and retry.", js_response.text)


if __name__ == "__main__":
    unittest.main()
