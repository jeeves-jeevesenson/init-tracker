"""Tests for the CombatService canonical backend seam.

These tests validate that the service layer correctly reads and mutates
combat state, and that state propagates properly through the service
without requiring the Tkinter UI to be running.
"""
import types
import unittest

from combat_service import CombatService


def _make_tracker(num_combatants: int = 3):
    """Build a minimal fake InitiativeTracker-like namespace for testing."""
    app = types.SimpleNamespace()
    app.combatants = {}
    app.current_cid = None
    app.round_num = 1
    app.turn_num = 0
    app.in_combat = True
    app._next_stack_id = 1
    app._name_role_memory = {}

    app._log_calls = []
    app._rebuild_calls = []
    app._broadcast_calls = []
    app._next_turn_calls = []

    def _log(msg, cid=None):
        app._log_calls.append((msg, cid))

    def _rebuild_table(scroll_to_current=False):
        app._rebuild_calls.append(scroll_to_current)

    def _lan_force_state_broadcast():
        app._broadcast_calls.append(1)

    def _next_turn():
        app._next_turn_calls.append(1)
        # Advance current_cid to next in order
        ids = sorted(app.combatants.keys())
        if not ids:
            return
        if app.current_cid is None or app.current_cid not in ids:
            app.current_cid = ids[0]
            return
        idx = ids.index(app.current_cid)
        wrapped = (idx + 1) >= len(ids)
        app.current_cid = ids[(idx + 1) % len(ids)]
        if wrapped:
            app.round_num += 1
        app.turn_num += 1

    def _display_order():
        return [app.combatants[k] for k in sorted(app.combatants.keys())]

    def _ensure_condition_stack(c, ctype, remaining_turns):
        from helper_script import ConditionStack
        for st in getattr(c, "condition_stacks", []):
            if st.ctype == ctype:
                st.remaining_turns = remaining_turns
                return
        sid = int(getattr(app, "_next_stack_id", 1) or 1)
        app._next_stack_id = sid + 1
        c.condition_stacks.append(ConditionStack(sid=sid, ctype=ctype, remaining_turns=remaining_turns))

    def _remove_condition_type(c, ctype):
        c.condition_stacks = [st for st in c.condition_stacks if st.ctype != ctype]

    def _lan_battle_log_lines(limit=200):
        return ["Turn 1 started", "Goblin attacked Fighter"]

    app._log = _log
    app._rebuild_table = _rebuild_table
    app._lan_force_state_broadcast = _lan_force_state_broadcast
    app._next_turn = _next_turn
    app._display_order = _display_order
    app._ensure_condition_stack = _ensure_condition_stack
    app._remove_condition_type = _remove_condition_type
    app._lan_battle_log_lines = _lan_battle_log_lines

    # Populate combatants
    from helper_script import ConditionStack
    names = ["Fighter", "Goblin", "Wizard"]
    for i in range(num_combatants):
        cid = i + 1
        c = types.SimpleNamespace(
            cid=cid,
            name=names[i % len(names)],
            hp=20 + i * 5,
            max_hp=20 + i * 5,
            temp_hp=0,
            ac=14 + i,
            initiative=20 - i * 3,
            is_pc=(i == 0),
            condition_stacks=[],
        )
        app.combatants[cid] = c

    app.current_cid = 1
    return app


class CombatServiceSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.tracker = _make_tracker()
        self.service = CombatService(self.tracker)

    def test_snapshot_returns_dict(self):
        snap = self.service.combat_snapshot()
        self.assertIsInstance(snap, dict)

    def test_snapshot_has_required_keys(self):
        snap = self.service.combat_snapshot()
        for key in ("in_combat", "round", "turn", "active_cid", "turn_order", "combatants", "battle_log"):
            self.assertIn(key, snap, f"Missing key: {key}")

    def test_snapshot_combatants_count(self):
        snap = self.service.combat_snapshot()
        self.assertEqual(len(snap["combatants"]), 3)

    def test_snapshot_active_cid(self):
        snap = self.service.combat_snapshot()
        self.assertEqual(snap["active_cid"], 1)

    def test_snapshot_combatant_fields(self):
        snap = self.service.combat_snapshot()
        c = snap["combatants"][0]
        for field in ("cid", "name", "hp", "max_hp", "temp_hp", "ac", "initiative", "is_pc", "role", "conditions", "is_current"):
            self.assertIn(field, c, f"Missing combatant field: {field}")

    def test_snapshot_current_combatant_flagged(self):
        snap = self.service.combat_snapshot()
        current = [c for c in snap["combatants"] if c["is_current"]]
        self.assertEqual(len(current), 1)
        self.assertEqual(current[0]["cid"], 1)

    def test_snapshot_turn_order(self):
        snap = self.service.combat_snapshot()
        self.assertIsInstance(snap["turn_order"], list)
        self.assertEqual(len(snap["turn_order"]), 3)

    def test_snapshot_battle_log(self):
        snap = self.service.combat_snapshot()
        self.assertIsInstance(snap["battle_log"], list)
        self.assertGreater(len(snap["battle_log"]), 0)

    def test_snapshot_round_and_turn(self):
        snap = self.service.combat_snapshot()
        self.assertEqual(snap["round"], 1)
        self.assertEqual(snap["turn"], 0)

    def test_requires_tracker(self):
        with self.assertRaises(ValueError):
            CombatService(None)


