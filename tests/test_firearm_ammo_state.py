import unittest
import os
import sys
from typing import Dict, Any

# Ensure we can import from the root
sys.path.append(os.getcwd())

from dnd_initative_tracker import InitiativeTracker

class MockCombatant:
    def __init__(self, name, cid, monster_slug=None):
        self.name = name
        self.cid = cid
        self.monster_slug = monster_slug
        self.hp = 50
        self.max_hp = 50
        self.ac = 15
        self.speed = 30
        self.initiative = 10
        self.is_pc = False
        self.condition_stacks = []
        self.action_remaining = 1
        self.bonus_action_remaining = 1
        self.reaction_remaining = 1
        self.attack_resource_remaining = 1
        self.action_total = 1
        self.bonus_action_total = 1
        self.reaction_total = 1
        self.summon_requires_command = False
        self.summoned_by_cid = None

class TestFirearmAmmoState(unittest.TestCase):
    def setUp(self):
        self.app = InitiativeTracker()
        self.app.host_mode = "headless"

        # Add a Rifleman
        self.rifleman_cid = 1
        self.rifleman = MockCombatant("Rifleman 1", self.rifleman_cid, "black-and-tan-rifleman")
        self.app.combatants[self.rifleman_cid] = self.rifleman

        # Add a Pistol user (Constable)
        self.constable_cid = 2
        self.constable = MockCombatant("Constable 1", self.constable_cid, "black-and-tan-constable")
        self.app.combatants[self.constable_cid] = self.constable

    def test_ammo_initialization(self):
        # Trigger initialization by requesting capabilities summary
        svc = self.app._ensure_monster_capabilities()

        # Ensure ammo for Rifleman
        cap_rifle = {"id": "armalite-rifle", "mechanics": {"magazine_capacity": 20, "ammo_type": "5.56"}}
        self.app._monster_capability_ensure_resource_state(self.rifleman_cid, cap_rifle)

        self.assertEqual(self.app._monster_resource_state.get(f"{self.rifleman_cid}:ammo:armalite-rifle:current"), 20)
        self.assertEqual(self.app._monster_resource_state.get(f"{self.rifleman_cid}:ammo:5.56:reserve_mags"), 6)

        # Ensure ammo for Constable
        cap_pistol = {"id": "pistol", "mechanics": {"magazine_capacity": 8, "ammo_type": ".45"}}
        self.app._monster_capability_ensure_resource_state(self.constable_cid, cap_pistol)

        self.assertEqual(self.app._monster_resource_state.get(f"{self.constable_cid}:ammo:pistol:current"), 8)
        self.assertEqual(self.app._monster_resource_state.get(f"{self.constable_cid}:ammo:.45:reserve_mags"), 4)
    def test_ammo_spend_normal_attack(self):
        # Seed ammo
        self.app._monster_resource_state[f"{self.rifleman_cid}:ammo:armalite-rifle:current"] = 20

        # Execute normal attack (automatic)
        # We need a target
        target_cid = 10
        self.app.combatants[target_cid] = MockCombatant("Target", target_cid)

        payload = {
            "capability_id": "armalite-rifle",
            "target_cid": target_cid,
            "spend": "action"
        }

        # We need to mock _resolve_map_attack_sequence to avoid grid/dice dependency
        old_resolve = self.app._resolve_map_attack_sequence
        self.app._resolve_map_attack_sequence = lambda a, t, b: {"ok": True}

        self.app.round_num = 1
        self.app.turn_num = 1
        self.app.current_cid = self.rifleman_cid
        self.app.in_combat = True

        res = self.app._dm_monster_capability_execute(actor_cid=self.rifleman_cid, payload=payload)
        self.assertTrue(res.get("ok"))

        # Ammo should be 19
        self.assertEqual(self.app._monster_resource_state.get(f"{self.rifleman_cid}:ammo:armalite-rifle:current"), 19)

        self.app._resolve_map_attack_sequence = old_resolve

    def test_controlled_burst_spend(self):
        # Seed ammo
        self.app._monster_resource_state[f"{self.rifleman_cid}:ammo:armalite-rifle:current"] = 20

        # Arm Controlled Burst
        payload_cb = {"capability_id": "controlled-burst"}
        res_cb = self.app._dm_monster_capability_execute(actor_cid=self.rifleman_cid, payload=payload_cb)
        self.assertTrue(res_cb.get("ok"))
        self.assertIn("armed", res_cb.get("status", "").lower())

        # Ammo should still be 20
        self.assertEqual(self.app._monster_resource_state.get(f"{self.rifleman_cid}:ammo:armalite-rifle:current"), 20)

        # Execute attack
        target_cid = 10
        self.app.combatants[target_cid] = MockCombatant("Target", target_cid)
        payload_atk = {
            "capability_id": "armalite-rifle",
            "target_cid": target_cid,
            "spend": "action"
        }

        self.app._resolve_map_attack_sequence = lambda a, t, b: {"ok": True}

        res_atk = self.app._dm_monster_capability_execute(actor_cid=self.rifleman_cid, payload=payload_atk)
        self.assertTrue(res_atk.get("ok"))

        # Ammo should be 20 - 1 (normal) - 3 (burst) = 16
        # Wait, the plan says "Controlled Burst modified attack spends 3 rounds total."
        # My implementation does ammo_spent = 1 + mod_ammo_cost = 1 + 3 = 4.
        # If the plan says "3 rounds total", I should adjust.
        # "Controlled Burst ... spends 3 ammo" in YAML.
        # If I want it to be 3 total, then ammo_spent = mod_ammo_cost if present, else 1.
        # Let's check the implementation.
        # My implementation: ammo_spent = 1; ammo_spent += mod.get("ammo_cost")
        # If Controlled Burst says ammo_cost: 3, then it spends 4.
        # I'll update it to spend 3 total as requested.

        self.assertEqual(self.app._monster_resource_state.get(f"{self.rifleman_cid}:ammo:armalite-rifle:current"), 17) # If 1+2=3

    def test_controlled_burst_disarm(self):
        # Seed ammo
        self.app._monster_resource_state[f"{self.rifleman_cid}:ammo:armalite-rifle:current"] = 20

        # Arm
        self.app._dm_monster_capability_execute(actor_cid=self.rifleman_cid, payload={"capability_id": "controlled-burst"})
        self.assertEqual(len(self.app._monster_modifier_state.get(self.rifleman_cid, [])), 1)

        # Disarm (Toggle)
        res = self.app._dm_monster_capability_execute(actor_cid=self.rifleman_cid, payload={"capability_id": "controlled-burst"})
        self.assertTrue(res.get("ok"))
        self.assertIn("disarmed", res.get("status", "").lower())
        self.assertEqual(len(self.app._monster_modifier_state.get(self.rifleman_cid, [])), 0)

        # No ammo spent
        self.assertEqual(self.app._monster_resource_state.get(f"{self.rifleman_cid}:ammo:armalite-rifle:current"), 20)

    def test_reload(self):
        # Seed ammo
        self.app._monster_resource_state[f"{self.rifleman_cid}:ammo:armalite-rifle:current"] = 0
        self.app._monster_resource_state[f"{self.rifleman_cid}:ammo:5.56:reserve_mags"] = 6

        # Reload
        payload = {"capability_id": "reload"}
        res = self.app._dm_monster_capability_execute(actor_cid=self.rifleman_cid, payload=payload)
        self.assertTrue(res.get("ok"))

        # Ammo should be 20
        self.assertEqual(self.app._monster_resource_state.get(f"{self.rifleman_cid}:ammo:armalite-rifle:current"), 20)
        # Reserves should be 5
        self.assertEqual(self.app._monster_resource_state.get(f"{self.rifleman_cid}:ammo:5.56:reserve_mags"), 5)

    def test_insufficient_ammo_blocked(self):
        # Seed ammo
        self.app._monster_resource_state[f"{self.rifleman_cid}:ammo:armalite-rifle:current"] = 2

        # Arm Controlled Burst (needs 3)
        payload_cb = {"capability_id": "controlled-burst"}
        res_cb = self.app._dm_monster_capability_execute(actor_cid=self.rifleman_cid, payload=payload_cb)
        self.assertFalse(res_cb.get("ok"))
        self.assertIn("not enough ammo", res_cb.get("error", "").lower())

        # Try normal attack with 0 ammo
        self.app._monster_resource_state[f"{self.rifleman_cid}:ammo:armalite-rifle:current"] = 0
        payload_atk = {
            "capability_id": "armalite-rifle",
            "target_cid": 10,
            "spend": "action"
        }
        res_atk = self.app._dm_monster_capability_execute(actor_cid=self.rifleman_cid, payload=payload_atk)
        self.assertFalse(res_atk.get("ok"))
        self.assertIn("needs 1 ammo", res_atk.get("error", "").lower())

    def test_controlled_burst_damage_bonus(self):
        # Seed ammo
        self.app._monster_resource_state[f"{self.rifleman_cid}:ammo:armalite-rifle:current"] = 20

        # Arm
        self.app._dm_monster_capability_execute(actor_cid=self.rifleman_cid, payload={"capability_id": "controlled-burst"})

        # Execute attack (mocked hit)
        target_cid = 10
        self.app.combatants[target_cid] = MockCombatant("Target", target_cid)

        # We need a real-ish sequence resolution to see damage rolls
        # But we mock randint for hit
        import unittest.mock as mock
        with mock.patch("random.randint", return_value=10):
            payload = {
                "capability_id": "armalite-rifle",
                "target_cid": target_cid,
                "spend": "action"
            }
            res = self.app._dm_monster_capability_execute(actor_cid=self.rifleman_cid, payload=payload)
            self.assertTrue(res.get("ok"))

            # Check damage rolls (automatic path returns damage_rolls)
            damage_rolls = res.get("damage_rolls", [])
            # Should be 1d12+4 (base) and 1d12 (burst)
            # Actually, _resolve_map_attack_sequence aggregates them if possible?
            # No, it returns a list.
            self.assertEqual(len(damage_rolls), 2)

    def test_controlled_burst_jam_on_nat1(self):
        # Seed ammo
        self.app._monster_resource_state[f"{self.rifleman_cid}:ammo:armalite-rifle:current"] = 20

        # Arm
        self.app._dm_monster_capability_execute(actor_cid=self.rifleman_cid, payload={"capability_id": "controlled-burst"})

        # Execute attack with nat 1
        target_cid = 10
        self.app.combatants[target_cid] = MockCombatant("Target", target_cid)

        import unittest.mock as mock
        with mock.patch("random.randint", return_value=1):
            payload = {
                "capability_id": "armalite-rifle",
                "target_cid": target_cid,
                "spend": "action"
            }
            res = self.app._dm_monster_capability_execute(actor_cid=self.rifleman_cid, payload=payload)
            self.assertTrue(res.get("ok"))

            # Should be jammed
            self.assertTrue(self.app._monster_resource_state.get(f"{self.rifleman_cid}:jammed:armalite-rifle"))

    def test_controlled_burst_once_per_turn_consumption(self):
        # Seed ammo
        self.app._monster_resource_state[f"{self.rifleman_cid}:ammo:armalite-rifle:current"] = 20

        # Arm
        self.app._dm_monster_capability_execute(actor_cid=self.rifleman_cid, payload={"capability_id": "controlled-burst"})

        # Execute attack (automatic)
        target_cid = 10
        self.app.combatants[target_cid] = MockCombatant("Target", target_cid)
        self.app._resolve_map_attack_sequence = lambda a, t, b: {"ok": True}

        self.app._dm_monster_capability_execute(actor_cid=self.rifleman_cid, payload={"capability_id": "armalite-rifle", "target_cid": target_cid})

        # Should be marked used
        self.assertTrue(self.app._monster_resource_state.get(f"{self.rifleman_cid}:mod_used:controlled-burst"))

        # Arming again should fail
        res = self.app._dm_monster_capability_execute(actor_cid=self.rifleman_cid, payload={"capability_id": "controlled-burst"})
        self.assertFalse(res.get("ok"))
        self.assertIn("already used", res.get("error", "").lower())

if __name__ == "__main__":
    unittest.main()
