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
            map_structures={"ship_a": {"id": "ship_a", "kind": "ship_hull", "payload": {"ship_instance_id": "ship_1"}}},
            _is_ship_structure_payload=lambda structure: helper_mod.BattleMapWindow._is_ship_structure_payload(structure),
            _active_map_interaction_mode=lambda: "ship",
        )
        helper._selected_ship_for_boarding_action = lambda: helper_mod.BattleMapWindow._selected_ship_for_boarding_action(helper)
        helper._selected_ship_command_available = lambda: helper_mod.BattleMapWindow._selected_ship_command_available(helper)
        sid = helper_mod.BattleMapWindow._selected_ship_for_boarding_action(helper)
        self.assertEqual(sid, "ship_a")
        self.assertTrue(helper_mod.BattleMapWindow._selected_ship_command_available(helper))
        helper._active_map_interaction_mode = lambda: "select"
        self.assertFalse(helper_mod.BattleMapWindow._selected_ship_command_available(helper))
        helper._active_map_interaction_mode = lambda: "ship"
        helper.map_structures["ship_a"] = {"id": "ship_a", "kind": "dock", "payload": {}}
        self.assertFalse(helper_mod.BattleMapWindow._selected_ship_command_available(helper))
        helper._map_author_selected_cell = None
        self.assertFalse(helper_mod.BattleMapWindow._selected_ship_command_available(helper))

    def test_refresh_tactical_palette_state_uses_mode_aware_status_copy(self):
        helper = types.SimpleNamespace(
            map_author_tool_var=_Var("select"),
            map_place_source_var=_Var("tactical"),
            map_author_active_status_var=_Var(""),
            map_author_elevation_var=_Var("0"),
            rough_mode_var=_Var(False),
            obstacle_mode_var=_Var(False),
            _active_map_interaction_mode=lambda: helper_mod.MAP_INTERACTION_MODE_MEASURE,
            _selected_tactical_preset_id=lambda: "",
            _selected_tactical_preset=lambda: {},
        )
        helper_mod.BattleMapWindow._refresh_tactical_palette_state(
            helper,
            normalized={"category": "feature", "display_name": "Crate"},
        )
        self.assertIn("Measure", helper.map_author_active_status_var.get())
        self.assertIn("Click two points", helper.map_author_active_status_var.get())

        helper._active_map_interaction_mode = lambda: helper_mod.MAP_INTERACTION_MODE_SHIP
        helper_mod.BattleMapWindow._refresh_tactical_palette_state(
            helper,
            normalized={"category": "feature", "display_name": "Crate"},
        )
        self.assertIn("Ship Command", helper.map_author_active_status_var.get())
        self.assertIn("right-click cancels", helper.map_author_active_status_var.get())

        helper._active_map_interaction_mode = lambda: helper_mod.MAP_INTERACTION_MODE_PLACE
        helper.map_author_tool_var.set("stamp")
        helper.map_place_source_var.set("tactical")
        helper_mod.BattleMapWindow._refresh_tactical_palette_state(
            helper,
            normalized={"category": "feature", "display_name": "Crate"},
        )
        self.assertIn("right-click/Esc to Select", helper.map_author_active_status_var.get())


if __name__ == "__main__":
    unittest.main()
