# DM Control Surface Redesign — Master Plan

Version: 2026-05-06  
Target repo path: `docs/dm-control-surface-master-plan.md`

## 1. Purpose

This document is the consolidated master plan for redesigning the `init-tracker` DM control surface.

It merges the milestone planning documents, repo inspection findings, and online research synthesis into one repo-ready plan. It should be treated as the source-of-truth planning document for future DM control-surface work until replaced by a newer plan.

This is not a single implementation task. It is a design, sequencing, and guardrail document for issuing bounded implementation passes.

## 2. Source material consolidated

This master plan combines the following planning artifacts:

- Initial DM control surface milestone plan.
- Revised milestone plan with live user feedback.
- Final workshop milestone plan v3.
- Deep repo inspection milestone plan.
- Online UX / D&D / VTT research synthesis.

The key evolution across those documents was:

1. The original plan identified that the current DM controls were cluttered and dropdown-heavy.
2. The workshop clarified that the desired result is not a polish pass on the current right-side controls; it is a new DM control surface.
3. Repo inspection confirmed that the LAN player client already contains much of the desired interaction model.
4. Online research supported the actor-centered, recognition-over-recall, target-mode, and progressive-disclosure direction.
5. This master plan combines those findings into a final implementation roadmap.

## 3. Executive summary

The current `/dm` page contains useful backend-backed features, but the active combat control model is wrong.

The future DM combat surface should not be based on the current Monster Turn Controls, Monster Pilot, or other stacked dropdown controls. Those should be treated as legacy/current fallback surfaces.

The target model is:

- Initiative selects the normal control actor.
- The current monster/NPC/enemy automatically appears in a focused actor panel.
- That panel behaves like a LAN-style actor sheet for the DM.
- Monster actions are visible as grouped action cards/buttons, not hidden in dropdowns.
- Selecting an action enters target mode.
- Valid targets are highlighted.
- Area and multi-target actions show selected targets before resolution.
- Multiattack is a guided assisted sequence, not rigid over-enforcement.
- Movement range appears automatically and remains visible because movement can be split.
- Movement is tracked through remaining movement.
- Invalid movement snaps/rejects without spending movement.
- The tactical map is primarily reference and inspection, with movement and targeting visualization layered on top.
- Rare, powerful, setup, override, and debug controls move into a tabbed DM Toolbox.
- Encounter setup becomes a real Monster Library / Encounter Builder instead of a shallow monster dropdown.
- Technical/debug information stays out of the D&D combat log.

The LAN player client is the best local model to reuse. The repo inspection found existing LAN patterns for target mode, attack resolution, multi-target spell selection, movement range, and movement remaining. Future DM work should adapt those patterns rather than inventing a new interaction language.

## 4. Non-negotiable direction

### 4.1 This is a new control surface

The target DM combat control surface is not a polish pass on the current `/dm` right-side dropdown controls.

The current dropdown-heavy Monster Turn Control and Monster Pilot model is not the foundation. It should be frozen, demoted, or deprecated as the new model comes online.

The target is a new DM combat control model:

- LAN-style actor sheet/control surface.
- Dynamically focused on the current initiative actor.
- Actor-centered, action-card-driven, and target-mode-driven.

### 4.2 Initiative owns normal actor focus

The DM should not normally select a monster from a dropdown before controlling it.

When initiative advances, the current actor becomes the default control actor. The focused actor panel updates automatically.

Manual actor control is an exception and belongs in DM Toolbox override flows.

### 4.3 Dropdowns are not active-combat controls

Dropdowns are acceptable for setup, filtering, modals, rare configuration, debugging, and toolbox/admin controls.

Dropdowns are not acceptable as the main way to run:

- monster turns
- movement
- attacks
- target selection
- action selection
- repeated combat commands

### 4.4 Design for complex creatures first

The UI must be designed with the hardest stat blocks in mind:

- dragons
- spellcasters
- legendary creatures
- recharge actions
- AoE actions
- multi-target actions
- multiattack
- rider effects
- spell slots and daily powers
- long passive trait lists

