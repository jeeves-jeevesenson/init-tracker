"""Focused tests for the DM browser tactical map slice.

These tests lock the smallest browser-owned tactical encounter controls:
combined DM snapshots that include tactical map state plus DM-authenticated
move / place / facing routes. HTTP integration coverage is gated on
fastapi/httpx availability; direct helper and HTML-surface tests still run in
minimal environments.
"""
import threading
import types
import unittest
from pathlib import Path
from unittest import mock

try:
    import httpx  # noqa: F401  (required by fastapi.testclient)
    from fastapi.testclient import TestClient

    _HTTP_AVAILABLE = True
except Exception:
    TestClient = None  # type: ignore[assignment]
    _HTTP_AVAILABLE = False

import dnd_initative_tracker as tracker_mod

_DM_HTML_PATH = Path(__file__).resolve().parent.parent / "assets" / "web" / "dm" / "index.html"


class _TacticalAppStub:
    """Minimal tracker stand-in for DM tactical route tests."""

    def __init__(self) -> None:
        self.round_num = 2
        self.turn_num = 1
        self.current_cid = 1
        self.in_combat = True
        self.map_cols = 12
        self.map_rows = 8
        self._name_role_memory = {"Aelar": "pc", "Goblin": "enemy"}
        self.positions = {1: (1, 1), 2: (4, 2)}
        self.facings = {1: 0, 2: 180}
        self.move_calls: list = []
        self.place_calls: list = []
        self.facing_calls: list = []
        self.obstacle_calls: list = []
        self.terrain_calls: list = []
        self.hazard_upsert_calls: list = []
        self.hazard_remove_calls: list = []
        self.feature_upsert_calls: list = []
        self.feature_remove_calls: list = []
        self.structure_upsert_calls: list = []
        self.structure_move_calls: list = []
        self.structure_remove_calls: list = []
        self.elevation_calls: list = []
        self.background_asset_list_calls = 0
        self.background_upsert_calls: list = []
        self.background_remove_calls: list = []
        self.aoe_create_calls: list = []
        self.aoe_move_calls: list = []
        self.aoe_remove_calls: list = []
        self.auras_overlay_calls: list = []
        self.map_new_calls: list = []
        self.map_settings_calls: list = []
        self.broadcast_calls = 0
        self.obstacles = {(3, 3)}
        self.rough_cells = {
            (6, 5): {"col": 6, "row": 5, "movement_type": "ground", "is_rough": True, "color": "#705040"}
        }
        self.hazards = {
            "hazard_1": {"id": "hazard_1", "col": 7, "row": 1, "kind": "spikes", "payload": {}}
        }
        self.next_hazard_id = 2
        self.features = {
            "feature_1": {"id": "feature_1", "col": 2, "row": 6, "kind": "brazier", "payload": {}}
        }
        self.next_feature_id = 2
        self.structures = {
            "ship_1": {
                "id": "ship_1",
                "anchor_col": 0,
                "anchor_row": 7,
                "occupied_cells": [{"col": 0, "row": 7}, {"col": 1, "row": 7}],
                "kind": "ship_hull",
                "payload": {},
            }
        }
        self.next_structure_id = 2
        self.elevation_cells = {(3, 4): {"col": 3, "row": 4, "elevation": 10.0}}
        self.background_assets = [
            {"path": "/assets/maps/ship_deck.webp", "label": "maps/ship_deck.webp"},
            {"path": "/assets/maps/cavern.png", "label": "maps/cavern.png"},
        ]
        self.background_layers = [
            {
                "bid": 1,
                "path": "/home/jeeves/src/init-tracker/assets/maps/ship_deck.webp",
                "x": 0.0,
                "y": 0.0,
                "scale_pct": 100.0,
                "trans_pct": 0.0,
                "locked": False,
            }
        ]
        self.next_background_id = 2
        self.aoes = {
            11: {"aid": 11, "kind": "circle", "name": "Cloudkill", "cx": 4.0, "cy": 2.0, "radius_sq": 4.0}
        }
        self.next_aoe_id = 12
        self.auras_enabled = True
        self.combatants = {
            1: types.SimpleNamespace(
                cid=1,
                name="Aelar",
                hp=27,
                max_hp=27,
                temp_hp=0,
                ac=16,
                initiative=14,
                is_pc=True,
                condition_stacks=[],
            ),
            2: types.SimpleNamespace(
                cid=2,
                name="Goblin",
                hp=7,
                max_hp=7,
                temp_hp=0,
                ac=13,
                initiative=12,
                is_pc=False,
                condition_stacks=[],
            ),
        }

    def _display_order(self):
        return [self.combatants[cid] for cid in sorted(self.combatants.keys())]

    def _peek_next_turn_cid(self, current_cid):
        ordered = [int(c.cid) for c in self._display_order()]
        if current_cid not in ordered:
            return ordered[0] if ordered else None
        idx = ordered.index(int(current_cid))
        return ordered[(idx + 1) % len(ordered)] if ordered else None

    def _lan_battle_log_lines(self, limit=30):
        return ["Aelar advances on the goblin."][: max(0, int(limit or 0))]

    def _oplog(self, *_args, **_kwargs):
        return None

    def _lan_force_state_broadcast(self):
        self.broadcast_calls += 1

    def _lan_pcs(self):
        return []

    def after(self, *_args, **_kwargs):
        return None

    def _dm_tactical_snapshot(self):
        units = []
        for cid in sorted(self.combatants.keys()):
            combatant = self.combatants[cid]
            col, row = self.positions.get(int(cid), (0, 0))
            role = "pc" if bool(getattr(combatant, "is_pc", False)) else "enemy"
            units.append(
                {
                    "cid": int(cid),
                    "name": str(getattr(combatant, "name", "")),
                    "role": role,
                    "ally": role != "enemy",
                    "hp": int(getattr(combatant, "hp", 0) or 0),
                    "max_hp": int(getattr(combatant, "max_hp", 0) or 0),
                    "facing_deg": int(self.facings.get(int(cid), 0)),
                    "pos": {"col": int(col), "row": int(row)},
                }
            )
        return {
            "grid": {"cols": int(self.map_cols), "rows": int(self.map_rows), "feet_per_square": 5.0},
            "obstacles": [{"col": int(col), "row": int(row)} for col, row in sorted(self.obstacles)],
            "rough_terrain": [dict(cell) for _key, cell in sorted(self.rough_cells.items())],
            "aoes": [dict(self.aoes[aid]) for aid in sorted(self.aoes.keys())],
            "map_state": {
                "grid": {"cols": int(self.map_cols), "rows": int(self.map_rows), "feet_per_square": 5.0},
                "presentation": {
                    "bg_images": [dict(layer) for layer in self.background_layers],
                    "next_bg_id": int(self.next_background_id),
                    "auras_enabled": bool(self.auras_enabled),
                },
            },
            "features": [dict(self.features[fid]) for fid in sorted(self.features.keys())],
            "hazards": [dict(self.hazards[hid]) for hid in sorted(self.hazards.keys())],
            "structures": [dict(self.structures[sid]) for sid in sorted(self.structures.keys())],
            "elevation_cells": [dict(self.elevation_cells[key]) for key in sorted(self.elevation_cells.keys())],
            "units": units,
            "active_cid": self.current_cid,
            "up_next_cid": self._peek_next_turn_cid(self.current_cid),
            "round_num": self.round_num,
            "turn_order": [1, 2],
            "boarding_links": [],
            "active_boarding_links": [],
            "ships": [],
            "auras_enabled": bool(self.auras_enabled),
        }

    def _lan_snapshot(self, *_, **__):
        snap = self._dm_tactical_snapshot()
        snap["spell_presets"] = []
        return snap

    def _occupied_by_other(self, cid: int, col: int, row: int) -> bool:
        for other_cid, pos in self.positions.items():
            if int(other_cid) == int(cid):
                continue
            if (int(pos[0]), int(pos[1])) == (int(col), int(row)):
                return True
        return False

    def _dm_move_combatant_on_map(self, cid: int, col: int, row: int):
        self.move_calls.append({"cid": int(cid), "col": int(col), "row": int(row)})
        if cid not in self.combatants:
            return {"ok": False, "error": "Combatant not found."}
        if not (0 <= int(col) < int(self.map_cols) and 0 <= int(row) < int(self.map_rows)):
            return {"ok": False, "error": "Off the map, matey."}
        if self._occupied_by_other(cid, col, row):
            return {"ok": False, "error": "Destination is occupied."}
        self.positions[int(cid)] = (int(col), int(row))
        self._lan_force_state_broadcast()
        return {"ok": True, "cid": int(cid), "col": int(col), "row": int(row), "spent_ft": 10}

    def _dm_place_combatant_on_map(self, cid: int, col: int, row: int):
        self.place_calls.append({"cid": int(cid), "col": int(col), "row": int(row)})
        if cid not in self.combatants:
            return {"ok": False, "error": "Combatant not found."}
        if not (0 <= int(col) < int(self.map_cols) and 0 <= int(row) < int(self.map_rows)):
            return {"ok": False, "error": "Destination is out of map bounds."}
        if self._occupied_by_other(cid, col, row):
            return {"ok": False, "error": "Destination is occupied."}
        self.positions[int(cid)] = (int(col), int(row))
        self._lan_force_state_broadcast()
        return {"ok": True, "cid": int(cid), "col": int(col), "row": int(row)}

    def _dm_set_combatant_facing(self, cid: int, facing_deg: int):
        self.facing_calls.append({"cid": int(cid), "facing_deg": int(facing_deg)})
        if cid not in self.combatants:
            return {"ok": False, "error": "Combatant not found."}
        self.facings[int(cid)] = int(facing_deg) % 360
        self._lan_force_state_broadcast()
        return {"ok": True, "cid": int(cid), "facing_deg": int(facing_deg) % 360}

    def _dm_set_obstacle_on_map(self, col: int, row: int, blocked: bool):
        self.obstacle_calls.append({"col": int(col), "row": int(row), "blocked": bool(blocked)})
        if not (0 <= int(col) < int(self.map_cols) and 0 <= int(row) < int(self.map_rows)):
            return {"ok": False, "error": "Cell out of bounds."}
        if blocked:
            self.obstacles.add((int(col), int(row)))
        else:
            self.obstacles.discard((int(col), int(row)))
        self._lan_force_state_broadcast()
        return {"ok": True, "col": int(col), "row": int(row), "blocked": bool(blocked)}

    def _dm_set_terrain_on_map(
        self,
        col: int,
        row: int,
        *,
        is_rough: bool,
        movement_type: str = "ground",
        color: str = None,
        label: str = None,
    ):
        self.terrain_calls.append(
            {
                "col": int(col),
                "row": int(row),
                "is_rough": bool(is_rough),
                "movement_type": str(movement_type),
            }
        )
        if not (0 <= int(col) < int(self.map_cols) and 0 <= int(row) < int(self.map_rows)):
            return {"ok": False, "error": "Cell out of bounds."}
        key = (int(col), int(row))
        if bool(is_rough):
            move_type = "water" if str(movement_type).strip().lower() == "water" else "ground"
            default_color = "#4aa3df" if move_type == "water" else "#8d6e63"
            self.rough_cells[key] = {
                "col": int(col),
                "row": int(row),
                "movement_type": move_type,
                "is_rough": True,
                "color": str(color or default_color),
                "label": str(label or ""),
            }
        else:
            self.rough_cells.pop(key, None)
            move_type = "ground"
        self._lan_force_state_broadcast()
        return {"ok": True, "col": int(col), "row": int(row), "is_rough": bool(is_rough), "movement_type": move_type}

    def _dm_upsert_hazard_on_map(
        self,
        *,
        col: int,
        row: int,
        hazard_id: str = None,
        kind: str = "hazard",
        tactical_preset_id: str = None,
        count=None,
        name: str = None,
        payload=None,
    ):
        _ = count
        self.hazard_upsert_calls.append(
            {
                "col": int(col),
                "row": int(row),
                "hazard_id": str(hazard_id or ""),
                "kind": str(kind),
                "tactical_preset_id": str(tactical_preset_id or ""),
            }
        )
        if not (0 <= int(col) < int(self.map_cols) and 0 <= int(row) < int(self.map_rows)):
            return {"ok": False, "error": "Cell out of bounds."}
        hid = str(hazard_id or "").strip()
        if not hid:
            hid = f"hazard_{self.next_hazard_id}"
            self.next_hazard_id += 1
        preset_kind_map = {"fire": "fire", "smoke": "smoke", "oil": "grease"}
        effective_kind = preset_kind_map.get(str(tactical_preset_id or "").strip(), str(kind or "hazard"))
        hazard_payload = dict(payload if isinstance(payload, dict) else {})
        if tactical_preset_id:
            hazard_payload["tactical_preset_id"] = str(tactical_preset_id)
        if name:
            hazard_payload["name"] = str(name)
        entry = {
            "id": hid,
            "col": int(col),
            "row": int(row),
            "kind": str(effective_kind),
            "payload": hazard_payload,
        }
        self.hazards[hid] = entry
        self._lan_force_state_broadcast()
        return {"ok": True, "hazard_id": hid, "hazard": dict(entry)}

    def _dm_remove_hazard_on_map(self, hazard_id):
        self.hazard_remove_calls.append(str(hazard_id))
        key = str(hazard_id or "")
        if key not in self.hazards:
            return {"ok": False, "error": "Hazard not found."}
        self.hazards.pop(key, None)
        self._lan_force_state_broadcast()
        return {"ok": True, "hazard_id": key}

    def _dm_upsert_feature_on_map(
        self,
        *,
        col: int,
        row: int,
        feature_id: str = None,
        kind: str = "feature",
        tactical_preset_id: str = None,
        count=None,
        name: str = None,
        payload=None,
    ):
        _ = count
        self.feature_upsert_calls.append(
            {
                "col": int(col),
                "row": int(row),
                "feature_id": str(feature_id or ""),
                "kind": str(kind),
                "tactical_preset_id": str(tactical_preset_id or ""),
            }
        )
        if not (0 <= int(col) < int(self.map_cols) and 0 <= int(row) < int(self.map_rows)):
            return {"ok": False, "error": "Cell out of bounds."}
        fid = str(feature_id or "").strip()
        if not fid:
            fid = f"feature_{self.next_feature_id}"
            self.next_feature_id += 1
        preset_kind_map = {"crate": "crate", "pillar": "pillar", "brazier": "brazier"}
        effective_kind = preset_kind_map.get(str(tactical_preset_id or "").strip(), str(kind or "feature"))
        feature_payload = dict(payload if isinstance(payload, dict) else {})
        if tactical_preset_id:
            feature_payload["tactical_preset_id"] = str(tactical_preset_id)
        if name:
            feature_payload["name"] = str(name)
        entry = {
            "id": fid,
            "col": int(col),
            "row": int(row),
            "kind": str(effective_kind),
            "payload": feature_payload,
        }
        self.features[fid] = entry
        self._lan_force_state_broadcast()
        return {"ok": True, "feature_id": fid, "feature": dict(entry)}

    def _dm_remove_feature_on_map(self, feature_id):
        self.feature_remove_calls.append(str(feature_id))
        key = str(feature_id or "").strip()
        if key not in self.features:
            return {"ok": False, "error": "Feature not found."}
        self.features.pop(key, None)
        self._lan_force_state_broadcast()
        return {"ok": True, "feature_id": key}

    def _dm_upsert_structure_on_map(
        self,
        *,
        anchor_col: int,
        anchor_row: int,
        structure_id: str = None,
        kind: str = "structure",
        tactical_preset_id: str = None,
        width_cells=None,
        height_cells=None,
        occupied_offsets=None,
        name: str = None,
        payload=None,
    ):
        _ = occupied_offsets
        self.structure_upsert_calls.append(
            {
                "anchor_col": int(anchor_col),
                "anchor_row": int(anchor_row),
                "structure_id": str(structure_id or ""),
                "kind": str(kind),
                "tactical_preset_id": str(tactical_preset_id or ""),
            }
        )
        if not (0 <= int(anchor_col) < int(self.map_cols) and 0 <= int(anchor_row) < int(self.map_rows)):
            return {"ok": False, "error": "Cell out of bounds."}
        sid = str(structure_id or "").strip()
        if not sid:
            sid = f"structure_{self.next_structure_id}"
            self.next_structure_id += 1
        width = max(1, int(width_cells or 1))
        height = max(1, int(height_cells or 1))
        occupied_cells = []
        for row_offset in range(height):
            for col_offset in range(width):
                occupied_cells.append({"col": int(anchor_col) + col_offset, "row": int(anchor_row) + row_offset})
        structure_payload = dict(payload if isinstance(payload, dict) else {})
        if tactical_preset_id:
            structure_payload["tactical_preset_id"] = str(tactical_preset_id)
        if name:
            structure_payload["name"] = str(name)
        entry = {
            "id": sid,
            "anchor_col": int(anchor_col),
            "anchor_row": int(anchor_row),
            "occupied_cells": occupied_cells,
            "kind": str(kind or "structure"),
            "payload": structure_payload,
        }
        self.structures[sid] = entry
        self._lan_force_state_broadcast()
        return {"ok": True, "structure_id": sid, "structure": dict(entry)}

    def _dm_move_structure_on_map(self, structure_id, anchor_col: int, anchor_row: int):
        self.structure_move_calls.append(
            {"structure_id": str(structure_id), "anchor_col": int(anchor_col), "anchor_row": int(anchor_row)}
        )
        sid = str(structure_id or "").strip()
        if sid not in self.structures:
            return {"ok": False, "error": "Structure not found."}
        if not (0 <= int(anchor_col) < int(self.map_cols) and 0 <= int(anchor_row) < int(self.map_rows)):
            return {"ok": False, "error": "Cell out of bounds."}
        existing = dict(self.structures[sid])
        old_anchor_col = int(existing.get("anchor_col", 0))
        old_anchor_row = int(existing.get("anchor_row", 0))
        dc = int(anchor_col) - old_anchor_col
        dr = int(anchor_row) - old_anchor_row
        shifted_cells = []
        for cell in list(existing.get("occupied_cells") if isinstance(existing.get("occupied_cells"), list) else []):
            shifted_cells.append({"col": int(cell.get("col", 0)) + dc, "row": int(cell.get("row", 0)) + dr})
        existing["anchor_col"] = int(anchor_col)
        existing["anchor_row"] = int(anchor_row)
        existing["occupied_cells"] = shifted_cells
        self.structures[sid] = existing
        self._lan_force_state_broadcast()
        return {"ok": True, "structure_id": sid, "anchor_col": int(anchor_col), "anchor_row": int(anchor_row), "structure": dict(existing)}

    def _dm_remove_structure_on_map(self, structure_id):
        self.structure_remove_calls.append(str(structure_id))
        sid = str(structure_id or "").strip()
        if sid not in self.structures:
            return {"ok": False, "error": "Structure not found."}
        self.structures.pop(sid, None)
        self._lan_force_state_broadcast()
        return {"ok": True, "structure_id": sid}

    def _dm_set_elevation_on_map(self, col: int, row: int, elevation):
        self.elevation_calls.append({"col": int(col), "row": int(row), "elevation": float(elevation)})
        if not (0 <= int(col) < int(self.map_cols) and 0 <= int(row) < int(self.map_rows)):
            return {"ok": False, "error": "Cell out of bounds."}
        self.elevation_cells[(int(col), int(row))] = {"col": int(col), "row": int(row), "elevation": float(elevation)}
        self._lan_force_state_broadcast()
        return {"ok": True, "col": int(col), "row": int(row), "elevation": float(elevation)}

    def _dm_list_background_assets(self):
        self.background_asset_list_calls += 1
        return [dict(item) for item in self.background_assets]

    def _dm_create_blank_map(self, *, cols=None, rows=None):
        next_cols = int(self.map_cols if cols is None else cols)
        next_rows = int(self.map_rows if rows is None else rows)
        if next_cols < 10 or next_cols > 1000:
            return {"ok": False, "error": "cols must be between 10 and 1000."}
        if next_rows < 10 or next_rows > 1000:
            return {"ok": False, "error": "rows must be between 10 and 1000."}
        self.map_new_calls.append({"cols": int(next_cols), "rows": int(next_rows)})
        self.map_cols = int(next_cols)
        self.map_rows = int(next_rows)
        self.obstacles = set()
        self.rough_cells = {}
        self.hazards = {}
        self.next_hazard_id = 1
        self.features = {}
        self.next_feature_id = 1
        self.structures = {}
        self.next_structure_id = 1
        self.elevation_cells = {}
        self.background_layers = []
        self.next_background_id = 1
        self.aoes = {}
        self.next_aoe_id = 1
        self.positions = {}
        self._lan_force_state_broadcast()
        return {"ok": True, "grid": {"cols": int(next_cols), "rows": int(next_rows), "feet_per_square": 5.0}}

    def _dm_set_map_grid_settings(self, *, cols=None, rows=None):
        next_cols = int(self.map_cols if cols is None else cols)
        next_rows = int(self.map_rows if rows is None else rows)
        if next_cols < 10 or next_cols > 1000:
            return {"ok": False, "error": "cols must be between 10 and 1000."}
        if next_rows < 10 or next_rows > 1000:
            return {"ok": False, "error": "rows must be between 10 and 1000."}
        self.map_settings_calls.append({"cols": int(next_cols), "rows": int(next_rows)})
        self.map_cols = int(next_cols)
        self.map_rows = int(next_rows)
        self._lan_force_state_broadcast()
        return {"ok": True, "grid": {"cols": int(next_cols), "rows": int(next_rows), "feet_per_square": 5.0}}

    def _dm_upsert_background_layer(
        self,
        *,
        asset_path,
        bid=None,
        x=0.0,
        y=0.0,
        scale_pct=100.0,
        trans_pct=0.0,
        locked=False,
    ):
        self.background_upsert_calls.append(
            {
                "asset_path": str(asset_path),
                "bid": bid,
                "x": float(x),
                "y": float(y),
                "scale_pct": float(scale_pct),
                "trans_pct": float(trans_pct),
                "locked": bool(locked),
            }
        )
        if bid is None:
            resolved_bid = int(self.next_background_id)
            self.next_background_id += 1
        else:
            resolved_bid = int(bid)
            self.next_background_id = max(int(self.next_background_id), resolved_bid + 1)
        existing_idx = next((idx for idx, item in enumerate(self.background_layers) if int(item.get("bid", 0)) == resolved_bid), None)
        entry = {
            "bid": int(resolved_bid),
            "path": str(asset_path),
            "x": float(x),
            "y": float(y),
            "scale_pct": float(scale_pct),
            "trans_pct": float(trans_pct),
            "locked": bool(locked),
            "asset_url": str(asset_path),
        }
        if existing_idx is None:
            self.background_layers.append(entry)
        else:
            self.background_layers[existing_idx] = entry
        self.background_layers.sort(key=lambda item: int(item.get("bid", 0)))
        self._lan_force_state_broadcast()
        return {"ok": True, "background": dict(entry)}

    def _dm_remove_background_layer(self, bid):
        self.background_remove_calls.append(int(bid))
        target = int(bid)
        before = len(self.background_layers)
        self.background_layers = [entry for entry in self.background_layers if int(entry.get("bid", 0)) != target]
        if len(self.background_layers) == before:
            return {"ok": False, "error": "Background layer not found."}
        self._lan_force_state_broadcast()
        return {"ok": True, "bid": int(target)}

    def _dm_create_aoe_on_map(self, payload):
        self.aoe_create_calls.append(dict(payload if isinstance(payload, dict) else {}))
        if not isinstance(payload, dict):
            return {"ok": False, "error": "Invalid payload."}
        aid = int(self.next_aoe_id)
        self.next_aoe_id += 1
        entry = {
            "aid": aid,
            "kind": str(payload.get("shape") or payload.get("kind") or "circle"),
            "name": str(payload.get("name") or f"AoE {aid}"),
            "cx": float(payload.get("cx")),
            "cy": float(payload.get("cy")),
        }
        self.aoes[aid] = entry
        self._lan_force_state_broadcast()
        return {"ok": True, "aid": aid, "aoe": dict(entry)}

    def _dm_move_aoe_on_map(self, aid: int, payload):
        self.aoe_move_calls.append({"aid": int(aid), "payload": dict(payload if isinstance(payload, dict) else {})})
        if int(aid) not in self.aoes:
            return {"ok": False, "error": "AoE not found."}
        if not isinstance(payload, dict):
            return {"ok": False, "error": "Invalid payload."}
        cx = payload.get("cx", payload.get("col"))
        cy = payload.get("cy", payload.get("row"))
        self.aoes[int(aid)]["cx"] = float(cx)
        self.aoes[int(aid)]["cy"] = float(cy)
        if payload.get("angle_deg") is not None:
            self.aoes[int(aid)]["angle_deg"] = float(payload.get("angle_deg"))
        self._lan_force_state_broadcast()
        return {"ok": True, "aid": int(aid), "aoe": dict(self.aoes[int(aid)])}

    def _dm_remove_aoe_on_map(self, aid: int):
        self.aoe_remove_calls.append(int(aid))
        if int(aid) not in self.aoes:
            return {"ok": False, "error": "AoE not found."}
        self.aoes.pop(int(aid), None)
        self._lan_force_state_broadcast()
        return {"ok": True, "aid": int(aid)}

    def _dm_set_auras_enabled(self, enabled: bool):
        self.auras_overlay_calls.append(bool(enabled))
        self.auras_enabled = bool(enabled)
        self._lan_force_state_broadcast()
        return {"ok": True, "enabled": bool(enabled)}

    def _dm_list_tactical_presets(self, *, categories=None):
        presets = [
            {"id": "fire", "display_name": "Fire Patch", "category": "hazard", "kind": "fire", "summary": "Fire"},
            {"id": "smoke", "display_name": "Smoke Patch", "category": "hazard", "kind": "smoke", "summary": "Smoke"},
            {"id": "oil", "display_name": "Oil / Grease", "category": "hazard", "kind": "grease", "summary": "Oil"},
            {"id": "crate", "display_name": "Crate Stack", "category": "feature", "kind": "crate", "summary": "Cover"},
            {"id": "pillar", "display_name": "Stone Pillar", "category": "feature", "kind": "pillar", "summary": "Column"},
            {"id": "wagon", "display_name": "Wagon", "category": "structure", "kind": "wagon", "summary": "2x1 blocker"},
        ]
        allowed = {str(entry).strip().lower() for entry in categories} if isinstance(categories, (set, list, tuple)) else None
        if allowed:
            return [entry for entry in presets if str(entry.get("category") or "").strip().lower() in allowed]
        return presets


