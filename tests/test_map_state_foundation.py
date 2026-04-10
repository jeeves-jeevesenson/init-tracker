import unittest

from map_state import MapQueryAPI, MapState, apply_map_delta, build_map_delta, map_delta_has_changes


class MapStateFoundationTests(unittest.TestCase):
    def test_legacy_round_trip_preserves_core_layers(self):
        state = MapState.from_legacy(
            cols=12,
            rows=10,
            positions={1: (2, 3)},
            obstacles={(4, 5)},
            rough_terrain={(1, 1): {"color": "#abc", "movement_type": "ground", "is_swim": False, "is_rough": True}},
            aoes={9: {"kind": "circle", "cx": 1.0, "cy": 2.0}},
            presentation={"auras_enabled": False},
        )
        payload = state.to_dict()
        restored = MapState.from_dict(payload)
        legacy = restored.to_legacy()
        self.assertEqual(legacy["cols"], 12)
        self.assertEqual(legacy["rows"], 10)
        self.assertEqual(legacy["positions"][1], (2, 3))
        self.assertIn((4, 5), legacy["obstacles"])
        self.assertEqual(legacy["rough_terrain"][(1, 1)]["color"], "#abc")
        self.assertIn(9, legacy["aoes"])

    def test_map_query_reports_blocking_and_traversal(self):
        state = MapState.from_legacy(
            cols=8,
            rows=8,
            positions={1: (2, 2)},
            obstacles={(3, 3)},
            rough_terrain={(2, 3): {"color": "#111", "movement_type": "ground", "is_swim": False, "is_rough": True}},
        )
        query = MapQueryAPI(state)
        self.assertTrue(query.blocks_movement(3, 3))
        self.assertFalse(query.blocks_movement(2, 3))
        self.assertEqual(query.movement_cost_for_step(2, 2, 2, 3, 5), 10)
        traversal = query.traversal_state_for_unit(2, 2)
        self.assertEqual(traversal["occupied_by"], [1])

    def test_map_delta_applies_atomic_changes(self):
        prev = MapState.from_legacy(cols=6, rows=6, positions={1: (1, 1)}, obstacles={(2, 2)}, rough_terrain={})
        curr = MapState.from_legacy(
            cols=6,
            rows=6,
            positions={1: (3, 3)},
            obstacles={(4, 4)},
            rough_terrain={(2, 1): {"color": "#999", "movement_type": "ground", "is_swim": False, "is_rough": True}},
            aoes={11: {"kind": "circle", "cx": 2.0, "cy": 2.0}},
        )
        delta = build_map_delta(prev, curr)
        self.assertTrue(map_delta_has_changes(delta))
        merged = apply_map_delta(prev, delta)
        legacy = merged.to_legacy()
        self.assertEqual(legacy["positions"][1], (3, 3))
        self.assertIn((4, 4), legacy["obstacles"])
        self.assertIn((2, 1), legacy["rough_terrain"])
        self.assertIn(11, legacy["aoes"])


if __name__ == "__main__":
    unittest.main()
