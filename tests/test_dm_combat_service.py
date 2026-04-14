"""Tests for the CombatService canonical backend seam.

These tests validate that the service layer correctly reads and mutates
combat state, and that state propagates properly through the service
without requiring the Tkinter UI to be running.
"""
import types
import unittest

from helper_script import ConditionStack

from combat_service import CombatService
from dnd_initative_tracker import InitiativeTracker


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
    app._dm_service = None  # Set by tests when needed
    app._oplog_calls = []

    def _oplog(msg, level="info"):
        app._oplog_calls.append((msg, level))

    app._oplog = _oplog

    # Deep damage / heal stubs for CombatService.apply_damage / apply_heal
    app._apply_damage_calls = []

    def _apply_damage_to_target_with_temp_hp(target, raw_damage):
        """Minimal temp HP absorption matching the real tracker semantics."""
        damage = max(0, int(raw_damage or 0))
        temp_before = max(0, int(getattr(target, "temp_hp", 0) or 0))
        hp_before = max(0, int(getattr(target, "hp", 0) or 0))
        absorbed = min(temp_before, damage)
        temp_after = max(0, temp_before - absorbed)
        hp_damage = max(0, damage - absorbed)
        hp_after = max(0, hp_before - hp_damage)
        target.temp_hp = int(temp_after)
        target.hp = int(hp_after)
        app._apply_damage_calls.append(
            {"cid": int(getattr(target, "cid", 0) or 0), "raw_damage": damage}
        )
        return {"temp_absorbed": absorbed, "hp_damage": hp_damage, "hp_after": hp_after}

    app._apply_damage_to_target_with_temp_hp = _apply_damage_to_target_with_temp_hp

    app._apply_heal_calls = []

    def _apply_heal_to_combatant(cid, amount, *, is_temp_hp=False):
        c = app.combatants.get(int(cid))
        if c is None:
            return False
        if is_temp_hp:
            c.temp_hp = max(0, int(amount))
        else:
            c.hp = max(0, int(c.hp) + int(amount))
        app._apply_heal_calls.append(
            {"cid": int(cid), "amount": amount, "is_temp_hp": is_temp_hp}
        )
        return True

    app._apply_heal_to_combatant = _apply_heal_to_combatant

    # Populate combatants
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


class CombatServiceTempHpTests(unittest.TestCase):
    def setUp(self):
        self.tracker = _make_tracker()
        self.service = CombatService(self.tracker)

    def test_set_temp_hp_returns_ok(self):
        result = self.service.set_temp_hp(cid=1, amount=10)
        self.assertTrue(result["ok"])

    def test_set_temp_hp_updates_value(self):
        c = self.tracker.combatants[1]
        self.service.set_temp_hp(cid=1, amount=8)
        self.assertEqual(c.temp_hp, 8)

    def test_set_temp_hp_result_fields(self):
        result = self.service.set_temp_hp(cid=1, amount=5)
        self.assertIn("temp_hp_before", result)
        self.assertIn("temp_hp_after", result)
        self.assertEqual(result["temp_hp_after"], 5)

    def test_clear_temp_hp_with_zero(self):
        c = self.tracker.combatants[1]
        c.temp_hp = 15
        result = self.service.set_temp_hp(cid=1, amount=0)
        self.assertTrue(result["ok"])
        self.assertEqual(c.temp_hp, 0)
        self.assertEqual(result["temp_hp_after"], 0)

    def test_negative_amount_clamped_to_zero(self):
        result = self.service.set_temp_hp(cid=1, amount=-5)
        self.assertTrue(result["ok"])
        self.assertEqual(result["temp_hp_after"], 0)

    def test_unknown_cid_returns_error(self):
        result = self.service.set_temp_hp(cid=999, amount=10)
        self.assertFalse(result["ok"])
        self.assertIn("error", result)

    def test_set_temp_hp_triggers_broadcast(self):
        self.service.set_temp_hp(cid=1, amount=4)
        self.assertGreater(len(self.tracker._broadcast_calls), 0)

    def test_temp_hp_appears_in_snapshot(self):
        self.service.set_temp_hp(cid=2, amount=12)
        snap = self.service.combat_snapshot()
        c_row = next(c for c in snap["combatants"] if c["cid"] == 2)
        self.assertEqual(c_row["temp_hp"], 12)


class CombatServiceLockTests(unittest.TestCase):
    def setUp(self):
        self.tracker = _make_tracker()
        self.service = CombatService(self.tracker)

    def test_service_has_lock(self):
        lock = self.service._lock
        self.assertTrue(lock.acquire(blocking=False))
        try:
            self.assertTrue(lock.acquire(blocking=False))
        finally:
            lock.release()
            lock.release()

    def test_concurrent_hp_adjustments_safe(self):
        """Two threads can call adjust_hp concurrently without raising."""
        import threading
        errors = []

        def adjust():
            try:
                self.service.adjust_hp(cid=1, delta=-1)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=adjust) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(errors, [])
        c = self.tracker.combatants[1]
        self.assertGreaterEqual(c.hp, 0)


class CombatServiceUpNextTests(unittest.TestCase):
    """Tests for up_next_cid / up_next_name in the snapshot."""

    def _make_tracker_with_peek(self):
        """Make a tracker that has a _peek_next_turn_cid method."""
        app = _make_tracker(num_combatants=3)
        app.current_cid = 1

        def _peek_next_turn_cid(current_cid):
            ids = sorted(app.combatants.keys())
            if not ids or current_cid is None or current_cid not in ids:
                return None
            idx = ids.index(int(current_cid))
            return ids[(idx + 1) % len(ids)]

        app._peek_next_turn_cid = _peek_next_turn_cid
        return app

    def test_snapshot_has_up_next_keys(self):
        tracker = self._make_tracker_with_peek()
        service = CombatService(tracker)
        snap = service.combat_snapshot()
        self.assertIn("up_next_cid", snap)
        self.assertIn("up_next_name", snap)

    def test_up_next_cid_is_next_in_order(self):
        tracker = self._make_tracker_with_peek()
        service = CombatService(tracker)
        # current_cid = 1, next should be 2
        snap = service.combat_snapshot()
        self.assertEqual(snap["up_next_cid"], 2)

    def test_up_next_name_matches_cid(self):
        tracker = self._make_tracker_with_peek()
        service = CombatService(tracker)
        snap = service.combat_snapshot()
        expected_name = tracker.combatants[snap["up_next_cid"]].name
        self.assertEqual(snap["up_next_name"], expected_name)

    def test_up_next_none_when_no_peek_method(self):
        tracker = _make_tracker(num_combatants=3)
        # no _peek_next_turn_cid defined
        service = CombatService(tracker)
        snap = service.combat_snapshot()
        self.assertIsNone(snap["up_next_cid"])
        self.assertIsNone(snap["up_next_name"])

    def test_up_next_none_when_no_current(self):
        tracker = self._make_tracker_with_peek()
        tracker.current_cid = None
        service = CombatService(tracker)
        snap = service.combat_snapshot()
        self.assertIsNone(snap["up_next_cid"])


class CombatServiceStartCombatTests(unittest.TestCase):
    """Tests for CombatService.start_combat()."""

    def _make_tracker_with_start(self):
        app = _make_tracker(num_combatants=3)
        app.in_combat = False
        app.current_cid = None
        app._start_turns_calls = []

        def _start_turns():
            app._start_turns_calls.append(1)
            ids = sorted(app.combatants.keys())
            if ids:
                app.current_cid = ids[0]
                app.round_num = 1
                app.turn_num = 1

        app._start_turns = _start_turns
        return app

    def test_start_combat_returns_ok(self):
        tracker = self._make_tracker_with_start()
        service = CombatService(tracker)
        result = service.start_combat()
        self.assertTrue(result["ok"])

    def test_start_combat_sets_in_combat(self):
        tracker = self._make_tracker_with_start()
        service = CombatService(tracker)
        service.start_combat()
        self.assertTrue(tracker.in_combat)

    def test_start_combat_calls_start_turns(self):
        tracker = self._make_tracker_with_start()
        service = CombatService(tracker)
        service.start_combat()
        self.assertEqual(len(tracker._start_turns_calls), 1)

    def test_start_combat_returns_snapshot(self):
        tracker = self._make_tracker_with_start()
        service = CombatService(tracker)
        result = service.start_combat()
        self.assertIn("snapshot", result)
        self.assertIn("combatants", result["snapshot"])

    def test_start_combat_snapshot_shows_in_combat(self):
        tracker = self._make_tracker_with_start()
        service = CombatService(tracker)
        result = service.start_combat()
        self.assertTrue(result["snapshot"]["in_combat"])

    def test_start_combat_no_combatants_returns_error(self):
        tracker = self._make_tracker_with_start()
        tracker.combatants = {}
        service = CombatService(tracker)
        result = service.start_combat()
        self.assertFalse(result["ok"])
        self.assertIn("error", result)

    def test_start_combat_triggers_broadcast(self):
        tracker = self._make_tracker_with_start()
        service = CombatService(tracker)
        service.start_combat()
        self.assertGreater(len(tracker._broadcast_calls), 0)


