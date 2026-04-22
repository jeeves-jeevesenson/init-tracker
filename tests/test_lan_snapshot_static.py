import queue
import threading
import unittest

import dnd_initative_tracker as tracker_mod


class LanSnapshotStaticTests(unittest.TestCase):
    def test_static_data_payload_hydrates_presets_when_cache_empty(self):
        lan = object.__new__(tracker_mod.LanController)
        lan._cached_snapshot = {}
        lan._monster_choices_cache = []
        lan._monster_choices_cache_key = None

        live_presets = [{"name": "Aid", "slug": "aid", "level": 2}]

        class AppStub:
            _monster_specs = []

            def _spell_presets_payload(self_inner):
                return live_presets

        lan._tracker = AppStub()
        payload = lan._static_data_payload(planning=False)
        self.assertEqual(payload["spell_presets"], live_presets)

    def test_static_data_payload_prefers_cached_presets_when_present(self):
        lan = object.__new__(tracker_mod.LanController)
        cached = [{"name": "Bless", "slug": "bless", "level": 1}]
        lan._cached_snapshot = {"spell_presets": cached}
        lan._monster_choices_cache = []
        lan._monster_choices_cache_key = None

        class AppStub:
            _monster_specs = []

            def _spell_presets_payload(self_inner):
                raise AssertionError("should not hydrate when cache populated")

        lan._tracker = AppStub()
        payload = lan._static_data_payload(planning=False)
        self.assertEqual(payload["spell_presets"], cached)

    def test_monster_choices_payload_cache_uses_monster_specs_id_and_len(self):
        lan = object.__new__(tracker_mod.LanController)

        class Spec:
            def __init__(self, name, filename):
                self.name = name
                self.filename = filename
                self.mtype = "beast"
                self.hp = 9
                self.speed = 30
                self.swim_speed = 0
                self.fly_speed = 0
                self.burrow_speed = 0
                self.climb_speed = 0
                self.raw_data = {"ac": 12, "abilities": {"str": 14, "dex": 13, "con": 12, "int": 10, "wis": 11, "cha": 8}}

        class AppStub:
            def __init__(self):
                self._monster_specs = [Spec("Wolf", "wolf.yaml")]

        lan._tracker = AppStub()
        lan._monster_choices_cache = []
        lan._monster_choices_cache_key = None

        first = lan._monster_choices_payload()
        second = lan._monster_choices_payload()
        self.assertIs(first, second)

        lan._tracker._monster_specs = list(lan._tracker._monster_specs)
        third = lan._monster_choices_payload()
        self.assertIsNot(third, second)

        lan._tracker._monster_specs.append(Spec("Bear", "bear.yaml"))
        fourth = lan._monster_choices_payload()
        self.assertIsNot(fourth, third)
        self.assertEqual(len(fourth), 2)

    def test_next_turn_notification_target_skips_skipped_combatants(self):
        lan = object.__new__(tracker_mod.LanController)

        combatants = [
            type("C", (), {"cid": 1})(),
            type("C", (), {"cid": 2})(),
            type("C", (), {"cid": 3})(),
        ]

        class TrackerStub:
            def _display_order(self):
                return combatants

            def _should_skip_turn(self, cid):
                return int(cid) == 2

        lan._tracker = TrackerStub()

        self.assertEqual(lan._next_turn_notification_target(1), 3)

    def test_dispatch_turn_notification_sends_active_and_up_next_payloads(self):
        lan = object.__new__(tracker_mod.LanController)
        sent_payloads = []
        removed = []

        class TrackerStub:
            def _pc_name_for(self, cid):
                return {1: "Alice", 2: "Bob"}.get(int(cid), f"#{cid}")

            def _display_order(self):
                return [type("C", (), {"cid": 1})(), type("C", (), {"cid": 2})()]

            def _should_skip_turn(self, _cid):
                return False

        lan._tracker = TrackerStub()
        lan._subscriptions_for_cid = lambda cid: [{"endpoint": f"https://example.com/{cid}", "keys": {"p256dh": "a", "auth": "b"}}]
        lan._send_push_notifications = lambda subs, payload: sent_payloads.append((subs, payload)) or []
        lan._remove_push_subscription = lambda cid, endpoint: removed.append((cid, endpoint))

        lan._dispatch_turn_notification(1, 2, 4)

        self.assertEqual(len(sent_payloads), 2)
        self.assertEqual(sent_payloads[0][1]["title"], "Your turn!")
        self.assertEqual(sent_payloads[0][1]["body"], "Alice is up (round 2, turn 4).")
        self.assertEqual(sent_payloads[1][1]["title"], "You're up next")
        self.assertEqual(sent_payloads[1][1]["body"], "Alice's turn started — you're next. Plan your move.")
        self.assertEqual(removed, [])


    def test_dispatch_turn_notification_still_sends_when_next_lookup_fails(self):
        lan = object.__new__(tracker_mod.LanController)
        sent_payloads = []

        class TrackerStub:
            def _pc_name_for(self, cid):
                return {1: "Alice"}.get(int(cid), f"#{cid}")

        lan._tracker = TrackerStub()
        lan._subscriptions_for_cid = lambda cid: [{"endpoint": f"https://example.com/{cid}", "keys": {"p256dh": "a", "auth": "b"}}]
        lan._send_push_notifications = lambda subs, payload: sent_payloads.append((subs, payload)) or []
        lan._remove_push_subscription = lambda *_args, **_kwargs: None
        lan._next_turn_notification_target = lambda _cid: (_ for _ in ()).throw(RuntimeError("boom"))

        lan._dispatch_turn_notification(1, 2, 4)

        self.assertEqual(len(sent_payloads), 1)
        self.assertEqual(sent_payloads[0][1]["title"], "Your turn!")

    def test_include_static_false_reuses_cached_static_payload(self):
        app = object.__new__(tracker_mod.InitiativeTracker)
        app._lan_grid_cols = 10
        app._lan_grid_rows = 10
        app._lan_obstacles = set()
        app._lan_positions = {}
        app._lan_aoes = {}
        app._lan_rough_terrain = {}
        app._lan_next_aoe_id = 1
        app.combatants = {}
        app.current_cid = None
        app.round_num = 1
        app._display_order = lambda: []
        app._oplog = lambda *args, **kwargs: None

        app._spell_presets_payload = lambda: (_ for _ in ()).throw(AssertionError("spell presets should not be called"))
        app._player_spell_config_payload = lambda: (_ for _ in ()).throw(AssertionError("player spells should not be called"))
        app._player_profiles_payload = lambda: (_ for _ in ()).throw(AssertionError("player profiles should not be called"))
        app._player_resource_pools_payload = lambda: {"Alice": [{"id": "wild_shape", "current": 0}]}
        app._load_beast_forms = lambda: (_ for _ in ()).throw(AssertionError("beast forms should not be called"))

        app._lan = type("LanStub", (), {"_cached_snapshot": {
            "spell_presets": [{"name": "cached"}],
            "player_spells": {"Alice": {"spells": []}},
            "player_profiles": {"Alice": {"name": "Alice"}},
            "resource_pools": {"Alice": [{"id": "wild_shape", "current": 1}]},
            "beast_forms": [{"id": "wolf"}],
        }})()

        snap = app._lan_snapshot(include_static=False)
        self.assertEqual(snap["spell_presets"], [{"name": "cached"}])
        self.assertEqual(snap["player_spells"], {"Alice": {"spells": []}})
        self.assertEqual(snap["player_profiles"], {"Alice": {"name": "Alice"}})
        self.assertEqual(snap["resource_pools"], {"Alice": [{"id": "wild_shape", "current": 0}]})
        self.assertEqual(snap["beast_forms"], [{"id": "wolf"}])

    def test_include_static_false_without_hydration_skips_static_builders(self):
        app = object.__new__(tracker_mod.InitiativeTracker)
        app._lan_grid_cols = 10
        app._lan_grid_rows = 10
        app._lan_obstacles = set()
        app._lan_positions = {}
        app._lan_aoes = {}
        app._lan_rough_terrain = {}
        app._lan_next_aoe_id = 1
        app.combatants = {}
        app.current_cid = None
        app.round_num = 1
        app._display_order = lambda: []
        app._oplog = lambda *args, **kwargs: None
        app._player_yaml_refresh_interval_s = 1.0
        app._lan_resource_pools_last_build = 0.0

        app._spell_presets_payload = lambda: (_ for _ in ()).throw(AssertionError("spell presets should not be called"))
        app._player_spell_config_payload = lambda: (_ for _ in ()).throw(AssertionError("player spells should not be called"))
        app._player_profiles_payload = lambda: (_ for _ in ()).throw(AssertionError("player profiles should not be called"))
        app._player_resource_pools_payload = lambda: (_ for _ in ()).throw(AssertionError("resource pools should not be called"))
        app._load_beast_forms = lambda: (_ for _ in ()).throw(AssertionError("beast forms should not be called"))

        app._lan = type("LanStub", (), {"_cached_snapshot": {}})()

        snap = app._lan_snapshot(include_static=False, hydrate_static=False)
        self.assertEqual(snap["spell_presets"], [])
        self.assertEqual(snap["player_spells"], {})
        self.assertEqual(snap["player_profiles"], {})
        self.assertEqual(snap["resource_pools"], {})
        self.assertEqual(snap["beast_forms"], [])

    def test_include_static_false_reuses_cached_resource_pools_within_refresh_interval(self):
        app = object.__new__(tracker_mod.InitiativeTracker)
        app._lan_grid_cols = 10
        app._lan_grid_rows = 10
        app._lan_obstacles = set()
        app._lan_positions = {}
        app._lan_aoes = {}
        app._lan_rough_terrain = {}
        app._lan_next_aoe_id = 1
        app.combatants = {}
        app.current_cid = None
        app.round_num = 1
        app._display_order = lambda: []
        app._oplog = lambda *args, **kwargs: None
        app._player_yaml_refresh_interval_s = 1.0
        app._lan_resource_pools_last_build = tracker_mod.time.monotonic()

        app._spell_presets_payload = lambda: []
        app._player_spell_config_payload = lambda: {}
        app._player_profiles_payload = lambda: {}
        app._player_resource_pools_payload = lambda: (_ for _ in ()).throw(AssertionError("resource pools should not be called"))
        app._load_beast_forms = lambda: []

        cached_resource_pools = {"Alice": [{"id": "wild_shape", "current": 1}]}
        app._lan = type("LanStub", (), {"_cached_snapshot": {"resource_pools": cached_resource_pools}})()

        snap = app._lan_snapshot(include_static=False)
        self.assertIs(snap["resource_pools"], cached_resource_pools)

    def test_view_only_state_payload_includes_grid_and_terrain(self):
        lan = object.__new__(tracker_mod.LanController)
        lan._cached_snapshot = {
            "grid": {"cols": 5, "rows": 6, "feet_per_square": 5},
            "rough_terrain": [{"col": 0, "row": 1}],
            "obstacles": [{"col": 2, "row": 3}],
            "units": [],
        }
        lan._cached_pcs = []
        lan._cid_to_host = {}
        lan._clients_lock = threading.Lock()

        payload = lan._view_only_state_payload({"units": []})

        self.assertEqual(payload["grid"], {"cols": 5, "rows": 6, "feet_per_square": 5})
        self.assertEqual(payload["rough_terrain"], [{"col": 0, "row": 1}])
        self.assertEqual(payload["obstacles"], [{"col": 2, "row": 3}])

    def test_lan_snapshot_structures_include_contact_semantics(self):
        app = object.__new__(tracker_mod.InitiativeTracker)
        app._lan_grid_cols = 20
        app._lan_grid_rows = 20
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
        app._map_state = tracker_mod.MapState.from_dict(
            {
                "grid": {"cols": 20, "rows": 20, "feet_per_square": 5},
                "structures": [
                    {
                        "id": "a",
                        "kind": "ship_hull",
                        "anchor_col": 5,
                        "anchor_row": 5,
                        "occupied_cells": [{"col": 5, "row": 5}, {"col": 6, "row": 5}],
                        "payload": {"name": "Black Pearl", "boardable": True},
                    },
                    {
                        "id": "b",
                        "kind": "ship_hull",
                        "anchor_col": 7,
                        "anchor_row": 5,
                        "occupied_cells": [{"col": 7, "row": 5}],
                        "payload": {"name": "Interceptor", "allow_boarding": True},
                    },
                ],
                "presentation": {
                    "ship_instances": {
                        "ship_1": {
                            "id": "ship_1",
                            "name": "Black Pearl",
                            "blueprint_id": "sloop",
                            "parent_structure_id": "a",
                            "facing_deg": 90,
                            "components": [{"id": "hull"}],
                            "mounted_weapons": [{"id": "cannon_a"}],
                        }
                    },
                    "boarding_links": [
                        {
                            "id": "boarding_link_1",
                            "source_id": "a",
                            "target_id": "b",
                            "status": "active",
                        }
                    ],
                },
                "features": [
                    {
                        "id": "f1",
                        "col": 6,
                        "row": 5,
                        "kind": "barrel",
                        "payload": {"name": "Deck Barrel"},
                    }
                ],
            }
        )
        app._capture_canonical_map_state = lambda prefer_window=True: app._map_state.normalized()
        app._apply_canonical_map_state = lambda state, hydrate_window=False: setattr(app, "_map_state", state.normalized())

        snap = app._lan_snapshot(include_static=False, hydrate_static=False)
        structure_a = next(item for item in snap["structures"] if item["id"] == "a")
        semantics = structure_a.get("contact_semantics") or {}
        self.assertEqual(semantics.get("boardable_structure_ids"), ["b"])
        self.assertEqual((semantics.get("boardable_structures") or [])[0]["name"], "Interceptor")
        self.assertEqual(semantics.get("active_boarding_structure_ids"), ["b"])
        self.assertEqual((semantics.get("boarding_links") or [])[0]["id"], "boarding_link_1")
        ship_state = structure_a.get("ship_state") or {}
        self.assertEqual(ship_state.get("blueprint_id"), "sloop")
        self.assertEqual(ship_state.get("weapon_count"), 1)
        self.assertEqual(ship_state.get("active_boarding_count"), 1)
        self.assertEqual((snap.get("ships") or [])[0]["id"], "ship_1")
        self.assertEqual((snap.get("boarding_links") or [])[0]["id"], "boarding_link_1")
        self.assertEqual((snap.get("active_boarding_links") or [])[0]["id"], "boarding_link_1")
        feature = next(item for item in snap["features"] if item["id"] == "f1")
        self.assertEqual(feature.get("preset_id"), "barrel")
        self.assertEqual(feature.get("display_name"), "Deck Barrel")

    def test_lan_snapshot_units_include_boarding_context(self):
        app = object.__new__(tracker_mod.InitiativeTracker)
        app._lan_grid_cols = 20
        app._lan_grid_rows = 20
        app._lan_obstacles = set()
        app._lan_positions = {101: (5, 5)}
        app._lan_aoes = {}
        app._lan_rough_terrain = {}
        app._lan_next_aoe_id = 1
        app.current_cid = 101
        app.round_num = 1
        app._display_order = lambda: [type("OrderC", (), {"cid": 101})()]
        app._peek_next_turn_cid = lambda _cid: None
        app._oplog = lambda *args, **kwargs: None
        app._name_role_memory = {"Boarder": "pc"}
        app._lan_marks_for = lambda _c: []
        app._normalize_action_entries = lambda _entries, _kind: []
        app._token_color_payload = lambda _c: None
        app._token_border_color_payload = lambda _c: None
        app._has_condition = lambda _c, _name: False
        app._collect_combat_modifiers = lambda _c: {}
        app._lan_seed_missing_positions = lambda positions, *_args: positions
        app._build_you_payload = lambda _ws_id=None: {"claimed_cid": None, "claimed_name": None}
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
        app._lan = type("LanStub", (), {"_cached_snapshot": {}})()
        app.combatants = {
            101: type("C", (), {"cid": 101, "name": "Boarder", "hp": 9, "max_hp": 9, "speed": 30, "move_remaining": 30, "move_total": 30})(),
        }
        app._map_state = tracker_mod.MapState.from_dict(
            {
                "grid": {"cols": 20, "rows": 20, "feet_per_square": 5},
                "token_positions": [{"cid": 101, "col": 5, "row": 5}],
                "structures": [
                    {
                        "id": "a",
                        "kind": "ship_hull",
                        "anchor_col": 5,
                        "anchor_row": 5,
                        "occupied_cells": [{"col": 5, "row": 5}, {"col": 6, "row": 5}],
                        "payload": {
                            "name": "Ship A",
                            "ship_instance_id": "ship_1",
                            "boardable": True,
                            "boarding_points": [{"id": "p", "col": 6, "row": 5}],
                        },
                    },
                    {
                        "id": "b",
                        "kind": "ship_hull",
                        "anchor_col": 7,
                        "anchor_row": 5,
                        "occupied_cells": [{"col": 7, "row": 5}],
                        "payload": {
                            "name": "Ship B",
                            "ship_instance_id": "ship_2",
                            "allow_boarding": True,
                            "boarding_points": [{"id": "p", "col": 7, "row": 5}],
                        },
                    },
                ],
                "presentation": {
                    "boarding_links": [{"id": "boarding_link_1", "source_id": "a", "target_id": "b", "status": "active"}],
                },
            }
        )
        app._capture_canonical_map_state = lambda prefer_window=True: app._map_state.normalized()
        app._apply_canonical_map_state = lambda state, hydrate_window=False: setattr(app, "_map_state", state.normalized())

        snap = app._lan_snapshot(include_static=False, hydrate_static=False)
        unit = (snap.get("units") or [])[0]
        self.assertTrue(unit.get("on_ship"))
        self.assertEqual(unit.get("ship_structure_id"), "a")
        self.assertIn("b", unit.get("traversable_boarding_target_ids") or [])
        active_boarding = snap.get("active_creature_boarding") or {}
        self.assertTrue(active_boarding.get("on_ship"))
        self.assertEqual(active_boarding.get("source_structure_id"), "a")

    def test_lan_snapshot_units_expose_new_condition_and_create_undead_command_flags(self):
        app = object.__new__(tracker_mod.InitiativeTracker)
        app._lan_grid_cols = 20
        app._lan_grid_rows = 20
        app._lan_obstacles = set()
        app._lan_positions = {101: (5, 5)}
        app._lan_aoes = {}
        app._lan_rough_terrain = {}
        app._lan_next_aoe_id = 1
        app.current_cid = 101
        app.round_num = 2
        app.turn_num = 4
        app._display_order = lambda: [type("OrderC", (), {"cid": 101})()]
        app._peek_next_turn_cid = lambda _cid: None
        app._oplog = lambda *args, **kwargs: None
        app._name_role_memory = {"Boarder": "pc"}
        app._lan_marks_for = lambda _c: []
        app._normalize_action_entries = lambda entries, _kind: list(entries or [])
        app._token_color_payload = lambda _c: None
        app._token_border_color_payload = lambda _c: None
        app._has_condition = tracker_mod.InitiativeTracker._has_condition.__get__(app, tracker_mod.InitiativeTracker)
        app._collect_combat_modifiers = tracker_mod.InitiativeTracker._collect_combat_modifiers.__get__(app, tracker_mod.InitiativeTracker)
        app._has_starry_wisp_reveal = tracker_mod.InitiativeTracker._has_starry_wisp_reveal.__get__(app, tracker_mod.InitiativeTracker)
        app._has_muddled_thoughts = tracker_mod.InitiativeTracker._has_muddled_thoughts.__get__(app, tracker_mod.InitiativeTracker)
        app._is_create_undead_uncommanded_this_turn = tracker_mod.InitiativeTracker._is_create_undead_uncommanded_this_turn.__get__(app, tracker_mod.InitiativeTracker)
        app._lan_seed_missing_positions = lambda positions, *_args: positions
        app._build_you_payload = lambda _ws_id=None: {"claimed_cid": None, "claimed_name": None}
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
        app._map_state = tracker_mod.MapState.from_dict({"grid": {"cols": 20, "rows": 20, "feet_per_square": 5}, "token_positions": []})
        app._capture_canonical_map_state = lambda prefer_window=True: app._map_state.normalized()
        app._apply_canonical_map_state = lambda state, hydrate_window=False: setattr(app, "_map_state", state.normalized())
        app.combatants = {
            101: type(
                "C",
                (),
                {
                    "cid": 101,
                    "name": "Boarder",
                    "hp": 9,
                    "max_hp": 9,
                    "speed": 30,
                    "move_remaining": 30,
                    "move_total": 30,
                    "action_remaining": 1,
                    "action_total": 1,
                    "attack_resource_remaining": 0,
                    "bonus_action_remaining": 1,
                    "reaction_remaining": 1,
                    "spell_cast_remaining": 1,
                    "actions": [{"name": "Attack"}],
                    "bonus_actions": [],
                    "reactions": [],
                    "is_spellcaster": False,
                    "is_wild_shaped": False,
                    "condition_stacks": [
                        tracker_mod.base.ConditionStack(sid=1, ctype="invisible", remaining_turns=None),
                        tracker_mod.base.ConditionStack(sid=2, ctype="starry_wisp_revealed", remaining_turns=1),
                        tracker_mod.base.ConditionStack(sid=3, ctype="otto_dancing", remaining_turns=None),
                        tracker_mod.base.ConditionStack(sid=4, ctype="muddled_thoughts", remaining_turns=3),
                    ],
                    "ongoing_spell_effects": [],
                    "saving_throws": {},
                    "ability_mods": {},
                    "summon_requires_command": True,
                    "summon_commanded_turn": [2, 4],
                },
            )(),
        }

        snap = app._lan_snapshot(include_static=False, hydrate_static=False)
        unit = (snap.get("units") or [])[0]
        self.assertTrue(bool(unit.get("starry_wisp_revealed")))
        self.assertTrue(bool(unit.get("otto_dancing")))
        self.assertTrue(bool(unit.get("muddled_thoughts")))
        self.assertTrue(bool(unit.get("invisibility_suppressed")))
        self.assertFalse(bool(unit.get("is_invisible")))
        self.assertTrue(bool(unit.get("summon_requires_command")))
        self.assertTrue(bool(unit.get("summon_commanded_this_turn")))
        self.assertEqual(unit.get("summon_commanded_turn"), [2, 4])

    def test_lan_snapshot_exposes_ship_render_metadata_and_texture_candidates(self):
        app = object.__new__(tracker_mod.InitiativeTracker)
        app._lan_grid_cols = 20
        app._lan_grid_rows = 20
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
        app._ship_render_asset_path_for_key = lambda _key: None
        app._map_state = tracker_mod.MapState.from_dict(
            {
                "grid": {"cols": 20, "rows": 20, "feet_per_square": 5},
                "structures": [
                    {
                        "id": "ship_a",
                        "kind": "ship_hull",
                        "anchor_col": 5,
                        "anchor_row": 5,
                        "occupied_cells": [{"col": 5, "row": 5}, {"col": 6, "row": 5}],
                        "payload": {
                            "name": "Deckship",
                            "ship_instance_id": "ship_1",
                            "ship_render": {"deck_texture_key": "ship_deck_wood"},
                            "ship_local_space": {"facing_mode": "rotate_90"},
                            "ship_deck_regions": [{"id": "main", "label": "Main Deck", "cells": [{"col": 5, "row": 5}]}],
                        },
                    }
                ],
                "presentation": {
                    "ship_instances": {
                        "ship_1": {
                            "id": "ship_1",
                            "name": "Deckship",
                            "blueprint_id": "sloop",
                            "parent_structure_id": "ship_a",
                            "facing_deg": 0,
                            "components": [{"id": "hull"}],
                            "mounted_weapons": [],
                        }
                    }
                },
            }
        )
        app._capture_canonical_map_state = lambda prefer_window=True: app._map_state.normalized()
        app._apply_canonical_map_state = lambda state, hydrate_window=False: setattr(app, "_map_state", state.normalized())

        snap = app._lan_snapshot(include_static=False, hydrate_static=False)
        ship_entry = next(item for item in (snap.get("structures") or []) if item.get("id") == "ship_a")
        self.assertEqual(ship_entry.get("occupied_cells"), [{"col": 5, "row": 5}, {"col": 6, "row": 5}])
        self.assertEqual((ship_entry.get("ship_local_space") or {}).get("facing_mode"), "rotate_90")
        self.assertEqual((ship_entry.get("ship_deck_regions") or [])[0]["id"], "main")
        ship_render = ship_entry.get("ship_render") or {}
        self.assertEqual(ship_render.get("deck_texture_key"), "ship_deck_wood")
        self.assertTrue(any(str(url).endswith(".png") for url in (ship_render.get("deck_texture_url_candidates") or [])))

    def test_lan_asset_url_variants_keep_original_and_deterministic_extension_order(self):
        variants = tracker_mod.InitiativeTracker._lan_asset_url_variants("/assets/ships/art/WOOD.PNG?v=1")
        self.assertEqual(
            variants,
            [
                "/assets/ships/art/WOOD.PNG?v=1",
                "/assets/ships/art/WOOD.avif?v=1",
                "/assets/ships/art/WOOD.webp?v=1",
                "/assets/ships/art/WOOD.png?v=1",
                "/assets/ships/art/WOOD.jpg?v=1",
                "/assets/ships/art/WOOD.jpeg?v=1",
            ],
        )

    def test_lan_ship_deck_texture_urls_preserve_supplied_candidates(self):
        app = object.__new__(tracker_mod.InitiativeTracker)
        app._ship_render_asset_path_for_key = lambda _key: "assets/ships/art/wood.avif"
        urls = app._lan_ship_deck_texture_urls(
            {
                "deck_texture_key": "ship_deck_wood",
                "deck_texture_url_candidates": [
                    "/assets/custom/deck.PNG?rev=1",
                    "/assets/custom/deck.PNG?rev=1",
                ],
            }
        )
        self.assertGreaterEqual(len(urls), 6)
        self.assertEqual(urls[0], "/assets/custom/deck.PNG?rev=1")
        self.assertEqual(urls.count("/assets/custom/deck.PNG?rev=1"), 1)
        self.assertIn("/assets/custom/deck.avif?rev=1", urls)
        self.assertIn("/assets/ships/art/wood.avif", urls)

    def test_units_include_max_hp_field(self):
        app = object.__new__(tracker_mod.InitiativeTracker)
        app._lan_grid_cols = 10
        app._lan_grid_rows = 10
        app._lan_obstacles = set()
        app._lan_positions = {}
        app._lan_aoes = {}
        app._lan_rough_terrain = {}
        app.current_cid = None
        app.round_num = 1
        app._display_order = lambda: [1]
        app._oplog = lambda *args, **kwargs: None
        app._name_role_memory = {"alice": "pc"}
        app._lan_marks_for = lambda _c: []
        app._normalize_action_entries = lambda _entries, _kind: []
        app._token_color_payload = lambda _c: None
        app._has_condition = lambda _c, _name: False
        app._lan_seed_missing_positions = lambda positions, *_args: positions
        app._build_you_payload = lambda _ws_id=None: {"claimed_cid": None, "claimed_name": None}
        app._spell_presets_payload = lambda: []
        app._player_spell_config_payload = lambda: {}
        app._player_profiles_payload = lambda: {}
        app._player_resource_pools_payload = lambda: {}
        app._lan = type("LanStub", (), {"_cached_snapshot": None})()
        app.combatants = {
            1: type("C", (), {"cid": 1, "name": "Alice", "hp": 7, "max_hp": 22})(),
        }

        snap = app._lan_snapshot(include_static=False)

        self.assertEqual(snap["units"][0]["hp"], 7)
        self.assertEqual(snap["units"][0]["max_hp"], 22)
        self.assertEqual(snap["units"][0]["facing_deg"], 0)
        self.assertEqual(snap["units"][0]["reactions"], [])
        self.assertEqual(snap["units"][0]["action_total"], 1)


    def test_units_include_concentration_timing_fields(self):
        app = object.__new__(tracker_mod.InitiativeTracker)
        app._lan_grid_cols = 10
        app._lan_grid_rows = 10
        app._lan_obstacles = set()
        app._lan_positions = {}
        app._lan_aoes = {}
        app._lan_rough_terrain = {}
        app.current_cid = 1
        app.round_num = 3
        app._display_order = lambda: [1]
        app._oplog = lambda *args, **kwargs: None
        app._name_role_memory = {"alice": "pc"}
        app._lan_marks_for = lambda _c: []
        app._normalize_action_entries = lambda _entries, _kind: []
        app._token_color_payload = lambda _c: None
        app._has_condition = lambda _c, _name: False
        app._lan_seed_missing_positions = lambda positions, *_args: positions
        app._build_you_payload = lambda _ws_id=None: {"claimed_cid": None, "claimed_name": None}
        app._spell_presets_payload = lambda: []
        app._player_spell_config_payload = lambda: {}
        app._player_profiles_payload = lambda: {}
        app._player_resource_pools_payload = lambda: {}
        app._lan = type("LanStub", (), {"_cached_snapshot": None})()
        app._concentration_total_rounds_for_combatant = lambda _c: 10
        app._beguiling_magic_window_remaining = lambda _c: 0.0

        app.combatants = {
            1: type(
                "C",
                (),
                {
                    "cid": 1,
                    "name": "Alice",
                    "hp": 7,
                    "max_hp": 22,
                    "concentrating": True,
                    "concentration_spell": "web",
                    "concentration_started_turn": (2, 4),
                },
            )(),
        }

        snap = app._lan_snapshot(include_static=False)

        self.assertTrue(snap["units"][0]["concentrating"])
        self.assertEqual(snap["units"][0]["concentration_spell"], "web")
        self.assertEqual(snap["units"][0]["concentration_started_turn"], [2, 4])
        self.assertEqual(snap["units"][0]["concentration_total_rounds"], 10)

    def test_units_include_action_total_from_combatant(self):
        app = object.__new__(tracker_mod.InitiativeTracker)
        app._lan_grid_cols = 10
        app._lan_grid_rows = 10
        app._lan_obstacles = set()
        app._lan_positions = {}
        app._lan_aoes = {}
        app._lan_rough_terrain = {}
        app.current_cid = None
        app.round_num = 1
        app._display_order = lambda: [1]
        app._oplog = lambda *args, **kwargs: None
        app._name_role_memory = {"alice": "pc"}
        app._lan_marks_for = lambda _c: []
        app._normalize_action_entries = lambda _entries, _kind: []
        app._token_color_payload = lambda _c: None
        app._has_condition = lambda _c, _name: False
        app._lan_seed_missing_positions = lambda positions, *_args: positions
        app._build_you_payload = lambda _ws_id=None: {"claimed_cid": None, "claimed_name": None}
        app._spell_presets_payload = lambda: []
        app._player_spell_config_payload = lambda: {}
        app._player_profiles_payload = lambda: {}
        app._player_resource_pools_payload = lambda: {}
        app._lan = type("LanStub", (), {"_cached_snapshot": None})()
        app.combatants = {
            1: type("C", (), {"cid": 1, "name": "Alice", "hp": 7, "max_hp": 22, "action_total": 3})(),
        }

        snap = app._lan_snapshot(include_static=False)

        self.assertEqual(snap["units"][0]["action_total"], 3)


    def test_tick_uses_idle_interval_without_clients(self):
        lan = object.__new__(tracker_mod.LanController)
        lan._actions = queue.Queue()
        lan._clients_lock = threading.Lock()
        lan._clients = {}
        lan._polling = True
        lan._active_poll_interval_ms = 120
        lan._idle_poll_interval_ms = 350
        lan._idle_cache_refresh_interval_s = 1.0
        lan._last_idle_cache_refresh = 0.0
        lan._cached_snapshot = {}
        lan._cached_pcs = []
        lan._battle_log_subscribers = set()
        lan._log_lan_exception = lambda *args, **kwargs: None

        scheduled = []
        call_counts = {"snap": 0}

        class AppStub:
            def _lan_snapshot(self, include_static=False, hydrate_static=True):
                call_counts["snap"] += 1
                return {"grid": {}}

            def _lan_claimable(self):
                return []

            def after(self, ms, fn):
                scheduled.append((ms, fn))

        lan._tracker = AppStub()

        lan._tick()

        self.assertEqual(call_counts["snap"], 1)
        self.assertEqual(len(scheduled), 1)
        self.assertEqual(scheduled[0][0], 350)

    def test_tick_throttles_static_payload_checks_when_idle_with_clients(self):
        lan = object.__new__(tracker_mod.LanController)
        lan._actions = queue.Queue()
        lan._clients_lock = threading.Lock()
        lan._clients = {1: object()}
        lan._polling = False
        lan._active_poll_interval_ms = 120
        lan._idle_poll_interval_ms = 350
        lan._idle_cache_refresh_interval_s = 1.0
        lan._last_idle_cache_refresh = 0.0
        lan._cached_snapshot = {"grid": {"cols": 8, "rows": 8}, "units": [], "obstacles": []}
        lan._cached_pcs = []
        lan._battle_log_subscribers = set()
        lan._log_lan_exception = lambda *args, **kwargs: None
        lan._move_debug_log = lambda *args, **kwargs: None
        lan._broadcast_grid_update = lambda *_args, **_kwargs: None
        lan._build_turn_update = lambda *_args, **_kwargs: {}
        lan._build_unit_updates = lambda *_args, **_kwargs: (None, [])
        lan._build_terrain_patch = lambda *_args, **_kwargs: None
        lan._apply_terrain_patch_to_map = lambda *_args, **_kwargs: None
        lan._build_aoe_patch = lambda *_args, **_kwargs: None
        lan._broadcast_payload = lambda *_args, **_kwargs: None
        lan._grid_last_sent = None
        lan._grid_version = 0
        lan._last_snapshot = None
        lan._last_static_json = None
        lan._last_static_check_ts = 0.0
        lan._static_check_interval_s = 10.0

        static_call_count = {"count": 0}

        def _fake_static_data_payload():
            static_call_count["count"] += 1
            return {
                "spell_presets": [],
                "player_spells": {},
                "player_profiles": {},
                "resource_pools": {},
                "monster_choices": [],
                "conditions": [],
                "dice_types": [],
                "token_colours": [],
            }

        lan._static_data_payload = _fake_static_data_payload

        class AppStub:
            def _lan_snapshot(self, include_static=False, hydrate_static=True):
                return {
                    "grid": {"cols": 8, "rows": 8},
                    "units": [],
                    "obstacles": [],
                    "rough_terrain": [],
                    "active_cid": None,
                    "round_num": 1,
                }

            def _lan_claimable(self):
                return []

            def _lan_apply_action(self, _msg):
                return None

            def after(self, _ms, _fn):
                return None

        lan._tracker = AppStub()

        lan._tick()
        lan._tick()
        self.assertEqual(static_call_count["count"], 1)

        lan._actions.put({"type": "noop"})
        lan._tick()
        self.assertEqual(static_call_count["count"], 2)

    def test_build_map_delta_envelope_includes_terrain_and_token_updates(self):
        lan = object.__new__(tracker_mod.LanController)
        prev = {
            "grid": {"cols": 8, "rows": 8, "feet_per_square": 5},
            "rough_terrain": [],
            "obstacles": [],
            "units": [{"cid": 1, "pos": {"col": 1, "row": 1}}],
            "aoes": [],
        }
        curr = {
            "grid": {"cols": 8, "rows": 8, "feet_per_square": 5},
            "rough_terrain": [{"col": 2, "row": 3, "color": "#fff", "movement_type": "ground", "is_swim": False, "is_rough": True}],
            "obstacles": [{"col": 4, "row": 4}],
            "units": [{"cid": 1, "pos": {"col": 5, "row": 5}}],
            "aoes": [{"aid": 10, "kind": "circle"}],
        }

        envelope = lan._build_map_delta_envelope(prev, curr)
        self.assertEqual(envelope["type"], "map_delta")
        delta = envelope["delta"]
        self.assertEqual(delta["terrain_cells"]["upserts"][0]["col"], 2)
        self.assertEqual(delta["obstacles"]["upserts"][0]["col"], 4)
        self.assertEqual(delta["tokens"]["upserts"][0]["cid"], 1)

    def test_build_map_delta_envelope_includes_canonical_layers(self):
        lan = object.__new__(tracker_mod.LanController)
        prev = {
            "grid": {"cols": 8, "rows": 8, "feet_per_square": 5},
            "rough_terrain": [],
            "obstacles": [],
            "units": [{"cid": 1, "pos": {"col": 1, "row": 1}}],
            "aoes": [],
            "features": [{"id": "f1", "col": 1, "row": 1, "kind": "crate", "payload": {}}],
            "hazards": [{"id": "h1", "col": 2, "row": 2, "kind": "fire", "payload": {}}],
            "structures": [{"id": "s1", "kind": "ship_hull", "anchor_col": 0, "anchor_row": 0, "occupied_cells": [], "payload": {}}],
            "elevation_cells": [{"col": 1, "row": 1, "elevation": 0}],
        }
        curr = {
            "grid": {"cols": 8, "rows": 8, "feet_per_square": 5},
            "rough_terrain": [],
            "obstacles": [],
            "units": [{"cid": 1, "pos": {"col": 2, "row": 2}}],
            "aoes": [],
            "features": [{"id": "f2", "col": 4, "row": 4, "kind": "barrel", "payload": {}}],
            "hazards": [{"id": "h2", "col": 5, "row": 5, "kind": "smoke", "payload": {}}],
            "structures": [{"id": "s2", "kind": "rowboat", "anchor_col": 3, "anchor_row": 3, "occupied_cells": [], "payload": {}}],
            "elevation_cells": [{"col": 7, "row": 7, "elevation": 10}],
        }
        envelope = lan._build_map_delta_envelope(prev, curr)
        delta = envelope["delta"]
        self.assertEqual(delta["features"]["upserts"][0]["id"], "f2")
        self.assertEqual(delta["hazards"]["upserts"][0]["id"], "h2")
        self.assertEqual(delta["structures"]["upserts"][0]["id"], "s2")
        self.assertEqual(delta["elevation_cells"]["upserts"][0]["col"], 7)

    def test_snapshot_to_map_state_prefers_map_state_payload_with_templates(self):
        lan = object.__new__(tracker_mod.LanController)
        snap = {
            "map_state": {
                "grid": {"cols": 9, "rows": 9, "feet_per_square": 5},
                "features": [{"id": "f1", "col": 1, "row": 1, "kind": "crate", "payload": {}}],
                "presentation": {
                    "structure_templates": {"ship_a": {"name": "Ship A", "kind": "ship_hull", "footprint": [{"col": 0, "row": 0}]}},
                    "ship_blueprints": {"sloop": {"id": "sloop", "name": "Sloop", "template": {"name": "Sloop", "kind": "ship_hull", "footprint": [{"col": 0, "row": 0}]}}},
                    "ship_instances": {"ship_1": {"id": "ship_1", "blueprint_id": "sloop", "parent_structure_id": "ship_a"}},
                },
            },
            "features": [{"id": "f2", "col": 2, "row": 2, "kind": "barrel", "payload": {}}],
        }
        state = lan._snapshot_to_map_state(snap).to_dict()
        self.assertEqual(state["features"][0]["id"], "f1")
        self.assertIn("structure_templates", state["presentation"])
        self.assertIn("ship_a", state["presentation"]["structure_templates"])
        self.assertIn("ship_blueprints", state["presentation"])
        self.assertIn("sloop", state["presentation"]["ship_blueprints"])


if __name__ == "__main__":
    unittest.main()
