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

## Current status snapshot

Update this section after each pass.

| Area | Current status | Notes |
|---|---|---|
| `/dm` cockpit | Admin/reference/setup | Cleaned up; legacy controls demoted. Link to `/dmcontrol` added. |
| `/dmcontrol` | Map shell added | Dedicated LAN-style monster/NPC control page. Read-only map surface with grid and tokens implemented. |
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
| Movement model | Gaps | LAN movement works; monster/NPC-specific movement on `/dmcontrol` planned. |

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
- No `/dmcontrol` route or page exists yet.
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
| M2 | Phase 2 — LAN-like map & movement | In progress | Phase 2A (Read-only map) completed |
| M3 | Phase 3 — Basic attack flow | Not started | Action cards + normal attacks |
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
- Phase 3A — Basic attack action display and selection on `/dmcontrol`.

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
Next recommended pass:
- M7 — Monster Actions / action cards integration (first slice).

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
