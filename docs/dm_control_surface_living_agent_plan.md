# DM Control Surface Redesign — Living Agent Plan

Version: 2026-05-06  
Status: Living planning and execution document  
Recommended repo path: `docs/dm-control-surface-living-plan.md`  
Source plan: `docs/dm-control-surface-master-plan.md`

## How to use this document

This is the working document agents should use when planning, implementing, and reporting DM control-surface work.

The master design direction is stable:

- Build a new actor-centered DM combat control surface.
- Do not polish the current dropdown-heavy Monster Turn Controls / Monster Pilot as the target UI.
- Use LAN player flow as the local interaction reference.
- Keep the tactical map primarily as a reference/inspection surface with spatial movement/targeting visualization.
- Move rare, destructive, override, setup, and debugging tools into DM Toolbox.
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

## Non-negotiable guardrails

### UI direction

- The current `/dm` right-side dropdown control stack is not the target UI.
- Monster Turn Controls and Monster Pilot are legacy/current fallback surfaces.
- Do not build new active-combat workflows from dropdown stacks.
- Do not let agents invent major interaction models without user approval.
- Use LAN player flow as the local interaction reference.
- Design for complex monsters first: dragons, spellcasters, legendary creatures, AoEs, multiattack, riders, and spellcasting.

### Runtime and state direction

- Preserve backend authority.
- Do not introduce a DM-only parallel source of truth.
- Treat stale UI as frontend state/DOM bugs unless endpoint evidence proves backend divergence.
- Use measured evidence for bug/performance fixes.
- Separate confirmed findings from hypotheses.

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

### Large-file discipline

The browser files are large. Do not wander.

Known size context from repo inspection:

- `assets/web/lan/index.html` is about 26k lines.
- `assets/web/dm/index.html` is about 6.8k lines.
- `dnd_initative_tracker.py` is about 47k lines.

For implementation tasks, agents should use exact anchors. Broad file-wide exploration is allowed only in explicit discovery/research passes.

## Current status snapshot

Update this section after each pass.

| Area | Current status | Notes |
|---|---|---|
| `/dm` bootstrap/render | Verified | Recent parse/stale reset bugs were fixed; HP/Temp HP/Remove Combatant/Set Initiative migrated to Toolbox |
| `/` LAN client | Useful local model | LAN has targeting, movement range, attack resolution, spell target selection, and remaining movement concepts |
| Monster Turn Controls | Legacy/fallback | Do not polish as target UI |
| Monster Pilot | Legacy/fallback | Do not use as foundation for future current-turn movement |
| Monster capability backend | Useful | Labels renamed to 'Monster Actions' in DM UI |
| Focused actor panel | Prototype | Current actor focused automatically; token click inspects; stats and actions display |
| DM Toolbox | In progress | Tabbed modal with Session, Encounter, Overrides tabs partially populated |
| Encounter Builder | In progress | Monster Library search and Add Monster workflow migrated to Encounter tab |
| Duplicate monster names | Completed | Backend auto-numbering implemented via CombatantNameService |
| Enemy/NPC initiative | Completed | Auto-roll individually when added via monster spawn path |
| Tactical map inspection | Completed | Token click focuses actor in panel without changing initiative turn |
| Movement model | Planned | Reuse/expose LAN canonical movement path where possible |
| Battle log | Planned refinement | Gameplay-focused, detailed, visible by default; technical logs separate |
| Automation settings | Planned | Support app rolls and manual/physical dice per roll or roll type |
| Map editor | Deferred | Separate tool/mode; do not bolt onto combat cockpit |

## Final target interaction model

### Normal monster/NPC turn

1. Initiative advances.
2. Current actor is automatically focused.
3. Focused actor panel shows stats, conditions, movement, resources, and actions.
4. Legal movement range appears.
5. DM may move before acting.
6. DM selects an action card.
7. Action enters target mode.
8. Valid targets/range/area appear.
9. DM selects target or targets.
10. Resolution handles hit, save, damage, effects, riders, and resources.
11. DM may continue moving or acting if valid.
12. DM ends turn.

Movement is not a single fixed phase. The UI must support split movement such as move, attack, move, bonus action, move, end.

