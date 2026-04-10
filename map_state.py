from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple


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
            if key == (item.anchor_col, item.anchor_row) or key in set(item.occupied_cells):
                found.append(item)
        return found

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

    def movement_cost_for_step(self, from_col: int, from_row: int, to_col: int, to_row: int, base_cost: int) -> int:
        if self.blocks_movement(to_col, to_row):
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