@unittest.skipUnless(_HTTP_AVAILABLE, "fastapi/httpx not available in this environment")
class DmTacticalMapRoutesTests(unittest.TestCase):
    def _build_lan_controller(self, admin_password_configured: bool = False):
        lan = object.__new__(tracker_mod.LanController)
        lan._tracker = _TacticalAppStub()
        lan.cfg = types.SimpleNamespace(
            host="127.0.0.1",
            port=0,
            vapid_public_key=None,
            allowlist=[],
            denylist=[],
            admin_password=None,
        )
        lan._server_thread = None
        lan._fastapi_app = None
        lan._polling = False
        lan._cached_snapshot = {}
        lan._cached_pcs = []
        lan._clients_lock = threading.RLock()
        lan._dm_ws_clients = {}
        lan._actions = None
        lan._loop = None
        lan._best_lan_url = lambda: "http://127.0.0.1:0"
        lan._tick = lambda: None
        lan._append_lan_log = lambda *_args, **_kwargs: None
        lan._init_admin_auth = lambda: None
        lan._admin_password_hash = b"configured" if admin_password_configured else None
        lan._admin_password_salt = b"salt"
        lan._admin_tokens = {}
        lan._admin_token_ttl_seconds = 900
        lan._save_push_subscription = lambda *_args, **_kwargs: True
        lan._admin_password_matches = lambda password: password == "pw"
        lan._monster_choices_payload = lambda: []
        return lan

    def _build_client(self, admin_password_configured: bool = False):
        lan = self._build_lan_controller(admin_password_configured=admin_password_configured)
        with mock.patch("threading.Thread.start", return_value=None):
            lan.start(quiet=True)
        return TestClient(lan._fastapi_app), lan

    def _auth_headers(self, client, lan) -> dict:
        if not lan._admin_password_hash:
            return {}
        login = client.post("/api/admin/login", json={"password": "pw"})
        self.assertEqual(200, login.status_code)
        token = login.json()["token"]
        return {"Authorization": f"Bearer {token}"}

    def test_dm_combat_snapshot_includes_tactical_map(self):
        client, _lan = self._build_client()
        response = client.get("/api/dm/combat")
        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertTrue(payload["in_combat"])
        self.assertIn("tactical_map", payload)
        self.assertEqual(12, payload["tactical_map"]["grid"]["cols"])
        self.assertEqual({"col": 1, "row": 1}, payload["tactical_map"]["units"][0]["pos"])

    def test_map_new_route_initializes_blank_map(self):
        client, lan = self._build_client()
        response = client.post("/api/dm/map/new", json={"cols": 30, "rows": 18})
        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual([{"cols": 30, "rows": 18}], lan._tracker.map_new_calls)
        self.assertEqual(30, payload["snapshot"]["tactical_map"]["grid"]["cols"])
        self.assertEqual(18, payload["snapshot"]["tactical_map"]["grid"]["rows"])
        self.assertEqual([], payload["snapshot"]["tactical_map"]["hazards"])
        self.assertEqual([], payload["snapshot"]["tactical_map"]["features"])

    def test_map_settings_route_updates_grid_dimensions(self):
        client, lan = self._build_client()
        response = client.post("/api/dm/map/settings", json={"cols": 16, "rows": 11})
        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual([{"cols": 16, "rows": 11}], lan._tracker.map_settings_calls)
        self.assertEqual(16, payload["snapshot"]["tactical_map"]["grid"]["cols"])
        self.assertEqual(11, payload["snapshot"]["tactical_map"]["grid"]["rows"])

    def test_move_route_updates_position_and_returns_combined_snapshot(self):
        client, lan = self._build_client()
        response = client.post("/api/dm/map/combatants/1/move", json={"col": 2, "row": 3})
        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(10, payload["spent_ft"])
        self.assertEqual([{"cid": 1, "col": 2, "row": 3}], lan._tracker.move_calls)
        self.assertEqual({"col": 2, "row": 3}, payload["snapshot"]["tactical_map"]["units"][0]["pos"])

    def test_place_route_repositions_token_for_setup(self):
        client, lan = self._build_client()
        response = client.post("/api/dm/map/combatants/2/place", json={"col": 9, "row": 6})
        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual([{"cid": 2, "col": 9, "row": 6}], lan._tracker.place_calls)
        goblin = next(unit for unit in payload["snapshot"]["tactical_map"]["units"] if unit["cid"] == 2)
        self.assertEqual({"col": 9, "row": 6}, goblin["pos"])

    def test_set_facing_updates_snapshot(self):
        client, lan = self._build_client()
        response = client.post("/api/dm/map/combatants/1/facing", json={"facing_deg": 270})
        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual([{"cid": 1, "facing_deg": 270}], lan._tracker.facing_calls)
        aelar = next(unit for unit in payload["snapshot"]["tactical_map"]["units"] if unit["cid"] == 1)
        self.assertEqual(270, aelar["facing_deg"])

    def test_cell_obstacle_and_terrain_routes_update_tactical_snapshot(self):
        client, lan = self._build_client()
        obstacle = client.post("/api/dm/map/obstacles/cell", json={"col": 5, "row": 4, "blocked": True})
        self.assertEqual(200, obstacle.status_code)
        obstacle_payload = obstacle.json()
        self.assertTrue(obstacle_payload["ok"])
        self.assertIn({"col": 5, "row": 4, "blocked": True}, lan._tracker.obstacle_calls)
        self.assertIn({"col": 5, "row": 4}, obstacle_payload["snapshot"]["tactical_map"]["obstacles"])

        terrain = client.post(
            "/api/dm/map/terrain/cell",
            json={"col": 5, "row": 4, "is_rough": True, "movement_type": "water"},
        )
        self.assertEqual(200, terrain.status_code)
        terrain_payload = terrain.json()
        self.assertTrue(terrain_payload["ok"])
        self.assertIn({"col": 5, "row": 4, "is_rough": True, "movement_type": "water"}, lan._tracker.terrain_calls)
        rough_cells = terrain_payload["snapshot"]["tactical_map"]["rough_terrain"]
        placed = next(cell for cell in rough_cells if cell["col"] == 5 and cell["row"] == 4)
        self.assertEqual("water", placed["movement_type"])

    def test_hazard_routes_place_and_remove_entries(self):
        client, lan = self._build_client()
        create = client.post(
            "/api/dm/map/hazards",
            json={"col": 8, "row": 3, "tactical_preset_id": "fire", "name": "Lantern Fire"},
        )
        self.assertEqual(200, create.status_code)
        create_payload = create.json()
        self.assertTrue(create_payload["ok"])
        hazard_id = create_payload["hazard_id"]
        self.assertTrue(hazard_id.startswith("hazard_"))
        self.assertIn("fire", [entry["tactical_preset_id"] for entry in lan._tracker.hazard_upsert_calls if entry["tactical_preset_id"]])
        hazards = create_payload["snapshot"]["tactical_map"]["hazards"]
        created = next(item for item in hazards if item["id"] == hazard_id)
        self.assertEqual(8, created["col"])
        self.assertEqual(3, created["row"])

        remove = client.delete(f"/api/dm/map/hazards/{hazard_id}")
        self.assertEqual(200, remove.status_code)
        remove_payload = remove.json()
        self.assertTrue(remove_payload["ok"])
        self.assertIn(hazard_id, lan._tracker.hazard_remove_calls)
        remaining = remove_payload["snapshot"]["tactical_map"]["hazards"]
        self.assertFalse(any(item["id"] == hazard_id for item in remaining))

    def test_feature_structure_and_elevation_routes_update_tactical_snapshot(self):
        client, lan = self._build_client()
        feature_create = client.post(
            "/api/dm/map/features",
            json={"col": 5, "row": 1, "tactical_preset_id": "crate", "name": "Cargo Pile"},
        )
        self.assertEqual(200, feature_create.status_code)
        feature_payload = feature_create.json()
        self.assertTrue(feature_payload["ok"])
        feature_id = str(feature_payload["feature_id"])
        self.assertTrue(any(entry["tactical_preset_id"] == "crate" for entry in lan._tracker.feature_upsert_calls))
        placed_feature = next(item for item in feature_payload["snapshot"]["tactical_map"]["features"] if item["id"] == feature_id)
        self.assertEqual(5, placed_feature["col"])
        self.assertEqual(1, placed_feature["row"])

        structure_create = client.post(
            "/api/dm/map/structures",
            json={
                "anchor_col": 4,
                "anchor_row": 2,
                "tactical_preset_id": "wagon",
                "width_cells": 2,
                "height_cells": 1,
                "name": "Supply Wagon",
            },
        )
        self.assertEqual(200, structure_create.status_code)
        structure_payload = structure_create.json()
        self.assertTrue(structure_payload["ok"])
        structure_id = str(structure_payload["structure_id"])
        placed_structure = next(item for item in structure_payload["snapshot"]["tactical_map"]["structures"] if item["id"] == structure_id)
        self.assertEqual(4, placed_structure["anchor_col"])
        self.assertEqual(2, placed_structure["anchor_row"])

        structure_move = client.post(
            f"/api/dm/map/structures/{structure_id}/move",
            json={"anchor_col": 6, "anchor_row": 3},
        )
        self.assertEqual(200, structure_move.status_code)
        moved_payload = structure_move.json()
        moved_structure = next(item for item in moved_payload["snapshot"]["tactical_map"]["structures"] if item["id"] == structure_id)
        self.assertEqual(6, moved_structure["anchor_col"])
        self.assertEqual(3, moved_structure["anchor_row"])
        self.assertTrue(any(entry["structure_id"] == structure_id for entry in lan._tracker.structure_move_calls))

        elevation_set = client.post("/api/dm/map/elevation/cell", json={"col": 6, "row": 3, "elevation": 15})
        self.assertEqual(200, elevation_set.status_code)
        elevation_payload = elevation_set.json()
        self.assertTrue(elevation_payload["ok"])
        elevation_cell = next(
            item
            for item in elevation_payload["snapshot"]["tactical_map"]["elevation_cells"]
            if item["col"] == 6 and item["row"] == 3
        )
        self.assertEqual(15.0, elevation_cell["elevation"])

    def test_background_asset_and_layer_routes(self):
        client, lan = self._build_client()
        assets = client.get("/api/dm/map/backgrounds/assets")
        self.assertEqual(200, assets.status_code)
        assets_payload = assets.json()
        self.assertTrue(assets_payload["ok"])
        self.assertTrue(any(str(item.get("path", "")).endswith("ship_deck.webp") for item in assets_payload["assets"]))
        self.assertEqual(1, lan._tracker.background_asset_list_calls)

        upsert = client.post(
            "/api/dm/map/backgrounds",
            json={
                "asset_path": "/assets/maps/cavern.png",
                "x": 8,
                "y": -4,
                "scale_pct": 140,
                "trans_pct": 25,
                "locked": True,
            },
        )
        self.assertEqual(200, upsert.status_code)
        upsert_payload = upsert.json()
        self.assertTrue(upsert_payload["ok"])
        created_bid = int(upsert_payload["background"]["bid"])
        bg_layers = upsert_payload["snapshot"]["tactical_map"]["map_state"]["presentation"]["bg_images"]
        self.assertTrue(any(int(layer["bid"]) == created_bid for layer in bg_layers))

        remove = client.delete(f"/api/dm/map/backgrounds/{created_bid}")
        self.assertEqual(200, remove.status_code)
        remove_payload = remove.json()
        self.assertTrue(remove_payload["ok"])
        remaining_layers = remove_payload["snapshot"]["tactical_map"]["map_state"]["presentation"]["bg_images"]
        self.assertFalse(any(int(layer["bid"]) == created_bid for layer in remaining_layers))
        self.assertIn(created_bid, lan._tracker.background_remove_calls)

    def test_aoe_routes_place_move_and_remove_effects(self):
        client, lan = self._build_client()
        create = client.post(
            "/api/dm/map/aoes",
            json={"shape": "circle", "cx": 2, "cy": 2, "radius_ft": 20, "name": "Web"},
        )
        self.assertEqual(200, create.status_code)
        create_payload = create.json()
        self.assertTrue(create_payload["ok"])
        aid = int(create_payload["aid"])
        self.assertTrue(any(int(item["aid"]) == aid for item in create_payload["snapshot"]["tactical_map"]["aoes"]))
        self.assertEqual("circle", create_payload["aoe"]["kind"])
        self.assertEqual("Web", create_payload["aoe"]["name"])

        move = client.post(f"/api/dm/map/aoes/{aid}/move", json={"col": 6, "row": 4, "angle_deg": 90})
        self.assertEqual(200, move.status_code)
        move_payload = move.json()
        self.assertTrue(move_payload["ok"])
        moved = next(item for item in move_payload["snapshot"]["tactical_map"]["aoes"] if int(item["aid"]) == aid)
        self.assertEqual(6.0, moved["cx"])
        self.assertEqual(4.0, moved["cy"])
        self.assertEqual(90.0, moved["angle_deg"])
        self.assertTrue(any(entry["aid"] == aid for entry in lan._tracker.aoe_move_calls))

        remove = client.delete(f"/api/dm/map/aoes/{aid}")
        self.assertEqual(200, remove.status_code)
        remove_payload = remove.json()
        self.assertTrue(remove_payload["ok"])
        self.assertIn(aid, lan._tracker.aoe_remove_calls)
        self.assertFalse(any(int(item["aid"]) == aid for item in remove_payload["snapshot"]["tactical_map"]["aoes"]))

    def test_map_overlay_and_preset_routes(self):
        client, lan = self._build_client()
        presets = client.get("/api/dm/map/tactical-presets")
        self.assertEqual(200, presets.status_code)
        presets_payload = presets.json()
        self.assertTrue(presets_payload["ok"])
        self.assertTrue(any(entry["id"] == "fire" for entry in presets_payload["presets"]))
        self.assertTrue(any(entry["id"] == "crate" for entry in presets_payload["presets"]))
        self.assertTrue(any(entry["id"] == "wagon" for entry in presets_payload["presets"]))

        overlays = client.post("/api/dm/map/overlays/auras", json={"enabled": False})
        self.assertEqual(200, overlays.status_code)
        overlays_payload = overlays.json()
        self.assertTrue(overlays_payload["ok"])
        self.assertFalse(overlays_payload["enabled"])
        self.assertEqual([False], lan._tracker.auras_overlay_calls)
        self.assertFalse(overlays_payload["snapshot"]["tactical_map"]["auras_enabled"])

    def test_map_routes_require_admin_when_password_configured(self):
        client, lan = self._build_client(admin_password_configured=True)
        unauth_new = client.post("/api/dm/map/new", json={"cols": 20, "rows": 20})
        unauth_settings = client.post("/api/dm/map/settings", json={"cols": 22, "rows": 18})
        unauth_obstacle = client.post("/api/dm/map/obstacles/cell", json={"col": 2, "row": 2, "blocked": True})
        self.assertEqual(401, unauth_new.status_code)
        self.assertEqual(401, unauth_settings.status_code)
        self.assertEqual(401, unauth_obstacle.status_code)
        headers = self._auth_headers(client, lan)
        auth_new = client.post("/api/dm/map/new", json={"cols": 20, "rows": 20}, headers=headers)
        auth_settings = client.post("/api/dm/map/settings", json={"cols": 22, "rows": 18}, headers=headers)
        auth_obstacle = client.post("/api/dm/map/obstacles/cell", json={"col": 2, "row": 2, "blocked": True}, headers=headers)
        self.assertEqual(200, auth_new.status_code)
        self.assertEqual(200, auth_settings.status_code)
        self.assertEqual(200, auth_obstacle.status_code)


