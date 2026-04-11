import unittest

import helper_script as helper_mod


class ShipCompositeRenderingTests(unittest.TestCase):
    def test_selection_prefers_ship_hull_when_cells_overlap(self):
        window = object.__new__(helper_mod.BattleMapWindow)
        window._structure_id_by_cell = {(5, 5): "dock_a"}
        window.map_structures = {
            "dock_a": {
                "id": "dock_a",
                "kind": "dock",
                "anchor_col": 5,
                "anchor_row": 5,
                "payload": {},
                "occupied_cells": [{"col": 5, "row": 5}],
            },
            "ship_a": {
                "id": "ship_a",
                "kind": "ship_hull",
                "anchor_col": 5,
                "anchor_row": 5,
                "payload": {"ship_instance_id": "ship_1"},
                "occupied_cells": [{"col": 5, "row": 5}, {"col": 6, "row": 5}],
            },
        }
        selected = window._selected_structure_id_at_cell(5, 5)
        self.assertEqual(selected, "ship_a")

    def test_ship_hull_polygon_is_single_coherent_shape(self):
        window = object.__new__(helper_mod.BattleMapWindow)
        window.x0 = 0.0
        window.y0 = 0.0
        window.cell = 10.0
        points = window._ship_hull_polygon_points([(0, 0), (1, 0), (1, 1)])
        self.assertGreaterEqual(len(points), 6)
        self.assertEqual(len(points) % 2, 0)


if __name__ == "__main__":
    unittest.main()