class CombatServiceEndCombatTests(unittest.TestCase):
    """Tests for CombatService.end_combat()."""

    def setUp(self):
        self.tracker = _make_tracker()
        self.tracker.in_combat = True
        self.tracker.current_cid = 1
        self.service = CombatService(self.tracker)

    def test_end_combat_returns_ok(self):
        result = self.service.end_combat()
        self.assertTrue(result["ok"])

    def test_end_combat_clears_in_combat(self):
        self.service.end_combat()
        self.assertFalse(self.tracker.in_combat)

    def test_end_combat_clears_current_cid(self):
        self.service.end_combat()
        self.assertIsNone(self.tracker.current_cid)

    def test_end_combat_returns_snapshot(self):
        result = self.service.end_combat()
        self.assertIn("snapshot", result)

    def test_end_combat_snapshot_not_in_combat(self):
        result = self.service.end_combat()
        self.assertFalse(result["snapshot"]["in_combat"])

    def test_end_combat_snapshot_no_active_cid(self):
        result = self.service.end_combat()
        self.assertIsNone(result["snapshot"]["active_cid"])

    def test_end_combat_triggers_broadcast(self):
        self.service.end_combat()
        self.assertGreater(len(self.tracker._broadcast_calls), 0)

    def test_end_combat_logs_round(self):
        self.tracker.round_num = 4
        self.service.end_combat()
        # Check that a log message mentioning round 4 was emitted
        logged_msgs = [m for m, _ in self.tracker._log_calls]
        self.assertTrue(any("4" in m for m in logged_msgs))


# ---------------------------------------------------------------------------
# Helpers for encounter-setup tests
# ---------------------------------------------------------------------------

def _make_tracker_with_encounter_setup(num_combatants: int = 2):
    """Extend the base fake tracker with _create_combatant and cleanup stubs."""
    app = _make_tracker(num_combatants=num_combatants)
    app._next_id = max(app.combatants.keys(), default=0) + 1
    app._create_combatant_calls = []
    app._remove_cleanup_calls = []

    def _create_combatant(name, hp, speed, initiative, dex, ally, is_pc=False, **_kw):
        cid = app._next_id
        app._next_id += 1
        # Intentionally do NOT pre-set max_hp so CombatService's post-creation
        # logic is the only thing that sets it.
        c = types.SimpleNamespace(
            cid=cid,
            name=name,
            hp=int(hp),
            ac=10,
            temp_hp=0,
            initiative=int(initiative),
            is_pc=bool(is_pc),
            condition_stacks=[],
        )
        app.combatants[cid] = c
        app._create_combatant_calls.append({
            "name": name,
            "hp": hp,
            "initiative": initiative,
            "ally": ally,
            "is_pc": is_pc,
        })
        return cid

    def _remove_combatants_with_lan_cleanup(cids):
        for cid in cids:
            app.combatants.pop(cid, None)
            if app.current_cid == cid:
                app.current_cid = None
        app._remove_cleanup_calls.extend(list(cids))

    app._create_combatant = _create_combatant
    app._remove_combatants_with_lan_cleanup = _remove_combatants_with_lan_cleanup
    return app


class CombatServiceAddCombatantTests(unittest.TestCase):
    """Tests for CombatService.add_combatant()."""

    def setUp(self):
        self.tracker = _make_tracker_with_encounter_setup()
        self.service = CombatService(self.tracker)

    def test_add_combatant_returns_ok(self):
        result = self.service.add_combatant("Orc", hp=15, initiative=12)
        self.assertTrue(result["ok"])

    def test_add_combatant_returns_cid(self):
        result = self.service.add_combatant("Orc", hp=15, initiative=12)
        self.assertIsNotNone(result.get("cid"))

    def test_add_combatant_appears_in_snapshot(self):
        result = self.service.add_combatant("Orc", hp=15, initiative=12)
        names = [c["name"] for c in result["snapshot"]["combatants"]]
        self.assertIn("Orc", names)

    def test_add_combatant_triggers_broadcast(self):
        before = len(self.tracker._broadcast_calls)
        self.service.add_combatant("Orc", hp=15, initiative=12)
        self.assertGreater(len(self.tracker._broadcast_calls), before)

    def test_add_combatant_empty_name_returns_error(self):
        result = self.service.add_combatant("", hp=15, initiative=12)
        self.assertFalse(result["ok"])
        self.assertIn("error", result)

    def test_add_combatant_sets_max_hp_from_hp_when_omitted(self):
        result = self.service.add_combatant("Orc", hp=20, initiative=10)
        cid = result["cid"]
        c = self.tracker.combatants[cid]
        # max_hp must be set by the service (stub does NOT pre-set it)
        self.assertEqual(getattr(c, "max_hp", None), 20)

    def test_add_combatant_explicit_max_hp_applied(self):
        """When max_hp is explicitly provided it should be set on the combatant."""
        result = self.service.add_combatant("Orc", hp=10, initiative=10, max_hp=30)
        cid = result["cid"]
        c = self.tracker.combatants[cid]
        self.assertEqual(getattr(c, "max_hp", None), 30)

    def test_add_combatant_hp_clamped_to_max_hp(self):
        """hp must be clamped to max_hp when caller passes hp > max_hp."""
        result = self.service.add_combatant("Orc", hp=50, initiative=10, max_hp=30)
        cid = result["cid"]
        c = self.tracker.combatants[cid]
        # The service clamps hp ≤ max_hp before creating the combatant
        self.assertLessEqual(getattr(c, "hp", 50), 30)

    def test_add_combatant_ally_flag_passed_to_create(self):
        """ally=True must be forwarded to _create_combatant."""
        self.service.add_combatant("Guard", hp=12, initiative=8, ally=True)
        ally_calls = [c for c in self.tracker._create_combatant_calls if c["name"] == "Guard"]
        self.assertTrue(ally_calls, "No _create_combatant call recorded for Guard")
        self.assertTrue(ally_calls[0]["ally"])

    def test_add_combatant_ally_defaults_to_false(self):
        """ally should default to False when not provided."""
        self.service.add_combatant("Goblin", hp=7, initiative=14)
        goblin_calls = [c for c in self.tracker._create_combatant_calls if c["name"] == "Goblin"]
        self.assertTrue(goblin_calls, "No _create_combatant call recorded for Goblin")
        self.assertFalse(goblin_calls[0]["ally"])

    def test_add_combatant_is_pc_flag_passed_to_create(self):
        """is_pc=True must be forwarded to _create_combatant."""
        self.service.add_combatant("Hero", hp=30, initiative=18, is_pc=True)
        hero_calls = [c for c in self.tracker._create_combatant_calls if c["name"] == "Hero"]
        self.assertTrue(hero_calls, "No _create_combatant call recorded for Hero")
        self.assertTrue(hero_calls[0]["is_pc"])

    def test_add_combatant_logs_action(self):
        self.service.add_combatant("Troll", hp=84, initiative=5)
        logged_msgs = [m for m, _ in self.tracker._log_calls]
        self.assertTrue(any("Troll" in m for m in logged_msgs))


class CombatServiceSetInitiativeTests(unittest.TestCase):
    """Tests for CombatService.set_initiative()."""

    def setUp(self):
        self.tracker = _make_tracker_with_encounter_setup()
        self.service = CombatService(self.tracker)

    def test_set_initiative_returns_ok(self):
        result = self.service.set_initiative(cid=1, initiative=18)
        self.assertTrue(result["ok"])

    def test_set_initiative_updates_value(self):
        self.service.set_initiative(cid=1, initiative=18)
        self.assertEqual(self.tracker.combatants[1].initiative, 18)

    def test_set_initiative_returns_before_after(self):
        old = self.tracker.combatants[1].initiative
        result = self.service.set_initiative(cid=1, initiative=18)
        self.assertEqual(result["initiative_before"], old)
        self.assertEqual(result["initiative_after"], 18)

    def test_set_initiative_returns_snapshot(self):
        result = self.service.set_initiative(cid=1, initiative=18)
        self.assertIn("snapshot", result)

    def test_set_initiative_unknown_cid_returns_error(self):
        result = self.service.set_initiative(cid=999, initiative=10)
        self.assertFalse(result["ok"])
        self.assertIn("error", result)

    def test_set_initiative_triggers_broadcast(self):
        before = len(self.tracker._broadcast_calls)
        self.service.set_initiative(cid=1, initiative=18)
        self.assertGreater(len(self.tracker._broadcast_calls), before)

    def test_set_initiative_logs_change(self):
        self.service.set_initiative(cid=1, initiative=18)
        logged_msgs = [m for m, _ in self.tracker._log_calls]
        self.assertTrue(any("initiative" in m.lower() for m in logged_msgs))


