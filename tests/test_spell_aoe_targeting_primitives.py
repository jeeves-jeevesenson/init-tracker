import unittest
from dnd_initative_tracker import InitiativeTracker, AoeSpec
from spell_engine_primitives import resolve_aoe_cells
from unittest import mock

class TestSpellAoeTargetingPrimitives(unittest.TestCase):
    def setUp(self):
        self.tracker = InitiativeTracker()

    def test_sphere_resolution(self):
        # 10ft radius sphere at (5,5)
        spec = AoeSpec(
            origin_mode="point",
            shape="sphere",
            origin_col=5.0,
            origin_row=5.0,
            radius_ft=10.0
        )
        cells = self.tracker._resolve_aoe_cells(spec)
        self.assertIn((5, 5), cells)
        self.assertIn((3, 5), cells)
        self.assertIn((7, 5), cells)
        self.assertIn((5, 3), cells)
        self.assertIn((5, 7), cells)
        self.assertNotIn((2, 5), cells)

    def test_line_resolution(self):
        # 30ft line from (5,5) towards (10,5) -> east
        spec = AoeSpec(
            origin_mode="point",
            shape="line",
            origin_col=5.0,
            origin_row=5.0,
            target_col=10.0,
            target_row=5.0,
            length_ft=30.0,
            width_ft=5.0
        )
        cells = self.tracker._resolve_aoe_cells(spec)
        self.assertIn((5, 5), cells)
        self.assertIn((10, 5), cells)
        self.assertNotIn((5, 6), cells)
        self.assertNotIn((4, 5), cells)

    def test_cone_resolution(self):
        # 15ft cone from (5,5) towards (10,5) -> east
        spec = AoeSpec(
            origin_mode="point",
            shape="cone",
            origin_col=5.0,
            origin_row=5.0,
            target_col=10.0,
            target_row=5.0,
            length_ft=15.0
        )
        cells = self.tracker._resolve_aoe_cells(spec)
        self.assertIn((5, 5), cells)
        self.assertIn((8, 5), cells) # 15ft = 3 cells
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
            
            targets = self.tracker._lan_compute_included_units_for_aoe({
                "shape": "sphere",
                "cx": 5.0,
                "cy": 5.0,
                "radius_ft": 15.0
            })
            
            self.assertIn(1, targets)
            self.assertIn(2, targets)
            self.assertNotIn(3, targets)

if __name__ == "__main__":
    unittest.main()
