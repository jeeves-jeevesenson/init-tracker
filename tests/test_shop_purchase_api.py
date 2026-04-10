import copy
import tempfile
import threading
import types
import unittest
from pathlib import Path
from unittest import mock

import pytest
import yaml

pytest.importorskip("httpx")

from fastapi.testclient import TestClient

import dnd_initative_tracker as tracker_mod


class _PurchaseApiAppStub:
    combatants = {}

    def _oplog(self, *_args, **_kwargs):
        return None

    def _lan_snapshot(self):
        return {"grid": None, "obstacles": [], "units": [], "active_cid": None, "round_num": 0}

    def _lan_pcs(self):
        return []

    def after(self, *_args, **_kwargs):
        return None

    def _load_shop_catalog_normalized(self):
        return []

    def _purchase_shop_item_for_player(self, _name, _payload):
        return {"ok": True}


class ShopPurchaseApiRouteTests(unittest.TestCase):
    def _build_lan_controller(self):
        lan = object.__new__(tracker_mod.LanController)
        lan._tracker = _PurchaseApiAppStub()
        lan.cfg = types.SimpleNamespace(host="127.0.0.1", port=0, vapid_public_key=None, allowlist=[], denylist=[], admin_password=None)
        lan._server_thread = None
        lan._fastapi_app = None
        lan._polling = False
        lan._cached_snapshot = {}
        lan._cached_pcs = []
        lan._clients_lock = threading.RLock()
        lan._actions = None
        lan._best_lan_url = lambda: "http://127.0.0.1:0"
        lan._tick = lambda: None
        lan._append_lan_log = lambda *_args, **_kwargs: None
        lan._init_admin_auth = lambda: None
        lan._admin_password_hash = None
        lan._admin_token_ttl_seconds = 900
        lan._save_push_subscription = lambda *_args, **_kwargs: True
        lan._admin_password_matches = lambda *_args, **_kwargs: False
        lan._issue_admin_token = lambda: "token"
        return lan

    def _build_test_client(self):
        lan = self._build_lan_controller()
        with mock.patch("threading.Thread.start", return_value=None):
            lan.start(quiet=True)
        return TestClient(lan._fastapi_app), lan

    def test_purchase_route_forwards_payload_and_returns_success(self):
        client, lan = self._build_test_client()
        payload = {"item_bucket": "consumable", "item_id": "healing_potion", "quantity": 2}
        expected = {"ok": True, "purchase": {"item_id": "healing_potion"}}
        with mock.patch.object(lan.app, "_purchase_shop_item_for_player", return_value=expected) as purchase_mock:
            response = client.post("/api/shop/players/Alice/purchase", json=payload)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(expected, response.json())
        purchase_mock.assert_called_once_with("Alice", payload)


