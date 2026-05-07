import unittest
from unittest import mock
from pathlib import Path
import os
import sys

# Ensure we can import the tracker
sys.path.append(os.getcwd())

# Force headless for testing
os.environ["INIT_TRACKER_HEADLESS"] = "1"

import dnd_initative_tracker as tracker_mod

class TestDMControlRoute(unittest.TestCase):
    def setUp(self):
        self.app = tracker_mod.InitiativeTracker()
        self.app._lan.start(quiet=True)
        # We need to wait a bit for the server to be ready or just use the app's fastapi_app
        self.client = self.app._lan._fastapi_app
    
    def tearDown(self):
        self.app._lan.stop()

    def test_dm_control_route_exists(self):
        """Verify /dmcontrol route returns 200 and expected content."""
        from fastapi.testclient import TestClient
        client = TestClient(self.client)
        response = client.get("/dmcontrol")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"DM Control", response.content)
        self.assertIn(b"DM Cockpit", response.content)

    def test_dm_cockpit_has_link_to_dm_control(self):
        """Verify /dm cockpit includes the link to /dmcontrol."""
        from fastapi.testclient import TestClient
        client = TestClient(self.client)
        response = client.get("/dm")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"/dmcontrol", response.content)
        self.assertIn(b"Open DM Control", response.content)

    def test_dm_control_has_link_to_dm_cockpit(self):
        """Verify /dmcontrol includes the link back to /dm."""
        from fastapi.testclient import TestClient
        client = TestClient(self.client)
        response = client.get("/dmcontrol")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"href=\"/dm\"", response.content)
        self.assertIn(b"DM Cockpit", response.content)

    def test_dm_control_has_map_canvas(self):
        """Verify /dmcontrol includes a map canvas."""
        from fastapi.testclient import TestClient
        client = TestClient(self.client)
        response = client.get("/dmcontrol")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"id=\"mapCanvas\"", response.content)

    def test_dm_control_has_no_legacy_controls(self):
        """Verify /dmcontrol does not include legacy monster controls."""
        from fastapi.testclient import TestClient
        client = TestClient(self.client)
        response = client.get("/dmcontrol")
        self.assertEqual(response.status_code, 200)
        # Legacy controls usually have these IDs or classes
        self.assertNotIn(b"id=\"monsterTurnControls\"", response.content)
        self.assertNotIn(b"id=\"monsterPilotPanel\"", response.content)
        self.assertNotIn(b"DM Toolbox", response.content)

    def test_dm_control_has_movement_visualization(self):
        """Verify /dmcontrol includes movement range logic and UI."""
        from fastapi.testclient import TestClient
        client = TestClient(self.client)
        # We check for the script content that indicates movement range logic
        response = client.get("/dmcontrol")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"function movementCostMap", response.content)
        self.assertIn(b"Movement Remaining", response.content)

    def test_dm_control_has_drag_drop_logic(self):
        """Verify /dmcontrol includes drag-and-drop movement logic."""
        from fastapi.testclient import TestClient
        client = TestClient(self.client)
        response = client.get("/dmcontrol")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"pointerdown", response.content)
        self.assertIn(b"pointermove", response.content)
        self.assertIn(b"pointerup", response.content)
        self.assertIn(b"async function executeMove", response.content)
        self.assertIn(b"/api/dm/map/combatants/", response.content)
        self.assertIn(b"/move", response.content)

    def test_dm_control_has_movement_hints(self):
        """Verify /dmcontrol includes UI hints for movement."""
        from fastapi.testclient import TestClient
        client = TestClient(self.client)
        response = client.get("/dmcontrol")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Drag token on map to move", response.content)
        self.assertIn(b"Movement is backend-validated", response.content)

    def test_dm_move_combatant_on_map_functional(self):
        """Verify backend move endpoint works for a monster."""
        from fastapi.testclient import TestClient
        client = TestClient(self.client)
        
        # 1. Setup combat with a monster on map
        self.app._lan_try_move = lambda cid, col, row: (True, "", 10) # Mock successful move
        
        # We need a real combatant and a map position for the service/tracker to work
        # but for this test we can just check if the endpoint calls the tracker method.
        # Actually, let's use the real tracker if possible or mock the underlying _dm_move_combatant_on_map
        
        with mock.patch.object(self.app, '_dm_move_combatant_on_map') as mock_move:
            mock_move.return_value = {"ok": True, "cid": 1, "col": 2, "row": 3, "spent_ft": 10}
            
            response = client.post("/api/dm/map/combatants/1/move", json={"col": 2, "row": 3})
            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["cid"], 1)
            self.assertEqual(payload["col"], 2)
            self.assertEqual(payload["row"], 3)
            self.assertEqual(payload["spent_ft"], 10)
            self.assertIn("snapshot", payload)
            
            mock_move.assert_called_once_with(1, 2, 3)

if __name__ == "__main__":
    unittest.main()
