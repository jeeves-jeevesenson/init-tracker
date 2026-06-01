import copy
import unittest
from pathlib import Path
from unittest.mock import MagicMock

import yaml

import dnd_initative_tracker as tracker_mod


class PactMagicSpellSlotRegressionTests(unittest.TestCase):
    @staticmethod
    def _load_vicnor_profile():
        return yaml.safe_load(Path("players/vicnor.yaml").read_text(encoding="utf-8"))

    def setUp(self):
        self.app = object.__new__(tracker_mod.InitiativeTracker)

    @staticmethod
    def _load_throat_goat_profile():
        return yaml.safe_load(Path("players/throat_goat.yaml").read_text(encoding="utf-8"))

    def test_progression_inference_does_not_default_rogue_warlock_to_full(self):
        progression = self.app._spell_slot_progression_from_profile(
            {
                "classes": [
                    {"name": "Rogue", "subclass": "Swashbuckler", "level": 3},
                    {"name": "Warlock", "subclass": "The Noble Genie", "level": 7},
                ]
            },
            {"enabled": True},
        )
        self.assertEqual(progression, "none")

    def test_normalization_keeps_standard_slots_zero_for_pact_only_profile(self):
        raw = self._load_vicnor_profile()
        normalized = self.app._normalize_player_profile(copy.deepcopy(raw), "Vicnor")
        slots = (((normalized.get("spellcasting") or {}).get("spell_slots")) or {})
        self.assertEqual(
            {str(level): int((slots.get(str(level), {}) or {}).get("max", -1)) for level in range(1, 10)},
            {str(level): 0 for level in range(1, 10)},
        )
        pact = ((normalized.get("spellcasting") or {}).get("pact_magic_slots")) or {}
        self.assertEqual(int(pact.get("level") or 0), 4)
        self.assertEqual(int(pact.get("count") or 0), 2)

    def test_cast_attempt_with_standard_slot_does_not_persist_fake_slots(self):
        raw = self._load_vicnor_profile()
        normalized = self.app._normalize_player_profile(copy.deepcopy(raw), "Vicnor")
        saved_payloads = []

        self.app._profile_for_player_name = lambda _name: normalized
        self.app._save_player_spell_slots = lambda _name, slots: saved_payloads.append(copy.deepcopy(slots))

        ok, err, spent = self.app._consume_spell_slot_for_cast("Vicnor", 5, 4)
        self.assertFalse(ok)
        self.assertIn("No spell slots left", err)
        self.assertIsNone(spent)
        self.assertEqual(saved_payloads, [])

        slots = (((normalized.get("spellcasting") or {}).get("spell_slots")) or {})
        self.assertTrue(all(int((slots.get(str(level), {}) or {}).get("max", 0)) == 0 for level in range(1, 10)))

    def test_throat_goat_keeps_bard_slots_and_pact_slots(self):
        raw = self._load_throat_goat_profile()
        normalized = self.app._normalize_player_profile(copy.deepcopy(raw), "Throat Goat")
        spellcasting = normalized.get("spellcasting") if isinstance(normalized.get("spellcasting"), dict) else {}
        slots = spellcasting.get("spell_slots") if isinstance(spellcasting.get("spell_slots"), dict) else {}
        self.assertEqual(int((slots.get("5") or {}).get("max") or 0), 1)
        self.assertEqual(int((slots.get("4") or {}).get("max") or 0), 3)
        pact = spellcasting.get("pact_magic_slots") if isinstance(spellcasting.get("pact_magic_slots"), dict) else {}
        self.assertEqual(int(pact.get("count") or 0), 2)
        self.assertEqual(int(pact.get("level") or 0), 1)

    def test_refund_spell_slot_restores_pact_pool_without_materializing_fake_standard_slots(self):
        raw = self._load_vicnor_profile()
        normalized = self.app._normalize_player_profile(copy.deepcopy(raw), "Vicnor")
        normalized.setdefault("resources", {})["pools"] = [
            {
                "id": "pact_magic_slots",
                "label": "Pact Magic Slots (Level 4)",
                "current": 1,
                "max": 2,
                "max_formula": "2",
                "reset": "short_rest",
                "slot_level": 4,
            }
        ]
        pool_updates = []
        saved_payloads = []

        self.app._profile_for_player_name = lambda _name: copy.deepcopy(normalized)
        self.app._set_player_resource_pool_current = (
            lambda player_name, pool_id, new_current: pool_updates.append((player_name, pool_id, int(new_current))) or (True, "")
        )
        self.app._save_player_spell_slots = lambda _name, slots: saved_payloads.append(copy.deepcopy(slots)) or slots

        refunded = self.app._refund_spell_slot("Vicnor", 4)

        self.assertTrue(refunded)
        self.assertEqual(pool_updates, [("Vicnor", "pact_magic_slots", 2)])
        self.assertEqual(saved_payloads, [])

    def test_refund_spell_slot_uses_standard_provenance_for_mixed_slot_profile(self):
        raw = self._load_throat_goat_profile()
        normalized = self.app._normalize_player_profile(copy.deepcopy(raw), "Throat Goat")
        spellcasting = normalized.setdefault("spellcasting", {})
        slots = self.app._normalize_spell_slots(spellcasting.get("spell_slots"))
        slots["1"] = {"max": 4, "current": 3}
        spellcasting["spell_slots"] = slots
        normalized.setdefault("resources", {})["pools"] = [
            {
                "id": "pact_magic_slots",
                "label": "Pact Magic Slots (Level 1)",
                "current": 1,
                "max": 2,
                "max_formula": "2",
                "reset": "short_rest",
                "slot_level": 1,
            }
        ]
        pool_updates = []
        saved_payloads = []

        self.app._profile_for_player_name = lambda _name: copy.deepcopy(normalized)
        self.app._save_player_spell_slots = lambda _name, slots: saved_payloads.append(copy.deepcopy(slots)) or slots
        self.app._set_player_resource_pool_current = (
            lambda player_name, pool_id, new_current: pool_updates.append((player_name, pool_id, int(new_current))) or (True, "")
        )

        refunded = self.app._refund_spell_slot(
            "Throat Goat",
            1,
            {"pool_id": "spell_slots", "slot_level": 1},
        )

        self.assertTrue(refunded)
        self.assertEqual(int((saved_payloads[-1].get("1") or {}).get("current") or 0), 4)
        self.assertEqual(pool_updates, [])

    def test_manual_override_reconciles_stale_pact_max(self):
        # P0-007: setup profile with pact count 3 (leveled up)
        # but resource pool has max 2 (stale)
        profile = {
            "name": "Vicnor",
            "spellcasting": {
                "pact_magic_slots": {"level": 4, "count": 3} # Authority is 3
            },
            "resources": {
                "pools": [
                    {
                        "id": "pact_magic_slots",
                        "current": 2,
                        "max": 2,
                        "max_formula": "2",
                        "reset": "short_rest"
                    }
                ]
            }
        }

        self.app.combatants = {
            1: MagicMock(cid=1, name="Vicnor")
        }
        self.app._pc_name_for = lambda cid: "Vicnor"
        self.app._find_player_profile_path = lambda name: "vicnor.yaml"
        self.app._json_safe = lambda x: x
        self.app._send_ws_payload = MagicMock()
        self.app._toast = MagicMock()
        self.app._log = MagicMock()
        self.app._rebuild_table = MagicMock()
        self.app._lan_force_state_broadcast = MagicMock()

        saved_profiles = []
        self.app._profile_for_player_name = MagicMock(return_value=profile)
        self.app._store_character_yaml = lambda path, p, **kwargs: saved_profiles.append(copy.deepcopy(p))

        from player_command_service import PlayerCommandService
        service = PlayerCommandService(self.app)

        # Override to 3 slots (+1 delta)
        msg = {"type": "manual_override_spell_slot", "slot_level": 4, "delta": 1}
        result = service.manual_override_spell_slot(msg, cid=1, ws_id="ws1", is_admin=True)

        self.assertTrue(result["ok"])
        self.assertEqual(len(saved_profiles), 1)
        saved = saved_profiles[0]
        pool = next(p for p in saved["resources"]["pools"] if p["id"] == "pact_magic_slots")

        self.assertEqual(pool["max"], 3, "Max should be reconciled to 3")
        self.assertEqual(pool["current"], 3, "Current should be 3")
        self.assertEqual(pool["max_formula"], "3", "Formula should be reconciled")

    def test_long_rest_reconciles_stale_pact_max(self):
        # P0-007: setup profile with pact count 3 (leveled up)
        # but resource pool has max 2 (stale)
        profile = {
            "name": "Vicnor",
            "spellcasting": {
                "pact_magic_slots": {"level": 4, "count": 3} # Authority is 3
            },
            "resources": {
                "pools": [
                    {
                        "id": "pact_magic_slots",
                        "current": 0,
                        "max": 2,
                        "max_formula": "2",
                        "reset": "short_rest"
                    }
                ]
            }
        }

        self.app.combatants = {
            1: MagicMock(cid=1, name="Vicnor", is_pc=True, hp=60, max_hp=60)
        }
        self.app._profile_for_player_name = MagicMock(return_value=profile)
        self.app._find_player_profile_path = MagicMock(return_value="vicnor.yaml")
        self.app._compute_resource_pool_max = MagicMock(side_effect=lambda profile, formula, fallback: int(formula) if str(formula).isdigit() else int(fallback))
        self.app._log = MagicMock()
        self.app._rebuild_table = MagicMock()
        self.app._lan_force_state_broadcast = MagicMock()

        # Mocking the context manager for YAML cache hold
        tracker_mod._PlayerYamlCacheHold = MagicMock()

        from combat_service import CombatService
        service = CombatService(self.app)

        stored = []
        def mock_bulk(mutations, **kwargs):
            for mut in mutations:
                stored.append(copy.deepcopy(mut["profile"]))
        self.app._bulk_report_character_mutations = mock_bulk

        service.long_rest(scope="players")

        self.assertEqual(len(stored), 1)
        saved = stored[0]
        pool = next(p for p in saved["resources"]["pools"] if p["id"] == "pact_magic_slots")

        self.assertEqual(pool["max"], 3, "Max should be reconciled to 3 during long rest")
        self.assertEqual(pool["current"], 3, "Current should be 3 during long rest")
        self.assertEqual(pool["max_formula"], "3", "Formula should be reconciled during long rest")


if __name__ == "__main__":
    unittest.main()
