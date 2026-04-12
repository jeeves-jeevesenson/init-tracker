import json
from pathlib import Path
import unittest

import dnd_initative_tracker as tracker_mod
from ship_blueprints import (
    COMPOSITE_SHIP_SCHEMA,
    import_tiled_ship_blueprint,
    load_composite_ship_blueprints_from_dir,
    load_repo_runtime_ship_blueprints,
    normalize_composite_ship_blueprint,
)


class ShipBlueprintPipelineTests(unittest.TestCase):
    def test_repo_blueprint_load_includes_imported_starters(self):
        runtime, errors = load_repo_runtime_ship_blueprints()
        self.assertFalse(errors, msg=errors)
        self.assertIn("dinghy_launch", runtime)
        self.assertIn("sloop", runtime)
        self.assertIn("brig", runtime)
        self.assertIn("frigate_heavy", runtime)
        self.assertEqual(((runtime["sloop"].get("render") or {}).get("style")), "polygon")
        self.assertEqual(((runtime["sloop"].get("render") or {}).get("base_image_key")), "sloop_hull")
        self.assertEqual(((runtime["sloop"].get("render") or {}).get("fallback_style")), "polygon")
        self.assertEqual(((runtime["sloop"].get("render") or {}).get("deck_texture_key")), "ship_deck_wood")
        self.assertEqual(((runtime["dinghy_launch"].get("render") or {}).get("style")), "polygon")
        self.assertTrue(isinstance(runtime["sloop"].get("deck_regions"), list) and runtime["sloop"].get("deck_regions"))
        self.assertTrue(isinstance(runtime["frigate_heavy"].get("deck_regions"), list) and runtime["frigate_heavy"].get("deck_regions"))
        self.assertTrue(((runtime["brig"].get("local_space") or {}).get("hull_cells")))

    def test_composite_schema_validation_rejects_invalid_anchor(self):
        normalized, errors = normalize_composite_ship_blueprint(
            {
                "schema": COMPOSITE_SHIP_SCHEMA,
                "id": "bad_ship",
                "display_name": "Bad Ship",
                "local_space": {
                    "render_anchor": {"col": 9, "row": 9},
                    "hull_cells": [{"col": 0, "row": 0}],
                },
            }
        )
        self.assertEqual(normalized.get("id"), "bad_ship")
        self.assertIn("render_anchor_not_in_hull", errors)

    def test_tiled_import_requires_hull(self):
        with self.assertRaises(Exception):
            import_tiled_ship_blueprint(
                {
                    "id": "broken",
                    "width": 2,
                    "height": 2,
                    "layers": [],
                }
            )

    def test_tiled_source_files_round_trip_to_composite_schema(self):
        repo_root = Path(__file__).resolve().parents[1]
        source_dir = repo_root / "assets" / "ships" / "source_tiled"
        for source_path in sorted(source_dir.glob("*.tiled.json")):
            payload = json.loads(source_path.read_text(encoding="utf-8"))
            normalized = import_tiled_ship_blueprint(payload, blueprint_id=source_path.stem.replace(".tiled", ""))
            self.assertEqual(normalized.get("schema"), COMPOSITE_SHIP_SCHEMA)
            self.assertTrue(((normalized.get("local_space") or {}).get("hull_cells")))
            self.assertTrue(((normalized.get("deck_regions") if isinstance(normalized.get("deck_regions"), list) else [])))

    def test_runtime_app_uses_loaded_composite_blueprints(self):
        app = object.__new__(tracker_mod.InitiativeTracker)
        app._map_state = tracker_mod.MapState.from_dict({"grid": {"cols": 30, "rows": 30, "feet_per_square": 5}})
        app._capture_canonical_map_state = lambda prefer_window=False: app._map_state.normalized()
        blueprints = app._ship_blueprints()
        self.assertIn("dinghy_launch", blueprints)
        self.assertIn("sloop", blueprints)
        self.assertIn("brig", blueprints)
        self.assertIn("frigate_heavy", blueprints)
        self.assertTrue(blueprints["sloop"].get("deck_regions"))
        self.assertTrue(blueprints["brig"].get("deck_regions"))
        self.assertTrue(blueprints["frigate_heavy"].get("deck_regions"))
        self.assertEqual(((blueprints["sloop"].get("render") or {}).get("style")), "polygon")
        self.assertTrue(((blueprints["brig"].get("local_space") or {}).get("hull_cells")))
        path = app._ship_render_asset_path_for_key("sloop_hull")
        self.assertTrue(path)
        self.assertTrue(Path(path).exists())

    def test_normalized_blueprint_files_validate(self):
        repo_root = Path(__file__).resolve().parents[1]
        normalized_dir = repo_root / "assets" / "ships" / "blueprints"
        blueprints, errors = load_composite_ship_blueprints_from_dir(normalized_dir)
        self.assertFalse(errors, msg=errors)
        self.assertIn("dinghy_launch", blueprints)
        self.assertIn("sloop", blueprints)
        self.assertIn("brig", blueprints)
        self.assertIn("frigate_heavy", blueprints)

    def test_imported_starter_region_labels_are_present(self):
        runtime, errors = load_repo_runtime_ship_blueprints()
        self.assertFalse(errors, msg=errors)
        dinghy_labels = {str(region.get("label") or "") for region in (runtime["dinghy_launch"].get("deck_regions") or []) if isinstance(region, dict)}
        frigate_labels = {str(region.get("label") or "") for region in (runtime["frigate_heavy"].get("deck_regions") or []) if isinstance(region, dict)}
        self.assertIn("Open Deck", dinghy_labels)
        self.assertIn("Stern", dinghy_labels)
        self.assertIn("Main Battery", frigate_labels)
        self.assertIn("Helm / Captain's Stern", frigate_labels)

    def test_frigate_heavy_hull_bounds_scaled_to_triple_size(self):
        runtime, errors = load_repo_runtime_ship_blueprints()
        self.assertFalse(errors, msg=errors)
        frigate = runtime.get("frigate_heavy") or {}
        hull_cells = list(((frigate.get("local_space") or {}).get("hull_cells") or []))
        self.assertTrue(hull_cells)
        cols = [int(cell.get("col", 0)) for cell in hull_cells if isinstance(cell, dict)]
        rows = [int(cell.get("row", 0)) for cell in hull_cells if isinstance(cell, dict)]
        self.assertTrue(cols and rows)
        self.assertEqual((max(cols) - min(cols) + 1), 33)
        self.assertEqual((max(rows) - min(rows) + 1), 66)

    def test_render_metadata_supports_asset_fields_and_facing_overrides(self):
        normalized, errors = normalize_composite_ship_blueprint(
            {
                "schema": COMPOSITE_SHIP_SCHEMA,
                "id": "asset_ship",
                "display_name": "Asset Ship",
                "local_space": {"render_anchor": {"col": 0, "row": 0}, "hull_cells": [{"col": 0, "row": 0}]},
                "render": {
                    "style": "asset_or_polygon",
                    "base_image_key": "asset_ship_base",
                    "base_image_path": "assets/ships/art/asset_ship.png",
                    "image_anchor": "center",
                    "image_offset_col": 1,
                    "image_offset_row": -1,
                    "facing_assets": {
                        "90": {"image_key": "asset_ship_east", "offset_col": 2, "offset_row": 0},
                        "180": {"image_path": "assets/ships/art/asset_ship_south.png", "image_anchor": "s"},
                    },
                },
            }
        )
        self.assertFalse(errors, msg=errors)
        render = normalized.get("render") or {}
        self.assertEqual(render.get("base_image_key"), "asset_ship_base")
        self.assertEqual(render.get("base_image_path"), "assets/ships/art/asset_ship.png")
        self.assertEqual(render.get("image_anchor"), "center")
        self.assertEqual(render.get("image_offset_col"), 1)
        self.assertEqual(render.get("image_offset_row"), -1)
        self.assertIn("90", render.get("facing_assets") or {})

    def test_composite_schema_validates_deck_regions_within_hull(self):
        normalized, errors = normalize_composite_ship_blueprint(
            {
                "schema": COMPOSITE_SHIP_SCHEMA,
                "id": "deck_ship",
                "display_name": "Deck Ship",
                "local_space": {
                    "render_anchor": {"col": 0, "row": 0},
                    "hull_cells": [{"col": 0, "row": 0}, {"col": 1, "row": 0}],
                },
                "deck_regions": [
                    {"id": "main", "label": "Main Deck", "cells": [{"col": 0, "row": 0}]},
                    {"id": "bad", "label": "Bad", "cells": [{"col": 3, "row": 3}]},
                ],
            }
        )
        self.assertEqual(normalized.get("id"), "deck_ship")
        self.assertIn("deck_region_outside_hull:bad", errors)


if __name__ == "__main__":
    unittest.main()
