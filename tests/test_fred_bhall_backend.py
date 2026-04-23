import copy
import unittest
from pathlib import Path
from unittest import mock

import yaml

import dnd_initative_tracker as tracker_mod


class FredBhallBackendTests(unittest.TestCase):
    @staticmethod
    def _combatant(**overrides):
        base = {
            "cid": 0,
            "name": "Combatant",
            "ac": 12,
            "hp": 20,
            "max_hp": 20,
            "temp_hp": 0,
            "condition_stacks": [],
            "ongoing_spell_effects": [],
            "start_turn_damage_riders": [],
            "end_turn_damage_riders": [],
            "start_turn_save_riders": [],
            "end_turn_save_riders": [],
            "on_damage_save_riders": [],
            "exhaustion_level": 0,
            "saving_throws": {},
            "ability_mods": {},
            "action_remaining": 1,
            "bonus_action_remaining": 1,
            "reaction_remaining": 1,
            "attack_resource_remaining": 0,
            "spell_cast_remaining": 1,
            "move_total": 30,
            "move_remaining": 30,
            "is_pc": False,
            "ally": False,
            "_feature_turn_hooks": [],
        }
        base.update(overrides)
        return type("CombatantStub", (), base)()

    def setUp(self):
        self.toasts = []
        self.logs = []
        self.mi_current = 0
        self.fred_profile = yaml.safe_load(Path("players/fred_figglehorn.yaml").read_text(encoding="utf-8"))

        self.app = object.__new__(tracker_mod.InitiativeTracker)
        self.app._oplog = lambda *args, **kwargs: None
        self.app._log = lambda message, cid=None: self.logs.append((cid, message))
        self.app._is_admin_token_valid = lambda token: False
        self.app._summon_can_be_controlled_by = lambda claimed, target: False
        self.app._is_valid_summon_turn_for_controller = lambda controlling, target, current: True
        self.app._profile_for_player_name = lambda name: copy.deepcopy(self.fred_profile) if str(name or "").strip() == "Fred" else {}
        self.app._pc_name_for = lambda cid: "Fred" if int(cid) == 1 else ""
        self.app._items_registry_payload = lambda: {"weapons": {}}
        self.app._magic_items_registry_payload = lambda: {}
        self.app._find_spell_preset = lambda **_kwargs: None
        self.app._rebuild_table = lambda *args, **kwargs: None
        self.app._lan_force_state_broadcast = lambda *args, **kwargs: None
        self.app._retarget_current_after_removal = lambda removed, pre_order=None: None
        self.app._remove_combatants_with_lan_cleanup = lambda cids: [self.app.combatants.pop(int(cid), None) for cid in cids]
        self.app._display_order = lambda: [self.app.combatants[cid] for cid in sorted(self.app.combatants.keys())]
        self.app._lan_live_map_data = lambda: (20, 20, set(), {}, dict(self.app._lan_positions))
        self.app._lan_current_position = lambda cid: dict(self.app._lan_positions).get(int(cid))
        self.app._lan_feet_per_square = lambda: 5.0
        self.app._lan_shortest_cost = (
            lambda origin, dest, obstacles, rough, cols, rows, max_ft, creature=None: int(
                max(abs(int(dest[0]) - int(origin[0])), abs(int(dest[1]) - int(origin[1]))) * 5
            )
        )
        self.app._lan_aura_effects_for_target = lambda _target: {}
        self.app._lan_sync_fixed_to_caster_aoes = lambda *args, **kwargs: None
        self.app._lan_handle_environment_triggers_for_moved_unit = lambda *args, **kwargs: None
        self.app._enforce_johns_echo_tether = lambda *args, **kwargs: None
        self.app._name_role_memory = {"Fred": "pc", "Cultist": "enemy"}
        self.app._reaction_prefs_by_cid = {}
        self.app._pending_reaction_offers = {}
        self.app._pending_shield_resolutions = {}
        self.app._pending_hellish_rebuke_resolutions = {}
        self.app._pending_absorb_elements_resolutions = {}
        self.app._pending_interception_resolutions = {}
        self.app._next_stack_id = 1
        self.app._lan_positions = {1: (5, 5), 2: (5, 4)}
        self.app.in_combat = True
        self.app.round_num = 1
        self.app.turn_num = 1
        self.app.current_cid = 1
        self.app.start_cid = None
        self.app._map_window = None
        self.app._lan = type(
            "LanStub",
            (),
            {
                "toast": lambda _self, ws_id, message: self.toasts.append((ws_id, message)),
                "_append_lan_log": lambda *args, **kwargs: None,
                "_loop": None,
            },
        )()

        original_normalize_pools = tracker_mod.InitiativeTracker._normalize_player_resource_pools.__get__(
            self.app,
            tracker_mod.InitiativeTracker,
        )

        def _normalize_player_resource_pools(profile):
            pools = original_normalize_pools(profile)
            for entry in pools:
                if not isinstance(entry, dict):
                    continue
                if str(entry.get("id") or "").strip().lower() != "murderous_intent":
                    continue
                entry["current"] = int(self.mi_current)
                entry["max"] = 3
            return pools

        self.app._normalize_player_resource_pools = _normalize_player_resource_pools
        self.app._set_player_resource_pool_current = self._set_pool_current

    def _set_pool_current(self, player_name, pool_id, new_current):
        if str(player_name or "").strip() != "Fred":
            return False, "unknown player"
        if str(pool_id or "").strip().lower() != "murderous_intent":
            return False, "unknown pool"
        self.mi_current = max(0, int(new_current))
        return True, ""

    def _reset_combatants(self, *, target_hp=20, target_max_hp=20):
        self.app.combatants = {
            1: self._combatant(
                cid=1,
                name="Fred",
                ac=16,
                hp=59,
                max_hp=59,
                is_pc=True,
                ally=True,
            ),
            2: self._combatant(
                cid=2,
                name="Cultist",
                ac=13,
                hp=target_hp,
                max_hp=target_max_hp,
                saving_throws={"wis": 0},
                ability_mods={"wis": 0},
            ),
        }

    def test_murderspawn_gains_once_on_first_damage_event_each_turn(self):
        self._reset_combatants(target_hp=20, target_max_hp=20)

        first = {
            "type": "attack_request",
            "cid": 1,
            "_claimed_cid": 1,
            "_ws_id": 91,
            "target_cid": 2,
            "weapon_id": "rotted_fork",
            "hit": True,
            "damage_entries": [{"amount": 4, "type": "piercing"}],
        }
        second = {
            "type": "attack_request",
            "cid": 1,
            "_claimed_cid": 1,
            "_ws_id": 92,
            "target_cid": 2,
            "weapon_id": "rotted_fork",
            "hit": True,
            "damage_entries": [{"amount": 3, "type": "piercing"}],
        }

        self.app._lan_apply_action(first)
        self.app._lan_apply_action(second)

        self.assertEqual(self.mi_current, 1)
        first_state = ((first.get("_attack_result") or {}).get("bhall_feature_state") or {}).get("murderous_intent") or {}
        second_state = ((second.get("_attack_result") or {}).get("bhall_feature_state") or {}).get("murderous_intent") or {}
        self.assertEqual(int(first_state.get("gained") or 0), 1)
        self.assertEqual(int(second_state.get("gained") or 0), 0)

    def test_murderspawn_kill_grants_extra_intent(self):
        self._reset_combatants(target_hp=4, target_max_hp=20)

        msg = {
            "type": "attack_request",
            "cid": 1,
            "_claimed_cid": 1,
            "_ws_id": 93,
            "target_cid": 2,
            "weapon_id": "rotted_fork",
            "hit": True,
            "damage_entries": [{"amount": 5, "type": "piercing"}],
        }

        self.app._lan_apply_action(msg)

        state = ((msg.get("_attack_result") or {}).get("bhall_feature_state") or {}).get("murderous_intent") or {}
        self.assertEqual(self.mi_current, 2)
        self.assertEqual(int(state.get("gained") or 0), 2)
        self.assertTrue(bool(state.get("damage_gain_triggered")))
        self.assertTrue(bool(state.get("kill_gain_triggered")))

    def test_murderspawn_gains_on_generic_single_target_spell_damage(self):
        self._reset_combatants(target_hp=20, target_max_hp=20)
        self.app._find_spell_preset = lambda *_args, **_kwargs: {
            "slug": "eldritch-blast",
            "id": "eldritch-blast",
            "name": "Eldritch Blast",
            "level": 0,
            "mechanics": {
                "sequence": [
                    {
                        "check": {"kind": "spell_attack"},
                        "outcomes": {
                            "hit": [{"effect": "damage", "damage_type": "force", "dice": "1d10"}],
                            "miss": [],
                        },
                    }
                ]
            },
        }
        msg = {
            "type": "spell_target_request",
            "cid": 1,
            "_claimed_cid": 1,
            "_ws_id": 94,
            "target_cid": 2,
            "spell_name": "Eldritch Blast",
            "spell_slug": "eldritch-blast",
            "spell_mode": "attack",
            "hit": True,
        }

        with mock.patch("dnd_initative_tracker.random.randint", return_value=6):
            self.app._lan_apply_action(msg)

        state = ((msg.get("_spell_target_result") or {}).get("bhall_feature_state") or {}).get("murderous_intent") or {}
        self.assertEqual(self.mi_current, 1)
        self.assertEqual(int(state.get("gained") or 0), 1)

    def test_murderspawn_explicit_spend_adds_necrotic_and_consumes_pool(self):
        self._reset_combatants(target_hp=20, target_max_hp=20)
        self.mi_current = 2

        msg = {
            "type": "attack_request",
            "cid": 1,
            "_claimed_cid": 1,
            "_ws_id": 95,
            "target_cid": 2,
            "weapon_id": "rotted_fork",
            "hit": True,
            "damage_entries": [{"amount": 4, "type": "piercing"}],
            "murderspawn_spend": 2,
        }

        with mock.patch("dnd_initative_tracker.random.randint", side_effect=[3, 2]):
            self.app._lan_apply_action(msg)

        result = msg.get("_attack_result") or {}
        state = ((result.get("bhall_feature_state") or {}).get("murderous_intent")) or {}
        necrotic_total = sum(
            int((entry or {}).get("amount") or 0)
            for entry in (result.get("damage_entries") or [])
            if str((entry or {}).get("type") or "").strip().lower() == "necrotic"
        )

        self.assertEqual(int(result.get("damage_total") or 0), 9)
        self.assertEqual(necrotic_total, 5)
        self.assertEqual(self.mi_current, 1)
        self.assertEqual(int(state.get("spend_requested") or 0), 2)
        self.assertEqual(int(state.get("spent") or 0), 2)
        self.assertEqual(int(state.get("bonus_damage_total") or 0), 5)
        self.assertEqual(int(state.get("gained") or 0), 1)

    def test_murderspawn_explicit_spend_applies_on_generic_warlock_spell_damage(self):
        self._reset_combatants(target_hp=20, target_max_hp=20)
        self.mi_current = 1
        self.app._find_spell_preset = lambda *_args, **_kwargs: {
            "slug": "eldritch-blast",
            "id": "eldritch-blast",
            "name": "Eldritch Blast",
            "level": 0,
            "mechanics": {
                "sequence": [
                    {
                        "check": {"kind": "spell_attack"},
                        "outcomes": {
                            "hit": [{"effect": "damage", "damage_type": "force", "dice": "1d10"}],
                            "miss": [],
                        },
                    }
                ]
            },
        }
        msg = {
            "type": "spell_target_request",
            "cid": 1,
            "_claimed_cid": 1,
            "_ws_id": 96,
            "target_cid": 2,
            "spell_name": "Eldritch Blast",
            "spell_slug": "eldritch-blast",
            "spell_mode": "attack",
            "hit": True,
            "murderspawn_spend": 1,
        }

        with mock.patch("dnd_initative_tracker.random.randint", side_effect=[6, 4]):
            self.app._lan_apply_action(msg)

        result = msg.get("_spell_target_result") or {}
        state = ((result.get("bhall_feature_state") or {}).get("murderous_intent")) or {}

        self.assertEqual(int(result.get("damage_total") or 0), 10)
        self.assertEqual(self.mi_current, 1)
        self.assertEqual(int(state.get("spent") or 0), 1)
        self.assertEqual(int(state.get("bonus_damage_total") or 0), 4)
        self.assertEqual(int(state.get("gained") or 0), 1)

    def test_blood_in_the_air_requires_explicit_choice_and_keeps_awareness_flags(self):
        self._reset_combatants(target_hp=10, target_max_hp=40)
        msg = {
            "type": "attack_request",
            "cid": 1,
            "_claimed_cid": 1,
            "_ws_id": 97,
            "target_cid": 2,
            "weapon_id": "rotted_fork",
            "hit": True,
            "damage_entries": [{"amount": 3, "type": "piercing"}],
        }

        self.app._lan_apply_action(msg)

        result = msg.get("_attack_result") or {}
        bhall_state = (result.get("bhall_feature_state") or {})
        awareness = bhall_state.get("awareness") or {}
        blood_in_the_air = bhall_state.get("blood_in_the_air") or {}
        target = self.app.combatants[2]

        self.assertTrue(bool(awareness.get("below_half_hp")))
        self.assertTrue(bool(awareness.get("below_quarter_hp")))
        self.assertTrue(bool(awareness.get("within_30ft")))
        self.assertTrue(bool(awareness.get("cull_the_weak_active")))
        self.assertTrue(bool(awareness.get("blood_in_the_air_awareness_active")))
        self.assertTrue(bool(blood_in_the_air.get("available")))
        self.assertFalse(bool(blood_in_the_air.get("applied")))
        self.assertEqual(blood_in_the_air.get("reason"), "choice_required")
        self.assertFalse(self.app._combatant_reactions_blocked(target))

    def test_blood_in_the_air_reactions_choice_applies_reaction_lock_and_clears(self):
        self._reset_combatants(target_hp=10, target_max_hp=40)
        msg = {
            "type": "attack_request",
            "cid": 1,
            "_claimed_cid": 1,
            "_ws_id": 98,
            "target_cid": 2,
            "weapon_id": "rotted_fork",
            "hit": True,
            "damage_entries": [{"amount": 3, "type": "piercing"}],
            "blood_in_the_air_choice": "reactions",
        }

        with mock.patch("dnd_initative_tracker.random.randint", return_value=2):
            self.app._lan_apply_action(msg)

        result = msg.get("_attack_result") or {}
        blood_in_the_air = ((result.get("bhall_feature_state") or {}).get("blood_in_the_air")) or {}
        target = self.app.combatants[2]

        self.assertEqual(blood_in_the_air.get("selected_choice"), "reactions")
        self.assertTrue(bool(blood_in_the_air.get("applied")))
        self.assertTrue(self.app._combatant_reactions_blocked(target))

        self.app._run_combatant_turn_hooks(target, "start_turn")
        self.assertFalse(self.app._combatant_reactions_blocked(target))

    def test_blood_in_the_air_move_choice_relocates_attacker_for_free(self):
        self._reset_combatants(target_hp=10, target_max_hp=40)
        fred = self.app.combatants[1]
        fred.move_remaining = 0
        self.app._lan_positions[1] = (5, 5)
        self.app._lan_positions[2] = (5, 4)

        msg = {
            "type": "attack_request",
            "cid": 1,
            "_claimed_cid": 1,
            "_ws_id": 99,
            "target_cid": 2,
            "weapon_id": "rotted_fork",
            "hit": True,
            "damage_entries": [{"amount": 3, "type": "piercing"}],
            "blood_in_the_air_choice": "move",
            "blood_in_the_air_destination_col": 7,
            "blood_in_the_air_destination_row": 5,
        }

        self.app._lan_apply_action(msg)

        result = msg.get("_attack_result") or {}
        blood_in_the_air = ((result.get("bhall_feature_state") or {}).get("blood_in_the_air")) or {}
        movement = blood_in_the_air.get("movement") or {}

        self.assertEqual(self.app._lan_positions.get(1), (7, 5))
        self.assertEqual(int(getattr(fred, "move_remaining", 0) or 0), 0)
        self.assertEqual(blood_in_the_air.get("selected_choice"), "move")
        self.assertTrue(bool(blood_in_the_air.get("applied")))
        self.assertEqual(int(movement.get("distance_ft") or 0), 10)
        self.assertEqual(int(movement.get("destination_col") or 0), 7)
        self.assertEqual(int(movement.get("destination_row") or 0), 5)


if __name__ == "__main__":
    unittest.main()
