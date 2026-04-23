import random
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import yaml

import dnd_initative_tracker as tracker_mod


class Level11PlayerSupportTests(unittest.TestCase):
    """Backend support for level-11 player updates.

    Covers: Dorian Radiant Strikes damage_rider compile path, Malagrou
    Relentless Rage 0-HP intercept, Eldramar wand-granted shocking grasp
    and lightning bolt projection from the magic item.
    """

    def _new_app(self):
        app = object.__new__(tracker_mod.InitiativeTracker)
        app._oplog = lambda *args, **kwargs: None
        app._items_registry_payload = lambda: {"weapons": {}}
        app._find_spell_preset = lambda **_kwargs: None
        return app

    # --- Dorian: Radiant Strikes damage_rider compile ---------------------

    def test_radiant_strikes_damage_rider_compiles_on_feature_grants(self):
        app = self._new_app()
        normalized = app._normalize_player_profile(
            {
                "name": "Dorian",
                "features": [
                    {
                        "id": "radiant_strikes",
                        "name": "Radiant Strikes",
                        "grants": {
                            "damage_riders": [
                                {
                                    "id": "radiant_strikes",
                                    "trigger": ["melee_weapon_or_unarmed_attack"],
                                    "damage_formula": "1d8",
                                    "damage_type": "radiant",
                                }
                            ]
                        },
                    }
                ],
            },
            "dorian",
        )
        effects = normalized.get("feature_effects") or {}
        riders = effects.get("damage_riders") or []
        self.assertEqual(len(riders), 1)
        rider = riders[0]
        self.assertEqual(rider.get("id"), "radiant_strikes")
        self.assertIn("melee_weapon_or_unarmed_attack", rider.get("trigger") or [])
        self.assertEqual(rider.get("damage_type"), "radiant")
        self.assertEqual(rider.get("damage_formula"), "1d8")

    # --- Malagrou: Relentless Rage ---------------------------------------

    def _mock_barb_target(self, *, hp=0, rage=True, prev_uses=0, con_mod=3):
        target = SimpleNamespace(
            cid=1,
            name="Malagrou",
            hp=hp,
            temp_hp=0,
            is_pc=True,
            rage_active=rage,
            _relentless_rage_uses=prev_uses,
            saving_throws={"con": con_mod},
            ability_mods={"con": con_mod},
            ongoing_spell_effects=[],
        )
        return target

    def _build_rage_app(self, *, barb_level=11, roll=20):
        app = self._new_app()
        app._pc_name_for = lambda cid: "Malagrou"
        app._profile_for_player_name = lambda name: {"leveling": {"classes": [{"name": "Barbarian", "level": barb_level}]}}
        app._class_level_from_profile = lambda profile, class_name: barb_level if str(class_name or "").strip().lower() == "barbarian" else 0
        # Deterministic save roll
        app._roll_save_with_mode = lambda target, ability, advantage=False, disadvantage=False: (roll, roll)
        app._combatant_save_roll_mode = lambda combatant, ability: "normal"
        app._log = lambda *args, **kwargs: None
        return app

    def test_relentless_rage_save_success_raises_hp_to_twice_barb_level(self):
        app = self._build_rage_app(barb_level=11, roll=20)
        target = self._mock_barb_target()
        new_hp = app._maybe_apply_relentless_rage(target, hp_before=18, hp_after=0)
        self.assertEqual(new_hp, 22)
        self.assertEqual(target._relentless_rage_uses, 1)

    def test_relentless_rage_save_failure_returns_none(self):
        app = self._build_rage_app(barb_level=11, roll=1)
        target = self._mock_barb_target()
        new_hp = app._maybe_apply_relentless_rage(target, hp_before=18, hp_after=0)
        self.assertIsNone(new_hp)
        # Failure does not consume a use
        self.assertEqual(target._relentless_rage_uses, 0)

    def test_relentless_rage_escalates_dc_each_use(self):
        app = self._build_rage_app(barb_level=11, roll=14)
        target = self._mock_barb_target(prev_uses=1, con_mod=3)
        # DC = 10 + 5 * 1 = 15 ; roll 14 + 3 = 17 >= 15 passes
        new_hp = app._maybe_apply_relentless_rage(target, hp_before=30, hp_after=0)
        self.assertEqual(new_hp, 22)
        self.assertEqual(target._relentless_rage_uses, 2)
        # After a second use, DC = 20; same roll 14 + 3 = 17 < 20 fails
        result2 = app._maybe_apply_relentless_rage(target, hp_before=30, hp_after=0)
        self.assertIsNone(result2)

    def test_relentless_rage_ignored_when_not_raging(self):
        app = self._build_rage_app()
        target = self._mock_barb_target(rage=False)
        self.assertIsNone(app._maybe_apply_relentless_rage(target, hp_before=10, hp_after=0))

    def test_relentless_rage_ignored_below_barbarian_11(self):
        app = self._build_rage_app(barb_level=10, roll=20)
        target = self._mock_barb_target()
        self.assertIsNone(app._maybe_apply_relentless_rage(target, hp_before=10, hp_after=0))

    def test_relentless_rage_ignored_when_damage_does_not_zero_hp(self):
        app = self._build_rage_app()
        target = self._mock_barb_target()
        self.assertIsNone(app._maybe_apply_relentless_rage(target, hp_before=20, hp_after=5))

    # --- Eldramar: wand-granted shocking grasp + lightning bolt ----------

    def test_wand_of_sparking_projects_shocking_grasp_and_lightning_bolt_grants(self):
        wand_yaml = yaml.safe_load(
            Path("Items/Magic_Items/wand_of_sparking.yaml").read_text(encoding="utf-8")
        )
        grants = wand_yaml.get("grants") or {}
        self.assertIn("shocking-grasp", grants.get("always_prepared_spells") or [])
        self.assertIn("lightning-bolt", grants.get("always_prepared_spells") or [])
        pools = grants.get("pools") or []
        self.assertTrue(
            any(str((p or {}).get("id") or "") == "wand_of_sparking_lightning_bolt" for p in pools)
        )
        casts = ((grants.get("spells") or {}).get("casts")) or []
        lb_cast = next((c for c in casts if c.get("spell") == "lightning-bolt"), {})
        self.assertEqual((lb_cast.get("consumes") or {}).get("pool"), "wand_of_sparking_lightning_bolt")

    def test_eldramar_yaml_no_longer_lists_wand_cantrips_or_known_spells(self):
        data = yaml.safe_load(
            Path("players/eldramar_thunderclopper.yaml").read_text(encoding="utf-8")
        )
        cantrips_known = (((data.get("spellcasting") or {}).get("cantrips") or {}).get("known")) or []
        self.assertNotIn("shocking-grasp", cantrips_known)
        self.assertNotIn("lightning-bolt", cantrips_known)
        known_spells = (((data.get("spellcasting") or {}).get("known_spells") or {}).get("known")) or []
        self.assertNotIn("shocking-grasp", known_spells)
        self.assertNotIn("lightning-bolt", known_spells)
        prepared = (((data.get("spellcasting") or {}).get("prepared_spells") or {}).get("prepared")) or []
        self.assertNotIn("shocking-grasp", prepared)
        self.assertNotIn("lightning-bolt", prepared)
        # The wand state pool persists the 1/LR lightning bolt charge
        items = ((data.get("inventory") or {}).get("items")) or []
        wand = next((entry for entry in items if (entry or {}).get("id") == "wand_of_sparking"), {})
        self.assertTrue(bool(wand.get("equipped")))
        self.assertTrue(bool(wand.get("attuned")))
        wand_pools = ((wand.get("state") or {}).get("pools")) or []
        lb_pool = next(
            (p for p in wand_pools if (p or {}).get("id") == "wand_of_sparking_lightning_bolt"),
            {},
        )
        self.assertEqual(lb_pool.get("reset"), "long_rest")

    def test_oldahhman_speeds_enable_fly_and_swim_cycle(self):
        data = yaml.safe_load(Path("players/oldahhman.yaml").read_text(encoding="utf-8"))
        speed = ((data.get("vitals") or {}).get("speed")) or {}
        self.assertEqual(int(speed.get("walk") or 0), 50)
        self.assertEqual(int(speed.get("fly") or 0), 50)
        self.assertEqual(int(speed.get("swim") or 0), 50)


if __name__ == "__main__":
    unittest.main()
