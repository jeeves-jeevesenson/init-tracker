import unittest
from pathlib import Path

import yaml

import dnd_initative_tracker as tracker_mod


class AbsorbElementsReactionTests(unittest.TestCase):
    def setUp(self):
        self.sent = []
        self.toasts = []
        self.slot_spend_calls = []
        self.app = object.__new__(tracker_mod.InitiativeTracker)
        self.app._oplog = lambda *args, **kwargs: None
        self.app._is_admin_token_valid = lambda token: False
        self.app._summon_can_be_controlled_by = lambda claimed, target: False
        self.app._is_valid_summon_turn_for_controller = lambda controlling, target, current: True
        self.app._mount_action_is_restricted = lambda *args, **kwargs: False
        self.app._find_action_entry = lambda c, spend, action: {"name": action}
        self.app._action_name_key = lambda v: str(v or "").strip().lower()
        self.app._lan_aura_effects_for_target = lambda target: {}
        self.app._apply_damage_to_target_with_temp_hp = (
            lambda target, dmg: setattr(target, "hp", max(0, int(target.hp) - int(dmg))) or {"hp_after": int(target.hp)}
        )
        self.app._remove_combatants_with_lan_cleanup = lambda cids: None
        self.app._retarget_current_after_removal = lambda *args, **kwargs: None
        self.app._unit_has_sentinel_feat = lambda unit: False
        self.app._lan_apply_forced_movement = lambda *args, **kwargs: False
        self.app._clear_hide_state = lambda *args, **kwargs: None
        self.app._use_action = lambda c, **kwargs: True
        self.app._use_bonus_action = lambda c, **kwargs: True
        self.app._use_reaction = lambda c, **kwargs: setattr(c, "reaction_remaining", max(0, int(getattr(c, "reaction_remaining", 0)) - 1)) or True
        self.app._rebuild_table = lambda *args, **kwargs: None
        self.app._lan_force_state_broadcast = lambda *args, **kwargs: None
        self.app._log = lambda msg, **kwargs: None
        self.app._find_ws_for_cid = lambda cid: [101] if int(cid) == 1 else [202]
        self.app._resolve_spell_slot_profile = lambda caster_name: (caster_name, {"1": {"current": 1}, "2": {"current": 1}})
        self.app._consume_spell_slot_for_cast = (
            lambda caster_name, slot_level, minimum_level: self.slot_spend_calls.append((caster_name, slot_level, minimum_level))
            or (True, "", slot_level)
        )
        self.app._consume_resource_pool_for_cast = lambda *args, **kwargs: (False, "")
        self.app._lan = type(
            "LanStub",
            (),
            {
                "toast": lambda _self, ws_id, message: self.toasts.append((ws_id, message)),
                "_append_lan_log": lambda *args, **kwargs: None,
                "_loop": object(),
                "_send_async": lambda _self, ws_id, payload: self.sent.append((ws_id, payload)),
                "play_ko": lambda *_args, **_kwargs: None,
            },
        )()
        self.app._name_role_memory = {"Vicnor": "pc", "Enemy": "enemy"}
        self.app._lan_positions = {1: (5, 5), 2: (6, 5)}
        self.app._lan_live_map_data = lambda: (20, 20, set(), {}, dict(self.app._lan_positions))
        self.app._map_window = None
        self.app._lan_aoes = {}
        self.app._pending_reaction_offers = {}
        self.app._pending_shield_resolutions = {}
        self.app._pending_hellish_rebuke_resolutions = {}
        self.app._pending_absorb_elements_resolutions = {}
        self.app._reaction_prefs_by_cid = {1: {"absorb_elements": "ask"}}
        self.app.in_combat = True
        self.app.current_cid = 2
        self.app.round_num = 1
        self.app.turn_num = 1
        self.app.start_cid = None
        self.app.combatants = {
            1: type("C", (), {"cid": 1, "name": "Vicnor", "reaction_remaining": 1, "hp": 20, "ac": 12, "condition_stacks": [], "saving_throws": {}, "ability_mods": {}, "exhaustion_level": 0, "is_pc": True})(),
            2: type("C", (), {"cid": 2, "name": "Enemy", "reaction_remaining": 1, "action_remaining": 1, "bonus_action_remaining": 1, "attack_resource_remaining": 1, "move_remaining": 30, "move_total": 30, "hp": 40, "ac": 10, "condition_stacks": [], "saving_throws": {}, "ability_mods": {}, "is_pc": False})(),
        }
        self.app._pc_name_for = lambda cid: {1: "Vicnor", 2: "Enemy"}.get(int(cid), "PC")

        def profile_for(name):
            key = str(name or "").strip().lower()
            if key == "vicnor":
                return {
                    "features": [],
                    "attacks": {"weapon_to_hit": 7, "weapons": [{"id": "scimitar", "name": "Scimitar", "category": "martial_melee", "to_hit": 7, "range": "5", "one_handed": {"damage_formula": "1d6+4", "damage_type": "slashing"}, "effect": {}}]},
                    "leveling": {"classes": [{"name": "Rogue", "attacks_per_action": 1}]},
                    "spellcasting": {"prepared_spells": {"prepared": ["absorb-elements"]}},
                }
            return {
                "features": [],
                "attacks": {"weapon_to_hit": 5, "weapons": [{"id": "sword", "name": "Sword", "category": "martial_melee", "to_hit": 5, "range": "5", "one_handed": {"damage_formula": "1d8+3", "damage_type": "slashing"}, "effect": {}}]},
                "leveling": {"classes": [{"name": "Fighter", "attacks_per_action": 1}]},
                "spellcasting": {"prepared_spells": {"prepared": []}},
            }

        self.app._profile_for_player_name = profile_for

    def _incoming_fire_attack(self):
        return {
            "type": "attack_request",
            "cid": 2,
            "_claimed_cid": 2,
            "_ws_id": 77,
            "target_cid": 1,
            "weapon_id": "sword",
            "attack_roll": 15,
            "damage_entries": [{"amount": 10, "type": "fire"}],
        }

    def test_accept_absorb_elements_reduces_triggering_damage(self):
        self.app._lan_apply_action(self._incoming_fire_attack())
        offers = [payload for _ws, payload in self.sent if isinstance(payload, dict) and payload.get("trigger") == "absorb_elements"]
        self.assertTrue(offers)
        req_id = offers[-1]["request_id"]
        self.app._lan_apply_action(
            {
                "type": "reaction_response",
                "cid": 1,
                "_claimed_cid": 1,
                "_ws_id": 101,
                "request_id": req_id,
                "choice": "cast_absorb_elements_fire",
                "slot_level": 2,
            }
        )
        self.assertEqual(self.slot_spend_calls[-1], ("Vicnor", 2, 1))
        self.assertEqual(int(getattr(self.app.combatants[1], "hp", 0) or 0), 15)

    def test_bonus_damage_applies_once_on_next_melee_hit(self):
        self.app._activate_absorb_elements(self.app.combatants[1], "fire", 2)
        self.app.current_cid = 1
        self.app.turn_num = 2
        self.app._absorb_elements_turn_start(self.app.combatants[1])

        self.app._lan_apply_action(
            {
                "type": "attack_request",
                "cid": 1,
                "_claimed_cid": 1,
                "_ws_id": 101,
                "target_cid": 2,
                "weapon_id": "scimitar",
                "attack_roll": 15,
                "damage_entries": [{"amount": 6, "type": "slashing"}],
            }
        )
        results = [payload for _ws, payload in self.sent if isinstance(payload, dict) and payload.get("type") == "attack_result"]
        self.assertTrue(results)
        self.assertTrue(any(str(entry.get("type") or "").strip().lower() == "fire" for entry in results[-1].get("damage_entries", [])))

        self.app._lan_apply_action(
            {
                "type": "attack_request",
                "cid": 1,
                "_claimed_cid": 1,
                "_ws_id": 101,
                "target_cid": 2,
                "weapon_id": "scimitar",
                "attack_roll": 15,
                "damage_entries": [{"amount": 6, "type": "slashing"}],
            }
        )
        latest = [payload for _ws, payload in self.sent if isinstance(payload, dict) and payload.get("type") == "attack_result"][-1]
        self.assertFalse(any(str(entry.get("type") or "").strip().lower() == "fire" for entry in latest.get("damage_entries", [])))


class AbsorbElementsDataTests(unittest.TestCase):
    def test_vicnor_has_absorb_elements_as_free_prepared_spell(self):
        repo_root = Path(__file__).resolve().parent.parent
        vicnor = yaml.safe_load((repo_root / "players" / "vicnor.yaml").read_text(encoding="utf-8")) or {}
        spellcasting = vicnor.get("spellcasting") if isinstance(vicnor.get("spellcasting"), dict) else {}
        prepared_block = spellcasting.get("prepared_spells") if isinstance(spellcasting.get("prepared_spells"), dict) else {}
        prepared = [str(item).strip().lower() for item in (prepared_block.get("prepared") or []) if str(item).strip()]
        free = [str(item).strip().lower() for item in (prepared_block.get("free") or []) if str(item).strip()]
        self.assertIn("absorb-elements", prepared)
        self.assertIn("absorb-elements", free)


if __name__ == "__main__":
    unittest.main()
