"""Regression tests for Counterspell reaction (bounded core).

Tests the offer creation on a hostile spellcast within 60 ft, slot+reaction
consumption on accept, spell interruption via the _spell_counterspelled flag,
and gating when no counterspell is prepared / no 3rd+ slot is available.

The counterspell core mirrors the Spell Stopper reaction (same seam in
``_adjudicate_spell_target_request``), but is gated on a prepared spell +
3rd-level slot instead of an equipped item + pool. Success/failure is driven
by the caster's Constitution save against the counterspeller's spell save DC.
"""

import copy
import unittest

import dnd_initative_tracker as tracker_mod


class CounterspellReactionTests(unittest.TestCase):
    def setUp(self):
        self.sent = []
        self.toasts = []
        self.logs = []
        self.app = object.__new__(tracker_mod.InitiativeTracker)
        self.app._oplog = lambda *args, **kwargs: None
        self.app._is_admin_token_valid = lambda token: False
        self.app._summon_can_be_controlled_by = lambda claimed, target: False
        self.app._is_valid_summon_turn_for_controller = lambda controlling, target, current: True
        self.app._mount_action_is_restricted = lambda *args, **kwargs: False
        self.app._find_action_entry = lambda c, spend, action: {"name": action}
        self.app._action_name_key = lambda v: str(v or "").strip().lower()
        self.app._lan_aura_effects_for_target = lambda target: {}
        self.app._adjust_damage_entries_for_target = lambda target, entries: {"entries": list(entries), "notes": []}
        self.app._apply_damage_to_target_with_temp_hp = lambda target, dmg: {"hp_after": max(0, int(target.hp) - int(dmg))}
        self.app._remove_combatants_with_lan_cleanup = lambda cids: None
        self.app._retarget_current_after_removal = lambda *args, **kwargs: None
        self.app._unit_has_sentinel_feat = lambda unit: False
        self.app._lan_apply_forced_movement = lambda *args, **kwargs: False
        self.app._clear_hide_state = lambda *args, **kwargs: None
        self.saved_spell_slot_payloads = []
        self.pool_set_calls = []
        self._profile_data = {
            "Eldramar Thunderclopper": {
                "name": "Eldramar Thunderclopper",
                "features": [],
                "attacks": {"weapon_to_hit": 3},
                "leveling": {"classes": [{"name": "Wizard", "attacks_per_action": 1}]},
                "spellcasting": {
                    "prepared_spells": {"prepared": ["counterspell", "shield"]},
                },
            },
            "Enemy Caster": {
                "name": "Enemy Caster",
                "features": [],
                "attacks": {"weapon_to_hit": 3},
                "leveling": {"classes": [{"name": "Sorcerer", "attacks_per_action": 1}]},
                "spellcasting": {"prepared_spells": {"prepared": ["magic-missile"]}},
            },
        }

        def _profile_for(name):
            profile = self._profile_data.get(str(name or "").strip())
            if isinstance(profile, dict):
                return copy.deepcopy(profile)
            return {
                "name": name,
                "features": [],
                "attacks": {"weapon_to_hit": 3},
                "leveling": {"classes": [{"name": "Sorcerer", "attacks_per_action": 1}]},
                "spellcasting": {"prepared_spells": {"prepared": ["magic-missile"]}},
            }

        self.app._profile_for_player_name = _profile_for
        self.app._pc_name_for = lambda cid: {1: "Eldramar Thunderclopper", 2: "Enemy Caster"}.get(int(cid), "PC")

        self._slot_state = {"3": {"current": 1, "max": 1}}

        def _resolve_slot_profile(caster_name):
            if "Eldramar" in (caster_name or ""):
                return caster_name, self._slot_state
            profile = self._profile_data.get(str(caster_name or "").strip()) or {}
            spellcasting = profile.get("spellcasting") if isinstance(profile.get("spellcasting"), dict) else {}
            slots = self.app._normalize_spell_slots(spellcasting.get("spell_slots"))
            return caster_name, slots

        self.app._resolve_spell_slot_profile = _resolve_slot_profile

        def _consume_slot(caster_name, slot_level, minimum_level):
            if "Eldramar" not in (caster_name or ""):
                return False, "not_caster", 0
            lvl = int(slot_level or minimum_level or 3)
            entry = self._slot_state.get(str(lvl))
            if not isinstance(entry, dict) or int(entry.get("current", 0) or 0) <= 0:
                return False, "no_slot", 0
            entry["current"] = int(entry["current"]) - 1
            return True, "", lvl

        self.app._consume_spell_slot_for_cast = _consume_slot
        self.app._consume_resource_pool_for_cast = lambda *a, **k: (False, "no_pool")
        self.app._save_player_spell_slots = self._save_player_spell_slots
        self.app._set_player_resource_pool_current = self._set_player_resource_pool_current

        self.app._use_action = lambda c, **kwargs: True
        self.app._use_bonus_action = lambda c, **kwargs: True
        self.app._use_reaction = lambda c, **kwargs: (
            setattr(c, "reaction_remaining", max(0, int(getattr(c, "reaction_remaining", 0)) - 1)) or True
        ) if int(getattr(c, "reaction_remaining", 0) or 0) > 0 else False
        self.app._rebuild_table = lambda *args, **kwargs: None
        self.app._lan_force_state_broadcast = lambda *args, **kwargs: None
        self.app._log = lambda msg, **kwargs: self.logs.append(msg)
        self.app._find_ws_for_cid = lambda cid: [101] if int(cid) == 1 else [202]

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

        self.app._name_role_memory = {"Eldramar Thunderclopper": "pc", "Enemy Caster": "enemy"}
        # 2 grid squares = 10 ft; well within 60 ft counterspell range.
        self.app._lan_positions = {1: (5, 5), 2: (7, 5)}
        self.app._lan_live_map_data = lambda: (20, 20, set(), {}, dict(self.app._lan_positions))
        self.app._map_window = None
        self.app._lan_aoes = {}
        self.app._pending_reaction_offers = {}
        self.app._pending_shield_resolutions = {}
        self.app._reaction_prefs_by_cid = {1: {}}
        self.app.in_combat = True
        self.app.current_cid = 2
        self.app.round_num = 1
        self.app.turn_num = 1
        self.app.start_cid = None

        eldramar = type("C", (), {
            "cid": 1,
            "name": "Eldramar Thunderclopper",
            "reaction_remaining": 1,
            "hp": 40,
            "ac": 14,
            "condition_stacks": [],
            "saving_throws": {},
            "ability_mods": {},
            "exhaustion_level": 0,
            "is_pc": True,
            "inventory": {"items": []},
        })()
        enemy = type("C", (), {
            "cid": 2,
            "name": "Enemy Caster",
            "reaction_remaining": 1,
            "action_remaining": 1,
            "bonus_action_remaining": 1,
            "attack_resource_remaining": 1,
            "move_remaining": 30,
            "move_total": 30,
            "hp": 30,
            "ac": 12,
            "condition_stacks": [],
            "is_pc": False,
        })()
        self.app.combatants = {1: eldramar, 2: enemy}

        self.app._normalize_player_resource_pools = tracker_mod.InitiativeTracker._normalize_player_resource_pools.__get__(
            self.app,
            tracker_mod.InitiativeTracker,
        )

    def _set_player_resource_pool_current(self, caster_name, pool_id, new_current):
        self.pool_set_calls.append((str(caster_name), str(pool_id), int(new_current)))
        profile = self._profile_data.get(str(caster_name or "").strip())
        if not isinstance(profile, dict):
            return False, "missing_profile"
        resources = profile.setdefault("resources", {})
        pools = resources.setdefault("pools", [])
        for entry in pools:
            if not isinstance(entry, dict):
                continue
            if str(entry.get("id") or "").strip().lower() != str(pool_id or "").strip().lower():
                continue
            entry["current"] = int(new_current)
            return True, ""
        return False, "missing_pool"

    def _save_player_spell_slots(self, caster_name, slots):
        self.saved_spell_slot_payloads.append(copy.deepcopy(slots))
        profile = self._profile_data.get(str(caster_name or "").strip())
        if isinstance(profile, dict):
            spellcasting = profile.setdefault("spellcasting", {})
            spellcasting["spell_slots"] = copy.deepcopy(slots)
        return slots

    def _install_pact_magic_caster(self, *, current, count=2, level=4):
        self._profile_data["Enemy Caster"] = {
            "name": "Enemy Caster",
            "features": [],
            "attacks": {"weapon_to_hit": 3},
            "leveling": {"classes": [{"name": "Warlock", "attacks_per_action": 1}]},
            "spellcasting": {
                "enabled": True,
                "prepared_spells": {"prepared": ["guiding-bolt", "fireball"]},
                "spell_slots": {str(spell_level): {"max": 0, "current": 0} for spell_level in range(1, 10)},
                "pact_magic_slots": {"level": int(level), "count": int(count)},
            },
            "resources": {
                "pools": [
                    {
                        "id": "pact_magic_slots",
                        "label": f"Pact Magic Slots (Level {int(level)})",
                        "current": int(current),
                        "max": int(count),
                        "max_formula": str(int(count)),
                        "reset": "short_rest",
                        "slot_level": int(level),
                    }
                ]
            },
        }

    def _install_mixed_slot_caster(self, *, standard_current=4, standard_max=4, pact_current=1, pact_count=2, pact_level=1):
        spell_slots = {str(spell_level): {"max": 0, "current": 0} for spell_level in range(1, 10)}
        spell_slots["1"] = {"max": int(standard_max), "current": int(standard_current)}
        self._profile_data["Enemy Caster"] = {
            "name": "Enemy Caster",
            "features": [],
            "attacks": {"weapon_to_hit": 3},
            "leveling": {
                "classes": [
                    {"name": "Bard", "attacks_per_action": 1, "level": 9},
                    {"name": "Warlock", "attacks_per_action": 1, "level": 2},
                ]
            },
            "spellcasting": {
                "enabled": True,
                "prepared_spells": {"prepared": ["guiding-bolt", "fireball"]},
                "spell_slots": spell_slots,
                "pact_magic_slots": {"level": int(pact_level), "count": int(pact_count)},
            },
            "resources": {
                "pools": [
                    {
                        "id": "pact_magic_slots",
                        "label": f"Pact Magic Slots (Level {int(pact_level)})",
                        "current": int(pact_current),
                        "max": int(pact_count),
                        "max_formula": str(int(pact_count)),
                        "reset": "short_rest",
                        "slot_level": int(pact_level),
                    }
                ]
            },
        }

    def _spell_target_msg(self, caster_cid=2, target_cid=1, spell_slug="guiding-bolt", spell_name="Guiding Bolt", slot_level=None):
        msg = {
            "type": "spell_target_request",
            "cid": caster_cid,
            "_claimed_cid": caster_cid,
            "_ws_id": 202 if caster_cid == 2 else 101,
            "target_cid": target_cid,
            "spell_slug": spell_slug,
            "spell_name": spell_name,
            "spell_mode": "auto_hit",
            "damage_entries": [{"amount": 9, "type": "radiant"}],
        }
        if slot_level is not None:
            msg["slot_level"] = int(slot_level)
        return msg

    def _offers(self, trigger="counterspell"):
        return [
            payload for _ws, payload in self.sent
            if isinstance(payload, dict)
            and payload.get("type") == "reaction_offer"
            and payload.get("trigger") == trigger
        ]

    def test_counterspell_offer_appears_on_hostile_spellcast_in_range(self):
        self.app._find_spell_preset = lambda *a, **k: {
            "slug": "guiding-bolt",
            "id": "guiding-bolt",
            "name": "Guiding Bolt",
            "mechanics": {"sequence": []},
        }
        self.app._infer_spell_targeting_mode = lambda preset: "auto_hit"

        self.app._lan_apply_action(self._spell_target_msg())

        offers = self._offers()
        self.assertTrue(offers, "Counterspell offer should be created")
        self.assertEqual(offers[-1]["reactor_cid"], 1)

    def test_counterspell_offer_not_created_when_out_of_range(self):
        # 60 ft ≈ 12 squares; put caster 20 squares (100 ft) away.
        self.app._lan_positions = {1: (5, 5), 2: (25, 5)}
        self.app._find_spell_preset = lambda *a, **k: {
            "slug": "guiding-bolt",
            "id": "guiding-bolt",
            "name": "Guiding Bolt",
            "mechanics": {"sequence": []},
        }
        self.app._infer_spell_targeting_mode = lambda preset: "auto_hit"

        self.app._lan_apply_action(self._spell_target_msg())
        self.assertFalse(self._offers(), "Counterspell should not be offered out of range")

    def test_counterspell_offer_not_created_without_prepared_spell(self):
        # Swap profile so Eldramar no longer has counterspell prepared.
        original = self.app._profile_for_player_name
        self.app._profile_for_player_name = lambda name: {
            **(original(name) or {}),
            "spellcasting": {"prepared_spells": {"prepared": ["shield"]}},
        }
        self.app._find_spell_preset = lambda *a, **k: {
            "slug": "guiding-bolt",
            "id": "guiding-bolt",
            "name": "Guiding Bolt",
            "mechanics": {"sequence": []},
        }
        self.app._infer_spell_targeting_mode = lambda preset: "auto_hit"

        self.app._lan_apply_action(self._spell_target_msg())
        self.assertFalse(self._offers(), "Counterspell requires the spell prepared")

    def test_counterspell_offer_not_created_without_third_slot(self):
        self._slot_state["3"] = {"current": 0, "max": 1}
        self.app._find_spell_preset = lambda *a, **k: {
            "slug": "guiding-bolt",
            "id": "guiding-bolt",
            "name": "Guiding Bolt",
            "mechanics": {"sequence": []},
        }
        self.app._infer_spell_targeting_mode = lambda preset: "auto_hit"

        self.app._lan_apply_action(self._spell_target_msg())
        self.assertFalse(self._offers(), "Counterspell requires a 3rd+ slot")

    def test_counterspell_not_offered_for_counterspell_cast(self):
        # Even though reactor is eligible, bounded core suppresses
        # counterspell-of-counterspell to avoid recursion.
        self.app._find_spell_preset = lambda *a, **k: {
            "slug": "counterspell",
            "id": "counterspell",
            "name": "Counterspell",
            "mechanics": {"sequence": []},
        }
        self.app._infer_spell_targeting_mode = lambda preset: "auto_hit"

        msg = self._spell_target_msg(spell_slug="counterspell", spell_name="Counterspell")
        self.app._lan_apply_action(msg)
        self.assertFalse(self._offers(), "counterspell-on-counterspell should be suppressed")

    def _force_save_roll(self, value):
        """Force the Constitution save d20 roll to ``value`` for the contest."""
        self.app._roll_save_with_mode = lambda target, ability, **kwargs: (int(value), int(value))

    def _force_dc(self, dc):
        """Force ``_compute_spell_save_dc`` to return ``dc`` regardless of profile."""
        self.app._compute_spell_save_dc = lambda profile: int(dc)

    def test_counterspell_accept_spends_reaction_and_slot(self):
        self.app._find_spell_preset = lambda *a, **k: {
            "slug": "guiding-bolt",
            "id": "guiding-bolt",
            "name": "Guiding Bolt",
            "mechanics": {"sequence": []},
        }
        self.app._infer_spell_targeting_mode = lambda preset: "auto_hit"
        # Force a failing save so the contest always interrupts (this test
        # asserts only resource spend + interruption, not the contest branches).
        self._force_dc(15)
        self._force_save_roll(1)

        self.app._lan_apply_action(self._spell_target_msg())
        offers = self._offers()
        self.assertTrue(offers, "Offer expected")
        req_id = offers[-1]["request_id"]

        eldramar = self.app.combatants[1]
        self.assertEqual(eldramar.reaction_remaining, 1)
        self.assertEqual(self._slot_state["3"]["current"], 1)

        response = self.app._ensure_player_commands().reaction_response(
            {
                "type": "reaction_response",
                "cid": 1,
                "_claimed_cid": 1,
                "_ws_id": 101,
                "request_id": req_id,
                "choice": "counterspell_yes",
            },
            cid=1,
            ws_id=101,
        )

        self.assertTrue(response.get("ok"), f"Counterspell accept should succeed: {response}")
        self.assertEqual(eldramar.reaction_remaining, 0, "reaction should be spent")
        self.assertEqual(self._slot_state["3"]["current"], 0, "3rd-level slot should be spent")
        self.assertTrue(response.get("resume_dispatched"), "Resume dispatch should have been triggered")
        self.assertTrue(
            any("countered" in str(log).lower() for log in self.logs),
            f"Interruption should be logged; logs={self.logs}",
        )
        contest = response.get("contest") or {}
        self.assertTrue(contest.get("countered"), "contest dict should report countered=True")
        self.assertEqual(contest.get("dc"), 15)

    def test_contest_failure_allows_spell_through(self):
        """Caster saves: reaction + slot spent by counterspeller, but the spell proceeds."""
        self.app._find_spell_preset = lambda *a, **k: {
            "slug": "guiding-bolt",
            "id": "guiding-bolt",
            "name": "Guiding Bolt",
            "mechanics": {"sequence": []},
        }
        self.app._infer_spell_targeting_mode = lambda preset: "auto_hit"
        self._force_dc(10)
        self._force_save_roll(20)  # caster auto-saves

        self.app._lan_apply_action(self._spell_target_msg())
        req_id = self._offers()[-1]["request_id"]

        response = self.app._ensure_player_commands().reaction_response(
            {
                "type": "reaction_response",
                "cid": 1,
                "_claimed_cid": 1,
                "_ws_id": 101,
                "request_id": req_id,
                "choice": "counterspell_yes",
            },
            cid=1,
            ws_id=101,
        )

        self.assertTrue(response.get("ok"), f"Accept should succeed even on contest loss: {response}")
        contest = response.get("contest") or {}
        self.assertFalse(contest.get("countered"), "contest should report countered=False on save")
        # Counterspeller still pays reaction + slot (5e RAW).
        self.assertEqual(self.app.combatants[1].reaction_remaining, 0)
        self.assertEqual(self._slot_state["3"]["current"], 0)
        self.assertFalse(
            any("countered" in str(log).lower() and "caster" not in str(log).lower() for log in self.logs if "countered!" in str(log).lower()),
            "No interruption-success log on contest failure",
        )
        self.assertTrue(
            any("succeeds on the save" in str(log).lower() for log in self.logs),
            f"Save-success should be logged; logs={self.logs}",
        )

    def test_contest_success_interrupts_spell(self):
        """Caster fails save: spell is countered."""
        self.app._find_spell_preset = lambda *a, **k: {
            "slug": "guiding-bolt",
            "id": "guiding-bolt",
            "name": "Guiding Bolt",
            "mechanics": {"sequence": []},
        }
        self.app._infer_spell_targeting_mode = lambda preset: "auto_hit"
        self._force_dc(15)
        self._force_save_roll(5)

        self.app._lan_apply_action(self._spell_target_msg())
        req_id = self._offers()[-1]["request_id"]

        response = self.app._ensure_player_commands().reaction_response(
            {
                "type": "reaction_response",
                "cid": 1,
                "_claimed_cid": 1,
                "_ws_id": 101,
                "request_id": req_id,
                "choice": "counterspell_yes",
            },
            cid=1,
            ws_id=101,
        )

        self.assertTrue(response.get("ok"))
        contest = response.get("contest") or {}
        self.assertTrue(contest.get("countered"))
        self.assertTrue(
            any("spell was countered" in str(log).lower() for log in self.logs),
            f"Interruption log expected; logs={self.logs}",
        )

    def test_counterspell_refunds_pact_slot_for_targeted_pact_magic_caster(self):
        self._install_pact_magic_caster(current=1, count=2, level=4)
        self.app._find_spell_preset = lambda *a, **k: {
            "slug": "guiding-bolt",
            "id": "guiding-bolt",
            "name": "Guiding Bolt",
            "mechanics": {"sequence": []},
        }
        self.app._infer_spell_targeting_mode = lambda preset: "auto_hit"
        self._force_dc(15)
        self._force_save_roll(1)

        self.app._lan_apply_action(self._spell_target_msg(slot_level=4))
        req_id = self._offers()[-1]["request_id"]

        response = self.app._ensure_player_commands().reaction_response(
            {
                "type": "reaction_response",
                "cid": 1,
                "_claimed_cid": 1,
                "_ws_id": 101,
                "request_id": req_id,
                "choice": "counterspell_yes",
            },
            cid=1,
            ws_id=101,
        )

        self.assertTrue(response.get("ok"), f"Counterspell accept should succeed: {response}")
        self.assertEqual(self.pool_set_calls, [("Enemy Caster", "pact_magic_slots", 2)])
        self.assertEqual(self.saved_spell_slot_payloads, [], "pact refund should not mint fake standard spell slots")
        pact_pool = self._profile_data["Enemy Caster"]["resources"]["pools"][0]
        self.assertEqual(int(pact_pool.get("current") or 0), 2)

    def test_counterspell_refunds_standard_slot_for_mixed_slot_caster_using_recorded_provenance(self):
        self._install_mixed_slot_caster(standard_current=4, standard_max=4, pact_current=1, pact_count=2, pact_level=1)
        self.app._find_spell_preset = lambda *a, **k: {
            "slug": "guiding-bolt",
            "id": "guiding-bolt",
            "name": "Guiding Bolt",
            "level": 1,
            "mechanics": {"sequence": []},
        }
        self.app._infer_spell_targeting_mode = lambda preset: "auto_hit"
        self.app._resolve_spell_spend_type = lambda preset, msg, payload: "action"
        self.app._combatant_can_cast_spell = lambda c, spend: True
        self.app._spellcast_blocked_by_environment = lambda c, preset: (False, "")
        self.app._spell_label_from_identifiers = lambda *a, **k: "Guiding Bolt"
        self.app._spell_cast_log_message = lambda *a, **k: "cast"
        self.app._smite_slug_from_preset = lambda preset: None
        self._force_dc(15)
        self._force_save_roll(1)

        cast_msg = {
            "type": "cast_spell",
            "cid": 2,
            "_claimed_cid": 2,
            "_ws_id": 202,
            "spell_slug": "guiding-bolt",
            "spell_id": "guiding-bolt",
            "spell_name": "Guiding Bolt",
            "slot_level": 1,
            "payload": {
                "action_type": "action",
                "name": "Guiding Bolt",
            },
        }
        self.app._handle_cast_spell_request(cast_msg, cid=2, ws_id=202, is_admin=False, claimed=2)

        self.assertGreaterEqual(len(self.saved_spell_slot_payloads), 1)
        self.assertEqual(int((self.saved_spell_slot_payloads[-1].get("1") or {}).get("current") or 0), 3)
        self.assertEqual(self.pool_set_calls, [], "mixed-slot cast should spend the standard slot before pact")

        self.app._lan_apply_action(self._spell_target_msg(slot_level=1))
        self.assertNotIn(2, self.app._pending_spell_target_resource_spends())
        req_id = self._offers()[-1]["request_id"]

        response = self.app._ensure_player_commands().reaction_response(
            {
                "type": "reaction_response",
                "cid": 1,
                "_claimed_cid": 1,
                "_ws_id": 101,
                "request_id": req_id,
                "choice": "counterspell_yes",
            },
            cid=1,
            ws_id=101,
        )

        self.assertTrue(response.get("ok"), f"Counterspell accept should succeed: {response}")
        self.assertGreaterEqual(len(self.saved_spell_slot_payloads), 2)
        self.assertEqual(int((self.saved_spell_slot_payloads[-1].get("1") or {}).get("current") or 0), 4)
        self.assertEqual(self.pool_set_calls, [], "refund should not guess pact usage when standard slot provenance was recorded")
        pact_pool = self._profile_data["Enemy Caster"]["resources"]["pools"][0]
        self.assertEqual(int(pact_pool.get("current") or 0), 1)

    def test_direct_spell_target_request_auto_authorizes_before_counterspell_refund_path(self):
        self._install_mixed_slot_caster(standard_current=4, standard_max=4, pact_current=1, pact_count=2, pact_level=1)
        self.app._find_spell_preset = lambda *a, **k: {
            "slug": "guiding-bolt",
            "id": "guiding-bolt",
            "name": "Guiding Bolt",
            "level": 1,
            "mechanics": {"sequence": []},
        }
        self.app._infer_spell_targeting_mode = lambda preset: "auto_hit"
        self.app._combatant_can_cast_spell = lambda c, spend: True
        self.app._spellcast_blocked_by_environment = lambda c, preset: (False, "")
        self.app._spell_label_from_identifiers = lambda *a, **k: "Guiding Bolt"
        self.app._spell_cast_log_message = lambda *a, **k: "cast"
        self.app._smite_slug_from_preset = lambda preset: None
        self.app.combatants[2].spell_cast_remaining = 1
        self.app.combatants[2].actions = [{"name": "Magic"}]
        self._force_dc(15)
        self._force_save_roll(1)

        msg = self._spell_target_msg(slot_level=1)
        self.app._lan_apply_action(msg)

        self.assertTrue(msg.get("_spell_cast_authorized"))
        self.assertEqual(msg.get("_spell_cast_authority_source"), "spell_target_request_direct")
        self.assertEqual(msg.get("_spell_resource_spend_provenance"), {"pool_id": "spell_slots", "slot_level": 1})
        self.assertGreaterEqual(len(self.saved_spell_slot_payloads), 1)
        self.assertEqual(int((self.saved_spell_slot_payloads[-1].get("1") or {}).get("current") or 0), 3)

        req_id = self._offers()[-1]["request_id"]
        response = self.app._ensure_player_commands().reaction_response(
            {
                "type": "reaction_response",
                "cid": 1,
                "_claimed_cid": 1,
                "_ws_id": 101,
                "request_id": req_id,
                "choice": "counterspell_yes",
            },
            cid=1,
            ws_id=101,
        )

        self.assertTrue(response.get("ok"), f"Counterspell accept should succeed: {response}")
        self.assertGreaterEqual(len(self.saved_spell_slot_payloads), 2)
        self.assertEqual(int((self.saved_spell_slot_payloads[-1].get("1") or {}).get("current") or 0), 4)
        self.assertEqual(self.pool_set_calls, [], "direct targeted-cast authority should preserve standard-slot provenance")

    def test_aoe_counterspell_for_pact_magic_caster_does_not_touch_pact_pool(self):
        self._install_pact_magic_caster(current=2, count=2, level=4)
        self._force_dc(15)
        self._force_save_roll(1)

        self.app._find_spell_preset = lambda *a, **k: {
            "slug": "fireball",
            "id": "fireball",
            "name": "Fireball",
            "level": 3,
            "range": "150 feet",
            "mechanics": {"sequence": []},
        }
        self.app._resolve_spell_spend_type = lambda preset, msg, payload: "action"
        self.app._combatant_can_cast_spell = lambda c, spend: True
        self.app._spellcast_blocked_by_environment = lambda c, preset: (False, "")
        self.app._spell_label_from_identifiers = lambda *a, **k: "Fireball"
        self.app._spell_cast_log_message = lambda *a, **k: "cast"
        self.app._normalize_map_environment_metadata = lambda env: {}
        self.app._find_summon_requested_variant = lambda *a, **k: None
        self.app._lan_auto_resolve_cast_aoe = lambda *a, **k: False

        msg = {
            "type": "cast_aoe",
            "cid": 2,
            "_claimed_cid": 2,
            "_ws_id": 202,
            "spell_slug": "fireball",
            "spell_name": "Fireball",
            "slot_level": 4,
            "payload": {
                "shape": "sphere",
                "center_col": 10,
                "center_row": 10,
                "radius_ft": 20,
            },
        }

        self.app._handle_cast_aoe_request(msg, cid=2, ws_id=202, is_admin=False, claimed=2)
        req_id = self._offers()[-1]["request_id"]

        response = self.app._ensure_player_commands().reaction_response(
            {
                "type": "reaction_response",
                "cid": 1,
                "_claimed_cid": 1,
                "_ws_id": 101,
                "request_id": req_id,
                "choice": "counterspell_yes",
            },
            cid=1,
            ws_id=101,
        )

        self.assertTrue(response.get("ok"), f"AoE counterspell accept should succeed: {response}")
        self.assertEqual(self.pool_set_calls, [], "AoE counterspell should not need a pact-slot refund")
        pact_pool = self._profile_data["Enemy Caster"]["resources"]["pools"][0]
        self.assertEqual(int(pact_pool.get("current") or 0), 2)

    def test_aoe_counterspell_offer_fires(self):
        """Counterspell offer appears on a cast_aoe cast (e.g. fireball)."""
        self.app._find_spell_preset = lambda *a, **k: {
            "slug": "fireball",
            "id": "fireball",
            "name": "Fireball",
            "level": 3,
            "range": "150 feet",
            "mechanics": {"sequence": []},
        }
        self.app._resolve_spell_spend_type = lambda preset, msg, payload: "action"
        self.app._combatant_can_cast_spell = lambda c, spend: True
        self.app._spellcast_blocked_by_environment = lambda c, preset: (False, "")
        self.app._spell_label_from_identifiers = lambda *a, **k: "Fireball"
        self.app._spell_cast_log_message = lambda *a, **k: "cast"
        self.app._normalize_map_environment_metadata = lambda env: {}
        self.app._find_summon_requested_variant = lambda *a, **k: None
        self.app._lan_auto_resolve_cast_aoe = lambda *a, **k: False

        msg = {
            "type": "cast_aoe",
            "cid": 2,
            "_claimed_cid": 2,
            "_ws_id": 202,
            "spell_slug": "fireball",
            "spell_name": "Fireball",
            "slot_level": 3,
            "payload": {
                "shape": "sphere",
                "center_col": 10,
                "center_row": 10,
                "radius_ft": 20,
            },
        }

        self.app._handle_cast_aoe_request(msg, cid=2, ws_id=202, is_admin=False, claimed=2)
        offers = self._offers()
        self.assertTrue(offers, f"AoE cast should create counterspell offer; sent={self.sent}")
        self.assertEqual(offers[-1]["reactor_cid"], 1)
        # Resources should NOT be consumed yet — pre-offer insertion.
        self.assertEqual(self._slot_state["3"]["current"], 1, "caster's slot state untouched")

    def test_aoe_counterspell_accept_cancels_before_resources_consumed(self):
        """Accepting counterspell on an AoE cast (with contest-success) cancels before any
        template/damage is applied. Caster's resources remain intact because the offer
        fires before consumption on the AoE path."""
        # Eldramar's profile drives counterspeller DC calc; caster DC/saves forced.
        self._force_dc(15)
        self._force_save_roll(1)

        self.app._find_spell_preset = lambda *a, **k: {
            "slug": "fireball",
            "id": "fireball",
            "name": "Fireball",
            "level": 3,
            "range": "150 feet",
            "mechanics": {"sequence": []},
        }
        self.app._resolve_spell_spend_type = lambda preset, msg, payload: "action"
        self.app._combatant_can_cast_spell = lambda c, spend: True
        self.app._spellcast_blocked_by_environment = lambda c, preset: (False, "")
        self.app._spell_label_from_identifiers = lambda *a, **k: "Fireball"
        self.app._spell_cast_log_message = lambda *a, **k: "cast"
        self.app._normalize_map_environment_metadata = lambda env: {}
        self.app._find_summon_requested_variant = lambda *a, **k: None

        resolve_calls = []
        self.app._lan_auto_resolve_cast_aoe = lambda *a, **k: (resolve_calls.append(1) or False)

        msg = {
            "type": "cast_aoe",
            "cid": 2,
            "_claimed_cid": 2,
            "_ws_id": 202,
            "spell_slug": "fireball",
            "spell_name": "Fireball",
            "slot_level": 3,
            "payload": {
                "shape": "sphere",
                "center_col": 10,
                "center_row": 10,
                "radius_ft": 20,
            },
        }

        self.app._handle_cast_aoe_request(msg, cid=2, ws_id=202, is_admin=False, claimed=2)
        req_id = self._offers()[-1]["request_id"]

        response = self.app._ensure_player_commands().reaction_response(
            {
                "type": "reaction_response",
                "cid": 1,
                "_claimed_cid": 1,
                "_ws_id": 101,
                "request_id": req_id,
                "choice": "counterspell_yes",
            },
            cid=1,
            ws_id=101,
        )

        self.assertTrue(response.get("ok"), f"AoE counterspell accept should succeed: {response}")
        contest = response.get("contest") or {}
        self.assertTrue(contest.get("countered"), "contest should succeed with forced failing save")
        # No AoE template resolution attempted in either the initial call or the resume.
        self.assertEqual(resolve_calls, [], "AoE should not have resolved when countered")
        self.assertTrue(
            any("spell was countered" in str(log).lower() for log in self.logs),
            f"Interruption log expected; logs={self.logs}",
        )

    def test_counterspell_decline_does_not_spend_resources(self):
        self.app._find_spell_preset = lambda *a, **k: {
            "slug": "guiding-bolt",
            "id": "guiding-bolt",
            "name": "Guiding Bolt",
            "mechanics": {"sequence": []},
        }
        self.app._infer_spell_targeting_mode = lambda preset: "auto_hit"

        self.app._lan_apply_action(self._spell_target_msg())
        offers = self._offers()
        self.assertTrue(offers)
        req_id = offers[-1]["request_id"]

        response = self.app._ensure_player_commands().reaction_response(
            {
                "type": "reaction_response",
                "cid": 1,
                "_claimed_cid": 1,
                "_ws_id": 101,
                "request_id": req_id,
                "choice": "counterspell_decline",
            },
            cid=1,
            ws_id=101,
        )

        self.assertTrue(response.get("ok"), f"Decline should succeed: {response}")
        eldramar = self.app.combatants[1]
        self.assertEqual(eldramar.reaction_remaining, 1, "No reaction spent on decline")
        self.assertEqual(self._slot_state["3"]["current"], 1, "No slot spent on decline")
        self.assertFalse(
            any("countered" in str(log).lower() for log in self.logs),
            f"No interruption log on decline; logs={self.logs}",
        )


if __name__ == "__main__":
    unittest.main()