class ShopPurchaseApiTransactionTests(unittest.TestCase):
    def setUp(self):
        self.app = object.__new__(tracker_mod.InitiativeTracker)
        self.app._oplog = lambda *_args, **_kwargs: None
        self.app._player_yaml_lock = threading.RLock()
        self.app._player_yaml_cache_by_path = {}
        self.app._player_yaml_meta_by_path = {}
        self.app._player_yaml_data_by_name = {}
        self.app._player_yaml_name_map = {}
        self.app._player_yaml_refresh_scheduled = False
        self.app.after = lambda *_args, **_kwargs: None
        self.app._lan = types.SimpleNamespace(_cached_snapshot={})
        self.app._lan_snapshot = lambda: {}
        self.app._normalize_player_profile = lambda payload, _fallback_name: copy.deepcopy(payload)

    def _write_yaml(self, path: Path, payload):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    def _seed_items(self, root: Path, *, healing_enabled: bool = True):
        items_dir = root / "Items"
        self._write_yaml(items_dir / "Consumables" / "healing_potion.yaml", {
            "id": "healing_potion",
            "name": "Healing Potion",
            "type": "consumable",
            "kind": "consumable",
            "stackable": True,
        })
        self._write_yaml(items_dir / "Weapons" / "longsword.yaml", {
            "id": "longsword",
            "name": "Longsword",
            "type": "weapon",
        })
        self._write_yaml(items_dir / "Armor" / "leather.yaml", {
            "id": "leather",
            "name": "Leather",
            "type": "armor",
        })
        self._write_yaml(items_dir / "Magic_Items" / "wand_of_sparking.yaml", {
            "id": "wand_of_sparking",
            "name": "Wand of Sparking",
            "type": "wondrous",
            "requires_attunement": True,
        })
        self._write_yaml(items_dir / "Gear" / "arrow.yaml", {
            "id": "arrow",
            "name": "Arrow",
            "type": "gear",
            "kind": "gear",
            "stackable": True,
        })
        self._write_yaml(items_dir / "Gear" / "rope.yaml", {
            "id": "rope",
            "name": "Rope, Hempen (50 feet)",
            "type": "gear",
            "kind": "gear",
            "stackable": False,
        })
        self._write_yaml(
            items_dir / "Shop" / "catalog.yaml",
            {
                "format_version": 1,
                "entries": [
                    {
                        "item_id": "healing_potion",
                        "item_bucket": "consumable",
                        "shop_category": "consumables",
                        "enabled": healing_enabled,
                        "price": {"gp": 5},
                        "stock": {"limit": 3, "sold": 0},
                    },
                    {
                        "item_id": "longsword",
                        "item_bucket": "weapon",
                        "shop_category": "weapons",
                        "enabled": True,
                        "price": {"gp": 15},
                    },
                    {
                        "item_id": "wand_of_sparking",
                        "item_bucket": "magic_item",
                        "shop_category": "magic_items",
                        "enabled": True,
                        "price": {"gp": 250},
                    },
                    {
                        "item_id": "arrow",
                        "item_bucket": "gear",
                        "shop_category": "gear",
                        "enabled": True,
                        "price": {"cp": 5},
                    },
                    {
                        "item_id": "rope",
                        "item_bucket": "gear",
                        "shop_category": "gear",
                        "enabled": True,
                        "price": {"gp": 1},
                    },
                ],
            },
        )
        return items_dir

    def _seed_player(self, root: Path, *, gp: int = 100):
        player_path = root / "players" / "alice.yaml"
        self._write_yaml(
            player_path,
            {
                "name": "Alice",
                "inventory": {
                    "currency": {"gp": gp, "sp": 0, "cp": 0},
                    "items": [
                        {
                            "instance_id": "healing_potion_stack",
                            "id": "healing_potion",
                            "name": "Healing Potion",
                            "quantity": 1,
                            "equipped": False,
                        }
                    ],
                },
            },
        )
        return player_path

    def test_successful_purchase_of_stackable_consumable_increments_quantity_and_deducts_currency(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            items_dir = self._seed_items(root)
            player_path = self._seed_player(root)
            self.app._resolve_items_dir = lambda: items_dir
            self.app._resolve_character_path = lambda _name: player_path

            result = self.app._purchase_shop_item_for_player(
                "Alice", {"item_bucket": "consumable", "item_id": "healing_potion", "quantity": 2}
            )

            self.assertTrue(result.get("ok"))
            self.assertTrue(result.get("inventory_change", {}).get("stacked"))
            persisted = yaml.safe_load(player_path.read_text(encoding="utf-8"))
            self.assertEqual({"gp": 90, "sp": 0, "cp": 0}, persisted["inventory"]["currency"])
            self.assertEqual(3, persisted["inventory"]["items"][0]["quantity"])
            persisted_catalog = yaml.safe_load((items_dir / "Shop" / "catalog.yaml").read_text(encoding="utf-8"))
            self.assertEqual(2, persisted_catalog["entries"][0]["stock"]["sold"])

    def test_successful_purchase_non_stackable_creates_instance_id_and_repeated_purchase_creates_separate_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            items_dir = self._seed_items(root)
            player_path = self._seed_player(root)
            self.app._resolve_items_dir = lambda: items_dir
            self.app._resolve_character_path = lambda _name: player_path

            first = self.app._purchase_shop_item_for_player("Alice", {"item_bucket": "weapon", "item_id": "longsword"})
            second = self.app._purchase_shop_item_for_player("Alice", {"item_bucket": "weapon", "item_id": "longsword"})

            first_ids = first.get("inventory_change", {}).get("created_instance_ids") or []
            second_ids = second.get("inventory_change", {}).get("created_instance_ids") or []
            self.assertEqual(1, len(first_ids))
            self.assertEqual(1, len(second_ids))
            self.assertNotEqual(first_ids[0], second_ids[0])

            persisted = yaml.safe_load(player_path.read_text(encoding="utf-8"))
            longswords = [entry for entry in persisted["inventory"]["items"] if entry.get("id") == "longsword"]
            self.assertEqual(2, len(longswords))
            self.assertTrue(all(entry.get("equipped") is False for entry in longswords))

    def test_successful_purchase_magic_item_initializes_attuned_false(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            items_dir = self._seed_items(root)
            player_path = self._seed_player(root, gp=300)
            self.app._resolve_items_dir = lambda: items_dir
            self.app._resolve_character_path = lambda _name: player_path

            self.app._purchase_shop_item_for_player("Alice", {"item_bucket": "magic_item", "item_id": "wand_of_sparking"})

            persisted = yaml.safe_load(player_path.read_text(encoding="utf-8"))
            owned = [entry for entry in persisted["inventory"]["items"] if entry.get("id") == "wand_of_sparking"]
            self.assertEqual(1, len(owned))
            self.assertEqual(False, owned[0].get("attuned"))

    def test_insufficient_funds_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            items_dir = self._seed_items(root)
            player_path = self._seed_player(root)
            self.app._resolve_items_dir = lambda: items_dir
            self.app._resolve_character_path = lambda _name: player_path

            with self.assertRaises(tracker_mod.CharacterApiError) as ctx:
                self.app._purchase_shop_item_for_player("Alice", {"item_bucket": "magic_item", "item_id": "wand_of_sparking"})

            self.assertEqual(409, ctx.exception.status_code)
            self.assertEqual("insufficient_funds", (ctx.exception.detail or {}).get("error"))

    def test_disabled_catalog_entry_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            items_dir = self._seed_items(root, healing_enabled=False)
            player_path = self._seed_player(root)
            self.app._resolve_items_dir = lambda: items_dir
            self.app._resolve_character_path = lambda _name: player_path

            with self.assertRaises(tracker_mod.CharacterApiError) as ctx:
                self.app._purchase_shop_item_for_player(
                    "Alice", {"item_bucket": "consumable", "item_id": "healing_potion", "quantity": 1}
                )

            self.assertEqual(400, ctx.exception.status_code)
            self.assertEqual("catalog_disabled", (ctx.exception.detail or {}).get("error"))

    def test_unknown_catalog_target_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            items_dir = self._seed_items(root)
            player_path = self._seed_player(root)
            self.app._resolve_items_dir = lambda: items_dir
            self.app._resolve_character_path = lambda _name: player_path

            with self.assertRaises(tracker_mod.CharacterApiError) as ctx:
                self.app._purchase_shop_item_for_player("Alice", {"item_bucket": "weapon", "item_id": "unknown_item"})

            self.assertEqual(404, ctx.exception.status_code)
            self.assertEqual("not_found", (ctx.exception.detail or {}).get("error"))

    def test_catalog_entry_with_missing_definition_is_rejected_without_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            items_dir = self._seed_items(root)
            player_path = self._seed_player(root, gp=300)
            self.app._resolve_items_dir = lambda: items_dir
            self.app._resolve_character_path = lambda _name: player_path

            catalog_path = items_dir / "Shop" / "catalog.yaml"
            payload = yaml.safe_load(catalog_path.read_text(encoding="utf-8"))
            payload["entries"].append(
                {
                    "item_id": "phantom_blade",
                    "item_bucket": "weapon",
                    "shop_category": "weapons",
                    "enabled": True,
                    "price": {"gp": 1},
                }
            )
            catalog_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
            before_player = player_path.read_text(encoding="utf-8")
            before_catalog = catalog_path.read_text(encoding="utf-8")

            with self.assertRaises(tracker_mod.CharacterApiError) as ctx:
                self.app._purchase_shop_item_for_player("Alice", {"item_bucket": "weapon", "item_id": "phantom_blade"})

            self.assertEqual(500, ctx.exception.status_code)
            self.assertEqual("catalog_load_failed", (ctx.exception.detail or {}).get("error"))
            self.assertEqual(before_player, player_path.read_text(encoding="utf-8"))
            self.assertEqual(before_catalog, catalog_path.read_text(encoding="utf-8"))

    def test_missing_item_identifier_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            items_dir = self._seed_items(root)
            player_path = self._seed_player(root)
            self.app._resolve_items_dir = lambda: items_dir
            self.app._resolve_character_path = lambda _name: player_path

            with self.assertRaises(tracker_mod.CharacterApiError) as ctx:
                self.app._purchase_shop_item_for_player("Alice", {"item_bucket": "weapon"})

            self.assertEqual(400, ctx.exception.status_code)
            self.assertEqual("invalid_purchase", (ctx.exception.detail or {}).get("error"))

    def test_purchase_rejected_when_stock_exhausted_without_charging_currency(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            items_dir = self._seed_items(root)
            player_path = self._seed_player(root)
            self.app._resolve_items_dir = lambda: items_dir
            self.app._resolve_character_path = lambda _name: player_path

            catalog_path = items_dir / "Shop" / "catalog.yaml"
            payload = yaml.safe_load(catalog_path.read_text(encoding="utf-8"))
            payload["entries"][0]["stock"] = {"limit": 2, "sold": 2}
            catalog_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

            with self.assertRaises(tracker_mod.CharacterApiError) as ctx:
                self.app._purchase_shop_item_for_player("Alice", {"item_bucket": "consumable", "item_id": "healing_potion", "quantity": 1})
            self.assertEqual("out_of_stock", (ctx.exception.detail or {}).get("error"))

            persisted = yaml.safe_load(player_path.read_text(encoding="utf-8"))
            self.assertEqual({"gp": 100, "sp": 0, "cp": 0}, persisted["inventory"]["currency"])

    def test_purchase_rejected_when_quantity_exceeds_remaining_stock(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            items_dir = self._seed_items(root)
            player_path = self._seed_player(root)
            self.app._resolve_items_dir = lambda: items_dir
            self.app._resolve_character_path = lambda _name: player_path
            with self.assertRaises(tracker_mod.CharacterApiError) as ctx:
                self.app._purchase_shop_item_for_player("Alice", {"item_bucket": "consumable", "item_id": "healing_potion", "quantity": 4})
            self.assertEqual("insufficient_stock", (ctx.exception.detail or {}).get("error"))

    def test_catalog_save_failure_does_not_persist_player_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            items_dir = self._seed_items(root)
            player_path = self._seed_player(root, gp=300)
            self.app._resolve_items_dir = lambda: items_dir
            self.app._resolve_character_path = lambda _name: player_path
            self.app._save_shop_catalog_payload = mock.Mock(side_effect=RuntimeError("write failed"))
            before_player = player_path.read_text(encoding="utf-8")

            with self.assertRaises(tracker_mod.CharacterApiError) as ctx:
                self.app._purchase_shop_item_for_player(
                    "Alice", {"item_bucket": "consumable", "item_id": "healing_potion", "quantity": 1}
                )

            self.assertEqual(500, ctx.exception.status_code)
            self.assertEqual("catalog_save_failed", (ctx.exception.detail or {}).get("error"))
            self.assertEqual(before_player, player_path.read_text(encoding="utf-8"))

    def test_player_save_failure_rolls_back_catalog_stock_best_effort(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            items_dir = self._seed_items(root)
            player_path = self._seed_player(root, gp=300)
            self.app._resolve_items_dir = lambda: items_dir
            self.app._resolve_character_path = lambda _name: player_path
            original_store = self.app._store_character_yaml
            self.app._store_character_yaml = mock.Mock(side_effect=RuntimeError("player write failed"))
            catalog_path = items_dir / "Shop" / "catalog.yaml"
            before_catalog = yaml.safe_load(catalog_path.read_text(encoding="utf-8"))
            before_player = player_path.read_text(encoding="utf-8")

            with self.assertRaises(tracker_mod.CharacterApiError) as ctx:
                self.app._purchase_shop_item_for_player(
                    "Alice", {"item_bucket": "consumable", "item_id": "healing_potion", "quantity": 1}
                )

            self.assertEqual(500, ctx.exception.status_code)
            self.assertEqual("player_save_failed", (ctx.exception.detail or {}).get("error"))
            after_catalog = yaml.safe_load(catalog_path.read_text(encoding="utf-8"))
            self.assertEqual(before_catalog, after_catalog)
            self.assertEqual(before_player, player_path.read_text(encoding="utf-8"))
            self.app._store_character_yaml = original_store

    def test_gear_stackable_purchase_increments_quantity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            items_dir = self._seed_items(root)
            player_path = self._seed_player(root, gp=50)
            self.app._resolve_items_dir = lambda: items_dir
            self.app._resolve_character_path = lambda _name: player_path

            # First purchase creates a new stack
            first = self.app._purchase_shop_item_for_player("Alice", {"item_bucket": "gear", "item_id": "arrow", "quantity": 10})
            self.assertTrue(first.get("ok"))
            self.assertFalse(first.get("inventory_change", {}).get("stacked"))
            self.assertEqual(1, len(first.get("inventory_change", {}).get("created_instance_ids") or []))

            # Second purchase stacks onto existing
            second = self.app._purchase_shop_item_for_player("Alice", {"item_bucket": "gear", "item_id": "arrow", "quantity": 10})
            self.assertTrue(second.get("ok"))
            self.assertTrue(second.get("inventory_change", {}).get("stacked"))

            persisted = yaml.safe_load(player_path.read_text(encoding="utf-8"))
            arrows = [e for e in persisted["inventory"]["items"] if e.get("id") == "arrow"]
            self.assertEqual(1, len(arrows))
            self.assertEqual(20, arrows[0]["quantity"])

    def test_gear_non_stackable_purchase_creates_separate_instance(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            items_dir = self._seed_items(root)
            player_path = self._seed_player(root, gp=50)
            self.app._resolve_items_dir = lambda: items_dir
            self.app._resolve_character_path = lambda _name: player_path

            result = self.app._purchase_shop_item_for_player("Alice", {"item_bucket": "gear", "item_id": "rope"})

            self.assertTrue(result.get("ok"))
            self.assertFalse(result.get("inventory_change", {}).get("stacked"))
            ids = result.get("inventory_change", {}).get("created_instance_ids") or []
            self.assertEqual(1, len(ids))
            persisted = yaml.safe_load(player_path.read_text(encoding="utf-8"))
            ropes = [e for e in persisted["inventory"]["items"] if e.get("id") == "rope"]
            self.assertEqual(1, len(ropes))

    def test_gear_non_stackable_quantity_gt_1_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            items_dir = self._seed_items(root)
            player_path = self._seed_player(root, gp=50)
            self.app._resolve_items_dir = lambda: items_dir
            self.app._resolve_character_path = lambda _name: player_path

            with self.assertRaises(tracker_mod.CharacterApiError) as ctx:
                self.app._purchase_shop_item_for_player("Alice", {"item_bucket": "gear", "item_id": "rope", "quantity": 3})

            self.assertEqual(400, ctx.exception.status_code)
            self.assertEqual("invalid_purchase", (ctx.exception.detail or {}).get("error"))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            items_dir = self._seed_items(root)
            player_path = self._seed_player(root, gp=300)
            self.app._resolve_items_dir = lambda: items_dir
            self.app._resolve_character_path = lambda _name: player_path
            original_store = self.app._store_character_yaml
            self.app._store_character_yaml = mock.Mock(side_effect=RuntimeError("player write failed"))
            catalog_path = items_dir / "Shop" / "catalog.yaml"
            before_catalog = yaml.safe_load(catalog_path.read_text(encoding="utf-8"))
            before_player = player_path.read_text(encoding="utf-8")

            with self.assertRaises(tracker_mod.CharacterApiError) as ctx:
                self.app._purchase_shop_item_for_player(
                    "Alice", {"item_bucket": "consumable", "item_id": "healing_potion", "quantity": 1}
                )

            self.assertEqual(500, ctx.exception.status_code)
            self.assertEqual("player_save_failed", (ctx.exception.detail or {}).get("error"))
            after_catalog = yaml.safe_load(catalog_path.read_text(encoding="utf-8"))
            self.assertEqual(before_catalog, after_catalog)
            self.assertEqual(before_player, player_path.read_text(encoding="utf-8"))
            self.app._store_character_yaml = original_store


if __name__ == "__main__":
    unittest.main()
