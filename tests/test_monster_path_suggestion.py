import types
import unittest

import helper_script as helper_mod
from map_state import MapState


class _Var:
    def __init__(self, value):
        self._value = value

    def get(self):
        return self._value

    def set(self, value):
        self._value = value


class _Button:
    def configure(self, **_kwargs):
        return None


def _c(cid, name, hp=30, *, ally=False, is_pc=False):
    c = helper_mod.Combatant(
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
    c.max_hp = hp
    c.move_total = 30
    c.action_remaining = 1
    c.condition_stacks = []
    return c


class MonsterPathSuggestionTests(unittest.TestCase):
    def _make_window(self, *, move_remaining=15):
        monster = _c(1, "Ogre", ally=False, is_pc=False)
        monster.move_remaining = move_remaining
        hero = _c(2, "Hero", ally=True, is_pc=True)
        logs = []
        broadcasts = []
        app = types.SimpleNamespace(
            combatants={1: monster, 2: hero},
            round_num=1,
            turn_num=1,
            _mode_speed=lambda c: int(getattr(c, "speed", 30) or 30),
            _capture_canonical_map_state=lambda prefer_window=True: MapState.from_legacy(cols=12, rows=12),
            _movement_cost_multiplier_for_step=lambda *args, **kwargs: 1.0,
            _normalize_movement_mode=lambda value: "normal" if not isinstance(value, str) else value.strip().lower() or "normal",
            _water_movement_multiplier=lambda c, mode: 1.0,
            _log=lambda message, cid=None: logs.append((cid, str(message))),
            _rebuild_table=lambda scroll_to_current=True: None,
            _has_condition=lambda c, cond: False,
            _set_movement_mode=lambda cid, mode: setattr(app.combatants[int(cid)], "movement_mode", mode),
            _sneak_handle_hidden_movement=lambda *args, **kwargs: None,
            _lan_force_state_broadcast=lambda: broadcasts.append(True),
        )

        window = object.__new__(helper_mod.BattleMapWindow)
        window.app = app
        window.cols = 12
        window.rows = 12
        window.feet_per_square = 5
        window.obstacles = set()
        window.rough_terrain = {}
        window.unit_tokens = {1: {"col": 0, "row": 0}, 2: {"col": 4, "row": 0}}
        window._active_cid = 1
        window.monster_auto_path_var = _Var(False)
        window.map_monster_path_status_var = _Var("")
        window._monster_path_suggest_button = _Button()
        window._monster_path_approve_button = _Button()
        window._monster_path_reject_button = _Button()
        window._monster_path_suggestion = None
        window._monster_path_rejected_turn_marker = None
        window.refresh_units = lambda: None
        window._update_groups = lambda: None
        window._update_move_highlight = lambda: None
        window._update_included_for_selected = lambda: None
        window._redraw_tactical_layers = lambda: None
        window._sync_mount_pair_position = lambda cid, col, row: None
        window.logs = logs
        window.broadcasts = broadcasts
        return window

    def test_build_monster_path_suggestion_reaches_melee_without_dash(self):
        window = self._make_window(move_remaining=15)
        suggestion = window._build_monster_path_suggestion(1)
        self.assertIsNotNone(suggestion)
        self.assertEqual(suggestion["destination"], (3, 0))
        self.assertFalse(suggestion["requires_dash"])
        self.assertEqual(suggestion["cost"], 15)
        self.assertEqual(suggestion["path_cells"], [(0, 0), (1, 0), (2, 0), (3, 0)])

    def test_build_monster_path_suggestion_uses_dash_budget_when_better(self):
        window = self._make_window(move_remaining=5)
        suggestion = window._build_monster_path_suggestion(1)
        self.assertIsNotNone(suggestion)
        self.assertEqual(suggestion["destination"], (3, 0))
        self.assertTrue(suggestion["requires_dash"])
        self.assertEqual(suggestion["cost"], 15)

    def test_reject_suppresses_auto_suggestion_until_turn_changes(self):
        window = self._make_window(move_remaining=15)
        window.monster_auto_path_var.set(True)
        window._update_monster_path_suggestion(force=False, redraw=False)
        self.assertIsNotNone(window._monster_path_suggestion)

        window._reject_monster_path_suggestion()
        self.assertIsNone(window._monster_path_suggestion)

        window._update_monster_path_suggestion(force=False, redraw=False)
        self.assertIsNone(window._monster_path_suggestion)

        window.app.turn_num = 2
        window._update_monster_path_suggestion(force=False, redraw=False)
        self.assertIsNotNone(window._monster_path_suggestion)

    def test_approve_applies_destination_and_consumes_dash_budget(self):
        window = self._make_window(move_remaining=5)
        window._update_monster_path_suggestion(force=True, redraw=False)
        self.assertIsNotNone(window._monster_path_suggestion)

        window._approve_monster_path_suggestion()

        self.assertEqual((window.unit_tokens[1]["col"], window.unit_tokens[1]["row"]), (3, 0))
        self.assertEqual(window.app.combatants[1].move_remaining, 20)
        self.assertTrue(any("follows the suggested path" in message for _cid, message in window.logs))
        self.assertEqual(window.broadcasts, [True])


if __name__ == "__main__":
    unittest.main()
