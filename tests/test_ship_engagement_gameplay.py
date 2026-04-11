import random
import unittest

import dnd_initative_tracker as tracker_mod


class ShipEngagementGameplayTests(unittest.TestCase):
    def _build_app(self, *, target_anchor_col: int = 11, contact_target: bool = False):
        app = object.__new__(tracker_mod.InitiativeTracker)
        app._lan_grid_cols = 30
        app._lan_grid_rows = 30
        app._lan_obstacles = set()
        app._lan_positions = {}
        app._lan_aoes = {}
        app._lan_rough_terrain = {}
        app._lan_next_aoe_id = 1
        app.combatants = {}
        app.current_cid = None
        app.round_num = 1
        app._display_order = lambda: []
        app._peek_next_turn_cid = lambda _cid: None
        app._oplog = lambda *args, **kwargs: None
        app._lan_reaction_debug_enabled = lambda: False
        app._lan = type("LanStub", (), {"_cached_snapshot": {}})()
        app._map_state_version = 0
        app._structure_contact_semantics_cache = {}
        app._selected_ship_summary_cache = {}
        target_col = 7 if contact_target else int(target_anchor_col)
        app._map_state = tracker_mod.MapState.from_dict(
            {
                "grid": {"cols": 30, "rows": 30, "feet_per_square": 5},
                "structures": [
                    {
                        "id": "ship_a",
                        "kind": "ship_hull",
                        "anchor_col": 5,
                        "anchor_row": 5,
                        "occupied_cells": [{"col": 5, "row": 5}, {"col": 6, "row": 5}],
                        "payload": {"name": "Red Wake", "ship_instance_id": "ship_1", "allow_boarding": True},
                    },
                    {
                        "id": "ship_b",
                        "kind": "ship_hull",
                        "anchor_col": int(target_col),
                        "anchor_row": 5,
                        "occupied_cells": [{"col": int(target_col), "row": 5}, {"col": int(target_col) + 1, "row": 5}],
                        "payload": {"name": "Blue Fang", "ship_instance_id": "ship_2", "allow_boarding": True},
                    },
                ],
                "presentation": {
                    "ship_instances": {
                        "ship_1": {
                            "id": "ship_1",
                            "name": "Red Wake",
                            "blueprint_id": "sloop",
                            "parent_structure_id": "ship_a",
                            "facing_deg": 0,
                            "size": "medium",
                            "components": [
                                {"id": "hull", "type": "hull", "max_hp": 200, "ac": 14, "damage_threshold": 0},
                                {"id": "helm", "type": "control", "max_hp": 40, "ac": 14, "damage_threshold": 0},
                                {"id": "rigging", "type": "rigging", "max_hp": 40, "ac": 12, "damage_threshold": 0},
                            ],
                            "mounted_weapons": [{"id": "gun_a", "name": "Deck Gun", "weapon_type": "cannon", "arc": "all", "range": 15, "to_hit": 25, "damage": 12}],
                            "crew": {"min_crew": 3, "recommended_crew": 8},
                            "boarding": {"boardable": True, "edges": ["port", "starboard"], "points": [{"id": "p1", "col": 5, "row": 5}]},
                        },
                        "ship_2": {
                            "id": "ship_2",
                            "name": "Blue Fang",
                            "blueprint_id": "sloop",
                            "parent_structure_id": "ship_b",
                            "facing_deg": 180,
                            "size": "medium",
                            "components": [{"id": "hull", "type": "hull", "max_hp": 200, "ac": 14, "damage_threshold": 0}],
                            "mounted_weapons": [],
                            "crew": {"min_crew": 3, "recommended_crew": 8},
                            "boarding": {"boardable": True, "edges": ["port", "starboard"], "points": [{"id": "p1", "col": target_col, "row": 5}]},
                        },
                    }
                },
            }
        )
        app._capture_canonical_map_state = lambda prefer_window=True: app._map_state.normalized()

        def _apply(state, hydrate_window=False):
            app._map_state = state.normalized()
            app._map_state_version = int(getattr(app, "_map_state_version", 0) or 0) + 1
            app._structure_contact_semantics_cache = {}
            app._selected_ship_summary_cache = {}

        app._apply_canonical_map_state = _apply
        return app

    def test_ship_engagement_state_normalization(self):
        app = self._build_app()
        ship = app._ship_instance_for_structure("ship_a")
        self.assertIsInstance(ship, dict)
        self.assertIn("engagement_state", ship)
        self.assertGreaterEqual(int((ship.get("hull_state") or {}).get("max_hp", 0) or 0), 1)
        self.assertGreaterEqual(int((ship.get("crew_state") or {}).get("active_crew", 0) or 0), 1)
        self.assertIn("gun_a", ship.get("weapon_state") or {})

    def test_ship_maneuver_success_and_blocked_reason(self):
        app = self._build_app(target_anchor_col=15)
        moved = app._ship_engagement_maneuver("ship_a", "move_forward", steps=1)
        self.assertTrue(moved.get("ok"))
        structure = app._ship_structure_for_id("ship_a")
        self.assertIsNotNone(structure)
        self.assertEqual(int(structure.anchor_col), 6)
        app._map_state = tracker_mod.MapState.from_dict(
            {
                **app._map_state.to_dict(),
                "obstacles": [{"col": 7, "row": 5}],
            }
        )
        blocked = app._ship_engagement_maneuver("ship_a", "move_forward", steps=1)
        self.assertFalse(blocked.get("ok"))
        self.assertEqual(blocked.get("reason"), "movement_blocked")

    def test_ship_weapon_action_applies_damage(self):
        app = self._build_app(target_anchor_col=10)
        random.seed(7)
        result = app._ship_engagement_fire_weapon("ship_a", "gun_a", "ship_b")
        self.assertTrue(result.get("ok"))
        self.assertTrue(result.get("hit"))
        target = app._ship_instance_for_structure("ship_b")
        self.assertIsInstance(target, dict)
        self.assertLess(int((target.get("hull_state") or {}).get("hp", 0) or 0), int((target.get("hull_state") or {}).get("max_hp", 0) or 0))

    def test_ship_ram_requires_contact_and_applies_damage(self):
        app = self._build_app(contact_target=True)
        result = app._ship_engagement_ram("ship_a", "ship_b")
        self.assertTrue(result.get("ok"))
        self.assertGreater(int(result.get("target_damage", 0) or 0), 0)
        self.assertGreater(int(result.get("source_damage", 0) or 0), 0)
        source = app._ship_instance_for_structure("ship_a")
        target = app._ship_instance_for_structure("ship_b")
        self.assertIsInstance(source, dict)
        self.assertIsInstance(target, dict)
        self.assertLess(int((source.get("hull_state") or {}).get("hp", 0) or 0), int((source.get("hull_state") or {}).get("max_hp", 0) or 0))
        self.assertLess(int((target.get("hull_state") or {}).get("hp", 0) or 0), int((target.get("hull_state") or {}).get("max_hp", 0) or 0))

    def test_lan_snapshot_exposes_engagement_fields(self):
        app = self._build_app()
        snap = app._lan_snapshot(include_static=False, hydrate_static=False)
        self.assertTrue(isinstance(snap.get("ships"), list) and snap.get("ships"))
        ship_payload = snap["ships"][0]
        self.assertIn("hull_hp", ship_payload)
        self.assertIn("movement_remaining", ship_payload)
        structure_entry = next(item for item in (snap.get("structures") or []) if item.get("id") == "ship_a")
        ship_state = structure_entry.get("ship_state") or {}
        self.assertIn("hull_hp", ship_state)
        self.assertIn("actions_remaining", ship_state)

    def test_ship_engagement_state_persists_in_map_presentation(self):
        app = self._build_app(target_anchor_col=12)
        _ = app._ship_engagement_maneuver("ship_a", "move_forward", steps=1)
        state_payload = app._map_state.to_dict()
        ship_instances = ((state_payload.get("presentation") or {}).get("ship_instances") or {})
        ship_1 = ship_instances.get("ship_1") or {}
        self.assertIn("engagement_state", ship_1)
        self.assertIn("movement_profile", ship_1)

    def test_ship_maneuver_multi_step_applies_canonical_state_once(self):
        app = self._build_app(target_anchor_col=20)
        calls = {"apply": 0}
        original_apply = app._apply_canonical_map_state

        def _counted_apply(state, hydrate_window=False):
            calls["apply"] += 1
            original_apply(state, hydrate_window=hydrate_window)

        app._apply_canonical_map_state = _counted_apply
        moved = app._ship_engagement_maneuver("ship_a", "move_forward", steps=3)
        self.assertTrue(moved.get("ok"))
        self.assertEqual(int(moved.get("moved_squares", 0) or 0), 3)
        self.assertEqual(calls["apply"], 1)

    def test_selected_ship_summary_cache_invalidates_after_map_mutation(self):
        app = self._build_app(target_anchor_col=15)
        calls = {"semantics": 0}
        original_semantics = app._structure_contact_semantics

        def _counted_semantics(*args, **kwargs):
            calls["semantics"] += 1
            return original_semantics(*args, **kwargs)

        app._structure_contact_semantics = _counted_semantics
        first = app._selected_ship_summary("ship_a")
        second = app._selected_ship_summary("ship_a")
        self.assertTrue(first.get("ok"))
        self.assertTrue(second.get("ok"))
        self.assertEqual(calls["semantics"], 1)
        moved = app._ship_engagement_maneuver("ship_a", "move_forward", steps=1)
        self.assertTrue(moved.get("ok"))
        refreshed = app._selected_ship_summary("ship_a")
        self.assertTrue(refreshed.get("ok"))
        self.assertEqual(calls["semantics"], 3)


if __name__ == "__main__":
    unittest.main()
