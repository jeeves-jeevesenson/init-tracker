import copy
import unittest
from pathlib import Path

import dnd_initative_tracker as tracker_mod


class ResourcePoolAccountingRegressionTests(unittest.TestCase):
    def setUp(self):
        self.app = object.__new__(tracker_mod.InitiativeTracker)
        self.saved_payloads = []
        self.app._load_player_yaml_cache = lambda force_refresh=False: None
        self.app._player_yaml_name_map = {}
        self.app._player_yaml_cache_by_path = {}
        self.app._store_character_yaml = lambda _path, payload: self.saved_payloads.append(copy.deepcopy(payload))
        self.app._resolve_active_inventory_item_pool_state = lambda _raw, _pool_id: None
        self.app._normalize_inventory_item_granted_pools = lambda _profile: []
        self.app._derive_consumable_resource_pools_from_inventory = lambda _profile: []

    def _register_profile(self, name, raw_profile):
        path = Path(f"/tmp/{str(name).strip().lower().replace(' ', '_')}.yaml")
        key = self.app._normalize_character_lookup_key(name)
        self.app._player_yaml_name_map[key] = path
        self.app._player_yaml_cache_by_path[path] = copy.deepcopy(raw_profile)
        return path

    def test_consume_resource_pool_defaults_missing_current_to_computed_max(self):
        self._register_profile(
            "John Twilight",
            {
                "name": "John Twilight",
                "leveling": {"classes": [{"name": "Fighter", "level": 5}]},
                "resources": {
                    "pools": [
                        {"id": "action_surge", "label": "Action Surge", "max_formula": "1", "reset": "short_rest"},
                    ]
                },
            },
        )

        ok, err = self.app._consume_resource_pool_for_cast("John Twilight", "action_surge", 1)

        self.assertTrue(ok, err)
        self.assertEqual(err, "")
        saved = self.saved_payloads[-1]
        pool = next(entry for entry in (saved.get("resources", {}).get("pools") or []) if entry.get("id") == "action_surge")
        self.assertEqual(int(pool.get("current", -1)), 0)

    def test_consume_resource_pool_materializes_missing_focus_pool(self):
        self._register_profile(
            "Old Ahmman",
            {
                "name": "Old Ahmman",
                "leveling": {"classes": [{"name": "Monk", "level": 3}]},
                "resources": {"pools": []},
            },
        )

        ok, err = self.app._consume_resource_pool_for_cast("Old Ahmman", "focus_points", 1)

        self.assertTrue(ok, err)
        self.assertEqual(err, "")
        saved = self.saved_payloads[-1]
        pool = next(entry for entry in (saved.get("resources", {}).get("pools") or []) if entry.get("id") == "focus_points")
        self.assertEqual(int(pool.get("max", -1)), 3)
        self.assertEqual(int(pool.get("current", -1)), 2)

    def test_consume_spell_slot_falls_back_to_pact_magic_pool(self):
        profile = {
            "name": "Vicnor",
            "spellcasting": {
                "enabled": True,
                "spell_slots": {str(level): {"max": 0, "current": 0} for level in range(1, 10)},
                "pact_magic_slots": {"level": 4, "count": 2},
            },
        }
        consumed = []
        self.app._profile_for_player_name = lambda _name: copy.deepcopy(profile)
        self.app._consume_resource_pool_for_cast = lambda player_name, pool_id, cost: (
            consumed.append((player_name, pool_id, cost)) or True,
            "",
        )

        ok, err, spent = self.app._consume_spell_slot_for_cast("Vicnor", 1, 1)

        self.assertTrue(ok, err)
        self.assertEqual(err, "")
        self.assertEqual(spent, 4)
        self.assertEqual(consumed, [("Vicnor", "pact_magic_slots", 1)])

    def test_consume_spell_slot_with_provenance_prefers_standard_slots_before_pact_on_mixed_profile(self):
        profile = {
            "name": "Throat Goat",
            "spellcasting": {
                "enabled": True,
                "spell_slots": {
                    **{str(level): {"max": 0, "current": 0} for level in range(1, 10)},
                    "1": {"max": 4, "current": 4},
                },
                "pact_magic_slots": {"level": 1, "count": 2},
            },
            "resources": {
                "pools": [
                    {"id": "pact_magic_slots", "current": 1, "max_formula": "2", "reset": "short_rest", "slot_level": 1},
                ]
            },
        }
        saved_slots = []
        self.app._profile_for_player_name = lambda _name: copy.deepcopy(profile)
        self.app._save_player_spell_slots = lambda _name, slots: saved_slots.append(copy.deepcopy(slots)) or slots

        ok, err, spent, provenance = self.app._consume_spell_slot_for_cast_with_provenance("Throat Goat", 1, 1)

        self.assertTrue(ok, err)
        self.assertEqual(err, "")
        self.assertEqual(spent, 1)
        self.assertEqual(provenance, {"pool_id": "spell_slots", "slot_level": 1})
        self.assertEqual(int((saved_slots[-1].get("1") or {}).get("current") or 0), 3)

    def test_player_profiles_payload_projects_runtime_pact_slots_from_pool(self):
        self.app._load_player_yaml_cache = lambda force_refresh=False: None
        self.app._player_yaml_data_by_name = {
            "Vicnor": {
                "name": "Vicnor",
                "leveling": {"classes": [{"name": "Warlock", "level": 7}]},
                "spellcasting": {
                    "enabled": True,
                    "spell_slots": {str(level): {"max": 0, "current": 0} for level in range(1, 10)},
                    "pact_magic_slots": {"level": 4, "count": 2},
                },
                "resources": {
                    "pools": [
                        {"id": "pact_magic_slots", "current": 1, "max_formula": "2", "reset": "short_rest"},
                    ]
                },
            }
        }
        self.app._wild_shape_available_cache = {}
        self.app._wild_shape_beast_cache = object()
        self.app._wild_shape_available_cache_source = self.app._wild_shape_beast_cache
        self.app._wild_shape_known_by_player = {}
        self.app._compute_spell_save_dc = lambda _profile: None

        payload = self.app._player_profiles_payload()

        slots = ((payload.get("Vicnor", {}).get("spellcasting") or {}).get("spell_slots")) or {}
        self.assertEqual(int((slots.get("4") or {}).get("max") or 0), 2)
        self.assertEqual(int((slots.get("4") or {}).get("current") or 0), 1)


if __name__ == "__main__":
    unittest.main()
