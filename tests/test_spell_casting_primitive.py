import unittest
from unittest import mock
import dnd_initative_tracker as tracker_mod

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
    return c

class SpellCastingPrimitiveTests(unittest.TestCase):
    def setUp(self):
        self.toasts = []
        self.app = object.__new__(tracker_mod.InitiativeTracker)
        self.app._oplog = lambda *args, **kwargs: None
        self.app._find_spell_preset = lambda *_args, **_kwargs: None
        self.app._log = lambda *args, **kwargs: None
        self.app._is_valid_turn_for_cid = lambda cid: True
        self.app._combatant_can_cast_spell = lambda combatant, spend: True
        self.app._spellcast_blocked_by_environment = lambda combatant, preset: (False, "")
        self.app._resolve_spell_spend_type = lambda **kwargs: "action"
        self.app._authorize_spell_cast_for_resolution = tracker_mod.InitiativeTracker._authorize_spell_cast_for_resolution.__get__(self.app, tracker_mod.InitiativeTracker)
        self.app._infer_spell_targeting_mode = lambda preset: "target"
        self.app._spell_label_from_identifiers = lambda *args: "Spell"
        self.app._lan_is_friendly_unit = lambda cid: True
        self.app._lan_sculpt_spells_context = lambda *args, **kwargs: (False, 0)
        self.app._register_map_spell_effect = lambda aid, aoe: None
        self.app._lan_auto_resolve_cast_aoe = lambda *args, **kwargs: True
        self.app._use_action = lambda c, **kwargs: True
        self.app._spell_cast_log_message = lambda *args: "Cast AOE"
        self.app._lan_grid_cols = 20
        self.app._lan_grid_rows = 20
        self.app._rebuild_table = lambda **kwargs: None
        self.app._find_counterspell_reactor = lambda cid: None
        self.app._ensure_player_commands = lambda: mock.Mock()
        self.app._lan_live_map_data = lambda: (None, None, None, None, {})
        self.app._normalize_token_color = lambda c: c
        self.app._normalize_map_environment_metadata = lambda m: m
        self.app._lan_next_aoe_id = 1
        self.app._lan_aoes = {}
        
        # Mock _map_window
        mw = mock.Mock()
        mw.winfo_exists.return_value = False # Simplify for tests
        self.app._map_window = mw

        self.app.combatants = {
            1: _make_combatant(1, "Caster", ac=15, hp=20, ally=True, is_pc=True),
            2: _make_combatant(2, "Target", ac=15, hp=20),
        }
        self.send_async_mock = mock.Mock()
        self.app._lan = type(
            "LanStub",
            (),
            {
                "toast": lambda _self, ws_id, message: self.toasts.append((ws_id, message)),
                "_append_lan_log": lambda *args, **kwargs: None,
                "_loop": mock.Mock(),
                "_send_async": self.send_async_mock,
            },
        )()
        # Bind methods
        self.app._handle_cast_spell_request = tracker_mod.InitiativeTracker._handle_cast_spell_request.__get__(self.app, tracker_mod.InitiativeTracker)
        self.app._adjudicate_spell_target_request = tracker_mod.InitiativeTracker._adjudicate_spell_target_request.__get__(self.app, tracker_mod.InitiativeTracker)
        self.app._handle_cast_aoe_request = tracker_mod.InitiativeTracker._handle_cast_aoe_request.__get__(self.app, tracker_mod.InitiativeTracker)
        self.app._send_spell_result = tracker_mod.InitiativeTracker._send_spell_result.__get__(self.app, tracker_mod.InitiativeTracker)
        self.app._send_spell_target_result = tracker_mod.InitiativeTracker._send_spell_target_result.__get__(self.app, tracker_mod.InitiativeTracker)
        
        # Mock _find_spell_preset
        self.app._find_spell_preset = mock.Mock(return_value={
            "slug": "fire-bolt",
            "name": "Fire Bolt",
            "mechanics": {
                "records_target_authority": True
            }
        })

    @mock.patch("asyncio.run_coroutine_threadsafe")
    def test_cast_spell_request_needs_target(self, mock_run_coro):
        msg = {
            "type": "cast_spell_request",
            "cid": 1,
            "_claimed_cid": 1,
            "_ws_id": "ws_123",
            "spell_slug": "fire-bolt"
        }
        
        self.app._handle_cast_spell_request(msg, cid=1, ws_id="ws_123", is_admin=False, claimed=1)
        
        self.assertTrue(self.send_async_mock.called)
        ws_id, payload = self.send_async_mock.call_args[0]
        self.assertEqual(payload["status"], "CAST_NEEDS_TARGET")

    @mock.patch("asyncio.run_coroutine_threadsafe")
    def test_spell_target_request_invalid_target_rejection(self, mock_run_coro):
        msg = {
            "type": "spell_target_request",
            "cid": 1,
            "_claimed_cid": 1,
            "_ws_id": "ws_123",
            "target_cid": 999,
            "spell_slug": "fire-bolt"
        }
        
        self.app._adjudicate_spell_target_request(msg, cid=1, ws_id="ws_123", is_admin=False)
        
        self.assertTrue(self.send_async_mock.called)
        ws_id, payload = self.send_async_mock.call_args[0]
        self.assertEqual(payload["status"], "REJECTED")
        self.assertEqual(payload["reason"], "Pick a valid target, matey.")

    @mock.patch("asyncio.run_coroutine_threadsafe")
    def test_cast_aoe_request_success(self, mock_run_coro):
        self.app._map_spell_effect_targets = lambda aoe: [2]
        msg = {
            "type": "cast_aoe_request",
            "cid": 1,
            "_claimed_cid": 1,
            "_ws_id": "ws_123",
            "payload": {
                "shape": "circle",
                "radius_ft": 20,
                "cx": 10,
                "cy": 10
            }
        }
        
        self.app._handle_cast_aoe_request(msg, cid=1, ws_id="ws_123", is_admin=False, claimed=1)
        
        self.assertTrue(self.send_async_mock.called)
        ws_id, payload = self.send_async_mock.call_args[0]
        self.assertEqual(payload["status"], "CAST_APPLIED")
        self.assertEqual(payload["type"], "spell_cast_result")

    @mock.patch("asyncio.run_coroutine_threadsafe")
    def test_cast_aoe_request_no_action_rejection(self, mock_run_coro):
        msg = {
            "type": "cast_aoe_request",
            "cid": 1,
            "_claimed_cid": 1,
            "_ws_id": "ws_123",
            "payload": {
                "shape": "circle",
                "radius_ft": 20,
                "cx": 10,
                "cy": 10
            }
        }
        # Mock no actions left
        self.app._use_action = lambda c, **kwargs: False
        
        self.app._handle_cast_aoe_request(msg, cid=1, ws_id="ws_123", is_admin=False, claimed=1)
        
        self.assertTrue(self.send_async_mock.called)
        ws_id, payload = self.send_async_mock.call_args[0]
        self.assertEqual(payload["status"], "CAST_REJECTED")
        self.assertEqual(payload["reason"], "No actions left, matey.")

    @mock.patch("asyncio.run_coroutine_threadsafe")
    def test_cast_aoe_request_no_targets(self, mock_run_coro):
        # Mock _map_spell_effect_targets to return empty list
        self.app._map_spell_effect_targets = lambda aoe: []
        
        msg = {
            "type": "cast_aoe_request",
            "cid": 1,
            "_claimed_cid": 1,
            "_ws_id": "ws_123",
            "payload": {
                "shape": "circle",
                "radius_ft": 20,
                "cx": 10,
                "cy": 10
            }
        }
        
        self.app._handle_cast_aoe_request(msg, cid=1, ws_id="ws_123", is_admin=False, claimed=1)
        
        self.assertTrue(self.send_async_mock.called)
        ws_id, payload = self.send_async_mock.call_args[0]
        # Currently it might return CAST_APPLIED, let's see.
        # The goal is to make it return CAST_NO_TARGETS.
        self.assertEqual(payload["status"], "CAST_NO_TARGETS")

    @mock.patch("asyncio.run_coroutine_threadsafe")
    def test_cast_aoe_request_invalid_shape(self, mock_run_coro):
        msg = {
            "type": "cast_aoe_request",
            "cid": 1,
            "_claimed_cid": 1,
            "_ws_id": "ws_123",
            "payload": {
                "shape": "invalid_shape",
                "radius_ft": 20
            }
        }
        
        self.app._handle_cast_aoe_request(msg, cid=1, ws_id="ws_123", is_admin=False, claimed=1)
        
        self.assertTrue(self.send_async_mock.called)
        ws_id, payload = self.send_async_mock.call_args[0]
        self.assertEqual(payload["status"], "CAST_REJECTED")
        self.assertEqual(payload["reason"], "Pick a valid spell shape, matey.")

    @mock.patch("asyncio.run_coroutine_threadsafe")
    def test_cast_aoe_request_persistent(self, mock_run_coro):
        self.app._map_spell_effect_targets = lambda aoe: [2]
        msg = {
            "type": "cast_aoe_request",
            "cid": 1,
            "_claimed_cid": 1,
            "_ws_id": "ws_123",
            "payload": {
                "shape": "circle",
                "radius_ft": 20,
                "persistent": True
            }
        }
        
        self.app._handle_cast_aoe_request(msg, cid=1, ws_id="ws_123", is_admin=False, claimed=1)
        
        self.assertTrue(self.send_async_mock.called)
        ws_id, payload = self.send_async_mock.call_args[0]
        self.assertEqual(payload["status"], "CAST_CREATED_PERSISTENT_EFFECT")

    @mock.patch("asyncio.run_coroutine_threadsafe")
    def test_cast_aoe_request_manual_damage_with_targets(self, mock_run_coro):
        self.app._map_spell_effect_targets = lambda aoe: [2]
        # Mock auto-resolve to return False
        self.app._lan_auto_resolve_cast_aoe = lambda *args, **kwargs: False
        
        # Mock _lan_prompt_manual_aoe_damage
        self.app._lan_prompt_manual_aoe_damage = mock.Mock()
        
        msg = {
            "type": "cast_aoe_request",
            "cid": 1,
            "_claimed_cid": 1,
            "_ws_id": "ws_123",
            "payload": {
                "shape": "circle",
                "radius_ft": 20
            }
        }
        
        self.app._handle_cast_aoe_request(msg, cid=1, ws_id="ws_123", is_admin=False, claimed=1)
        
        # Verify result has targets
        self.assertTrue(self.send_async_mock.called)
        ws_id, payload = self.send_async_mock.call_args[0]
        self.assertEqual(payload["status"], "CAST_NEEDS_MANUAL_DAMAGE")
        self.assertEqual(payload["target_cids"], [2])
        
        # Verify prompt was called
        self.app._lan_prompt_manual_aoe_damage.assert_called_once()
        args, kwargs = self.app._lan_prompt_manual_aoe_damage.call_args
        self.assertEqual(kwargs["target_cids"], [2])

if __name__ == "__main__":
    unittest.main()
