"""Tests for the CombatService canonical backend seam.

These tests validate that the service layer correctly reads and mutates
combat state, and that state propagates properly through the service
without requiring the Tkinter UI to be running.
"""
import types
import unittest

from helper_script import ConditionStack

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

    # Service-routing wrappers (mirror the real tracker methods).
    def _next_turn_via_service():
        dm_svc = getattr(app, "_dm_service", None)
        if dm_svc is not None:
            try:
                result = dm_svc.next_turn()
                if result.get("ok"):
                    return
            except Exception:
                pass
        _next_turn()
        try:
            _lan_force_state_broadcast()
        except Exception:
            pass

    def _adjust_hp_via_service(cid, delta):
        dm_svc = getattr(app, "_dm_service", None)
        if dm_svc is not None:
            try:
                result = dm_svc.adjust_hp(cid=int(cid), delta=int(delta))
                if result.get("ok"):
                    return True
            except Exception:
                pass
        c = app.combatants.get(int(cid))
        if c is None:
            return False
        old_hp = int(getattr(c, "hp", 0) or 0)
        max_hp = int(getattr(c, "max_hp", old_hp) or old_hp)
        new_hp = max(0, old_hp + int(delta))
        if max_hp > 0:
            new_hp = min(new_hp, max_hp)
        setattr(c, "hp", new_hp)
        try:
            _rebuild_table(scroll_to_current=True)
        except Exception:
            pass
        try:
            _lan_force_state_broadcast()
        except Exception:
            pass
        return True

    def _set_condition_via_service(cid, ctype, action, remaining_turns=None):
        dm_svc = getattr(app, "_dm_service", None)
        if dm_svc is not None:
            try:
                result = dm_svc.set_condition(
                    cid=int(cid), ctype=ctype, action=action,
                    remaining_turns=remaining_turns,
                )
                if result.get("ok"):
                    return True
            except Exception:
                pass
        c = app.combatants.get(int(cid))
        if c is None:
            return False
        ctype_key = str(ctype or "").strip().lower()
        if not ctype_key:
            return False
        action_key = str(action or "").strip().lower()
        if action_key == "add":
            try:
                _ensure_condition_stack(c, ctype_key, remaining_turns)
            except Exception:
                return False
        elif action_key == "remove":
            try:
                _remove_condition_type(c, ctype_key)
            except Exception:
                return False
        else:
            return False
        try:
            _rebuild_table(scroll_to_current=True)
        except Exception:
            pass
        try:
            _lan_force_state_broadcast()
        except Exception:
            pass
        return True

    def _set_temp_hp_via_service(cid, amount):
        dm_svc = getattr(app, "_dm_service", None)
        if dm_svc is not None:
            try:
                result = dm_svc.set_temp_hp(cid=int(cid), amount=int(amount))
                if result.get("ok"):
                    return True
            except Exception:
                pass
        c = app.combatants.get(int(cid))
        if c is None:
            return False
        setattr(c, "temp_hp", max(0, int(amount)))
        try:
            _rebuild_table(scroll_to_current=True)
        except Exception:
            pass
        try:
            _lan_force_state_broadcast()
        except Exception:
            pass
        return True

    app._next_turn_via_service = _next_turn_via_service
    app._adjust_hp_via_service = _adjust_hp_via_service
    app._set_condition_via_service = _set_condition_via_service
    app._set_temp_hp_via_service = _set_temp_hp_via_service

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
        import threading
        self.assertIsInstance(self.service._lock, type(threading.Lock()))

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
    """Tests for the _*_via_service() wrapper methods on the tracker.

    These verify that when _dm_service is set, the wrapper delegates to
    CombatService, and when it is not set, the wrapper falls back to
    direct mutation.
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
        result = tracker._adjust_hp_via_service(cid=1, delta=-5)
        self.assertTrue(result)
        self.assertEqual(c.hp, old_hp - 5)

    def test_adjust_hp_via_service_fallback_without_service(self):
        tracker = _make_tracker()
        tracker._dm_service = None
        c = tracker.combatants[1]
        old_hp = c.hp
        result = tracker._adjust_hp_via_service(cid=1, delta=-3)
        self.assertTrue(result)
        self.assertEqual(c.hp, old_hp - 3)

    def test_adjust_hp_via_service_invalid_cid(self):
        tracker, service = self._make_tracker_with_service()
        result = tracker._adjust_hp_via_service(cid=999, delta=-5)
        self.assertFalse(result)

    def test_adjust_hp_via_service_broadcasts(self):
        tracker, service = self._make_tracker_with_service()
        before = len(tracker._broadcast_calls)
        tracker._adjust_hp_via_service(cid=1, delta=-5)
        self.assertGreater(len(tracker._broadcast_calls), before)

    # -- _set_condition_via_service --

    def test_set_condition_via_service_adds_condition(self):
        tracker, service = self._make_tracker_with_service()
        result = tracker._set_condition_via_service(cid=1, ctype="poisoned", action="add")
        self.assertTrue(result)
        c = tracker.combatants[1]
        ctypes = [st.ctype for st in c.condition_stacks]
        self.assertIn("poisoned", ctypes)

    def test_set_condition_via_service_removes_condition(self):
        tracker, service = self._make_tracker_with_service()
        tracker._set_condition_via_service(cid=1, ctype="stunned", action="add")
        result = tracker._set_condition_via_service(cid=1, ctype="stunned", action="remove")
        self.assertTrue(result)
        c = tracker.combatants[1]
        ctypes = [st.ctype for st in c.condition_stacks]
        self.assertNotIn("stunned", ctypes)

    def test_set_condition_via_service_fallback(self):
        tracker = _make_tracker()
        tracker._dm_service = None
        result = tracker._set_condition_via_service(cid=1, ctype="blinded", action="add")
        self.assertTrue(result)
        c = tracker.combatants[1]
        ctypes = [st.ctype for st in c.condition_stacks]
        self.assertIn("blinded", ctypes)

    def test_set_condition_via_service_invalid_cid(self):
        tracker, service = self._make_tracker_with_service()
        result = tracker._set_condition_via_service(cid=999, ctype="poisoned", action="add")
        self.assertFalse(result)

    # -- _set_temp_hp_via_service --

    def test_set_temp_hp_via_service_sets_value(self):
        tracker, service = self._make_tracker_with_service()
        result = tracker._set_temp_hp_via_service(cid=1, amount=10)
        self.assertTrue(result)
        self.assertEqual(tracker.combatants[1].temp_hp, 10)

    def test_set_temp_hp_via_service_clears_temp_hp(self):
        tracker, service = self._make_tracker_with_service()
        tracker.combatants[1].temp_hp = 8
        result = tracker._set_temp_hp_via_service(cid=1, amount=0)
        self.assertTrue(result)
        self.assertEqual(tracker.combatants[1].temp_hp, 0)

    def test_set_temp_hp_via_service_fallback(self):
        tracker = _make_tracker()
        tracker._dm_service = None
        result = tracker._set_temp_hp_via_service(cid=1, amount=15)
        self.assertTrue(result)
        self.assertEqual(tracker.combatants[1].temp_hp, 15)

    def test_set_temp_hp_via_service_invalid_cid(self):
        tracker, service = self._make_tracker_with_service()
        result = tracker._set_temp_hp_via_service(cid=999, amount=10)
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
