from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

COMPOSITE_SHIP_SCHEMA = "composite_ship_blueprint_v1"


class CompositeShipBlueprintError(ValueError):
    pass


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _normalize_tags(raw: Any) -> List[str]:
    return sorted({str(item).strip().lower() for item in (raw if isinstance(raw, list) else []) if str(item).strip()})


def _normalize_cells(raw: Any) -> List[Dict[str, int]]:
    cells = set()
    for cell in raw if isinstance(raw, list) else []:
        if not isinstance(cell, dict):
            continue
        if cell.get("col") is None or cell.get("row") is None:
            continue
        cells.add((_as_int(cell.get("col")), _as_int(cell.get("row"))))
    return [{"col": col, "row": row} for col, row in sorted(cells)]


def _normalize_local_entities(raw: Any, *, prefix: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for index, item in enumerate(raw if isinstance(raw, list) else []):
        if not isinstance(item, dict):
            continue
        ident = str(item.get("id") or f"{prefix}_{index + 1}").strip().lower() or f"{prefix}_{index + 1}"
        out_item: Dict[str, Any] = {
            "id": ident,
            "name": str(item.get("name") or ident.replace("_", " ").title()).strip() or ident,
            "kind": str(item.get("kind") or item.get("type") or prefix.rstrip("s")).strip().lower() or prefix.rstrip("s"),
            "col": _as_int(item.get("col")),
            "row": _as_int(item.get("row")),
        }
        tags = _normalize_tags(item.get("tags"))
        if tags:
            out_item["tags"] = tags
        for key in ("max_hp", "ac", "damage_threshold", "range", "ammo", "to_hit", "damage"):
            if item.get(key) is not None:
                out_item[key] = _as_int(item.get(key))
        if item.get("weapon_type") is not None:
            out_item["weapon_type"] = str(item.get("weapon_type")).strip().lower()
        if item.get("arc") is not None:
            out_item["arc"] = str(item.get("arc")).strip().lower()
        out.append(out_item)
    out.sort(key=lambda entry: (int(entry.get("col", 0)), int(entry.get("row", 0)), str(entry.get("id") or "")))
    return out


def normalize_composite_ship_blueprint(payload: Any, *, source: str = "") -> Tuple[Dict[str, Any], List[str]]:
    data = dict(payload) if isinstance(payload, dict) else {}
    errors: List[str] = []
    schema = str(data.get("schema") or COMPOSITE_SHIP_SCHEMA).strip()
    if schema != COMPOSITE_SHIP_SCHEMA:
        errors.append("unsupported_schema")
    blueprint_id = str(data.get("id") or "").strip().lower()
    if not blueprint_id:
        errors.append("missing_id")
        blueprint_id = "ship"
    local_space = dict(data.get("local_space") if isinstance(data.get("local_space"), dict) else {})
    hull_cells = _normalize_cells(local_space.get("hull_cells"))
    if not hull_cells:
        hull_cells = [{"col": 0, "row": 0}]
        errors.append("missing_hull_cells")
    render_anchor_raw = local_space.get("render_anchor") if isinstance(local_space.get("render_anchor"), dict) else {}
    render_anchor = {"col": _as_int(render_anchor_raw.get("col")), "row": _as_int(render_anchor_raw.get("row"))}
    fixtures = _normalize_local_entities(data.get("fixtures"), prefix="fixture")
    components = _normalize_local_entities(data.get("components"), prefix="component")
    weapon_hardpoints = _normalize_local_entities(data.get("weapon_hardpoints"), prefix="hardpoint")
    for item in weapon_hardpoints:
        item["weapon_type"] = str(item.get("weapon_type") or item.get("kind") or "weapon").strip().lower() or "weapon"
        item["arc"] = str(item.get("arc") or "broadside").strip().lower() or "broadside"
    boarding_raw = dict(data.get("boarding") if isinstance(data.get("boarding"), dict) else {})
    boarding_points = _normalize_local_entities(boarding_raw.get("points"), prefix="point")
    boarding_edges = _normalize_tags(boarding_raw.get("edges"))
    if not boarding_edges:
        boarding_edges = ["port", "starboard"]
    render = dict(data.get("render") if isinstance(data.get("render"), dict) else {})
    engagement_defaults = dict(data.get("engagement_defaults") if isinstance(data.get("engagement_defaults"), dict) else {})
    crew = dict(engagement_defaults.get("crew") if isinstance(engagement_defaults.get("crew"), dict) else {})
    normalized = {
        "schema": COMPOSITE_SHIP_SCHEMA,
        "id": blueprint_id,
        "display_name": str(data.get("display_name") or data.get("name") or blueprint_id.replace("_", " ").title()).strip() or blueprint_id,
        "kind": str(data.get("kind") or "ship_hull").strip() or "ship_hull",
        "category": str(data.get("category") or "ship").strip().lower() or "ship",
        "size": str(data.get("size") or "medium").strip().lower() or "medium",
        "local_space": {
            "render_anchor": render_anchor,
            "facing_mode": str(local_space.get("facing_mode") or "rotate_90").strip().lower() or "rotate_90",
            "hull_cells": hull_cells,
        },
        "fixtures": fixtures,
        "components": components,
        "weapon_hardpoints": weapon_hardpoints,
        "boarding": {
            "boardable": bool(boarding_raw.get("boardable", True)),
            "edges": boarding_edges,
            "points": boarding_points,
            "contact_tags": _normalize_tags(boarding_raw.get("contact_tags")),
            "bridges": [dict(item) for item in (boarding_raw.get("bridges") if isinstance(boarding_raw.get("bridges"), list) else []) if isinstance(item, dict)],
        },
        "render": {
            "style": str(render.get("style") or "polygon").strip().lower() or "polygon",
            "base_image_key": str(render.get("base_image_key") or "").strip(),
            "overlay_hints": _normalize_tags(render.get("overlay_hints")),
            "preview": dict(render.get("preview") if isinstance(render.get("preview"), dict) else {}),
        },
        "engagement_defaults": {
            "crew": {
                "min_crew": max(0, _as_int(crew.get("min_crew"), _as_int(data.get("crew_min"), 0))),
                "recommended_crew": max(0, _as_int(crew.get("recommended_crew"), _as_int(data.get("crew_recommended"), 0))),
            }
        },
    }
    hull_set = {(int(cell["col"]), int(cell["row"])) for cell in hull_cells}
    if (int(render_anchor["col"]), int(render_anchor["row"])) not in hull_set:
        errors.append("render_anchor_not_in_hull")
    for section_name in ("fixtures", "components", "weapon_hardpoints"):
        for item in normalized.get(section_name, []):
            if (int(item.get("col", 0)), int(item.get("row", 0))) not in hull_set:
                errors.append(f"{section_name[:-1]}_outside_hull:{item.get('id')}")
    for point in normalized["boarding"]["points"]:
        if (int(point.get("col", 0)), int(point.get("row", 0))) not in hull_set:
            errors.append(f"boarding_point_outside_hull:{point.get('id')}")
    if source:
        normalized["source"] = source
    return normalized, sorted(set(errors))


def runtime_blueprint_from_composite(normalized: Dict[str, Any]) -> Dict[str, Any]:
    local_space = normalized.get("local_space") if isinstance(normalized.get("local_space"), dict) else {}
    boarding = normalized.get("boarding") if isinstance(normalized.get("boarding"), dict) else {}
    crew = ((normalized.get("engagement_defaults") if isinstance(normalized.get("engagement_defaults"), dict) else {}).get("crew") if isinstance((normalized.get("engagement_defaults") if isinstance(normalized.get("engagement_defaults"), dict) else {}).get("crew"), dict) else {})
    return {
        "id": str(normalized.get("id") or "").strip().lower(),
        "name": str(normalized.get("display_name") or "Ship").strip() or "Ship",
        "kind": str(normalized.get("kind") or "ship_hull"),
        "category": str(normalized.get("category") or "ship"),
        "size": str(normalized.get("size") or "medium"),
        "default_facing_deg": 0.0,
        "footprint": [dict(item) for item in (local_space.get("hull_cells") if isinstance(local_space.get("hull_cells"), list) else []) if isinstance(item, dict)],
        "fixtures": [dict(item) for item in (normalized.get("fixtures") if isinstance(normalized.get("fixtures"), list) else []) if isinstance(item, dict)],
        "components": [dict(item) for item in (normalized.get("components") if isinstance(normalized.get("components"), list) else []) if isinstance(item, dict)],
        "mounted_weapons": [dict(item) for item in (normalized.get("weapon_hardpoints") if isinstance(normalized.get("weapon_hardpoints"), list) else []) if isinstance(item, dict)],
        "boarding": {
            "boardable": bool(boarding.get("boardable", True)),
            "edges": list(boarding.get("edges") if isinstance(boarding.get("edges"), list) else []),
            "points": [dict(item) for item in (boarding.get("points") if isinstance(boarding.get("points"), list) else []) if isinstance(item, dict)],
            "bridges": [dict(item) for item in (boarding.get("bridges") if isinstance(boarding.get("bridges"), list) else []) if isinstance(item, dict)],
            "contact_tags": list(boarding.get("contact_tags") if isinstance(boarding.get("contact_tags"), list) else []),
        },
        "crew": {
            "min_crew": _as_int(crew.get("min_crew"), 0),
            "recommended_crew": _as_int(crew.get("recommended_crew"), 0),
        },
        "render": dict(normalized.get("render") if isinstance(normalized.get("render"), dict) else {}),
        "local_space": {
            "render_anchor": dict(local_space.get("render_anchor") if isinstance(local_space.get("render_anchor"), dict) else {"col": 0, "row": 0}),
            "facing_mode": str(local_space.get("facing_mode") or "rotate_90"),
            "hull_cells": [dict(item) for item in (local_space.get("hull_cells") if isinstance(local_space.get("hull_cells"), list) else []) if isinstance(item, dict)],
        },
    }


def load_composite_ship_blueprints_from_dir(path: Path) -> Tuple[Dict[str, Dict[str, Any]], List[str]]:
    blueprints: Dict[str, Dict[str, Any]] = {}
    errors: List[str] = []
    if not path.exists():
        return blueprints, [f"missing_directory:{path}"]
    for file_path in sorted(path.glob("*.json")):
        try:
            payload = json.loads(file_path.read_text(encoding="utf-8"))
        except Exception as exc:
            errors.append(f"{file_path.name}:invalid_json:{exc}")
            continue
        normalized, normalized_errors = normalize_composite_ship_blueprint(payload, source=file_path.name)
        if normalized_errors:
            errors.extend([f"{file_path.name}:{entry}" for entry in normalized_errors])
            continue
        blueprint_id = str(normalized.get("id") or "").strip().lower()
        if blueprint_id:
            blueprints[blueprint_id] = normalized
    return blueprints, errors


def load_repo_runtime_ship_blueprints(repo_root: Optional[Path] = None) -> Tuple[Dict[str, Dict[str, Any]], List[str]]:
    root = Path(repo_root) if repo_root is not None else Path(__file__).resolve().parent
    blueprint_dir = root / "assets" / "ships" / "blueprints"
    normalized, errors = load_composite_ship_blueprints_from_dir(blueprint_dir)
    runtime = {blueprint_id: runtime_blueprint_from_composite(payload) for blueprint_id, payload in normalized.items()}
    return runtime, errors


def import_tiled_ship_blueprint(tiled_payload: Any, *, blueprint_id: Optional[str] = None) -> Dict[str, Any]:
    data = dict(tiled_payload) if isinstance(tiled_payload, dict) else {}
    width = _as_int(data.get("width"), 0)
    height = _as_int(data.get("height"), 0)
    if width <= 0 or height <= 0:
        raise CompositeShipBlueprintError("missing_map_dimensions")
    ship = dict(data.get("ship") if isinstance(data.get("ship"), dict) else {})
    bid = str(blueprint_id or ship.get("id") or data.get("id") or "").strip().lower()
    if not bid:
        raise CompositeShipBlueprintError("missing_ship_id")
    layers = {str(layer.get("name") or "").strip().lower(): layer for layer in (data.get("layers") if isinstance(data.get("layers"), list) else []) if isinstance(layer, dict)}
    hull_layer = layers.get("hull")
    if not isinstance(hull_layer, dict):
        raise CompositeShipBlueprintError("missing_hull_layer")
    hull_cells = _normalize_cells(hull_layer.get("cells"))
    if not hull_cells:
        data_values = hull_layer.get("data")
        if isinstance(data_values, list) and len(data_values) == width * height:
            for index, tile in enumerate(data_values):
                if _as_int(tile, 0) > 0:
                    hull_cells.append({"col": int(index % width), "row": int(index // width)})
    hull_cells = _normalize_cells(hull_cells)
    if not hull_cells:
        raise CompositeShipBlueprintError("empty_hull")

    def _objects(layer_name: str) -> List[Dict[str, Any]]:
        layer = layers.get(layer_name)
        if not isinstance(layer, dict):
            return []
        return _normalize_local_entities(layer.get("objects"), prefix=layer_name.rstrip("s"))

    payload = {
        "schema": COMPOSITE_SHIP_SCHEMA,
        "id": bid,
        "display_name": str(ship.get("display_name") or ship.get("name") or bid.replace("_", " ").title()),
        "kind": str(ship.get("kind") or "ship_hull"),
        "category": str(ship.get("category") or "ship"),
        "size": str(ship.get("size") or "medium"),
        "local_space": {
            "render_anchor": dict(ship.get("render_anchor") if isinstance(ship.get("render_anchor"), dict) else {"col": 0, "row": 0}),
            "facing_mode": str(ship.get("facing_mode") or "rotate_90"),
            "hull_cells": hull_cells,
        },
        "fixtures": _objects("fixtures"),
        "components": _objects("components"),
        "weapon_hardpoints": _objects("weapon_hardpoints"),
        "boarding": {
            "boardable": bool(ship.get("boardable", True)),
            "edges": list(ship.get("boarding_edges") if isinstance(ship.get("boarding_edges"), list) else ["port", "starboard", "fore", "aft"]),
            "points": _objects("boarding_points"),
            "contact_tags": _normalize_tags(ship.get("contact_tags")),
            "bridges": [dict(item) for item in (ship.get("bridges") if isinstance(ship.get("bridges"), list) else []) if isinstance(item, dict)],
        },
        "render": dict(ship.get("render") if isinstance(ship.get("render"), dict) else {"style": "polygon"}),
        "engagement_defaults": {"crew": dict(ship.get("crew") if isinstance(ship.get("crew"), dict) else {})},
    }
    normalized, errors = normalize_composite_ship_blueprint(payload)
    if errors:
        raise CompositeShipBlueprintError(",".join(errors))
    return normalized


def import_tiled_json_file(source_path: Path, *, blueprint_id: Optional[str] = None) -> Dict[str, Any]:
    return import_tiled_ship_blueprint(json.loads(source_path.read_text(encoding="utf-8")), blueprint_id=blueprint_id)


def export_normalized_blueprint(destination_path: Path, payload: Dict[str, Any]) -> None:
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    destination_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
