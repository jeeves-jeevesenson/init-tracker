import unittest

import dnd_initative_tracker as tracker_mod
from player_command_contracts import UTILITY_ADMIN_COMMAND_TYPES
from player_command_service import PlayerCommandService


class LanUtilityAdminDispatchTests(unittest.TestCase):
    def test_service_dispatcher_routes_every_utility_admin_command(self):
        service = PlayerCommandService(type("TrackerStub", (), {})())
        calls = []
        ordered_types = sorted(UTILITY_ADMIN_COMMAND_TYPES)

        def _make_handler(expected_type):
            def _handler(msg, *, cid, ws_id, is_admin, claimed=None):
                calls.append((expected_type, dict(msg), cid, ws_id, is_admin, claimed))
                return {"ok": True, "command_type": expected_type}

            return _handler

        for command_type in ordered_types:
            setattr(service, command_type, _make_handler(command_type))

        for index, command_type in enumerate(ordered_types):
            result = service.dispatch_utility_admin_command(
                {"type": command_type},
                cid=1,
                ws_id=index,
                is_admin=False,
                claimed=77,
            )
            self.assertTrue(result.get("ok"))
            self.assertEqual(result.get("command_type"), command_type)

        self.assertEqual([entry[0] for entry in calls], ordered_types)
        self.assertTrue(all(entry[5] == 77 for entry in calls))

    def test_service_dispatcher_rejects_unknown_command(self):
        service = PlayerCommandService(type("TrackerStub", (), {})())
        result = service.dispatch_utility_admin_command(
            {"type": "manual_override_hp"},
            cid=1,
            ws_id=17,
            is_admin=False,
            claimed=1,
        )
        self.assertFalse(result.get("ok"))
        self.assertEqual(result.get("reason"), "unsupported_command")
        self.assertEqual(result.get("received_type"), "manual_override_hp")

    def test_lan_apply_action_routes_family_commands_through_dispatcher(self):
        app = object.__new__(tracker_mod.InitiativeTracker)
        app._oplog = lambda *args, **kwargs: None
        app._is_admin_token_valid = lambda token: token == "ok-admin-token"
        app._summon_can_be_controlled_by = lambda claimed, target: False
        app._is_valid_summon_turn_for_controller = lambda controlling, target, current: True
        app.in_combat = True
        app.current_cid = 1
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

            def dispatch_utility_admin_command(self, msg, *, cid, ws_id, is_admin, claimed=None):
                self.calls.append((str(msg.get("type")), cid, ws_id, is_admin, claimed))
                return {"ok": True}

        service_stub = ServiceStub()
        app._ensure_player_commands = lambda: service_stub

        sample_payloads = {
            "set_color": {"color": "#00ff00", "border_color": "#ffffff"},
            "set_facing": {"facing_deg": 180},
            "set_auras_enabled": {"enabled": False},
            "reset_player_characters": {},
        }
        for command_type in sorted(UTILITY_ADMIN_COMMAND_TYPES):
            payload = {
                "type": command_type,
                "cid": 1,
                "_claimed_cid": 1,
                "_ws_id": 81,
                "admin_token": "ok-admin-token",
            }
            payload.update(sample_payloads.get(command_type, {}))
            app._lan_apply_action(payload)

        self.assertEqual([entry[0] for entry in service_stub.calls], sorted(UTILITY_ADMIN_COMMAND_TYPES))
        self.assertTrue(all(entry[3] is True for entry in service_stub.calls))
        self.assertTrue(all(entry[4] == 1 for entry in service_stub.calls))


class LanUtilityAdminServiceBehaviorTests(unittest.TestCase):
    def test_family_handlers_delegate_to_tracker_request_helpers(self):
        tracker = type("TrackerStub", (), {})()
        tracker._lan = type("LanStub", (), {"toast": lambda *_args, **_kwargs: None})()
        tracker._oplog = lambda *args, **kwargs: None
        calls = []

        tracker._handle_set_color_request = (
            lambda msg, *, cid, ws_id, is_admin: calls.append(
                ("_handle_set_color_request", dict(msg), cid, ws_id, is_admin, None)
            )
        )
        tracker._handle_set_facing_request = (
            lambda msg, *, cid, ws_id, is_admin, claimed: calls.append(
                ("_handle_set_facing_request", dict(msg), cid, ws_id, is_admin, claimed)
            )
        )
        tracker._handle_set_auras_enabled_request = (
            lambda msg, *, cid, ws_id, is_admin: calls.append(
                ("_handle_set_auras_enabled_request", dict(msg), cid, ws_id, is_admin, None)
            )
        )
        tracker._handle_reset_player_characters_request = (
            lambda msg, *, cid, ws_id, is_admin: calls.append(
                ("_handle_reset_player_characters_request", dict(msg), cid, ws_id, is_admin, None)
            )
        )

        service = PlayerCommandService(tracker)
        dispatches = [
            ("set_color", {"type": "set_color", "color": "#00ff00", "border_color": "#ffffff"}),
            ("set_facing", {"type": "set_facing", "facing_deg": 90}),
            ("set_auras_enabled", {"type": "set_auras_enabled", "enabled": True}),
            ("reset_player_characters", {"type": "reset_player_characters"}),
        ]

        for command_type, payload in dispatches:
            result = getattr(service, command_type)(
                dict(payload),
                cid=7,
                ws_id=12,
                is_admin=True,
                claimed=99,
            )
            self.assertTrue(result.get("ok"))
            self.assertEqual((result.get("request") or {}).get("command_type"), command_type)
            self.assertEqual(calls[-1][1], payload)
            self.assertEqual(calls[-1][2:5], (7, 12, True))

        self.assertEqual(calls[1][0], "_handle_set_facing_request")
        self.assertEqual(calls[1][5], 99)


if __name__ == "__main__":
    unittest.main()
