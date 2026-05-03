import unittest
from unittest import mock

import dnd_initative_tracker as tracker_mod


def _make_app(positions=None, grid=(20, 20), obstacles=None, feet_per_square=5.0):
    app = object.__new__(tracker_mod.InitiativeTracker)
    dragon = mock.Mock(cid=1, is_pc=False, ally=False, hp=180, max_hp=256, ac=19, speed=40,
                       swim_speed=0, fly_speed=80)
    dragon.name = "Dragon"
    hero = mock.Mock(cid=2, is_pc=True, ally=False, hp=80, max_hp=80, ac=16, speed=30,
                     swim_speed=0, fly_speed=0)
    hero.name = "Hero"
    goblin = mock.Mock(cid=3, is_pc=False, ally=False, hp=7, max_hp=7, ac=13, speed=30,
                       swim_speed=0, fly_speed=0)
    goblin.name = "Goblin"
    app.__dict__.update({
        "combatants": {1: dragon, 2: hero, 3: goblin},
        "_name_role_memory": {"Dragon": "enemy", "Hero": "pc", "Goblin": "enemy"},
        "_lan_grid_cols": int(grid[0]),
        "_lan_grid_rows": int(grid[1]),
        "_lan_positions": dict(positions or {}),
    })
    cols, rows = int(grid[0]), int(grid[1])
    obs = set(obstacles or set())
    app._lan_live_map_data = lambda: (cols, rows, obs, {}, dict(app._lan_positions))
    app._lan_feet_per_square = lambda: float(feet_per_square)
    app.broadcast_calls = 0

    def _set_pos(cid, col, row):
        app._lan_positions[int(cid)] = (int(col), int(row))

    app._lan_set_token_position = _set_pos

    def _broadcast():
        app.broadcast_calls += 1

    app._lan_force_state_broadcast = _broadcast
    app._lan_marks_for = lambda c: ""
    return app


class TestDmMonsterPilotSummary(unittest.TestCase):
    def test_returns_active_non_pc_combatants(self):
        app = _make_app(positions={1: (5, 6), 3: (10, 12)})
        result = app._dm_monster_pilot_summary()
        self.assertTrue(result["ok"])
        cids = [m["cid"] for m in result["monsters"]]
        self.assertIn(1, cids)
        self.assertIn(3, cids)
        self.assertNotIn(2, cids)
        dragon = next(m for m in result["monsters"] if m["cid"] == 1)
        self.assertEqual(dragon["name"], "Dragon")
        self.assertEqual(dragon["max_hp"], 256)
        self.assertEqual(dragon["ac"], 19)
        self.assertEqual(dragon["position"], {"x": 5, "y": 6})
        self.assertEqual(result["grid"], {"cols": 20, "rows": 20})


class TestDmMonsterPilotMove(unittest.TestCase):
    def test_rejects_missing_combatant(self):
        app = _make_app()
        result = app._dm_monster_pilot_move(cid=999, payload={"x": 1, "y": 2})
        self.assertFalse(result["ok"])
        self.assertIn("999", result["error"])

    def test_rejects_invalid_coordinates(self):
        app = _make_app()
        result = app._dm_monster_pilot_move(cid=1, payload={"x": "nope", "y": 2})
        self.assertFalse(result["ok"])
        self.assertIn("integer", result["error"].lower())

    def test_rejects_out_of_bounds(self):
        app = _make_app(grid=(10, 10))
        result = app._dm_monster_pilot_move(cid=1, payload={"x": 99, "y": 1})
        self.assertFalse(result["ok"])
        self.assertIn("bounds", result["error"].lower())

    def test_rejects_pc_target(self):
        app = _make_app()
        result = app._dm_monster_pilot_move(cid=2, payload={"x": 1, "y": 2})
        self.assertFalse(result["ok"])
        self.assertIn("non-PC", result["error"])

    def test_normal_move_succeeds_on_clear_cell(self):
        app = _make_app(positions={1: (5, 6)})
        result = app._dm_monster_pilot_move(cid=1, payload={"x": 6, "y": 6})
        self.assertTrue(result["ok"])
        self.assertEqual(result["mode"], "normal")
        self.assertEqual(result["previous_position"], {"x": 5, "y": 6})
        self.assertEqual(result["new_position"], {"x": 6, "y": 6})
        self.assertEqual(app._lan_positions[1], (6, 6))
        self.assertEqual(app.broadcast_calls, 1)
        self.assertEqual(result["warnings"], [])

    def test_normal_move_rejects_obstacle(self):
        app = _make_app(positions={1: (5, 6)}, obstacles={(8, 9)})
        result = app._dm_monster_pilot_move(cid=1, payload={"x": 8, "y": 9})
        self.assertFalse(result["ok"])
        self.assertEqual(result.get("blocked"), "obstacle")
        # Position is unchanged.
        self.assertEqual(app._lan_positions[1], (5, 6))
        self.assertEqual(app.broadcast_calls, 0)

    def test_normal_move_rejects_occupied(self):
        app = _make_app(positions={1: (5, 6), 3: (8, 9)})
        result = app._dm_monster_pilot_move(cid=1, payload={"x": 8, "y": 9})
        self.assertFalse(result["ok"])
        self.assertEqual(result.get("blocked"), "occupied")
        self.assertIn("Goblin", result["error"])
        self.assertEqual(app._lan_positions[1], (5, 6))

    def test_force_move_allows_obstacle_with_warning(self):
        app = _make_app(positions={1: (5, 6)}, obstacles={(8, 9)})
        result = app._dm_monster_pilot_move(cid=1, payload={"x": 8, "y": 9, "mode": "force"})
        self.assertTrue(result["ok"])
        self.assertEqual(result["mode"], "force")
        self.assertTrue(any("obstacle" in w.lower() for w in result["warnings"]))
        self.assertEqual(app._lan_positions[1], (8, 9))

    def test_force_move_allows_occupied_with_warning(self):
        app = _make_app(positions={1: (5, 6), 3: (8, 9)})
        result = app._dm_monster_pilot_move(cid=1, payload={"x": 8, "y": 9, "mode": "force"})
        self.assertTrue(result["ok"])
        self.assertTrue(any("occup" in w.lower() for w in result["warnings"]))
        self.assertEqual(app._lan_positions[1], (8, 9))

    def test_long_move_returns_speed_warning(self):
        # Dragon speed 40, 5ft/sq → max 8 squares (chebyshev). 15-square move = 75ft.
        app = _make_app(positions={1: (0, 0)})
        result = app._dm_monster_pilot_move(cid=1, payload={"x": 15, "y": 0})
        self.assertTrue(result["ok"])
        self.assertEqual(result["speed_ft"], 40)
        self.assertEqual(result["distance_ft"], 75.0)
        self.assertTrue(any("exceeds_speed" in w for w in result["warnings"]))

    def test_short_move_no_speed_warning(self):
        app = _make_app(positions={1: (0, 0)})
        # Dragon speed 40 → 8 squares max. Move 8 squares chebyshev = 40ft, OK.
        result = app._dm_monster_pilot_move(cid=1, payload={"x": 8, "y": 5})
        self.assertTrue(result["ok"])
        self.assertEqual(result["distance_ft"], 40.0)
        self.assertFalse(any("exceeds_speed" in w for w in result["warnings"]))


