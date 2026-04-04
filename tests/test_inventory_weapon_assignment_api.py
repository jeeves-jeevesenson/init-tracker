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

    def _mutate_owned_inventory_weapon_assignment(self, name, instance_id, operation, payload=None):
        return self._tracker._mutate_owned_inventory_weapon_assignment(name, instance_id, operation, payload=payload)


class InventoryWeaponAssignmentApiTests(unittest.TestCase):
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
            "hellfire_battleaxe_plus_2": {
                "id": "hellfire_battleaxe_plus_2",
                "name": "Hellfire Battleaxe (+2)",
                "category": "martial_melee",
                "properties": ["versatile"],
                "requires_attunement": True,
            },
            "ring_of_greater_invisibility": {
                "id": "ring_of_greater_invisibility",
                "name": "Ring of Greater Invisibility",
                "category": "ring",
                "requires_attunement": True,
            },
        }
        tracker._items_registry_payload = lambda: {
            "armors": {
                "leather": {"id": "leather", "name": "Leather Armor", "category": "armor"},
                "shield": {"id": "shield", "name": "Shield", "category": "shield"},
            },
            "weapons": {
                "longsword": {
                    "id": "longsword",
                    "name": "Longsword",
                    "category": "martial_melee",
                    "properties": ["versatile"],
                    "damage": {"one_handed": {"formula": "1d8"}, "versatile": {"formula": "1d10"}},
                },
                "dagger": {
                    "id": "dagger",
                    "name": "Dagger",
                    "category": "simple_melee",
                    "properties": ["light", "finesse"],
                    "damage": {"one_handed": {"formula": "1d4"}},
                },
                "greatsword": {
                    "id": "greatsword",
                    "name": "Greatsword",
                    "category": "martial_melee",
                    "properties": ["heavy", "two_handed"],
                    "damage": {"two_handed": {"formula": "2d6"}},
                },
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

    def test_mainhand_offhand_and_two_handed_rules(self):
        with TemporaryDirectory() as tmpdir:
            player_path = Path(tmpdir) / "hero.yaml"
            player_path.write_text(
                yaml.safe_dump(
                    {
                        "name": "Hero",
                        "inventory": {
                            "items": [
                                {"id": "longsword", "instance_id": "longsword_1", "equipped": False},
                                {"id": "dagger", "instance_id": "dagger_1", "equipped": False},
                                {"id": "dagger", "instance_id": "dagger_2", "equipped": False},
                            ]
                        },
                    },
                    sort_keys=False,
                ),
                encoding="utf-8",
            )
            client = self._build_client(self._build_tracker(player_path))

            mh = client.post("/api/characters/Hero/inventory/items/longsword_1/equip_weapon_mainhand")
            self.assertEqual(mh.status_code, 200)
            self.assertEqual(mh.json().get("equipped_slot"), "main_hand")

            off1 = client.post("/api/characters/Hero/inventory/items/dagger_1/equip_weapon_offhand")
            self.assertEqual(off1.status_code, 200)
            off2 = client.post("/api/characters/Hero/inventory/items/dagger_2/equip_weapon_offhand")
            self.assertEqual(off2.status_code, 200)

            two = client.post(
                "/api/characters/Hero/inventory/items/longsword_1/equip_weapon_mainhand",
                json={"mode": "two"},
            )
            self.assertEqual(two.status_code, 200)
            self.assertEqual(two.json().get("selected_mode"), "two")

            saved = yaml.safe_load(player_path.read_text(encoding="utf-8"))
            by_instance = {item["instance_id"]: item for item in saved["inventory"]["items"]}
            self.assertEqual(by_instance["longsword_1"].get("equipped_slot"), "main_hand")
            self.assertEqual(by_instance["longsword_1"].get("selected_mode"), "two")
            self.assertFalse(by_instance["dagger_1"].get("equipped_slot"))
            self.assertFalse(by_instance["dagger_2"].get("equipped_slot"))

    def test_mainhand_exclusivity_and_unknown_instance(self):
        with TemporaryDirectory() as tmpdir:
            player_path = Path(tmpdir) / "hero.yaml"
            player_path.write_text(
                yaml.safe_dump(
                    {
                        "name": "Hero",
                        "inventory": {
                            "items": [
                                {"id": "longsword", "instance_id": "longsword_1", "equipped": True, "equipped_slot": "main_hand"},
                                {"id": "dagger", "instance_id": "dagger_1", "equipped": False},
                            ]
                        },
                    },
                    sort_keys=False,
                ),
                encoding="utf-8",
            )
            client = self._build_client(self._build_tracker(player_path))

            move = client.post("/api/characters/Hero/inventory/items/dagger_1/equip_weapon_mainhand")
            self.assertEqual(move.status_code, 200)
            missing = client.post("/api/characters/Hero/inventory/items/missing/equip_weapon_mainhand")
            self.assertEqual(missing.status_code, 404)

            saved = yaml.safe_load(player_path.read_text(encoding="utf-8"))
            by_instance = {item["instance_id"]: item for item in saved["inventory"]["items"]}
            self.assertFalse(by_instance["longsword_1"].get("equipped_slot"))
            self.assertEqual(by_instance["dagger_1"].get("equipped_slot"), "main_hand")

    def test_shield_conflict_non_weapon_and_magic_weapon_state(self):
        with TemporaryDirectory() as tmpdir:
            player_path = Path(tmpdir) / "hero.yaml"
            player_path.write_text(
                yaml.safe_dump(
                    {
                        "name": "Hero",
                        "inventory": {
                            "items": [
                                {"id": "greatsword", "instance_id": "greatsword_1", "equipped": False},
                                {"id": "shield", "instance_id": "shield_1", "equipped": True},
                                {"id": "leather", "instance_id": "armor_1", "equipped": False},
                                {
                                    "id": "hellfire_battleaxe_plus_2",
                                    "instance_id": "magic_weapon_1",
                                    "equipped": True,
                                    "attuned": True,
                                    "state": {"pools": [{"id": "foo", "current": 1, "max": 1}]},
                                },
                                {"id": "ring_of_greater_invisibility", "instance_id": "ring_1", "equipped": False, "attuned": False},
                            ]
                        },
                    },
                    sort_keys=False,
                ),
                encoding="utf-8",
            )
            client = self._build_client(self._build_tracker(player_path))

            blocked = client.post(
                "/api/characters/Hero/inventory/items/greatsword_1/equip_weapon_mainhand",
                json={"mode": "two"},
            )
            self.assertEqual(blocked.status_code, 400)

            offhand_fail = client.post("/api/characters/Hero/inventory/items/greatsword_1/equip_weapon_offhand")
            self.assertEqual(offhand_fail.status_code, 400)

            non_weapon = client.post("/api/characters/Hero/inventory/items/armor_1/equip_weapon_mainhand")
            self.assertEqual(non_weapon.status_code, 400)

            magic = client.post(
                "/api/characters/Hero/inventory/items/magic_weapon_1/equip_weapon_mainhand",
                json={"mode": "two"},
            )
            self.assertEqual(magic.status_code, 400)  # shield still blocks two-handed

            unequip_shield = client.post("/api/characters/Hero/inventory/items/shield_1/unequip_non_magic")
            self.assertEqual(unequip_shield.status_code, 200)
            magic = client.post(
                "/api/characters/Hero/inventory/items/magic_weapon_1/equip_weapon_mainhand",
                json={"mode": "two"},
            )
            self.assertEqual(magic.status_code, 200)

            saved = yaml.safe_load(player_path.read_text(encoding="utf-8"))
            by_instance = {item["instance_id"]: item for item in saved["inventory"]["items"]}
            self.assertTrue(by_instance["magic_weapon_1"].get("attuned"))
            self.assertEqual(by_instance["magic_weapon_1"].get("state", {}).get("pools", [])[0].get("id"), "foo")
            self.assertEqual(by_instance["magic_weapon_1"].get("equipped_slot"), "main_hand")
            self.assertEqual(by_instance["magic_weapon_1"].get("selected_mode"), "two")


if __name__ == "__main__":
    unittest.main()
