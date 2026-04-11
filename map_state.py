from __future__ import annotations

import copy
import math
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple


MAP_STATE_SCHEMA_VERSION = 1
INFINITE_MOVEMENT_COST = 10**9
CellKey = Tuple[int, int]


def _normalize_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _normalize_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _cell_key_to_string(key: CellKey) -> str:
    return f"{int(key[0])},{int(key[1])}"


def _string_to_cell_key(raw: Any) -> Optional[CellKey]:
    if isinstance(raw, str):
        parts = [part.strip() for part in raw.split(",")]
        if len(parts) != 2:
            return None
        try:
            return (int(parts[0]), int(parts[1]))
        except Exception:
            return None
    if isinstance(raw, (list, tuple)) and len(raw) == 2:
        try:
            return (int(raw[0]), int(raw[1]))
        except Exception:
            return None
    return None


def _normalize_cell_list(raw_cells: Any) -> List[CellKey]:
    cells: List[CellKey] = []
    for raw in raw_cells if isinstance(raw_cells, list) else []:
        key = None
        if isinstance(raw, dict):
            key = (_normalize_int(raw.get("col")), _normalize_int(raw.get("row")))
        else:
            key = _string_to_cell_key(raw)
        if key is None:
            continue
        cells.append((int(key[0]), int(key[1])))
    return cells


def _entity_cells(col: int, row: int, payload: Any) -> List[CellKey]:
    base = (int(col), int(row))
    if not isinstance(payload, dict):
        return [base]
    cells = _normalize_cell_list(payload.get("occupied_cells"))
    if cells:
        return cells
    footprint = _normalize_cell_list(payload.get("footprint"))
    if footprint:
        return footprint
    return [base]


def _merge_tags(default_tags: Any, existing_tags: Any) -> List[str]:
    merged: List[str] = []
    seen = set()
    for source in (default_tags, existing_tags):
        for raw in source if isinstance(source, list) else []:
            text = str(raw or "").strip().lower()
            if not text or text in seen:
                continue
            merged.append(text)
            seen.add(text)
    return merged


BOARDING_LINK_STATUSES = {"available", "prepared", "active", "broken", "blocked", "withdrawn"}
BOARDING_LINK_TRAVERSABLE_STATUSES = {"prepared", "active"}


def _normalize_boarding_status(value: Any, default: str = "active") -> str:
    status = str(value or "").strip().lower()
    if status in BOARDING_LINK_STATUSES:
        return status
    return default


