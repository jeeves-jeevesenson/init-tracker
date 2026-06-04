import unittest
from unittest import mock
import dnd_initative_tracker as tracker_mod
from monster_capability_service import MonsterCapabilityService
from spell_engine_primitives import AoeSpec

class TestScorcherAoeContract(unittest.TestCase):
    def setUp(self):
        self.app = object.__new__(tracker_mod.InitiativeTracker)
        
        # Setup minimal state
        self.app.__dict__.update({
            "combatants": {
                1: mock.Mock(cid=1, monster_slug="black-and-tan-vda-scorcher", is_pc=False, name="Scorcher 1", hp=126, action_resource=1, bonus_action_resource=1, reaction_resource=1, _turn_action_restrictions=None, _turn_bonus_action_restrictions=None),
                2: mock.Mock(cid=2, is_pc=True, name="Hero 2", hp=100, pos=mock.Mock(col=10, row=10)),
            },
            "_monster_resource_state": {
                "1:ammo:ignite-ground:current": 10,
                "1:ammo:flamethrower-burst:current": 10
            },
            "_monster_modifier_state": {},
            "_monster_sequence_state": {},
            "round_num": 1,
            "turn_num": 1,
            "in_combat": True,
            "_lan_grid_cols": 20,
            "_lan_grid_rows": 20,
            "_lan_positions": {1: (5, 5), 2: (10, 10)}
        })
        
        # Mocking methods
        self.app._ensure_monster_capabilities = lambda: MonsterCapabilityService()
        self.app._lan_force_state_broadcast = lambda: None
        self.app._log = lambda *args, **kwargs: None
        self.app._oplog = lambda *args, **kwargs: None
        self.app._rebuild_table = lambda *args, **kwargs: None
        self.app._damage_perf_enabled = lambda: False
        self.app._lan_feet_per_square = lambda: 5
        self.app._resolve_aoe_cells = tracker_mod.InitiativeTracker._resolve_aoe_cells.__get__(self.app, tracker_mod.InitiativeTracker)
        
        # Inject methods
        self.app._dm_monster_capability_resolve_targets = tracker_mod.InitiativeTracker._dm_monster_capability_resolve_targets.__get__(self.app, tracker_mod.InitiativeTracker)
        self.app._dm_validate_monster_actor_for_turn = tracker_mod.InitiativeTracker._dm_validate_monster_actor_for_turn.__get__(self.app, tracker_mod.InitiativeTracker)
        self.app._dm_normalize_turn_spend = tracker_mod.InitiativeTracker._dm_normalize_turn_spend
        self.app._dm_spend_combatant_turn_resource = tracker_mod.InitiativeTracker._dm_spend_combatant_turn_resource.__get__(self.app, tracker_mod.InitiativeTracker)
        self.app._use_action = lambda c, log_message=None: True
        self.app._monster_capability_damage_roll_packet = tracker_mod.InitiativeTracker._monster_capability_damage_roll_packet.__get__(self.app, tracker_mod.InitiativeTracker)
        self.app._roll_monster_attack_formula = lambda formula: 7
        self.app._monster_capability_success_damage_amount = tracker_mod.InitiativeTracker._monster_capability_success_damage_amount
        self.app._apply_map_attack_manual_damage = mock.Mock(return_value={"ok": True})
        self.app._resolved_monster_capabilities_for_target = lambda *args, **kwargs: []
        self.app._trigger_monster_hit_reaction_prompts = lambda *args, **kwargs: ""
        self.app._trigger_monster_death_reaction_prompts = lambda *args, **kwargs: ""
        self.app._trigger_monster_save_reaction_prompts = lambda *args, **kwargs: ""
        self.app._dm_console_snapshot = lambda: {"ok": True, "mock": "snapshot"}
        self.app._upsert_map_hazard = mock.Mock(return_value="haz_123")

    def test_ignite_ground_contract(self):
        """
        Verify that Ignite Ground creates a persistent hazard and that
        the backend returns the expected unwrapped contract fields.
        """
        payload = {
            "capability_id": "ignite-ground",
            "targets": [
                {"target_cid": 2, "outcome": "fail"}
            ],
            "apply_damage": True,
            "spend": "action",
            "aoe_geometry": {
                "shape": "square",
                "size": 10,
                "origin": {"col": 10, "row": 10},
                "ax": 10,
                "ay": 10
            }
        }
        
        result = self.app._dm_monster_capability_resolve_targets(actor_cid=1, payload=payload)
        
        # Verify contract fields match frontend expectations
        self.assertTrue(result["ok"])
        self.assertIn("results", result)
        self.assertIn("hazard_placed_count", result)
        self.assertIn("snapshot", result)
        
        # Verify hazard was placed
        self.assertGreater(result["hazard_placed_count"], 0)
        self.app._upsert_map_hazard.assert_called()

if __name__ == "__main__":
    unittest.main()
