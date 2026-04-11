import unittest

import dnd_initative_tracker as tracker_mod
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

    def test_exact_cell_union_boundary_handles_concave_hull(self):
        boundary = helper_mod.BattleMapWindow._ship_cell_union_boundary_vertices([(0, 0), (1, 0), (0, 1)])
        self.assertIn((1, 1), boundary)
        self.assertIn((0, 0), boundary)
        self.assertIn((2, 1), boundary)
        self.assertEqual(abs(helper_mod.BattleMapWindow._polygon_area(boundary)), 3.0)
        for idx, current in enumerate(boundary):
            nxt = boundary[(idx + 1) % len(boundary)]
            self.assertEqual(abs(int(current[0]) - int(nxt[0])) + abs(int(current[1]) - int(nxt[1])), 1)

    def test_ship_hull_geometry_is_stable_across_rotation_steps(self):
        window = object.__new__(helper_mod.BattleMapWindow)
        window.x0 = 0.0
        window.y0 = 0.0
        window.cell = 10.0
        local_cells = [(0, 0), (1, 0), (2, 0), (0, 1), (1, 1)]
        expected_area = None
        for facing in (0.0, 90.0, 180.0, 270.0):
            world_cells = tracker_mod.InitiativeTracker._ship_world_cells_from_local(
                anchor_col=12,
                anchor_row=8,
                local_cells=local_cells,
                facing_deg=facing,
            )
            points = window._ship_hull_polygon_points(world_cells)
            self.assertGreaterEqual(len(points), 8)
            coords = [float(v) / 10.0 for v in points]
            for value in coords:
                self.assertAlmostEqual(value, round(value), places=6)
            polygon = [(points[i], points[i + 1]) for i in range(0, len(points), 2)]
            area = abs(helper_mod.BattleMapWindow._polygon_area([(int(x / 10.0), int(y / 10.0)) for x, y in polygon]))
            if expected_area is None:
                expected_area = area
            self.assertEqual(area, expected_area)


if __name__ == "__main__":
    unittest.main()
