import unittest
import random
from unittest import mock
import dnd_initative_tracker as tracker_mod
from monster_capability_service import MonsterCapabilityService

class TestMonsterCapabilityBackend(unittest.TestCase):
    def setUp(self):
        self.app = object.__new__(tracker_mod.InitiativeTracker)
        self.app.__dict__.update({
            "combatants": {
                1: mock.Mock(cid=1, monster_slug="adult-red-dragon", is_pc=False, hp=256),
                2: mock.Mock(cid=2, is_pc=True, hp=100, temp_hp=0),
                3: mock.Mock(cid=3, is_pc=True, hp=80, temp_hp=0)
            },
            "_name_role_memory": {"Dragon": "enemy", "Hero": "pc"},
            "_monster_resource_state": {},
            "active_cid": 1,
            "CONDITIONS_META": {"frightened": {"label": "Frightened"}, "prone": {"label": "Prone"}}
        })
        self.app.combatants[1].name = "Dragon"
        self.app.combatants[2].name = "Hero"
        self.app.combatants[3].name = "Rogue"

        # Mock methods
        self.app._dm_validate_monster_actor_for_turn = lambda cid: (self.app.combatants.get(cid), None, cid)
        self.app._ensure_monster_capabilities = lambda: MonsterCapabilityService()
        self.app._roll_monster_attack_formula = lambda f, critical=False: 10
        self.app._dm_normalize_turn_spend = lambda s, **kwargs: s
        self.app._lan_force_state_broadcast = lambda: None
        self.app._oplog = lambda m: None
        self.applied_conditions = []
        self.removed_conditions = []
        self.applied_damage = []
        self.app._ensure_condition_stack = lambda c, ctype, turns: self.applied_conditions.append((getattr(c, "cid", None), ctype, turns))
        self.app._remove_condition_type = lambda c, ctype: None
        self.app._apply_map_attack_manual_damage = self._apply_damage

    def _apply_damage(self, attacker_cid, target_cid, attack_name, damage_entries):
        total = sum(int(entry.get("amount") or 0) for entry in damage_entries)
        target = self.app.combatants[int(target_cid)]
        target.hp = max(0, int(getattr(target, "hp", 0) or 0) - total)
        result = {
            "ok": True,
            "attacker_cid": int(attacker_cid),
            "target_cid": int(target_cid),
            "attack_name": attack_name,
            "total_damage": total,
            "target_hp": target.hp,
            "target_removed": False,
        }
        self.applied_damage.append(result)
        return result

    def test_recharge_roll_success(self):
        with mock.patch("random.randint", return_value=6):
            result = self.app._dm_monster_capability_roll_recharge(cid=1, capability_id="fire-breath")
            self.assertTrue(result["ok"])
            self.assertTrue(result["success"])
            self.assertEqual(result["roll"], 6)
            self.assertTrue(self.app._monster_resource_state.get("1:cap:fire-breath"))

    def test_recharge_roll_failure(self):
        with mock.patch("random.randint", return_value=1):
            result = self.app._dm_monster_capability_roll_recharge(cid=1, capability_id="fire-breath")
            self.assertTrue(result["ok"])
            self.assertFalse(result["success"])
            self.assertFalse(self.app._monster_resource_state.get("1:cap:fire-breath", False))

    def test_execute_save_ability_assisted(self):
        payload = {
            "capability_id": "fire-breath",
            "target_cid": 2,
            "spend": "action"
        }
        # Fire breath is recharge 5
        self.app._monster_resource_state["1:cap:fire-breath"] = True

        result = self.app._dm_monster_capability_execute(actor_cid=1, payload=payload)
        self.assertTrue(result["ok"])
        self.assertEqual(result["resolution"], "assisted")
        self.assertEqual(result["save_dc"], 21)
        self.assertEqual(result["target_name"], "Hero")
        self.assertIn("damage_rolls", result)
        self.assertIn("resolution_packet", result)
        self.assertTrue(result["multi_target_capable"])
        self.assertEqual(result["area"]["shape"], "cone")
        self.assertEqual(result["resolution_packet"]["total_success"], 5)
        # Should be marked as used
        self.assertFalse(self.app._monster_resource_state["1:cap:fire-breath"])

    def test_resolve_targets_rejects_missing_capability(self):
        result = self.app._dm_monster_capability_resolve_targets(
            actor_cid=1,
            payload={
                "capability_id": "missing",
                "targets": [{"target_cid": 2, "outcome": "fail"}],
            },
        )
        self.assertFalse(result["ok"])
        self.assertIn("not found", result["error"])

    def test_resolve_targets_rejects_invalid_target(self):
        result = self.app._dm_monster_capability_resolve_targets(
            actor_cid=1,
            payload={
                "capability_id": "fire-breath",
                "targets": [{"target_cid": 999, "outcome": "fail"}],
            },
        )
        self.assertFalse(result["ok"])
        self.assertIn("not found", result["error"])

    def test_resolve_targets_multiple_outcomes_without_implicit_application(self):
        result = self.app._dm_monster_capability_resolve_targets(
            actor_cid=1,
            payload={
                "capability_id": "fire-breath",
                "targets": [
                    {"target_cid": 2, "outcome": "fail"},
                    {"target_cid": 3, "outcome": "success"},
                    {"target_cid": 1, "outcome": "no_effect"},
                ],
                "damage_rolls": [{"type": "fire", "rolled": 18, "rolled_success": 9}],
            },
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["target_count"], 3)
        self.assertEqual(len(self.applied_damage), 0)
        self.assertEqual(self.app.combatants[2].hp, 100)
        self.assertEqual(self.app.combatants[3].hp, 80)

    def test_resolve_targets_apply_damage_explicitly(self):
        result = self.app._dm_monster_capability_resolve_targets(
            actor_cid=1,
            payload={
                "capability_id": "fire-breath",
                "targets": [
                    {"target_cid": 2, "outcome": "fail"},
                    {"target_cid": 3, "outcome": "success"},
                    {"target_cid": 1, "outcome": "no_effect"},
                ],
                "damage_rolls": [{"type": "fire", "rolled": 18, "rolled_success": 9}],
                "apply_damage": True,
            },
        )
        self.assertTrue(result["ok"])
        self.assertEqual(self.app.combatants[2].hp, 82)
        self.assertEqual(self.app.combatants[3].hp, 71)
        self.assertEqual(len(self.applied_damage), 2)

    def test_resolve_targets_apply_effects_explicitly(self):
        result = self.app._dm_monster_capability_resolve_targets(
            actor_cid=1,
            payload={
                "capability_id": "frightful-presence",
                "targets": [
                    {"target_cid": 2, "outcome": "fail"},
                    {"target_cid": 3, "outcome": "success"},
                ],
                "apply_effects": True,
            },
        )
        self.assertTrue(result["ok"])
        self.assertEqual(self.applied_conditions, [(2, "frightened", None)])

    def test_resolve_targets_wing_attack_damage_and_prone(self):
        result = self.app._dm_monster_capability_resolve_targets(
            actor_cid=1,
            payload={
                "capability_id": "wing-attack-(costs-2-actions)",
                "targets": [{"target_cid": 2, "outcome": "fail"}],
                "damage_rolls": [{"type": "bludgeoning", "rolled": 15, "rolled_success": 0}],
                "apply_damage": True,
                "apply_effects": True,
            },
        )
        self.assertTrue(result["ok"])
        self.assertEqual(self.app.combatants[2].hp, 85)
        self.assertEqual(self.applied_conditions, [(2, "prone", None)])

    def test_execute_recharge_not_ready(self):
        payload = {
            "capability_id": "fire-breath",
            "target_cid": 2
        }
        self.app._monster_resource_state["1:cap:fire-breath"] = False

        result = self.app._dm_monster_capability_execute(actor_cid=1, payload=payload)
        self.assertFalse(result["ok"])
        self.assertIn("not recharged", result["error"])

    def test_resource_op_mark_used_recharge(self):
        self.app._monster_resource_state["1:cap:fire-breath"] = True
        payload = {"capability_id": "fire-breath", "operation": "mark_used"}
        result = self.app._dm_monster_capability_resource_op(cid=1, payload=payload)
        self.assertTrue(result["ok"])
        self.assertFalse(self.app._monster_resource_state["1:cap:fire-breath"])

    def test_resource_op_mark_used_slots(self):
        # Archmage has 3 slots at level 3
        self.app.combatants[1].monster_slug = "archmage"
        payload = {
            "capability_id": "spellcasting",
            "operation": "mark_used",
            "slot_level": 3
        }
        # Initialize
        self.app._monster_resource_state["1:slot:3"] = 3
        result = self.app._dm_monster_capability_resource_op(cid=1, payload=payload)
        self.assertTrue(result["ok"])
        self.assertEqual(self.app._monster_resource_state["1:slot:3"], 2)

    def test_resource_op_restore_all(self):
        self.app._monster_resource_state["1:cap:fire-breath"] = False
        self.app._monster_resource_state["1:slot:3"] = 0
        payload = {"operation": "restore_all"}
        result = self.app._dm_monster_capability_resource_op(cid=1, payload=payload)
        self.assertTrue(result["ok"])
        self.assertNotIn("1:cap:fire-breath", self.app._monster_resource_state)

    def test_execute_composite_assisted_sequence(self):
        payload = {
            "capability_id": "multiattack"
        }
        result = self.app._dm_monster_capability_execute(actor_cid=1, payload=payload)
        self.assertTrue(result["ok"])
        self.assertEqual(result["resolution"], "assisted_sequence")
        self.assertIn("steps", result)
        self.assertGreaterEqual(len(result["steps"]), 2)

        # Check bite step
        bite_step = next((s for s in result["steps"] if s["action_id"] == "bite"), None)
        self.assertIsNotNone(bite_step)
        self.assertTrue(bite_step["executable"])

    def test_apply_remove_effect(self):
        # Adult Red Dragon Frightful Presence has frightened effect
        payload = {
            "capability_id": "frightful-presence",
            "effect_index": 0,
            "target_cid": 2
        }
        
        # 1. Apply
        result = self.app._dm_monster_capability_effect_change(actor_cid=1, payload=payload, action="apply")
        self.assertTrue(result["ok"])
        self.assertEqual(result["condition"], "frightened")
        
        # Verify condition was applied (using mock or real state check if practical)
        # Our setUp mocks _ensure_condition_stack if we want, but here we can check the call
        # Actually setUp didn't mock it, but IniciativeTracker has it.
        # Let's mock it in setUp if it's missing or check if we can use real one.
        # For now, let's just assert ok and that it didn't crash.

        # 2. Remove
        result = self.app._dm_monster_capability_effect_change(actor_cid=1, payload=payload, action="remove")
        self.assertTrue(result["ok"])
        self.assertEqual(result["condition"], "frightened")

    def test_apply_effect_invalid_index(self):
        payload = {
            "capability_id": "frightful-presence",
            "effect_index": 99,
            "target_cid": 2
        }
        result = self.app._dm_monster_capability_effect_change(actor_cid=1, payload=payload, action="apply")
        self.assertFalse(result["ok"])
        self.assertIn("out of range", result["error"])

    def test_execute_spellcasting_assisted(self):
        # Archmage spellcasting
        self.app.combatants[1].monster_slug = "archmage"
        payload = {
            "capability_id": "spellcasting",
            "spell_slug": "lightning-bolt",
            "target_cid": 2
        }
        result = self.app._dm_monster_capability_execute(actor_cid=1, payload=payload)
        self.assertTrue(result["ok"])
        self.assertEqual(result["resolution"], "assisted_spell")
        self.assertEqual(result["spell_slug"], "lightning-bolt")
        self.assertEqual(result["save_dc"], 17)
        self.assertEqual(result["save_ability"], "dexterity")

    def test_dm_ui_contains_multi_target_hooks(self):
        with open("assets/web/dm/index.html", "r", encoding="utf-8") as handle:
            html = handle.read()
        self.assertIn("monster-cap-target-checkbox", html)
        self.assertIn("resolve-targets", html)
        self.assertIn("Apply Damage + Effects", html)

if __name__ == "__main__":
    unittest.main()
