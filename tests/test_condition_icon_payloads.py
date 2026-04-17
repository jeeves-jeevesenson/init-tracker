import unittest
from pathlib import Path

import dnd_initative_tracker as tracker_mod


class ConditionIconPayloadTests(unittest.TestCase):
    def test_effect_icon_entries_include_badge_counts_and_durations(self):
        tracker = object.__new__(tracker_mod.base.InitiativeTracker)
        combatant = type(
            "C",
            (),
            {
                "condition_stacks": [
                    tracker_mod.base.ConditionStack(sid=1, ctype="star_advantage", remaining_turns=None),
                    tracker_mod.base.ConditionStack(sid=2, ctype="dot", remaining_turns=None, dot_type="burn"),
                    tracker_mod.base.ConditionStack(sid=3, ctype="dot", remaining_turns=None, dot_type="burn"),
                    tracker_mod.base.ConditionStack(sid=4, ctype="poisoned", remaining_turns=3),
                ],
                "exhaustion_level": 2,
            },
        )()

        entries = tracker._effect_icon_entries(combatant)
        by_key = {str(entry.get("key")): entry for entry in entries}

        self.assertEqual(by_key["star_advantage"]["icon"], "⭐")
        self.assertEqual(by_key["dot_burn"]["badge_text"], "2")
        self.assertEqual(by_key["poisoned"]["badge_text"], "3")
        self.assertEqual(by_key["exhaustion"]["badge_text"], "2")
        self.assertEqual(tracker._format_effects(combatant), "⭐ 🔥2 🤢3 🥱2")

    def test_lan_snapshot_exposes_condition_icons_alongside_marks(self):
        app = object.__new__(tracker_mod.InitiativeTracker)
        app._lan_grid_cols = 10
        app._lan_grid_rows = 10
        app._lan_obstacles = set()
        app._lan_positions = {1: (1, 1)}
        app._lan_aoes = {}
        app._lan_rough_terrain = {}
        app._lan_next_aoe_id = 1
        app.current_cid = None
        app.round_num = 1
        app._display_order = lambda: []
        app._peek_next_turn_cid = lambda _cid: None
        app._oplog = lambda *args, **kwargs: None
        app._name_role_memory = {"Hero": "pc"}
        app._lan_marks_for = tracker_mod.InitiativeTracker._lan_marks_for.__get__(app, tracker_mod.InitiativeTracker)
        app._normalize_action_entries = lambda _entries, _kind: []
        app._token_color_payload = lambda _c: None
        app._token_border_color_payload = lambda _c: None
        app._combatant_token_image_url = lambda _c: None
        app._has_condition = tracker_mod.InitiativeTracker._has_condition.__get__(app, tracker_mod.InitiativeTracker)
        app._has_starry_wisp_reveal = lambda _c: False
        app._has_muddled_thoughts = lambda _c: False
        app._collect_combat_modifiers = lambda _c: {}
        app._lan_seed_missing_positions = lambda positions, *_args: positions
        app._spell_presets_payload = lambda: []
        app._player_spell_config_payload = lambda: {}
        app._player_profiles_payload = lambda: {}
        app._player_resource_pools_payload = lambda: {}
        app._consumables_registry_list_payload = lambda: []
        app._load_beast_forms = lambda: []
        app._elemental_attunement_active = lambda _c: False
        app._json_safe = lambda value: value
        app._concentration_total_rounds_for_combatant = lambda _c: 0
        app._active_produce_flame_state = lambda _c: None
        app._beguiling_magic_window_remaining = lambda _c: 0.0
        app._lan_active_aura_contexts = lambda **_kwargs: []
        app._lan_reaction_debug_enabled = lambda: False
        app._movement_mode_label = lambda mode: str(mode or "normal")
        app._creature_boarding_context = lambda *_args, **_kwargs: {}
        app._lan = type("LanStub", (), {"_cached_snapshot": {}})()
        app._map_state = tracker_mod.MapState.from_legacy(cols=10, rows=10, positions=app._lan_positions)
        app._capture_canonical_map_state = lambda prefer_window=True: app._map_state.normalized()
        app._apply_canonical_map_state = lambda state, hydrate_window=False: setattr(app, "_map_state", state.normalized())
        app.combatants = {
            1: type(
                "C",
                (),
                {
                    "cid": 1,
                    "name": "Hero",
                    "hp": 12,
                    "max_hp": 12,
                    "speed": 30,
                    "move_remaining": 30,
                    "move_total": 30,
                    "condition_stacks": [
                        tracker_mod.base.ConditionStack(sid=1, ctype="dot", remaining_turns=None, dot_type="burn"),
                        tracker_mod.base.ConditionStack(sid=2, ctype="poisoned", remaining_turns=2),
                    ],
                    "exhaustion_level": 0,
                },
            )(),
        }

        snap = app._lan_snapshot(include_static=False, hydrate_static=False)
        unit = snap["units"][0]
        self.assertEqual(unit["marks"], "🔥 🤢2")
        self.assertEqual([entry["key"] for entry in unit["condition_icons"]], ["dot_burn", "poisoned"])
        self.assertEqual(unit["condition_icons"][1]["badge_text"], "2")


class ConditionIconLanHtmlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = Path("assets/web/lan/index.html").read_text(encoding="utf-8")

    def test_lan_client_defines_condition_icon_lookup_and_badge_renderer(self):
        self.assertIn("const conditionIconGlyphs = Object.freeze({", self.html)
        self.assertIn("function normalizeConditionIconEntries(unit){", self.html)
        self.assertIn("function effectOverlayEntriesForUnit(unit){", self.html)
        self.assertIn("function drawConditionIconBadges(unit, x, y, radius){", self.html)
        self.assertIn("const renderedConditionBadges = drawConditionIconBadges(u, x, y, r);", self.html)


if __name__ == "__main__":
    unittest.main()
