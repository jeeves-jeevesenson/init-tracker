# Work Item: WORK-20260530-black-tan-vda-scorcher-automation - Automate Black and Tan monster control and add VDA Scorcher

- **Status:** Completed (2026-06-04)
- **Source:** docs/planning/living_docs/PLAN-20260530-black-tan-vda-scorcher-automation.md
- **Assigned To:** Gemini CLI (Orchestrator)

---

## Goal
Add a new Black and Tan / VDA lore enemy, the **Black and Tan VDA Scorcher**, and finish the existing Black and Tan package so the DM no longer sees manual-action reminders for ammunition, consumables, healing, temp HP, reactions, saves, area effects, or emergency faction protocols.

## Scope & Non-Goals
- **In Scope:**
  - Gate 0: Automation contract audit for existing Black and Tan enemies.
  - Gate 1: Resource and consumable initialization.
  - Gate 2: Generic execution primitives (healing, temp HP, area hazards, etc).
  - Gate 3: Convert existing Black and Tans to full automation.
  - Gate 4: Add VDA Scorcher and Scorched Earth Protocol.
  - Gate 5: Quality gate and browser smoke.
- **Non-Goals:**
  - Do not rebalance every firearm rule.
  - Do not replace player-side D&D 2014 behavior.
  - Do not implement ships/boarding systems.

---

## Technical Constraints

- **Allowed Files:**
  - `docs/work_items/**/*`
  - `docs/planning/**/*`
  - `Monsters/black-and-tan-vda-scorcher.yaml`
  - `monster_capabilities/vandergraff/black-and-tan-*.yaml`
  - `tests/test_black_and_tan_*.py`
  - `dnd_initative_tracker.py` (for automation primitives)
  - `monster_capability_service.py` (for summarization/resources)
  - `assets/web/dmcontrol/index.html` (for UI controls)
- **Forbidden Scope:**
  - `combat_service.py` (Protecting P0-007)
  - `player_command_service.py` (Protecting P0-007)
  - `tests/test_pact_magic_spell_slots.py` (Protecting P0-007)
  - Do not edit other Monster YAMLs unless strictly required for capability normalization.

---

## Execution Plan
1. **Gate 0 (Completed):** Audit current automation contract and document gaps.
2. **Gate 1 (Completed):** Initialize resource schema for ammo, fuel, and consumables.
   - Renamed `_monster_capability_ensure_ammo_state` to `_monster_capability_ensure_resource_state`.
   - Added support for `.45` ammo reserves (4 mags).
   - Added support for generic `uses` initialization (Smoke Canisters, Stimulants, Not Yet).
   - Proactive initialization during summary generation ensures clean UI on first view.
3. **Gate 2 (Active):** Implement backend primitives for area hazards, healing, and faction protocols.
   - **Gate 2A (Completed):** Clear hard quality-gate errors for existing save/area capabilities.
     - Normalized `save_dc` and `save_ability` schema for Suppression Gunner and Major.
     - Added `braced` and `suppressed` to `SUPPORTED_CONDITIONS` in quality gate audit.
     - Resolved `on_save` missing metadata for `automatic-sweep`.
   - **Gate 2B (Completed):** Implement backend primitives for healing and temporary HP.
     - Implemented `utility` action handler in `_dm_monster_capability_execute`.
     - Automated `Field Treatment` (healing) and `Stimulant Ampoule` (temp HP).
     - Enforced 5e "highest wins" logic for temporary HP.
     - Implemented generic `uses` resource check/decrement during execution.
     - Supported `spend: "none"` resolution preview for utility actions.
     - Verified with `tests/test_field_medic_automation.py`.
   - **Gate 2C (Completed):** Implement backend primitives for area hazards and smoke zones.
     - Marked `Suppressive Fire`, `Automatic Sweep`, and `Smoke Canister` as `executable: true`.
     - Updated `_dm_monster_capability_execute` to support ammo consumption for `save_ability` actions.
     - Updated `utility` action handler to support generic "Deployed" status for area utilities like Smoke Canister.
     - Added duration metadata to `suppressed` condition for `Suppressive Fire`.
     - Verified with `tests/test_suppression_gunner_automation.py` and updated `tests/test_black_and_tan_expansion.py`.
     - Quality gate warnings reduced from 50 to 45 (0 errors).
