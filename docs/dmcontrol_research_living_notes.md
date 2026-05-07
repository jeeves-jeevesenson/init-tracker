# DM Control Surface Research Living Notes

Purpose: capture the research pass for the future `/dmcontrol` design without letting details get lost or accidentally folded into the wrong page.

This file is **research/session notes**, not the final implementation spec. The final living repo plan should be updated only after repo inspection and online research are complete.

---

## Current architectural correction

### Page split

`/dm` is the DM cockpit, prep, overview, actor sheet, initiative, toolbox, reference map, admin override, and debug page.

`/dmcontrol` is a separate active play surface for controlling the current monster/NPC/enemy. It should feel much closer to the LAN client than to the DM cockpit.

### Critical rule

Do **not** move `/dm` UI into `/dmcontrol`.

Build `/dmcontrol` from LAN-index interaction patterns, adapted for DM-controlled monsters/NPCs.

### Current intended flow

```text
Initiative advances to monster/NPC/enemy
→ /dm automatically shows that actor’s sheet/reference info
→ /dmcontrol controls that actor’s active turn
→ DM chooses attack/spell/action from LAN-style controls
→ DM targets using /dmcontrol’s active map/range/AoE preview
→ DM resolves using modal flow
→ Multiattack uses guided child-step modal/flow
→ DM can move by drag/drop at any point during the turn using remaining movement
→ DM ends turn
```

### Important distinction about maps

`/dm` tactical map:
- reference
- inspection
- visual context
- not the active combat-control surface

`/dmcontrol` map:
- active LAN-like control surface
- movement
- attack targeting
- AoE/template placement
- range/reach previews
- selected/affected target preview

---

## Repo inspection anchors already found

Source: uploaded repo zip inspected directly during this research session.

### LAN page shape

`assets/web/lan/index.html` is the best implementation reference for `/dmcontrol`.

Known anchors from repo inspection:

```text
Topbar:
  assets/web/lan/index.html around 2574-2623

Main map surface:
  assets/web/lan/index.html around 2639-2668

Bottom player control sheet:
  assets/web/lan/index.html around 3301-3365
```

The LAN page is already structured as:

```text
map-first active play surface
+ sticky/resizable bottom control sheet
+ attack/spell/AoE targeting on the map
+ modal resolution flow
+ disabled/non-turn state
```

### LAN non-turn / disabled behavior

Relevant anchors:

```text
activeControlledUnitCid()
  assets/web/lan/index.html around 13522

updateResourceGatedControls()
  assets/web/lan/index.html around 13655

updateHud()
  assets/web/lan/index.html around 15940
```

This likely maps to `/dmcontrol` behavior when the active initiative actor is a PC or no DM-controlled actor is active.

### LAN movement

Relevant anchors:

```text
getMovementRangeCostMap()
  assets/web/lan/index.html around 10879

movementCostMap()
  assets/web/lan/index.html around 14094

draw() movement range overlay
  assets/web/lan/index.html around 14529

canvas pointerdown/pointerup movement flow
  assets/web/lan/index.html around 18525 and 18877

_lan_try_move()
  dnd_initative_tracker.py around 43514
```

Desired `/dmcontrol` movement behavior:
- movement range appears automatically
- movement remaining stays visible
- drag/drop token movement
- movement can be split around actions
- invalid movement rejects/snaps back
- backend validates movement

### LAN normal attack flow

Relevant anchors:

```text
setAttackOverlayMode()
  assets/web/lan/index.html around 12395

attack/range overlay drawing
  assets/web/lan/index.html around 14574

attack target click flow
  assets/web/lan/index.html around 19003-19131

openAttackResolveModal()
  assets/web/lan/index.html around 12757

attackResolveModal HTML
  assets/web/lan/index.html around 2730
```

Desired `/dmcontrol` normal attack flow:
```text
click attack
→ range preview appears
→ click valid target token
→ resolution modal opens
```

### LAN spell / AoE targeting

Relevant anchors:

```text
AoE target preview panel:
  assets/web/lan/index.html around 2643

spell target selection UI:
  assets/web/lan/index.html around 2655

runSpellTargetingAgainstTarget()
  assets/web/lan/index.html around 16326

renderSpellTargetSelectionUi()
  assets/web/lan/index.html around 22732

startSpellTargetingSession()
  assets/web/lan/index.html around 22794
```

Possible `/dmcontrol` direction:
- monster spellcasting may become Monster Action cards rather than a full spell search panel
- spellcaster monsters usually have fewer spells
- need online research before final grouping decision

### `/dmcontrol` route status

No `/dmcontrol` route/page currently exists.

Current known routes:

```text
/           serves LAN index
/planning   serves LAN index
/dm         serves DM console
/dm/map     serves DM map workspace
```

Likely future route:

```text
GET /dmcontrol
assets/web/dmcontrol/index.html
```

---

## Current `/dm` bugs / cleanup confirmed from repo inspection

These are cleanup tasks before or alongside `/dmcontrol` planning.

### Monster Library duplicates

Root likely in:

```text
renderMonsterLibrary(monsters, filter = '')
  assets/web/dm/index.html around 2648
```

Current Monster Library appears to render from raw `encounterOptions.monsters` without dedupe.

Likely fix:
- dedupe by `slug` first
- fallback to normalized name if slug missing
- preserve sorting/search

### Repeated single-spawn numbering regression

Root likely in the DM monster add route:

```text
/api/dm/encounter/monsters/add
  dnd_initative_tracker.py around 4298-4368
```

Problem pattern:

```text
name = name_prefix if count == 1 else f"{name_prefix} {index + 1}"
```

This means adding the same monster one at a time can repeat the unsuffixed name.

`CombatantNameService` exists:

```text
combatant_name_service.py
```

But route integration appears incomplete/bypassed.

Expected repeated one-at-a-time behavior:

```text
Black and Tan Rifleman 1
Black and Tan Rifleman 2
Black and Tan Rifleman 3
```

### DM Toolbox cramped

Current approximate modal sizing:

```text
width: min(900px, 94vw)
height: min(720px, 88vh)
```

Likely target:

```text
width: min(96vw, 1400px)
height: min(92vh, 950px)
resize: both
```

or similar desktop-friendly sizing.

### Legacy Monster Turn Controls / Monster Pilot still in `/dm`

Confirmed in `/dm` around:

```text
Monster Turn Controls
  assets/web/dm/index.html around 1287-1363

Monster Pilot
  assets/web/dm/index.html around 1366+
```

These should be removed/demoted from the main `/dm` active cockpit area. If preserved, move to Debug/Legacy/Fallback, not primary controls.

---

# Online research progress

## Pass 1 — VTT GM control surfaces

Status: initial pass completed.

Goal:
```text
How do mature VTTs let a GM run monsters/NPCs?
Where do actions live?
Where does targeting happen?
How do they separate map, sheet, tracker, and controls?
What lessons apply to /dm vs /dmcontrol?
```

### Foundry VTT

Observed model:
- Actor/document state is distinct from token/map representation.
- Combat Tracker handles turn order and current actor.
- Tokens support map-native targeting.
- Measured templates support spell/AoE areas.

Design takeaways:
- Keep `/dm` as tracker/reference/cockpit.
- Let `/dmcontrol` be the active token/action/map interaction page.
- Map targeting is appropriate on an active play surface like `/dmcontrol`.
- AoE/templates should be previewed visually.
- Full actor sheet/reference does not need to be crammed into the active control page.

### Roll20

Observed model:
- Turn Tracker is token/tabletop-driven.
- Macros/token actions act as quick controls for repeated actions.
- Token actions can apply to PCs and NPCs.

Design takeaways:
- `/dmcontrol` should prioritize quick repeated combat actions.
- Current actor/token state should drive visible action controls.
- Full stat sheet does not need to be the primary action surface.
- `/dm` should keep tracker/reference responsibility.

### Fantasy Grounds

Observed model:
- Combat Tracker is powerful and GM-focused.
- NPC traits/actions can be parsed into combat-relevant effects.
- NPCs become combat-ready when placed on tracker.

Design takeaways:
- Monster/NPC actions should become combat-ready controls when possible.
- Assisted/manual flows are acceptable for complex mechanics.
- Avoid one giant overloaded GM page; split `/dm` and `/dmcontrol`.

### D&D Beyond Maps

Observed model:
- Lightweight map/encounter/initiative manager.
- Supports tokens, encounter setup, initiative, rounds/turns, and auto initiative options.

Design takeaways:
- `/dm` should make setup/initiative easy.
- `/dmcontrol` needs deeper active action execution than D&D Beyond Maps alone appears to offer.
- Auto initiative for enemies/NPCs is consistent with modern VTT workflows.

### Owlbear Rodeo and extensions

Observed model:
- Core Owlbear is lightweight map/scenes/tokens/drawings/fog.
- Combat-oriented extensions add initiative, ranges, health tracking, stat blocks, effects, and distance.

Design takeaways:
- Keep base/cockpit/reference concerns separate from active combat manager concerns.
- `/dmcontrol` can be the active combat manager/control surface.
- Range overlays and distance calculations belong on `/dmcontrol`, not as primary `/dm` behavior.

### Cross-VTT conclusions

```text
/dmcontrol should be LAN-like, not /dm-like.
Current /dm Focused Actor work is reusable logic, not final layout.
Map-click targeting is correct on /dmcontrol, wrong as the primary /dm workflow.
Monster action controls should be compact and immediately usable.
Automation should assist, not trap the DM.
```

Reusable from `/dm` prototype:
- Monster Action card ideas
- selected/expanded action state
- target tray concept
- resolution tray endpoint reuse
- sequence tray concept
- error/in-flight handling

Not final as-is:
- `/dm` placement
- `/dm` map-click target workflow
- Focused Actor Panel as final `/dmcontrol` layout

---

# Remaining online research checklist

The following sections should be filled in subsequent research passes.

## Pass 2 — LAN-like player control UI patterns

Status: completed.

Research target:
```text
map-first active control surfaces
bottom control bars
disabled/non-turn state
action buttons near map
modal resolution patterns
```

Questions:
```text
What makes a map-first combat UI feel fast?
Where should action buttons live relative to the map?
How do games/VTTs show selected actor, movement remaining, actions, and targets without clutter?
How do they keep non-current actors disabled/read-only?
```

### Sources consulted

- Nielsen Norman Group — "10 Usability Heuristics Applied to Video Games"
- Feral Interactive — XCOM 2 manual
- Game Developer — "A Deep Dive Into XCOM and XCOM 2"
- bg3.wiki — Actions
- Throw the Project — Tactical-RPG Move Range
- GameDev.net forum thread — Turn Based Action Selection and UI design
- Justinmind — Game UI design guide
- Repo inspection from `assets/web/lan/index.html`

### Findings

#### 1. `/dmcontrol` should be map-first, but not map-only

LAN-like active combat pages work best when the main tactical surface is always visible and action controls sit near it, rather than forcing the user to switch into a separate sheet/admin view. The repo’s LAN client already follows this pattern: the map is the base surface and the control sheet/bottom bar sits over or below it.

External UI research supports this. General game UI guidance frames the UI as the player’s control panel, with HUDs showing vital stats and abilities without blocking the action. The useful lesson is not "make everything minimal"; it is "keep active controls close to the gameplay surface and avoid forcing the user through deep menus during play."

Implication:
```text
/dmcontrol should start from the LAN page structure:
map surface + bottom/control bar + modal resolution overlays.
```

#### 2. Bottom/control bar is the right baseline for `/dmcontrol`

The LAN page’s bottom control sheet is probably the strongest repo-native pattern to adapt. It already shows player identity, HP/action state, movement/action/reaction/turn controls, attacks, spells, and resources. That is much closer to the desired monster/NPC play surface than the current `/dm` right-side controls.

For `/dmcontrol`, the bottom bar should be adapted rather than copied blindly:
```text
current monster/NPC identity
HP/status summary
movement remaining
action buttons/cards
spell/action groups if applicable
turn controls
target/resolution status
```

The full actor/stat sheet should stay on `/dm`; `/dmcontrol` only needs enough state to make a turn playable.

#### 3. Movement range should be immediate and visual

XCOM 2 is a useful benchmark because the selected unit gets immediate visual movement feedback: the manual describes two action points and blue/yellow movement outlines indicating one-action movement vs dash movement. That reinforces the repo/LAN pattern of showing movement range directly on the map rather than hiding movement information in text.

For `/dmcontrol`, movement should be:
```text
automatic on monster/NPC turn start
visible on the map
remaining movement visible in the control bar
drag/drop driven
validated by backend
invalid movement snaps/rejects without spending movement
split movement supported
```

The exact D&D movement semantics should come from the existing LAN movement code first, not from a newly invented system.

#### 4. Action order must support D&D-style flexibility

Game Developer’s XCOM analysis notes that movement, attacks, weapon use, and special abilities can occur in different orders in XCOM-style tactical play. That is not D&D, but it lines up with the user requirement that monster turns may be action → move → action → move when legal.

Implication:
```text
/dmcontrol must not force a single rigid turn script.
```

It should let the DM move before, between, or after actions, while showing remaining movement and action/bonus/reaction state where the system can track it.

#### 5. Actions should be quick controls, not a full sheet

Baldur’s Gate 3’s action model is a useful comparison because actions are the acts creatures take on their turns to deal damage, inflict conditions, heal, or aid allies. This supports exposing monster/NPC actions as direct controls in the active play surface. The user should not need to open a full actor sheet to make a basic attack.

For `/dmcontrol`, action controls should be:
```text
visible in the LAN-like control bar/sheet
grouped enough to avoid clutter
fast to activate
rich enough to show range/damage/save/recharge basics
able to open modals for resolution
```

#### 6. Targeting can be action-first, target-first, or hybrid

The GameDev.net discussion is useful because it points out that target-first selection can filter invalid actions and reduce hover/checking work, especially when there are fewer targets than actions. For D&D, though, action-first is often natural because the DM chooses "Bite," "Fire Breath," or "Hold Person" first, then the target rules become clear.

Recommended `/dmcontrol` model:
```text
Primary flow:
choose action → show legal/advisory target preview → click target(s) on map → resolution modal

Optional assist:
target list / cycle target / panel picker for crowded maps or accessibility

Future improvement:
target-first shortcuts may filter action cards, but this should not be the first implementation model.
```

#### 7. Range/validity overlays should inform without overwhelming

Tactical RPG movement/range algorithms often start from the selected unit and calculate selectable tiles, entities in area, and best targets within a range. This validates our map overlay direction for `/dmcontrol`: show range, reach, AoE, and selected/affected targets directly on the map.

But research and player feedback on tactical games also warns that range overlays can become visually dense. The lesson for `/dmcontrol`:
```text
show only the active actor/action overlay by default
keep colors/labels consistent
avoid always-on overlays for everything
make Escape/cancel clear visual modes
```

#### 8. Disabled/non-turn state should look like LAN, not like an error

When initiative is on a PC, `/dmcontrol` should behave like a player client when it is not that player’s turn: visible but mostly disabled/idle. This should not look broken. It should show a calm state such as:
```text
Current turn: Player Character
No DM-controlled actor active.
Controls disabled.
Override available from DM controls.
```

If override is added, it should be explicit and visually distinct.

#### 9. Resolution should stay modal

LAN already uses modal resolution for attack flow. That should remain the baseline. The resolution modal is where deliberate confirmation belongs:
```text
hit/miss/crit or save result
damage entry or auto-roll if blank/formula available
rider/effect preview when supported
Apply / Cancel
```

A modal is appropriate here because applying results mutates combat state. The control bar/map should set up the action; the modal should confirm and apply it.

#### 10. Avoid broad-sheet creep

A key risk is accidentally rebuilding `/dm` inside `/dmcontrol`. The research supports a smaller active-play surface:
```text
/dmcontrol should show the minimum state needed to take the current turn.
Detailed stat/reference views belong on /dm.
```

### Implications for `/dmcontrol`

Concrete design rules to carry forward:

```text
1. Build from `assets/web/lan/index.html`, not from `assets/web/dm/index.html`.
2. Main surface is the tactical map.
3. Bottom/control bar is the main action area.
4. Full actor sheet stays on /dm.
5. Current monster/NPC is controlled by default.
6. PC turns show idle/disabled state, not a broken page.
7. DM override exists but is not default.
8. Movement range appears automatically.
9. Drag/drop movement is allowed during the monster/NPC turn.
10. Remaining movement must remain visible.
11. Normal attacks should match LAN flow closely.
12. Spell/AoE actions should use LAN-style target preview/template placement.
13. Resolution is modal and state-mutating only after confirmation.
14. Multiattack should become a guided modal/sequence flow.
15. Active overlays should be contextual, not all-on.
16. Escape cancels active modes.
```

### Open questions for later spec

```text
- Should the `/dmcontrol` bottom bar be one row like LAN, or a larger desktop-only drawer?
- Should monster action cards be grouped by action economy or by stat block section?
- Should target list/picker be always visible or only available as a fallback for crowded maps?
- Should DM override live on `/dmcontrol`, `/dm`, or both?
- Should `/dmcontrol` show small actor HP/conditions, or rely on `/dm` for all details?
```

## Pass 3 — D&D 2024 monster action structure

Status: completed.

Research target:
```text
How current D&D monsters are structured in 2024/2025 rules/content.
```

Questions:
```text
How common are Multiattack, Recharge, Bonus Actions, Reactions, Legendary Actions?
How are spellcasting monsters presented now?
Are monster spell lists still common, or are spells increasingly rewritten as actions?
How should action cards be grouped for modern monsters?
```

### Sources consulted

Official / rules-facing sources:
- D&D Beyond Basic Rules 2024 — "How to Use a Monster"
- D&D Beyond — "Preview the New Stat Block Design in the 2024 Monster Manual"
- D&D Beyond — "Updates in the Monster Manual (2025)"
- Roll20 D&D 2024 Compendium — "Parts of a Stat Block"

Supplemental / context sources:
- AlphaStream review of revised Monster Manual
- Arcane Eye overview of 2025 spellcasting monsters
- D&D Beyond forum/community discussion snippets treated as low-authority context only, not as design authority

### Findings

#### 1. The modern monster stat block is explicitly action-oriented

The 2024/2025 monster structure is organized around the information needed to run the creature at the table:
- traits
- actions
- bonus actions
- reactions
- legendary actions
- limited-use/recharge features
- spellcasting entries when relevant

The rules-facing "How to Use a Monster" material defines the main action section as the place where a monster’s specific actions live. It also breaks down attack notation, saving throw notation, damage notation, Multiattack, Spellcasting, Bonus Actions, Reactions, Legendary Actions, and Limited Usage.

Design implication:
```text
/dmcontrol action UI should be organized from the stat block’s combat-use sections, not from a generic character-sheet model.
```

#### 2. Attack entries contain enough structure to become action cards

The 2024 stat-block guidance says monster attack entries identify:
- melee or ranged attack
- attack roll bonus
- reach or range
- what happens on hit
- miss effects if any
- hit-or-miss effects if any

That maps directly to action-card fields:
```text
Action name
Melee/Ranged
Attack bonus
Reach/Range
Hit damage/effects
Miss/Hit-or-Miss text when present
```

Design implication:
```text
Basic monster attacks should be first-class /dmcontrol action buttons/cards.
```

For normal attacks, `/dmcontrol` should use LAN-style:
```text
click attack
→ show range/reach preview
→ click target
→ resolution modal
```

#### 3. Saving throw effects also map cleanly to cards and AoE workflows

The rules-facing guidance says saving throw effects identify:
- save type/ability
- DC
- which creatures make the save
- failure result
- success result

That maps directly to:
```text
Save DC
Save ability
Target description
Failure effect
Success effect
Half damage note
AoE shape/range when present
```

