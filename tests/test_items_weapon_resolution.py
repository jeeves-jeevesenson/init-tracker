import tempfile
import unittest
import re
from pathlib import Path
from unittest import mock

import dnd_initative_tracker as tracker_mod


class ItemsWeaponResolutionTests(unittest.TestCase):
    def setUp(self):
        self.app = object.__new__(tracker_mod.InitiativeTracker)
        self.app._oplog = lambda *args, **kwargs: None
        self.app._items_registry_cache = None
        self.app._items_dir_signature = None

    def test_items_registry_loads_per_item_and_catalog_with_per_item_precedence(self):
        with tempfile.TemporaryDirectory() as tmp:
            items_dir = Path(tmp) / "Items"
            weapons_dir = items_dir / "Weapons"
            armor_dir = items_dir / "Armor"
            weapons_dir.mkdir(parents=True, exist_ok=True)
            armor_dir.mkdir(parents=True, exist_ok=True)

            (weapons_dir / "longsword.yaml").write_text(
                "id: longsword\nname: Longsword File\ndamage:\n  one_handed:\n    formula: 1d8\n    type: slashing\n",
                encoding="utf-8",
            )
            (weapons_dir / "legacy_catalog.yaml").write_text(
                "weapons:\n  - id: longsword\n    name: Longsword Catalog\n  - id: shortbow\n    name: Shortbow\n",
                encoding="utf-8",
            )
            (weapons_dir / "properties_2024_basic.yaml").write_text(
                "properties:\n  - id: finesse\n",
                encoding="utf-8",
            )
            (armor_dir / "catalog.yaml").write_text(
                "armors:\n  - id: chain_mail\n    name: Chain Mail\n",
                encoding="utf-8",
            )

            with mock.patch.object(self.app, "_resolve_items_dir", return_value=items_dir):
                registry = self.app._items_registry_payload()

            self.assertIn("longsword", registry["weapons"])
            self.assertEqual(registry["weapons"]["longsword"]["name"], "Longsword File")
            self.assertIn("shortbow", registry["weapons"])
            self.assertIn("chain_mail", registry["armors"])
            self.assertNotIn("finesse", registry["weapons"])


    def test_items_registry_uses_signature_cache_between_calls(self):
        with tempfile.TemporaryDirectory() as tmp:
            items_dir = Path(tmp) / "Items"
            weapons_dir = items_dir / "Weapons"
            armor_dir = items_dir / "Armor"
            weapons_dir.mkdir(parents=True, exist_ok=True)
            armor_dir.mkdir(parents=True, exist_ok=True)
            (weapons_dir / "dagger.yaml").write_text(
                "id: dagger\nname: Dagger\ndamage:\n  one_handed:\n    formula: 1d4\n    type: piercing\n",
                encoding="utf-8",
            )

            with mock.patch.object(self.app, "_resolve_items_dir", return_value=items_dir):
                first = self.app._items_registry_payload()
                self.assertIn("dagger", first["weapons"])
                with mock.patch.object(tracker_mod.yaml, "safe_load", side_effect=RuntimeError("should not parse again")):
                    second = self.app._items_registry_payload()

            self.assertIn("dagger", second["weapons"])

    def test_items_registry_loads_weapon_shaped_magic_items(self):
        with tempfile.TemporaryDirectory() as tmp:
            items_dir = Path(tmp) / "Items"
            weapons_dir = items_dir / "Weapons"
            armor_dir = items_dir / "Armor"
            magic_dir = items_dir / "Magic_Items"
            weapons_dir.mkdir(parents=True, exist_ok=True)
            armor_dir.mkdir(parents=True, exist_ok=True)
            magic_dir.mkdir(parents=True, exist_ok=True)
            (magic_dir / "inazuma.yaml").write_text(
                "id: inazuma\ntype: weapon\nname: Inazuma\ndamage:\n  one_handed:\n    formula: 1d8\n    type: slashing\n",
                encoding="utf-8",
            )

            with mock.patch.object(self.app, "_resolve_items_dir", return_value=items_dir):
                registry = self.app._items_registry_payload()

            self.assertIn("inazuma", registry["weapons"])
            self.assertEqual(registry["weapons"]["inazuma"]["name"], "Inazuma")

    def test_items_registry_prefers_magic_items_over_weapons_directory_on_duplicate_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            items_dir = Path(tmp) / "Items"
            weapons_dir = items_dir / "Weapons"
            armor_dir = items_dir / "Armor"
            magic_dir = items_dir / "Magic_Items"
            weapons_dir.mkdir(parents=True, exist_ok=True)
            armor_dir.mkdir(parents=True, exist_ok=True)
            magic_dir.mkdir(parents=True, exist_ok=True)
            (weapons_dir / "inazuma.yaml").write_text(
                "id: inazuma\ntype: weapon\nname: Inazuma Weapon Dir\ndamage:\n  one_handed:\n    formula: 1d8\n    type: slashing\n",
                encoding="utf-8",
            )
            (magic_dir / "inazuma.yaml").write_text(
                "id: inazuma\ntype: weapon\nname: Inazuma Magic Dir\ndamage:\n  one_handed:\n    formula: 2d6\n    type: lightning\n",
                encoding="utf-8",
            )

            with mock.patch.object(self.app, "_resolve_items_dir", return_value=items_dir):
                registry = self.app._items_registry_payload()

            self.assertEqual(registry["weapons"]["inazuma"]["name"], "Inazuma Magic Dir")
            self.assertEqual(registry["weapons"]["inazuma"]["damage"]["one_handed"]["formula"], "2d6")

    def test_normalize_player_weapon_resolves_item_fields_fill_missing_only(self):
        registry = {
            "weapons": {
                "longsword": {
                    "id": "longsword",
                    "name": "Longsword",
                    "category": "martial_melee",
                    "attack_bonus": 1,
                    "damage": {
                        "one_handed": {"formula": "1d8", "type": "slashing"},
                        "versatile": {"formula": "1d10", "type": "slashing"},
                    },
                    "properties": ["versatile", "sap"],
                }
            },
            "armors": {},
        }
        player = {
            "name": "Test",
            "abilities": {"str": 16, "dex": 12},
            "attacks": {
                "weapons": [
                    {
                        "id": "longsword",
                        "to_hit": 7,
                        "one_handed": {"damage_formula": "2d6 + str_mod"},
                    }
                ]
            },
        }
        with mock.patch.object(tracker_mod.InitiativeTracker, "_items_registry_payload", return_value=registry):
            normalized = self.app._normalize_player_profile(player, "Test")

        weapon = normalized["attacks"]["weapons"][0]
        self.assertEqual(weapon["name"], "Longsword")
        self.assertEqual(weapon["one_handed"]["damage_formula"], "2d6 + str_mod")
        self.assertEqual(weapon["one_handed"]["damage_type"], "slashing")
        self.assertEqual(weapon["two_handed"]["damage_formula"], "1d10 + str_mod")
        self.assertEqual(weapon["magic_bonus"], 1)
        self.assertIn("versatile", weapon["properties"])

    def test_normalize_appends_finesse_or_ranged_ability_mod_when_missing(self):
        registry = {
            "weapons": {
                "rapier": {
                    "id": "rapier",
                    "name": "Rapier",
                    "category": "martial_melee",
                    "damage": {"one_handed": {"formula": "1d8", "type": "piercing"}},
                    "properties": ["finesse"],
                },
                "shortbow": {
                    "id": "shortbow",
                    "name": "Shortbow",
                    "category": "martial_ranged",
                    "damage": {"one_handed": {"formula": "1d6", "type": "piercing"}},
                },
            },
            "armors": {},
        }
        player = {
            "name": "Archer",
            "abilities": {"str": 10, "dex": 18},
            "attacks": {"weapons": [{"id": "rapier"}, {"id": "shortbow"}]},
        }
        with mock.patch.object(tracker_mod.InitiativeTracker, "_items_registry_payload", return_value=registry):
            normalized = self.app._normalize_player_profile(player, "Archer")

        rapier, shortbow = normalized["attacks"]["weapons"]
        self.assertEqual(rapier["one_handed"]["damage_formula"], "1d8 + max(str_mod, dex_mod)")
        self.assertEqual(shortbow["one_handed"]["damage_formula"], "1d6 + dex_mod")

    def test_resolve_weapon_from_items_maps_versatile_to_two_handed_formula(self):
        registry = {
            "weapons": {
                "inazuma": {
                    "id": "inazuma",
                    "name": "Inazuma",
                    "damage": {
                        "one_handed": {"formula": "1d8", "type": "slashing"},
                        "versatile": {"formula": "1d10", "type": "slashing"},
                    },
                    "properties": ["versatile"],
                }
            },
            "armors": {},
        }
        weapon = {"id": "inazuma", "one_handed": {}, "two_handed": {}}
        resolved = self.app._resolve_weapon_from_items(weapon, registry["weapons"])

        self.assertEqual(resolved["two_handed"]["damage_formula"], "1d10 + str_mod")

    def test_resolve_weapon_from_items_maps_two_handed_damage_without_one_handed(self):
        registry = {
            "weapons": {
                "bardiche_plus_2": {
                    "id": "bardiche_plus_2",
                    "name": "Bardiche (+2)",
                    "damage": {
                        "two_handed": {"formula": "1d12 + 2", "type": "force"},
                    },
                    "properties": ["two_handed"],
                }
            },
            "armors": {},
        }
        weapon = {"id": "bardiche_plus_2", "one_handed": {}, "two_handed": {}}
        resolved = self.app._resolve_weapon_from_items(weapon, registry["weapons"])

        self.assertEqual(resolved["one_handed"].get("damage_formula", ""), "")
        self.assertEqual(resolved["two_handed"]["damage_formula"], "1d12 + 2 + str_mod")

    def test_resolve_weapon_from_items_infers_melee_reach_range_when_missing(self):
        registry = {
            "weapons": {
                "glaive": {
                    "id": "glaive",
                    "name": "Glaive",
                    "category": "martial_melee",
                    "properties": ["reach", "heavy", "two_handed"],
                    "damage": {"one_handed": {"formula": "1d10", "type": "slashing"}},
                }
            },
            "armors": {},
        }
        resolved = self.app._resolve_weapon_from_items({"id": "glaive"}, registry["weapons"])
        self.assertEqual(resolved["range"], "10")

    def test_resolve_weapon_from_items_infers_default_melee_range_when_missing(self):
        registry = {
            "weapons": {
                "battleaxe": {
                    "id": "battleaxe",
                    "name": "Battleaxe",
                    "category": "martial_melee",
                    "properties": ["versatile"],
                    "damage": {"one_handed": {"formula": "1d8", "type": "slashing"}},
                }
            },
            "armors": {},
        }
        resolved = self.app._resolve_weapon_from_items({"id": "battleaxe"}, registry["weapons"])
        self.assertEqual(resolved["range"], "5")

    def test_normalize_player_weapon_canonicalizes_properties_and_selected_mode(self):
        player = {
            "name": "Test",
            "attacks": {
                "weapons": [
                    {
                        "id": "greatsword",
                        "properties": ["Two-Handed", "heavy weapon"],
                        "selected_mode": "Two",
                    }
                ]
            },
        }
        with mock.patch.object(tracker_mod.InitiativeTracker, "_items_registry_payload", return_value={"weapons": {}, "armors": {}}):
            normalized = self.app._normalize_player_profile(player, "Test")

        weapon = normalized["attacks"]["weapons"][0]
        self.assertEqual(weapon["properties"], ["two_handed", "heavy_weapon"])
        self.assertEqual(weapon["selected_mode"], "two")

    def test_normalize_player_weapon_preserves_equipped_and_hand_flags(self):
        player = {
            "name": "Test",
            "attacks": {
                "weapons": [
                    {
                        "id": "shortsword",
                        "equipped": False,
                        "main_hand": "true",
                        "off_hand": 0,
                    }
                ]
            },
        }
        with mock.patch.object(tracker_mod.InitiativeTracker, "_items_registry_payload", return_value={"weapons": {}, "armors": {}}):
            normalized = self.app._normalize_player_profile(player, "Test")

        weapon = normalized["attacks"]["weapons"][0]
        self.assertFalse(weapon["equipped"])
        self.assertTrue(weapon["main_hand"])
        self.assertFalse(weapon["off_hand"])

    def test_repository_melee_items_resolve_with_range_for_attack_workflow(self):
        registry = self.app._items_registry_payload()
        weapons = registry.get("weapons") if isinstance(registry, dict) else {}
        self.assertIsInstance(weapons, dict)
        melee_items = []
        for item_id, item_data in weapons.items():
            if not isinstance(item_data, dict):
                continue
            category = str(item_data.get("category") or "").strip().lower()
            if "melee" not in category:
                continue
            melee_items.append((item_id, item_data))
        self.assertGreater(len(melee_items), 0)

        for item_id, item_data in melee_items:
            resolved = self.app._resolve_weapon_from_items({"id": item_id}, weapons)
            range_text = str(resolved.get("range") or "").strip()
            self.assertTrue(range_text, f"{item_id} did not resolve to a usable range")
            match = re.search(r"(\d+(?:\.\d+)?)", range_text.split("/")[0])
            self.assertIsNotNone(match, f"{item_id} resolved with non-numeric range '{range_text}'")
            feet = float(match.group(1))
            self.assertGreater(feet, 0.0, f"{item_id} resolved with non-positive range '{range_text}'")


    def test_inventory_payload_non_empty_for_seeded_equipment_user(self):
        # Verify that weapons equipped in inventory show up in attacks.weapons
        profile_data = {
            "name": "John",
            "inventory": {
                "items": [
                    {"id": "longsword", "instance_id": "ls1", "equipped": True, "equipped_slot": "main_hand"}
                ]
            },
            "attacks": {"weapons": []}
        }
        weapon_registry = {
            "longsword": {"id": "longsword", "name": "Longsword", "category": "martial_melee", "damage": {"one_handed": {"formula": "1d8"}}}
        }

        with mock.patch.object(self.app, "_items_registry_payload", return_value={"weapons": weapon_registry}), \
             mock.patch.object(self.app, "_magic_items_registry_payload", return_value={}):
            normalized = self.app._normalize_player_profile(profile_data, "John")

        weapons = normalized.get("attacks", {}).get("weapons", [])
        self.assertEqual(len(weapons), 1)
        self.assertEqual(weapons[0]["id"], "longsword")
        self.assertEqual(weapons[0]["instance_id"], "ls1")
        self.assertTrue(weapons[0]["equipped"])

    def test_equipped_weapon_selected_for_attack(self):
        # Verify that if no weapon requested, equipped weapon is used
        profile_data = {
            "name": "John",
            "attacks": {
                "weapons": [
                    {"id": "dagger", "name": "Dagger", "equipped": False},
                    {"id": "longsword", "name": "Longsword", "equipped": True}
                ]
            }
        }
        c = mock.Mock()
        c.name = "John"
        c.cid = 1
        target = mock.Mock()
        target.cid = 2

        self.app.combatants = {1: c, 2: target}
        self.app._lan = mock.Mock()

        msg = {"type": "attack_request", "cid": 1, "target_cid": 2, "attack_roll": 15}

        with mock.patch.object(self.app, "_profile_for_player_name", return_value=profile_data), \
             mock.patch.object(self.app, "_pc_name_for", return_value="John"), \
             mock.patch.object(self.app, "_use_action", return_value=True), \
             mock.patch.object(self.app, "_class_level_from_profile", return_value=0), \
             mock.patch.object(self.app, "_get_controlled_unit_or_pc", return_value=c):
            # Capture the weapon passed to resolve_weapon_from_items
            with mock.patch.object(self.app, "_resolve_weapon_from_items") as mock_resolve:
                mock_resolve.side_effect = lambda w, **kw: w
                try:
                    self.app._adjudicate_attack_request(msg, cid=1, ws_id="ws", is_admin=False)
                except Exception:
                    pass # We only care about selection stage

                self.assertTrue(mock_resolve.called)
                selected = mock_resolve.call_args[0][0]
                self.assertEqual(selected["id"], "longsword")

    def test_configured_weapon_prevents_unarmed_fallback(self):
        # Verify that if a weapon exists but none are equipped, it uses the first weapon instead of unarmed
        profile_data = {
            "name": "John",
            "attacks": {
                "weapons": [
                    {"id": "longsword", "name": "Longsword", "equipped": False}
                ]
            }
        }
        c = mock.Mock()
        c.name = "John"
        c.cid = 1
        target = mock.Mock()
        target.cid = 2
        self.app.combatants = {1: c, 2: target}
        self.app._lan = mock.Mock()
        msg = {"type": "attack_request", "cid": 1, "target_cid": 2, "attack_roll": 15}

        with mock.patch.object(self.app, "_profile_for_player_name", return_value=profile_data), \
             mock.patch.object(self.app, "_pc_name_for", return_value="John"), \
             mock.patch.object(self.app, "_get_controlled_unit_or_pc", return_value=c):
            with mock.patch.object(self.app, "_resolve_weapon_from_items") as mock_resolve:
                mock_resolve.side_effect = lambda w, **kw: w
                try:
                    self.app._adjudicate_attack_request(msg, cid=1, ws_id="ws", is_admin=False)
                except Exception:
                    pass

                self.assertTrue(mock_resolve.called)
                selected = mock_resolve.call_args[0][0]
                self.assertEqual(selected["id"], "longsword")

    def test_unarmed_fallback_requires_fallback_reason(self):
        # Verify that if we fall back to unarmed, it's traced with a reason
        profile_data = {"name": "John", "attacks": {"weapons": []}}
        c = mock.Mock()
        c.name = "John"
        c.cid = 1
        c.is_wild_shaped = False
        target = mock.Mock()
        target.cid = 2
        self.app.combatants = {1: c, 2: target}
        self.app._lan = mock.Mock()
        msg = {"type": "attack_request", "cid": 1, "target_cid": 2, "attack_roll": 15}

        with mock.patch.object(self.app, "_profile_for_player_name", return_value=profile_data), \
             mock.patch.object(self.app, "_pc_name_for", return_value="John"), \
             mock.patch.object(self.app, "_get_controlled_unit_or_pc", return_value=c), \
             mock.patch.object(self.app, "_oplog") as mock_oplog:
            try:
                self.app._adjudicate_attack_request(msg, cid=1, ws_id="ws", is_admin=False)
            except Exception:
                pass

            # Check if oplog was called with trace containing fallback_reason
            traces = [str(args[0]) for args, kwargs in mock_oplog.call_args_list if "fallback_reason" in str(args[0])]
            self.assertTrue(any("falling back to basic unarmed strike" in t for t in traces))

    def test_attack_resolution_traces_inventory_and_fallback_reason(self):
        # Verify that failed resolution toasts with a reason
        profile_data = {"name": "John", "attacks": {"weapons": []}}
        c = mock.Mock()
        c.name = "John"
        c.cid = 1
        c.is_wild_shaped = False
        target = mock.Mock()
        target.cid = 2
        self.app.combatants = {1: c, 2: target}
        self.app._lan = mock.Mock()
        # Request a specific weapon that doesn't exist
        msg = {"type": "attack_request", "cid": 1, "target_cid": 2, "attack_roll": 15, "weapon_id": "missing"}

        with mock.patch.object(self.app, "_profile_for_player_name", return_value=profile_data), \
             mock.patch.object(self.app, "_pc_name_for", return_value="John"), \
             mock.patch.object(self.app, "_get_controlled_unit_or_pc", return_value=c):
            self.app._adjudicate_attack_request(msg, cid=1, ws_id="ws", is_admin=False)

            # Should toast with reason
            toasts = [str(args[1]) for args, kwargs in self.app._lan.toast.call_args_list]
            self.assertTrue(any("Requested weapon 'missing' not found" in t for t in toasts))


if __name__ == "__main__":
    unittest.main()
