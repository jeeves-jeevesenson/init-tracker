import json
import tempfile
import types
import unittest
from pathlib import Path

import dnd_initative_tracker as tracker_mod
from player_command_contracts import (
    AOE_MANIPULATION_COMMAND_TYPES,
    MOVEMENT_ACTION_COMMAND_TYPES,
    SPELL_LAUNCH_COMMAND_TYPES,
    TURN_LOCAL_COMMAND_TYPES,
    WILD_SHAPE_COMMAND_TYPES,
    build_aoe_move_contract,
    build_aoe_remove_contract,
    build_action_surge_use_contract,
    build_attack_request_contract,
    build_cast_aoe_contract,
    build_cast_spell_contract,
    build_cycle_movement_mode_contract,
    build_dash_contract,
    build_dismount_contract,
    build_inventory_adjust_consumable_contract,
    build_lay_on_hands_use_contract,
    build_monk_elemental_attunement_contract,
    build_monk_elemental_burst_contract,
    build_monk_patient_defense_contract,
    build_monk_step_of_wind_contract,
    build_monk_uncanny_metabolism_contract,
    build_move_contract,
    build_manual_override_resource_pool_contract,
    build_manual_override_spell_slot_contract,
    build_mount_request_contract,
    build_mount_response_contract,
    build_perform_action_contract,
    build_reaction_prefs_update_contract,
    build_reset_turn_contract,
    build_resume_dispatch,
    build_second_wind_use_contract,
    build_star_advantage_use_contract,
    build_stand_up_contract,
    build_use_action_contract,
    build_use_bonus_action_contract,
    build_use_consumable_contract,
    build_wild_shape_apply_contract,
    build_wild_shape_pool_set_current_contract,
    build_wild_shape_regain_spell_contract,
    build_wild_shape_regain_use_contract,
    build_wild_shape_revert_contract,
    build_wild_shape_set_known_contract,
)
from player_command_service import PromptState


class PromptContractStateTests(unittest.TestCase):
    def test_prompt_state_projects_canonical_records_into_legacy_views(self):
        tracker = object.__new__(tracker_mod.InitiativeTracker)
        state = PromptState(tracker)
        prompt = state.create_reaction_offer(
            reactor_cid=1,
            trigger="shield",
            source_cid=2,
            target_cid=1,
            allowed_choices=[{"kind": "shield_yes", "label": "Yes", "mode": "ask"}],
            ws_ids=[101],
            extra_payload={"prompt": "Enemy attacks you with Sword.", "prompt_attack": "Sword"},
        )
        request_contract = build_attack_request_contract(
            {
                "type": "attack_request",
                "target_cid": 1,
                "weapon_id": "sword",
                "attack_roll": 14,
                "damage_entries": [{"amount": 7, "type": "slashing"}],
            },
            cid=2,
            ws_id=77,
            is_admin=False,
        )
        state.attach_resolution(
            prompt["prompt_id"],
            resume_dispatch=build_resume_dispatch(
                "attack_request",
                actor_cid=2,
                ws_id=77,
                is_admin=False,
                payload=request_contract["payload"],
            ),
        )

        prompt_id = str(prompt["prompt_id"])
        offer_event = state.build_offer_event(prompt_id)
        self.assertIsInstance(offer_event, dict)
        self.assertEqual(offer_event.get("prompt_id"), prompt_id)
        self.assertEqual((offer_event.get("contract") or {}).get("schema"), "player_command.reaction_offer")
        self.assertIn(prompt_id, tracker._pending_reaction_offers)
        self.assertIn(prompt_id, tracker._pending_shield_resolutions)
        self.assertEqual(tracker._pending_reaction_offers[prompt_id]["trigger"], "shield")
        self.assertEqual(tracker._pending_shield_resolutions[prompt_id]["msg"]["type"], "attack_request")

        visible = state.player_visible_prompts_for_actor(1)
        self.assertEqual(len(visible), 1)
        self.assertEqual(visible[0]["prompt_id"], prompt_id)
        self.assertEqual(visible[0]["trigger"], "shield")
        self.assertEqual((visible[0].get("contract") or {}).get("schema"), "player_command.prompt_snapshot")