def _normalize_boarding_point(raw: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(raw, dict):
        return None
    if raw.get("col") is None or raw.get("row") is None:
        return None
    try:
        col = int(raw.get("col"))
        row = int(raw.get("row"))
    except Exception:
        return None
    payload: Dict[str, Any] = {"col": col, "row": row}
    point_id = str(raw.get("id") or "").strip()
    if point_id:
        payload["id"] = point_id
    point_name = str(raw.get("name") or "").strip()
    if point_name:
        payload["name"] = point_name
    tags = [str(tag).strip().lower() for tag in (raw.get("tags") if isinstance(raw.get("tags"), list) else []) if str(tag).strip()]
    if tags:
        payload["tags"] = tags
    return payload


TACTICAL_PRESET_STACK_RULES: Dict[str, Dict[str, Any]] = {
    "barrel": {
        "light": {"max_count": 1, "blocks_movement": False, "cover": "none", "is_difficult_terrain": False},
        "medium": {"max_count": 3, "blocks_movement": False, "cover": "half", "is_difficult_terrain": True},
        "dense": {"max_count": None, "blocks_movement": True, "cover": "three_quarters", "is_difficult_terrain": True},
    },
    "crate_stack": {
        "light": {"max_count": 1, "blocks_movement": False, "cover": "half", "is_difficult_terrain": False},
        "medium": {"max_count": 3, "blocks_movement": True, "cover": "three_quarters", "is_difficult_terrain": True},
        "dense": {"max_count": None, "blocks_movement": True, "cover": "full", "is_difficult_terrain": True},
    },
    "debris": {
        "light": {"max_count": 1, "blocks_movement": False, "cover": "none", "is_difficult_terrain": True},
        "medium": {"max_count": 3, "blocks_movement": False, "cover": "half", "is_difficult_terrain": True},
        "dense": {"max_count": None, "blocks_movement": True, "cover": "half", "is_difficult_terrain": True},
    },
    "difficult_patch": {
        "light": {"max_count": 1, "blocks_movement": False, "cover": "none", "is_difficult_terrain": True},
        "medium": {"max_count": 3, "blocks_movement": False, "cover": "none", "is_difficult_terrain": True},
        "dense": {"max_count": None, "blocks_movement": True, "cover": "half", "is_difficult_terrain": True},
    },
}


TACTICAL_PRESET_CATALOG: Dict[str, Dict[str, Any]] = {
    "barrel": {
        "id": "barrel",
        "display_name": "Barrel",
        "family": "Clutter / Props",
        "category": "feature",
        "kind": "barrel",
        "stackable": True,
        "default_count": 1,
        "payload": {
            "name": "Barrel",
            "tags": ["prop", "barrel", "cover"],
            "blocks_movement": False,
            "cover": "none",
            "destructible": True,
            "flammable": True,
            "hp": 8,
            "ac": 11,
            "damage_threshold": 0,
            "on_destroy_spawn_hazard": {"kind": "fire", "payload": {"duration_turns": 2, "remaining_turns": 2, "tags": ["fire", "environment"]}},
        },
    },
    "powder_barrel": {
        "id": "powder_barrel",
        "display_name": "Powder Barrel",
        "family": "Clutter / Props",
        "category": "feature",
        "kind": "powder_barrel",
        "payload": {
            "name": "Powder Barrel",
            "tags": ["prop", "powder", "explosive", "flammable"],
            "blocks_movement": False,
            "destructible": True,
            "flammable": True,
            "explosive": True,
            "hp": 6,
            "ac": 11,
            "damage_threshold": 0,
            "on_ignite_spawn_hazard": {"kind": "fire", "payload": {"duration_turns": 3, "remaining_turns": 3, "tags": ["fire", "environment"], "movement_multiplier": 2.0}},
            "on_destroy_spawn_hazard": {"kind": "fire", "payload": {"duration_turns": 4, "remaining_turns": 4, "tags": ["fire", "explosion", "environment"], "movement_multiplier": 2.0, "blocks_movement": True}},
        },
    },
    "crate_stack": {
        "id": "crate_stack",
        "display_name": "Crate Stack",
        "family": "Clutter / Props",
        "category": "feature",
        "kind": "crate",
        "stackable": True,
        "default_count": 2,
        "payload": {
            "name": "Crate Stack",
            "tags": ["prop", "crate", "cover"],
            "blocks_movement": True,
            "cover": "half",
            "destructible": True,
            "flammable": True,
            "hp": 15,
            "ac": 12,
            "damage_threshold": 0,
        },
    },
    "debris": {
        "id": "debris",
        "display_name": "Difficult Debris",
        "family": "Clutter / Props",
        "category": "feature",
        "kind": "difficult_terrain",
        "stackable": True,
        "default_count": 2,
        "payload": {
            "name": "Debris",
            "tags": ["debris", "difficult_terrain"],
            "blocks_movement": False,
            "is_difficult_terrain": True,
            "cover": "none",
        },
    },
    "cannon": {
        "id": "cannon",
        "display_name": "Cannon",
        "family": "Ship Fixtures",
        "category": "feature",
        "kind": "cannon",
        "payload": {
            "name": "Cannon",
            "tags": ["weapon", "siege", "ship_fixture", "cover"],
            "blocks_movement": True,
            "cover": "half",
            "destructible": True,
            "hp": 22,
            "ac": 19,
            "damage_threshold": 5,
        },
    },
    "ballista": {
        "id": "ballista",
        "display_name": "Ballista",
        "family": "Ship Fixtures",
        "category": "feature",
        "kind": "ballista",
        "payload": {
            "name": "Ballista",
            "tags": ["weapon", "siege", "ship_fixture"],
            "blocks_movement": True,
            "cover": "half",
            "destructible": True,
            "hp": 20,
            "ac": 15,
            "damage_threshold": 3,
        },
    },
    "railing": {
        "id": "railing",
        "display_name": "Railing",
        "family": "Ship Fixtures",
        "category": "feature",
        "kind": "railing",
        "payload": {
            "name": "Railing",
            "tags": ["ship_fixture", "cover", "railing"],
            "blocks_movement": False,
            "cover": "half",
            "destructible": True,
            "hp": 10,
            "ac": 13,
        },
    },
    "hatch": {
        "id": "hatch",
        "display_name": "Hatch",
        "family": "Ship Fixtures",
        "category": "feature",
        "kind": "hatch",
        "payload": {
            "name": "Hatch",
            "tags": ["ship_fixture", "hatch", "traversal"],
            "blocks_movement": False,
            "destructible": True,
            "hp": 12,
            "ac": 13,
        },
    },
    "ladder": {
        "id": "ladder",
        "display_name": "Ladder",
        "family": "Ship Fixtures",
        "category": "feature",
        "kind": "ladder",
        "payload": {
            "name": "Ladder",
            "tags": ["ship_fixture", "ladder", "climbable", "traversal"],
            "blocks_movement": False,
            "destructible": True,
            "hp": 8,
            "ac": 12,
            "max_climb_delta": 20,
        },
    },
    "mast": {
        "id": "mast",
        "display_name": "Mast",
        "family": "Ship Fixtures",
        "category": "feature",
        "kind": "mast",
        "payload": {
            "name": "Mast",
            "tags": ["ship_fixture", "mast", "climbable", "requires_climb_transition"],
            "blocks_movement": True,
            "cover": "half",
            "destructible": True,
            "flammable": True,
            "hp": 30,
            "ac": 15,
            "damage_threshold": 5,
            "max_climb_delta": 25,
        },
    },
    "stairs": {
        "id": "stairs",
        "display_name": "Stairs",
        "family": "Ship Fixtures",
        "category": "feature",
        "kind": "stairs",
        "payload": {
            "name": "Stairs",
            "tags": ["ship_fixture", "stairs", "climbable", "traversal"],
            "blocks_movement": False,
            "max_climb_delta": 15,
        },
    },
    "gangplank": {
        "id": "gangplank",
        "display_name": "Gangplank",
        "family": "Ship Fixtures",
        "category": "feature",
        "kind": "gangplank",
        "payload": {
            "name": "Gangplank",
            "tags": ["ship_fixture", "gangplank", "bridge", "boarding_bridge", "traversal"],
            "blocks_movement": False,
            "destructible": True,
            "hp": 16,
            "ac": 12,
            "cover": "none",
            "max_climb_delta": 10,
        },
    },
    "door": {
        "id": "door",
        "display_name": "Door",
        "family": "Ship Fixtures",
        "category": "feature",
        "kind": "door",
        "payload": {
            "name": "Door",
            "tags": ["ship_fixture", "door"],
            "blocks_movement": True,
            "destructible": True,
            "hp": 18,
            "ac": 15,
            "damage_threshold": 3,
        },
    },
    "fire": {
        "id": "fire",
        "display_name": "Fire Patch",
        "family": "Hazards / Effects",
        "category": "hazard",
        "kind": "fire",
        "payload": {
            "name": "Fire",
            "tags": ["fire", "environment", "hazard"],
            "duration_turns": 3,
            "remaining_turns": 3,
            "movement_multiplier": 2.0,
            "blocks_movement": False,
        },
    },
    "smoke": {
        "id": "smoke",
        "display_name": "Smoke Patch",
        "family": "Hazards / Effects",
        "category": "hazard",
        "kind": "smoke",
        "payload": {
            "name": "Smoke",
            "tags": ["smoke", "obscurement", "hazard"],
            "duration_turns": 3,
            "remaining_turns": 3,
            "movement_multiplier": 1.0,
            "blocks_movement": False,
            "cover": "half",
        },
    },
    "oil": {
        "id": "oil",
        "display_name": "Oil / Grease",
        "family": "Hazards / Effects",
        "category": "hazard",
        "kind": "grease",
        "payload": {
            "name": "Oil Slick",
            "tags": ["oil", "grease", "hazard", "flammable"],
            "duration_turns": 4,
            "remaining_turns": 4,
            "movement_multiplier": 2.0,
            "blocks_movement": False,
            "flammable": True,
        },
    },
    "burning_debris": {
        "id": "burning_debris",
        "display_name": "Burning Debris",
        "family": "Hazards / Effects",
        "category": "hazard",
        "kind": "burning_debris",
        "payload": {
            "name": "Burning Debris",
            "tags": ["fire", "debris", "hazard"],
            "duration_turns": 3,
            "remaining_turns": 3,
            "movement_multiplier": 2.0,
            "blocks_movement": True,
            "cover": "half",
        },
    },
    "dock_platform": {
        "id": "dock_platform",
        "display_name": "Dock Platform",
        "family": "Support / World",
        "category": "structure",
        "kind": "dock",
        "occupied_offsets": [{"col": 0, "row": 0}, {"col": 1, "row": 0}, {"col": 0, "row": 1}, {"col": 1, "row": 1}],
        "payload": {
            "name": "Dock Platform",
            "tags": ["dock", "platform", "boardable"],
            "blocks_movement": True,
            "boardable": True,
        },
    },
    "cover_obstacle": {
        "id": "cover_obstacle",
        "display_name": "Cover Obstacle",
        "family": "Support / World",
        "category": "feature",
        "kind": "cover_prop",
        "payload": {
            "name": "Cover Obstacle",
            "tags": ["cover", "obstacle"],
            "blocks_movement": False,
            "cover": "half",
            "destructible": True,
            "hp": 12,
            "ac": 12,
        },
    },
    "difficult_patch": {
        "id": "difficult_patch",
        "display_name": "Difficult Terrain Patch",
        "family": "Support / World",
        "category": "feature",
        "kind": "difficult_terrain",
        "stackable": True,
        "default_count": 2,
        "payload": {
            "name": "Difficult Terrain",
            "tags": ["difficult_terrain"],
            "blocks_movement": False,
            "is_difficult_terrain": True,
            "cover": "none",
        },
    },
    "brazier": {
        "id": "brazier",
        "display_name": "Brazier",
        "family": "Hazards / Effects",
        "category": "feature",
        "kind": "brazier",
        "payload": {
            "name": "Brazier",
            "tags": ["brazier", "fire_source", "flammable"],
            "blocks_movement": False,
            "destructible": True,
            "flammable": True,
            "hp": 10,
            "ac": 13,
            "on_destroy_spawn_hazard": {"kind": "fire", "payload": {"duration_turns": 2, "remaining_turns": 2, "tags": ["fire", "environment"]}},
        },
    },
}

TACTICAL_PRESET_ALIASES: Dict[str, str] = {
    "crate": "crate_stack",
    "blocking_prop": "cover_obstacle",
    "cover_prop": "cover_obstacle",
    "difficult_terrain": "difficult_patch",
    "magical_zone": "smoke",
    "blocked_zone": "cover_obstacle",
    "moving_platform": "dock_platform",
}


_TACTICAL_PRESET_LOADER: Optional[Callable[[], Dict[str, Dict[str, Any]]]] = None


def set_tactical_preset_loader(loader: Optional[Callable[[], Dict[str, Dict[str, Any]]]]) -> None:
    """Register an optional tactical preset loader for additive external definitions."""
    global _TACTICAL_PRESET_LOADER
    _TACTICAL_PRESET_LOADER = loader if callable(loader) else None


def _active_tactical_preset_catalog() -> Dict[str, Dict[str, Any]]:
    catalog: Dict[str, Dict[str, Any]] = copy.deepcopy(TACTICAL_PRESET_CATALOG)
    loader = _TACTICAL_PRESET_LOADER
    if not callable(loader):
        return catalog
    try:
        loaded = loader()
    except Exception:
        loaded = {}
    if not isinstance(loaded, dict):
        return catalog
    for raw_key, raw_value in loaded.items():
        preset = dict(raw_value) if isinstance(raw_value, dict) else {}
        preset_id = str(preset.get("id") or raw_key or "").strip().lower()
        if not preset_id:
            continue
        preset["id"] = preset_id
        if "display_name" not in preset:
            preset["display_name"] = preset_id.replace("_", " ").title()
        if "payload" in preset and not isinstance(preset.get("payload"), dict):
            preset["payload"] = {}
        catalog[preset_id] = preset
    return catalog


def tactical_preset_catalog() -> Dict[str, Dict[str, Any]]:
    return copy.deepcopy(_active_tactical_preset_catalog())


def tactical_preset_families() -> List[str]:
    families = {str(preset.get("family") or "Other") for preset in _active_tactical_preset_catalog().values()}
    return sorted(families)


def _stack_state_for_count(preset_id: str, count: int) -> Optional[str]:
    rules = TACTICAL_PRESET_STACK_RULES.get(str(preset_id))
    if not isinstance(rules, dict):
        return None
    normalized_count = max(1, int(count))
    for state in ("light", "medium", "dense"):
        limit = rules.get(state, {}).get("max_count") if isinstance(rules.get(state), dict) else None
        if limit is None:
            return state
        if normalized_count <= int(limit):
            return state
    return "dense"


def _resolve_preset_id(preset_id: Any = None, kind: Any = None) -> str:
    catalog = _active_tactical_preset_catalog()
    direct = str(preset_id or "").strip().lower()
    if direct in catalog:
        return direct
    kind_key = str(kind or "").strip().lower()
    if kind_key in catalog:
        return kind_key
    if kind_key in TACTICAL_PRESET_ALIASES:
        mapped = str(TACTICAL_PRESET_ALIASES.get(kind_key) or "").strip().lower()
        if mapped in catalog:
            return mapped
    return ""


def normalize_tactical_payload(
    *,
    category: Any,
    kind: Any,
    payload: Any = None,
    preset_id: Any = None,
    count: Any = None,
) -> Dict[str, Any]:
    catalog = _active_tactical_preset_catalog()
    category_key = str(category or "").strip().lower() or "feature"
    kind_key = str(kind or "").strip().lower() or category_key
    payload_dict = dict(payload if isinstance(payload, dict) else {})
    resolved_preset_id = _resolve_preset_id(preset_id=preset_id, kind=kind_key)
    if not resolved_preset_id:
        if "name" not in payload_dict and kind_key:
            payload_dict["name"] = kind_key
        return {
            "preset_id": "",
            "display_name": str(payload_dict.get("name") or kind_key),
            "category": category_key,
            "kind": kind_key,
            "payload": payload_dict,
            "occupied_offsets": [],
        }
    preset = catalog.get(resolved_preset_id, {})
    preset_payload = dict(preset.get("payload") if isinstance(preset.get("payload"), dict) else {})
    merged = {**preset_payload, **payload_dict}
    merged["tags"] = _merge_tags(preset_payload.get("tags"), payload_dict.get("tags"))
    display_name = str(payload_dict.get("name") or preset.get("display_name") or kind_key or "Object")
    merged["name"] = display_name
    merged["tactical_preset_id"] = resolved_preset_id
    merged["display_name"] = display_name
    if merged.get("duration_turns") is not None and payload_dict.get("remaining_turns") is None:
        try:
            merged["remaining_turns"] = int(merged.get("duration_turns"))
        except Exception:
            pass

    stackable = bool(preset.get("stackable"))
    if stackable:
        fallback_count = int(preset.get("default_count", 1) or 1)
        try:
            normalized_count = int(count if count is not None else merged.get("count", fallback_count))
        except Exception:
            normalized_count = fallback_count
        normalized_count = max(1, normalized_count)
        merged["count"] = normalized_count
        stack_state = _stack_state_for_count(resolved_preset_id, normalized_count) or "light"
        merged["stack_state"] = stack_state
        rules = TACTICAL_PRESET_STACK_RULES.get(resolved_preset_id, {})
        state_rules = rules.get(stack_state) if isinstance(rules, dict) else {}
        if isinstance(state_rules, dict):
            merged.update({key: value for key, value in state_rules.items() if key in {"blocks_movement", "cover", "is_difficult_terrain"}})
        merged["tags"] = _merge_tags(merged.get("tags"), [f"stack_{stack_state}"])
    else:
        merged.pop("stack_state", None)
        if "count" in merged:
            try:
                merged["count"] = max(1, int(merged.get("count", 1)))
            except Exception:
                merged.pop("count", None)

    normalized_category = str(preset.get("category") or category_key).strip().lower() or category_key
    occupied_offsets = _normalize_cell_list(preset.get("occupied_offsets"))
    normalized_kind = str(preset.get("kind") or kind_key).strip().lower() or kind_key
    return {
        "preset_id": resolved_preset_id,
        "display_name": display_name,
        "category": normalized_category,
        "kind": normalized_kind,
        "payload": merged,
        "occupied_offsets": [{"col": int(col), "row": int(row)} for col, row in occupied_offsets],
    }


def tactical_preset_author_summary(preset_id: Any, count: Any = None) -> str:
    catalog = _active_tactical_preset_catalog()
    resolved = _resolve_preset_id(preset_id=preset_id, kind="")
    if not resolved:
        return "Custom tactical object"
    preset = catalog.get(resolved, {})
    normalized = normalize_tactical_payload(
        category=preset.get("category"),
        kind=preset.get("kind"),
        payload={},
        preset_id=resolved,
        count=count,
    )
    payload = normalized.get("payload") if isinstance(normalized.get("payload"), dict) else {}
    parts = [
        str(preset.get("display_name") or resolved),
        f"as {str(normalized.get('category') or 'feature')}",
    ]
    if payload.get("count") is not None:
        parts.append(f"x{int(payload.get('count') or 1)} ({str(payload.get('stack_state') or 'light')})")
    if payload.get("cover"):
        parts.append(f"cover={payload.get('cover')}")
    if payload.get("blocks_movement"):
        parts.append("blocking")
    if payload.get("destructible"):
        hp = payload.get("hp")
        ac = payload.get("ac")
        if hp is not None and ac is not None:
            parts.append(f"HP {hp}/AC {ac}")
        else:
            parts.append("destructible")
    return " · ".join(parts)


@dataclass
class GridSpec:
    cols: int = 20
    rows: int = 20
    feet_per_square: float = 5.0

    def normalized(self) -> "GridSpec":
        cols = max(1, _normalize_int(self.cols, 20))
        rows = max(1, _normalize_int(self.rows, 20))
        feet = _normalize_float(self.feet_per_square, 5.0)
        if feet <= 0:
            feet = 5.0
        return GridSpec(cols=cols, rows=rows, feet_per_square=feet)

    def to_dict(self) -> Dict[str, Any]:
        data = self.normalized()
        return {
            "cols": int(data.cols),
            "rows": int(data.rows),
            "feet_per_square": float(data.feet_per_square),
        }

    @classmethod
    def from_dict(cls, payload: Any) -> "GridSpec":
        src = payload if isinstance(payload, dict) else {}
        return cls(
            cols=_normalize_int(src.get("cols"), 20),
            rows=_normalize_int(src.get("rows"), 20),
            feet_per_square=_normalize_float(src.get("feet_per_square"), 5.0),
        ).normalized()


@dataclass
class TerrainCell:
    col: int
    row: int
    color: str = "#8d6e63"
    label: str = ""
    movement_type: str = "ground"
    is_swim: bool = False
    is_rough: bool = True

    def normalized(self) -> "TerrainCell":
        movement = str(self.movement_type or "").strip().lower()
        if movement not in ("ground", "water"):
            movement = "water" if bool(self.is_swim) else "ground"
        return TerrainCell(
            col=_normalize_int(self.col),
            row=_normalize_int(self.row),
            color=str(self.color or "#8d6e63"),
            label=str(self.label or ""),
            movement_type=movement,
            is_swim=(movement == "water"),
            is_rough=bool(self.is_rough),
        )

    @property
    def key(self) -> CellKey:
        return (int(self.col), int(self.row))

    def to_dict(self) -> Dict[str, Any]:
        cell = self.normalized()
        return {
            "col": int(cell.col),
            "row": int(cell.row),
            "color": str(cell.color),
            "label": str(cell.label),
            "movement_type": str(cell.movement_type),
            "is_swim": bool(cell.is_swim),
            "is_rough": bool(cell.is_rough),
        }

    @classmethod
    def from_dict(cls, payload: Any) -> "TerrainCell":
        src = payload if isinstance(payload, dict) else {}
        return cls(
            col=_normalize_int(src.get("col")),
            row=_normalize_int(src.get("row")),
            color=str(src.get("color") or "#8d6e63"),
            label=str(src.get("label") or ""),
            movement_type=str(src.get("movement_type") or "ground"),
            is_swim=bool(src.get("is_swim", False)),
            is_rough=bool(src.get("is_rough", True)),
        ).normalized()


@dataclass
class MapFeature:
    feature_id: str
    col: int = 0
    row: int = 0
    kind: str = "feature"
    payload: Dict[str, Any] = field(default_factory=dict)

    def normalized(self) -> "MapFeature":
        return MapFeature(
            feature_id=str(self.feature_id or "").strip(),
            col=_normalize_int(self.col),
            row=_normalize_int(self.row),
            kind=str(self.kind or "feature").strip() or "feature",
            payload=dict(self.payload or {}),
        )

    def to_dict(self) -> Dict[str, Any]:
        item = self.normalized()
        return {
            "id": item.feature_id,
            "col": item.col,
            "row": item.row,
            "kind": item.kind,
            "payload": dict(item.payload),
        }

    @classmethod
    def from_dict(cls, payload: Any) -> Optional["MapFeature"]:
        src = payload if isinstance(payload, dict) else {}
        item = cls(
            feature_id=str(src.get("id") or "").strip(),
            col=_normalize_int(src.get("col")),
            row=_normalize_int(src.get("row")),
            kind=str(src.get("kind") or "feature"),
            payload=dict(src.get("payload") if isinstance(src.get("payload"), dict) else {}),
        ).normalized()
        return item if item.feature_id else None


@dataclass
class MapHazard:
    hazard_id: str
    col: int = 0
    row: int = 0
    kind: str = "hazard"
    payload: Dict[str, Any] = field(default_factory=dict)

    def normalized(self) -> "MapHazard":
        return MapHazard(
            hazard_id=str(self.hazard_id or "").strip(),
            col=_normalize_int(self.col),
            row=_normalize_int(self.row),
            kind=str(self.kind or "hazard").strip() or "hazard",
            payload=dict(self.payload or {}),
        )

    def to_dict(self) -> Dict[str, Any]:
        item = self.normalized()
        return {
            "id": item.hazard_id,
            "col": item.col,
            "row": item.row,
            "kind": item.kind,
            "payload": dict(item.payload),
        }

    @classmethod
    def from_dict(cls, payload: Any) -> Optional["MapHazard"]:
        src = payload if isinstance(payload, dict) else {}
        item = cls(
            hazard_id=str(src.get("id") or "").strip(),
            col=_normalize_int(src.get("col")),
            row=_normalize_int(src.get("row")),
            kind=str(src.get("kind") or "hazard"),
            payload=dict(src.get("payload") if isinstance(src.get("payload"), dict) else {}),
        ).normalized()
        return item if item.hazard_id else None


@dataclass
class MapStructure:
    structure_id: str
    kind: str = "structure"
    anchor_col: int = 0
    anchor_row: int = 0
    occupied_cells: List[CellKey] = field(default_factory=list)
    payload: Dict[str, Any] = field(default_factory=dict)

    def normalized(self) -> "MapStructure":
        cells: List[CellKey] = []
        for raw in list(self.occupied_cells or []):
            key = _string_to_cell_key(raw)
            if key is not None:
                cells.append((int(key[0]), int(key[1])))
        return MapStructure(
            structure_id=str(self.structure_id or "").strip(),
            kind=str(self.kind or "structure").strip() or "structure",
            anchor_col=_normalize_int(self.anchor_col),
            anchor_row=_normalize_int(self.anchor_row),
            occupied_cells=cells,
            payload=dict(self.payload or {}),
        )

    def to_dict(self) -> Dict[str, Any]:
        item = self.normalized()
        return {
            "id": item.structure_id,
            "kind": item.kind,
            "anchor_col": item.anchor_col,
            "anchor_row": item.anchor_row,
            "occupied_cells": [
                {"col": int(col), "row": int(row)} for col, row in item.occupied_cells
            ],
            "payload": dict(item.payload),
        }

    @classmethod
    def from_dict(cls, payload: Any) -> Optional["MapStructure"]:
        src = payload if isinstance(payload, dict) else {}
        occupied: List[CellKey] = []
        occupied_raw = src.get("occupied_cells")
        for entry in occupied_raw if isinstance(occupied_raw, list) else []:
            if not isinstance(entry, dict):
                continue
            occupied.append((_normalize_int(entry.get("col")), _normalize_int(entry.get("row"))))
        item = cls(
            structure_id=str(src.get("id") or "").strip(),
            kind=str(src.get("kind") or "structure"),
            anchor_col=_normalize_int(src.get("anchor_col")),
            anchor_row=_normalize_int(src.get("anchor_row")),
            occupied_cells=occupied,
            payload=dict(src.get("payload") if isinstance(src.get("payload"), dict) else {}),
        ).normalized()
        return item if item.structure_id else None


@dataclass
class ElevationCell:
    col: int
    row: int
    elevation: float = 0.0

    @property
    def key(self) -> CellKey:
        return (int(self.col), int(self.row))

    def normalized(self) -> "ElevationCell":
        return ElevationCell(
            col=_normalize_int(self.col),
            row=_normalize_int(self.row),
            elevation=_normalize_float(self.elevation, 0.0),
        )

    def to_dict(self) -> Dict[str, Any]:
        item = self.normalized()
        return {"col": item.col, "row": item.row, "elevation": item.elevation}

    @classmethod
    def from_dict(cls, payload: Any) -> "ElevationCell":
        src = payload if isinstance(payload, dict) else {}
        return cls(
            col=_normalize_int(src.get("col")),
            row=_normalize_int(src.get("row")),
            elevation=_normalize_float(src.get("elevation"), 0.0),
        ).normalized()


@dataclass
class MapState:
    schema_version: int = MAP_STATE_SCHEMA_VERSION
    grid: GridSpec = field(default_factory=GridSpec)
    terrain_cells: Dict[CellKey, TerrainCell] = field(default_factory=dict)
    obstacles: Dict[CellKey, bool] = field(default_factory=dict)
    features: Dict[str, MapFeature] = field(default_factory=dict)
    hazards: Dict[str, MapHazard] = field(default_factory=dict)
    structures: Dict[str, MapStructure] = field(default_factory=dict)
    elevation_cells: Dict[CellKey, ElevationCell] = field(default_factory=dict)
    token_positions: Dict[int, CellKey] = field(default_factory=dict)
    aoes: Dict[int, Dict[str, Any]] = field(default_factory=dict)
    presentation: Dict[str, Any] = field(default_factory=dict)

    def normalized(self) -> "MapState":
        grid = self.grid.normalized()
        terrain = {cell.key: cell.normalized() for cell in self.terrain_cells.values()}
        obstacle_map = {(_normalize_int(k[0]), _normalize_int(k[1])): True for k in self.obstacles.keys()}
        features = {
            feature.feature_id: feature.normalized()
            for feature in self.features.values()
            if str(getattr(feature, "feature_id", "")).strip()
        }
        hazards = {
            hazard.hazard_id: hazard.normalized()
            for hazard in self.hazards.values()
            if str(getattr(hazard, "hazard_id", "")).strip()
        }
        structures = {
            structure.structure_id: structure.normalized()
            for structure in self.structures.values()
            if str(getattr(structure, "structure_id", "")).strip()
        }
        elevation = {cell.key: cell.normalized() for cell in self.elevation_cells.values()}
        tokens: Dict[int, CellKey] = {}
        for raw_cid, raw_pos in (self.token_positions or {}).items():
            try:
                cid = int(raw_cid)
                col, row = raw_pos
                tokens[cid] = (int(col), int(row))
            except Exception:
                continue
        aoes = {}
        for raw_id, raw_aoe in (self.aoes or {}).items():
            try:
                aid = int(raw_id)
            except Exception:
                continue
            aoes[aid] = dict(raw_aoe) if isinstance(raw_aoe, dict) else {}
        presentation = dict(self.presentation or {})
        return MapState(
            schema_version=MAP_STATE_SCHEMA_VERSION,
            grid=grid,
            terrain_cells=terrain,
            obstacles=obstacle_map,
            features=features,
            hazards=hazards,
            structures=structures,
            elevation_cells=elevation,
            token_positions=tokens,
            aoes=aoes,
            presentation=presentation,
        )

    def validate(self) -> List[str]:
        errors: List[str] = []
        grid = self.grid.normalized()
        if grid.cols <= 0 or grid.rows <= 0:
            errors.append("grid dimensions must be positive")
        for col, row in list(self.obstacles.keys()):
            if col < 0 or row < 0:
                errors.append(f"obstacle out of bounds: {(col, row)}")
        for cid, (col, row) in self.token_positions.items():
            if cid <= 0:
                errors.append(f"invalid token cid: {cid}")
            if col < 0 or row < 0:
                errors.append(f"token position out of bounds: {cid}@{(col, row)}")
        return errors

    def to_dict(self) -> Dict[str, Any]:
        normalized = self.normalized()
        return {
            "schema_version": int(normalized.schema_version),
            "grid": normalized.grid.to_dict(),
            "terrain_cells": [cell.to_dict() for cell in sorted(normalized.terrain_cells.values(), key=lambda c: c.key)],
            "obstacles": [{"col": int(col), "row": int(row)} for col, row in sorted(normalized.obstacles.keys())],
            "features": [feature.to_dict() for feature in sorted(normalized.features.values(), key=lambda item: item.feature_id)],
            "hazards": [hazard.to_dict() for hazard in sorted(normalized.hazards.values(), key=lambda item: item.hazard_id)],
            "structures": [structure.to_dict() for structure in sorted(normalized.structures.values(), key=lambda item: item.structure_id)],
            "elevation_cells": [cell.to_dict() for cell in sorted(normalized.elevation_cells.values(), key=lambda item: (item.col, item.row))],
            "token_positions": [{"cid": int(cid), "col": int(pos[0]), "row": int(pos[1])} for cid, pos in sorted(normalized.token_positions.items())],
            "aoes": {str(int(aid)): dict(aoe) for aid, aoe in sorted(normalized.aoes.items())},
            "presentation": dict(normalized.presentation),
        }

    @classmethod
    def from_dict(cls, payload: Any) -> "MapState":
        src = payload if isinstance(payload, dict) else {}
        grid = GridSpec.from_dict(src.get("grid"))
        terrain_cells: Dict[CellKey, TerrainCell] = {}
        for raw in src.get("terrain_cells") if isinstance(src.get("terrain_cells"), list) else []:
            cell = TerrainCell.from_dict(raw)
            terrain_cells[cell.key] = cell
        obstacles: Dict[CellKey, bool] = {}
        for raw in src.get("obstacles") if isinstance(src.get("obstacles"), list) else []:
            if not isinstance(raw, dict):
                continue
            key = (_normalize_int(raw.get("col")), _normalize_int(raw.get("row")))
            obstacles[key] = True
        features: Dict[str, MapFeature] = {}
        for raw in src.get("features") if isinstance(src.get("features"), list) else []:
            feature = MapFeature.from_dict(raw)
            if feature is not None:
                features[feature.feature_id] = feature
        hazards: Dict[str, MapHazard] = {}
        for raw in src.get("hazards") if isinstance(src.get("hazards"), list) else []:
            hazard = MapHazard.from_dict(raw)
            if hazard is not None:
                hazards[hazard.hazard_id] = hazard
        structures: Dict[str, MapStructure] = {}
        for raw in src.get("structures") if isinstance(src.get("structures"), list) else []:
            structure = MapStructure.from_dict(raw)
            if structure is not None:
                structures[structure.structure_id] = structure
        elevation: Dict[CellKey, ElevationCell] = {}
        for raw in src.get("elevation_cells") if isinstance(src.get("elevation_cells"), list) else []:
            cell = ElevationCell.from_dict(raw)
            elevation[cell.key] = cell
        tokens: Dict[int, CellKey] = {}
        for raw in src.get("token_positions") if isinstance(src.get("token_positions"), list) else []:
            if not isinstance(raw, dict):
                continue
            cid = _normalize_int(raw.get("cid"), 0)
            if cid <= 0:
                continue
            tokens[cid] = (_normalize_int(raw.get("col")), _normalize_int(raw.get("row")))
        aoes: Dict[int, Dict[str, Any]] = {}
        raw_aoes = src.get("aoes") if isinstance(src.get("aoes"), dict) else {}
        for raw_id, raw_aoe in raw_aoes.items():
            try:
                aid = int(raw_id)
            except Exception:
                continue
            aoes[aid] = dict(raw_aoe) if isinstance(raw_aoe, dict) else {}
        state = cls(
            schema_version=MAP_STATE_SCHEMA_VERSION,
            grid=grid,
            terrain_cells=terrain_cells,
            obstacles=obstacles,
            features=features,
            hazards=hazards,
            structures=structures,
            elevation_cells=elevation,
            token_positions=tokens,
            aoes=aoes,
            presentation=dict(src.get("presentation") if isinstance(src.get("presentation"), dict) else {}),
        )
        return state.normalized()

    @classmethod
    def from_legacy(
        cls,
        *,
        cols: int,
        rows: int,
        feet_per_square: float = 5.0,
        positions: Optional[Dict[int, Tuple[int, int]]] = None,
        obstacles: Optional[Iterable[Tuple[int, int]]] = None,
        rough_terrain: Optional[Dict[Tuple[int, int], Any]] = None,
        aoes: Optional[Dict[int, Dict[str, Any]]] = None,
        presentation: Optional[Dict[str, Any]] = None,
    ) -> "MapState":
        terrain_cells: Dict[CellKey, TerrainCell] = {}
        for raw_key, raw_cell in (rough_terrain or {}).items():
            key = _string_to_cell_key(raw_key)
            if key is None:
                continue
            if isinstance(raw_cell, dict):
                payload = dict(raw_cell)
                payload["col"] = key[0]
                payload["row"] = key[1]
                cell = TerrainCell.from_dict(payload)
            elif isinstance(raw_cell, str):
                cell = TerrainCell(col=key[0], row=key[1], color=str(raw_cell), is_rough=True)
            else:
                cell = TerrainCell(col=key[0], row=key[1])
            terrain_cells[cell.key] = cell
        obstacle_map: Dict[CellKey, bool] = {}
        for raw in list(obstacles or []):
            key = _string_to_cell_key(raw)
            if key is None:
                continue
            obstacle_map[key] = True
        token_positions: Dict[int, CellKey] = {}
        for raw_cid, raw_pos in (positions or {}).items():
            try:
                cid = int(raw_cid)
                token_positions[cid] = (int(raw_pos[0]), int(raw_pos[1]))
            except Exception:
                continue
        out_aoes: Dict[int, Dict[str, Any]] = {}
        for raw_id, raw_aoe in (aoes or {}).items():
            try:
                aid = int(raw_id)
            except Exception:
                continue
            out_aoes[aid] = dict(raw_aoe) if isinstance(raw_aoe, dict) else {}
        return cls(
            schema_version=MAP_STATE_SCHEMA_VERSION,
            grid=GridSpec(cols=cols, rows=rows, feet_per_square=feet_per_square).normalized(),
            terrain_cells=terrain_cells,
            obstacles=obstacle_map,
            token_positions=token_positions,
            aoes=out_aoes,
            presentation=dict(presentation or {}),
        ).normalized()

    def to_legacy(self) -> Dict[str, Any]:
        normalized = self.normalized()
        return {
            "cols": int(normalized.grid.cols),
            "rows": int(normalized.grid.rows),
            "feet_per_square": float(normalized.grid.feet_per_square),
            "positions": {int(cid): (int(pos[0]), int(pos[1])) for cid, pos in normalized.token_positions.items()},
            "obstacles": {(int(col), int(row)) for col, row in normalized.obstacles.keys()},
            "rough_terrain": {
                (int(cell.col), int(cell.row)): {
                    "color": str(cell.color),
                    "label": str(cell.label),
                    "movement_type": str(cell.movement_type),
                    "is_swim": bool(cell.is_swim),
                    "is_rough": bool(cell.is_rough),
                }
                for cell in normalized.terrain_cells.values()
            },
            "aoes": {int(aid): dict(aoe) for aid, aoe in normalized.aoes.items()},
            "presentation": dict(normalized.presentation),
        }


class MapQueryAPI:
    def __init__(self, state: MapState) -> None:
        self.state = state.normalized()

    @staticmethod
    def hazard_blocks_structure_movement(payload: Any) -> bool:
        data = payload if isinstance(payload, dict) else {}
        if data.get("blocks_structure_movement") is False:
            return False
        if bool(data.get("blocks_structure_movement")):
            return True
        return bool(data.get("blocks_movement"))

    def terrain_at(self, col: int, row: int) -> TerrainCell:
        return self.state.terrain_cells.get((int(col), int(row)), TerrainCell(col=int(col), row=int(row), is_rough=False))

    def features_at(self, col: int, row: int) -> List[MapFeature]:
        key = (int(col), int(row))
        found: List[MapFeature] = []
        for item in self.state.features.values():
            if key in _entity_cells(item.col, item.row, item.payload):
                found.append(item)
        return found

    def hazards_at(self, col: int, row: int) -> List[MapHazard]:
        key = (int(col), int(row))
        found: List[MapHazard] = []
        for item in self.state.hazards.values():
            if key in _entity_cells(item.col, item.row, item.payload):
                found.append(item)
        return found

    def structures_at(self, col: int, row: int) -> List[MapStructure]:
        key = (int(col), int(row))
        found: List[MapStructure] = []
        for item in self.state.structures.values():
            if key in self.structure_cells(item):
                found.append(item)
        return found

    def structure_cells(self, structure: Any) -> set[CellKey]:
        if isinstance(structure, MapStructure):
            item = structure
        elif isinstance(structure, str):
            item = (self.state.structures or {}).get(str(structure))
        else:
            item = None
        if not isinstance(item, MapStructure):
            return set()
        cells = {(int(item.anchor_col), int(item.anchor_row))}
        for col, row in list(item.occupied_cells or []):
            cells.add((int(col), int(row)))
        return cells

    def structure_world_cells_for_anchor(self, structure_id: Any, anchor_col: int, anchor_row: int) -> set[CellKey]:
        item = (self.state.structures or {}).get(str(structure_id or ""))
        if not isinstance(item, MapStructure):
            return set()
        dc = int(anchor_col) - int(item.anchor_col)
        dr = int(anchor_row) - int(item.anchor_row)
        return {(col + dc, row + dr) for col, row in self.structure_cells(item)}

    def elevation_at(self, col: int, row: int) -> float:
        cell = self.state.elevation_cells.get((int(col), int(row)))
        return float(cell.elevation) if cell is not None else 0.0

    def blocks_movement(self, col: int, row: int) -> bool:
        key = (int(col), int(row))
        if key in self.state.obstacles:
            return True
        for feature in self.features_at(col, row):
            payload = feature.payload if isinstance(feature.payload, dict) else {}
            if bool(payload.get("blocks_movement")):
                return True
        for structure in self.structures_at(col, row):
            payload = structure.payload if isinstance(structure.payload, dict) else {}
            if bool(payload.get("blocks_movement")):
                return True
        for hazard in self.hazards_at(col, row):
            payload = hazard.payload if isinstance(hazard.payload, dict) else {}
            if bool(payload.get("blocks_movement")):
                return True
        return False

    def _cell_tags(self, col: int, row: int) -> set[str]:
        tags: set[str] = set()
        for item in self.features_at(col, row):
            payload = item.payload if isinstance(item.payload, dict) else {}
            for raw in payload.get("tags") if isinstance(payload.get("tags"), list) else []:
                text = str(raw or "").strip().lower()
                if text:
                    tags.add(text)
            kind = str(item.kind or "").strip().lower()
            if kind:
                tags.add(kind)
        for item in self.structures_at(col, row):
            payload = item.payload if isinstance(item.payload, dict) else {}
            for raw in payload.get("tags") if isinstance(payload.get("tags"), list) else []:
                text = str(raw or "").strip().lower()
                if text:
                    tags.add(text)
            kind = str(item.kind or "").strip().lower()
            if kind:
                tags.add(kind)
        return tags

    def _cell_climb_cap(self, col: int, row: int) -> Optional[float]:
        candidates: List[float] = []
        for item in self.features_at(col, row):
            payload = item.payload if isinstance(item.payload, dict) else {}
            for key in ("max_climb_delta", "max_step_height", "climb_delta_ft"):
                if payload.get(key) is None:
                    continue
                try:
                    candidates.append(float(payload.get(key)))
                except Exception:
                    continue
        for item in self.structures_at(col, row):
            payload = item.payload if isinstance(item.payload, dict) else {}
            for key in ("max_climb_delta", "max_step_height", "climb_delta_ft"):
                if payload.get(key) is None:
                    continue
                try:
                    candidates.append(float(payload.get(key)))
                except Exception:
                    continue
        if not candidates:
            return None
        return max(0.0, max(candidates))

    def climbable_transition(self, from_col: int, from_row: int, to_col: int, to_row: int) -> Dict[str, Any]:
        from_elevation = float(self.elevation_at(from_col, from_row))
        to_elevation = float(self.elevation_at(to_col, to_row))
        delta = abs(to_elevation - from_elevation)
        feet_per_square = max(1.0, float(self.state.grid.feet_per_square or 5.0))
        from_tags = self._cell_tags(from_col, from_row)
        to_tags = self._cell_tags(to_col, to_row)
        tags = from_tags | to_tags
        climbable = bool(
            tags.intersection(
                {
                    "climbable",
                    "ladder",
                    "stairs",
                    "stair",
                    "ramp",
                    "gangplank",
                    "bridge",
                    "boarding_bridge",
                }
            )
        )
        strict_transition = bool("requires_climb_transition" in tags or "cliff" in tags or "mast" in tags)
        cap_candidates = [feet_per_square]
        local_cap = self._cell_climb_cap(from_col, from_row)
        if local_cap is not None:
            cap_candidates.append(local_cap)
        local_cap = self._cell_climb_cap(to_col, to_row)
        if local_cap is not None:
            cap_candidates.append(local_cap)
        max_step_without_climb = max(0.0, max(cap_candidates))
        blocked = bool(strict_transition and delta > max_step_without_climb and not climbable)
        return {
            "from": {"col": int(from_col), "row": int(from_row), "elevation": from_elevation},
            "to": {"col": int(to_col), "row": int(to_row), "elevation": to_elevation},
            "delta": delta,
            "climbable": climbable,
            "strict_transition": strict_transition,
            "max_step_without_climb": max_step_without_climb,
            "blocked": blocked,
        }

    def movement_cost_for_step(self, from_col: int, from_row: int, to_col: int, to_row: int, base_cost: int) -> int:
        if self.blocks_movement(to_col, to_row):
            return INFINITE_MOVEMENT_COST
        transition = self.climbable_transition(from_col, from_row, to_col, to_row)
        if bool(transition.get("blocked")):
            return INFINITE_MOVEMENT_COST
        target = self.terrain_at(to_col, to_row)
        cost = int(base_cost)
        if bool(target.is_rough):
            cost *= 2
        for hazard in self.hazards_at(to_col, to_row):
            payload = hazard.payload if isinstance(hazard.payload, dict) else {}
            try:
                multiplier = float(payload.get("movement_multiplier", 1.0) or 1.0)
            except Exception:
                multiplier = 1.0
            if multiplier > 0:
                cost = int(max(1, round(float(cost) * multiplier)))
        try:
            from_elev = float(self.elevation_at(from_col, from_row))
            to_elev = float(self.elevation_at(to_col, to_row))
            delta = abs(to_elev - from_elev)
            if delta > 0.0:
                step_unit = float(self.state.grid.feet_per_square or 5.0)
                climb_penalty = int(round((delta / max(1.0, step_unit)) * max(1, int(base_cost))))
                if bool(transition.get("climbable")) and climb_penalty > 0:
                    climb_penalty = int(math.ceil(climb_penalty * 0.5))
                cost += max(0, climb_penalty)
        except Exception:
            pass
        return max(1, int(cost))

    def vertical_distance(self, from_col: int, from_row: int, to_col: int, to_row: int) -> float:
        dx = float(to_col) - float(from_col)
        dy = float(to_row) - float(from_row)
        dz = float(self.elevation_at(to_col, to_row)) - float(self.elevation_at(from_col, from_row))
        return (dx * dx + dy * dy + dz * dz) ** 0.5

    def traversal_state_for_unit(self, col: int, row: int) -> Dict[str, Any]:
        key = (int(col), int(row))
        terrain = self.terrain_at(col, row)
        return {
            "cell": {"col": key[0], "row": key[1]},
            "blocked": self.blocks_movement(col, row),
            "terrain": terrain.to_dict(),
            "features": [item.to_dict() for item in self.features_at(col, row)],
            "hazards": [item.to_dict() for item in self.hazards_at(col, row)],
            "structures": [item.to_dict() for item in self.structures_at(col, row)],
            "elevation": self.elevation_at(col, row),
            "occupied_by": [int(cid) for cid, pos in self.state.token_positions.items() if tuple(pos) == key],
        }

    def structure_move_blockers(self, structure_id: Any, delta_col: int, delta_row: int) -> Dict[str, Any]:
        sid = str(structure_id or "").strip()
        if not sid:
            return {"ok": False, "reason": "missing_structure_id", "target_cells": []}
        structure = (self.state.structures or {}).get(sid)
        if not isinstance(structure, MapStructure):
            return {"ok": False, "reason": "structure_not_found", "target_cells": []}
        current_cells = self.structure_cells(structure)
        target_cells = {(int(col) + int(delta_col), int(row) + int(delta_row)) for col, row in current_cells}
        cols = int(self.state.grid.cols)
        rows = int(self.state.grid.rows)
        out_of_bounds = sorted((col, row) for col, row in target_cells if col < 0 or row < 0 or col >= cols or row >= rows)
        obstacle_hits = sorted((col, row) for col, row in target_cells if (col, row) in self.state.obstacles)
        blocking_features: List[Dict[str, Any]] = []
        blocking_structures: List[Dict[str, Any]] = []
        blocking_hazards: List[Dict[str, Any]] = []
        for col, row in sorted(target_cells):
            for feature in self.features_at(col, row):
                if str(feature.feature_id) == sid:
                    continue
                payload = feature.payload if isinstance(feature.payload, dict) else {}
                attached_sid = str(payload.get("attached_structure_id") or "").strip()
                if attached_sid == sid:
                    continue
                if bool(payload.get("blocks_structure_movement")) or bool(payload.get("blocks_movement")):
                    blocking_features.append({"id": str(feature.feature_id), "cell": {"col": int(col), "row": int(row)}})
            for hazard in self.hazards_at(col, row):
                payload = hazard.payload if isinstance(hazard.payload, dict) else {}
                if self.hazard_blocks_structure_movement(payload):
                    blocking_hazards.append({"id": str(hazard.hazard_id), "cell": {"col": int(col), "row": int(row)}})
            for other in self.structures_at(col, row):
                if str(other.structure_id) == sid:
                    continue
                blocking_structures.append({"id": str(other.structure_id), "cell": {"col": int(col), "row": int(row)}})
        blockers = {
            "out_of_bounds": [{"col": int(col), "row": int(row)} for col, row in out_of_bounds],
            "obstacles": [{"col": int(col), "row": int(row)} for col, row in obstacle_hits],
            "features": blocking_features,
            "structures": blocking_structures,
            "hazards": blocking_hazards,
        }
        has_blockers = any(bool(value) for value in blockers.values())
        return {
            "ok": not has_blockers,
            "structure_id": sid,
            "delta": {"col": int(delta_col), "row": int(delta_row)},
            "target_cells": [{"col": int(col), "row": int(row)} for col, row in sorted(target_cells)],
            "blockers": blockers,
        }

    def adjacent_structures(self, structure_id: Any, *, include_diagonal: bool = True) -> List[MapStructure]:
        sid = str(structure_id or "").strip()
        source = (self.state.structures or {}).get(sid)
        if not isinstance(source, MapStructure):
            return []
        source_cells = self.structure_cells(source)
        found: Dict[str, MapStructure] = {}
        for other in self.state.structures.values():
            if str(other.structure_id) == sid:
                continue
            other_cells = self.structure_cells(other)
            adjacent = False
            for col, row in source_cells:
                for ocol, orow in other_cells:
                    dc = abs(int(col) - int(ocol))
                    dr = abs(int(row) - int(orow))
                    if include_diagonal:
                        if max(dc, dr) == 1:
                            adjacent = True
                            break
                    elif dc + dr == 1:
                        adjacent = True
                        break
                if adjacent:
                    break
            if adjacent:
                found[str(other.structure_id)] = other
        return list(found.values())

    def structure_contacts(self, structure_id: Any) -> List[Dict[str, Any]]:
        sid = str(structure_id or "").strip()
        source = (self.state.structures or {}).get(sid)
        if not isinstance(source, MapStructure):
            return []
        source_cells = self.structure_cells(source)
        relations: List[Dict[str, Any]] = []
        for other in self.state.structures.values():
            oid = str(other.structure_id)
            if oid == sid:
                continue
            other_cells = self.structure_cells(other)
            shared = sorted(source_cells & other_cells)
            edge_touch: set[CellKey] = set()
            corner_touch: set[CellKey] = set()
            for col, row in source_cells:
                for ocol, orow in other_cells:
                    dc = abs(int(col) - int(ocol))
                    dr = abs(int(row) - int(orow))
                    if dc + dr == 1:
                        edge_touch.add((int(col), int(row)))
                    elif max(dc, dr) == 1:
                        corner_touch.add((int(col), int(row)))
            if not shared and not edge_touch and not corner_touch:
                continue
            source_payload = source.payload if isinstance(source.payload, dict) else {}
            other_payload = other.payload if isinstance(other.payload, dict) else {}
            boardable = bool(
                shared
                or source_payload.get("boardable")
                or other_payload.get("boardable")
                or source_payload.get("allow_boarding")
                or other_payload.get("allow_boarding")
                or source_payload.get("has_gangplank")
                or other_payload.get("has_gangplank")
            )
            relations.append(
                {
                    "source_id": sid,
                    "target_id": oid,
                    "shared_cells": [{"col": int(col), "row": int(row)} for col, row in shared],
                    "touching_edges": [{"col": int(col), "row": int(row)} for col, row in sorted(edge_touch)],
                    "touching_corners": [{"col": int(col), "row": int(row)} for col, row in sorted(corner_touch - edge_touch)],
                    "adjacent": bool(edge_touch or corner_touch),
                    "contact": bool(shared or edge_touch),
                    "boardable": boardable,
                }
            )
        relations.sort(key=lambda item: str(item.get("target_id") or ""))
        return relations

    def boardable_structure_ids(self, structure_id: Any) -> List[str]:
        return [str(item.get("target_id") or "") for item in self.structure_contacts(structure_id) if bool(item.get("boardable"))]

    @staticmethod
    def _is_ship_structure(item: Any) -> bool:
        if not isinstance(item, MapStructure):
            return False
        kind = str(item.kind or "").strip().lower()
        payload = item.payload if isinstance(item.payload, dict) else {}
        return bool("ship" in kind or payload.get("ship_instance_id") or payload.get("ship_blueprint_id"))

    @staticmethod
    def _boarding_points(payload: Any) -> List[Dict[str, Any]]:
        if not isinstance(payload, dict):
            return []
        points_raw = payload.get("boarding_points")
        points: List[Dict[str, Any]] = []
        for raw in points_raw if isinstance(points_raw, list) else []:
            if not isinstance(raw, dict):
                continue
            try:
                col = int(raw.get("col", 0))
                row = int(raw.get("row", 0))
            except Exception:
                continue
            points.append(
                {
                    "id": str(raw.get("id") or "").strip(),
                    "name": str(raw.get("name") or "").strip(),
                    "col": col,
                    "row": row,
                    "tags": [str(tag).strip().lower() for tag in (raw.get("tags") if isinstance(raw.get("tags"), list) else []) if str(tag).strip()],
                }
            )
        return points

    def ship_contacts(self, structure_id: Any) -> List[Dict[str, Any]]:
        sid = str(structure_id or "").strip()
        source = (self.state.structures or {}).get(sid)
        if not isinstance(source, MapStructure):
            return []
        source_payload = source.payload if isinstance(source.payload, dict) else {}
        source_points = self._boarding_points(source_payload)
        source_point_cells = {(int(point.get("col", 0)), int(point.get("row", 0))) for point in source_points}
        contacts: List[Dict[str, Any]] = []
        for relation in self.structure_contacts(sid):
            if not isinstance(relation, dict):
                continue
            target_id = str(relation.get("target_id") or "").strip()
            target = (self.state.structures or {}).get(target_id)
            if not isinstance(target, MapStructure):
                continue
            target_payload = target.payload if isinstance(target.payload, dict) else {}
            if not (self._is_ship_structure(source) or self._is_ship_structure(target)):
                continue
            target_points = self._boarding_points(target_payload)
            target_point_cells = {(int(point.get("col", 0)), int(point.get("row", 0))) for point in target_points}
            shared_cells = {(int(entry.get("col", 0)), int(entry.get("row", 0))) for entry in (relation.get("shared_cells") if isinstance(relation.get("shared_cells"), list) else []) if isinstance(entry, dict)}
            edge_cells = {(int(entry.get("col", 0)), int(entry.get("row", 0))) for entry in (relation.get("touching_edges") if isinstance(relation.get("touching_edges"), list) else []) if isinstance(entry, dict)}
            shared_boarding_set = (
                source_point_cells & target_point_cells
                | (source_point_cells & edge_cells)
                | (target_point_cells & edge_cells)
                | (source_point_cells & shared_cells)
                | (target_point_cells & shared_cells)
            )
            shared_boarding_cells = [{"col": int(col), "row": int(row)} for col, row in sorted(shared_boarding_set)]
            has_bridge = bool(source_payload.get("has_gangplank") or target_payload.get("has_gangplank"))
            bridge_links: List[Dict[str, Any]] = []
            if has_bridge:
                bridge_links.append(
                    {
                        "kind": "gangplank",
                        "source_id": sid,
                        "target_id": target_id,
                        "active": bool(relation.get("contact") or relation.get("adjacent")),
                    }
                )
            contact_type = "none"
            if shared_cells:
                contact_type = "overlap"
            elif edge_cells:
                contact_type = "touching_edge"
            elif bool(relation.get("adjacent")):
                contact_type = "touching_corner"
            if has_bridge and bool(relation.get("adjacent") or relation.get("contact")):
                contact_type = "bridged" if contact_type != "overlap" else "overlap_bridged"
            boarding_capable = bool(
                relation.get("boardable")
                or shared_boarding_cells
                or has_bridge
                or source_payload.get("allow_boarding")
                or target_payload.get("allow_boarding")
            )
            contacts.append(
                {
                    **relation,
                    "ship_contact": True,
                    "collision_adjacent": bool(relation.get("adjacent")),
                    "contact_type": contact_type,
                    "source_ship": self._is_ship_structure(source),
                    "target_ship": self._is_ship_structure(target),
                    "source_boarding_points": source_points,
                    "target_boarding_points": target_points,
                    "source_boardable_edges": [
                        str(edge).strip().lower()
                        for edge in (
                            source_payload.get("boardable_edges")
                            if isinstance(source_payload.get("boardable_edges"), list)
                            else []
                        )
                        if str(edge).strip()
                    ],
                    "target_boardable_edges": [
                        str(edge).strip().lower()
                        for edge in (
                            target_payload.get("boardable_edges")
                            if isinstance(target_payload.get("boardable_edges"), list)
                            else []
                        )
                        if str(edge).strip()
                    ],
                    "boarding_points": shared_boarding_cells,
                    "bridge_links": bridge_links,
                    "boarding_capable": boarding_capable,
                }
            )
        return contacts

    def ship_boardable_structure_ids(self, structure_id: Any) -> List[str]:
        return [str(item.get("target_id") or "") for item in self.ship_contacts(structure_id) if bool(item.get("boarding_capable"))]

    def ship_contact_relation(self, source_id: Any, target_id: Any) -> Optional[Dict[str, Any]]:
        sid = str(source_id or "").strip()
        tid = str(target_id or "").strip()
        if not sid or not tid:
            return None
        for relation in self.ship_contacts(sid):
            if str(relation.get("target_id") or "").strip() == tid:
                return dict(relation)
        return None

    @staticmethod
    def _pair_matches(source_id: str, target_id: str, relation_source: str, relation_target: str) -> bool:
        return (source_id == relation_source and target_id == relation_target) or (
            source_id == relation_target and target_id == relation_source
        )

    def _raw_boarding_links(self) -> List[Dict[str, Any]]:
        presentation = self.state.presentation if isinstance(self.state.presentation, dict) else {}
        raw_links = presentation.get("boarding_links")
        links: List[Dict[str, Any]] = []
        for raw in raw_links if isinstance(raw_links, list) else []:
            if isinstance(raw, dict):
                links.append(dict(raw))
        return links

    def _normalize_boarding_link(self, raw_link: Dict[str, Any], index: int) -> Dict[str, Any]:
        source_id = str(raw_link.get("source_id") or "").strip()
        target_id = str(raw_link.get("target_id") or "").strip()
        link_id = str(raw_link.get("id") or f"boarding_link_{index + 1}").strip() or f"boarding_link_{index + 1}"
        source_point = _normalize_boarding_point(raw_link.get("source_point"))
        target_point = _normalize_boarding_point(raw_link.get("target_point"))
        shared_points: List[Dict[str, Any]] = []
        for raw_point in (raw_link.get("shared_points") if isinstance(raw_link.get("shared_points"), list) else []):
            point = _normalize_boarding_point(raw_point)
            if point is None:
                continue
            shared_points.append(point)
        normalized: Dict[str, Any] = {
            "id": link_id,
            "source_id": source_id,
            "target_id": target_id,
            "source_ship_id": str(raw_link.get("source_ship_id") or "").strip(),
            "target_ship_id": str(raw_link.get("target_ship_id") or "").strip(),
            "source_edge": str(raw_link.get("source_edge") or "").strip().lower() or None,
            "target_edge": str(raw_link.get("target_edge") or "").strip().lower() or None,
            "bridge_kind": str(raw_link.get("bridge_kind") or "").strip().lower() or None,
            "status": _normalize_boarding_status(raw_link.get("status"), default="active"),
            "initiator": str(raw_link.get("initiator") or "").strip() or None,
            "opened_round": _normalize_int(raw_link.get("opened_round"), 0) or None,
            "opened_turn_cid": _normalize_int(raw_link.get("opened_turn_cid"), 0) or None,
            "reason": str(raw_link.get("reason") or "").strip() or None,
            "notes": str(raw_link.get("notes") or "").strip() or None,
            "created_at": str(raw_link.get("created_at") or "").strip() or None,
            "updated_at": str(raw_link.get("updated_at") or "").strip() or None,
            "source_point": source_point,
            "target_point": target_point,
            "shared_points": shared_points,
        }
        return normalized

    def boarding_links(self) -> List[Dict[str, Any]]:
        links: List[Dict[str, Any]] = []
        for index, raw_link in enumerate(self._raw_boarding_links()):
            link = self._normalize_boarding_link(raw_link, index)
            source_id = str(link.get("source_id") or "").strip()
            target_id = str(link.get("target_id") or "").strip()
            relation = self.ship_contact_relation(source_id, target_id) if source_id and target_id else None
            status = _normalize_boarding_status(link.get("status"), default="active")
            blocking_reason: Optional[str] = None
            if relation is None and status in BOARDING_LINK_TRAVERSABLE_STATUSES:
                status = "broken"
                blocking_reason = "relation_not_found"
            elif relation is not None and not bool(relation.get("boarding_capable")) and status in BOARDING_LINK_TRAVERSABLE_STATUSES:
                status = "blocked"
                blocking_reason = "relation_not_boarding_capable"
            elif relation is not None and not bool(relation.get("contact")) and status in BOARDING_LINK_TRAVERSABLE_STATUSES:
                status = "broken"
                blocking_reason = "contact_lost"
            traversable = bool(
                status in BOARDING_LINK_TRAVERSABLE_STATUSES
                and relation is not None
                and bool(relation.get("boarding_capable"))
                and bool(relation.get("contact"))
            )
            links.append(
                {
                    **link,
                    "status": status,
                    "relation_found": relation is not None,
                    "contact": bool(relation.get("contact")) if isinstance(relation, dict) else False,
                    "boarding_capable": bool(relation.get("boarding_capable")) if isinstance(relation, dict) else False,
                    "contact_type": str(relation.get("contact_type") or "none") if isinstance(relation, dict) else "none",
                    "boarding_points": list(relation.get("boarding_points") if isinstance(relation, dict) and isinstance(relation.get("boarding_points"), list) else []),
                    "bridge_links": list(relation.get("bridge_links") if isinstance(relation, dict) and isinstance(relation.get("bridge_links"), list) else []),
                    "blocking_reason": blocking_reason,
                    "traversable": traversable,
                }
            )
        links.sort(key=lambda item: str(item.get("id") or ""))
        return links

    def boarding_links_for_structure(self, structure_id: Any) -> List[Dict[str, Any]]:
        sid = str(structure_id or "").strip()
        if not sid:
            return []
        return [
            dict(link)
            for link in self.boarding_links()
            if sid in {str(link.get("source_id") or "").strip(), str(link.get("target_id") or "").strip()}
        ]

    def active_boarding_links_for_structure(self, structure_id: Any) -> List[Dict[str, Any]]:
        return [
            dict(link)
            for link in self.boarding_links_for_structure(structure_id)
            if _normalize_boarding_status(link.get("status"), default="active") in BOARDING_LINK_TRAVERSABLE_STATUSES
        ]

    def traversable_boarding_links_for_structure(self, structure_id: Any) -> List[Dict[str, Any]]:
        return [dict(link) for link in self.boarding_links_for_structure(structure_id) if bool(link.get("traversable"))]

    def ship_boarding_relations(self, structure_id: Any) -> List[Dict[str, Any]]:
        sid = str(structure_id or "").strip()
        if not sid:
            return []
        relations: Dict[str, Dict[str, Any]] = {}
        links_by_target: Dict[str, List[Dict[str, Any]]] = {}
        for link in self.boarding_links_for_structure(sid):
            source_id = str(link.get("source_id") or "").strip()
            target_id = str(link.get("target_id") or "").strip()
            other_id = target_id if source_id == sid else source_id
            if not other_id:
                continue
            links_by_target.setdefault(other_id, []).append(dict(link))
        for relation in self.ship_contacts(sid):
            target_id = str(relation.get("target_id") or "").strip()
            if not target_id:
                continue
            relation_links = links_by_target.get(target_id, [])
            traversable = any(bool(item.get("traversable")) for item in relation_links)
            status = "available" if bool(relation.get("boarding_capable")) else "blocked"
            if relation_links:
                status = str(relation_links[0].get("status") or status)
            relations[target_id] = {
                **dict(relation),
                "boarding_status": status,
                "boarding_link_ids": [str(item.get("id") or "") for item in relation_links if str(item.get("id") or "").strip()],
                "boarding_links": relation_links,
                "boarding_active": bool(relation_links),
                "boarding_traversable": traversable,
                "boarding_blocked": bool(status in {"blocked", "broken", "withdrawn"}),
            }
        for target_id, relation_links in links_by_target.items():
            if target_id in relations:
                continue
            status = str(relation_links[0].get("status") or "broken") if relation_links else "broken"
            traversable = any(bool(item.get("traversable")) for item in relation_links)
            relations[target_id] = {
                "source_id": sid,
                "target_id": target_id,
                "ship_contact": False,
                "contact": False,
                "adjacent": False,
                "boarding_capable": False,
                "contact_type": "none",
                "boarding_points": [],
                "bridge_links": [],
                "boarding_status": status,
                "boarding_link_ids": [str(item.get("id") or "") for item in relation_links if str(item.get("id") or "").strip()],
                "boarding_links": relation_links,
                "boarding_active": bool(relation_links),
                "boarding_traversable": traversable,
                "boarding_blocked": bool(status in {"blocked", "broken", "withdrawn"}),
            }
        return [relations[key] for key in sorted(relations.keys())]

    def connected_boarding_structure_ids(self, structure_id: Any, *, traversable_only: bool = True) -> List[str]:
        sid = str(structure_id or "").strip()
        if not sid:
            return []
        visited = {sid}
        pending = [sid]
        while pending:
            current = pending.pop(0)
            links = (
                self.traversable_boarding_links_for_structure(current)
                if traversable_only
                else self.boarding_links_for_structure(current)
            )
            for link in links:
                source_id = str(link.get("source_id") or "").strip()
                target_id = str(link.get("target_id") or "").strip()
                next_id = target_id if source_id == current else source_id
                if not next_id or next_id in visited:
                    continue
                visited.add(next_id)
                pending.append(next_id)
        return sorted(item for item in visited if item != sid)


def build_map_delta(prev: MapState, curr: MapState) -> Dict[str, Any]:
    p = prev.normalized()
    c = curr.normalized()

    terrain_upserts: List[Dict[str, Any]] = []
    terrain_removals: List[Dict[str, int]] = []
    for key, cell in c.terrain_cells.items():
        if p.terrain_cells.get(key) != cell:
            terrain_upserts.append(cell.to_dict())
    for key in p.terrain_cells.keys() - c.terrain_cells.keys():
        terrain_removals.append({"col": int(key[0]), "row": int(key[1])})

    obstacle_upserts = [{"col": int(col), "row": int(row)} for col, row in sorted(c.obstacles.keys() - p.obstacles.keys())]
    obstacle_removals = [{"col": int(col), "row": int(row)} for col, row in sorted(p.obstacles.keys() - c.obstacles.keys())]

    token_upserts: List[Dict[str, int]] = []
    token_removals: List[Dict[str, int]] = []
    for cid, pos in c.token_positions.items():
        if p.token_positions.get(cid) != pos:
            token_upserts.append({"cid": int(cid), "col": int(pos[0]), "row": int(pos[1])})
    for cid in p.token_positions.keys() - c.token_positions.keys():
        token_removals.append({"cid": int(cid)})

    def _entity_delta(prev_map: Dict[str, Any], curr_map: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[str]]:
        upserts = []
        removals = []
        for item_id, item in curr_map.items():
            if prev_map.get(item_id) != item:
                upserts.append(item.to_dict())
        for item_id in prev_map.keys() - curr_map.keys():
            removals.append(str(item_id))
        return upserts, removals

    feature_upserts, feature_removals = _entity_delta(p.features, c.features)
    hazard_upserts, hazard_removals = _entity_delta(p.hazards, c.hazards)
    structure_upserts, structure_removals = _entity_delta(p.structures, c.structures)

    elevation_upserts: List[Dict[str, Any]] = []
    elevation_removals: List[Dict[str, int]] = []
    for key, cell in c.elevation_cells.items():
        if p.elevation_cells.get(key) != cell:
            elevation_upserts.append(cell.to_dict())
    for key in p.elevation_cells.keys() - c.elevation_cells.keys():
        elevation_removals.append({"col": int(key[0]), "row": int(key[1])})

    aoe_upserts: List[Dict[str, Any]] = []
    aoe_removals: List[int] = []
    for aid, aoe in c.aoes.items():
        if p.aoes.get(aid) != aoe:
            payload = dict(aoe)
            payload["aid"] = int(aid)
            aoe_upserts.append(payload)
    for aid in p.aoes.keys() - c.aoes.keys():
        aoe_removals.append(int(aid))

    return {
        "schema_version": MAP_STATE_SCHEMA_VERSION,
        "grid": c.grid.to_dict() if p.grid != c.grid else None,
        "terrain_cells": {"upserts": terrain_upserts, "removals": terrain_removals},
        "obstacles": {"upserts": obstacle_upserts, "removals": obstacle_removals},
        "features": {"upserts": feature_upserts, "removals": feature_removals},
        "hazards": {"upserts": hazard_upserts, "removals": hazard_removals},
        "structures": {"upserts": structure_upserts, "removals": structure_removals},
        "elevation_cells": {"upserts": elevation_upserts, "removals": elevation_removals},
        "tokens": {"upserts": token_upserts, "removals": token_removals},
        "aoes": {"upserts": aoe_upserts, "removals": aoe_removals},
    }


def map_delta_has_changes(delta: Dict[str, Any]) -> bool:
    if not isinstance(delta, dict):
        return False
    if isinstance(delta.get("grid"), dict):
        return True
    for section in ("terrain_cells", "obstacles", "features", "hazards", "structures", "elevation_cells", "tokens", "aoes"):
        part = delta.get(section)
        if not isinstance(part, dict):
            continue
        if part.get("upserts") or part.get("removals"):
            return True
    return False


def apply_map_delta(state: MapState, delta: Dict[str, Any]) -> MapState:
    next_state = state.normalized()
    if not isinstance(delta, dict):
        return next_state
    grid = delta.get("grid")
    if isinstance(grid, dict):
        next_state.grid = GridSpec.from_dict(grid)

    def _cell_apply(section_name: str, target: Dict[CellKey, Any], parser) -> None:
        section = delta.get(section_name) if isinstance(delta.get(section_name), dict) else {}
        for item in section.get("upserts") if isinstance(section.get("upserts"), list) else []:
            parsed = parser(item)
            if parsed is None:
                continue
            target[parsed.key] = parsed
        for item in section.get("removals") if isinstance(section.get("removals"), list) else []:
            if not isinstance(item, dict):
                continue
            key = (_normalize_int(item.get("col")), _normalize_int(item.get("row")))
            target.pop(key, None)

    _cell_apply("terrain_cells", next_state.terrain_cells, TerrainCell.from_dict)
    _cell_apply("elevation_cells", next_state.elevation_cells, ElevationCell.from_dict)

    obstacle_section = delta.get("obstacles") if isinstance(delta.get("obstacles"), dict) else {}
    for item in obstacle_section.get("upserts") if isinstance(obstacle_section.get("upserts"), list) else []:
        if not isinstance(item, dict):
            continue
        key = (_normalize_int(item.get("col")), _normalize_int(item.get("row")))
        next_state.obstacles[key] = True
    for item in obstacle_section.get("removals") if isinstance(obstacle_section.get("removals"), list) else []:
        if not isinstance(item, dict):
            continue
        next_state.obstacles.pop((_normalize_int(item.get("col")), _normalize_int(item.get("row"))), None)

    def _entity_apply(section_name: str, target: Dict[str, Any], parser, id_key: str) -> None:
        section = delta.get(section_name) if isinstance(delta.get(section_name), dict) else {}
        for item in section.get("upserts") if isinstance(section.get("upserts"), list) else []:
            parsed = parser(item)
            if parsed is None:
                continue
            target[str(getattr(parsed, id_key))] = parsed
        for item_id in section.get("removals") if isinstance(section.get("removals"), list) else []:
            target.pop(str(item_id), None)

    _entity_apply("features", next_state.features, MapFeature.from_dict, "feature_id")
    _entity_apply("hazards", next_state.hazards, MapHazard.from_dict, "hazard_id")
    _entity_apply("structures", next_state.structures, MapStructure.from_dict, "structure_id")

    token_section = delta.get("tokens") if isinstance(delta.get("tokens"), dict) else {}
    for item in token_section.get("upserts") if isinstance(token_section.get("upserts"), list) else []:
        if not isinstance(item, dict):
            continue
        cid = _normalize_int(item.get("cid"), 0)
        if cid <= 0:
            continue
        next_state.token_positions[cid] = (_normalize_int(item.get("col")), _normalize_int(item.get("row")))
    for item in token_section.get("removals") if isinstance(token_section.get("removals"), list) else []:
        if not isinstance(item, dict):
            continue
        next_state.token_positions.pop(_normalize_int(item.get("cid"), 0), None)

    aoe_section = delta.get("aoes") if isinstance(delta.get("aoes"), dict) else {}
    for item in aoe_section.get("upserts") if isinstance(aoe_section.get("upserts"), list) else []:
        if not isinstance(item, dict):
            continue
        aid = _normalize_int(item.get("aid"), 0)
        if aid <= 0:
            continue
        payload = dict(item)
        payload.pop("aid", None)
        next_state.aoes[aid] = payload
    for aid in aoe_section.get("removals") if isinstance(aoe_section.get("removals"), list) else []:
        try:
            next_state.aoes.pop(int(aid), None)
        except Exception:
            continue

    return next_state.normalized()
