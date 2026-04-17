import unittest

import dnd_initative_tracker as tracker_mod
from player_command_contracts import TURN_LOCAL_COMMAND_TYPES
from player_command_service import PlayerCommandService


class LanTurnLocalCommandDispatchTests(unittest.TestCase):
    def test_service_dispatcher_routes_every_turn_local_command(self):
        service = PlayerCommandService(type("TrackerStub", (), {})())
        calls = []
        ordered_types = sorted(TURN_LOCAL_COMMAND_TYPES)

        def _make_handler(expected_type):
            def _handler(msg, *, cid, ws_id, is_admin):
                calls.append((expected_type, dict(msg), cid, ws_id, is_admin))
                return {"ok": True, "command_type": expected_type}

            return _handler

        for command_type in ordered_types:
            setattr(service, command_type, _make_handler(command_type))

        for index, command_type in enumerate(ordered_types):
            result = service.dispatch_turn_local_command(
                {"type": command_type},
                cid=1,
                ws_id=index,
                is_admin=False,
            )
            self.assertTrue(result.get("ok"))
            self.assertEqual(result.get("command_type"), command_type)

        self.assertEqual([entry[0] for entry in calls], ordered_types)

    def test_service_dispatcher_rejects_unknown_command(self):
        service = PlayerCommandService(type("TrackerStub", (), {})())
        result = service.dispatch_turn_local_command(
            {"type": "initiative_roll"},
            cid=1,
            ws_id=17,
            is_admin=False,
        )
        self.assertFalse(result.get("ok"))
        self.assertEqual(result.get("reason"), "unsupported_command")
        self.assertEqual(result.get("received_type"), "initiative_roll")

    def test_lan_apply_action_routes_turn_local_family_through_dispatcher(self):
        app = object.__new__(tracker_mod.InitiativeTracker)
        app._oplog = lambda *args, **kwargs: None
        app._is_admin_token_valid = lambda token: False
        app._summon_can_be_controlled_by = lambda claimed, target: False
        app._is_valid_summon_turn_for_controller = lambda controlling, target, current: True
        app.combatants = {1: type("C", (), {"cid": 1})()}
        app._lan = type(
            "LanStub",
            (),
            {
                "toast": lambda *_args, **_kwargs: None,
                "_append_lan_log": lambda *args, **kwargs: None,
                "_loop": None,
            },
        )()

        class ServiceStub:
            def __init__(self):
                self.calls = []

            def dispatch_turn_local_command(self, msg, *, cid, ws_id, is_admin):
                self.calls.append((str(msg.get("type")), cid, ws_id, is_admin))
                return {"ok": True}

        service_stub = ServiceStub()
        app._ensure_player_commands = lambda: service_stub

        ordered_types = sorted(TURN_LOCAL_COMMAND_TYPES)
        for command_type in ordered_types:
            app._lan_apply_action(
                {
                    "type": command_type,
                    "cid": 1,
                    "_claimed_cid": 1,
                    "_ws_id": 81,
                }
            )

        self.assertEqual([entry[0] for entry in service_stub.calls], ordered_types)