Design implication:
```text
AoE/spell/breath-style actions need a different resolution mode than attack rolls:
template/target preview → affected target list → per-target save outcome → apply.
```

#### 4. Damage notation supports both average damage and dice formulas

The 2024 stat-block guidance says a stat block usually gives both a number and a die expression, and the DM chooses whether to use the number or the die expression.

Design implication:
```text
/dmcontrol resolution modals should support both:
- quick average damage
- roll formula / auto-roll when blank, following LAN behavior
```

This aligns with the existing LAN behavior where leaving damage blank can auto-roll when formula data exists.

#### 5. Multiattack remains a central monster-action pattern

The rules-facing guidance says some creatures can make more than one attack when they take the Attack action, and the Multiattack entry details those attacks and any additional abilities that are part of the Attack action.

Design implication:
```text
Multiattack should not be treated as one opaque attack button.
```

The right `/dmcontrol` model is a guided sequence:
```text
Multiattack
→ child steps such as Bite 0/1, Claw 0/2
→ resolve each child through normal attack flow
→ allow different targets when legal
→ DM ends sequence manually
```

This reinforces the existing Sequence Tray concept as useful, but the final UX should probably be more LAN-like/modal than the current `/dm` prototype.

#### 6. Limited-use and recharge actions must be visible

The rules-facing guidance covers:
- X/Day
- Recharge X-Y
- Recharge after rest

It also advises that limited high-damage abilities, such as recharging breath weapons or once-per-day spells, should be used quickly and often if the monster is to act according to its Challenge Rating.

Design implication:
```text
/dmcontrol must surface limited-use/recharge actions prominently.
```

Potential UI:
```text
Fire Breath — Recharge 5-6 — ready/not ready
1/Day action — remaining uses
Recharge roll button or automatic start-of-turn check later
```

For initial `/dmcontrol`, show the state and allow assisted/manual tracking before deep automation.

#### 7. Bonus Actions, Reactions, and Legendary Actions are not optional afterthoughts

The stat block rules explicitly list Bonus Actions, Reactions, and Legendary Actions as their own sections. The "running a monster" guidance says if monsters have Bonus Actions, Reactions, or Legendary Actions, the DM should use them as often as possible.

Design implication:
```text
/dmcontrol should not only show Actions.
```

Recommended grouping:
```text
Main Actions
Bonus Actions
Reactions
Legendary Actions
Traits / Passive
Manual / Assisted
```

However, the default current-turn view should not become cluttered. Reactions and Legendary Actions may need separate compact drawers/tabs because they often happen outside the monster’s own turn.

#### 8. Legendary Actions in 2025 are still present and have their own use economy

D&D Beyond’s preview describes updated Legendary Actions as more varied, including repositioning and spellcasting options, and says each Legendary Action now counts as one use rather than having different action costs. Expended uses still return at the start of the monster’s turn. Lair context can add additional Legendary Action uses.

Design implication:
```text
/dmcontrol eventually needs a between-turn / legendary mode, but it should not be part of the first normal monster-turn slice.
```

A later design may need:
```text
Legendary Action prompt after other creatures’ turns
remaining legendary uses
lair bonus state
clear “this is not the monster’s normal turn” UI
```

#### 9. Spellcasting monsters are presented for combat usability, but spellcasting still needs special handling

The 2024 guidance says a monster’s stat block lists spells, spellcasting ability, spell save DC, and spell attack bonus when relevant. D&D Beyond’s preview says spellcasting monsters may have spells inside the Spellcasting action, or specially highlighted as Bonus Actions or Reactions.

This does not fully answer whether `/dmcontrol` should use a dedicated spell panel or generic Monster Action cards. That belongs in Pass 4.

Tentative implication:
```text
Spells should probably appear as action cards grouped under Spellcasting / Magical Actions, not as a massive searchable player-style spellbook.
```

Monster spellcasters usually need fast combat options, not the full player spell-prep workflow.

#### 10. 2025 Monster Manual revisions emphasize usability and table utility

D&D Beyond says the 2025 Monster Manual includes 87 new stat blocks and that carried-forward 2014 stat blocks were revised with a focus on fun and usability. The D&D Beyond preview also says the new stat blocks were designed to make encounter-running information easier to find in the heat of battle, and that consolidated actions reduce clutter.

Design implication:
```text
/dmcontrol should follow the same philosophy:
surface the immediate combat action data, hide/defer long reference text, and avoid forcing the DM to parse YAML/stat text during a turn.
```

### Recommended `/dmcontrol` action grouping

Initial grouping should reflect the stat block, but stay compact:

```text
Main Actions
  - basic attacks
  - Multiattack
  - breath weapons / recharge attacks
  - major save effects
  - Spellcasting action if present

Bonus Actions
  - bonus action attacks/spells/movement/effects

Reactions
  - listed with triggers
  - likely disabled/secondary during normal turn unless override/trigger mode exists

Legendary Actions
  - separate later mode for between-turn use
  - do not cram into normal current-turn flow initially

Traits / Passive
  - compact passive/always-on notes
  - not primary buttons unless the trait has an active trigger

Manual / Assisted
  - complex actions not yet automated
  - reminders or assisted resolution cards
```

### Suggested first-slice priorities for `/dmcontrol`

Do first:
```text
1. Normal attack action card
2. Attack range/reach preview
3. Target click on /dmcontrol map
4. Attack resolution modal
5. Average-or-roll damage behavior
6. Multiattack sequence shell for child attacks
```

Do after:
```text
1. Save/AoE action resolution
2. Recharge / limited-use automation
3. Bonus action handling
4. Reaction handling
5. Legendary action mode
6. Monster spellcasting polish
```

### Implications for `/dmcontrol`

Concrete design rules to carry forward:

```text
1. /dmcontrol action cards should follow monster stat block combat sections.
2. Normal attacks need first-class support.
3. Saving throw/AoE effects need their own target + save resolution model.
4. Damage modal should support both average and rolled formula.
5. Multiattack should be guided child-step workflow, not opaque one-click.
6. Recharge and X/Day actions must be visible even if automation is deferred.
7. Bonus Actions/Reactions/Legendary Actions need dedicated grouping.
8. Reactions and Legendary Actions probably need later modes because they are not normal-turn actions.
9. Monster spellcasting should be fast and combat-use oriented, not a full player spellbook clone.
10. Long descriptions should be collapsible or kept on /dm, while /dmcontrol shows combat-critical mechanics.
```

### Open questions for later spec

```text
- Should Legendary Actions be on /dmcontrol from the start or deferred until normal turn flow is stable?
- Should Reactions be shown on /dmcontrol when it is not the monster’s turn?
- How should recharge rolls happen: automatic at turn start, manual button, or both?
- Should X/Day uses be tracked in backend or initially advisory/manual?
- Should Spellcasting be grouped under Main Actions or its own compact section?
- How should “Traits / Passive” avoid taking too much space?
```

### Repo comparison after Pass 3

Status: completed from uploaded repo zip inspection.

Purpose:
```text
Compare D&D 2024 monster-action research against the current live monster YAML and monster_capabilities overlay structure.
```

#### Current repo monster corpus

Current live monster YAML corpus:

```text
Monsters/*.yaml count: 516
```

Common raw monster YAML keys:

```text
name: 516
hp: 516
abilities: 516
traits: 516
ac: 515
speed: 515
actions: 515
legendary_actions: 513
initiative: 503
skills: 333
```

Text-pattern counts from raw monster YAML:

```text
multiattack: 190 monsters
recharge: 85 monsters
bonus action text: 37 monsters
reaction text: 16 monsters
spellcasting exact text: 4 monsters
spell text broadly: 101 monsters
legendary_actions non-empty: 32 monsters
```

Important caveat:
```text
Most raw Monster YAMLs include a legendary_actions key, but it is often empty. Count non-empty legendary action lists, not key presence.
```

#### Current normalized capability overlays

Current normalized overlay corpus:

```text
monster_capabilities/**/*.yaml count: 18 overlays
capability count: 63
```

Capability type groups:

```text
action: 40
trait: 20
legendary_action: 3
```

Action types:

```text
melee_attack: 25
ranged_attack: 9
save_ability: 3
composite: 2
spellcasting: 1
utility: 23
```

Executable flags:

```text
executable true: 37
executable false: 26
```

Existing overlays include:
```text
adult-red-dragon
archmage
bandit
bugbear / bugbear-warrior
cultist
goblin / goblin-warrior
kobold / kobold-warrior
ogre
orc
skeleton
troll
wolf
zombie
black-and-tan-constable
black-and-tan-rifleman
```

#### Match with researched standards

The current overlay schema already matches much of the researched D&D monster-action structure:

```text
Research: Main attacks need structured action cards.
Repo: melee_attack and ranged_attack overlays already include attack_bonus, damage, reach/range.

Research: Save/AoE actions need different resolution model.
Repo: save_ability overlays include save_dc, save_ability, damage, shape/size, effects.

Research: Multiattack should be guided sequence, not opaque one-click.
Repo: composite overlays use mechanics.composite child action_id/name/count.

Research: Recharge and limited-use actions must be visible.
Repo: recharge exists on some overlays and backend has monster capability recharge/resource helpers.

Research: Spellcasting should be fast/combat-use oriented.
Repo: spellcasting overlay exists for Archmage and resolves spell lists to local spell definitions.
```

#### Gaps vs researched standards

The current live data does not yet fully support a complete `/dmcontrol` action surface.

Gaps:

```text
1. Normalized overlays cover only 18 monsters out of 516 raw monster YAMLs.
2. Raw monster YAML actions are mostly text blobs and not directly executable.
3. Bonus Actions and Reactions are mostly embedded as text, not normalized sections.
4. Legendary Actions exist for 32 monsters, but only 3 normalized legendary_action capabilities are present.
5. Spellcasting exact normalized support is minimal: only one spellcasting overlay was found.
6. Recharge support exists, but visible/useful UI state and automation are still incomplete.
7. X/Day / rest-based limited uses are not yet broadly normalized.
8. Raw spell-related text appears often, but much of it is traits/resistances/descriptions, not clean combat spellcasting data.
```

#### Repo-specific examples

Adult Red Dragon overlay is the best current complex example:

```text
Multiattack: composite
Children:
- Frightful Presence x1
- Bite x1
- Claw x2

Bite/Claw/Tail:
- melee_attack
- attack_bonus
- reach
- damage formulas

Frightful Presence:
- save_ability
- save_dc
- save_ability
- effects condition frightened
- radius metadata

Fire Breath:
- save_ability
- shape cone
- size 60
- damage 18d6 fire
- recharge 5
```

Archmage overlay shows current spellcasting direction:

```text
Dagger: executable attack
Magic Resistance: utility trait
Spellcasting: non-executable spellcasting capability
Mechanics include:
- ability
- save_dc
- attack_bonus
- spell level lists
- resolved spell data from Spells/
```

Black and Tan Rifleman overlay shows current firearm content:

```text
Armalite Rifle: ranged_attack, range 120/360, damage 1d12+4
.45 Pistol: ranged_attack, range 40/120, damage 1d10+4
Knife: melee/ranged attack
Controlled Burst: utility manual/assisted
```

Black and Tan Constable and Rifleman raw monster YAML both have Multiattack text, but current rifleman overlay did not include a composite Multiattack entry in the inspected snippet. That means some custom monster multiattack behavior may still be descriptive/manual unless overlay is expanded.

#### Backend support already present

The backend already has useful support for researched concepts:

```text
MonsterCapabilityService.summarize_capabilities_for_ui()
- groups capabilities by action/trait/legendary_action/etc.
- derives target_mode
- derives area metadata
- derives outcome_options for save abilities
- resolves spellcasting lists
- resolves composite children into resolved_composite
- exposes recharge_rule and uses fields when present

_dm_monster_capability_execute()
- supports composite actions by returning resolution: assisted_sequence
- supports spellcasting as assisted_spellcasting / assisted_spell
- supports melee_attack and ranged_attack execution with target_cid
- supports recharge readiness checks
- spends turn resources for executed attacks

_dm_monster_capability_resolve_targets()
- supports target rows
- supports multiple targets for assisted resolution
- applies damage/effects after confirmation
```

Important implementation caveat:
```text
Some focused-panel prototype code used target_cid: selected[0] during /execute. For `/dmcontrol`, single-target normal attacks can reuse this, but AoE/multi-target actions need a cleaner flow that does not pretend one selected target represents the whole area.
```

#### Implications for `/dmcontrol`

The repo supports the Pass 3 research direction, with one major qualifier:

```text
The schema/backend are promising, but normalized monster coverage is shallow.
```

Therefore `/dmcontrol` should be designed in layers:

First implementation-friendly layer:
```text
- current actor detection
- LAN-style map/movement surface
- normalized attack action cards for overlay-backed monsters
- normal melee/ranged attack flow
- modal resolution
- Multiattack sequence for overlay-backed composite actions
```

Fallback layer:
```text
- if no overlay exists, show “No structured actions yet”
- provide manual/assisted controls only if they do not recreate the old dropdown-heavy DM UI
- allow DM to reference full stat sheet on /dm
```

Content/tooling layer needed later:
```text
- expand overlays for more monsters
- build authoring/normalization tools for monster actions
- normalize Bonus Actions, Reactions, Legendary Actions, recharge, and limited-use features
- improve spellcasting extraction for monster/NPC spellcasters
```

#### Updates to Pass 3 conclusions after repo comparison

Confirmed:
```text
1. Action-card grouping by stat block section is correct.
2. Multiattack guided sequence is correct.
3. Normal attacks should be first-class.
4. Save/AoE actions need separate resolution flow.
5. Recharge/limited-use visibility is important.
6. Monster spellcasting needs special research before final UI design.
```

Adjusted:
```text
1. Initial /dmcontrol cannot assume every monster has structured actions.
2. First /dmcontrol action implementation should target overlay-backed monsters.
3. Raw YAML stat blocks remain reference material until normalization coverage grows.
4. The final UI must handle “no structured overlay” gracefully without falling back to dropdown hell.
5. Overlay expansion/content tooling is a future enabling milestone, not just polish.
```

## Pass 4 — Monster spellcasting UX

Status: completed.

Research target:
```text
Dedicated spell panel vs Monster Action cards for monster/NPC spellcasting.
```

Questions:
```text
Do modern monster stat blocks use compact spellcasting or action-like spell attacks?
How many spells do typical NPC spellcasters have?
Should spells be grouped under Monster Actions, or shown in a spell section?
What data needs to be visible: save DC, range, target, concentration, components, slots/uses?
```

### Sources consulted

Official / rules-facing sources:
- D&D Beyond Basic Rules 2024 — "How to Use a Monster"
- D&D Beyond — "Preview the New Stat Block Design in the 2024 Monster Manual"
- Roll20 D&D 2024 Compendium — Casting Spells / special abilities without spell slots

VTT / implementation-context sources:
- Fantasy Grounds forum discussion of 2024 Monster Manual stat blocks and spellcasting
- Roll20 forum feedback on 2024 Monster Manual stat blocks and spellcasting configuration

Community/context sources treated as lower authority:
- D&D Beyond forum discussions about X/Day monster spells and spell-slot rules
- Reddit discussions about 2025 Monster Manual spell-like abilities and "not actually spells"
- The Monsters Know / older Archmage spell-tactics material for complexity context only

### Findings

#### 1. Modern monster spellcasting is being made easier to use in combat

The D&D Beyond preview of the 2024 Monster Manual says spellcasting monsters now cast spells in ways that are easier to use in combat. It says spells might appear in the Spellcasting action or be highlighted as Reactions or Bonus Actions.

Design implication:
```text
/dmcontrol should not bury monster spells in a large player-style spellbook search by default.
```

Monster spellcasting should appear where it is used:
```text
Main Actions
Bonus Actions
Reactions
possibly Traits / Passive for always-on magic
```

This supports action-card grouping over a full player spell manager clone.

#### 2. Monster spellcasting entries still need core spell metadata

The 2024 Basic Rules say if a monster can cast spells, its stat block lists the spells and provides:
- spellcasting ability
- spell save DC, if relevant
- spell attack bonus, if relevant

They also say a spell of level 1 or higher is cast at its lowest possible level unless otherwise noted.

Design implication:
```text
/dmcontrol spell/action cards should show:
- spell/action name
- casting type/action economy
- save DC or attack bonus
- range
- concentration
- duration
- damage/effect summary
- usage/slot/at-will information when available
```

The full text can remain collapsible or visible on `/dm`.

#### 3. Monster spells may not use player-style spell slots

2024/2025 monster discussions and VTT implementation notes repeatedly indicate that many newer monsters use at-will, X/day, or action-like spellcasting rather than full player-style slot tracking. Roll20’s D&D 2024 casting rules also note that some characters and monsters have special abilities that cast specific spells without a spell slot and are limited in another way, such as per-day use.

Design implication:
```text
Do not assume player-style spell-slot UI for /dmcontrol monsters.
```

Instead, support multiple usage models:
```text
at will
X/day per spell/action
recharge
spell slots, where older/imported data has them
manual/advisory if usage is unclear
```

The repo currently has an older-style Archmage overlay with slot lists. `/dmcontrol` needs to handle that, but should not make slot UI the only spellcasting model.

#### 4. Some magical monster abilities are not spells

Community discussion around the 2025 Monster Manual repeatedly notes that many magical-looking NPC/monster abilities are not actually spells unless the stat block says they are spells. This matters for Counterspell and for UI labeling.

Design implication:
```text
/dmcontrol should distinguish:
- Spell
- Magical action / supernatural action
- Save ability
- Recharge ability
```

Do not label every magical-looking ability as a spell. A "spellcasting" section should only be used when the overlay/source identifies actual spellcasting.

#### 5. A dedicated spell search is probably not needed for monsters/NPCs at first

Player spellcasters can have huge spell lists and preparation workflows; monsters usually need a smaller combat-use set. Even when an older Archmage-style stat block has many spells, the DM typically needs a few combat-relevant spells immediately, with the rest as reference.

Design implication:
```text
Initial /dmcontrol should not implement a full spell search/preparation manager for monsters.
```

Better first model:
```text
Monster Actions / Spellcasting group
→ compact spell/action cards
→ filter/group by At-Will, X/Day, Slots, Reaction, Bonus Action if needed
→ click spell/action
→ LAN-style target/AoE preview
→ resolution modal
```

If later needed, add simple filtering within the spell group, not a full player spellbook clone.

#### 6. Spellcasting should be grouped by action economy first, spell level second

For active combat, the DM cares most about when the spell can be used:
```text
Action
Bonus Action
Reaction
Legendary Action / special timing
```

Spell level/slot/usage matters, but it is secondary during a monster’s turn.

Recommended `/dmcontrol` grouping:
```text
Main Actions
  - attacks
  - save/AoE abilities
  - Spellcasting action or action spells

Bonus Actions
  - bonus action spells/actions

Reactions
  - reaction spells/actions with trigger text

Legendary Actions
  - legendary spell/action options, later mode

Traits / Passive
  - Magic Resistance, spell-like passive traits, etc.
```

Inside a Spellcasting group, show smaller badges:
```text
At Will
1/day
3/day
Slot 3
Concentration
Save DC 17
+9 spell attack
```

#### 7. Spell/AoE targeting can reuse LAN spell-targeting concepts

The repo LAN client already has spell/AoE targeting primitives:
- spell target selection UI
- AoE target preview panel
- spell targeting sessions
- map-based target/area workflows

Design implication:
```text
/dmcontrol spellcasting should reuse LAN spell/AoE targeting patterns when possible.
```

