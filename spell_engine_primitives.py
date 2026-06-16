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
    Checks if a combatant in this cell is within the AOE using a 50% token footprint coverage rule.
    The 1x1 token footprint is modeled as a circle of radius 0.35 centered in the cell.
    For circular AoEs, uses exact circle-circle overlap area.
    For other shapes, approximates by checking 9 points distributed within that circular footprint.
    If 5 or more points are inside, the token is considered covered.
    """
    center_x, center_y = float(col) + 0.5, float(row) + 0.5
    token_radius = 0.35

    # Deterministic geometry contract: for circular AoEs and circular tokens, use exact overlap area.
    if spec.shape in ("circle", "sphere", "cylinder", "radius"):
        cx, cy = spec.origin_col, spec.origin_row
        dx = center_x - cx
        dy = center_y - cy
        dist = math.hypot(dx, dy)
        aoe_radius = spec.radius_ft / feet_per_square

        overlap = get_circle_circle_overlap_area(aoe_radius, token_radius, dist)
        token_area = math.pi * (token_radius ** 2)
        # Include if >= 50% overlap. Use a small epsilon for floating point boundary equality.
        return overlap >= (token_area * 0.5) - 1e-9

    # Fallback sampling pattern (relative to center) for non-circular AoE shapes:
    # Center (1)
    # Cardinal (4) at distance 0.3
    # Diagonal (4) at distance 0.22
    offsets = [
        (0.0, 0.0),
        (0.3, 0.0), (-0.3, 0.0), (0.0, 0.3), (0.0, -0.3),
        (0.22, 0.22), (-0.22, 0.22), (0.22, -0.22), (-0.22, -0.22)
    ]

    in_count = 0
    for ox, oy in offsets:
        px, py = center_x + ox, center_y + oy
        if is_point_in_aoe(px, py, spec, feet_per_square):
            in_count += 1

    return in_count >= 5

def get_circle_circle_overlap_area(r1: float, r2: float, d: float) -> float:
    """Returns the overlap area between two circles of radii r1 and r2 separated by distance d."""
    if d >= r1 + r2:
        return 0.0
    if d <= abs(r1 - r2):
        return math.pi * (min(r1, r2) ** 2)

    # Standard circle-circle overlap area formula
    r1sq = r1 * r1
    r2sq = r2 * r2
    dsq = d * d

    phi1 = math.acos((dsq + r1sq - r2sq) / (2.0 * d * r1))
    phi2 = math.acos((dsq + r2sq - r1sq) / (2.0 * d * r2))

    area = (r1sq * phi1) + (r2sq * phi2) - (0.5 * math.sqrt((-d + r1 + r2) * (d + r1 - r2) * (d - r1 + r2) * (d + r1 + r2)))
    return area

def is_point_in_aoe(px: float, py: float, spec: AoeSpec, feet_per_square: float) -> bool:
    """
    Checks if a specific point (px, py) is within the AOE.
    """
    cx, cy = spec.origin_col, spec.origin_row
    dx = px - cx
    dy = py - cy
    dist_sq = dx*dx + dy*dy

    if spec.shape in ("circle", "sphere", "cylinder", "radius"):
        r_sq = (spec.radius_ft / feet_per_square) ** 2
        # Use a small epsilon for floating point boundary cases
        return dist_sq <= r_sq + 1e-9

    elif spec.shape in ("cube", "square"):
        dim_ft = spec.length_ft if spec.length_ft > 0 else spec.radius_ft
        half_side = (dim_ft / feet_per_square) / 2.0

        if spec.origin_mode == "caster" and spec.target_col is not None:
            tx, ty = spec.target_col, spec.target_row
            v_dx, v_dy = tx - cx, ty - cy
            side_sq = dim_ft / feet_per_square
            offset = side_sq / 2.0

            if abs(v_dx) > abs(v_dy):
                real_cx = cx + (offset if v_dx > 0 else -offset)
                real_cy = cy
            else:
                real_cx = cx
                real_cy = cy + (offset if v_dy > 0 else -offset)

            return abs(px - real_cx) <= half_side + 1e-9 and abs(py - real_cy) <= half_side + 1e-9

        return abs(dx) <= half_side + 1e-9 and abs(dy) <= half_side + 1e-9

    elif spec.shape == "line":
        if spec.target_col is None:
            return False

        tx, ty = spec.target_col, spec.target_row
        v_dx, v_dy = tx - cx, ty - cy
        length_sq = math.hypot(v_dx, v_dy)
        if length_sq < 0.001:
            return False

        ux, uy = v_dx / length_sq, v_dy / length_sq
        proj = dx * ux + dy * uy
        perp_x = dx - proj * ux
        perp_y = dy - proj * uy
        perp_dist = math.hypot(perp_x, perp_y)

        max_len_sq = spec.length_ft / feet_per_square
        width_sq = (spec.width_ft / feet_per_square) / 2.0

        return -1e-9 <= proj <= max_len_sq + 1e-9 and perp_dist <= width_sq + 1e-9

    elif spec.shape == "cone":
        if spec.target_col is None:
            return False

        tx, ty = spec.target_col, spec.target_row
        v_dx, v_dy = tx - cx, ty - cy

        dist = math.hypot(dx, dy)
        max_dist_sq = spec.length_ft / feet_per_square

        if dist > max_dist_sq + 1e-9:
            return False
        if dist < 0.001:
            return spec.include_origin

        angle_to_px = math.atan2(dy, dx)
        angle_to_target = math.atan2(v_dy, v_dx)
        diff = (angle_to_px - angle_to_target + math.pi) % (2 * math.pi) - math.pi

        half_angle = math.radians(53.13 / 2.0)
        return abs(diff) <= half_angle + 1e-9

    return False

    return False