class LanTurnLocalCommandBehaviorTests(unittest.TestCase):
    def _make_tracker(self):
        tracker = type("TrackerStub", (), {})()
        tracker._lan_toasts = []
        tracker._logs = []
        tracker._rebuild_calls = []
        tracker._update_turn_ui_calls = []
        tracker._normalize_concentration_state_calls = []
        tracker._lan = type(
            "LanStub",
            (),
            {
                "toast": lambda _self, ws_id, text: tracker._lan_toasts.append((ws_id, text)),
            },
        )()
        tracker._log = lambda message, **kwargs: tracker._logs.append((message, kwargs))
        tracker._rebuild_table = lambda **kwargs: tracker._rebuild_calls.append(kwargs)
        tracker._lan_force_state_broadcast = lambda: tracker._logs.append(("broadcast", {}))
        tracker._mode_speed = lambda c: int(getattr(c, "speed", 0) or 0)
        tracker._effective_speed = lambda c: int(getattr(c, "speed", 0) or 0)
        tracker._has_condition = lambda c, ctype: ctype in list(getattr(c, "condition_stacks", []) or [])
        tracker._remove_condition_type = lambda c, ctype: setattr(
            c,
            "condition_stacks",
            [entry for entry in list(getattr(c, "condition_stacks", []) or []) if entry != ctype],
        )
        tracker._mount_cost = lambda rider: max(0, int(getattr(rider, "speed", 0) or 0) // 2)
        tracker._restore_mount_initiative = lambda rider_cid, mount_cid: None
        tracker._normalize_concentration_state = lambda: tracker._normalize_concentration_state_calls.append(True)
        tracker._update_turn_ui = lambda: tracker._update_turn_ui_calls.append(True)
        tracker._map_window = None
        tracker._turn_snapshots = {}
        tracker._lan_positions = {}
        return tracker

    def test_dash_spends_action_and_adds_movement(self):
        tracker = self._make_tracker()
        combatant = type(
            "C",
            (),
            {
                "cid": 1,
                "name": "Runner",
                "speed": 30,
                "move_total": 30,
                "move_remaining": 15,
                "action_remaining": 1,
                "bonus_action_remaining": 1,
            },
        )()
        tracker.combatants = {1: combatant}
        tracker._use_action = lambda c: setattr(c, "action_remaining", max(0, int(getattr(c, "action_remaining", 0)) - 1)) or True
        tracker._use_bonus_action = lambda c: setattr(c, "bonus_action_remaining", max(0, int(getattr(c, "bonus_action_remaining", 0)) - 1)) or True

        result = PlayerCommandService(tracker).dash(
            {"type": "dash", "spend": "action"},
            cid=1,
            ws_id=7,
            is_admin=False,
        )

        self.assertTrue(result.get("ok"))
        self.assertEqual(combatant.action_remaining, 0)
        self.assertEqual(combatant.move_total, 60)
        self.assertEqual(combatant.move_remaining, 45)
        self.assertIn((7, "Dashed (action)."), tracker._lan_toasts)
        self.assertEqual(len(tracker._rebuild_calls), 1)

    def test_use_action_and_bonus_action_spend_resources(self):
        tracker = self._make_tracker()
        combatant = type(
            "C",
            (),
            {
                "cid": 1,
                "name": "Scout",
                "action_remaining": 1,
                "bonus_action_remaining": 1,
            },
        )()
        tracker.combatants = {1: combatant}
        tracker._use_action = lambda c: setattr(c, "action_remaining", max(0, int(getattr(c, "action_remaining", 0)) - 1)) or True
        tracker._use_bonus_action = lambda c: setattr(c, "bonus_action_remaining", max(0, int(getattr(c, "bonus_action_remaining", 0)) - 1)) or True

        service = PlayerCommandService(tracker)
        action_result = service.use_action({"type": "use_action"}, cid=1, ws_id=3, is_admin=False)
        bonus_result = service.use_bonus_action({"type": "use_bonus_action"}, cid=1, ws_id=3, is_admin=False)

        self.assertTrue(action_result.get("ok"))
        self.assertTrue(bonus_result.get("ok"))
        self.assertEqual(combatant.action_remaining, 0)
        self.assertEqual(combatant.bonus_action_remaining, 0)
        self.assertIn((3, "Action used."), tracker._lan_toasts)
        self.assertIn((3, "Bonus action used."), tracker._lan_toasts)
        self.assertEqual(len(tracker._rebuild_calls), 2)

    def test_stand_up_spends_half_speed_and_clears_prone(self):
        tracker = self._make_tracker()
        combatant = type(
            "C",
            (),
            {
                "cid": 1,
                "name": "Bruiser",
                "speed": 30,
                "move_remaining": 20,
                "condition_stacks": ["prone"],
            },
        )()
        tracker.combatants = {1: combatant}

        result = PlayerCommandService(tracker).stand_up(
            {"type": "stand_up"},
            cid=1,
            ws_id=9,
            is_admin=False,
        )

        self.assertTrue(result.get("ok"))
        self.assertEqual(combatant.move_remaining, 5)
        self.assertEqual(combatant.condition_stacks, [])
        self.assertIn((9, "Stood up."), tracker._lan_toasts)
        self.assertEqual(len(tracker._rebuild_calls), 1)

    def test_reset_turn_restores_snapshot_and_logs(self):
        tracker = self._make_tracker()
        combatant = type(
            "C",
            (),
            {
                "cid": 1,
                "name": "Resetter",
                "move_remaining": 0,
                "move_total": 0,
                "action_remaining": 0,
                "action_total": 0,
                "attack_resource_remaining": 0,
                "bonus_action_remaining": 0,
                "reaction_remaining": 0,
                "spell_cast_remaining": 0,
            },
        )()
        tracker.combatants = {1: combatant}
        tracker._turn_snapshots = {
            1: {
                "col": 4,
                "row": 5,
                "move_remaining": 20,
                "move_total": 30,
                "action_remaining": 1,
                "action_total": 1,
                "attack_resource_remaining": 1,
                "bonus_action_remaining": 1,
                "reaction_remaining": 1,
                "spell_cast_remaining": 1,
            }
        }
        tracker._lan_positions = {1: (0, 0)}
        tracker._lan_restore_turn_snapshot = tracker_mod.InitiativeTracker._lan_restore_turn_snapshot.__get__(
            tracker,
            type(tracker),
        )

        result = PlayerCommandService(tracker).reset_turn(
            {"type": "reset_turn"},
            cid=1,
            ws_id=12,
            is_admin=False,
        )

        self.assertTrue(result.get("ok"))
        self.assertEqual(combatant.move_remaining, 20)
        self.assertEqual(combatant.action_remaining, 1)
        self.assertEqual(tracker._lan_positions[1], (4, 5))
        self.assertIn((12, "Turn reset."), tracker._lan_toasts)
        self.assertEqual(len(tracker._rebuild_calls), 1)
        self.assertEqual(len(tracker._normalize_concentration_state_calls), 1)
        self.assertEqual(len(tracker._update_turn_ui_calls), 1)


if __name__ == "__main__":
    unittest.main()
