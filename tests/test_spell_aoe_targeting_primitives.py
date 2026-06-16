import unittest
from dnd_initative_tracker import InitiativeTracker, AoeSpec
from spell_engine_primitives import resolve_aoe_cells
from unittest import mock

class TestSpellAoeTargetingPrimitives(unittest.TestCase):
    def setUp(self):
        self.tracker = InitiativeTracker()

    def test_sphere_resolution(self):
        # A 10.5ft (~2.1 sq) sphere at center (5.5, 5.5) should hit (7, 5)
        # (7, 5) center is (7.5, 5.5), dist 2.0.
        # With R=2.1, R^2 = 4.41.
        # col 7.5: 2.0^2 + 0.33^2 = 4.11 (IN). 3 points IN.
        # col 7.16: 1.66^2 + 0.33^2 = 2.88 (IN). 3 points IN.
        # Total 6 points IN -> IN.
        spec = AoeSpec(
            origin_mode="point",
            shape="sphere",
            origin_col=5.5,
            origin_row=5.5,
            radius_ft=10.5
        )
        cells = self.tracker._resolve_aoe_cells(spec)
        self.assertIn((5, 5), cells)
        self.assertIn((7, 5), cells)
        self.assertIn((3, 5), cells)
        self.assertIn((5, 3), cells)
        self.assertIn((5, 7), cells)
        self.assertNotIn((1, 5), cells)

    def test_line_resolution(self):
        # 30ft line from (5.5, 5.5) towards (10.5, 5.5) -> east
        spec = AoeSpec(
            origin_mode="point",
            shape="line",
            origin_col=5.5,
            origin_row=5.5,
            target_col=10.5,
            target_row=5.5,
            length_ft=30.0,
            width_ft=5.0
        )
        cells = self.tracker._resolve_aoe_cells(spec)
        self.assertIn((5, 5), cells)
        self.assertIn((10, 5), cells)
        self.assertNotIn((5, 6), cells)
        self.assertNotIn((4, 5), cells)

    def test_cone_resolution(self):
        # 16ft cone (~3.2 sq) from (5.5, 5.5) towards (10.5, 5.5) -> east
        # At R=3.2, cell (8, 5) center (8.5, 5.5) dist 3.0 is well within distance.
        spec = AoeSpec(
            origin_mode="point",
            shape="cone",
            origin_col=5.5,
            origin_row=5.5,
            target_col=10.5,
            target_row=5.5,
            length_ft=16.0
        )
        cells = self.tracker._resolve_aoe_cells(spec)
        # (5, 5) is still mostly OUT
        self.assertNotIn((5, 5), cells)
        self.assertIn((8, 5), cells)
        self.assertIn((7, 5), cells)
        self.assertIn((6, 5), cells)

    def test_target_inclusion(self):
        # Mock _lan_live_map_data to return positions
        # cols, rows, obstacles, rough_terrain, positions
        positions = {
            1: (5, 5),  # Alice
            2: (7, 5),  # Bob
            3: (10, 10) # Charlie
        }
        self.tracker._lan_live_map_data = mock.Mock(return_value=(20, 20, set(), {}, positions))

        # Mock _lan_get_map_state for MapQueryAPI
        self.tracker._lan_get_map_state = mock.Mock()

        # Mock MapQueryAPI to avoid real map logic
        with mock.patch("dnd_initative_tracker.MapQueryAPI") as mock_query_cls:
            mock_query = mock_query_cls.return_value
            mock_query.blocks_line_of_effect.return_value = False

            # Using center-aligned coordinates for the sphere
            targets = self.tracker._lan_compute_included_units_for_aoe({
                "shape": "sphere",
                "cx": 5.5,
                "cy": 5.5,
                "radius_ft": 15.0
            })

            self.assertIn(1, targets)
            self.assertIn(2, targets)
            self.assertNotIn(3, targets)

    def test_half_coverage(self):
        # A circle at (5.5, 5.5) with radius 4.0 (20ft)
        # Token at (9, 5) center is (9.5, 5.5). Distance is exactly 4.0.
        # With new circular footprint sampling (R=0.35):
        # Center (9.5, 5.5) is IN (distance 4.0, hit by epsilon).
        # Offset (-0.3, 0) -> (9.2, 5.5) is IN (distance 3.7).
        # Offsets (-0.22, +/-0.22) -> (9.28, 5.28/5.72) are IN (dist ~3.79).
        # Offsets (0, +/-0.3) -> (9.5, 5.2/5.8) are OUT (dist = sqrt(4^2 + 0.3^2) = 4.011).
        # Offset (0.3, 0) -> (9.8, 5.5) is OUT (dist 4.3).
        # Offsets (0.22, +/-0.22) -> (9.72, 5.28/5.72) are OUT (dist ~4.23).
        # Total IN: center + 3 left offsets = 4 points.
        # 4/9 is < 50%, so it should be OUT.

        spec = AoeSpec(
            origin_mode="point",
            shape="sphere",
            origin_col=5.5,
            origin_row=5.5,
            radius_ft=20.0
        )
        cells = self.tracker._resolve_aoe_cells(spec)
        self.assertNotIn((9, 5), cells)

        # Move it slightly closer: radius 20.1 ft (~4.02 sq)
        # Now (9.5, 5.2) distance is 4.011. If R=4.02, it's IN.
        # This would add the 2 cardinal vertical points.
        # Total IN: 4 + 2 = 6 points. IN.
        spec = AoeSpec(
            origin_mode="point",
            shape="sphere",
            origin_col=5.5,
            origin_row=5.5,
            radius_ft=20.1
        )
        cells = self.tracker._resolve_aoe_cells(spec)
        self.assertIn((9, 5), cells)

    def test_fireball_sliver_exclusion(self):
        # Fireball at (5.5, 5.5) radius 20ft (4 squares).
        # Edge at 9.5.
        # Token at (10, 5) center is (10.5, 5.5).
        # Token footprint is [10.15, 10.85].
        # The square (10, 5) is touched from 10.0 to 9.5 (negative? no).
        # Wait, if origin is 5.5 and R=4, it reaches 9.5.
        # Square (9, 5) is [9, 10]. It's half covered.
        # Square (10, 5) is [10, 11]. It is NOT touched at all.

        # Let's try a diagonal square. (8, 8).
        # Center (8.5, 8.5). Distance from (5.5, 5.5) is sqrt(3^2 + 3^2) = 4.24.
        # Top-left of square (8, 8) is (8, 8). Distance sqrt(2.5^2 + 2.5^2) = 3.53.
        # So the top-left corner of square (8, 8) is INSIDE.
        # But the token center (8.5, 8.5) is OUT (4.24 > 4).
        # The closest point of the token footprint (radius 0.35) is:
        # (8.5, 8.5) - (0.35/sqrt(2), 0.35/sqrt(2)) = (8.25, 8.25).
        # Distance = sqrt(2.75^2 + 2.75^2) = 3.89.
        # This point is INSIDE (3.89 < 4).
        # However, we need 50% coverage.
        # Since the center (4.24) is OUT, and the circle is mostly further away,
        # it should be OUT.

        spec = AoeSpec(
            origin_mode="point",
            shape="sphere",
            origin_col=5.5,
            origin_row=5.5,
            radius_ft=20.0
        )
        cells = self.tracker._resolve_aoe_cells(spec)
        self.assertNotIn((8, 8), cells)


    def test_map_query_api_none_state(self):
        """Verify MapQueryAPI handles None state without crashing."""
        from map_state import MapQueryAPI
        query = MapQueryAPI(None)
        self.assertIsNotNone(query.state)
        self.assertEqual(query.state.grid.cols, 20)
        # Should not raise
        self.assertFalse(query.blocks_line_of_effect(0, 0, 5, 5))

    def test_resolve_aoe_targets_no_map_state(self):
        """Verify _resolve_aoe_targets handles missing _lan_get_map_state safely."""
        # Ensure it doesn't crash even if _lan_get_map_state returns None
        spec = AoeSpec(
            shape="sphere",
            origin_mode="point",
            origin_col=5.5,
            origin_row=5.5,
            radius_ft=10.0
        )
        # Force the dummy getattr behavior or mock it to return None
        with mock.patch.object(self.tracker, "_lan_get_map_state", return_value=None):
            # Mock positions to avoid real map data dependency
            self.tracker._lan_live_map_data = mock.Mock(return_value=(20, 20, set(), {}, {1: (5, 5)}))

            targets = self.tracker._resolve_aoe_targets(spec, {(5, 5)})
            self.assertEqual(targets, [1])

    def test_lan_get_map_state_returns_valid_state(self):
        """Verify _lan_get_map_state returns a valid MapState object."""
        from map_state import MapState
        state = self.tracker._lan_get_map_state()
        self.assertIsInstance(state, MapState)
        self.assertEqual(state.grid.cols, 20)

    def test_fractional_center(self):
        # A 10ft circle (R=2.0) at (5.7, 5.7)
        # Token at (7, 7) center is (7.5, 7.5).
        # Distance = sqrt((7.5-5.7)^2 + (7.5-5.7)^2) = sqrt(1.8^2 + 1.8^2) = 2.54.
        # R=2.0, dist=2.54. Should be OUT.
        spec = AoeSpec(
            origin_mode="point",
            shape="sphere",
            origin_col=5.7,
            origin_row=5.7,
            radius_ft=10.0
        )
        cells = self.tracker._resolve_aoe_cells(spec)
        self.assertNotIn((7, 7), cells)

        # Token at (5, 5) center is (5.5, 5.5).
        # Distance = sqrt(0.2^2 + 0.2^2) = 0.28.
        # R=2.0, dist=0.28. Should be IN.
        self.assertIn((5, 5), cells)

if __name__ == "__main__":
    unittest.main()
