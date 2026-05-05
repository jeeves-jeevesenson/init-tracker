import unittest
import os
import yaml
from dnd_initative_tracker import InitiativeTracker, MonsterSpec
from monster_capability_service import MonsterCapabilityService

class TestVandergraffContent(unittest.TestCase):
    def setUp(self):
        self.tracker = InitiativeTracker()
        self.capability_service = MonsterCapabilityService()

    def test_constable_stat_block_loads(self):
        path = os.path.join("Monsters", "black-and-tan-constable.yaml")
        self.assertTrue(os.path.exists(path))
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        
        self.assertEqual(data["name"], "Black and Tan Constable")
        self.assertEqual(data["hp"], 52)
        self.assertEqual(data["ac"], "16")
        self.assertEqual(data["challenge_rating"], "3")

    def test_rifleman_stat_block_loads(self):
        path = os.path.join("Monsters", "black-and-tan-rifleman.yaml")
        self.assertTrue(os.path.exists(path))
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        
        self.assertEqual(data["name"], "Black and Tan Rifleman")
        self.assertEqual(data["hp"], 68)
        self.assertEqual(data["ac"], "16")
        self.assertEqual(data["challenge_rating"], "4")

    def test_constable_capabilities_match(self):
        overlay = self.capability_service.get_capability_by_slug("black-and-tan-constable")
        self.assertIsNotNone(overlay)
        
        caps = {c["id"]: c for c in overlay["capabilities"]}
        self.assertIn("pistol", caps)
        self.assertEqual(caps["pistol"]["action_type"], "ranged_attack")
        self.assertTrue(caps["pistol"]["executable"])
        
        self.assertIn("baton", caps)
        self.assertEqual(caps["baton"]["action_type"], "melee_attack")
        self.assertTrue(caps["baton"]["executable"])
        
        self.assertIn("rough-arrest", caps)
        self.assertFalse(caps["rough-arrest"]["executable"])

    def test_rifleman_capabilities_match(self):
        overlay = self.capability_service.get_capability_by_slug("black-and-tan-rifleman")
        self.assertIsNotNone(overlay)
        
        caps = {c["id"]: c for c in overlay["capabilities"]}
        self.assertIn("armalite-rifle", caps)
        self.assertEqual(caps["armalite-rifle"]["action_type"], "ranged_attack")
        self.assertTrue(caps["armalite-rifle"]["executable"])
        
        self.assertIn("pistol", caps)
        self.assertEqual(caps["pistol"]["action_type"], "ranged_attack")
        self.assertTrue(caps["pistol"]["executable"])
        
        self.assertIn("knife", caps)
        self.assertEqual(caps["knife"]["action_type"], "melee_attack")
        self.assertTrue(caps["knife"]["executable"])

if __name__ == "__main__":
    unittest.main()