If the UI works for an adult dragon or archmage, simple monsters will fit cleanly.

### 4.5 Tactical map is reference and inspection first

The map is not the general-purpose control surface.

It should primarily answer:

- where everyone is
- what token/cell is selected
- what the current actor is
- what is in a cell
- what effects/terrain/elevation matter
- what range/area/movement information matters right now

The map may support spatial actions like dragging the current actor or selecting targets, but it should not host every combat/admin/map control.

### 4.6 DM Toolbox holds power tools

Rare, destructive, override, setup, and debugging actions belong in a tabbed DM Toolbox modal.

All DM Toolbox actions require confirmation.

### 4.7 Agents must not invent major UI interaction models

For any major DM control-surface work, the interaction model must be approved before implementation.

Future prompts should explicitly say:

- Do not treat current Monster Turn Controls or Monster Pilot as the target UI.
- Do not build new active-combat workflows from dropdown stacks.
- Use LAN player flow as the local interaction reference.
- Inspect exact named functions before editing large browser assets.
- Run browser asset JavaScript syntax checks when editing DM/LAN HTML.

## 5. Current surface inventory and decision table

| Current area | Verdict | Master-plan decision |
|---|---|---|
| Cockpit tracking | Useful | Keep and refine |
| AC / HP / conditions display | Useful | Keep visible in combat |
| Conditions UI | Good and intuitive | Keep in main combat flow |
| Duplicate enemy names | Real usability issue | Backend auto-number every spawn |
| HP Adjustment | Useful but rare | Move to DM Toolbox Overrides |
| Temp HP | Useful but rare | Move to DM Toolbox Overrides |
| Monster Turn Controls | Wrong interaction model | Freeze/deprecate; replace with focused actor panel |
| Monster Pilot | Wrong interaction model | Freeze/deprecate; replace with current-turn movement |
| Normalized Capabilities | Useful backend, bad UI label | Rename to Monster Actions and move into actor panel |
| Add Player Profiles | Useful but setup/session flow | Move to DM Toolbox Session |
| Add Monster Specs | Useful but underbuilt | Replace with Encounter Builder / Monster Library |
| Add Combatant | Too shallow for high-level play | Move to Advanced/Debug; later replace with deeper builder if needed |
| Set Initiative | Useful | Keep manual override; add enemy/NPC auto-roll |
| Remove Combatant | Useful but rare | Move to DM Toolbox Encounter or Overrides |
| Map Setup | Useful but clunky | Move to Map Tools / Map Editor flow |
| Session Persistence | Useful but rare | Move to DM Toolbox Session |
| Tactical Map controls | Too broad/dropdown-heavy | Demote to map reference/inspection and Map Tools |
| Battlefield Cell / Hazards / Features / Structures / AoE / Overlays stack | Not useful in active combat surface yet | Hide/collapse into Map Tools until redesigned |
| Battle log | Useful | Default visible, gameplay-focused, detailed |
| Debug/log technical output | Useful but not gameplay | Separate debug logs and Debug tab |

## 6. Research-backed design principles

### 6.1 Recognition over recall

Online UX research supports showing relevant information and actions rather than forcing the DM to remember stat blocks, dropdown paths, or hidden options.

Applied to `init-tracker`:

- The current actor’s stats/actions should be visible.
- Core mechanics such as attack bonus, range, save DC, damage, and resource state should appear in collapsed action summaries.
- Full text should be available by expansion, not required to run every action.

### 6.2 Menus and dropdowns are temporary choice surfaces

Research supports using menus/dropdowns for temporary selections or configuration. It does not support using them as the main command surface for repeated active combat.

Applied to `init-tracker`:

- Dropdowns can live in DM Toolbox, filters, search facets, or setup forms.
- Active monster turns should use visible action cards/buttons and direct target mode.

### 6.3 Progressive disclosure is useful but can hide too much

Collapsible sections are appropriate for complex monster stat blocks, but important actions must not be buried.

Applied to `init-tracker`:

