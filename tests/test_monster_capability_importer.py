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

    def test_rider_extraction_prone(self):
        desc = "Hit: 7 (2d4 + 2) piercing damage. If the target is a creature, it must succeed on a DC 11 Strength saving throw or be knocked prone."
        from scripts.importers.monster_capability_import import extract_riders
        riders = extract_riders(desc)
        self.assertEqual(len(riders), 1)
        self.assertEqual(riders[0]["condition"], "prone")
        self.assertEqual(riders[0]["trigger"], "on_failed_save")
        self.assertEqual(riders[0]["save_dc"], 11)
        self.assertEqual(riders[0]["save_ability"], "str")

    def test_rider_extraction_frightened(self):
        desc = "must succeed on a DC 19 Wisdom saving throw or become frightened for 1 minute"
        from scripts.importers.monster_capability_import import extract_riders
        riders = extract_riders(desc)
        self.assertEqual(len(riders), 1)
        self.assertEqual(riders[0]["condition"], "frightened")
        self.assertEqual(riders[0]["trigger"], "on_failed_save")
        self.assertEqual(riders[0]["save_dc"], 19)
        self.assertEqual(riders[0]["save_ability"], "wis")

    def test_rider_extraction_grappled(self):
        desc = "the target is grappled (escape DC 14)"
        from scripts.importers.monster_capability_import import extract_riders
        riders = extract_riders(desc)
        self.assertEqual(len(riders), 1)
        self.assertEqual(riders[0]["condition"], "grappled")
        self.assertEqual(riders[0]["trigger"], "on_hit")
        self.assertEqual(riders[0]["escape_dc"], 14)

    def test_dnd5eapi_spellcasting_extraction(self):
        action = {
            "name": "Spellcasting",
            "spellcasting": {
                "ability": {"index": "int"},
                "dc": 17,
                "modifier": 9,
                "slots": {"1": 4, "2": 3},
                "spells": [
                    {"name": "Magic Missile", "level": 1},
                    {"name": "Shield", "level": 1},
                    {"name": "Misty Step", "level": 2},
                    {"name": "Detect Magic", "level": 1, "usage": {"type": "at will"}}
                ]
            }
        }
        cap = normalize_dnd5eapi_action(action, "test-mage")
        self.assertEqual(cap["action_type"], "spellcasting")
        s = cap["mechanics"]["spellcasting"]
        self.assertEqual(s["ability"], "int")
        self.assertEqual(s["save_dc"], 17)
        self.assertEqual(len(s["lists"]), 3) # at_will, slot lvl 1, slot lvl 2
        
        at_will = next(l for l in s["lists"] if l["frequency"] == "at_will")
        self.assertIn("detect-magic", at_will["spells"])

if __name__ == "__main__":
    unittest.main()
