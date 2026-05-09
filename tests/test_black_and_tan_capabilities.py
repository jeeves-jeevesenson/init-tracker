import unittest
import os
import sys
import yaml

# Ensure we can import from the root
sys.path.append(os.getcwd())

from monster_capability_service import MonsterCapabilityService

class TestBlackAndTanCapabilities(unittest.TestCase):
    def setUp(self):
        self.service = MonsterCapabilityService()

    def test_rifleman_overlay_exists_and_matches(self):
        overlay = self.service.get_capability_by_slug("black-and-tan-rifleman")
        self.assertIsNotNone(overlay, "Black and Tan Rifleman overlay should exist")
        self.assertEqual(overlay["name"], "Black and Tan Rifleman")
        
        caps = {c["id"]: c for c in overlay["capabilities"]}
        
        # Multiattack
        self.assertIn("multiattack", caps)
        self.assertEqual(caps["multiattack"]["action_type"], "composite")
        self.assertIn("composite", caps["multiattack"]["mechanics"])
        
        # Armalite Rifle
        self.assertIn("armalite-rifle", caps)
        self.assertEqual(caps["armalite-rifle"]["action_type"], "ranged_attack")
        self.assertTrue(caps["armalite-rifle"]["executable"])
        self.assertEqual(caps["armalite-rifle"]["mechanics"]["attack_bonus"], 6)
        
        # Pistol
        self.assertIn("pistol", caps)
        self.assertEqual(caps["pistol"]["action_type"], "ranged_attack")
        
        # Traits
        self.assertIn("vandergraff-drill", caps)
        self.assertEqual(caps["vandergraff-drill"]["type"], "trait")

    def test_constable_overlay_exists_and_matches(self):
        overlay = self.service.get_capability_by_slug("black-and-tan-constable")
        self.assertIsNotNone(overlay, "Black and Tan Constable overlay should exist")
        self.assertEqual(overlay["name"], "Black and Tan Constable")
        
        caps = {c["id"]: c for c in overlay["capabilities"]}
        
        # Multiattack
        self.assertIn("multiattack", caps)
        self.assertEqual(caps["multiattack"]["action_type"], "composite")
        
        # Pistol
        self.assertIn("pistol", caps)
        self.assertEqual(caps["pistol"]["action_type"], "ranged_attack")
        self.assertTrue(caps["pistol"]["executable"])
        self.assertEqual(caps["pistol"]["mechanics"]["attack_bonus"], 5)
        
        # Baton
        self.assertIn("baton", caps)
        self.assertEqual(caps["baton"]["action_type"], "melee_attack")

    def test_multiattack_composite_resolution(self):
        # We need to simulate a combatant to test summarize_capabilities_for_ui
        combatant = {"monster_slug": "black-and-tan-rifleman", "name": "Rifleman 1"}
        summary = self.service.summarize_capabilities_for_ui(1, combatant)
        
        self.assertTrue(summary["matched"])
        actions = summary["groups"]["actions"]
        multiattack = next((a for a in actions if a["id"] == "multiattack"), None)
        self.assertIsNotNone(multiattack)
        
        # Check resolved composite
        resolved = multiattack["mechanics"].get("resolved_composite")
        self.assertIsNotNone(resolved)
        self.assertTrue(any(r["action_id"] == "armalite-rifle" for r in resolved))
        self.assertTrue(all(r["matched"] for r in resolved))

if __name__ == "__main__":
    unittest.main()
