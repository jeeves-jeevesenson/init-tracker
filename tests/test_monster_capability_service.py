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

if __name__ == "__main__":
    unittest.main()
