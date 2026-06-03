# PLAN-20260601-dmcontrol-monster-aoe-preview-architecture

## ID and Title
PLAN-20260601-dmcontrol-monster-aoe-preview-architecture: `/dmcontrol` Monster AoE Preview and Aiming Architecture

## Status
Ready for Orchestrator

## Last Updated
2026-06-01

## Owner Roles
- Developer: product decision maker and browser smoke tester.
- Planning Tool: recovery architecture, scope control, living-document governance.
- Orchestrator/Gemini: future implementation executor only after this plan is approved.
- Codex: not assigned unless the developer explicitly requests Codex.

## Goal
Design a robust `/dmcontrol` monster Area of Effect preview, aiming, target derivation, manual override, and multi-target resolution architecture so the Black and Tan VDA Scorcher can use Flamethrower and Ignite Ground without fragile UI behavior.

The desired UX should be comparable to the LAN player spellcasting AoE flow: visible shape preview, clear aiming, included target detection, and resolution after confirmation.

## Scope
In scope:
- `/dmcontrol` monster AoE UX contract.
- Monster capability AoE metadata contract.
- Map/token coordinate contract.
- Preview rendering contract for cone, line, and radius/sphere shapes.
- Aiming/anchor/direction state transitions.
- Included target derivation.
- Manual add/remove override.
- Multi-target resolution modal.
- Per-target save/outcome adjudication.
- Backend execute payload shape.
- Validation and browser smoke gates.

## Non-Goals
- Do not blindly copy/paste LAN JavaScript into `/dmcontrol`.
- Do not patch the existing fragile `/dmcontrol` AoE implementation incrementally.
- Do not redesign all LAN spellcasting.
- Do not change player-side D&D 2014/2024 behavior.
- Do not commit/push current Scorcher work as complete.
- Do not implement ships, boarding, surfaces, or unrelated experimental systems.
- Do not edit production/deployment configuration.
- Do not begin Phase 2 implementation until this plan is approved.

## Source Evidence
- `docs/work_items/current_work.md` now marks Gate 5 as browser-smoke failed and `/dmcontrol` Scorcher AoE blocked pending planned AoE preview architecture.
- `docs/work_items/active/WORK-20260530-black-tan-vda-scorcher-automation.md` records the 2026-06-01 browser smoke failure.
- Developer smoke note: Scorcher AoE actions have no preview or aiming, clicking the map does nothing, and no tokens can be targeted.
- Smoke successes: Tank Bash works; Scorched Earth Protocol utility behavior works.
- Smoke failure: Flamethrower and Ignite Ground do not provide usable `/dmcontrol` AoE interaction.
- Research note: `docs/planning/research/WORK-20260530-scorcher-aoe-smoke-failure-20260601.md`.
- Current dirty tree includes Gate 4 backend/YAML salvage plus documentation changes; it must not be committed as complete while Gate 5 is blocked.

## Research Agenda
R-001: Confirm current failure boundary.
- Separate working Gate 4 backend/YAML Scorcher salvage from failed Gate 5 `/dmcontrol` AoE UI.

R-002: Inspect LAN AoE behavior.
- Identify the LAN player spellcasting UX and geometry concepts that should inform `/dmcontrol`.
- Extract concepts, not code blocks.

R-003: Inspect `/dmcontrol` state model.
- Identify how monster capability selection, map drawing, token interaction, and resolution modal state currently work.

R-004: Define shared AoE contract.
- Define action metadata, geometry payload, target derivation, manual override, and execution payload.

R-005: Define implementation gates.
- Split work into small gates with browser smoke after each gate.

R-006: Define validation and refusal rules.
- Define test requirements, browser smoke requirements, completion criteria, and reopen conditions.

## Research Log
### 2026-06-01 — Source inspection: LAN AoE vs /dmcontrol monster resolution
Findings:
- LAN has mature AoE preview concepts: `renderAoeOverlay`, `aoeContainsGridPoint`, `updateAoeTargetPreviewPanel`, `pendingAoePlacement`, `computeAoePlacementAimGuide`, and `getPendingAoePlacementPreview`.
- `/dmcontrol` currently has a single-target model: `targetPreviewMode`, `selectedTargetCid`, `localResolutionTray`, and `localResolutionOutcomes`.
- `/dmcontrol` preview preparation sends one `target_cid`.
- `/dmcontrol` apply sends a `targets` array, but currently builds it with exactly one target from `localResolutionTray.targetCid`.
- Backend AoE machinery already exists through `AoeSpec`, `_resolve_aoe_cells`, `_resolve_aoe_targets`, and `_lan_compute_included_units_for_aoe`.

Decision:
- Frontend should preview and propose included targets.
- Backend should validate or recompute affected targets where possible.
- **Save-first redesign (2026-06-01):** The DM chooses/aims AoE geometry, the system derives affected creatures, and the DM confirms. Manual overrides are an advanced post-confirmation correction, not the primary flow.
- First implementation gate must be a preview-state skeleton only, not full Scorcher execution.