4. **Gate 3 (Active):** Convert remaining Black and Tans to full automation.
   - **Gate 3A (Completed):** Design backend + /dmcontrol contract for monster reactions and ally-command prompts.
     - Audited 13 remaining reaction/command capabilities.
     - Classified into four models: Pending Reaction, Explicit Commander Action, Modifier Prompt, and Passive/Reminder.
     - Designed `_pending_prompts` backend contract and UX overlay plan.
     - Recommendation: Start Gate 3B with "Save Modifier Prompts" (`not-yet`, `countermand`).
   - **Gate 3B (Completed):** Implement "Save Modifier Prompts" for Captain and Major.
     - Implemented `_pending_prompts` integration in DM console snapshot.
     - Added `_create_monster_prompt` and `_trigger_monster_save_reaction_prompts` to `InitiativeTracker`.
     - Hooked save failure triggers into `_dm_monster_capability_resolve_targets` and `_adjudicate_spell_target_request`.
     - Added `POST /api/dm/combat/resolve-monster-prompt` route to handle DM choices.
     - Implemented logic for `Not Yet` (+1d6 to save) and `Countermand` (reroll save).
     - Added prompt notification UI to `/dmcontrol` with [Use Reaction] and [Skip] controls.
     - Recovery 2026-05-30: prompt resolution now replays the blocked save flow authoritatively before downstream damage/effects finalize. `Not Yet` only offers when the failed save total is known.
     - Verified with `tests/test_reaction_prompt_automation.py`.
     - Quality gate warnings reduced from 45 to 43 (0 errors).
   - **Gate 3C (Completed):** Implement "Pending Reaction" prompts for Shield Trooper and Field Medic.
     - Implemented `_trigger_monster_hit_reaction_prompts` (Shield Trooper: Interpose Shield) and `_trigger_monster_death_reaction_prompts` (Field Medic: Keep the Officer Breathing).
     - Hooked hit triggers into `_dm_monster_capability_resolve_targets` and `_adjudicate_attack_request` (player attacks).
     - Hooked death/0HP triggers into `_dm_monster_capability_resolve_targets` and `_adjudicate_attack_request` before damage application.
     - Updated `_resume_monster_prompt_resolution` to support damage reduction and HP overrides.
     - Marked `interpose-shield` and `keep-officer-breathing` as `executable: true` and removed manual warnings from YAMLs.
     - Verified with `tests/test_black_and_tan_gate_3c.py` and updated `tests/test_black_and_tan_expansion.py`.
     - Quality gate warnings reduced from 43 to 42 (0 errors).
5. **Gate 4 (Completed):** Add VDA Scorcher and Scorched Earth Protocol.
   - Added `Monsters/black-and-tan-vda-scorcher.yaml` and `monster_capabilities/vandergraff/black-and-tan-vda-scorcher.yaml`.
   - Automated "Scorched Earth Protocol" via new backend route `/api/dm/combat/faction-protocol` and UI button in `/dmcontrol` Toolbox.
   - Verified that protocol grants dynamic fire immunity to all eligible Black and Tans (checking for `protocol-implant` capability).
   - Created `tests/test_black_and_tan_gate_4.py` and updated capabilities.
