import unittest

import dnd_initative_tracker as tracker_mod
from player_command_contracts import BARD_GLAMOUR_SPECIALTY_COMMAND_TYPES
from player_command_service import PlayerCommandService


class LanBardGlamourSpecialtyDispatchTests(unittest.TestCase):
    def test_service_dispatcher_routes_every_bard_glamour_specialty_command(self):
        service = PlayerCommandService(type("TrackerStub", (), {})())
        calls = []
        ordered_types = sorted(BARD_GLAMOUR_SPECIALTY_COMMAND_TYPES)

        def _make_handler(expected_type):
            def _handler(msg, *, cid, ws_id, is_admin):
                calls.append((expected_type, dict(msg), cid, ws_id, is_admin))
                return {"ok": True, "command_type": expected_type}

            return _handler

        for command_type in ordered_types:
            setattr(service, command_type, _make_handler(command_type))

        for index, command_type in enumerate(ordered_types):
            result = service.dispatch_bard_glamour_specialty_command(
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
        result = service.dispatch_bard_glamour_specialty_command(
            {"type": "initiative_roll"},
            cid=1,
            ws_id=17,
            is_admin=False,
        )
        self.assertFalse(result.get("ok"))
        self.assertEqual(result.get("reason"), "unsupported_command")
        self.assertEqual(result.get("received_type"), "initiative_roll")

    def test_lan_apply_action_routes_bard_glamour_family_through_dispatcher(self):
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

            def dispatch_bard_glamour_specialty_command(self, msg, *, cid, ws_id, is_admin):
                self.calls.append((str(msg.get("type")), cid, ws_id, is_admin))
                return {"ok": True}

        service_stub = ServiceStub()
        app._ensure_player_commands = lambda: service_stub

        sample_payloads = {
            "command_resolve": {"target_cids": [2], "command_option": "halt", "slot_level": 1},
            "bardic_inspiration_grant": {"target_cid": 1},
            "bardic_inspiration_use": {},
            "mantle_of_inspiration": {"target_cids": [1]},
            "beguiling_magic_restore": {},
            "beguiling_magic_use": {"target_cid": 2, "condition": "charmed"},
        }
        for command_type in sorted(BARD_GLAMOUR_SPECIALTY_COMMAND_TYPES):
            payload = {
                "type": command_type,
                "cid": 1,
                "_claimed_cid": 1,
                "_ws_id": 81,
            }
            payload.update(sample_payloads.get(command_type, {}))
            app._lan_apply_action(payload)

        self.assertEqual([entry[0] for entry in service_stub.calls], sorted(BARD_GLAMOUR_SPECIALTY_COMMAND_TYPES))


class LanBardGlamourSpecialtyServiceBehaviorTests(unittest.TestCase):
    def test_family_handlers_delegate_to_tracker_request_helpers(self):
        tracker = type("TrackerStub", (), {})()
        tracker._lan = type("LanStub", (), {"toast": lambda *_args, **_kwargs: None})()
        tracker._oplog = lambda *args, **kwargs: None
        calls = []

        dispatches = [
            (
                "command_resolve",
                "_handle_command_resolve_request",
                {"type": "command_resolve", "target_cids": [2], "command_option": "halt", "slot_level": 1},
            ),
            (
                "bardic_inspiration_grant",
                "_handle_bardic_inspiration_grant_request",
                {"type": "bardic_inspiration_grant", "target_cid": 2},
            ),
            (
                "bardic_inspiration_use",
                "_handle_bardic_inspiration_use_request",
                {"type": "bardic_inspiration_use"},
            ),
            (
                "mantle_of_inspiration",
                "_handle_mantle_of_inspiration_request",
                {"type": "mantle_of_inspiration", "target_cids": [2], "die_override": 4},
            ),
            (
                "beguiling_magic_restore",
                "_handle_beguiling_magic_restore_request",
                {"type": "beguiling_magic_restore"},
            ),
            (
                "beguiling_magic_use",
                "_handle_beguiling_magic_use_request",
                {"type": "beguiling_magic_use", "target_cid": 2, "condition": "frightened"},
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
