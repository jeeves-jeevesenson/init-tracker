import unittest

import dnd_initative_tracker as tracker_mod
from player_command_contracts import AOE_MANIPULATION_COMMAND_TYPES
from player_command_service import PlayerCommandService


class LanAoeManipulationDispatchTests(unittest.TestCase):
    def test_service_dispatcher_routes_every_aoe_manipulation_command(self):
        service = PlayerCommandService(type("TrackerStub", (), {})())
        calls = []
        ordered_types = sorted(AOE_MANIPULATION_COMMAND_TYPES)

        def _make_handler(expected_type):
            def _handler(msg, *, cid, ws_id, is_admin, claimed=None):
                calls.append((expected_type, dict(msg), cid, ws_id, is_admin, claimed))
                return {"ok": True, "command_type": expected_type}

            return _handler

        for command_type in ordered_types:
            setattr(service, command_type, _make_handler(command_type))

        for index, command_type in enumerate(ordered_types):
            result = service.dispatch_aoe_manipulation_command(
                {"type": command_type},
                cid=1,
                ws_id=index,
                is_admin=False,
                claimed=99,
            )
            self.assertTrue(result.get("ok"))
            self.assertEqual(result.get("command_type"), command_type)

        self.assertEqual([entry[0] for entry in calls], ordered_types)
        self.assertTrue(all(entry[5] == 99 for entry in calls))

    def test_service_dispatcher_rejects_unknown_command(self):
        service = PlayerCommandService(type("TrackerStub", (), {})())
        result = service.dispatch_aoe_manipulation_command(
            {"type": "cast_aoe_adjust"},
            cid=1,
            ws_id=17,
            is_admin=False,
            claimed=1,
        )
        self.assertFalse(result.get("ok"))
        self.assertEqual(result.get("reason"), "unsupported_command")
        self.assertEqual(result.get("received_type"), "cast_aoe_adjust")

    def test_lan_apply_action_routes_family_commands_through_dispatcher(self):
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

            def dispatch_aoe_manipulation_command(self, msg, *, cid, ws_id, is_admin, claimed=None):
                self.calls.append((str(msg.get("type")), cid, ws_id, is_admin, claimed))
                return {"ok": True}

        service_stub = ServiceStub()
        app._ensure_player_commands = lambda: service_stub

        for command_type in sorted(AOE_MANIPULATION_COMMAND_TYPES):
            app._lan_apply_action(
                {
                    "type": command_type,
                    "cid": 1,
                    "_claimed_cid": 1,
                    "_ws_id": 81,
                    "aid": 5,
                    "to": {"cx": 1.0, "cy": 2.0},
                }
            )

        self.assertEqual([entry[0] for entry in service_stub.calls], sorted(AOE_MANIPULATION_COMMAND_TYPES))
        self.assertTrue(all(entry[4] == 1 for entry in service_stub.calls))


class LanAoeManipulationServiceBehaviorTests(unittest.TestCase):
    def test_aoe_move_delegates_to_tracker_handler(self):
        tracker = type("TrackerStub", (), {})()
        calls = []
        tracker._handle_aoe_move_request = (
            lambda msg, *, cid, ws_id, is_admin, claimed=None: calls.append((dict(msg), cid, ws_id, is_admin, claimed))
        )
        tracker._lan = type("LanStub", (), {"toast": lambda *_args, **_kwargs: None})()

        result = PlayerCommandService(tracker).aoe_move(
            {"type": "aoe_move", "aid": 11, "to": {"cx": 4.0, "cy": 5.0}},
            cid=7,
            ws_id=12,
            is_admin=False,
            claimed=7,
        )

        self.assertTrue(result.get("ok"))
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][1:], (7, 12, False, 7))

    def test_aoe_remove_delegates_to_tracker_handler(self):
        tracker = type("TrackerStub", (), {})()
        calls = []
        tracker._handle_aoe_remove_request = (
            lambda msg, *, cid, ws_id, is_admin, claimed=None: calls.append((dict(msg), cid, ws_id, is_admin, claimed))
        )
        tracker._lan = type("LanStub", (), {"toast": lambda *_args, **_kwargs: None})()

        result = PlayerCommandService(tracker).aoe_remove(
            {"type": "aoe_remove", "aid": 11},
            cid=7,
            ws_id=12,
            is_admin=False,
            claimed=7,
        )

        self.assertTrue(result.get("ok"))
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][1:], (7, 12, False, 7))


if __name__ == "__main__":
    unittest.main()
