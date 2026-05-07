import unittest
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

if __name__ == "__main__":
    unittest.main()
