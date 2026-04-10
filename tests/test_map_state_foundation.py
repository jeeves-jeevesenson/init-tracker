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

    def test_query_uses_feature_footprint_and_hazard_cost(self):
        state = MapState.from_dict(
            {
                "grid": {"cols": 10, "rows": 10, "feet_per_square": 5},
                "terrain_cells": [],
                "obstacles": [],
                "features": [
                    {
                        "id": "f1",
                        "col": 2,
                        "row": 2,
                        "kind": "feature",
                        "payload": {
                            "blocks_movement": True,
                            "occupied_cells": [{"col": 2, "row": 2}, {"col": 3, "row": 2}],
                        },
                    }
                ],
                "hazards": [
                    {
                        "id": "h1",
                        "col": 4,
                        "row": 4,
                        "kind": "fire",
                        "payload": {"movement_multiplier": 2},
                    }
                ],
                "elevation_cells": [{"col": 4, "row": 4, "elevation": 10}],
            }
        )
        query = MapQueryAPI(state)
        self.assertTrue(query.blocks_movement(3, 2))
        self.assertEqual(query.movement_cost_for_step(4, 3, 4, 4, 5), 20)

    def test_map_delta_carries_canonical_layers(self):
        prev = MapState.from_dict(
            {
                "grid": {"cols": 8, "rows": 8, "feet_per_square": 5},
                "features": [{"id": "f1", "col": 1, "row": 1, "kind": "crate", "payload": {}}],
                "hazards": [{"id": "h1", "col": 2, "row": 2, "kind": "fire", "payload": {}}],
                "structures": [{"id": "s1", "kind": "ship_hull", "anchor_col": 0, "anchor_row": 0, "occupied_cells": [], "payload": {}}],
                "elevation_cells": [{"col": 3, "row": 3, "elevation": 5}],
            }
        )
        curr = MapState.from_dict(
            {
                "grid": {"cols": 8, "rows": 8, "feet_per_square": 5},
                "features": [{"id": "f2", "col": 4, "row": 4, "kind": "barrel", "payload": {}}],
                "hazards": [{"id": "h2", "col": 5, "row": 5, "kind": "smoke", "payload": {}}],
                "structures": [{"id": "s2", "kind": "rowboat", "anchor_col": 1, "anchor_row": 1, "occupied_cells": [], "payload": {}}],
                "elevation_cells": [{"col": 6, "row": 6, "elevation": 10}],
            }
        )
        delta = build_map_delta(prev, curr)
        merged = apply_map_delta(prev, delta)
        payload = merged.to_dict()
        self.assertEqual(payload["features"][0]["id"], "f2")
        self.assertEqual(payload["hazards"][0]["id"], "h2")
        self.assertEqual(payload["structures"][0]["id"], "s2")
        self.assertEqual(payload["elevation_cells"][0]["col"], 6)

    def test_structure_move_blockers_detect_conflicts(self):
        state = MapState.from_dict(
            {
                "grid": {"cols": 10, "rows": 10, "feet_per_square": 5},
                "obstacles": [{"col": 4, "row": 3}],
                "structures": [
                    {
                        "id": "s1",
                        "kind": "ship",
                        "anchor_col": 2,
                        "anchor_row": 3,
                        "occupied_cells": [{"col": 2, "row": 3}, {"col": 3, "row": 3}],
                        "payload": {"blocks_movement": True},
                    },
                    {
                        "id": "s2",
                        "kind": "ship",
                        "anchor_col": 6,
                        "anchor_row": 3,
                        "occupied_cells": [{"col": 6, "row": 3}],
                        "payload": {"blocks_movement": True},
                    },
                ],
                "features": [
                    {
                        "id": "f1",
                        "col": 5,
                        "row": 3,
                        "kind": "wall",
                        "payload": {"blocks_structure_movement": True},
                    }
                ],
            }
        )
        query = MapQueryAPI(state)
        blocked = query.structure_move_blockers("s1", 2, 0)
        self.assertFalse(blocked["ok"])
        self.assertTrue(blocked["blockers"]["obstacles"])
        self.assertTrue(blocked["blockers"]["features"])
        clear = query.structure_move_blockers("s1", 0, 1)
        self.assertTrue(clear["ok"])

    def test_structure_contact_and_boarding_semantics(self):
        state = MapState.from_dict(
            {
                "grid": {"cols": 12, "rows": 12, "feet_per_square": 5},
                "structures": [
                    {
                        "id": "ship_a",
                        "kind": "ship_hull",
                        "anchor_col": 2,
                        "anchor_row": 2,
                        "occupied_cells": [{"col": 2, "row": 2}, {"col": 3, "row": 2}],
                        "payload": {"boardable": True},
                    },
                    {
                        "id": "ship_b",
                        "kind": "ship_hull",
                        "anchor_col": 4,
                        "anchor_row": 2,
                        "occupied_cells": [{"col": 4, "row": 2}],
                        "payload": {"allow_boarding": True},
                    },
                ],
            }
        )
        query = MapQueryAPI(state)
        contacts = query.structure_contacts("ship_a")
        self.assertEqual(len(contacts), 1)
        self.assertTrue(contacts[0]["adjacent"])
        self.assertTrue(contacts[0]["contact"])
        self.assertTrue(contacts[0]["boardable"])
        self.assertEqual(query.boardable_structure_ids("ship_a"), ["ship_b"])

    def test_climb_transition_blocks_strict_unclimbable_vertical_steps(self):
        state = MapState.from_dict(
            {
                "grid": {"cols": 8, "rows": 8, "feet_per_square": 5},
                "features": [
                    {
                        "id": "cliff_edge",
                        "col": 1,
                        "row": 1,
                        "kind": "cliff",
                        "payload": {"tags": ["requires_climb_transition"]},
                    }
                ],
                "elevation_cells": [{"col": 1, "row": 2, "elevation": 15}],
            }
        )
        query = MapQueryAPI(state)
        transition = query.climbable_transition(1, 1, 1, 2)
        self.assertTrue(transition["blocked"])
        self.assertGreaterEqual(query.movement_cost_for_step(1, 1, 1, 2, 5), 10**9)

    def test_climbable_transition_reduces_penalty(self):
        state = MapState.from_dict(
            {
                "grid": {"cols": 8, "rows": 8, "feet_per_square": 5},
                "features": [
                    {"id": "ladder_1", "col": 2, "row": 2, "kind": "ladder", "payload": {"tags": ["ladder"]}},
                ],
                "elevation_cells": [{"col": 2, "row": 3, "elevation": 10}],
            }
        )
        query = MapQueryAPI(state)
        cost = query.movement_cost_for_step(2, 2, 2, 3, 5)
        self.assertLess(cost, 15)


if __name__ == "__main__":
    unittest.main()
