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

class SpellSummonPrimitiveTests(unittest.TestCase):
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
        self.app._spell_label_from_identifiers = lambda *args: "Summon Spell"
        self.app._lan_is_friendly_unit = lambda cid: True
        self.app._rebuild_table = lambda **kwargs: None
        self.app._lan_force_state_broadcast = lambda *args: None
        self.app._find_counterspell_reactor = lambda cid: None
        self.app._lan_live_map_data = lambda: (20, 20, set(), set(), {1: (10, 10)})
        self.app._lan_current_position = lambda cid: (10, 10)
        self.app._find_monster_spec_by_slug = lambda slug: mock.Mock(name="Spec", hp=10, speed=30, dex=10, saving_throws={}, ability_mods={})
        self.app._is_summon_auto_spawn_allowed = tracker_mod.InitiativeTracker._is_summon_auto_spawn_allowed.__get__(self.app, tracker_mod.InitiativeTracker)

        self.app.combatants = {
            1: _make_combatant(1, "Caster", ac=15, hp=20, ally=True, is_pc=True),
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
        self.app._spawn_summons_from_cast = mock.Mock(return_value=[101])
        self.app._send_spell_result = tracker_mod.InitiativeTracker._send_spell_result.__get__(self.app, tracker_mod.InitiativeTracker)
        self.app._resolve_spell_summon_request = lambda **kwargs: ({"quantity": 1, "monster_slug": "test-monster"}, None)

    @mock.patch("asyncio.run_coroutine_threadsafe")
    def test_summon_pending_dm_for_player(self, mock_run_coro):
        self.app._find_spell_preset = mock.Mock(return_value={
            "slug": "summon-fey",
            "name": "Summon Fey",
            "summon": {
                "control": "summoner"
            }
        })
        msg = {
            "type": "cast_spell_request",
            "cid": 1,
            "spell_slug": "summon-fey",
            "payload": {
                "summon_positions": [{"col": 11, "row": 11}]
            }
        }
        
        self.app._handle_cast_spell_request(msg, cid=1, ws_id="ws_123", is_admin=False, claimed=1)
        
        self.assertTrue(self.send_async_mock.called)
        ws_id, payload = self.send_async_mock.call_args[0]
        self.assertEqual(payload["status"], "CAST_SUMMON_PENDING_DM")
        self.assertIn("Summon requires DM approval", payload["message"])

    @mock.patch("asyncio.run_coroutine_threadsafe")
    def test_summon_created_for_admin(self, mock_run_coro):
        self.app._find_spell_preset = mock.Mock(return_value={
            "slug": "summon-fey",
            "name": "Summon Fey",
            "summon": {
                "control": "summoner"
            }
        })
        msg = {
            "type": "cast_spell_request",
            "cid": 1,
            "spell_slug": "summon-fey",
            "payload": {
                "summon_positions": [{"col": 11, "row": 11}]
            }
        }
        
        self.app._handle_cast_spell_request(msg, cid=1, ws_id="ws_123", is_admin=True, claimed=1)
        
        self.assertTrue(self.send_async_mock.called)
        ws_id, payload = self.send_async_mock.call_args[0]
        self.assertEqual(payload["status"], "CAST_SUMMON_CREATED")
        self.assertEqual(payload["spawned_cids"], [101])

    @mock.patch("asyncio.run_coroutine_threadsafe")
    def test_summon_auto_spawn_allowed(self, mock_run_coro):
        # Mock a spell that allows auto-spawn
        self.app._find_spell_preset = mock.Mock(return_value={
            "slug": "manifest-echo",
            "name": "Manifest Echo",
            "summon": {
                "auto_spawn": True,
                "control": "summoner"
            }
        })
        msg = {
            "type": "cast_spell_request",
            "cid": 1,
            "spell_slug": "manifest-echo",
            "payload": {
                "summon_positions": [{"col": 11, "row": 11}]
            }
        }
        
        self.app._handle_cast_spell_request(msg, cid=1, ws_id="ws_123", is_admin=False, claimed=1)
        
        self.assertTrue(self.send_async_mock.called)
        ws_id, payload = self.send_async_mock.call_args[0]
        self.assertEqual(payload["status"], "CAST_SUMMON_CREATED")
        self.assertEqual(payload["spawned_cids"], [101])

    @mock.patch("asyncio.run_coroutine_threadsafe")
    def test_summon_rejected_invalid_position(self, mock_run_coro):
        self.app._find_spell_preset = mock.Mock(return_value={
            "slug": "summon-fey",
            "name": "Summon Fey",
            "range": "90 feet",
            "summon": {
                "control": "summoner"
            }
        })
        # Mock obstacle at (11, 11)
        self.app._lan_live_map_data = lambda: (20, 20, {(11, 11)}, set(), {1: (10, 10)})
        
        msg = {
            "type": "cast_spell_request",
            "cid": 1,
            "spell_slug": "summon-fey",
            "payload": {
                "summon_positions": [{"col": 11, "row": 11}]
            }
        }
        
        self.app._handle_cast_spell_request(msg, cid=1, ws_id="ws_123", is_admin=True, claimed=1)
        
        self.assertTrue(self.send_async_mock.called)
        ws_id, payload = self.send_async_mock.call_args[0]
        self.assertEqual(payload["status"], "CAST_REJECTED")
        self.assertIn("invalid", payload["message"])

if __name__ == "__main__":
    unittest.main()