The UX should be:
```text
select spell/action card
→ show range or AoE template
→ click target/origin/place template
→ preview affected targets
→ confirm
→ resolution modal
```

#### 8. Monster spellcasting should support manual/assisted fallback

Because repo overlays are incomplete and monster data varies, `/dmcontrol` needs graceful fallback:
```text
No structured spellcasting actions yet.
Use /dm stat sheet/reference.
```

If an action is known but not executable:
```text
Manual / Assisted
show DC/range/effect text
no fake automation
```

Avoid rebuilding the old dropdown-heavy DM controls as the fallback.

### Repo comparison after Pass 4

Status: completed from uploaded repo zip inspection.

#### Current spell corpus

Current repo spell library:

```text
Spells/*.yaml count: 395
```

Spell YAML fields are structured and useful:
```text
schema
id
name
level
school
tags
casting_time
range
components
duration
ritual
concentration
lists
text
mechanics
```

Spell levels in current repo:
```text
cantrip / level 0: 34
level 1: 66
level 2: 63
level 3: 52
level 4: 41
level 5: 49
level 6: 34
level 7: 21
level 8: 18
level 9: 16
```

This is a strong foundation for spell detail cards and resolution, but it is a player-style spell library. `/dmcontrol` should not expose all 395 spells directly. It should expose only spells attached to the current monster/NPC overlay or stat block.

#### Current monster spellcasting corpus

Raw monster YAMLs containing the word "spell":

```text
101 monsters
```

Raw monster YAMLs containing exact "Spellcasting":

```text
4 monsters:
- Archmage
- Mage
- Mage Apprentice
- Pseudodragon
```

Important caveat:
```text
Many "spell" hits are Magic Resistance, antimagic, magical effects, or references to spells such as antimagic field/dispel magic. They are not necessarily spellcasting monsters.
```

This supports the research point that not every magical-looking ability should become a spellcasting UI.

#### Current normalized spellcasting overlay support

Current normalized overlay spellcasting support is minimal.

Found overlay:
```text
monster_capabilities/samples/archmage.yaml
```

It contains:
```text
Magic Resistance: utility trait
Spellcasting: non-executable spellcasting capability
```

The Archmage Spellcasting capability includes:
```text
ability: int
save_dc: 17
attack_bonus: 9
level: 18
school: wizard
spell lists:
  at_will
  cantrips
  level 1-9 slot lists
resolved spell data from Spells/
```

This is useful, but it is not yet executable from the current normalized monster action system.

#### Current backend support

`MonsterCapabilityService.summarize_capabilities_for_ui()` already resolves spellcasting lists and can attach local spell definitions.

`_dm_monster_capability_execute()` supports spellcasting as assisted output:
```text
assisted_spellcasting
assisted_spell
```

However, current overlay spellcasting is non-executable, so `/dmcontrol` cannot assume monster spells are currently runnable.

#### Repo-specific implications

Confirmed:
```text
1. The repo has a rich spell library.
2. The repo can resolve spell data into capability summaries.
3. Archmage demonstrates a viable spellcasting overlay structure.
4. Monster spellcasting coverage is very shallow.
5. Many magical monster abilities are not spellcasting.
```

Adjusted:
```text
1. Initial /dmcontrol should not build a full spell UI.
2. Initial /dmcontrol should show spellcasting only when the current monster has a structured overlay.
3. Spellcasting should be a compact group under action cards, not a global spell search.
4. Non-executable spellcasting should display as assisted/manual until backend execution is safe.
5. Overlay/content authoring will be needed before monster spellcasting feels complete.
```

#### Recommended initial `/dmcontrol` spellcasting behavior

For overlay-backed spellcasting monsters:
```text
Show a Spellcasting / Magical Actions group.
Show spell cards grouped by usage/frequency:
- At Will
- Cantrips
- 1/day, 3/day, etc.
- Slots, if older-style overlay provides slots
Show badges:
- DC
- attack bonus
- concentration
- range
- duration
- action economy
Clicking an executable spell/action eventually uses LAN-style spell targeting.
Non-executable spells show assisted/manual text.
```

For monsters without structured spellcasting overlay:
```text
No structured spellcasting actions yet.
Use /dm stat sheet/reference.
```

Do not:
```text
Expose all 395 repo spells in /dmcontrol.
Require spell search for normal monster use.
Pretend magical abilities are spells unless identified as spells.
Force player-style spell slot UI onto modern X/day monster spellcasting.
```

### Implications for `/dmcontrol`

Concrete design rules to carry forward:

```text
1. Monster spellcasting should be action-card based, not a player spellbook clone.
2. Group spells by action economy and usage/frequency, not primarily by spell level.
3. Show DC/attack bonus/range/concentration/duration/usage on cards.
4. Use LAN-style targeting and resolution for executable spells.
5. Keep non-executable spellcasting assisted/manual.
6. Do not expose global spell search in first /dmcontrol version.
7. Do not call magical abilities spells unless the data says they are spells.
8. Older slot-based overlays must be supported, but modern X/day/at-will usage must also be supported.
9. The current repo has enough spell library data for cards, but not enough monster overlay coverage for broad automation.
10. Spellcasting content/overlay expansion is a later enabling milestone.
```

### Open questions for later spec

```text
- Should Archmage-style slot lists be shown collapsed by level or grouped by combat relevance?
- Should /dmcontrol include a quick "combat spell favorites" list for complex spellcasters?
- How should spell slot or X/day consumption be tracked if the overlay is non-executable?
- Should Counterspell/Shield-style reactions appear when it is not the monster's turn?
- Should concentration status be tracked automatically or initially shown as an advisory badge?
- Should spell effects reuse player spell mechanics directly or pass through MonsterCapabilityService wrappers?
```

## Pass 5 — Multiattack and sequence UX

Status: completed.

Research target:
```text
Best way to guide a DM through multi-step monster turns.
```

Questions:
```text
Should Multiattack open a modal, drawer, or inline sequence tray?
How should child attacks be tracked?
How should different targets per child attack be supported?
How should cancellation/reset work?
How much should the app enforce vs assist?
```

### Sources consulted

Official / rules-facing sources:
- D&D Beyond Basic Rules 2024 — "How to Use a Monster"
- Roll20 D&D 2024 Compendium — "Parts of a Stat Block"
- Roll20 D&D 2024 monster examples: Mammoth, Giant Scorpion, Doppelganger, Giant Ape

VTT / implementation-context sources:
- Foundry VTT Multiattack 5e module
- GitHub Multiattack-5e README
- Foundry VTT Mob Attack Tool
- Foundry VTT Argon Combat HUD package/docs
- Foundry VTT GitHub issue discussing redundant attack clicks in chat-card workflows
- Fantasy Grounds NPC/effects automation docs and forum discussions

Community/context sources treated as lower authority:
- Foundry VTT Reddit thread about how GMs manage Multiattack
- D&D Beyond / RPG forum discussions about Multiattack edge cases
- AlphaStream monster design commentary

### Findings

#### 1. Multiattack is a parent action that details child attacks/abilities

The 2024 rules-facing text says some creatures can make more than one attack when they take the Attack action, and that the Multiattack entry in the Actions section details the attacks and any additional abilities the creature can use as part of that action.

Roll20’s 2024 compendium repeats the same structural point. Monster examples confirm several patterns:

```text
Mammoth:
  Multiattack. Two Gore attacks.

Giant Scorpion:
  Multiattack. Two Claw attacks and one Sting attack.

Doppelganger:
  Multiattack. Two Slam attacks and uses Unsettling Visage if available.

Giant Ape:
  Multiattack. Two Fist attacks.
  Separate Recharge/AoE action also exists.
```

Design implication:
```text
Multiattack is not always “same attack N times.”
It can be a parent sequence with heterogeneous child steps.
```

`/dmcontrol` must model Multiattack as a guided parent sequence rather than a single opaque button.

#### 2. Child steps need separate target flows

Because Multiattack may include different child attacks with different reach/range/effects, each child should use its own normal targeting/resolution flow.

Examples:
```text
Giant Scorpion:
  Claw x2 and Sting x1
  both melee, but different damage/effects

Adult Red Dragon-style:
  Frightful Presence x1
  Bite x1
  Claw x2
  children are not all identical target modes/effects
```

Design implication:
```text
Parent Multiattack opens sequence flow.
Child step selection enters normal LAN-like targeting for that child.
```

Do not assume:
```text
one target for all child attacks
one resolution modal for all child attacks
one damage formula for all child attacks
```

#### 3. The DM needs memory assistance, not over-enforcement

Community Foundry discussion around Multiattack often describes GMs clicking the Multiattack feature for reference, then performing the attacks normally. One comment specifically wished for automation that at least prompts “Attack again?” rather than forgetting the ability.

Design implication:
```text
The most valuable first UX is guided tracking:
- what child attacks remain
- what has been completed
- what child is currently resolving
```

The tool should assist memory and flow without trying to enforce every tactical/legal nuance.

#### 4. Batch/all-at-once multiattack is useful, but risky as the first model

Foundry’s Multiattack 5e module streamlines Multiattack by letting users perform several attack and damage rolls at once and condensing output into a custom chat card. Foundry’s Mob Attack Tool similarly focuses on quickly resolving multiple attack/damage rolls from groups, summons, and creatures with Multiattack.

This proves that batch workflows are useful, but they are not the safest first `/dmcontrol` model.

Why batch is risky for this repo:
```text
- D&D targets can differ per child attack.
- Movement can happen between attacks.
- Some children have different reach/range/effects.
- Some children are save/AoE/condition abilities, not attacks.
- DM may need to stop or change plans mid-sequence.
```

Design implication:
```text
First /dmcontrol Multiattack should be stepwise guided, not batch-all-at-once.
```

Batch shortcuts may come later for simple repeated same-attack cases, such as “Claw x2 against same target.”

#### 5. Avoid redundant click chains

A Foundry D&D 5e issue about chat-card attack clicks highlights a common UX problem: once a user has already chosen an attack/activity, requiring another redundant "Attack" click in the chat card slows the workflow.

Design implication:
```text
/dmcontrol Multiattack should avoid:
parent Multiattack → child → extra child activation → target → extra attack roll button → modal → apply
```

The preferred child flow should be as direct as possible:
```text
select child step
→ map enters child targeting mode
→ click target
→ resolution modal opens
```

#### 6. Multiattack should probably be a modal/overlay flow on `/dmcontrol`

For `/dmcontrol`, the main page should be map-first and LAN-like. A Multiattack sequence needs to remain visible while the DM targets/resolves child steps, but it should not permanently consume the main bottom bar.

Recommended first UX:
```text
Click Multiattack
→ guided Multiattack modal / tray opens
→ child step list visible
→ click child
→ modal minimizes/side-docks or stays context-visible while targeting
→ target/resolution modal runs for child
→ return to sequence modal/tray
→ completion counter updates
→ End Sequence manually
```

Why modal/tray over full actor-sheet panel:
```text
- keeps the map visible
- makes it clear the DM is inside a temporary sequence
- supports explicit cancel/end
- avoids turning the bottom action bar into a cluttered sequence tracker
```

The exact placement should be based on LAN layout inspection:
```text
desktop modal, bottom drawer, or right-side compact tray
```

But the behavior contract should be fixed before implementation.

#### 7. Child completion should be frontend-local at first

Multiattack sequence state is turn-local and DM-guided. Persisting it across refreshes or backend state snapshots is not necessary for the first implementation.

Track locally:
```text
parent action id
child action id
child max count
child completed count
active child
last selected targets if useful
error state
```

Do not initially track in backend:
```text
per-child completion
strict action economy
same-target/different-target constraints
resource use beyond what child action endpoint already handles
```

Design implication:
```text
Sequence progress is a UI guide, not authoritative rules enforcement.
```

#### 8. Movement must remain possible between child attacks

The user requirement and 2024 movement discussion both support split movement around actions. Since D&D movement can be broken up around actions, a monster/NPC may need to move between child attacks when legal.

Design implication:
```text
Multiattack modal/tray must not lock the map.
```

During sequence:
```text
movement range/remaining movement should still be visible
DM should still be able to drag/drop the active token
child targeting mode and movement mode need clear, cancelable state boundaries
```

Open design question:
```text
Should movement remain available while the sequence modal is open, or should the modal have a “Move” / “Resume movement” affordance?
```

Either way, `/dmcontrol` should not force all attacks before or after movement.

#### 9. Different targets per child must be supported

Multiattack often allows child attacks to target different creatures unless the specific stat block says otherwise.

Design implication:
```text
Each child step should have its own target selection.
```

Do not make the first implementation require:
```text
one target shared by all child attacks
same target unless manually overridden
automatic target distribution
```

A later optimization can add:
```text
repeat last target
use same target for remaining attacks
auto-select nearest valid target
```

But those should be explicit shortcuts, not assumptions.

#### 10. Cancellation/reset model must be explicit

Recommended behavior:
```text
Cancel child targeting/resolution:
  return to sequence without incrementing completion

End Sequence:
  clear sequence state and return to normal controls

Switch actor / PC turn / no active actor:
  clear sequence state

Switch top-level non-child action:
  clear sequence state after warning or clear immediately if no backend mutation is pending

Successful child apply:
  increment child completion exactly once
  clear child targeting/resolution state
  return to sequence

Failed child apply:
  keep child resolution modal/tray visible with error
  allow retry/cancel
```

This matches the direction already tested in the `/dm` prototype, but the final `/dmcontrol` implementation should live in the LAN-like page.

### Repo comparison after Pass 5

Status: completed from uploaded repo zip inspection.

#### Current normalized composite coverage

Current overlay corpus includes only two normalized composite Multiattack entries:

```text
monster_capabilities/samples/adult-red-dragon.yaml
monster_capabilities/samples/troll.yaml
```

Adult Red Dragon composite:

```text
Multiattack:
  Frightful Presence x1
  Bite x1
  Claw x2
```

Troll composite:

```text
Multiattack:
  Bite x1
  Claw x2
```

This matches the researched model well, but coverage is shallow.

#### Current backend support

The backend already has a good first version of assisted sequence support:

```text
_dm_monster_capability_execute()
  if action_type == "composite":
    returns:
      ok: true
      resolution: assisted_sequence
      capability_id
      name
      desc
      steps[]
```

Each step includes:
```text
action_id
name
count
executable
matched
```

`MonsterCapabilityService.summarize_capabilities_for_ui()` also resolves composite child actions into `resolved_composite`.

This is enough to build a `/dmcontrol` guided sequence UI without new backend endpoints for the first slice.

#### Current prototype support

The `/dm` Focused Actor prototype already implemented:
```text
Sequence Tray
child completion tracking
child selection into target/resolution flow
hardening for invalid/missing children
in-flight protection
focus-change cleanup
```

Reusable ideas:
```text
- sequence packet state
- child completed counts
- invalid child handling
- return-to-sequence after child resolution
- End Sequence cleanup
```

Not final as-is:
```text
- placement on /dm
- dependency on /dm Focused Actor panel layout
- map-targeting assumptions from /dm
```

#### Current content gaps

Observed gap:
```text
Black and Tan Rifleman raw YAML includes Multiattack text, but inspected normalized overlay did not include composite Multiattack.
```

Therefore:
```text
Black and Tan firearm enemies are still beta and need explicit overlay/content validation before being used as proof that Multiattack support works.
```

This should remain in the bug/validation list:
```text
- Black and Tan single-spawn numbering regression
- Black and Tan Rifleman/Constable overlay completeness
- firearm monster ammo/manual tracking assumptions
- composite Multiattack overlays for firearm enemies if desired
```

### Recommended `/dmcontrol` Multiattack model

First finalized model:

```text
Click Multiattack action card
→ open guided Multiattack modal/tray
→ show child steps with counts and completion
→ DM selects a child step
→ /dmcontrol enters that child action’s normal target mode
→ DM targets on active /dmcontrol map
→ child resolution modal opens
→ Apply increments child completion once
→ Cancel returns to sequence without progress
→ DM can move between child steps
→ DM ends sequence manually
```

Recommended UI details:
```text
Parent title:
  Multiattack

Child rows:
  Bite        0 / 1    Select
  Claw        0 / 2    Select
  Frightful Presence 0 / 1 Select

Shortcuts later:
  Use same target again
  Repeat this child
  Resolve remaining identical attacks
```

Recommended state model:
```text
activeSequence = {
  actorCid,
  parentActionId,
  parentName,
  steps: [
    { actionId, name, maxCount, completedCount, executable, matched }
  ],
  activeChildActionId,
  error
}
```

### Explicitly deferred

```text
- automatic target distribution
- one-click batch multiattack
- enforced same-target/different-target rules
- backend-persisted sequence state
- action economy enforcement
- movement opportunity-attack enforcement
- legendary action integration
- reaction integration
- spellcasting sequence automation
- AoE child automation beyond existing child action flow
```

### Implications for `/dmcontrol`

Concrete design rules to carry forward:

```text
1. Multiattack is a guided sequence, not a single opaque button.
2. Child actions reuse normal /dmcontrol attack/spell/AoE targeting.
3. Child completion is tracked locally and assistively at first.
4. Different targets per child must be supported.
5. Movement between child attacks must remain possible.
6. Apply increments completion exactly once.
7. Cancel child resolution does not increment completion.
8. End Sequence is manual and explicit.
9. Batch-all-at-once multiattack can be a future shortcut, not the first model.
10. Black and Tan firearm Multiattack content must be validated separately before relying on it.
```

### Open questions for later spec

```text
- Should the Multiattack sequence UI be a modal, bottom drawer, or side tray in /dmcontrol?
- How should movement mode and child target mode interact while the sequence is active?
- Should “same target as previous child” be a first-version shortcut?
- Should the sequence show per-child last target/result history?
- Should a failed/missed child count as completed after Apply Results? Likely yes, because the attack was used.
- Should child completion be reset on turn end automatically?
- How should recharge/limited-use children behave inside Multiattack if they appear?
```

## Pass 6 — Target selection UX

Status: completed.

Research target:
```text
Best patterns for selecting targets in tactical combat UIs.
```

Questions:
```text
Map-click targeting vs target list vs hybrid?
How do UIs show valid/invalid targets?
How do they handle crowded maps?
How do they handle AoE affected-target previews?
How do they support manual override?
How do they avoid making target selection annoying for the GM?
```

### Sources consulted

VTT / tabletop sources:
- Foundry VTT Tokens documentation
- Foundry VTT Game Controls documentation
- Foundry VTT targeting modules: Smart Target, T is for Target, Token Targeting
- Roll20 Macros & Token Actions documentation
- Roll20 macro target prompt documentation
- Fantasy Grounds Combat Tracker documentation
- Fantasy Grounds forum / help discussions on control-click targeting
- D&D Beyond Maps combat encounter documentation

Game/tactical UI sources:
- Tactical-RPG Move Range
- GameDev.net discussion: Turn Based Action Selection and UI Design
- ORK Framework Target Selection documentation
- Games R UX / tactical UI discussion
- Cogmind UI feedback discussion on map labels/scanning
- Persona 5 UI analysis for target selector feedback
- General game UI design references from Sketch / Justinmind

### Findings

#### 1. Map-click targeting is appropriate on an active control surface

Foundry’s token documentation describes a direct map-targeting model:
```text
targeting tool
→ left-click token
→ indicator appears
→ shift-click additional tokens
→ drag-box can target multiple tokens
```

Fantasy Grounds commonly uses control-click targeting on a token or combat tracker row. Roll20 macros can prompt the user to select target tokens before the roll executes. These all support map or token targeting as a normal VTT interaction.

Design implication:
```text
Map-click targeting is appropriate on /dmcontrol.
Map-click targeting is not appropriate as the required primary workflow on /dm.
```

