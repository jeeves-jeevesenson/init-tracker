import unittest
from unittest import mock
import time
import dnd_initative_tracker as tracker_mod
from player_command_contracts import (
    REACTION_PROMPT_CREATED,
    REACTION_ACCEPTED,
    REACTION_DECLINED,
    REACTION_EXPIRED,
    REACTION_REJECTED,
)

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

class ReactionContractTests(unittest.TestCase):
    def setUp(self):
        self.app = object.__new__(tracker_mod.InitiativeTracker)
        self.app._oplog = lambda *args, **kwargs: None
        self.app._log = lambda *args, **kwargs: None
        self.app.combatants = {
            1: _make_combatant(1, "Reactor", ac=15, hp=20, ally=True, is_pc=True),
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
                "_cid_to_ws": {1: {99}},
            },
        )()
        
        # Bind methods
        self.app._ensure_player_commands = tracker_mod.InitiativeTracker._ensure_player_commands.__get__(self.app, tracker_mod.InitiativeTracker)
        self.app._find_ws_for_cid = tracker_mod.InitiativeTracker._find_ws_for_cid.__get__(self.app, tracker_mod.InitiativeTracker)
        self.app._create_pending_reaction = tracker_mod.InitiativeTracker._create_pending_reaction.__get__(self.app, tracker_mod.InitiativeTracker)
        self.app._send_reaction_result = tracker_mod.InitiativeTracker._send_reaction_result.__get__(self.app, tracker_mod.InitiativeTracker)
        
    @mock.patch("asyncio.run_coroutine_threadsafe")
    def test_create_pending_reaction(self, mock_run_coro):
        rid = self.app._create_pending_reaction(
            trigger="test_trigger",
            reactor_cid=1,
            prompt="Test prompt",
        )
        self.assertTrue(rid.startswith("react_") or len(rid) > 0)
        self.assertIn(rid, self.app._pending_prompts)
        
        # Verify broadcast
        self.assertTrue(self.send_async_mock.called)
        ws_id, payload = self.send_async_mock.call_args[0]
        self.assertEqual(ws_id, 99)
        self.assertEqual(payload["type"], "reaction_offer")
        self.assertEqual(payload["trigger"], "test_trigger")

    @mock.patch("asyncio.run_coroutine_threadsafe")
    def test_accept_reaction_prompt(self, mock_run_coro):
        rid = self.app._create_pending_reaction(trigger="test_trigger", reactor_cid=1)
        self.send_async_mock.reset_mock()
        
        msg = {
            "type": "reaction_response",
            "request_id": rid,
            "choice": "accept",
        }
        self.app._ensure_player_commands().reaction_response(msg, cid=1, ws_id=99)
        
        # Verify result sent
        self.assertTrue(self.send_async_mock.called)
        ws_id, payload = self.send_async_mock.call_args[0]
        self.assertEqual(payload["status"], REACTION_ACCEPTED)
        self.assertEqual(payload["request_id"], rid)
        
        # Verify prompt removed
        self.assertNotIn(rid, self.app._pending_prompts)

    @mock.patch("asyncio.run_coroutine_threadsafe")
    def test_decline_reaction_prompt(self, mock_run_coro):
        rid = self.app._create_pending_reaction(trigger="test_trigger", reactor_cid=1)
        self.send_async_mock.reset_mock()
        
        msg = {
            "type": "reaction_response",
            "request_id": rid,
            "choice": "decline",
        }
        self.app._ensure_player_commands().reaction_response(msg, cid=1, ws_id=99)
        
        # Verify result sent
        self.assertTrue(self.send_async_mock.called)
        ws_id, payload = self.send_async_mock.call_args[0]
        self.assertEqual(payload["status"], REACTION_DECLINED)
        
        # Verify prompt removed
        self.assertNotIn(rid, self.app._pending_prompts)

    @mock.patch("asyncio.run_coroutine_threadsafe")
    def test_reaction_missing_prompt_rejects(self, mock_run_coro):
        msg = {
            "type": "reaction_response",
            "request_id": "nonexistent",
            "choice": "accept",
        }
        result = self.app._ensure_player_commands().reaction_response(msg, cid=1, ws_id=99)
        
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "no_offer")

    @mock.patch("asyncio.run_coroutine_threadsafe")
    def test_reaction_expired_prompt(self, mock_run_coro):
        rid = self.app._create_pending_reaction(trigger="test_trigger", reactor_cid=1, expires_in=-1.0)
        
        self.app._ensure_player_commands().prompts.expire_offers()
        
        self.assertNotIn(rid, self.app._pending_prompts)
        
        msg = {
            "type": "reaction_response",
            "request_id": rid,
            "choice": "accept",
        }
        result = self.app._ensure_player_commands().reaction_response(msg, cid=1, ws_id=99)
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "no_offer")

    @mock.patch("asyncio.run_coroutine_threadsafe")
    def test_reaction_unavailable_resource(self, mock_run_coro):
        rid = self.app._create_pending_reaction(trigger="test_trigger", reactor_cid=1)
        self.app.combatants[1].reaction_remaining = 0
        self.send_async_mock.reset_mock()
        
        msg = {
            "type": "reaction_response",
            "request_id": rid,
            "choice": "accept",
        }
        result = self.app._ensure_player_commands().reaction_response(msg, cid=1, ws_id=99)
        
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "no_reaction")
        
        # Verify rejection result sent
        self.assertTrue(self.send_async_mock.called)
        ws_id, payload = self.send_async_mock.call_args[0]
        self.assertEqual(payload["status"], REACTION_REJECTED)

import threading
if __name__ == "__main__":
    unittest.main()
