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


class _ApiAppStub:
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

    def _validate_shop_catalog_payload(self, _payload):
        return {"format_version": 1, "entries": []}

    def _save_shop_catalog_payload(self, _payload, *, expected_revision=None):
        return {"format_version": 1, "entries": []}


class ShopCatalogWriteApiTests(unittest.TestCase):
    def _build_lan_controller(self):
        lan = object.__new__(tracker_mod.LanController)
        lan._tracker = _ApiAppStub()
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

    def test_validate_route_returns_normalized_entries_without_saving(self):
        client, lan = self._build_test_client()
        payload = {
            "format_version": 1,
            "entries": [
                {
                    "item_id": "healing_potion",
                    "item_bucket": "consumable",
                    "shop_category": "consumables",
                    "enabled": True,
                    "price": {"gp": 50},
                }
            ],
        }
        normalized = {
            "format_version": 1,
            "entries": [
                {
                    "item_id": "healing_potion",
                    "item_bucket": "consumable",
                    "name": "Healing Potion",
                    "type": "consumable",
                    "shop_category": "consumables",
                    "enabled": True,
                    "price": {"gp": 50},
                    "definition_path": "Items/Consumables/healing_potion.yaml",
                }
            ],
        }
        with mock.patch.object(lan.app, "_validate_shop_catalog_payload", return_value=normalized) as validate_mock:
            with mock.patch.object(lan.app, "_save_shop_catalog_payload") as save_mock:
                response = client.post("/api/shop/catalog/validate", json=payload)

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(1, body.get("format_version"))
        self.assertEqual(["healing_potion"], [row.get("item_id") for row in body.get("entries") or []])
        validate_mock.assert_called_once_with(payload)
        save_mock.assert_not_called()

    def test_validate_route_rejects_invalid_payload_with_http_400(self):
        client, lan = self._build_test_client()
        with mock.patch.object(lan.app, "_validate_shop_catalog_payload", side_effect=ValueError("bad catalog payload")):
            response = client.post("/api/shop/catalog/validate", json={"entries": []})

        self.assertEqual(response.status_code, 400)
        self.assertIn("bad catalog payload", response.json().get("detail", ""))

    def test_put_route_saves_and_returns_normalized_entries(self):
        client, lan = self._build_test_client()
        payload = {
            "format_version": 1,
            "entries": [
                {
                    "item_id": "longsword",
                    "item_bucket": "weapon",
                    "shop_category": "weapons",
                    "enabled": True,
                    "price": {"gp": 20},
                }
            ],
        }
        saved = {
            "format_version": 1,
            "revision": "2-200",
            "entries": [
                {
                    "item_id": "longsword",
                    "item_bucket": "weapon",
                    "name": "Longsword",
                    "type": "weapon",
                    "shop_category": "weapons",
                    "enabled": True,
                    "price": {"gp": 20},
                    "definition_path": "Items/Weapons/longsword.yaml",
                }
            ],
        }
        with mock.patch.object(lan.app, "_save_shop_catalog_payload", return_value=saved) as save_mock:
            response = client.put("/api/shop/catalog", json=payload)

        self.assertEqual(response.status_code, 200)
        response_payload = response.json()
        self.assertEqual(["longsword"], [row.get("item_id") for row in response_payload.get("entries") or []])
        self.assertEqual("2-200", response_payload.get("revision"))
        save_mock.assert_called_once_with(payload, expected_revision=None)

    def test_put_route_passes_expected_revision_to_save_helper(self):
        client, lan = self._build_test_client()
        payload = {
            "format_version": 1,
            "expected_revision": "1-100",
            "entries": [],
        }
        with mock.patch.object(lan.app, "_save_shop_catalog_payload", return_value={"format_version": 1, "entries": [], "revision": "2-100"}) as save_mock:
            response = client.put("/api/shop/catalog", json=payload)
        self.assertEqual(response.status_code, 200)
        save_mock.assert_called_once_with(payload, expected_revision="1-100")

    def test_put_route_returns_409_on_revision_conflict(self):
        client, lan = self._build_test_client()
        with mock.patch.object(
            lan.app,
            "_save_shop_catalog_payload",
            side_effect=tracker_mod.ShopCatalogConflictError("Catalog has changed since load."),
        ):
            response = client.put("/api/shop/catalog", json={"format_version": 1, "expected_revision": "1-100", "entries": []})
        self.assertEqual(response.status_code, 409)
        self.assertIn("Catalog has changed since load", response.json().get("detail", ""))


