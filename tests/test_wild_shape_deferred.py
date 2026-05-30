import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
import dnd_initative_tracker as tracker_mod

class TestWildShapeDeferredPersistence(unittest.TestCase):
    def setUp(self):
        self.app = object.__new__(tracker_mod.InitiativeTracker)
        self.app._oplog = lambda *args, **kwargs: None
        self.app.combatants = {}
        self.app._wild_shape_beast_cache = [
            {
                "id": "riding-horse",
                "name": "Riding Horse",
                "challenge_rating": 0.25,
                "speed": {"walk": 60, "swim": 0, "fly": 0, "climb": 0},
                "abilities": {"str": 16, "dex": 10, "con": 12, "int": 2, "wis": 11, "cha": 7},
                "actions": [],
            }
        ]
        self.app._pc_name_for = lambda _cid: "Johnny"
        self.app._load_player_yaml_cache = lambda force_refresh=False: None
        self.app._find_player_profile_path = lambda name: Path(f"/tmp/{name}.yaml")
        self.app._player_yaml_cache_by_path = {
            Path("/tmp/Johnny.yaml"): {
                "name": "Johnny",
                "leveling": {"classes": [{"name": "Druid", "level": 2}]},
                "prepared_wild_shapes": ["riding-horse"],
                "resources": {"pools": [{"id": "wild_shape", "current": 2, "max": 2}]},
            }
        }
        # Wire up real methods we want to test
        self.app._set_wild_shape_pool_current = tracker_mod.InitiativeTracker._set_wild_shape_pool_current.__get__(self.app, tracker_mod.InitiativeTracker)
        self.app._apply_wild_shape = tracker_mod.InitiativeTracker._apply_wild_shape.__get__(self.app, tracker_mod.InitiativeTracker)
        
        # Mocks for dependencies
        self.app._normalize_player_resource_pools = tracker_mod.InitiativeTracker._normalize_player_resource_pools.__get__(self.app, tracker_mod.InitiativeTracker)
        self.app._profile_for_player_name = lambda name: self.app._player_yaml_cache_by_path.get(Path(f"/tmp/{name}.yaml"))
        self.app._wild_shape_available_forms = lambda *args, **kwargs: self.app._wild_shape_beast_cache
        self.app._wild_shape_identifier_key = tracker_mod.InitiativeTracker._wild_shape_identifier_key
        self.app._wild_shape_alias_lookup = lambda forms: {self.app._wild_shape_identifier_key(f["id"]): f["id"] for f in forms}
        self.app._mode_speed = lambda *args: 60
        self.app._druid_level_from_profile = lambda *args: 2
        self.app._set_temp_hp_via_service = lambda *args: True
        self.app._normalize_action_entries = lambda *args: []
        self.app._action_name_key = lambda name: str(name).lower()
        self.app._normalize_character_lookup_key = lambda x: str(x).lower()

        # The target mocks
        self.app._store_character_yaml = MagicMock()
        self.app._bulk_report_character_mutations = MagicMock()

    def test_apply_wild_shape_uses_deferred_bulk_persistence(self):
        c = type("C", (), {
            "cid": 1,
            "name": "Johnny",
            "speed": 30,
            "move_total": 30,
            "move_remaining": 30,
            "dex": 10,
            "con": 10,
            "str": 10,
            "temp_hp": 0,
            "is_spellcaster": True,
            "is_wild_shaped": False,
        })()
        self.app.combatants = {1: c}

        # Call with deferred=True
        ok, err = self.app._apply_wild_shape(1, "riding-horse", deferred=True)
        self.assertTrue(ok, err)

        # Verify _bulk_report_character_mutations was used instead of _store_character_yaml
        self.app._bulk_report_character_mutations.assert_called_once()
        self.app._store_character_yaml.assert_not_called()

        args, kwargs = self.app._bulk_report_character_mutations.call_args
        self.assertTrue(kwargs.get("deferred"))
        self.assertFalse(kwargs.get("include_static_refresh"))
        
        mutations = args[0]
        self.assertEqual(len(mutations), 1)
        self.assertEqual(mutations[0]["domains"], ["dynamic_player_values", "resource_pools"])

    def test_apply_wild_shape_default_is_sync_bulk(self):
        c = type("C", (), {
            "cid": 1,
            "name": "Johnny",
            "speed": 30,
            "move_total": 30,
            "move_remaining": 30,
            "dex": 10,
            "con": 10,
            "str": 10,
            "temp_hp": 0,
            "is_spellcaster": True,
            "is_wild_shaped": False,
        })()
        self.app.combatants = {1: c}

        # Call with default (deferred=False)
        ok, err = self.app._apply_wild_shape(1, "riding-horse", deferred=False)
        self.assertTrue(ok, err)

        # Verify _bulk_report_character_mutations was used with deferred=False
        self.app._bulk_report_character_mutations.assert_called_once()
        args, kwargs = self.app._bulk_report_character_mutations.call_args
        self.assertFalse(kwargs.get("deferred"))


if __name__ == "__main__":
    unittest.main()