6. **Gate 5 (Active):** Verify with automated tests and browser smoke.
   - **Recovery (2026-06-01):** Fixed `AttributeError: 'LanController' object has no attribute '_json_safe'` in `_dm_console_snapshot_payload`. This was blocking browser smoke when adding monsters/players.
   - **Recovery (2026-06-01):** Fixed Gate 4 smoke failure where non-melee Scorcher actions (Flamethrower, Ignite Ground, Swap Tank) did not execute from `/dmcontrol`.
     - Fixed `_area_metadata_for_capability` backend bug where nested `area` dict was ignored.
     - Updated `/dmcontrol` to support `save_ability` and `area_hazard` targeting preview.
     - **Recovery (2026-06-01):** Replaced single-target workflow for Scorcher AoE with a proper AoE placement/preview/included-target workflow modeled on the root LAN player spell flow.
       - Implemented `aoePlacementMode` in `/dmcontrol` with directional anchor logic (cone/line).
       - Added map-based target detection for AoE previews.
       - Updated resolution modal to support multi-target adjudication and "Common Damage" application.
       - Enhanced `_dm_monster_capability_execute` to handle `target_ids` and `aoe_geometry`.
       - Added `area_hazard` (Ignite Ground) support to backend.
     - **Recovery (2026-06-01):** Stabilized `/dmcontrol` AoE implementation.
       - Fixed bug where map tokens disappeared during AoE mode due to missing `screenToGridFloat` and inefficient `draw` loop.
       - Added robust guards for AoE geometry and anchor calculation.
       - Updated `updateModeBanner` to correctly display AoE aiming instructions.
     - Added generic "Execute Action" button for actions like `Swap Tank` and non-targeted utility.
     - Enhanced `firearm_reload` backend logic to correctly handle fuel/magazine capacity.
   - **Recovery (2026-06-01) - BROWSER SMOKE FAILED:**
     - **Symptom:** Scorcher AoE actions (Flamethrower, Ignite Ground) have no preview or aiming. Clicking on the map does nothing. No tokens can be targeted.
     - **Evidence:** Developer smoke notes confirm the prior AoE implementation/stabilization claim is contradicted by reality. The `/dmcontrol` AoE state remains fragile/broken.
     - **Successes:** Tank Bash (melee) and Scorched Earth Protocol (utility) work as expected.
     - **Blocker:** /dmcontrol monster AoE preview/aiming requires a proper long-term architectural plan, not blind code porting.
     - **Status:** **BLOCKED** pending `PLAN-20260601-dmcontrol-monster-aoe-preview-architecture.md`.
   - **Gate 5C (Completed):** Implement minimal /dmcontrol monster AoE preview-state skeleton.
     - Added `aoePlacementMode` and `cursorGridPos` to `/dmcontrol`.
     - Implemented `line` preview shape (30-foot rectangle) that follows cursor.
     - Added support for entering AoE mode from capability selection and cancelling via UI or Escape key.
     - Verified with mandatory JS syntax check.
   - **Gate 5D (Completed):** Target derivation for the line shape.
     - Implemented `aoeContainsGridPoint` for `line` geometry (rectangle).
     - Added visual highlighting for included tokens using a gold ring and soft fill.
     - Updated the AoE status overlay to display the live count of included targets.
     - Excluded the acting monster from the target count/highlight by default.
     - Verified with mandatory JS syntax check.
   - **Gate 5E (Superseded):** Manual override for AoE targeting.
     - *Superseded by product redesign (2026-06-01):* Developer rejected manual-click as the primary flow in favor of save-first D&D 2024 style.
   - **Gate 5E-R (Completed):** Save-first AoE confirmation flow.
     - Added "Confirm AoE" or "Lock Aim" action to transition from aiming to resolution.
     - Removed manual-click-to-toggle logic from the aiming phase.
     - Implementation snapshots geometry and derived targets.
     - Verified with mandatory JS syntax check.
   - **Gate 5F-R (Completed):** Multi-target save resolution modal.
     - Implemented `openAoeResolutionModal` to trigger from AoE lock.
     - Modal prepopulates with targets derived from `aoeContainsGridPoint`.
     - Added per-target save/outcome adjudication UI.
     - Generic metadata support for shape, size, and save DC.
     - **Recovery (2026-06-02 - ITR-20260602-G5FR-FIX01):** Fixed AoE origin race condition.
       - Implemented `optimisticPos` tracker to use latest known position immediately after move.
       - Ensured AoE aiming starts from the new square even before the move is backend-reconciled.
     - **Recovery (2026-06-02 - ITR-20260602-G5FR-FIX02):** Fixed Ignite Ground AoE preview.
       - Implemented `square`, `radius`, and `cone` support in `renderAoePreview` and `aoeContainsGridPoint`.
       - Made `isAoeAction` more robust by checking both `cap.area` and `cap.mechanics.area`.
       - Updated `enterAoePlacementMode` to handle normalized `area` metadata.
     - Verified with `node --check` and regression tests `tests/test_black_and_tan_gate_4.py`.
   - **Gate 5G-R (Completed):** Backend execution payload.
     - Implemented `applyAoeResolutionResultsFromModal` in `/dmcontrol`.
     - Added support for `aoe_geometry` payload (shape, size, width, origin, direction).
     - Enhanced `_dm_monster_capability_resolve_targets` to validate geometry and spend resources (Action + Fuel/Ammo cost from metadata).
     - Verified per-target damage application for both save-based (Scorcher Line/Cone) and hazard-based (Scorcher Square) AoE actions.
     - Updated `ignite-ground` YAML to set `on_save: none` for correct damage application on "Miss".
     - Verified with new targeted tests `tests/test_scorcher_aoe_resolution.py`.
   - **Gate 5H-R (Completed):** Resource cleanup and final polish.
     - Prevented duplicate AoE resolution modals with `active` class guard.
     - Added `aoeResolutionInFlight` flag to prevent duplicate submissions.
     - Implemented `Escape` key listener to close resolution modal and clear state.
     - **Redesign ITR-20260602-G5HR:** Product-rejected the flat `Action 1/1`, `Bonus 1/1`, and `Reaction 1/1` card counters.
     - Removed selection-blocking and dimming for exhausted generic resources.
     - Replaced with a neutral "Turn Resources: Backend Enforced" pill in the selected actor panel.
     - Removed misleading generic resource injection from the DM console snapshot.
     - Restored persistent regression test `tests/test_scorcher_aoe_resolution.py`.
   - **Gate 5I-R (Active):** Final Scorcher smoke audit.
     - Final browser smoke validation of all Scorcher AoE actions and resource tracking.
   - Added `tests/test_scorcher_aoe_resolution.py` for persistent regression coverage.
   - Added `tests/test_lan_dm_snapshot_crash.py` and updated `tests/test_black_and_tan_gate_4.py` for regression coverage.