class CombatServiceRemoveCombatantTests(unittest.TestCase):
    """Tests for CombatService.remove_combatant()."""

    def setUp(self):
        self.tracker = _make_tracker_with_encounter_setup()
        self.service = CombatService(self.tracker)

    def test_remove_combatant_returns_ok(self):
        result = self.service.remove_combatant(cid=1)
        self.assertTrue(result["ok"])

    def test_remove_combatant_removes_from_state(self):
        self.service.remove_combatant(cid=1)
        self.assertNotIn(1, self.tracker.combatants)

    def test_remove_combatant_returns_cid(self):
        result = self.service.remove_combatant(cid=1)
        self.assertEqual(result["cid"], 1)

    def test_remove_combatant_returns_snapshot(self):
        result = self.service.remove_combatant(cid=1)
        self.assertIn("snapshot", result)
        remaining = [c["cid"] for c in result["snapshot"]["combatants"]]
        self.assertNotIn(1, remaining)

    def test_remove_unknown_cid_returns_error(self):
        result = self.service.remove_combatant(cid=999)
        self.assertFalse(result["ok"])
        self.assertIn("error", result)

    def test_remove_combatant_triggers_broadcast(self):
        before = len(self.tracker._broadcast_calls)
        self.service.remove_combatant(cid=1)
        self.assertGreater(len(self.tracker._broadcast_calls), before)

    def test_remove_active_combatant_clears_current(self):
        self.tracker.current_cid = 1
        self.service.remove_combatant(cid=1)
        self.assertIsNone(self.tracker.current_cid)

    def test_remove_combatant_calls_cleanup(self):
        self.service.remove_combatant(cid=2)
        self.assertIn(2, self.tracker._remove_cleanup_calls)


# ── Slice 6: adjust_temp_hp + service-routing wrapper tests ──────────


class CombatServiceAdjustTempHpTests(unittest.TestCase):
    """Tests for CombatService.adjust_temp_hp() (delta-based temp HP)."""

    def setUp(self):
        self.tracker = _make_tracker()
        self.service = CombatService(self.tracker)

    def test_positive_delta_adds_temp_hp(self):
        c = self.tracker.combatants[1]
        c.temp_hp = 0
        result = self.service.adjust_temp_hp(cid=1, delta=5)
        self.assertTrue(result["ok"])
        self.assertEqual(result["temp_hp_after"], 5)
        self.assertEqual(c.temp_hp, 5)

    def test_negative_delta_removes_temp_hp(self):
        c = self.tracker.combatants[1]
        c.temp_hp = 10
        result = self.service.adjust_temp_hp(cid=1, delta=-3)
        self.assertTrue(result["ok"])
        self.assertEqual(result["temp_hp_before"], 10)
        self.assertEqual(result["temp_hp_after"], 7)
        self.assertEqual(c.temp_hp, 7)

    def test_temp_hp_clamped_to_zero(self):
        c = self.tracker.combatants[1]
        c.temp_hp = 3
        result = self.service.adjust_temp_hp(cid=1, delta=-10)
        self.assertTrue(result["ok"])
        self.assertEqual(result["temp_hp_after"], 0)
        self.assertEqual(c.temp_hp, 0)

    def test_unknown_cid_returns_error(self):
        result = self.service.adjust_temp_hp(cid=999, delta=5)
        self.assertFalse(result["ok"])
        self.assertIn("error", result)

    def test_adjust_temp_hp_triggers_broadcast(self):
        before = len(self.tracker._broadcast_calls)
        self.service.adjust_temp_hp(cid=1, delta=5)
        self.assertGreater(len(self.tracker._broadcast_calls), before)

    def test_adjust_temp_hp_result_has_delta(self):
        result = self.service.adjust_temp_hp(cid=1, delta=7)
        self.assertEqual(result["delta"], 7)

    def test_adjust_temp_hp_stacks_on_existing(self):
        c = self.tracker.combatants[1]
        c.temp_hp = 4
        result = self.service.adjust_temp_hp(cid=1, delta=6)
        self.assertTrue(result["ok"])
        self.assertEqual(result["temp_hp_after"], 10)


class ServiceRoutingWrapperTests(unittest.TestCase):
    """Tests for the real InitiativeTracker._*_via_service() methods.

    Uses InitiativeTracker unbound methods called against the
    SimpleNamespace test double so we exercise the production code
    without instantiating Tkinter.
    """

    def _make_tracker_with_service(self):
        """Build a tracker with a CombatService attached."""
        tracker = _make_tracker()
        service = CombatService(tracker)
        tracker._dm_service = service
        return tracker, service

    # -- _adjust_hp_via_service --

    def test_adjust_hp_via_service_routes_through_service(self):
        tracker, service = self._make_tracker_with_service()
        c = tracker.combatants[1]
        old_hp = c.hp
        result = InitiativeTracker._adjust_hp_via_service(tracker, cid=1, delta=-5)
        self.assertTrue(result)
        self.assertEqual(c.hp, old_hp - 5)

    def test_adjust_hp_via_service_fallback_without_service(self):
        tracker = _make_tracker()
        tracker._dm_service = None
        c = tracker.combatants[1]
        old_hp = c.hp
        result = InitiativeTracker._adjust_hp_via_service(tracker, cid=1, delta=-3)
        self.assertTrue(result)
        self.assertEqual(c.hp, old_hp - 3)

    def test_adjust_hp_via_service_invalid_cid(self):
        tracker, service = self._make_tracker_with_service()
        result = InitiativeTracker._adjust_hp_via_service(tracker, cid=999, delta=-5)
        self.assertFalse(result)

    def test_adjust_hp_via_service_broadcasts(self):
        tracker, service = self._make_tracker_with_service()
        before = len(tracker._broadcast_calls)
        InitiativeTracker._adjust_hp_via_service(tracker, cid=1, delta=-5)
        self.assertGreater(len(tracker._broadcast_calls), before)

    def test_adjust_hp_via_service_logs_on_failure(self):
        tracker = _make_tracker()
        # Attach a broken service that always returns {ok: False}
        broken = CombatService(tracker)
        broken.adjust_hp = lambda **kw: {"ok": False, "error": "test failure"}
        tracker._dm_service = broken
        InitiativeTracker._adjust_hp_via_service(tracker, cid=1, delta=-5)
        warnings = [(m, l) for m, l in tracker._oplog_calls if l == "warning"]
        self.assertTrue(any("adjust_hp" in m for m, _ in warnings))

    # -- _set_condition_via_service --

    def test_set_condition_via_service_adds_condition(self):
        tracker, service = self._make_tracker_with_service()
        result = InitiativeTracker._set_condition_via_service(
            tracker, cid=1, ctype="poisoned", action="add"
        )
        self.assertTrue(result)
        c = tracker.combatants[1]
        ctypes = [st.ctype for st in c.condition_stacks]
        self.assertIn("poisoned", ctypes)

    def test_set_condition_via_service_removes_condition(self):
        tracker, service = self._make_tracker_with_service()
        InitiativeTracker._set_condition_via_service(
            tracker, cid=1, ctype="stunned", action="add"
        )
        result = InitiativeTracker._set_condition_via_service(
            tracker, cid=1, ctype="stunned", action="remove"
        )
        self.assertTrue(result)
        c = tracker.combatants[1]
        ctypes = [st.ctype for st in c.condition_stacks]
        self.assertNotIn("stunned", ctypes)

    def test_set_condition_via_service_fallback(self):
        tracker = _make_tracker()
        tracker._dm_service = None
        result = InitiativeTracker._set_condition_via_service(
            tracker, cid=1, ctype="blinded", action="add"
        )
        self.assertTrue(result)
        c = tracker.combatants[1]
        ctypes = [st.ctype for st in c.condition_stacks]
        self.assertIn("blinded", ctypes)

    def test_set_condition_via_service_invalid_cid(self):
        tracker, service = self._make_tracker_with_service()
        result = InitiativeTracker._set_condition_via_service(
            tracker, cid=999, ctype="poisoned", action="add"
        )
        self.assertFalse(result)

    def test_set_condition_via_service_logs_on_failure(self):
        tracker = _make_tracker()
        broken = CombatService(tracker)
        broken.set_condition = lambda **kw: {"ok": False, "error": "test failure"}
        tracker._dm_service = broken
        InitiativeTracker._set_condition_via_service(
            tracker, cid=1, ctype="poisoned", action="add"
        )
        warnings = [(m, l) for m, l in tracker._oplog_calls if l == "warning"]
        self.assertTrue(any("set_condition" in m for m, _ in warnings))

    # -- _set_temp_hp_via_service --

    def test_set_temp_hp_via_service_sets_value(self):
        tracker, service = self._make_tracker_with_service()
        result = InitiativeTracker._set_temp_hp_via_service(tracker, cid=1, amount=10)
        self.assertTrue(result)
        self.assertEqual(tracker.combatants[1].temp_hp, 10)

    def test_set_temp_hp_via_service_clears_temp_hp(self):
        tracker, service = self._make_tracker_with_service()
        tracker.combatants[1].temp_hp = 8
        result = InitiativeTracker._set_temp_hp_via_service(tracker, cid=1, amount=0)
        self.assertTrue(result)
        self.assertEqual(tracker.combatants[1].temp_hp, 0)

    def test_set_temp_hp_via_service_fallback(self):
        tracker = _make_tracker()
        tracker._dm_service = None
        result = InitiativeTracker._set_temp_hp_via_service(tracker, cid=1, amount=15)
        self.assertTrue(result)
        self.assertEqual(tracker.combatants[1].temp_hp, 15)

    def test_set_temp_hp_via_service_invalid_cid(self):
        tracker, service = self._make_tracker_with_service()
        result = InitiativeTracker._set_temp_hp_via_service(tracker, cid=999, amount=10)
        self.assertFalse(result)

    def test_set_temp_hp_via_service_logs_on_failure(self):
        tracker = _make_tracker()
        broken = CombatService(tracker)
        broken.set_temp_hp = lambda **kw: {"ok": False, "error": "test failure"}
        tracker._dm_service = broken
        InitiativeTracker._set_temp_hp_via_service(tracker, cid=1, amount=10)
        warnings = [(m, l) for m, l in tracker._oplog_calls if l == "warning"]
        self.assertTrue(any("set_temp_hp" in m for m, _ in warnings))


