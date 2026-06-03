# Research: Scorcher AoE Smoke Failure (2026-06-01)

## Overview
On 2026-06-01, a browser smoke test was performed on the VDA Scorcher automation, specifically targeting the new Area of Effect (AoE) functionality in the `/dmcontrol` surface. The smoke test failed, revealing that the implemented AoE preview and aiming system was non-functional in the real browser environment despite passing local syntax checks and unit tests.

## Symptom Analysis
- **Scorcher AoE Actions:** "Flamethrower" and "Ignite Ground" buttons appear in the UI, but clicking them does not initiate the expected aiming workflow.
- **No Preview/Aiming:** The map does not show any directional anchors or shape previews.
- **Map Interaction:** Clicking on the map during an AoE action does not select points or lock coordinates.
- **Targeting:** It is impossible to select tokens for multi-target resolution.
- **Successes:** Single-target melee actions (Tank Bash) and non-targeted utility protocols (Scorched Earth) continue to function correctly.

## Root Cause Hypothesis
The prior "stabilization" pass likely suffered from:
1. **State Desync:** The `/dmcontrol` state model (managed in `assets/web/dmcontrol/index.html`) did not correctly transition into `aoePlacementMode` due to unhandled exceptions or logic gaps.
2. **Coordinate Math Failure:** The coordinate conversion math (`screenToGridFloat`) may have been broken or insufficient for the `/dmcontrol` canvas context.
3. **Fragile Porting:** The attempt to port LAN-specific AoE logic into the DM console was too shallow, failing to account for differences in token management and canvas rendering between the two surfaces.

## Debug Evidence
- **Developer Smoke Note:** "Scorcher AoE actions have no preview or aiming. AoE clicking does nothing. No tokens/people can be targeted."
- **Trace Logs:** `logs/debug-trace-20260601-142012.jsonl` (Note: The log was not successfully retrieved in the research turn, but developer feedback is conclusive).

## Recovery Requirement
The `/dmcontrol` AoE system is currently "fragile/broken." A "Phase 2" implementation is strictly forbidden until a proper architecture is planned in `PLAN-20260601-dmcontrol-monster-aoe-preview-architecture.md`.

## Next Steps
1. Stop all implementation work on the Scorcher.
2. Research the `LAN` player spellcasting AoE geometry math for clean extraction.
3. Define a new, shared contract for AoE placement that works for both surfaces.

## Source Inspection Addendum: LAN AoE vs /dmcontrol Resolution (2026-06-01)

### LAN reference behavior

The LAN player surface already contains the AoE concepts needed for a robust `/dmcontrol` monster AoE design:

- `renderAoeOverlay(aoe, options = {})` renders visible AoE shapes on the map.
- `aoeContainsGridPoint(aoe, point)` performs frontend geometric hit testing for included cells/tokens.
- `updateAoeTargetPreviewPanel(previewAoe)` derives visible ally/enemy target lists from token positions.
- `pendingAoePlacement` stores active placement state.
- `computeAoePlacementAimGuide()` computes caster-to-cursor aiming information, range, line-of-sight, and facing.
- `getPendingAoePlacementPreview()` builds the current preview AoE payload.
- `maybeRunSculptSelectionForPendingAoe()` shows that LAN AoE has post-preview target filtering/special-case hooks.
- `startPlanningAoePreview()` shows how spell area metadata becomes a preview payload.

These should be treated as reference concepts only. Blind copy/paste from LAN to `/dmcontrol` remains forbidden.

### /dmcontrol gap

`/dmcontrol` currently has a single-target monster capability resolution model:

- `targetPreviewMode`
- `selectedTargetCid`
- `localResolutionTray`
- `localResolutionOutcomes`

`openLocalResolutionTray(actorCid, capabilityId, targetCid)` stores one `targetCid`.

`prepareLocalResolutionPreview()` sends a single `target_cid` to `/api/dm/monster-capabilities/{actorCid}/execute?workspace=dmcontrol`.

`applyLocalResolutionResults()` sends a `targets` array, but currently builds it with exactly one target from `localResolutionTray.targetCid`.

Conclusion: `/dmcontrol` does not need only geometry helpers. It needs a new AoE placement state and a multi-target resolution state.

### Backend opportunity

The backend already has reusable AoE target machinery:

- `_lan_compute_included_units_for_aoe()`
- `_resolve_aoe_cells()`
- `_resolve_aoe_targets()`
- `_map_spell_effect_targets()`

This suggests the future contract should not make the frontend the only source of targeting truth.

Recommended authority split:

- Frontend previews the shape and proposes included targets.
- DM can manually include/exclude targets.
- Backend validates or recomputes affected targets when possible.
- Final payload records geometry, proposed targets, and manual overrides for audit/debug.

### Planning decision

Gate 5 remains BLOCKED.

The next implementation gate must not be “make Scorcher AoE work.” The next gate should be:

Gate A: `/dmcontrol` AoE source mapping and contract refinement only.

No code edits are authorized until the plan defines:
1. AoE placement state.
2. Preview payload shape.
3. Backend validation target.
4. Manual override representation.
5. Multi-target resolution state.
6. First browser-smokable UI slice.
