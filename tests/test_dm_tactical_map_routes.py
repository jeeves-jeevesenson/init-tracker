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
        self.background_reorder_calls: list = []
        self.aoe_create_calls: list = []
        self.aoe_move_calls: list = []
        self.aoe_remove_calls: list = []
        self.auras_overlay_calls: list = []
        self.ship_blueprint_list_calls = 0
        self.ship_blueprint_preview_calls: list = []
        self.ship_instantiate_calls: list = []
        self.structure_template_list_calls = 0
        self.structure_template_instantiate_calls: list = []
        self.boarding_link_list_calls = 0
        self.boarding_link_upsert_calls: list = []
        self.boarding_link_status_calls: list = []
        self.boarding_link_remove_calls: list = []
        self.ship_engagement_summary_calls: list = []
        self.ship_maneuver_calls: list = []
        self.ship_fire_calls: list = []
        self.ship_ram_calls: list = []
        self.map_new_calls: list = []
        self.map_settings_calls: list = []
        self.dm_monster_attack_options_calls: list = []
        self.dm_monster_attack_resolve_calls: list = []
        self.dm_monster_attack_damage_calls: list = []
        self.dm_monster_perform_action_calls: list = []
        self.dm_monster_spell_target_calls: list = []
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
                "payload": {"ship_instance_id": "ship_runtime_1", "ship_blueprint_id": "sloop"},
            }
        }
        self.next_structure_id = 2
        self.boarding_links = []
        self.next_boarding_link_id = 1
        self.ships = [
            {
                "id": "ship_runtime_1",
                "name": "Sloop One",
                "blueprint_id": "sloop",
                "parent_structure_id": "ship_1",
                "facing_deg": 0.0,
                "component_count": 2,
                "weapon_count": 1,
                "hull_hp": 100,
                "hull_max_hp": 100,
                "hull_status": "intact",
                "active_crew": 8,
                "crew_ready": True,
                "movement_remaining": 0,
                "turns_remaining": 0,
                "actions_remaining": 0,
            }
        ]
        self.ship_engagement_state = {
            "ship_1": {
                "ok": True,
                "structure_id": "ship_1",
                "ship_id": "ship_runtime_1",
                "name": "Sloop One",
                "blueprint_id": "sloop",
                "facing_deg": 0.0,
                "hull_hp": 100,
                "hull_max_hp": 100,
                "movement_remaining": 0,
                "turns_remaining": 0,
                "actions_remaining": 1,
                "contact_structure_ids": [],
                "contact_count": 0,
                "mounted_weapons": [
                    {"id": "ballista", "name": "Ballista", "arc": "forward", "range_cells": 12, "reload_remaining": 0},
                ],
                "components": [
                    {"id": "hull", "name": "Hull", "type": "hull", "hp": 100, "max_hp": 100},
                    {"id": "helm", "name": "Helm", "type": "control", "hp": 20, "max_hp": 20},
                ],
            }
        }
        self.ship_blueprints = [
            {
                "id": "sloop",
                "name": "Sloop",
                "kind": "ship_hull",
                "category": "ship",
                "size": "medium",
                "default_facing_deg": 0.0,
                "footprint_cells": 8,
                "deck_count": 2,
                "deck_region_count": 2,
                "component_count": 3,
                "weapon_count": 1,
            },
            {
                "id": "rowboat_launch",
                "name": "Rowboat Launch",
                "kind": "ship_hull",
                "category": "ship",
                "size": "small",
                "default_facing_deg": 90.0,
                "footprint_cells": 4,
                "deck_count": 1,
                "deck_region_count": 1,
                "component_count": 1,
                "weapon_count": 0,
            },
        ]
        self.structure_templates = [
            {
                "id": "fortified_gate",
                "name": "Fortified Gate",
                "kind": "structure",
                "footprint_cells": 6,
                "feature_count": 1,
                "deck_count": 0,
                "anchor_point_count": 1,
            }
        ]
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
            "boarding_links": [dict(item) for item in self.boarding_links],
            "active_boarding_links": [dict(item) for item in self.boarding_links if str(item.get("status") or "active") == "active"],
            "ships": [dict(item) for item in self.ships],
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

    def _dm_monster_attack_options(self, attacker_cid: int):
        self.dm_monster_attack_options_calls.append({"attacker_cid": int(attacker_cid)})
        if int(attacker_cid) not in self.combatants:
            return {"ok": False, "error": "Combatant not found."}
        combatant = self.combatants[int(attacker_cid)]
        if bool(getattr(combatant, "is_pc", False)):
            return {"ok": False, "error": "Monster control only supports non-PC combatants."}
        return {
            "ok": True,
            "attacker_cid": int(attacker_cid),
            "attacker_name": str(getattr(combatant, "name", "")),
            "multiattack_description": "The goblin makes two scimitar attacks.",
            "multiattack_counts": {"scimitar": 2},
            "default_sequence": [{"attack_key": "scimitar", "count": 2, "roll_mode": "normal"}],
            "attack_options": [
                {
                    "key": "scimitar",
                    "label": "Scimitar",
                    "to_hit": 4,
                    "attack_type": "melee",
                    "reach_ft": 5,
                    "damage": [{"amount": 5, "roll": "1d6+2", "type": "slashing"}],
                }
            ],
        }

    def _dm_resolve_monster_attack_sequence(self, *, attacker_cid: int, target_cid: int, sequence_blocks, spend="action"):
        self.dm_monster_attack_resolve_calls.append(
            {
                "attacker_cid": int(attacker_cid),
                "target_cid": int(target_cid),
                "sequence_blocks": list(sequence_blocks) if isinstance(sequence_blocks, list) else sequence_blocks,
                "spend": spend,
            }
        )
        if int(attacker_cid) not in self.combatants or int(target_cid) not in self.combatants:
            return {"ok": False, "error": "Combatant not found."}
        return {
            "ok": True,
            "attacker_cid": int(attacker_cid),
            "target_cid": int(target_cid),
            "spend": str(spend or "action"),
            "results": [
                {
                    "attack_key": "scimitar",
                    "attack_name": "Scimitar",
                    "roll_mode": "normal",
                    "to_hit_roll": 18,
                    "to_hit_bonus": 4,
                    "total_to_hit": 22,
                    "target_ac": 16,
                    "hit": True,
                    "crit": False,
                    "damage_rolls": [{"type": "slashing", "roll": "1d6+2", "default_total": 5}],
                }
            ],
            "reason": "Resolved.",
        }

    def _dm_apply_monster_attack_damage(self, *, attacker_cid: int, target_cid: int, attack_name: str, damage_entries):
        self.dm_monster_attack_damage_calls.append(
            {
                "attacker_cid": int(attacker_cid),
                "target_cid": int(target_cid),
                "attack_name": str(attack_name),
                "damage_entries": list(damage_entries) if isinstance(damage_entries, list) else damage_entries,
            }
        )
        if int(attacker_cid) not in self.combatants or int(target_cid) not in self.combatants:
            return {"ok": False, "error": "Combatant not found."}
        return {"ok": True, "target_hp": 2, "removed_target": False, "message": "Applied manual damage."}

    def _dm_monster_perform_action(self, *, actor_cid: int, action_name: str, spend="action"):
        self.dm_monster_perform_action_calls.append(
            {"actor_cid": int(actor_cid), "action_name": str(action_name), "spend": spend}
        )
        if int(actor_cid) not in self.combatants:
            return {"ok": False, "error": "Combatant not found."}
        return {
            "ok": True,
            "actor_cid": int(actor_cid),
            "actor_name": str(getattr(self.combatants[int(actor_cid)], "name", "")),
            "action": str(action_name),
            "spend": str(spend or "action"),
        }

    def _dm_monster_spell_target(self, *, actor_cid: int, payload):
        self.dm_monster_spell_target_calls.append({"actor_cid": int(actor_cid), "payload": dict(payload or {})})
        if int(actor_cid) not in self.combatants:
            return {"ok": False, "error": "Combatant not found."}
        target_cid = int((payload or {}).get("target_cid") or actor_cid)
        if target_cid not in self.combatants:
            return {"ok": False, "error": "Target combatant not found."}
        return {
            "ok": True,
            "actor_cid": int(actor_cid),
            "target_cid": int(target_cid),
            "target_name": str(getattr(self.combatants[int(target_cid)], "name", "")),
            "pending": False,
            "spell_result": {"ok": True, "reason": "resolved"},
        }

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
        self.ship_engagement_state.pop(sid, None)
        self.ships = [item for item in self.ships if str(item.get("parent_structure_id") or "") != sid]
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
        self.boarding_links = []
        self.next_boarding_link_id = 1
        self.ships = []
        self.ship_engagement_state = {}
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

    def _dm_reorder_background_layer(self, *, bid, direction):
        self.background_reorder_calls.append({"bid": int(bid), "direction": str(direction)})
        target = int(bid)
        action = str(direction or "").strip().lower()
        if action not in {"up", "down", "front", "back"}:
            return {"ok": False, "error": "direction must be one of: up, down, front, back."}
        ordered = sorted(self.background_layers, key=lambda item: int(item.get("bid", 0)))
        index = next((idx for idx, item in enumerate(ordered) if int(item.get("bid", 0)) == target), None)
        if index is None:
            return {"ok": False, "error": "Background layer not found."}
        if action == "up":
            new_index = min(len(ordered) - 1, int(index) + 1)
        elif action == "down":
            new_index = max(0, int(index) - 1)
        elif action == "front":
            new_index = len(ordered) - 1
        else:
            new_index = 0
        if new_index != index:
            layer = dict(ordered.pop(index))
            ordered.insert(new_index, layer)
        for idx, entry in enumerate(ordered, start=1):
            entry["bid"] = int(idx)
            entry["asset_url"] = str(entry.get("path") or "")
        self.background_layers = [dict(entry) for entry in ordered]
        self.next_background_id = max(int(self.next_background_id), len(self.background_layers) + 1)
        selected = dict(self.background_layers[new_index])
        self._lan_force_state_broadcast()
        return {
            "ok": True,
            "bid": int(selected.get("bid", 0)),
            "background": dict(selected),
            "backgrounds": [dict(entry) for entry in self.background_layers],
        }

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

    def _dm_list_ship_blueprints(self):
        self.ship_blueprint_list_calls += 1
        return [dict(item) for item in self.ship_blueprints]

    def _dm_list_structure_templates(self):
        self.structure_template_list_calls += 1
        return [dict(item) for item in self.structure_templates]

    def _dm_list_boarding_links(self):
        self.boarding_link_list_calls += 1
        return [dict(item) for item in self.boarding_links]

    def _dm_preview_ship_blueprint_on_map(self, *, blueprint_id, anchor_col, anchor_row, facing_deg=0.0):
        self.ship_blueprint_preview_calls.append(
            {
                "blueprint_id": str(blueprint_id),
                "anchor_col": int(anchor_col),
                "anchor_row": int(anchor_row),
                "facing_deg": float(facing_deg),
            }
        )
        if not any(str(item.get("id") or "") == str(blueprint_id) for item in self.ship_blueprints):
            return {"ok": False, "error": "Ship blueprint not found.", "reason": "ship_blueprint_not_found"}
        in_bounds = 0 <= int(anchor_col) < int(self.map_cols) and 0 <= int(anchor_row) < int(self.map_rows)
        blockers = {
            "ok": bool(in_bounds),
            "blockers": {
                "out_of_bounds": [] if in_bounds else [{"col": int(anchor_col), "row": int(anchor_row)}],
                "obstacles": [],
                "features": [],
                "structures": [],
                "hazards": [],
                "template_conflicts": [],
            },
        }
        return {
            "ok": bool(in_bounds),
            "blueprint_id": str(blueprint_id),
            "anchor_col": int(anchor_col),
            "anchor_row": int(anchor_row),
            "facing_deg": float(facing_deg),
            "target_cells": [{"col": int(anchor_col), "row": int(anchor_row)}],
            "blockers": blockers,
        }

    def _dm_instantiate_ship_blueprint_on_map(
        self,
        *,
        blueprint_id,
        anchor_col,
        anchor_row,
        facing_deg=0.0,
        name=None,
    ):
        self.ship_instantiate_calls.append(
            {
                "blueprint_id": str(blueprint_id),
                "anchor_col": int(anchor_col),
                "anchor_row": int(anchor_row),
                "facing_deg": float(facing_deg),
                "name": str(name or ""),
            }
        )
        if not any(str(item.get("id") or "") == str(blueprint_id) for item in self.ship_blueprints):
            return {"ok": False, "error": "Ship blueprint not found.", "reason": "ship_blueprint_not_found"}
        if not (0 <= int(anchor_col) < int(self.map_cols) and 0 <= int(anchor_row) < int(self.map_rows)):
            return {"ok": False, "error": "Cell out of bounds.", "reason": "invalid_anchor"}
        sid = f"ship_structure_{self.next_structure_id}"
        self.next_structure_id += 1
        ship_id = f"ship_runtime_{self.next_structure_id}"
        display_name = str(name or "").strip() or f"{str(blueprint_id).replace('_', ' ').title()} {sid}"
        structure = {
            "id": sid,
            "anchor_col": int(anchor_col),
            "anchor_row": int(anchor_row),
            "occupied_cells": [{"col": int(anchor_col), "row": int(anchor_row)}],
            "kind": "ship_hull",
            "payload": {
                "name": display_name,
                "ship_instance_id": ship_id,
                "ship_blueprint_id": str(blueprint_id),
                "facing_deg": float(facing_deg),
            },
            "ship_state": {"ship_id": ship_id, "name": display_name, "blueprint_id": str(blueprint_id)},
        }
        ship_summary = {
            "ok": True,
            "ship_id": ship_id,
            "structure_id": sid,
            "name": display_name,
            "blueprint_id": str(blueprint_id),
            "facing_deg": float(facing_deg),
            "hull_hp": 100,
            "hull_max_hp": 100,
            "movement_remaining": 0,
            "turns_remaining": 0,
            "actions_remaining": 1,
            "contact_structure_ids": [],
            "contact_count": 0,
            "mounted_weapons": [
                {"id": "ballista", "name": "Ballista", "arc": "forward", "range_cells": 12, "reload_remaining": 0},
            ],
            "components": [
                {"id": "hull", "name": "Hull", "type": "hull", "hp": 100, "max_hp": 100},
                {"id": "helm", "name": "Helm", "type": "control", "hp": 20, "max_hp": 20},
            ],
        }
        self.structures[sid] = structure
        self.ships.append(
            {
                "id": ship_id,
                "name": display_name,
                "blueprint_id": str(blueprint_id),
                "parent_structure_id": sid,
                "facing_deg": float(facing_deg),
                "component_count": 0,
                "weapon_count": 0,
                "hull_hp": 100,
                "hull_max_hp": 100,
                "hull_status": "intact",
                "active_crew": 8,
                "crew_ready": True,
                "movement_remaining": 0,
                "turns_remaining": 0,
                "actions_remaining": 1,
            }
        )
        self.ship_engagement_state[sid] = dict(ship_summary)
        self._lan_force_state_broadcast()
        return {
            "ok": True,
            "blueprint_id": str(blueprint_id),
            "structure_id": sid,
            "structure": dict(structure),
            "ship": dict(ship_summary),
        }

    def _dm_instantiate_structure_template_on_map(self, *, template_id, anchor_col, anchor_row, facing_deg=0.0):
        self.structure_template_instantiate_calls.append(
            {
                "template_id": str(template_id),
                "anchor_col": int(anchor_col),
                "anchor_row": int(anchor_row),
                "facing_deg": float(facing_deg),
            }
        )
        if not any(str(item.get("id") or "") == str(template_id) for item in self.structure_templates):
            return {"ok": False, "error": "Structure template not found.", "reason": "template_not_found"}
        if not (0 <= int(anchor_col) < int(self.map_cols) and 0 <= int(anchor_row) < int(self.map_rows)):
            return {"ok": False, "error": "Cell out of bounds.", "reason": "invalid_anchor"}
        sid = f"template_structure_{self.next_structure_id}"
        self.next_structure_id += 1
        structure = {
            "id": sid,
            "anchor_col": int(anchor_col),
            "anchor_row": int(anchor_row),
            "occupied_cells": [{"col": int(anchor_col), "row": int(anchor_row)}],
            "kind": "structure",
            "payload": {"template_id": str(template_id), "facing_deg": float(facing_deg)},
        }
        self.structures[sid] = structure
        self._lan_force_state_broadcast()
        return {"ok": True, "template_id": str(template_id), "structure_id": sid, "structure": dict(structure)}

    def _dm_upsert_boarding_link_on_map(self, *, source_structure_id, target_structure_id, status="active", notes=None):
        self.boarding_link_upsert_calls.append(
            {
                "source_structure_id": str(source_structure_id),
                "target_structure_id": str(target_structure_id),
                "status": str(status),
                "notes": str(notes or ""),
            }
        )
        source_id = str(source_structure_id or "").strip()
        target_id = str(target_structure_id or "").strip()
        if not source_id or not target_id:
            return {"ok": False, "error": "source_structure_id and target_structure_id are required.", "reason": "missing_structure_id"}
        existing = next(
            (
                item
                for item in self.boarding_links
                if {str(item.get("source_id") or ""), str(item.get("target_id") or "")} == {source_id, target_id}
            ),
            None,
        )
        status_value = str(status or "active").strip().lower() or "active"
        if existing is None:
            link_id = f"boarding_link_{self.next_boarding_link_id}"
            self.next_boarding_link_id += 1
            link = {
                "id": link_id,
                "source_id": source_id,
                "target_id": target_id,
                "status": status_value,
                "notes": str(notes or "").strip(),
                "traversable": status_value == "active",
            }
            self.boarding_links.append(link)
            result_link = link
        else:
            existing["status"] = status_value
            existing["notes"] = str(notes or "").strip()
            existing["traversable"] = status_value == "active"
            result_link = existing
        self._lan_force_state_broadcast()
        return {"ok": True, "boarding_link": dict(result_link), "message": "Boarding link updated."}

    def _dm_set_boarding_link_status_on_map(self, *, link_id, status, notes=None):
        self.boarding_link_status_calls.append(
            {"link_id": str(link_id), "status": str(status), "notes": str(notes or "")}
        )
        key = str(link_id or "").strip()
        if not key:
            return {"ok": False, "error": "link_id is required.", "reason": "missing_link_id"}
        target = next((item for item in self.boarding_links if str(item.get("id") or "") == key), None)
        if target is None:
            return {"ok": False, "error": "Boarding link not found.", "reason": "boarding_link_not_found"}
        status_value = str(status or "").strip().lower() or "active"
        target["status"] = status_value
        target["notes"] = str(notes or "").strip()
        target["traversable"] = status_value == "active"
        self._lan_force_state_broadcast()
        return {
            "ok": True,
            "boarding_link_id": key,
            "status": status_value,
            "boarding_link": dict(target),
            "message": "Boarding link status updated.",
        }

    def _dm_remove_boarding_link_on_map(self, *, link_id):
        self.boarding_link_remove_calls.append(str(link_id))
        key = str(link_id or "").strip()
        before = len(self.boarding_links)
        self.boarding_links = [item for item in self.boarding_links if str(item.get("id") or "") != key]
        if len(self.boarding_links) == before:
            return {"ok": False, "error": "Boarding link not found.", "reason": "boarding_link_not_found"}
        self._lan_force_state_broadcast()
        return {"ok": True, "boarding_link_id": key}

    def _ship_engagement_summary_for(self, structure_id: str):
        sid = str(structure_id or "").strip()
        if not sid:
            return None
        structure = self.structures.get(sid)
        if not isinstance(structure, dict):
            return None
        payload = structure.get("payload") if isinstance(structure.get("payload"), dict) else {}
        ship_id = str(payload.get("ship_instance_id") or "")
        if not ship_id:
            return None
        summary = self.ship_engagement_state.get(sid)
        if not isinstance(summary, dict):
            summary = {
                "ok": True,
                "structure_id": sid,
                "ship_id": ship_id,
                "name": str(payload.get("name") or sid),
                "blueprint_id": str(payload.get("ship_blueprint_id") or ""),
                "facing_deg": float(payload.get("facing_deg", 0.0) or 0.0),
                "hull_hp": 100,
                "hull_max_hp": 100,
                "movement_remaining": 0,
                "turns_remaining": 0,
                "actions_remaining": 1,
                "contact_structure_ids": [],
                "contact_count": 0,
                "mounted_weapons": [
                    {"id": "ballista", "name": "Ballista", "arc": "forward", "range_cells": 12, "reload_remaining": 0},
                ],
                "components": [
                    {"id": "hull", "name": "Hull", "type": "hull", "hp": 100, "max_hp": 100},
                    {"id": "helm", "name": "Helm", "type": "control", "hp": 20, "max_hp": 20},
                ],
            }
            self.ship_engagement_state[sid] = summary
        ship_obj = next((item for item in self.ships if str(item.get("parent_structure_id") or "") == sid), None)
        if isinstance(ship_obj, dict):
            summary["facing_deg"] = float(ship_obj.get("facing_deg", summary.get("facing_deg", 0.0)) or 0.0)
            summary["hull_hp"] = int(ship_obj.get("hull_hp", summary.get("hull_hp", 0)) or 0)
            summary["hull_max_hp"] = int(ship_obj.get("hull_max_hp", summary.get("hull_max_hp", 0)) or 0)
            summary["movement_remaining"] = int(ship_obj.get("movement_remaining", summary.get("movement_remaining", 0)) or 0)
            summary["turns_remaining"] = int(ship_obj.get("turns_remaining", summary.get("turns_remaining", 0)) or 0)
            summary["actions_remaining"] = int(ship_obj.get("actions_remaining", summary.get("actions_remaining", 0)) or 0)
        contacts = {
            str(item)
            for item in (summary.get("contact_structure_ids") if isinstance(summary.get("contact_structure_ids"), list) else [])
            if str(item).strip()
        }
        for link in self.boarding_links:
            if not isinstance(link, dict):
                continue
            status = str(link.get("status") or "active").strip().lower() or "active"
            if status != "active":
                continue
            source_id = str(link.get("source_id") or "").strip()
            target_id = str(link.get("target_id") or "").strip()
            if source_id == sid and target_id:
                contacts.add(target_id)
            elif target_id == sid and source_id:
                contacts.add(source_id)
        summary["contact_structure_ids"] = sorted(contacts)
        summary["contact_count"] = len(summary["contact_structure_ids"])
        return dict(summary)

    def _dm_ship_engagement_summary(self, *, structure_id):
        sid = str(structure_id or "").strip()
        self.ship_engagement_summary_calls.append(sid)
        summary = self._ship_engagement_summary_for(sid)
        if not isinstance(summary, dict):
            return {"ok": False, "error": "Selected structure is not a ship.", "reason": "ship_not_found"}
        return {"ok": True, "structure_id": sid, "ship": dict(summary)}

    def _dm_ship_maneuver_on_map(self, *, structure_id, maneuver, steps=1, preview_only=False):
        sid = str(structure_id or "").strip()
        action = str(maneuver or "").strip().lower()
        self.ship_maneuver_calls.append(
            {"structure_id": sid, "maneuver": action, "steps": steps, "preview_only": bool(preview_only)}
        )
        allowed = {"move_forward", "move_reverse", "move_port", "move_starboard", "turn_port", "turn_starboard"}
        if action not in allowed:
            return {"ok": False, "error": "Unsupported ship maneuver.", "reason": "unsupported_maneuver"}
        summary = self._ship_engagement_summary_for(sid)
        structure = self.structures.get(sid)
        if not isinstance(summary, dict) or not isinstance(structure, dict):
            return {"ok": False, "error": "Selected structure is not a ship.", "reason": "ship_not_found"}
        step_count = 1
        if action in {"move_forward", "move_reverse"}:
            try:
                step_count = max(1, int(steps if steps is not None else 1))
            except Exception:
                return {"ok": False, "error": "steps must be an integer >= 1 for this maneuver.", "reason": "invalid_steps"}
        start_col = int(structure.get("anchor_col", 0))
        start_row = int(structure.get("anchor_row", 0))
        facing = float(summary.get("facing_deg", 0.0) or 0.0)
        next_col = int(start_col)
        next_row = int(start_row)
        if action == "move_forward":
            next_row = max(0, start_row - int(step_count))
        elif action == "move_reverse":
            next_row = min(int(self.map_rows) - 1, start_row + int(step_count))
        elif action == "move_port":
            next_col = max(0, start_col - 1)
        elif action == "move_starboard":
            next_col = min(int(self.map_cols) - 1, start_col + 1)
        elif action == "turn_port":
            facing = (float(facing) - 90.0) % 360.0
        elif action == "turn_starboard":
            facing = (float(facing) + 90.0) % 360.0
        if not bool(preview_only):
            structure["anchor_col"] = int(next_col)
            structure["anchor_row"] = int(next_row)
            structure["occupied_cells"] = [{"col": int(next_col), "row": int(next_row)}]
            payload = structure.get("payload") if isinstance(structure.get("payload"), dict) else {}
            payload["facing_deg"] = float(facing)
            structure["payload"] = payload
            ship_obj = next((item for item in self.ships if str(item.get("parent_structure_id") or "") == sid), None)
            if isinstance(ship_obj, dict):
                ship_obj["facing_deg"] = float(facing)
            entry = self.ship_engagement_state.get(sid)
            if isinstance(entry, dict):
                entry["facing_deg"] = float(facing)
            self._lan_force_state_broadcast()
        refreshed = self._ship_engagement_summary_for(sid) or {}
        return {
            "ok": True,
            "structure_id": sid,
            "maneuver": action,
            "steps": int(step_count),
            "preview_only": bool(preview_only),
            "result": {
                "ok": True,
                "maneuver": action,
                "steps": int(step_count),
                "moved_squares": int(step_count) if action in {"move_forward", "move_reverse"} else 0,
                "facing_deg": float(facing),
                "contact_count": int(refreshed.get("contact_count", 0) or 0),
            },
            "ship": dict(refreshed),
        }

    def _dm_ship_fire_weapon_on_map(self, *, source_structure_id, target_structure_id, weapon_id, target_component_id=None):
        source_id = str(source_structure_id or "").strip()
        target_id = str(target_structure_id or "").strip()
        wid = str(weapon_id or "").strip().lower()
        component = str(target_component_id or "").strip().lower() or None
        self.ship_fire_calls.append(
            {
                "source_structure_id": source_id,
                "target_structure_id": target_id,
                "weapon_id": wid,
                "target_component_id": component,
            }
        )
        source = self._ship_engagement_summary_for(source_id)
        target = self._ship_engagement_summary_for(target_id)
        if not isinstance(source, dict):
            return {"ok": False, "error": "source_structure_id is required.", "reason": "missing_source_structure_id"}
        if not isinstance(target, dict):
            return {"ok": False, "error": "target_structure_id is required.", "reason": "missing_target_structure_id"}
        if not wid:
            return {"ok": False, "error": "weapon_id is required.", "reason": "missing_weapon_id"}
        weapons = source.get("mounted_weapons") if isinstance(source.get("mounted_weapons"), list) else []
        if not any(str(item.get("id") or "").strip().lower() == wid for item in weapons if isinstance(item, dict)):
            return {"ok": False, "error": "Weapon not found.", "reason": "weapon_not_found"}
        damage = 11
        target_ship = next((item for item in self.ships if str(item.get("parent_structure_id") or "") == target_id), None)
        if isinstance(target_ship, dict):
            target_ship["hull_hp"] = max(0, int(target_ship.get("hull_hp", 0) or 0) - int(damage))
        source_ship = next((item for item in self.ships if str(item.get("parent_structure_id") or "") == source_id), None)
        if isinstance(source_ship, dict):
            source_ship["actions_remaining"] = max(0, int(source_ship.get("actions_remaining", 0) or 0) - 1)
        target_state = self.ship_engagement_state.get(target_id)
        if isinstance(target_state, dict):
            target_state["hull_hp"] = max(0, int(target_state.get("hull_hp", 0) or 0) - int(damage))
        self._lan_force_state_broadcast()
        return {
            "ok": True,
            "result": {
                "ok": True,
                "weapon_id": wid,
                "hit": True,
                "attack_total": 18,
                "target_ac": 14,
                "damage": int(damage),
                "target_structure_id": target_id,
                "target_component_id": component,
            },
            "source_ship": self._ship_engagement_summary_for(source_id) or {},
            "target_ship": self._ship_engagement_summary_for(target_id) or {},
        }

    def _dm_ship_ram_on_map(self, *, source_structure_id, target_structure_id):
        source_id = str(source_structure_id or "").strip()
        target_id = str(target_structure_id or "").strip()
        self.ship_ram_calls.append(
            {
                "source_structure_id": source_id,
                "target_structure_id": target_id,
            }
        )
        source = self._ship_engagement_summary_for(source_id)
        target = self._ship_engagement_summary_for(target_id)
        if not isinstance(source, dict):
            return {"ok": False, "error": "source_structure_id is required.", "reason": "missing_source_structure_id"}
        if not isinstance(target, dict):
            return {"ok": False, "error": "target_structure_id is required.", "reason": "missing_target_structure_id"}
        target_damage = 14
        source_damage = 5
        for sid, delta in ((target_id, target_damage), (source_id, source_damage)):
            ship_obj = next((item for item in self.ships if str(item.get("parent_structure_id") or "") == sid), None)
            if isinstance(ship_obj, dict):
                ship_obj["hull_hp"] = max(0, int(ship_obj.get("hull_hp", 0) or 0) - int(delta))
            state = self.ship_engagement_state.get(sid)
            if isinstance(state, dict):
                state["hull_hp"] = max(0, int(state.get("hull_hp", 0) or 0) - int(delta))
        self._lan_force_state_broadcast()
        return {
            "ok": True,
            "result": {
                "ok": True,
                "source_structure_id": source_id,
                "target_structure_id": target_id,
                "target_damage": int(target_damage),
                "source_damage": int(source_damage),
            },
            "source_ship": self._ship_engagement_summary_for(source_id) or {},
            "target_ship": self._ship_engagement_summary_for(target_id) or {},
        }


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

    def test_dm_dashboard_and_map_workspace_routes_render_workspace_mode(self):
        client, _lan = self._build_client()
        dashboard = client.get("/dm")
        self.assertEqual(200, dashboard.status_code)
        self.assertIn('data-dm-workspace="dashboard"', dashboard.text)
        self.assertIn('id="workspaceNavLink" href="/dm/map"', dashboard.text)
        map_workspace = client.get("/dm/map")
        self.assertEqual(200, map_workspace.status_code)
        self.assertIn('data-dm-workspace="map"', map_workspace.text)
        self.assertIn("nav.href = '/dm';", map_workspace.text)
        self.assertIn("DM_WORKSPACE", map_workspace.text)
        self.assertIn('id="mapWorkspacePanel"', map_workspace.text)

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

        reorder = client.post(f"/api/dm/map/backgrounds/{created_bid}/order", json={"direction": "down"})
        self.assertEqual(200, reorder.status_code)
        reorder_payload = reorder.json()
        self.assertTrue(reorder_payload["ok"])
        self.assertEqual("down", lan._tracker.background_reorder_calls[-1]["direction"])
        reordered_layers = reorder_payload["snapshot"]["tactical_map"]["map_state"]["presentation"]["bg_images"]
        reordered_target = next(layer for layer in reordered_layers if str(layer.get("path")) == "/assets/maps/cavern.png")
        self.assertEqual(1, int(reordered_target["bid"]))
        created_bid = int(reorder_payload["bid"])

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

    def test_ship_blueprint_and_structure_template_routes(self):
        client, lan = self._build_client()

        blueprints = client.get("/api/dm/map/ship-blueprints")
        self.assertEqual(200, blueprints.status_code)
        blueprints_payload = blueprints.json()
        self.assertTrue(blueprints_payload["ok"])
        self.assertTrue(any(entry["id"] == "sloop" for entry in blueprints_payload["blueprints"]))
        self.assertEqual(1, lan._tracker.ship_blueprint_list_calls)

        preview = client.post(
            "/api/dm/map/ship-blueprints/sloop/preview",
            json={"anchor_col": 5, "anchor_row": 5, "facing_deg": 90},
        )
        self.assertEqual(200, preview.status_code)
        preview_payload = preview.json()
        self.assertTrue(preview_payload["ok"])
        self.assertEqual("sloop", preview_payload["blueprint_id"])
        self.assertTrue(any(call["blueprint_id"] == "sloop" for call in lan._tracker.ship_blueprint_preview_calls))

        place_ship = client.post(
            "/api/dm/map/ships",
            json={"blueprint_id": "sloop", "anchor_col": 6, "anchor_row": 6, "facing_deg": 180, "name": "Sea Ghost"},
        )
        self.assertEqual(200, place_ship.status_code)
        ship_payload = place_ship.json()
        self.assertTrue(ship_payload["ok"])
        self.assertEqual("sloop", ship_payload["blueprint_id"])
        structure_id = str(ship_payload["structure_id"])
        snapshot_structure = next(item for item in ship_payload["snapshot"]["tactical_map"]["structures"] if item["id"] == structure_id)
        self.assertEqual("sloop", snapshot_structure["payload"]["ship_blueprint_id"])
        self.assertTrue(any(call["blueprint_id"] == "sloop" for call in lan._tracker.ship_instantiate_calls))

        templates = client.get("/api/dm/map/structure-templates")
        self.assertEqual(200, templates.status_code)
        templates_payload = templates.json()
        self.assertTrue(templates_payload["ok"])
        self.assertTrue(any(entry["id"] == "fortified_gate" for entry in templates_payload["templates"]))
        self.assertEqual(1, lan._tracker.structure_template_list_calls)

        place_template = client.post(
            "/api/dm/map/structure-templates/fortified_gate/instantiate",
            json={"anchor_col": 3, "anchor_row": 3, "facing_deg": 270},
        )
        self.assertEqual(200, place_template.status_code)
        template_payload = place_template.json()
        self.assertTrue(template_payload["ok"])
        self.assertEqual("fortified_gate", template_payload["template_id"])
        self.assertTrue(any(call["template_id"] == "fortified_gate" for call in lan._tracker.structure_template_instantiate_calls))

    def test_boarding_link_routes_create_status_update_and_remove(self):
        client, lan = self._build_client()

        create_ship_a = client.post(
            "/api/dm/map/ships",
            json={"blueprint_id": "sloop", "anchor_col": 2, "anchor_row": 2, "facing_deg": 0, "name": "A"},
        )
        create_ship_b = client.post(
            "/api/dm/map/ships",
            json={"blueprint_id": "rowboat_launch", "anchor_col": 3, "anchor_row": 2, "facing_deg": 90, "name": "B"},
        )
        self.assertEqual(200, create_ship_a.status_code)
        self.assertEqual(200, create_ship_b.status_code)
        source_id = str(create_ship_a.json()["structure_id"])
        target_id = str(create_ship_b.json()["structure_id"])

        create_link = client.post(
            "/api/dm/map/boarding-links",
            json={"source_structure_id": source_id, "target_structure_id": target_id, "status": "active", "notes": "Gangplank"},
        )
        self.assertEqual(200, create_link.status_code)
        create_payload = create_link.json()
        self.assertTrue(create_payload["ok"])
        link_id = str(create_payload["boarding_link"]["id"])
        self.assertTrue(any(call["source_structure_id"] == source_id for call in lan._tracker.boarding_link_upsert_calls))
        self.assertTrue(any(item["id"] == link_id for item in create_payload["snapshot"]["tactical_map"]["boarding_links"]))

        list_links = client.get("/api/dm/map/boarding-links")
        self.assertEqual(200, list_links.status_code)
        listed_payload = list_links.json()
        self.assertTrue(listed_payload["ok"])
        self.assertTrue(any(item["id"] == link_id for item in listed_payload["boarding_links"]))
        self.assertEqual(1, lan._tracker.boarding_link_list_calls)

        set_status = client.post(
            f"/api/dm/map/boarding-links/{link_id}/status",
            json={"status": "withdrawn", "notes": "Pulled away"},
        )
        self.assertEqual(200, set_status.status_code)
        status_payload = set_status.json()
        self.assertTrue(status_payload["ok"])
        self.assertEqual("withdrawn", status_payload["status"])
        self.assertTrue(any(call["link_id"] == link_id for call in lan._tracker.boarding_link_status_calls))

        remove_link = client.delete(f"/api/dm/map/boarding-links/{link_id}")
        self.assertEqual(200, remove_link.status_code)
        remove_payload = remove_link.json()
        self.assertTrue(remove_payload["ok"])
        self.assertIn(link_id, lan._tracker.boarding_link_remove_calls)
        self.assertFalse(any(item["id"] == link_id for item in remove_payload["snapshot"]["tactical_map"]["boarding_links"]))

    def test_ship_engagement_routes_summary_maneuver_fire_and_ram(self):
        client, lan = self._build_client()

        create_ship_a = client.post(
            "/api/dm/map/ships",
            json={"blueprint_id": "sloop", "anchor_col": 5, "anchor_row": 5, "facing_deg": 0, "name": "A"},
        )
        create_ship_b = client.post(
            "/api/dm/map/ships",
            json={"blueprint_id": "sloop", "anchor_col": 7, "anchor_row": 5, "facing_deg": 180, "name": "B"},
        )
        self.assertEqual(200, create_ship_a.status_code)
        self.assertEqual(200, create_ship_b.status_code)
        source_id = str(create_ship_a.json()["structure_id"])
        target_id = str(create_ship_b.json()["structure_id"])

        link = client.post(
            "/api/dm/map/boarding-links",
            json={"source_structure_id": source_id, "target_structure_id": target_id, "status": "active"},
        )
        self.assertEqual(200, link.status_code)

        summary = client.get(f"/api/dm/map/ships/{source_id}/engagement")
        self.assertEqual(200, summary.status_code)
        summary_payload = summary.json()
        self.assertTrue(summary_payload["ok"])
        self.assertEqual(source_id, summary_payload["structure_id"])
        self.assertTrue(any(str(item.get("id")) == "ballista" for item in summary_payload["ship"]["mounted_weapons"]))
        self.assertIn(source_id, lan._tracker.ship_engagement_summary_calls)

        preview = client.post(
            f"/api/dm/map/ships/{source_id}/maneuver-preview",
            json={"maneuver": "move_forward", "steps": 2},
        )
        self.assertEqual(200, preview.status_code)
        preview_payload = preview.json()
        self.assertTrue(preview_payload["ok"])
        self.assertTrue(preview_payload["preview_only"])
        self.assertEqual("move_forward", preview_payload["maneuver"])
        self.assertTrue(any(call["preview_only"] for call in lan._tracker.ship_maneuver_calls))

        apply_maneuver = client.post(
            f"/api/dm/map/ships/{source_id}/maneuver",
            json={"maneuver": "move_forward", "steps": 2},
        )
        self.assertEqual(200, apply_maneuver.status_code)
        maneuver_payload = apply_maneuver.json()
        self.assertTrue(maneuver_payload["ok"])
        self.assertEqual("move_forward", maneuver_payload["maneuver"])
        moved_source = next(
            item for item in maneuver_payload["snapshot"]["tactical_map"]["structures"] if item["id"] == source_id
        )
        self.assertEqual(3, int(moved_source["anchor_row"]))
        self.assertTrue(any(not call["preview_only"] for call in lan._tracker.ship_maneuver_calls))

        fire = client.post(
            f"/api/dm/map/ships/{source_id}/weapons/fire",
            json={"target_structure_id": target_id, "weapon_id": "ballista", "target_component_id": "hull"},
        )
        self.assertEqual(200, fire.status_code)
        fire_payload = fire.json()
        self.assertTrue(fire_payload["ok"])
        self.assertTrue(fire_payload["result"]["hit"])
        self.assertTrue(
            any(
                call["source_structure_id"] == source_id
                and call["target_structure_id"] == target_id
                and call["weapon_id"] == "ballista"
                for call in lan._tracker.ship_fire_calls
            )
        )

        ram = client.post(
            f"/api/dm/map/ships/{source_id}/ram",
            json={"target_structure_id": target_id},
        )
        self.assertEqual(200, ram.status_code)
        ram_payload = ram.json()
        self.assertTrue(ram_payload["ok"])
        self.assertGreater(int(ram_payload["result"]["target_damage"]), 0)
        self.assertTrue(
            any(
                call["source_structure_id"] == source_id and call["target_structure_id"] == target_id
                for call in lan._tracker.ship_ram_calls
            )
        )

    def test_dm_monster_attack_routes_resolve_and_apply_damage(self):
        client, lan = self._build_client()
        options = client.get("/api/dm/combat/combatants/2/monster-attacks")
        self.assertEqual(200, options.status_code)
        options_payload = options.json()
        self.assertTrue(options_payload["ok"])
        self.assertEqual(2, options_payload["attacker_cid"])
        self.assertTrue(any(call["attacker_cid"] == 2 for call in lan._tracker.dm_monster_attack_options_calls))

        resolve = client.post(
            "/api/dm/combat/monster-attacks/resolve",
            json={
                "attacker_cid": 2,
                "target_cid": 1,
                "spend": "action",
                "sequence": [{"attack_key": "scimitar", "count": 2, "roll_mode": "normal"}],
            },
        )
        self.assertEqual(200, resolve.status_code)
        resolve_payload = resolve.json()
        self.assertTrue(resolve_payload["ok"])
        self.assertTrue(resolve_payload["result"]["ok"])
        self.assertEqual("action", resolve_payload["result"]["spend"])
        self.assertTrue(
            any(
                call["attacker_cid"] == 2 and call["target_cid"] == 1
                for call in lan._tracker.dm_monster_attack_resolve_calls
            )
        )

        apply_damage = client.post(
            "/api/dm/combat/monster-attacks/apply-damage",
            json={
                "attacker_cid": 2,
                "target_cid": 1,
                "attack_name": "Scimitar",
                "damage_entries": [{"type": "slashing", "amount": 5}],
            },
        )
        self.assertEqual(200, apply_damage.status_code)
        damage_payload = apply_damage.json()
        self.assertTrue(damage_payload["ok"])
        self.assertTrue(damage_payload["result"]["ok"])
        self.assertEqual(2, damage_payload["result"]["target_hp"])
        self.assertTrue(
            any(
                call["attacker_cid"] == 2 and call["target_cid"] == 1
                for call in lan._tracker.dm_monster_attack_damage_calls
            )
        )

    def test_dm_monster_action_and_spell_routes(self):
        client, lan = self._build_client()
        action = client.post("/api/dm/combat/combatants/2/perform-action", json={"action": "Nimble Escape"})
        self.assertEqual(200, action.status_code)
        action_payload = action.json()
        self.assertTrue(action_payload["ok"])
        self.assertTrue(action_payload["result"]["ok"])
        self.assertEqual("Nimble Escape", action_payload["result"]["action"])
        self.assertTrue(any(call["actor_cid"] == 2 for call in lan._tracker.dm_monster_perform_action_calls))

        spell = client.post(
            "/api/dm/combat/combatants/2/spell-target",
            json={"target_cid": 1, "spell_slug": "fire-bolt", "spell_name": "Fire Bolt"},
        )
        self.assertEqual(200, spell.status_code)
        spell_payload = spell.json()
        self.assertTrue(spell_payload["ok"])
        self.assertTrue(spell_payload["result"]["ok"])
        self.assertEqual(1, spell_payload["result"]["target_cid"])
        self.assertTrue(any(call["actor_cid"] == 2 for call in lan._tracker.dm_monster_spell_target_calls))

    def test_map_routes_require_admin_when_password_configured(self):
        client, lan = self._build_client(admin_password_configured=True)
        unauth_new = client.post("/api/dm/map/new", json={"cols": 20, "rows": 20})
        unauth_settings = client.post("/api/dm/map/settings", json={"cols": 22, "rows": 18})
        unauth_obstacle = client.post("/api/dm/map/obstacles/cell", json={"col": 2, "row": 2, "blocked": True})
        unauth_ship = client.post("/api/dm/map/ships", json={"blueprint_id": "sloop", "anchor_col": 2, "anchor_row": 2})
        unauth_ship_engagement = client.get("/api/dm/map/ships/ship_1/engagement")
        unauth_bg_order = client.post("/api/dm/map/backgrounds/1/order", json={"direction": "front"})
        unauth_monster_attacks = client.get("/api/dm/combat/combatants/2/monster-attacks")
        unauth_monster_action = client.post("/api/dm/combat/combatants/2/perform-action", json={"action": "Strike"})
        self.assertEqual(401, unauth_new.status_code)
        self.assertEqual(401, unauth_settings.status_code)
        self.assertEqual(401, unauth_obstacle.status_code)
        self.assertEqual(401, unauth_ship.status_code)
        self.assertEqual(401, unauth_ship_engagement.status_code)
        self.assertEqual(401, unauth_bg_order.status_code)
        self.assertEqual(401, unauth_monster_attacks.status_code)
        self.assertEqual(401, unauth_monster_action.status_code)
        headers = self._auth_headers(client, lan)
        auth_new = client.post("/api/dm/map/new", json={"cols": 20, "rows": 20}, headers=headers)
        auth_settings = client.post("/api/dm/map/settings", json={"cols": 22, "rows": 18}, headers=headers)
        auth_obstacle = client.post("/api/dm/map/obstacles/cell", json={"col": 2, "row": 2, "blocked": True}, headers=headers)
        auth_ship = client.post(
            "/api/dm/map/ships",
            json={"blueprint_id": "sloop", "anchor_col": 2, "anchor_row": 2},
            headers=headers,
        )
        auth_ship_engagement = client.get("/api/dm/map/ships/ship_1/engagement", headers=headers)
        auth_bg_order = client.post("/api/dm/map/backgrounds/1/order", json={"direction": "front"}, headers=headers)
        auth_monster_attacks = client.get("/api/dm/combat/combatants/2/monster-attacks", headers=headers)
        auth_monster_action = client.post(
            "/api/dm/combat/combatants/2/perform-action",
            json={"action": "Strike"},
            headers=headers,
        )
        self.assertEqual(200, auth_new.status_code)
        self.assertEqual(200, auth_settings.status_code)
        self.assertEqual(200, auth_obstacle.status_code)
        self.assertEqual(200, auth_ship.status_code)
        self.assertEqual(200, auth_ship_engagement.status_code)
        self.assertEqual(200, auth_bg_order.status_code)
        self.assertEqual(200, auth_monster_attacks.status_code)
        self.assertEqual(200, auth_monster_action.status_code)