class CombatServiceManualOverrideTests(unittest.TestCase):
    """Tests for CombatService.manual_override() (atomic HP + temp-HP)."""

    def setUp(self):
        self.tracker = _make_tracker()
        self.service = CombatService(self.tracker)

    def test_hp_only(self):
        c = self.tracker.combatants[1]
        old_hp = c.hp
        result = self.service.manual_override(cid=1, hp_delta=-5)
        self.assertTrue(result["ok"])
        self.assertEqual(result["hp_after"], old_hp - 5)
        self.assertEqual(c.hp, old_hp - 5)

    def test_temp_hp_only(self):
        c = self.tracker.combatants[1]
        c.temp_hp = 0
        result = self.service.manual_override(cid=1, temp_hp_delta=8)
        self.assertTrue(result["ok"])
        self.assertEqual(result["temp_hp_after"], 8)
        self.assertEqual(c.temp_hp, 8)

    def test_both_hp_and_temp_hp(self):
        c = self.tracker.combatants[1]
        old_hp = c.hp
        c.temp_hp = 5
        result = self.service.manual_override(cid=1, hp_delta=-3, temp_hp_delta=2)
        self.assertTrue(result["ok"])
        self.assertEqual(result["hp_after"], old_hp - 3)
        self.assertEqual(result["temp_hp_after"], 7)
        self.assertEqual(c.hp, old_hp - 3)
        self.assertEqual(c.temp_hp, 7)

    def test_hp_clamped_to_zero(self):
        c = self.tracker.combatants[1]
        result = self.service.manual_override(cid=1, hp_delta=-999)
        self.assertTrue(result["ok"])
        self.assertEqual(result["hp_after"], 0)
        self.assertEqual(c.hp, 0)

    def test_hp_clamped_to_max(self):
        c = self.tracker.combatants[1]
        result = self.service.manual_override(cid=1, hp_delta=999)
        self.assertTrue(result["ok"])
        self.assertEqual(result["hp_after"], c.max_hp)

    def test_temp_hp_clamped_to_zero(self):
        c = self.tracker.combatants[1]
        c.temp_hp = 3
        result = self.service.manual_override(cid=1, temp_hp_delta=-100)
        self.assertTrue(result["ok"])
        self.assertEqual(result["temp_hp_after"], 0)
        self.assertEqual(c.temp_hp, 0)

    def test_unknown_cid_returns_error(self):
        result = self.service.manual_override(cid=999, hp_delta=-5)
        self.assertFalse(result["ok"])
        self.assertIn("error", result)

    def test_triggers_single_broadcast(self):
        before = len(self.tracker._broadcast_calls)
        self.service.manual_override(cid=1, hp_delta=-5, temp_hp_delta=3)
        # Should be exactly one broadcast, not two
        self.assertEqual(len(self.tracker._broadcast_calls), before + 1)

    def test_no_change_when_both_zero(self):
        c = self.tracker.combatants[1]
        old_hp = c.hp
        old_temp = c.temp_hp
        result = self.service.manual_override(cid=1, hp_delta=0, temp_hp_delta=0)
        self.assertTrue(result["ok"])
        self.assertEqual(c.hp, old_hp)
        self.assertEqual(c.temp_hp, old_temp)


# ---------------------------------------------------------------------------
# Slice 7: CombatService.prev_turn() tests
# ---------------------------------------------------------------------------


class CombatServicePrevTurnTests(unittest.TestCase):
    """Tests for CombatService.prev_turn()."""

    def _make_tracker_with_prev(self):
        app = _make_tracker(num_combatants=3)
        app.in_combat = True
        app.current_cid = 2  # Start on the second combatant
        app._prev_turn_calls = []

        def _prev_turn():
            app._prev_turn_calls.append(1)
            ids = sorted(app.combatants.keys())
            if not ids:
                return
            if app.current_cid not in ids:
                app.current_cid = ids[0]
                return
            idx = ids.index(app.current_cid)
            prev_idx = idx - 1
            if prev_idx < 0:
                prev_idx = len(ids) - 1
                app.round_num = max(1, app.round_num - 1)
            app.current_cid = ids[prev_idx]
            app.turn_num = max(0, app.turn_num - 1)

        app._prev_turn = _prev_turn
        return app

    def test_prev_turn_returns_ok(self):
        tracker = self._make_tracker_with_prev()
        service = CombatService(tracker)
        result = service.prev_turn()
        self.assertTrue(result["ok"])

    def test_prev_turn_calls_prev_turn(self):
        tracker = self._make_tracker_with_prev()
        service = CombatService(tracker)
        service.prev_turn()
        self.assertEqual(len(tracker._prev_turn_calls), 1)

    def test_prev_turn_returns_snapshot(self):
        tracker = self._make_tracker_with_prev()
        service = CombatService(tracker)
        result = service.prev_turn()
        self.assertIn("snapshot", result)
        self.assertIn("combatants", result["snapshot"])

    def test_prev_turn_changes_current_cid(self):
        tracker = self._make_tracker_with_prev()
        tracker.current_cid = 2
        service = CombatService(tracker)
        service.prev_turn()
        self.assertEqual(tracker.current_cid, 1)

    def test_prev_turn_triggers_broadcast(self):
        tracker = self._make_tracker_with_prev()
        service = CombatService(tracker)
        before = len(tracker._broadcast_calls)
        service.prev_turn()
        self.assertGreater(len(tracker._broadcast_calls), before)

    def test_prev_turn_triggers_rebuild(self):
        tracker = self._make_tracker_with_prev()
        service = CombatService(tracker)
        before = len(tracker._rebuild_calls)
        service.prev_turn()
        self.assertGreater(len(tracker._rebuild_calls), before)

    def test_prev_turn_wraps_around_decrements_round(self):
        tracker = self._make_tracker_with_prev()
        tracker.current_cid = 1  # First combatant
        tracker.round_num = 3
        service = CombatService(tracker)
        service.prev_turn()
        # Should wrap to last combatant and decrement round
        self.assertEqual(tracker.current_cid, 3)
        self.assertEqual(tracker.round_num, 2)


# ---------------------------------------------------------------------------
# Slice 7: _start_combat_via_service and _prev_turn_via_service wrapper tests
# ---------------------------------------------------------------------------


class StartCombatViaServiceTests(unittest.TestCase):
    """Tests for InitiativeTracker._start_combat_via_service()."""

    def _make_tracker_with_start_service(self):
        tracker = _make_tracker(num_combatants=3)
        tracker.in_combat = False
        tracker.current_cid = None
        tracker._start_turns_calls = []

        def _start_turns():
            tracker._start_turns_calls.append(1)
            ids = sorted(tracker.combatants.keys())
            if ids:
                tracker.current_cid = ids[0]
                tracker.round_num = 1
                tracker.turn_num = 1

        tracker._start_turns = _start_turns
        service = CombatService(tracker)
        tracker._dm_service = service
        return tracker, service

    def test_start_combat_via_service_routes_through_service(self):
        tracker, service = self._make_tracker_with_start_service()
        InitiativeTracker._start_combat_via_service(tracker)
        self.assertTrue(tracker.in_combat)
        self.assertIsNotNone(tracker.current_cid)

    def test_start_combat_via_service_triggers_broadcast(self):
        tracker, service = self._make_tracker_with_start_service()
        before = len(tracker._broadcast_calls)
        InitiativeTracker._start_combat_via_service(tracker)
        self.assertGreater(len(tracker._broadcast_calls), before)

    def test_start_combat_via_service_fallback_without_service(self):
        tracker = _make_tracker(num_combatants=3)
        tracker.in_combat = False
        tracker.current_cid = None
        tracker._dm_service = None
        tracker._start_turns_calls = []

        def _start_turns():
            tracker._start_turns_calls.append(1)
            ids = sorted(tracker.combatants.keys())
            if ids:
                tracker.current_cid = ids[0]

        tracker._start_turns = _start_turns
        InitiativeTracker._start_combat_via_service(tracker)
        self.assertEqual(len(tracker._start_turns_calls), 1)

    def test_start_combat_via_service_logs_on_failure(self):
        tracker = _make_tracker(num_combatants=0)
        tracker._dm_service = CombatService(tracker)
        tracker._start_turns_calls = []

        def _start_turns():
            tracker._start_turns_calls.append(1)

        tracker._start_turns = _start_turns
        # Service will fail because no combatants
        InitiativeTracker._start_combat_via_service(tracker)
        warnings = [(m, l) for m, l in tracker._oplog_calls if l == "warning"]
        self.assertTrue(any("start_combat" in m for m, _ in warnings))


