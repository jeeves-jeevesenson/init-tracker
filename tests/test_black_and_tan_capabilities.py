import unittest
import os
import sys
import yaml

# Ensure we can import from the root
sys.path.append(os.getcwd())

from monster_capability_service import MonsterCapabilityService

class TestBlackAndTanCapabilities(unittest.TestCase):
    def setUp(self):
        self.service = MonsterCapabilityService()

    def test_rifleman_overlay_exists_and_matches(self):
        overlay = self.service.get_capability_by_slug("black-and-tan-rifleman")
        self.assertIsNotNone(overlay, "Black and Tan Rifleman overlay should exist")
        self.assertEqual(overlay["name"], "Black and Tan Rifleman")
        
        caps = {c["id"]: c for c in overlay["capabilities"]}
        
        # Multiattack
        self.assertIn("multiattack", caps)
        self.assertEqual(caps["multiattack"]["action_type"], "composite")
        self.assertIn("composite", caps["multiattack"]["mechanics"])
        
        # Armalite Rifle
        self.assertIn("armalite-rifle", caps)
        self.assertEqual(caps["armalite-rifle"]["action_type"], "ranged_attack")
        self.assertTrue(caps["armalite-rifle"]["executable"])
        self.assertEqual(caps["armalite-rifle"]["mechanics"]["attack_bonus"], 6)
        
        # Pistol
        self.assertIn("pistol", caps)
        self.assertEqual(caps["pistol"]["action_type"], "ranged_attack")
        
        # Traits
        self.assertIn("vandergraff-drill", caps)
        self.assertEqual(caps["vandergraff-drill"]["type"], "trait")

    def test_constable_overlay_exists_and_matches(self):
        overlay = self.service.get_capability_by_slug("black-and-tan-constable")
        self.assertIsNotNone(overlay, "Black and Tan Constable overlay should exist")
        self.assertEqual(overlay["name"], "Black and Tan Constable")

        caps = {c["id"]: c for c in overlay["capabilities"]}

        # Multiattack — must NOT be a 4-attack composite. Phase 3E3 reduces this
        # to a manual/assisted entry so engine cannot interpret it as Pistol x2 + Baton x2.
        self.assertIn("multiattack", caps)
        self.assertNotEqual(caps["multiattack"]["action_type"], "composite")
        self.assertFalse(caps["multiattack"].get("executable", False))
        self.assertNotIn("composite", caps["multiattack"].get("mechanics", {}) or {})

        # Pistol
        self.assertIn("pistol", caps)
        self.assertEqual(caps["pistol"]["action_type"], "ranged_attack")
        self.assertTrue(caps["pistol"]["executable"])
        self.assertEqual(caps["pistol"]["mechanics"]["attack_bonus"], 5)

        # Baton
        self.assertIn("baton", caps)
        self.assertEqual(caps["baton"]["action_type"], "melee_attack")
        self.assertTrue(caps["baton"]["executable"])

    def test_constable_multiattack_no_four_child_completions(self):
        """Phase 3E3 fix: Constable Multiattack must not expose four child completions."""
        combatant = {"monster_slug": "black-and-tan-constable", "name": "Constable 1"}
        summary = self.service.summarize_capabilities_for_ui(1, combatant)

        actions = {a["id"]: a for a in summary["groups"]["actions"]}
        multi = actions["multiattack"]
        # No composite resolution should be exposed for Constable Multiattack.
        self.assertNotIn("resolved_composite", multi.get("mechanics", {}) or {})
        # Should carry a clear manual instruction so the DM knows what to do.
        self.assertIn("two attacks", str(multi.get("manual_instructions") or "").lower())

    def test_constable_multiattack_is_manual_assist(self):
        combatant = {"monster_slug": "black-and-tan-constable", "name": "Constable 1"}
        summary = self.service.summarize_capabilities_for_ui(1, combatant)
        actions = {a["id"]: a for a in summary["groups"]["actions"]}
        multi = actions["multiattack"]
        self.assertFalse(multi.get("executable", False))

    def test_rifleman_multiattack_remains_two_armalite(self):
        """Phase 3E3 regression: Rifleman Multiattack remains two Armalite Rifle attacks."""
        combatant = {"monster_slug": "black-and-tan-rifleman", "name": "Rifleman 1"}
        summary = self.service.summarize_capabilities_for_ui(1, combatant)
        actions = {a["id"]: a for a in summary["groups"]["actions"]}
        multi = actions["multiattack"]
        self.assertEqual(multi["action_type"], "composite")
        resolved = multi["mechanics"].get("resolved_composite") or []
        self.assertEqual(len(resolved), 1)
        self.assertEqual(resolved[0]["action_id"], "armalite-rifle")
        self.assertEqual(resolved[0]["count"], 2)

    def test_firearm_target_mode_is_single_not_area(self):
        """Phase 3E3 fix: weapon range no longer leaks into area metadata."""
        combatant = {"monster_slug": "black-and-tan-rifleman", "name": "Rifleman 1"}
        summary = self.service.summarize_capabilities_for_ui(1, combatant)
        actions = {a["id"]: a for a in summary["groups"]["actions"]}

        rifle = actions["armalite-rifle"]
        self.assertEqual(rifle["target_mode"], "single")
        # Area metadata (if present at all) must not have been populated
        # solely by mechanics.range / long_range.
        area = rifle.get("area")
        if area is not None:
            self.assertNotIn("range", area)
            self.assertFalse(area.get("shape"))
            self.assertFalse(area.get("size"))

        pistol = actions["pistol"]
        self.assertEqual(pistol["target_mode"], "single")
        area = pistol.get("area")
        if area is not None:
            self.assertNotIn("range", area)
            self.assertFalse(area.get("shape"))
            self.assertFalse(area.get("size"))

    def test_firearm_range_exposed_for_advisory(self):
        """Weapon range remains available for range/advisory text via flat fields."""
        combatant = {"monster_slug": "black-and-tan-rifleman", "name": "Rifleman 1"}
        summary = self.service.summarize_capabilities_for_ui(1, combatant)
        actions = {a["id"]: a for a in summary["groups"]["actions"]}
        rifle = actions["armalite-rifle"]
        self.assertEqual(rifle.get("range_ft"), 120)
        self.assertEqual(rifle.get("long_range_ft"), 360)

    def test_controlled_burst_remains_manual(self):
        combatant = {"monster_slug": "black-and-tan-rifleman", "name": "Rifleman 1"}
        summary = self.service.summarize_capabilities_for_ui(1, combatant)
        actions = {a["id"]: a for a in summary["groups"]["actions"]}
        burst = actions["controlled-burst"]
        self.assertFalse(burst.get("executable", True))

    def test_multiattack_composite_resolution(self):
        # We need to simulate a combatant to test summarize_capabilities_for_ui
        combatant = {"monster_slug": "black-and-tan-rifleman", "name": "Rifleman 1"}
        summary = self.service.summarize_capabilities_for_ui(1, combatant)
        
        self.assertTrue(summary["matched"])
        actions = summary["groups"]["actions"]
        multiattack = next((a for a in actions if a["id"] == "multiattack"), None)
        self.assertIsNotNone(multiattack)
        
        # Check resolved composite
        resolved = multiattack["mechanics"].get("resolved_composite")
        self.assertIsNotNone(resolved)
        self.assertTrue(any(r["action_id"] == "armalite-rifle" for r in resolved))
        self.assertTrue(all(r["matched"] for r in resolved))

    def test_rifleman_ui_summaries(self):
        combatant = {"monster_slug": "black-and-tan-rifleman", "name": "Rifleman 1"}
        summary = self.service.summarize_capabilities_for_ui(1, combatant)
        
        actions = {a["id"]: a for a in summary["groups"]["actions"]}
        traits = {t["id"]: t for t in summary["groups"]["traits"]}
        
        # Armalite Rifle summary
        rifle = actions["armalite-rifle"]
        self.assertIn("+6 to hit", rifle["mechanics_summary"])
        self.assertIn("1d12+4 piercing", rifle["mechanics_summary"])
        self.assertIn("Magazine 20", rifle["mechanics_summary"])
        self.assertIn("Track ammunition manually.", rifle["manual_instructions"])
        
        # Controlled Burst summary
        burst = actions["controlled-burst"]
        self.assertIn("Manual/Assisted: Spends 3 ammo, +1 die damage.", burst["manual_instructions"])
        self.assertIn("Track ammunition manually.", burst["manual_instructions"])
        
        # Vandergraff Drill
        drill = traits["vandergraff-drill"]
        self.assertIn("Reminder: +1 to attack if near another officer.", drill["manual_instructions"])

    def test_constable_ui_summaries(self):
        combatant = {"monster_slug": "black-and-tan-constable", "name": "Constable 1"}
        summary = self.service.summarize_capabilities_for_ui(1, combatant)
        
        actions = {a["id"]: a for a in summary["groups"]["actions"]}
        
        # Rough Arrest
        arrest = actions["rough-arrest"]
        self.assertIn("Manual/Assisted grapple action.", arrest["manual_instructions"])
        self.assertIn("Apply Grappled condition manually in /dm if hit.", arrest["manual_instructions"])

if __name__ == "__main__":
    unittest.main()
