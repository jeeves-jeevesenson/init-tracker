import unittest

import dnd_initative_tracker as tracker_mod
from player_command_contracts import INITIATIVE_REACTION_SPECIALTY_COMMAND_TYPES
from player_command_service import PlayerCommandService


class LanInitiativeReactionSpecialtyDispatchTests(unittest.TestCase):
    def test_service_dispatcher_routes_every_initiative_reaction_specialty_command(self):
        service = PlayerCommandService(type("TrackerStub", (), {})())
        calls = []
        ordered_types = sorted(INITIATIVE_REACTION_SPECIALTY_COMMAND_TYPES)

        def _make_handler(expected_type):
            def _handler(msg, *, cid, ws_id, is_admin):
                calls.append((expected_type, dict(msg), cid, ws_id, is_admin))
                return {"ok": True, "command_type": expected_type}

            return _handler

        for command_type in ordered_types:
            setattr(service, command_type, _make_handler(command_type))

        for index, command_type in enumerate(ordered_types):
            result = service.dispatch_initiative_reaction_specialty_command(
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
        result = service.dispatch_initiative_reaction_specialty_command(
            {"type": "reaction_response"},
            cid=1,
            ws_id=17,
            is_admin=False,
        )
        self.assertFalse(result.get("ok"))
        self.assertEqual(result.get("reason"), "unsupported_command")
        self.assertEqual(result.get("received_type"), "reaction_response")

    def test_lan_apply_action_routes_initiative_reaction_family_through_dispatcher(self):
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

            def dispatch_initiative_reaction_specialty_command(self, msg, *, cid, ws_id, is_admin):
                self.calls.append((str(msg.get("type")), cid, ws_id, is_admin))
                return {"ok": True}

        service_stub = ServiceStub()
        app._ensure_player_commands = lambda: service_stub

        sample_payloads = {
            "initiative_roll": {"initiative": 13},
            "hellish_rebuke_resolve": {"request_id": "req-11", "slot_level": 2, "target_cid": 2},
        }
        for command_type in sorted(INITIATIVE_REACTION_SPECIALTY_COMMAND_TYPES):
            payload = {
                "type": command_type,
                "cid": 1,
                "_claimed_cid": 1,
                "_ws_id": 81,
            }
            payload.update(sample_payloads.get(command_type, {}))
            app._lan_apply_action(payload)

        self.assertEqual(
            [entry[0] for entry in service_stub.calls],
            sorted(INITIATIVE_REACTION_SPECIALTY_COMMAND_TYPES),
        )


class LanInitiativeReactionSpecialtyServiceBehaviorTests(unittest.TestCase):
    def test_family_handlers_delegate_to_tracker_request_helpers(self):
        tracker = type("TrackerStub", (), {})()
        tracker._lan = type("LanStub", (), {"toast": lambda *_args, **_kwargs: None})()
        tracker._oplog = lambda *args, **kwargs: None
        calls = []

        dispatches = [
            (
                "initiative_roll",
                "_handle_initiative_roll_request",
                {"type": "initiative_roll", "initiative": 16},
            ),
            (
                "hellish_rebuke_resolve",
                "_handle_hellish_rebuke_resolve_request",
                {"type": "hellish_rebuke_resolve", "request_id": "req-1", "slot_level": 1, "target_cid": 9},
            ),
        ]

        for _command_type, helper_name, _msg in dispatches:
            setattr(
                tracker,
                helper_name,
                lambda msg, *, cid, ws_id, is_admin, _helper_name=helper_name: calls.append(
                    (_helper_name, dict(msg), cid, ws_id, is_admin)
                ),
            )

        service = PlayerCommandService(tracker)
        for command_type, helper_name, msg in dispatches:
            result = getattr(service, command_type)(dict(msg), cid=7, ws_id=12, is_admin=False)
            self.assertTrue(result.get("ok"))
            self.assertEqual((result.get("request") or {}).get("command_type"), command_type)
            self.assertEqual(calls[-1][0], helper_name)
            self.assertEqual(calls[-1][2:], (7, 12, False))


if __name__ == "__main__":
    unittest.main()