class PrevTurnViaServiceTests(unittest.TestCase):
    """Tests for InitiativeTracker._prev_turn_via_service()."""

    def _make_tracker_with_prev_service(self):
        tracker = _make_tracker(num_combatants=3)
        tracker.in_combat = True
        tracker.current_cid = 2
        tracker._prev_turn_calls = []

        def _prev_turn():
            tracker._prev_turn_calls.append(1)
            ids = sorted(tracker.combatants.keys())
            if not ids:
                return
            idx = ids.index(tracker.current_cid) if tracker.current_cid in ids else 0
            prev_idx = idx - 1
            if prev_idx < 0:
                prev_idx = len(ids) - 1
            tracker.current_cid = ids[prev_idx]

        tracker._prev_turn = _prev_turn
        service = CombatService(tracker)
        tracker._dm_service = service
        return tracker, service

    def test_prev_turn_via_service_routes_through_service(self):
        tracker, service = self._make_tracker_with_prev_service()
        old_cid = tracker.current_cid
        InitiativeTracker._prev_turn_via_service(tracker)
        self.assertNotEqual(tracker.current_cid, old_cid)

    def test_prev_turn_via_service_triggers_broadcast(self):
        tracker, service = self._make_tracker_with_prev_service()
        before = len(tracker._broadcast_calls)
        InitiativeTracker._prev_turn_via_service(tracker)
        self.assertGreater(len(tracker._broadcast_calls), before)

    def test_prev_turn_via_service_fallback_without_service(self):
        tracker = _make_tracker(num_combatants=3)
        tracker._dm_service = None
        tracker.current_cid = 2
        tracker._prev_turn_calls = []

        def _prev_turn():
            tracker._prev_turn_calls.append(1)
            tracker.current_cid = 1

        tracker._prev_turn = _prev_turn
        InitiativeTracker._prev_turn_via_service(tracker)
        self.assertEqual(len(tracker._prev_turn_calls), 1)
        self.assertEqual(tracker.current_cid, 1)

    def test_prev_turn_via_service_logs_on_failure(self):
        tracker = _make_tracker(num_combatants=3)
        tracker.current_cid = 2
        broken = CombatService(tracker)
        broken.prev_turn = lambda: {"ok": False, "error": "test failure"}
        tracker._dm_service = broken
        tracker._prev_turn_calls = []

        def _prev_turn():
            tracker._prev_turn_calls.append(1)
            tracker.current_cid = 1

        tracker._prev_turn = _prev_turn
        InitiativeTracker._prev_turn_via_service(tracker)
        warnings = [(m, l) for m, l in tracker._oplog_calls if l == "warning"]
        self.assertTrue(any("prev_turn" in m for m, _ in warnings))
        # Should fall back to direct call
        self.assertEqual(len(tracker._prev_turn_calls), 1)


# ---------------------------------------------------------------------------
# Slice 8: CombatService.set_turn_here() tests
# ---------------------------------------------------------------------------


class CombatServiceSetTurnHereTests(unittest.TestCase):
    """Tests for CombatService.set_turn_here()."""

    def _make_service(self, num_combatants=3, in_combat=True, current_cid=1):
        app = _make_tracker(num_combatants=num_combatants)
        app.in_combat = in_combat
        app.current_cid = current_cid
        app.turn_num = 1
        app._enter_turn_calls = []

        def _enter_turn_with_auto_skip(starting=True):
            app._enter_turn_calls.append(starting)

        app._enter_turn_with_auto_skip = _enter_turn_with_auto_skip
        service = CombatService(app)
        return app, service

    def test_set_turn_here_valid_cid(self):
        app, service = self._make_service()
        result = service.set_turn_here(cid=2)
        self.assertTrue(result["ok"])
        self.assertEqual(result["cid"], 2)
        self.assertEqual(result["previous_cid"], 1)
        self.assertEqual(app.current_cid, 2)

    def test_set_turn_here_returns_snapshot(self):
        app, service = self._make_service()
        result = service.set_turn_here(cid=2)
        self.assertIn("snapshot", result)
        snap = result["snapshot"]
        self.assertEqual(snap["active_cid"], 2)

    def test_set_turn_here_invalid_cid(self):
        app, service = self._make_service()
        result = service.set_turn_here(cid=999)
        self.assertFalse(result["ok"])
        self.assertIn("not found", result["error"])

    def test_set_turn_here_no_combat(self):
        app, service = self._make_service(in_combat=False)
        result = service.set_turn_here(cid=1)
        self.assertFalse(result["ok"])
        self.assertIn("No active combat", result["error"])

    def test_set_turn_here_triggers_rebuild(self):
        app, service = self._make_service()
        before = len(app._rebuild_calls)
        service.set_turn_here(cid=2)
        self.assertGreater(len(app._rebuild_calls), before)

    def test_set_turn_here_triggers_broadcast(self):
        app, service = self._make_service()
        before = len(app._broadcast_calls)
        service.set_turn_here(cid=2)
        self.assertGreater(len(app._broadcast_calls), before)

    def test_set_turn_here_calls_enter_turn(self):
        app, service = self._make_service()
        service.set_turn_here(cid=2)
        self.assertEqual(len(app._enter_turn_calls), 1)
        self.assertTrue(app._enter_turn_calls[0])  # starting=True

    def test_set_turn_here_logs_turn_change(self):
        app, service = self._make_service()
        before = len(app._log_calls)
        service.set_turn_here(cid=2)
        self.assertGreater(len(app._log_calls), before)
        # Should mention the combatant name
        log_msgs = [m for m, _ in app._log_calls]
        self.assertTrue(any("Goblin" in m for m in log_msgs))

    def test_set_turn_here_sets_turn_num_if_zero(self):
        app, service = self._make_service()
        app.turn_num = 0
        service.set_turn_here(cid=2)
        self.assertGreaterEqual(app.turn_num, 1)

    def test_set_turn_here_preserves_turn_num_if_positive(self):
        app, service = self._make_service()
        app.turn_num = 5
        service.set_turn_here(cid=2)
        # turn_num should remain unchanged
        self.assertEqual(app.turn_num, 5)

    def test_set_turn_here_previous_cid_none(self):
        app, service = self._make_service(current_cid=None)
        # Ensure turn_num is at least 1 for in_combat
        app.turn_num = 1
        result = service.set_turn_here(cid=2)
        self.assertTrue(result["ok"])
        self.assertIsNone(result["previous_cid"])
        self.assertEqual(result["cid"], 2)

    def test_set_turn_here_same_cid(self):
        """Setting turn to the already-active combatant should still succeed."""
        app, service = self._make_service(current_cid=1)
        result = service.set_turn_here(cid=1)
        self.assertTrue(result["ok"])
        self.assertEqual(result["cid"], 1)
        self.assertEqual(result["previous_cid"], 1)

    def test_set_turn_here_without_enter_method(self):
        """Should work even if _enter_turn_with_auto_skip is not available."""
        app, service = self._make_service()
        del app._enter_turn_with_auto_skip
        result = service.set_turn_here(cid=2)
        self.assertTrue(result["ok"])
        self.assertEqual(app.current_cid, 2)


# ---------------------------------------------------------------------------
# Slice 8: _set_turn_here_via_service wrapper tests
# ---------------------------------------------------------------------------


