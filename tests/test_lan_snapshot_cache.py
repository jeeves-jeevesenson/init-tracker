import json
import tempfile
import types
import unittest
from pathlib import Path

import dnd_initative_tracker as tracker_mod
from runtime_config import configure_debug_trace


class LanSnapshotCacheTests(unittest.TestCase):
    def tearDown(self):
        configure_debug_trace(False)

    def _snapshot_app(self):
        app = object.__new__(tracker_mod.InitiativeTracker)
        app._lan_grid_cols = 10
        app._lan_grid_rows = 10
        app._lan_obstacles = set()
        app._lan_positions = {}
        app._lan_aoes = {}
        app._lan_rough_terrain = {}
        app._lan_next_aoe_id = 1
        app.combatants = {}
        app.current_cid = None
        app.round_num = 1
        app._display_order = lambda: []
        app._oplog = lambda *args, **kwargs: None
        app._lan_resource_pools_last_build = tracker_mod.time.monotonic()
        app._lan = types.SimpleNamespace(_cached_snapshot={})

        calls = {"presets": 0, "spells": 0, "profiles": 0, "beasts": 0}

        def _count(key, value):
            calls[key] += 1
            return value

        app._spell_presets_payload = lambda: _count("presets", [{"slug": "shield"}])
        app._player_spell_config_payload = lambda: _count("spells", {"Alice": {"prepared": ["shield"]}})
        app._player_profiles_payload = lambda: _count("profiles", {"Alice": {"name": "Alice"}})
        app._load_beast_forms = lambda: _count("beasts", [{"id": "wolf"}])
        app._player_resource_pools_payload = lambda: {"Alice": [{"id": "slots", "current": app.round_num}]}
        return app, calls

    def test_repeated_full_snapshots_reuse_copied_static_component(self):
        app, calls = self._snapshot_app()

        first = app._lan_snapshot(include_static=True)
        first["player_profiles"]["Alice"]["name"] = "mutated"
        second = app._lan_snapshot(include_static=True)

        self.assertEqual(calls, {"presets": 1, "spells": 1, "profiles": 1, "beasts": 1})
        self.assertEqual(second["spell_presets"], [{"slug": "shield"}])
        self.assertEqual(second["player_profiles"]["Alice"]["name"], "Alice")

    def test_dynamic_snapshot_fields_stay_fresh_after_static_cache_reuse(self):
        app, calls = self._snapshot_app()

        first = app._lan_snapshot(include_static=True)
        app.round_num = 4
        second = app._lan_snapshot(include_static=True)

        self.assertEqual(first["round_num"], 1)
        self.assertEqual(second["round_num"], 4)
        self.assertEqual(calls["profiles"], 1)

    def test_static_invalidation_causes_static_component_rebuild(self):
        app, calls = self._snapshot_app()

        app._lan_snapshot(include_static=True)
        app._invalidate_lan_static_snapshot_cache("unit_test_dirty")
        rebuilt = app._lan_snapshot(include_static=True)

        self.assertEqual(calls["presets"], 2)
        self.assertEqual(calls["profiles"], 2)
        self.assertEqual(rebuilt["beast_forms"], [{"id": "wolf"}])

    def test_no_client_force_broadcast_skips_snapshot_build(self):
        app, _calls = self._snapshot_app()
        app._lan = types.SimpleNamespace(_clients={}, _dm_ws_clients={})
        app._lan_snapshot = lambda **_kwargs: (_ for _ in ()).throw(AssertionError("snapshot should be skipped"))

        tracker_mod.InitiativeTracker._lan_force_state_broadcast(app)

    def test_force_broadcast_keeps_full_lan_snapshot_shape_with_cached_static(self):
        app, _calls = self._snapshot_app()
        full = app._lan_snapshot(include_static=True)
        states = []
        app.round_num = 2
        app._lan = types.SimpleNamespace(
            _clients={1: object()},
            _dm_ws_clients={},
            _cached_snapshot={},
            _cached_pcs=[],
            _last_snapshot=None,
            _dm_service=None,
            _broadcast_state=lambda snap: states.append(dict(snap)),
        )
        app._lan_pcs = lambda: []
        app._lan_claimable = lambda: []

        tracker_mod.InitiativeTracker._lan_force_state_broadcast(app)

        self.assertEqual(len(states), 1)
        self.assertEqual(states[0]["round_num"], 2)
        for key in ("units", "grid", "aoes", "spell_presets", "player_spells", "player_profiles", "beast_forms"):
            self.assertIn(key, states[0])
            self.assertIn(key, full)

    def test_force_snapshot_span_marks_static_cache_hit_in_debug_trace(self):
        app, _calls = self._snapshot_app()
        app._lan_snapshot(include_static=True)
        app._lan = types.SimpleNamespace(
            _clients={1: object()},
            _dm_ws_clients={},
            _cached_snapshot={},
            _cached_pcs=[],
            _last_snapshot=None,
            _dm_service=None,
            _broadcast_state=lambda _snap: None,
        )
        app._lan_pcs = lambda: []
        app._lan_claimable = lambda: []

        with tempfile.TemporaryDirectory() as tmpdir:
            trace_path = configure_debug_trace(True, log_dir=Path(tmpdir))
            tracker_mod.InitiativeTracker._lan_force_state_broadcast(app)
            entries = [
                json.loads(line)
                for line in Path(trace_path).read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]

        snapshot_end = next(
            entry
            for entry in entries
            if entry.get("event") == "span.end" and entry.get("span") == "lan.snapshot.build"
        )
        self.assertTrue(snapshot_end.get("snapshot_cache_hit"))
        self.assertEqual(snapshot_end.get("snapshot_cache_scope"), "dynamic+cached_static")

    def test_lan_controller_carryover_prevents_static_erasure(self):
        app, _calls = self._snapshot_app()
        lan = tracker_mod.LanController(app)

        # 1. Seed with full static data
        full = app._lan_snapshot(include_static=True)
        lan._cached_snapshot = full
        self.assertTrue(len(lan._cached_snapshot.get("spell_presets", [])) > 0)
        self.assertTrue(len(lan._cached_snapshot.get("player_spells", {})) > 0)

        # 2. Perform a cheap "stripped" snapshot
        stripped = app._lan_snapshot(include_static=False, hydrate_static=False)
        self.assertEqual(len(stripped.get("spell_presets", [])), 0)

        # 3. Merge carryover
        merged = lan._merge_cached_snapshot_carryover(stripped)

        # Verify carryover preserved the fields
        self.assertEqual(merged["spell_presets"], full["spell_presets"])
        self.assertEqual(merged["player_spells"], full["player_spells"])
        self.assertEqual(merged["player_profiles"], full["player_profiles"])

    def test_static_data_payload_repairs_missing_cache_fields(self):
        app, calls = self._snapshot_app()
        lan = tracker_mod.LanController(app)

        # Poison cache with empty static fields
        lan._cached_snapshot = {
            "spell_presets": [],
            "player_spells": {},
            "player_profiles": {},
            "resource_pools": {},
            "beast_forms": []
        }

        payload = lan._static_data_payload()

        # Verify it went to the app to repair
        self.assertEqual(calls["presets"], 1)
        self.assertEqual(calls["spells"], 1)
        self.assertEqual(calls["profiles"], 1)
        self.assertEqual(calls["beasts"], 1)

        # Verify payload is rich
        self.assertEqual(payload["spell_presets"], [{"slug": "shield"}])
        self.assertEqual(payload["player_spells"], {"Alice": {"prepared": ["shield"]}})

        # Verify cache was also repaired
        self.assertEqual(lan._cached_snapshot["spell_presets"], [{"slug": "shield"}])
        self.assertEqual(lan._cached_snapshot["player_spells"], {"Alice": {"prepared": ["shield"]}})


if __name__ == "__main__":
    unittest.main()
