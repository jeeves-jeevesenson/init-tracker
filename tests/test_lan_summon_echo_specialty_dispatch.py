import unittest

import dnd_initative_tracker as tracker_mod
from player_command_contracts import SUMMON_ECHO_SPECIALTY_COMMAND_TYPES
from player_command_service import PlayerCommandService


class LanSummonEchoSpecialtyDispatchTests(unittest.TestCase):
    def test_service_dispatcher_routes_every_summon_echo_specialty_command(self):
        service = PlayerCommandService(type("TrackerStub", (), {})())
        calls = []
        ordered_types = sorted(SUMMON_ECHO_SPECIALTY_COMMAND_TYPES)

        def _make_handler(expected_type):
            def _handler(msg, *, cid, ws_id, is_admin, claimed=None):
                calls.append((expected_type, dict(msg), cid, ws_id, is_admin, claimed))
                return {"ok": True, "command_type": expected_type}

            return _handler

        for command_type in ordered_types:
            setattr(service, command_type, _make_handler(command_type))

        for index, command_type in enumerate(ordered_types):
            result = service.dispatch_summon_echo_specialty_command(
                {"type": command_type},
                cid=1,
                ws_id=index,
                is_admin=False,
                claimed=9,
            )
            self.assertTrue(result.get("ok"))
            self.assertEqual(result.get("command_type"), command_type)

        self.assertEqual([entry[0] for entry in calls], ordered_types)
        self.assertTrue(all(entry[5] == 9 for entry in calls))

    def test_service_dispatcher_rejects_unknown_command(self):
        service = PlayerCommandService(type("TrackerStub", (), {})())
        result = service.dispatch_summon_echo_specialty_command(
            {"type": "initiative_roll"},
            cid=1,
            ws_id=17,
            is_admin=False,
            claimed=1,
        )
        self.assertFalse(result.get("ok"))
        self.assertEqual(result.get("reason"), "unsupported_command")
        self.assertEqual(result.get("received_type"), "initiative_roll")

    def test_lan_apply_action_routes_summon_echo_family_through_dispatcher(self):
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

            def dispatch_summon_echo_specialty_command(self, msg, *, cid, ws_id, is_admin, claimed=None):
                self.calls.append((str(msg.get("type")), cid, ws_id, is_admin, claimed))
                return {"ok": True}

        service_stub = ServiceStub()
        app._ensure_player_commands = lambda: service_stub

        sample_payloads = {
            "echo_summon": {"to": {"col": 3, "row": 4}},
            "echo_swap": {},
            "dismiss_summons": {"target_caster_cid": 1},
            "dismiss_persistent_summon": {"summon_group_id": "echo:1"},
            "reappear_persistent_summon": {"summon_group_id": "echo:1", "to": {"col": 4, "row": 5}},
            "assign_pre_summon": {"target_cid": 1, "spell_slug": "find-familiar", "monster_slug": "owl"},
            "echo_tether_response": {"request_id": "req-1", "accept": True},
        }
        for command_type in sorted(SUMMON_ECHO_SPECIALTY_COMMAND_TYPES):
            payload = {
                "type": command_type,
                "cid": 1,
                "_claimed_cid": 1,
                "_ws_id": 81,
            }
            payload.update(sample_payloads.get(command_type, {}))
            app._lan_apply_action(payload)

        self.assertEqual([entry[0] for entry in service_stub.calls], sorted(SUMMON_ECHO_SPECIALTY_COMMAND_TYPES))
        self.assertTrue(all(entry[4] == 1 for entry in service_stub.calls))


class LanSummonEchoSpecialtyServiceBehaviorTests(unittest.TestCase):
    def test_family_handlers_delegate_to_tracker_request_helpers(self):
        tracker = type("TrackerStub", (), {})()
        tracker._lan = type("LanStub", (), {"toast": lambda *_args, **_kwargs: None})()
        tracker._oplog = lambda *args, **kwargs: None
        calls = []

        dispatches = [
            (
                "echo_summon",
                "_handle_echo_summon_request",
                {"type": "echo_summon", "to": {"col": 3, "row": 4}},
                False,
            ),
            (
                "echo_swap",
                "_handle_echo_swap_request",
                {"type": "echo_swap"},
                False,
            ),
            (
                "dismiss_summons",
                "_handle_dismiss_summons_request",
                {"type": "dismiss_summons", "target_caster_cid": 7},
                True,
            ),
            (
                "dismiss_persistent_summon",
                "_handle_dismiss_persistent_summon_request",
                {"type": "dismiss_persistent_summon", "summon_group_id": "echo:7"},
                True,
            ),
            (
                "reappear_persistent_summon",
                "_handle_reappear_persistent_summon_request",
                {"type": "reappear_persistent_summon", "summon_group_id": "echo:7", "to": {"col": 1, "row": 2}},
                True,
            ),
            (
                "assign_pre_summon",
                "_handle_assign_pre_summon_request",
                {"type": "assign_pre_summon", "target_cid": 7, "spell_slug": "find-familiar", "monster_slug": "owl"},
                False,
            ),
            (
                "echo_tether_response",
                "_handle_echo_tether_response_request",
                {"type": "echo_tether_response", "request_id": "req-1", "accept": True},
                False,
            ),
        ]

        for _command_type, helper_name, _msg, needs_claimed in dispatches:
            if needs_claimed:
                setattr(
                    tracker,
                    helper_name,
                    lambda msg, *, cid, ws_id, is_admin, claimed, _helper_name=helper_name: calls.append(
                        (_helper_name, dict(msg), cid, ws_id, is_admin, claimed)
                    ),
                )
            else:
                setattr(
                    tracker,
                    helper_name,
                    lambda msg, *, cid, ws_id, is_admin, _helper_name=helper_name: calls.append(
                        (_helper_name, dict(msg), cid, ws_id, is_admin, None)
                    ),
                )

        service = PlayerCommandService(tracker)
        for command_type, helper_name, msg, needs_claimed in dispatches:
            kwargs = {"claimed": 88} if needs_claimed else {}
            result = getattr(service, command_type)(dict(msg), cid=7, ws_id=12, is_admin=False, **kwargs)
            self.assertTrue(result.get("ok"))
            self.assertEqual((result.get("request") or {}).get("command_type"), command_type)
            self.assertEqual(calls[-1][0], helper_name)
            self.assertEqual(calls[-1][2:5], (7, 12, False))
            self.assertEqual(calls[-1][5], 88 if needs_claimed else None)


if __name__ == "__main__":
    unittest.main()
