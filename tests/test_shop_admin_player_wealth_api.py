import threading
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

import pytest
import yaml

pytest.importorskip("httpx")

from fastapi.testclient import TestClient

import dnd_initative_tracker as tracker_mod


class _WealthApiAppStub:
    combatants = {}

    def _oplog(self, *_args, **_kwargs):
        return None

    def _lan_snapshot(self):
        return {"grid": None, "obstacles": [], "units": [], "active_cid": None, "round_num": 0}

    def _lan_pcs(self):
        return []

    def after(self, *_args, **_kwargs):
        return None

    def _get_shop_admin_player_wealth_payload(self):
        return {
            "players": [
                {"name": "Alice", "currency": {"gp": 10, "sp": 5, "cp": 0}, "total_cp": 1050},
                {"name": "Bob", "currency": {"gp": 3, "sp": 0, "cp": 7}, "total_cp": 307},
            ],
            "party_total_cp": 1357,
            "party_total_currency": {"gp": 13, "sp": 5, "cp": 7},
        }


class ShopAdminPlayerWealthApiTests(unittest.TestCase):
    def _build_lan_controller(self):
        lan = object.__new__(tracker_mod.LanController)
        lan._tracker = _WealthApiAppStub()
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

    def test_player_wealth_route_returns_normalized_payload(self):
        lan = self._build_lan_controller()
        with mock.patch("threading.Thread.start", return_value=None):
            lan.start(quiet=True)
        client = TestClient(lan._fastapi_app)

        response = client.get("/api/shop/admin/player-wealth")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(2, len(payload.get("players") or []))
        self.assertEqual(1357, payload.get("party_total_cp"))
        self.assertEqual({"gp": 13, "sp": 5, "cp": 7}, payload.get("party_total_currency"))

    def test_helper_reads_player_yaml_currency(self):
        app = object.__new__(tracker_mod.InitiativeTracker)
        app._oplog = lambda *_args, **_kwargs: None

        with tempfile.TemporaryDirectory() as tmp:
            players_dir = Path(tmp) / "players"
            players_dir.mkdir(parents=True, exist_ok=True)
            (players_dir / "alice.yaml").write_text(yaml.safe_dump({"name": "Alice", "inventory": {"currency": {"gp": 2, "sp": 5, "cp": 1}}}, sort_keys=False), encoding="utf-8")
            (players_dir / "bob.yaml").write_text(yaml.safe_dump({"name": "Bob", "inventory": {"currency": {"gp": 1}}}, sort_keys=False), encoding="utf-8")
            app._players_dir = lambda: players_dir
            app._list_character_filenames = lambda: ["alice.yaml", "bob.yaml"]

            payload = app._get_shop_admin_player_wealth_payload()

        self.assertEqual(2, len(payload["players"]))
        self.assertEqual(351, payload["party_total_cp"])


if __name__ == "__main__":
    unittest.main()