class TurnLocalCommandContractTests(unittest.TestCase):
    def test_turn_local_command_contract_builders_cover_the_family(self):
        builders = {
            "mount_request": (
                build_mount_request_contract,
                {"type": "mount_request", "rider_cid": 1, "mount_cid": 2},
            ),
            "mount_response": (
                build_mount_response_contract,
                {"type": "mount_response", "request_id": "mount:1:2", "accept": True},
            ),
            "dismount": (
                build_dismount_contract,
                {"type": "dismount"},
            ),
            "dash": (
                build_dash_contract,
                {"type": "dash", "spend": "action"},
            ),
            "use_action": (
                build_use_action_contract,
                {"type": "use_action"},
            ),
            "use_bonus_action": (
                build_use_bonus_action_contract,
                {"type": "use_bonus_action"},
            ),
            "stand_up": (
                build_stand_up_contract,
                {"type": "stand_up"},
            ),
            "reset_turn": (
                build_reset_turn_contract,
                {"type": "reset_turn"},
            ),
        }

        self.assertEqual(set(builders.keys()), set(TURN_LOCAL_COMMAND_TYPES))

        for command_type, (builder, msg) in builders.items():
            contract = builder(dict(msg), cid=7, ws_id=8, is_admin=False)
            self.assertEqual(contract.get("command_type"), command_type)
            self.assertEqual(
                (contract.get("contract") or {}).get("schema"),
                f"player_command.{command_type}.request",
            )
            self.assertEqual((contract.get("actor") or {}).get("cid"), 7)
            self.assertEqual((contract.get("payload") or {}).get("type"), command_type)


class MovementActionCommandContractTests(unittest.TestCase):
    def test_movement_action_contract_builders_cover_the_family(self):
        builders = {
            "move": (
                build_move_contract,
                {"type": "move", "to": {"col": 4, "row": 5}},
            ),
            "cycle_movement_mode": (
                build_cycle_movement_mode_contract,
                {"type": "cycle_movement_mode"},
            ),
            "perform_action": (
                build_perform_action_contract,
                {"type": "perform_action", "spend": "action", "action": "Disengage"},
            ),
        }

        self.assertEqual(set(builders.keys()), set(MOVEMENT_ACTION_COMMAND_TYPES))

        for command_type, (builder, msg) in builders.items():
            contract = builder(dict(msg), cid=11, ws_id=12, is_admin=False)
            self.assertEqual(contract.get("command_type"), command_type)
            self.assertEqual(
                (contract.get("contract") or {}).get("schema"),
                f"player_command.{command_type}.request",
            )
            self.assertEqual((contract.get("actor") or {}).get("cid"), 11)
            self.assertEqual((contract.get("payload") or {}).get("type"), command_type)


class WildShapeCommandContractTests(unittest.TestCase):
    def test_wild_shape_command_contract_builders_cover_the_family(self):
        builders = {
            "wild_shape_apply": (
                build_wild_shape_apply_contract,
                {"type": "wild_shape_apply", "beast_id": "wolf"},
            ),
            "wild_shape_pool_set_current": (
                build_wild_shape_pool_set_current_contract,
                {"type": "wild_shape_pool_set_current", "current": 2},
            ),
            "wild_shape_revert": (
                build_wild_shape_revert_contract,
                {"type": "wild_shape_revert"},
            ),
            "wild_shape_regain_use": (
                build_wild_shape_regain_use_contract,
                {"type": "wild_shape_regain_use"},
            ),
            "wild_shape_regain_spell": (
                build_wild_shape_regain_spell_contract,
                {"type": "wild_shape_regain_spell"},
            ),
            "wild_shape_set_known": (
                build_wild_shape_set_known_contract,
                {"type": "wild_shape_set_known", "known": ["reef-shark", "wolf"]},
            ),
        }

        self.assertEqual(set(builders.keys()), set(WILD_SHAPE_COMMAND_TYPES))

        for command_type, (builder, msg) in builders.items():
            contract = builder(dict(msg), cid=13, ws_id=14, is_admin=False)
            self.assertEqual(contract.get("command_type"), command_type)
            self.assertEqual(
                (contract.get("contract") or {}).get("schema"),
                f"player_command.{command_type}.request",
            )
            self.assertEqual((contract.get("actor") or {}).get("cid"), 13)
            self.assertEqual((contract.get("payload") or {}).get("type"), command_type)


