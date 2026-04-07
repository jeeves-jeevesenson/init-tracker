import tempfile
import threading
import types
import unittest
from pathlib import Path
from unittest import mock

import pytest
import yaml

pytest.importorskip("httpx")

from fastapi.testclient import TestClient

import dnd_initative_tracker as tracker_mod


class _PlayerStateApiAppStub:
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

    def _get_shop_player_state_payload(self, _name):
        return {
            "player": {
                "name": "Alice",
                "currency": {"gp": 10, "sp": 0, "cp": 0},
                "inventory_summary": {"item_count": 1, "distinct_count": 1},
            }
        }


class ShopPlayerStateApiRouteTests(unittest.TestCase):
    def _build_lan_controller(self):
        lan = object.__new__(tracker_mod.LanController)
        lan._tracker = _PlayerStateApiAppStub()
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
        return TestClient(lan._fastapi_app), lan

    def test_shop_me_route_returns_narrow_player_state_payload(self):
        client, lan = self._build_test_client()
        expected = {
            "player": {
                "name": "Alice",
                "currency": {"gp": 33, "sp": 4, "cp": 5},
                "inventory_summary": {"item_count": 7, "distinct_count": 4},
            }
        }
        with mock.patch.object(lan, "_assigned_character_name_for_host", return_value="Alice"):
            with mock.patch.object(lan.app, "_get_shop_player_state_payload", return_value=expected) as payload_mock:
                response = client.get("/api/shop/me")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(expected, response.json())
        payload_mock.assert_called_once_with("Alice")

    def test_shop_me_route_returns_404_when_no_assigned_character(self):
        client, lan = self._build_test_client()
        with mock.patch.object(lan, "_assigned_character_name_for_host", return_value=None):
            response = client.get("/api/shop/me")

        self.assertEqual(response.status_code, 404)
        self.assertEqual("No assigned character.", response.json().get("detail"))

    def test_shop_player_route_returns_payload_for_named_player(self):
        client, lan = self._build_test_client()
        expected = {
            "player": {
                "name": "Alice",
                "currency": {"gp": 33, "sp": 4, "cp": 5},
                "inventory_summary": {"item_count": 7, "distinct_count": 4},
            }
        }
        with mock.patch.object(lan.app, "_get_shop_player_state_payload", return_value=expected) as payload_mock:
            response = client.get("/api/shop/players/Alice")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(expected, response.json())
        payload_mock.assert_called_once_with("Alice")

    def test_shop_player_route_returns_404_for_unknown_player(self):
        client, lan = self._build_test_client()
        with mock.patch.object(
            lan.app,
            "_get_shop_player_state_payload",
            side_effect=tracker_mod.CharacterApiError(status_code=404, detail="Character not found."),
        ):
            response = client.get("/api/shop/players/Unknown")

        self.assertEqual(response.status_code, 404)
        self.assertEqual("Character not found.", response.json().get("detail"))


class ShopPlayerStatePayloadTests(unittest.TestCase):
    def setUp(self):
        self.app = object.__new__(tracker_mod.InitiativeTracker)

    def _write_yaml(self, path: Path, payload):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    def test_shop_player_state_payload_shape_and_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            player_path = root / "players" / "alice.yaml"
            self._write_yaml(
                player_path,
                {
                    "name": "Alice",
                    "inventory": {
                        "currency": {"gp": 12, "sp": 3, "cp": 4},
                        "items": [
                            {"id": "healing_potion", "quantity": 2},
                            {"id": "longsword", "quantity": 1},
                            {"id": "longsword", "quantity": 1},
                            {"id": "", "quantity": 5},
                        ],
                    },
                },
            )
            self.app._resolve_character_path = lambda _name: player_path
            self.app._load_character_raw = lambda path: yaml.safe_load(path.read_text(encoding="utf-8"))
            self.app._character_merge_defaults = lambda payload: payload

            result = self.app._get_shop_player_state_payload("Alice")

            self.assertEqual("Alice", result["player"]["name"])
            self.assertEqual({"gp": 12, "sp": 3, "cp": 4}, result["player"]["currency"])
            self.assertEqual(9, result["player"]["inventory_summary"]["item_count"])
            self.assertEqual(2, result["player"]["inventory_summary"]["distinct_count"])

    def test_shop_player_state_payload_missing_character_raises_not_found(self):
        self.app._resolve_character_path = lambda _name: None

        with self.assertRaises(tracker_mod.CharacterApiError) as ctx:
            self.app._get_shop_player_state_payload("Unknown")

        self.assertEqual(404, ctx.exception.status_code)


if __name__ == "__main__":
    unittest.main()