class _TrackerTacticalHarness:
    _capture_canonical_map_state = tracker_mod.InitiativeTracker._capture_canonical_map_state
    _apply_canonical_map_state = tracker_mod.InitiativeTracker._apply_canonical_map_state
    _mutate_canonical_map_state = tracker_mod.InitiativeTracker._mutate_canonical_map_state
    _next_map_entity_id = tracker_mod.InitiativeTracker._next_map_entity_id
    _normalize_tactical_entity_payload = tracker_mod.InitiativeTracker._normalize_tactical_entity_payload
    _upsert_map_feature = tracker_mod.InitiativeTracker._upsert_map_feature
    _remove_map_feature = tracker_mod.InitiativeTracker._remove_map_feature
    _upsert_map_structure = tracker_mod.InitiativeTracker._upsert_map_structure
    _remove_map_structure = tracker_mod.InitiativeTracker._remove_map_structure
    _set_map_elevation = tracker_mod.InitiativeTracker._set_map_elevation
    _dm_tactical_snapshot = tracker_mod.InitiativeTracker._dm_tactical_snapshot
    _dm_move_combatant_on_map = tracker_mod.InitiativeTracker._dm_move_combatant_on_map
    _dm_place_combatant_on_map = tracker_mod.InitiativeTracker._dm_place_combatant_on_map
    _dm_set_combatant_facing = tracker_mod.InitiativeTracker._dm_set_combatant_facing
    _dm_map_grid_bounds = tracker_mod.InitiativeTracker._dm_map_grid_bounds
    _dm_parse_grid_dimensions = tracker_mod.InitiativeTracker._dm_parse_grid_dimensions
    _dm_create_blank_map = tracker_mod.InitiativeTracker._dm_create_blank_map
    _dm_set_map_grid_settings = tracker_mod.InitiativeTracker._dm_set_map_grid_settings
    _dm_validate_map_cell = tracker_mod.InitiativeTracker._dm_validate_map_cell
    _dm_set_obstacle_on_map = tracker_mod.InitiativeTracker._dm_set_obstacle_on_map
    _dm_set_terrain_on_map = tracker_mod.InitiativeTracker._dm_set_terrain_on_map
    _dm_set_auras_enabled = tracker_mod.InitiativeTracker._dm_set_auras_enabled
    _dm_upsert_feature_on_map = tracker_mod.InitiativeTracker._dm_upsert_feature_on_map
    _dm_remove_feature_on_map = tracker_mod.InitiativeTracker._dm_remove_feature_on_map
    _dm_structure_offsets_from_payload = staticmethod(tracker_mod.InitiativeTracker._dm_structure_offsets_from_payload)
    _dm_upsert_structure_on_map = tracker_mod.InitiativeTracker._dm_upsert_structure_on_map
    _dm_move_structure_on_map = tracker_mod.InitiativeTracker._dm_move_structure_on_map
    _dm_remove_structure_on_map = tracker_mod.InitiativeTracker._dm_remove_structure_on_map
    _dm_set_elevation_on_map = tracker_mod.InitiativeTracker._dm_set_elevation_on_map
    _dm_resolve_background_asset_path = tracker_mod.InitiativeTracker._dm_resolve_background_asset_path
    _dm_upsert_background_layer = tracker_mod.InitiativeTracker._dm_upsert_background_layer
    _dm_remove_background_layer = tracker_mod.InitiativeTracker._dm_remove_background_layer
    _dm_list_background_assets = tracker_mod.InitiativeTracker._dm_list_background_assets
    _lan_tactical_entity_view = tracker_mod.InitiativeTracker._lan_tactical_entity_view
    _lan_asset_url_for_path = staticmethod(tracker_mod.InitiativeTracker._lan_asset_url_for_path)
    _normalize_facing_degrees = tracker_mod.InitiativeTracker._normalize_facing_degrees

    def __init__(self) -> None:
        self.combatants = {
            1: types.SimpleNamespace(cid=1, name="Aelar", rider_cid=None, mounted_by_cid=None, facing_deg=0),
        }
        self.positions = {1: (1, 1)}
        self._map_window = None
        self._lan_grid_cols = 10
        self._lan_grid_rows = 10
        self._lan_positions = dict(self.positions)
        self._lan_obstacles = {(4, 4)}
        self._lan_rough_terrain = {}
        self._lan_aoes = {}
        self._lan_next_aoe_id = 1
        self._lan_auras_enabled = True
        self._session_bg_images = []
        self._session_next_bg_id = 1
        self._map_state = tracker_mod.MapState.from_legacy(
            cols=10,
            rows=10,
            feet_per_square=5.0,
            positions=self._lan_positions,
            obstacles=self._lan_obstacles,
            rough_terrain=self._lan_rough_terrain,
            aoes=self._lan_aoes,
            presentation={"auras_enabled": True, "bg_images": [], "next_bg_id": 1},
        )
        self.broadcast_calls = 0
        self.move_calls: list = []
        self.log_messages: list = []
        self.rebuild_calls = 0
        self.synced_aoes: list = []
        self.tethered: list = []
        self.environment_triggers: list = []

    def _lan_snapshot(self, *_, **__):
        return {
            "grid": {"cols": 10, "rows": 10, "feet_per_square": 5.0},
            "obstacles": [{"col": 4, "row": 4}],
            "rough_terrain": [],
            "aoes": [],
            "map_state": {"cols": 10, "rows": 10},
            "features": [],
            "hazards": [],
            "structures": [],
            "elevation_cells": [],
            "units": [
                {
                    "cid": 1,
                    "name": "Aelar",
                    "role": "pc",
                    "ally": True,
                    "facing_deg": int(getattr(self.combatants[1], "facing_deg", 0)),
                    "pos": {"col": int(self.positions[1][0]), "row": int(self.positions[1][1])},
                }
            ],
            "active_cid": 1,
            "up_next_cid": None,
            "round_num": 1,
            "turn_order": [1],
            "boarding_links": [],
            "active_boarding_links": [],
            "ships": [],
            "auras_enabled": bool(self._lan_auras_enabled),
            "spell_presets": ["ignore me"],
        }

    def _lan_try_move(self, cid: int, col: int, row: int):
        self.move_calls.append({"cid": int(cid), "col": int(col), "row": int(row)})
        self.positions[int(cid)] = (int(col), int(row))
        return (True, "", 15)

    def _lan_force_state_broadcast(self):
        self.broadcast_calls += 1

    def _lan_live_map_data(self):
        return (10, 10, set(), {}, dict(self.positions))

    def _validate_relocation_destination(self, **_kwargs):
        return (True, "")

    def _lan_set_token_position(self, cid: int, col: int, row: int):
        self.positions[int(cid)] = (int(col), int(row))

    def _lan_sync_fixed_to_caster_aoes(self, cid: int):
        self.synced_aoes.append(int(cid))

    def _sync_owned_rotatable_aoes_with_facing(self, cid: int, facing_deg: int):
        self.synced_aoes.append((int(cid), int(facing_deg)))
        return True

    def _lan_handle_environment_triggers_for_moved_unit(self, cid: int, origin, destination):
        self.environment_triggers.append((int(cid), tuple(origin), tuple(destination)))

    def _enforce_johns_echo_tether(self, cid: int):
        self.tethered.append(int(cid))

    def _log(self, message: str, cid=None):
        self.log_messages.append({"message": str(message), "cid": cid})

    def _rebuild_table(self, scroll_to_current=True):
        self.rebuild_calls += 1


