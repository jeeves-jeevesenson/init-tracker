import unittest
import os
import sys
from unittest import mock

# Ensure we can import from the root
sys.path.append(os.getcwd())

import dnd_initative_tracker as tracker_mod
from monster_capability_service import MonsterCapabilityService

class TestSuppressionGunnerAutomation(unittest.TestCase):
    def setUp(self):
        self.app = object.__new__(tracker_mod.InitiativeTracker)
        self.app.__dict__.update({
            "combatants": {
                1: mock.Mock(cid=1, monster_slug="black-and-tan-suppression-gunner", is_pc=False, hp=50),
                2: mock.Mock(cid=2, is_pc=False, hp=30, max_hp=50, name="Target")
            },
            "_monster_resource_state": {},
            "active_cid": 1,
            "round_num": 1,
            "turn_num": 1,
        })
        self.app.combatants[1].name = "Gunner"
        
        # Mock methods
        self.app._dm_validate_monster_actor_for_turn = lambda cid: (self.app.combatants.get(cid), None, cid)
        self.app._ensure_monster_capabilities = lambda: MonsterCapabilityService()
        self.app._dm_normalize_turn_spend = lambda s, **kwargs: s
        self.app._dm_spend_combatant_turn_resource = lambda actor, spend: (True, None)
        self.app._lan_force_state_broadcast = lambda: None
        self.app._rebuild_table = lambda **kw: None
        self.app._monster_modifier_state = {}
        self.app._monster_sequence_state = {}
        self.app._monster_capability_damage_roll_packet = lambda cap, **kw: {"damage_rolls": [], "total_fail": 0, "total_success": 0}
        self.app._monster_capability_resolution_packet = lambda **kw: {"area": {}, "damage": [], "effects": []}
        
        # Necessary for execution
        self.app._dm_monster_capability_execute = tracker_mod.InitiativeTracker._dm_monster_capability_execute.__get__(self.app, tracker_mod.InitiativeTracker)
        self.app._monster_capability_ensure_resource_state = tracker_mod.InitiativeTracker._monster_capability_ensure_resource_state.__get__(self.app, tracker_mod.InitiativeTracker)

    def test_suppressive_fire_ammo_consumption(self):
        """Suppressive Fire (save_ability) consumes 10 ammo."""
        payload = {
            "capability_id": "suppressive-fire",
            "target_cid": 2,
            "spend": "action"
        }
        # Initialize ammo
        self.app._monster_resource_state["1:ammo:suppressive-fire:current"] = 30
        
        result = self.app._dm_monster_capability_execute(actor_cid=1, payload=payload)
        
        self.assertTrue(result["ok"], result.get("error"))
        self.assertEqual(result["resolution"], "assisted")
        self.assertEqual(self.app._monster_resource_state["1:ammo:suppressive-fire:current"], 20)

    def test_automatic_sweep_ammo_consumption(self):
        """Automatic Sweep (save_ability) consumes 10 ammo."""
        payload = {
            "capability_id": "automatic-sweep",
            "target_cid": 2,
            "spend": "action"
        }
        # Initialize ammo
        self.app._monster_resource_state["1:ammo:automatic-sweep:current"] = 30
        
        result = self.app._dm_monster_capability_execute(actor_cid=1, payload=payload)
        
        self.assertTrue(result["ok"], result.get("error"))
        self.assertEqual(result["resolution"], "assisted")
        self.assertEqual(self.app._monster_resource_state["1:ammo:automatic-sweep:current"], 20)

    def test_suppressive_fire_no_ammo_fails(self):
        """Suppressive Fire fails if not enough ammo."""
        payload = {
            "capability_id": "suppressive-fire",
            "target_cid": 2,
            "spend": "action"
        }
        # Initialize ammo to less than 10
        self.app._monster_resource_state["1:ammo:suppressive-fire:current"] = 5
        
        result = self.app._dm_monster_capability_execute(actor_cid=1, payload=payload)
        
        self.assertFalse(result["ok"])
        self.assertIn("needs 10 ammo", result["error"])
        # Verify ammo was NOT consumed
        self.assertEqual(self.app._monster_resource_state["1:ammo:suppressive-fire:current"], 5)

    def test_smoke_canister_execution_and_use_consumption(self):
        """Smoke Canister (utility) consumes 1 use and returns Deployed status."""
        payload = {
            "capability_id": "smoke-canister",
            "target_cid": 2,
            "spend": "action"
        }
        # Initialize uses
        self.app._monster_resource_state["1:uses:smoke-canister:current"] = 2
        
        # We need to use Field Medic for this test as Gunner doesn't have it
        self.app.combatants[1].monster_slug = "black-and-tan-field-medic"
        
        result = self.app._dm_monster_capability_execute(actor_cid=1, payload=payload)
        
        self.assertTrue(result["ok"], result.get("error"))
        self.assertEqual(result["resolution"], "automatic")
        self.assertIn("Deployed (10-foot radius)", result["status"])
        self.assertEqual(self.app._monster_resource_state["1:uses:smoke-canister:current"], 1)

if __name__ == "__main__":
    unittest.main()
