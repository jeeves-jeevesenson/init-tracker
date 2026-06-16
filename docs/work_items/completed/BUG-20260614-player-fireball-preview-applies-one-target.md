# Work Item: BUG-20260614-player-fireball-preview-applies-one-target

- **ID**: BUG-20260614-player-fireball-preview-applies-one-target
- **Title**: Player Fireball AoE preview includes multiple targets but resolution applies to only one
- **Status**: Completed
- **Goal**: Identify and resolve the discrepancy between the frontend AoE targeting preview and backend spell resolution.
- **Bug Report**: [docs/bug_reports/resolved/BUG-20260614-player-fireball-preview-applies-one-target.md](../bug_reports/resolved/BUG-20260614-player-fireball-preview-applies-one-target.md)

---

## 1. Evidence and Triage (Completed)

### Symptom
A player used Fireball, the frontend overlay showed two targets would be hit, but the cast resolution only affected one.

### Root Cause
1.  **Missing `radius_ft` in Backend Context**: In `_handle_cast_aoe_request`, if the client sent `size` instead of `radius_ft`, the server populated `aoe["radius_sq"]` but left `aoe["radius_ft"]` unset. This caused the reconstructed `AoeSpec` to default to `0.0` radius.
2.  **Missing `_lan_get_map_state`**: The method was missing from `InitiativeTracker`, causing MapQueryAPI to fallback to a default 20x20 blank state during AoE resolution.
3.  **Coordinate Offset Mismatch**: Backend inclusion logic in `spell_engine_primitives.py` uses cell centers (`+ 0.5`). `InitiativeTracker` was providing integer coordinates for caster-aligned spells, causing a half-square offset that excluded targets at the radius boundary.

### Evidence
- **Source**: Jun 13 live player smoke test.
- **Unit Test Failures**: `tests/test_spell_aoe_targeting_primitives.py` failures confirmed the radius loss and coordinate offset issue.

---

## 2. Execution Plan

### Gate 1: Evidence Capture & Reproduction (Completed)
- **Findings**: Backend `radius_ft` was lost if client sent `size`. Center-point logic and map-state fallback further degraded precision.

### Gate 2: Implementation (Completed)
- **Action**:
  - Updated `_handle_cast_aoe_request` to ensure `radius_ft` is derived from `size` if missing.
  - Implemented `_lan_get_map_state` in `InitiativeTracker` returning the canonical map state.
  - Adjusted caster-aligned origin coordinates to cell centers (`+ 0.5`) in `_normalize_aoe_spec` and `_handle_cast_aoe_request`.
  - Updated `tests/test_spell_aoe_targeting_primitives.py` to use center-aligned coordinates and verified all 7 tests pass.
- **Files**: `dnd_initative_tracker.py`, `tests/test_spell_aoe_targeting_primitives.py`.
### Gate 3: Validation (Failed Smoke Correction - Round 5)
- **Status**: Completed (Correction Pass 5)
- **Symptom Root Cause**:
  - **Render Shift**: The LAN map `renderAoeOverlay` used `gridToScreen(cx, cy)`, which adds `0.5 * zoom` to center indices. However, the backend and preview logic had already normalized `cx` to the absolute center (`col + 0.5`). This resulted in a double-addition of `0.5`, shifting the rendered circle half a square away from its logical center.
  - **Geometry Mismatch**: The 9-point sampling was an approximation that disagreed with the sharp visual boundary of the rendered circle and token.
- **Algorithm**: Deterministic circle-circle overlap area.
  - Token footprint is a circle of radius 0.35 centered at `col + 0.5`.
  - AoE is a circle of radius `R` centered at `cx`.
  - Target is included if the overlap area between these two circles is >= 50% of the token footprint area.
  - Boundary equality (within `1e-9`) counts as included.
  - Fallback to 9-point sampling remains for non-circular AoE shapes (cones, lines, squares) until exact geometry is required for them.
- **Action**:
  - **Fixed Rendering**: Updated `renderAoeOverlay` and `renderDmPreview` in `assets/web/lan/index.html` to use absolute grid coordinates (`panX + cx * zoom`), removing the redundant `0.5` offset.
  - **Fixed Snapping**: Updated `setPendingAoePlacementCursorFromPointer` to snap point-clicks to the center of the cell (`col + 0.5`) to ensure consistent absolute coordinates.
  - **Exact Math**: Implemented `getCircleCircleOverlapArea` in `assets/web/lan/index.html` and `get_circle_circle_overlap_area` in `spell_engine_primitives.py`.
  - **Unified Logic**: Updated `aoeContainsGridPoint` (JS) and `is_cell_in_aoe` (Python) to use the exact overlap math for circular AoEs.
- **Files**: `spell_engine_primitives.py`, `assets/web/lan/index.html`, `tests/test_spell_aoe_targeting_primitives.py`.
- **Validation**:
  - `python3 -m unittest tests.test_spell_aoe_targeting_primitives` passed (9 tests).
  - Mandatory browser-asset JS syntax check passed for `assets/web/lan/index.html`.
  - `git status --short` verified.

### Gate 3: Validation (Failed Smoke Correction - Round 6)
- **Status**: Completed (Correction Pass 6)
- **Precision Restoration**: Restored free-floating AoE aiming for point-click spells like Fireball.
  - Updated `setPendingAoePlacementCursorFromPointer` to use `screenToGridFloat`, allowing fractional grid coordinates for the AoE center.
  - Verified that rendering, preview, and backend resolution all use these fractional absolute grid coordinates.
- **Contract Preservation**:
  - Kept exact circle-circle overlap area targeting (>= 50% coverage).
  - Kept absolute grid rendering (no double 0.5 offset).
  - Kept caster-origin snap-to-center behavior.
- **Action**:
  - Modified `assets/web/lan/index.html` to capture precise pointer coordinates.
  - Added `test_fractional_center` to `tests/test_spell_aoe_targeting_primitives.py` verifying that fractional centers correctly include/exclude targets.
- **Validation**:
  - `python3 -m unittest tests.test_spell_aoe_targeting_primitives` passed (10 tests).
  - Mandatory browser-asset JS syntax check passed.

### Gate 4: Closure
- **Status**: Completed
- **Final Commit**: ccbd6a8
- **Developer Smoke Result**: Passed
- **Final Behavior**:
  - Free-floating Fireball aim restored.
  - Rendered circle is the source of truth for targeting.
  - Targets included only when >= 50% of the visible token footprint (radius 0.35) is covered by the AoE.
  - Preview panel and resolution match exactly by target identity.
- **Future Follow-up**: An optional automated harness to test all AoE spells against the deterministic geometry contract could be implemented later to prevent regressions.

---

## 3. Progress Tracking

- [x] Gate 1: Evidence Capture & Reproduction
- [x] Gate 2: Implementation
- [x] Gate 3: Validation
- [x] Gate 4: Closure