### Focused actor panel

Default actor:

- current initiative actor

Inspection actor:

- clicked token, or current actor by default

PC behavior:

- player characters are view-only by default
- DM control of PCs requires Toolbox override

Visible data should include:

- name
- side/type
- HP and temp HP
- AC
- speed
- passive perception
- initiative
- conditions
- position/facing if useful
- remaining movement
- resources/recharge/limited uses
- grouped action cards

### Action cards

Collapsed cards show mechanics summary:

- name
- attack bonus or save DC
- damage
- damage type
- range/reach/area
- recharge/resource marker
- key rider summary

Expanded cards show full description/rules text.

Unsupported/manual cards are collapsed by default and clearly labeled Manual / Assisted.

Candidate groups:

- Actions
- Bonus Actions
- Reactions
- Legendary Actions
- Spellcasting
- Traits / Passive Rules
- Manual / Unsupported

Action grouping defaults still need prototype work against complex monster data.

### Targeting and resolution

- Selecting an attack/action enters target mode.
- Escape cancels target mode without consuming resources.
- Valid targets should be highlighted.
- AoE and multi-target selections should display selected targets before resolution.
- Damage can be automatic after the relevant result is determined.
- AoE/mass effects may require review/confirmation.

The system must support both app rolls and physical dice/manual entry.

Automation settings should eventually support app/manual toggles for:

- attack rolls
- damage rolls
- saving throws
- initiative
- recharge rolls

### Multiattack

Preferred flow:

- guided assisted sequence
- child attacks tracked
- different targets allowed when legal
- app warns/assists but does not over-enforce
- DM remains authoritative

Example:

- Multiattack starts Bite, Claw, Claw.
- The sequence tracks Bite 0/1 and Claw 0/2.
- DM may choose same target or choose per child attack if legal.

### Movement

Movement range should:

- appear automatically at the start of every monster/NPC turn
- remain visible because movement can be split
- track remaining movement
- reject invalid drags
- snap token back on invalid drag
- not consume movement on invalid drag

Diagonal movement remains unresolved. Do not change diagonal logic until current repo behavior and table rule are confirmed.

### Force / override movement

Force/override is not normal movement.

Initial model:

- lives in DM Toolbox
- requires confirmation
- may allow moving any token, out-of-turn movement, or forced illegal movement
- should log visibly when used

Future WIP:

- crates/objects
- physics-like interactions
- pushed/shoved movement
- terrain/object interactions

### Tactical map

Default display:

- current initiative actor

Left-click token:

- inspect/focus that token

Left-click empty cell:

- show detailed cell information

Drag current-turn token:

- current actor movement

Right-click token:

- possible future contextual actions

Right-click empty cell:

- map tools only in explicit map-edit mode

Map editing should be a separate mode/tool, not bolted onto combat controls.

### DM Toolbox

One modal with tabs.

Accessible from cockpit and map.

All actions require confirmation.

Planned tabs:

- Session
- Encounter
- Overrides
- Map Tools
- Debug

Session tab:

- New Blank Session
- Save Session
- Load Session
- Add Player Profiles

Encounter tab:

- Monster Library / Add Monsters
- Encounter group tools
- Remove Combatant
- possibly Add Custom Combatant if retained

Overrides tab:

- HP adjustment
- Temp HP adjustment
- manual initiative
- DM-side PC control override
- move any token / force movement
- reroll all enemy/NPC initiative

Map Tools tab:

- map setup
- hazards
- structures
- terrain
- elevation
- background layers
- overlays
- manual AoE placement

Debug tab:

- endpoint health
- runtime status
- debug command reminders
- log/status summaries
- webdev debug workflow reminder

### Encounter Builder / Monster Library

Desired behavior:

- search
- browse
- visible name, CR, AC, HP, type
- spawn count
- automatic numbering
- mixed monster groups later
- HP randomization later

Current Add Combatant should move to Advanced/Debug for now.

### Initiative

Confirmed rule:

- all enemies/NPCs auto-roll initiative individually when added
- PCs use LAN initiative prompts when appropriate
- no shared initiative by default unless a specific summon/feature says so
- reroll all enemy/NPC initiative belongs in DM Toolbox

