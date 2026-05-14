# DM Control Surface Redesign — Living Agent Plan

Version: 2026-05-06
Status: Living planning and execution document
Recommended repo path: `docs/dm_control_surface_living_agent_plan.md`
Source plan: `docs/dm-control-surface-master-plan.md`
Research source: `docs/dmcontrol_research_living_notes.md`

## How to use this document

This is the working document agents should use when planning, implementing, and reporting DM control-surface work.

The master design direction is stable:

- **The active monster/NPC control surface is a dedicated `/dmcontrol` page, not the `/dm` cockpit.**
- **`/dmcontrol` must be based on LAN client interaction patterns, not `/dm` UI.**
- **The tactical map is not the primary combat-control surface for `/dm`.** Do not build workflows that require map clicks to run monster turns, select targets, or execute actions on the `/dm` cockpit. Panel-first controls are required there.
- **`/dmcontrol` uses a map-first active play surface modeled after the LAN client.** It uses the same backend-authority model and combat state snapshots.
- Build a new actor-centered DM combat control surface on `/dmcontrol`.
- Focused Actor Panel work on `/dm` is transitional/reusable prototype work, not the final target layout.
- Target selection on `/dmcontrol` should match LAN targeting: action-first, then map-click or panel-based picker.
- Tactical map on `/dm` is reference / inspection / visual feedback only.
- Tactical map on `/dmcontrol` is the active play surface: movement, targeting, AoE placement.
- DM Toolbox on `/dm` is setup / overrides / admin / debug.
- Legacy Monster Turn Controls and Monster Pilot must be removed/demoted from the main active cockpit area on `/dm`.
- Do not polish the current dropdown-heavy Monster Turn Controls / Monster Pilot as the target UI.
- Use LAN player flow as the local interaction reference for `/dmcontrol`.
- Preserve backend authority and avoid DM-only parallel state.

Agents should update this document after meaningful passes.

## Update rules for agents

When an agent completes a pass, update the relevant sections below:

1. Work log
2. Current status snapshot
3. Milestone status
4. Decisions made
5. New risks / blockers
6. Validation state
7. Best next task

Do not delete historical notes unless they are replaced by a clearer durable summary.

Do not mark a milestone complete unless tests and, where relevant, browser/runtime evidence support it.

Do not claim browser readiness after editing `assets/web/dm/index.html` or `assets/web/lan/index.html` unless the inline JavaScript syntax check passed.

## Critical Architecture Correction: /dm vs /dmcontrol

| Feature / Surface | `/dm` (Cockpit / Reference) | `/dmcontrol` (Active Play Surface) |
|---|---|---|
| **Role** | Command Center, Prep, Admin, Debug | Active monster/NPC/enemy play page |
| **Interaction Model** | Panel-first, administrative, overview | Map-first, LAN-like, high-speed resolution |
| **Main Surface** | Multi-panel dashboard | Tactical map + bottom control bar |
| **Tactical Map Role** | Reference, inspection, visual context | Active movement, targeting, AoE placement |
| **Initiative** | Full overview, all combatants | Current turn/round status, actor focus |
| **Actor Focus** | Full stat-sheet reference, inspection | Turn-critical state, active action controls |
| **Monster Library** | Search, browse, encounter building | N/A |
| **Toolbox** | Global overrides, session, setup | Soft DM override if explicit |
| **Battle Log** | Full historical/technical log | Compact recent-result feed |
| **Movement** | Visualization / setup (if any) | Active drag/drop movement, range overlays |

## Dedicated /dmcontrol Page Architecture

### Purpose
The `/dmcontrol` page is the dedicated active combat cockpit for the DM to run monster, NPC, and enemy turns. It is optimized for high-speed interaction and D&D action resolution, modeled after the LAN player client (`assets/web/lan/index.html`).

### Relationship to /dm
- `/dm` remains the "Command Center" for session management, encounter building, map editing, and global overrides.
- `/dmcontrol` is the "Action Surface" focused on the current initiative actor.
- Navigation should allow quick switching between the two.

### Relationship to LAN client
- `/dmcontrol` should feel familiar to users of the LAN client.
- It uses the same backend-authority model and combat state snapshots.
- Interaction style (action cards, target selection, resolution modals) should be shared or mirrored.
- Page structure: Map-first surface + bottom control bar/sheet.

### Final /dmcontrol interaction model

1. Initiative advances to monster/NPC/enemy.
2. `/dm` shows that actor’s sheet/reference information.
3. `/dmcontrol` automatically focuses the current actor.
4. Movement range appears automatically on the `/dmcontrol` map.
5. DM can move the token by drag/drop at any point during the turn using remaining movement.
6. DM chooses action/spell/Multiattack from LAN-style controls in the bottom bar.
7. `/dmcontrol` map enters action-specific target/template mode (range/reach/AoE previews).
8. DM selects target(s) from the map (or panel-based picker fallback).
9. Selected/affected targets are previewed on the map.
10. Resolution modal opens (reusing LAN resolution logic).
11. DM manually/app-assisted resolves results (hit/save/damage/effects).
12. "Apply Results" mutates backend combat state.
13. Multiattack returns to guided child-sequence tray until ended.
14. DM ends turn.

**PC Turn Behavior:** When initiative is on a PC, `/dmcontrol` idles/disables normal controls, similar to a LAN client when it is not that actor’s turn.

## Final /dmcontrol Design Principles

- **Build from `assets/web/lan/index.html`**, not from `assets/web/dm/index.html`.
- **Map-first and active:** Keep the tactical map as the primary interaction surface for play.
- **Bottom/control bar:** Use a LAN-like bottom bar for main monster controls.
- **Minimum state:** Only duplicate turn-critical state on `/dmcontrol` (name, HP, conditions, movement, round/turn).
- **Movement is always available:** Range appears automatically; drag/drop is the normal input; movement can be split around actions.
- **Action-first targeting:** Choose action -> enter map target mode -> click target.
- **Avoid redundant click chains:**
    - Avoid: click action -> click target -> click attack again -> reselect target -> click resolve.
    - Preferred: click action -> map enters target mode -> click target -> resolution modal opens.
- **Guided Multiattack:** Multiattack is a child-step flow (select child -> map target mode -> click target -> resolution modal).
- **Automation assists, does not trap:** Double-submit guards and manual override are mandatory.
- **Graceful degradation:** If no structured monster overlay exists, fall back to simple manual/assisted controls without "dropdown hell".

## Reusable work from /dm prototype
The following logic/features implemented on `/dm` should be ported/reused:
- Monster Action card rendering and mechanics summaries.
- Selected/expanded action state management.
- Target Tray state model (for panel-based selection/preview).
- Range/AoE advisory wording and validation hints.
- Resolution Tray backend wiring and manual adjudication logic.
- Sequence Tray model and child completion tracking for Multiattack.
- Error/in-flight hardening and double-submit prevention.

### What should not be ported
- UI placement within the `/dm` cockpit (must move to dedicated `/dmcontrol` page).
- Dependency on `/dm` right-side panel layout.
- Tactical map as the active play surface on `/dm`.
- Old Monster Turn Controls / Monster Pilot dependencies.

## Non-negotiable guardrails

### UI direction

- **Panel-first controls are mandatory for `/dm`.** The tactical map on `/dm` is for reference and inspection.
- **`/dmcontrol` is the active combat surface.** Modeled after the LAN client.
- **Tactical map on `/dmcontrol` is the active play surface.**
- **Avoid redundant click chains.**
- Target selection on `/dmcontrol` uses map-first interaction with panel-based fallback.
- The current `/dm` right-side dropdown control stack is not the target UI.
- Monster Turn Controls and Monster Pilot are legacy/current fallback surfaces.
- Do not build new active-combat workflows from dropdown stacks.
- Design for complex monsters first: dragons, spellcasters, legendary creatures, AoEs, multiattack, riders, and spellcasting.

### Runtime and state direction

- Preserve backend authority.
- Do not introduce a DM-only parallel source of truth.
- Use existing monster capability backend paths where practical.
- Do not create a third parallel combat-resolution backend unless proven necessary.
- No state mutation without explicit Apply/Confirm.
- Double-submit guards are mandatory for Apply/End/Override.
- Treat stale UI as frontend state/DOM bugs unless endpoint evidence proves backend divergence.

### Browser asset safety

Any pass editing either file below must run an inline JavaScript parse/syntax check:

- `assets/web/dm/index.html`
- `assets/web/lan/index.html`

Required report item:

- exact syntax-check command
- result
- whether node was available
- whether manual browser smoke was run

Browser parse errors such as `Unexpected token '}'` or `Identifier '<name>' has already been declared` are blockers.

## Monster Action Backend Contract (Pass 2B)

### A. Multiattack Sequence Model

Multiattack is handled as an `assisted_sequence` resolution flow.

#### 1. `sequence_kind`
- **`fixed_children` (Default):** The DM must complete the specific counts for all listed child actions.
    - *Example:* Troll (Bite x1, Claw x2).
- **`choose_n`:** The DM has a total budget of $N$ selections from a provided list of valid child actions.
    - *Example:* Constable (Choose 2 from .45 Pistol or Baton).
- **`variant` (Reserved):** Monsters that make $N$ attacks and can replace one with a special action (e.g., Grapple/Shove or a specific trait).

