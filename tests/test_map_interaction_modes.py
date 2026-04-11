import types
import unittest

import helper_script as helper_mod


class _Var:
    def __init__(self, value=""):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class MapInteractionModeTests(unittest.TestCase):
    def test_normalize_map_interaction_mode_defaults_to_select(self):
        self.assertEqual(helper_mod._normalize_map_interaction_mode("place"), "place")
        self.assertEqual(helper_mod._normalize_map_interaction_mode("ship"), "ship")
        self.assertEqual(helper_mod._normalize_map_interaction_mode("unknown"), "select")

    def test_sync_map_author_tool_from_mode_maps_place_and_erase(self):
        helper = types.SimpleNamespace(
            map_interaction_mode_var=_Var("place"),
            map_author_tool_var=_Var("select"),
            _refresh_tactical_palette_state=lambda: None,
            _refresh_selected_ship_command_surface=lambda: None,
        )
        helper._active_map_interaction_mode = lambda: helper_mod.BattleMapWindow._active_map_interaction_mode(helper)
        helper_mod.BattleMapWindow._sync_map_author_tool_from_mode(helper)
        self.assertEqual(helper.map_author_tool_var.get(), "stamp")
        helper.map_interaction_mode_var.set("erase")
        helper_mod.BattleMapWindow._sync_map_author_tool_from_mode(helper)
        self.assertEqual(helper.map_author_tool_var.get(), "erase")

    def test_selected_ship_command_available_requires_selected_ship(self):
        helper = types.SimpleNamespace(
            _map_author_selected_cell=(2, 3),
            _selected_structure_id_at_cell=lambda _col, _row: "ship_a",
        )
        helper._selected_ship_for_boarding_action = lambda: helper_mod.BattleMapWindow._selected_ship_for_boarding_action(helper)
        sid = helper_mod.BattleMapWindow._selected_ship_for_boarding_action(helper)
        self.assertEqual(sid, "ship_a")
        self.assertTrue(helper_mod.BattleMapWindow._selected_ship_command_available(helper))
        helper._map_author_selected_cell = None
        self.assertFalse(helper_mod.BattleMapWindow._selected_ship_command_available(helper))


if __name__ == "__main__":
    unittest.main()
