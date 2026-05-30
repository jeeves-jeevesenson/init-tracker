import unittest
import os
from monster_capability_service import MonsterCapabilityService

class TestBlackAndTanExpansion(unittest.TestCase):
    def setUp(self):
        self.service = MonsterCapabilityService()

    def test_shield_trooper_loading(self):
        """Shield Trooper should load and summarize correctly."""
        summary = self.service.summarize_capabilities_for_ui(1, {"monster_slug": "black-and-tan-shield-trooper", "name": "Shield Trooper"})
        self.assertTrue(summary["matched"])
        self.assertEqual(summary["monster_name"], "Black and Tan Shield Trooper")
        
        actions = summary["groups"]["actions"]
        multi = next(a for a in actions if a["id"] == "multiattack")
        self.assertEqual(multi["mechanics"]["sequence_kind"], "choose_n")
        self.assertEqual(multi["mechanics"]["choose_n"], 2)
        
        shield_bash = next(a for a in actions if a["id"] == "shield-bash")
        self.assertTrue(shield_bash["executable"])
        self.assertIn("Rider: Shield Bash Save", shield_bash["mechanics_summary"])
        
        reactions = summary["groups"]["reactions"]
        interpose = next(a for a in reactions if a["id"] == "interpose-shield")
        self.assertFalse(interpose["executable"])

    def test_suppression_gunner_audit(self):
        """Suppression Gunner area effects should be executable after Gate 2C automation."""
        summary = self.service.summarize_capabilities_for_ui(1, {"monster_slug": "black-and-tan-suppression-gunner", "name": "Gunner"})
        actions = summary["groups"]["actions"]
        
        suppress = next(a for a in actions if a["id"] == "suppressive-fire")
        self.assertTrue(suppress["executable"])
        self.assertEqual(suppress["area"]["shape"], "cube")
        self.assertEqual(suppress["area"]["size"], 10)

        sweep = next(a for a in actions if a["id"] == "automatic-sweep")
        self.assertTrue(sweep["executable"])
        self.assertEqual(sweep["area"]["shape"], "cone")
        self.assertEqual(sweep["area"]["size"], 15)

        brace = next(a for a in actions if a["id"] == "brace")
        self.assertTrue(brace["executable"])

    def test_field_medic_multiattack(self):
        """Field Medic should have choose_n Multiattack and executable automated actions."""
        summary = self.service.summarize_capabilities_for_ui(1, {"monster_slug": "black-and-tan-field-medic", "name": "Medic"})
        actions = summary["groups"]["actions"]
        multi = next(a for a in actions if a["id"] == "multiattack")
        self.assertEqual(multi["mechanics"]["sequence_kind"], "choose_n")
        self.assertEqual(multi["mechanics"]["choose_n"], 2)

        treatment = next(a for a in actions if a["id"] == "field-treatment")
        self.assertTrue(treatment["executable"])

        smoke = next(a for a in actions if a["id"] == "smoke-canister")
        self.assertTrue(smoke["executable"])

        reactions = summary["groups"]["reactions"]
        keep_breathing = next(a for a in reactions if a["id"] == "keep-officer-breathing")
        self.assertFalse(keep_breathing["executable"])

    def test_lieutenant_multiattack_and_bonus(self):
        """Lieutenant should have choose_n: 3 Multiattack and correct action status."""
        summary = self.service.summarize_capabilities_for_ui(1, {"monster_slug": "black-and-tan-lieutenant", "name": "Lieutenant"})
        actions = summary["groups"]["actions"]
        multi = next(a for a in actions if a["id"] == "multiattack")
        self.assertEqual(multi["mechanics"]["sequence_kind"], "choose_n")
        self.assertEqual(multi["mechanics"]["choose_n"], 3)

        bonus_actions = summary["groups"]["bonus_actions"]
        direct_fire = next(a for a in bonus_actions if a["id"] == "direct-fire")
        self.assertFalse(direct_fire["executable"])

        brace = next(a for a in bonus_actions if a["id"] == "brace")
        self.assertTrue(brace["executable"])

        reload = next(a for a in bonus_actions if a["id"] == "reload")
        self.assertTrue(reload["executable"])

        reactions = summary["groups"]["reactions"]
        get_down = next(a for a in reactions if a["id"] == "get-down")
        self.assertFalse(get_down["executable"])

    def test_captain_loading(self):
        """Captain should load with choose_n: 3 Multiattack and correct action status."""
        summary = self.service.summarize_capabilities_for_ui(1, {"monster_slug": "black-and-tan-captain", "name": "Captain"})
        self.assertTrue(summary["matched"])

        actions = summary["groups"]["actions"]
        multi = next(a for a in actions if a["id"] == "multiattack")
        self.assertEqual(multi["mechanics"]["sequence_kind"], "choose_n")
        self.assertEqual(multi["mechanics"]["choose_n"], 3)

        condemn = next(a for a in actions if a["id"] == "condemn-target")
        self.assertFalse(condemn["executable"])

        bonus = summary["groups"]["bonus_actions"]
        reload = next(a for a in bonus if a["id"] == "reload")
        self.assertTrue(reload["executable"])

        reactions = summary["groups"]["reactions"]
        not_yet = next(a for a in reactions if a["id"] == "not-yet")
        self.assertTrue(not_yet["executable"])

    def test_major_loading(self):
        """Major should load with choose_n: 3 Multiattack and correct action status."""
        summary = self.service.summarize_capabilities_for_ui(1, {"monster_slug": "black-and-tan-major", "name": "Major"})
        self.assertTrue(summary["matched"])

        actions = summary["groups"]["actions"]
        example = next(a for a in actions if a["id"] == "make-an-example")
        self.assertFalse(example["executable"])
        self.assertEqual(example["action_type"], "save_ability")
        self.assertEqual(example["mechanics"]["save_ability"], "wis")

        reactions = summary["groups"]["reactions"]
        countermand = next(a for a in reactions if a["id"] == "countermand")
        self.assertTrue(countermand["executable"])

        duck = next(a for a in reactions if a["id"] == "duck-behind-them")
        self.assertFalse(duck["executable"])

if __name__ == "__main__":
    unittest.main()