class SpellLaunchCommandContractTests(unittest.TestCase):
    def test_spell_launch_command_contract_builders_cover_the_family(self):
        builders = {
            "cast_spell": (
                build_cast_spell_contract,
                {
                    "type": "cast_spell",
                    "spell_slug": "fire-bolt",
                    "spell_id": "fire-bolt",
                    "slot_level": 1,
                    "payload": {"spell_slug": "fire-bolt"},
                },
            ),
            "cast_aoe": (
                build_cast_aoe_contract,
                {
                    "type": "cast_aoe",
                    "spell_slug": "fireball",
                    "spell_id": "fireball",
                    "slot_level": 3,
                    "payload": {"shape": "sphere", "radius_ft": 20},
                },
            ),
        }

        self.assertEqual(set(builders.keys()), set(SPELL_LAUNCH_COMMAND_TYPES))

        for command_type, (builder, msg) in builders.items():
            contract = builder(dict(msg), cid=21, ws_id=42, is_admin=False)
            self.assertEqual(contract.get("command_type"), command_type)
            self.assertEqual(
                (contract.get("contract") or {}).get("schema"),
                f"player_command.{command_type}.request",
            )
            self.assertEqual((contract.get("actor") or {}).get("cid"), 21)
            self.assertEqual((contract.get("payload") or {}).get("type"), command_type)


class AoeManipulationCommandContractTests(unittest.TestCase):
    def test_aoe_manipulation_command_contract_builders_cover_the_family(self):
        builders = {
            "aoe_move": (
                build_aoe_move_contract,
                {
                    "type": "aoe_move",
                    "aid": 9,
                    "to": {"cx": 4.5, "cy": 7.0, "angle_deg": 90},
                },
            ),
            "aoe_remove": (
                build_aoe_remove_contract,
                {
                    "type": "aoe_remove",
                    "aid": 9,
                },
            ),
        }

        self.assertEqual(set(builders.keys()), set(AOE_MANIPULATION_COMMAND_TYPES))

        for command_type, (builder, msg) in builders.items():
            contract = builder(dict(msg), cid=23, ws_id=24, is_admin=False)
            self.assertEqual(contract.get("command_type"), command_type)
            self.assertEqual(
                (contract.get("contract") or {}).get("schema"),
                f"player_command.{command_type}.request",
            )
            self.assertEqual((contract.get("actor") or {}).get("cid"), 23)
            self.assertEqual((contract.get("payload") or {}).get("type"), command_type)


