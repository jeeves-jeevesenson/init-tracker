import unittest
from pathlib import Path

import yaml


class ShopCatalogTests(unittest.TestCase):
    BUCKET_DIRS = {
        "weapon": Path("Items/Weapons"),
        "armor": Path("Items/Armor"),
        "magic_item": Path("Items/Magic_Items"),
        "consumable": Path("Items/Consumables"),
    }

    @staticmethod
    def _load_yaml(path: Path):
        return yaml.safe_load(path.read_text(encoding="utf-8"))

    @classmethod
    def _item_ids_for_bucket(cls, bucket: str):
        ids = set()
        base = cls.BUCKET_DIRS[bucket]
        for path in sorted(base.glob("*.yaml")):
            data = cls._load_yaml(path) or {}
            if not isinstance(data, dict):
                continue
            item_id = str(data.get("id") or "").strip()
            if item_id:
                ids.add(item_id)
        return ids

    def test_shop_catalog_file_exists(self):
        self.assertTrue(Path("Items/Shop/catalog.yaml").exists())

    def test_shop_readme_exists(self):
        self.assertTrue(Path("Items/Shop/README.md").exists())

    def test_shop_catalog_entries_reference_real_item_ids(self):
        catalog = self._load_yaml(Path("Items/Shop/catalog.yaml")) or {}
        entries = catalog.get("entries") or []
        self.assertTrue(entries, msg="catalog entries must not be empty")

        cached_ids = {bucket: self._item_ids_for_bucket(bucket) for bucket in self.BUCKET_DIRS}
        for entry in entries:
            self.assertIsInstance(entry, dict)
            bucket = str(entry.get("item_bucket") or "").strip()
            item_id = str(entry.get("item_id") or "").strip()
            self.assertIn(bucket, self.BUCKET_DIRS)
            self.assertIn(item_id, cached_ids[bucket], msg=f"{item_id} not found in {bucket}")

    def test_shop_catalog_entry_shape_and_price_schema(self):
        allowed_buckets = set(self.BUCKET_DIRS.keys())
        allowed_price_keys = {"gp", "sp", "cp"}

        catalog = self._load_yaml(Path("Items/Shop/catalog.yaml")) or {}
        self.assertEqual(int(catalog.get("format_version") or 0), 1)
        entries = catalog.get("entries") or []
        self.assertIsInstance(entries, list)

        for entry in entries:
            self.assertTrue(str(entry.get("item_id") or "").strip())
            self.assertIn(str(entry.get("item_bucket") or "").strip(), allowed_buckets)
            self.assertTrue(str(entry.get("shop_category") or "").strip())
            self.assertIsInstance(entry.get("enabled"), bool)

            price = entry.get("price") or {}
            self.assertIsInstance(price, dict)
            self.assertTrue(price, msg="price must include at least one denomination")
            unknown = set(price.keys()) - allowed_price_keys
            self.assertFalse(unknown, msg=f"unsupported price keys: {sorted(unknown)}")
            for key, value in price.items():
                self.assertIsInstance(value, int, msg=f"price {key} must be an integer")
                self.assertGreaterEqual(value, 0, msg=f"price {key} must be non-negative")

    def test_shop_catalog_has_multibucket_coverage(self):
        catalog = self._load_yaml(Path("Items/Shop/catalog.yaml")) or {}
        entries = catalog.get("entries") or []
        counts = {"weapon": 0, "armor": 0, "consumable": 0, "magic_item": 0}

        for entry in entries:
            bucket = str((entry or {}).get("item_bucket") or "").strip()
            if bucket in counts:
                counts[bucket] += 1

        self.assertGreaterEqual(counts["weapon"], 2)
        self.assertGreaterEqual(counts["armor"], 2)
        self.assertGreaterEqual(counts["consumable"], 3)
        self.assertGreaterEqual(counts["magic_item"], 2)


if __name__ == "__main__":
    unittest.main()
