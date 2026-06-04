import unittest
from unittest import mock
import os
import sys
from fastapi.testclient import TestClient

# Ensure we can import the tracker
sys.path.append(os.getcwd())

# Force headless and debugging for testing
os.environ["INIT_TRACKER_HEADLESS"] = "1"
os.environ["INIT_TRACKER_DEBUGGING"] = "1"
os.environ["INIT_TRACKER_ENABLE_TACTICAL_MAP"] = "1"
os.environ["INIT_TRACKER_MODE"] = "production"

import dnd_initative_tracker as tracker_mod

class TestBlackTanCombatFixture(unittest.TestCase):
    def setUp(self):
        self.app = tracker_mod.InitiativeTracker()
        self.app._lan.start(quiet=True)
        self.client = TestClient(self.app._lan._fastapi_app)
    
    def tearDown(self):
        self.app._lan.stop()

    def test_fixture_route_rejected_when_debugging_off(self):
        """Verify the route is rejected when INIT_TRACKER_DEBUGGING is not enabled."""
        with mock.patch("runtime_config.debugging_env_enabled", return_value=False):
            response = self.client.post("/api/dev/smoke-fixtures/black-tan-combat-exploration")
            self.assertEqual(response.status_code, 403)
            self.assertEqual(response.json()["detail"], "Debugging mode is not enabled.")

    def test_fixture_route_success(self):
        """Verify the route successfully seeds the Black and Tan combat exploration fixture."""
        response = self.client.post("/api/dev/smoke-fixtures/black-tan-combat-exploration")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["fixture_id"], "black-tan-combat-exploration")
        self.assertEqual(data["player_count"], 10)
        self.assertEqual(data["monster_count"], 9)
        
        # Verify state via snapshot
        snapshot = data["snapshot"]
        self.assertTrue(snapshot["in_combat"])
        # 10 players + 9 monsters + 2 summons (Owl, Raven) = 21 combatants
        self.assertEqual(len(snapshot["combatants"]), 21)
        
        # Verify names are present
        combatant_names = [c["name"] for c in snapshot["combatants"]]
        for name in data["player_names"]:
            self.assertIn(name, combatant_names)
        
        for name in data["monster_names"]:
            self.assertIn(name, combatant_names)
            
        # Verify tactical map placements
        self.assertIn("tactical_map", snapshot)
        units = snapshot["tactical_map"]["units"]
        # 10 players + 9 monsters + 2 summons (placed automatically) = 21
        self.assertEqual(len(units), 21)
        
        # Check some placements
        # Players should be at col 2-3
        # Monsters should be at col 26-27
        player_units = [u for u in units if u["name"] in data["player_names"]]
        monster_units = [u for u in units if u["name"] in data["monster_names"]]
        
        for u in player_units:
            self.assertIn(u["pos"]["col"], [2, 3])
            
        for u in monster_units:
            self.assertIn(u["pos"]["col"], [26, 27])

if __name__ == "__main__":
    unittest.main()