class ReactionResumeDispatchTests(unittest.TestCase):
    def _make_shield_app(self):
        sent = []
        toasts = []
        logs = []
        slot_spend_calls = []
        app = object.__new__(tracker_mod.InitiativeTracker)
        app._oplog = lambda *args, **kwargs: None
        app._is_admin_token_valid = lambda token: False
        app._summon_can_be_controlled_by = lambda claimed, target: False
        app._is_valid_summon_turn_for_controller = lambda controlling, target, current: True
        app._mount_action_is_restricted = lambda *args, **kwargs: False
        app._find_action_entry = lambda c, spend, action: {"name": action}
        app._action_name_key = lambda v: str(v or "").strip().lower()
        app._lan_aura_effects_for_target = lambda target: {}
        app._adjust_damage_entries_for_target = lambda target, entries: {"entries": list(entries), "notes": []}
        app._apply_damage_to_target_with_temp_hp = lambda target, dmg: {"hp_after": max(0, int(target.hp) - int(dmg))}
        app._remove_combatants_with_lan_cleanup = lambda cids: None
        app._retarget_current_after_removal = lambda *args, **kwargs: None
        app._unit_has_sentinel_feat = lambda unit: False
        app._lan_apply_forced_movement = lambda *args, **kwargs: False
        app._clear_hide_state = lambda *args, **kwargs: None
        app._profile_for_player_name = lambda name: {
            "features": [],
            "attacks": {"weapon_to_hit": 5, "weapons": [{"id": "sword", "name": "Sword", "to_hit": 5, "effect": {}}]},
            "leveling": {"classes": [{"name": "Fighter", "attacks_per_action": 1}]},
            "spellcasting": {"prepared_spells": {"prepared": ["shield"]}},
        }
        app._pc_name_for = lambda cid: {1: "Eldramar", 2: "Enemy"}.get(int(cid), "PC")
        app._resolve_spell_slot_profile = lambda caster_name: (caster_name, {"1": {"current": 2}})
        app._consume_spell_slot_for_cast = lambda caster_name, slot_level, minimum_level: slot_spend_calls.append((caster_name, slot_level, minimum_level)) or (True, "", 1)
        app._consume_resource_pool_for_cast = lambda *args, **kwargs: (False, "")
        app._use_action = lambda c, **kwargs: True
        app._use_bonus_action = lambda c, **kwargs: True
        app._use_reaction = lambda c, **kwargs: setattr(c, "reaction_remaining", max(0, int(getattr(c, "reaction_remaining", 0)) - 1)) or True
        app._rebuild_table = lambda *args, **kwargs: None
        app._lan_force_state_broadcast = lambda *args, **kwargs: None
        app._log = lambda msg, **kwargs: logs.append(msg)
        app._find_ws_for_cid = lambda cid: [101] if int(cid) == 1 else [202]
        app._lan = type(
            "LanStub",
            (),
            {
                "toast": lambda _self, ws_id, message: toasts.append((ws_id, message)),
                "_append_lan_log": lambda *args, **kwargs: None,
                "_loop": object(),
                "_send_async": lambda _self, ws_id, payload: sent.append((ws_id, payload)),
                "play_ko": lambda *_args, **_kwargs: None,
            },
        )()
        app._name_role_memory = {"Eldramar": "pc", "Enemy": "enemy"}
        app._lan_positions = {1: (5, 5), 2: (6, 5)}
        app._lan_live_map_data = lambda: (20, 20, set(), {}, dict(app._lan_positions))
        app._map_window = None
        app._lan_aoes = {}
        app._pending_prompts = {}
        app._pending_reaction_offers = {}
        app._pending_shield_resolutions = {}
        app._reaction_prefs_by_cid = {1: {"shield": "ask"}}
        app.in_combat = True
        app.current_cid = 2
        app.round_num = 1
        app.turn_num = 1
        app.start_cid = None
        app.combatants = {
            1: type("C", (), {"cid": 1, "name": "Eldramar", "reaction_remaining": 1, "hp": 20, "ac": 12, "condition_stacks": [], "saving_throws": {}, "ability_mods": {}, "exhaustion_level": 0, "is_pc": True})(),
            2: type("C", (), {"cid": 2, "name": "Enemy", "reaction_remaining": 1, "action_remaining": 1, "bonus_action_remaining": 1, "attack_resource_remaining": 1, "move_remaining": 30, "move_total": 30, "hp": 20, "ac": 10, "condition_stacks": [], "is_pc": False})(),
        }
        return app, sent, toasts, logs, slot_spend_calls

    def test_reaction_response_service_dispatches_resume_without_transport_recursion(self):
        app, sent, _toasts, _logs, _slot_spend_calls = self._make_shield_app()
        attack_msg = {
            "type": "attack_request",
            "cid": 2,
            "_claimed_cid": 2,
            "_ws_id": 77,
            "target_cid": 1,
            "weapon_id": "sword",
            "attack_roll": 11,
            "damage_entries": [{"amount": 7, "type": "slashing"}],
        }
        app._lan_apply_action(attack_msg)
        offers = [payload for _ws, payload in sent if isinstance(payload, dict) and payload.get("type") == "reaction_offer" and payload.get("trigger") == "shield"]
        self.assertTrue(offers)
        req_id = str(offers[-1]["request_id"])

        def _forbid_recursive_transport(*_args, **_kwargs):
            raise AssertionError("resume should dispatch through PlayerCommandService, not _lan_apply_action recursion")

        app._lan_apply_action = _forbid_recursive_transport
        result = app._ensure_player_commands().reaction_response(
            {"type": "reaction_response", "request_id": req_id, "choice": "shield_yes"},
            cid=1,
            ws_id=101,
        )

        self.assertTrue(result.get("resume_dispatched"))
        attack_results = [payload for _ws, payload in sent if isinstance(payload, dict) and payload.get("type") == "attack_result"]
        self.assertTrue(attack_results)
        self.assertFalse(bool(attack_results[-1].get("hit")))
        self.assertNotIn(req_id, app._ensure_player_commands().prompts.all_prompts())