- Actions should be open by default.
- Bonus Actions should be open by default when present.
- Full action text should be collapsed behind summaries.
- Traits, passive rules, and long spell lists can be collapsed.
- Bad pattern: every important action hidden behind accordions each turn.

### 6.4 Inspector panels match tactical-map usage

Inspector panels are a good match for token/cell inspection.

Applied to `init-tracker`:

- Default inspector shows the current initiative actor.
- Clicking a token inspects that token.
- Clicking an empty cell shows cell information.
- Inspection does not automatically change the normal control actor.

### 6.5 Control, inspection, and targeting are distinct states

VTT patterns support separating selected/control actor from targeted actors.

Applied to `init-tracker`:

- Control actor: current initiative actor by default.
- Inspected actor: clicked token or current actor by default.
- Targeted actors: selected during target mode.
- Override actor: temporary DM Toolbox override.

These states should not collapse into one ambiguous dropdown value.

### 6.6 Movement split and remaining movement tracking are rules-backed

D&D turn movement can be split around actions. This supports the requirement that movement range remain visible and movement remaining be tracked through the turn.

Applied to `init-tracker`:

- Movement range should show automatically at the start of every monster/NPC turn.
- Movement range should remain visible.
- Remaining movement should update as movement is spent.
- Invalid movement should reject/snap back without spending movement.

### 6.7 Multiattack should assist, not over-enforce

Monster multiattack is stat-block-specific. A rigid flow will break on complex monsters.

Applied to `init-tracker`:

- Multiattack is a guided sequence.
- Child attacks are tracked.
- Child attacks may target different creatures when legal.
- The app warns/assists; the DM remains authoritative.

### 6.8 Battle log should be gameplay-focused

The battle log should track D&D combat events, not technical diagnostics.

Applied to `init-tracker`:

- Combat log defaults visible.
- Combat log records attacks, saves, damage, healing, conditions, resources, turn changes, meaningful movement, and important state changes.
- Technical/debug events go to debug logs and optional Debug tab tools.

## 7. Repo inspection findings

### 7.1 LAN already contains much of the desired interaction model

The LAN player client already has concepts that match the desired DM surface:

- controlled actor concept
- weapon/action selection
- attack overlay mode
- range preview
- target click behavior
- attack resolve modal
- manual/app-assisted damage entry
- spell targeting
- multi-target spell selection UI
- movement range rendering
- movement remaining display

Relevant LAN anchors identified during repo inspection include:

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

Implementation implication: future DM actor-control work should inspect and adapt LAN concepts before touching the current DM dropdown stack.

### 7.2 LAN targeting and AoE selection should be the local model

LAN already supports a pattern close to the desired DM flow:

- select action or spell
- set pending targeting state
- show map overlay/range
- validate clicked target
- accumulate selected targets if multi-target
- resolve or confirm

Potential DM equivalents:

- `dmTargetMode`
- `pendingMonsterAction`
- `pendingMonsterTargetSelection`
- `focusedDmActorCid`

Do not copy LAN code blindly because LAN has player claim assumptions.

### 7.3 LAN movement already tracks remaining movement

LAN movement uses:

- active controlled unit
- movement range/cost map
- `move_remaining`
- drag movement command
- backend movement validation
- movement spending
- movement log/broadcast

The backend movement path `_lan_try_move()` is important because it validates blocking, cost, reachability, and remaining movement.

Implementation implication: future DM current-turn movement should reuse or expose the canonical LAN movement logic, not build on Monster Pilot as-is.

### 7.4 Monster Pilot is not the right movement foundation

Monster Pilot is dropdown/coordinate-driven. It can move tokens and has some drag/drop support, but it is not tied to the active initiative actor and does not appear to spend remaining movement through the canonical LAN movement path.

Implementation implication: freeze/deprecate Monster Pilot as a transitional fallback. Build future movement around current-turn actor movement and canonical movement validation.

### 7.5 Current DM frontend is dropdown-heavy and should be demoted

The current `/dm` page is built around many command selects:

- `monsterActorCidSelect`
- `monsterCapabilitySelect`
- `monsterPilotCidSelect`
- `mapCidSelect`
- `initCidSelect`
- `removeCidSelect`

