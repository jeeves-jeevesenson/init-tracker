import base64
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import dnd_initative_tracker as tracker_mod


TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO5xJ7sAAAAASUVORK5CYII="
)


class TokenImageOverlaySnapshotTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.base_dir = self.root / "app"
        self.data_dir = self.root / "data"
        (self.base_dir / "assets" / "profile_pictures").mkdir(parents=True, exist_ok=True)
        (self.base_dir / "Monsters" / "Images").mkdir(parents=True, exist_ok=True)
        (self.data_dir / "players").mkdir(parents=True, exist_ok=True)

    def _make_app(self):
        app = object.__new__(tracker_mod.InitiativeTracker)
        app._lan_grid_cols = 10
        app._lan_grid_rows = 10
        app._lan_obstacles = set()
        app._lan_positions = {1: (1, 1), 2: (2, 2)}
        app._lan_aoes = {}
        app._lan_rough_terrain = {}
        app._lan_next_aoe_id = 1
        app.current_cid = None
        app.round_num = 1
        app._display_order = lambda: []
        app._peek_next_turn_cid = lambda _cid: None
        app._oplog = lambda *args, **kwargs: None
        app._name_role_memory = {"Hero": "pc", "Wolf": "enemy"}
        app._lan_marks_for = lambda _c: []
        app._normalize_action_entries = lambda _entries, _kind: []
        app._token_color_payload = lambda _c: None
        app._token_border_color_payload = lambda _c: None
        app._has_condition = lambda _c, _name: False
        app._has_starry_wisp_reveal = lambda _c: False
        app._has_muddled_thoughts = lambda _c: False
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
        app._collect_combat_modifiers = lambda _c: {}
        app._creature_boarding_context = lambda *_args, **_kwargs: {}
        app._movement_mode_label = lambda _mode: "Normal"
        app._lan = type("LanStub", (), {"_cached_snapshot": {}})()
        app._player_yaml_name_map = {"Hero": self.data_dir / "players" / "hero.yaml"}
        app._map_state = tracker_mod.MapState.from_legacy(cols=10, rows=10, positions=app._lan_positions)
        app._capture_canonical_map_state = lambda prefer_window=True: app._map_state.normalized()
        app._apply_canonical_map_state = lambda state, hydrate_window=False: setattr(app, "_map_state", state.normalized())
        return app

    def test_lan_snapshot_includes_profile_and_monster_token_image_urls(self):
        (self.data_dir / "players" / "hero.yaml").write_text("name: Hero\n", encoding="utf-8")
        (self.base_dir / "assets" / "profile_pictures" / "hero.png").write_bytes(TINY_PNG)
        (self.base_dir / "Monsters" / "Images" / "wolf.png").write_bytes(TINY_PNG)

        app = self._make_app()
        app.combatants = {
            1: type("C", (), {"cid": 1, "name": "Hero", "hp": 12, "max_hp": 12, "speed": 30, "move_remaining": 30, "move_total": 30, "condition_stacks": []})(),
            2: type(
                "C",
                (),
                {
                    "cid": 2,
                    "name": "Wolf",
                    "hp": 11,
                    "max_hp": 11,
                    "speed": 40,
                    "move_remaining": 40,
                    "move_total": 40,
                    "monster_slug": "wolf",
                    "condition_stacks": [],
                },
            )(),
        }

        with mock.patch.dict("os.environ", {"INITTRACKER_DATA_DIR": str(self.data_dir)}, clear=False):
            with mock.patch.object(tracker_mod, "_app_base_dir", return_value=self.base_dir):
                snap = app._lan_snapshot(include_static=False, hydrate_static=False)

        by_cid = {int(unit["cid"]): unit for unit in snap["units"]}
        self.assertEqual(by_cid[1]["token_image_url"], "/assets/profile_pictures/hero.png")
        self.assertEqual(by_cid[2]["token_image_url"], "/monsters/images/wolf.png")


class TokenImageOverlayLanHtmlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = Path("assets/web/lan/index.html").read_text(encoding="utf-8")

    def test_lan_client_caches_and_draws_token_portraits(self):
        self.assertIn("const tokenPortraitCache = new Map();", self.html)
        self.assertIn("function ensureTokenPortrait(url){", self.html)
        self.assertIn('return ensureTokenPortrait(unit?.token_image_url || unit?.tokenImageUrl || "");', self.html)
        self.assertIn("function drawTokenPortrait(unit, x, y, radius){", self.html)
        self.assertIn("const portraitReady = drawTokenPortrait(u, x, y, r);", self.html)


if __name__ == "__main__":
    unittest.main()