class PromptSnapshotPersistenceTests(unittest.TestCase):
    def _make_app(self, history_path: Path):
        app = object.__new__(tracker_mod.InitiativeTracker)
        app.combatants = {}
        app._next_id = 1
        app._next_stack_id = 7
        app.current_cid = None
        app.start_cid = None
        app.round_num = 1
        app.turn_num = 0
        app.in_combat = False
        app._turn_snapshots = {}
        app._name_role_memory = {}
        app._summon_groups = {}
        app._summon_group_meta = {}
        app._pending_pre_summons = {}
        app._pending_mount_requests = {}
        app._pending_prompts = {}
        app._pending_reaction_offers = {}
        app._pending_shield_resolutions = {}
        app._pending_hellish_rebuke_resolutions = {}
        app._pending_absorb_elements_resolutions = {}
        app._pending_interception_resolutions = {}
        app._concentration_save_state = {}
        app._reaction_prefs_by_cid = {}

        app._lan_grid_cols = 20
        app._lan_grid_rows = 20
        app._lan_positions = {}
        app._lan_obstacles = set()
        app._lan_rough_terrain = {}
        app._lan_aoes = {}
        app._lan_next_aoe_id = 1
        app._lan_auras_enabled = True
        app._session_bg_images = []
        app._session_next_bg_id = 1
        app._map_window = None
        app._monsters_by_name = {}
        app._map_state = tracker_mod.MapState.from_dict({"grid": {"cols": 20, "rows": 20, "feet_per_square": 5}})

        def _create_combatant(**kwargs):
            cid = int(app._next_id)
            app._next_id += 1
            c = types.SimpleNamespace(
                cid=cid,
                name=kwargs["name"],
                hp=int(kwargs["hp"]),
                speed=int(kwargs["speed"]),
                swim_speed=int(kwargs.get("swim_speed", 0)),
                fly_speed=int(kwargs.get("fly_speed", 0)),
                burrow_speed=int(kwargs.get("burrow_speed", 0)),
                climb_speed=int(kwargs.get("climb_speed", 0)),
                movement_mode=str(kwargs.get("movement_mode", "normal")),
                move_remaining=int(kwargs.get("speed", 0)),
                move_total=int(kwargs.get("speed", 0)),
                initiative=int(kwargs.get("initiative", 0)),
                dex=kwargs.get("dex"),
                roll=None,
                nat20=False,
                ally=bool(kwargs.get("ally", False)),
                is_pc=bool(kwargs.get("is_pc", False)),
                is_spellcaster=bool(kwargs.get("is_spellcaster", False)),
                saving_throws=dict(kwargs.get("saving_throws") or {}),
                ability_mods=dict(kwargs.get("ability_mods") or {}),
                actions=list(kwargs.get("actions") or []),
                bonus_actions=list(kwargs.get("bonus_actions") or []),
                reactions=list(kwargs.get("reactions") or []),
                monster_spec=kwargs.get("monster_spec"),
            )
            app.combatants[cid] = c
            return cid

        app._create_combatant = _create_combatant
        app._find_monster_spec_by_slug = lambda _slug: None
        app._remove_combatants_with_lan_cleanup = lambda cids: [app.combatants.pop(int(cid), None) for cid in list(cids)]
        app._history_file_path = lambda: history_path
        app._load_history_into_log = lambda max_lines=2000: None
        app._update_turn_ui = lambda: None
        app._rebuild_table = lambda scroll_to_current=True: None
        app._lan_force_state_broadcast = lambda: None
        app._log = lambda *_args, **_kwargs: None
        app._lan_battle_log_lines = lambda limit=0: []
        app._pc_name_for = lambda cid: {1: "Alice"}.get(int(cid), f"cid:{cid}")
        return app

    def test_session_snapshot_roundtrip_preserves_pending_prompts(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            snap_path = Path(tmpdir) / "snapshot.json"
            app = self._make_app(Path(tmpdir) / "battle.log")
            app._reaction_prefs_by_cid = {1: {"shield": "ask"}}
            state = app._ensure_player_commands().prompts
            prompt = state.create_reaction_offer(
                reactor_cid=1,
                trigger="shield",
                source_cid=2,
                target_cid=1,
                allowed_choices=[{"kind": "shield_yes", "label": "Yes", "mode": "ask"}],
                ws_ids=[101],
                extra_payload={"prompt": "Enemy attacks you with Sword.", "prompt_attack": "Sword"},
            )
            state.attach_resolution(
                prompt["prompt_id"],
                resume_dispatch=build_resume_dispatch(
                    "attack_request",
                    actor_cid=2,
                    ws_id=77,
                    is_admin=False,
                    payload={"type": "attack_request", "target_cid": 1, "weapon_id": "sword"},
                ),
            )
            app._save_session_to_path(snap_path, label="prompt-roundtrip")
            payload = json.loads(snap_path.read_text(encoding="utf-8"))
            self.assertIn("pending_prompts", payload.get("combat", {}))

            restored = self._make_app(Path(tmpdir) / "restored.log")
            restored._load_session_from_path(snap_path)
            pending_prompts = restored._ensure_player_commands().prompts.player_visible_prompts_for_actor(1)
            self.assertEqual(len(pending_prompts), 1)
            self.assertEqual(pending_prompts[0]["prompt_id"], prompt["prompt_id"])
            self.assertIn(prompt["prompt_id"], restored._pending_reaction_offers)
            self.assertIn(prompt["prompt_id"], restored._pending_shield_resolutions)


class PlayerResourceCommandContractTests(unittest.TestCase):
    def test_resource_command_contract_builders_shape_payloads(self):
        spell_slot = build_manual_override_spell_slot_contract(
            {"type": "manual_override_spell_slot", "slot_level": 2, "delta": -1, "ignored": "x"},
            cid=1,
            ws_id=10,
            is_admin=False,
        )
        self.assertEqual(spell_slot["command_type"], "manual_override_spell_slot")
        self.assertEqual(spell_slot["payload"], {"type": "manual_override_spell_slot", "slot_level": 2, "delta": -1})

        pool = build_manual_override_resource_pool_contract(
            {"type": "manual_override_resource_pool", "pool_id": "focus_points", "delta": 1},
            cid=1,
            ws_id=10,
            is_admin=True,
        )
        self.assertEqual(pool["payload"]["pool_id"], "focus_points")
        self.assertEqual(pool["actor"]["is_admin"], True)

        prefs = build_reaction_prefs_update_contract(
            {"type": "reaction_prefs_update", "prefs": {"shield": "auto"}},
            cid=1,
            ws_id=10,
            is_admin=False,
        )
        self.assertEqual((prefs["contract"] or {}).get("schema"), "player_command.reaction_prefs_update.request")
        self.assertEqual(prefs["payload"]["prefs"], {"shield": "auto"})

        lay_on_hands = build_lay_on_hands_use_contract(
            {"type": "lay_on_hands_use", "target_cid": 2, "amount": 5, "cure_poisoned": False},
            cid=1,
            ws_id=10,
            is_admin=False,
        )
        self.assertEqual(lay_on_hands["payload"]["target_cid"], 2)
        self.assertEqual(lay_on_hands["payload"]["amount"], 5)

        adjust = build_inventory_adjust_consumable_contract(
            {"type": "inventory_adjust_consumable", "consumable_id": "lesser_healing_potion", "delta": 1},
            cid=1,
            ws_id=10,
            is_admin=False,
        )
        self.assertEqual(adjust["payload"]["consumable_id"], "lesser_healing_potion")
        self.assertEqual(adjust["payload"]["delta"], 1)

        use = build_use_consumable_contract(
            {"type": "use_consumable", "id": "lesser_healing_potion"},
            cid=1,
            ws_id=10,
            is_admin=False,
        )
        self.assertEqual(use["payload"]["id"], "lesser_healing_potion")

        second_wind = build_second_wind_use_contract(
            {"type": "second_wind_use", "healing_roll": 7, "ignored": "x"},
            cid=1,
            ws_id=10,
            is_admin=False,
        )
        self.assertEqual(second_wind["payload"], {"type": "second_wind_use", "healing_roll": 7})

        action_surge = build_action_surge_use_contract(
            {"type": "action_surge_use", "ignored": "x"},
            cid=1,
            ws_id=10,
            is_admin=False,
        )
        self.assertEqual(action_surge["payload"], {"type": "action_surge_use"})

        star_advantage = build_star_advantage_use_contract(
            {"type": "star_advantage_use", "ignored": "x"},
            cid=1,
            ws_id=10,
            is_admin=False,
        )
        self.assertEqual(star_advantage["payload"], {"type": "star_advantage_use"})

        patient_defense = build_monk_patient_defense_contract(
            {"type": "monk_patient_defense", "mode": "focus", "ignored": "x"},
            cid=1,
            ws_id=10,
            is_admin=False,
        )
        self.assertEqual(patient_defense["payload"], {"type": "monk_patient_defense", "mode": "focus"})

        step_of_wind = build_monk_step_of_wind_contract(
            {"type": "monk_step_of_wind", "mode": "free", "ignored": "x"},
            cid=1,
            ws_id=10,
            is_admin=False,
        )
        self.assertEqual(step_of_wind["payload"], {"type": "monk_step_of_wind", "mode": "free"})

        attunement = build_monk_elemental_attunement_contract(
            {"type": "monk_elemental_attunement", "mode": "activate", "ignored": "x"},
            cid=1,
            ws_id=10,
            is_admin=False,
        )
        self.assertEqual(attunement["payload"], {"type": "monk_elemental_attunement", "mode": "activate"})

        burst = build_monk_elemental_burst_contract(
            {
                "type": "monk_elemental_burst",
                "damage_type": "fire",
                "movement_mode": "push",
                "payload": {"cx": 4, "cy": 5},
                "ignored": "x",
            },
            cid=1,
            ws_id=10,
            is_admin=False,
        )
        self.assertEqual(burst["payload"]["damage_type"], "fire")
        self.assertEqual(burst["payload"]["movement_mode"], "push")
        self.assertEqual(burst["payload"]["payload"], {"cx": 4, "cy": 5})

        uncanny = build_monk_uncanny_metabolism_contract(
            {"type": "monk_uncanny_metabolism", "ignored": "x"},
            cid=1,
            ws_id=10,
            is_admin=False,
        )
        self.assertEqual(uncanny["payload"], {"type": "monk_uncanny_metabolism"})
