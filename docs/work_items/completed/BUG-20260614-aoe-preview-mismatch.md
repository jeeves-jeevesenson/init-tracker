# BUG-20260614-aoe-preview-mismatch

- **Title**: AoE preview mismatch (Target count/location)
- **Status**: Completed (Closed as Stale/Duplicate)
- **Source bug**: [docs/bug_reports/resolved/BUG-20260614-aoe-preview-mismatch.md](../bug_reports/resolved/BUG-20260614-aoe-preview-mismatch.md)

## Closeout Note (2026-06-17)
This work item was mistakenly opened during triage. The developer confirmed that the AoE preview mismatch was already resolved by [BUG-20260614-player-fireball-preview-applies-one-target](BUG-20260614-player-fireball-preview-applies-one-target.md) (fixed on 2026-06-16). The suspected desync on the DM control surface was found to be stale or already addressed.

## Initial Gate: Gate 1 — Evidence capture and implementation plan (Cancelled)

### Goal
Identify why the AoE preview on the DM control surface does not match the actual spell resolution. Verify if the DM control surface is still using point-sampling math that was previously fixed for the player surface.

### Non-goals
- Do not change monster AI.
- Do not change mount behavior.
- Do not change 1080p layout.
- Do not change weapon attack/reload logic.

## Plan

### Gate 1: Evidence capture and implementation plan
- [ ] Reproduce the mismatch on the DM control surface (via code inspection or manual verification).
- [ ] Inspect `assets/web/dmcontrol/index.html` for AoE preview/targeting logic.
- [ ] Inspect `assets/web/lan/index.html` for the reference fix applied to the player surface.
- [ ] Compare DM surface math with `spell_engine_primitives.py` and backend resolution.
- [ ] Propose a bounded fix plan.

#### Suspected Root Cause
The player-surface AoE preview mismatch (radius loss and coordinate offset) was fixed on 2026-06-16 (see `BUG-20260614-player-fireball-preview-applies-one-target`). However, the DM control surface (`assets/web/dmcontrol/index.html`) likely still uses the old point-sampling math or an inconsistent coordinate system, leading to the reported "2 in range in preview, 1 in roll" discrepancy.

#### Bounded Fix Plan
1.  **Sync DM Surface Math**: Migrate the radius/targeting fixes from `assets/web/lan/index.html` to `assets/web/dmcontrol/index.html`.
2.  **Verify Backend Consistency**: Ensure `spell_engine_primitives.py` and the backend spell engine use the same targeting logic as the UI.
3.  **Validation**:
    *   Mandatory inline JavaScript syntax check for `assets/web/dmcontrol/index.html`.
    *   Focused unit tests for AoE targeting if applicable.
    *   Developer-led browser smoke verification.

### Validation Expectations
- `python3 -m py_compile` on any edited Python files.
- Inline JS syntax check (Node.js `--check`) for edited browser assets.
- Verification that the previewed target count matches the resolution target count.

### Reopen/Close Conditions
- **Close**: Mismatch is resolved and verified on the DM control surface.
- **Reopen**: Regression in AoE targeting or mismatch persists on any surface.
