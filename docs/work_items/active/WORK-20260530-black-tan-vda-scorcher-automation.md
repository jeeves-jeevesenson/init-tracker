# Work Item: WORK-20260530-black-tan-vda-scorcher-automation - Automate Black and Tan monster control and add VDA Scorcher

- **Status:** Active
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
5. **Gate 4 (Next):** Add VDA Scorcher and Scorched Earth Protocol.
6. Verify with automated tests and browser smoke.

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
(To be added at completion)

---

## Reopen Conditions
- Regression to manual badges for automated actions.
- Desync in resource tracking.
- Protocol immunity failing to apply.

## Next Allowed Action
Complete Gate 0 audit and proceed to Gate 1 (Resource initialization).