This is the architecture split:
```text
/dm map = reference/inspection
/dmcontrol map = active play/targeting surface
```

#### 2. Targeting needs a hybrid model for crowded maps

Map-click is fast when tokens are visible and not crowded. It is less reliable when:
```text
tokens overlap
tokens are tiny
map is zoomed out
AoE affects many creatures
DM wants to target from initiative/combatant names
```

Several researched systems imply hybrid selection:
- Foundry supports click, shift-click, drag-box, and keyboard shortcuts/modules.
- Roll20 macro targeting prompts the user after invoking the action.
- Fantasy Grounds allows targeting via token or combat tracker row.
- ORK Framework explicitly supports target menus plus mouse/touch target selection.

Design implication:
```text
/dmcontrol should use map-click targeting as the primary LAN-like path,
but should also provide a target list/picker fallback.
```

Recommended model:
```text
Action-first:
  click action
  → map enters target mode
  → valid targets highlight
  → click token to select target(s)

Fallback:
  target tray/list shows eligible combatants
  → click row/chip to select/deselect
  → map highlights selection
```

This preserves the LAN-like flow while avoiding frustration on crowded maps.

#### 3. Action-first should be the default for D&D monsters

Turn-based UI discussion often weighs target-first vs action-first selection. Target-first can filter unavailable actions, but D&D monster turns usually start with the DM choosing what the monster does:
```text
Bite
Claw
Fire Breath
Hold Person
Multiattack
```

The target rules depend on that action:
```text
melee reach
ranged range
save DC
AoE shape
line/cone/cube
self/ally/enemy
```

Design implication:
```text
/dmcontrol should default to action-first targeting.
```

Recommended:
```text
select action card
→ target mode knows range/reach/AoE/target count
→ target valid/invalid state appears
→ selected targets go to tray/resolution
```

Target-first filtering can be a later enhancement, not the first model.

#### 4. Valid/invalid target feedback should be visual and textual

Foundry-style target indicators and tactical range overlays show that target state needs direct visual feedback. Game UI references emphasize that UI should provide visual cues that guide action. Tactical-grid algorithms commonly compute selectable tiles/entities in area and use overlays to show reachable/selectable state.

Design implication:
```text
/dmcontrol needs both:
- map highlight
- target tray/status text
```

Suggested target states:
```text
valid target
likely valid / advisory
out of range
blocked / invalid
unknown
affected by AoE
selected
source actor
```

Visual-only is not enough; the tray/status should explain why a target is invalid or advisory.

#### 5. Do not block the DM too aggressively

VTTs and D&D tables need overrides because the DM may have exceptions:
```text
custom monster rule
special terrain
line-of-sight ruling
rule-of-cool
hidden condition
manual adjustment
```

Design implication:
```text
/dmcontrol should warn first and block only when the interaction is technically impossible.
```

Recommended behavior:
```text
Out of normal range:
  warn/highlight red, but allow override if DM confirms or override mode is active

No token / no target:
  disable resolution until target exists if the action requires target

Invalid shape placement:
  snap/reject if the placement cannot exist on the grid

Backend error:
  show clear error and keep state recoverable
```

This keeps the system assistive rather than adversarial.

#### 6. Target tray is still useful even with map-first targeting

Even though `/dmcontrol` should be map-first, a target tray remains useful:
```text
selected target list
target HP/status
range/advisory status
remove target chip
clear targets
affected AoE preview
manual include/exclude later
```

The current `/dm` prototype target tray concept is reusable, but its final placement should be LAN-like and tied to `/dmcontrol` target mode/resolution, not `/dm` cockpit controls.

#### 7. AoE affected-target preview should be separate from confirmed targets

For AoE and templates, the app should distinguish:
```text
affected by current template preview
selected/confirmed for resolution
manually included/excluded
```

Foundry module examples include targeting all tokens inside a template, which supports the value of template-derived target sets. But `/dmcontrol` should still let the DM confirm before applying effects.

Recommended AoE model:
```text
select AoE action
→ place/aim template
→ preview affected targets
→ show affected list
→ allow manual include/exclude later
→ confirm to resolution modal
```

This belongs more fully in Pass 7, but it affects target selection design.

#### 8. Keyboard and escape behavior matter

Targeting must be easy to cancel. Foundry exposes many keyboard shortcuts and VTT modules add alternate targeting shortcuts because target selection speed matters.

Recommended `/dmcontrol` basics:
```text
Escape cancels current target mode
Shift-click toggles/adds extra target if multi-target mode exists
Enter confirms when modal is focused
Delete/backspace removes selected target chip when focused
Clear Targets button always available in tray
```

Exact shortcuts should be finalized after LAN code inspection and should avoid conflicting with existing LAN shortcuts.

#### 9. Crowded-map fallback should avoid label spam

Cogmind’s UI discussion about map labels and scanning is useful: always-on labels can become noisy, and a separate scan/list view can be more useful when many map items/entities overlap.

Design implication:
```text
Do not label every possible target all the time.
```

Recommended:
```text
only label source/selected/hovered/invalid target in active mode
show target list/tray for dense information
use hover/focus for details
```

#### 10. Redundant click chain warning

This remains important from Pass 5 and applies directly to targeting.

Avoid:
```text
click action
→ click target
→ click "attack" again
→ click target again
→ click resolve
```

Preferred:
```text
click action
→ map enters target mode
→ click target
→ resolution modal opens
```

For multi-target/AoE:
```text
click action
→ map enters target/template mode
→ click/select targets or place template
→ confirm selected/affected targets
→ resolution modal opens
```

The system should not ask for a target twice or require a second attack activation after target selection.

### Repo comparison after Pass 6

Status: completed from uploaded repo zip inspection and prior LAN anchors.

#### Current LAN targeting support

The LAN page already supports the desired active targeting model:

```text
setAttackOverlayMode()
  assets/web/lan/index.html around 12395

attack/range overlay drawing
  assets/web/lan/index.html around 14574

attack target click flow
  assets/web/lan/index.html around 19003-19131

openAttackResolveModal()
  assets/web/lan/index.html around 12757

attackResolveModal HTML
  assets/web/lan/index.html around 2730
```

Spell/AoE anchors:

```text
AoE target preview panel:
  assets/web/lan/index.html around 2643

spell target selection UI:
  assets/web/lan/index.html around 2655

runSpellTargetingAgainstTarget()
  assets/web/lan/index.html around 16326

renderSpellTargetSelectionUi()
  assets/web/lan/index.html around 22732

startSpellTargetingSession()
  assets/web/lan/index.html around 22794
```

This confirms:
```text
/dmcontrol should adapt LAN target mode rather than continue extending /dm map target mode.
```

#### Current `/dm` prototype support

The `/dm` Focused Actor prototype already has:
```text
target preview
target tray
selected target highlighting
range/AoE advisory hints
resolution tray
sequence tray
```

Reusable concepts:
```text
target tray state model
selected target chips/cards
advisory status wording
range/AoE status text
in-flight/error hardening
resolution transition
```

Not final as-is:
```text
/dm placement
/dm map as action surface
control flow built around Focused Actor Panel
```

#### Current repo gap

The repo does not yet have `/dmcontrol`, so target selection should not be added further to `/dm` except as bugfix/historical cleanup.

First `/dmcontrol` target selection should:
```text
reuse/adapt LAN attack targeting
then later incorporate target tray ideas if needed
```

### Recommended `/dmcontrol` target selection model

Initial attack target model:
```text
select attack/action from bottom/control bar
→ map enters action-specific target mode
→ source token and range/reach are shown
→ valid targets highlight
→ click target token
→ resolution modal opens
```

Multi-target model:
```text
select multi-target action
→ map enters multi-target mode
→ click tokens to add/remove
→ selected targets appear in tray/list
→ confirm targets
→ resolution modal opens
```

AoE model:
```text
select AoE action/spell
→ map enters template placement mode
→ affected targets preview
→ confirm affected target list
→ resolution modal opens
```

Fallback/crowded-map model:
```text
target picker/list available from control bar or tray
→ grouped by PCs/enemies/allies/NPCs
→ click row toggles target
→ map highlights selected target
```

Override model:
```text
out-of-range/invalid targets warn first
DM override can allow selected target where table ruling permits
technical impossibilities still block
```

### Explicitly deferred

```text
- target-first action filtering
- auto-selecting best targets
- line-of-sight authority if not already in LAN
- hard blocking all out-of-range selections
- template include/exclude polish
- keyboard shortcut finalization
- group/box select if not already easy from LAN
- persistent per-action target memory
```

### Implications for `/dmcontrol`

Concrete design rules to carry forward:

```text
1. /dmcontrol targeting should be map-first and LAN-like.
2. /dm map targeting should not be extended as primary workflow.
3. Action-first targeting should be the default.
4. Target list/picker is a fallback/assist for crowded maps, not the primary first slice.
5. Range/validity feedback must be visual and textual.
6. Selected targets should be visible in a tray/list before applying multi-target effects.
7. AoE preview targets should be distinguishable from confirmed targets.
8. Escape must cancel target mode.
9. Avoid redundant click chains.
10. DM override should warn/confirm, not fight the DM.
```

### Open questions for later spec

```text
- Should single-target attacks open the resolution modal immediately after clicking a valid target, or briefly show a one-target tray first?
- Should out-of-range target clicks be blocked by default or allowed with confirm?
- Should target picker/list always be visible in the bottom bar, or only as a fallback drawer?
- Should target list include distance/LoS/advisory data from the start?
- Should shift-click multi-target behavior be implemented in first /dmcontrol target pass?
- Should targets from AoE template preview auto-fill the resolution modal or require explicit confirmation?
```

## Pass 7 — AoE / template placement UX

Status: completed.

Research target:
```text
Cones, lines, spheres/circles, cubes, emanations, breath weapons.
```

Questions:
```text
How do VTTs let users place cones/lines/circles quickly?
Do they anchor AoE to actor, cursor, grid cell, or target?
How are affected targets previewed?
Can selected targets be manually included/excluded?
How should confirmation work before rolling/applying?
```

### Sources consulted

Official / rules-facing sources:
- D&D Beyond Basic Rules 2024 — Rules Glossary / Area of Effect
- D&D Beyond Basic Rules 2024 — Spells / Targets and Areas of Effect
- D&D Beyond — 2024 Player's Handbook spell changes / Emanation
- Roll20 D&D 2024 Rules Definitions for AoE shapes

VTT / implementation-context sources:
- Foundry VTT Measurement and Templates documentation
- Foundry VTT measured template type API docs
- Roll20 Measure Tool documentation
- Roll20 blog: New Measure Tool Shows AoE and Shapes
- Roll20 SmartAoE wiki/script notes
- Fantasy Grounds effects / targeting docs and forum context

Repo sources:
- `assets/web/lan/index.html`
- `dnd_initative_tracker.py`
- `map_state.py`
- `monster_capability_service.py`

### Findings

#### 1. D&D 2024 AoE rules are shape + point-of-origin driven

The 2024 rules define area effects around six common shapes:
```text
Cone
Cube
Cylinder
Emanation
Line
Sphere
```

They also emphasize:
```text
point of origin
shape-specific positioning
blocked lines / Total Cover exclusion
unseen point obstruction behavior
```

Design implication:
```text
/dmcontrol AoE UX must capture both shape and origin.
```

A simple "select all targets within N feet" is not enough for cones/lines/cubes. The UI must know where the effect originates and how it is aimed/placed.

#### 2. Emanation deserves first-class treatment

Emanation is a 2024 keyword. D&D Beyond describes it as extending from a creature/object in all directions, moving with the source for longer durations, and differing from Sphere in whether the origin is included by default.

Design implication:
```text
/dmcontrol should not treat all circular areas as the same thing.
```

Needed distinction:
```text
Sphere / circle:
  point-origin area, origin included

Emanation:
  source-attached or object-attached area, often moves with source, origin inclusion depends on creator/rule
```

For first implementation:
```text
show Emanation as source-centered/source-attached
mark origin inclusion as advisory if not fully implemented
```

#### 3. VTTs commonly use measured templates for AoE

Foundry describes measured templates as map overlays used primarily to calculate areas of effect. Roll20’s newer Measure Tool supports Square, Circle, and Cone shapes and lets users customize options like cone angle and center/edge measurement. These reinforce that AoE UX should be visual/template-based, not just a target list.

Design implication:
```text
/dmcontrol should use visible map templates/previews for AoE.
```

Core flow:
```text
select AoE action
→ enter template placement/aim mode
→ show preview shape
→ affected targets preview updates
→ confirm before resolution
```

#### 4. AoE placement needs shape-specific interaction models

Recommended interaction by shape:

```text
Cone:
  anchor at source or point of origin
  aim by cursor/drag direction
  show length and spread
  affected targets preview

Line:
  anchor at source/origin
  aim by cursor/drag direction
  show length and width
  affected targets preview

Sphere / Circle:
  choose center within range
  show radius
  affected targets preview

Cylinder:
  choose center within range
  show radius and height metadata
  2D map can show base circle; height is text/advisory unless elevation is implemented

Cube / Square:
  place square/cube footprint
  allow origin-face nuance to remain advisory at first
  affected targets preview

Emanation:
  source-attached or object-attached
  show radius around source/object
  moves with source if duration persists
```

For breath weapons:
```text
usually cone or line
source actor is origin
aim by cursor/drag direction
```

#### 5. AoE target preview should separate "affected" from "confirmed"

A strong pattern across VTTs is preview before application. The repo LAN page already has an `aoeTargetPreview` panel with ally/enemy sections, and backend functions can compute included units for AoEs.

Design implication:
```text
/dmcontrol should show affected targets before rolling/applying.
```

But the UX should distinguish:
```text
preview affected by template
confirmed targets for resolution
manually excluded/included targets later
```

Initial model:
```text
template placement
→ affected target preview list
→ Confirm Targets / Resolve
→ resolution modal with save outcomes
```

Later model:
```text
manual include/exclude target chips
```

#### 6. Confirmation before mutation is mandatory

AoE actions can hit many creatures and apply damage/conditions. They should not auto-apply on placement.

Recommended flow:
```text
select AoE/spell/breath action
→ place/aim template
→ preview affected targets
→ confirm target set
→ resolution modal
→ choose/roll saves/damage
→ Apply Results
```

Do not:
```text
place template and immediately apply damage
click action and immediately hit everyone
```

#### 7. Snapping and measurement modes matter

Roll20’s Measure Tool supports snapping to center, corner, or no snapping. This matters because D&D grid AoEs often depend on intersections/corners/centers and because some effects are easier to place freely.

Design implication:
```text
/dmcontrol should start with repo/LAN snapping behavior, but leave room for mode controls:
- snap to grid cell
- snap to corner/intersection if needed later
- free/precise mode later
```

Do not overbuild this in first slice; use LAN behavior first.

#### 8. Total Cover / line-blocking should be advisory unless repo support is strong

D&D 2024 rules say AoE locations blocked from the point of origin by Total Cover are excluded. The LAN code already has line-of-sight/blocked/out-of-range guide concepts around AoE placement. However, fully authoritative cover/LoS for every AoE shape is hard.

Design implication:
```text
First /dmcontrol AoE should present LoS/cover as advisory unless backend validation is already reliable.
```

Recommended text:
```text
Blocked by cover? advisory
DM decides final affected targets
```

#### 9. Avoid redundant AoE click chains

AoE should not require:
```text
click spell
→ choose AoE mode
→ click shape again
→ click origin
→ click targets individually
→ click spell again
→ resolve
```

Preferred:
```text
click AoE action/spell
→ template placement mode starts automatically
→ aim/place once
→ preview targets
→ confirm
→ resolution modal
```

For shape variants:
```text
only ask for shape if the action genuinely supports multiple shapes
```

#### 10. Long-duration AoEs are different from instantaneous AoEs

The repo already has persistent AoE state:
```text
state.aoes
aoe_move
aoe_remove
remaining_turns
pinned/aura/light metadata
```

Design implication:
```text
/dmcontrol must distinguish:
- instantaneous attack/effect template
- persistent AoE / hazard / aura
```

First monster/NPC combat slice should prioritize instantaneous or immediate resolution effects:
```text
breath weapon
fireball-like sphere
line/cone save effects
```

Persistent AoE editing/moving is more like map/tools or advanced spell behavior and can come later.

### Repo comparison after Pass 7

Status: completed from uploaded repo zip inspection.

#### LAN AoE frontend support

The LAN page already has significant AoE support:

```text
AoE target preview panel:
  assets/web/lan/index.html around 2643

Aimless AoE confirm panel:
  assets/web/lan/index.html around 2664

Resolve Spell (AoE) modal:
  assets/web/lan/index.html around 2779

AoE options:
  assets/web/lan/index.html around 3476
  shapes include line, sphere, cube, cone

AoE state variables:
  pendingAoePlacement
  aoeAimGuide
  aoeDragging
  aoeDragPreview
  aoeDragPending
```

Important functions:

```text
renderAoeOverlay(aoe, options = {})
  supports circle/sphere/cylinder, line/wall, square/cube, cone

hitTestAoe(p)
  supports click/hit testing for AoEs

aoeContainsGridPoint(aoe, point)
  shape containment helper

updateAoeTargetPreviewPanel(previewAoe)
  target preview panel for allies/enemies

computeAoePlacementAimGuide()
  computes blocked/out-of-range/invalid guide data

getPendingAoePlacementPreview()
  builds current preview AoE

startSpellTargetingSession()
  handles spell target sessions
```

#### LAN backend AoE support

Backend functions indicate existing AoE lifecycle support:

```text
_handle_cast_aoe_request()
_lan_auto_resolve_cast_aoe()
_lan_compute_included_units_for_aoe()
_map_spell_effect_targets()
_handle_aoe_move_request()
_handle_aoe_remove_request()
```

`map_state.py` stores persistent AoE objects:
```text
aoes
aoe upserts/removals
```

#### Monster capability AoE support

`MonsterCapabilityService` has area metadata helpers:
```text
_area_metadata_for_capability()
target_mode area_manual
multi_target_capable
area metadata with shape/range/size
```

Current overlay examples:
```text
Adult Red Dragon Fire Breath:
  shape cone
  size 60
  recharge 5
  save_ability action

Adult Red Dragon Frightful Presence:
  radius metadata
  save_ability
```

This means `/dmcontrol` has enough existing ingredients to eventually map monster save/AoE capabilities into LAN-style AoE preview and resolution.

#### Current gaps

```text
1. LAN AoE code is large and player/spell-oriented; it should be adapted carefully, not copied blindly.
2. Monster capability AoE metadata is thinner than spell preset data.
3. Some shapes are represented as circle/sphere/cylinder or square/cube, but exact D&D 2024 Emanation support is not clearly first-class.
4. Persistent AoE support exists, but monster breath/instant effects should not automatically become persistent map objects.
5. Cover/LoS and origin rules may be advisory depending on current backend reliability.
6. Manual include/exclude of affected targets is not clearly final/polished.
```

### Recommended `/dmcontrol` AoE model

First implementation model:

```text
select AoE/save action card
→ /dmcontrol enters template placement mode
→ source/origin and range are shown
→ template preview follows cursor or actor-facing direction
→ affected target preview updates live
→ DM confirms target set
→ resolution modal opens with save outcomes
→ Apply Results mutates combat state
```

Shape-specific first support priority:
```text
1. Cone / Line breath weapons
2. Sphere / Circle targeted AoEs
3. Cube / Square
4. Emanation / source-attached effects
5. Cylinder / elevation-aware effects
```

Initial resolution:
```text
manual save success/failure rows
average or rolled damage
half damage on success when data exists
conditions/effects only if backend already supports them safely
```

### Explicitly deferred

