import unittest
import os
import yaml
from monster_capability_service import MonsterCapabilityService

class TestMonsterCapabilityService(unittest.TestCase):
    def setUp(self):
        # We assume the samples are present in the repo
        self.svc = MonsterCapabilityService()

    def test_load_samples(self):
        self.assertIn("skeleton", self.svc.capabilities_by_slug)
        self.assertIn("goblin", self.svc.capabilities_by_slug)
        self.assertIn("goblin-warrior", self.svc.capabilities_by_slug)
        self.assertIn("zombie", self.svc.capabilities_by_slug)
        self.assertIn("wolf", self.svc.capabilities_by_slug)
        self.assertIn("orc", self.svc.capabilities_by_slug)
        self.assertIn("adult-red-dragon", self.svc.capabilities_by_slug)
        self.assertIn("archmage", self.svc.capabilities_by_slug)

    def test_match_by_slug(self):
        combatant = {"monster_slug": "skeleton", "name": "Skeleton 1"}
        matched = self.svc.match_capabilities_for_combatant(combatant)
        self.assertIsNotNone(matched)
        self.assertEqual(matched["slug"], "skeleton")

    def test_match_by_name(self):
        combatant = {"name": "Goblin 1"}
        matched = self.svc.match_capabilities_for_combatant(combatant)
        self.assertIsNotNone(matched)
        self.assertEqual(matched["slug"], "goblin")

    def test_summarize_for_ui(self):
        combatant = {"monster_slug": "skeleton", "name": "Skeleton 1"}
        summary = self.svc.summarize_capabilities_for_ui(1, combatant)
        self.assertTrue(summary["matched"])
        self.assertEqual(summary["name"], "Skeleton 1")
        self.assertIn("actions", summary["groups"])
        self.assertGreater(len(summary["groups"]["actions"]), 0)

    def test_no_match(self):
        combatant = {"name": "Unknown Monster"}
        summary = self.svc.summarize_capabilities_for_ui(99, combatant)
        self.assertFalse(summary["matched"])
        self.assertEqual(summary["combatant_id"], 99)

    def test_recharge_summarization(self):
        # Adult Red Dragon has fire-breath with recharge 5
        combatant = {"monster_slug": "adult-red-dragon", "name": "Dragon"}
        summary = self.svc.summarize_capabilities_for_ui(1, combatant)
        self.assertTrue(summary["matched"])

        actions = summary["groups"]["actions"]
        fire_breath = next((a for s in summary["groups"].values() for a in s if a["id"] == "fire-breath"), None)
        self.assertIsNotNone(fire_breath)
        self.assertEqual(fire_breath["recharge_rule"], "5-6")

    def test_save_ability_summarization(self):
        combatant = {"monster_slug": "adult-red-dragon", "name": "Dragon"}
        summary = self.svc.summarize_capabilities_for_ui(1, combatant)

        fire_breath = next((a for s in summary["groups"].values() for a in s if a["id"] == "fire-breath"), None)
        self.assertEqual(fire_breath["action_type"], "save_ability")
        self.assertEqual(fire_breath["mechanics"]["save_dc"], 21)
        self.assertEqual(fire_breath["mechanics"]["save_ability"], "dex")

    def test_composite_summarization(self):
        # Adult Red Dragon has multiattack
        combatant = {"monster_slug": "adult-red-dragon", "name": "Dragon"}
        summary = self.svc.summarize_capabilities_for_ui(1, combatant)

        multi = next((a for s in summary["groups"].values() for a in s if a["id"] == "multiattack"), None)
        self.assertIsNotNone(multi)
        self.assertEqual(multi["action_type"], "composite")
        self.assertIn("resolved_composite", multi["mechanics"])

        steps = multi["mechanics"]["resolved_composite"]
        self.assertGreaterEqual(len(steps), 2)

        # Check bite resolution
        bite_step = next((s for s in steps if s["action_id"] == "bite"), None)
        self.assertIsNotNone(bite_step)
        self.assertTrue(bite_step["matched"])
        self.assertTrue(bite_step["executable"])
        self.assertEqual(bite_step["count"], 1)

if __name__ == "__main__":
    unittest.main()
