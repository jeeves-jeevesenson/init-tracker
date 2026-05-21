import unittest
from unittest import mock
import time
import dnd_initative_tracker as tracker_mod
from player_command_contracts import (
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

class ReactionLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.app = object.__new__(tracker_mod.InitiativeTracker)
        self.app._oplog = lambda *args, **kwargs: None
        self.app._log = lambda *args, **kwargs: None
        self.app.combatants = {
            1: _make_combatant(1, "Reactor", ac=15, hp=20, ally=True, is_pc=True),
            2: _make_combatant(2, "Attacker", ac=12, hp=20, ally=False, is_pc=False),
        }
        self.app._pending_prompts = {}
        self.app._pending_reaction_offers = {}
        self.app._pending_shield_resolutions = {}
        self.app._pending_hellish_rebuke_resolutions = {}
        self.app._reaction_prefs_by_cid = {}
        self.app._lan_positions = {}
        self.app._turn_snapshots = {}
        self.app._lan_aoes = {}
        self.app._summon_groups = {}
        self.app._summon_group_meta = {}
        self.app.in_combat = True
        self.app.current_cid = 2
        self.app.round_num = 1
        self.app.turn_num = 1
        
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
        self.app._create_reaction_offer = tracker_mod.InitiativeTracker._create_reaction_offer.__get__(self.app, tracker_mod.InitiativeTracker)
        self.app._expire_reaction_offers = tracker_mod.InitiativeTracker._expire_reaction_offers.__get__(self.app, tracker_mod.InitiativeTracker)
        self.app._send_reaction_result = tracker_mod.InitiativeTracker._send_reaction_result.__get__(self.app, tracker_mod.InitiativeTracker)
        self.app._next_turn = tracker_mod.InitiativeTracker._next_turn.__get__(self.app, tracker_mod.InitiativeTracker)
        self.app._display_order = mock.Mock(return_value=[self.app.combatants[2], self.app.combatants[1]])
        self.app._advance_to_next_turn_candidate = mock.Mock(return_value=(True, False))
        self.app._end_turn_cleanup = mock.Mock()
        self.app._enter_turn_with_auto_skip = mock.Mock()
        self.app._record_turn_history = mock.Mock()
        self.app._rebuild_table = mock.Mock()
        self.app._log_turn_end = mock.Mock()
        self.app._init_cadence_scheduler_state = mock.Mock()
        self.app._should_show_dm_up_alert = mock.Mock(return_value=False)
        self.app._normalize_summons_shared_turn_state = mock.Mock()
        self.app._monster_sequence_state = set()
        self.app._monster_modifier_state = {}
        self.app._monster_resource_state = {}

    def test_pending_reaction_expires_on_turn_advance(self):
        rid = self.app._create_reaction_offer(
            reactor_cid=1,
            trigger="shield",
            source_cid=2,
            target_cid=1,
            allowed_choices=[{"kind": "shield_yes", "label": "Yes"}],
            ws_ids=[99],
        )
        self.assertIn(rid, self.app._pending_reaction_offers)
        
        # Advance turn
        self.app._next_turn()
        
        # Verify it's gone
        self.assertNotIn(rid, self.app._pending_reaction_offers)

    def test_stale_prompt_cannot_be_accepted(self):
        rid = self.app._create_reaction_offer(
            reactor_cid=1,
            trigger="shield",
            source_cid=2,
            target_cid=1,
            allowed_choices=[{"kind": "shield_yes", "label": "Yes"}],
            ws_ids=[99],
        )
        
        # Manually expire
        self.app._expire_reaction_offers(force=True)
        
        # Try to respond
        msg = {
            "type": "reaction_response",
            "request_id": rid,
            "choice": "shield_yes",
        }
        result = self.app._ensure_player_commands().reaction_response(msg, cid=1, ws_id=99)
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "no_offer")

    def test_decline_clears_prompt(self):
        rid = self.app._create_reaction_offer(
            reactor_cid=1,
            trigger="shield",
            source_cid=2,
            target_cid=1,
            allowed_choices=[{"kind": "shield_yes", "label": "Yes"}],
            ws_ids=[99],
        )
        
        msg = {
            "type": "reaction_response",
            "request_id": rid,
            "choice": "decline",
        }
        self.app._ensure_player_commands().reaction_response(msg, cid=1, ws_id=99)
        self.assertNotIn(rid, self.app._pending_reaction_offers)

    def test_accepted_reaction_clears_prompt(self):
        # Shield resolution clears prompt immediately
        rid = self.app._create_reaction_offer(
            reactor_cid=1,
            trigger="shield",
            source_cid=2,
            target_cid=1,
            allowed_choices=[{"kind": "shield_yes", "label": "Yes"}],
            ws_ids=[99],
            resolution={"attacker_cid": 2, "target_ac": 15, "attack_total": 16},
            resume_dispatch={"type": "attack_request", "actor_cid": 2},
        )
        
        msg = {
            "type": "reaction_response",
            "request_id": rid,
            "choice": "shield_yes",
        }
        # Mock tracker methods needed for shield resolution
        self.app._can_offer_shield_reaction = mock.Mock(return_value=(True, ""))
        self.app._use_reaction = mock.Mock(return_value=True)
        self.app._consume_shield_cast = mock.Mock(return_value=(True, ""))
        self.app._shield_effect_start = mock.Mock()
        self.app._dispatch_resume = mock.Mock(return_value={"ok": True})
        
        self.app._ensure_player_commands().reaction_response(msg, cid=1, ws_id=99)
        self.assertNotIn(rid, self.app._pending_reaction_offers)

    def test_death_clears_pending_reactions(self):
        rid = self.app._create_reaction_offer(
            reactor_cid=1,
            trigger="shield",
            source_cid=2,
            target_cid=1,
            allowed_choices=[{"kind": "shield_yes", "label": "Yes"}],
            ws_ids=[99],
        )
        self.assertIn(rid, self.app._pending_reaction_offers)
        
        # Remove combatant
        self.app._remove_combatants_from_runtime_state = tracker_mod.InitiativeTracker._remove_combatants_from_runtime_state.__get__(self.app, tracker_mod.InitiativeTracker)
        self.app._remove_combatants_from_runtime_state([1])
        
        # Verify it's gone
        self.assertNotIn(rid, self.app._pending_reaction_offers)

import threading
if __name__ == "__main__":
    unittest.main()