### 2026-06-01 — Gate 5E Manual Override Superseded
Findings:
- Developer rejected manual click-to-include/exclude as the primary flow.
- "Save-first" D&D 2024 style is the required UX: visible shape -> derived targets -> confirm -> multi-target resolution modal.
- Manual overrides may remain as an advanced correction but are deferred.

Decision:
- Redesign Gate 5E as 5E-R (Save-first confirmation flow).
- Mark previous Gate 5E implementation as salvage/superseded.

### 2026-06-01 — Browser smoke failure accepted
Findings:
- Gate 4 backend/YAML salvage remains valuable.
- Tank Bash works.
- Scorched Earth Protocol utility behavior works.
- Scorcher AoE actions are not usable in `/dmcontrol`.
- No preview appears.
- No aiming appears.
- Clicking the map does nothing.
- No tokens can be selected or resolved.
- Prior claims that `/dmcontrol` AoE was implemented/stabilized are contradicted by browser smoke.

Decision:
- Mark Gate 5 blocked.
- Do not continue patching the fragile AoE implementation.
- Plan a proper AoE preview/aiming architecture before implementation.

## Decisions
- `/dmcontrol` monster AoE must have visible preview/aiming; hidden/no-op AoE is not acceptable.
- LAN player spellcasting AoE is the UX reference, but blind LAN code porting is forbidden.
- Geometry preview should be designed through a stable contract.
- **D&D 2024 Save-First Flow:** Target derivation is primarily geometric. Confirmation of the shape triggers the resolution modal for all affected targets.
- Backend execution must receive explicit target IDs and enough AoE geometry metadata for audit/debug.
- Gate 4 backend/YAML salvage should remain separate from Gate 5 UI architecture recovery.

## Open Questions
1. Which LAN functions currently own spell AoE geometry, preview rendering, and included-target derivation?
2. Which `/dmcontrol` functions currently own map draw, token hit-testing, selected target state, and resolution modal state?
3. Should `/dmcontrol` derive included targets entirely on the frontend, or should the backend validate/recompute affected targets?
4. What exact `aoe_geometry` payload should be sent for cone, line, and radius/sphere?
5. How should manual add/remove overrides be represented in the execute payload if added as an advanced feature?
6. Should Ignite Ground create a persistent map hazard marker immediately, or only after resolution?
7. What is the minimum first shape to implement: line, cone, or radius?
8. Can Scorcher backend/YAML salvage be committed separately while Gate 5 remains blocked, or should all Scorcher work wait?

## Risks
- Reintroducing map rendering corruption if preview drawing is coupled to the normal draw loop incorrectly.
- Reintroducing missing-function runtime errors like the previous `aoeContainsGridPoint` failure.
- Creating a UI that appears to aim but sends incorrect target IDs.
- Desync between frontend target derivation and backend execution.
- Breaking existing single-target monster actions.
- Accidentally changing LAN player spellcasting behavior.
- Committing partial Scorcher work as complete while AoE remains unusable.

## Proposed Architecture Contract

### Capability Metadata
Each area-capable monster action should expose normalized metadata:
- action/capability ID
- action type
- shape: `cone`, `line`, `radius`, or equivalent
- range/length
- width when applicable
- save ability and DC when applicable
- damage/effect metadata
- resource cost such as fuel/ammo
- whether the action creates a persistent hazard

### `/dmcontrol` State Transitions
Required states:
1. Idle
2. Capability selected
3. AoE aiming
4. AoE locked/confirmed (Triggers Resolution Modal)
5. Multi-target resolving (Per-target saves)
6. Manual target override (Advanced/Optional correction)
7. Executing
8. Complete/error recovery

Each transition must have a visible UI state and a cancel path.

### Preview Rendering
Preview must:
- render without hiding or corrupting tokens
- use a clearly defined grid/screen coordinate conversion
- update on mouse movement while aiming
- show included targets distinctly
- be removed cleanly on cancel or completion

### Target Derivation
Target derivation must:
- use current map token positions
- support cone, line, and radius/sphere
- exclude invalid/dead/hidden targets as appropriate
- provide the base target list for the multi-target resolution modal
- preserve the final selected target list for resolution

### Resolution Modal
The modal must:
- support multiple targets
- show each target by name
- allow per-target save/outcome adjudication (D&D 2024 style)
- support common damage entry when appropriate
- prevent execution with zero targets unless the action is explicitly terrain-only
- submit explicit target IDs and geometry payload

### Backend Execute Payload
Draft shape:

{
  "capability_id": "flamethrower",
  "actor_cid": "monster-instance-id",
  "target_ids": ["cid-1", "cid-2"],
  "aoe_geometry": {
    "shape": "line",
    "origin": {"x": 0, "y": 0},
    "anchor": {"x": 0, "y": 0},
    "direction": {"x": 1, "y": 0},
    "range": 30,
    "width": 5,
    "manual_overrides": {
      "included": [],
      "excluded": []
    }
  },
  "resolution": {
    "targets": [
      {"target_id": "cid-1", "save_result": "fail"},
      {"target_id": "cid-2", "save_result": "success"}
    ]
  }
}

