import threading
import types
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

import pytest
import yaml

pytest.importorskip("httpx")
from fastapi.testclient import TestClient

import dnd_initative_tracker as tracker_mod


class _MutationAppStub:
    def __init__(self, tracker):
        self._tracker = tracker

    def _oplog(self, *_args, **_kwargs):
        return None

    def _lan_snapshot(self):
        return {"grid": None, "obstacles": [], "units": [], "active_cid": None, "round_num": 0}

    def _lan_pcs(self):
        return []

    def after(self, *_args, **_kwargs):
        return None

    def _character_schema_config(self):
        return tracker_mod._CHARACTER_SCHEMA_CONFIG or {}

    def _character_schema_readme_map(self):
        return tracker_mod._CHARACTER_SCHEMA_README_MAP or {}

    def _list_character_filenames(self):
        return ["hero.yaml"]

    def _get_character_payload(self, _name):
        return {"filename": "hero.yaml", "character": {}}

    def _create_character_payload(self, _payload):
        return {"filename": "hero.yaml", "character": {}}

    def _update_character_payload(self, _name, _payload):
        return {"filename": "hero.yaml", "character": {}}

    def _overwrite_character_payload(self, _name, _payload):
        return {"filename": "hero.yaml", "character": {}}

    def _upload_character_yaml_payload(self, _payload):
        return {"filename": "hero.yaml", "character": {}}

    def _mutate_owned_magic_item_state(self, name, instance_id, operation):
        return self._tracker._mutate_owned_magic_item_state(name, instance_id, operation)

    def _mutate_owned_inventory_item_equipped_state(self, name, instance_id, operation):
        return self._tracker._mutate_owned_inventory_item_equipped_state(name, instance_id, operation)


class InventoryEquippableMutationApiTests(unittest.TestCase):
    def _build_tracker(self, temp_player_path: Path):
        tracker = object.__new__(tracker_mod.InitiativeTracker)
        tracker._player_yaml_lock = threading.RLock()
        tracker._player_yaml_cache_by_path = {}
        tracker._player_yaml_meta_by_path = {}
        tracker._player_yaml_data_by_name = {}
        tracker._player_yaml_name_map = {}
        tracker._schedule_player_yaml_refresh = lambda: None
        tracker._normalize_player_profile = lambda raw, _name: raw
        tracker._load_player_yaml_cache = lambda: None
        tracker._find_player_profile_path = lambda _name: temp_player_path
        tracker._magic_items_registry_payload = lambda: {
            "wand_of_fireballs": {
                "id": "wand_of_fireballs",
                "name": "Wand of Fireballs",
                "requires_attunement": True,
            }
        }
        tracker._items_registry_payload = lambda: {
            "armors": {
                "leather": {"id": "leather", "name": "Leather Armor", "category": "armor"},
                "plate_armor": {"id": "plate_armor", "name": "Plate Armor", "category": "armor"},
                "shield": {"id": "shield", "name": "Shield", "category": "shield"},
            },
            "weapons": {
                "dagger": {"id": "dagger", "name": "Dagger", "category": "melee_weapon"},
            },
        }
        tracker._oplog = lambda *_args, **_kwargs: None
        return tracker

    def _build_client(self, tracker):
        lan = object.__new__(tracker_mod.LanController)
        lan._tracker = _MutationAppStub(tracker)
        lan.cfg = types.SimpleNamespace(host="127.0.0.1", port=0, vapid_public_key=None)
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
        with mock.patch("threading.Thread.start", return_value=None):
            lan.start(quiet=True)
        return TestClient(lan._fastapi_app)

    def test_equip_and_unequip_non_magic_item_by_instance_id(self):
        with TemporaryDirectory() as tmpdir:
            player_path = Path(tmpdir) / "hero.yaml"
            payload = {
                "name": "Hero",
                "inventory": {
                    "items": [
                        {"id": "leather", "instance_id": "armor_1", "equipped": False, "state": {"foo": "bar"}},
                    ]
                },
            }
            player_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
            client = self._build_client(self._build_tracker(player_path))

            equip = client.post("/api/characters/Hero/inventory/items/armor_1/equip_non_magic")
            self.assertEqual(equip.status_code, 200)
            self.assertTrue(equip.json().get("equipped"))

            unequip = client.post("/api/characters/Hero/inventory/items/armor_1/unequip_non_magic")
            self.assertEqual(unequip.status_code, 200)
            self.assertFalse(unequip.json().get("equipped"))

            saved = yaml.safe_load(player_path.read_text(encoding="utf-8"))
            self.assertFalse(saved["inventory"]["items"][0].get("equipped"))
            self.assertEqual(saved["inventory"]["items"][0].get("state", {}).get("foo"), "bar")

    def test_equip_armor_unequips_other_armor_and_shield_unequips_other_shield(self):
        with TemporaryDirectory() as tmpdir:
            player_path = Path(tmpdir) / "hero.yaml"
            payload = {
                "name": "Hero",
                "inventory": {
                    "items": [
                        {"id": "leather", "instance_id": "armor_1", "equipped": True},
                        {"id": "plate_armor", "instance_id": "armor_2", "equipped": False},
                        {"id": "shield", "instance_id": "shield_1", "equipped": True},
                        {"id": "shield", "instance_id": "shield_2", "equipped": False},
                    ]
                },
            }
            player_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
            client = self._build_client(self._build_tracker(player_path))

            armor = client.post("/api/characters/Hero/inventory/items/armor_2/equip_non_magic")
            self.assertEqual(armor.status_code, 200)
            shield = client.post("/api/characters/Hero/inventory/items/shield_2/equip_non_magic")
            self.assertEqual(shield.status_code, 200)

            saved = yaml.safe_load(player_path.read_text(encoding="utf-8"))
            by_instance = {item["instance_id"]: item for item in saved["inventory"]["items"]}
            self.assertFalse(by_instance["armor_1"].get("equipped"))
            self.assertTrue(by_instance["armor_2"].get("equipped"))
            self.assertFalse(by_instance["shield_1"].get("equipped"))
            self.assertTrue(by_instance["shield_2"].get("equipped"))

    def test_equip_shield_success(self):
        with TemporaryDirectory() as tmpdir:
            player_path = Path(tmpdir) / "hero.yaml"
            payload = {
                "name": "Hero",
                "inventory": {"items": [{"id": "shield", "instance_id": "shield_1", "equipped": False}]},
            }
            player_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
            client = self._build_client(self._build_tracker(player_path))

            response = client.post("/api/characters/Hero/inventory/items/shield_1/equip_non_magic")
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.json().get("equipped"))

    def test_guardrails_unknown_instance_non_equippable_and_magic(self):
        with TemporaryDirectory() as tmpdir:
            player_path = Path(tmpdir) / "hero.yaml"
            payload = {
                "name": "Hero",
                "inventory": {
                    "items": [
                        {"id": "rope", "instance_id": "rope_1", "equipped": False},
                        {"id": "wand_of_fireballs", "instance_id": "wand_1", "equipped": False},
                    ]
                },
            }
            player_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
            client = self._build_client(self._build_tracker(player_path))

            missing = client.post("/api/characters/Hero/inventory/items/missing/equip_non_magic")
            self.assertEqual(missing.status_code, 404)

            unresolved = client.post("/api/characters/Hero/inventory/items/rope_1/equip_non_magic")
            self.assertEqual(unresolved.status_code, 400)

            magic = client.post("/api/characters/Hero/inventory/items/wand_1/equip_non_magic")
            self.assertEqual(magic.status_code, 400)


if __name__ == "__main__":
    unittest.main()