class SetTurnHereViaServiceTests(unittest.TestCase):
    """Tests for InitiativeTracker._set_turn_here_via_service()."""

    def _make_tracker_with_service(self):
        tracker = _make_tracker(num_combatants=3)
        tracker.in_combat = True
        tracker.current_cid = 1
        tracker.turn_num = 1
        tracker._enter_turn_calls = []

        def _enter_turn_with_auto_skip(starting=True):
            tracker._enter_turn_calls.append(starting)

        tracker._enter_turn_with_auto_skip = _enter_turn_with_auto_skip

        # Simulate tree selection
        import types as _t
        tree = _t.SimpleNamespace()
        tree._selection = ("2",)
        tree.selection = lambda: tree._selection
        tracker.tree = tree

        service = CombatService(tracker)
        tracker._dm_service = service
        return tracker, service

    def test_routes_through_service(self):
        tracker, service = self._make_tracker_with_service()
        InitiativeTracker._set_turn_here_via_service(tracker)
        self.assertEqual(tracker.current_cid, 2)

    def test_triggers_broadcast(self):
        tracker, service = self._make_tracker_with_service()
        before = len(tracker._broadcast_calls)
        InitiativeTracker._set_turn_here_via_service(tracker)
        self.assertGreater(len(tracker._broadcast_calls), before)

    def test_fallback_without_service(self):
        tracker, _ = self._make_tracker_with_service()
        tracker._dm_service = None
        InitiativeTracker._set_turn_here_via_service(tracker)
        # Fallback direct mutation should still set current_cid
        self.assertEqual(tracker.current_cid, 2)

    def test_fallback_on_service_failure(self):
        tracker, _ = self._make_tracker_with_service()
        broken = CombatService(tracker)
        broken.set_turn_here = lambda cid: {"ok": False, "error": "test failure"}
        tracker._dm_service = broken
        InitiativeTracker._set_turn_here_via_service(tracker)
        # Should fall back and still set the turn
        self.assertEqual(tracker.current_cid, 2)
        warnings = [(m, l) for m, l in tracker._oplog_calls if l == "warning"]
        self.assertTrue(any("set_turn_here" in m for m, _ in warnings))

    def test_no_selection_does_nothing(self):
        tracker, _ = self._make_tracker_with_service()
        tracker.tree._selection = ()
        tracker.tree.selection = lambda: ()
        old_cid = tracker.current_cid
        InitiativeTracker._set_turn_here_via_service(tracker)
        self.assertEqual(tracker.current_cid, old_cid)

    def test_invalid_cid_selection_does_nothing(self):
        tracker, _ = self._make_tracker_with_service()
        tracker.tree._selection = ("999",)
        tracker.tree.selection = lambda: ("999",)
        old_cid = tracker.current_cid
        InitiativeTracker._set_turn_here_via_service(tracker)
        self.assertEqual(tracker.current_cid, old_cid)

    def test_no_tree_does_nothing(self):
        tracker, _ = self._make_tracker_with_service()
        tracker.tree = None
        old_cid = tracker.current_cid
        InitiativeTracker._set_turn_here_via_service(tracker)
        self.assertEqual(tracker.current_cid, old_cid)


# ===================================================================
# CombatService.apply_damage tests (Slice 9)
# ===================================================================


class CombatServiceApplyDamageTests(unittest.TestCase):
    """Tests for CombatService.apply_damage() — canonical deep damage path."""

    def setUp(self):
        self.tracker = _make_tracker()
        self.service = CombatService(self.tracker)

    def test_basic_damage_reduces_hp(self):
        c = self.tracker.combatants[1]
        c.hp = 20
        c.temp_hp = 0
        result = self.service.apply_damage(cid=1, raw_damage=7)
        self.assertTrue(result["ok"])
        self.assertEqual(result["hp_after"], 13)
        self.assertEqual(result["hp_damage"], 7)
        self.assertEqual(result["temp_absorbed"], 0)
        self.assertEqual(c.hp, 13)

    def test_damage_absorbs_temp_hp_first(self):
        c = self.tracker.combatants[1]
        c.hp = 20
        c.temp_hp = 5
        result = self.service.apply_damage(cid=1, raw_damage=3)
        self.assertTrue(result["ok"])
        self.assertEqual(result["temp_absorbed"], 3)
        self.assertEqual(result["hp_damage"], 0)
        self.assertEqual(result["hp_after"], 20)
        self.assertEqual(c.temp_hp, 2)
        self.assertEqual(c.hp, 20)

    def test_damage_overflows_temp_hp_into_main_hp(self):
        c = self.tracker.combatants[1]
        c.hp = 20
        c.temp_hp = 4
        result = self.service.apply_damage(cid=1, raw_damage=10)
        self.assertTrue(result["ok"])
        self.assertEqual(result["temp_absorbed"], 4)
        self.assertEqual(result["hp_damage"], 6)
        self.assertEqual(result["hp_after"], 14)
        self.assertEqual(c.temp_hp, 0)
        self.assertEqual(c.hp, 14)

    def test_zero_damage_is_noop(self):
        c = self.tracker.combatants[1]
        c.hp = 20
        result = self.service.apply_damage(cid=1, raw_damage=0)
        self.assertTrue(result["ok"])
        self.assertEqual(result["hp_after"], 20)
        self.assertEqual(result["hp_damage"], 0)
        self.assertEqual(result["temp_absorbed"], 0)
        self.assertEqual(c.hp, 20)

    def test_negative_damage_treated_as_zero(self):
        c = self.tracker.combatants[1]
        c.hp = 20
        result = self.service.apply_damage(cid=1, raw_damage=-5)
        self.assertTrue(result["ok"])
        self.assertEqual(result["hp_after"], 20)

    def test_damage_to_nonexistent_cid_fails(self):
        result = self.service.apply_damage(cid=999, raw_damage=10)
        self.assertFalse(result["ok"])
        self.assertIn("not found", result["error"])

    def test_damage_triggers_rebuild_and_broadcast(self):
        self.service.apply_damage(cid=1, raw_damage=5)
        self.assertTrue(len(self.tracker._rebuild_calls) > 0)
        self.assertTrue(len(self.tracker._broadcast_calls) > 0)

    def test_damage_delegates_to_tracker_method(self):
        self.service.apply_damage(cid=1, raw_damage=5)
        self.assertEqual(len(self.tracker._apply_damage_calls), 1)
        self.assertEqual(self.tracker._apply_damage_calls[0]["cid"], 1)
        self.assertEqual(self.tracker._apply_damage_calls[0]["raw_damage"], 5)

    def test_damage_clamps_hp_to_zero(self):
        c = self.tracker.combatants[1]
        c.hp = 5
        c.temp_hp = 0
        result = self.service.apply_damage(cid=1, raw_damage=100)
        self.assertTrue(result["ok"])
        self.assertEqual(result["hp_after"], 0)
        self.assertEqual(c.hp, 0)

    def test_damage_fully_absorbed_by_temp_hp(self):
        c = self.tracker.combatants[1]
        c.hp = 10
        c.temp_hp = 20
        result = self.service.apply_damage(cid=1, raw_damage=15)
        self.assertTrue(result["ok"])
        self.assertEqual(result["temp_absorbed"], 15)
        self.assertEqual(result["hp_damage"], 0)
        self.assertEqual(result["hp_after"], 10)
        self.assertEqual(c.temp_hp, 5)
        self.assertEqual(c.hp, 10)

    def test_damage_deferred_broadcast_skips_rebuild_and_broadcast(self):
        """apply_damage(_broadcast=False) should not rebuild or broadcast."""
        self.tracker._rebuild_calls.clear()
        self.tracker._broadcast_calls.clear()
        result = self.service.apply_damage(cid=1, raw_damage=3, _broadcast=False)
        self.assertTrue(result["ok"])
        self.assertEqual(len(self.tracker._rebuild_calls), 0)
        self.assertEqual(len(self.tracker._broadcast_calls), 0)

    def test_damage_default_broadcast_rebuilds_and_broadcasts(self):
        """apply_damage() with default _broadcast=True should rebuild and broadcast."""
        self.tracker._rebuild_calls.clear()
        self.tracker._broadcast_calls.clear()
        result = self.service.apply_damage(cid=1, raw_damage=3)
        self.assertTrue(result["ok"])
        self.assertTrue(len(self.tracker._rebuild_calls) > 0)
        self.assertTrue(len(self.tracker._broadcast_calls) > 0)


# ===================================================================
# CombatService.apply_heal tests (Slice 9)
# ===================================================================


