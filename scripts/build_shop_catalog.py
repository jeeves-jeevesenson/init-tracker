#!/usr/bin/env python3
"""Build or refresh the shop catalog from item definition directories.

Usage:
  python scripts/build_shop_catalog.py [--items-dir Items] [--catalog Items/Shop/catalog.yaml]
                                       [--enable-buckets weapon,armor,magic_item,consumable,gear]
                                       [--enable-tiers A,B,C]
                                       [--dry-run]

This script scans all item definitions in the configured buckets and generates
a shop catalog.yaml that:
  - Includes every definition that passes eligibility filters
  - Preserves existing entries' prices, stock, and enabled-state where possible
  - Assigns sensible default prices by rarity and bucket
  - Skips definitions that are missing a valid id/name
  - Emits a summary of what was added / preserved / skipped

It is designed to be re-run safely (idempotent with respect to stable entries).
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_ITEMS_DIR = REPO_ROOT / "Items"
DEFAULT_CATALOG_PATH = DEFAULT_ITEMS_DIR / "Shop" / "catalog.yaml"

BUCKET_DIRS: Dict[str, str] = {
    "weapon": "Weapons",
    "armor": "Armor",
    "magic_item": "Magic_Items",
    "consumable": "Consumables",
    "gear": "Gear",
}

BUCKET_DEFAULT_CATEGORIES: Dict[str, str] = {
    "weapon": "weapons",
    "armor": "armor",
    "magic_item": "magic_items",
    "consumable": "consumables",
    "gear": "gear",
}

# Default prices by rarity (in gp) for magic items
RARITY_DEFAULT_GP: Dict[str, int] = {
    "common": 50,
    "uncommon": 250,
    "rare": 1000,
    "very rare": 5000,
    "legendary": 25000,
    "artifact": 0,  # priceless — leave at 0 meaning admin must set
}

# Default prices by bucket for non-magic items (gp)
BUCKET_DEFAULT_GP: Dict[str, int] = {
    "weapon": 15,
    "armor": 25,
    "consumable": 5,
    "gear": 1,
}


def compute_item_tier(definition: Dict[str, Any]) -> str:
    """Mirror the backend _compute_item_tier logic."""
    if isinstance(definition.get("grants"), dict) and any(
        k in definition["grants"] for k in ("spells", "actions", "pools", "modifiers", "aura")
    ):
        return "A"
    if (
        isinstance(definition.get("description"), str) and definition["description"].strip()
    ) or definition.get("rarity") or definition.get("requires_attunement"):
        return "B"
    return "C"


def load_definitions(items_dir: Path, bucket: str) -> Dict[str, Dict[str, Any]]:
    bucket_dir = items_dir / BUCKET_DIRS[bucket]
    result: Dict[str, Dict[str, Any]] = {}
    if not bucket_dir.is_dir():
        return result
    for path in sorted(bucket_dir.glob("*.yaml")):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception as exc:
            print(f"  WARN: parse error in {path.name}: {exc}", file=sys.stderr)
            continue
        if not isinstance(data, dict):
            continue
        item_id = str(data.get("id") or "").strip().lower()
        if not item_id:
            continue
        data["_path"] = str(path.as_posix())
        result[item_id] = data
    return result


def default_price_for(bucket: str, definition: Dict[str, Any]) -> Dict[str, int]:
    if bucket == "magic_item":
        rarity = str(definition.get("rarity") or "").strip().lower()
        gp = RARITY_DEFAULT_GP.get(rarity, 100)
    else:
        gp = BUCKET_DEFAULT_GP.get(bucket, 1)
    if gp > 0:
        return {"gp": gp}
    return {"gp": 0}


def default_category_for(bucket: str, definition: Dict[str, Any]) -> str:
    consumable_type = str(definition.get("consumable_type") or "").strip().lower()
    if consumable_type == "scroll":
        return "scrolls"
    category = str(definition.get("category") or "").strip().lower()
    if bucket == "gear" and category:
        return category
    return BUCKET_DEFAULT_CATEGORIES.get(bucket, bucket)


def load_existing_catalog(catalog_path: Path) -> Dict[str, Any]:
    if not catalog_path.exists():
        return {"format_version": 1, "entries": []}
    try:
        data = yaml.safe_load(catalog_path.read_text(encoding="utf-8")) or {}
        return data if isinstance(data, dict) else {"format_version": 1, "entries": []}
    except Exception:
        return {"format_version": 1, "entries": []}


def build_entry_key(bucket: str, item_id: str) -> str:
    return f"{bucket}:{item_id}"


def build_catalog(
    items_dir: Path,
    existing_catalog: Dict[str, Any],
    *,
    enable_buckets: Set[str],
    enable_tiers: Set[str],
) -> Dict[str, Any]:
    # Index existing entries for preservation
    existing_by_key: Dict[str, Dict[str, Any]] = {}
    for entry in existing_catalog.get("entries") or []:
        if not isinstance(entry, dict):
            continue
        key = build_entry_key(
            str(entry.get("item_bucket") or "").strip().lower(),
            str(entry.get("item_id") or "").strip().lower(),
        )
        existing_by_key[key] = entry

    new_entries: List[Dict[str, Any]] = []
    stats = {"added": 0, "preserved": 0, "skipped_tier": 0, "skipped_bucket": 0, "skipped_invalid": 0}

    for bucket in sorted(BUCKET_DIRS.keys()):
        if bucket not in enable_buckets:
            continue
        definitions = load_definitions(items_dir, bucket)
        for item_id in sorted(definitions.keys()):
            defn = definitions[item_id]
            tier = compute_item_tier(defn)
            if tier not in enable_tiers:
                stats["skipped_tier"] += 1
                continue
            name = str(defn.get("name") or item_id).strip()
            if not name:
                stats["skipped_invalid"] += 1
                continue

            key = build_entry_key(bucket, item_id)
            if key in existing_by_key:
                new_entries.append(existing_by_key[key])
                stats["preserved"] += 1
                continue

            entry: Dict[str, Any] = {
                "item_id": item_id,
                "item_bucket": bucket,
                "shop_category": default_category_for(bucket, defn),
                "enabled": False,  # admin must explicitly enable
                "price": default_price_for(bucket, defn),
            }
            new_entries.append(entry)
            stats["added"] += 1

    return {"format_version": 1, "entries": new_entries}, stats


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--items-dir", default=str(DEFAULT_ITEMS_DIR), help="Path to Items directory")
    parser.add_argument("--catalog", default=str(DEFAULT_CATALOG_PATH), help="Path to catalog.yaml output")
    parser.add_argument(
        "--enable-buckets",
        default="weapon,armor,magic_item,consumable,gear",
        help="Comma-separated bucket names to include",
    )
    parser.add_argument(
        "--enable-tiers",
        default="A,B,C",
        help="Comma-separated tiers to include (A, B, C)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print what would change without writing")
    args = parser.parse_args()

    items_dir = Path(args.items_dir).resolve()
    catalog_path = Path(args.catalog).resolve()
    enable_buckets = {b.strip().lower() for b in args.enable_buckets.split(",") if b.strip()}
    enable_tiers = {t.strip().upper() for t in args.enable_tiers.split(",") if t.strip()}

    if not items_dir.is_dir():
        print(f"ERROR: items_dir not found: {items_dir}", file=sys.stderr)
        return 1

    existing = load_existing_catalog(catalog_path)
    new_catalog, stats = build_catalog(items_dir, existing, enable_buckets=enable_buckets, enable_tiers=enable_tiers)

    print(f"Catalog build summary:")
    print(f"  Preserved existing entries : {stats['preserved']}")
    print(f"  New entries added (disabled): {stats['added']}")
    print(f"  Skipped by tier filter     : {stats['skipped_tier']}")
    print(f"  Skipped (invalid/missing)  : {stats['skipped_invalid']}")
    print(f"  Total output entries       : {len(new_catalog['entries'])}")

    if args.dry_run:
        print("\n--dry-run: no file written.")
        return 0

    catalog_path.parent.mkdir(parents=True, exist_ok=True)
    catalog_path.write_text(yaml.safe_dump(new_catalog, sort_keys=False, allow_unicode=True), encoding="utf-8")
    print(f"\nWritten to: {catalog_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
