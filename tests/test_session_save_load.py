import json
import tempfile
import types
import unittest
from pathlib import Path

import dnd_initative_tracker as tracker_mod


class SessionSaveLoadTests(unittest.TestCase):
    def _make_app(self, history_path: Path):
        app = object.__new__(tracker_mod.InitiativeTracker)
        app.combatants = {}
        app._next_id = 1
        app._next_stack_id = 7
        app.current_cid = None
        app.start_cid = None
        app.round_num = 1
        app.turn_num = 0
        app.in_combat = False
        app._turn_snapshots = {}
        app._name_role_memory = {}
        app._summon_groups = {}
        app._summon_group_meta = {}
        app._pending_pre_summons = {}
        app._pending_mount_requests = {}
        app._concentration_save_state = {}

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

        app._map_window = None
        app._monsters_by_name = {}

        def _create_combatant(**kwargs):
            cid = int(app._next_id)
            app._next_id += 1
            c = types.SimpleNamespace(
                cid=cid,
                name=kwargs["name"],
                hp=int(kwargs["hp"]),
                speed=int(kwargs["speed"]),
                swim_speed=int(kwargs.get("swim_speed", 0)),
                fly_speed=int(kwargs.get("fly_speed", 0)),
                burrow_speed=int(kwargs.get("burrow_speed", 0)),
                climb_speed=int(kwargs.get("climb_speed", 0)),
                movement_mode=str(kwargs.get("movement_mode", "normal")),
                move_remaining=int(kwargs.get("speed", 0)),
                move_total=int(kwargs.get("speed", 0)),
                initiative=int(kwargs.get("initiative", 0)),
                dex=kwargs.get("dex"),
                roll=None,
                nat20=False,
                ally=bool(kwargs.get("ally", False)),
                is_pc=bool(kwargs.get("is_pc", False)),
                is_spellcaster=bool(kwargs.get("is_spellcaster", False)),
                saving_throws=dict(kwargs.get("saving_throws") or {}),
                ability_mods=dict(kwargs.get("ability_mods") or {}),
                actions=list(kwargs.get("actions") or []),
                bonus_actions=list(kwargs.get("bonus_actions") or []),
                reactions=list(kwargs.get("reactions") or []),
                monster_spec=kwargs.get("monster_spec"),
            )
            app.combatants[cid] = c
            return cid

        app._create_combatant = _create_combatant
        app._find_monster_spec_by_slug = lambda _slug: None
        app._remove_combatants_with_lan_cleanup = lambda cids: [app.combatants.pop(int(cid), None) for cid in list(cids)]
        app._history_file_path = lambda: history_path
        app._load_history_into_log = lambda max_lines=2000: None
        app._update_turn_ui = lambda: None
        app._rebuild_table = lambda scroll_to_current=True: None
        app._lan_force_state_broadcast = lambda: None
        app._log = lambda *_args, **_kwargs: None
        app._lan_battle_log_lines = lambda limit=0: ["[2026-01-01 00:00:00]\tFirst", "[2026-01-01 00:00:01]\tSecond"]
        return app

    def test_session_snapshot_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            history_path = Path(tmpdir) / "battle.log"
            app = self._make_app(history_path)

            app._next_id = 3
            c1 = types.SimpleNamespace(
                cid=1,
                name="Alice",
                hp=23,
                speed=30,
                swim_speed=15,
                fly_speed=0,
                burrow_speed=0,
                climb_speed=10,
                movement_mode="normal",
                move_remaining=10,
                move_total=30,
                initiative=18,
                dex=3,
                roll=15,
                nat20=False,
                ally=True,
                is_pc=True,
                is_spellcaster=True,
                saving_throws={"con": 5},
                ability_mods={"dex": 3},
                actions=[{"name": "Attack", "remaining": 0}],
                bonus_actions=[{"name": "Misty Step", "remaining": 1}],
                reactions=[{"name": "Shield", "remaining": 1}],
                monster_spec=None,
                condition_stacks=[tracker_mod.base.ConditionStack(sid=4, ctype="prone", remaining_turns=1)],
                concentration_started_turn=(2, 5),
                concentration_aoe_ids=[10],
                concentrating=True,
                concentration_spell="web",
                token_color="#123456",
                token_border_color="#ffffff",
                temp_hp=4,
                action_remaining=0,
                bonus_action_remaining=1,
                reaction_remaining=1,
                spell_cast_remaining=0,
                attack_resource_remaining=2,
                facing_deg=180,
                summon_group_id="grp-1",
                summoned_by_cid=None,
            )
            c2 = types.SimpleNamespace(
                cid=2,
                name="Goblin",
                hp=7,
                speed=30,
                swim_speed=0,
                fly_speed=0,
                burrow_speed=0,
                climb_speed=0,
                movement_mode="normal",
                move_remaining=30,
                move_total=30,
                initiative=12,
                dex=2,
                roll=10,
                nat20=False,
                ally=False,
                is_pc=False,
                is_spellcaster=False,
                saving_throws={},
                ability_mods={},
                actions=[],
                bonus_actions=[],
                reactions=[],
                monster_spec=None,
                condition_stacks=[],
                concentration_started_turn=None,
                concentration_aoe_ids=[],
                concentrating=False,
                concentration_spell=None,
            )
            app.combatants = {1: c1, 2: c2}
            app.current_cid = 1
            app.start_cid = 2
            app.round_num = 3
            app.turn_num = 6
            app.in_combat = True
            app._turn_snapshots = {"1": {"move_remaining": 10}}
            app._name_role_memory = {"Alice": "pc", "Goblin": "enemy"}
            app._summon_groups = {"grp-1": [1]}
            app._summon_group_meta = {"grp-1": {"name": "Summons"}}
            app._pending_pre_summons = {"1": {"spell": "summon beast"}}
            app._pending_mount_requests = {"req": {"rider": 1}}
            app._concentration_save_state = {"1": {"dc": 10}}

            app._lan_grid_cols = 40
            app._lan_grid_rows = 25
            app._lan_positions = {1: (4, 5), 2: (10, 3)}
            app._lan_obstacles = {(1, 1), (2, 2)}
            app._lan_rough_terrain = {(3, 3): {"color": "#ff0000", "movement_type": "ground", "is_swim": False, "is_rough": True}}
            app._lan_aoes = {10: {"kind": "circle", "name": "Web", "cx": 4.0, "cy": 5.0, "radius_sq": 4.0, "owner_cid": 1}}
            app._lan_next_aoe_id = 11
            app._lan_auras_enabled = False
            app._session_bg_images = [{"bid": 1, "path": "/tmp/missing.png", "x": 1.0, "y": 2.0, "scale_pct": 50.0, "trans_pct": 30.0, "locked": True}]
            app._session_next_bg_id = 2

            snap_path = Path(tmpdir) / "session.json"
            app._save_session_to_path(snap_path, label="roundtrip")

            payload = json.loads(snap_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["schema_version"], 2)
            self.assertEqual(payload["metadata"]["label"], "roundtrip")
            self.assertIn("canonical", payload["map"])
            canonical = payload["map"]["canonical"]
            self.assertEqual(canonical["grid"]["cols"], 40)
            self.assertEqual(canonical["token_positions"][0]["cid"], 1)
            self.assertEqual(canonical["terrain_cells"][0]["col"], 3)

            app.combatants = {}
            app.current_cid = None
            app.start_cid = None
            app.round_num = 1
            app.turn_num = 0
            app.in_combat = False
            app._lan_positions = {}
            app._lan_obstacles = set()
            app._lan_rough_terrain = {}
            app._lan_aoes = {}

            app._load_session_from_path(snap_path)

            self.assertEqual(sorted(app.combatants.keys()), [1, 2])
            self.assertEqual(app.combatants[1].name, "Alice")
            self.assertEqual(app.combatants[1].hp, 23)
            self.assertEqual(app.combatants[1].temp_hp, 4)
            self.assertEqual(app.combatants[1].concentration_aoe_ids, [10])
            self.assertEqual(app.combatants[1].condition_stacks[0].ctype, "prone")
            self.assertEqual(app.current_cid, 1)
            self.assertEqual(app.round_num, 3)
            self.assertEqual(app.turn_num, 6)
            self.assertTrue(app.in_combat)

            self.assertEqual(app._lan_grid_cols, 40)
            self.assertEqual(app._lan_grid_rows, 25)
            self.assertEqual(app._lan_positions[1], (4, 5))
            self.assertIn((1, 1), app._lan_obstacles)
            self.assertEqual(app._lan_rough_terrain[(3, 3)]["color"], "#ff0000")
            self.assertIn(10, app._lan_aoes)
            self.assertEqual(app._lan_next_aoe_id, 11)
            self.assertFalse(app._lan_auras_enabled)
            self.assertEqual(app._session_next_bg_id, 2)

            log_text = history_path.read_text(encoding="utf-8")
            self.assertIn("First", log_text)
            self.assertIn("Second", log_text)



    def test_new_session_apply_blank_state_clears_combat_map_and_log(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            history_path = Path(tmpdir) / "battle.log"
            history_path.write_text("line one\nline two\n", encoding="utf-8")
            app = self._make_app(history_path)

            app.combatants = {
                1: types.SimpleNamespace(cid=1, name="Alice"),
                2: types.SimpleNamespace(cid=2, name="Goblin"),
            }
            app._next_id = 9
            app._next_stack_id = 4
            app.current_cid = 2
            app.start_cid = 1
            app.round_num = 5
            app.turn_num = 7
            app.in_combat = True
            app._turn_snapshots = {1: {"move_remaining": 10}}
            app._name_role_memory = {"Alice": "pc"}
            app._summon_groups = {"group": [2]}
            app._summon_group_meta = {"group": {"name": "Summons"}}
            app._pending_pre_summons = {1: {"spell": "summon"}}
            app._pending_mount_requests = {"mount": {"cid": 1}}
            app._concentration_save_state = {1: {"dc": 10}}
            app._session_has_saved = True

            app._lan_positions = {1: (2, 3)}
            app._lan_obstacles = {(1, 1)}
            app._lan_rough_terrain = {(4, 4): {"color": "#fff"}}
            app._lan_aoes = {10: {"owner_cid": 1}}
            app._session_bg_images = [{"bid": 1, "path": "bg.png"}]
            app._session_next_bg_id = 3

            removed_cids = []
            def _remove(cids):
                removed_cids.extend(list(cids))
                for cid in list(cids):
                    app.combatants.pop(int(cid), None)
            app._remove_combatants_with_lan_cleanup = _remove

            reset_calls = []
            original_reset = tracker_mod.InitiativeTracker._reset_map_state
            def _reset():
                reset_calls.append(True)
                original_reset(app)
            app._reset_map_state = _reset

            history_reload_calls = []
            app._load_history_into_log = lambda max_lines=2000: history_reload_calls.append(max_lines)

            broadcasts = []
            app._lan_force_state_broadcast = lambda: broadcasts.append(True)

            result = app._new_session_apply_blank_state(confirm=False)

            self.assertTrue(result)
            self.assertEqual(sorted(removed_cids), [1, 2])
            self.assertEqual(app.combatants, {})
            self.assertEqual(app._next_id, 1)
            self.assertEqual(app._next_stack_id, 1)
            self.assertIsNone(app.current_cid)
            self.assertIsNone(app.start_cid)
            self.assertEqual(app.round_num, 1)
            self.assertEqual(app.turn_num, 0)
            self.assertFalse(app.in_combat)
            self.assertEqual(app._turn_snapshots, {})
            self.assertEqual(app._name_role_memory, {})
            self.assertEqual(app._summon_groups, {})
            self.assertEqual(app._summon_group_meta, {})
            self.assertEqual(app._pending_pre_summons, {})
            self.assertEqual(app._pending_mount_requests, {})
            self.assertEqual(app._concentration_save_state, {})
            self.assertFalse(app._session_has_saved)

            self.assertEqual(reset_calls, [True])
            self.assertEqual(app._lan_positions, {})
            self.assertEqual(app._lan_obstacles, set())
            self.assertEqual(app._lan_rough_terrain, {})
            self.assertEqual(app._lan_aoes, {})
            self.assertEqual(app._session_bg_images, [])
            self.assertEqual(app._session_next_bg_id, 1)

            self.assertEqual(history_path.read_text(encoding="utf-8"), "")
            self.assertEqual(history_reload_calls, [2000])
            self.assertEqual(len(broadcasts), 2)

    def test_auto_load_quick_save_on_startup_loads_existing_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            app = self._make_app(Path(tmpdir) / "battle.log")
            quick_path = Path(tmpdir) / "sessions" / "quick_save.json"
            quick_path.parent.mkdir(parents=True, exist_ok=True)
            quick_path.write_text("{}", encoding="utf-8")

            app._session_quicksave_path = lambda: quick_path
            loaded_paths = []
            app._load_session_from_path = lambda path: loaded_paths.append(Path(path))

            app._auto_load_quick_save_on_startup()

            self.assertEqual(loaded_paths, [quick_path])

    def test_apply_saved_positions_to_map_window_creates_and_moves_tokens(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            app = self._make_app(Path(tmpdir) / "battle.log")
            app.combatants = {1: types.SimpleNamespace(cid=1), 2: types.SimpleNamespace(cid=2)}
            app._lan_positions = {1: (4, 5), 2: (7, 8)}

            created = []
            laid_out = []

            mw = types.SimpleNamespace(
                unit_tokens={1: {"col": 0, "row": 0}},
                _create_unit_token=lambda cid, col, row: created.append((cid, col, row)),
                _layout_unit=lambda cid: laid_out.append(cid),
                _update_groups=lambda: None,
                _update_move_highlight=lambda: None,
                _update_included_for_selected=lambda: None,
                winfo_exists=lambda: True,
            )

            app._apply_saved_positions_to_map_window(mw)

            self.assertEqual(mw.unit_tokens[1]["col"], 4)
            self.assertEqual(mw.unit_tokens[1]["row"], 5)
            self.assertEqual(laid_out, [1])
            self.assertEqual(created, [(2, 7, 8)])

    def test_reset_map_state_clears_stored_and_live_map_data(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            app = self._make_app(Path(tmpdir) / "battle.log")
            app._lan_positions = {1: (1, 2)}
            app._lan_obstacles = {(0, 0)}
            app._lan_rough_terrain = {(1, 1): {"color": "#fff"}}
            app._lan_aoes = {1: {"kind": "circle"}}
            app._session_bg_images = [{"bid": 1, "path": "x"}]
            app._session_next_bg_id = 3
            app._lan_force_state_broadcast = lambda: None

            deleted_items = []

            class _Canvas:
                def delete(self, item):
                    deleted_items.append(item)

            mw = types.SimpleNamespace(
                obstacles={(3, 3)},
                rough_terrain={(4, 4): {"color": "#000"}},
                aoes={9: {"kind": "cone"}},
                unit_tokens={10: {"col": 1, "row": 1}},
                _token_facing={10: 0},
                bg_images={5: {"item": 88}},
                _next_aoe_id=12,
                _next_bg_id=6,
                _redraw_all=lambda: None,
                refresh_units=lambda: None,
                _refresh_aoe_list=lambda: None,
                canvas=_Canvas(),
                winfo_exists=lambda: True,
            )
            app._map_window = mw

            app._reset_map_state()

            self.assertEqual(app._lan_positions, {})
            self.assertEqual(app._lan_obstacles, set())
            self.assertEqual(app._lan_rough_terrain, {})
            self.assertEqual(app._lan_aoes, {})
            self.assertEqual(app._lan_next_aoe_id, 1)
            self.assertEqual(app._session_bg_images, [])
            self.assertEqual(app._session_next_bg_id, 1)
            self.assertEqual(mw.unit_tokens, {})
            self.assertEqual(mw.obstacles, set())
            self.assertEqual(mw.rough_terrain, {})
            self.assertEqual(mw.aoes, {})
            self.assertEqual(mw.bg_images, {})
            self.assertEqual(deleted_items, [88])

    def test_open_map_mode_keeps_prompted_grid_size_and_syncs_lan_state(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            app = self._make_app(Path(tmpdir) / "battle.log")
            app._lan_grid_cols = 20
            app._lan_grid_rows = 20
            app._lan_obstacles = set()
            app._lan_rough_terrain = {}
            app._lan_aoes = {}
            app._lan_next_aoe_id = 1
            app._session_next_bg_id = 1
            app._session_bg_images = []
            app._apply_saved_positions_to_map_window = lambda _mw: None
            app._restore_map_backgrounds = lambda _images: None

            map_window = types.SimpleNamespace(
                cols=100,
                rows=100,
                obstacles=set(),
                rough_terrain={},
                aoes={},
                _next_aoe_id=1,
                _next_bg_id=1,
                _redraw_all=lambda: None,
                refresh_units=lambda: None,
                _refresh_aoe_list=lambda: None,
                winfo_exists=lambda: True,
            )

            original_open_map_mode = tracker_mod.base.InitiativeTracker._open_map_mode
            try:
                tracker_mod.base.InitiativeTracker._open_map_mode = lambda self: setattr(self, "_map_window", map_window)
                tracker_mod.InitiativeTracker._open_map_mode(app)
            finally:
                tracker_mod.base.InitiativeTracker._open_map_mode = original_open_map_mode

            self.assertEqual(map_window.cols, 100)
            self.assertEqual(map_window.rows, 100)
            self.assertEqual(app._lan_grid_cols, 100)
            self.assertEqual(app._lan_grid_rows, 100)

    def test_migrate_v1_snapshot_adds_canonical_map_state(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            app = self._make_app(Path(tmpdir) / "battle.log")
            payload_v1 = {
                "schema_version": 1,
                "combat": {},
                "map": {
                    "grid": {"cols": 9, "rows": 7, "feet_per_square": 5},
                    "positions": [{"cid": 1, "col": 2, "row": 3}],
                    "obstacles": [{"col": 4, "row": 5}],
                    "rough_terrain": [{"col": 1, "row": 1, "color": "#fff", "movement_type": "ground", "is_swim": False, "is_rough": True}],
                    "aoes": {"10": {"kind": "circle", "cx": 1.0, "cy": 1.0}},
                    "next_aoe_id": 11,
                },
                "log": {"lines": []},
            }
            migrated = app._migrate_session_snapshot_payload(payload_v1)
            self.assertEqual(migrated["schema_version"], 2)
            self.assertIn("canonical", migrated["map"])
            canonical = migrated["map"]["canonical"]
            self.assertEqual(canonical["grid"]["cols"], 9)
            self.assertEqual(canonical["grid"]["rows"], 7)
            self.assertEqual(canonical["token_positions"][0]["cid"], 1)
            self.assertEqual(canonical["terrain_cells"][0]["col"], 1)
            self.assertEqual(canonical["obstacles"][0]["col"], 4)
            self.assertIn("10", canonical["aoes"])

    def test_capture_canonical_map_state_preserves_canonical_only_layers(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            app = self._make_app(Path(tmpdir) / "battle.log")
            app._lan_grid_cols = 12
            app._lan_grid_rows = 10
            app._lan_positions = {1: (2, 3)}
            app._lan_obstacles = {(4, 4)}
            app._lan_rough_terrain = {(1, 1): {"color": "#aaa", "movement_type": "ground", "is_swim": False, "is_rough": True}}
            app._lan_aoes = {9: {"kind": "circle", "cx": 1.0, "cy": 1.0}}
            app._map_state = tracker_mod.MapState.from_dict(
                {
                    "grid": {"cols": 12, "rows": 10, "feet_per_square": 5},
                    "features": [{"id": "f1", "col": 5, "row": 5, "kind": "feature", "payload": {"name": "crate"}}],
                    "hazards": [{"id": "h1", "col": 6, "row": 6, "kind": "hazard", "payload": {"name": "fire"}}],
                    "structures": [
                        {
                            "id": "s1",
                            "kind": "structure",
                            "anchor_col": 7,
                            "anchor_row": 7,
                            "occupied_cells": [{"col": 7, "row": 7}],
                            "payload": {"name": "wall"},
                        }
                    ],
                    "elevation_cells": [{"col": 8, "row": 8, "elevation": 10}],
                }
            )

            captured = app._capture_canonical_map_state(prefer_window=False).to_dict()
            self.assertEqual(captured["token_positions"][0]["cid"], 1)
            self.assertEqual(captured["features"][0]["id"], "f1")
            self.assertEqual(captured["hazards"][0]["id"], "h1")
            self.assertEqual(captured["structures"][0]["id"], "s1")
            self.assertEqual(captured["elevation_cells"][0]["col"], 8)

    def test_environment_event_destroy_feature_spawns_fire_hazard(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            app = self._make_app(Path(tmpdir) / "battle.log")
            app._map_state = tracker_mod.MapState.from_dict(
                {
                    "grid": {"cols": 12, "rows": 12, "feet_per_square": 5},
                    "features": [
                        {
                            "id": "f_powder",
                            "col": 3,
                            "row": 4,
                            "kind": "powder_barrel",
                            "payload": {"flammable": True},
                        }
                    ],
                    "hazards": [],
                }
            )
            result = app._resolve_map_environment_event({"type": "destroy_feature", "feature_id": "f_powder"})
            self.assertTrue(result.get("ok"))
            state = app._capture_canonical_map_state(prefer_window=False).to_dict()
            self.assertEqual(state["features"], [])
            self.assertEqual(state["hazards"][0]["kind"], "fire")

    def test_move_structure_moves_attached_feature_and_token(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            app = self._make_app(Path(tmpdir) / "battle.log")
            app._map_state = tracker_mod.MapState.from_dict(
                {
                    "grid": {"cols": 20, "rows": 20, "feet_per_square": 5},
                    "token_positions": [{"cid": 1, "col": 5, "row": 5}],
                    "structures": [
                        {
                            "id": "ship_1",
                            "kind": "ship_hull",
                            "anchor_col": 5,
                            "anchor_row": 5,
                            "occupied_cells": [{"col": 5, "row": 5}, {"col": 6, "row": 5}],
                            "payload": {},
                        }
                    ],
                    "features": [
                        {
                            "id": "f_mast",
                            "col": 6,
                            "row": 5,
                            "kind": "mast",
                            "payload": {"attached_structure_id": "ship_1"},
                        }
                    ],
                }
            )
            app._lan_positions = {1: (5, 5)}
            moved = app._move_map_structure("ship_1", 2, 0)
            self.assertTrue(moved)
            state = app._capture_canonical_map_state(prefer_window=False).to_dict()
            self.assertEqual(state["structures"][0]["anchor_col"], 7)
            self.assertEqual(state["features"][0]["col"], 8)
            self.assertEqual(state["token_positions"][0]["col"], 7)

    def test_move_structure_rejects_conflicting_cells(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            app = self._make_app(Path(tmpdir) / "battle.log")
            app._map_state = tracker_mod.MapState.from_dict(
                {
                    "grid": {"cols": 20, "rows": 20, "feet_per_square": 5},
                    "structures": [
                        {
                            "id": "ship_1",
                            "kind": "ship_hull",
                            "anchor_col": 5,
                            "anchor_row": 5,
                            "occupied_cells": [{"col": 5, "row": 5}, {"col": 6, "row": 5}],
                            "payload": {},
                        },
                        {
                            "id": "ship_2",
                            "kind": "ship_hull",
                            "anchor_col": 8,
                            "anchor_row": 5,
                            "occupied_cells": [{"col": 8, "row": 5}],
                            "payload": {},
                        },
                    ],
                    "features": [
                        {
                            "id": "f_wall",
                            "col": 7,
                            "row": 5,
                            "kind": "wall",
                            "payload": {"blocks_structure_movement": True},
                        }
                    ],
                }
            )
            moved = app._move_map_structure("ship_1", 2, 0)
            self.assertFalse(moved)
            self.assertEqual(getattr(app, "_last_map_structure_move_error", ""), "blocked")
            blockers = getattr(app, "_last_map_structure_move_blockers", {})
            self.assertTrue((blockers.get("blockers") or {}).get("features"))

    def test_environment_tick_reports_ignitions_and_expiry(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            app = self._make_app(Path(tmpdir) / "battle.log")
            app._map_state = tracker_mod.MapState.from_dict(
                {
                    "grid": {"cols": 12, "rows": 12, "feet_per_square": 5},
                    "features": [
                        {
                            "id": "f_mast",
                            "col": 5,
                            "row": 5,
                            "kind": "mast",
                            "payload": {"flammable": True, "on_ignite_spawn_hazard": {"kind": "fire", "payload": {"duration_turns": 2}}},
                        }
                    ],
                    "hazards": [
                        {
                            "id": "h_fire",
                            "col": 5,
                            "row": 4,
                            "kind": "fire",
                            "payload": {"duration_turns": 1, "remaining_turns": 1},
                        }
                    ],
                }
            )
            result = app._resolve_map_environment_event({"type": "tick_hazards"})
            self.assertTrue(result.get("ok"))
            self.assertTrue(result.get("expired_hazard_ids"))
            self.assertTrue(result.get("ignited_feature_ids"))
            state = app._capture_canonical_map_state(prefer_window=False).to_dict()
            self.assertTrue(any((item.get("payload") or {}).get("ignited") for item in state["features"]))

    def test_extinguish_hazard_by_cell(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            app = self._make_app(Path(tmpdir) / "battle.log")
            app._map_state = tracker_mod.MapState.from_dict(
                {
                    "grid": {"cols": 8, "rows": 8, "feet_per_square": 5},
                    "hazards": [
                        {"id": "h1", "col": 3, "row": 3, "kind": "fire", "payload": {"tags": ["fire"]}},
                        {"id": "h2", "col": 3, "row": 3, "kind": "smoke", "payload": {"tags": ["smoke"]}},
                    ],
                }
            )
            result = app._resolve_map_environment_event({"type": "extinguish_hazard", "col": 3, "row": 3, "tags": ["fire"]})
            self.assertTrue(result.get("ok"))
            self.assertEqual(result.get("removed_hazard_count"), 1)
            state = app._capture_canonical_map_state(prefer_window=False).to_dict()
            self.assertEqual(len(state["hazards"]), 1)

    def test_structure_template_validation_and_rotation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            app = self._make_app(Path(tmpdir) / "battle.log")
            app._map_state = tracker_mod.MapState.from_dict({"grid": {"cols": 20, "rows": 20, "feet_per_square": 5}})
            app._save_structure_template(
                "ship_alpha",
                {
                    "name": "Ship Alpha",
                    "kind": "ship_hull",
                    "footprint": [{"col": 0, "row": 0}, {"col": 1, "row": 0}],
                    "features": [{"col": 1, "row": 0, "kind": "mast", "name": "Mast", "tags": ["climbable"]}],
                },
            )
            created = app._instantiate_structure_template("ship_alpha", anchor_col=10, anchor_row=10, facing_deg=90)
            self.assertTrue(created)
            state = app._capture_canonical_map_state(prefer_window=False).to_dict()
            structure = next(item for item in state["structures"] if item["id"] == created)
            occupied = {(entry["col"], entry["row"]) for entry in structure["occupied_cells"]}
            self.assertIn((10, 10), occupied)
            self.assertIn((10, 11), occupied)

    def test_structure_template_rejects_attached_feature_blocking_feature_and_is_atomic(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            app = self._make_app(Path(tmpdir) / "battle.log")
            app._map_state = tracker_mod.MapState.from_dict(
                {
                    "grid": {"cols": 20, "rows": 20, "feet_per_square": 5},
                    "features": [
                        {"id": "f_wall", "col": 11, "row": 10, "kind": "wall", "payload": {"blocks_movement": True}},
                    ],
                }
            )
            app._save_structure_template(
                "ship_alpha",
                {
                    "name": "Ship Alpha",
                    "kind": "ship_hull",
                    "footprint": [{"col": 0, "row": 0}],
                    "features": [{"col": 1, "row": 0, "kind": "mast", "name": "Mast"}],
                },
            )
            created = app._instantiate_structure_template("ship_alpha", anchor_col=10, anchor_row=10)
            self.assertIsNone(created)
            self.assertEqual(getattr(app, "_last_map_template_error", ""), "template_conflict")
            blockers = getattr(app, "_last_map_template_blockers", {})
            self.assertTrue((blockers.get("blockers") or {}).get("features"))
            state = app._capture_canonical_map_state(prefer_window=False).to_dict()
            self.assertEqual(len(state["structures"]), 0)
            self.assertEqual(len([entry for entry in state["features"] if (entry.get("payload") or {}).get("attached_structure_id")]), 0)

    def test_structure_template_rejects_attached_feature_on_existing_structure_cell(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            app = self._make_app(Path(tmpdir) / "battle.log")
            app._map_state = tracker_mod.MapState.from_dict(
                {
                    "grid": {"cols": 20, "rows": 20, "feet_per_square": 5},
                    "structures": [
                        {
                            "id": "dock",
                            "kind": "dock",
                            "anchor_col": 11,
                            "anchor_row": 10,
                            "occupied_cells": [{"col": 11, "row": 10}],
                            "payload": {"blocks_movement": True},
                        }
                    ],
                }
            )
            app._save_structure_template(
                "ship_alpha",
                {
                    "name": "Ship Alpha",
                    "kind": "ship_hull",
                    "footprint": [{"col": 0, "row": 0}],
                    "features": [{"col": 1, "row": 0, "kind": "mast", "name": "Mast"}],
                },
            )
            created = app._instantiate_structure_template("ship_alpha", anchor_col=10, anchor_row=10)
            self.assertIsNone(created)
            blockers = getattr(app, "_last_map_template_blockers", {})
            self.assertTrue((blockers.get("blockers") or {}).get("structures"))

    def test_structure_template_rejects_attached_feature_on_generic_blocking_hazard(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            app = self._make_app(Path(tmpdir) / "battle.log")
            app._map_state = tracker_mod.MapState.from_dict(
                {
                    "grid": {"cols": 20, "rows": 20, "feet_per_square": 5},
                    "hazards": [
                        {"id": "h_fire", "col": 11, "row": 10, "kind": "fire", "payload": {"blocks_movement": True}},
                    ],
                }
            )
            app._save_structure_template(
                "ship_alpha",
                {
                    "name": "Ship Alpha",
                    "kind": "ship_hull",
                    "footprint": [{"col": 0, "row": 0}],
                    "features": [{"col": 1, "row": 0, "kind": "mast", "name": "Mast"}],
                },
            )
            created = app._instantiate_structure_template("ship_alpha", anchor_col=10, anchor_row=10)
            self.assertIsNone(created)
            blockers = getattr(app, "_last_map_template_blockers", {})
            self.assertTrue((blockers.get("blockers") or {}).get("hazards"))

    def test_structure_contact_semantics_reports_boardable_adjacency(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            app = self._make_app(Path(tmpdir) / "battle.log")
            app._map_state = tracker_mod.MapState.from_dict(
                {
                    "grid": {"cols": 20, "rows": 20, "feet_per_square": 5},
                    "structures": [
                        {
                            "id": "a",
                            "kind": "ship_hull",
                            "anchor_col": 5,
                            "anchor_row": 5,
                            "occupied_cells": [{"col": 5, "row": 5}, {"col": 6, "row": 5}],
                            "payload": {"boardable": True},
                        },
                        {
                            "id": "b",
                            "kind": "ship_hull",
                            "anchor_col": 7,
                            "anchor_row": 5,
                            "occupied_cells": [{"col": 7, "row": 5}],
                            "payload": {"allow_boarding": True},
                        },
                    ],
                }
            )
            semantics = app._structure_contact_semantics("a")
            self.assertTrue(semantics.get("ok"))
            self.assertEqual(semantics.get("boardable_structure_ids"), ["b"])

    def test_ship_blueprint_normalization_and_instantiation_creates_runtime_ship_instance(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            app = self._make_app(Path(tmpdir) / "battle.log")
            app._map_state = tracker_mod.MapState.from_dict({"grid": {"cols": 24, "rows": 24, "feet_per_square": 5}})
            app._save_ship_blueprint(
                "test_sloop",
                {
                    "name": "Test Sloop",
                    "kind": "ship_hull",
                    "footprint": [{"col": 0, "row": 0}, {"col": 1, "row": 0}, {"col": 2, "row": 0}],
                    "fixtures": [{"id": "mast_main", "name": "Mast", "kind": "mast", "col": 1, "row": 0, "tags": ["ship_fixture"]}],
                    "components": [{"id": "hull", "name": "Hull", "type": "hull", "max_hp": 200, "ac": 15}],
                    "mounted_weapons": [{"id": "port_cannon", "name": "Port Cannon", "weapon_type": "cannon", "arc": "port", "col": 0, "row": 0}],
                    "boarding": {
                        "boardable": True,
                        "edges": ["port", "starboard", "fore", "aft"],
                        "points": [{"id": "rail", "col": 2, "row": 0}],
                        "bridges": [{"id": "bridge_a", "col": 1, "row": 0, "kind": "gangplank"}],
                    },
                    "decks": [{"id": "main", "name": "Main Deck", "elevation_offset": 0}],
                },
            )
            blueprints = app._ship_blueprints()
            self.assertIn("test_sloop", blueprints)
            created = app._instantiate_ship_blueprint("test_sloop", anchor_col=10, anchor_row=10, facing_deg=90, name="Sea Ghost")
            self.assertTrue(created)
            state = app._capture_canonical_map_state(prefer_window=False).to_dict()
            structure = next(item for item in state["structures"] if item["id"] == created)
            payload = structure.get("payload") or {}
            self.assertEqual(payload.get("ship_blueprint_id"), "test_sloop")
            self.assertEqual(payload.get("name"), "Sea Ghost")
            presentation = state.get("presentation") or {}
            ship_instances = presentation.get("ship_instances") or {}
            self.assertTrue(ship_instances)
            ship = next(iter(ship_instances.values()))
            self.assertEqual(ship.get("parent_structure_id"), created)
            self.assertEqual(ship.get("blueprint_id"), "test_sloop")
            self.assertEqual(ship.get("name"), "Sea Ghost")
            self.assertEqual((payload.get("boarding_points") or [])[0]["col"], 10)
            self.assertEqual((payload.get("boarding_points") or [])[0]["row"], 12)
            self.assertIn("east", payload.get("boardable_edges") or [])
            self.assertIn("south", payload.get("boardable_edges") or [])
            self.assertEqual((payload.get("boarding_bridges") or [])[0]["col"], 10)
            self.assertEqual((payload.get("boarding_bridges") or [])[0]["row"], 11)
            self.assertEqual((ship.get("boarding") or {}).get("rotation_steps"), 1)
            self.assertEqual(((ship.get("boarding") or {}).get("points") or [])[0]["col"], 10)
            self.assertEqual(((ship.get("boarding") or {}).get("points") or [])[0]["row"], 12)

    def test_default_starter_ship_blueprints_instantiate_on_empty_map(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            app = self._make_app(Path(tmpdir) / "battle.log")
            app._map_state = tracker_mod.MapState.from_dict({"grid": {"cols": 80, "rows": 80, "feet_per_square": 5}})
            app._lan_grid_cols = 80
            app._lan_grid_rows = 80
            starters = ("rowboat_launch", "sloop", "brig", "galleon_heavy")
            for index, blueprint_id in enumerate(starters):
                created = app._instantiate_ship_blueprint(
                    blueprint_id,
                    anchor_col=5 + index * 12,
                    anchor_row=10,
                    facing_deg=0,
                )
                self.assertIsNotNone(created, msg=f"{blueprint_id} failed with {getattr(app, '_last_map_template_error', '')}")

    def test_ship_boarding_metadata_transforms_for_multiple_facings(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            app = self._make_app(Path(tmpdir) / "battle.log")
            app._map_state = tracker_mod.MapState.from_dict({"grid": {"cols": 40, "rows": 40, "feet_per_square": 5}})
            app._lan_grid_cols = 40
            app._lan_grid_rows = 40
            created_180 = app._instantiate_ship_blueprint("rowboat_launch", anchor_col=15, anchor_row=15, facing_deg=180)
            created_270 = app._instantiate_ship_blueprint("rowboat_launch", anchor_col=20, anchor_row=20, facing_deg=270)
            self.assertIsNotNone(created_180)
            self.assertIsNotNone(created_270)
            state = app._capture_canonical_map_state(prefer_window=False).to_dict()
            structure_180 = next(item for item in state["structures"] if item["id"] == created_180)
            structure_270 = next(item for item in state["structures"] if item["id"] == created_270)
            points_180 = (structure_180.get("payload") or {}).get("boarding_points") or []
            points_270 = (structure_270.get("payload") or {}).get("boarding_points") or []
            self.assertIn({"id": "starboard_mid", "name": "Starboard Rail", "col": 14, "row": 15, "tags": [], "local_col": 1, "local_row": 0}, points_180)
            self.assertIn({"id": "starboard_mid", "name": "Starboard Rail", "col": 20, "row": 19, "tags": [], "local_col": 1, "local_row": 0}, points_270)

    def test_ship_contacts_use_world_transformed_boarding_points(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            app = self._make_app(Path(tmpdir) / "battle.log")
            app._map_state = tracker_mod.MapState.from_dict({"grid": {"cols": 30, "rows": 30, "feet_per_square": 5}})
            app._lan_grid_cols = 30
            app._lan_grid_rows = 30
            src = app._instantiate_ship_blueprint("rowboat_launch", anchor_col=10, anchor_row=10, facing_deg=90)
            dst = app._instantiate_ship_blueprint("rowboat_launch", anchor_col=11, anchor_row=10, facing_deg=0)
            self.assertIsNotNone(src)
            self.assertIsNotNone(dst)
            semantics = app._structure_contact_semantics(src)
            self.assertTrue(semantics.get("ok"))
            ship_relations = semantics.get("ship_relations") if isinstance(semantics.get("ship_relations"), list) else []
            relation = next((item for item in ship_relations if str(item.get("target_id") or "") == str(dst)), {})
            self.assertTrue(relation.get("boarding_capable"))
            self.assertIn({"col": 10, "row": 10}, relation.get("boarding_points") or [])

    def test_ship_blueprints_coexist_with_structure_templates(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            app = self._make_app(Path(tmpdir) / "battle.log")
            app._map_state = tracker_mod.MapState.from_dict({"grid": {"cols": 20, "rows": 20, "feet_per_square": 5}})
            app._save_structure_template(
                "legacy_ship",
                {
                    "name": "Legacy Ship",
                    "kind": "ship_hull",
                    "footprint": [{"col": 0, "row": 0}, {"col": 1, "row": 0}],
                    "features": [],
                },
            )
            app._save_ship_blueprint(
                "new_ship",
                {
                    "name": "New Ship",
                    "kind": "ship_hull",
                    "footprint": [{"col": 0, "row": 0}],
                    "fixtures": [],
                    "components": [{"id": "hull", "name": "Hull", "type": "hull"}],
                    "mounted_weapons": [],
                    "boarding": {"boardable": True, "edges": ["port"], "points": []},
                },
            )
            templates = app._structure_templates()
            blueprints = app._ship_blueprints()
            self.assertIn("legacy_ship", templates)
            self.assertIn("legacy_ship", blueprints)
            self.assertIn("new_ship", blueprints)

    def test_migrate_schema_v2_sparse_legacy_map_payload_is_hardened(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            app = self._make_app(Path(tmpdir) / "battle.log")
            payload = {
                "schema_version": 2,
                "combat": {},
                "map": {
                    "grid": {"cols": 9, "rows": 7, "feet_per_square": 5},
                    "positions": {"1": [2, 3]},
                    "obstacles": [[4, 5], {"col": 1, "row": 1}],
                    "rough_terrain": {"3,4": {"color": "#fff", "movement_type": "ground", "is_swim": False, "is_rough": True}},
                    "aoes": [{"aid": 10, "kind": "circle", "cx": 1.0, "cy": 1.0}, {"aid": "bad"}],
                },
                "log": {"lines": []},
            }

            migrated = app._migrate_session_snapshot_payload(payload)
            canonical = migrated["map"]["canonical"]
            self.assertEqual(canonical["grid"]["cols"], 9)
            self.assertEqual(canonical["token_positions"][0]["cid"], 1)
            self.assertIn({"col": 4, "row": 5}, canonical["obstacles"])
            self.assertEqual(canonical["terrain_cells"][0]["col"], 3)
            self.assertIn("10", canonical["aoes"])


if __name__ == "__main__":
    unittest.main()
