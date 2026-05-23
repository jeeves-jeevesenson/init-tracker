import copy
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import dnd_initative_tracker as tracker_mod


class LanInventoryResponsivenessTests(unittest.TestCase):
    def _app(self):
        app = object.__new__(tracker_mod.InitiativeTracker)
        app._oplog = lambda *args, **kwargs: None
        app._lan_log_warning = lambda *args, **kwargs: None
        app._spell_presets_cache = None
        app._spell_preset_lookup_cache = None
        app._spell_preset_lookup_sig = None
        app._spell_index_entries = {}
        app._spell_index_loaded = False
        app._spell_dir_signature = None
        app._items_registry_cache = None
        app._items_dir_signature = None
        app._items_dir_cache = None
        app._magic_items_registry_cache = None
        app._magic_items_dir_signature = None
        app._consumables_registry_cache = {}
        app._consumables_dir_signature = None
        app._player_yaml_cache_by_path = {}
        app._player_yaml_meta_by_path = {}
        app._player_yaml_data_by_name = {}
        app._player_yaml_name_map = {}
        app._player_yaml_lock = mock.MagicMock()
        app._lan_static_snapshot_version = 0
        app._lan_static_snapshot_cache_version = -1
        app._lan_static_snapshot_cache = None
        app._lan_static_snapshot_cache_invalidation_reason = "startup"
        app._lan = mock.MagicMock()
        app._lan._cached_snapshot = {}
        app._schedule_player_yaml_refresh = mock.MagicMock()
        app._invalidate_lan_static_snapshot_cache = mock.MagicMock()
        return app

    def _items_tree(self, tmp: str) -> Path:
        items_dir = Path(tmp) / "Items"
        (items_dir / "Weapons").mkdir(parents=True)
        (items_dir / "Armor").mkdir(parents=True)
        (items_dir / "Magic_Items").mkdir(parents=True)
        return items_dir

    def test_spell_preset_lookup_reuses_cached_payload_when_signature_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            spells_dir = Path(tmp) / "Spells"
            spells_dir.mkdir()
            (spells_dir / "shield.yaml").write_text("name: Shield\nlevel: 1\n", encoding="utf-8")
            app = self._app()
            app._resolve_spells_dir = lambda: spells_dir
            app._spell_index_path = lambda: Path(tmp) / "spell_index.json"

            first = app._spell_preset_lookup()
            with mock.patch.object(app, "_spell_presets_payload", side_effect=AssertionError("catalog rebuilt")):
                second = app._spell_preset_lookup()

            self.assertIs(first, second)
            self.assertIn("shield", first[0])

    def test_spell_preset_lookup_invalidates_when_spell_signature_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            spells_dir = Path(tmp) / "Spells"
            spells_dir.mkdir()
            (spells_dir / "shield.yaml").write_text("name: Shield\nlevel: 1\n", encoding="utf-8")
            app = self._app()
            app._resolve_spells_dir = lambda: spells_dir
            app._spell_index_path = lambda: Path(tmp) / "spell_index.json"

            first = app._spell_preset_lookup()
            (spells_dir / "fireball.yaml").write_text("name: Fireball\nlevel: 3\n", encoding="utf-8")
            second = app._spell_preset_lookup()

            self.assertIsNot(first, second)
            self.assertIn("fireball", second[0])

    def test_normalize_player_profile_does_not_rebuild_spell_catalog_per_spell_lookup(self):
        app = self._app()
        app._items_registry_payload = lambda: {"weapons": {}, "armors": {}}
        app._magic_items_registry_payload = lambda: {}
        app._consumables_registry_payload = lambda: {}
        calls = {"payload": 0}
        presets = [
            {"slug": "fire-bolt", "id": "fire-bolt", "name": "Fire Bolt", "level": 0},
            {"slug": "shield", "id": "shield", "name": "Shield", "level": 1},
            {"slug": "mage-armor", "id": "mage-armor", "name": "Mage Armor", "level": 1},
        ]

        def payload():
            calls["payload"] += 1
            app._spell_dir_signature = (1, 1, ("fixed",))
            return copy.deepcopy(presets)

        app._current_spell_dir_signature = lambda: (1, 1, ("fixed",))
        app._spell_presets_payload = payload
        profile = {
            "name": "Caster",
            "spellcasting": {
                "enabled": True,
                "known_spells": {"known": ["fire-bolt", "shield"], "free": ["fire-bolt"]},
                "prepared_spells": {"prepared": ["shield", "mage-armor"]},
            },
        }

        app._normalize_player_profile(profile, "Caster")

        self.assertLessEqual(calls["payload"], 2)

    def test_magic_weapon_in_magic_items_registry_is_equip_eligible(self):
        with tempfile.TemporaryDirectory() as tmp:
            items_dir = self._items_tree(tmp)
            (items_dir / "Magic_Items" / "inazuma.yaml").write_text(
                "id: inazuma\nname: Inazuma\ncategory: weapon\ndamage:\n  one_handed:\n    formula: 1d8\n    type: slashing\n",
                encoding="utf-8",
            )
            app = self._app()
            app._resolve_items_dir = lambda: items_dir
            profile = {"name": "Hero", "inventory": {"items": [{"name": "Inazuma", "equipped": True}]}}

            weapons = app._normalize_owned_weapon_inventory_items(profile)

            self.assertEqual(weapons[0]["id"], "inazuma")
            self.assertTrue(weapons[0]["weapon_assignment"]["eligible_main_hand"])

    def test_throat_goat_sword_of_wounding_is_equip_eligible(self):
        app = self._app()
        app._resolve_items_dir = lambda: Path("Items")
        raw = tracker_mod.yaml.safe_load(Path("players/throat_goat.yaml").read_text(encoding="utf-8"))

        weapons = app._normalize_owned_weapon_inventory_items(raw)
        sword = next((entry for entry in weapons if entry.get("id") == "sword_of_wounding"), None)

        self.assertIsNotNone(sword)
        self.assertTrue(sword["weapon_assignment"]["eligible_main_hand"])

    def test_magic_weapon_equipped_syncs_to_attack_options(self):
        with tempfile.TemporaryDirectory() as tmp:
            items_dir = self._items_tree(tmp)
            (items_dir / "Magic_Items" / "inazuma.yaml").write_text(
                "id: inazuma\nname: Inazuma\ncategory: weapon\ndamage:\n  one_handed:\n    formula: 1d8\n    type: slashing\n",
                encoding="utf-8",
            )
            app = self._app()
            app._resolve_items_dir = lambda: items_dir
            profile = {
                "name": "Hero",
                "inventory": {
                    "items": [
                        {
                            "id": "inazuma",
                            "instance_id": "inazuma__001",
                            "name": "Inazuma",
                            "equipped": True,
                            "equipped_slot": "main_hand",
                        }
                    ]
                },
                "attacks": {"weapons": []},
            }

            normalized = app._normalize_player_profile(profile, "Hero")
            weapons = normalized["attacks"]["weapons"]

            self.assertEqual(weapons[0]["id"], "inazuma")
            self.assertEqual(weapons[0]["instance_id"], "inazuma__001")
            self.assertTrue(weapons[0]["equipped"])

    def test_item_equip_rejection_returns_reason_not_silent_noop(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "Hero.yaml"
            path.write_text(
                "name: Hero\ninventory:\n  items:\n    - id: rope\n      instance_id: rope__001\n      name: Rope\n",
                encoding="utf-8",
            )
            app = self._app()
            app._resolve_character_path = lambda _name: path
            app._load_character_raw = lambda p: tracker_mod.yaml.safe_load(p.read_text(encoding="utf-8"))
            app._resolve_items_dir = lambda: Path("Items")

            with self.assertRaises(tracker_mod.CharacterApiError) as ctx:
                app._mutate_owned_inventory_weapon_assignment("Hero", "rope__001", "equip_main_hand")

            detail = ctx.exception.detail
            self.assertEqual(detail["error"], "invalid_operation")
            self.assertIn("not a resolvable weapon", detail["message"])

    def test_equip_item_uses_inventory_equipment_invalidation_domain(self):
        app = self._app()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "Hero.yaml"
            path.write_text("name: Hero\ninventory:\n  items: []\n", encoding="utf-8")
            payload = {"name": "Hero", "inventory": {"items": []}}

            app._store_character_yaml(path, payload, **app._inventory_equipment_store_kwargs())

        app._invalidate_lan_static_snapshot_cache.assert_not_called()
        app._schedule_player_yaml_refresh.assert_called_with(include_static=False, force_reload=False)

    def test_equip_item_broadcast_kind_not_static_plus_dynamic_unless_capability_shape_changes(self):
        app = self._app()
        self.assertEqual(app._inventory_equipment_store_kwargs()["include_static_refresh"], False)
        self.assertEqual(app._inventory_equipment_store_kwargs()["invalidation_domains"], ["inventory_equipment_structure"])

    def test_inventory_equip_http_request_has_internal_trace_spans(self):
        with tempfile.TemporaryDirectory() as tmp:
            items_dir = self._items_tree(tmp)
            (items_dir / "Magic_Items" / "inazuma.yaml").write_text(
                "id: inazuma\nname: Inazuma\ncategory: weapon\ndamage:\n  one_handed:\n    formula: 1d8\n    type: slashing\n",
                encoding="utf-8",
            )
            path = Path(tmp) / "Hero.yaml"
            path.write_text(
                "name: Hero\ninventory:\n  items:\n    - id: inazuma\n      instance_id: inazuma__001\n      name: Inazuma\n",
                encoding="utf-8",
            )
            app = self._app()
            app._resolve_items_dir = lambda: items_dir
            app._resolve_character_path = lambda _name: path
            app._load_character_raw = lambda p: tracker_mod.yaml.safe_load(p.read_text(encoding="utf-8"))

            with mock.patch("dnd_initative_tracker.debug_event") as debug_event:
                app._mutate_owned_inventory_weapon_assignment("Hero", "inazuma__001", "equip_main_hand")

            events = [call.args[0] for call in debug_event.call_args_list]
            self.assertIn("inventory.equipment.mutation", events)
            event_call = next(call for call in debug_event.call_args_list if call.args[0] == "inventory.equipment.mutation")
            self.assertEqual(event_call.kwargs["broadcast_kind"], "dynamic_only")
            self.assertEqual(event_call.kwargs["invalidation_domains"], ["inventory_equipment_structure"])

    def test_inventory_item_granted_pool_satisfies_magic_item_spell_consumes_pool(self):
        app = self._app()
        app._resolve_items_dir = lambda: Path("Items")
        profile = {
            "name": "Old Man",
            "inventory": {
                "items": [
                    {
                        "id": "ring_of_greater_invisibility",
                        "instance_id": "ring__001",
                        "name": "Ring of Greater Invisibility",
                        "equipped": True,
                        "attuned": True,
                        "state": {
                            "pools": [
                                {"id": "ring_of_greater_invisibility", "label": "Ring", "current": 1, "max_formula": "1"}
                            ]
                        },
                    }
                ]
            },
        }

        casts = app._player_pool_granted_spells(profile)

        self.assertEqual(casts[0]["consumes_pool"]["id"], "ring_of_greater_invisibility")

    def test_old_man_ring_of_greater_invisibility_no_unknown_pool_warning_after_normalization(self):
        app = self._app()
        app._resolve_items_dir = lambda: Path("Items")
        warnings = []
        app._oplog = lambda message, level="info", **_kwargs: warnings.append(message) if level == "warning" else None
        raw = tracker_mod.yaml.safe_load(Path("players/oldahhman.yaml").read_text(encoding="utf-8"))

        app._player_pool_granted_spells(raw)

        self.assertFalse(any("unknown consumes.pool 'ring_of_greater_invisibility'" in msg for msg in warnings))

    def test_consumes_pool_warning_still_fires_for_truly_missing_pool(self):
        app = self._app()
        warnings = []
        app._oplog = lambda message, level="info", **_kwargs: warnings.append(message) if level == "warning" else None
        app._magic_items_registry_payload = lambda: {}
        app._consumables_registry_payload = lambda: {}
        profile = {
            "name": "Broken",
            "features": [
                {
                    "name": "Broken Ring",
                    "grants": {
                        "spells": {
                            "casts": [
                                {"spell": "greater-invisibility", "consumes": {"pool": "missing_pool", "cost": 1}}
                            ]
                        }
                    },
                }
            ],
        }

        casts = app._player_pool_granted_spells(profile)

        self.assertEqual(casts, [])
        self.assertTrue(any("unknown consumes.pool 'missing_pool'" in msg for msg in warnings))


if __name__ == "__main__":
    unittest.main()
