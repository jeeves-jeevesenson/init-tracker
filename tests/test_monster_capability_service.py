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
        self.assertEqual(fire_breath["target_mode"], "area_manual")
        self.assertTrue(fire_breath["multi_target_capable"])
        self.assertEqual(fire_breath["area"]["shape"], "cone")
        self.assertEqual(fire_breath["area"]["size"], 60)
        outcomes = {entry["outcome"] for entry in fire_breath["outcome_options"]}
        self.assertIn("fail", outcomes)
        self.assertIn("success", outcomes)

    def test_frightful_presence_multi_target_condition_summary(self):
        combatant = {"monster_slug": "adult-red-dragon", "name": "Dragon"}
        summary = self.svc.summarize_capabilities_for_ui(1, combatant)

        frightful = next((a for s in summary["groups"].values() for a in s if a["id"] == "frightful-presence"), None)
        self.assertEqual(frightful["target_mode"], "area_manual")
        self.assertTrue(frightful["multi_target_capable"])
        self.assertEqual(frightful["area"]["shape"], "radius")
        self.assertEqual(frightful["area"]["size"], 120)
        self.assertEqual(frightful["effects"][0]["condition"], "frightened")

    def test_wing_attack_area_condition_summary(self):
        combatant = {"monster_slug": "adult-red-dragon", "name": "Dragon"}
        summary = self.svc.summarize_capabilities_for_ui(1, combatant)

        wing = next((a for s in summary["groups"].values() for a in s if a["id"] == "wing-attack-(costs-2-actions)"), None)
        self.assertEqual(wing["target_mode"], "area_manual")
        self.assertEqual(wing["area"]["shape"], "radius")
        self.assertEqual(wing["area"]["size"], 10)
        self.assertEqual(wing["effects"][0]["condition"], "prone")

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

    def test_spellcasting_summarization(self):
        # Archmage has spellcasting
        combatant = {"monster_slug": "archmage", "name": "Mage"}
        summary = self.svc.summarize_capabilities_for_ui(1, combatant)
        
        spellcasting = next((a for s in summary["groups"].values() for a in s if a["id"] == "spellcasting"), None)
        self.assertIsNotNone(spellcasting)
        self.assertEqual(spellcasting["action_type"], "spellcasting")
        self.assertIn("resolved_lists", spellcasting["mechanics"])
        
        s_meta = spellcasting["mechanics"]["spellcasting"]
        self.assertEqual(s_meta["ability"], "int")
        self.assertEqual(s_meta["save_dc"], 17)
        
        lists = spellcasting["mechanics"]["resolved_lists"]
        self.assertGreaterEqual(len(lists), 3)
        
        # Check lightning-bolt in level 3 list
        slot_3 = next((l for l in lists if l.get("level") == 3), None)
        self.assertIsNotNone(slot_3)
        l_bolt = next((s for s in slot_3["resolved_spells"] if s["slug"] == "lightning-bolt"), None)
        self.assertIsNotNone(l_bolt)
        self.assertTrue(l_bolt["matched"])
        self.assertEqual(l_bolt["level"], 3)

if __name__ == "__main__":
    unittest.main()