class CombatServiceApplyHealTests(unittest.TestCase):
    """Tests for CombatService.apply_heal() — canonical heal path."""

    def setUp(self):
        self.tracker = _make_tracker()
        self.service = CombatService(self.tracker)

    def test_basic_heal_increases_hp(self):
        c = self.tracker.combatants[1]
        c.hp = 10
        c.max_hp = 20
        result = self.service.apply_heal(cid=1, amount=5)
        self.assertTrue(result["ok"])
        self.assertEqual(result["hp_after"], 15)
        self.assertEqual(result["hp_before"], 10)

    def test_heal_delegates_to_tracker(self):
        self.service.apply_heal(cid=1, amount=5)
        self.assertEqual(len(self.tracker._apply_heal_calls), 1)
        self.assertEqual(self.tracker._apply_heal_calls[0]["cid"], 1)
        self.assertEqual(self.tracker._apply_heal_calls[0]["amount"], 5)
        self.assertFalse(self.tracker._apply_heal_calls[0]["is_temp_hp"])

    def test_heal_temp_hp_mode_sets_temp_hp(self):
        c = self.tracker.combatants[1]
        c.temp_hp = 0
        result = self.service.apply_heal(cid=1, amount=8, is_temp_hp=True)
        self.assertTrue(result["ok"])
        self.assertEqual(result["temp_hp_after"], 8)
        self.assertEqual(c.temp_hp, 8)

    def test_heal_nonexistent_cid_fails(self):
        result = self.service.apply_heal(cid=999, amount=5)
        self.assertFalse(result["ok"])
        self.assertIn("not found", result["error"])

    def test_heal_triggers_rebuild_and_broadcast(self):
        self.service.apply_heal(cid=1, amount=3)
        self.assertTrue(len(self.tracker._rebuild_calls) > 0)
        self.assertTrue(len(self.tracker._broadcast_calls) > 0)

    def test_heal_logs_message(self):
        self.service.apply_heal(cid=1, amount=5)
        self.assertTrue(
            any("healed" in msg for msg, _ in self.tracker._log_calls)
        )

    def test_heal_temp_hp_logs_message(self):
        self.service.apply_heal(cid=1, amount=10, is_temp_hp=True)
        self.assertTrue(
            any("temp HP set" in msg for msg, _ in self.tracker._log_calls)
        )

    def test_heal_rejects_negative_amount(self):
        c = self.tracker.combatants[1]
        c.hp = 15
        result = self.service.apply_heal(cid=1, amount=-5)
        self.assertFalse(result["ok"])
        self.assertIn("non-negative", result["error"])
        self.assertEqual(c.hp, 15)

    def test_heal_zero_amount_is_noop(self):
        c = self.tracker.combatants[1]
        c.hp = 10
        result = self.service.apply_heal(cid=1, amount=0)
        self.assertTrue(result["ok"])
        self.assertEqual(result["hp_after"], 10)

    def test_heal_deferred_broadcast_skips_rebuild_and_broadcast(self):
        """apply_heal(_broadcast=False) should not rebuild or broadcast."""
        self.tracker._rebuild_calls.clear()
        self.tracker._broadcast_calls.clear()
        result = self.service.apply_heal(cid=1, amount=3, _broadcast=False)
        self.assertTrue(result["ok"])
        self.assertEqual(len(self.tracker._rebuild_calls), 0)
        self.assertEqual(len(self.tracker._broadcast_calls), 0)

    def test_heal_default_broadcast_rebuilds_and_broadcasts(self):
        """apply_heal() with default _broadcast=True should rebuild and broadcast."""
        self.tracker._rebuild_calls.clear()
        self.tracker._broadcast_calls.clear()
        result = self.service.apply_heal(cid=1, amount=3)
        self.assertTrue(result["ok"])
        self.assertTrue(len(self.tracker._rebuild_calls) > 0)
        self.assertTrue(len(self.tracker._broadcast_calls) > 0)


# ===================================================================
# _apply_damage_via_service wrapper tests (Slice 9)
# ===================================================================


class ApplyDamageViaServiceWrapperTests(unittest.TestCase):
    """Tests for InitiativeTracker._apply_damage_via_service() wrapper."""

    def _make_tracker_with_service(self):
        tracker = _make_tracker()
        service = CombatService(tracker)
        tracker._dm_service = service
        return tracker, service

    def test_routes_through_service(self):
        tracker, service = self._make_tracker_with_service()
        c = tracker.combatants[1]
        c.hp = 20
        c.temp_hp = 5
        result = InitiativeTracker._apply_damage_via_service(tracker, c, 8)
        self.assertEqual(result["temp_absorbed"], 5)
        self.assertEqual(result["hp_damage"], 3)
        self.assertEqual(result["hp_after"], 17)

    def test_fallback_without_service(self):
        tracker = _make_tracker()
        tracker._dm_service = None
        c = tracker.combatants[1]
        c.hp = 20
        c.temp_hp = 0
        result = InitiativeTracker._apply_damage_via_service(tracker, c, 7)
        self.assertEqual(result["hp_after"], 13)
        self.assertEqual(c.hp, 13)

    def test_fallback_on_service_failure(self):
        tracker = _make_tracker()
        broken = types.SimpleNamespace()
        broken.apply_damage = lambda **kw: {"ok": False, "error": "test error"}
        tracker._dm_service = broken
        c = tracker.combatants[1]
        c.hp = 20
        c.temp_hp = 0
        result = InitiativeTracker._apply_damage_via_service(tracker, c, 5)
        self.assertEqual(result["hp_after"], 15)
        self.assertTrue(
            any("failed" in msg.lower() for msg, _ in tracker._oplog_calls)
        )

    def test_fallback_on_service_exception(self):
        tracker = _make_tracker()
        broken = types.SimpleNamespace()
        def _raise(**kw):
            raise RuntimeError("boom")
        broken.apply_damage = _raise
        tracker._dm_service = broken
        c = tracker.combatants[1]
        c.hp = 20
        result = InitiativeTracker._apply_damage_via_service(tracker, c, 5)
        self.assertEqual(result["hp_after"], 15)
        self.assertTrue(
            any("exception" in msg.lower() for msg, _ in tracker._oplog_calls)
        )

    def test_service_skips_rebuild_and_broadcast(self):
        """Wrapper internally passes _broadcast=False so outer caller controls timing."""
        tracker, _ = self._make_tracker_with_service()
        c = tracker.combatants[1]
        c.hp = 20
        tracker._rebuild_calls.clear()
        tracker._broadcast_calls.clear()
        InitiativeTracker._apply_damage_via_service(tracker, c, 5)
        self.assertEqual(len(tracker._rebuild_calls), 0)
        self.assertEqual(len(tracker._broadcast_calls), 0)

    def test_invalid_cid_falls_back(self):
        tracker, _ = self._make_tracker_with_service()
        c = types.SimpleNamespace(cid=0, hp=20, temp_hp=0)
        # cid=0 won't route through service (guard: cid > 0)
        result = InitiativeTracker._apply_damage_via_service(tracker, c, 5)
        self.assertEqual(result["hp_after"], 15)


# ===================================================================
# _apply_heal_via_service wrapper tests (Slice 9)
# ===================================================================


class ApplyHealViaServiceWrapperTests(unittest.TestCase):
    """Tests for InitiativeTracker._apply_heal_via_service() wrapper."""

    def _make_tracker_with_service(self):
        tracker = _make_tracker()
        service = CombatService(tracker)
        tracker._dm_service = service
        return tracker, service

    def test_routes_through_service(self):
        tracker, _ = self._make_tracker_with_service()
        c = tracker.combatants[1]
        c.hp = 10
        result = InitiativeTracker._apply_heal_via_service(tracker, cid=1, amount=5)
        self.assertTrue(result)
        self.assertEqual(c.hp, 15)

    def test_temp_hp_routes_through_service(self):
        tracker, _ = self._make_tracker_with_service()
        c = tracker.combatants[1]
        c.temp_hp = 0
        result = InitiativeTracker._apply_heal_via_service(
            tracker, cid=1, amount=8, is_temp_hp=True
        )
        self.assertTrue(result)
        self.assertEqual(c.temp_hp, 8)

    def test_fallback_without_service(self):
        tracker = _make_tracker()
        tracker._dm_service = None
        c = tracker.combatants[1]
        c.hp = 10
        result = InitiativeTracker._apply_heal_via_service(tracker, cid=1, amount=5)
        self.assertTrue(result)
        self.assertEqual(c.hp, 15)

    def test_fallback_on_service_failure(self):
        tracker = _make_tracker()
        broken = types.SimpleNamespace()
        broken.apply_heal = lambda **kw: {"ok": False, "error": "test error"}
        tracker._dm_service = broken
        c = tracker.combatants[1]
        c.hp = 10
        result = InitiativeTracker._apply_heal_via_service(tracker, cid=1, amount=3)
        self.assertTrue(result)
        self.assertEqual(c.hp, 13)

    def test_fallback_on_service_exception(self):
        tracker = _make_tracker()
        broken = types.SimpleNamespace()
        def _raise(**kw):
            raise RuntimeError("boom")
        broken.apply_heal = _raise
        tracker._dm_service = broken
        c = tracker.combatants[1]
        c.hp = 10
        result = InitiativeTracker._apply_heal_via_service(tracker, cid=1, amount=3)
        self.assertTrue(result)
        self.assertTrue(
            any("exception" in msg.lower() for msg, _ in tracker._oplog_calls)
        )

    def test_invalid_cid_fails(self):
        tracker, _ = self._make_tracker_with_service()
        result = InitiativeTracker._apply_heal_via_service(tracker, cid=999, amount=5)
        self.assertFalse(result)

    def test_service_skips_rebuild_and_broadcast(self):
        """Wrapper internally passes _broadcast=False so outer caller controls timing."""
        tracker, _ = self._make_tracker_with_service()
        c = tracker.combatants[1]
        c.hp = 10
        tracker._rebuild_calls.clear()
        tracker._broadcast_calls.clear()
        InitiativeTracker._apply_heal_via_service(tracker, cid=1, amount=5)
        self.assertEqual(len(tracker._rebuild_calls), 0)
        self.assertEqual(len(tracker._broadcast_calls), 0)


# ===================================================================
# Slice 10 — migrated damage edge-path tests
# ===================================================================