### Battle log

Battle log should:

- default visible
- remain toggleable
- log D&D gameplay events in useful detail
- exclude technical/debug logs

Gameplay log should include:

- turn changes
- attacks
- saves
- damage
- healing
- conditions
- resources
- meaningful movement
- important state changes

## Repo inspection anchors

Agents should use these anchors when implementing or researching related work.

### LAN player interaction anchors

- `assets/web/lan/index.html`
- `getClaimedWeapons()`
- `getClaimedInventoryItems()`
- `resolveOwnedInventoryWeaponForSelector()`
- `getSelectedMainhandWeapon()`
- `refreshWeaponSelectors()`
- `setAttackOverlayMode(enabled)`
- `openAttackResolveModal(target, weapon)`
- `runSpellTargetingAgainstTarget(target)`
- `renderSpellTargetSelectionUi()`
- `effectiveAttackRangeFeetForWeapon(weapon, unit)`
- `activeControlledUnitCid()`
- `draw()`

### LAN movement anchors

- `getMovementRangeCostMap(unit, cols, rows, feetPerSquare)`
- `movementCostMap(...)`
- `move_remaining`
- `_lan_try_move(cid, col, row)`

### DM legacy controls to avoid treating as target

- `monsterActorCidSelect`
- `monsterCapabilitySelect`
- `monsterPilotCidSelect`
- `mapCidSelect`
- `initCidSelect`
- `removeCidSelect`
- Monster Turn Controls
- Monster Pilot
- Normalized Capabilities

### Backend/state anchors

- `combat_service.py`
- `CombatService`
- `_dm_console_snapshot_payload()`
- `_lan_snapshot()`
- `_dm_tactical_snapshot_from_lan_snapshot()`
- `/api/dm/combat`
- `/api/dm/sessions/new`

### Monster action anchors

- `monster_capability_service.py`
- `monster_capabilities/samples/adult-red-dragon.yaml`
- `_dm_monster_attack_options()`
- `_dm_resolve_monster_attack_sequence()`
- `_dm_monster_capability_execute()`
- `_dm_monster_capability_resolve_targets()`
- `_dm_monster_capability_resource_op()`
- `_dm_monster_capability_effect_change()`
- `_dm_monster_spell_target()`

### Known backend cleanup anchors

- `/api/dm/encounter/monsters/add`
- `CombatService.add_monster_spec_combatants()`
- `CombatService.roll_initiative()`

## Milestone board

Update the status column after each pass.

| ID | Milestone | Status | Next concrete pass |
|---|---|---|---|
| M0 | Stabilize `/dm` and `/` before redesign | In progress / verify | Browser smoke after current fixes |
| M1 | Low-risk correctness cleanup | Completed | Q5 - DM Toolbox shell |
| M2 | DM Toolbox shell | Completed | Modal shell + tabs |
| M3 | Move Session tools to Toolbox | Completed | Migrated New/Save/Load/Quick |
| M4 | Encounter Builder / Monster Library | In progress | Complete Encounter Builder (mixed groups/staging) |
| M5 | Initiative flow | In progress | Reroll all enemy/NPC initiative in Toolbox |
| M6 | Focused actor panel prototype | Completed | Static/prototype actor panel using current actor |
| M7 | Monster Actions / action cards | In progress | Display-only integration in Focused Actor Panel |
| M8 | Current-turn movement model | Not started | Reuse LAN movement path for DM current actor |
| M9 | Tactical map inspection | Not started | Token click inspection / empty cell info |
| M10 | Automation settings | Not started | Roll-path and persistence inspection |
| M11 | Battle log refinement | Not started | Gameplay-vs-debug log split review |
| M12 | Map tools / map editor separation | Deferred | Move advanced map controls later |

## Work log

Agents should append concise entries here.

Template:

Date:
Agent/model:
Branch/commit:
Scope:
Files inspected:
Files changed:
Validation:
Manual/browser result:
Outcome:
Next recommended pass:
Notes/risks:

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
- M7 — Monster Actions: Action execution from Focused Actor Panel.

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