```text
- full Total Cover authority for every shape
- exact 3D/elevation cylinder handling
- persistent hazard/aura editing in first combat slice
- manual include/exclude polish beyond basic target list
- freeform template drawing
- multiple-origin effects
- moving persistent AoEs after cast
- automated spell slot/resource spending for monster spells if not already safe
- exact Emanation origin-inclusion toggle
```

### Implications for `/dmcontrol`

Concrete design rules to carry forward:

```text
1. AoE uses visible template preview on /dmcontrol map.
2. Shape + origin are required, not optional details.
3. Affected targets preview before resolution.
4. Confirm target set before opening/applying resolution.
5. Do not apply damage/effects immediately on template placement.
6. Breath weapons should be first-class cone/line flows.
7. Emanation must be distinguished from Sphere, even if initially advisory.
8. Persistent AoEs/hazards are separate from instantaneous combat AoEs.
9. Use LAN AoE code as the implementation reference.
10. Avoid redundant AoE click chains.
```

### Open questions for later spec

```text
- Should first /dmcontrol AoE support only cone/line/sphere before cube/cylinder/emanation?
- Should manual include/exclude be in first AoE slice or follow-up?
- Should AoE template placement use actor facing by default?
- Should the DM be able to rotate cones/lines with mouse movement, keyboard, or both?
- Should /dmcontrol create persistent AoE map objects or use transient previews unless duration is non-instant?
- Should cover/LoS warnings block resolution or remain advisory?
- How much of existing LAN AoE code can be shared without importing player-only assumptions?
```

## Pass 8 — Movement UX for split movement

Status: completed.

Research target:
```text
Clear movement remaining and drag/drop behavior.
```

Questions:
```text
How do VTTs visualize remaining movement?
How do they handle split movement around actions?
How do they handle invalid movement?
How do they handle difficult terrain/opportunity attacks/occupied cells?
Should GM movement be less restrictive than player movement?
```

### Sources consulted

Official / rules-facing sources:
- Roll20 D&D 2024 Combat rules
- Roll20 D&D 2024 Rules Definitions
- D&D Beyond community/rules discussions treated as lower authority context only
- RPG StackExchange 2025 movement discussion treated as context, not primary authority

VTT / implementation-context sources:
- Foundry VTT Ruler API documentation
- Foundry VTT Game Controls documentation
- Foundry VTT Drag Ruler package documentation
- Roll20 Dynamic Lighting Page Settings / Restrict Movement documentation
- Roll20 dynamic lighting token movement discussions

Repo sources:
- `assets/web/lan/index.html`
- `dnd_initative_tracker.py`
- `map_state.py`

### Findings

#### 1. D&D explicitly supports split movement

The D&D 2024 combat rules state that you can break up movement before and after an action, Bonus Action, or Reaction on the same turn. Roll20’s 2024 rules definitions also state that if a feature such as Extra Attack gives more than one attack as part of the Attack action, the creature can use some or all movement between those attacks.

Design implication:
```text
/dmcontrol must support split movement.
```

The UI cannot assume:
```text
move once, then action, then turn ends
```

Instead:
```text
move → action → move → child attack → move → bonus action → end turn
```

must be possible where legal/DM-approved.

#### 2. Movement remaining must stay visible throughout the turn

Because movement can be split across the entire turn, `/dmcontrol` should continuously show:
```text
speed
movement used
movement remaining
current path cost while dragging
```

This should appear in the LAN-like bottom/control bar, not only on the map.

Recommended display:
```text
Movement: 15 / 30 ft remaining
```

or:
```text
Moved 15 ft · 15 ft left
```

The key is that movement state remains visible while actions, multiattack, and resolution flows happen.

#### 3. Movement range should appear automatically for the active DM-controlled actor

Foundry’s Drag Ruler module shows a ruler while dragging a token and colors spaces depending on token speed. Foundry’s Game Controls include token drag movement controls, distance ruler toggles, waypoints, vertical movement, unconstrained movement, and cycling movement method.

Design implication:
```text
/dmcontrol should show movement affordances automatically when the current actor is a monster/NPC.
```

This should not require the DM to select a movement tool each turn.

Initial target behavior:
```text
current monster/NPC turn starts
→ movement range overlay appears
→ dragging token previews path/cost
→ drop attempts movement
```

#### 4. Invalid movement should reject/snap back and preserve movement

Roll20’s Dynamic Lighting "Restrict Movement" documentation says movement restriction prevents player-controlled tokens from crossing Dynamic Lighting barriers and uses token bounding boxes to block movement through barriers. Foundry’s Ruler API includes a `moveToken()` result indicating whether movement was successfully handled.

Design implication:
```text
/dmcontrol should treat movement as tentative until backend accepts it.
```

Expected UX:
```text
drag token
→ preview path/cost
→ drop token
→ backend validates
→ if valid: token moves and movement remaining updates
→ if invalid: token returns to original square and movement is not spent
→ non-intrusive warning appears
```

Do not spend movement on invalid drag.

#### 5. Waypoints are useful, but not first-slice mandatory

Foundry’s ruler API tracks waypoints along a measured path, and Foundry controls support placing ruler waypoints. This is useful for tactical pathing around corners, difficult terrain, or complex maps.

First `/dmcontrol` movement slice can likely start with current LAN path/movement behavior. Later:
```text
waypoint movement
path preview
drag path around obstacles
```

should be added if the current LAN model lacks it.

#### 6. GM override should exist but not be the normal path

Foundry exposes unconstrained movement as a control, and Roll20 GM-level movement can bypass player restrictions depending on permissions/settings. For D&D DMs, override is necessary because:
```text
teleportation
forced movement
special monster rules
manual correction
table rulings
```

Design implication:
```text
/dmcontrol normal movement should validate and spend movement.
DM override should be explicit and visually distinct.
```

Recommended:
```text
Normal mode:
  validates movement, spends movement, blocks/snapbacks invalid

Override mode:
  requires toggle/confirmation
  visually marked
  does not pretend to be normal movement
  maybe lives in /dm Toolbox or a guarded /dmcontrol override drawer
```

Do not make override the default.

#### 7. Difficult terrain and occupied squares need careful treatment

The first `/dmcontrol` movement implementation should use existing LAN/backend movement cost logic rather than invent new movement rules.

Design questions for later:
```text
Does the current backend include difficult terrain?
How are hazards/structures/blocked cells represented?
Are occupied enemy/friendly cells passable?
Can two creatures share a square?
How are forced movement and teleport handled?
```

User preference context:
```text
normal movement should respect walls/obstructions
two creatures on the same square may be allowed in some cases
physics/object rules are WIP
DM override belongs behind explicit controls
```

#### 8. Opportunity attacks should be advisory/deferred

Movement through threatened spaces is tactically important but hard to automate safely because it depends on creature reactions, reach, visibility, conditions, and DM rulings.

Design implication:
```text
Do not block movement due to opportunity attacks in the first /dmcontrol movement slice.
```

Future:
```text
show advisory warning: “May provoke opportunity attack”
log suggestion
allow DM to resolve manually
```

But first implementation should focus on:
```text
distance/cost
blocked movement
remaining movement
snapback
```

#### 9. Movement must coexist with Multiattack and modals

Because movement can occur between child attacks, Multiattack sequence UI must not trap movement.

Recommended behavior:
```text
Sequence modal/tray remains active
DM can drag active token if not currently in target placement/resolution modal
movement updates remaining movement
sequence state stays active after movement
child target/resolution can continue
```

If a modal blocks the map, movement can require closing/cancelling that modal first. But the sequence state itself should not prevent movement.

#### 10. Do not create redundant movement click chains

Avoid:
```text
click Move
→ select token
→ drag token
→ confirm move
→ confirm again
```

Preferred:
```text
active monster turn
→ movement overlay already visible
→ drag token
→ drop
→ backend validates
→ update or snapback
```

Confirmation should only be needed for override/illegal movement, not normal movement.

### Repo comparison after Pass 8

Status: completed from uploaded repo zip inspection and prior LAN anchors.

#### LAN movement support already exists

Known anchors:

```text
getMovementRangeCostMap()
  assets/web/lan/index.html around 10879

movementCostMap()
  assets/web/lan/index.html around 14094

draw() movement range overlay
  assets/web/lan/index.html around 14529

canvas pointerdown/pointerup movement flow
  assets/web/lan/index.html around 18525 and 18877

_lan_try_move()
  dnd_initative_tracker.py around 43514
```

The LAN page already has the correct high-level movement model for `/dmcontrol`:
```text
map-first movement
range/cost overlay
drag/drop movement
backend validation
movement remaining updates through snapshot/state
```

#### Backend movement support

`_lan_try_move()` is the likely backend reference for:
```text
actor identity
destination cell
movement validation
state update
movement cost
error handling
snapshot response
```

For `/dmcontrol`, the first implementation should reuse/adapt this path where possible rather than creating separate DM-only movement logic.

#### Current `/dm` map movement should not be the implementation model

The current `/dm` Monster Pilot / DM movement path was part of the UI the user rejected:
```text
dropdown-based
clunky
not LAN-like
wrong page for active play
```

Do not build `/dmcontrol` from Monster Pilot.

#### Needed `/dmcontrol` movement model

```text
current monster/NPC actor
→ active token on /dmcontrol map
→ movement range visible
→ drag/drop token
→ backend validates with LAN-style movement path
→ valid move consumes movement
→ invalid move snaps/rejects and leaves movement unchanged
→ remaining movement stays visible in control bar
```

### Recommended `/dmcontrol` movement model

First implementation slice:
```text
1. Show current actor movement remaining.
2. Show movement range overlay automatically on current monster/NPC turn.
3. Allow drag/drop current actor token.
4. Submit movement through adapted LAN movement backend path.
5. Update snapshot/remaining movement after success.
6. Snap/reject invalid movement without spending movement.
7. Show non-intrusive error toast/status.
```

Second slice:
```text
1. Movement during Multiattack sequence remains supported.
2. Movement path preview cost while dragging.
3. Difficult terrain/hazard display if already supported.
4. Explicit DM override toggle.
```

Later:
```text
1. Waypoints.
2. Opportunity attack advisory.
3. Forced movement.
4. Teleport movement.
5. Physics/object interactions.
6. Occupied-square advanced rules.
```

### Explicitly deferred

```text
- opportunity attack automation
- authoritative difficult-terrain overhaul if not already in LAN backend
- movement waypoints if LAN does not already support them
- forced movement workflow
- teleport workflow
- physics/crates/pushing objects
- automatic reaction prompts
- exact monster-specific movement modes beyond current speed data
- elevation/vertical movement beyond current map support
```

### Implications for `/dmcontrol`

Concrete design rules to carry forward:

```text
1. Split movement is required.
2. Movement remaining must stay visible throughout the turn.
3. Movement range should appear automatically for current monster/NPC.
4. Drag/drop is the normal movement input.
5. Normal movement should not require extra confirmation.
6. Invalid movement snaps/rejects and does not spend movement.
7. Backend should validate movement through LAN-style path.
8. DM override is explicit, not default.
9. Opportunity attacks are advisory/deferred.
10. Multiattack sequence must not block legal movement between child attacks.
```

### Open questions for later spec

```text
- Does current LAN movement already account for difficult terrain, hazards, structures, and occupied cells?
- Should /dmcontrol include a visible movement path/cost label while dragging from the first slice?
- Where should DM override live: /dmcontrol control bar, /dm Toolbox, or both?
- Should forced movement and teleport use separate modes from normal movement?
- How should movement reset at turn boundaries for monsters/NPCs?
- How should mounts, flying, burrowing, swimming, and climbing be represented initially?
- Should /dmcontrol support waypoints in the first movement milestone if LAN already has ruler waypoints?
```

## Pass 9 — Resolution modal UX

Status: completed.

Research target:
```text
Fast but safe adjudication.
```

Questions:
```text
What should the modal show before applying results?
How are attack roll, hit/miss/crit, save success/failure, damage, and riders represented?
How should manual dice vs app dice be toggled?
How can blank damage auto-roll safely?
How are multiple targets handled without clutter?
```

### Sources consulted

Official / rules-facing sources:
- D&D Beyond Basic Rules 2024 — "How to Use a Monster"
- D&D Beyond Basic Rules 2024 — "Playing the Game" / Saving Throws
- D&D Beyond forum context on 2024 DMG monster critical-hit advice, treated as lower-authority context where it quotes/paraphrases DMG advice

VTT / implementation-context sources:
- Fantasy Grounds 5E Combat Tracker documentation
- Foundry VTT package docs for Damage Application
- Foundry VTT Minimal Rolling Enhancements package docs
- Foundry/Reddit context on chat damage buttons, treated as low-authority UX context only
- Roll20 general automation positioning and macro/targeting patterns from earlier passes

General UX sources:
- Nielsen Norman Group — Modal & Nonmodal Dialogs
- Nielsen Norman Group — Confirmation Dialogs Can Prevent User Errors
- Nielsen Norman Group — Preventing User Errors
- Nielsen Norman Group — Dangerous UX: Consequential Options Close to Benign Options
- Baymard Institute — Users Continue to Double-Click Online
- Baymard Institute — Button Design / disabled/loading states

Repo sources:
- `assets/web/lan/index.html`
- `assets/web/dm/index.html`
- `dnd_initative_tracker.py`
- `monster_capability_service.py`

### Findings

#### 1. Resolution deserves a modal because it mutates combat state

Nielsen Norman Group says modal dialogs are appropriate when the user's attention must be directed to important information, but they interrupt workflow and should be used carefully. Applying damage, conditions, resource use, or action results is exactly the kind of state-changing step that deserves focused confirmation.

Design implication:
```text
/dmcontrol should use modals for state-mutating resolution.
```

Action targeting can happen on the map/control bar, but final application should be a deliberate modal:
```text
selected action
selected target(s)
outcome/damage/effects
Apply / Cancel
```

Do not make normal targeting itself modal unless necessary.

#### 2. Confirmation should be reserved for meaningful state changes

NNG also warns not to overuse heavy confirmation dialogs; confirmation is most useful for serious or hard-to-reverse actions. In `/dmcontrol`, applying HP damage/conditions/resources is meaningful enough to confirm. Selecting an action or previewing targets is not.

Design implication:
```text
Preview/targeting should be lightweight.
Apply Results should be explicit and confirmed.
```

Avoid:
```text
confirmation on every harmless preview click
```

Require:
```text
confirmation before backend mutation
```

#### 3. Average damage and roll formulas both need first-class support

The 2024 "How to Use a Monster" guidance says stat blocks usually provide both a number and a die expression for each damage instance, and the DM chooses either the number or the die expression, not both.

Design implication:
```text
Resolution modal must support:
- average damage
- rolled/formula damage
```

The existing LAN behavior where leaving damage blank can auto-roll from formula is good and should be preserved/adapted.

Recommended UI:
```text
Damage:
  [ input ]
  if blank: Auto-roll 1d8+4
  [Use Average 8] [Roll Formula]
```

This makes the auto behavior visible and avoids surprising the DM.

#### 4. Critical hits need explicit handling

The 2024 DMG context around monster critical hits indicates that if the DM uses average monster damage, critical hits can add the rolled damage dice to the average damage. This is not the same as simply doubling the average number.

Design implication:
```text
Critical hit handling must be explicit.
```

Resolution modal should show:
```text
Outcome: Hit / Miss / Critical
Damage mode: Average / Roll / Manual
Critical damage note or preview
```

First implementation can be manual/advisory:
```text
Critical selected → show “critical damage adjustment required” if formula support is not ready.
```

Do not silently apply the wrong critical formula.

#### 5. Attack and save resolutions need different rows

Attack resolution row:
```text
Target
AC
Attack bonus
Roll / manual total if available
Outcome: Miss / Hit / Critical
Damage input / formula / average
Riders/effects if supported
```

Save resolution row:
```text
Target
Save ability
DC
Manual save result or app roll
Outcome: Success / Failure / No Effect
Damage/effect on fail
Damage/effect on success
```

The 2024 rules-facing monster guidance identifies save ability, DC, affected creatures, and failure/success result. That should be visible in the save resolution modal.

Do not force save effects through attack hit/miss UI.

#### 6. Multiple targets require a compact table, not one giant card per target

Fantasy Grounds applies attacks/damage through targeted creatures in the Combat Tracker, and damage rolls can be targeted/dropped onto targets. Foundry damage-application tools add apply damage/healing buttons to chat results for selected tokens. The common pattern is:
```text
selected targets
→ row/list of targets
→ apply result(s)
```

For `/dmcontrol`, multiple target resolution should use a compact target table:
```text
Target | Outcome | Damage | Notes
```

For AoE:
```text
bulk controls:
  all fail
  all success
  roll all saves
  apply average damage
  clear outcomes
per-target overrides:
  each row can be changed manually
```

This keeps the modal from getting huge.

#### 7. Manual and app-rolled dice should coexist

The user wants both physical/manual dice and app automation depending on preference. Prior design context says automation should be configurable per roll type later.

Recommended first model:
```text
Manual entry always available.
App roll available when formula/DC data is present.
Blank damage auto-roll can remain as LAN behavior, but the modal should explain it.
```

Future:
```text
Automation settings:
  attack rolls app/manual
  damage app/manual
  saving throws app/manual
  per-roll override
```

For first `/dmcontrol`, do not block manual play behind automation.

#### 8. Double-submit prevention is mandatory

Baymard notes that users double-click online and recommends disabling the button immediately after click, ideally with feedback/spinner. This directly applies to "Apply Results."

Design implication:
```text
Resolution modal must prevent duplicate apply.
```

Required:
```text
in-flight state
Apply disabled while request pending
visible “Applying…” state
backend idempotency if possible later
Cancel disabled or safe while applying
error re-enables buttons
```

This was already learned in the `/dm` Resolution Tray hardening and should carry forward.

#### 9. Consequential actions should be visually separated from cancel/benign actions

NNG warns that consequential options close to benign options cause errors, and recommends separating confirmatory/destructive actions with redundant visual signals.

Design implication:
```text
Apply Results and Cancel should not be cramped together as identical buttons.
```

Recommended modal footer:
```text
left: Cancel / Back
right: Apply Results
warning text near Apply:
  “Apply Results will update combat state.”
```

For severe/large effects:
```text
Apply 8 target results
```

Button label should describe the consequence.

#### 10. Error handling should preserve recoverability

NNG’s error-prevention guidance recommends warning before errors and helping users recover. In `/dmcontrol`, backend resolution can fail for stale targets, missing actor, unsupported action, or validation issues.

Recommended:
```text
show clear inline error in modal
preserve selected targets/outcomes
allow retry or cancel
do not clear the modal on failure
do not leave controls permanently disabled
```

#### 11. Redundant click chains must stay forbidden

Resolution flow should not ask the DM to repeat choices already made.

Avoid:
```text
click action
→ click target
→ modal asks to choose target again
→ click roll
→ click apply
```

Preferred single-target attack:
```text
click action
→ click target
→ resolution modal opens with target already selected
→ choose/confirm outcome/damage
→ Apply Results
```

Preferred AoE:
```text
place template
→ confirm affected targets
→ resolution modal opens with rows already populated
→ choose/roll outcomes
→ Apply Results
```

### Repo comparison after Pass 9

Status: completed from uploaded repo zip inspection and prior LAN anchors.

#### LAN resolution modal support

Known LAN anchors:

```text
attackResolveModal HTML
  assets/web/lan/index.html around 2730

openAttackResolveModal()
  assets/web/lan/index.html around 12757

attack target click flow
  assets/web/lan/index.html around 19003-19131

Resolve Spell (AoE) modal
  assets/web/lan/index.html around 2779
```

The LAN attack flow already supports the desired pattern:
```text
action/range mode
→ target click
→ modal resolution
→ backend command
```