---

## 3A Findings & Recommendation
- **Research Doc:** `docs/planning/research/WORK-20260530-black-tan-vda-scorcher-G3A-reaction-command-contract.md`
- **Smallest Safe Slice:** Save modifier prompts (`not-yet`, `countermand`). These share a common resolution-hook pattern and provide high value by automating "failure-mitigation" choices.
- **Allowed Files for 3B:** `dnd_initative_tracker.py`, `monster_capability_service.py`, `assets/web/dmcontrol/index.html`.
- **Blocked Files:** `combat_service.py`, `player_command_service.py`.

---

## Validation & Evidence

### Required Validation
- `scripts/agent_gate_validate.sh A0` (Workflow check)
- `python3 scripts/audit/monster_capability_inventory.py`
- `python3 scripts/audit/monster_capability_quality_gate.py`
- New unit tests for each automation primitive.
- End-to-end combat resolution tests for Black and Tans.

### Smoke Check Requirement
Full DM control sweep in `/dmcontrol` for all Black and Tan types, confirming no "Manual" badges remain for combat actions.

### Completion Evidence
- Gate 5E: Manual AoE overrides verified in `/dmcontrol`. Click-to-toggle logic works; visuals (Gold/Green/Red) are distinct; count is accurate.

---

## Reopen Conditions
- Regression to manual badges for automated actions.
- Desync in resource tracking.
- Protocol immunity failing to apply.

## Next Allowed Action
Gate 5E-R: Save-first AoE confirmation flow. Implement confirmation action and remove manual overrides from aiming. Do not commit or push.
