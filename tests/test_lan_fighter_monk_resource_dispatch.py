import unittest

import dnd_initative_tracker as tracker_mod
from player_command_contracts import FIGHTER_MONK_RESOURCE_ACTION_TYPES
from player_command_service import PlayerCommandService


class LanFighterMonkResourceDispatchTests(unittest.TestCase):
    def test_service_dispatcher_routes_every_fighter_monk_resource_command(self):
        service = PlayerCommandService(type("TrackerStub", (), {})())
        calls = []
        ordered_types = sorted(FIGHTER_MONK_RESOURCE_ACTION_TYPES)

        def _make_handler(expected_type):
            def _handler(msg, *, cid, ws_id, is_admin):
                calls.append((expected_type, dict(msg), cid, ws_id, is_admin))
                return {"ok": True, "command_type": expected_type}

            return _handler

        for command_type in ordered_types:
            setattr(service, command_type, _make_handler(command_type))

        for index, command_type in enumerate(ordered_types):
            result = service.dispatch_fighter_monk_resource_action(
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
        result = service.dispatch_fighter_monk_resource_action(
            {"type": "lay_on_hands_use"},
            cid=1,
            ws_id=17,
            is_admin=False,
        )
        self.assertFalse(result.get("ok"))
        self.assertEqual(result.get("reason"), "unsupported_command")
        self.assertEqual(result.get("received_type"), "lay_on_hands_use")

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

            def dispatch_fighter_monk_resource_action(self, msg, *, cid, ws_id, is_admin):
                self.calls.append((str(msg.get("type")), cid, ws_id, is_admin))
                return {"ok": True}

        service_stub = ServiceStub()
        app._ensure_player_commands = lambda: service_stub

        ordered_types = sorted(FIGHTER_MONK_RESOURCE_ACTION_TYPES)
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


if __name__ == "__main__":
    unittest.main()