This is the right implementation reference for `/dmcontrol`.

#### `/dm` prototype resolution support

The `/dm` Focused Actor prototype already produced useful reusable ideas:
```text
Resolution Tray
manual outcome controls
Apply/Cancel behavior
in-flight guards
backend endpoint reuse
error preservation
sequence child completion
```

Reusable:
```text
state hardening
error/in-flight behavior
manual outcome rows
resolve-targets endpoint usage for monster capabilities
```

Not final as-is:
```text
placement in /dm Focused Actor panel
map-click target path on /dm
tray instead of LAN-like modal
```

#### Backend resolution paths

Existing backend paths likely relevant:

```text
LAN/player attack:
  attack_request command path
  _adjudicate_attack_request

Monster capability:
  /api/dm/monster-capabilities/${cid}/execute
  /api/dm/monster-capabilities/${cid}/resolve-targets
```

Potential `/dmcontrol` approach:
```text
For overlay-backed monster capabilities:
  use monster capability execute/resolve-targets backend.

For LAN-like weapon attacks if actor has weapon/action data:
  adapt or reuse the attack_request adjudication path where safe.
```

Important caveat:
```text
Do not create a third parallel resolution backend if existing paths can be adapted.
```

#### Repo gaps

```text
1. LAN attack modal is player-oriented and may assume claimed PC/player command context.
2. Monster capability resolution is DM-oriented but currently tied to /dm prototype/legacy flows.
3. A clean /dmcontrol frontend needs to bridge LAN-style UI to DM/monster backend semantics.
4. Critical hit + average damage behavior should be verified before automating.
5. Multi-target save/AoE resolution should not be crammed into the single-target attack modal.
```

### Recommended `/dmcontrol` resolution models

#### Single-target attack modal

```text
Header:
  Actor uses Action Name

Summary:
  attack bonus
  target AC
  reach/range
  damage formula + average

Controls:
  Outcome: Miss / Hit / Critical
  Damage: manual input
  Buttons: Use Average, Roll Formula
  Optional: blank means auto-roll formula, clearly explained

Footer:
  Cancel
  Apply Results
  safety text: “Apply Results will update combat state.”
```

#### Save / AoE modal

```text
Header:
  Actor uses Action Name

Summary:
  Save DC
  save ability
  area shape/range
  damage/effect summary

Target table:
  target
  save outcome: Success / Failure / No Effect
  damage/effect column
  notes

Bulk controls:
  roll all saves, if automation enabled
  all success
  all failure
  use average damage

Footer:
  Cancel
  Apply Results
```

#### Multiattack child modal

```text
Parent sequence visible behind or in compact header:
  Multiattack — Bite 0/1, Claw 1/2

Child resolution modal:
  same as single-target attack or save modal

After Apply:
  returns to sequence
  marks child complete exactly once
```

### Explicitly deferred

```text
- full automated saving throw rolls for all targets
- global automation settings UI
- authoritative critical-hit average-damage formula if not verified in backend
- applying complex rider conditions that lack backend support
- undo after Apply Results
- batch multiattack resolution
- reaction/legendary action resolution mode
- concentration automation
- spell slot/resource automation unless backend already safely supports it
```

### Implications for `/dmcontrol`

Concrete design rules to carry forward:

```text
1. Resolution should be modal because it mutates combat state.
2. Targeting/preview should remain lightweight and non-modal where possible.
3. Apply Results must be explicit.
4. Cancel must always be available before mutation.
5. Damage modal must support average, formula roll, and manual input.
6. Save and attack resolution require different row/control models.
7. Multi-target resolution needs compact tables and bulk controls.
8. Double-submit prevention is required.
9. Backend errors should preserve modal state for retry/cancel.
10. Avoid redundant click chains.
11. Do not create a third backend resolution path if existing LAN/monster-capability paths can be adapted.
```

### Open questions for later spec

```text
- Should blank damage auto-roll by default for monsters, or should that be behind an automation setting?
- Should critical damage use average + dice, doubled dice, or backend-calculated rules depending on edition setting?
- Should Apply Results support undo, or is battle-log/manual correction enough initially?
- Which backend path should /dmcontrol first use for normal monster attacks: monster capabilities or LAN attack_request?
- Should single-target attacks open modal immediately after target click, or allow a one-target tray first?
- Should save/AoE bulk controls be included in the first AoE slice?
- Should damage/effects be previewed in the battle log before Apply?
```

## Pass 10 — GM override model

Status: completed.

Research target:
```text
How much should a DM control surface enforce rules vs assist?
```

Questions:
```text
Should out-of-range actions be blocked or warned?
Should invalid movement be blocked or overrideable?
Where should override live?
How do tools avoid fighting the DM during unusual table situations?
```

### Sources consulted

VTT / implementation-context sources:
- Foundry VTT Game Controls documentation
- Foundry VTT Tokens documentation
- Foundry VTT Users and Permissions documentation
- Foundry VTT Ruler API documentation
- Foundry VTT Token Movement package documentation
- Foundry VTT Not Your Turn package documentation
- Foundry VTT Movement Approval package documentation
- Roll20 Page Settings for Dynamic Lighting / Restrict Movement documentation
- Roll20 community/forum context on movement restriction
- Fantasy Grounds 5E Effects / Combat Tracker documentation and manual damage forum context

General UX sources:
- Nielsen Norman Group — 10 Usability Heuristics
- Nielsen Norman Group — User Control and Freedom
- Nielsen Norman Group — Preventing User Errors / slips
- Nielsen Norman Group — Confirmation dialogs / consequential actions
- Baymard Institute — double-click prevention / loading states, from previous pass

Repo sources:
- `assets/web/lan/index.html`
- `assets/web/dm/index.html`
- `dnd_initative_tracker.py`
- `map_state.py`

### Findings

#### 1. DM override is necessary, but should be explicit

VTTs usually distinguish normal player-permission movement/control from GM-level control. Foundry’s permissions model lets the GM configure how much restriction users have, and Foundry controls expose advanced movement options such as unconstrained movement. Roll20’s Restrict Movement blocks player-controlled tokens from crossing Dynamic Lighting barriers, while GM-level workflows/settings can still manage the map.

Design implication:
```text
/dmcontrol should have normal assisted/rule-aware operation by default,
with an explicit DM override mode for unusual table situations.
```

Override should never be ambiguous. When active, it should be visibly marked.

#### 2. Warnings are better than hard blocks for table-ruling ambiguity

D&D has too many exceptions for every rule to be hard-blocked:
```text
special monster traits
homebrew rules
temporary effects
DM rulings
rule-of-cool moments
hidden/unknown map facts
forced movement
teleportation
manual corrections
```

NNG’s error-prevention guidance recommends using constraints and suggestions to prevent slips, but also staying flexible. That maps well to:
```text
warn first
block only technical impossibilities
provide explicit override for DM-authorized exceptions
```

Recommended:
```text
Out of range:
  warn and require confirm/override

Potential LoS/cover issue:
  advisory warning, DM decides

Occupied square ambiguity:
  warn/advisory unless backend has authoritative rule

Wall/blocked geometry:
  normal move rejects
  override mode can force if needed

No target selected for target-required action:
  block until target is selected
```

#### 3. Technical impossibilities should still block by default

Some actions are not "rules disagreements"; they are invalid UI/state problems:
```text
no actor selected
actor no longer exists
action id missing
target no longer exists
backend rejects movement
resolution already applying
```

These should block and show clear error messages, not allow override in the same flow.

Design implication:
```text
Override is for DM rulings, not broken state.
```

If backend state is stale, refresh/retry/cancel is safer than allowing a forced mutation.

#### 4. Override should be visually and procedurally separate

NNG’s user-control guidance emphasizes visible exits and undo/cancel affordances; NNG’s consequential-action guidance warns against placing dangerous actions too close to benign ones. Therefore override controls should not live beside normal attack/apply buttons as identical buttons.

Recommended override placement:
```text
/dmcontrol:
  compact Override toggle/drawer for active-turn exceptions
  visually marked when enabled
  confirmation for forced actions

/dm Toolbox:
  broader admin overrides and repairs
  HP overrides
  force movement
  remove combatants
  set initiative
  debug/legacy tools
```

Do not put override as the default path.

#### 5. Movement override should be separate from normal drag movement

Normal `/dmcontrol` movement:
```text
drag/drop active token
backend validates
movement spent on success
snap/reject on invalid
```

Override movement:
```text
toggle Override Movement
drag/drop or choose destination
confirmation: Force move without normal validation?
state clearly marked as override
log as override/manual if applied
```

This follows the distinction seen in VTTs between normal restricted movement and GM/advanced movement controls.

#### 6. Target override should allow DM exceptions without destroying the fast path

Normal targeting:
```text
valid target highlight
invalid target warning
click valid target → resolution modal
```

Override targeting:
```text
out-of-range/blocked target can be added with warning/confirm
tray marks target as override/advisory
resolution modal shows “override target”
battle log can record manual/override context later
```

Do not:
```text
hard-block every out-of-range or unknown target
silently accept invalid target as normal
```

#### 7. Damage/effect override belongs in resolution modal or /dm Toolbox

Resolution modal should support manual damage entry and manual outcome selection by default. That is not "override"; it is normal DM adjudication.

True override includes:
```text
apply custom damage not tied to action
apply/remove condition manually
force resource state
manual HP/temp HP changes
```

Those are better in `/dm` Toolbox Overrides or a guarded `/dmcontrol` override drawer, not the primary action flow.

#### 8. Override must be logged or at least visibly labeled

If the DM overrides normal validation, the app should not pretend automation did it.

Recommended:
```text
toast/status: Override applied
battle log later: Manual override / Forced movement / Out-of-range target allowed
```

First implementation can show UI labeling; battle-log polish can follow.

#### 9. Cancel/escape must always exist before mutation

NNG's user-control heuristic says users need a clearly marked emergency exit to leave an unwanted action without an extended process. `/dmcontrol` should provide:
```text
Escape cancels target/placement/preview mode
Cancel closes resolution modal before apply
End/Cancel Sequence exits multiattack sequence
Cancel Override exits override mode
```

Once Apply Results mutates state, correction may need separate manual tools. Before Apply, exiting should be easy.

#### 10. Do not fight the DM, but do not hide uncertainty

The key balance:
```text
assistive validation
clear warnings
explicit override
recoverable errors
safe defaults
```

The app should say:
```text
Likely out of range — DM override required
Template may be blocked by cover — advisory, DM decides
Invalid move — blocked by wall
```

Rather than:
```text
No, impossible
```

or:
```text
Sure, everything is fine
```

### Repo comparison after Pass 10

Status: completed from uploaded repo zip inspection and prior anchors.

#### Current LAN support

LAN already has good normal-mode behavior:
```text
movement validation path
invalid/rejected movement behavior
range/target overlays
attack/spell targeting modes
resolution modals
toasts/status feedback
```

This should be the baseline for `/dmcontrol`.

#### Current `/dm` override tools

Current `/dm` already has or recently moved administrative override controls into DM Toolbox:
```text
HP adjustment
Temp HP
Set Initiative
Remove Combatant
Add Custom Combatant
Session tools
```

These should remain `/dm` toolbox/admin functions, not normal `/dmcontrol` flow.

#### Current rejected UI

The old `/dm` Monster Turn Controls / Monster Pilot were rejected because they are dropdown-heavy and unintuitive. They should not be reused as override design.

Do not:
```text
build override as another dropdown stack
hide override inside the old Monster Pilot UI
make normal /dmcontrol control depend on legacy controls
```

#### Needed `/dmcontrol` override support

First `/dmcontrol` override should be minimal:
```text
visible Override toggle/drawer
out-of-range target override confirmation
force movement later or via /dm Toolbox first
manual damage already available in resolution modal
```

Broader override should stay in `/dm`:
```text
force HP/conditions
force initiative
force token placement
debug tools
legacy fallback controls if preserved
```

### Recommended `/dmcontrol` override model

Default mode:
```text
rule-aware assistive UI
valid target/movement previews
warnings for uncertain/invalid choices
backend validation
```

Soft override:
```text
DM can confirm out-of-range/advisory target
target/result marked as override
does not require admin toolbox
```

Hard override:
```text
force token placement
force HP/condition/resource state
bypass movement validation
debug/repair
```

Hard override should live in:
```text
/dm Toolbox primarily
or a guarded /dmcontrol Override drawer later
```

Visual treatment:
```text
override toggle is visually distinct
override state has a banner/badge
forced actions require confirmation
override exits are obvious
```

Logging:
```text
normal actions log normally
override actions should be labeled as manual/override when battle-log polish exists
```

### Explicitly deferred

```text
- full override audit log
- undo system after Apply Results
- full force-movement workflow
- physics/object override
- blanket bypass-all-rules mode
- complex permissions model
- opportunity attack automation/override
- hard LoS/cover authority for every action
- override hotkeys
```

### Implications for `/dmcontrol`

Concrete design rules to carry forward:

```text
1. Default /dmcontrol behavior is assistive/rule-aware, not override.
2. DM override exists but is explicit and visually marked.
3. Warn before allowing ambiguous invalid choices.
4. Block broken/stale UI state rather than overriding it.
5. Normal movement validates and spends movement; forced movement is separate.
6. Target override is allowed with warning/confirmation.
7. Manual outcome/damage in resolution modal is normal adjudication, not override.
8. Admin repairs belong in /dm Toolbox.
9. Escape/Cancel must remain available before mutation.
10. Override actions should be labeled/logged when practical.
```

### Open questions for later spec

```text
- Should /dmcontrol first include only soft target override, leaving movement override to /dm Toolbox?
- Should out-of-range target override require a modal confirmation or a persistent override toggle?
- Should hard override ever be available on /dmcontrol, or only through /dm Toolbox?
- Should override state persist for one action, one turn, or until manually toggled off?
- Should override application write special battle-log text in first version?
- Should override require an extra confirmation before Apply Results?
```

## Pass 11 — Two-screen DM workflow

Status: completed.

Research target:
```text
Dashboards/control surfaces split across monitors.
```

Questions:
```text
How should /dm and /dmcontrol link to each other?
What information should be duplicated on /dmcontrol vs only shown on /dm?
What should remain visible if the DM has /dm on monitor 1 and /dmcontrol on monitor 2?
```

### Sources consulted

VTT / tabletop sources:
- Foundry VTT PopOut! module documentation
- Foundry VTT Popout Resizer module documentation
- Foundry VTT GM Screen module documentation
- Roll20 forum discussions on multiple monitors, pop-out character sheets, pop-out chat, and multiple browser windows
- D&D Beyond forum discussion on DM view vs player view / two outputs
- Reddit / community context on VTT two-screen setups, treated as lower-authority context

General workflow / dashboard sources:
- Pencil & Paper dashboard UX best practices
- Smashing Magazine real-time dashboard UX strategies
- General multi-monitor workflow guidance, lower-authority context only

Repo sources:
- `assets/web/dm/index.html`
- `assets/web/lan/index.html`
- route definitions in `dnd_initative_tracker.py`

### Findings

#### 1. Multi-window / multi-monitor use is common in VTT workflows

Foundry’s PopOut! module exists specifically to open sheets, applications, and documents in separate windows for easier viewing and multiple-monitor use. Roll20 forum discussions mention multiple browser windows, popped-out character sheets, popped-out chat, and hiding/maximizing UI regions to maximize map real estate. D&D Beyond forum context also describes running one DM view and one player-view window for two outputs.

Design implication:
```text
/dm and /dmcontrol should be designed as separate browser pages that can be open side-by-side.
```

This is not an unusual or exotic workflow. It matches how VTT users already stretch control/reference surfaces across monitors.

#### 2. `/dm` and `/dmcontrol` should link directly, but not depend on each other visually

Recommended:
```text
/dm has "Open DM Control" link/button.
/dmcontrol has "Back to DM Cockpit" link/button.
Both pages can run independently in separate tabs/windows.
```

Do not require:
```text
modal launching
window-management hacks
pop-out-only architecture
```

A plain route/page is more robust:
```text
/dmcontrol
```

#### 3. `/dmcontrol` should duplicate only turn-critical state

Because `/dm` is available as the full reference/cockpit, `/dmcontrol` should not duplicate the full actor sheet.

Duplicate on `/dmcontrol`:
```text
current actor name
current turn/round
HP summary
conditions/status summary
movement remaining
action/bonus/reaction availability where supported
selected action/target/resolution state
important resource/recharge/use badges
```

Keep primarily on `/dm`:
```text
full actor sheet
full stat block/reference text
all combatants overview
session persistence
encounter setup
DM Toolbox
admin overrides
debug
large battle log / deep history
```

This reduces clutter on `/dmcontrol` and avoids rebuilding `/dm` inside it.

#### 4. `/dmcontrol` should be resilient if `/dm` is not visible

Even if the DM expects two monitors, they may switch tabs or temporarily use one screen. `/dmcontrol` should still be usable by itself for the active turn.

Minimum self-contained state:
```text
who am I controlling?
is it my active monster/NPC turn?
what movement remains?
what actions can I take?
what target/resolution mode am I in?
how do I end turn?
```

It should not require glancing at `/dm` to answer those questions.

#### 5. `/dm` remains the overview and reference source of truth

Dashboard UX research emphasizes showing the right information for the task at hand and reducing cognitive overload. Real-time dashboard UX writing describes dashboards as decision assistants that reduce time-to-decision and cognitive load. This maps well to:
```text
/dm = overview/reference/decision context
/dmcontrol = immediate action execution
```

Do not turn `/dmcontrol` into another dashboard full of every available stat. It should answer “what do I do right now with this monster?”

#### 6. Window size / layout should assume desktop, not tablet

The user explicitly does not need DM tablet/touch support. A two-monitor desktop workflow means `/dmcontrol` can afford:
```text
large map area
bottom control bar
modal overlays
keyboard shortcuts
resizable/collapsible panels
```

But it should still work if the window is narrower than expected:
```text
bottom sheet scrolls/collapses
modal remains usable
map remains visible enough to target/move
```

#### 7. Pop-out/resizable concepts support remembering layouts later

Foundry Popout Resizer remembers popout sizes/positions between sessions for toolbar popouts. This is not needed for first `/dmcontrol`, but it suggests a future quality-of-life improvement:
```text
remember /dmcontrol panel sizing
remember bottom sheet height
remember reference map zoom/pan
```

This is later polish, not first implementation.

#### 8. Battle log split

The user wants a detailed D&D combat battle log, with technical/debug logs separate. In a two-monitor model:
```text
/dm can hold the larger battle log/history.
/dmcontrol can show a compact recent-result feed.
```

Recommended:
```text
/dmcontrol:
  last result / recent few events
  enough to confirm the action worked

/dm:
  full battle log
  filters/toggles/history
  technical/debug access in toolbox/debug
```

This keeps `/dmcontrol` focused.

#### 9. Cross-page state should be backend authoritative

Because `/dm` and `/dmcontrol` may be open simultaneously, they must not maintain competing source-of-truth state.

Required:
```text
shared backend snapshot/source of truth
WebSocket or polling updates to both pages
actions on /dmcontrol update /dm
setup/admin on /dm updates /dmcontrol
```

Do not:
```text
create separate /dmcontrol local combat state
fork action/resource state between pages
```

This is especially important for:
```text
initiative/current actor
movement remaining
HP/conditions
target/resolution results
sequence/multiattack state if local only
```

Local UI-only sequence/target state is acceptable for the active page, but authoritative combat state must remain backend.

#### 10. Links/buttons between pages should preserve mental model

Recommended labels:
```text
/dm → Open DM Control
/dmcontrol → DM Cockpit
```

