import json
import os
import unittest
from scripts.importers.monster_capability_import import (
    normalize_dnd5eapi_action,
    normalize_o5e_action,
    parse_area_metadata,
    validate_composite_children,
)

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
        self.assertEqual(cap["mechanics"]["composite"][1]["action_id"], "claws")
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

    def test_area_metadata_extracts_cone_line_sphere_and_radius(self):
        self.assertEqual(parse_area_metadata("The dragon exhales fire in a 60-foot cone.")["shape"], "cone")
        self.assertEqual(parse_area_metadata("A line that is 100 feet long and 5 feet wide.")["width"], 5)
        self.assertEqual(parse_area_metadata("Each creature within 10 ft. of the dragon must save.")["shape"], "radius")
        self.assertEqual(parse_area_metadata("A 20-foot-radius sphere appears.")["shape"], "sphere")

    def test_dnd5eapi_save_half_and_area_metadata(self):
        action = {
            "name": "Fire Breath",
            "desc": "The dragon exhales fire in a 60-foot cone. Each creature in that area must make a DC 21 Dexterity saving throw, taking 63 (18d6) fire damage on a failed save, or half as much damage on a successful one.",
            "usage": {"type": "recharge on roll", "min_value": 5},
            "dc": {"dc_type": {"index": "dex"}, "dc_value": 21, "success_type": "none"},
            "damage": [{"damage_type": {"index": "fire"}, "damage_dice": "18d6"}],
        }
        cap = normalize_dnd5eapi_action(action, "adult-red-dragon")
        self.assertEqual(cap["mechanics"]["shape"], "cone")
        self.assertEqual(cap["mechanics"]["size"], 60)
        self.assertEqual(cap["mechanics"]["on_save"], "half")
        self.assertEqual(cap["mechanics"]["damage"][0]["on_save"], "half")
        self.assertEqual(cap["recharge"], 5)

    def test_dnd5eapi_save_no_effect_and_radius_metadata(self):
        action = {
            "name": "Wing Attack (Costs 2 Actions)",
            "desc": "Each creature within 10 ft. of the dragon must succeed on a DC 22 Dexterity saving throw or take 15 (2d6 + 8) bludgeoning damage and be knocked prone.",
            "dc": {"dc_type": {"index": "dex"}, "dc_value": 22, "success_type": "none"},
            "damage": [{"damage_type": {"index": "bludgeoning"}, "damage_dice": "2d6+8"}],
        }
        cap = normalize_dnd5eapi_action(action, "adult-red-dragon")
        self.assertEqual(cap["mechanics"]["shape"], "radius")
        self.assertEqual(cap["mechanics"]["size"], 10)
        self.assertEqual(cap["mechanics"]["on_save"], "none")
        self.assertEqual(cap["mechanics"]["effects"][0]["condition"], "prone")

    def test_frightened_rider_keeps_duration_and_repeat_save(self):
        desc = "must succeed on a DC 19 Wisdom saving throw or become frightened for 1 minute. A creature can repeat the saving throw at the end of each of its turns."
        from scripts.importers.monster_capability_import import extract_riders
        riders = extract_riders(desc)
        self.assertEqual(riders[0]["condition"], "frightened")
        self.assertEqual(riders[0]["duration"], "1 minute")
        self.assertEqual(riders[0]["repeat_save"], "end_of_turn")

    def test_conditional_trait_gets_manual_warning(self):
        action = {
            "name": "Surprise Attack",
            "desc": "If the bugbear surprises a creature and hits it with an attack during the first round of combat, the target takes an extra 7 (2d6) damage from the attack.",
            "damage": [],
        }
        cap = normalize_dnd5eapi_action(action, "bugbear")
        self.assertFalse(cap["executable"])
        self.assertEqual(cap["warnings"][0]["code"], "manual_resolution_required")

    def test_composite_validation_matches_plural_child_without_bad_singularizing(self):
        norm = {
            "capabilities": [
                {
                    "id": "multiattack",
                    "name": "Multiattack",
                    "action_type": "composite",
                    "mechanics": {"composite": [{"action_id": "claws", "name": "Claws", "count": 2}]},
                },
                {"id": "claw", "name": "Claw", "action_type": "melee_attack", "executable": True, "mechanics": {}},
            ]
        }
        validate_composite_children(norm)
        child = norm["capabilities"][0]["mechanics"]["composite"][0]
        self.assertEqual(child["action_id"], "claw")
        self.assertTrue(child["matched"])

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

    def test_sample_adult_red_dragon_import_quality(self):
        path = os.path.join("docs", "reports", "monster-source-samples", "adult-red-dragon-dnd5eapi.json")
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        caps = [normalize_dnd5eapi_action(action, "adult-red-dragon") for action in data["actions"] + data["legendary_actions"]]
        norm = {"capabilities": caps}
        validate_composite_children(norm)
        by_id = {cap["id"]: cap for cap in caps}
        self.assertEqual(by_id["fire-breath"]["mechanics"]["shape"], "cone")
        self.assertEqual(by_id["fire-breath"]["mechanics"]["on_save"], "half")
        self.assertEqual(by_id["frightful-presence"]["mechanics"]["effects"][0]["condition"], "frightened")
        self.assertTrue(by_id["multiattack"]["mechanics"]["composite"][0]["matched"])

if __name__ == "__main__":
    unittest.main()