class CombatServiceNextTurnTests(unittest.TestCase):
    def setUp(self):
        self.tracker = _make_tracker()
        self.service = CombatService(self.tracker)

    def test_next_turn_returns_ok(self):
        result = self.service.next_turn()
        self.assertTrue(result["ok"])

    def test_next_turn_advances_cid(self):
        old_cid = self.tracker.current_cid
        self.service.next_turn()
        self.assertNotEqual(self.tracker.current_cid, old_cid)

    def test_next_turn_calls_broadcast(self):
        self.service.next_turn()
        self.assertGreater(len(self.tracker._broadcast_calls), 0)

    def test_next_turn_snapshot_in_result(self):
        result = self.service.next_turn()
        self.assertIn("snapshot", result)
        snap = result["snapshot"]
        self.assertIn("combatants", snap)

    def test_next_turn_wraps_round(self):
        # Advance through all 3 combatants to wrap round
        self.service.next_turn()
        self.service.next_turn()
        self.service.next_turn()
        self.assertGreater(self.tracker.round_num, 1)


class CombatServiceAdjustHpTests(unittest.TestCase):
    def setUp(self):
        self.tracker = _make_tracker()
        self.service = CombatService(self.tracker)

    def test_damage_reduces_hp(self):
        c = self.tracker.combatants[1]
        initial_hp = c.hp
        result = self.service.adjust_hp(cid=1, delta=-5)
        self.assertTrue(result["ok"])
        self.assertEqual(result["hp_after"], initial_hp - 5)
        self.assertEqual(c.hp, initial_hp - 5)

    def test_heal_increases_hp(self):
        c = self.tracker.combatants[1]
        c.hp = 10
        result = self.service.adjust_hp(cid=1, delta=5)
        self.assertTrue(result["ok"])
        self.assertEqual(result["hp_after"], 15)

    def test_hp_clamped_to_zero(self):
        c = self.tracker.combatants[1]
        result = self.service.adjust_hp(cid=1, delta=-9999)
        self.assertTrue(result["ok"])
        self.assertEqual(result["hp_after"], 0)
        self.assertEqual(c.hp, 0)

    def test_hp_clamped_to_max(self):
        c = self.tracker.combatants[1]
        c.hp = 5
        result = self.service.adjust_hp(cid=1, delta=9999)
        self.assertTrue(result["ok"])
        self.assertEqual(result["hp_after"], c.max_hp)

    def test_unknown_cid_returns_error(self):
        result = self.service.adjust_hp(cid=999, delta=-5)
        self.assertFalse(result["ok"])
        self.assertIn("error", result)

    def test_adjust_hp_triggers_broadcast(self):
        self.service.adjust_hp(cid=1, delta=-3)
        self.assertGreater(len(self.tracker._broadcast_calls), 0)

    def test_adjust_hp_result_has_delta(self):
        result = self.service.adjust_hp(cid=1, delta=-7)
        self.assertEqual(result["delta"], -7)


class CombatServiceConditionTests(unittest.TestCase):
    def setUp(self):
        self.tracker = _make_tracker()
        self.service = CombatService(self.tracker)

    def test_add_condition(self):
        result = self.service.set_condition(cid=1, ctype="poisoned", action="add")
        self.assertTrue(result["ok"])
        c = self.tracker.combatants[1]
        ctypes = [st.ctype for st in c.condition_stacks]
        self.assertIn("poisoned", ctypes)

    def test_remove_condition(self):
        from helper_script import ConditionStack
        c = self.tracker.combatants[1]
        c.condition_stacks.append(ConditionStack(sid=99, ctype="stunned", remaining_turns=None))
        result = self.service.set_condition(cid=1, ctype="stunned", action="remove")
        self.assertTrue(result["ok"])
        ctypes = [st.ctype for st in c.condition_stacks]
        self.assertNotIn("stunned", ctypes)

    def test_add_condition_with_duration(self):
        result = self.service.set_condition(cid=2, ctype="blinded", action="add", remaining_turns=3)
        self.assertTrue(result["ok"])
        c = self.tracker.combatants[2]
        matching = [st for st in c.condition_stacks if st.ctype == "blinded"]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0].remaining_turns, 3)

    def test_unknown_cid_returns_error(self):
        result = self.service.set_condition(cid=999, ctype="prone", action="add")
        self.assertFalse(result["ok"])

    def test_empty_ctype_returns_error(self):
        result = self.service.set_condition(cid=1, ctype="", action="add")
        self.assertFalse(result["ok"])

    def test_invalid_action_returns_error(self):
        result = self.service.set_condition(cid=1, ctype="prone", action="toggle")
        self.assertFalse(result["ok"])

    def test_condition_triggers_broadcast(self):
        self.service.set_condition(cid=1, ctype="prone", action="add")
        self.assertGreater(len(self.tracker._broadcast_calls), 0)

    def test_condition_appears_in_snapshot(self):
        self.service.set_condition(cid=1, ctype="frightened", action="add")
        snap = self.service.combat_snapshot()
        c_row = next(c for c in snap["combatants"] if c["cid"] == 1)
        ctypes = [cond["type"] for cond in c_row["conditions"]]
        self.assertIn("frightened", ctypes)

    def test_remove_condition_disappears_from_snapshot(self):
        self.service.set_condition(cid=1, ctype="frightened", action="add")
        self.service.set_condition(cid=1, ctype="frightened", action="remove")
        snap = self.service.combat_snapshot()
        c_row = next(c for c in snap["combatants"] if c["cid"] == 1)
        ctypes = [cond["type"] for cond in c_row["conditions"]]
        self.assertNotIn("frightened", ctypes)


if __name__ == "__main__":
    unittest.main()
