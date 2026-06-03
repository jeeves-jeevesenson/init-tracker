import unittest
from unittest import mock
import dnd_initative_tracker as tracker_mod
from monster_capability_service import MonsterCapabilityService

class TestScorcherAoeResolution(unittest.TestCase):
    def setUp(self):
        # We need a real-ish InitiativeTracker but with mocked UI/OS side effects
        self.app = object.__new__(tracker_mod.InitiativeTracker)
        
        # Setup minimal state
        self.app.__dict__.update({
            "combatants": {
                1: mock.Mock(cid=1, monster_slug="black-and-tan-vda-scorcher", is_pc=False, name="Scorcher 1", hp=126, action_resource=1, bonus_action_resource=1, reaction_resource=1, _turn_action_restrictions=None, _turn_bonus_action_restrictions=None),
                2: mock.Mock(cid=2, is_pc=True, name="Hero 2", hp=100),
                3: mock.Mock(cid=3, is_pc=True, name="Hero 3", hp=100),
            },
            "_monster_resource_state": {},
            "_monster_modifier_state": {},
            "_monster_sequence_state": {},
            "round_num": 1,
            "turn_num": 1,
            "in_combat": True
        })
        
        # Mocking methods
        self.app._ensure_monster_capabilities = lambda: MonsterCapabilityService()
        self.app._lan_force_state_broadcast = lambda: None
        self.app._log = lambda *args, **kwargs: None
        self.app._oplog = lambda *args, **kwargs: None
        self.app._rebuild_table = lambda *args, **kwargs: None
        self.app._damage_perf_enabled = lambda: False
        
        # Inject methods from class
        self.app._dm_monster_capability_resolve_targets = tracker_mod.InitiativeTracker._dm_monster_capability_resolve_targets.__get__(self.app, tracker_mod.InitiativeTracker)
        self.app._dm_validate_monster_actor_for_turn = tracker_mod.InitiativeTracker._dm_validate_monster_actor_for_turn.__get__(self.app, tracker_mod.InitiativeTracker)
        self.app._dm_normalize_turn_spend = tracker_mod.InitiativeTracker._dm_normalize_turn_spend
        self.app._dm_spend_combatant_turn_resource = tracker_mod.InitiativeTracker._dm_spend_combatant_turn_resource.__get__(self.app, tracker_mod.InitiativeTracker)
        
        # Mock actual resource usage
        def mock_use_action(c, log_message=None):
            if c.action_resource > 0:
                c.action_resource -= 1
                return True
            return False
        def mock_use_bonus_action(c, log_message=None):
            if c.bonus_action_resource > 0:
                c.bonus_action_resource -= 1
                return True
            return False
        def mock_use_reaction(c, log_message=None):
            if c.reaction_resource > 0:
                c.reaction_resource -= 1
                return True
            return False
            
        self.app._use_action = mock_use_action
        self.app._use_bonus_action = mock_use_bonus_action
        self.app._use_reaction = mock_use_reaction
        
        self.app._monster_capability_damage_roll_packet = tracker_mod.InitiativeTracker._monster_capability_damage_roll_packet.__get__(self.app, tracker_mod.InitiativeTracker)
        self.app._roll_monster_attack_formula = lambda formula: 21 # Mock fixed roll (6d6 -> 21)
        self.app._monster_capability_success_damage_amount = tracker_mod.InitiativeTracker._monster_capability_success_damage_amount
        self.app._apply_map_attack_manual_damage = mock.Mock(return_value={"ok": True, "hp_after": 79})
        self.app._resolved_monster_capabilities_for_target = lambda *args, **kwargs: []
        self.app._trigger_monster_hit_reaction_prompts = lambda *args, **kwargs: ""
        self.app._trigger_monster_death_reaction_prompts = lambda *args, **kwargs: ""
        self.app._trigger_monster_save_reaction_prompts = lambda *args, **kwargs: ""
        self.app._lan_feet_per_square = lambda: 5
        self.app._damage_perf_emit = lambda *args, **kwargs: None

    def test_scorcher_flamethrower_resolve_targets_spending(self):
        """Resolving Flamethrower Burst should spend 2 fuel and the action resource."""
        # Setup fuel
        self.app._monster_resource_state["1:ammo:flamethrower-burst:current"] = 10
        
        payload = {
            "capability_id": "flamethrower-burst",
            "targets": [
                {"target_cid": 2, "outcome": "fail"},
                {"target_cid": 3, "outcome": "success"}
            ],
            "apply_damage": True,
            "spend": "action",
            "aoe_geometry": {
                "shape": "cone",
                "size": 15,
                "origin": [5, 5],
                "direction": 0
            }
        }
        
        result = self.app._dm_monster_capability_resolve_targets(actor_cid=1, payload=payload)
        
        self.assertTrue(result["ok"])
        self.assertEqual(result["target_count"], 2)
        
        # Verify Fuel spending: 10 - 2 = 8
        self.assertEqual(self.app._monster_resource_state["1:ammo:flamethrower-burst:current"], 8)
        
        # Verify Action spending
        self.assertEqual(self.app.combatants[1].action_resource, 0)
        
        # Verify damage application calls
        # Hero 2 (fail) -> full damage (21)
        # Hero 3 (success) -> half damage (10)
        self.assertEqual(self.app._apply_map_attack_manual_damage.call_count, 2)
        
        # Check first call (Hero 2)
        args2 = self.app._apply_map_attack_manual_damage.call_args_list[0]
        self.assertEqual(args2[0][1], 2) # target_cid
        self.assertEqual(args2[0][3][0]["amount"], 21)
        
        # Check second call (Hero 3)
        args3 = self.app._apply_map_attack_manual_damage.call_args_list[1]
        self.assertEqual(args3[0][1], 3) # target_cid
        self.assertEqual(args3[0][3][0]["amount"], 10)

    def test_scorcher_ignite_ground_resolve_targets_spending(self):
        """Resolving Ignite Ground should spend 2 fuel and the action resource."""
        # Setup fuel
        # Ignite Ground uses fuel as ammo_type in YAML
        self.app._monster_resource_state["1:ammo:ignite-ground:current"] = 10
        
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
                "origin": [10, 10]
            }
        }
        
        # Mock roll for 2d6 -> 7
        self.app._roll_monster_attack_formula = lambda formula: 7
        
        result = self.app._dm_monster_capability_resolve_targets(actor_cid=1, payload=payload)
        
        self.assertTrue(result["ok"])
        
        # Verify Fuel spending: 10 - 2 = 8
        self.assertEqual(self.app._monster_resource_state["1:ammo:ignite-ground:current"], 8)
        
        # Verify Action spending
        self.assertEqual(self.app.combatants[1].action_resource, 0)
        
        # Verify damage (7)
        self.app._apply_map_attack_manual_damage.assert_called_once()
        args = self.app._apply_map_attack_manual_damage.call_args
        self.assertEqual(args[0][3][0]["amount"], 7)

    def test_unsupported_aoe_shape_rejection(self):
        """Backend should reject unsupported AoE shapes."""
        payload = {
            "capability_id": "flamethrower-burst",
            "targets": [{"target_cid": 2, "outcome": "fail"}],
            "aoe_geometry": {"shape": "hexagon", "size": 10}
        }
        result = self.app._dm_monster_capability_resolve_targets(actor_cid=1, payload=payload)
        self.assertFalse(result["ok"])
        self.assertIn("Unsupported AoE shape", result["error"])

    def test_scorcher_ignite_ground_zero_targets_persistent_placement(self):
        """Resolving Ignite Ground with zero targets should still place hazards."""
        self.app._upsert_map_hazard = mock.Mock(return_value="haz_123")
        self.app._lan_get_map_state = lambda: {}
        self.app._resolve_aoe_cells = lambda spec: {(10, 10), (11, 10), (10, 11), (11, 11)}
        self.app._dm_console_snapshot = lambda: {"ok": True}
        
        payload = {
            "capability_id": "ignite-ground",
            "targets": [], # ZERO TARGETS
            "apply_damage": True,
            "spend": "action",
            "aoe_geometry": {
                "shape": "square",
                "size": 10,
                "origin": {"col": 10, "row": 10}
            }
        }
        
        result = self.app._dm_monster_capability_resolve_targets(actor_cid=1, payload=payload)
        
        self.assertTrue(result["ok"])
        self.assertEqual(result.get("hazard_placed_count"), 4)
        self.assertEqual(self.app._upsert_map_hazard.call_count, 4)

if __name__ == "__main__":
    unittest.main()