class _TrackerTacticalHarness:
    _capture_canonical_map_state = tracker_mod.InitiativeTracker._capture_canonical_map_state
    _apply_canonical_map_state = tracker_mod.InitiativeTracker._apply_canonical_map_state
    _broadcast_tactical_state_update = tracker_mod.InitiativeTracker._broadcast_tactical_state_update
    _mutate_canonical_map_state = tracker_mod.InitiativeTracker._mutate_canonical_map_state
    _next_map_entity_id = tracker_mod.InitiativeTracker._next_map_entity_id
    _normalize_tactical_entity_payload = tracker_mod.InitiativeTracker._normalize_tactical_entity_payload
    _upsert_map_feature = tracker_mod.InitiativeTracker._upsert_map_feature
    _remove_map_feature = tracker_mod.InitiativeTracker._remove_map_feature
    _upsert_map_structure = tracker_mod.InitiativeTracker._upsert_map_structure
    _remove_map_structure = tracker_mod.InitiativeTracker._remove_map_structure
    _set_map_elevation = tracker_mod.InitiativeTracker._set_map_elevation
    _dm_tactical_snapshot_from_lan_snapshot = staticmethod(tracker_mod.InitiativeTracker._dm_tactical_snapshot_from_lan_snapshot)
    _dm_tactical_snapshot = tracker_mod.InitiativeTracker._dm_tactical_snapshot
    _dm_move_combatant_on_map = tracker_mod.InitiativeTracker._dm_move_combatant_on_map
    _dm_place_combatant_on_map = tracker_mod.InitiativeTracker._dm_place_combatant_on_map
    _dm_set_combatant_facing = tracker_mod.InitiativeTracker._dm_set_combatant_facing
    _dm_normalize_turn_spend = staticmethod(tracker_mod.InitiativeTracker._dm_normalize_turn_spend)
    _dm_validate_monster_actor_for_turn = tracker_mod.InitiativeTracker._dm_validate_monster_actor_for_turn
    _dm_spend_combatant_turn_resource = tracker_mod.InitiativeTracker._dm_spend_combatant_turn_resource
    _dm_monster_attack_options = tracker_mod.InitiativeTracker._dm_monster_attack_options
    _dm_resolve_monster_attack_sequence = tracker_mod.InitiativeTracker._dm_resolve_monster_attack_sequence
    _dm_apply_monster_attack_damage = tracker_mod.InitiativeTracker._dm_apply_monster_attack_damage
    _dm_monster_perform_action = tracker_mod.InitiativeTracker._dm_monster_perform_action
    _dm_monster_spell_target = tracker_mod.InitiativeTracker._dm_monster_spell_target
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
    _dm_reorder_background_layer = tracker_mod.InitiativeTracker._dm_reorder_background_layer
    _dm_list_background_assets = tracker_mod.InitiativeTracker._dm_list_background_assets
    _dm_ship_engagement_summary = tracker_mod.InitiativeTracker._dm_ship_engagement_summary
    _dm_sync_ship_engagement_state = tracker_mod.InitiativeTracker._dm_sync_ship_engagement_state
    _dm_ship_maneuver_on_map = tracker_mod.InitiativeTracker._dm_ship_maneuver_on_map
    _dm_ship_fire_weapon_on_map = tracker_mod.InitiativeTracker._dm_ship_fire_weapon_on_map
    _dm_ship_ram_on_map = tracker_mod.InitiativeTracker._dm_ship_ram_on_map
    _lan_tactical_entity_view = tracker_mod.InitiativeTracker._lan_tactical_entity_view
    _lan_asset_url_for_path = staticmethod(tracker_mod.InitiativeTracker._lan_asset_url_for_path)
    _normalize_facing_degrees = tracker_mod.InitiativeTracker._normalize_facing_degrees

    def __init__(self) -> None:
        self.combatants = {
            1: types.SimpleNamespace(
                cid=1,
                name="Aelar",
                is_pc=True,
                hp=20,
                max_hp=20,
                rider_cid=None,
                mounted_by_cid=None,
                facing_deg=0,
            ),
            2: types.SimpleNamespace(cid=2, name="Goblin", is_pc=False, hp=7, max_hp=7, rider_cid=None, mounted_by_cid=None),
        }
        self.positions = {1: (1, 1)}
        self.current_cid = 2
        self.in_combat = True
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
        self.broadcast_include_static: list = []
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

    def _lan_force_state_broadcast(self, include_static=True):
        self.broadcast_calls += 1
        self.broadcast_include_static.append(bool(include_static))

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

    def test_dm_tactical_snapshot_projection_helper_reuses_lan_shape(self):
        payload = _TrackerTacticalHarness._dm_tactical_snapshot_from_lan_snapshot(
            {
                "grid": {"cols": 8, "rows": 6, "feet_per_square": 5.0},
                "units": [{"cid": 1, "pos": {"col": 2, "row": 3}}],
                "spell_presets": ["ignored"],
            }
        )
        self.assertEqual(8, payload["grid"]["cols"])
        self.assertEqual({"col": 2, "row": 3}, payload["units"][0]["pos"])
        self.assertNotIn("spell_presets", payload)

    def test_dm_move_combatant_on_map_routes_through_lan_move_and_broadcasts(self):
        app = _TrackerTacticalHarness()
        result = app._dm_move_combatant_on_map(1, 3, 2)
        self.assertTrue(result["ok"])
        self.assertEqual(15, result["spent_ft"])
        self.assertEqual((3, 2), app.positions[1])
        self.assertEqual([{"cid": 1, "col": 3, "row": 2}], app.move_calls)
        self.assertEqual(1, app.broadcast_calls)
        self.assertEqual([False], app.broadcast_include_static)

    def test_dm_place_combatant_on_map_updates_position_and_logs(self):
        app = _TrackerTacticalHarness()
        result = app._dm_place_combatant_on_map(1, 5, 6)
        self.assertTrue(result["ok"])
        self.assertEqual((5, 6), app.positions[1])
        self.assertIn(1, app.synced_aoes)
        self.assertIn(1, app.tethered)
        self.assertEqual(1, app.broadcast_calls)
        self.assertEqual([False], app.broadcast_include_static)
        self.assertTrue(any("placed on map" in entry["message"] for entry in app.log_messages))

    def test_dm_set_combatant_facing_normalizes_and_broadcasts(self):
        app = _TrackerTacticalHarness()
        result = app._dm_set_combatant_facing(1, 450)
        self.assertTrue(result["ok"])
        self.assertEqual(90, result["facing_deg"])
        self.assertEqual(90, getattr(app.combatants[1], "facing_deg"))
        self.assertEqual(1, app.broadcast_calls)
        self.assertEqual([False], app.broadcast_include_static)

    def test_dm_monster_turn_spend_normalization(self):
        self.assertEqual("action", _TrackerTacticalHarness._dm_normalize_turn_spend("actions"))
        self.assertEqual("bonus", _TrackerTacticalHarness._dm_normalize_turn_spend("bonus_action"))
        self.assertEqual("reaction", _TrackerTacticalHarness._dm_normalize_turn_spend("reaction"))
        self.assertEqual("none", _TrackerTacticalHarness._dm_normalize_turn_spend("none", allow_none=True))
        self.assertIsNone(_TrackerTacticalHarness._dm_normalize_turn_spend("none", allow_none=False))
        self.assertIsNone(_TrackerTacticalHarness._dm_normalize_turn_spend("mystery"))

    def test_dm_validate_monster_actor_for_turn_enforces_non_pc_and_turn(self):
        app = _TrackerTacticalHarness()
        actor, error, actor_cid = app._dm_validate_monster_actor_for_turn(2)
        self.assertIsNone(error)
        self.assertEqual(2, actor_cid)
        self.assertEqual("Goblin", getattr(actor, "name", ""))

        _, pc_error, _ = app._dm_validate_monster_actor_for_turn(1)
        self.assertEqual("Monster control only supports non-PC combatants.", pc_error)

        app.current_cid = 1
        _, turn_error, _ = app._dm_validate_monster_actor_for_turn(2)
        self.assertEqual("It's not that combatant's turn.", turn_error)

    def test_dm_monster_attack_options_and_resolve_helpers_use_existing_attack_engine(self):
        app = _TrackerTacticalHarness()
        app._monster_attack_options_for_map = lambda _attacker: (
            [
                {
                    "key": "scimitar",
                    "label": "Scimitar",
                    "to_hit": 4,
                    "damage": [{"amount": 5, "roll": "1d6+2", "type": "slashing"}],
                }
            ],
            {"scimitar": 2},
        )
        app._monster_multiattack_description_for_map = lambda _attacker: "The goblin makes two scimitar attacks."
        app._build_map_attack_sequence_defaults = (
            lambda _attacker, _options, _counts: [{"attack_key": "scimitar", "count": 2, "roll_mode": "normal"}]
        )
        app._use_action = lambda _combatant: True
        app._use_bonus_action = lambda _combatant: True
        app._use_reaction = lambda _combatant: True
        resolve_calls: list = []
        app._resolve_map_attack_sequence = (
            lambda attacker_cid, target_cid, blocks: (
                resolve_calls.append(
                    {
                        "attacker_cid": int(attacker_cid),
                        "target_cid": int(target_cid),
                        "blocks": list(blocks),
                    }
                )
                or {
                    "ok": True,
                    "reason": "Resolved.",
                    "results": [
                        {
                            "attack_name": "Scimitar",
                            "hit": True,
                            "damage_rolls": [{"type": "slashing", "default_total": 5}],
                        }
                    ],
                }
            )
        )
        options = app._dm_monster_attack_options(2)
        self.assertTrue(options["ok"])
        self.assertEqual(2, options["multiattack_counts"]["scimitar"])
        self.assertEqual("scimitar", options["default_sequence"][0]["attack_key"])

        result = app._dm_resolve_monster_attack_sequence(
            attacker_cid=2,
            target_cid=1,
            sequence_blocks=[{"attack_key": "scimitar", "count": 2, "roll_mode": "normal"}],
            spend="action",
        )
        self.assertTrue(result["ok"])
        self.assertEqual("action", result["spend"])
        self.assertEqual(1, len(resolve_calls))
        self.assertEqual(1, app.broadcast_calls)
        self.assertEqual(1, app.rebuild_calls)

    def test_dm_monster_perform_action_helper_dispatches_player_command_service(self):
        app = _TrackerTacticalHarness()
        app._use_action = lambda _combatant: True
        app._use_bonus_action = lambda _combatant: True
        app._use_reaction = lambda _combatant: True
        calls: list = []

        class _PlayerCommands:
            def perform_action(self, msg, *, cid, ws_id, is_admin):
                calls.append({"msg": dict(msg), "cid": int(cid), "ws_id": ws_id, "is_admin": bool(is_admin)})
                return {"ok": True}

        app._ensure_player_commands = lambda: _PlayerCommands()
        result = app._dm_monster_perform_action(actor_cid=2, action_name="Nimble Escape", spend="action")
        self.assertTrue(result["ok"])
        self.assertEqual("Nimble Escape", result["action"])
        self.assertEqual(1, len(calls))
        self.assertEqual(2, calls[0]["cid"])
        self.assertFalse(calls[0]["is_admin"])
        self.assertEqual("perform_action", calls[0]["msg"]["type"])

    def test_dm_monster_spell_target_helper_dispatches_existing_spell_target_request(self):
        app = _TrackerTacticalHarness()
        app._use_action = lambda _combatant: True
        app._use_bonus_action = lambda _combatant: True
        app._use_reaction = lambda _combatant: True
        app._find_spell_preset = lambda _slug, _spell_id: {"slug": "fire-bolt", "id": "fire_bolt", "name": "Fire Bolt"}
        app._is_produce_flame_spell_key = lambda *_args, **_kwargs: False
        calls: list = []

        class _PlayerCommands:
            def spell_target_request(self, msg, *, cid, ws_id, is_admin):
                calls.append({"msg": dict(msg), "cid": int(cid), "ws_id": ws_id, "is_admin": bool(is_admin)})
                msg["_spell_target_result"] = {"ok": True, "reason": "resolved"}
                return {"ok": True}

        app._ensure_player_commands = lambda: _PlayerCommands()
        result = app._dm_monster_spell_target(
            actor_cid=2,
            payload={"target_cid": 1, "spell_slug": "fire-bolt", "spell_name": "Fire Bolt", "spend": "action"},
        )
        self.assertTrue(result["ok"])
        self.assertFalse(result["pending"])
        self.assertEqual(1, result["target_cid"])
        self.assertEqual(1, len(calls))
        self.assertEqual(2, calls[0]["cid"])
        self.assertFalse(calls[0]["is_admin"])
        self.assertEqual("spell_target_request", calls[0]["msg"]["type"])
        self.assertEqual(1, calls[0]["msg"]["target_cid"])

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
        self.assertEqual([False, False, False], app.broadcast_include_static)

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

    def test_dm_background_reorder_helper_resequences_layer_bids(self):
        app = _TrackerTacticalHarness()
        repo_root = Path(__file__).resolve().parent.parent
        assets_dir = repo_root / "assets"
        test_asset_a = assets_dir / "_dm_web_bg_order_a.png"
        test_asset_b = assets_dir / "_dm_web_bg_order_b.png"
        test_asset_a.write_bytes(b"a")
        test_asset_b.write_bytes(b"b")
        try:
            first = app._dm_upsert_background_layer(asset_path="/assets/_dm_web_bg_order_a.png", x=0, y=0)
            second = app._dm_upsert_background_layer(asset_path="/assets/_dm_web_bg_order_b.png", x=1, y=1)
            self.assertTrue(first["ok"])
            self.assertTrue(second["ok"])
            second_bid = int(second["background"]["bid"])
            reorder = app._dm_reorder_background_layer(bid=second_bid, direction="back")
            self.assertTrue(reorder["ok"])
            self.assertEqual(1, int(reorder["bid"]))
            state_after = app._capture_canonical_map_state(prefer_window=True).normalized()
            presentation = state_after.presentation if isinstance(state_after.presentation, dict) else {}
            layers = presentation.get("bg_images") if isinstance(presentation.get("bg_images"), list) else []
            ordered_paths = [str(layer.get("path")) for layer in layers if isinstance(layer, dict)]
            self.assertGreaterEqual(len(ordered_paths), 2)
            self.assertTrue(ordered_paths[0].endswith("/assets/_dm_web_bg_order_b.png"))
            self.assertTrue(ordered_paths[1].endswith("/assets/_dm_web_bg_order_a.png"))
        finally:
            if test_asset_a.exists():
                test_asset_a.unlink()
            if test_asset_b.exists():
                test_asset_b.unlink()

    def test_dm_ship_engagement_helper_family_wraps_ship_ops_and_sync(self):
        app = types.SimpleNamespace()
        sync_calls: list = []
        app._dm_sync_ship_engagement_state = lambda: sync_calls.append("sync")
        app._selected_ship_summary = lambda sid: {"ok": True, "structure_id": str(sid), "ship_id": f"runtime_{sid}"}
        app._ship_engagement_maneuver = (
            lambda sid, action, *, steps, preview_only: {
                "ok": True,
                "sid": str(sid),
                "maneuver": str(action),
                "steps": int(steps),
                "preview_only": bool(preview_only),
            }
        )
        app._ship_engagement_fire_weapon = (
            lambda source_id, weapon_id, target_id, target_component_id=None: {
                "ok": True,
                "source_id": str(source_id),
                "target_id": str(target_id),
                "weapon_id": str(weapon_id),
                "target_component_id": target_component_id,
            }
        )
        app._ship_engagement_ram = (
            lambda source_id, target_id: {
                "ok": True,
                "source_id": str(source_id),
                "target_id": str(target_id),
            }
        )

        preview = tracker_mod.InitiativeTracker._dm_ship_maneuver_on_map(
            app,
            structure_id="ship_a",
            maneuver="move_forward",
            steps=2,
            preview_only=True,
        )
        self.assertTrue(preview["ok"])
        self.assertTrue(preview["preview_only"])
        self.assertEqual([], sync_calls)

        applied = tracker_mod.InitiativeTracker._dm_ship_maneuver_on_map(
            app,
            structure_id="ship_a",
            maneuver="move_forward",
            steps=2,
            preview_only=False,
        )
        self.assertTrue(applied["ok"])
        self.assertFalse(applied["preview_only"])
        self.assertEqual(["sync"], sync_calls)

        fired = tracker_mod.InitiativeTracker._dm_ship_fire_weapon_on_map(
            app,
            source_structure_id="ship_a",
            target_structure_id="ship_b",
            weapon_id="ballista",
            target_component_id="hull",
        )
        self.assertTrue(fired["ok"])
        self.assertEqual("ballista", fired["result"]["weapon_id"])

        rammed = tracker_mod.InitiativeTracker._dm_ship_ram_on_map(
            app,
            source_structure_id="ship_a",
            target_structure_id="ship_b",
        )
        self.assertTrue(rammed["ok"])
        self.assertEqual("ship_b", rammed["result"]["target_id"])
        self.assertEqual(3, len(sync_calls))

    def test_dm_ship_preview_helper_wraps_ship_blueprint_preview_semantics(self):
        app = types.SimpleNamespace()
        app._dm_validate_map_cell = lambda _col, _row: None
        app._ship_blueprint_placement_preview = (
            lambda _blueprint_id, *, anchor_col, anchor_row, facing_deg: {
                "ok": False,
                "target_cells": [{"col": int(anchor_col), "row": int(anchor_row)}],
                "blockers": {"ok": False, "blockers": {"structures": [{"id": "structure_1"}]}},
                "facing_deg": float(facing_deg),
            }
        )

        blocked = tracker_mod.InitiativeTracker._dm_preview_ship_blueprint_on_map(
            app,
            blueprint_id="sloop",
            anchor_col=4,
            anchor_row=5,
            facing_deg=90,
        )
        self.assertFalse(blocked["ok"])
        self.assertEqual("ship_blueprint_blocked", blocked["reason"])
        self.assertIn("structures", blocked["blockers"]["blockers"])

        app._ship_blueprint_placement_preview = (
            lambda _blueprint_id, *, anchor_col, anchor_row, facing_deg: {
                "ok": True,
                "blueprint_id": "sloop",
                "anchor_col": int(anchor_col),
                "anchor_row": int(anchor_row),
                "facing_deg": float(facing_deg),
                "target_cells": [{"col": int(anchor_col), "row": int(anchor_row)}],
                "blockers": {"ok": True, "blockers": {}},
            }
        )
        clear = tracker_mod.InitiativeTracker._dm_preview_ship_blueprint_on_map(
            app,
            blueprint_id="sloop",
            anchor_col=6,
            anchor_row=2,
            facing_deg=180,
        )
        self.assertTrue(clear["ok"])
        self.assertEqual("sloop", clear["blueprint_id"])
        self.assertEqual(180.0, clear["facing_deg"])

    def test_dm_boarding_link_helper_family_wraps_existing_boarding_mutators(self):
        app = types.SimpleNamespace()
        app._create_boarding_link = (
            lambda _source_id, _target_id, **_kwargs: {
                "ok": True,
                "boarding_link": {"id": "boarding_link_1", "source_id": "ship_a", "target_id": "ship_b", "status": "active"},
                "message": "created",
            }
        )
        app._set_boarding_link_status = (
            lambda **kwargs: {
                "ok": True,
                "boarding_link_id": str(kwargs.get("link_id") or ""),
                "status": None if kwargs.get("remove") else str(kwargs.get("status") or ""),
                "message": "updated",
            }
        )
        app._boarding_links = lambda: [{"id": "boarding_link_1", "status": "withdrawn"}]

        created = tracker_mod.InitiativeTracker._dm_upsert_boarding_link_on_map(
            app,
            source_structure_id="ship_a",
            target_structure_id="ship_b",
            status="active",
            notes="gangplank",
        )
        self.assertTrue(created["ok"])
        self.assertEqual("boarding_link_1", created["boarding_link"]["id"])

        updated = tracker_mod.InitiativeTracker._dm_set_boarding_link_status_on_map(
            app,
            link_id="boarding_link_1",
            status="withdrawn",
            notes="pulled away",
        )
        self.assertTrue(updated["ok"])
        self.assertEqual("withdrawn", updated["status"])
        self.assertEqual("boarding_link_1", updated["boarding_link"]["id"])

        removed = tracker_mod.InitiativeTracker._dm_remove_boarding_link_on_map(
            app,
            link_id="boarding_link_1",
        )
        self.assertTrue(removed["ok"])
        self.assertEqual("boarding_link_1", removed["boarding_link_id"])


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

    def test_combined_snapshot_uses_precomputed_tactical_payload_when_provided(self):
        lan = object.__new__(tracker_mod.LanController)
        lan._tracker = types.SimpleNamespace(
            _dm_tactical_snapshot=lambda: (_ for _ in ()).throw(AssertionError("unexpected tactical snapshot call"))
        )
        lan._dm_service = types.SimpleNamespace(combat_snapshot=lambda: {"in_combat": False})
        payload = tracker_mod.LanController._dm_console_snapshot_payload(
            lan,
            tactical_snapshot={"grid": {"cols": 9, "rows": 9}, "units": []},
        )
        self.assertEqual(9, payload["tactical_map"]["grid"]["cols"])