class ShopCatalogWriteHelpersTests(unittest.TestCase):
    def setUp(self):
        self.app = object.__new__(tracker_mod.InitiativeTracker)
        self.app._oplog = lambda *args, **kwargs: None

    def _write_yaml(self, path: Path, payload):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    def _seed_item_definitions(self, items_dir: Path):
        self._write_yaml(items_dir / "Weapons" / "longsword.yaml", {"id": "longsword", "name": "Longsword", "type": "weapon"})
        self._write_yaml(items_dir / "Consumables" / "healing_potion.yaml", {"id": "healing_potion", "name": "Healing Potion", "type": "consumable"})
        self._write_yaml(items_dir / "Armor" / "leather.yaml", {"id": "leather", "name": "Leather", "type": "armor"})
        self._write_yaml(items_dir / "Magic_Items" / "wand_of_sparking.yaml", {"id": "wand_of_sparking", "name": "Wand", "type": "wand"})

    def test_save_shop_catalog_payload_writes_catalog_yaml(self):
        with tempfile.TemporaryDirectory() as tmp:
            items_dir = Path(tmp) / "Items"
            self._seed_item_definitions(items_dir)
            catalog_path = items_dir / "Shop" / "catalog.yaml"
            self._write_yaml(catalog_path, {"format_version": 1, "entries": []})

            payload = {
                "format_version": 1,
                "entries": [
                    {
                        "item_id": "healing_potion",
                        "item_bucket": "consumable",
                        "shop_category": "consumables",
                        "enabled": True,
                        "price": {"gp": 50},
                    }
                ],
            }
            with mock.patch.object(self.app, "_resolve_items_dir", return_value=items_dir):
                saved = self.app._save_shop_catalog_payload(payload)

            self.assertEqual(["healing_potion"], [row.get("item_id") for row in saved.get("entries") or []])
            self.assertTrue(bool(str(saved.get("revision") or "").strip()))
            persisted = yaml.safe_load(catalog_path.read_text(encoding="utf-8"))
            self.assertEqual(1, persisted.get("format_version"))
            self.assertEqual("healing_potion", persisted["entries"][0]["item_id"])
            self.assertEqual({"gp": 50}, persisted["entries"][0]["price"])

    def test_save_shop_catalog_payload_rejects_stale_expected_revision(self):
        with tempfile.TemporaryDirectory() as tmp:
            items_dir = Path(tmp) / "Items"
            self._seed_item_definitions(items_dir)
            catalog_path = items_dir / "Shop" / "catalog.yaml"
            self._write_yaml(catalog_path, {"format_version": 1, "entries": []})
            payload = {
                "format_version": 1,
                "entries": [
                    {
                        "item_id": "longsword",
                        "item_bucket": "weapon",
                        "shop_category": "weapons",
                        "enabled": True,
                        "price": {"gp": 20},
                    }
                ],
            }
            with mock.patch.object(self.app, "_resolve_items_dir", return_value=items_dir):
                with self.assertRaises(tracker_mod.ShopCatalogConflictError):
                    self.app._save_shop_catalog_payload(payload, expected_revision="stale-revision")

    def test_save_shop_catalog_payload_failure_does_not_corrupt_existing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            items_dir = Path(tmp) / "Items"
            self._seed_item_definitions(items_dir)
            catalog_path = items_dir / "Shop" / "catalog.yaml"
            original_payload = {
                "format_version": 1,
                "entries": [
                    {
                        "item_id": "longsword",
                        "item_bucket": "weapon",
                        "shop_category": "weapons",
                        "enabled": True,
                        "price": {"gp": 15},
                    }
                ],
            }
            self._write_yaml(catalog_path, original_payload)
            original_text = catalog_path.read_text(encoding="utf-8")

            with mock.patch.object(self.app, "_resolve_items_dir", return_value=items_dir):
                with mock.patch("dnd_initative_tracker.yaml.safe_dump", side_effect=OSError("disk full")):
                    with self.assertRaises(OSError):
                        self.app._save_shop_catalog_payload(original_payload)

            self.assertEqual(original_text, catalog_path.read_text(encoding="utf-8"))
            self.assertFalse(list((items_dir / "Shop").glob("*.tmp")))


if __name__ == "__main__":
    unittest.main()