Avoid labels like:
```text
Focused Actor
Pilot
Monster Turn Controls
```

Those names are connected to the rejected/ambiguous `/dm` prototype.

### Repo comparison after Pass 11

Status: completed from uploaded repo zip inspection and prior route anchors.

Current routes:
```text
/           serves LAN index
/planning   serves LAN index
/dm         serves DM console
/dm/map     serves DM map workspace
```

No `/dmcontrol` route/page currently exists.

Likely implementation route:
```text
GET /dmcontrol
assets/web/dmcontrol/index.html
```

Current `/dm` should add:
```text
Open DM Control link/button
```

Current `/dmcontrol` future page should add:
```text
DM Cockpit link/button
```

Existing LAN route should remain unchanged:
```text
/ and /planning
```

### Recommended `/dm` vs `/dmcontrol` information split

`/dm`:
```text
full initiative order
all combatants
full actor sheets/stat references
encounter builder
monster library
session persistence
DM Toolbox
admin overrides
debug tools
large battle log/history
reference/inspection map
```

`/dmcontrol`:
```text
current controlled monster/NPC
turn/round
movement remaining
active map for movement/targeting/AoE
monster/NPC action controls
targeting/resolution modal state
multiattack guided flow
End/Next/Previous turn controls if they fit cleanly
soft override affordance
compact recent result feed
```

Duplicate between both:
```text
current actor name
current turn/round
HP/conditions summary
links to each other
basic connection/status indicator
```

### Recommended first `/dmcontrol` two-screen behavior

First slice:
```text
1. Add /dmcontrol route/page shell.
2. Add link from /dm to /dmcontrol.
3. Add link from /dmcontrol back to /dm.
4. Show current initiative actor and disabled/idle state when it is a PC or no DM-controlled actor.
5. Subscribe/fetch the same backend snapshot as /dm/LAN where practical.
```

Do not first slice:
```text
copy /dm right-side controls
copy /dm toolbox
copy full actor sheet
make /dmcontrol depend on /dm being open
```

### Explicitly deferred

```text
- automatic window spawning/positioning
- remembering multi-monitor layout
- pop-out subpanels
- full battle-log mirror
- separate player-facing display mode
- second-window synchronization UX beyond shared backend state
- browser-local layout persistence
```

### Implications for `/dmcontrol`

Concrete design rules to carry forward:

```text
1. /dm and /dmcontrol are separate pages meant to run side-by-side.
2. /dmcontrol must be usable alone for the active turn.
3. /dmcontrol duplicates only turn-critical information.
4. /dm remains full reference/admin/cockpit.
5. /dmcontrol must not copy /dm UI wholesale.
6. Both pages share backend authoritative state.
7. Links between pages should be simple and explicit.
8. Compact recent-result feed on /dmcontrol; full battle log on /dm.
9. Desktop/two-monitor design is acceptable.
10. Future layout persistence is polish, not first slice.
```

### Open questions for later spec

```text
- Should /dmcontrol use WebSocket subscription from LAN, /dm, or its own small channel?
- Should /dmcontrol show Previous/Next turn in first version or only End Turn?
- Should /dmcontrol compact result feed show last 3 events or only last event?
- Should /dmcontrol link to /dm open in same tab or new tab/window by default?
- Should /dm include an obvious warning that /dmcontrol is the active monster/NPC play page?
- Should /dmcontrol show a small “open /dm for full stat sheet” helper when actor details are missing?
```

## Pass 12 — Accessibility / desktop interaction basics

Status: completed.

Research target:
```text
Practical desktop-only controls for DM use.
```

Questions:
```text
Keyboard shortcuts: Escape cancel, Enter confirm, arrows/tab?
Resizable panels?
Modal focus behavior?
Large click targets?
Scrollable vs collapsible sections?
How to prevent accidental destructive actions?
```

### Sources consulted

Accessibility / UX sources:
- W3C WCAG 2.2 Target Size Minimum
- WAI-ARIA Authoring Practices — Modal Dialog Pattern
- W3C HTML technique H102 — modal dialogs with the HTML dialog element
- Nielsen Norman Group — 10 Usability Heuristics
- Nielsen Norman Group — User Control and Freedom
- Nielsen Norman Group — Confirmation Dialogs Can Prevent User Errors
- Nielsen Norman Group — Preventing User Errors
- Nielsen Norman Group — Dangerous UX: Consequential Options Close to Benign Options
- Baymard Institute — Users continue to double-click online
- Baymard Institute button/design guidance from previous pass context

VTT / implementation-context sources:
- Foundry VTT Game Controls documentation
- Foundry VTT Measurement and Templates documentation
- Foundry keyboard shortcut references and module context, lower-authority
- Prior Roll20 / Foundry / Fantasy Grounds research from earlier passes

Repo sources:
- `assets/web/lan/index.html`
- `assets/web/dm/index.html`
- current LAN modal/target/movement patterns from repo inspection

### Findings

#### 1. Desktop-only does not mean small or inaccessible

The user does not need DM tablet/touch support, but desktop controls still need comfortable click targets and readable spacing. WCAG 2.2 target-size guidance says pointer targets should generally be at least 24 by 24 CSS pixels, with spacing exceptions for smaller targets.

Design implication:
```text
/dmcontrol controls should use comfortable desktop button/chip sizes.
```

Recommended minimums:
```text
small utility controls: at least 24x24 px
primary action buttons: larger than minimum, visually obvious
target chips/remove buttons: not tiny X controls
modal Apply/Cancel buttons: large and separated
```

Do not cram `/dmcontrol` into the cramped `/dm` toolbox/modal style.

#### 2. Keyboard escape behavior is mandatory

NNG’s user-control heuristic says users need a clearly marked emergency exit to leave unwanted states without going through an extended process. For `/dmcontrol`, Escape must consistently cancel temporary modes.

Required Escape behavior:
```text
if resolution modal open:
  close/cancel modal if no request is applying

else if AoE/template placement active:
  cancel template placement

else if target mode active:
  cancel target mode and clear target preview

else if movement drag/preview active:
  cancel movement preview / snap back

else if Multiattack sequence child targeting active:
  return to sequence

else if override mode active:
  exit override mode or ask confirm if needed
```

Escape should not silently apply anything.

#### 3. Enter should confirm only inside focused modals/forms

Enter can be dangerous if globally bound. In a combat UI, accidental Enter should not apply damage just because the page has focus.

Recommended:
```text
Enter confirms only when focus is inside a resolution modal/form and the primary action is valid.
Enter should not globally end turn, apply damage, or resolve actions from the map.
```

For target modes:
```text
Enter may confirm selected targets only if a clear target tray/template confirm button is focused or modal context exists.
```

#### 4. Modal focus behavior should follow ARIA patterns

WAI-ARIA modal dialog guidance says Tab and Shift+Tab should stay inside the modal tab sequence, and users should not be able to move keyboard focus outside the modal without closing it. W3C dialog technique guidance says focus should move into the modal when opened and return to the invoking element when closed.

Design implication:
```text
/dmcontrol resolution and confirmation modals need focus management.
```

Required:
```text
focus moves into modal on open
Tab/Shift+Tab remain within modal
Escape closes/cancels when safe
focus returns to invoking action/control on close
background map/control actions are blocked while modal is active
```

This matters because resolution modals mutate combat state.

#### 5. Button state must prevent duplicate application

Baymard’s double-click research says users still double-click online and recommends disabling buttons immediately after click with progress feedback. This directly applies to Apply Results, End Turn, and forced override actions.

Required:
```text
Apply Results disabled while request is in flight
button text changes to Applying...
double-click cannot send duplicate requests
errors re-enable controls
success clears/updates state
```

This was already learned in `/dm` prototype hardening and should be first-class in `/dmcontrol`.

#### 6. Consequential actions must be visually separated

NNG warns against placing consequential options close to benign options and recommends separating confirmatory/destructive actions with redundant visual signals.

For `/dmcontrol`:
```text
Cancel/Back on left
Apply Results on right
End Turn visually distinct from attack/action buttons
Override actions visually marked
Remove/Delete/Force controls not in normal action clusters
```

Do not place:
```text
Apply Results
Cancel
End Turn
Force Move
```

as identical adjacent buttons.

#### 7. Confirmation should be used for state mutation, not harmless previews

NNG confirmation-dialog guidance says confirmation dialogs are useful before serious actions, especially actions that cannot be undone, but overuse creates friction.

Apply this distinction:
```text
No confirmation:
  select action
  show target preview
  move hover/path preview
  select target
  open modal

Confirmation/modal required:
  Apply damage/effects
  End turn if pending unresolved state exists
  Override illegal movement/targeting
  Remove combatant
  Force state changes
```

The UI should stay fast until it is about to mutate authoritative combat state.

#### 8. Recognition beats recall

NNG’s 10 heuristics include recognition rather than recall and visibility of system status. For a DM controlling many monsters/NPCs, `/dmcontrol` should not require memorizing stat blocks or hidden action details.

Show:
```text
current actor
current turn/round
movement remaining
active mode
selected action
range/reach/DC/damage summary
selected targets
pending resolution status
```

Hide/collapse:
```text
long descriptions
full stat block text
rare/unsupported details
```

Full reference remains on `/dm`.

#### 9. Resizable/collapsible panels are useful, but defaults matter

For desktop DM use, resizable panels and drawers are useful, especially with two monitors. But a bad default still hurts.

Recommended:
```text
LAN-like bottom/control sheet has sane default height
can expand/collapse
does not cover the entire map by default
action groups are collapsible
modals remain centered/usable
large target picker/list can be a drawer
```

First slice can use fixed sane layout; persistence of panel size is later polish.

#### 10. Scroll should be contained and intentional

The user prefers avoiding mandatory scrolling during active combat. However, monster actions can be numerous. Use:
```text
collapsible action groups
horizontal/compact cards
scroll inside secondary drawers, not whole page
modal tables with sticky headers if many targets
```

Avoid:
```text
page-level scrolling while map interactions need wheel zoom
burying Apply/Cancel below scroll
long unbounded action lists
```

For `/dmcontrol`, map zoom and scrollable panels must not fight each other. If the pointer is over the map, wheel zoom/pan should behave like map interaction. If pointer is over a drawer/list, wheel scrolls the drawer.

#### 11. Keyboard shortcuts should be few and predictable first

Foundry exposes many keyboard shortcuts and configurable controls, but a first `/dmcontrol` version should avoid a large shortcut vocabulary.

Recommended first shortcut set:
```text
Escape:
  cancel current mode/modal where safe

Enter:
  confirm focused modal/form only

M:
  maybe focus/movement mode later if needed

T:
  maybe target mode later if needed, but not first unless LAN already uses it

Space:
  do not bind globally until movement/ruler behavior is clear

Arrow keys:
  avoid first-slice reliance
```

If shortcuts are added, they should be discoverable in a small help popover later.

#### 12. Text labels beat ambiguous icons for first implementation

Because this is a complex DM workflow, first implementation should prefer clear labels:
```text
Target Preview
Cancel Targeting
Apply Results
End Sequence
End Turn
Override
```

Avoid icon-only controls for dangerous or mode-changing operations. Icons can be added later once the workflow is stable.

#### 13. Mode banners/status are essential

A map-first UI can become confusing if the DM forgets which mode is active. Use visible status:
```text
Targeting: Bite
Place Cone: Fire Breath
Resolving: Claw
Override Movement Active
Multiattack: Bite 0/1, Claw 1/2
```

Status should appear in the bottom/control bar and/or near the map, not hidden inside a log.

#### 14. Preventing mistakes matters more than undo at first

An undo system would be useful later but is not a first-slice requirement. Until undo exists:
```text
confirm before mutation
show clear preview
prevent double-submit
keep errors recoverable
route corrections to /dm Toolbox if needed
```

Admin correction tools on `/dm` remain the fallback for mistakes.

### Repo comparison after Pass 12

Status: completed from uploaded repo zip inspection and prior anchors.

#### LAN already has patterns to reuse

The LAN page already uses:
```text
modal resolution
target/attack modes
AoE preview panels
HUD/control updates
toasts/status text
map-first interaction
bottom control sheet
```

These are the right implementation reference.

#### `/dm` has known modal sizing issue

The current `/dm` DM Toolbox modal is too cramped:
```text
width: min(900px, 94vw)
height: min(720px, 88vh)
```

This should be fixed as `/dm` cleanup, but it also teaches a `/dmcontrol` rule:
```text
do not default to cramped modal/control surfaces
```

#### `/dm` prototype hardening is reusable

Reusable:
```text
in-flight guards
error preservation
explicit apply/cancel
safe cleanup on actor/action change
target/sequence state cleanup
```

Not final:
```text
/dm placement
tray-in-cockpit UI
map targeting on /dm
```

#### Current repo risk

`assets/web/lan/index.html` is large and monolithic. `/dmcontrol` must not become a blind copy with pasted complexity. It should:
```text
start from LAN layout/interaction concepts
reuse code only where safe
extract/share helpers later if practical
avoid copy-paste drift where possible
```

### Recommended `/dmcontrol` desktop interaction contract

Basic controls:
```text
Escape cancels current transient mode.
Enter confirms only focused modal/form actions.
Apply buttons prevent double-submit.
Cancel/Back exits before mutation.
Mode banners make active mode obvious.
```

Target/button sizing:
```text
use at least 24x24 px targets for small controls
larger hit areas for action cards and map target chips
avoid tiny remove/close buttons
```

Modal behavior:
```text
focus moves into modal on open
focus stays in modal
focus returns on close
Apply separated from Cancel
errors stay visible and recoverable
```

Panel behavior:
```text
bottom/control sheet has sane default height
collapsible action groups
contained scrolling
map remains usable
no page-level scroll dependence during combat
```

Safety behavior:
```text
state mutation requires explicit Apply/End/Confirm
harmless previews do not require confirmation
override is visibly marked
technical invalid state blocks with error
```

### Explicitly deferred

```text
- full keyboard shortcut customization
- screen-reader-perfect tactical map interaction
- undo system after Apply Results
- persistent panel size/layout memory
- complex keyboard-only map movement/targeting
- global command palette
- icon-only compact mode
- touch/mobile control optimization
```

### Implications for `/dmcontrol`

Concrete design rules to carry forward:

```text
1. Desktop-only still requires comfortable targets and spacing.
2. Escape cancels modes consistently.
3. Enter confirms only in focused modal/form contexts.
4. Resolution modals must manage focus correctly.
5. Apply/End/Override actions need in-flight/double-submit protection.
6. Dangerous actions need visual separation.
7. Confirmation is for mutation, not preview.
8. Active mode/status must be visible.
9. Use collapsible/contained-scroll panels, not page scroll.
10. Text labels should be preferred until the workflow stabilizes.
11. Avoid redundant click chains.
12. Do not blindly copy LAN’s monolith; adapt patterns carefully.
```

### Open questions for later spec

```text
- Should /dmcontrol first use native <dialog> or existing repo modal patterns?
- Should Escape cancel target mode before closing a modal if both are active?
- Should End Turn require confirmation if a sequence/resolution is active?
- Should panel collapse/expand state persist in localStorage?
- Should shortcut help be visible from the first /dmcontrol version?
- Should target chips have keyboard focus/remove support in first slice?
- How much ARIA polish is practical in the first /dmcontrol shell?
```

---

## Pass 12 — Accessibility / desktop interaction basics

Status: completed.

Research target:
```text
Practical desktop-only controls for DM use.
```

Questions:
```text
Keyboard shortcuts: Escape cancel, Enter confirm, arrows/tab?
Resizable panels?
Modal focus behavior?
Large click targets?
Scrollable vs collapsible sections?
How to prevent accidental destructive actions?
```

### Sources consulted

Accessibility / UX sources:
- W3C WCAG 2.2 Target Size Minimum
- WAI-ARIA Authoring Practices — Modal Dialog Pattern
- W3C HTML technique H102 — modal dialogs with the HTML dialog element
- Nielsen Norman Group — 10 Usability Heuristics
- Nielsen Norman Group — User Control and Freedom
- Nielsen Norman Group — Confirmation Dialogs Can Prevent User Errors
- Nielsen Norman Group — Preventing User Errors
- Nielsen Norman Group — Dangerous UX: Consequential Options Close to Benign Options
- Baymard Institute — Users continue to double-click online
- Baymard Institute button/design guidance from previous pass context

VTT / implementation-context sources:
- Foundry VTT Game Controls documentation
- Foundry VTT Measurement and Templates documentation
- Foundry keyboard shortcut references and module context, lower-authority
- Prior Roll20 / Foundry / Fantasy Grounds research from earlier passes

Repo sources:
- `assets/web/lan/index.html`
- `assets/web/dm/index.html`
- current LAN modal/target/movement patterns from repo inspection

### Findings

#### 1. Desktop-only does not mean small or inaccessible

The user does not need DM tablet/touch support, but desktop controls still need comfortable click targets and readable spacing. WCAG 2.2 target-size guidance says pointer targets should generally be at least 24 by 24 CSS pixels, with spacing exceptions for smaller targets.

Design implication:
```text
/dmcontrol controls should use comfortable desktop button/chip sizes.
```

Recommended minimums:
```text
small utility controls: at least 24x24 px
primary action buttons: larger than minimum, visually obvious
target chips/remove buttons: not tiny X controls
modal Apply/Cancel buttons: large and separated
```

Do not cram `/dmcontrol` into the cramped `/dm` toolbox/modal style.

#### 2. Keyboard escape behavior is mandatory

NNG’s user-control heuristic says users need a clearly marked emergency exit to leave unwanted states without going through an extended process. For `/dmcontrol`, Escape must consistently cancel temporary modes.

Required Escape behavior:
```text
if resolution modal open:
  close/cancel modal if no request is applying

else if AoE/template placement active:
  cancel template placement

else if target mode active:
  cancel target mode and clear target preview

else if movement drag/preview active:
  cancel movement preview / snap back

else if Multiattack sequence child targeting active:
  return to sequence

else if override mode active:
  exit override mode or ask confirm if needed
```

Escape should not silently apply anything.

#### 3. Enter should confirm only inside focused modals/forms

Enter can be dangerous if globally bound. In a combat UI, accidental Enter should not apply damage just because the page has focus.

Recommended:
```text
Enter confirms only when focus is inside a resolution modal/form and the primary action is valid.
Enter should not globally end turn, apply damage, or resolve actions from the map.
```

For target modes:
```text
Enter may confirm selected targets only if a clear target tray/template confirm button is focused or modal context exists.
```

#### 4. Modal focus behavior should follow ARIA patterns

WAI-ARIA modal dialog guidance says Tab and Shift+Tab should stay inside the modal tab sequence, and users should not be able to move keyboard focus outside the modal without closing it. W3C dialog technique guidance says focus should move into the modal when opened and return to the invoking element when closed.

Design implication:
```text
/dmcontrol resolution and confirmation modals need focus management.
```

Required:
```text
focus moves into modal on open
Tab/Shift+Tab remain within modal
Escape closes/cancels when safe
focus returns to invoking action/control on close
background map/control actions are blocked while modal is active
```

This matters because resolution modals mutate combat state.

#### 5. Button state must prevent duplicate application

Baymard’s double-click research says users still double-click online and recommends disabling buttons immediately after click with progress feedback. This directly applies to Apply Results, End Turn, and forced override actions.

Required:
```text
Apply Results disabled while request is in flight
button text changes to Applying...
double-click cannot send duplicate requests
errors re-enable controls
success clears/updates state
```

This was already learned in `/dm` prototype hardening and should be first-class in `/dmcontrol`.

#### 6. Consequential actions must be visually separated

NNG warns against placing consequential options close to benign options and recommends separating confirmatory/destructive actions with redundant visual signals.