#### 2. Completion Rules
- **Increment:** Completion for a child step increments exactly **once** per successful "Apply Results".
- **Outcome Neutrality:** Hit, Miss, and "No Effect" all count as a completed attack/action once applied.
- **Cancellation:** Cancelling a resolution modal or targeting mode does **not** increment completion.
- **Failures:** A failed backend apply (e.g., network error) does not increment completion.
- **Authority:** Sequence state is **turn-scoped** and **actor-scoped**.
- **Persistence:** Initially frontend-assistive; backend state broadcast should clear it on actor/turn change. Reconnect/Refresh clears active sequence progress (resetting the turn's attacks).

#### 3. Interaction Contract
- Each child uses the standard LAN-like `target -> modal -> apply` flow.
- Each child performs its own range/reach validation.
- Movement remains allowed between child attacks.
- Sequence Tray stays visible or minimized until the total budget/fixed-steps are met or the DM clicks "End Sequence".

---

### B. Controlled Burst & Firearm Modifiers

Controlled Burst is modeled as a **Stateful Modifier Action**.

#### 1. Mechanics
- **Action Type:** `modifier`
- **State:** `next_attack` modifier.
- **Ammo Cost:** 3 (consumed hit or miss).
- **Damage Bonus:** +1 base weapon damage die on hit (no extra modifier).
- **Limit:** Once per turn.
- **Jam Risk:** Natural 1 on the modified attack roll triggers the `Jammed` state on the weapon.
- **Resolution:**
    1. DM clicks "Controlled Burst" action card.
    2. Backend `/execute` verifies ammo (>= 3) and `once_per_turn` limit.
    3. Backend sets `actor_cid:controlled_burst = True` in turn-local resource state.
    4. Next `melee_attack` or `ranged_attack` resolution checks this flag.
    5. If set, the resolution packet includes the extra die and increases ammo spend to 3.
    6. Flag clears after resolution.

#### 2. Unresolved / Questions
- **Jamming UI:** Does "Jammed" need a new backend condition or just a weapon-state flag? (Proposal: use a weapon-specific resource/flag).
- **Multiple Weapons:** If a monster has two guns, does Controlled Burst apply to the *next* attack with *either* or only the one used? (Design: applies to the next attack with a `burst` weapon).

---

### C. Black and Tan Manual Tray Cleanup

| Item | Classification | Notes |
|---|---|---|
| **Armalite Rifle** | Executable | Ranged Attack |
| **.45 Pistol** | Executable | Ranged Attack |
| **Baton / Knife** | Executable | Melee Attack |
| **Multiattack (Rifleman)** | `fixed_children` | Armalite x2 |
| **Multiattack (Constable)** | `choose_n` | Choose 2 (Pistol/Baton) |
| **Controlled Burst** | `modifier` | Stateful resource/damage bonus |
| **Vandergraff Drill** | Passive Reminder | Demote to Traits/Collapsed |
| **Fire Discipline** | Passive Reminder | Demote to Traits/Collapsed |
| **Baton and Boot** | Passive Reminder | Demote to Traits/Collapsed |
| **Rough Arrest** | Rider / Prompt | Future: Prompt on Baton hit |

---

### D. Testing Strategy

1. **Schema/Service Tests:**
    - Verify `MonsterCapabilityService` correctly parses `sequence_kind` and `choose_n`.
    - Verify modifier actions are correctly summarized for UI.
2. **Backend Logic Tests:**
    - `test_monster_sequence_budget`: Prove `choose_n` enforcement.
    - `test_controlled_burst_modifier`: Verify flag sets on execute and consumes on resolution.
3. **Regression Tests:**
    - Ensure fixed multiattack (Troll/Rifleman) still works.
    - Ensure range validation remains per-child attack.

---

### E. Implementation Pass Breakdown

#### Pass 2C: Multiattack Schema & Service Support
- Add `sequence_kind` and `choose_n` to schema.
- Update `MonsterCapabilityService` to expose these in UI summaries.
- Add unit tests for parsing.

#### Pass 2D: Backend Sequence Authority
- Implement `choose_n` budget tracking in `dnd_initative_tracker.py`.
- Update `/execute` to respect multiattack kind.

#### Pass 2E: /dmcontrol Sequence UI
- Update sequence tray to support "Choose N" display.
- Improved "End Sequence" and "Next Step" flow.

#### Pass 2F: Black and Tan Conversion
- Update Rifleman/Constable overlays to use the new contracts.
- Demote passive reminders to a collapsed Traits section.

#### Pass 2G: Controlled Burst & Jamming
- Implement stateful modifier backend logic.
- Implement ammo cost (3) and extra damage die.
- Implement Natural 1 jamming.

---

## Current status snapshot

Update this section after each pass.

| Area | Current status | Notes |
|---|---|---|
| `/dm` cockpit | Admin/reference/setup | Cleaned up; legacy controls demoted. Link to `/dmcontrol` added. |
| `/dmcontrol` | Map & Movement completed | Dedicated LAN-style monster/NPC control page with map, tokens, movement range, and backend-validated active-actor drag/drop movement. |
| `/` LAN client | Useful local model | LAN has targeting, movement range, attack resolution, spell target selection, and remaining movement concepts |
| Monster Turn Controls | Demoted | **Moved to Legacy tab in DM Toolbox.** |
| Monster Pilot | Demoted | **Moved to Legacy tab in DM Toolbox.** |
| Focused actor panel | Transitional Prototype | Current implementation on `/dm` is for reusable learning, not final target location. |
| DM Toolbox | In progress | Tabbed modal with Session, Encounter, Overrides, Map Tools, Debug, and Legacy tabs. Resized for desktop. |
| Encounter Builder | In progress | Monster Library search and Add Monster workflow migrated to Encounter tab |
| Monster Library | Completed | Deduplication implemented in frontend. |
| Duplicate monster names | Completed | Backend auto-numbering fixed for single-spawns via CombatantNameService |
| Enemy/NPC initiative | Completed | Auto-roll individually when added via monster spawn path |
| Tactical map inspection | Completed | Token click focuses actor in panel without changing initiative turn |
| Movement model | Completed | LAN movement works; monster/NPC-specific movement on `/dmcontrol` implemented and backend-validated. |

## Repo Realities (Foundations & Gaps)

### Strong foundations
- LAN map-first page (`assets/web/lan/index.html`).
- LAN bottom control sheet and attack resolution modals.
- Movement range/cost overlays and drag/drop movement.
- Spell/AoE targeting primitives and preview panels.
- Backend movement validation and `resolve-targets` endpoint.
- `MonsterCapabilityService` summaries and structured action overlays.
- Composite Multiattack model and `assisted_sequence` backend packets.

### Gaps
- Normalized monster coverage is shallow (only 18 overlays).
- Many raw monster YAML actions are text, not structured/executable.
- Monster spellcasting and Bonus Actions/Reactions are not broadly normalized.
- Black and Tan firearm content remains beta/untested.
- Black and Tan Rifleman may be missing composite Multiattack overlay.
- Monster Library contains duplicate entries. (Fixed in Phase 0)
- Repeated single-spawn numbering has regressed. (Fixed in Phase 0)
- DM Toolbox modal is cramped on desktop. (Fixed in Phase 0)
- Legacy Monster Turn Controls / Monster Pilot remain visible in `/dm` main cockpit. (Fixed in Phase 0)

## Milestone board

Update the status column after each pass.

| ID | Milestone | Status | Next concrete pass |
|---|---|---|---|
| M0 | Phase 0 — Clean `/dm` regressions | Completed | M1 - /dmcontrol shell |
| M1 | Phase 1 — `/dmcontrol` shell | Completed | Route/page shell + status |
| M2 | Phase 2 — LAN-like map & movement | Completed | Map, movement range, and drag/drop |
| M3 | Phase 3 — Basic attack flow | In progress | Phase 3A (Action panel scaffold) |
| M4 | Phase 4 — Multiattack guided flow | Not started | Sequence tray + resolution reuse |
| M5 | Phase 5 — AoE/save action flow | Not started | AoE template placement |
| M6 | Phase 6 — Monster spellcasting | Not started | Spell list integration |
| M7 | Phase 7 — Content expansion | Not started | Normalize more monsters |
| M10 | DM Toolbox shell | Completed | Resize modal |
| M11 | Demote legacy controls from `/dm` | Not started | Remove/hide Monster Turn Controls / Monster Pilot |

## Immediate implementation queue (Phase 0)

These are safe cleanup tasks before construction begins.

### Q1 — Fix Monster Library duplicate entries
- Dedupe `encounterOptions.monsters` by `slug` before rendering.
- Likely file: `assets/web/dm/index.html` (around `renderMonsterLibrary`).

### Q2 — Fix repeated single-spawn numbering regression
- Ensure `CombatantNameService` is used in `/api/dm/encounter/monsters/add`.
- Likely file: `dnd_initative_tracker.py`.

### Q3 — Resize/improve DM Toolbox modal
- Increase default desktop width/height (e.g., `1400px` x `950px`).
- Support resize.
- Likely file: `assets/web/dm/index.html`.

### Q4 — Demote legacy controls from `/dm`
- Remove or move Monster Turn Controls and Monster Pilot to a "Legacy" or "Debug" tab in the Toolbox.
- Clear space in the main `/dm` cockpit.

## Work log

Agents should append concise entries here.

### 2026-05-09 — Phase 3E3: live combat correctness bugfix for Black and Tan /dmcontrol
Agent/model: Claude Opus 4.7
Scope:
- Live testing exposed several combat-correctness issues in `/dmcontrol` for Black and Tan enemies. This pass fixes them with the smallest safe changes; no new features and no architecture moves.
- Attack miss correctness: `_dm_monster_capability_resolve_targets` now branches on `action_type`. For `melee_attack` / `ranged_attack`, only `outcome=fail` (hit) produces damage entries; `success` (miss), `no_effect`, and unset outcomes produce zero damage. Save-style half damage (`rolled_success`) is preserved for save-based actions only. Resolution packets now include `action_type` so the UI can label outcome previews correctly.
- Friendly-fire guard: `isTargetCandidate` now consults a new `isSameSideAsActor` helper that uses `unit.ally` / `unit.role` to exclude same-side units from candidate highlights. The Apply path also calls `isFriendlyFireSelection` and surfaces a `confirm()` warning before applying damage/effects to a same-side target. This prevents accidental Black-and-Tan-on-Black-and-Tan damage. DM override is documented as a future toggle (an explicit confirm acts as the override today).
- Constable Multiattack semantics: `monster_capabilities/vandergraff/black-and-tan-constable.yaml` Multiattack changed from `action_type: composite` (with a misleading Pistol×2 + Baton×2 expansion that read as four attacks) to `action_type: utility` with a clear manual instruction "Make two attacks total, using .45 Pistol or Baton in any combination." Pistol and Baton remain individually executable. Constable Multiattack no longer exposes `resolved_composite`.
- Weapon range no longer leaks into area metadata: `MonsterCapabilityService._area_metadata_for_capability` and `InitiativeTracker._monster_capability_area_metadata` no longer copy `mechanics.range` / `mechanics.long_range` into the `area` dict. AoE shape/size still populates area. Range/reach is now exposed as flat fields (`cap.range_ft`, `cap.long_range_ft`, `cap.reach_ft`) so target-advisory text in `/dmcontrol` continues to work.
- Packet preview hardening: added `formatPacketValue` / `formatPacketEntries` helpers in `assets/web/dmcontrol/index.html`. `renderLocalResolutionPacket` now formats arrays of damage/effect/condition objects into readable summaries (rolled total + type, condition/name/label) instead of `[object Object]`. The fragile `.join(', ')` on object arrays is gone.
- Sequence cleanup after a child apply: `applyLocalResolutionResults` now clears `targetPreviewMode` and `selectedTargetCid` after every successful child apply. Sequence completion is checked: when every step has hit its required count, `localSequencePacket` and the completed-step counter are cleared, the status bar reads "Multiattack sequence complete.", and `selectedCapabilityId` is cleared so the panel returns to a clean state. While the sequence still has remaining steps, `selectedCapabilityId` is popped back to the parent multiattack so the sequence tray re-renders cleanly and the DM must explicitly Select the next step.
Files inspected:
- GEMINI.md, AGENTS.md, docs/dm_control_surface_living_agent_plan.md
- assets/web/dmcontrol/index.html
- dnd_initative_tracker.py (resolve-targets, area metadata, resolution packet)
- monster_capability_service.py (area metadata, summary)
- monster_capabilities/vandergraff/black-and-tan-rifleman.yaml
- monster_capabilities/vandergraff/black-and-tan-constable.yaml
- tests/test_black_and_tan_capabilities.py, tests/test_dm_control_apply_results.py, tests/test_dm_control_route.py
Files changed:
- assets/web/dmcontrol/index.html
- dnd_initative_tracker.py
- monster_capability_service.py
- monster_capabilities/vandergraff/black-and-tan-constable.yaml
- tests/test_black_and_tan_capabilities.py
- tests/test_dm_control_apply_results.py
- docs/dm_control_surface_living_agent_plan.md
Validation:
- `./.venv/bin/python3 -m unittest -v tests.test_black_and_tan_capabilities` → 11 passed.
- `./.venv/bin/python3 -m unittest -v tests.test_dm_control_apply_results` → 11 passed.
- `./.venv/bin/python3 -m unittest -v tests.test_dm_control_route` → 25 passed.
- `./.venv/bin/python3 -m unittest -v tests.test_dm_console_asset_syntax` → 3 passed (Node `--check` over inline `<script>` blocks of the three browser asset HTML files, including `assets/web/dmcontrol/index.html`).
- `git diff --check` → clean.
Outcome:
- Attack misses (`success` outcome on a `melee_attack` / `ranged_attack`) now apply zero damage; hits still apply full damage; save-style half damage still works for save-based actions.
- Black and Tan target candidates default to opposing-side combatants. Same-side selection requires an explicit confirm.
- Constable Multiattack is now an unambiguous Manual Assist that cannot be misread as four attacks.
- Firearm `target_mode` is `single`, never `area_manual`. AoE actions still route to `area_manual` correctly.
- Packet preview never renders `[object Object]`.
- Rifleman Multiattack stops prompting after exactly two Armalite Rifle child applies.
Remaining manual fallbacks (unchanged this pass):
- Ammo / reload tracking is still manual; Fire Discipline note remains a reminder.
- Controlled Burst stays manual-assist (extra die / 3-ammo spend handled by DM).
- Rough Arrest / grapple is manual.
- Vandergraff Drill +1 attack bonus is a reminder; no automatic modifier is applied.
Remaining live risks:
- Friendly-fire guard relies on `unit.ally` / `unit.role` being populated for both actor and target. If the snapshot drops these fields, the guard falls back to "no same-side known" and behaves as before.
- Confirm dialog is a `window.confirm`; if a future browser harness suppresses dialogs we may need an inline confirm UI.
- No live-server smoke this pass; verified via static UI assertions and focused backend unit tests.
Next recommended pass:
- Live game smoke testing only. Do not start a new feature pass unless a specific reproduced bug appears.

### 2026-05-09 — Phase 3E2: /dmcontrol live UX and interaction stabilization
Agent/model: Claude Opus 4.7
Scope:
- Stabilized `/dmcontrol` for live Black and Tan combat without changing backend rules.
- Added a draggable horizontal split between map and control bar (`#splitHandle`) with localStorage persistence (`dmcontrol.controlBarHeightPx`), safe min/max clamping, double-click reset, and re-clamp on viewport resize. Canvas is re-fit and redrawn after split changes.
- Replaced exact-cell drag start with token hit-testing (`getTokenAtScreen`). Click within the active token's visible radius now starts a drag; multi-token overlaps prefer the active initiative actor. Drag remains blocked for PCs and during target/resolution mode.
- Added a prominent mode banner (`#modeBanner`) above the map covering Move / Target / Resolve / Sequence states, with an inline "Cancel Targeting" / "Cancel" / "End Sequence" button. Banner stays in sync with local state via `updateModeBanner()` called from `renderActionPanel` and `renderState`.
- Surfaced a transient status when movement is attempted during resolution ("Cancel resolution to move."). Targeting clicks also use token hit-testing so clicks near a token edge select correctly.
- Cleaned up the action panel: HP/AC/Movement/Conditions are stat pills; action cards have larger hit areas and a clear "Attack" vs "Manual Assist" / "Reminder" badge with a coloured left border. Traits and special items collapse under a single `<details>` so primary actions stay prominent.
- Manual-only capabilities now render a "Manual Assist — DM resolves this action by hand." note in the selected-summary, never enter target mode, and show no Apply button. Executable attacks remain previewable and reach Apply via the existing flow.
- Improved canvas target visibility: candidate tokens get a soft fill + solid amber ring; the selected target gets a stronger ring plus an inner white accent. Active actor is excluded from candidates.
Files changed:
- assets/web/dmcontrol/index.html
- tests/test_dm_control_route.py
- docs/dm_control_surface_living_agent_plan.md
Outcome:
- Map and control bar are user-resizable and persist across reloads.
- Token drag is reliable across click positions; target mode no longer accidentally moves the actor.
- Mode is unambiguous from a glance via banner and inline cancel button.
- Manual assists vs executable attacks are visually unmistakable.
- Apply Results and Multiattack sequence flows verified preserved by the route + apply-results tests.
Validation:
- `python3 -m unittest tests.test_dm_control_route tests.test_dm_control_apply_results tests.test_black_and_tan_capabilities tests.test_dm_console_asset_syntax` — all passed.
- Mandatory JS syntax check passed (Node `--check` over inline `<script>` blocks of `assets/web/dmcontrol/index.html`).
Remaining rough edges:
- No live-server smoke yet against an actual browser this pass; UX validated only via static UI assertions.
- Split drag uses pointer capture on the handle; very fast cross-window pointer-up events may need a stray `mouseleave` recovery if real-world testing surfaces stuck dragging.
- Action card layout is tuned for desktop widths; narrow viewports will still stack but were not regressed-tested live.
Next recommended pass:
- Live game smoke testing only. Do not start a new feature pass unless a specific reproduced bug appears.

### 2026-05-08 — Phase 3C2: /dmcontrol browser readiness hardening
Agent/model: Gemini CLI
Scope:
- Hardened `/dmcontrol` state management for live browser use.
- Implemented `fullResetLocalState()` helper and `lastActiveCid` tracking to clear state on active actor change.
- Added defensive checks for stale target (`selectedTargetCid`) and capability (`selectedCapabilityId`) in polling loops.
- Refined `closeLocalResolutionTray` to clear `selectedTargetCid`, allowing a clean return to target selection phase.
- Improved UI copy to clarify `spend: "none"`, local-only outcomes, and manual HP workflow in `/dm`.
- Added defensive tests for hardening logic in `tests/test_dm_control_route.py`.
- Mandatory JS syntax check passed.
Files changed:
- assets/web/dmcontrol/index.html
- tests/test_dm_control_route.py
- docs/dm_control_surface_living_agent_plan.md
Outcome:
- `/dmcontrol` is stable and ready for live game DMing with robust state cleanup.
- Manual HP application in `/dm` remains the safe, recommended workflow.
- All Python route tests and JS syntax checks passed.
Next recommended pass:
- Phase 3D: Apply Results planning or encounter-specific enemy readiness.

### 2026-05-08 — Phase 3C1: /dmcontrol local-only outcome controls
Agent/model: Gemini CLI
Scope:
- Added local outcome state `localResolutionOutcomes` to `/dmcontrol`.
- Added helper functions for outcome management: `getLocalResolutionOutcome`, `setLocalResolutionOutcome`, `getOutcomeLabel`.
- Added `getOutcomePreviewDamage` to calculate local damage previews based on outcome (Fail/Hit, Success/Miss, No Effect, Manual).
- Updated Resolution Preview UI to include a local outcome dropdown and a prominent local preview damage text.
- Implemented state cleanup: outcomes are cleared when closing the tray, canceling preview, or changing action/actor.
- Ensured hard constraints: maintained `spend: "none"`, no `/resolve-targets` or "Apply Results" logic added.
Files changed:
- assets/web/dmcontrol/index.html
- tests/test_dm_control_route.py
- docs/dm_control_surface_living_agent_plan.md
Outcome:
- DM can now choose an intended outcome for a target and see a local-only damage/effect preview.
- Outcome selection is strictly local and does not mutate backend state.
- All Python route tests and JS syntax checks passed.
Next recommended pass:
- Phase 3C2: Browser readiness hardening or Phase 3D Apply-flow planning.

### 2026-05-07 — Phase 3B2b: /dmcontrol resolution packet rendering hardening
Agent/model: Gemini CLI
Scope:
- Hardened `/dmcontrol` resolution packet rendering and normalization.
- Added `normalizeLocalExecutionResult(data)` helper for safe execute-preview response handling.
- Added `renderLocalResolutionPacket(packet, resolution)` for robust, escaped HTML building of packet details.
- Displayed fields (when present): DC, save ability, attack bonus, damage (with formula/rolls), effects, and conditions.
- Added compact `<details>` "Packet debug details" section for troubleshooting.
- Improved deferred resolution handling for "automatic" and "assisted_sequence" types.
- Hardened state cleanup: resolution state is explicitly cleared when changing actors or actions.
- Updated UI copy: "Backend packet preview" and "No combat state will be changed from this preview."
- Maintained non-mutating scope: preserved `spend: "none"`, no `/resolve-targets` or "Apply Results" added.
Files changed:
- assets/web/dmcontrol/index.html
- tests/test_dm_control_route.py
- docs/dm_control_surface_living_agent_plan.md
Outcome:
- DM receives safe, rich, and well-structured previews of resolution packets.
- Resolution state is robust against actor/action switching.
- All Python route tests and JS syntax checks passed.
Next recommended pass:
- Phase 3B3: Outcome controls and apply flow planning.

### 2026-05-07 — Phase 3B2a: backend execute packet preview
Agent/model: Gemini CLI
Scope:
- Wired `/dmcontrol` local resolution tray to the backend `/execute` endpoint.
- Implemented `prepareLocalResolutionPreview` function using `spend: "none"` to fetch resolution packets without mutation.
- Added local state: `localResolutionPacket`, `localResolutionError`, `localResolutionInFlight`.
- Updated Resolution Preview UI to include a "Prepare Resolution Preview" button.
- UI now displays resolution packet details (DC, save ability, damage summary) when available.
- Added safety warning: "Preview only. Results are not applied."
- Implemented handling for "automatic" and "assisted_sequence" resolution types (deferred/unimplemented in this pass).
- Hardened state cleanup: tray, packet, and error state are cleared on Escape, cancel, or actor/action changes.
- Maintained non-mutating scope: no `/resolve-targets` or "Apply Results" added.
Files changed:
- assets/web/dmcontrol/index.html
- tests/test_dm_control_route.py
- docs/dm_control_surface_living_agent_plan.md
Outcome:
- DM can now preview the backend-calculated resolution packet for a selected action and target.
- Verification of distance and basic mechanics via real backend execution logic.
- All Python route tests and JS syntax checks passed.
Next recommended pass:
- Phase 3B2b: Outcome controls scaffold or full apply planning.

### 2026-05-07 — Phase 3B1: local resolution tray scaffold
Agent/model: Gemini CLI
Scope:
- Implemented local-only resolution tray scaffold on `/dmcontrol`.
- Added `localResolutionTray` state to capture actor, capability, and target context.
- Target selection now automatically opens the local resolution tray.
- Added helpers: `openLocalResolutionTray`, `closeLocalResolutionTray`, and `getLocalResolutionContext`.
- Updated `Escape` key behavior: first Escape closes the resolution tray; second Escape cancels target preview.
- Enhanced `renderActionPanel` to display a compact "Resolution Preview" section when the tray is open, showing:
    - Actor, Action, and Target names.
    - Distance and advisory status.
    - Safety text: "Resolution is not implemented in this pass. No combat state will be changed."
    - Safe local controls: "Back to target selection" and "Cancel preview".
- Updated `draw()` to strengthen the selected target ring when the resolution tray is open.
- Ensured state cleanup: tray is cleared when changing actions, actors, or cancelling preview.
- Maintained non-mutating scope: no execution, resolution, or backend mutation added.
Files changed:
- assets/web/dmcontrol/index.html
- tests/test_dm_control_route.py
- docs/dm_control_surface_living_agent_plan.md
Outcome:
- `/dmcontrol` now has a functional local-only resolution preview flow.
- Clear separation between targeting and resolution phases in the UI.
- All Python route tests and JS syntax checks passed.
Next recommended pass:
- Phase 3B2: Backend prepare/execute integration planning or resolution packet preview.

### 2026-05-07 — Phase 3A2c: selected-target advisory details
Agent/model: Gemini CLI
Scope:
- Implemented local, non-authoritative advisory details for selected targets on `/dmcontrol`.
- Added `getSelectedTargetAdvisory` helper to compute Chebyshev distance and compare against structured range/reach.
- Updated `renderActionPanel` to display target distance and advisory status (Likely in range, Likely out of range, Unknown).
- Updated `draw()` to color-code the selected target indicator:
    - Green (`#4caf82`) for likely-in-range.
    - Red (`#ff5b5b`) for likely-out-of-range.
    - Gold (`#d6ba7e`) for unknown/advisory.
- Enhanced target preview status overlay with distance and advisory labels.
- Maintained non-mutating scope: no backend resolution or execution.
Files changed:
- assets/web/dmcontrol/index.html
- tests/test_dm_control_route.py
- docs/dm_control_surface_living_agent_plan.md
Outcome:
- DM receives immediate spatial feedback on target validity.
- All Python route tests and JS syntax checks passed.
Next recommended pass:
- Phase 3B1: Resolution modal scaffold without backend mutation.

### 2026-05-07 — Phase 3A2b: local clicked-target selection
Agent/model: Gemini CLI
Scope:
- Implemented local clicked-target selection while `targetPreviewMode` is active on `/dmcontrol`.
- Added `selectedTargetCid` local state.
- Implemented helpers: `findUnitAtGridCell`, `findCombatantByCid`, `isTargetCandidate`, `selectPreviewTarget`.
- Updated `pointerdown` to handle target selection (clicking a unit) and block movement drag during target preview.
- Enhanced `renderActionPanel` to show the selected target name and local selection status.
- Updated `draw()` to visualize all target candidates with dashed rings and the selected target with a solid ring and fill.
- Enhanced target preview status overlay to show the selected target name.
- Non-mutating pass: no backend mutations, execution, or resolution added.
Files changed:
- assets/web/dmcontrol/index.html
- tests/test_dm_control_route.py
- docs/dm_control_surface_living_agent_plan.md
Outcome:
- DM can now click tokens on the map to select a target locally during action preview.
- Clear visual feedback on map and in action panel for the selected target.
- Movement drag is safely blocked while in target preview mode.
- All Python route tests and JS syntax checks passed.
Next recommended pass:
- Phase 3A2c: target selection summary and action-specific advisory details (range/AoE validation hints).

### 2026-05-07 — Phase 3A2a: target-preview mode scaffold
Agent/model: Gemini CLI
Scope:
- Implemented local-only `targetPreviewMode` scaffold on `/dmcontrol`.
- Added helpers `findCapabilityById` and `isPreviewableTargetAction` for action-context detection.
- Simple melee/ranged actions now enter target-preview mode when selected.
- Implemented `Escape` key handler to cancel target-preview mode.
- Blocked movement drag while target-preview mode is active.
- Added visual status overlay and dashed target indicators on the map during preview.
- Non-mutating pass: no execution, resolution, or target-click selection added.
Files changed:
- assets/web/dmcontrol/index.html
- tests/test_dm_control_route.py
- docs/dm_control_surface_living_agent_plan.md
Outcome:
- `/dmcontrol` can now enter a visual target-preview mode for simple attacks.
- Movement safety preserved.
- JS syntax check passed.
- All Python route tests passed.
Next recommended pass:
- Phase 3A2b — Valid target highlighting and local clicked-target selection.

### 2026-05-07 — Phase 3A1: action panel scaffold/read-only capability fetch
Agent/model: Gemini CLI
Scope:
- Implemented `/dmcontrol` action panel scaffold using existing `GET /api/dm/monster-capabilities/{cid}`.
- Added grouped action cards (Actions, Bonus Actions, Reactions, Legendary Actions, Traits, Special).
- Implemented read-only capability summaries with mechanics, action types, and uses.
- Added local-only selection state with compact selected-action summary.
- Implemented appropriate idle handling for PC turns and missing monster overlays.
- Ensured Phase 2C drag/drop movement remains functional.
- **Correction:** Fixed rendering to correctly unwrap `payload.summary` from the backend response and access action lists within `summary.groups`. Added HTML escaping and hardened CID comparisons.
Files changed:
- assets/web/dmcontrol/index.html
- tests/test_dm_control_route.py
- docs/dm_control_surface_living_agent_plan.md
Outcome:
- Monster/NPC actions are now visible on `/dmcontrol` for the active actor.
- Non-mutating pass: no execution, targeting, or resolution logic added.
- Phase 2C movement preserved and verified.
- All Python tests and JS syntax checks passed.
Next recommended pass:
- Phase 3A2 — Simple melee/ranged target preview only for /dmcontrol.

### 2026-05-07 — Phase 1: /dmcontrol route and shell
Agent/model: Gemini CLI
Scope:
- Created dedicated `/dmcontrol` route and page shell (`assets/web/dmcontrol/index.html`).
- Added "Open DM Control" link to `/dm` cockpit.
- Added "DM Cockpit" link to `/dmcontrol` page.
- Implemented basic state fetching and rendering (actor name, HP, meta) on `/dmcontrol`.
- Added middleware to disable caching for `/dmcontrol`.
Files changed:
- dnd_initative_tracker.py
- assets/web/dm/index.html
- assets/web/dmcontrol/index.html (New)
- tests/test_dm_control_route.py (New)
- docs/dm_control_surface_living_agent_plan.md
Outcome:
- Dedicated monster/NPC play surface shell is live.
- Seamless navigation between cockpit and action surface.
- JS syntax check passed for all touched assets.
- Route verification tests passed.
Next recommended pass:
- Phase 2 — Port LAN tactical map surface and movement range/drag-drop to `/dmcontrol`.

### 2026-05-07 — Phase 2A: Read-only LAN-like map surface
Agent/model: Gemini CLI
Scope:
- Implemented read-only tactical map surface on `/dmcontrol` using HTML5 Canvas.
- Grid rendering with auto-fit, zoom, and pan logic ported from LAN client.
- Token rendering for combatants with positions, using role-based coloring.
- Active actor highlighting based on `active_cid`.
- Resize handling for map responsiveness.
Files changed:
- assets/web/dmcontrol/index.html
- tests/test_dm_control_route.py
- docs/dm_control_surface_living_agent_plan.md
Outcome:
- `/dmcontrol` now has a functional, read-only tactical map synchronized with backend state.
- JS syntax check passed.
- Route and element verification tests passed.
Next recommended pass:
- Phase 2B — Movement range visualization or drag-and-drop movement.

### 2026-05-07 — Phase 2B: Movement Range Visualization
Agent/model: Gemini CLI
Scope:
- Implemented `movementCostMap` (simplified Dijkstra) for reachable cell calculation on `/dmcontrol`.
- Integrated movement visualization into `/dmcontrol` map surface.
- Movement range automatically appears for the active monster/NPC actor.
- Added "Movement Remaining" and speed stats to the active actor panel.
- Verified visualization-only scope (no drag/drop or mutation yet).
- Cleaned up unused/buggy heap code ported from LAN but not used in the simplified pass.
Files changed:
- assets/web/dmcontrol/index.html
- tests/test_dm_control_route.py
- docs/dm_control_surface_living_agent_plan.md
Outcome:
- `/dmcontrol` now visualizes reachable movement cells for the active combatant.
- Graceful handling of PC turns and missing map/position states.
- All Python tests and JS syntax checks passed.
Next recommended pass:
- Phase 2C — Drag-and-drop movement mutation for `/dmcontrol`.

### 2026-05-07 — Phase 2C: Drag-and-drop movement
Agent/model: Gemini CLI
Scope:
- Implemented drag-and-drop movement for the active monster/NPC actor on `/dmcontrol`.
- Uses rules-aware `POST /api/dm/map/combatants/{cid}/move` backend endpoint.
- Movement validation (obstacles, costs, speed) enforced by backend via `_lan_try_move`.
- Drag preview shows destination and validity (blue for valid, red for invalid).
- Movement range overlay remains visible and updates after successful move.
- Added UI hints: "Drag token on map to move • Movement is backend-validated".
- Restricted movement to active non-PC actors only.
Files changed:
- assets/web/dmcontrol/index.html
- tests/test_dm_control_route.py
- docs/dm_control_surface_living_agent_plan.md
Outcome:
- DM can now move the active monster directly on the `/dmcontrol` map.
- Invalid moves are rejected by the backend and tokens snap back.
- All Python tests and JS syntax checks passed.
Next recommended pass:
- Phase 3A1 — /dmcontrol action panel scaffold and read-only capability fetch.

### 2026-05-06 — Phase 0 Cleanup: Dedupe, Numbering, Sizing, and Demotion
Agent/model: Gemini CLI
Scope:
- Deduped Monster Library results in frontend.
- Fixed backend monster numbering regression (single-spawns now numbered uniquely).
- Resized DM Toolbox modal for better desktop usability (1400px x 950px, resizable).
- Demoted legacy "Monster Turn Controls" and "Monster Pilot" to a new "Legacy" tab in the Toolbox.
Files changed:
- assets/web/dm/index.html
- dnd_initative_tracker.py
- docs/dm_control_surface_living_agent_plan.md
Outcome:
- Cockpit decluttered.
- Backend numbering consistency restored.
- Toolbox usability improved.
- All tests passed (326).
- JS syntax check passed.
Next recommended pass:
- Phase 1 — /dmcontrol shell and state.

### 2026-05-06 — Architecture Realignment & Research Integration
Agent/model: Gemini CLI
Scope:
- Formalized `/dmcontrol` as the dedicated active monster play surface (LAN-like).
- Updated design principles based on VTT and D&D 2024 research.
- Redefined `/dm` as cockpit/reference only.
- Mapped current repo foundations and gaps.
- Defined Phase 0 cleanup and Phase 1-7 implementation roadmap.
Files changed:
- docs/dm_control_surface_living_agent_plan.md
Outcome:
- Roadmap pivot confirmed.
- Implementation queue redirected to Phase 0 cleanup.
- Reusable prototype work identified.

### 2026-05-06 — Architecture Correction: Dedicated Control Page
Agent/model: Gemini CLI
Scope:
- Formalized `/dmcontrol` as the dedicated active monster/NPC control page.
- Redefined `/dm` as the admin/cockpit/reference surface.
- Marked current `/dm` Focused Actor Panel work as a transitional prototype.
- Defined reusable components for porting to `/dmcontrol`.
Files changed:
- docs/dm_control_surface_living_agent_plan.md
Outcome:
- Clearer separation of concerns.
- Roadmap updated to pivot toward `/dmcontrol`.
- Map-click dependency marked as provisional/wrong-direction for primary workflow.

### 2026-05-06 — Planning consolidation

Scope:

- Consolidated DM control surface design direction.
- Integrated live user feedback, repo inspection, and online research.
- Established this living agent plan.

Outcome:

- New control surface direction confirmed.
- LAN client identified as local interaction reference.
- Current DM dropdown controls marked legacy/fallback.
- First implementation candidates identified.

Next recommended pass:
- Q3 — Rename Normalized Capabilities to Monster Actions.

### 2026-05-06 — Rename Normalized Capabilities to Monster Actions (Q3)

Agent/model: Gemini CLI (Autonomous Mode)
Scope:
- Rename user-facing labels and descriptions in the DM UI.
- Improve no-match messaging for monsters without structured action cards.
Files changed:
- assets/web/dm/index.html
- dnd_initative_tracker.py
- docs/dm_control_surface_living_agent_plan.md
Outcome:
- DM UI now uses "Monster Actions" instead of "Normalized Capabilities".
- No-match message is more helpful and less jargon-heavy.
- Mandatory JS syntax check passed.
Next recommended pass:
- Q5 — DM Toolbox shell.

### 2026-05-06 — Auto-number duplicate monster spawns (Q1)

Agent/model: Gemini CLI (Autonomous Mode)
Scope:
- Implement backend auto-numbering for duplicate monster names.
- Ensure unique suffixes (e.g., "Goblin 1", "Goblin 2") even for single spawns.
Files changed:
- combatant_name_service.py (New)
- dnd_initative_tracker.py
- tests/test_combatant_name_service.py (New)
Outcome:
- Monsters receive unique numeric suffixes upon spawning.

### 2026-05-06 — Auto-roll enemy/NPC initiative (Q2)

Agent/model: Gemini CLI (Autonomous Mode)
Scope:
- Implement auto-rolling of initiative for monsters spawned via the DM encounter route.
- Each monster in a multi-count spawn gets an independent roll.
Files changed:
- combat_service.py
- helper_script.py
- tests/test_monster_init_auto_roll.py (New)
Outcome:
- Monsters automatically roll initiative when added if the initiative is 0.
- Multi-count spawns have independent initiative values.

### 2026-05-06 — DM Toolbox shell (Q5)

Agent/model: Gemini CLI (Autonomous Mode)
Scope:
- Create accessible modal shell with tabs in /dm.
- Add DM Toolbox button to topbar.
- Implement tab switching and basic open/close logic.
Files changed:
- assets/web/dm/index.html
- tests/test_dm_toolbox_ui.py (New)
- docs/dm_control_surface_living_agent_plan.md
Outcome:
- DM Toolbox button added to the DM cockpit topbar.
- Tabbed modal (Session, Encounter, Overrides, Map Tools, Debug) implemented with ARIA roles.
- Close on background click and Escape key supported.
- Mandatory JS syntax check passed.

### 2026-05-06 — Move Session tools to Toolbox (M3)

Agent/model: Gemini CLI (Autonomous Mode)
Scope:
- Migrate New Blank Session, Save/Load Session, and Quick Save/Load into DM Toolbox -> Session tab.
- Remove redundant session persistence block from main cockpit.
- Update UI tests to verify placement and accessibility.
Files changed:
- assets/web/dm/index.html
- tests/test_dm_toolbox_ui.py
- docs/dm_control_surface_living_agent_plan.md
Outcome:
- Session controls moved to Toolbox.
- All JS handlers (Save, Load, Quick, New) preserved and functional.
- Old main-cockpit session card removed.
- Mandatory JS syntax check passed.

### 2026-05-06 — Move Add Player Profiles to Toolbox (M3 extension)

Agent/model: Gemini CLI (Autonomous Mode)
Scope:
- Migrate "Add Player Profiles" controls into DM Toolbox -> Session tab.
- Group with Session Persistence under "Roster & Players" section.
- Remove redundant roster setup block from main cockpit.
- Update UI tests to verify placement and removal.
Files changed:
- assets/web/dm/index.html
- tests/test_dm_toolbox_ui.py
- docs/dm_control_surface_living_agent_plan.md
Outcome:
- Player profile controls moved to Toolbox.
- JS handlers for selecting/adding players preserved and functional.
- Old main-cockpit "Add Player Profiles" card removed.
- Mandatory JS syntax check passed.
Next recommended pass:
- M4 — Encounter Builder / Monster Library (or Overrides tab migration for HP/temp HP).

### 2026-05-06 — Move HP / Temp HP controls into Toolbox Overrides tab (M2/M12 partial)

Agent/model: Gemini CLI (Autonomous Mode)
Scope:
- Migrate HP Adjustment and Temp HP controls into DM Toolbox -> Overrides tab.
- Remove redundant Health block from main cockpit.
- Preserve all element IDs and JS behavior.
Files changed:
- assets/web/dm/index.html
- tests/test_dm_toolbox_ui.py
- docs/dm_control_surface_living_agent_plan.md
Outcome:
- HP and Temp HP controls moved to Toolbox.
- Cockpit clutter reduced.
- All JS handlers (HP adjustment, Temp HP set) preserved and functional.
- Mandatory JS syntax check passed.
Next recommended pass:
- M4 — Encounter Builder / Monster Library (or Overrides tab migration for Set Initiative).

### 2026-05-06 — Move Remove Combatant into Toolbox Encounter tab (M3/M4 partial)

Agent/model: Gemini CLI (Autonomous Mode)
Scope:
- Migrate Remove Combatant controls into DM Toolbox -> Encounter tab.
- Remove redundant Remove Combatant card from main cockpit.
- Preserve all element IDs and JS behavior.
Files changed:
- assets/web/dm/index.html
- tests/test_dm_toolbox_ui.py
- docs/dm_control_surface_living_agent_plan.md
Outcome:
- Remove Combatant controls moved to Toolbox.
- Cockpit clutter reduced.
- All JS handlers (remove combatant) preserved and functional.
- Mandatory JS syntax check passed.
Next recommended pass:
- M4/M5 — Encounter Builder / Monster Library (or Overrides tab migration for Set Initiative).

### 2026-05-06 — Move Set Initiative into Toolbox Overrides tab (M2/M5 partial)

Agent/model: Gemini CLI (Autonomous Mode)
Scope:
- Migrate Set Initiative controls into DM Toolbox -> Overrides tab.
- Remove redundant Combat Setup block from main cockpit.
- Preserve all element IDs and JS behavior.
Files changed:
- assets/web/dm/index.html
- tests/test_dm_toolbox_ui.py
- docs/dm_control_surface_living_agent_plan.md
Outcome:
- Set Initiative controls moved to Toolbox.
- Cockpit clutter reduced; Combat Setup group removed from cockpit.
- All JS handlers (set/roll initiative) preserved and functional.
- Mandatory JS syntax check passed.
Next recommended pass:
- M4/M5 — Encounter Builder / Monster Library (Search/Browse monster library).

### 2026-05-06 — Monster Library / Encounter Builder shell (M4 partial)

Agent/model: Gemini CLI (Autonomous Mode)
Scope:
- Create Monster Library shell in DM Toolbox -> Encounter tab.
- Implement search input and results container.
- Add logic to filter and render monster cards from existing data.
- Wire card click to populate existing "Add Monster Specs" dropdown.
Files changed:
- assets/web/dm/index.html
- tests/test_dm_toolbox_ui.py
- docs/dm_control_surface_living_agent_plan.md
Outcome:
- Searchable Monster Library added to Toolbox.
- Real monster data (name, CR, type, HP, AC) displayed in result cards.
- Search/filter works client-side.
- Clicking a monster card pre-selects it in the existing add-monster workflow.
- Mandatory JS syntax check passed.
Next recommended pass:
- M4 — Complete Encounter Builder (Wire Monster Library results to spawn monsters directly and migrate Add Monster Specs into Toolbox).

### 2026-05-06 — Self-contained Add Monster Specs spawning (M4 extension)

Agent/model: Gemini CLI (Autonomous Mode)
Scope:
- Migrate Add Monster Specs controls into DM Toolbox -> Encounter tab.
- Position below Monster Library shell for self-contained workflow.
- Remove redundant Add Monster Specs block from main cockpit.
- Preserve all element IDs and JS behavior.
Files changed:
- assets/web/dm/index.html
- tests/test_dm_toolbox_ui.py
- docs/dm_control_surface_living_agent_plan.md
Outcome:
- Add Monster Specs controls moved to Toolbox.
- Monster Library cards pre-fill the moved form.
- Cockpit clutter reduced.
- Mandatory JS syntax check passed.
Next recommended pass:
- M4 — Complete Encounter Builder (Migrate Add Combatant into Toolbox).

### 2026-05-06 — Move Add Combatant into Toolbox Encounter tab (M4 partial)

Agent/model: Gemini CLI (Autonomous Mode)
Scope:
- Migrate Add Combatant controls into DM Toolbox -> Encounter tab as "Advanced / Custom Combatant".
- Remove redundant roster setup section from main cockpit.
- Update UI tests to verify placement and removal.
Files changed:
- assets/web/dm/index.html
- tests/test_dm_toolbox_ui.py
- docs/dm_control_surface_living_agent_plan.md
Outcome:
- Add Combatant controls moved to Toolbox Encounter tab.
- Roster setup group removed from cockpit.
- All JS handlers (add custom combatant) preserved and functional.
- Mandatory JS syntax check passed.
Next recommended pass:
- M6 — Focused actor panel prototype.

### 2026-05-06 — Focused Actor Panel prototype (M6)

Agent/model: Gemini CLI (Autonomous Mode)
Scope:
- Create first Focused Actor Panel prototype on /dm.
- Display current initiative actor stats (HP, AC, Speed, Init, Conditions).
- Handle PC view-only state.
- Add placeholders for future features (Movement, Actions, Resources, Traits).
Files changed:
- assets/web/dm/index.html
- tests/test_dm_focused_actor_panel.py (New)
- docs/dm_control_surface_living_agent_plan.md
Outcome:
- Focused Actor Panel added to initiative cockpit.
- Panel updates automatically when turn changes.
- PC actors labeled as "View Only".
- Mandatory JS syntax check passed.
Next recommended pass:
- M7 — Monster Actions / action cards integration (first slice).

### 2026-05-06 — Focused Actor Panel - Monster Actions Detail/Selection (M7)

Agent/model: Gemini CLI (Autonomous Mode)
Scope:
- Add display-only card expansion/details and selected-action state to Monster Actions in the Focused Actor Panel.
- Implement click handlers for selection and toggle expansion.
- Render detailed mechanics (Description, Reach, Range, Target Mode) in expanded view.
- Ensure selection state is cleared on focused actor change.
Files changed:
- assets/web/dm/index.html
- tests/test_dm_focused_actor_panel_actions.py
- docs/dm_control_surface_living_agent_plan.md
Outcome:
- DM can click action cards to select and expand them for detailed inspection.
- Visual highlighting indicates the selected action.
- Expanded cards show full descriptions and structured metadata from existing capability summaries.
- Mandatory JS syntax check passed.
- All relevant tests (340) passed.
Next recommended pass:
- M7 — Monster Actions: Action target mode prototype (visualizing range/AoE).

### 2026-05-06 — Focused Actor Panel - Monster Actions Display Integration (M7)

Agent/model: Gemini CLI (Autonomous Mode)
Scope:
- Implement display-only "Monster Actions" integration in the Focused Actor Panel.
- Add CSS for compact action cards.
- Introduce `monsterCapabilitiesByCid` cache to optimize capability fetching.
- Update `fetchMonsterCapabilities` to handle multi-panel updates.
- Implement `renderCompactMonsterActions` for display-only mechanics summaries.
- Handle PC view-only and monster no-match messaging.
Files changed:
- assets/web/dm/index.html
- tests/test_dm_focused_actor_panel_actions.py (New)
- docs/dm_control_surface_living_agent_plan.md
Outcome:
- Focused Actor Panel now displays compact, display-only action cards for the focused monster.
- PC actors show appropriate "View Only" message.
- "No structured action cards" message shown for monsters without overlays.
- Mandatory JS syntax check passed.
- All relevant tests (339) passed, including new focused tests.
Next recommended pass:
- M7 — Monster Actions: Action execution hardening / error handling.

### 2026-05-06 — Monster Actions: Resolution Tray (M7 extension)

Agent/model: Gemini CLI (Autonomous Mode)
Scope:
- Implement the first executable slice from Focused Actor Panel Target Tray to a backend-backed Resolution Tray.
- Reuse existing standalone Monster Actions backend endpoints: `/execute` and `/resolve-targets`.
- Added "Execute / Prepare Resolution" button to the Target Tray.
- Added `Resolution Tray` UI that appears after execution intent is sent.
- Manual outcome adjudication (fail/hit, success/miss, etc.) per target.
- "Apply Results" finalizing damage/effects via the existing backend flow.
- "Cancel" controls for both execution and resolution phases.
- State management ensuring resolution state is cleared on actor/action changes.
Files changed:
- assets/web/dm/index.html
- tests/test_dm_focused_actor_panel_actions.py
- docs/dm_control_surface_living_agent_plan.md
Outcome:
- DM can now select targets on the map and trigger a real backend execution/resolution flow directly from the Focused Actor Panel.
- Full parity with the manual adjudication logic of the standalone panel, but integrated into the new cockpit.
- **Correction Note:** This implementation currently depends too much on map-click target selection. Future passes must refactor this to panel-first target selection.
- Mandatory JS syntax check passed.
- All relevant tests (348) passed.

### 2026-05-06 — Monster Actions: Multiattack Sequencing Planning (M7 extension)

Agent/model: Gemini CLI (Autonomous Mode)
Scope:
- Repo-grounded planning for Multiattack / Composite action sequencing in the Focused Actor Panel.
- Inspected `MonsterCapabilityService` and YAML overlays for composite representation.
- Reviewed backend support for `assisted_sequence` resolution type.
- Analyzed standalone panel behavior for child attacks.
- Defined a "Sequence Tray" UI model for step-by-step assisted resolution.
Outcome:
- Detailed implementation plan added to the living doc.
- Ready for first implementation slice: Sequence Tray UI and child-action execution wiring.
- **Correction Note:** Plan relies on map-click targeting for child steps; needs refactoring to panel-first.

### 2026-05-06 — Monster Actions: Sequence Tray Hardening (M7 extension)

Agent/model: Gemini CLI (Autonomous Mode)
Scope:
- Harden the Focused Actor Sequence Tray.
- Improved `selectFocusedActorSequenceStep` with invalid child checks and in-flight guards.
- Added graceful handling for missing or malformed sequence packets in the UI.
- Ensured successful child apply only increments completion exactly once.
- Hardened state cleanup: switching focus (CID change) now reliably clears sequence state.
- Verified in-flight double-submit prevention for both sequence preparation and child execution.
Files changed:
- assets/web/dm/index.html
- tests/test_dm_focused_actor_panel_sequence.py
Outcome:
- Sequence Tray is significantly more resilient to invalid data and rapid user clicks.
- Clearer visual feedback when child attacks are missing or resolution fails.
- Mandatory JS syntax check passed.
- All relevant tests (364) passed.
Decision Log:
- **Actor Focus change:** Inspected tokens/actors now reliably clear the active sequence state. This prevents "floating" sequence context from an previous actor leaking into a new inspection focus.

### 2026-05-06 — Monster Actions: Focused Actor Sequence Tray (M7 extension)

Agent/model: Gemini CLI (Autonomous Mode)
Scope:
- Implement the Focused Actor Sequence Tray for composite / Multiattack actions.
- Added `focusedActorSequencePacket` and `focusedActorSequenceCompletedSteps` frontend state.
- Updated `executeFocusedActorAction` to detect and capture `assisted_sequence` resolution.
- Rendered Sequence Tray UI in the Focused Actor Panel with child steps and completion counters.
- Wired child buttons to trigger target preview for specific child sub-capabilities.
- Updated `resolveFocusedActorAction` and `cancelFocusedActorActionResolution` to return focus to the sequence tray.
- Added sequence state cleanup on actor change or non-child action selection.
Files changed:
- assets/web/dm/index.html
- tests/test_dm_focused_actor_panel_sequence.py (New)
- docs/dm_control_surface_living_agent_plan.md
Outcome:
- DMs can now execute complex Multiattack sequences step-by-step from the Focused Actor Panel.
- Each child attack uses the standard target selection and resolution flow.
- Progress is tracked visually within the sequence tray.
- **Correction Note:** Feature currently depends on map-click target selection; must be refactor to panel-first.
- Mandatory JS syntax check passed.
- All relevant tests (360) passed.

### 2026-05-06 — Monster Actions: Resolution Tray Hardening (M7 extension)

Agent/model: Gemini CLI (Autonomous Mode)
Scope:
- Harden the Focused Actor Panel Monster Actions Resolution Tray.
- Added `focusedActorResolutionInFlight` state to prevent duplicate submissions.
- Implemented button disabling and logic guards for Prepare and Apply phases.
- Improved error handling: show backend errors, keep tray for retry on failure.
- Added state cleanup: clear resolution state on actor change, action change, or expansion toggle.
- Added safety text: "Apply Results will update combat state."
- Verified successful apply clears all preview/tray/resolution state and applies snapshot.
- Ensured no regressions in standalone Monster Actions panel.
Files changed:
- assets/web/dm/index.html
- tests/test_dm_resolution_tray_hardening.py (New)
- tests/test_dm_focused_actor_panel_actions.py
Outcome:
- DM resolution flow is now significantly more robust and safer against accidental double-clicks or stale state.
- Clear visual and functional feedback for in-flight operations.
- Mandatory JS syntax check passed.
- All relevant tests (354) passed.

### 2026-05-06 — Monster Actions: Resolution Planning / Target-Resolution Review (M7 extension)

Agent/model: Gemini CLI (Autonomous Mode)
Scope:
- Perform a repo-grounded planning pass for wiring Monster Actions execution from the Focused Actor Panel.
- Identify existing execution flows (standalone panel vs LAN client).
- Define the Resolution Tray model and the first executable slice.
Files changed:
- docs/dm_control_surface_living_agent_plan.md
Outcome:
- Planning complete. Recommended path is to reuse the existing `/api/dm/monster-capabilities/${cid}/execute` and `/api/dm/monster-capabilities/${cid}/resolve-targets` endpoints.
- First executable slice identified as "Manual adjudication for selected targets."
- Resolution Tray design defined: an integrated panel replacing the Target Tray after execution is triggered.
- **Correction Note:** Planning normalized map-click targeting; must be refactored to panel-first.

### 2026-05-06 — Monster Actions: Range / AoE Validation Hints (M7 extension)

Agent/model: Gemini CLI (Autonomous Mode)
Scope:
- Implement advisory validation hints for Monster Actions in target preview mode.
- Add `getFocusedActorTargetAdvisory` helper to compute target status based on Chebyshev distance.
- Target Tray now shows color-coded validity status for each selected target (Likely in range, Likely out of range, AoE advisory).
- Tactical-map highlights are color-coded: yellow for likely valid/AoE, red for likely out-of-range.
- Map highlights for invalid targets include an "OUT OF RANGE" text label.
- Map highlights for AoE actions use a dashed yellow ring and "AOE ADVISORY" label.
- Target Tray includes a footer reminding the DM that selection is not blocked and they have final authority.
- No backend state changes, resource spending, or execution logic added.
Files changed:
- assets/web/dm/index.html
- tests/test_dm_focused_actor_panel_actions.py
- docs/dm_control_surface_living_agent_plan.md
Outcome:
- DM receives immediate spatial and textual feedback on target validity without being constrained by automated rules.
- Clear distinction between "direct range" actions and "AoE" actions in the validation UI.
- **Correction Note:** Highlights and hints currently support map-click targeting; must be refactored to panel-first.
- Mandatory JS syntax check passed.
- All relevant tests (347) passed.

### 2026-05-06 — Monster Actions: Selected-Target Highlighting (M7 extension)

Agent/model: Gemini CLI (Autonomous Mode)
Scope:
- Implement visual highlighting for the source actor and selected targets on the tactical map during Monster Actions target preview.
- Source actor is marked with a dashed orange ring and "SOURCE" label.
- Selected targets are marked with a solid yellow ring and "TARGET" label.
- Highlighting is visual-only and synchronized with the target tray state.
- Target count added to the preview status banner in the Focused Actor Panel.
- Highlighting is automatically cleared when target preview is disabled or cancelled.
- Normal token inspection and map interactions are preserved.
Files changed:
- assets/web/dm/index.html
- tests/test_dm_focused_actor_panel_actions.py
- docs/dm_control_surface_living_agent_plan.md
Outcome:
- Clear visual feedback on the map confirms which token is the source and which tokens are selected as targets.
- Map and tray remain in sync as targets are toggled.
- **Correction Note:** Highlighting currently visualizes map-click selections; must be refactored to panel-first.
- Mandatory JS syntax check passed.
- All relevant tests (346) passed.

### 2026-05-06 — Monster Actions: Target Selection Tray Prototype (M7 extension)

Agent/model: Gemini CLI (Autonomous Mode)
Scope:
- Implement a visual target selection tray prototype for Monster Actions in the Focused Actor Panel.
- Clicking a token on the tactical map while target preview is active toggles that token as a selected target.
- Selected targets appear in a visible Target Tray in the Focused Actor Panel with name, role, and HP.
- Toggling a target or clicking a "remove" button in the tray removes the target.
- "Clear targets" button added to the tray.
- Target list is cleared when target preview is closed, focused actor changes, or action changes.
- Stale targets (missing from snapshot) are automatically cleaned up.
- Normal token inspection is preserved when target preview is inactive.
Files changed:
- assets/web/dm/index.html
- tests/test_dm_focused_actor_panel_actions.py
- docs/dm_control_surface_living_agent_plan.md
Outcome:
- DM can interactively select multiple targets on the map while in target preview mode.
- Selected targets are summarized in a tray within the Focused Actor Panel.
- Visual state is correctly maintained across snapshot updates and actor changes.
- **Correction Note:** This feature currently relies on map-click target selection; must be refactored to panel-first.
- Mandatory JS syntax check passed.
- All relevant tests (345) passed.

### 2026-05-06 — Monster Actions: Target Mode Prototype (M7 extension)

Agent/model: Gemini CLI (Autonomous Mode)
Scope:
- Implement a visual-only target mode prototype for Monster Actions in the Focused Actor Panel.
- Add "Target Preview" button to expanded action cards.
- Implement tactical map overlay for range circles and AoE hints.
- Support Escape key and manual UI controls for cancelling target preview.
- Ensure no backend execution or state changes occur during preview.
Files changed:
- assets/web/dm/index.html
- tests/test_dm_focused_actor_panel_actions.py
- docs/dm_control_surface_living_agent_plan.md
Outcome:
- DM can enter a visual-only targeting preview mode for any structured monster action.
- Tactical map displays a dashed range circle and AoE shape label based on capability mechanics.
- Focused Actor Panel shows a prominent "Targeting Preview Active" status with a cancel button.
- Escape key cancels the preview mode.
- **Correction Note:** Feature currently normalizes map-click targeting; must be refactored to panel-first.
- Mandatory JS syntax check passed.
- All relevant tests (343) passed.

### 2026-05-06 — Tactical-map token-click inspection (M9 partial)

Agent/model: Gemini CLI (Autonomous Mode)
Scope:
- Implement token-click inspection for the Focused Actor Panel.
- Use global `focusedActorInspectCid` to track inspected actor.
- Show "Inspecting" vs "Active Turn" badges.
- Clear inspection state on blank snapshot or actor removal.
Files changed:
- assets/web/dm/index.html
- tests/test_dm_focused_actor_panel.py
- docs/dm_control_surface_living_agent_plan.md
Outcome:
- DM can click tokens on the map to inspect them in the Focused Actor Panel.
- Inspection does not change active combatant or turn.
- Visual feedback (badge) indicates current state.
- Mandatory JS syntax check passed.

### 2026-05-09 — Phase 3E1: live-smoke bugfix for Black and Tan /dmcontrol actions
Agent/model: Gemini CLI
Scope:
- Fixed `/dmcontrol` selected action description display to fallback to `desc` if `description` is missing.
- Fixed `target_mode` classification in `MonsterCapabilityService` and `InitiativeTracker`: range alone no longer triggers `area_manual`.
- Improved manual-only action UX: non-executable actions now render with a 'Manual' badge and unique styling; targeting mode is disabled for them.
- Fixed simple attack preview mismatch: backend `execute` with `spend: "none"` now returns a non-mutating `assisted` resolution packet for melee/ranged attacks.
- Surveillance check: Verified Multiattack child-sequence tray remains functional and correctly uses corrected attack flow.
- Added focused tests for `target_mode` and `executable` logic in `tests/test_black_and_tan_capabilities.py`.
Files changed:
- monster_capability_service.py
- dnd_initative_tracker.py
- assets/web/dmcontrol/index.html
- tests/test_black_and_tan_capabilities.py
- docs/dm_control_surface_living_agent_plan.md
Outcome:
- Black and Tan firearm and melee attacks are now correctly classified as single-target and previewable.
- Utility actions like Controlled Burst are clearly identified as manual assistance tasks.
- All primary attacks support the "Preview -> Apply" flow without premature mutation or "No description" errors.
- All Python tests and JS syntax checks passed.
Next recommended pass:
- Live game smoke testing only. No more feature passes unless a reproduced bug appears.

### 2026-05-09 — Phase 3D3: Black and Tan live-game readiness polish
Agent/model: Gemini CLI
Scope:
- Improved `MonsterCapabilityService` to generate `mechanics_summary` and `manual_instructions` for all capabilities.
- Updated `/dmcontrol` UI to display `mechanics_summary` in action cards and `manual_instructions` in the selection panel.
- Surfaced special rules (Controlled Burst, Rough Arrest, Vandergraff Drill) as clear manual instructions.
- Added explicit ammunition and condition reminders for Black and Tan units.
- Verified that Multiattack child-sequence apply flow remains functional.
- Added tests in `tests/test_black_and_tan_capabilities.py` for UI summaries and manual instructions.
Files changed:
- monster_capability_service.py
- assets/web/dmcontrol/index.html
- monster_capabilities/vandergraff/black-and-tan-rifleman.yaml
- monster_capabilities/vandergraff/black-and-tan-constable.yaml
- tests/test_black_and_tan_capabilities.py
- docs/dm_control_surface_living_agent_plan.md
Outcome:
- Remaining Black and Tan live-play gaps closed with clear DM reminders.
- Improved quick-read support for attack bonus, damage, and range in `/dmcontrol`.
- Action cards no longer show `[object Object]` for structured mechanics.
Next recommended pass:
- Phase 3E — Live game smoke testing and bugfix capture, or Phase 4 — Broader content expansion.

### 2026-05-09 — Phase 3D2: /dmcontrol Multiattack and assisted-sequence apply support
Agent/model: Gemini CLI
Scope:
- Added local sequence state tracking to `/dmcontrol`.
- Implemented Sequence Tray UI for `assisted_sequence` and `composite` actions.
- Multiattack/composite actions now render a list of child steps with completion tracking.
- DM can select individual child attacks, resolve them using the standard flow, and Apply Results.
- Successful child apply increments completion counts in the local sequence state.
- Integrated `selectLocalSequenceStep` to correctly manage child targeting and preview.
- State hardening: actor or unrelated action changes clear the active sequence.
- Verified Black and Tan Rifleman and Constable Multiattack now expose their Armalite Rifle or Pistol/Baton attacks correctly.
Files changed:
- assets/web/dmcontrol/index.html
- tests/test_dm_control_apply_results.py
- docs/dm_control_surface_living_agent_plan.md
Outcome:
- `/dmcontrol` supports multi-step actions like Multiattack.
- Black and Tan enemies are now significantly more usable in live DM-controlled combat.
- Safety guards prevent double-submits and ensure stale sequences are cleared.
Next recommended pass:
- Phase 3D3: live-game readiness polish or live-smoke bugfixes.

### 2026-05-09 — Phase 3D1: /dmcontrol Apply Results first safe slice
Agent/model: Gemini CLI
Scope:
- Implemented "Apply Results" logic in `/dmcontrol` for simple, direct selected-target action packets.
- Added `applyLocalResolutionResults(applyDamage, applyEffects)` function to call backend `/api/dm/monster-capabilities/{cid}/resolve-targets`.
- Updated Resolution Preview UI to include "Apply Damage", "Apply Effects", and "Apply Damage + Effects" buttons.
- Implemented double-submit guards using `localResolutionInFlight` to disable buttons during backend calls.
- Success path: applies returned snapshot, clears local resolution tray/packet/outcome state, and shows a compact success message.
- Error path: keeps tray open and displays backend error.
- Added manual fallback instructions for unsupported `automatic` and `assisted_sequence` packets.
- Verified Black and Tan Rifleman and Constable simple attacks can reach Apply Results via structured packets.
Files changed:
- assets/web/dmcontrol/index.html
- tests/test_dm_control_route.py
- tests/test_dm_control_apply_results.py (New)
- docs/dm_control_surface_living_agent_plan.md
Outcome:
- `/dmcontrol` now supports direct combat state mutation for supported monster actions.
- Safe, validated resolution flow modeled after `/dm` Focused Actor Panel.
- All Python tests and JS syntax checks passed.
Next recommended pass:
- Phase 3D2: Multiattack/sequence apply support OR live-smoke bugfixes.

### 2026-05-09 — Phase 3C3: Black and Tan Readiness

Agent/model: Gemini CLI (Autonomous Mode)
Scope:
- Prepare Black and Tan enemies for `/dmcontrol` usage.
- Update `monster_capabilities/vandergraff/black-and-tan-rifleman.yaml` and `black-and-tan-constable.yaml`.
- Add structured Multiattack as `composite` actions.
- Add structured mechanics for firearms (Armalite Rifle, .45 Pistol) and melee (Baton, Knife).
- Include traits (Vandergraff Drill, Baton and Boot, Fire Discipline) for visibility.
- Ensure all primary combat actions are marked as `executable: true`.
- Add focused validation tests in `tests/test_black_and_tan_capabilities.py`.
Files changed:
- monster_capabilities/vandergraff/black-and-tan-rifleman.yaml
- monster_capabilities/vandergraff/black-and-tan-constable.yaml
- tests/test_black_and_tan_capabilities.py
- docs/dm_control_surface_living_agent_plan.md
Outcome:
- Black and Tan Rifleman and Constable have fully structured capability overlays compatible with `/dmcontrol`.
- Multiattack resolves to its child actions in the UI.
- All primary attacks expose structured mechanics (attack bonus, damage, range/reach).
- Manual fallback notes provided for complex mechanics (Controlled Burst, Rough Arrest).
- All focused tests and relevant regression tests passed.
Next recommended pass:
- Phase 3D Apply Results planning or live-smoke bugfixes.

## Decision log

Agents should append or update durable decisions here.

| Date | Decision | Reason | Status |
|---|---|---|---|
| 2026-05-06 | Build a new DM control surface, not a polish pass on current dropdown controls | Current Monster Turn Controls / Monster Pilot are unintuitive and structurally wrong for active combat | Accepted |
| 2026-05-06 | Use LAN player flow as local interaction reference | Repo inspection found LAN targeting, movement range, attack resolution, and multi-target selection patterns | Accepted |
| 2026-05-06 | Initiative owns normal DM control actor | DM should not select active monster from dropdown when initiative already defines whose turn it is | Accepted |
| 2026-05-06 | Tactical map is reference/inspection first | Map should not become generic command surface; it should inspect tokens/cells and visualize spatial context | Accepted |
| 2026-05-06 | DM Toolbox holds rare/power/admin/debug controls | Keeps active cockpit focused and avoids clutter | Accepted |
| 2026-05-06 | Every spawned monster should be numbered | Duplicate names are confusing during combat | Completed |
| 2026-05-06 | Enemies/NPCs auto-roll initiative individually when added | Table rule; only PCs use LAN initiative prompts | Completed |
| 2026-05-06 | Browser asset JS syntax check required for DM/LAN HTML edits | Recent parse errors broke `/dm` despite Python tests passing | Accepted |
| 2026-05-06 | Separate /dm (cockpit) from /dmcontrol (active control) | Functional separation of concerns; high-intensity combat resolution needs a dedicated, focused surface | Accepted |

## Work Log - 2026-05-13
- Resumed interrupted pass for /dmcontrol UI improvements.
- Moved simple attack resolution from bottom tray into a large, desktop-friendly modal.
- Implemented automatic resolution preview and modal opening upon target selection.
- Added DM-facing labels (Hit, Miss, No Effect) and prominent damage input to the modal.
- Hidden backend packet and debug details behind collapsed sections in the modal.
- Improved map/tray resize recovery by resetting fittedToGrid and re-triggering resize logic.
- Verified fix for movement cost map entity cell access (row -> cell.row).
- Updated tests in tests/test_dm_control_apply_results.py to match the new modal-based UI.
- All relevant tests (tests.test_black_and_tan_capabilities, tests.test_dm_control_apply_results, tests.test_dm_control_route) passed individually.

### 2026-05-13 — Pass 1B: /dmcontrol modal UI live smoke observation
Agent/model: Gemini CLI
Scope:
- Live runtime observation of the new /dmcontrol modal UI.
- Detailed report: `docs/runtime_reports/dmcontrol_modal_smoke_20260513_1132.md`
Outcome:
- No server-side exceptions or tracebacks observed.
- Clean shutdown after 5-minute window.

### 2026-05-13 — Pass 1C: Latency fix, Range enforcement, and Dropdown stability
Agent/model: Gemini CLI
Status: Completed
Changes:
- **Latency & UX:** Added timing instrumentation, disabled "Apply Result" button while in-flight, removed 2s delay in UI refresh, and applied state snapshots immediately on success.
- **Range Enforcement:** Implemented backend distance validation in `_dm_monster_capability_resolve_targets` and updated frontend to warn/confirm if an attack target is likely out of range. Added `override_range` flag for DM adjudication.
- **UI Stability:** Preserved "Traits & Reminders" `<details>` state across re-renders in `renderActionPanel`.
- **Validation:** Added `test_dm_control_range_validation` to `tests/test_dm_control_apply_results.py`. Verified JS syntax in `assets/web/dmcontrol/index.html`. All 12 targeted tests passed.

### 2026-05-14 — Pass 2G: Controlled Burst stateful firearm modifier implementation
Agent/model: Gemini CLI
Scope:
- Implemented `Controlled Burst` as a structured, stateful modifier action for Black and Tan Rifleman.
- Added `action_type: modifier` support to `MonsterCapabilityService` with automated mechanics summaries.
- Implemented backend state for pending modifiers (`_monster_modifier_state`) in `InitiativeTracker`.
- Updated `_dm_monster_capability_execute` to arm modifiers, respecting `once_per_turn` limits and checking for `Jammed` weapons.
- Enhanced `_resolve_map_attack_sequence` to detect and apply pending modifiers during attack resolution.
- Added `Jammed` state on natural 1 if a modifier requires it (Jam Risk).
- Injected extra base weapon damage dice into resolution results for modified hits.
- Updated `/dmcontrol` UI to display `Active` and `Jammed` badges on action cards.
- Verified end-to-end functionality with a new test suite: `tests/test_black_and_tan_controlled_burst.py`.
Files changed:
- monster_capabilities/vandergraff/black-and-tan-rifleman.yaml
- monster_capability_service.py
- dnd_initative_tracker.py
- assets/web/dmcontrol/index.html
- tests/test_black_and_tan_controlled_burst.py (New)
- tests/test_black_and_tan_capabilities.py
- docs/dm_control_surface_living_agent_plan.md
Validation:
- `./.venv/bin/python3 -m unittest tests.test_black_and_tan_controlled_burst tests.test_black_and_tan_capabilities` → 16 tests passed.
- JS syntax check passed for `assets/web/dmcontrol/index.html`.
Outcome:
- Controlled Burst is now a fully automated, stateful modifier that correctly interacts with firearm resolution.
- Weapons can now become Jammed on a natural 1 after a Controlled Burst, blocking further use until cleared (manual clear for now).
- UI provides clear visual feedback for armed modifiers and jammed equipment.
Next recommended pass:
- Pass 2H: AOE/Multi-target support (Automation for SAM-7 or similar area effects).

### 2026-05-13 — Pass 2F: Black and Tan Multiattack conversion and manual tray cleanup
Agent/model: Gemini CLI
Scope:
- Converted Constable Multiattack from a manual-assist utility to a structured `choose_n: 2` composite action.
- Updated Rifleman Multiattack to use explicit `fixed_children` sequence and marked it `executable: true`.
- Added "Start Sequence" button to `/dmcontrol` for composite actions to initiate the multiattack flow.
- Cleaned up manual tray clutter by removing redundant Multiattack warnings in Black and Tan overlays.
- Verified that traits and reminders correctly collapse into the "Traits & Reminders" section.
- Ensured `Controlled Burst` and `Rough Arrest` remain as manual-assist entries (deferred automation).
Files changed:
- monster_capabilities/vandergraff/black-and-tan-rifleman.yaml
- monster_capabilities/vandergraff/black-and-tan-constable.yaml
- assets/web/dmcontrol/index.html
- docs/dm_control_surface_living_agent_plan.md
- tests/test_black_and_tan_capabilities.py
Validation:
- `python3 -m unittest tests.test_black_and_tan_capabilities tests.test_monster_sequence_schema tests.test_monster_sequence_state` → 22 tests passed.
- JS syntax check passed for `assets/web/dmcontrol/index.html`.
Outcome:
- Black and Tan enemies now have fully structured, executable Multiattack sequences in `/dmcontrol`.
- The DM can initiate these sequences via a single button click, followed by child action targeting.
- Sequence budgets and progress are authoritatively tracked and enforced by the backend.
Next recommended pass:
- Pass 2G: AOE/Multi-target support (Automation for SAM-7 or similar area effects).

### 2026-05-13 — Pass 2C: Multiattack Schema & Service Support
Agent/model: Gemini CLI
Scope:
- Added `sequence_kind` and `choose_n` support to `MonsterCapabilityService` and `/execute` backend.
- Supported both legacy list-based `composite` actions and new object-based `composite` with `children`, `sequence_kind`, and `choose_n`.
- Metadata is exposed in UI summaries and `/execute` responses for `assisted_sequence` resolution.
- Added targeted tests in `tests/test_monster_sequence_schema.py` for varied schema shapes.
- Updated `docs/monster-capability-schema.md` with valid YAML examples for choose-N sequences.
Files changed:
- monster_capability_service.py
- dnd_initative_tracker.py
- docs/monster-capability-schema.md
- tests/test_monster_sequence_schema.py (New)
Outcome:
- Backend correctly parses and surfaces Multiattack sequence metadata.
- Backward compatibility for existing Troll/Rifleman-style fixed sequences is preserved.
- All targeted tests passed.
Next recommended pass:
- Pass 2D: Backend Sequence Authority (tracking `choose_n` budget in combat state).

### 2026-05-13 — Pass 1D Rescue: Interrupted run cleanup and Modal state fix
Agent/model: Gemini CLI
Status: Completed
Scope:
- Cleaned up interrupted Pass 1D noisy instrumentation and formatting churn in `dnd_initative_tracker.py`.
- Fixed initial state of "Apply Result" button in the resolution modal.
- Fixed trailing whitespace errors.
Outcome:
- **Cleanup:** Removed all `[DEBUG]` timing logs and restored clean `_lan_snapshot` and `_lan_force_state_broadcast` methods.
- **UI Bugfix:** Ensured `localResolutionApplying` state is reset when the modal or tray is closed/cancelled, preventing the button from being stuck in "Applying..." state.
- **Validation:** `py_compile` clean, JS syntax check passed, and targeted range validation tests passed.
- **Latency:** 11-12s latency remains unresolved as it requires deeper investigation beyond this rescue pass.
Recommended next pass:
- **Pass 2:** Multiattack expansion and AoE/multi-target support, now that the foundation is stable and clean.

### 2026-05-14 — Pass 2H: Black and Tan remaining manual combat cleanup
Agent/model: Gemini CLI
Scope:
- Implemented **Rough Arrest** as a structured rider prompt for Black and Tan Constable.
- Updated `dnd_initative_tracker.py` and `assets/web/dmcontrol/index.html` to support **Rider Prompts** in the resolution modal.
- Cleaned up the `/dmcontrol` action tray by demoting `executable: false` items (Manual Assist) to the collapsed "Traits & Reminders" section.
- Updated `MonsterCapabilityService` to include rider names in action summaries.
- Resolved manual combat friction by clearly separating actionable cards from passive rules.
Files changed:
- monster_capabilities/vandergraff/black-and-tan-constable.yaml
- monster_capability_service.py
- dnd_initative_tracker.py
- assets/web/dmcontrol/index.html
- tests/test_black_and_tan_capabilities.py
- tests/test_black_and_tan_rough_arrest.py (New)
Validation:
- `./.venv/bin/python3 -m unittest tests.test_black_and_tan_capabilities tests.test_black_and_tan_rough_arrest` → All tests passed.
- JS syntax check passed for `assets/web/dmcontrol/index.html`.
Outcome:
- Rough Arrest now appears as a clear DM-facing prompt after a successful Baton hit, reducing mental load.
- Tray clutter is significantly reduced; DM only sees clickable actions in the primary area.
- Passive reminders (Vandergraff Drill, Fire Discipline, etc.) remain accessible but out of the way.
Next recommended pass:
- Pass 2I: Add additional Black and Tan enemies (Shield Trooper, Medic, etc.) from the firearms plan.
