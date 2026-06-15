import unittest
import copy
from pathlib import Path
from unittest.mock import MagicMock, patch
import dnd_initative_tracker as tracker_mod

class LanBroadcastInvalidationTests(unittest.TestCase):
    def setUp(self):
        self.app = tracker_mod.InitiativeTracker()
        self.app._lan_log_warning = MagicMock()

        # mock directory setups to prevent real IO where possible
        self.app._players_dir = MagicMock(return_value=Path("/tmp/mock_players"))
        self.app._player_yaml_lock = MagicMock()
        self.app._player_yaml_lock.__enter__ = MagicMock(return_value=None)
        self.app._player_yaml_lock.__exit__ = MagicMock(return_value=None)

        self.app._invalidate_lan_static_snapshot_cache = MagicMock()
        self.app._refresh_cached_player_profile_projection = MagicMock()

        # We replace the actual file write with a no-op
        self.patcher = patch("pathlib.Path.replace")
        self.mock_replace = self.patcher.start()

        self.patcher2 = patch("pathlib.Path.write_text")
        self.mock_write_text = self.patcher2.start()

    def tearDown(self):
        self.patcher.stop()
        self.patcher2.stop()

    def test_cast_spell_current_values_request_static_snapshot_for_authoritative_sync(self):
        """Casting a spell (which writes player slots) requests static refresh to ensure profile-sync."""
        self.app._schedule_player_yaml_refresh = MagicMock()
        self.app._save_player_spell_slots("Tester", {"1": {"max": 4, "current": 3}})

        # Static invalidation optimized to projection refresh
        self.assertTrue(self.app._refresh_cached_player_profile_projection.called)

        # We now expect include_static=True for spell slots because they live in the static projection.
        self.app._schedule_player_yaml_refresh.assert_called_with(include_static=True, force_reload=False)

    def test_unknown_player_yaml_write_domain_traces_warning(self):
        """Writing a player YAML without passing domains logs a warning and falls back to static invalidation."""
        with patch("dnd_initative_tracker.debug_event") as mock_debug:
            self.app._write_player_yaml_atomic(Path("/tmp/mock_players/Tester.yaml"), {})

            # The static invalidation should be called
            self.app._invalidate_lan_static_snapshot_cache.assert_called_once()
            self.app._lan_log_warning.assert_called()

            warning_call = next((call for call in mock_debug.call_args_list if call.args[0] == "ws.warning.unknown_player_yaml_write_domain"), None)
            self.assertIsNotNone(warning_call)

    def test_manage_spells_change_requests_static_capability_refresh(self):
        """Changing prepared spells via _save_player_spellbook requests static rebuild."""
        self.app._schedule_player_yaml_refresh = MagicMock()
        self.app._save_player_spellbook("Tester", {"prepared_list": ["fireball"]})

        # Static invalidation optimized to projection refresh
        self.assertTrue(self.app._refresh_cached_player_profile_projection.called)

        # Scheduler called with include_static=True
        self.app._schedule_player_yaml_refresh.assert_called_with(include_static=True, force_reload=False)

    def test_broadcast_trace_records_kind_and_invalidation_domains(self):
        """The broadcast mechanism includes necessary tracing information."""
        self.app._lan = MagicMock()
        self.app._lan._clients = {"ws1": MagicMock()}
        self.app._lan_snapshot = MagicMock(return_value={})
        self.app._last_invalidation_domains = {"dynamic_player_values"}
        self.app._lan_static_snapshot_cache_status = MagicMock(return_value=(True, "", 1))

        with patch("dnd_initative_tracker.debug_event") as mock_debug:
            self.app._lan_force_state_broadcast(include_static=False)

            completed_call = next((call for call in mock_debug.call_args_list if call.args[0] == "lan.state.broadcast_completed"), None)
            self.assertIsNotNone(completed_call)

            kwargs = completed_call.kwargs
            self.assertEqual(kwargs.get("broadcast_kind"), "dynamic_only")
            self.assertEqual(set(kwargs.get("invalidation_domains") or []), {"dynamic_player_values"})
            self.assertFalse(kwargs.get("include_static"))
            self.assertFalse(kwargs.get("static_payload_rebuild"))
            self.assertTrue(kwargs.get("dynamic_payload_rebuild"))

    def test_manual_resource_override_current_value_write_does_not_request_static_snapshot(self):
        self.app._load_player_yaml_cache = MagicMock()
        self.app._normalize_character_lookup_key = lambda name: str(name).lower()
        player_path = Path("/tmp/mock_players/Tester.yaml")
        self.app._player_yaml_name_map = {"tester": player_path}
        self.app._player_yaml_cache_by_path = {
            player_path: {"name": "Tester", "resources": {"pools": [{"id": "focus_points", "max": 3, "current": 1}]}}
        }
        self.app._store_character_yaml = MagicMock(return_value={})

        ok, err = self.app._set_player_resource_pool_current("Tester", "focus_points", 2)

        self.assertTrue(ok, err)
        self.app._store_character_yaml.assert_called_once()
        kwargs = self.app._store_character_yaml.call_args.kwargs
        self.assertEqual(set(kwargs.get("invalidation_domains") or []), {"dynamic_player_values", "resource_pools"})
        self.assertFalse(kwargs.get("include_static_refresh"))

if __name__ == "__main__":
    unittest.main()