Implementation implication: current `/dm` controls should be classified as keep backend, move to toolbox, move to Encounter Builder, hide/deprecate, or replace with the new current-actor surface.

### 7.6 Backend source of truth is not obviously split

Repo inspection did not show a true split between DM and LAN backend source of truth.

`CombatService` appears to be the intended state seam, and DM snapshots derive from tracker/combat state plus tactical projections.

Implementation implication: preserve backend authority. Do not introduce a second DM-only state model. Stale DM bugs should be treated as frontend state/DOM bugs unless endpoint evidence proves otherwise.

### 7.7 Monster spawn naming bug has a clear backend cause

Current add-monster behavior names single spawns without a suffix and only suffixes grouped spawns. Repeated single spawns therefore duplicate names.

Desired behavior: every spawned monster gets a stable numeric suffix, including repeated single spawns.

Implementation implication: fix in the backend spawn/encounter service boundary, not the frontend.

### 7.8 Enemy/NPC initiative defaulting to 0 has a clear backend cause

The current add-monster route defaults initiative to 0 unless a value is supplied.

Desired behavior: all enemies/NPCs auto-roll initiative individually when added.

Implementation implication: fix in the backend spawn path. Use the existing initiative rolling semantics after confirming modifier source.

### 7.9 Monster capability backend is useful

`MonsterCapabilityService` supports useful pieces:

- overlay loading
- slug/name matching
- executable actions
- save abilities
- area metadata
- target modes
- composite/multiattack children
- spellcasting summaries
- recharge/resource metadata
- effects/riders
- manual warnings

Implementation implication: keep backend idea. Rename/reposition frontend as Monster Actions inside the focused actor panel.

### 7.10 DM monster action endpoints can power the future actor panel

Existing backend endpoints/helpers can likely power the new UI:

- monster attack options
- monster capability execution
- target resolution
- resource/recharge operations
- effect apply/remove
- spell targeting

Implementation implication: the new actor panel should call these through cards/buttons and guided flows.

### 7.11 DM needs its own actor identity model

LAN has claim-based actor identity. DM needs a different model:

- current initiative actor = default control actor
- clicked token = inspection actor
- DM Toolbox override = temporary control actor

Potential state model:

- `dmCurrentActorCid`
- `dmInspectedActorCid`
- `dmOverrideActorCid`
- `dmControlMode`: initiative, inspect, or override

This should be designed/prototyped before implementation.

### 7.12 Browser asset syntax guard is mandatory

Recent `/dm` failures were browser parse errors, not backend bugs.

Any pass editing `assets/web/dm/index.html` or `assets/web/lan/index.html` must run the inline JavaScript syntax check before reporting success.

## 8. Final interaction model

### 8.1 Normal DM monster/NPC turn

The normal turn flow should support flexible D&D sequencing:

1. Initiative advances.
2. Current actor is automatically focused.
3. Actor panel shows stats, conditions, movement, resources, and actions.
4. Legal movement range appears.
5. DM may move before acting.
6. DM selects an action.
7. Action enters target mode.
8. Valid targets/range/area appear.
9. DM selects target or targets.
10. Resolution flow handles hit, save, damage, effects, riders, and resources.
11. DM may continue movement/action flow if valid.
12. DM ends turn.

Movement is not a single fixed phase. The UI must support move, attack, move, bonus action, move, end.

### 8.2 Focused actor panel

Purpose: a LAN-style actor sheet/control panel for the current initiative actor.

Default actor: current initiative actor.

Inspection override: clicking a token shows that token in inspector/focused view, without necessarily changing the control actor.

PC behavior: player characters are view-only by default unless DM Toolbox override is enabled.

Suggested visible data:

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

### 8.3 Action cards

Collapsed action cards show mechanics summary:

- name
- attack bonus or save DC
- damage
- damage type
- range/reach/area
- recharge/resource marker
- key rider summary

Expanded action cards show full description/rules text.

Unsupported/manual actions are collapsed by default and clearly labeled Manual / Assisted.

Candidate groups:

