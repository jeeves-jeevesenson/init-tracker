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

        # Multiattack — now a choose_n composite
        self.assertIn("multiattack", caps)
        self.assertEqual(caps["multiattack"]["action_type"], "composite")
        self.assertTrue(caps["multiattack"].get("executable", False))
        comp = caps["multiattack"]["mechanics"]["composite"]
        self.assertEqual(comp["sequence_kind"], "choose_n")
        self.assertEqual(comp["choose_n"], 2)

        # Pistol
        self.assertIn("pistol", caps)
        self.assertEqual(caps["pistol"]["action_type"], "ranged_attack")
        self.assertTrue(caps["pistol"]["executable"])
        self.assertEqual(caps["pistol"]["mechanics"]["attack_bonus"], 5)

        # Baton
        self.assertIn("baton", caps)
        self.assertEqual(caps["baton"]["action_type"], "melee_attack")
        self.assertTrue(caps["baton"]["executable"])

    def test_constable_multiattack_is_structured_composite(self):
        """Phase 2F: Constable Multiattack is now a structured choose_n composite."""
        combatant = {"monster_slug": "black-and-tan-constable", "name": "Constable 1"}
        summary = self.service.summarize_capabilities_for_ui(1, combatant)

        actions = {a["id"]: a for a in summary["groups"]["actions"]}
        multi = actions["multiattack"]
        self.assertEqual(multi["action_type"], "composite")
        self.assertTrue(multi["executable"])

        mech = multi.get("mechanics", {})
        self.assertEqual(mech.get("sequence_kind"), "choose_n")
        self.assertEqual(mech.get("choose_n"), 2)

        resolved = mech.get("resolved_composite") or []
        self.assertEqual(len(resolved), 2)
        action_ids = {r["action_id"] for r in resolved}
        self.assertIn("pistol", action_ids)
        self.assertIn("baton", action_ids)

    def test_rifleman_multiattack_remains_two_armalite(self):
        """Phase 2F: Rifleman Multiattack remains two Armalite Rifle attacks but uses explicit fixed_children."""
        combatant = {"monster_slug": "black-and-tan-rifleman", "name": "Rifleman 1"}
        summary = self.service.summarize_capabilities_for_ui(1, combatant)
        actions = {a["id"]: a for a in summary["groups"]["actions"]}
        multi = actions["multiattack"]
        self.assertEqual(multi["action_type"], "composite")
        self.assertTrue(multi["executable"])

        mech = multi.get("mechanics", {})
        self.assertEqual(mech.get("sequence_kind"), "fixed_children")

        resolved = mech.get("resolved_composite") or []
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

    def test_controlled_burst_is_structured_modifier(self):
        combatant = {"monster_slug": "black-and-tan-rifleman", "name": "Rifleman 1"}
        summary = self.service.summarize_capabilities_for_ui(1, combatant)
        actions = {a["id"]: a for a in summary["groups"]["actions"]}
        burst = actions["controlled-burst"]
        self.assertTrue(burst.get("executable"))
        self.assertEqual(burst.get("action_type"), "modifier")
        self.assertIn("3 ammo", burst["mechanics_summary"])
        self.assertIn("+1 weapon die", burst["mechanics_summary"])

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
        self.assertIn("1d12+4 force", rifle["mechanics_summary"])
        self.assertIn("Magazine 20", rifle["mechanics_summary"])
        self.assertIn("Track ammunition manually.", rifle["manual_instructions"])

        # Controlled Burst summary
        burst = actions["controlled-burst"]
        self.assertIn("3 ammo", burst["mechanics_summary"])
        self.assertIn("+1 weapon die", burst["mechanics_summary"])
        self.assertIn("Jam risk (1)", burst["mechanics_summary"])
        self.assertIn("1/turn", burst["mechanics_summary"])
        self.assertIn("Track ammunition manually.", burst["manual_instructions"])

        # Vandergraff Drill
        drill = traits["vandergraff-drill"]
        self.assertIn("Reminder: +1 to attack if near another officer.", drill["manual_instructions"])

    def test_rifleman_manual_ammo_suppression(self):
        combatant = {"monster_slug": "black-and-tan-rifleman", "name": "Rifleman 1"}
        # Provide resource state with ammo info
        resource_state = {
            "1:ammo:armalite-rifle:current": 20,
            "1:ammo:armalite-rifle:max": 20
        }
        summary = self.service.summarize_capabilities_for_ui(1, combatant, resource_state=resource_state)

        actions = {a["id"]: a for a in summary["groups"]["actions"]}
        rifle = actions["armalite-rifle"]

        # Should NOT contain manual ammo instruction
        self.assertNotIn("Track ammunition manually.", rifle.get("manual_instructions", ""))
        # Should contain structured ammo info
        self.assertIn("ammo", rifle)
        self.assertEqual(rifle["ammo"]["current"], 20)

    def test_black_and_tan_damage_types_force_for_guns_only(self):
        # 1. Verify force for guns
        combatant_rifleman = {"monster_slug": "black-and-tan-rifleman", "name": "Rifleman 1"}
        rifleman = self.service.summarize_capabilities_for_ui(1, combatant_rifleman)
        actions_rifleman = {a["id"]: a for a in rifleman["groups"]["actions"]}
        armalite = actions_rifleman["armalite-rifle"]
        self.assertEqual(armalite["mechanics"]["damage"][0]["type"], "force")
        self.assertIn("force damage", armalite["desc"])

        combatant_constable = {"monster_slug": "black-and-tan-constable", "name": "Constable 1"}
        constable = self.service.summarize_capabilities_for_ui(2, combatant_constable)
        actions_constable = {a["id"]: a for a in constable["groups"]["actions"]}
        pistol = actions_constable["pistol"]
        self.assertEqual(pistol["mechanics"]["damage"][0]["type"], "force")
        self.assertIn("force damage", pistol["desc"])

        # 2. Verify correct type for melee
        baton = actions_constable["baton"]
        self.assertEqual(baton["mechanics"]["damage"][0]["type"], "bludgeoning")
        self.assertIn("bludgeoning damage", baton["desc"])

        combatant_lt = {"monster_slug": "black-and-tan-lieutenant", "name": "Lt 1"}
        lt = self.service.summarize_capabilities_for_ui(3, combatant_lt)
        actions_lt = {a["id"]: a for a in lt["groups"]["actions"]}
        saber = actions_lt["saber"]
        self.assertEqual(saber["mechanics"]["damage"][0]["type"], "slashing")
        self.assertIn("slashing damage", saber["desc"])

    def test_black_and_tan_combat_log_force_damage(self):
        from dnd_initative_tracker import InitiativeTracker
        app = object.__new__(InitiativeTracker)
        logs = []
        app._log = lambda msg, cid=None: logs.append(msg)
        app._name_role_memory = {"Rifleman": "enemy", "Hero": "pc"}
        app._apply_damage_via_service = lambda target, amt: {"hp_after": 10}
        app._queue_concentration_save = lambda t, s: None
        app._death_flavor_line = lambda a, am, d, t: "died"
        app._rebuild_table = lambda **kw: None
        app._monster_modifier_state = {}
        app._monster_sequence_state = {}
        app._monster_resource_state = {}

        attacker = type("C", (), {"name": "Rifleman", "cid": 1})()
        target = type("C", (), {"name": "Hero", "cid": 2, "hp": 20})()
        app.combatants = {1: attacker, 2: target}

        # Case: Armalite Rifle (Force)
        app._apply_map_attack_manual_damage(
            attacker_cid=1,
            target_cid=2,
            attack_name="Armalite Rifle",
            damage_entries=[{"amount": 10, "type": "force"}]
        )
        self.assertTrue(any("applies 10 force damage to Hero." in m for m in logs))

        # Case: Baton (Bludgeoning)
        logs.clear()
        app._apply_map_attack_manual_damage(
            attacker_cid=1,
            target_cid=2,
            attack_name="Baton",
            damage_entries=[{"amount": 5, "type": "bludgeoning"}]
        )
        self.assertTrue(any("applies 5 bludgeoning damage to Hero." in m for m in logs))

    def test_constable_ui_summaries(self):
        combatant = {"monster_slug": "black-and-tan-constable", "name": "Constable 1"}
        summary = self.service.summarize_capabilities_for_ui(1, combatant)

        actions = {a["id"]: a for a in summary["groups"]["actions"]}
        traits = {t["id"]: t for t in summary["groups"]["traits"]}

        # Rough Arrest is now a trait/reminder
        arrest = traits["rough-arrest"]
        self.assertIn("Manual/Assisted grapple action.", arrest["manual_instructions"])
        self.assertIn("Apply Grappled condition manually in /dm if hit.", arrest["manual_instructions"])

        # Baton has Rough Arrest rider
        baton = actions["baton"]
        riders = baton["mechanics"].get("riders", [])
        self.assertTrue(any(r["id"] == "rough-arrest" for r in riders))

if __name__ == "__main__":
    unittest.main()
