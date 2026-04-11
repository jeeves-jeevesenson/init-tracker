import types
import unittest

import dnd_initative_tracker as tracker_mod
import helper_script


class _Var:
    def __init__(self, value):
        self._value = value

    def get(self):
        return self._value


class TacticalAuthoringPerformanceTests(unittest.TestCase):
    def _make_minimal_app(self):
        app = object.__new__(tracker_mod.InitiativeTracker)
        app._map_window = None
        app._lan_grid_cols = 20
        app._lan_grid_rows = 20
        app._lan_positions = {}
        app._lan_obstacles = set()
        app._lan_rough_terrain = {}
        app._lan_aoes = {}
        app._lan_next_aoe_id = 1
        app._lan_auras_enabled = True
        app._session_bg_images = []
        app._session_next_bg_id = 1
        app._map_state = tracker_mod.MapState.from_legacy(cols=20, rows=20)
        app._lan_force_state_broadcast = lambda *args, **kwargs: None
        return app

    def test_apply_tactical_author_feature_uses_single_canonical_path_and_deferred_flush(self):
        app_calls = {"upsert_feature": 0, "scheduled_flush": 0}
        state_obj = object()

        def _upsert_map_feature(**kwargs):
            app_calls["upsert_feature"] += 1
            self.assertFalse(kwargs.get("hydrate_window", True))
            self.assertFalse(kwargs.get("broadcast", True))
            return "feature_1"

        app = types.SimpleNamespace(
            _upsert_map_feature=_upsert_map_feature,
            _capture_canonical_map_state=lambda prefer_window=False: state_obj,
            _schedule_lan_state_broadcast=lambda: app_calls.__setitem__("scheduled_flush", app_calls["scheduled_flush"] + 1),
        )

        redraw_calls = {"count": 0}
        helper = types.SimpleNamespace(
            _map_author_selected_cell=(2, 3),
            map_author_mode_var=_Var("feature"),
            map_author_kind_var=_Var("crate"),
            map_author_label_var=_Var("Crate"),
            map_author_blocking_var=_Var(True),
            map_author_duration_var=_Var(""),
            app=app,
            cols=20,
            rows=20,
            _apply_canonical_map_layers_from_state=lambda state: self.assertIs(state, state_obj),
            _redraw_tactical_layers=lambda: redraw_calls.__setitem__("count", redraw_calls["count"] + 1),
            _sync_tactical_layers_to_app=lambda: self.fail("legacy tactical sync-back should not run during placement"),
        )

        helper_script.BattleMapWindow._apply_tactical_author_to_selected_cell(helper)

        self.assertEqual(app_calls["upsert_feature"], 1)
        self.assertEqual(app_calls["scheduled_flush"], 1)
        self.assertEqual(redraw_calls["count"], 1)

    def test_apply_tactical_author_preset_mode_routes_to_hazard_with_defaults(self):
        app_calls = {"upsert_hazard": 0}
        state_obj = object()

        def _upsert_map_hazard(**kwargs):
            app_calls["upsert_hazard"] += 1
            self.assertEqual(kwargs.get("kind"), "fire")
            payload = kwargs.get("payload") or {}
            self.assertEqual(payload.get("tactical_preset_id"), "fire")
            return "hazard_1"

        app = types.SimpleNamespace(
            _upsert_map_hazard=_upsert_map_hazard,
            _capture_canonical_map_state=lambda prefer_window=False: state_obj,
            _schedule_lan_state_broadcast=lambda: None,
        )

        redraw_calls = {"count": 0}
        helper = types.SimpleNamespace(
            _map_author_selected_cell=(2, 3),
            map_author_mode_var=_Var("preset"),
            map_author_kind_var=_Var("fire"),
            map_author_preset_var=_Var("fire"),
            map_author_count_var=_Var("1"),
            map_author_label_var=_Var(""),
            map_author_blocking_var=_Var(False),
            map_author_advanced_var=_Var(False),
            map_author_duration_var=_Var(""),
            app=app,
            cols=20,
            rows=20,
            _apply_canonical_map_layers_from_state=lambda state: self.assertIs(state, state_obj),
            _redraw_tactical_layers=lambda: redraw_calls.__setitem__("count", redraw_calls["count"] + 1),
        )

        helper_script.BattleMapWindow._apply_tactical_author_to_selected_cell(helper)
        self.assertEqual(app_calls["upsert_hazard"], 1)
        self.assertEqual(redraw_calls["count"], 1)

    def test_tactical_upserts_still_build_expected_canonical_state_without_immediate_hydrate_or_broadcast(self):
        app = self._make_minimal_app()

        feature_id = tracker_mod.InitiativeTracker._upsert_map_feature(
            app,
            col=1,
            row=2,
            kind="crate",
            payload={"name": "Crate"},
            hydrate_window=False,
            broadcast=False,
        )
        hazard_id = tracker_mod.InitiativeTracker._upsert_map_hazard(
            app,
            col=3,
            row=4,
            kind="fire",
            payload={"duration_turns": 2},
            hydrate_window=False,
            broadcast=False,
        )
        structure_id = tracker_mod.InitiativeTracker._upsert_map_structure(
            app,
            kind="wall",
            anchor_col=5,
            anchor_row=6,
            occupied_cells=[(5, 6), (6, 6)],
            payload={"name": "Wall"},
            hydrate_window=False,
            broadcast=False,
        )
        tracker_mod.InitiativeTracker._set_map_elevation(
            app,
            7,
            8,
            10.0,
            hydrate_window=False,
            broadcast=False,
        )

        state = tracker_mod.InitiativeTracker._capture_canonical_map_state(app, prefer_window=False).to_dict()
        self.assertTrue(any(item["id"] == feature_id and item["kind"] == "crate" for item in state["features"]))
        self.assertTrue(any(item["id"] == hazard_id and item["kind"] == "fire" for item in state["hazards"]))
        self.assertTrue(any(item["id"] == structure_id and item["kind"] == "wall" for item in state["structures"]))
        self.assertTrue(any(item["col"] == 7 and item["row"] == 8 and item["elevation"] == 10.0 for item in state["elevation_cells"]))

    def test_schedule_lan_state_broadcast_coalesces_repeated_requests(self):
        app = object.__new__(tracker_mod.InitiativeTracker)
        app._lan_state_broadcast_after_id = None
        app._lan_state_broadcast_delay_ms = 50
        timers = {}
        next_id = {"value": 1}
        broadcasts = []

        def _after(delay, callback):
            timer_id = f"after-{next_id['value']}"
            next_id["value"] += 1
            timers[timer_id] = {"delay": delay, "callback": callback}
            return timer_id

        def _after_cancel(timer_id):
            timers.pop(timer_id, None)

        app.after = _after
        app.after_cancel = _after_cancel
        app._lan_force_state_broadcast = lambda include_static=True: broadcasts.append(include_static)

        tracker_mod.InitiativeTracker._schedule_lan_state_broadcast(app)
        tracker_mod.InitiativeTracker._schedule_lan_state_broadcast(app)

        self.assertEqual(len(timers), 1)
        only_timer = next(iter(timers.values()))
        self.assertEqual(only_timer["delay"], 50)
        self.assertEqual(broadcasts, [])

        only_timer["callback"]()
        self.assertEqual(broadcasts, [False])
        self.assertIsNone(app._lan_state_broadcast_after_id)


if __name__ == "__main__":
    unittest.main()
