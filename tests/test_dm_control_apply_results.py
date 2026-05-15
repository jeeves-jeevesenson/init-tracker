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
        self.assertIn(b"applyLocalResolutionResultsFromModal", response.content)
        self.assertIn(b"/api/dm/monster-capabilities/", response.content)
        self.assertIn(b"/resolve-targets", response.content)

        # Verify UI components (now in modal)
        self.assertIn(b"Apply Result", response.content)
        self.assertIn(b"resolutionModal", response.content)
        self.assertIn(b"modalDamageInput", response.content)

        # Verify outcome labels (flexible check for dynamic labels)
        self.assertIn(b"Miss", response.content)
        self.assertIn(b"No Effect", response.content)
        self.assertIn(b"Hit", response.content)

        # Verify safety/hardening
        self.assertIn(b"localResolutionInFlight", response.content)

    def test_dm_control_has_double_submit_protection(self):
        """Verify Apply buttons are disabled while in flight."""
        from fastapi.testclient import TestClient
        client = TestClient(self.client)
        response = client.get("/dmcontrol")
        self.assertEqual(response.status_code, 200)

        # Check that buttons use localResolutionApplying to disable
        self.assertIn(b"applyBtn.disabled = localResolutionApplying", response.content)

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

    def test_dm_control_has_friendly_fire_guard(self):
        """Phase 3E3: target-selection guards against same-side targets."""
        from fastapi.testclient import TestClient
        client = TestClient(self.client)
        response = client.get("/dmcontrol")
        self.assertEqual(response.status_code, 200)
        # isTargetCandidate now consults a same-side check.
        self.assertIn(b"isSameSideAsActor", response.content)
        # Apply path requires explicit confirm if target is same-side.
        self.assertIn(b"isFriendlyFireSelection", response.content)
        self.assertIn(b"Friendly target:", response.content)

    def test_dm_control_packet_preview_formatter(self):
        """Phase 3E3: packet preview helper handles arrays of objects without [object Object]."""
        from fastapi.testclient import TestClient
        client = TestClient(self.client)
        response = client.get("/dmcontrol")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"function formatPacketValue", response.content)
        self.assertIn(b"function formatPacketEntries", response.content)
        # The fragile raw join over object arrays must be gone.
        self.assertNotIn(b"packet.damage_rolls.join(', ')", response.content)
        self.assertNotIn(b"packet.effects.map(e => esc(e)).join(', ')", response.content)
        self.assertNotIn(b"packet.conditions.map(c => esc(c)).join(', ')", response.content)

    def test_dm_control_sequence_completion_cleanup(self):
        """Phase 3E3: after applying a child sequence step, target/preview state clears cleanly."""
        from fastapi.testclient import TestClient
        client = TestClient(self.client)
        response = client.get("/dmcontrol")
        self.assertEqual(response.status_code, 200)
        # Apply path drops stale target/preview state and pops back to parent multiattack.
        self.assertIn(b"sequenceComplete", response.content)
        self.assertIn(b"Multiattack sequence complete.", response.content)
        self.assertIn(b"selectedCapabilityId = String(localSequencePacket.capability_id)", response.content)

    def test_dm_control_attack_miss_outcome_label(self):
        """Phase 3E3: attack action 'success' outcome shows a miss preview."""
        from fastapi.testclient import TestClient
        client = TestClient(self.client)
        response = client.get("/dmcontrol")
        self.assertEqual(response.status_code, 200)
        # Outcome success is now labeled as Miss in the modal
        self.assertIn(b"Miss", response.content)