## Open decisions and research needs

Do not implement these until resolved.

### OD1 — Exact action grouping defaults

Need prototype against complex local monster data.

Questions:

- Which sections are open by default?
- How should spellcasting be grouped?
- Should legendary actions show outside the monster’s turn?
- How do dragons and archmages look without scrolling?

### OD2 — Diagonal movement

Need repo/table decision.

Options:

- current repo behavior
- simple 5-foot diagonals
- alternating 5/10 diagonal rule
- configurable setting

### OD3 — Target tray behavior

Need focused repo pass against LAN spell target selection UI.

Questions:

- How much of LAN multi-target UI can be reused?
- How should selected AoE targets be edited before resolution?
- How should allies/enemies be distinguished visually?

### OD4 — Automation settings shape

Need roll-path and persistence inspection.

Questions:

- Which rolls can be app/manual today?
- Where should settings persist?
- Are settings per-session, per-campaign, per-DM, or global?
- How are app rolls represented in battle log?

### OD5 — Combat log display design

Need later UI decision.

Options:

- docked panel
- collapsible drawer
- filter chips
- grouped events
- DM-only vs player-visible events

### OD6 — HP randomization

Desired later.

Need to inspect monster HP/hit-dice data availability and decide modes:

- average
- roll
- roll per group
- manual

## Immediate implementation queue

These are safe before major UI replacement.

### Q1 — Auto-number duplicate monster spawns

Goal:

- Every spawned monster receives unambiguous numbering.

Expected behavior:

- repeated single spawns continue numbering existing monsters
- grouped spawns number all members
- mixed future groups should also number correctly

Likely files:

- `dnd_initative_tracker.py`
- `combat_service.py`
- relevant DM encounter tests

Validation:

- focused backend tests
- snapshot/API tests
- no browser UI changes unless scoped

### Q2 — Auto-roll enemy/NPC initiative individually when added

Goal:

- Enemies/NPCs do not default to initiative 0.
- Each enemy/NPC rolls independently when added.
- PCs retain LAN initiative prompt behavior.

Likely files:

- `dnd_initative_tracker.py`
- `combat_service.py`
- session/DM encounter tests

Validation:

- initiative value is rolled
- modifier source is correct
- player initiative prompt behavior unaffected

### Q3 — Rename Normalized Capabilities to Monster Actions

Goal:

- Replace implementation jargon with user-facing language.
- Improve no-match message.

Likely files:

- `assets/web/dm/index.html`
- DM asset tests

Validation:

- JS syntax check
- asset tests
- browser smoke if practical

### Q4 — Improve no-match and fallback messaging

Goal:

- Missing overlays feel like missing enhanced cards, not broken monsters.

Suggested message:

- “No structured action cards for this monster yet. Use the stat block/manual controls.”

Validation:

- asset tests
- visual/browser confirmation

### Q5 — DM Toolbox shell

Goal:

- Create accessible modal shell and tabs.
- Do not move every control at once.

Likely tabs:

- Session
- Encounter
- Overrides
- Map Tools
- Debug

Validation:

- JS syntax check
- accessibility sanity checks
- asset tests
- browser smoke

## Milestone acceptance details

### M0 — Stabilize before redesign

Complete when:

- `/dm` opens without parse errors.
- `/` opens and claim flow works.
- New Blank Session clears DM and LAN.
- No current blocker prevents short manual combat smoke.
- Browser asset syntax guard is committed.

### M1 — Low-risk correctness cleanup

Complete when:

- monster spawns are auto-numbered
- enemy/NPC initiative auto-rolls individually when added
- Normalized Capabilities label is gone from user-facing UI
- no-match message is clear

### M2 — DM Toolbox shell

Complete when:

- Toolbox modal exists
- tabs exist
- confirmation wrapper exists
- no major control migration breaks active combat
- accessibility basics are present

### M3 — Encounter Builder / Monster Library

Complete when:

- monster library supports search/browse
- result rows/cards show name, CR, AC, HP, type
- spawn count works
- auto-numbering integrated
- shallow Add Combatant is no longer primary

### M4 — Initiative flow

