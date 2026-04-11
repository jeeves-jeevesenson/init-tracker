import tempfile
import unittest
from pathlib import Path

import dnd_initative_tracker as tracker_mod
from map_state import normalize_tactical_payload, tactical_preset_catalog


class TacticalPresetCatalogTests(unittest.TestCase):
    def test_barrel_defaults_normalize_to_feature_semantics(self):
        normalized = normalize_tactical_payload(category="feature", kind="barrel", payload={})
        self.assertEqual(normalized["category"], "feature")
        self.assertEqual(normalized["kind"], "barrel")
        payload = normalized["payload"]
        self.assertEqual(payload["tactical_preset_id"], "barrel")
        self.assertTrue(payload["destructible"])
        self.assertTrue(payload["flammable"])
        self.assertEqual(payload["hp"], 8)
        self.assertEqual(payload["ac"], 11)

    def test_powder_barrel_defaults_include_explosive_fire_aftermath(self):
        normalized = normalize_tactical_payload(category="feature", kind="powder_barrel", payload={})
        payload = normalized["payload"]
        self.assertEqual(payload["tactical_preset_id"], "powder_barrel")
        self.assertTrue(payload["explosive"])
        self.assertTrue(payload["flammable"])
        self.assertIsInstance(payload.get("on_destroy_spawn_hazard"), dict)
        self.assertEqual(payload["on_destroy_spawn_hazard"]["kind"], "fire")

    def test_traversal_presets_include_expected_tags(self):
        ladder = normalize_tactical_payload(category="feature", kind="ladder", payload={})
        gangplank = normalize_tactical_payload(category="feature", kind="gangplank", payload={})
        stairs = normalize_tactical_payload(category="feature", kind="stairs", payload={})
        self.assertIn("climbable", ladder["payload"]["tags"])
        self.assertIn("traversal", gangplank["payload"]["tags"])
        self.assertIn("stairs", stairs["payload"]["tags"])

    def test_stack_semantics_are_deterministic_for_barrels(self):
        light = normalize_tactical_payload(category="feature", kind="barrel", payload={}, count=1)["payload"]
        medium = normalize_tactical_payload(category="feature", kind="barrel", payload={}, count=3)["payload"]
        dense = normalize_tactical_payload(category="feature", kind="barrel", payload={}, count=5)["payload"]
        self.assertEqual(light["stack_state"], "light")
        self.assertEqual(medium["stack_state"], "medium")
        self.assertEqual(dense["stack_state"], "dense")
        self.assertFalse(light["blocks_movement"])
        self.assertTrue(dense["blocks_movement"])

    def test_catalog_contains_expected_pirate_combat_presets(self):
        catalog = tactical_preset_catalog()
        for preset_id in (
            "barrel",
            "powder_barrel",
            "crate_stack",
            "cannon",
            "ballista",
            "railing",
            "hatch",
            "ladder",
            "mast",
            "stairs",
            "gangplank",
            "door",
            "fire",
            "smoke",
            "oil",
            "burning_debris",
            "dock_platform",
            "cover_obstacle",
            "difficult_patch",
        ):
            self.assertIn(preset_id, catalog)


class TacticalPresetPersistenceTests(unittest.TestCase):
    def test_upsert_feature_applies_preset_defaults_and_persists(self):
        app = object.__new__(tracker_mod.InitiativeTracker)
        app._map_window = None
        app._lan_grid_cols = 12
        app._lan_grid_rows = 12
        app._lan_positions = {}
        app._lan_obstacles = set()
        app._lan_rough_terrain = {}
        app._lan_aoes = {}
        app._lan_next_aoe_id = 1
        app._lan_auras_enabled = True
        app._session_bg_images = []
        app._session_next_bg_id = 1
        app._map_state = tracker_mod.MapState.from_legacy(cols=12, rows=12)
        app._lan_force_state_broadcast = lambda *args, **kwargs: None

        fid = tracker_mod.InitiativeTracker._upsert_map_feature(
            app,
            col=2,
            row=3,
            kind="barrel",
            payload={"name": "Deck Barrel"},
            hydrate_window=False,
            broadcast=False,
        )
        state = tracker_mod.InitiativeTracker._capture_canonical_map_state(app, prefer_window=False).to_dict()
        feature = next(item for item in state["features"] if item["id"] == fid)
        payload = feature["payload"]
        self.assertEqual(payload["tactical_preset_id"], "barrel")
        self.assertEqual(payload["name"], "Deck Barrel")
        self.assertTrue(payload["destructible"])

    def test_legacy_snapshot_feature_kind_is_normalized_non_destructively(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            app = object.__new__(tracker_mod.InitiativeTracker)
            app._history_file_path = lambda: Path(tmpdir) / "battle.log"
            state = tracker_mod.InitiativeTracker._canonical_map_state_from_snapshot_map_payload(
                app,
                {
                    "grid": {"cols": 8, "rows": 8, "feet_per_square": 5},
                    "features": [{"id": "f1", "col": 1, "row": 1, "kind": "barrel", "payload": {"name": "Legacy Barrel"}}],
                },
            )
            payload = state.to_dict()
            entry = payload["features"][0]
            self.assertEqual(entry["kind"], "barrel")
            self.assertEqual(entry["payload"]["name"], "Legacy Barrel")
            self.assertEqual(entry["payload"]["tactical_preset_id"], "barrel")


if __name__ == "__main__":
    unittest.main()
