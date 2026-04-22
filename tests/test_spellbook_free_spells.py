import tempfile
import unittest
from pathlib import Path
from unittest import mock

import dnd_initative_tracker as tracker_mod


class SpellbookFreeSpellsTests(unittest.TestCase):
    def test_live_spellbook_contract_wizard_and_non_wizard_tabs(self):
        app = object.__new__(tracker_mod.InitiativeTracker)
        wizard_profile = {"leveling": {"classes": [{"name": "Wizard", "level": 11}]}}
        druid_profile = {"leveling": {"classes": [{"name": "Druid", "level": 11}]}}

        wizard = app._build_live_spellbook_contract(
            wizard_profile,
            fallback_known_enabled=True,
            known_limit=30,
            prepared_limit=18,
            cantrips_limit=8,
            source_lists={"eligible_spells": [], "eligible_cantrips": []},
        )
        druid = app._build_live_spellbook_contract(
            druid_profile,
            fallback_known_enabled=False,
            known_limit=None,
            prepared_limit=19,
            cantrips_limit=5,
            source_lists={"eligible_spells": [], "eligible_cantrips": []},
        )

        self.assertEqual(wizard["mode"], "known_and_prepared")
        self.assertTrue(wizard["known_spells_managed"])
        self.assertTrue(wizard["ui"]["tabs"]["known"]["visible"])
        self.assertEqual(wizard["ui"]["default_mode"], "known")
        self.assertEqual(wizard["ui"]["modes"]["prepared"]["left_source"], "known")
        self.assertEqual(wizard["ui"]["modes"]["prepared"]["left_title"], "Known Spells")

        self.assertEqual(druid["mode"], "prepared_only")
        self.assertFalse(druid["known_spells_managed"])
        self.assertFalse(druid["ui"]["tabs"]["known"]["visible"])
        self.assertEqual(druid["ui"]["default_mode"], "prepared")
        self.assertEqual(druid["ui"]["modes"]["prepared"]["left_source"], "eligible_spells")
        self.assertEqual(druid["ui"]["modes"]["prepared"]["left_title"], "Eligible Spells")
        self.assertEqual(druid["ui"]["modes"]["cantrips"]["left_source"], "eligible_cantrips")
        self.assertEqual(druid["limits"]["prepared"]["max"], 19)
        self.assertEqual(druid["limits"]["cantrips"]["max"], 5)

    def test_normalize_runtime_lists_separates_cantrips_and_free_cantrips(self):
        app = object.__new__(tracker_mod.InitiativeTracker)
        levels = {
            "guidance": 0,
            "light": 0,
            "shocking-grasp": 0,
            "magic-missile": 1,
            "cure-wounds": 1,
        }
        app._normalize_spell_slug_list = lambda value: [
            str(item).strip().lower()
            for item in (value if isinstance(value, list) else [value] if isinstance(value, str) else [])
            if str(item).strip()
        ]
        app._find_spell_preset = lambda spell_slug=None, spell_id=None: {
            "level": levels.get(str(spell_slug or spell_id or "").strip().lower())
        }
        app._feature_always_prepared_spell_slugs = lambda _profile: []
        app._compute_resource_pool_max = lambda _profile, _formula, fallback: int(fallback) if fallback is not None else None

        runtime = app._normalize_spellbook_runtime_lists(
            {},
            {
                "cantrips": {"known": ["guidance", "light"], "free": ["light"], "max": 4},
                "known_spells": {"known": ["magic-missile", "shocking-grasp"], "free": ["shocking-grasp"], "max": 8},
                "prepared_spells": {"prepared": ["cure-wounds", "light"], "free": ["light"], "max": 5},
            },
        )

        self.assertEqual(runtime["known_list"], ["magic-missile"])
        self.assertEqual(runtime["known_free_list"], [])
        self.assertEqual(runtime["prepared_list"], ["cure-wounds"])
        self.assertEqual(runtime["prepared_free_list"], [])
        self.assertEqual(runtime["cantrips_list"], ["guidance", "light", "shocking-grasp"])
        self.assertEqual(runtime["cantrips_free_list"], ["light", "shocking-grasp"])
        self.assertEqual(runtime["prepared_limit"], 5)
        self.assertEqual(runtime["known_limit"], 8)
        self.assertEqual(runtime["cantrips_limit"], 4)

    def test_save_spellbook_filters_free_spells_to_current_lists(self):
        app = object.__new__(tracker_mod.InitiativeTracker)
        with tempfile.TemporaryDirectory() as tmpdir:
            player_path = Path(tmpdir) / "mage.yaml"
            player_path.write_text("name: Mage\n", encoding="utf-8")

            app._load_player_yaml_cache = lambda: None
            app._find_player_profile_path = lambda _name: player_path
            app._players_dir = lambda: player_path.parent
            app._sanitize_player_filename = lambda value: str(value or "player")
            app._normalize_character_lookup_key = lambda value: str(value or "").strip().lower()
            app._schedule_player_yaml_refresh = lambda: None
            app._player_yaml_cache_by_path = {
                player_path: {
                    "name": "Mage",
                    "spellcasting": {
                        "known_spells": {"known": ["magic-missile", "shield"], "free": ["shield", "sleep"]},
                        "prepared_spells": {"prepared": ["mage-armor", "shield"], "free": ["shield", "sleep"]},
                    },
                }
            }
            app._player_yaml_meta_by_path = {}
            app._player_yaml_data_by_name = {}
            app._player_yaml_name_map = {}
            app._write_player_yaml_atomic = lambda path, payload: app._player_yaml_cache_by_path.__setitem__(path, payload)
            app._find_spell_preset = lambda spell_slug=None, spell_id=None: None
            app._normalize_player_profile = lambda payload, _stem: {
                "name": payload.get("name", "Mage"),
                "spellcasting": payload.get("spellcasting", {}),
            }
            app._all_active_features = lambda profile: profile.get("features", []) if isinstance(profile, dict) else []
            app._normalize_spell_slug_list = lambda value: [str(item).strip().lower() for item in (value if isinstance(value, list) else [value] if isinstance(value, str) else []) if str(item).strip()]

            with mock.patch.object(tracker_mod, "yaml", object()), mock.patch.object(
                tracker_mod, "_file_stat_metadata", return_value={}
            ):
                app._save_player_spellbook(
                    "Mage",
                    {
                        "known_enabled": True,
                        "known_list": ["magic-missile"],
                        "prepared_list": ["shield"],
                        "cantrips_list": [],
                    },
                )

            saved = app._player_yaml_cache_by_path[player_path]
            self.assertEqual(saved["spellcasting"]["known_spells"]["known"], ["magic-missile"])
            self.assertNotIn("free", saved["spellcasting"]["known_spells"])
            self.assertEqual(saved["spellcasting"]["prepared_spells"]["prepared"], ["shield"])
            self.assertEqual(saved["spellcasting"]["prepared_spells"]["free"], ["shield"])

    def test_save_spellbook_preserves_free_cantrips_separately(self):
        app = object.__new__(tracker_mod.InitiativeTracker)
        with tempfile.TemporaryDirectory() as tmpdir:
            player_path = Path(tmpdir) / "cleric.yaml"
            player_path.write_text("name: Cleric\n", encoding="utf-8")

            levels = {
                "light": 0,
                "guidance": 0,
                "bless": 1,
            }
            app._load_player_yaml_cache = lambda: None
            app._find_player_profile_path = lambda _name: player_path
            app._players_dir = lambda: player_path.parent
            app._sanitize_player_filename = lambda value: str(value or "player")
            app._normalize_character_lookup_key = lambda value: str(value or "").strip().lower()
            app._schedule_player_yaml_refresh = lambda: None
            app._all_active_features = lambda profile: profile.get("features", []) if isinstance(profile, dict) else []
            app._normalize_spell_slug_list = lambda value: [
                str(item).strip().lower()
                for item in (value if isinstance(value, list) else [value] if isinstance(value, str) else [])
                if str(item).strip()
            ]
            app._find_spell_preset = lambda spell_slug=None, spell_id=None: {
                "level": levels.get(str(spell_slug or spell_id or "").strip().lower())
            }
            app._player_yaml_cache_by_path = {
                player_path: {
                    "name": "Cleric",
                    "leveling": {"classes": [{"name": "cleric", "level": 5}]},
                    "spellcasting": {
                        "cantrips": {"known": ["light"]},
                        "prepared_spells": {"prepared": ["bless", "light"], "free": ["light"]},
                    },
                }
            }
            app._player_yaml_meta_by_path = {}
            app._player_yaml_data_by_name = {}
            app._player_yaml_name_map = {}
            app._write_player_yaml_atomic = lambda path, payload: app._player_yaml_cache_by_path.__setitem__(path, payload)
            app._normalize_player_profile = lambda payload, _stem: {
                "name": payload.get("name", "Cleric"),
                "spellcasting": payload.get("spellcasting", {}),
            }

            with mock.patch.object(tracker_mod, "yaml", object()), mock.patch.object(
                tracker_mod, "_file_stat_metadata", return_value={}
            ):
                app._save_player_spellbook(
                    "Cleric",
                    {
                        "known_enabled": False,
                        "known_list": [],
                        "prepared_list": ["bless"],
                        "cantrips_list": ["light", "guidance"],
                    },
                )

            saved = app._player_yaml_cache_by_path[player_path]
            self.assertEqual(saved["spellcasting"]["cantrips"]["known"], ["light", "guidance"])
            self.assertEqual(saved["spellcasting"]["cantrips"]["free"], ["light"])
            self.assertEqual(saved["spellcasting"]["prepared_spells"]["prepared"], ["bless"])
            self.assertNotIn("free", saved["spellcasting"]["prepared_spells"])

    def test_save_spellbook_reinserts_feature_always_prepared_spells(self):
        app = object.__new__(tracker_mod.InitiativeTracker)
        with tempfile.TemporaryDirectory() as tmpdir:
            player_path = Path(tmpdir) / "glamour.yaml"
            player_path.write_text("name: Throat Goat\n", encoding="utf-8")

            app._load_player_yaml_cache = lambda: None
            app._find_player_profile_path = lambda _name: player_path
            app._players_dir = lambda: player_path.parent
            app._sanitize_player_filename = lambda value: str(value or "player")
            app._normalize_character_lookup_key = lambda value: str(value or "").strip().lower()
            app._schedule_player_yaml_refresh = lambda: None
            app._all_active_features = lambda profile: profile.get("features", []) if isinstance(profile, dict) else []
            app._normalize_spell_slug_list = lambda value: [str(item).strip().lower() for item in (value if isinstance(value, list) else [value] if isinstance(value, str) else []) if str(item).strip()]
            app._find_spell_preset = lambda spell_slug=None, spell_id=None: None
            app._player_yaml_cache_by_path = {
                player_path: {
                    "name": "Throat Goat",
                    "features": [
                        {
                            "name": "Mantle of Majesty",
                            "grants": {"always_prepared_spells": ["command"]},
                        }
                    ],
                    "spellcasting": {
                        "prepared_spells": {
                            "prepared": ["command", "healing-word"],
                            "free": ["command"],
                        }
                    },
                }
            }
            app._player_yaml_meta_by_path = {}
            app._player_yaml_data_by_name = {}
            app._player_yaml_name_map = {}
            app._write_player_yaml_atomic = lambda path, payload: app._player_yaml_cache_by_path.__setitem__(path, payload)
            app._normalize_player_profile = lambda payload, _stem: {
                "name": payload.get("name", "Throat Goat"),
                "spellcasting": payload.get("spellcasting", {}),
            }

            with mock.patch.object(tracker_mod, "yaml", object()), mock.patch.object(
                tracker_mod, "_file_stat_metadata", return_value={}
            ):
                app._save_player_spellbook(
                    "Throat Goat",
                    {
                        "known_enabled": False,
                        "known_list": [],
                        "prepared_list": ["healing-word"],
                        "cantrips_list": [],
                    },
                )

            saved = app._player_yaml_cache_by_path[player_path]
            prepared = saved["spellcasting"]["prepared_spells"]["prepared"]
            free = saved["spellcasting"]["prepared_spells"]["free"]
            self.assertIn("command", prepared)
            self.assertIn("command", free)

    def test_save_spellbook_derives_known_enabled_from_wizard_class(self):
        app = object.__new__(tracker_mod.InitiativeTracker)
        with tempfile.TemporaryDirectory() as tmpdir:
            player_path = Path(tmpdir) / "wizard.yaml"
            player_path.write_text("name: Wizard\n", encoding="utf-8")

            app._load_player_yaml_cache = lambda: None
            app._find_player_profile_path = lambda _name: player_path
            app._players_dir = lambda: player_path.parent
            app._sanitize_player_filename = lambda value: str(value or "player")
            app._normalize_character_lookup_key = lambda value: str(value or "").strip().lower()
            app._schedule_player_yaml_refresh = lambda: None
            app._all_active_features = lambda profile: profile.get("features", []) if isinstance(profile, dict) else []
            app._normalize_spell_slug_list = lambda value: [
                str(item).strip().lower()
                for item in (value if isinstance(value, list) else [value] if isinstance(value, str) else [])
                if str(item).strip()
            ]
            app._find_spell_preset = lambda spell_slug=None, spell_id=None: None
            app._player_yaml_cache_by_path = {
                player_path: {
                    "name": "Wizard",
                    "leveling": {"classes": [{"name": "wizard", "level": 5}]},
                    "spellcasting": {
                        "known_spells": {"known": ["shield"], "free": ["shield"]},
                        "prepared_spells": {"prepared": ["shield"], "free": ["shield"]},
                    },
                }
            }
            app._player_yaml_meta_by_path = {}
            app._player_yaml_data_by_name = {}
            app._player_yaml_name_map = {}
            app._write_player_yaml_atomic = lambda path, payload: app._player_yaml_cache_by_path.__setitem__(path, payload)
            app._normalize_player_profile = lambda payload, _stem: {
                "name": payload.get("name", "Wizard"),
                "spellcasting": payload.get("spellcasting", {}),
            }

            with mock.patch.object(tracker_mod, "yaml", object()), mock.patch.object(
                tracker_mod, "_file_stat_metadata", return_value={}
            ):
                app._save_player_spellbook(
                    "Wizard",
                    {
                        "known_enabled": False,
                        "known_list": ["shield", "magic-missile"],
                        "prepared_list": ["shield"],
                        "cantrips_list": [],
                    },
                )

            saved = app._player_yaml_cache_by_path[player_path]
            self.assertTrue(saved["spellcasting"]["known_enabled"])
            self.assertEqual(saved["spellcasting"]["known_spells"]["known"], ["shield", "magic-missile"])
            self.assertEqual(saved["spellcasting"]["known_spells"]["free"], ["shield"])

    def test_save_spellbook_disables_known_list_for_non_wizard(self):
        app = object.__new__(tracker_mod.InitiativeTracker)
        with tempfile.TemporaryDirectory() as tmpdir:
            player_path = Path(tmpdir) / "cleric.yaml"
            player_path.write_text("name: Cleric\n", encoding="utf-8")

            app._load_player_yaml_cache = lambda: None
            app._find_player_profile_path = lambda _name: player_path
            app._players_dir = lambda: player_path.parent
            app._sanitize_player_filename = lambda value: str(value or "player")
            app._normalize_character_lookup_key = lambda value: str(value or "").strip().lower()
            app._schedule_player_yaml_refresh = lambda: None
            app._all_active_features = lambda profile: profile.get("features", []) if isinstance(profile, dict) else []
            app._normalize_spell_slug_list = lambda value: [
                str(item).strip().lower()
                for item in (value if isinstance(value, list) else [value] if isinstance(value, str) else [])
                if str(item).strip()
            ]
            app._find_spell_preset = lambda spell_slug=None, spell_id=None: None
            app._player_yaml_cache_by_path = {
                player_path: {
                    "name": "Cleric",
                    "leveling": {"classes": [{"name": "cleric", "level": 5}]},
                    "spellcasting": {
                        "known_spells": {"known": ["bless"], "free": ["bless"]},
                        "prepared_spells": {"prepared": ["bless"], "free": ["bless"]},
                    },
                }
            }
            app._player_yaml_meta_by_path = {}
            app._player_yaml_data_by_name = {}
            app._player_yaml_name_map = {}
            app._write_player_yaml_atomic = lambda path, payload: app._player_yaml_cache_by_path.__setitem__(path, payload)
            app._normalize_player_profile = lambda payload, _stem: {
                "name": payload.get("name", "Cleric"),
                "spellcasting": payload.get("spellcasting", {}),
            }

            with mock.patch.object(tracker_mod, "yaml", object()), mock.patch.object(
                tracker_mod, "_file_stat_metadata", return_value={}
            ):
                app._save_player_spellbook(
                    "Cleric",
                    {
                        "known_enabled": True,
                        "known_list": ["guiding-bolt"],
                        "prepared_list": ["guiding-bolt"],
                        "cantrips_list": ["sacred-flame"],
                    },
                )

            saved = app._player_yaml_cache_by_path[player_path]
            self.assertFalse(saved["spellcasting"]["known_enabled"])
            self.assertNotIn("known", saved["spellcasting"]["known_spells"])
            self.assertNotIn("free", saved["spellcasting"]["known_spells"])

    def test_spellbook_contract_uses_wizard_class_mode(self):
        app = object.__new__(tracker_mod.InitiativeTracker)
        contract = app._build_live_spellbook_contract(
            {"leveling": {"classes": [{"name": "wizard", "level": 3}]}},
            fallback_known_enabled=False,
        )
        self.assertEqual(contract["mode"], "known_and_prepared")
        self.assertTrue(contract["known_spells_managed"])
        self.assertEqual(contract["source"], "wizard_class_levels")
        self.assertEqual(contract["lists"]["known"]["candidate_source"], "eligible_spells")
        self.assertTrue(contract["lists"]["known"]["direct_remove"])
        self.assertTrue(contract["lists"]["cantrips"]["direct_remove"])
        self.assertEqual(contract["lists"]["prepared"]["candidate_source"], "known")
        self.assertEqual(contract["ui"]["modes"]["prepared"]["left_source"], "known")
        self.assertTrue(contract["ui"]["tabs"]["known"]["visible"])
        self.assertTrue(contract["ui"]["tabs"]["cantrips"]["visible"])
        self.assertEqual(contract["lists"]["cantrips_free"]["policy"], "subset_of_cantrips")
        self.assertFalse(contract["limits"]["cantrips"]["counts_free"])
        self.assertTrue(contract["lists"]["prepared"]["direct_remove"])
        self.assertFalse(contract["lists"]["prepared_free"]["direct_remove"])

    def test_spellbook_contract_uses_prepared_only_for_non_wizard_classes(self):
        app = object.__new__(tracker_mod.InitiativeTracker)
        contract = app._build_live_spellbook_contract(
            {"leveling": {"classes": [{"name": "cleric", "level": 3}]}},
            fallback_known_enabled=True,
        )
        self.assertEqual(contract["mode"], "prepared_only")
        self.assertFalse(contract["known_spells_managed"])
        self.assertEqual(contract["source"], "non_wizard_class_levels")
        self.assertEqual(contract["lists"]["prepared"]["candidate_source"], "eligible_spells")
        self.assertFalse(contract["ui"]["tabs"]["known"]["visible"])
        self.assertTrue(contract["ui"]["tabs"]["cantrips"]["visible"])
        self.assertTrue(contract["lists"]["prepared"]["direct_remove"])

    def test_spellbook_contract_falls_back_when_class_data_missing(self):
        app = object.__new__(tracker_mod.InitiativeTracker)
        contract = app._build_live_spellbook_contract({}, fallback_known_enabled=True)
        self.assertEqual(contract["mode"], "known_and_prepared")
        self.assertTrue(contract["known_spells_managed"])
        self.assertEqual(contract["source"], "legacy_known_enabled_fallback")

    def test_spellbook_source_lists_filter_to_character_spell_lists(self):
        app = object.__new__(tracker_mod.InitiativeTracker)
        presets = {
            "magic-missile": {"slug": "magic-missile", "level": 1, "lists": {"classes": ["wizard"]}},
            "fire-bolt": {"slug": "fire-bolt", "level": 0, "lists": {"classes": ["wizard"]}},
            "bless": {"slug": "bless", "level": 1, "lists": {"classes": ["cleric"]}},
            "guidance": {"slug": "guidance", "level": 0, "lists": {"classes": ["cleric"]}},
            "spirit-guardians": {"slug": "spirit-guardians", "level": 3, "lists": {"classes": ["cleric"]}},
        }
        app._spell_presets_payload = lambda: list(presets.values())
        app._find_spell_preset = lambda spell_slug=None, spell_id=None: presets.get(
            str(spell_slug or spell_id or "").strip().lower()
        )

        source_lists = app._build_spellbook_source_lists(
            {
                "leveling": {"classes": [{"name": "cleric", "level": 3}]},
                "spellcasting": {"spell_slots": {"1": {"max": 4}, "2": {"max": 2}}},
            },
            known_list=[],
            known_free_list=[],
            cantrips_list=[],
            cantrips_free_list=[],
            prepared_list=[],
            prepared_free_list=[],
        )

        self.assertEqual(source_lists["eligible_spells"], ["bless"])
        self.assertEqual(source_lists["eligible_cantrips"], ["guidance"])


if __name__ == "__main__":
    unittest.main()