Complete when:

- adding enemy/NPC auto-rolls initiative
- active combat additions also roll
- PCs still use LAN prompts
- reroll enemy/NPC initiative exists in Toolbox

### M5 — Focused actor panel prototype

Complete when:

- current initiative actor appears by default
- clicked token can inspect another actor
- PCs are view-only by default
- complex monster can be displayed without using dropdown primary controls
- panel is approved before full replacement

### M6 — Monster Actions / action cards

Complete when:

- action cards render in focused actor panel
- collapsed summaries show core mechanics
- expansion shows full text
- action target mode connects to resolution
- multiattack sequence has first usable assisted flow

### M7 — Current-turn movement model

Complete when:

- movement range appears for monster/NPC turns
- drag current actor works through canonical movement validation
- movement remaining updates
- invalid moves snap/reject without spending movement
- override movement remains in Toolbox

### M8 — Tactical map inspection

Complete when:

- default inspection shows current actor
- token click inspects token
- empty cell click shows useful cell info
- advanced map controls are not in active cockpit

### M9 — Automation settings

Complete when:

- roll settings exist for major roll types
- app/manual modes are both supported intentionally
- behavior is reflected in resolution UI and battle log

### M10 — Battle log refinement

Complete when:

- gameplay log is detailed enough to reconstruct combat
- technical/debug logs are separated
- visibility toggle remains
- log noise is manageable

### M11 — Map tools / map editor separation

Complete when:

- advanced map controls live outside active cockpit
- map editing is explicitly separate from combat operation

## Validation expectations by task type

### Browser asset task

Required:

- inline JS syntax check for edited DM/LAN HTML
- focused asset tests
- relevant browser smoke if behavior is user-visible

### Backend spawn/initiative task

Required:

- focused backend tests
- snapshot/API tests
- no browser UI changes unless explicitly scoped

### Movement task

Required:

- movement cost/path/blocking tests
- movement remaining tests
- invalid movement no-spend test
- LAN movement regression tests

### Monster action task

Required:

- capability service tests
- target resolution tests
- backend endpoint tests
- action-card asset tests if UI changes

### Session/reset task

Required:

- `/api/dm/combat` empty-state verification
- `/api/dm/monster-pilot` empty-state verification if relevant
- LAN client clear behavior
- DM stale UI clear behavior
- no heavy static rebroadcast regression

## End-of-pass report template

Agents should use this structure for non-trivial passes.

Summary:

Files inspected:

Files changed:

Confirmed evidence / root cause / design reason:

Implementation details:

Tests added or changed:

Validation commands and results:

Browser/manual smoke result, if applicable:

Updated sections in this document:

Known limitations / risks:

Single best next pass:

## Prompt guardrail block

Use this block in future agent prompts when relevant.

Do not treat current Monster Turn Controls or Monster Pilot as the target UI. Do not build new active-combat workflows from dropdown stacks. Use LAN player flow as the local interaction reference. Inspect exact named functions before editing large browser assets. Avoid broad wandering in `assets/web/lan/index.html` or `assets/web/dm/index.html` unless this is explicitly a discovery pass. Preserve backend source-of-truth. Do not introduce DM-only parallel state. If editing `assets/web/dm/index.html` or `assets/web/lan/index.html`, run the browser asset JavaScript syntax check and report the exact command/result. Separate confirmed findings from hypotheses. Use measured runtime evidence for bug/performance fixes.

## Final acceptance vision

The redesign is successful when the DM can run a complex monster turn without using the old dropdown stacks.

A successful turn should feel like:

1. The monster’s turn comes up.
2. The actor panel updates automatically.
3. The map shows the monster and legal movement range.
4. The DM sees the monster’s relevant actions without opening a stat block.
5. The DM drags movement if desired.
6. The DM clicks an action card.
7. Target mode begins.
8. Valid targets or AoE preview appear.
9. The DM selects target(s).
10. Resolution guides hit/save/damage/effects.
11. Movement remaining and resources update.
12. Combat log records important events.
13. The DM ends turn.

The old Monster Turn Controls and Monster Pilot should no longer be the primary way to run combat.