class TestDmMonsterPilotAssetHooks(unittest.TestCase):
    def test_dm_index_html_contains_pilot_hooks(self):
        from pathlib import Path
        html = Path("assets/web/dm/index.html").read_text(encoding="utf-8")
        self.assertIn("Monster Pilot", html)
        self.assertIn("monsterPilotCidSelect", html)
        self.assertIn("monsterPilotMoveBtn", html)
        self.assertIn("/api/dm/monster-pilot/", html)
        # Hardening surface: UI offers a force-mode toggle/checkbox.
        self.assertIn("monsterPilotForceModeInput", html)
    
    def test_dm_index_html_contains_map_cell_integration(self):
        """Verify map-to-pilot movement integration hooks exist."""
        from pathlib import Path
        html = Path("assets/web/dm/index.html").read_text(encoding="utf-8")
        # "Use map cell" button should be present
        self.assertIn("monsterPilotUseSelectedCellBtn", html)
        self.assertIn("Use map cell", html)
        # "Move selected cell" button for faster flow
        self.assertIn("monsterPilotMoveSelectedCellBtn", html)
        self.assertIn("Move selected cell", html)
        # Canvas click handler should set tacticalSelection
        self.assertIn("tacticalSelection", html)
        self.assertIn("handleTacticalCanvasClick", html)
    
    def test_dm_index_html_endpoint_correct(self):
        """Verify the Monster Pilot endpoint string is correct."""
        from pathlib import Path
        html = Path("assets/web/dm/index.html").read_text(encoding="utf-8")
        # The JS should call the correct endpoint
        self.assertIn("/api/dm/monster-pilot/", html)
        self.assertIn("monsterPilotMoveAction", html)
        # Should handle both direct and map-based moves
        self.assertIn("tacticalSelection.col", html)
        self.assertIn("tacticalSelection.row", html)
    
    def test_dm_index_html_contains_drag_drop_hooks(self):
        """Verify drag-and-drop Monster Pilot hooks exist in HTML."""
        from pathlib import Path
        html = Path("assets/web/dm/index.html").read_text(encoding="utf-8")
        # Drag state management
        self.assertIn("monsterPilotDragState", html)
        self.assertIn("dragging", html)
        self.assertIn("sourceCid", html)
        self.assertIn("cancelled", html)
        # Drag functions
        self.assertIn("startMonsterPilotDrag", html)
        self.assertIn("onMonsterPilotDragMove", html)
        self.assertIn("endMonsterPilotDrag", html)
        self.assertIn("cancelMonsterPilotDrag", html)
        self.assertIn("executeMonsterPilotDragMove", html)
        # Event listeners
        self.assertIn("addEventListener('mousedown'", html)
        self.assertIn("addEventListener('mousemove'", html)
        self.assertIn("addEventListener('mouseup'", html)
        self.assertIn("addEventListener('keydown'", html)
        # Endpoint is reused
        self.assertIn("api/dm/monster-pilot/", html)
    
    def test_dm_index_html_drag_respects_force_mode(self):
        """Verify drag-and-drop uses force mode checkbox."""
        from pathlib import Path
        html = Path("assets/web/dm/index.html").read_text(encoding="utf-8")
        # Drag move delegates through the existing move action path.
        self.assertIn("await monsterPilotMoveAction()", html)
        # The shared move path should still read force mode and pass mode.
        self.assertIn("monsterPilotForceModeEnabled", html)
        self.assertIn("mode", html)
        self.assertIn("'force'", html)


if __name__ == "__main__":
    unittest.main()
