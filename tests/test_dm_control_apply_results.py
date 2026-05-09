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

class TestDMControlApplyResults(unittest.TestCase):
    def setUp(self):
        self.app = tracker_mod.InitiativeTracker()
        self.app._lan.start(quiet=True)
        self.client = self.app._lan._fastapi_app
    
    def tearDown(self):
        self.app._lan.stop()

    def test_dm_control_has_apply_results_logic(self):
        """Verify /dmcontrol includes Apply Results logic and UI."""
        from fastapi.testclient import TestClient
        client = TestClient(self.client)
        response = client.get("/dmcontrol")
        self.assertEqual(response.status_code, 200)
        
        # Verify functions exist
        self.assertIn(b"async function applyLocalResolutionResults", response.content)
        self.assertIn(b"/api/dm/monster-capabilities/", response.content)
        self.assertIn(b"/resolve-targets", response.content)
        
        # Verify UI components
        self.assertIn(b"Apply Damage", response.content)
        self.assertIn(b"Apply Effects", response.content)
        self.assertIn(b"Apply Damage + Effects", response.content)
        self.assertIn(b"Apply Results will mutate combat state.", response.content)
        
        # Verify safety/hardening
        self.assertIn(b"localResolutionInFlight", response.content)
        self.assertIn(b"Manual fallback: apply result in /dm.", response.content)

    def test_dm_control_has_double_submit_protection(self):
        """Verify Apply buttons are disabled while in flight."""
        from fastapi.testclient import TestClient
        client = TestClient(self.client)
        response = client.get("/dmcontrol")
        self.assertEqual(response.status_code, 200)
        
        # Check that buttons use localResolutionInFlight to disable
        self.assertIn(b"onclick=\"applyLocalResolutionResults(true, false)\" ${localResolutionInFlight ? 'disabled' : ''}", response.content)
        self.assertIn(b"onclick=\"applyLocalResolutionResults(false, true)\" ${localResolutionInFlight ? 'disabled' : ''}", response.content)
        self.assertIn(b"onclick=\"applyLocalResolutionResults(true, true)\" ${localResolutionInFlight ? 'disabled' : ''}", response.content)

    def test_dm_control_has_sequence_tray_logic(self):
        """Verify /dmcontrol includes Sequence Tray logic and UI."""
        from fastapi.testclient import TestClient
        client = TestClient(self.client)
        response = client.get("/dmcontrol")
        self.assertEqual(response.status_code, 200)
        
        # Verify state variables
        self.assertIn(b"localSequencePacket", response.content)
        self.assertIn(b"localSequenceCompletedSteps", response.content)
        
        # Verify functions
        self.assertIn(b"function selectLocalSequenceStep", response.content)
        self.assertIn(b"function cancelLocalSequence", response.content)
        
        # Verify UI markers
        self.assertIn(b"Sequence:", response.content)
        self.assertIn(b"localSequenceCompletedSteps", response.content)
        self.assertIn(b"selectLocalSequenceStep", response.content)
        
        # Verify sequence detection in execution preview
        self.assertIn(b"assisted_sequence", response.content)
        self.assertIn(b"localSequencePacket = rawData.result", response.content)

    def test_dm_control_apply_increments_sequence(self):
        """Verify that applying results increments sequence completion if active."""
        from fastapi.testclient import TestClient
        client = TestClient(self.client)
        response = client.get("/dmcontrol")
        self.assertEqual(response.status_code, 200)
        
        self.assertIn(b"if (localSequencePacket)", response.content)
        self.assertIn(b"localSequenceCompletedSteps[String(capId)] =", response.content)

if __name__ == "__main__":
    unittest.main()