- Actions
- Bonus Actions
- Reactions
- Legendary Actions
- Spellcasting
- Traits / Passive Rules
- Manual / Unsupported

Action grouping defaults still need a prototype against complex monster data.

### 8.4 Targeting and resolution

Selecting an attack/action enters target mode.

Escape cancels target mode without consuming resources.

Valid targets should be highlighted.

AoE and multi-target selections should display selected targets before resolution.

The system must support both app rolls and physical dice/manual entry.

Automation settings should eventually support per-roll or per-roll-type toggles:

- attack rolls
- damage rolls
- saving throws
- initiative
- recharge rolls

Damage can be automatic after result, with review/confirmation for AoE/mass effects where appropriate.

### 8.5 Multiattack

Preferred flow: guided assisted sequence.

Example: Multiattack starts a sequence such as Bite, Claw, Claw.

Requirements:

- track child attack usage
- allow different targets when legal
- support same-target or choose-target-per-child options
- assist without over-enforcing
- DM remains authoritative

### 8.6 Movement

Movement range should appear automatically at the start of every monster/NPC turn.

Movement range should remain visible because movement can be split.

Remaining movement should be tracked.

Invalid movement should:

- reject
- snap token back to original square
- show non-intrusive warning
- not consume movement

Diagonal movement remains open. Do not change diagonal behavior until repo behavior and table rule are confirmed.

### 8.7 Force / override movement

Force/override is not normal movement.

Initial model:

- belongs in DM Toolbox
- requires confirmation
- can eventually allow out-of-turn movement, moving any token, or force movement
- should log visibly when used

Future expansion may include objects/crates/physics-like interactions, but do not overbuild this now.

### 8.8 Tactical map

Default display: current initiative actor.

Left-click token: inspect/focus that token.

Left-click empty cell: show detailed cell information.

Drag current-turn token: current actor movement interaction.

Right-click token: possible future contextual actions.

Right-click empty cell: map tools only in explicit map-edit mode.

Map editing should be a separate mode/tool, not bolted onto combat controls.

### 8.9 DM Toolbox

One modal with tabs is acceptable.

Accessible from cockpit and map contexts.

All actions require confirmation.

Candidate tabs:

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

### 8.10 Encounter Builder / Monster Library

Desired behavior:

- search
- browse
- visible name, CR, AC, HP, type
- spawn count
- auto-numbering
- mixed monster groups later
- HP randomization later

Not required by default in result rows:

- source
- action-card availability

Current Add Combatant should move to Advanced/Debug for now.

### 8.11 Initiative

Confirmed rule:

- all enemies/NPCs auto-roll initiative individually when added
- PCs use LAN initiative prompts when appropriate
- no shared initiative by default unless a specific summon/feature says so
- reroll all enemy/NPC initiative button belongs in DM Toolbox

### 8.12 Battle log

The battle log should default visible and remain toggleable.

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

Technical/debug logs should stay out of the D&D combat log and be available through debug files/tools.

### 8.13 Screen assumptions

DM is desktop-monitor only.

No DM touch/tablet support is needed.

The map should remain large enough to be useful at all times.

Avoid scrolling in active controls; use collapsible groups/cards.

## 9. Accessibility and implementation requirements

### 9.1 Modal accessibility

DM Toolbox should use accessible modal behavior:

- dialog semantics
- focus moved into modal
- focus returned to trigger on close
- Escape close where appropriate
- keyboard-accessible tab/buttons
- background effectively inert while modal is active

### 9.2 Accordion/disclosure accessibility

Collapsible groups should be implemented with accessible button semantics and clear state.

### 9.3 Browser asset validation

Any pass editing `assets/web/dm/index.html` or `assets/web/lan/index.html` must run the inline JavaScript syntax check.

The end-of-pass report must include the exact syntax-check command and result.

Do not claim browser readiness if the syntax check was skipped, unavailable, or failed.

### 9.4 Runtime evidence for bugs

For bug/performance issues:

- capture logs/payloads/browser errors first
- do not guess from code alone
- use the webdev debug capture when `/dm` appears broken
- separate confirmed evidence from hypothesis

