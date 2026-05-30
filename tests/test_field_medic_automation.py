import unittest
import os
import sys
from unittest import mock

# Ensure we can import from the root
sys.path.append(os.getcwd())

import dnd_initative_tracker as tracker_mod
from monster_capability_service import MonsterCapabilityService

class TestFieldMedicAutomation(unittest.TestCase):
    def setUp(self):
        self.app = object.__new__(tracker_mod.InitiativeTracker)
        self.app.__dict__.update({
            "combatants": {
                1: mock.Mock(cid=1, monster_slug="black-and-tan-field-medic", is_pc=False, hp=50),
                2: mock.Mock(cid=2, is_pc=False, hp=30, max_hp=50, temp_hp=0),
                3: mock.Mock(cid=3, is_pc=False, hp=20, max_hp=50, temp_hp=5)
            },
            "_monster_resource_state": {},
            "active_cid": 1,
            "round_num": 1,
            "turn_num": 1,
        })
        self.app.combatants[1].name = "Medic"
        self.app.combatants[2].name = "Grunt"
        self.app.combatants[3].name = "Wounded"

        # Mock methods
        self.app._dm_validate_monster_actor_for_turn = lambda cid: (self.app.combatants.get(cid), None, cid)
        self.app._ensure_monster_capabilities = lambda: MonsterCapabilityService()
        self.app._roll_monster_attack_formula = lambda f, critical=False: 14 if "2d8" in str(f) else 10
        self.app._dm_normalize_turn_spend = lambda s, **kwargs: s
        self.app._dm_spend_combatant_turn_resource = lambda actor, spend: (True, None)
        self.app._lan_force_state_broadcast = lambda: None
        self.app._rebuild_table = lambda **kw: None
        self.app._monster_modifier_state = {}
        self.app._monster_sequence_state = {}
        
        # Real-ish implementation for heal
        def _apply_heal(cid, amount, is_temp_hp=False):
            c = self.app.combatants.get(cid)
            if not c: return False
            if is_temp_hp:
                setattr(c, "temp_hp", max(0, int(amount)))
            else:
                old_hp = int(getattr(c, "hp", 0))
                max_hp = int(getattr(c, "max_hp", old_hp))
                setattr(c, "hp", min(max_hp, old_hp + int(amount)))
            return True
        self.app._apply_heal_to_combatant = _apply_heal
        
        # Necessary for utility handler in _dm_monster_capability_execute
        self.app._dm_monster_capability_execute = tracker_mod.InitiativeTracker._dm_monster_capability_execute.__get__(self.app, tracker_mod.InitiativeTracker)
        self.app._monster_capability_ensure_resource_state = tracker_mod.InitiativeTracker._monster_capability_ensure_resource_state.__get__(self.app, tracker_mod.InitiativeTracker)

    def test_field_treatment_healing_execution(self):
        """Field Treatment heals target and consumes use."""
        payload = {
            "capability_id": "field-treatment",
            "target_cid": 2,
            "spend": "action"
        }
        # Initialize uses
        self.app._monster_resource_state["1:uses:field-treatment:current"] = 1
        
        result = self.app._dm_monster_capability_execute(actor_cid=1, payload=payload)
        
        self.assertTrue(result["ok"], result.get("error"))
        self.assertEqual(result["resolution"], "automatic")
        self.assertEqual(self.app.combatants[2].hp, 44) # 30 + 14
        self.assertEqual(self.app._monster_resource_state["1:uses:field-treatment:current"], 0)
        self.assertIn("Healed 14 HP", result["status"])

    def test_stimulant_ampoule_temp_hp_execution(self):
        """Stimulant Ampoule grants temp HP (highest wins) and consumes use."""
        # 1. Grant to target with 0 temp HP
        payload = {
            "capability_id": "stimulant-ampoule",
            "target_cid": 2,
            "spend": "bonus"
        }
        self.app._monster_resource_state["1:uses:stimulant-ampoule:current"] = 2
        
        result = self.app._dm_monster_capability_execute(actor_cid=1, payload=payload)
        self.assertTrue(result["ok"])
        self.assertEqual(self.app.combatants[2].temp_hp, 10)
        self.assertEqual(self.app._monster_resource_state["1:uses:stimulant-ampoule:current"], 1)
        self.assertIn("Granted 10 Temp HP", result["status"])

        # 2. Grant to target with 5 temp HP (should become 10)
        payload["target_cid"] = 3
        result = self.app._dm_monster_capability_execute(actor_cid=1, payload=payload)
        self.assertTrue(result["ok"])
        self.assertEqual(self.app.combatants[3].temp_hp, 10)
        self.assertEqual(self.app._monster_resource_state["1:uses:stimulant-ampoule:current"], 0)
        self.assertIn("Granted 10 Temp HP", result["status"])

        # 3. Grant to target with 15 temp HP (should remain 15)
        self.app.combatants[2].temp_hp = 15
        self.app._monster_resource_state["1:uses:stimulant-ampoule:current"] = 1
        payload["target_cid"] = 2
        result = self.app._dm_monster_capability_execute(actor_cid=1, payload=payload)
        self.assertTrue(result["ok"])
        self.assertEqual(self.app.combatants[2].temp_hp, 15)
        self.assertIn("Target already has 15 Temp HP", result["status"])

    def test_utility_preview_spend_none(self):
        """Utility execution with spend: none returns assisted resolution preview."""
        payload = {
            "capability_id": "field-treatment",
            "target_cid": 2,
            "spend": "none"
        }
        self.app._monster_resource_state["1:uses:field-treatment:current"] = 1
        
        result = self.app._dm_monster_capability_execute(actor_cid=1, payload=payload)
        
        self.assertTrue(result["ok"])
        self.assertEqual(result["resolution"], "assisted")
        self.assertEqual(result["healing_amount"], 14)
        # Verify state was NOT mutated
        self.assertEqual(self.app.combatants[2].hp, 30)
        self.assertEqual(self.app._monster_resource_state["1:uses:field-treatment:current"], 1)

    def test_utility_no_uses_remaining(self):
        """Utility execution fails if no uses remain."""
        payload = {
            "capability_id": "field-treatment",
            "target_cid": 2,
            "spend": "action"
        }
        # Initialize uses to 0
        self.app._monster_resource_state["1:uses:field-treatment:current"] = 0
        
        result = self.app._dm_monster_capability_execute(actor_cid=1, payload=payload)
        
        self.assertFalse(result["ok"])
        self.assertIn("no uses remaining", result["error"])
        # Verify state was NOT mutated
        self.assertEqual(self.app.combatants[2].hp, 30)

if __name__ == "__main__":
    unittest.main()
