import unittest
from scripts.importers.monster_capability_import import normalize_dnd5eapi_action, normalize_o5e_action

class TestMonsterCapabilityImporter(unittest.TestCase):
    def test_dnd5eapi_multiattack_extraction(self):
        action = {
            "name": "Multiattack",
            "desc": "The dragon makes three attacks: one with its bite and two with its claws.",
            "actions": [
                {"action_name": "Bite", "count": 1, "type": "melee"},
                {"action_name": "Claw", "count": 2, "type": "melee"}
            ]
        }
        cap = normalize_dnd5eapi_action(action, "test-dragon")
        self.assertEqual(cap["action_type"], "composite")
        self.assertIn("composite", cap["mechanics"])
        self.assertEqual(len(cap["mechanics"]["composite"]), 2)
        self.assertEqual(cap["mechanics"]["composite"][0]["action_id"], "bite")
        self.assertEqual(cap["mechanics"]["composite"][0]["count"], 1)
        self.assertEqual(cap["mechanics"]["composite"][1]["action_id"], "claw")
        self.assertEqual(cap["mechanics"]["composite"][1]["count"], 2)

    def test_o5e_multiattack_parsing_pattern1(self):
        # "one with its Bite and two with its Claws"
        action = {
            "name": "Multiattack",
            "desc": "The dragon makes three attacks: one with its bite and two with its claws.",
            "action_type": "ACTION"
        }
        cap = normalize_o5e_action(action, "test-dragon")
        self.assertEqual(cap["action_type"], "composite")
        self.assertIn("composite", cap["mechanics"])
        self.assertEqual(len(cap["mechanics"]["composite"]), 2)
        self.assertEqual(cap["mechanics"]["composite"][0]["action_id"], "bite")
        self.assertEqual(cap["mechanics"]["composite"][1]["action_id"], "claw")
        self.assertEqual(cap["mechanics"]["composite"][1]["count"], 2)

    def test_o5e_multiattack_parsing_pattern2(self):
        # "makes two scimitar attacks"
        action = {
            "name": "Multiattack",
            "desc": "The goblin makes two scimitar attacks.",
            "action_type": "ACTION"
        }
        cap = normalize_o5e_action(action, "test-goblin")
        self.assertEqual(cap["action_type"], "composite")
        self.assertIn("composite", cap["mechanics"])
        self.assertEqual(len(cap["mechanics"]["composite"]), 1)
        self.assertEqual(cap["mechanics"]["composite"][0]["action_id"], "scimitar")
        self.assertEqual(cap["mechanics"]["composite"][0]["count"], 2)

if __name__ == "__main__":
    unittest.main()
