import unittest
from pathlib import Path
from unittest.mock import MagicMock
import dnd_initative_tracker as tracker_mod
from combat_service import CombatService

class TestWildShapeMovementReal(unittest.TestCase):
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
        self.app._player_yaml_data_by_name = {
            "Johnny": {
                "name": "Johnny",
                "leveling": {"classes": [{"name": "Druid", "level": 2}]},
                "prepared_wild_shapes": ["riding-horse"],
                "resources": {"pools": [{"id": "wild_shape", "current": 2, "max": 2}]},
            }
        }
        self.app._set_wild_shape_pool_current = lambda _name, value: (True, "", value)
        self.app._set_temp_hp_via_service = lambda _cid, _amt: True
        self.app._mode_speed = tracker_mod.InitiativeTracker._mode_speed.__get__(self.app, tracker_mod.InitiativeTracker)
        self.app._apply_wild_shape = tracker_mod.InitiativeTracker._apply_wild_shape.__get__(self.app, tracker_mod.InitiativeTracker)
        self.app._revert_wild_shape = tracker_mod.InitiativeTracker._revert_wild_shape.__get__(self.app, tracker_mod.InitiativeTracker)
        self.app._wild_shape_identifier_key = tracker_mod.InitiativeTracker._wild_shape_identifier_key
        self.app._wild_shape_available_forms = tracker_mod.InitiativeTracker._wild_shape_available_forms.__get__(self.app, tracker_mod.InitiativeTracker)
        self.app._normalized_prepared_wild_shapes_from_profile = tracker_mod.InitiativeTracker._normalized_prepared_wild_shapes_from_profile.__get__(self.app, tracker_mod.InitiativeTracker)
        self.app._normalize_prepared_wild_shapes = tracker_mod.InitiativeTracker._normalize_prepared_wild_shapes.__get__(self.app, tracker_mod.InitiativeTracker)
        self.app._normalize_player_resource_pools = tracker_mod.InitiativeTracker._normalize_player_resource_pools.__get__(self.app, tracker_mod.InitiativeTracker)
        self.app._wild_shape_alias_lookup = tracker_mod.InitiativeTracker._wild_shape_alias_lookup.__get__(self.app, tracker_mod.InitiativeTracker)
        self.app._druid_level_from_profile = tracker_mod.InitiativeTracker._druid_level_from_profile
        self.app._log = MagicMock()
        self.app._rebuild_table = MagicMock()
        self.app.round_num = 1
        self.app.turn_num = 1
        self.app.current_cid = 1
        self.app.initiative_order = [1]
        self.app.combat_started = True
        self.app.map_aoes = []
        self.app.pending_reactions = []
        self.app._monster_resource_state = {}
        self.app._lan = MagicMock()

        self.service = CombatService(self.app)
        self.service._broadcast_tracker_state = MagicMock()

    def test_combat_service_apply_no_name_error(self):
        # Johnny has 30ft speed, has moved 30ft (0 remaining)
        c = type("C", (), {
            "cid": 1,
            "name": "Johnny",
            "speed": 30,
            "swim_speed": 0,
            "fly_speed": 0,
            "climb_speed": 0,
            "burrow_speed": 0,
            "movement_mode": "Normal",
            "move_total": 30,
            "move_remaining": 0,
            "dex": 10,
            "con": 10,
            "str": 10,
            "temp_hp": 0,
            "actions": [],
            "bonus_actions": [],
            "is_spellcaster": True,
            "is_wild_shaped": False,
        })()
        self.app.combatants = {1: c}

        # Calling CombatService.wild_shape_apply should NOT raise NameError
        result = self.service.wild_shape_apply(1, "riding-horse")
        self.assertTrue(result["ok"])
        self.assertEqual(c.move_remaining, 0)
        self.assertIn("move_remaining", result)
        self.assertNotIn("distance_moved", result)

    def test_combat_service_revert_no_name_error(self):
        c = type("C", (), {
            "cid": 1,
            "name": "Johnny (Riding Horse)",
            "speed": 60,
            "swim_speed": 0,
            "fly_speed": 0,
            "climb_speed": 0,
            "burrow_speed": 0,
            "movement_mode": "Normal",
            "move_total": 60,
            "move_remaining": 20,
            "dex": 10,
            "con": 10,
            "str": 16,
            "temp_hp": 8,
            "actions": [],
            "bonus_actions": [],
            "is_spellcaster": False,
            "is_wild_shaped": True,
            "wild_shape_base": {
                "name": "Johnny",
                "speed": 30,
                "swim_speed": 0,
                "fly_speed": 0,
                "climb_speed": 0,
                "burrow_speed": 0,
                "movement_mode": "Normal",
                "dex": 10,
                "con": 10,
                "str": 10,
                "is_spellcaster": True,
                "temp_hp": 0,
                "actions": [],
                "bonus_actions": [],
            },
            "wild_shape_applied_temp_hp": 8,
            "wild_shape_prev_temp_hp": 0,
        })()
        self.app.combatants = {1: c}

        result = self.service.wild_shape_revert(1)
        self.assertTrue(result["ok"])
        self.assertEqual(c.move_remaining, 0) # 40 moved > 30 base
        self.assertIn("move_remaining", result)
        self.assertNotIn("distance_moved", result)

    def test_wild_shape_spent_all_movement_remains_zero(self):
        # Johnny has 30ft speed, has moved 30ft (0 remaining)
        c = type("C", (), {
            "cid": 1,
            "name": "Johnny",
            "speed": 30,
            "swim_speed": 0,
            "fly_speed": 0,
            "climb_speed": 0,
            "burrow_speed": 0,
            "movement_mode": "Normal",
            "move_total": 30,
            "move_remaining": 0,
            "dex": 10,
            "con": 10,
            "str": 10,
            "temp_hp": 0,
            "actions": [],
            "bonus_actions": [],
            "is_spellcaster": True,
            "is_wild_shaped": False,
        })()
        self.app.combatants = {1: c}

        # Apply Wild Shape into Riding Horse (60ft speed)
        ok, err = self.app._apply_wild_shape(1, "riding-horse")
        self.assertTrue(ok, err)

        # BUG: It likely resets to 60.
        # EXPECTED: 0 (because he used all movement)
        self.assertEqual(c.move_remaining, 0, f"Expected 0 remaining movement, but got {c.move_remaining}")

    def test_wild_shape_spent_partial_movement_is_preserved(self):
        # Johnny has 30ft speed, has moved 10ft (20 remaining)
        c = type("C", (), {
            "cid": 1,
            "name": "Johnny",
            "speed": 30,
            "swim_speed": 0,
            "fly_speed": 0,
            "climb_speed": 0,
            "burrow_speed": 0,
            "movement_mode": "Normal",
            "move_total": 30,
            "move_remaining": 20,
            "dex": 10,
            "con": 10,
            "str": 10,
            "temp_hp": 0,
            "actions": [],
            "bonus_actions": [],
            "is_spellcaster": True,
            "is_wild_shaped": False,
        })()
        self.app.combatants = {1: c}

        ok, err = self.app._apply_wild_shape(1, "riding-horse")
        self.assertTrue(ok, err)

        # EXPECTED: 60 - 10 = 50
        self.assertEqual(c.move_remaining, 50)

    def test_revert_wild_shape_preserves_spent_movement(self):
        # Horse has 60ft speed, has moved 40ft (20 remaining)
        # Johnny's base speed is 30ft.
        # Reverting should leave him with 0 remaining (since 40 > 30)
        c = type("C", (), {
            "cid": 1,
            "name": "Johnny (Riding Horse)",
            "speed": 60,
            "swim_speed": 0,
            "fly_speed": 0,
            "climb_speed": 0,
            "burrow_speed": 0,
            "movement_mode": "Normal",
            "move_total": 60,
            "move_remaining": 20,
            "dex": 10,
            "con": 10,
            "str": 16,
            "temp_hp": 8,
            "actions": [],
            "bonus_actions": [],
            "is_spellcaster": False,
            "is_wild_shaped": True,
            "wild_shape_base": {
                "name": "Johnny",
                "speed": 30,
                "swim_speed": 0,
                "fly_speed": 0,
                "climb_speed": 0,
                "burrow_speed": 0,
                "movement_mode": "Normal",
                "dex": 10,
                "con": 10,
                "str": 10,
                "is_spellcaster": True,
                "temp_hp": 0,
                "actions": [],
                "bonus_actions": [],
            },
            "wild_shape_applied_temp_hp": 8,
            "wild_shape_prev_temp_hp": 0,
        })()
        self.app.combatants = {1: c}

        ok, err = self.app._revert_wild_shape(1)
        self.assertTrue(ok, err)

        # Johnny moved 40ft. Base speed 30.
        # EXPECTED: max(0, 30 - 40) = 0
        self.assertEqual(c.move_remaining, 0)

if __name__ == "__main__":
    unittest.main()