## 10. Milestone roadmap

### Milestone 0 — Stabilize before redesign

Goal: ensure `/dm` and `/` are not actively broken before UI replacement begins.

Scope:

- `/dm` renders.
- `/` renders.
- New Blank Session clears both DM and LAN.
- JS syntax guard exists and is mandatory.
- Backend source of truth is not split.
- App survives short manual combat smoke.

Acceptance criteria:

- `/dm` opens without browser parse errors.
- `/` opens and claim flow works.
- New Blank Session clears initiative, combatants, map units, transient panels, and LAN clients.
- No feature work proceeds if `/dm` parse/bootstrap is broken.

### Milestone 1 — Low-risk correctness cleanup

Goal: fix concrete behavior issues useful regardless of final UI.

Tasks:

1. Auto-number duplicate monster spawns.
2. Auto-roll enemy/NPC initiative individually when added.
3. Rename Normalized Capabilities to Monster Actions.
4. Improve no-match message.
5. Move Add Combatant to Advanced/Debug later.

Acceptance criteria:

- every spawned monster has unambiguous numbering
- enemies/NPCs do not default to initiative 0
- player initiative prompt behavior is preserved
- implementation jargon no longer appears in active UI

### Milestone 2 — DM Toolbox shell

Goal: create the tabbed modal home for rare/power controls.

Scope:

- create modal shell and tabs
- Session, Encounter, Overrides, Map Tools, Debug
- confirmation wrappers for toolbox actions
- begin moving rare controls out of main combat surface

Acceptance criteria:

- toolbox accessible from cockpit and map
- toolbox actions are confirmation-gated
- rare controls have a home
- debug/status tools have a home

### Milestone 3 — Encounter Builder / Monster Library

Goal: replace Add Monster Specs and shallow Add Combatant with usable encounter setup.

Scope:

- search
- browse
- monster summary
- spawn count
- auto-numbering
- mixed groups later
- HP randomization later

Acceptance criteria:

- DM can find monsters quickly
- repeated spawns are named clearly
- shallow Add Combatant is no longer primary workflow

### Milestone 4 — Initiative flow

Goal: make initiative match confirmed table rules.

Scope:

- enemies/NPCs auto-roll individually when added
- PCs use LAN prompt when appropriate
- reroll all enemy/NPC initiative in DM Toolbox

Acceptance criteria:

- enemy/NPC initiative is rolled when added
- PCs retain LAN prompt behavior
- manual override remains possible

### Milestone 5 — Focused actor panel prototype

Goal: prototype the LAN-style current actor panel.

Scope:

- current initiative actor as default
- PC view-only inspection
- token-click inspection override
- complex stat block support
- collapsible groups/cards
- no dropdown primary flow

Acceptance criteria:

- panel can display a complex monster cleanly
- actions are visible as cards/buttons
- current actor is obvious
- clicked actor inspection does not confuse control actor

### Milestone 6 — Monster Actions / action cards

Goal: replace confusing normalized capability presentation with actor-centered Monster Actions.

Scope:

- collapsed mechanics summary
- expanded full text
- guided targeting
- multiattack sequence
- manual/unsupported cards
- action grouping after prototype/research

Acceptance criteria:

- “Normalized Capabilities” label removed
- no-match message is clear
- overlay-backed monsters show useful action cards
- manual fallback is understandable

### Milestone 7 — Movement model

Goal: replace Monster Pilot with current-turn movement.

Scope:

- automatic movement range
- remaining movement tracking
- drag current actor token
- invalid movement snapback
- DM Toolbox override/force movement later
- reuse canonical LAN movement path where possible

Acceptance criteria:

- movement does not require selecting monster from dropdown
- current actor movement is obvious
- remaining movement updates
- invalid movement does not spend movement

### Milestone 8 — Tactical map inspection

Goal: make the map useful as reference/inspector.

Scope:

- current actor default inspection
- token click inspection
- empty cell info
- map controls separated into Map Tools / Map Editor

Acceptance criteria:

