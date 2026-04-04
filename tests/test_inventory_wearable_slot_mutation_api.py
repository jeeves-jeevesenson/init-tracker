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

    def _mutate_owned_inventory_wearable_slot(self, name, instance_id, operation, payload=None):
        return self._tracker._mutate_owned_inventory_wearable_slot(name, instance_id, operation, payload=payload)


class InventoryWearableSlotMutationApiTests(unittest.TestCase):
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
        tracker._items_registry_payload = lambda: {"armors": {}, "weapons": {}}
        tracker._magic_items_registry_payload = lambda: {
            "tyrs_circlet": {"id": "tyrs_circlet", "name": "Tyr's Circlet", "requires_attunement": True},
            "ring_of_desert_sands": {"id": "ring_of_desert_sands", "name": "Ring of Desert Sands", "requires_attunement": False},
            "nature_speaker_necklace": {"id": "nature_speaker_necklace", "name": "Nature Speaker Necklace", "requires_attunement": True},
            "wand_of_fireballs": {"id": "wand_of_fireballs", "name": "Wand of Fireballs", "requires_attunement": True},
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

    def test_wearable_equip_success_and_slot_exclusivity(self):
        with TemporaryDirectory() as tmpdir:
            player_path = Path(tmpdir) / "hero.yaml"
            player_path.write_text(
                yaml.safe_dump(
                    {
                        "name": "Hero",
                        "inventory": {
                            "items": [
                                {"id": "iron_helm", "instance_id": "head_1", "name": "Iron Helm", "equipped": False},
                                {"id": "shadow_hood", "instance_id": "head_2", "name": "Shadow Hood", "equipped": True, "equipped_slot": "head"},
                                {"id": "traveler_cloak", "instance_id": "cloak_1", "name": "Traveler Cloak", "equipped": False},
                                {"id": "swift_boots", "instance_id": "boots_1", "name": "Swift Boots", "equipped": False},
                                {"id": "grip_gloves", "instance_id": "gloves_1", "name": "Grip Gloves", "equipped": False},
                            ]
                        },
                    },
                    sort_keys=False,
                ),
                encoding="utf-8",
            )
            client = self._build_client(self._build_tracker(player_path))

            head = client.post("/api/characters/Hero/inventory/items/head_1/equip_wearable", json={"slot": "head"})
            self.assertEqual(head.status_code, 200)
            self.assertEqual(head.json().get("equipped_slot"), "head")

            cloak = client.post("/api/characters/Hero/inventory/items/cloak_1/equip_wearable", json={"slot": "cloak"})
            self.assertEqual(cloak.status_code, 200)
            boots = client.post("/api/characters/Hero/inventory/items/boots_1/equip_wearable", json={"slot": "boots"})
            self.assertEqual(boots.status_code, 200)
            gloves = client.post("/api/characters/Hero/inventory/items/gloves_1/equip_wearable", json={"slot": "gloves"})
            self.assertEqual(gloves.status_code, 200)

            saved = yaml.safe_load(player_path.read_text(encoding="utf-8"))
            by_instance = {item["instance_id"]: item for item in saved["inventory"]["items"]}
            self.assertTrue(by_instance["head_1"].get("equipped"))
            self.assertEqual(by_instance["head_1"].get("equipped_slot"), "head")
            self.assertFalse(by_instance["head_2"].get("equipped"))
            self.assertFalse(by_instance["head_2"].get("equipped_slot"))
            self.assertEqual(by_instance["cloak_1"].get("equipped_slot"), "cloak")
            self.assertEqual(by_instance["boots_1"].get("equipped_slot"), "boots")
            self.assertEqual(by_instance["gloves_1"].get("equipped_slot"), "gloves")

    def test_amulet_and_ring_slots_and_magic_attunement_preserved(self):
        with TemporaryDirectory() as tmpdir:
            player_path = Path(tmpdir) / "hero.yaml"
            player_path.write_text(
                yaml.safe_dump(
                    {
                        "name": "Hero",
                        "inventory": {
                            "items": [
                                {"id": "nature_speaker_necklace", "instance_id": "amulet_1", "equipped": False, "attuned": True},
                                {"id": "ring_of_desert_sands", "instance_id": "ring_1", "equipped": False},
                                {"id": "silver_band", "instance_id": "ring_2", "name": "Silver Ring", "equipped": False},
                            ]
                        },
                    },
                    sort_keys=False,
                ),
                encoding="utf-8",
            )
            client = self._build_client(self._build_tracker(player_path))

            amulet = client.post("/api/characters/Hero/inventory/items/amulet_1/equip_wearable", json={"slot": "amulet"})
            self.assertEqual(amulet.status_code, 200)
            self.assertTrue(amulet.json().get("equipped"))
            self.assertEqual(amulet.json().get("equipped_slot"), "amulet")

            ring1 = client.post("/api/characters/Hero/inventory/items/ring_1/equip_wearable", json={"slot": "ring_one"})
            self.assertEqual(ring1.status_code, 200)
            ring2 = client.post("/api/characters/Hero/inventory/items/ring_2/equip_wearable", json={"slot": "ring_two"})
            self.assertEqual(ring2.status_code, 200)

            saved = yaml.safe_load(player_path.read_text(encoding="utf-8"))
            by_instance = {item["instance_id"]: item for item in saved["inventory"]["items"]}
            self.assertTrue(by_instance["amulet_1"].get("attuned"))
            self.assertEqual(by_instance["amulet_1"].get("equipped_slot"), "amulet")
            self.assertEqual(by_instance["ring_1"].get("equipped_slot"), "ring_one")
            self.assertEqual(by_instance["ring_2"].get("equipped_slot"), "ring_two")

    def test_guardrails_unknown_instance_invalid_slot_and_non_wearable(self):
        with TemporaryDirectory() as tmpdir:
            player_path = Path(tmpdir) / "hero.yaml"
            player_path.write_text(
                yaml.safe_dump(
                    {
                        "name": "Hero",
                        "inventory": {
                            "items": [
                                {"id": "wand_of_fireballs", "instance_id": "wand_1", "equipped": False},
                                {"id": "iron_helm", "instance_id": "head_1", "name": "Iron Helm", "equipped": False},
                                {"id": "rope", "instance_id": "rope_1", "name": "Rope", "equipped": False},
                            ]
                        },
                    },
                    sort_keys=False,
                ),
                encoding="utf-8",
            )
            client = self._build_client(self._build_tracker(player_path))

            missing = client.post("/api/characters/Hero/inventory/items/missing/equip_wearable", json={"slot": "head"})
            self.assertEqual(missing.status_code, 404)

            invalid_for_item = client.post("/api/characters/Hero/inventory/items/head_1/equip_wearable", json={"slot": "boots"})
            self.assertEqual(invalid_for_item.status_code, 400)

            unknown_slot = client.post("/api/characters/Hero/inventory/items/head_1/equip_wearable", json={"slot": "back"})
            self.assertEqual(unknown_slot.status_code, 400)

            non_wearable = client.post("/api/characters/Hero/inventory/items/rope_1/equip_wearable", json={"slot": "head"})
            self.assertEqual(non_wearable.status_code, 400)

            unequip = client.post("/api/characters/Hero/inventory/items/head_1/unequip_wearable")
            self.assertEqual(unequip.status_code, 200)
            self.assertFalse(unequip.json().get("equipped"))


if __name__ == "__main__":
    unittest.main()
