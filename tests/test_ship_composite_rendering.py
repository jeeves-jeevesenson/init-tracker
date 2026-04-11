import unittest
import tempfile
import types
from pathlib import Path

import dnd_initative_tracker as tracker_mod
import helper_script as helper_mod
from ship_blueprints import load_repo_runtime_ship_blueprints


class ShipCompositeRenderingTests(unittest.TestCase):
    class _CanvasSpy:
        def __init__(self):
            self.polygons = []

        def delete(self, *_args, **_kwargs):
            return None

        def create_image(self, *_args, **_kwargs):
            return None

        def create_polygon(self, points, **kwargs):
            self.polygons.append((list(points), dict(kwargs)))
            return len(self.polygons)

        def create_rectangle(self, *_args, **_kwargs):
            return None

        def create_text(self, *_args, **_kwargs):
            return None

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

    def test_deck_texture_render_uses_converted_raster_when_avif_unreadable(self):
        window = object.__new__(helper_mod.BattleMapWindow)
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            avif = tmp / "wood.avif"
            png = tmp / "wood.png"
            avif.write_bytes(b"not-real-avif")
            if helper_mod.Image is None:
                self.skipTest("Pillow not available")
            helper_mod.Image.new("RGBA", (4, 4), (140, 100, 60, 255)).save(png)
            window._resolve_ship_asset_path = lambda image_path, image_key: str(avif)
            window.cell = 20.0
            window.x0 = 0.0
            window.y0 = 0.0
            window._ship_deck_render_cache = {}
            window.map_structures = {"ship_a": {"payload": {"ship_blueprint_id": "sloop"}}}
            image_tk_original = helper_mod.ImageTk

            class _FakeImageTk:
                @staticmethod
                def PhotoImage(image):
                    return ("photo", image.size)

            helper_mod.ImageTk = _FakeImageTk
            try:
                composite = window._ship_deck_composite_tk_image(
                    sid="ship_a",
                    occupied=[(0, 0), (1, 0), (0, 1), (1, 1)],
                    render={"deck_texture_key": "ship_deck_wood"},
                    facing_deg=0.0,
                )
            finally:
                helper_mod.ImageTk = image_tk_original
            self.assertIsNotNone(composite)

    def test_deck_texture_asset_seam_reports_missing_deterministically(self):
        window = object.__new__(helper_mod.BattleMapWindow)
        window._resolve_ship_asset_path = lambda image_path, image_key: None
        resolved, identity = window._resolve_ship_deck_texture({})
        self.assertIsNone(resolved)
        self.assertEqual(identity, "ship_deck_wood:missing")

    def test_deck_render_cache_reuses_same_composite_key(self):
        if helper_mod.Image is None:
            self.skipTest("Pillow not available")
        window = object.__new__(helper_mod.BattleMapWindow)
        window.cell = 20.0
        window.x0 = 0.0
        window.y0 = 0.0
        window._ship_deck_render_cache = {}
        window.map_structures = {"ship_a": {"payload": {"ship_blueprint_id": "sloop"}}}
        window._resolve_ship_asset_path = lambda image_path, image_key: None
        image_tk_original = helper_mod.ImageTk

        class _FakeImageTk:
            @staticmethod
            def PhotoImage(image):
                return ("photo", image.size)

        helper_mod.ImageTk = _FakeImageTk
        try:
            occupied = [(0, 0), (1, 0), (0, 1), (1, 1)]
            first = window._ship_deck_composite_tk_image(sid="ship_a", occupied=occupied, render={}, facing_deg=0.0)
            second = window._ship_deck_composite_tk_image(sid="ship_a", occupied=occupied, render={}, facing_deg=0.0)
        finally:
            helper_mod.ImageTk = image_tk_original
        self.assertIsNotNone(first)
        self.assertIs(first, second)

    def test_entity_cells_supports_payload_occupied_cells(self):
        window = object.__new__(helper_mod.BattleMapWindow)
        cells = window._entity_cells(
            2,
            3,
            {"occupied_cells": [{"col": 2, "row": 3}, {"col": 3, "row": 3}]},
        )
        self.assertEqual(cells, [(2, 3), (3, 3)])

    def test_draw_map_structures_uses_structure_root_occupied_cells_for_ships(self):
        window = object.__new__(helper_mod.BattleMapWindow)
        window.canvas = self._CanvasSpy()
        window.x0 = 0.0
        window.y0 = 0.0
        window.cell = 10.0
        window._map_author_selected_cell = None
        window.map_ship_debug_render_var = types.SimpleNamespace(get=lambda: False)
        window.app = types.SimpleNamespace(
            _ship_instance_for_structure=lambda _sid: {},
            _ship_blueprints=lambda: {},
        )
        window.map_structures = {
            "ship_a": {
                "id": "ship_a",
                "kind": "ship_hull",
                "anchor_col": 5,
                "anchor_row": 5,
                "occupied_cells": [{"col": 5, "row": 5}, {"col": 6, "row": 5}],
                "payload": {"name": "Red Wake", "ship_instance_id": "ship_1", "occupied_cells": [{"col": 5, "row": 5}]},
            }
        }
        captured = {}

        def _capture_draw(*, sid, occupied, render, facing_deg):
            captured["sid"] = sid
            captured["occupied"] = list(occupied)
            return False

        window._draw_ship_deck_surface = _capture_draw
        window._draw_ship_selected_overlays = lambda *args, **kwargs: None
        window._draw_map_structures()
        self.assertEqual(captured.get("sid"), "ship_a")
        self.assertEqual(captured.get("occupied"), [(5, 5), (6, 5)])

    def test_rotated_starter_deck_regions_stay_within_rotated_hull_footprint(self):
        runtime, errors = load_repo_runtime_ship_blueprints()
        self.assertFalse(errors, msg=errors)
        blueprint = runtime["sloop"]
        local_hull = [
            (int(cell.get("col", 0) or 0), int(cell.get("row", 0) or 0))
            for cell in (blueprint.get("footprint") if isinstance(blueprint.get("footprint"), list) else [])
            if isinstance(cell, dict)
        ]
        self.assertGreater(len(local_hull), 1)
        for facing in (0.0, 90.0, 180.0, 270.0):
            occupied = set(
                tracker_mod.InitiativeTracker._ship_world_cells_from_local(
                    anchor_col=20,
                    anchor_row=12,
                    local_cells=local_hull,
                    facing_deg=facing,
                )
            )
            regions = tracker_mod.InitiativeTracker._transform_ship_deck_regions_runtime_metadata(
                deck_regions=list(blueprint.get("deck_regions") if isinstance(blueprint.get("deck_regions"), list) else []),
                anchor_col=20,
                anchor_row=12,
                facing_deg=facing,
            )
            self.assertTrue(regions)
            for region in regions:
                cells = {
                    (int(cell.get("col", 0) or 0), int(cell.get("row", 0) or 0))
                    for cell in (region.get("cells") if isinstance(region.get("cells"), list) else [])
                    if isinstance(cell, dict)
                }
                self.assertTrue(cells)
                self.assertTrue(cells.issubset(occupied))

    def test_deck_region_alignment_stays_consistent_across_facings(self):
        region = {"id": "mast_zone", "label": "Mast Zone", "cells": [{"col": 1, "row": 0}, {"col": 1, "row": 1}]}
        expected_count = None
        for facing in (0.0, 90.0, 180.0, 270.0):
            transformed = tracker_mod.InitiativeTracker._transform_ship_deck_regions_runtime_metadata(
                deck_regions=[region],
                anchor_col=10,
                anchor_row=10,
                facing_deg=facing,
            )
            self.assertEqual(len(transformed), 1)
            world_cells = transformed[0].get("cells") if isinstance(transformed[0].get("cells"), list) else []
            self.assertEqual(len(world_cells), 2)
            if expected_count is None:
                expected_count = len(world_cells)
            self.assertEqual(len(world_cells), expected_count)


if __name__ == "__main__":
    unittest.main()