This is a planning draft, not an implementation contract, until source inspection confirms the existing backend route schema.

## Implementation Gates
Implementation is blocked until this plan is approved.

Gate A: Source inspection only.
- Inspect LAN AoE functions.
- Inspect `/dmcontrol` map/token/resolution functions.
- Produce a mapping note.
- No code edits.

Gate B: Contract design.
- Define exact metadata and payload contract.
- Identify backend/frontend files that will change.
- No implementation until approved.

Gate C: Minimal preview-state skeleton.
- Implement AoE placement state only.
- Implement one preview shape only.
- No target derivation, no resolution modal changes, and no backend execution yet.
- Browser smoke: preview appears, moves, cancels, and does not corrupt map/tokens.

Gate D: Target derivation.
- Add included-target detection for the first shape.
- Browser smoke: included targets match visible preview.

Gate 5E-R: Save-first AoE confirmation flow.
- Add "Confirm AoE" or "Lock Aim" action.
- Disable/Remove manual-click-to-toggle logic from the aiming phase.
- Ensure aiming state transitions cleanly to resolution preparation.

Gate 5F-R: Multi-target save resolution modal.
- Add per-target save/outcome adjudication.
- Modal must be prepopulated with derived targets.
- Browser smoke: modal represents all selected targets correctly.

Gate 5G-R: Backend execution payload.
- Submit target IDs and geometry payload.
- Validate resource spend and damage/effect application.
- Unit tests required.

Gate 5H-R: Remaining shapes.
- Repeat preview/derive/resolve smoke for each shape.

Gate 5I-R: Full Scorcher smoke.
- Flamethrower works.
- Ignite Ground works.
- Tank Bash still works.
- Swap Tank/reload still works.
- Scorched Earth Protocol still works.
- No console errors.
- No token disappearance or map corruption.

## Validation Requirements
Before implementation:
- `git status --short`
- `scripts/chatgpt_context_refresher.sh`
- `scripts/agent_context_bundle.sh`
- Source inspection notes for LAN and `/dmcontrol`.

During implementation:
- Existing Gate 4 Scorcher tests must still pass through repo-supported test command.
- Monster capability quality gate must remain 0 errors.
- Browser asset syntax checks must pass for edited browser surfaces.
- No unrelated files may be edited.

After implementation:
- Add focused regression tests for backend multi-target monster AoE execution.
- Add regression coverage for area metadata parsing.
- Confirm no regressions to Tank Bash, Swap Tank/reload, and Scorched Earth Protocol.

## Browser Smoke Requirements
Required browser smoke after each UI gate:
- `/dmcontrol` loads without console errors.
- Existing tokens render correctly.
- Existing token movement still works.
- Single-target monster actions still work.
- AoE mode can be entered.
- AoE mode can be canceled.
- Preview appears and updates.
- Included targets are visually clear.
- Manual overrides work.
- Resolution modal shows all targets.
- Execution applies effects correctly.
- No token disappearance.
- No map corruption.
- No repeated-click cascade.

## Completion Criteria
This plan can be marked Ready for Orchestrator only when:
- LAN AoE source inspection is complete.
- `/dmcontrol` state model inspection is complete.
- The exact implementation gates are accepted by the developer.
- The first implementation slice is small enough to smoke independently.
- Validation and smoke requirements are explicit.

The Scorcher work item can be completed only when:
- Gate 4 backend/YAML salvage is validated.
- Gate 5 `/dmcontrol` AoE preview/aiming works in browser smoke.
- Flamethrower and Ignite Ground are usable.
- Existing Scorcher non-AoE actions still work.
- No console errors, token disappearance, or map corruption occur.
- The developer approves final browser smoke.
- Changes are committed/pushed only after approval.

## Reopen Conditions
Reopen this plan if:
- Any AoE action again lacks preview/aiming.
- AoE clicking does nothing.
- Targets cannot be selected or resolved.
- Tokens disappear or map rendering corrupts.
- Backend execution receives incorrect target IDs.
- LAN spellcasting behavior regresses.
- The developer changes the desired AoE UX.

## Orchestrator Handoff
I created/updated a planning document at: `docs/planning/living_docs/PLAN-20260601-dmcontrol-monster-aoe-preview-architecture.md`.

Please read it, check `docs/work_items/current_work.md`, and decide whether to request more research, create a bounded source-inspection task, promote an implementation gate later, use Codex, or ask for developer smoke.

Current recommendation:
- Gate 5E-R is approved as the next bounded implementation slice.
- Implement `/dmcontrol` AoE confirmation flow only.
- Disable/Remove manual-click-to-toggle logic from the aiming phase.
- Ensure aiming state transitions cleanly to resolution preparation.
- No resolution modal changes, and no backend execution.

## Refusal / End-State Rule
If this plan is marked Completed, Superseded, Archived, or reaches its completion criteria, Orchestrator should refuse to continue from it unless the developer explicitly reopens it.

Only Gate 5E-R is authorized. Orchestrator must refuse multi-target resolution, backend execution, Scorcher damage/effects, or commit/push until the developer approves the next gate.
