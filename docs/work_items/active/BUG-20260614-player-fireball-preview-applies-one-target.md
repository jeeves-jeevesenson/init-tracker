# Work Item: BUG-20260614-player-fireball-preview-applies-one-target

- **ID**: BUG-20260614-player-fireball-preview-applies-one-target
- **Title**: Player Fireball AoE preview includes multiple targets but resolution applies to only one
- **Status**: Active
- **Goal**: Identify and resolve the discrepancy between the frontend AoE targeting preview and backend spell resolution.
- **Bug Report**: [docs/bug_reports/triaged/BUG-20260614-player-fireball-preview-applies-one-target.md](../bug_reports/triaged/BUG-20260614-player-fireball-preview-applies-one-target.md)

---

## 1. Evidence and Triage

### Symptom
A player used Fireball, the frontend overlay showed two targets would be hit, but the cast resolution only affected one.

### Suspected Root Cause
1.  **Missing `radius_ft` in Backend Context**: In `_handle_cast_aoe_request`, if the client sends `size` instead of `radius_ft`, the server populates `aoe["radius_sq"]` but leaves `aoe["radius_ft"]` unset. The `AoeSpec` then defaults to `radius_ft=0.0`, making the spell effective only in its origin cell.
2.  **Center-Point Logic Change**: `spell_engine_primitives.py` now uses cell centers (`+ 0.5`) for inclusion checks. This makes radial AoEs effectively smaller than the old integer-corner logic, causing targets at the exact radius boundary to be missed.
3.  **Missing `_lan_get_map_state`**: The method is called during AoE resolution but appears to be missing or returning `None`, causing a fallback to a 20x20 blank grid which might exclude targets on larger maps.

### Evidence
- **Source**: Jun 13 live player smoke test.
- **Unit Test Failures**: `tests/test_spell_aoe_targeting_primitives.py` fails with:
  - `test_sphere_resolution`: Cell `(7, 5)` missed by 10ft radius from `(5, 5)` due to center-point distance (2.54 sq vs 2.0 sq).
  - `test_lan_get_map_state_returns_valid_state`: Returned `None` instead of `MapState`.
- **Static Trace**:
  - `dnd_initative_tracker.py:40502`: `elif shape in ("sphere", "cylinder"):` block does not set `aoe["radius_ft"]` in the `else` (size-based) branch.
  - `dnd_initative_tracker.py:22207`: `AoeSpec` construction uses `float(aoe.get("radius_ft") or 0.0)`.

---

## 2. Execution Plan

### Gate 1: Evidence Capture & Reproduction (Completed)
- **Goal**: Confirm the mismatch between `AoeSpec` visualization and backend unit inclusion.
- **Findings**: Backend `radius_ft` is lost if client sends `size`. Center-point logic and map-state fallback further degrade precision and coverage.

### Gate 2: Implementation (Pending)
- **Goal**: Align the inclusion logic and restore missing state.
- **Action**:
  - Update `_handle_cast_aoe_request` to ensure `radius_ft` is always set for radial shapes (syncing with `radius_sq` if needed).
  - Add missing `_lan_get_map_state` method to `InitiativeTracker`.
  - Refine `is_cell_in_aoe` to match client-side inclusion expectations (e.g. including cells where the center OR any corner is hit, or reverting to integer-based checks if appropriate for the D&D grid).
- **Files**: `dnd_initative_tracker.py`, `spell_engine_primitives.py`.

### Gate 3: Validation (Pending)
- **Goal**: Verify the fix with targeted unit tests and browser smoke check.
- **Action**: Fix `tests/test_spell_aoe_targeting_primitives.py` and add a new regression test covering the `size` vs `radius_ft` discrepancy.

---

## 3. Progress Tracking

- [ ] Gate 1: Evidence Capture & Reproduction
- [ ] Gate 2: Implementation
- [ ] Gate 3: Validation