class DmTacticalHelperTests(unittest.TestCase):
    def test_dm_tactical_snapshot_projects_map_payload_without_static_lan_fields(self):
        app = _TrackerTacticalHarness()
        payload = app._dm_tactical_snapshot()
        self.assertEqual(10, payload["grid"]["cols"])
        self.assertEqual({"col": 1, "row": 1}, payload["units"][0]["pos"])
        self.assertNotIn("spell_presets", payload)

    def test_dm_tactical_snapshot_falls_back_to_map_state_grid(self):
        app = _TrackerTacticalHarness()
        app._lan_snapshot = lambda *_, **__: {
            "grid": None,
            "map_state": {"grid": {"cols": 14, "rows": 9, "feet_per_square": 5.0}},
            "units": [],
        }
        payload = app._dm_tactical_snapshot()
        self.assertEqual(14, payload["grid"]["cols"])
        self.assertEqual(9, payload["grid"]["rows"])

    def test_dm_move_combatant_on_map_routes_through_lan_move_and_broadcasts(self):
        app = _TrackerTacticalHarness()
        result = app._dm_move_combatant_on_map(1, 3, 2)
        self.assertTrue(result["ok"])
        self.assertEqual(15, result["spent_ft"])
        self.assertEqual((3, 2), app.positions[1])
        self.assertEqual([{"cid": 1, "col": 3, "row": 2}], app.move_calls)
        self.assertEqual(1, app.broadcast_calls)

    def test_dm_place_combatant_on_map_updates_position_and_logs(self):
        app = _TrackerTacticalHarness()
        result = app._dm_place_combatant_on_map(1, 5, 6)
        self.assertTrue(result["ok"])
        self.assertEqual((5, 6), app.positions[1])
        self.assertIn(1, app.synced_aoes)
        self.assertIn(1, app.tethered)
        self.assertEqual(1, app.broadcast_calls)
        self.assertTrue(any("placed on map" in entry["message"] for entry in app.log_messages))

    def test_dm_set_combatant_facing_normalizes_and_broadcasts(self):
        app = _TrackerTacticalHarness()
        result = app._dm_set_combatant_facing(1, 450)
        self.assertTrue(result["ok"])
        self.assertEqual(90, result["facing_deg"])
        self.assertEqual(90, getattr(app.combatants[1], "facing_deg"))
        self.assertEqual(1, app.broadcast_calls)

    def test_dm_set_obstacle_and_terrain_helpers_mutate_canonical_map_state(self):
        app = _TrackerTacticalHarness()
        obstacle_result = app._dm_set_obstacle_on_map(2, 3, True)
        self.assertTrue(obstacle_result["ok"])
        state_after_obstacle = app._capture_canonical_map_state(prefer_window=True).normalized()
        self.assertIn((2, 3), state_after_obstacle.obstacles)

        terrain_result = app._dm_set_terrain_on_map(2, 3, is_rough=True, movement_type="water")
        self.assertTrue(terrain_result["ok"])
        state_after_terrain = app._capture_canonical_map_state(prefer_window=True).normalized()
        terrain_cell = state_after_terrain.terrain_cells.get((2, 3))
        self.assertIsNotNone(terrain_cell)
        self.assertEqual("water", getattr(terrain_cell, "movement_type", ""))

        clear_result = app._dm_set_terrain_on_map(2, 3, is_rough=False)
        self.assertTrue(clear_result["ok"])
        state_after_clear = app._capture_canonical_map_state(prefer_window=True).normalized()
        self.assertNotIn((2, 3), state_after_clear.terrain_cells)
        self.assertEqual(3, app.broadcast_calls)

    def test_dm_create_blank_map_helper_resets_map_layers_and_grid(self):
        app = _TrackerTacticalHarness()
        app._dm_set_obstacle_on_map(2, 3, True)
        app._dm_upsert_feature_on_map(col=4, row=4, tactical_preset_id="crate", name="Crate")
        result = app._dm_create_blank_map(cols=14, rows=12)
        self.assertTrue(result["ok"])
        state = app._capture_canonical_map_state(prefer_window=True).normalized()
        self.assertEqual(14, state.grid.cols)
        self.assertEqual(12, state.grid.rows)
        self.assertEqual({}, state.obstacles)
        self.assertEqual({}, state.features)
        self.assertEqual({}, state.token_positions)

    def test_dm_set_map_grid_settings_helper_preserves_existing_layers(self):
        app = _TrackerTacticalHarness()
        app._dm_set_obstacle_on_map(2, 3, True)
        result = app._dm_set_map_grid_settings(cols=16, rows=11)
        self.assertTrue(result["ok"])
        state = app._capture_canonical_map_state(prefer_window=True).normalized()
        self.assertEqual(16, state.grid.cols)
        self.assertEqual(11, state.grid.rows)
        self.assertIn((2, 3), state.obstacles)

    def test_dm_set_auras_enabled_helper_updates_projection(self):
        app = _TrackerTacticalHarness()
        result = app._dm_set_auras_enabled(False)
        self.assertTrue(result["ok"])
        self.assertFalse(result["enabled"])
        payload = app._dm_tactical_snapshot()
        self.assertFalse(payload["auras_enabled"])
        self.assertEqual(1, app.broadcast_calls)

    def test_dm_feature_structure_and_elevation_helpers_mutate_canonical_map_state(self):
        app = _TrackerTacticalHarness()
        feature_result = app._dm_upsert_feature_on_map(col=2, row=2, tactical_preset_id="crate", name="Crate")
        self.assertTrue(feature_result["ok"])
        feature_id = str(feature_result["feature_id"])
        state_after_feature = app._capture_canonical_map_state(prefer_window=True).normalized()
        self.assertIn(feature_id, state_after_feature.features)

        structure_result = app._dm_upsert_structure_on_map(
            anchor_col=4,
            anchor_row=5,
            tactical_preset_id="wagon",
            width_cells=2,
            height_cells=1,
            name="Wagon",
        )
        self.assertTrue(structure_result["ok"])
        structure_id = str(structure_result["structure_id"])
        state_after_structure = app._capture_canonical_map_state(prefer_window=True).normalized()
        self.assertIn(structure_id, state_after_structure.structures)

        elevation_result = app._dm_set_elevation_on_map(col=7, row=1, elevation=20)
        self.assertTrue(elevation_result["ok"])
        state_after_elevation = app._capture_canonical_map_state(prefer_window=True).normalized()
        elevation_cell = state_after_elevation.elevation_cells.get((7, 1))
        self.assertIsNotNone(elevation_cell)
        self.assertEqual(20.0, float(getattr(elevation_cell, "elevation", 0.0)))

    def test_dm_background_layer_helpers_mutate_map_presentation(self):
        app = _TrackerTacticalHarness()
        repo_root = Path(__file__).resolve().parent.parent
        assets_dir = repo_root / "assets"
        test_asset = assets_dir / "_dm_web_bg_test.png"
        test_asset.write_bytes(b"test")
        try:
            upsert_result = app._dm_upsert_background_layer(
                asset_path="/assets/_dm_web_bg_test.png",
                x=4,
                y=-2,
                scale_pct=125,
                trans_pct=30,
                locked=True,
            )
            self.assertTrue(upsert_result["ok"])
            bid = int(upsert_result["background"]["bid"])
            state_after_upsert = app._capture_canonical_map_state(prefer_window=True).normalized()
            presentation = state_after_upsert.presentation if isinstance(state_after_upsert.presentation, dict) else {}
            layers = presentation.get("bg_images") if isinstance(presentation.get("bg_images"), list) else []
            self.assertTrue(any(int(layer.get("bid", 0)) == bid for layer in layers if isinstance(layer, dict)))

            remove_result = app._dm_remove_background_layer(bid)
            self.assertTrue(remove_result["ok"])
            state_after_remove = app._capture_canonical_map_state(prefer_window=True).normalized()
            presentation_after_remove = state_after_remove.presentation if isinstance(state_after_remove.presentation, dict) else {}
            layers_after_remove = (
                presentation_after_remove.get("bg_images")
                if isinstance(presentation_after_remove.get("bg_images"), list)
                else []
            )
            self.assertFalse(any(int(layer.get("bid", 0)) == bid for layer in layers_after_remove if isinstance(layer, dict)))
        finally:
            if test_asset.exists():
                test_asset.unlink()


