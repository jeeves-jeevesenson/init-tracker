import types
import unittest

import dnd_initative_tracker as tracker_mod
import helper_script


class _Var:
    def __init__(self, value):
        self._value = value

    def get(self):
        return self._value

    def set(self, value):
        self._value = value


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
            map_author_tool_var=_Var("stamp"),
            map_author_preset_var=_Var("crate_stack"),
            map_author_label_var=_Var("Crate"),
            map_author_duration_var=_Var(""),
            map_author_count_var=_Var("1"),
            app=app,
            cols=20,
            rows=20,
            _apply_canonical_map_layers_from_state=lambda state: self.assertIs(state, state_obj),
            _redraw_tactical_layers=lambda: redraw_calls.__setitem__("count", redraw_calls["count"] + 1),
            _sync_tactical_layers_to_app=lambda: self.fail("legacy tactical sync-back should not run during placement"),
            _refresh_tactical_palette_state=lambda normalized=None: None,
            _selected_tactical_preset_id=lambda: "crate_stack",
            _selected_tactical_preset=lambda: {"stackable": True, "kind": "crate"},
            map_author_elevation_var=_Var("5"),
            _post_tactical_map_mutation=lambda redraw_all=False, schedule_broadcast=True: (
                self.assertFalse(redraw_all),
                helper._apply_canonical_map_layers_from_state(state_obj),
                app._schedule_lan_state_broadcast() if schedule_broadcast else None,
                helper._redraw_tactical_layers(),
            ),
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
            map_author_tool_var=_Var("stamp"),
            map_author_preset_var=_Var("fire"),
            map_author_count_var=_Var("1"),
            map_author_label_var=_Var(""),
            map_author_duration_var=_Var(""),
            map_author_elevation_var=_Var("5"),
            app=app,
            cols=20,
            rows=20,
            _apply_canonical_map_layers_from_state=lambda state: self.assertIs(state, state_obj),
            _redraw_tactical_layers=lambda: redraw_calls.__setitem__("count", redraw_calls["count"] + 1),
            _refresh_tactical_palette_state=lambda normalized=None: None,
            _selected_tactical_preset_id=lambda: "fire",
            _selected_tactical_preset=lambda: {"kind": "fire"},
            _post_tactical_map_mutation=lambda redraw_all=False, schedule_broadcast=True: (
                self.assertFalse(redraw_all),
                helper._apply_canonical_map_layers_from_state(state_obj),
                app._schedule_lan_state_broadcast() if schedule_broadcast else None,
                helper._redraw_tactical_layers(),
            ),
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

    def test_remove_tactical_entities_batches_canonical_removals_without_sync_back(self):
        calls = {"remove_feature": 0, "remove_hazard": 0, "remove_structure": 0, "set_elevation": 0, "scheduled_flush": 0}
        state_obj = object()

        app = types.SimpleNamespace(
            _remove_map_feature=lambda _id, **kwargs: (calls.__setitem__("remove_feature", calls["remove_feature"] + 1), self.assertFalse(kwargs.get("hydrate_window", True)), self.assertFalse(kwargs.get("broadcast", True))),
            _remove_map_hazard=lambda _id, **kwargs: (calls.__setitem__("remove_hazard", calls["remove_hazard"] + 1), self.assertFalse(kwargs.get("hydrate_window", True)), self.assertFalse(kwargs.get("broadcast", True))),
            _remove_map_structure=lambda _id, **kwargs: (calls.__setitem__("remove_structure", calls["remove_structure"] + 1), self.assertFalse(kwargs.get("hydrate_window", True)), self.assertFalse(kwargs.get("broadcast", True))),
            _set_map_elevation=lambda _col, _row, _value, **kwargs: (calls.__setitem__("set_elevation", calls["set_elevation"] + 1), self.assertFalse(kwargs.get("hydrate_window", True)), self.assertFalse(kwargs.get("broadcast", True))),
            _capture_canonical_map_state=lambda prefer_window=False: state_obj,
            _schedule_lan_state_broadcast=lambda: calls.__setitem__("scheduled_flush", calls["scheduled_flush"] + 1),
        )

        helper = types.SimpleNamespace(
            _map_author_selected_cell=(2, 3),
            map_features={"f1": {"id": "f1", "col": 2, "row": 3, "payload": {}}},
            map_hazards={"h1": {"id": "h1", "col": 2, "row": 3, "payload": {}}},
            map_structures={"s1": {"id": "s1", "anchor_col": 2, "anchor_row": 3, "occupied_cells": []}},
            map_elevation_cells={(2, 3): 5.0},
            _entity_cells=lambda col, row, payload: [(int(col), int(row))],
            app=app,
            _apply_canonical_map_layers_from_state=lambda state: self.assertIs(state, state_obj),
            _redraw_tactical_layers=lambda: None,
            _update_selected_structure_contact_status=lambda: None,
            _post_tactical_map_mutation=lambda redraw_all=False, schedule_broadcast=True: (
                self.assertFalse(redraw_all),
                helper._apply_canonical_map_layers_from_state(state_obj),
                app._schedule_lan_state_broadcast() if schedule_broadcast else None,
            ),
        )

        changed = helper_script.BattleMapWindow._remove_tactical_entities_at_selected_cell(helper)
        self.assertTrue(changed)
        self.assertEqual(calls["remove_feature"], 1)
        self.assertEqual(calls["remove_hazard"], 1)
        self.assertEqual(calls["remove_structure"], 1)
        self.assertEqual(calls["set_elevation"], 1)
        self.assertEqual(calls["scheduled_flush"], 1)

    def test_canvas_tactical_drag_defers_broadcast_until_release(self):
        calls = {"apply": 0, "scheduled_flush": 0}

        helper = types.SimpleNamespace(
            canvas=types.SimpleNamespace(canvasx=lambda x: x, canvasy=lambda y: y),
            _rotation_handle_hit_cid=lambda _mx, _my: None,
            rough_mode_var=_Var(False),
            obstacle_mode_var=_Var(False),
            map_place_source_var=_Var("tactical"),
            _pixel_to_grid=lambda mx, my: (int(mx), int(my)),
            _update_selected_structure_contact_status=lambda: None,
            _update_selected_tactical_cell_status=lambda: None,
            _refresh_tactical_palette_state=lambda: None,
            map_author_tool_var=_Var("stamp"),
            _active_map_interaction_mode=lambda: "place",
            _apply_tactical_author_to_selected_cell=lambda **kwargs: (
                calls.__setitem__("apply", calls["apply"] + 1),
                self.assertFalse(kwargs.get("schedule_broadcast", True)),
                True,
            )[-1],
            _remove_tactical_entities_at_selected_cell=lambda **kwargs: False,
            _map_author_selected_cell=None,
            _map_author_painting=False,
            _map_author_drag_dirty=False,
            _map_author_last_painted_cell=None,
            _drawing_obstacles=False,
            _drawing_rough=False,
            app=types.SimpleNamespace(
                _schedule_lan_state_broadcast=lambda: calls.__setitem__("scheduled_flush", calls["scheduled_flush"] + 1),
                _lan_force_state_broadcast=lambda: calls.__setitem__("scheduled_flush", calls["scheduled_flush"] + 1),
            ),
        )
        event = types.SimpleNamespace(x=4, y=6, state=0)

        helper_script.BattleMapWindow._on_canvas_press(helper, event)
        helper_script.BattleMapWindow._on_canvas_release(helper, event)

        self.assertEqual(calls["apply"], 1)
        self.assertEqual(calls["scheduled_flush"], 1)
        self.assertFalse(helper._map_author_painting)

    def test_rough_paint_toggle_does_not_override_select_mode(self):
        calls = {"rough_paint": 0}
        helper = types.SimpleNamespace(
            canvas=types.SimpleNamespace(
                canvasx=lambda x: x,
                canvasy=lambda y: y,
                find_overlapping=lambda *_args: [],
            ),
            _rotation_handle_hit_cid=lambda _mx, _my: None,
            _active_map_interaction_mode=lambda: "select",
            rough_mode_var=_Var(True),
            obstacle_mode_var=_Var(False),
            map_place_source_var=_Var("tactical"),
            _paint_rough_terrain_from_event=lambda _event: calls.__setitem__("rough_paint", calls["rough_paint"] + 1),
            _pixel_to_grid=lambda _mx, _my: (2, 3),
            _update_selected_structure_contact_status=lambda: None,
            _update_selected_tactical_cell_status=lambda: None,
            _refresh_tactical_palette_state=lambda: None,
            _map_author_selected_cell=None,
            _drag_kind=None,
            _drag_id=None,
            _drag_origin_cell=None,
            _rotating_token_cid=None,
            _group_preferred_cid=None,
            _cell_to_cids={},
            _shift_held=False,
            _clear_rotation_affordance=lambda: None,
            _drawing_obstacles=False,
            _drawing_rough=False,
        )
        event = types.SimpleNamespace(x=4, y=6, state=0)

        helper_script.BattleMapWindow._on_canvas_press(helper, event)

        self.assertEqual(calls["rough_paint"], 0)
        self.assertEqual(helper._map_author_selected_cell, (2, 3))


if __name__ == "__main__":
    unittest.main()
