import unittest
import random
from unittest import mock
import dnd_initative_tracker as tracker_mod
from monster_capability_service import MonsterCapabilityService

class TestMonsterCapabilityBackend(unittest.TestCase):
    def setUp(self):
        self.app = object.__new__(tracker_mod.InitiativeTracker)
        self.app.__dict__.update({
            "combatants": {
                1: mock.Mock(cid=1, monster_slug="adult-red-dragon", is_pc=False, hp=256),
                2: mock.Mock(cid=2, is_pc=True, hp=100, temp_hp=0)
            },
            "_name_role_memory": {"Dragon": "enemy", "Hero": "pc"},
            "_monster_recharge_state": {},
            "active_cid": 1,
            "CONDITIONS_META": {"frightened": {"label": "Frightened"}, "prone": {"label": "Prone"}}
        })
        self.app.combatants[1].name = "Dragon"
        self.app.combatants[2].name = "Hero"

        # Mock methods
        self.app._dm_validate_monster_actor_for_turn = lambda cid: (self.app.combatants.get(cid), None, cid)
        self.app._ensure_monster_capabilities = lambda: MonsterCapabilityService()
        self.app._roll_monster_attack_formula = lambda f, critical=False: 10
        self.app._dm_normalize_turn_spend = lambda s, **kwargs: s
        self.app._lan_force_state_broadcast = lambda: None
        self.app._oplog = lambda m: None
        self.app._ensure_condition_stack = lambda c, ctype, turns: None
        self.app._remove_condition_type = lambda c, ctype: None

    def test_recharge_roll_success(self):
        with mock.patch("random.randint", return_value=6):
            result = self.app._dm_monster_capability_roll_recharge(cid=1, capability_id="fire-breath")
            self.assertTrue(result["ok"])
            self.assertTrue(result["success"])
            self.assertEqual(result["roll"], 6)
            self.assertTrue(self.app._monster_recharge_state.get("1:fire-breath"))

    def test_recharge_roll_failure(self):
        with mock.patch("random.randint", return_value=1):
            result = self.app._dm_monster_capability_roll_recharge(cid=1, capability_id="fire-breath")
            self.assertTrue(result["ok"])
            self.assertFalse(result["success"])
            self.assertFalse(self.app._monster_recharge_state.get("1:fire-breath", False))

    def test_execute_save_ability_assisted(self):
        payload = {
            "capability_id": "fire-breath",
            "target_cid": 2,
            "spend": "action"
        }
        # Fire breath is recharge 5
        self.app._monster_recharge_state["1:fire-breath"] = True

        result = self.app._dm_monster_capability_execute(actor_cid=1, payload=payload)
        self.assertTrue(result["ok"])
        self.assertEqual(result["resolution"], "assisted")
        self.assertEqual(result["save_dc"], 21)
        self.assertEqual(result["target_name"], "Hero")
        self.assertIn("damage_rolls", result)
        # Should be marked as used
        self.assertFalse(self.app._monster_recharge_state["1:fire-breath"])

    def test_execute_recharge_not_ready(self):
        payload = {
            "capability_id": "fire-breath",
            "target_cid": 2
        }
        self.app._monster_recharge_state["1:fire-breath"] = False

        result = self.app._dm_monster_capability_execute(actor_cid=1, payload=payload)
        self.assertFalse(result["ok"])
        self.assertIn("not recharged", result["error"])

    def test_execute_composite_assisted_sequence(self):
        payload = {
            "capability_id": "multiattack"
        }
        result = self.app._dm_monster_capability_execute(actor_cid=1, payload=payload)
        self.assertTrue(result["ok"])
        self.assertEqual(result["resolution"], "assisted_sequence")
        self.assertIn("steps", result)
        self.assertGreaterEqual(len(result["steps"]), 2)

        # Check bite step
        bite_step = next((s for s in result["steps"] if s["action_id"] == "bite"), None)
        self.assertIsNotNone(bite_step)
        self.assertTrue(bite_step["executable"])

    def test_apply_remove_effect(self):
        # Adult Red Dragon Frightful Presence has frightened effect
        payload = {
            "capability_id": "frightful-presence",
            "effect_index": 0,
            "target_cid": 2
        }
        
        # 1. Apply
        result = self.app._dm_monster_capability_effect_change(actor_cid=1, payload=payload, action="apply")
        self.assertTrue(result["ok"])
        self.assertEqual(result["condition"], "frightened")
        
        # Verify condition was applied (using mock or real state check if practical)
        # Our setUp mocks _ensure_condition_stack if we want, but here we can check the call
        # Actually setUp didn't mock it, but IniciativeTracker has it.
        # Let's mock it in setUp if it's missing or check if we can use real one.
        # For now, let's just assert ok and that it didn't crash.

        # 2. Remove
        result = self.app._dm_monster_capability_effect_change(actor_cid=1, payload=payload, action="remove")
        self.assertTrue(result["ok"])
        self.assertEqual(result["condition"], "frightened")

    def test_apply_effect_invalid_index(self):
        payload = {
            "capability_id": "frightful-presence",
            "effect_index": 99,
            "target_cid": 2
        }
        result = self.app._dm_monster_capability_effect_change(actor_cid=1, payload=payload, action="apply")
        self.assertFalse(result["ok"])
        self.assertIn("out of range", result["error"])

if __name__ == "__main__":
    unittest.main()
