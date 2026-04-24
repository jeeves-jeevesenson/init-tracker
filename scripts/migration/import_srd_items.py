#!/usr/bin/env python3
"""Bulk-import open SRD item data into local YAML item definitions.

This script is intentionally conservative:
- it writes into the repo's existing item buckets
- it skips files that already exist unless --overwrite is passed
- it emits simple, repo-compatible stubs for complex magic items
- it can optionally emit suggested shop overlay entries for later review

The default source adapter fetches 2014 SRD equipment + magic items from the
D&D 5e API at https://www.dnd5eapi.co/api/2014. It is designed to be "good
enough" for bootstrapping the catalog, not a perfect 1:1 importer for every
possible external schema nuance.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import urlopen

import yaml


DEFAULT_API_BASE_URL = "https://www.dnd5eapi.co/api/2014"
DEFAULT_TIMEOUT_SECONDS = 30


@dataclass
class ImportRecord:
    bucket: str
    item_id: str
    payload: Dict[str, Any]
    source_url: str
    source_name: str
    notes: List[str]
    skip_reason: Optional[str] = None


def normalize_identifier(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = text.replace("'", "")
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")


def normalize_text_block(lines: Iterable[Any]) -> str:
    parts: List[str] = []
    for line in lines:
        text = str(line or "").strip()
        if text:
            parts.append(text)
    return "\n\n".join(parts).strip()


def money_payload(quantity: Any, unit: Any) -> Optional[Dict[str, int]]:
    if isinstance(quantity, bool):
        return None
    try:
        amount = int(quantity or 0)
    except Exception:
        return None
    if amount < 0:
        return None
    unit_key = str(unit or "").strip().lower()
    unit_map = {"gp": "gp", "sp": "sp", "cp": "cp", "pp": None, "ep": None}
    mapped = unit_map.get(unit_key)
    if mapped is None:
        return None
    if amount == 0:
        return {mapped: 0}
    return {mapped: amount}


def scalar_cost_gp(cost_payload: Optional[Dict[str, int]]) -> Optional[int]:
    if not isinstance(cost_payload, dict) or not cost_payload:
        return None
    if set(cost_payload.keys()) == {"gp"}:
        try:
            return int(cost_payload["gp"])
        except Exception:
            return None
    return None


def build_source_block(*, provider: str, edition: str, source_url: str) -> Dict[str, Any]:
    return {"provider": provider, "edition": edition, "url": source_url}


def classify_equipment_bucket(entry: Dict[str, Any]) -> str:
    if any(key in entry for key in ("weapon_category", "weapon_range", "damage")):
        return "weapon"
    if any(key in entry for key in ("armor_category", "armor_class")):
        return "armor"
    return "gear"


def infer_gear_category(entry: Dict[str, Any]) -> Tuple[str, Optional[str]]:
    equipment_category = entry.get("equipment_category") if isinstance(entry.get("equipment_category"), dict) else {}
    gear_category = entry.get("gear_category") if isinstance(entry.get("gear_category"), dict) else {}
    tool_category = entry.get("tool_category")
    vehicle_category = entry.get("vehicle_category")
    category_index = str(equipment_category.get("index") or "").strip().lower()

    if category_index == "adventuring-gear":
        subtype = normalize_identifier(gear_category.get("index") or gear_category.get("name") or "")
        return "adventuring_gear", subtype or None
    if category_index == "tools":
        subtype = normalize_identifier(tool_category or "")
        return "tool", subtype or None
    if category_index == "mounts-and-vehicles":
        subtype = normalize_identifier(vehicle_category or "")
        return "vehicle", subtype or None
    if category_index == "weapon":
        return "weapon_accessory", None
    if category_index == "armor":
        return "armor_accessory", None
    if category_index == "ammunition":
        return "ammunition", None
    if category_index == "equipment-packs":
        return "equipment_pack", None

    normalized = normalize_identifier(category_index or equipment_category.get("name") or "gear")
    return normalized or "gear", None


def should_default_stackable(entry: Dict[str, Any], *, bucket: str, category: str) -> bool:
    if bucket == "consumable":
        return True
    if bucket != "gear":
        return False
    if category in {"ammunition"}:
        return True
    name = str(entry.get("name") or "").strip().lower()
    return name.startswith("rations") or name.startswith("torches") or name.startswith("ball bearings")


def normalize_weapon_property_names(raw_properties: Any) -> List[str]:
    values: List[str] = []
    if not isinstance(raw_properties, list):
        return values
    for raw_entry in raw_properties:
        if isinstance(raw_entry, dict):
            label = raw_entry.get("index") or raw_entry.get("name")
        else:
            label = raw_entry
        normalized = normalize_identifier(label)
        if normalized and normalized not in values:
            values.append(normalized)
    return values


def build_weapon_payload(entry: Dict[str, Any], *, source_url: str) -> ImportRecord:
    item_id = normalize_identifier(entry.get("index") or entry.get("name"))
    damage = entry.get("damage") if isinstance(entry.get("damage"), dict) else {}
    damage_dice = str(damage.get("damage_dice") or "").strip()
    damage_type = (
        str((damage.get("damage_type") or {}).get("index") or (damage.get("damage_type") or {}).get("name") or "")
        .strip()
        .lower()
    )

    weapon_category = normalize_identifier(entry.get("weapon_category") or "weapon")
    weapon_range = normalize_identifier(entry.get("weapon_range") or "melee")
    category = f"{weapon_category}_{weapon_range}".strip("_")
    payload: Dict[str, Any] = {
        "format_version": 1,
        "id": item_id,
        "name": str(entry.get("name") or item_id).strip() or item_id,
        "type": "weapon",
        "category": category or "weapon",
        "weapon_group": category or "weapon",
        "source": build_source_block(provider="dnd5eapi", edition="2014", source_url=source_url),
    }

    cost_payload = money_payload((entry.get("cost") or {}).get("quantity"), (entry.get("cost") or {}).get("unit"))
    cost_gp = scalar_cost_gp(cost_payload)
    if cost_gp is not None:
        payload["cost_gp"] = cost_gp
    elif cost_payload:
        payload["cost"] = cost_payload

    try:
        weight = entry.get("weight")
        if weight is not None and not isinstance(weight, bool):
            payload["weight_lb"] = float(weight) if "." in str(weight) else int(weight)
    except Exception:
        pass

    notes: List[str] = []
    if damage_dice and damage_type:
        payload["damage"] = {
            "one_handed": {
                "formula": damage_dice,
                "type": damage_type,
            }
        }
    else:
        notes.append("manual review: weapon missing damage fields from source payload")

    properties = normalize_weapon_property_names(entry.get("properties"))
    if properties:
        payload["properties"] = properties

    two_handed_damage = entry.get("two_handed_damage") if isinstance(entry.get("two_handed_damage"), dict) else {}
    versatile_formula = str(two_handed_damage.get("damage_dice") or "").strip()
    if versatile_formula and payload.get("damage", {}).get("one_handed"):
        payload["damage"]["versatile"] = {
            "formula": versatile_formula,
            "type": damage_type or str((two_handed_damage.get("damage_type") or {}).get("index") or "").strip().lower(),
        }

    desc_text = normalize_text_block(entry.get("desc") or [])
    if desc_text:
        payload["description"] = desc_text

    payload.setdefault("import_notes", [])
    payload["import_notes"].append("Imported from 2014 SRD equipment data.")
    if "mastery" not in payload:
        payload["import_notes"].append("Weapon mastery was not inferred automatically.")
        notes.append("manual review: add 2024 mastery if needed")

    return ImportRecord(
        bucket="weapon",
        item_id=item_id,
        payload=payload,
        source_url=source_url,
        source_name=str(entry.get("name") or item_id),
        notes=notes,
    )


def build_armor_payload(entry: Dict[str, Any], *, source_url: str) -> ImportRecord:
    item_id = normalize_identifier(entry.get("index") or entry.get("name"))
    armor_category = normalize_identifier(entry.get("armor_category") or "armor")
    armor_class = entry.get("armor_class") if isinstance(entry.get("armor_class"), dict) else {}
    base_value = armor_class.get("base")
    if base_value is None:
        raise ValueError(f"armor item '{entry.get('name')}' is missing armor_class.base")

    payload: Dict[str, Any] = {
        "format_version": 1,
        "id": item_id,
        "name": str(entry.get("name") or item_id).strip() or item_id,
        "type": "armor",
        "category": "shield" if armor_category == "shield" else armor_category,
        "ac": {"base_formula": str(int(base_value))},
        "source": build_source_block(provider="dnd5eapi", edition="2014", source_url=source_url),
    }
    notes: List[str] = []

    dex_bonus = armor_class.get("dex_bonus")
    if dex_bonus is False:
        payload["ac"]["dex_cap"] = 0
    elif armor_class.get("max_bonus") is not None:
        try:
            payload["ac"]["dex_cap"] = int(armor_class.get("max_bonus"))
        except Exception:
            notes.append("manual review: armor max dex bonus was not an integer")

    strength_minimum = entry.get("str_minimum", entry.get("strength_minimum"))
    if strength_minimum not in (None, "") and not isinstance(strength_minimum, bool):
        try:
            payload["requirements"] = {"strength": int(strength_minimum)}
        except Exception:
            notes.append("manual review: armor strength minimum was not an integer")

    if bool(entry.get("stealth_disadvantage")) is True:
        payload["properties"] = {"stealth_disadvantage": True}

    cost_payload = money_payload((entry.get("cost") or {}).get("quantity"), (entry.get("cost") or {}).get("unit"))
    cost_gp = scalar_cost_gp(cost_payload)
    if cost_gp is not None:
        payload["cost_gp"] = cost_gp
    elif cost_payload:
        payload["cost"] = cost_payload

    try:
        weight = entry.get("weight")
        if weight is not None and not isinstance(weight, bool):
            payload["weight_lb"] = float(weight) if "." in str(weight) else int(weight)
    except Exception:
        pass

    desc_text = normalize_text_block(entry.get("desc") or [])
    if desc_text:
        payload["description"] = desc_text

    payload.setdefault("import_notes", [])
    payload["import_notes"].append("Imported from 2014 SRD equipment data.")

    return ImportRecord(
        bucket="armor",
        item_id=item_id,
        payload=payload,
        source_url=source_url,
        source_name=str(entry.get("name") or item_id),
        notes=notes,
    )


def build_gear_payload(entry: Dict[str, Any], *, source_url: str) -> ImportRecord:
    item_id = normalize_identifier(entry.get("index") or entry.get("name"))
    category, subtype = infer_gear_category(entry)
    payload: Dict[str, Any] = {
        "format_version": 1,
        "id": item_id,
        "name": str(entry.get("name") or item_id).strip() or item_id,
        "type": "gear",
        "kind": "gear",
        "category": category,
        "source": build_source_block(provider="dnd5eapi", edition="2014", source_url=source_url),
    }
    if subtype:
        payload["subtype"] = subtype

    desc_parts: List[str] = []
    desc_parts.extend(entry.get("desc") or [])
    desc_parts.extend(entry.get("special") or [])
    if isinstance(entry.get("contents"), list) and entry.get("contents"):
        content_lines = []
        for component in entry.get("contents") or []:
            if not isinstance(component, dict):
                continue
            quantity = component.get("quantity")
            item_name = str((component.get("item") or {}).get("name") or component.get("item") or "").strip()
            if not item_name:
                continue
            if quantity in (None, ""):
                content_lines.append(f"- {item_name}")
            else:
                content_lines.append(f"- {quantity} × {item_name}")
        if content_lines:
            desc_parts.append("Contains:\n" + "\n".join(content_lines))
    desc_text = normalize_text_block(desc_parts)
    if desc_text:
        payload["description"] = desc_text

    cost_payload = money_payload((entry.get("cost") or {}).get("quantity"), (entry.get("cost") or {}).get("unit"))
    if cost_payload:
        payload["cost"] = cost_payload

    try:
        weight = entry.get("weight")
        if weight is not None and not isinstance(weight, bool):
            payload["weight_lb"] = float(weight) if "." in str(weight) else int(weight)
    except Exception:
        pass

    if should_default_stackable(entry, bucket="gear", category=category):
        payload["stackable"] = True

    payload.setdefault("import_notes", [])
    payload["import_notes"].append("Imported from 2014 SRD equipment data.")
    notes: List[str] = []

    return ImportRecord(
        bucket="gear",
        item_id=item_id,
        payload=payload,
        source_url=source_url,
        source_name=str(entry.get("name") or item_id),
        notes=notes,
    )


def infer_magic_item_bucket(entry: Dict[str, Any]) -> str:
    equipment_category = entry.get("equipment_category") if isinstance(entry.get("equipment_category"), dict) else {}
    category_name = str(equipment_category.get("name") or "").strip().lower()
    name = str(entry.get("name") or "").strip().lower()
    if "potion" in category_name or name.startswith("potion of "):
        return "consumable"
    if "scroll" in category_name or name.startswith("spell scroll") or name.startswith("scroll of "):
        return "consumable"
    return "magic_item"


def build_magic_item_payload(entry: Dict[str, Any], *, source_url: str) -> ImportRecord:
    item_id = normalize_identifier(entry.get("index") or entry.get("name"))
    bucket = infer_magic_item_bucket(entry)
    name = str(entry.get("name") or item_id).strip() or item_id
    desc_text = normalize_text_block(entry.get("desc") or [])
    rarity_name = str((entry.get("rarity") or {}).get("name") or "").strip().lower()

    notes: List[str] = []
    if bucket == "consumable":
        category_name = str(((entry.get("equipment_category") or {}).get("name") or "")).strip().lower()
        if "scroll" in category_name or name.lower().startswith("spell scroll") or name.lower().startswith("scroll of "):
            category = "scroll"
            consumable_type = "spell_scroll"
            subtype = "magic_scroll"
            notes.append("manual review: attach grants.spells.casts[] if this should cast a known spell")
        else:
            category = "potion"
            consumable_type = "potion"
            subtype = rarity_name or "magic_potion"
        payload = {
            "format_version": 1,
            "id": item_id,
            "name": name,
            "type": "consumable",
            "kind": "consumable",
            "category": category,
            "consumable_type": consumable_type,
            "subtype": subtype,
            "description": desc_text or f"Imported {category} stub.",
            "effect_hint": "Imported from external SRD data. Review description for exact behavior.",
            "stackable": True,
            "source": build_source_block(provider="dnd5eapi", edition="2014", source_url=source_url),
            "import_notes": [
                "Imported from 2014 SRD magic item data.",
                "This is a descriptive stub; add automation manually if desired.",
            ],
        }
        if rarity_name:
            payload["rarity"] = rarity_name
        return ImportRecord(bucket=bucket, item_id=item_id, payload=payload, source_url=source_url, source_name=name, notes=notes)

    equipment_category = entry.get("equipment_category") if isinstance(entry.get("equipment_category"), dict) else {}
    category = normalize_identifier(equipment_category.get("index") or equipment_category.get("name") or "magic_item") or "magic_item"
    payload = {
        "id": item_id,
        "name": name,
        "category": category,
        "description": desc_text or "Imported magic item stub.",
        "source": build_source_block(provider="dnd5eapi", edition="2014", source_url=source_url),
        "import_notes": [
            "Imported from 2014 SRD magic item data.",
            "This is a descriptive stub; add grants/modifiers manually if desired.",
        ],
    }
    if rarity_name:
        payload["rarity"] = rarity_name
    requires_attunement = "attune" in desc_text.lower() or "attunement" in desc_text.lower()
    if requires_attunement:
        payload["requires_attunement"] = True
        notes.append("manual review: verify attunement requirement text")

    return ImportRecord(
        bucket="magic_item",
        item_id=item_id,
        payload=payload,
        source_url=source_url,
        source_name=name,
        notes=notes,
    )


def convert_dnd5eapi_equipment_entry(entry: Dict[str, Any], *, source_url: str) -> ImportRecord:
    bucket = classify_equipment_bucket(entry)
    if bucket == "weapon":
        return build_weapon_payload(entry, source_url=source_url)
    if bucket == "armor":
        return build_armor_payload(entry, source_url=source_url)
    return build_gear_payload(entry, source_url=source_url)


def item_output_path(items_dir: Path, record: ImportRecord) -> Path:
    bucket_dirs = {
        "weapon": "Weapons",
        "armor": "Armor",
        "gear": "Gear",
        "magic_item": "Magic_Items",
        "consumable": "Consumables",
    }
    relative_dir = bucket_dirs.get(record.bucket)
    if not relative_dir:
        raise KeyError(f"Unsupported import bucket '{record.bucket}'.")
    return items_dir / relative_dir / f"{record.item_id}.yaml"


def default_shop_category_for_bucket(bucket: str, payload: Dict[str, Any]) -> str:
    if bucket == "weapon":
        return "weapons"
    if bucket == "armor":
        return "armor"
    if bucket == "gear":
        return "gear"
    if bucket == "consumable":
        category = str(payload.get("category") or "").strip().lower()
        if category == "scroll":
            return "scrolls"
        return "consumables"
    if bucket == "magic_item":
        return "magic_items"
    return "misc"


def build_shop_suggestion(record: ImportRecord) -> Dict[str, Any]:
    suggestion: Dict[str, Any] = {
        "item_id": record.item_id,
        "item_bucket": record.bucket,
        "shop_category": default_shop_category_for_bucket(record.bucket, record.payload),
        "enabled": False,
    }
    if record.bucket == "weapon":
        cost_gp = record.payload.get("cost_gp")
        if isinstance(cost_gp, int) and cost_gp >= 0:
            suggestion["price"] = {"gp": int(cost_gp)}
    elif record.bucket == "armor":
        cost_gp = record.payload.get("cost_gp")
        if isinstance(cost_gp, int) and cost_gp >= 0:
            suggestion["price"] = {"gp": int(cost_gp)}
    elif record.bucket == "gear":
        cost = record.payload.get("cost") if isinstance(record.payload.get("cost"), dict) else {}
        if cost:
            suggestion["price"] = dict(cost)
    if record.bucket == "consumable" and isinstance(record.payload.get("cost"), dict):
        suggestion["price"] = dict(record.payload["cost"])
    return suggestion


def parse_resource_list(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    results = payload.get("results")
    if isinstance(results, list):
        return [entry for entry in results if isinstance(entry, dict)]
    if isinstance(payload.get("count"), int) and isinstance(payload.get("results"), list):
        return [entry for entry in payload["results"] if isinstance(entry, dict)]
    if isinstance(payload.get("index"), str):
        return [payload]
    return []


def fetch_json(url: str, *, timeout: int) -> Any:
    request_headers = {"User-Agent": "dnd-initiative-tracker item importer"}
    request = None
    try:
        from urllib.request import Request
        request = Request(url, headers=request_headers)
    except Exception:
        request = url
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_resource_details(*, base_url: str, resource_path: str, timeout: int) -> List[Tuple[str, Dict[str, Any]]]:
    list_url = urljoin(base_url.rstrip("/") + "/", resource_path.lstrip("/"))
    payload = fetch_json(list_url, timeout=timeout)
    resources = parse_resource_list(payload if isinstance(payload, dict) else {})
    details: List[Tuple[str, Dict[str, Any]]] = []

    for row in resources:
        detail_url = row.get("url")

        if isinstance(detail_url, str) and detail_url.strip():
            if detail_url.startswith("http://") or detail_url.startswith("https://"):
                absolute_url = detail_url
            else:
                absolute_url = urljoin(base_url.rstrip("/") + "/", detail_url)
        else:
            index = str(row.get("index") or "").strip()
            if not index:
                continue
            absolute_url = urljoin(base_url.rstrip("/") + "/", f"{resource_path.strip('/')}/{index}")

        detail_payload = fetch_json(absolute_url, timeout=timeout)
        if isinstance(detail_payload, dict):
            details.append((absolute_url, detail_payload))

    return details


def write_yaml(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")


def collect_records(*, base_url: str, timeout: int, include_weapons: bool) -> Tuple[List[ImportRecord], List[Dict[str, Any]]]:
    records: List[ImportRecord] = []
    report_errors: List[Dict[str, Any]] = []

    for source_url, entry in fetch_resource_details(base_url=base_url, resource_path="/equipment", timeout=timeout):
        try:
            record = convert_dnd5eapi_equipment_entry(entry, source_url=source_url)
        except Exception as exc:
            report_errors.append({"source_url": source_url, "name": str(entry.get("name") or ""), "error": str(exc)})
            continue
        if record.bucket == "weapon" and not include_weapons:
            record.skip_reason = "skipped by default; rerun with --include-weapons to backfill weapon definitions"
        records.append(record)

    for source_url, entry in fetch_resource_details(base_url=base_url, resource_path="/magic-items", timeout=timeout):
        try:
            record = build_magic_item_payload(entry, source_url=source_url)
        except Exception as exc:
            report_errors.append({"source_url": source_url, "name": str(entry.get("name") or ""), "error": str(exc)})
            continue
        records.append(record)

    return records, report_errors


def apply_import(
    *,
    items_dir: Path,
    records: List[ImportRecord],
    overwrite: bool,
    write_shop_suggestions: Optional[Path],
) -> Dict[str, Any]:
    summary = {
        "written": [],
        "skipped_existing": [],
        "skipped_intentional": [],
        "shop_suggestions": [],
        "manual_review": [],
    }

    for record in records:
        if record.skip_reason:
            summary["skipped_intentional"].append(
                {
                    "bucket": record.bucket,
                    "item_id": record.item_id,
                    "name": record.source_name,
                    "reason": record.skip_reason,
                }
            )
            continue

        output_path = item_output_path(items_dir, record)
        if output_path.exists() and not overwrite:
            summary["skipped_existing"].append(
                {
                    "bucket": record.bucket,
                    "item_id": record.item_id,
                    "name": record.source_name,
                    "path": str(output_path),
                }
            )
            continue

        write_yaml(output_path, record.payload)
        summary["written"].append(
            {
                "bucket": record.bucket,
                "item_id": record.item_id,
                "name": record.source_name,
                "path": str(output_path),
            }
        )

        if record.notes:
            summary["manual_review"].append(
                {
                    "bucket": record.bucket,
                    "item_id": record.item_id,
                    "name": record.source_name,
                    "notes": list(record.notes),
                }
            )

        if write_shop_suggestions is not None:
            summary["shop_suggestions"].append(build_shop_suggestion(record))

    if write_shop_suggestions is not None:
        payload = {
            "format_version": 1,
            "entries": sorted(
                summary["shop_suggestions"],
                key=lambda row: (str(row.get("item_bucket") or ""), str(row.get("item_id") or "")),
            ),
        }
        write_yaml(write_shop_suggestions, payload)

    summary["counts"] = {
        "written": len(summary["written"]),
        "skipped_existing": len(summary["skipped_existing"]),
        "skipped_intentional": len(summary["skipped_intentional"]),
        "manual_review": len(summary["manual_review"]),
    }
    return summary


def build_report_payload(*, summary: Dict[str, Any], errors: List[Dict[str, Any]], base_url: str) -> Dict[str, Any]:
    return {
        "format_version": 1,
        "importer": {
            "name": "import_srd_items.py",
            "source": "dnd5eapi-2014",
            "base_url": base_url,
        },
        "counts": dict(summary.get("counts") or {}),
        "written": summary.get("written") or [],
        "skipped_existing": summary.get("skipped_existing") or [],
        "skipped_intentional": summary.get("skipped_intentional") or [],
        "manual_review": summary.get("manual_review") or [],
        "errors": errors,
    }


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Import open SRD item data into this repo's item YAML folders.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent(
            """\
            Examples:
              python scripts/migration/import_srd_items.py
              python scripts/migration/import_srd_items.py --include-weapons
              python scripts/migration/import_srd_items.py --overwrite --write-shop-suggestions Items/Shop/import_suggestions.yaml
            """
        ),
    )
    parser.add_argument("--items-dir", default="Items", help="Repo Items directory to write into. Default: %(default)s")
    parser.add_argument(
        "--base-url",
        default=DEFAULT_API_BASE_URL,
        help="Base API URL for the source adapter. Default: %(default)s",
    )
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS, help="HTTP timeout in seconds.")
    parser.add_argument(
        "--include-weapons",
        action="store_true",
        help="Import weapon definitions too. Off by default to avoid clobbering the existing curated weapon set.",
    )
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing YAML files instead of skipping them.")
    parser.add_argument(
        "--write-shop-suggestions",
        default="",
        help="Optional path for a generated shop overlay suggestion YAML file.",
    )
    parser.add_argument(
        "--write-report",
        default="items_import_report.yaml",
        help="Write a YAML import report to this path. Default: %(default)s",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_argument_parser()
    args = parser.parse_args(argv)

    items_dir = Path(args.items_dir).resolve()
    report_path = Path(args.write_report).resolve()
    shop_suggestions_path = Path(args.write_shop_suggestions).resolve() if str(args.write_shop_suggestions).strip() else None

    if not items_dir.exists():
        parser.error(f"Items directory does not exist: {items_dir}")

    try:
        records, errors = collect_records(
            base_url=str(args.base_url),
            timeout=max(1, int(args.timeout or DEFAULT_TIMEOUT_SECONDS)),
            include_weapons=bool(args.include_weapons),
        )
    except HTTPError as exc:
        print(f"Import failed: HTTP error {exc.code} while fetching source data: {exc}", file=sys.stderr)
        return 2
    except URLError as exc:
        print(f"Import failed: could not reach source data: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"Import failed: {exc}", file=sys.stderr)
        return 2

    summary = apply_import(
        items_dir=items_dir,
        records=records,
        overwrite=bool(args.overwrite),
        write_shop_suggestions=shop_suggestions_path,
    )
    report_payload = build_report_payload(summary=summary, errors=errors, base_url=str(args.base_url))
    write_yaml(report_path, report_payload)

    counts = report_payload.get("counts") or {}
    print(
        "Import complete: "
        f"{counts.get('written', 0)} written, "
        f"{counts.get('skipped_existing', 0)} skipped existing, "
        f"{counts.get('skipped_intentional', 0)} skipped by flags, "
        f"{counts.get('manual_review', 0)} flagged for manual review."
    )
    print(f"Report written to {report_path}")
    if shop_suggestions_path is not None:
        print(f"Shop suggestions written to {shop_suggestions_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
