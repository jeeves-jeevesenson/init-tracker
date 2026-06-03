from __future__ import annotations
import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

@dataclass(frozen=True)
class AoeSpec:
    shape: str  # cone, cube, cylinder, line, sphere, wall
    origin_mode: str  # point, caster
    origin_col: float
    origin_row: float
    target_col: Optional[float] = None  # For directional AoEs (aim point)
    target_row: Optional[float] = None
    radius_ft: float = 0.0
    length_ft: float = 0.0
    width_ft: float = 0.0
    height_ft: float = 0.0
    include_origin: bool = True
    persistent: bool = False
    concentration: bool = False
    spell_id: str = ""
    spell_name: str = ""
    
    # Optional metadata for logging/resolution
    save_type: str = ""
    damage_type: str = ""
    dc: Optional[int] = None

@dataclass(frozen=True)
class SpellCastResult:
    ok: bool
    status: str
    spell_id: str
    spell_name: str
    caster_cid: Optional[int] = None
    message: str = ""
    target_cids: List[int] = None
    aoe_ids_added: List[str] = None
    aoe_ids_removed: List[str] = None
    reason: Optional[str] = None
    needs_manual_damage: bool = False
    
    def __post_init__(self):
        if self.target_cids is None:
            object.__setattr__(self, "target_cids", [])
        if self.aoe_ids_added is None:
            object.__setattr__(self, "aoe_ids_added", [])
        if self.aoe_ids_removed is None:
            object.__setattr__(self, "aoe_ids_removed", [])

def resolve_aoe_cells(spec: AoeSpec, grid_cols: int, grid_rows: int, feet_per_square: float) -> Set[Tuple[int, int]]:
    """
    Returns a set of (col, row) coordinates covered by the AOE.
    This is useful for highlighting the map or checking for effects.
    """
    affected_cells: Set[Tuple[int, int]] = set()
    
    # We could optimize by only checking cells within a bounding box
    # For now, let's keep it simple or use the logic from _lan_compute_included_units_for_aoe
    
    # Bounding box calculation
    max_dim_ft = max(spec.radius_ft, spec.length_ft, spec.width_ft)
    max_dim_sq = max_dim_ft / feet_per_square
    
    min_c = max(0, int(spec.origin_col - max_dim_sq - 2))
    max_c = min(grid_cols - 1, int(spec.origin_col + max_dim_sq + 2))
    min_r = max(0, int(spec.origin_row - max_dim_sq - 2))
    max_r = min(grid_rows - 1, int(spec.origin_row + max_dim_sq + 2))
    
    for c in range(min_c, max_c + 1):
        for r in range(min_r, max_r + 1):
            if is_cell_in_aoe(c, r, spec, feet_per_square):
                affected_cells.add((c, r))
                
    return affected_cells

def is_cell_in_aoe(col: int, row: int, spec: AoeSpec, feet_per_square: float) -> bool:
    """
    Checks if a specific cell (center point) is within the AOE.
    """
    cx, cy = spec.origin_col, spec.origin_row
    px, py = float(col) + 0.5, float(row) + 0.5
    
    dx = px - cx
    dy = py - cy
    dist_sq = dx*dx + dy*dy
    
    if spec.shape in ("circle", "sphere", "cylinder", "radius"):
        r_sq = spec.radius_ft / feet_per_square
        return dist_sq <= r_sq * r_sq
        
    elif spec.shape in ("cube", "square"):
        # 5e rules: A cube's point of origin is not its center unless specified.
        # However, for manual placement (point cube), it's often centered or corner-aligned.
        # If origin_mode is 'point', we'll treat origin as center for now or follow the payload.
        # If it's Thunderwave style, it's usually self-origin.
        
        dim_ft = spec.length_ft if spec.length_ft > 0 else spec.radius_ft
        half_side = (dim_ft / feet_per_square) / 2.0
        
        if spec.origin_mode == "caster" and spec.target_col is not None:
            # Thunderwave style: 15ft cube originating from caster.
            # We use target_col/row to determine the direction.
            tx, ty = spec.target_col, spec.target_row
            v_dx, v_dy = tx - cx, ty - cy
            
            # Center of cube is 1.5 squares (7.5ft) away from caster center in that direction
            # if the side is 3 squares (15ft).
            side_sq = dim_ft / feet_per_square
            offset = side_sq / 2.0

            # Simple 4-way alignment for now
            if abs(v_dx) > abs(v_dy):
                real_cx = cx + (offset if v_dx > 0 else -offset)
                real_cy = cy
            else:
                real_cx = cx
                real_cy = cy + (offset if v_dy > 0 else -offset)
            
            return abs(px - real_cx) <= half_side and abs(py - real_cy) <= half_side
            
        # Generic centered cube/square
        return abs(dx) <= half_side and abs(dy) <= half_side

    elif spec.shape == "line":
        if spec.target_col is None:
            return False
        
        tx, ty = spec.target_col, spec.target_row
        v_dx, v_dy = tx - cx, ty - cy
        length_sq = math.hypot(v_dx, v_dy)
        if length_sq < 0.001:
            return False
            
        # Normalize direction
        ux, uy = v_dx / length_sq, v_dy / length_sq
        
        # Projection of P-C onto U
        proj = dx * ux + dy * uy
        
        # Distance from line
        perp_x = dx - proj * ux
        perp_y = dy - proj * uy
        perp_dist = math.hypot(perp_x, perp_y)
        
        max_len_sq = spec.length_ft / feet_per_square
        width_sq = (spec.width_ft / feet_per_square) / 2.0
        
        return 0 <= proj <= max_len_sq and perp_dist <= width_sq

    elif spec.shape == "cone":
        if spec.target_col is None:
            return False
            
        tx, ty = spec.target_col, spec.target_row
        v_dx, v_dy = tx - cx, ty - cy
        
        dist = math.hypot(dx, dy)
        max_dist_sq = spec.length_ft / feet_per_square
        
        if dist > max_dist_sq:
            return False
        if dist < 0.001:
            return spec.include_origin
            
        angle_to_px = math.atan2(dy, dx)
        angle_to_target = math.atan2(v_dy, v_dx)
        
        diff = (angle_to_px - angle_to_target + math.pi) % (2 * math.pi) - math.pi
        
        # 5e cone is usually 90 degrees (45 degrees half-angle) or 60?
        # PHB: "A cone's width at a given point along its length is equal to that point's distance from the point of origin."
        # This implies a 53.13 degree total angle? No, it implies width = distance.
        # That means tan(half_angle) = 0.5, so half_angle = 26.56 deg, total = 53.13 deg.
        # Standard cone in many tools is 60 or 90.
        
        # Let's use 53.13 as default or follow spec.
        half_angle = math.radians(53.13 / 2.0)
        return abs(diff) <= half_angle

    return False
