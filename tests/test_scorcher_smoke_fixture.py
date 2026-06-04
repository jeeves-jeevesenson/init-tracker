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

class TestScorcherSmokeFixture(unittest.TestCase):
    def setUp(self):
        self.app = tracker_mod.InitiativeTracker()
        self.app._lan.start(quiet=True)
        self.client = TestClient(self.app._lan._fastapi_app)
    
    def tearDown(self):
        self.app._lan.stop()

    def test_fixture_route_rejected_when_debugging_off(self):
        """Verify the route is rejected when INIT_TRACKER_DEBUGGING is not enabled."""
        with mock.patch("runtime_config.debugging_env_enabled", return_value=False):
            response = self.client.post("/api/dev/smoke-fixtures/dmcontrol-scorcher-ignite-ground")
            self.assertEqual(response.status_code, 403)
            self.assertEqual(response.json()["detail"], "Debugging mode is not enabled.")

    def test_fixture_route_success(self):
        """Verify the route successfully seeds the Scorcher fixture."""
        response = self.client.post("/api/dev/smoke-fixtures/dmcontrol-scorcher-ignite-ground")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["fixture_id"], "dmcontrol-scorcher-ignite-ground")
        self.assertEqual(data["expected_action"], "Ignite Ground")
        
        # Verify state via snapshot
        snapshot = data["snapshot"]
        self.assertTrue(snapshot["in_combat"])
        self.assertEqual(len(snapshot["combatants"]), 2)
        
        # Active actor should be the Scorcher
        active_cid = snapshot["active_cid"]
        self.assertEqual(active_cid, data["actor_cid"])
        
        combatants = {str(c["cid"]): c for c in snapshot["combatants"]}
        scorcher = combatants.get(str(active_cid))
        self.assertIsNotNone(scorcher)
        self.assertEqual(scorcher["name"], "Scorcher Pilot")
        
        # Verify map placement
        units = snapshot["tactical_map"]["units"]
        scorcher_unit = next((u for u in units if str(u["cid"]) == str(data["actor_cid"])), None)
        target_unit = next((u for u in units if str(u["cid"]) == str(data["target_cid"])), None)
        
        self.assertIsNotNone(scorcher_unit)
        self.assertEqual(scorcher_unit["pos"]["col"], 5)
        self.assertEqual(scorcher_unit["pos"]["row"], 5)
        
        self.assertIsNotNone(target_unit)
        self.assertEqual(target_unit["pos"]["col"], 7)
        self.assertEqual(target_unit["pos"]["row"], 5)

if __name__ == "__main__":
    unittest.main()
