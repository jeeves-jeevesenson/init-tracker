import unittest
from unittest import mock
import time
import threading
import dnd_initative_tracker as tracker_mod
from player_command_contracts import REACTION_EXPIRED

def _make_combatant(cid: int, name: str, *, ac: int, hp: int, ally: bool = False, is_pc: bool = False):
    c = tracker_mod.base.Combatant(
        cid=cid,
        name=name,
        hp=hp,
        speed=30,
        swim_speed=0,
        fly_speed=0,
        burrow_speed=0,
        climb_speed=0,
        movement_mode="normal",
        move_remaining=30,
        initiative=10,
        ally=ally,
        is_pc=is_pc,
    )
    c.ac = ac
    c.max_hp = hp
    c.reaction_remaining = 1
    return c

class ReactionPromptExpiryResumeTests(unittest.TestCase):
    def setUp(self):
        self.app = object.__new__(tracker_mod.InitiativeTracker)
        self.app._oplog = lambda *args, **kwargs: None
        self.app._log = lambda *args, **kwargs: None
        self.app.combatants = {
            1: _make_combatant(1, "Reactor", ac=15, hp=20, ally=True, is_pc=True),
            2: _make_combatant(2, "Caster", ac=10, hp=15, ally=True, is_pc=True),
        }
        self.app._pending_prompts = {}
        self.app._pending_reaction_offers = {}
        self.app._pending_shield_resolutions = {}
        self.app._pending_hellish_rebuke_resolutions = {}
        self.app._pending_absorb_elements_resolutions = {}
        self.app._pending_interception_resolutions = {}

        self.send_async_mock = mock.Mock()
        self.app._lan = type(
            "LanStub",
            (),
            {
                "toast": lambda *args: None,
                "_append_lan_log": lambda *args, **kwargs: None,
                "_loop": mock.Mock(),
                "_send_async": self.send_async_mock,
                "_clients_lock": threading.Lock(),
                "_cid_to_ws": {1: {99}, 2: {100}},
            },
        )()

        # Bind methods
        self.app._ensure_player_commands = tracker_mod.InitiativeTracker._ensure_player_commands.__get__(self.app, tracker_mod.InitiativeTracker)
        self.app._find_ws_for_cid = tracker_mod.InitiativeTracker._find_ws_for_cid.__get__(self.app, tracker_mod.InitiativeTracker)
        self.app._create_pending_reaction = tracker_mod.InitiativeTracker._create_pending_reaction.__get__(self.app, tracker_mod.InitiativeTracker)
        self.app._send_reaction_result = tracker_mod.InitiativeTracker._send_reaction_result.__get__(self.app, tracker_mod.InitiativeTracker)

        self.resume_dispatch_mock = mock.Mock(return_value={"ok": True})
        self.app._ensure_player_commands()._dispatch_resume = self.resume_dispatch_mock

    @mock.patch("asyncio.run_coroutine_threadsafe")
    def test_expiry_resumes_and_notifies(self, mock_run_coro):
        # Create a pending prompt for reactor_cid=1 (Counterspell trigger) with a resume_dispatch
        # for caster_cid=2 (ws_id=100)
        resume_payload = {
            "command_type": "spell_target_request",
            "actor_cid": 2,
            "ws_id": 100,
            "payload": {"spell_id": "fireball", "target_cid": 1},
        }

        # create_reaction_offer signature in service:
        # def create_reaction_offer(self, reactor_cid, trigger, source_cid, target_cid, allowed_choices, ws_ids, ...)
        choices = [{"kind": "decline", "label": "No"}]
        ws_ids = [99]
        
        prompt_record = self.app._ensure_player_commands().prompts.create_reaction_offer(
            reactor_cid=1,
            trigger="counterspell",
            source_cid=2,
            target_cid=1,
            allowed_choices=choices,
            ws_ids=ws_ids,
            expires_in_seconds=-1.0,  # Force immediate expiration
            resume_dispatch=resume_payload,
        )
        rid = prompt_record["prompt_id"]

        self.assertIn(rid, self.app._pending_prompts)

        # Force expire offers
        self.app._ensure_player_commands().prompts.expire_offers()

        # 1. Verify prompt is popped
        self.assertNotIn(rid, self.app._pending_prompts)

        # 2. Verify resume_dispatch is executed with correct flags updated
        self.resume_dispatch_mock.assert_called_once()
        called_arg = self.resume_dispatch_mock.call_args[0][0]
        self.assertEqual(called_arg["command_type"], "spell_target_request")
        self.assertEqual(called_arg["actor_cid"], 2)
        self.assertEqual(called_arg["ws_id"], 100)
        self.assertEqual(called_arg["flags"], {"_counterspell_resolution_done": True})

        # 3. Verify REACTION_EXPIRED WebSocket result sent to reactor (ws 99) and caster (ws 100)
        self.assertTrue(self.send_async_mock.called)
        sent_ws_ids = [call[0][0] for call in self.send_async_mock.call_args_list]
        self.assertIn(99, sent_ws_ids)
        self.assertIn(100, sent_ws_ids)

        # Check payload properties
        for call in self.send_async_mock.call_args_list:
            payload = call[0][1]
            self.assertEqual(payload["type"], "reaction_result")
            self.assertEqual(payload["status"], REACTION_EXPIRED)
            self.assertEqual(payload["request_id"], rid)
            self.assertEqual(payload["reactor_cid"], 1)

if __name__ == "__main__":
    unittest.main()