class TestDMControlResolveTargetsAttackMiss(unittest.TestCase):
    """Phase 3E3 backend correctness: attack miss outcome must apply zero damage."""

    def setUp(self):
        self.app = tracker_mod.InitiativeTracker()

    def _make_target(self, cid: int, name: str = "Tav", hp: int = 20, max_hp: int = 20):
        c = mock.Mock()
        c.cid = cid
        c.name = name
        c.hp = hp
        c.max_hp = max_hp
        c.temp_hp = 0
        c.is_pc = True
        c.ongoing_spell_effects = []
        c.conditions = []
        c.inventory = []
        c.attunements = []
        c.resistance_overrides = {}
        c.vulnerability_overrides = {}
        c.immunity_overrides = {}
        return c

    def _make_attacker(self, cid: int, slug: str = "black-and-tan-rifleman", name: str = "Rifleman 1"):
        c = mock.Mock()
        c.cid = cid
        c.name = name
        c.hp = 20
        c.max_hp = 20
        c.temp_hp = 0
        c.is_pc = False
        c.monster_slug = slug
        c.ongoing_spell_effects = []
        c.conditions = []
        c.inventory = []
        c.attunements = []
        return c

    def test_attack_miss_applies_zero_damage(self):
        """A ranged_attack with outcome=success (miss) must produce no damage entries."""
        attacker = self._make_attacker(101)
        target = self._make_target(202, hp=20)
        self.app.combatants = {101: attacker, 202: target}

        # Force the attacker turn predicates to pass.
        self.app.in_combat = False  # disables turn check; cid validation passes

        applied = []

        def fake_apply(actor_cid, target_cid, label, entries):
            applied.append({"actor": actor_cid, "target": target_cid, "label": label, "entries": list(entries)})
            return {"ok": True}

        self.app._apply_map_attack_manual_damage = fake_apply
        # Avoid broadcast side-effects.
        self.app._lan_force_state_broadcast = lambda: None

        # Force a known damage roll so the outcome is the only variable.
        damage_rolls = [{"formula": "1d12+4", "type": "piercing", "rolled": 12, "rolled_success": 6, "on_save": "half"}]

        # Outcome = success → for ranged_attack this is a MISS → zero damage.
        result = self.app._dm_monster_capability_resolve_targets(
            actor_cid=101,
            payload={
                "capability_id": "armalite-rifle",
                "targets": [{"target_cid": 202, "outcome": "success"}],
                "damage_rolls": damage_rolls,
                "apply_damage": True,
                "apply_effects": False,
            },
        )
        self.assertTrue(result.get("ok"), result)
        rows = result.get("results") or []
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["damage_entries"], [])
        # Apply was not invoked because there were no damage entries to apply.
        self.assertEqual(applied, [])

    def test_attack_hit_applies_full_damage(self):
        attacker = self._make_attacker(101)
        target = self._make_target(202, hp=20)
        self.app.combatants = {101: attacker, 202: target}
        self.app.in_combat = False

        applied = []
        self.app._apply_map_attack_manual_damage = lambda actor_cid, target_cid, label, entries: (
            applied.append({"actor": actor_cid, "target": target_cid, "entries": list(entries)}) or {"ok": True}
        )
        self.app._lan_force_state_broadcast = lambda: None

        damage_rolls = [{"formula": "1d12+4", "type": "piercing", "rolled": 12, "rolled_success": 6, "on_save": "half"}]
        result = self.app._dm_monster_capability_resolve_targets(
            actor_cid=101,
            payload={
                "capability_id": "armalite-rifle",
                "targets": [{"target_cid": 202, "outcome": "fail"}],
                "damage_rolls": damage_rolls,
                "apply_damage": True,
                "apply_effects": False,
            },
        )
        self.assertTrue(result.get("ok"), result)
        rows = result.get("results") or []
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["damage_entries"], [{"amount": 12, "type": "piercing"}])
        self.assertEqual(len(applied), 1)
        self.assertEqual(applied[0]["entries"], [{"amount": 12, "type": "piercing"}])

    def test_attack_no_effect_applies_zero_damage(self):
        attacker = self._make_attacker(101)
        target = self._make_target(202, hp=20)
        self.app.combatants = {101: attacker, 202: target}
        self.app.in_combat = False
        self.app._apply_map_attack_manual_damage = lambda *a, **kw: {"ok": True}
        self.app._lan_force_state_broadcast = lambda: None

        damage_rolls = [{"formula": "1d12+4", "type": "piercing", "rolled": 12, "rolled_success": 6}]
        result = self.app._dm_monster_capability_resolve_targets(
            actor_cid=101,
            payload={
                "capability_id": "armalite-rifle",
                "targets": [{"target_cid": 202, "outcome": "no_effect"}],
                "damage_rolls": damage_rolls,
                "apply_damage": True,
                "apply_effects": False,
            },
        )
        self.assertTrue(result.get("ok"), result)
        rows = result.get("results") or []
        self.assertEqual(rows[0]["damage_entries"], [])

    def test_dm_control_range_validation(self):
        """Pass 1C: verify backend range validation for simple attacks."""
        attacker = self._make_attacker(101, slug="test-monster")
        target = self._make_target(202, name="Dorian")
        self.app.combatants = {101: attacker, 202: target}
        self.app.in_combat = False

        # Mock positions: Actor at (0,0), Target at (5,0) -> 25ft distance (assuming 5ft per square)
        self.app._lan_positions = {
            101: (0, 0),
            202: (5, 0)
        }
        self.app._lan_feet_per_square = lambda: 5.0
        self.app._apply_map_attack_manual_damage = lambda *a, **kw: {"ok": True}
        self.app._lan_force_state_broadcast = lambda: None

        # Capability with reach 5ft (Baton)
        cap = {
            "id": "baton",
            "name": "Baton",
            "action_type": "melee_attack",
            "mechanics": {"reach": 5, "attack_bonus": 4, "damage": [{"formula": "1d4+2", "type": "bludgeoning"}]}
        }

        # Mock the service to return this capability
        svc = self.app._ensure_monster_capabilities()
        svc.capabilities_by_slug["test-monster"] = {"slug": "test-monster", "capabilities": [cap]}

        # 1. Attempt resolve without override -> should fail
        payload = {
            "capability_id": "baton",
            "targets": [{"target_cid": 202, "outcome": "fail"}],
            "apply_damage": True,
            "override_range": False
        }
        result = self.app._dm_monster_capability_resolve_targets(actor_cid=101, payload=payload)
        self.assertFalse(result["ok"])
        self.assertIn("out of range", result["error"])

        # 2. Attempt resolve with override -> should succeed
        payload["override_range"] = True
        result = self.app._dm_monster_capability_resolve_targets(actor_cid=101, payload=payload)
        self.assertTrue(result["ok"])




if __name__ == "__main__":
    unittest.main()