For `/dmcontrol`:
```text
Cancel/Back on left
Apply Results on right
End Turn visually distinct from attack/action buttons
Override actions visually marked
Remove/Delete/Force controls not in normal action clusters
```

Do not place:
```text
Apply Results
Cancel
End Turn
Force Move
```

as identical adjacent buttons.

#### 7. Confirmation should be used for state mutation, not harmless previews

NNG confirmation-dialog guidance says confirmation dialogs are useful before serious actions, especially actions that cannot be undone, but overuse creates friction.

Apply this distinction:
```text
No confirmation:
  select action
  show target preview
  move hover/path preview
  select target
  open modal

Confirmation/modal required:
  Apply damage/effects
  End turn if pending unresolved state exists
  Override illegal movement/targeting
  Remove combatant
  Force state changes
```

The UI should stay fast until it is about to mutate authoritative combat state.

#### 8. Recognition beats recall

NNG’s 10 heuristics include recognition rather than recall and visibility of system status. For a DM controlling many monsters/NPCs, `/dmcontrol` should not require memorizing stat blocks or hidden action details.

Show:
```text
current actor
current turn/round
movement remaining
active mode
selected action
range/reach/DC/damage summary
selected targets
pending resolution status
```

Hide/collapse:
```text
long descriptions
full stat block text
rare/unsupported details
```

Full reference remains on `/dm`.

#### 9. Resizable/collapsible panels are useful, but defaults matter

For desktop DM use, resizable panels and drawers are useful, especially with two monitors. But a bad default still hurts.

Recommended:
```text
LAN-like bottom/control sheet has sane default height
can expand/collapse
does not cover the entire map by default
action groups are collapsible
modals remain centered/usable
large target picker/list can be a drawer
```

First slice can use fixed sane layout; persistence of panel size is later polish.

#### 10. Scroll should be contained and intentional

The user prefers avoiding mandatory scrolling during active combat. However, monster actions can be numerous. Use:
```text
collapsible action groups
horizontal/compact cards
scroll inside secondary drawers, not whole page
modal tables with sticky headers if many targets
```

Avoid:
```text
page-level scrolling while map interactions need wheel zoom
burying Apply/Cancel below scroll
long unbounded action lists
```

For `/dmcontrol`, map zoom and scrollable panels must not fight each other. If the pointer is over the map, wheel zoom/pan should behave like map interaction. If pointer is over a drawer/list, wheel scrolls the drawer.

#### 11. Keyboard shortcuts should be few and predictable first

Foundry exposes many keyboard shortcuts and configurable controls, but a first `/dmcontrol` version should avoid a large shortcut vocabulary.

Recommended first shortcut set:
```text
Escape:
  cancel current mode/modal where safe

Enter:
  confirm focused modal/form only

M:
  maybe focus/movement mode later if needed

T:
  maybe target mode later if needed, but not first unless LAN already uses it

Space:
  do not bind globally until movement/ruler behavior is clear

Arrow keys:
  avoid first-slice reliance
```

If shortcuts are added, they should be discoverable in a small help popover later.

#### 12. Text labels beat ambiguous icons for first implementation

Because this is a complex DM workflow, first implementation should prefer clear labels:
```text
Target Preview
Cancel Targeting
Apply Results
End Sequence
End Turn
Override
```

Avoid icon-only controls for dangerous or mode-changing operations. Icons can be added later once the workflow is stable.

#### 13. Mode banners/status are essential

A map-first UI can become confusing if the DM forgets which mode is active. Use visible status:
```text
Targeting: Bite
Place Cone: Fire Breath
Resolving: Claw
Override Movement Active
Multiattack: Bite 0/1, Claw 1/2
```

Status should appear in the bottom/control bar and/or near the map, not hidden inside a log.

#### 14. Preventing mistakes matters more than undo at first

An undo system would be useful later but is not a first-slice requirement. Until undo exists:
```text
confirm before mutation
show clear preview
prevent double-submit
keep errors recoverable
route corrections to /dm Toolbox if needed
```

Admin correction tools on `/dm` remain the fallback for mistakes.

### Repo comparison after Pass 12

Status: completed from uploaded repo zip inspection and prior anchors.

#### LAN already has patterns to reuse

The LAN page already uses:
```text
modal resolution
target/attack modes
AoE preview panels
HUD/control updates
toasts/status text
map-first interaction
bottom control sheet
```

These are the right implementation reference.

#### `/dm` has known modal sizing issue

The current `/dm` DM Toolbox modal is too cramped:
```text
width: min(900px, 94vw)
height: min(720px, 88vh)
```

This should be fixed as `/dm` cleanup, but it also teaches a `/dmcontrol` rule:
```text
do not default to cramped modal/control surfaces
```

#### `/dm` prototype hardening is reusable

Reusable:
```text
in-flight guards
error preservation
explicit apply/cancel
safe cleanup on actor/action change
target/sequence state cleanup
```

Not final:
```text
/dm placement
tray-in-cockpit UI
map targeting on /dm
```

#### Current repo risk

`assets/web/lan/index.html` is large and monolithic. `/dmcontrol` must not become a blind copy with pasted complexity. It should:
```text
start from LAN layout/interaction concepts
reuse code only where safe
extract/share helpers later if practical
avoid copy-paste drift where possible
```

### Recommended `/dmcontrol` desktop interaction contract

Basic controls:
```text
Escape cancels current transient mode.
Enter confirms only focused modal/form actions.
Apply buttons prevent double-submit.
Cancel/Back exits before mutation.
Mode banners make active mode obvious.
```

Target/button sizing:
```text
use at least 24x24 px targets for small controls
larger hit areas for action cards and map target chips
avoid tiny remove/close buttons
```

Modal behavior:
```text
focus moves into modal on open
focus stays in modal
focus returns on close
Apply separated from Cancel
errors stay visible and recoverable
```

Panel behavior:
```text
bottom/control sheet has sane default height
collapsible action groups
contained scrolling
map remains usable
no page-level scroll dependence during combat
```

Safety behavior:
```text
state mutation requires explicit Apply/End/Confirm
harmless previews do not require confirmation
override is visibly marked
technical invalid state blocks with error
```

### Explicitly deferred

```text
- full keyboard shortcut customization
- screen-reader-perfect tactical map interaction
- undo system after Apply Results
- persistent panel size/layout memory
- complex keyboard-only map movement/targeting
- global command palette
- icon-only compact mode
- touch/mobile control optimization
```

### Implications for `/dmcontrol`

Concrete design rules to carry forward:

```text
1. Desktop-only still requires comfortable targets and spacing.
2. Escape cancels modes consistently.
3. Enter confirms only in focused modal/form contexts.
4. Resolution modals must manage focus correctly.
5. Apply/End/Override actions need in-flight/double-submit protection.
6. Dangerous actions need visual separation.
7. Confirmation is for mutation, not preview.
8. Active mode/status must be visible.
9. Use collapsible/contained-scroll panels, not page scroll.
10. Text labels should be preferred until the workflow stabilizes.
11. Avoid redundant click chains.
12. Do not blindly copy LAN’s monolith; adapt patterns carefully.
```

### Open questions for later spec

```text
- Should /dmcontrol first use native <dialog> or existing repo modal patterns?
- Should Escape cancel target mode before closing a modal if both are active?
- Should End Turn require confirmation if a sequence/resolution is active?
- Should panel collapse/expand state persist in localStorage?
- Should shortcut help be visible from the first /dmcontrol version?
- Should target chips have keyboard focus/remove support in first slice?
- How much ARIA polish is practical in the first /dmcontrol shell?
```


# Final synthesis

## Overall research verdict

The research supports a clear architectural pivot:

```text
/dm is the DM cockpit, prep, reference, overview, actor sheet, initiative, toolbox, admin override, debug, and historical battle-log page.

/dmcontrol should be a separate LAN-index-like active play page for controlling the current monster/NPC/enemy.
```

The central correction is:

```text
Do not move /dm UI into /dmcontrol.
Do not keep expanding /dm into the active monster-control surface.
Build /dmcontrol from LAN client interaction patterns, adapted for DM-controlled monsters/NPCs.
```

The current `/dm` Focused Actor / Monster Actions / Target Tray / Resolution Tray / Sequence Tray work is still useful, but it should be treated as prototype logic and reusable lessons, not the final `/dmcontrol` layout.

---

## Final /dm vs /dmcontrol split

### /dm

Purpose:
```text
DM cockpit, prep, overview, reference, and administration.
```

Belongs on `/dm`:
```text
initiative overview
all combatants
full actor/stat-sheet reference
encounter setup
Monster Library / Encounter Builder
session persistence
DM Toolbox
HP/temp HP/initiative overrides
remove/add custom combatants
debug tools
large battle log/history
reference/inspection map
```

Map role on `/dm`:
```text
reference
inspection
visual context
not the active combat-control surface
```

### /dmcontrol

Purpose:
```text
LAN-like active play surface for the current monster/NPC/enemy turn.
```

Belongs on `/dmcontrol`:
```text
current controlled monster/NPC/enemy
turn/round status
movement remaining
active tactical map for movement/targeting/AoE
monster/NPC action controls
attack/spell/AoE targeting
resolution modals
guided Multiattack
soft DM override
compact recent-result feed
End Turn / Next / Previous if they fit cleanly
```

Map role on `/dmcontrol`:
```text
active play surface
drag/drop movement
attack targeting
AoE/template placement
range/reach previews
selected/affected target previews
source/target highlights
```

---

## Final /dmcontrol interaction model

```text
Initiative advances to monster/NPC/enemy
→ /dm shows that actor’s sheet/reference information
→ /dmcontrol controls that actor’s active turn
→ movement range appears automatically
→ DM can move by drag/drop at any point during the turn
→ DM chooses action/spell/Multiattack from LAN-style controls
→ /dmcontrol map enters action-specific target/template mode
→ DM selects target(s) or places AoE/template
→ selected/affected targets are previewed
→ resolution modal opens
→ DM manually/app-assisted resolves hit/save/damage/effects
→ Apply Results mutates backend combat state
→ Multiattack returns to child sequence until ended
→ DM ends turn
```

When initiative is on a PC:
```text
/dmcontrol behaves like a client when it is not that actor’s turn:
controls are mostly idle/disabled.
A DM override can exist, but it is explicit and not the normal path.
```

---

## Final design principles for /dmcontrol

```text
1. Build from assets/web/lan/index.html interaction patterns, not assets/web/dm/index.html.
2. Keep /dmcontrol map-first and active.
3. Use a LAN-like bottom/control bar as the main control surface.
4. Do not duplicate the full actor sheet; /dm owns full reference.
5. Duplicate only turn-critical state on /dmcontrol.
6. Current monster/NPC/enemy is controlled by default.
7. PC turns show idle/disabled state unless DM override is explicitly enabled.
8. Movement range appears automatically for current monster/NPC.
9. Drag/drop movement is normal movement input.
10. Movement remaining remains visible throughout the turn.
11. Split movement before/between/after actions is required.
12. Normal attacks should match LAN flow closely.
13. Spell/AoE/breath actions use visible template previews.
14. Targeting is action-first by default.
15. Target list/picker is a fallback for crowded maps.
16. Resolution is modal and state-mutating only after Apply Results.
17. Multiattack is a guided child-step flow, not one opaque attack.
18. Automation assists the DM but should not trap the DM.
19. Override is explicit, visually marked, and not the default path.
20. Avoid redundant click chains.
```

---

## Research-backed UX contracts

### Action selection

Default:
```text
select action card/button
→ target/range/template mode starts immediately
→ no redundant second action activation
```

Avoid:
```text
select action
→ select target
→ click attack again
→ reselect target
→ click resolve
```

### Normal attack

```text
click attack
→ show reach/range preview
→ click target token
→ resolution modal opens with target already selected
→ choose/confirm miss/hit/crit and damage
→ Apply Results
```

### Save / AoE action

```text
click AoE/save action
→ place/aim template or select valid target area
→ affected target preview updates
→ confirm affected targets
→ resolution modal opens with target rows
→ choose/roll save outcomes
→ Apply Results
```

### Multiattack

```text
click Multiattack
→ guided sequence modal/tray opens
→ child steps display counts/completion
→ select child step
→ child uses normal attack/spell/AoE flow
→ Apply increments child completion exactly once
→ Cancel returns to sequence without progress
→ movement remains possible between child attacks
→ End Sequence clears sequence state
```

### Movement

```text
active monster/NPC turn starts
→ movement overlay appears
→ movement remaining is visible
→ drag/drop token
→ backend validates
→ valid move consumes movement
→ invalid move snaps/rejects without spending movement
```

### Resolution modal

```text
preview/targeting stays lightweight
Apply Results is explicit
Cancel is available before mutation
Apply buttons are double-submit guarded
errors preserve modal state for retry/cancel
```

### Override

```text
normal mode validates and warns
soft override can allow ambiguous/out-of-range targeting with confirmation
hard override/admin repair belongs primarily in /dm Toolbox
technical stale/broken state blocks rather than being overridden
```

---

## Current repo realities

### Strong foundations

The repo already has a strong LAN page foundation:

```text
map-first LAN page
bottom control sheet
movement range/cost overlays
drag/drop movement
attack targeting
attack resolution modal
spell/AoE targeting primitives
AoE preview panels
backend movement validation
```

The repo also has useful monster capability foundations:

```text
MonsterCapabilityService summaries
melee_attack / ranged_attack / save_ability capabilities
composite Multiattack model
resolved_composite child actions
assisted_sequence backend packets
resolve-targets endpoint
recharge/resource helper concepts
spell library resolution for overlays
```

### Current gaps

```text
No /dmcontrol route/page exists yet.
Normalized monster capability coverage is shallow: 18 overlays for 516 raw monster YAMLs.
Many raw monster YAML actions are text, not structured/executable actions.
Monster spellcasting overlay coverage is minimal.
Bonus Actions/Reactions/Legendary Actions are not broadly normalized.
Black and Tan firearm enemies remain beta/untested; Rifleman overlay may be missing composite Multiattack despite raw YAML text.
Current /dm Monster Library duplicates entries.
Repeated single-spawn numbering currently regresses for Black and Tan Rifleman-style adds.
DM Toolbox modal is too cramped.
Legacy Monster Turn Controls / Monster Pilot remain visible in /dm main cockpit.
```

---

## Reusable work from /dm prototype

Reusable concepts/logic:
```text
Monster Action card rendering ideas
selected/expanded action state
target tray state model
range/AoE advisory wording
resolution endpoint reuse
manual outcome rows
Apply/Cancel behavior
in-flight/error hardening
sequence tray concept
child completion tracking
invalid/missing child handling
```

Not final as-is:
```text
/dm placement
/dm Focused Actor Panel layout
/dm map as active action/targeting surface
map-click target workflow on /dm
legacy Monster Turn Controls / Monster Pilot
dropdown-heavy workflows
```

---

## Recommended implementation order

### Phase 0 — Clean current /dm regressions

Do before `/dmcontrol` construction:

```text
1. Fix Monster Library duplicate entries.
2. Fix repeated single-spawn numbering regression.
3. Resize/improve DM Toolbox modal.
4. Demote/remove legacy Monster Turn Controls and Monster Pilot from /dm main cockpit.
5. Keep /dm map reference/inspection only.
```

### Phase 1 — /dmcontrol shell and state

```text
1. Add /dmcontrol route and assets/web/dmcontrol/index.html.
2. Add Open DM Control link on /dm.
3. Add DM Cockpit link on /dmcontrol.
4. Fetch/subscribe to shared backend snapshot.
5. Show current initiative actor.
6. Show disabled/idle state when current actor is a PC or no DM-controlled actor is active.
7. Show minimal current actor turn-critical status:
   name, HP summary, conditions summary, movement remaining, turn/round.
```

### Phase 2 — LAN-like map and movement

```text
1. Adapt LAN map surface.
2. Show current actor token.
3. Show movement range automatically.
4. Implement drag/drop movement using LAN-style backend validation.
5. Show movement remaining in bottom/control bar.
6. Snap/reject invalid movement without spending movement.
```

### Phase 3 — Basic attack flow

```text
1. Show overlay-backed normal attack actions.
2. Click attack starts range/reach preview.
3. Click target on /dmcontrol map.
4. Open LAN-like attack resolution modal.
5. Support manual/average/roll-formula damage.
6. Apply Results through existing monster-capability or adapted LAN backend path.
7. Prevent double-submit.
```

### Phase 4 — Multiattack guided flow

```text
1. Show composite Multiattack cards for overlay-backed monsters.
2. Open guided sequence modal/tray.
3. Render child steps and completion counts.
4. Child step uses normal attack flow.
5. Allow movement between child steps.
6. End Sequence manually.
```

### Phase 5 — AoE / save action flow

```text
1. Support cone/line breath weapons first.
2. Add sphere/circle targeted AoEs next.
3. Preview affected targets.
4. Confirm target set.
5. Use save/AoE resolution modal with compact target rows.
```

### Phase 6 — Monster spellcasting

```text
1. Show structured monster spellcasting only when overlay exists.
2. Group by action economy and usage/frequency.
3. Do not expose all repo spells globally.
4. Use LAN-style targeting/resolution when executable.
5. Keep non-executable spellcasting assisted/manual.
```

### Phase 7 — Content/overlay expansion

```text
1. Validate Black and Tan Constable/Rifleman overlays.
2. Add missing firearm Multiattack composite overlays if intended.
3. Expand normalized overlays for common monsters.
4. Build authoring/normalization tools later.
```

---

## Updates needed for docs/dm_control_surface_living_agent_plan.md

Add/update these sections:

```text
Dedicated /dmcontrol Interaction Contract
/dm vs /dmcontrol split
LAN-index-derived /dmcontrol design rules
Active map role on /dmcontrol vs reference map role on /dm
Current repo realities and cleanup queue
Implementation phases for /dmcontrol
Reusable prototype work vs not-final /dm prototype work
Black and Tan beta/untested note
```

Correct or emphasize:

```text
Do not move /dm UI into /dmcontrol.
Do not build /dmcontrol from /dm Focused Actor Panel layout.
Do not continue active monster-control implementation on /dm.
Use LAN page as implementation reference.
```

---

## Agent guardrails to add after research

```text
1. /dmcontrol must be LAN-index-like, not /dm-like.
2. /dm remains cockpit/prep/reference/admin/debug.
3. /dm tactical map is reference/inspection only.
4. /dmcontrol tactical map is active movement/targeting/AoE surface.
5. Do not copy /dm right-side controls into /dmcontrol.
6. Do not resurrect dropdown-heavy Monster Turn Controls / Monster Pilot.
7. Avoid redundant click chains.
8. Use existing LAN movement/target/resolution patterns as reference.
9. Use existing monster capability backend paths where practical.
10. Do not create a third parallel combat-resolution backend unless proven necessary.
11. No state mutation without explicit Apply/Confirm.
12. Double-submit guards are mandatory for Apply/End/Override.
13. Missing structured monster overlay should degrade gracefully without dropdown hell.
14. Black and Tan firearm content is beta/untested until explicitly validated.
```

---

## Final recommendation

Do not implement `/dmcontrol` yet until the living repo plan is updated from this research.

The next work item should be:

```text
Update docs/dm_control_surface_living_agent_plan.md using this research.
```

Then:

```text
Run the /dm cleanup pass:
- Monster Library duplicates
- single-spawn numbering regression
- DM Toolbox sizing
- legacy Monster Turn Controls / Monster Pilot demotion
```

Then begin `/dmcontrol` with a tiny first slice:

```text
/dmcontrol route + LAN-like shell + current actor/disabled state only
```

Do not start by porting the old `/dm` Focused Actor panel.
