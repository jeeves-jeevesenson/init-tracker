import unittest
from combatant_name_service import CombatantNameService

class TestCombatantNameService(unittest.TestCase):
    def test_first_spawn_default_unsuffixed(self):
        # Default behavior: first one is NOT numbered
        name = CombatantNameService.get_next_available_name("Goblin", [])
        self.assertEqual(name, "Goblin")

    def test_first_spawn_forced_numbered(self):
        # Forced behavior: first one IS numbered
        name = CombatantNameService.get_next_available_name("Goblin", [], force_number=True)
        self.assertEqual(name, "Goblin 1")

    def test_increments_existing_suffixes(self):
        existing = ["Goblin 1", "Goblin 2"]
        name = CombatantNameService.get_next_available_name("Goblin", existing)
        self.assertEqual(name, "Goblin 3")

    def test_fills_gaps_in_suffixes(self):
        existing = ["Goblin 1", "Goblin 3"]
        name = CombatantNameService.get_next_available_name("Goblin", existing)
        self.assertEqual(name, "Goblin 2")

    def test_handles_unsuffixed_existing_name_as_1(self):
        existing = ["Goblin"]
        name = CombatantNameService.get_next_available_name("Goblin", existing)
        self.assertEqual(name, "Goblin 2")

    def test_mixed_unsuffixed_and_suffixed(self):
        existing = ["Goblin", "Goblin 2"]
        name = CombatantNameService.get_next_available_name("Goblin", existing)
        self.assertEqual(name, "Goblin 3")

    def test_case_insensitivity(self):
        existing = ["goblin 1"]
        name = CombatantNameService.get_next_available_name("Goblin", existing)
        self.assertEqual(name, "Goblin 2")

    def test_different_monsters_independent(self):
        existing = ["Orc 1", "Orc 2"]
        name = CombatantNameService.get_next_available_name("Goblin", existing, force_number=True)
        self.assertEqual(name, "Goblin 1")

    def test_base_name_with_numbers(self):
        # If the monster is literally named "Unit 731"
        existing = ["Unit 731 1"]
        name = CombatantNameService.get_next_available_name("Unit 731", existing)
        self.assertEqual(name, "Unit 731 2")

if __name__ == "__main__":
    unittest.main()
