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

    def test_dm_control_has_action_panel_scaffold(self):
        """Verify /dmcontrol includes the action panel scaffold and correct summary parsing."""
        from fastapi.testclient import TestClient
        client = TestClient(self.client)
        response = client.get("/dmcontrol")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"id=\"activeActionsPanel\"", response.content)
        self.assertIn(b"payload.summary", response.content)
        self.assertIn(b"summary.groups", response.content)
        self.assertIn(b"capabilitySummary", response.content)
        self.assertIn(b"selectedCapabilityId", response.content)
        self.assertIn(b"function renderActionPanel", response.content)
        self.assertIn(b"/api/dm/monster-capabilities/", response.content)

    def test_dm_control_has_mutation_endpoints(self):
        """Verify /dmcontrol includes action resolution endpoints."""
        from fastapi.testclient import TestClient
        client = TestClient(self.client)
        response = client.get("/dmcontrol")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"/execute", response.content)
        self.assertIn(b"/resolve-targets", response.content)
        self.assertIn(b"Apply Damage", response.content)
        self.assertIn(b"apply_damage", response.content)
        self.assertIn(b"apply_effects", response.content)

    def test_dm_control_has_no_toolbox(self):
        """Verify /dmcontrol does not include DM Toolbox or legacy components."""
        from fastapi.testclient import TestClient
        client = TestClient(self.client)
        response = client.get("/dmcontrol")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(b"id=\"dmToolbox\"", response.content)
        self.assertNotIn(b"Monster Turn Controls", response.content)
        self.assertNotIn(b"Monster Pilot", response.content)

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

    def test_dm_control_has_target_preview_scaffold(self):
        """Verify /dmcontrol includes the target-preview mode scaffold."""
        from fastapi.testclient import TestClient
        client = TestClient(self.client)
        response = client.get("/dmcontrol")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"targetPreviewMode", response.content)
        self.assertIn(b"function enterTargetPreviewMode", response.content)
        self.assertIn(b"function cancelTargetPreviewMode", response.content)
        self.assertIn(b"function findCapabilityById", response.content)
        self.assertIn(b"function isPreviewableTargetAction", response.content)
        self.assertIn(b"keydown", response.content)
        self.assertIn(b"Escape", response.content)

    def test_dm_control_target_preview_is_local_only(self):
        """Verify target-preview logic in /dmcontrol does not use mutation endpoints."""
        from fastapi.testclient import TestClient
        client = TestClient(self.client)
        response = client.get("/dmcontrol")
        self.assertEqual(response.status_code, 200)
        # We check that targetPreviewMode assignment doesn't involve fetch POST
        self.assertNotIn(b"targetPreviewMode = await fetch", response.content)
        self.assertIn(b"targetPreviewMode = {", response.content)

    def test_dm_control_has_local_target_selection(self):
        """Verify /dmcontrol includes local target selection logic."""
        from fastapi.testclient import TestClient
        client = TestClient(self.client)
        response = client.get("/dmcontrol")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"selectedTargetCid", response.content)
        self.assertIn(b"function findUnitAtGridCell", response.content)
        self.assertIn(b"function findCombatantByCid", response.content)
        self.assertIn(b"function isTargetCandidate", response.content)
        self.assertIn(b"function selectPreviewTarget", response.content)
        self.assertIn(b"Target: ${esc(target ? target.name : 'Unknown')} (Selected Locally)", response.content)
        self.assertIn(b"Resolution is deferred.", response.content)

    def test_dm_control_has_target_advisory(self):
        """Verify /dmcontrol includes target advisory logic."""
        from fastapi.testclient import TestClient
        client = TestClient(self.client)
        response = client.get("/dmcontrol")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"function getSelectedTargetAdvisory", response.content)
        self.assertIn(b"distanceFt", response.content)
        self.assertIn(b"likely-in-range", response.content)
        self.assertIn(b"likely-out-of-range", response.content)
        self.assertIn(b"DM adjudication needed", response.content)
        self.assertIn(b"Advisory only", response.content)

    def test_dm_control_has_local_resolution_tray_scaffold(self):
        """Verify /dmcontrol includes the local resolution tray scaffold and preview logic."""
        from fastapi.testclient import TestClient
        client = TestClient(self.client)
        response = client.get("/dmcontrol")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"localResolutionTray", response.content)
        self.assertIn(b"localResolutionPacket", response.content)
        self.assertIn(b"localResolutionInFlight", response.content)
        self.assertIn(b"function openLocalResolutionTray", response.content)
        self.assertIn(b"function closeLocalResolutionTray", response.content)
        self.assertIn(b"function prepareLocalResolutionPreview", response.content)
        self.assertIn(b"function getLocalResolutionContext", response.content)
        self.assertIn(b"Resolution Preview", response.content)
        self.assertIn(b"Prepare Resolution Preview", response.content)
        self.assertIn(b"Preview only. Results are not applied.", response.content)
        self.assertIn(b"No combat state will be changed from this preview (uses spend: \"none\").", response.content)
        self.assertIn(b"Automatic resolution is deferred on /dmcontrol.", response.content)
        self.assertIn(b"Sequence resolution is deferred on /dmcontrol.", response.content)
        self.assertIn(b"spend: \"none\"", response.content)
        self.assertIn(b"Back to target selection", response.content)
        self.assertIn(b"Cancel preview", response.content)
        self.assertIn(b"ctx.lineWidth = localResolutionTray ? 5 : 3", response.content)

    def test_dm_control_has_resolution_hardening(self):
        """Verify /dmcontrol includes resolution normalization and rendering hardening."""
        from fastapi.testclient import TestClient
        client = TestClient(self.client)
        response = client.get("/dmcontrol")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"function normalizeLocalExecutionResult", response.content)
        self.assertIn(b"function renderLocalResolutionPacket", response.content)
        self.assertIn(b"Backend packet preview", response.content)
        self.assertIn(b"Packet debug details", response.content)
        self.assertIn(b"No structured packet details available yet.", response.content)
        self.assertIn(b"deferredReason", response.content)

    def test_dm_control_has_hardening_logic(self):
        """Verify /dmcontrol includes state cleanup and hardening logic."""
        from fastapi.testclient import TestClient
        client = TestClient(self.client)
        response = client.get("/dmcontrol")
        self.assertEqual(response.status_code, 200)
        # Check for state cleanup markers I intend to add
        self.assertIn(b"lastActiveCid", response.content)
        self.assertIn(b"function fullResetLocalState", response.content)
        self.assertIn(b"if (selectedTargetCid &&", response.content)
        self.assertIn(b"findCombatantByCid(selectedTargetCid)", response.content)

    def test_dm_control_has_local_outcome_controls(self):
        """Verify /dmcontrol includes local-only outcome selection logic and Apply buttons."""
        from fastapi.testclient import TestClient
        client = TestClient(self.client)
        response = client.get("/dmcontrol")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"localResolutionOutcomes", response.content)
        self.assertIn(b"function getLocalResolutionOutcome", response.content)
        self.assertIn(b"function setLocalResolutionOutcome", response.content)
        self.assertIn(b"function getOutcomeLabel", response.content)
        self.assertIn(b"function getOutcomePreviewDamage", response.content)
        self.assertIn(b"function renderLocalOutcomeControls", response.content)
        self.assertIn(b"Fail / Hit", response.content)
        self.assertIn(b"Success / Miss", response.content)
        self.assertIn(b"No Effect", response.content)
        self.assertIn(b"Manual", response.content)
        self.assertIn(b"Local Outcome Selection", response.content)
        self.assertIn(b"Local preview:", response.content)
        
        # Verify Apply buttons exist
        self.assertIn(b"/resolve-targets", response.content)
        self.assertIn(b"Apply Damage", response.content)
        self.assertIn(b"Apply Effects", response.content)
        self.assertIn(b"Apply Damage + Effects", response.content)
        self.assertIn(b"Apply Results will mutate combat state.", response.content)

    def test_dm_move_combatant_on_map_functional(self):
        """Verify the move endpoint works and updates state."""
        from fastapi.testclient import TestClient
        client = TestClient(self.client)

        # 1. Setup a combatant on map via DM service
        res = self.app._dm_service.add_combatant("Goblin", hp=10, initiative=10, is_pc=False)
        self.assertTrue(res.get("ok"), f"Failed to add combatant: {res.get('error')}")
        cid = res.get("cid")

        # Place them at 0,0 so they have a known origin for 'move'
        self.app._dm_place_combatant_on_map(cid, 0, 0)
        self.app._dm_service.start_combat()

        # 2. Move them to 1,1
        response = client.post(f"/api/dm/map/combatants/{cid}/move", json={"col": 1, "row": 1})
        self.assertEqual(response.status_code, 200, f"Move failed: {response.json()}")
        self.assertTrue(response.json().get("ok"))

        # 3. Verify they moved
        tactical = self.app._dm_tactical_snapshot()
        units = tactical.get("units", [])
        unit = next((u for u in units if u.get("cid") == cid), None)
        self.assertIsNotNone(unit)
        self.assertEqual(unit["pos"]["col"], 1)
        self.assertEqual(unit["pos"]["row"], 1)

if __name__ == "__main__":
    unittest.main()
