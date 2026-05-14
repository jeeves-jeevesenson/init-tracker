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

    def test_suppression_gunner_area_effects(self):
        """Suppression Gunner should have correct area metadata."""
        summary = self.service.summarize_capabilities_for_ui(1, {"monster_slug": "black-and-tan-suppression-gunner", "name": "Gunner"})
        actions = summary["groups"]["actions"]
        
        # Suppressive Fire (Cube 10)
        suppress = next(a for a in actions if a["id"] == "suppressive-fire")
        self.assertEqual(suppress["action_type"], "save_ability")
        self.assertEqual(suppress["area"]["shape"], "cube")
        self.assertEqual(suppress["area"]["size"], 10)
        self.assertEqual(suppress["target_mode"], "area_manual")
        
        # Automatic Sweep (Cone 15)
        sweep = next(a for a in actions if a["id"] == "automatic-sweep")
        self.assertEqual(sweep["area"]["shape"], "cone")
        self.assertEqual(sweep["area"]["size"], 15)
        
        # Controlled Burst
        burst = next(a for a in actions if a["id"] == "controlled-burst")
        self.assertEqual(burst["action_type"], "modifier")
        self.assertIn("+1 weapon die", burst["mechanics_summary"])

    def test_field_medic_multiattack(self):
        """Field Medic should have choose_n Multiattack."""
        summary = self.service.summarize_capabilities_for_ui(1, {"monster_slug": "black-and-tan-field-medic", "name": "Medic"})
        actions = summary["groups"]["actions"]
        multi = next(a for a in actions if a["id"] == "multiattack")
        self.assertEqual(multi["mechanics"]["sequence_kind"], "choose_n")
        self.assertEqual(multi["mechanics"]["choose_n"], 2)
        
        treatment = next(a for a in actions if a["id"] == "field-treatment")
        self.assertFalse(treatment["executable"])
        self.assertIn("Manual healing", treatment.get("manual_instructions", ""))

    def test_lieutenant_multiattack_and_bonus(self):
        """Lieutenant should have choose_n: 3 Multiattack and correct bonus actions."""
        summary = self.service.summarize_capabilities_for_ui(1, {"monster_slug": "black-and-tan-lieutenant", "name": "Lieutenant"})
        actions = summary["groups"]["actions"]
        multi = next(a for a in actions if a["id"] == "multiattack")
        self.assertEqual(multi["mechanics"]["sequence_kind"], "choose_n")
        self.assertEqual(multi["mechanics"]["choose_n"], 3)
        
        bonus_actions = summary["groups"]["bonus_actions"]
        direct_fire = next(a for a in bonus_actions if a["id"] == "direct-fire")
        self.assertFalse(direct_fire["executable"])

if __name__ == "__main__":
    unittest.main()