class DmConsoleSnapshotPayloadTests(unittest.TestCase):
    def test_combined_snapshot_merges_combat_and_tactical_payloads(self):
        lan = object.__new__(tracker_mod.LanController)
        lan._tracker = types.SimpleNamespace(
            _dm_tactical_snapshot=lambda: {"grid": {"cols": 6, "rows": 6}, "units": [{"cid": 1, "pos": {"col": 1, "row": 2}}]}
        )
        lan._dm_service = types.SimpleNamespace(
            combat_snapshot=lambda: {"in_combat": True, "combatants": [{"cid": 1, "name": "Aelar"}]}
        )
        payload = tracker_mod.LanController._dm_console_snapshot_payload(lan)
        self.assertTrue(payload["in_combat"])
        self.assertEqual("Aelar", payload["combatants"][0]["name"])
        self.assertEqual(6, payload["tactical_map"]["grid"]["cols"])
        self.assertEqual({"col": 1, "row": 2}, payload["tactical_map"]["units"][0]["pos"])


class DmTacticalMapHtmlSurfaceTests(unittest.TestCase):
    def test_dm_console_contains_tactical_map_controls(self):
        html = _DM_HTML_PATH.read_text(encoding="utf-8")
        self.assertIn('id="mapColsInput"', html)
        self.assertIn('id="mapRowsInput"', html)
        self.assertIn('id="createMapBtn"', html)
        self.assertIn('id="applyMapSettingsBtn"', html)
        self.assertIn('id="tacticalMapCanvas"', html)
        self.assertIn('id="mapActionModeSelect"', html)
        self.assertIn('id="applyMapActionBtn"', html)
        self.assertIn('id="setFacingBtn"', html)
        self.assertIn('id="applyCellModeBtn"', html)
        self.assertIn('id="hazardPresetSelect"', html)
        self.assertIn('id="placeHazardBtn"', html)
        self.assertIn('id="featurePresetSelect"', html)
        self.assertIn('id="placeFeatureBtn"', html)
        self.assertIn('id="structurePresetSelect"', html)
        self.assertIn('id="placeStructureBtn"', html)
        self.assertIn('id="applyElevationBtn"', html)
        self.assertIn('id="bgAssetSelect"', html)
        self.assertIn('id="upsertBackgroundBtn"', html)
        self.assertIn('id="aoeShapeSelect"', html)
        self.assertIn('id="placeAoeBtn"', html)
        self.assertIn('id="applyOverlayBtn"', html)
        self.assertIn("/api/dm/map/combatants/{cid}/move", html)
        self.assertIn("/api/dm/map/combatants/{cid}/place", html)
        self.assertIn("/api/dm/map/obstacles/cell", html)
        self.assertIn("/api/dm/map/terrain/cell", html)
        self.assertIn("/api/dm/map/new", html)
        self.assertIn("/api/dm/map/settings", html)
        self.assertIn("/api/dm/map/hazards", html)
        self.assertIn("/api/dm/map/features", html)
        self.assertIn("/api/dm/map/structures", html)
        self.assertIn("/api/dm/map/elevation/cell", html)
        self.assertIn("/api/dm/map/backgrounds/assets", html)
        self.assertIn("/api/dm/map/backgrounds", html)
        self.assertIn("/api/dm/map/aoes", html)
        self.assertIn("/api/dm/map/overlays/auras", html)
        self.assertIn("/api/dm/map/combatants/${cid}/facing", html)


if __name__ == "__main__":
    unittest.main()