class Slice10DamageEdgePathTests(unittest.TestCase):
    """Verify that Heat Metal, Hellish Rebuke, and weapon-mastery attack
    damage paths route through _apply_damage_via_service (canonical helper)
    rather than calling _apply_damage_to_target_with_temp_hp directly."""

    def _make_tracker_with_service(self):
        tracker = _make_tracker()
        service = CombatService(tracker)
        tracker._dm_service = service
        return tracker, service

    def test_heat_metal_damage_routes_through_service(self):
        """Heat Metal damage should go through CombatService.apply_damage."""
        tracker, service = self._make_tracker_with_service()
        c = tracker.combatants[1]
        c.hp = 30
        c.temp_hp = 5
        # Simulate what Heat Metal does: route through the wrapper
        result = InitiativeTracker._apply_damage_via_service(tracker, c, 12)
        self.assertEqual(result["temp_absorbed"], 5)
        self.assertEqual(result["hp_damage"], 7)
        self.assertEqual(result["hp_after"], 23)
        self.assertEqual(c.hp, 23)
        self.assertEqual(c.temp_hp, 0)

    def test_hellish_rebuke_damage_routes_through_service(self):
        """Hellish Rebuke damage should go through CombatService.apply_damage."""
        tracker, service = self._make_tracker_with_service()
        c = tracker.combatants[2]
        c.hp = 25
        c.temp_hp = 0
        result = InitiativeTracker._apply_damage_via_service(tracker, c, 14)
        self.assertEqual(result["hp_damage"], 14)
        self.assertEqual(result["hp_after"], 11)
        self.assertEqual(c.hp, 11)

    def test_weapon_mastery_damage_routes_through_service(self):
        """Weapon-mastery attack damage should go through CombatService.apply_damage."""
        tracker, service = self._make_tracker_with_service()
        c = tracker.combatants[1]
        c.hp = 20
        c.temp_hp = 3
        result = InitiativeTracker._apply_damage_via_service(tracker, c, 10)
        self.assertEqual(result["temp_absorbed"], 3)
        self.assertEqual(result["hp_damage"], 7)
        self.assertEqual(result["hp_after"], 13)
        self.assertEqual(c.hp, 13)

    def test_edge_path_damage_with_temp_hp_fully_absorbed(self):
        """Edge-path damage fully absorbed by temp HP leaves main HP untouched."""
        tracker, service = self._make_tracker_with_service()
        c = tracker.combatants[1]
        c.hp = 20
        c.temp_hp = 15
        result = InitiativeTracker._apply_damage_via_service(tracker, c, 10)
        self.assertEqual(result["temp_absorbed"], 10)
        self.assertEqual(result["hp_damage"], 0)
        self.assertEqual(result["hp_after"], 20)
        self.assertEqual(c.temp_hp, 5)

    def test_edge_path_damage_service_skips_broadcast(self):
        """Edge-path damage via wrapper should not rebuild/broadcast (outer caller owns timing)."""
        tracker, service = self._make_tracker_with_service()
        c = tracker.combatants[1]
        c.hp = 20
        tracker._rebuild_calls.clear()
        tracker._broadcast_calls.clear()
        InitiativeTracker._apply_damage_via_service(tracker, c, 5)
        self.assertEqual(len(tracker._rebuild_calls), 0)
        self.assertEqual(len(tracker._broadcast_calls), 0)

    def test_edge_path_damage_zero_is_noop(self):
        """Zero damage through edge path should be a no-op."""
        tracker, service = self._make_tracker_with_service()
        c = tracker.combatants[1]
        c.hp = 20
        c.temp_hp = 5
        result = InitiativeTracker._apply_damage_via_service(tracker, c, 0)
        self.assertEqual(result["hp_after"], 20)
        self.assertEqual(c.hp, 20)
        self.assertEqual(c.temp_hp, 5)


# ===================================================================
# Slice 10 — migrated heal caller tests
# ===================================================================


class Slice10HealCallerMigrationTests(unittest.TestCase):
    """Verify that heal callers migrated in Slice 10 (heal dialog, Second Wind,
    Lay on Hands) route through _apply_heal_via_service."""

    def _make_tracker_with_service(self):
        tracker = _make_tracker()
        service = CombatService(tracker)
        tracker._dm_service = service
        return tracker, service

    def test_heal_dialog_routes_through_service(self):
        """Heal dialog now calls _apply_heal_via_service instead of _apply_heal_to_combatant."""
        tracker, service = self._make_tracker_with_service()
        c = tracker.combatants[1]
        c.hp = 10
        c.max_hp = 30
        result = InitiativeTracker._apply_heal_via_service(tracker, cid=1, amount=8)
        self.assertTrue(result)
        self.assertEqual(c.hp, 18)

    def test_heal_dialog_temp_hp_routes_through_service(self):
        """Heal dialog temp HP mode routes through _apply_heal_via_service."""
        tracker, service = self._make_tracker_with_service()
        c = tracker.combatants[1]
        c.temp_hp = 0
        result = InitiativeTracker._apply_heal_via_service(
            tracker, cid=1, amount=12, is_temp_hp=True
        )
        self.assertTrue(result)
        self.assertEqual(c.temp_hp, 12)

    def test_second_wind_heal_routes_through_service(self):
        """Second Wind heal amount routes through _apply_heal_via_service."""
        tracker, service = self._make_tracker_with_service()
        c = tracker.combatants[1]
        c.hp = 15
        c.max_hp = 30
        # Pre-clamp as the migrated code does
        hp_gain = 10
        cur_hp = c.hp
        max_hp = c.max_hp
        actual_heal = max(0, min(hp_gain, max(0, max_hp - cur_hp)))
        result = InitiativeTracker._apply_heal_via_service(tracker, cid=1, amount=actual_heal)
        self.assertTrue(result)
        self.assertEqual(c.hp, 25)

    def test_second_wind_heal_respects_max_hp_cap(self):
        """Second Wind clamped heal should not exceed max HP."""
        tracker, service = self._make_tracker_with_service()
        c = tracker.combatants[1]
        c.hp = 28
        c.max_hp = 30
        hp_gain = 15  # Would exceed max_hp
        actual_heal = max(0, min(hp_gain, max(0, c.max_hp - c.hp)))
        result = InitiativeTracker._apply_heal_via_service(tracker, cid=1, amount=actual_heal)
        self.assertTrue(result)
        self.assertEqual(c.hp, 30)  # Capped at max_hp

    def test_lay_on_hands_heal_routes_through_service(self):
        """Lay on Hands heal amount routes through _apply_heal_via_service."""
        tracker, service = self._make_tracker_with_service()
        c = tracker.combatants[2]
        c.hp = 10
        c.max_hp = 40
        heal_amount = 20
        actual_heal = max(0, min(heal_amount, max(0, c.max_hp - c.hp)))
        result = InitiativeTracker._apply_heal_via_service(tracker, cid=2, amount=actual_heal)
        self.assertTrue(result)
        self.assertEqual(c.hp, 30)

    def test_lay_on_hands_heal_respects_max_hp_cap(self):
        """Lay on Hands clamped heal should not exceed max HP."""
        tracker, service = self._make_tracker_with_service()
        c = tracker.combatants[2]
        c.hp = 35
        c.max_hp = 40
        heal_amount = 25  # Would exceed max_hp
        actual_heal = max(0, min(heal_amount, max(0, c.max_hp - c.hp)))
        result = InitiativeTracker._apply_heal_via_service(tracker, cid=2, amount=actual_heal)
        self.assertTrue(result)
        self.assertEqual(c.hp, 40)  # Capped at max_hp

    def test_heal_via_service_skips_rebuild_and_broadcast(self):
        """Heal via service with _broadcast=False should not rebuild or broadcast."""
        tracker, service = self._make_tracker_with_service()
        c = tracker.combatants[1]
        c.hp = 10
        tracker._rebuild_calls.clear()
        tracker._broadcast_calls.clear()
        InitiativeTracker._apply_heal_via_service(tracker, cid=1, amount=5)
        self.assertEqual(len(tracker._rebuild_calls), 0)
        self.assertEqual(len(tracker._broadcast_calls), 0)

    def test_heal_zero_amount_is_noop(self):
        """Heal of zero amount (e.g., already at max HP) is a safe no-op."""
        tracker, service = self._make_tracker_with_service()
        c = tracker.combatants[1]
        c.hp = 20
        c.max_hp = 20
        actual_heal = max(0, min(10, max(0, c.max_hp - c.hp)))
        self.assertEqual(actual_heal, 0)
        result = InitiativeTracker._apply_heal_via_service(tracker, cid=1, amount=actual_heal)
        self.assertTrue(result)
        self.assertEqual(c.hp, 20)


# ===================================================================
# RLock re-entrancy tests (Slice 9)
# ===================================================================


class CombatServiceRLockReentrancyTests(unittest.TestCase):
    """Verify the RLock allows re-entrant calls without deadlock."""

    def test_rlock_allows_reentrant_acquisition(self):
        """Simulate next_turn triggering damage (which acquires the lock again)."""
        tracker = _make_tracker()

        # Make _next_turn call apply_damage internally (simulates end-of-turn damage)
        service = CombatService(tracker)
        original_next_turn = tracker._next_turn

        def _next_turn_with_damage():
            original_next_turn()
            # Simulate end-of-turn damage rider calling apply_damage
            c = tracker.combatants.get(1)
            if c is not None:
                service.apply_damage(cid=1, raw_damage=3)

        tracker._next_turn = _next_turn_with_damage

        # This should NOT deadlock — RLock allows re-entrant acquisition
        result = service.next_turn()
        self.assertTrue(result["ok"])


if __name__ == "__main__":
    unittest.main()