- map remains useful at all times
- clicking token/cell produces useful info
- advanced map controls do not dominate cockpit

### Milestone 9 — Automation settings

Goal: support app rolls and physical dice/manual entry cleanly.

Scope:

- identify roll types
- decide persistence model
- design per-roll or per-roll-type toggles
- integrate with attack/save/damage/recharge/initiative flows

Acceptance criteria:

- DM can choose app/manual rolling mode
- both modes are supported intentionally, not as accidental fallback

### Milestone 10 — Battle log refinement

Goal: make battle log a detailed D&D combat timeline.

Scope:

- gameplay-only event logging
- filter/hide technical logs
- visible by default
- toggle/collapse retained
- possible filters later

Acceptance criteria:

- combat can be reconstructed from log
- technical messages do not pollute gameplay log

### Milestone 11 — Map tools and eventual map editor

Goal: separate map setup/editing from combat operation.

Scope:

- move current advanced map dropdown stack into Map Tools
- design separate map editing mode later
- avoid bolting map editing onto combat controls

Acceptance criteria:

- combat cockpit is not cluttered by map editing tools
- map editor is explicitly separate when built

## 11. Immediate implementation sequence

Start with safe cleanup before major UI replacement:

1. Auto-number duplicate monster spawns.
2. Auto-roll enemy/NPC initiative individually when added.
3. Rename Normalized Capabilities to Monster Actions.
4. Improve no-match message.
5. Create DM Toolbox shell.
6. Move rare controls into DM Toolbox.
7. Create focused actor panel prototype.
8. Add Monster Actions into focused actor panel.
9. Build current-turn movement model.
10. Demote/remove old Monster Turn Controls and Monster Pilot after replacement is usable.

## 12. Deferred or unresolved decisions

### 12.1 Exact action grouping defaults

Need prototype against the largest/most complex local monster data.

### 12.2 Diagonal movement mode

Need repo/table decision before changing movement behavior.

Possible modes:

- current repo behavior
- simple 5-foot diagonals
- alternating 5/10 diagonals
- configurable setting

### 12.3 Target tray behavior

Need repo pass against LAN spell target selection UI.

### 12.4 Automation settings shape

Need repo pass to identify roll paths, persistence location, and setting scope.

### 12.5 Combat log display design

Need later UI decision:

- docked panel
- collapsible drawer
- filter chips
- event grouping
- player-visible vs DM-only details

### 12.6 HP randomization

Desired later. Should use monster hit dice formula when available. Do not add until spawn/initiative and Encounter Builder model are stable.

## 13. Agent guardrails

Future agent prompts should include the relevant subset of these guardrails:

- Do not treat current Monster Turn Controls or Monster Pilot as the target UI.
- Do not build new active-combat workflows from dropdown stacks.
- Use LAN player flow as the local interaction reference.
- Inspect exact named functions before editing large browser assets.
- Avoid broad wandering in `assets/web/lan/index.html`.
- Avoid broad wandering in `assets/web/dm/index.html` unless the task is explicitly discovery.
- Run browser asset JS syntax checks if editing DM/LAN HTML.
- Preserve backend source-of-truth.
- Do not introduce DM-only parallel state.
- Separate confirmed findings from hypotheses.
- Use measured runtime evidence for bug/perf fixes.
- Do not claim browser readiness without syntax check and/or browser smoke where required.

## 14. Validation expectations by task type

### Browser asset task

Required:

- JS syntax check for edited DM/LAN HTML.
- Focused asset tests.
- Relevant browser smoke if behavior changes are user-visible.

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

## 15. Final acceptance vision

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
12. Combat log records the important events.
13. The DM ends turn.

The old Monster Turn Controls and Monster Pilot should no longer be the primary way to run combat.

## 16. Recommended repo placement

Save this file as:

- `docs/dm-control-surface-master-plan.md`

Optional later split-outs:

- `docs/dm-control-surface-repo-inspection.md`
- `docs/dm-control-surface-workshop.md`
- `docs/dm-control-surface-implementation-tasks.md`

For now, this master plan can stand alone.
