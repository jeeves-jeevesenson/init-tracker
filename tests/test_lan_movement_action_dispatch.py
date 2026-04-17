import unittest

import dnd_initative_tracker as tracker_mod
from player_command_contracts import MOVEMENT_ACTION_COMMAND_TYPES
from player_command_service import PlayerCommandService


class LanMovementActionDispatchTests(unittest.TestCase):
    def test_service_dispatcher_routes_every_movement_action_command(self):
        service = PlayerCommandService(type("TrackerStub", (), {})())
        calls = []
        ordered_types = sorted(MOVEMENT_ACTION_COMMAND_TYPES)

        def _make_handler(expected_type):
            def _handler(msg, *, cid, ws_id, is_admin):
                calls.append((expected_type, dict(msg), cid, ws_id, is_admin))
                return {"ok": True, "command_type": expected_type}

            return _handler

        for command_type in ordered_types:
            setattr(service, command_type, _make_handler(command_type))

        for index, command_type in enumerate(ordered_types):
            result = service.dispatch_movement_action_command(
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
        result = service.dispatch_movement_action_command(
            {"type": "initiative_roll"},
            cid=1,
            ws_id=17,
            is_admin=False,
        )
        self.assertFalse(result.get("ok"))
        self.assertEqual(result.get("reason"), "unsupported_command")
        self.assertEqual(result.get("received_type"), "initiative_roll")

    def test_lan_apply_action_routes_movement_action_family_through_dispatcher(self):
        app = object.__new__(tracker_mod.InitiativeTracker)
        app._oplog = lambda *args, **kwargs: None
        app._is_admin_token_valid = lambda token: False
        app._summon_can_be_controlled_by = lambda claimed, target: False
        app._is_valid_summon_turn_for_controller = lambda controlling, target, current: True
        app.in_combat = False
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

            def dispatch_movement_action_command(self, msg, *, cid, ws_id, is_admin):
                self.calls.append((str(msg.get("type")), cid, ws_id, is_admin))
                return {"ok": True}

        service_stub = ServiceStub()
        app._ensure_player_commands = lambda: service_stub

        ordered_types = sorted(MOVEMENT_ACTION_COMMAND_TYPES)
        sample_messages = {
            "move": {"to": {"col": 4, "row": 5}},
            "cycle_movement_mode": {},
            "perform_action": {"spend": "action", "action": "Disengage"},
        }
        for command_type in ordered_types:
            payload = {
                "type": command_type,
                "cid": 1,
                "_claimed_cid": 1,
                "_ws_id": 81,
            }
            payload.update(sample_messages.get(command_type, {}))
            app._lan_apply_action(payload)

        self.assertEqual([entry[0] for entry in service_stub.calls], ordered_types)


class LanMovementActionBehaviorTests(unittest.TestCase):
    def test_cycle_movement_mode_handler_rotates_and_toasts(self):
        tracker = type("TrackerStub", (), {})()
        tracker._lan_toasts = []
        tracker._rebuild_calls = []
        tracker._lan = type(
            "LanStub",
            (),
            {
                "toast": lambda _self, ws_id, text: tracker._lan_toasts.append((ws_id, text)),
            },
        )()
        tracker._normalize_movement_mode = lambda mode: str(mode or "normal").strip().lower() or "normal"
        tracker._set_movement_mode = lambda cid, mode: setattr(tracker.combatants[int(cid)], "movement_mode", mode)
        tracker._movement_mode_label = lambda mode: str(mode).title()
        tracker._rebuild_table = lambda **kwargs: tracker._rebuild_calls.append(kwargs)
        tracker.combatants = {
            1: type(
                "C",
                (),
                {
                    "cid": 1,
                    "movement_mode": "normal",
                    "swim_speed": 30,
                    "fly_speed": 60,
                    "burrow_speed": 0,
                },
            )()
        }

        result = PlayerCommandService(tracker).cycle_movement_mode(
            {"type": "cycle_movement_mode"},
            cid=1,
            ws_id=5,
            is_admin=False,
        )

        self.assertTrue(result.get("ok"))
        self.assertEqual(tracker.combatants[1].movement_mode, "swim")
        self.assertIn((5, "Movement mode: Swim."), tracker._lan_toasts)
        self.assertEqual(len(tracker._rebuild_calls), 1)

    def test_perform_action_handler_spends_reaction(self):
        tracker = type("TrackerStub", (), {})()
        tracker._lan_toasts = []
        tracker._logs = []
        tracker._rebuild_calls = []
        tracker._lan = type(
            "LanStub",
            (),
            {
                "toast": lambda _self, ws_id, text: tracker._lan_toasts.append((ws_id, text)),
            },
        )()
        tracker._find_action_entry = lambda c, spend, action: {"name": action}
        tracker._action_name_key = lambda value: str(value or "").strip().lower()
        tracker._is_create_undead_uncommanded_this_turn = lambda c: False
        tracker._mount_action_is_restricted = lambda c, action_name: False
        tracker._target_has_otto_dance_active = lambda c: False
        tracker._use_reaction = lambda c: setattr(c, "reaction_remaining", max(0, int(getattr(c, "reaction_remaining", 0)) - 1)) or True
        tracker._log = lambda message, **kwargs: tracker._logs.append((message, kwargs))
        tracker._rebuild_table = lambda **kwargs: tracker._rebuild_calls.append(kwargs)
        tracker.combatants = {
            1: type(
                "C",
                (),
                {
                    "cid": 1,
                    "name": "Aelar",
                    "reaction_remaining": 1,
                    "actions": [],
                    "bonus_actions": [],
                    "reactions": [{"name": "Opportunity Attack", "type": "reaction"}],
                },
            )()
        }

        result = PlayerCommandService(tracker).perform_action(
            {
                "type": "perform_action",
                "spend": "reaction",
                "action": "Opportunity Attack",
            },
            cid=1,
            ws_id=42,
            is_admin=False,
        )

        self.assertTrue(result.get("ok"))
        self.assertEqual(tracker.combatants[1].reaction_remaining, 0)
        self.assertIn((42, "Used Opportunity Attack."), tracker._lan_toasts)
        self.assertTrue(any("used Opportunity Attack (reaction)" in message for message, _kwargs in tracker._logs))
        self.assertEqual(len(tracker._rebuild_calls), 1)


if __name__ == "__main__":
    unittest.main()