class DmTacticalMapHtmlSurfaceTests(unittest.TestCase):
    def test_dm_console_contains_tactical_map_controls(self):
        html = _DM_HTML_PATH.read_text(encoding="utf-8")
        self.assertIn('data-dm-workspace="__DM_WORKSPACE__"', html)
        self.assertIn('id="workspaceNavLink"', html)
        self.assertIn('id="mapWorkspacePanel"', html)
        self.assertIn('id="mapSetupCard"', html)
        self.assertIn('id="tacticalMapCard"', html)
        self.assertIn('id="monsterTurnCard"', html)
        self.assertIn('id="mapColsInput"', html)
        self.assertIn('id="mapRowsInput"', html)
        self.assertIn('id="createMapBtn"', html)
        self.assertIn('id="applyMapSettingsBtn"', html)
        self.assertIn('id="tacticalMapCanvas"', html)
        self.assertIn('id="mapActionModeSelect"', html)
        self.assertIn('id="applyMapActionBtn"', html)
        self.assertIn('id="setFacingBtn"', html)
        self.assertIn('id="applyCellModeBtn"', html)
        self.assertIn('id="monsterActorCidSelect"', html)
        self.assertIn('id="monsterTargetCidSelect"', html)
        self.assertIn('id="monsterSpendSelect"', html)
        self.assertIn('id="loadMonsterAttacksBtn"', html)
        self.assertIn('id="monsterAttackSelect"', html)
        self.assertIn('id="resolveMonsterAttackBtn"', html)
        self.assertIn('id="applyMonsterDamageBtn"', html)
        self.assertIn('id="performMonsterActionBtn"', html)
        self.assertIn('id="castMonsterSpellBtn"', html)
        self.assertIn('id="hazardPresetSelect"', html)
        self.assertIn('id="placeHazardBtn"', html)
        self.assertIn('id="featurePresetSelect"', html)
        self.assertIn('id="placeFeatureBtn"', html)
        self.assertIn('id="structurePresetSelect"', html)
        self.assertIn('id="placeStructureBtn"', html)
        self.assertIn('id="structureTemplateSelect"', html)
        self.assertIn('id="placeTemplateBtn"', html)
        self.assertIn('id="shipBlueprintSelect"', html)
        self.assertIn('id="previewShipBtn"', html)
        self.assertIn('id="placeShipBtn"', html)
        self.assertIn('id="boardingSourceStructureSelect"', html)
        self.assertIn('id="boardingTargetStructureSelect"', html)
        self.assertIn('id="boardingLinkSelect"', html)
        self.assertIn('id="upsertBoardingLinkBtn"', html)
        self.assertIn('id="setBoardingLinkStatusBtn"', html)
        self.assertIn('id="removeBoardingLinkBtn"', html)
        self.assertIn('id="shipEngagementSourceStructureSelect"', html)
        self.assertIn('id="shipEngagementTargetStructureSelect"', html)
        self.assertIn('id="previewShipManeuverBtn"', html)
        self.assertIn('id="applyShipManeuverBtn"', html)
        self.assertIn('id="shipEngagementWeaponSelect"', html)
        self.assertIn('id="shipEngagementComponentSelect"', html)
        self.assertIn('id="fireShipWeaponBtn"', html)
        self.assertIn('id="ramShipTargetBtn"', html)
        self.assertIn('id="shipEngagementState"', html)
        self.assertIn('id="applyElevationBtn"', html)
        self.assertIn('id="bgAssetSelect"', html)
        self.assertIn('id="upsertBackgroundBtn"', html)
        self.assertIn('id="bgLayerBackBtn"', html)
        self.assertIn('id="bgLayerDownBtn"', html)
        self.assertIn('id="bgLayerUpBtn"', html)
        self.assertIn('id="bgLayerFrontBtn"', html)
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
        self.assertIn("/api/dm/map/ship-blueprints", html)
        self.assertIn("/api/dm/map/ships", html)
        self.assertIn("/api/dm/map/ships/{structure_id}/engagement", html)
        self.assertIn("/api/dm/map/ships/{structure_id}/maneuver-preview", html)
        self.assertIn("/api/dm/map/ships/{structure_id}/maneuver", html)
        self.assertIn("/api/dm/map/ships/{source_structure_id}/weapons/fire", html)
        self.assertIn("/api/dm/map/ships/{source_structure_id}/ram", html)
        self.assertIn("/api/dm/map/structure-templates", html)
        self.assertIn("/api/dm/map/boarding-links", html)
        self.assertIn("/api/dm/map/elevation/cell", html)
        self.assertIn("/api/dm/map/backgrounds/assets", html)
        self.assertIn("/api/dm/map/backgrounds", html)
        self.assertIn("/api/dm/map/backgrounds/{bid}/order", html)
        self.assertIn("/api/dm/map/aoes", html)
        self.assertIn("/api/dm/map/overlays/auras", html)
        self.assertIn("/api/dm/map/combatants/${cid}/facing", html)
        self.assertIn("/api/dm/combat/combatants/{cid}/monster-attacks", html)
        self.assertIn("/api/dm/combat/monster-attacks/resolve", html)
        self.assertIn("/api/dm/combat/monster-attacks/apply-damage", html)
        self.assertIn("/api/dm/combat/combatants/{cid}/perform-action", html)
        self.assertIn("/api/dm/combat/combatants/{cid}/spell-target", html)


if __name__ == "__main__":
    unittest.main()
