import unittest
import os
import json
from dnd_initative_tracker import InitiativeTracker
from monster_capability_service import MonsterCapabilityService

class TestBlackAndTanRoughArrest(unittest.TestCase):
    def setUp(self):
        self.app = InitiativeTracker()
        # Ensure we use repo-local capabilities
        self.service = MonsterCapabilityService()
        self.app._monster_capability_service = self.service
        
        # Setup a dummy combat with a Constable
        self.app.combatants = {}
        self.app.round_num = 1
        self.app.turn_num = 0
        
        # Add Constable (actor)
        self.constable_cid = 1
        self.constable = type('Combatant', (), {
            'cid': self.constable_cid,
            'name': 'Constable 1',
            'monster_slug': 'black-and-tan-constable',
            'role': 'enemy',
            'ally': False,
            'hp': 20,
            'max_hp': 20,
            'conditions': [],
            'resources': {'action': 1, 'bonus': 1, 'reaction': 1}
        })()
        self.app.combatants[self.constable_cid] = self.constable
        
        # Add Player (target)
        self.player_cid = 2
        self.player = type('Combatant', (), {
            'cid': self.player_cid,
            'name': 'Player 1',
            'role': 'pc',
            'ally': True,
            'hp': 30,
            'max_hp': 30,
            'conditions': [],
            'resources': {'action': 1, 'bonus': 1, 'reaction': 1}
        })()
        self.app.combatants[self.player_cid] = self.player
        
        # Set turn to constable
        self.app.turn_order = [self.constable_cid, self.player_cid]

    def test_baton_hit_includes_rough_arrest_rider(self):
        """Test that executing a Baton attack returns a resolution packet with the Rough Arrest rider."""
        payload = {
            "capability_id": "baton",
            "target_cid": self.player_cid,
            "spend": "none" # Preview mode
        }
        
        result = self.app._dm_monster_capability_execute(
            actor_cid=self.constable_cid,
            payload=payload
        )
        
        self.assertTrue(result.get("ok"))
        self.assertEqual(result.get("resolution"), "assisted")
        
        # Check for riders in the resolution packet (result is the packet in _dm_monster_capability_execute)
        # Wait, looking at dnd_initative_tracker.py:
        # res = { "ok": True, "resolution": "assisted", ... "riders": resolution_packet.get("riders", []), ... }
        
        riders = result.get("riders", [])
        self.assertTrue(any(r["id"] == "rough-arrest" for r in riders), f"Rough Arrest rider not found in {riders}")
        
        # Verify rider content
        rough_arrest = next(r for r in riders if r["id"] == "rough-arrest")
        self.assertEqual(rough_arrest["trigger"], "hit")
        self.assertIn("grapple", rough_arrest["desc"].lower())

    def test_pistol_does_not_include_rough_arrest_rider(self):
        """Test that executing a Pistol attack does NOT include the Rough Arrest rider."""
        payload = {
            "capability_id": "pistol",
            "target_cid": self.player_cid,
            "spend": "none"
        }
        
        result = self.app._dm_monster_capability_execute(
            actor_cid=self.constable_cid,
            payload=payload
        )
        
        self.assertTrue(result.get("ok"))
        riders = result.get("riders", [])
        self.assertFalse(any(r["id"] == "rough-arrest" for r in riders), f"Rough Arrest rider should NOT be in {riders}")

if __name__ == "__main__":
    unittest.main()
