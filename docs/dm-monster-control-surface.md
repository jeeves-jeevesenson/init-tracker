# DM Monster-Control Surface and Monster Capability Backend — Plan

> Status: planning / design proposal. No implementation in this pass.
>
> Scope: a durable architecture and migration plan for a robust DM monster-control
> surface, a normalized monster capability schema, backend execution support for
> monster actions, future DM cockpit integration, and a phased cleanup plan for
> the existing monster YAML pack.
>
> This document follows the project direction in `majorTODO.md`, `AGENTS.md`,
> `CLAUDE.md`, and `GEMINI.md`: backend-owned authority, explicit contracts,
> headless/browser-first as the permanent runtime direction, and Tk treated as
> a transitional compatibility surface (not an end-state design goal).

---

## 1. Executive summary

### 1.1 The problem

The player LAN page (`/`, `assets/web/lan/index.html`, ~26k lines) is already a
robust combat surface: claim a character, see turn prompts, spend actions,
move with movement-mode cycling, attack with target picking, cast spells with
modal flow, opt into reactions like Shield / Counterspell / Hellish Rebuke /
Absorb Elements, and use a long tail of class features. The corresponding
backend authority lives behind `PlayerCommandService` (6.8k lines) and
`player_command_contracts.py` (1.6k lines), with deep adjudication still
delegated into `InitiativeTracker`.

The DM, by contrast, has nothing close to that level of control over their
own combatants. The `/dm` console embeds a single "Monster Turns" card
(`assets/web/dm/index.html` lines 835–912) with:

- a free-text "type the monster action name" input that calls
  `/api/dm/combat/combatants/{cid}/perform-action`,
- a free-text "spell name / slug / id" input that calls
  `/api/dm/combat/combatants/{cid}/spell-target`,
- a "Load Monster Attacks" → pick attack → Resolve → manually enter
  `slashing:5, fire:3` damage entries → Apply Manual Damage flow that calls
  `/api/dm/combat/combatants/{cid}/monster-attacks` and
  `/api/dm/combat/monster-attacks/{resolve,apply-damage}`.

That toolkit is functional for the basic "swing a sword and roll damage"
case, but it does not let a DM run a real D&D combat. Save-DC abilities,
breath weapons / recharge, AoE templates, multiattack composition,
reactions (including opportunity attack), legendary actions, lair actions,
spellcasting beyond a known slug, and resource bookkeeping are all either
missing or punted to "type the right text and the backend will try."

### 1.2 Why this is foundational

D&D combat is not "PCs do clever things and monsters swing once." The
challenge, danger, and pacing of an encounter come from monsters using all
of their stat block: multiattack, save-or-suck riders, recharge breath,
legendary actions, lair actions, reactions, and spell-like abilities.

If the DM has to manually translate "the dragon recharges, then I move 40 ft.
flying, then I cone 18d6 fire on three PCs at DC 21 Dex" into a sequence of
free-text inputs and manual damage typing, the live-session experience
collapses. The DM either falls back to the desktop Tk surface (which the
project is intentionally migrating away from), runs encounters by hand on
paper / dice and then types totals into the tracker, or short-circuits monster
behavior to whatever fits the typeable surface.

A robust monster-control surface is therefore not a "nice DM polish task."
It is a precondition for the headless/browser-first product to be a real
operating mode for actual sessions, and it is the next major missing peer to
the player LAN UX.

### 1.3 The data must be audited, not assumed

The current monster YAML pack (`Monsters/*.yaml`, 514 files) is an
AideDD-derived 2024 snapshot. The schema is documented in
`Monsters/README.md` and the data is fundamentally *display text* with
embedded markup, not an executable action model. Concrete numbers from the
current repo state:

| Property | Files | % of 514 |
|---|---:|---:|
| `actions: []` (empty) | 139 | ~27% |
| `traits: []` (empty) | 200 | ~39% |
| `legendary_actions: []` (empty) | 481 | ~94% |
| Mentions Multiattack | 188 | ~37% |
| Has `{@dc N}` save-DC marker in text | 221 | ~43% |
| Has `{@recharge N}` marker in text | 74 | ~14% |
| References `{@spell ...}` in text | 30 | ~6% |
| Uses structured `bonus_actions:` field | 1 | ~0.2% |
| Uses structured `^reactions:` field | 0 | 0% |
| Uses optional `phases:` boss extension | 1 | ~0.2% |
| Uses optional `turn_schedule:` boss extension | 1 | ~0.2% |

Counts collected by `grep -l` over `Monsters/*.yaml` against the
checked-in files at the time of this writing.

What this means:

- A large fraction of monsters have **no structured actions at all**.
- Reactions are not modeled in the schema at all; they only appear inside
  trait or action description text on monsters that have them.
- Spellcasting blocks are essentially absent — even the Archmage and Lich
  YAMLs carry no spell list.
- Save-DC, AoE shape, recharge, and condition riders live entirely inside
  free-text `desc` fields with embedded `{@hit}`, `{@damage}`, `{@dc}`,
  `{@condition X}`, `{@spell X}`, `{@recharge N}` markup.
- The current parser (`_parse_monster_attack_options` in
  `dnd_initative_tracker.py` ~line 29476) recovers a subset
  (`to_hit`, `damage_entries[]`) from descriptions that have both `{@hit}`
  and a damage clause — and explicitly skips Multiattack as a unit, skips
  any action without those markers, and bypasses save-only / AoE-only /
  utility actions.
- Some YAMLs have parse artifacts (e.g., Archmage `type: or Small
  Humanoid (Wizard)`).
- Some single-action descriptions are mashed-together blobs of multiple
  distinct effects (e.g., Beholder's Eye Rays, where ten different ray
  effects share one paragraph).

The plan below treats this YAML pack as **partially serviceable, not
authoritative**. Monster control work must include an audit phase before
schema or UI work locks in assumptions about what data can be relied on.

---

## 2. Current repo reality

This section captures the state of the repository at the time of this plan,
to anchor the rest of the document. Confirmed findings come from grep / read
inspection at the cited file/line locations. Items marked **assumption**
are reasonable inferences that should be re-validated before any
implementation pass.

### 2.1 DM surfaces

- `/dm` (DM dashboard) and `/dm/map` (DM map workspace) are served by the
  same HTML file (`assets/web/dm/index.html`, ~5.5k lines), with the
  workspace selected via a `__DM_WORKSPACE__` template token that is
  replaced server-side (`dnd_initative_tracker.py` ~lines 3860–3877).
- Both routes share auth, snapshot polling, WebSocket (`/ws/dm`), and the
  three-lane workspace shell (cockpit / map / control lane). The
  `majorTODO.md` 3.2 entry confirms that the cockpit/initiative cards,
  resizable lanes, hideable panels, and grouped setup/live-play sections
  have already landed.
- The DM page contains the "Monster Turns" live-group card
  (lines 835–912) with the controls described in §1.1.
- `/dm/map` reuses the shared HTML and switches into a tactical-first
  layout. There is no separate map-only HTML asset.

### 2.2 Player LAN surface (peer baseline)

- `assets/web/lan/index.html` (~26k lines) is the production-quality
  player surface. It includes movement mode cycling, attack overlay,
  cast modal, AoE manipulation, action / bonus / reaction chips, condition
  icons, spellbook contract integration, mount/dismount, resource pools,
  reaction prompts (Shield, Counterspell, etc.), and many class/feature
  flows.
- The LAN page is the closest reference for what "robust combatant
  control" looks like in this project. Much of its action-card layout,
  spell modal, AoE picker, and reaction chip pattern can be re-used or
  adapted for monster control.

### 2.3 Backend services and authority

- `combat_service.py` (1.6k lines) owns combat lifecycle, initiative,
  HP / temp HP, conditions, encounter population (player profiles +
  monster specs), removal, deep damage / heal, manual override, and
  long-rest batch heal. It is the canonical seam for both the desktop
  and `/dm` paths. Documented in `docs/dm-web-migration.md`.
- `player_command_service.py` (6.8k lines) owns the player-command
  family dispatch:
  - movement / `perform_action`
  - attack request, spell target request, reaction response
  - manual override (HP, slot, resource pool)
  - turn-local commands (mount, dash, use_action, reset_turn, etc.)
  - wild shape, summon/echo, bard glamour, monk/fighter resources
  - utility/admin (set_color, set_facing, set_auras_enabled,
    reset_player_characters)
- `player_command_contracts.py` (1.6k lines) is the canonical
  request / response contract for those command families.
- `dnd_initative_tracker.py` (~46k lines) still owns:
  - the unified LAN dispatcher `_lan_apply_action()` (~line 39930)
  - deep adjudication helpers (attack, spell, reaction trigger
    resolution, rider damage)
  - `MonsterSpec` dataclass (~line 1705) and YAML loader
  - `_parse_monster_attack_options` (~line 29476) — semi-structured
    parser that recovers `(to_hit, damage_entries)` from `{@hit}` /
    `{@damage}` markup in `desc` text
  - `_dm_monster_attack_options`,
    `_dm_resolve_monster_attack_sequence`,
    `_dm_apply_monster_attack_damage`,
    `_dm_monster_perform_action`,
    `_dm_monster_spell_target` (~lines 43380–43614)
  - DM turn helpers `_dm_validate_monster_actor_for_turn`,
    `_dm_normalize_turn_spend`, `_dm_spend_combatant_turn_resource`
    (~lines 43334–43378)

### 2.4 DM API surface for monsters today

Confirmed in `dnd_initative_tracker.py` route registration:

- `GET  /api/dm/combat/combatants/{cid}/monster-attacks` — list parsed
  attacks for a non-PC actor (line 4433)
- `POST /api/dm/combat/monster-attacks/resolve` — resolve hit/miss
  rolls for an attack sequence (line 4454)
- `POST /api/dm/combat/monster-attacks/apply-damage` — apply manual
  damage totals (line 4487)
- `POST /api/dm/combat/combatants/{cid}/perform-action` — execute a
  perform_action by name on a non-PC combatant (line 4519)
- `POST /api/dm/combat/combatants/{cid}/spell-target` — single-target
  spell for a non-PC combatant (line 4544)

Plus the standard combat service routes (start/end, next/prev/set turn,
HP, conditions, temp HP, initiative, add/remove combatant) listed in
`docs/dm-web-migration.md`.

### 2.5 Monster YAML reality

See §1.3 for headline numbers. Schema is documented in `Monsters/README.md`:
flat top-level keys (`name`, `size`, `type`, `alignment`, `initiative`,
`ac`, `hp`, `speed`, `abilities`, `skills`, `immunities`, `senses`,
`languages`, `challenge_rating`, `traits`, `actions`, `legendary_actions`,
`legendary_uses`, `description`, `habitat`, `treasure`), with `traits` /
`actions` / `legendary_actions` as ordered lists of `{name, desc}` text
entries. AideDD-style markup (`{@atk mw|rw|ms|rs}`, `{@hit N}`,
`{@damage XdY+Z}`, `{@h}`, `{@dc N}`, `{@condition X}`, `{@spell X}`,
`{@recharge N}`, `{@dice XdY}`, `{@creature X}`, `{@skill X}`) lives inside
`desc` strings.

Optional boss extensions documented in `Monsters/README.md` (`turn_schedule`,
`phases`) exist in the schema but are essentially unused (1 file each).

### 2.6 Where existing docs are stale or incomplete

- `docs/dm-web-migration.md` calls out that "full monster-action UX parity
  for every prompt-heavy or bespoke spell/action branch" remains
  desktop-primary. That is still true and is exactly the gap this plan
  targets.
- The "Recommended next migration targets" list in the same doc is
  generic ("residual advanced authoring parity", "snapshot enhancements").
  It does not yet name monster-control parity as the next major slice.
- `majorTODO.md` does not currently track a monster-control surface or a
  monster YAML capability audit. Adding a pointer to this plan there is
  consistent with the existing convention for durable initiatives.

### 2.7 Confirmed vs assumed

**Confirmed** (from current code/files):

- File counts and structural-emptiness counts cited in §1.3.
- Existence and signatures of the DM monster routes and helpers in §2.4.
- `_parse_monster_attack_options` only emits `to_hit` + `damage_entries`
  and skips Multiattack (verified at the cited line range).
- `/dm` and `/dm/map` share the same HTML asset.
- The "Monster Turns" lane is the only DM-side monster-control UI.

**Assumption** (reasonable but should be re-checked before implementation):

- The "type the spell name/slug" path in `/api/dm/combat/combatants/{cid}/spell-target`
  primarily works for spells that already exist in the player spell preset
  catalog. Monsters without such spells in the catalog likely fail or
  silently no-op; this should be empirically verified during the Phase 0
  audit.
- The `MonsterSpec.raw_data` round-trips the YAML faithfully enough that a
  new structured layer can reference it without re-loading. This is the
  shape used by `_monster_attack_options_for_map` and looks safe but is
  worth verifying.
- The `_dm_monster_perform_action` path performs validation through
  `PlayerCommandService.perform_action`, which assumes player-shaped
  action lists. Monster `actions: []` arrays will likely not satisfy the
  same "available action" check; this should also be empirically verified.

---

## 3. DM cockpit direction

### 3.1 `/dm` and `/dm/map`: merge or stay separate?

**Recommendation: keep them as the same HTML, treat them as workspace modes,
and converge on a unified DM cockpit layout long-term — but do not delete
`/dm/map` until the unified cockpit demonstrably covers map-first
operation.**

Rationale:

- They are already the same HTML file with a `__DM_WORKSPACE__` switch.
  The cost of "merging" is low because they are not actually separate
  surfaces; the cost of *deleting* `/dm/map` is real because it is the
  current map-first entry that the user has been hardening (`majorTODO.md`
  3.2).
- A single unified cockpit that includes a real tactical lane covers both
  needs, with the workspace switch becoming a layout / focus toggle rather
  than a route bifurcation.
- Premature deletion of `/dm/map` would regress current map-first DM
  ergonomics that have been actively stabilized. Keep the route until the
  unified layout is proven.

### 3.2 Desired layout

The endgame DM cockpit is a single-page operator surface with three
primary lanes plus a bottom rail, all collapsible / resizable:

```
┌──────────────────────────────────────────────────────────────────────┐
│  Topbar: campaign / session / turn / round / connection / auth       │
├────────────┬───────────────────────────────────────┬─────────────────┤
│ Initiative │           Tactical map               │ Selected actor  │
│  / cockpit │  (tokens, AoEs, terrain, hazards)    │  + tools        │
│            │                                       │                 │
│  PC, ally, │   ── grid ──                          │  HP / AC /      │
│  enemy     │                                       │  speed / saves  │
│  cards in  │                                       │  defenses       │
│  init      │                                       │                 │
│  order;    │                                       │  Action cards:  │
│  active    │                                       │   - Attack      │
│  highlight │                                       │   - Spell/SLA   │
│  + up-next │                                       │   - Multiattack │
│            │                                       │   - Recharge    │
│            │                                       │   - Bonus       │
│            │                                       │   - Reaction    │
│            │                                       │   - Legendary   │
│            │                                       │   - Lair        │
│            │                                       │   - Move/Dash   │
│            │                                       │   - Override    │
├────────────┴───────────────────────────────────────┴─────────────────┤
│ Bottom rail: battle log, pending prompts, recent results, AoE list   │
└──────────────────────────────────────────────────────────────────────┘
```

Key ergonomics:

- **Left (initiative cockpit):** the existing initiative cards from
  `majorTODO.md` 3.2 follow-ups. Active highlight, up-next, badges,
  conditions, defenses. Click a card to make it the **selected actor**
  (which drives the right lane). This is intentionally distinct from
  *current actor* (whose turn it is) because the DM frequently inspects
  enemies that are not currently up.
- **Center (tactical map):** the map workspace from `/dm/map`, sized
  large by default. Token interactions (place, move, facing, AoE drag)
  work without needing a dedicated route. Clicking a token sets the
  selected actor on the right.
- **Right (selected actor + tools):** the new monster-control surface
  detailed in §4. When the selected actor is a player-controlled PC,
  this lane shows DM-tools-on-PC instead (override HP, condition apply,
  initiative tweak, view sheet). When the selected actor is a
  non-PC, this lane is the monster-control surface.
- **Bottom rail:** battle log, pending DM prompts, last attack/save
  result, current AoE list / hazards, and quick-action shortcuts.
  Collapsible.
- **Panels are collapsible and resizable** — the workspace shell that
  `majorTODO.md` 3.2 already landed is the foundation for this.

### 3.3 What stays in `/dm`

- The dashboard-mode default layout (cockpit + tools, smaller map) stays
  for setup-heavy work: roster building, encounter assembly, magic-item
  authoring entry points, session save/load, etc.
- Setup-only cards (Roster / Combat Setup / Map Setup / Session) keep
  their grouped sections.

### 3.4 Should there be a dedicated monster-control route short term?

**Recommendation: yes, ship the monster-control surface first as
`/monster-control` (or `/dm/monster`), then graft it into the unified
cockpit.**

Rationale:

- Building it inside the existing 5.5k-line shared HTML during MVP risks
  large mid-pass rewrites of the page and conflicts with the active
  cockpit/responsiveness work in `majorTODO.md` 3.1 / 3.2.
- A dedicated route can iterate quickly, prove the action model, and be
  reviewed in isolation.
- Once the surface is stable, it becomes the right-lane content for the
  unified cockpit. The cockpit graft is then a layout pass, not a
  re-implementation.

Route naming preference:

- **`/dm/monster`** — keeps the surface namespaced under `/dm` and
  consistent with `/dm/map`. Recommended.
- `/monster-control` — readable, but breaks the `/dm` namespacing.

The plan refers to it as `/dm/monster` for the rest of the document, but
the final name is open.

---

## 4. Monster-control surface concept

The monster-control surface (`/dm/monster`) is the DM-facing peer of the
LAN player page. It must be runnable in isolation (so the DM can sit on
this screen and run a creature's full turn) and embeddable as the
selected-actor lane of the unified cockpit.

### 4.1 Goals

1. **Robustness parity with the player LAN page.** The DM can do
   anything a smart player can do, plus DM-only authority.
2. **Surface what the monster can actually do right now.** The page
   reads from a backend "available actions" contract per combatant —
   attack options, multiattack, recharge state, save-DC abilities,
   spells, bonus actions, reactions, legendary actions, lair actions,
   movement modes, conditions affecting the actor.
3. **Real save-DC and AoE handling.** Save-or-suck riders, breath-weapon
   cones, and area templates are first-class, not free-text.
4. **DM authority everywhere.** DM can override validation,
   force a hit/miss, apply / waive damage, mark recharge ready,
   restore reaction, set legendary uses, manually grant or remove
   conditions, etc.
5. **Reuse over reinvention.** The surface should reuse player LAN
   action-card and spell-modal patterns, not duplicate them.

### 4.2 Page anatomy

```
┌─────────────────── Monster control ───────────────────┐
│ Selected actor: Adult Red Dragon                      │
│ HP 256/256 · AC 19 · Init +12 · Speed 40/Climb 40/Fly │
│ Conditions: — · Concentration: — · Reaction: ready    │
│ Recharge: Fire Breath (5)  Legendary: 3/3             │
├───────────────────────────────────────────────────────┤
│ Action lane (tabs):                                   │
│  [Attacks]  [Spells/SLAs]  [Bonus]  [Reactions]       │
│  [Recharge] [Legendary]    [Lair]   [Move]  [Other]   │
├───────────────────────────────────────────────────────┤
│ Action cards (per tab):                               │
│   ┌─ Bite ─────────┐ ┌─ Claw ─────────┐ ┌─ Tail ────┐│
│   │ +14 to hit     │ │ +14 to hit     │ │ +14       ││
│   │ 19 piercing    │ │ 15 slashing    │ │ 17 bludg. ││
│   │ +7 fire        │ │                │ │           ││
│   │ [Use ×N]       │ │ [Use ×N]       │ │ [Use ×N]  ││
│   └────────────────┘ └────────────────┘ └───────────┘│
│   ┌─ Multiattack ──────────────────────────────────┐ │
│   │ Frightful Presence + 1×Bite + 2×Claw           │ │
│   │ [Run sequence]                                  │ │
│   └────────────────────────────────────────────────┘ │
│   ┌─ Fire Breath (Recharge 5–6) — READY ────────────┐│
│   │ 60-ft cone · DC 21 Dex · 18d6 fire (half)       ││
│   │ [Place cone] [Targets...] [Resolve] [Apply]     ││
│   └────────────────────────────────────────────────┘ │
├───────────────────────────────────────────────────────┤
│ Targeting / map: pick targets from initiative or map  │
├───────────────────────────────────────────────────────┤
│ Recent results / pending prompts                      │
└───────────────────────────────────────────────────────┘
```

### 4.3 Actor selection

- Default selection follows the active turn when in combat and the actor
  is a non-PC.
- DM can manually select any non-PC by clicking an initiative card,
  clicking a token on the map, or picking from a dropdown.
- Selecting a PC switches the surface into "DM tools on PC" mode (HP
  override, condition, initiative override, sheet preview) without
  exposing player-private adjudication paths. PCs continue to be played
  by the LAN player surface.

### 4.4 Action dashboard

Tabs are populated from the backend "available actions" contract for the
selected actor (see §7). Each tab renders typed action cards:

- **Attacks** — parsed melee/ranged attacks: name, range/reach,
  to-hit, damage entries (incl. riders like "+7 fire"), tag chips
  ("ranged", "two-handed", "spell attack"), and a "Use ×N" control.
  Implements the existing `monster-attacks/resolve` +
  `monster-attacks/apply-damage` flow plus a per-attack "Force hit /
  Force miss" override and "Crit on use" toggle.
- **Spells / Spell-like Abilities** — list backed by either a spellbook
  contract entry on the monster (preferred long-term) or a manually
  augmented per-monster ability list. Each entry shows level / slot
  cost / damage formula / save / target shape and uses the same backend
  spell adjudication that PCs already use.
- **Bonus** — bonus actions (Cunning Action, Digest Corpse, etc.).
- **Reactions** — both generic (Opportunity Attack) and monster-specific
  (Lair-triggered reaction, Snake Strike, etc.). Includes "ready /
  spent" state and a "Force usable" override.
- **Recharge** — abilities marked with `{@recharge N}`. Shows
  "ready / used", roll-recharge button (with override), and the underlying
  resolve action.
- **Legendary** — legendary action menu with cost ("Costs 2 Actions"),
  per-round budget, and "Spend immediately after this PC's turn".
- **Lair** — lair actions on initiative count 20 (or 2024-style integrated
  lair triggers). Visible only when the encounter is flagged as a lair
  encounter.
- **Move** — speed by mode (walk/climb/swim/fly/burrow), drop prone,
  stand up, squeeze, teleport, mount/dismount where applicable. Moves
  go through the existing tactical move APIs.
- **Other / Standard** — Dash, Disengage, Dodge, Help, Hide, Ready,
  Search, Study, Influence, Utilize, Magic. These are the standard
  2024 actions; most are no-mechanical-resolution but should be
  loggable and consume the right action economy slot.

### 4.5 Targeting and AoEs

- **Single-target picker:** combatant chips selected from the initiative
  list or by clicking a token on the embedded map. Multi-target where
  the action allows ("up to three eye rays at random").
- **AoE templates:** use the existing AoE placement/move/remove APIs
  (`/api/dm/map/aoes*`). For breath cones, lines, and bursts the page
  generates a temporary AoE, lets the DM nudge it on the map, then
  collects all caught combatants automatically.
- **Save resolution:** for save-DC actions, the DM can Roll-All-Saves,
  Pick-Per-Target, or Manual-Override. The page reuses the existing
  spell save adjudication plumbing where it can; for monster-only
  abilities it uses a save resolution helper colocated with the new
  monster execution model.

### 4.6 Resources, recharge, reactions

- A persistent resource panel for the actor: action / bonus / reaction
  state for the current turn, recharge state per recharge ability,
  legendary action uses, limited-use abilities ("3/Day"), spell slots
  if the monster is a real caster, condition immunities, ongoing
  conditions on the actor.
- "End Turn" routes through `CombatService.next_turn()` after running
  any auto-rolled recharge attempts and clearing per-turn budgets.
- Reactions can be triggered out-of-turn from the DM cockpit (unlike
  player surfaces which prompt opt-in).

### 4.7 Override controls

- Force hit / Force miss on any attack roll.
- Override damage total before apply.
- Set HP / temp HP / conditions / death-save state directly (already
  supported by `/api/dm/combat/combatants/{cid}/...`).
- Set recharge state to ready / spent.
- Restore reaction or legendary uses.
- Skip an action without spending the corresponding economy slot.

### 4.8 Logs and prompts

- Bottom rail shows the last N battle-log entries.
- Pending DM prompts (e.g., "Counterspell offered to Lich") are surfaced
  here so the DM does not lose them while focused on the action lane.

---

## 5. Monster YAML audit plan (Phase 0)

The audit must precede schema design. This phase is **read-only** and
produces a report and tooling, not data edits.

### 5.1 What to audit

For each `Monsters/*.yaml`:

1. Top-level field presence (`name`, `ac`, `hp`, `speed`, `abilities`,
   `senses`, `challenge_rating`, etc.).
2. Section emptiness: `actions`, `traits`, `legendary_actions`,
   `bonus_actions`, `reactions`.
3. Per-action structure: presence of `name` / `desc`; presence of
   `{@atk}`, `{@hit}`, `{@damage}`, `{@h}`, `{@dc}`, `{@condition}`,
   `{@spell}`, `{@recharge}`, `{@dice}`, `{@creature}`, `{@skill}`.
4. Multiattack handling: presence of "X attacks", "one with X and two
   with Y" phrases, recovery via `_parse_monster_attack_options`
   multiattack-counts logic.
5. Save-DC and AoE shape recoverability from text.
6. Spellcasting evidence: any monster whose nominal role implies
   spellcasting (Mage, Archmage, Lich, dragon-knight casters, etc.)
   but lacks a spell list.
7. Type/parse artifacts (e.g., Archmage `type: or Small Humanoid`).
8. Mashed-together multi-effect descriptions (e.g., Beholder Eye Rays).
9. Recharge marker presence vs. "Recharge X-Y" name fragments without
   the `{@recharge N}` form (so we know which auto-extraction style is
   needed).
10. Optional boss extensions (`turn_schedule`, `phases`) actually used.

### 5.2 Audit script / report

Add a read-only script under `scripts/audit/` (matching the existing
convention with `scripts/audit/spell_automation_audit.py`):

- `scripts/audit/monster_capability_audit.py`
  - reads every `Monsters/*.yaml`
  - runs the same parsing helpers the runtime uses
    (`_parse_monster_attack_options` accessor, plus new
    audit-specific extractors for save/recharge/spell/condition
    presence)
  - emits `Monsters/automation_audit.md` (or `docs/monster_capability_audit.md`)
    summarizing:
    - overall counts (one row per monster, fields per category)
    - per-category buckets (see §5.3)
    - notable malformed entries
    - "high-risk" monsters (legendary creatures, spellcasters, bosses
      where the gap will hurt the DM most)

The audit is intentionally not normative; it does not edit YAMLs.

### 5.3 Capability tiers

Each monster should be classified into one of:

- **Tier A — Fully actionable.** Every action recoverable into the
  internal schema, including multiattack composition, save-DC riders,
  recharge, and reactions if applicable.
- **Tier B — Partially actionable.** Attacks recover, but at least one
  action class (saves, AoE, recharge, reactions, legendary, spells) is
  missing or text-only.
- **Tier C — Display-only / freeform.** Action list non-empty but no
  parseable mechanics. Should still be displayable to the DM as a
  reference card.
- **Tier D — Empty / malformed.** `actions: []`, missing fields, parse
  artifacts, or unrecoverable structure.

Today, by §1.3 numbers, Tier D includes at least the ~139 monsters
with `actions: []`, and Tier B/C dominates the remainder.

### 5.4 Common data problems and risks

- **Empty action arrays** (~27%): need a minimum-viable manual
  enrichment path or a default-action-from-statblock fallback (e.g.,
  generate a single Strength-mod melee strike from `abilities.Str`).
- **Mashed-together effect blocks** (e.g., Beholder Eye Rays, dragon
  Multiattacks with mixed weapon/save bullets): need a per-monster
  manual decomposition or a structured override file.
- **Reactions are absent everywhere**: all monster reactions must be
  added at the schema level — there is nothing to migrate from.
- **Spellcasting is essentially absent**: the data layer cannot back
  even Archmage/Lich casting today.
- **AideDD markup variance**: the parser already handles common forms
  but not all (`{@atk ms}` vs `{@atk mw,rw}`, mashed `{@damage 1d8}` /
  `{@damage 1d8 + 2}`). Edge cases must be enumerated and either
  parsed or reported.
- **Type field artifacts** ("or Small Humanoid (Wizard)") are mostly
  cosmetic but indicate that the YAML pack has not been linted.

---

## 6. Proposed monster capability schema

The goal is a **normalized internal schema** that the backend hands to
the DM surface, *not* a final YAML syntax. The YAML can stay as a source
form; an additive overlay layer (or a derived `Monsters/normalized/*.json`
artifact) carries the executable shape.

### 6.1 Compatibility strategy

- The existing flat YAML schema in `Monsters/README.md` stays as-is for
  source compatibility (no breaking change to existing files).
- New executable fields are **additive overlays**, not in-place
  rewrites. They live under a new optional top-level key (e.g.,
  `capabilities:`), or in a sibling overlay file
  (`Monsters/_overlays/<slug>.yaml`) so the source-of-truth YAML pack
  stays loadable by external consumers.
- The runtime treats overlays as authoritative when present and falls
  back to text parsing when absent. No monster should require an
  overlay to be loadable.
- Auto-generated overlays from text-parsing become a build artifact
  under `Monsters/_normalized/` (gitignored or tracked separately,
  per cleanup policy).

### 6.2 Normalized capability shape

Top-level normalized record per monster:

```yaml
slug: adult-red-dragon
identity:
  name: Adult Red Dragon
  size: Huge
  type: Dragon (Chromatic)
  alignment: Chaotic Evil
  cr: "17"
defenses:
  ac: 19
  hp: { average: 256, formula: "20d12 + 100" }
  speed: { walk: 40, climb: 40, fly: 80 }
  resistances: []
  immunities: { damage: [Fire], conditions: [] }
  saves: { Str: +13, Con: +12, Wis: +6, Cha: +11 }
  passive_perception: 23
abilities: { Str: 27, Dex: 10, Con: 25, Int: 16, Wis: 13, Cha: 23 }
senses: { darkvision: 120, blindsight: 60 }
languages: [Common, Draconic]

resources:
  legendary_uses: { max: 3, lair_bonus: 1 }
  recharge: [{ id: fire-breath, range: [5, 6], state: ready }]
  per_day: []        # e.g., 3/Day Enslave
  spell_slots: {}    # only for real casters
traits:
  - id: legendary-resistance
    name: Legendary Resistance
    uses: { kind: per_day, max: 3, current: 3 }
    desc: "If the dragon fails a saving throw..."
actions:
  - id: bite
    kind: attack
    economy: action
    melee:
      to_hit: +14
      reach: 10
      target_count: 1
    damage:
      - { formula: "2d10 + 8", type: piercing, kind: weapon }
      - { formula: "2d6", type: fire, kind: rider }
  - id: claw
    kind: attack
    economy: action
    melee: { to_hit: +14, reach: 5, target_count: 1 }
    damage:
      - { formula: "2d6 + 8", type: slashing }
  - id: tail
    kind: attack
    economy: action
    melee: { to_hit: +14, reach: 15, target_count: 1 }
    damage:
      - { formula: "2d8 + 8", type: bludgeoning }
  - id: multiattack
    kind: composite
    economy: action
    sequence:
      - { use: frightful-presence, count: 1 }
      - { use: bite,                count: 1 }
      - { use: claw,                count: 2 }
  - id: frightful-presence
    kind: save_or_effect
    economy: action_part   # used inside multiattack; not free
    save: { ability: Wis, dc: 19 }
    range: { shape: aura, radius: 120 }
    on_fail: { conditions: [{ id: frightened, duration_rounds: 10, save_repeat: end_of_turn }] }
    on_success: { immunity: { window_hours: 24 } }
  - id: fire-breath
    kind: save_aoe
    economy: action
    recharge: { id: fire-breath }
    save: { ability: Dex, dc: 21 }
    range: { shape: cone, length: 60 }
    damage:
      - { formula: "18d6", type: fire, on_fail: full, on_success: half }
bonus_actions: []
reactions:
  - id: opportunity-attack
    kind: reaction
    trigger: { event: leaves_reach }
    use: bite
legendary_actions:
  - id: detect
    cost: 1
    kind: skill_check
    check: { ability: Wis, skill: Perception }
  - id: tail-attack
    cost: 1
    kind: attack_use
    use: tail
  - id: wing-attack
    cost: 2
    kind: save_aoe
    save: { ability: Dex, dc: 22 }
    range: { shape: aura, radius: 10 }
    damage:
      - { formula: "2d6 + 8", type: bludgeoning, on_fail: full, on_success: none }
    on_fail: { conditions: [{ id: prone }] }
    rider: { mover: self, max_distance: half_fly_speed }
lair_actions:
  - id: volcanic-vent
    initiative_count: 20
    kind: save_aoe
    save: { ability: Dex, dc: 15 }
    range: { shape: cell, radius: 0 }
    damage: [{ formula: "2d10", type: fire, on_fail: full, on_success: half }]
spellcasting:
  ability: Cha
  save_dc: 19
  attack_bonus: +11
  groups:
    - kind: at_will
      spell_slugs: [detect-magic, command]
    - kind: per_day
      max: 3
      spell_slugs: [hold-person, suggestion]
display:
  description: "..."
  habitat: "Hill, Mountain"
  treasure: "Any"
```

Key shape decisions:

- **Each action has a stable `id`** so multiattack and reactions can
  reference other actions by id (e.g., Wing Attack's `use: tail`).
- **`kind` is an enum** that drives execution: `attack`, `save_aoe`,
  `save_or_effect`, `composite`, `reaction`, `attack_use`,
  `skill_check`, `freeform`, `move`, etc.
- **`economy`** is one of `action`, `bonus`, `reaction`,
  `legendary`, `lair`, `free`, `action_part` (used inside a composite).
- **`damage` entries** are explicit formula+type, with an
  `on_fail` / `on_success` modifier when the action is gated by a
  save.
- **`range`** is a shape primitive (`cone`, `line`, `cube`, `sphere`,
  `aura`, `cell`) usable by the existing AoE placement APIs.
- **`recharge`** is a per-action reference into the `resources.recharge`
  list so state survives across actions.
- **`save`** carries `ability` + `dc` and optionally `mode`
  (`half_on_success` is implicit in damage's `on_success` field).
- **`display`** carries the human description + flavor for showing the
  raw stat block alongside the executable surface.

### 6.3 Display vs executable

Every action also keeps the original `desc` text under
`display.text`. The DM page renders `display.text` in a small
"stat block detail" alongside the executable card, both for sanity
checking and so Tier C / Tier D monsters still surface useful info
even when they have no executable structure yet.

### 6.4 Examples

**Simple attack** (Skeleton Shortsword):

```yaml
- id: shortsword
  kind: attack
  economy: action
  melee: { to_hit: +4, reach: 5, target_count: 1 }
  damage: [{ formula: "1d6 + 2", type: piercing }]
```

**Multiattack** (Adult Red Dragon, see §6.2 sequence).

**Recharge breath / save AoE** (Adult Red Dragon Fire Breath, see §6.2).

**Bonus action** (Corpse Flower Digest Corpse):

```yaml
- id: digest-corpse
  kind: heal_self
  economy: bonus
  preconditions: [{ has_resource: humanoid_corpse, min: 1 }]
  heal: { formula: "2d10", target: self }
  effects: [{ kind: consume_resource, id: humanoid_corpse, count: 1 }]
```

**Reaction** (Opportunity Attack):

```yaml
- id: opportunity-attack
  kind: reaction
  economy: reaction
  trigger: { event: leaves_reach }
  use: bite
```

**Legendary action** (Adult Red Dragon Wing Attack, see §6.2).

**Spellcasting / SLA**: spell groups carry `at_will`, `per_day`,
`per_rest`, `slot` — see §6.2 `spellcasting`.

**Passive trait / aura** (Aboleth Mucous Cloud):

```yaml
- id: mucous-cloud
  kind: passive_aura
  trigger: { event: enters_aura, scope: melee_within_5 }
  save: { ability: Con, dc: 14 }
  on_fail: { conditions: [{ id: diseased, custom: true, duration: hours_1d4 }] }
  display: { text: "While underwater, the aboleth..." }
```

### 6.5 Compatibility with current parsers

- The current `_parse_monster_attack_options` becomes the
  fallback path that hydrates a Tier-B/C action list when no overlay
  exists. Its output maps directly into `actions[i] = { kind: attack,
  melee/ranged: {...}, damage: [...] }`.
- `MonsterSpec.raw_data` continues to hold the YAML payload; the
  normalized layer is computed on first read and cached on the spec.

---

## 7. Backend execution model

The backend exposes a unified actor command surface that supports both
players and DM-controlled monsters, with three permission tiers and one
common adjudication core.

### 7.1 "What can this combatant do right now?"

Add a per-actor capability snapshot:

```
GET /api/dm/combat/combatants/{cid}/capabilities
```

Returns:

```json
{
  "actor": { "cid": 7, "name": "Adult Red Dragon", "is_pc": false },
  "economy": { "action": "available", "bonus": "available", "reaction": "ready" },
  "movement": { "remaining_ft": 40, "modes": ["walk","climb","fly"], "current_mode": "fly" },
  "resources": {
    "legendary": { "max": 3, "current": 3 },
    "recharge": [{ "id": "fire-breath", "state": "ready" }],
    "per_day": [],
    "spell_slots": {}
  },
  "actions": [...],          // capability shape, see §6.2
  "bonus_actions": [...],
  "reactions": [...],
  "legendary_actions": [...],
  "lair_actions": [...],
  "spellcasting": {...},
  "display": {...}
}
```

The DM page renders directly from this contract. A peer LAN endpoint
already implicitly exists for PCs (the existing snapshot + spellbook
contract), and the longer-term goal is for both surfaces to converge on
this shape.

### 7.2 Actor command shape

A new actor command envelope:

```json
{
  "type": "actor_command",
  "command": "attack" | "save_aoe" | "save_or_effect" | "composite" | "spell" |
             "move" | "dash" | "disengage" | "dodge" | "help" | "hide" |
             "ready" | "search" | "study" | "influence" | "utilize" | "magic" |
             "stand_up" | "drop_prone" | "teleport" | "use_legendary" |
             "use_lair" | "manual_override",
  "actor_cid": 7,
  "action_id": "fire-breath",     // resolves to the capability entry
  "spend": "action",              // economy slot to consume
  "targets": [3, 5, 9],           // explicit cids
  "aoe": { "shape": "cone", "anchor": {"col": 12, "row": 4}, "facing_deg": 90 },
  "rolls": {                      // optional pre-rolled dice from the DM
    "attack": [12, 7],
    "damage": { "fire": 63 },
    "save": [{ "cid": 3, "result": 9, "outcome": "fail" }]
  },
  "force": { "hit": false, "miss": false, "max": false, "min": false },
  "override": { "ignore_economy": false, "skip_log": false }
}
```

Why this shape:

- It generalizes attacks, saves, AoEs, spells, and standard 2024
  actions under one envelope so the DM page does not need a different
  endpoint per action class.
- The DM can pre-roll on the page and submit results, or let the
  backend roll. Either path produces the same battle log, broadcast,
  and snapshot.
- `force` and `override` give the DM authority levers without adding
  side endpoints.
- The same envelope can be reused, with stricter checks, for player
  actors as the player command family migration continues.

### 7.3 Where this lives in the code

- A new module `monster_command_service.py` (or
  `actor_command_service.py` if/when player flow consolidates)
  next to `combat_service.py` and `player_command_service.py`.
- `monster_command_service.py` exposes:
  - `capabilities(actor_cid)` — produces the §7.1 contract from
    `MonsterSpec` + normalized overlay + runtime resource state.
  - `execute(envelope)` — validates economy + targeting, dispatches into
    existing adjudication helpers (`_adjudicate_attack_request`,
    `_adjudicate_spell_target_request`, AoE damage rollers, save
    resolution helpers), and returns a unified result.
  - `set_recharge_state(actor_cid, action_id, state)`.
  - `restore_resource(actor_cid, kind, id, amount)`.
  - reaction prompt registration + resolution glue compatible with
    `PromptState` in `player_command_contracts.py`.
- Contracts go into a new `actor_command_contracts.py` (or extend
  `player_command_contracts.py`) modeled after the existing
  request/result + lifecycle envelope helpers.
- DM HTTP routes shift from the per-feature endpoints in §2.4 to a
  single `POST /api/dm/combat/combatants/{cid}/command` envelope, with
  the existing endpoints remaining for backward compatibility during
  the migration (and being removed once `/dm/monster` only uses the
  unified command).

### 7.4 Reuse from player command flow

Reusable as-is or with minor extension:

- attack adjudication (`_adjudicate_attack_request`) — drives monster
  attacks today, just needs the capability-id resolution layer.
- spell target adjudication (`_adjudicate_spell_target_request`) —
  drives monster spells today; needs to learn `slot=at_will`,
  `slot=per_day`, and accept monster spell groups.
- AoE shape / placement APIs (`/api/dm/map/aoes*`, AoE adjudicate flow).
- HP / temp HP / condition mutation through `CombatService`.
- Battle log + WebSocket broadcast.
- Reaction prompt lifecycle (`PromptState`, `SPECIAL_REACTION_TRIGGERS`).
- Pre-rolled-dice path (DM may hand-roll on the page).

Monster-specific bits that need new code:

- recharge state per action.
- legendary action budget per round (and "after another creature's
  turn" trigger).
- lair actions on initiative count 20 (or 2024-style integrated
  triggers).
- save-or-effect non-damage actions (charm, frighten, paralysis).
- monster spellcasting groups (`at_will`, `per_day`, slots).
- monster bonus actions and monster-specific reactions
  (none of which exist as data today).
- multiattack as a sequenced composite that consumes the action slot
  exactly once.

### 7.5 Permission tiers

The execution layer must distinguish three tiers explicitly:

1. **Player-on-own-PC** — the existing player command path. Strict
   economy/turn checks. Reactions opt-in via prompts. Hidden info
   preserved (DC not revealed pre-resolution).
2. **DM-on-any-combatant** — full authority. Can act for non-PC and PC
   combatants (e.g., NPC ally, possessed PC, downed PC's death save).
   Bypasses claim checks. Can submit pre-rolled dice. Can resolve
   reactions on others.
3. **DM override** — within "DM-on-any" tier, the DM can additionally
   bypass economy checks (`spend: none`), force hit/miss outcomes,
   override damage totals, and restore spent resources. Always
   logged with an "override" tag in the battle log so the audit trail
   is honest.

Tiers are encoded in the envelope (`override.ignore_economy`,
`force.hit`, etc.) and gated by admin-token presence on the DM-only
routes — the existing pattern from `_check_dm_auth`.

### 7.6 Reactions, prompts, targeting, AoEs

- Monster reactions become first-class data with explicit triggers
  (`event: leaves_reach`, `event: takes_damage_in_aura`,
  `event: hit_by_attack`, etc.).
- The capability snapshot exposes which reactions are currently usable.
- The DM can fire a reaction directly from the surface; reactive
  triggers can also auto-prompt the DM (e.g., "Goblin can use
  Disengage as a reaction — fire?") similar to the existing player
  reaction prompts.
- Targeting resolves combatant cids and / or AoE template payloads.
- Save resolution handles per-target outcomes, half-damage on success,
  condition application on failure, and concentration save chains.

### 7.7 Result reporting

Each `execute()` call returns a structured result that the DM page can
render verbatim:

```json
{
  "ok": true,
  "actor_cid": 7,
  "action_id": "fire-breath",
  "spent": { "action": true, "recharge": "fire-breath" },
  "rolls": { ... },
  "per_target": [
    { "cid": 3, "save": "fail", "damage": { "fire": 63 }, "removed": false },
    { "cid": 5, "save": "success", "damage": { "fire": 31 }, "removed": false }
  ],
  "log": [ "Adult Red Dragon breathes fire (DC 21). Cleric saves; Fighter fails. ..." ],
  "snapshot": { ... }                  // updated combat snapshot
}
```

---

## 8. UI / UX architecture

### 8.1 Two delivery surfaces

- **Standalone `/dm/monster`** route — MVP delivery, proves the
  surface, iterates fast.
- **DM cockpit integration** — once stable, the surface becomes the
  right-lane content of the unified cockpit (§3.2).

### 8.2 Monster-control MVP shape

Single-page web app, structured around the §4.2 anatomy:

- top bar: connection / auth / round / turn
- selected-actor header: identity + defenses + resources
- action lane: tabs + cards
- targeting: combatant chips and embedded mini-map widget
- bottom rail: log + pending prompts + last result

State management:

- on actor selection, fetch `/api/dm/combat/combatants/{cid}/capabilities`
- on combat snapshot WebSocket push, refresh capabilities for the
  selected actor
- action submission goes through the unified actor-command POST
- pre-rolled dice supported via inline roll inputs on each card
- override toggles (force hit/miss, ignore economy) live in a
  collapsible "DM override" subsection per card

### 8.3 Selected-actor panel

- Behaves identically in standalone and cockpit-integrated modes.
- Updates when the DM clicks an initiative card, clicks a token, or
  uses the dropdown.
- Shows distinct sub-mode for PCs (DM tools on PC: HP / condition /
  initiative override, sheet preview, no opaque adjudication).

### 8.4 Action cards

- Compact card per action with name, summary, economy chip, "Use ×N"
  button, and an expansion drawer for details, save/AoE controls,
  and override.
- Multiattack card renders a numbered sequence; each step can be
  "skip", "use as printed", or "swap with sibling action."
- Recharge cards have explicit ready/used state and a single
  "Recharge now" button (DM override) plus an automatic roll button.

### 8.5 Target picker and map interactions

- For single-target actions: show a chip row of valid combatants
  (in-range filtering optional based on capability metadata + map state).
- For AoE actions: open the embedded map widget with the right
  template overlay; DM nudges the template; "Resolve" sweeps caught
  combatants and runs save resolution.
- All map mutations go through existing `/api/dm/map/...` routes.

### 8.6 Logs / results / pending prompts

- Bottom rail surfaces:
  - last 30 battle-log lines
  - last action result with per-target breakdown
  - any pending DM prompt (e.g., "Counterspell available", "Reaction
    triggered")
- Battle-log entries link back to the action that produced them so the
  DM can re-open the result for inspection.

### 8.7 Keyboard / quick actions

Optional but high value:

- `1`–`5` to pick the first five actions on the current tab.
- `A` / `B` / `R` / `L` to switch to attack / bonus / reaction /
  legendary tabs.
- `Enter` to submit; `Shift+Enter` to submit with override.
- `Esc` to clear targeting.

### 8.8 Reuse from the player LAN page

The LAN page already has working patterns for:

- claim/turn-state header
- action / bonus / reaction chips
- spell modal layout with target picker
- AoE placement / move overlay
- condition icon row
- reaction prompt chips
- battle-log presentation

These should be lifted into shared CSS / JS partials (`assets/web/_shared/`)
and reused by both surfaces. The `majorTODO.md` 5.3 exploration track also
contemplates a TypeScript-first server-resident runtime; the shared partial
extraction is a good staging point because it normalizes the surface area
that would later move to TS components.

---

## 9. Migration phases

Each phase is bounded, has a clear validation footprint, and lists the
likely files. No phase widens into unrelated DM/map/framework work.

### Phase 0 — Monster YAML audit + backend capability inventory

**Goal:** know what the data actually supports before designing schema.

Likely changes:
- new `scripts/audit/monster_capability_audit.py` (read-only)
- new `docs/monster_capability_audit.md` (generated report) or
  `Monsters/automation_audit.md` per the existing
  `scripts/audit/spell_automation_audit.py` precedent
- new `scripts/audit/monster_backend_inventory.py` that lists every
  monster-related backend route, helper, and fall-back path so the
  Phase 2 design has an evidence-based starting point

Risks:
- false sense of completeness if the audit script's parser is too
  forgiving — it must be calibrated against the same regexes used by
  the runtime.

Validation:
- `python3 -m py_compile scripts/audit/monster_capability_audit.py`
- run against the live `Monsters/` and check the report by hand for
  five known monsters across tiers (skeleton, goblin-warrior,
  adult-red-dragon, beholder, archmage).

### Phase 1 — Normalized monster capability contract (LANDED)

**Goal:** define and ship the §6 schema as additive overlays + a
runtime hydration layer.

Completed:
- `monster_capability_service.py` (loader and matcher)
- `monster_capabilities/samples/*.yaml` (prototype overlays)
- `/api/dm/monster-capabilities` endpoints
- DM UI "Monster Capabilities" card with simple execution support
- Unit tests in `tests/test_monster_capability_service.py`

Risks:
- contract churn if rolled out before §7 is sketched in code; mitigate
  by writing a draft of §7's capability snapshot consumer before
  finalizing the contract.

Validation:
- `python3 -m unittest tests.test_monster_capability_contracts`
- `python3 -m unittest tests.test_monster_capability_loader`
- spot-check the normalized output for the five known monsters above.

### Phase 2 — Backend actor / combatant command API

**Goal:** ship the unified `execute()` envelope and capabilities GET
endpoint.

Likely changes:
- new `monster_command_service.py` (or `actor_command_service.py`) +
  contracts
- new route `GET  /api/dm/combat/combatants/{cid}/capabilities`
- new route `POST /api/dm/combat/combatants/{cid}/command`
- preserve the existing per-feature DM monster routes for
  back-compat; mark them deprecation-tagged in code comments
- thread reactions / recharge state into the snapshot broadcast

Risks:
- adjudication regressions if the new path bypasses logging/broadcast
  hooks; mitigate by having `execute()` go through the same
  broadcast helpers as the existing routes.

Validation:
- `python3 -m unittest tests.test_actor_command_service` (new)
- `python3 -m unittest tests.test_dm_combat_service`
- `python3 -m unittest tests.test_dm_map_attack_automation`
- `python3 -m unittest tests.test_lan_attack_request`
- regression run on the five known monsters (smoke-level integration).

### Phase 3 — Monster-control MVP route / page

**Goal:** ship `/dm/monster` as a working DM surface backed by Phase 2.

Likely changes:
- new `assets/web/dm_monster/index.html` + CSS / JS, ideally lifting
  shared chrome/cards from `assets/web/lan/index.html` into
  `assets/web/_shared/` first
- new server route `GET /dm/monster` mirroring `/dm` / `/dm/map`
  (consider the `__DM_WORKSPACE__` token approach for consistency)
- DM auth identical to `/dm`

Risks:
- duplicating LAN action UI rather than reusing it; mitigate with the
  shared-partial extraction step before MVP UI work.

Validation:
- `python3 -m py_compile dnd_initative_tracker.py` (route addition)
- `python3 -m unittest tests.test_dm_tactical_map_routes` and any new
  `tests.test_dm_monster_route` covering auth/HTML serving
- manual browser smoke against five known monsters
- check `node scripts/validation/check-lan-script.mjs` if shared JS
  templates are introduced

### Phase 4 — DM cockpit integration and `/dm/map` de-duplication

**Goal:** fold `/dm/monster` into the unified cockpit right-lane.

Likely changes:
- update `assets/web/dm/index.html` to embed the monster-control
  surface as the right-lane content when the selected actor is a
  non-PC; show the existing setup/live-play cards otherwise
- progressively de-emphasize the standalone `/dm/monster` route (keep
  the route alive as a "focus mode" option)
- evaluate whether `/dm/map` can be deprecated to a workspace toggle
  inside `/dm` once the unified layout is proven

Risks:
- regressing the cockpit responsiveness work landed in `majorTODO.md`
  3.2; mitigate by performance-budgeting the right-lane (no synchronous
  capability calls during snapshot rebuild).

Validation:
- `python3 -m unittest tests.test_dm_tactical_map_routes`
- targeted JS asset tests for cockpit integration
- live-session smoke that confirms `/dm/map` still works during the
  transition (no immediate deletion)

### Phase 5 — Monster YAML migration / cleanup and validation tooling

**Goal:** raise the median monster from Tier C/D toward Tier B/A.

Likely changes:
- new `scripts/migration/normalize_monsters.py` that produces overlay
  YAMLs for Tier-D monsters using the existing parser + targeted
  manual decomposition rules (e.g., Beholder Eye Rays split into
  N save_or_effect entries by ray index)
- new `scripts/validation/validate_monsters.py` that fails if a
  monster slug used in saved encounters/sessions has no usable
  capability snapshot
- enrich a focused subset of high-value monsters first (CR ≥ 8,
  named bosses, common encounter staples)

Risks:
- breaking saved session compatibility; mitigate by keeping overlays
  additive and the source YAML untouched
- accidental data invention; overlays must cite the source YAML
  passage they were derived from (`source_desc:` field)

Validation:
- `python3 -m unittest tests.test_monster_capability_loader`
- `python3 -m unittest tests.test_monster_stat_blocks`
- spot-check normalized output for top-N enriched monsters

### Phase 6 — Advanced actions and automation helpers

**Goal:** legendary, lair, spellcasting, recharge, reactions, AI nudges.

Likely changes:
- legendary action budget per round, "after another creature's turn"
  prompt
- lair-action initiative-count-20 trigger (or 2024-style integrated
  trigger)
- monster spellcasting group support (at-will / per-day / slots) using
  existing spell adjudication
- automatic recharge roll at start of monster's turn, with override
- reaction trigger detection (opportunity attack, take-damage, in-aura)
  with DM-confirmation prompts
- optional morale / flee / AI hint helpers — surfaced to the DM as
  suggestions, not automation

Risks:
- automation creep — these helpers must stay advisory and explicitly
  DM-cancellable
- per-encounter complexity (lair vs non-lair, phase shifts)

Validation:
- focused tests per advanced action class
- manual full-encounter smoke on Adult Red Dragon (the canonical
  exercise of legendary + recharge + AoE + multi-attack)

---

## 10. Testing strategy

### 10.1 YAML / schema validation

- `tests/test_monster_capability_contracts.py` — round-trip tests for
  every action `kind`, every economy slot, every shape primitive.
- `tests/test_monster_capability_loader.py` — parser fallback,
  overlay precedence, malformed inputs, partial structures.
- `tests/test_monster_yaml_audit.py` (read-only audit smoke) — runs
  the audit script on a small fixture set and asserts category
  bucketing matches expectations.
- Existing `tests/test_monster_stat_blocks.py` continues to cover
  display payload generation; should be extended once the loader
  exposes capability records.

### 10.2 Backend action-contract tests

- `tests/test_actor_command_contracts.py` — command envelope shape +
  permission tier gating.
- `tests/test_actor_command_service.py` — `capabilities()` correctness,
  `execute()` paths for attack / save_aoe / save_or_effect / composite /
  spell / move / standard 2024 actions, override behavior, error
  surfaces, broadcast/log integration.
- `tests/test_lan_action_message_types_allowlist.py` regression — the
  new actor command envelope must not silently broaden the LAN
  player allowlist.

### 10.3 Monster action execution tests

- `tests/test_monster_attack_execution.py` — multiattack composition,
  pre-rolled dice path, force hit/miss override, AoE save resolution.
- `tests/test_monster_recharge_state.py` — recharge state lifecycle
  (ready/used/recharged), per-action references, persistence across
  rounds.
- `tests/test_monster_legendary_actions.py` — budget per round, "after
  another creature's turn" trigger, lair bonus.
- `tests/test_monster_lair_actions.py` — initiative-count-20 trigger,
  lair-encounter flag.
- `tests/test_monster_spellcasting_groups.py` — at-will / per-day /
  slot adjudication.

### 10.4 LAN / DM route tests

- `tests/test_dm_monster_capabilities_route.py` — auth, snapshot
  shape, hidden-info preservation.
- `tests/test_dm_monster_command_route.py` — envelope dispatch,
  override gating, snapshot/broadcast invariants.
- `tests/test_dm_monster_page_serving.py` — `/dm/monster` HTML serving,
  `__DM_WORKSPACE__` injection.
- Existing `tests/test_dm_combat_service.py`,
  `tests/test_dm_tactical_map_routes.py`,
  `tests/test_dm_map_attack_automation.py`, and reaction-specific
  tests must keep passing throughout.

### 10.5 JS asset tests

- `node scripts/validation/check-lan-script.mjs` continues to gate
  shared LAN/DM JS partials.
- Add a Node-backed test for the new monster-control page's action-card
  rendering and capability-contract consumption (matching the existing
  pattern from LAN websocket lifecycle tests).

### 10.6 Integration / manual test plans

For each phase, a short live-session checklist:

- run a Skeleton (Tier A simple) attack, multiattack-less.
- run a Goblin Warrior (Tier D empty) — confirm Tier-D fallback action
  ("default Strength strike") generated correctly and editable by DM.
- run an Adult Red Dragon (Tier B advanced) full turn:
  Frightful Presence → Bite → Claw ×2 → Fire Breath after recharge.
- run a Beholder (Tier B mashed) eye rays from a structured
  per-ray menu (post-Phase-5 enrichment).
- run an Aboleth (Tier B with passive aura) Mucous Cloud reaction
  flow.
- run a Lich (Tier B with legendary + spellcasting overlay) full
  encounter.

### 10.7 Player command regression coverage

Monster work must not break:

- `tests/test_lan_attack_request.py`
- `tests/test_lan_spell_target_request.py`
- `tests/test_lan_aoe_*` (multiple files)
- `tests/test_*_reaction.py` (shield, counterspell, hellish rebuke,
  absorb elements, spell stopper)
- `tests/test_lan_action_message_types_allowlist.py`
- `tests/test_dm_combat_service.py`
- `tests/test_headless_host.py`

---

## 11. Risks and open questions

1. **Licensing / data source.** AideDD-derived 2024 monster text is in
   `Monsters/`. The existing schema doc already calls out the licensing
   situation. Overlays that add executable structure should not paste
   substantial new text — they should cite the source description and
   add machine-readable fields. Any future ingestion of additional
   monster sets must be reviewed for license compatibility before
   landing in the repo.

2. **2014 vs 2024 rules / data mismatch.** The data is nominally 2024,
   but the action / economy / damage idioms in the descriptions vary.
   The capability schema in §6 maps cleanly onto 2024-style economy
   (action / bonus / reaction / legendary / lair) while still expressing
   2014-era constructs (no breaking change for legacy SRD content). The
   open question is whether rules-edition flagging should live on the
   action (e.g., `rules: 2024`) or on the monster as a whole. Decide
   during Phase 1.

3. **Messy YAML migration.** Tier-D monsters (~27% empty `actions`) and
   mashed Tier-B descriptions (Beholder, dragon multiattack texts)
   resist automation. The plan deliberately puts overlay enrichment
   in Phase 5, after the surface and contract are proven, so we can
   prioritize the most-played monsters first.

4. **UI complexity.** A full action dashboard with eight tabs and per-card
   detail can feel heavier than the player surface. Default layout
   should prioritize the active turn's most-likely actions (Attacks,
   Multiattack, Recharge if applicable) and hide unused tabs when the
   monster has nothing in that category.

5. **Action automation scope creep.** Auto-rolling recharge, auto-firing
   reactions, and AI nudges are tempting but risky. The plan keeps these
   advisory in Phase 6 and never automatic without DM confirmation.

6. **Preserving existing encounters / saves.** Overlays are additive
   and source YAMLs are untouched, so saved sessions keep loading.
   Validation tooling in Phase 5 ensures that monster slugs used in
   saved sessions resolve to a usable capability snapshot.

7. **Route naming.** `/dm/monster` is the recommended namespace, but
   `/monster-control` reads better in isolation. Decide before Phase 3.

8. **Should `/dm/map` be deprecated immediately or gradually?**
   **Gradually.** §3 keeps it alive until the unified cockpit demonstrably
   covers map-first operation; after that, demote to a workspace toggle
   inside `/dm` and remove the route in a separate cleanup pass.

9. **Hidden information.** PCs cannot see monster save DC, AC, HP, or
   spellcasting modifiers pre-encounter. The capability snapshot is
   served only to DM-auth'd clients. The unified actor envelope must
   preserve that invariant when player flow eventually consolidates onto
   it.

10. **Concurrency.** Existing `CombatService` lock semantics must extend
    to `monster_command_service.execute()`. The lock is already
    re-entrant; the new path must hold it for the same window the old
    `_dm_monster_*` helpers do.

---

## 12. Recommended next implementation pass

The next pass after this plan should be **Phase 0 — Monster YAML audit
and backend capability inventory**. It is read-only, low risk, and
produces the evidence needed to lock in the §6 schema.

### 12.1 Concrete pass

1. Add `scripts/audit/monster_capability_audit.py`:
   - load every `Monsters/*.yaml` via the same YAML loader the runtime
     uses
   - reuse / extract the regex patterns from
     `_parse_monster_attack_options` so the audit is calibrated to the
     runtime
   - emit a categorized report (Tier A / B / C / D, see §5.3) plus per-
     monster diagnostic flags (missing actions, mashed effects, type
     parse artifacts, recharge presence, save presence, spell refs,
     reactions presence, optional boss extension presence)
2. Add `scripts/audit/monster_backend_inventory.py`:
   - enumerate every DM monster route, helper, and fall-back path in
     `dnd_initative_tracker.py`
   - list which existing tests cover them
3. Write `docs/monster_capability_audit.md` and
   `docs/monster_backend_inventory.md` summarizing the report.
4. Update `majorTODO.md` with a short pointer to this plan and Phase 0
   ownership.

### 12.2 Files to inspect (no edits in this next pass beyond docs/scripts/majorTODO pointer)

- `Monsters/*.yaml`
- `Monsters/README.md`
- `dnd_initative_tracker.py`:
  - `MonsterSpec` (~line 1705)
  - `_parse_monster_attack_options` (~line 29476)
  - `_monster_attack_options_for_map` (~line 29584)
  - `_dm_monster_attack_options` / `_dm_resolve_monster_attack_sequence`
    / `_dm_apply_monster_attack_damage` /
    `_dm_monster_perform_action` / `_dm_monster_spell_target`
    (~lines 43380–43614)
- `combat_service.py`
- `player_command_service.py`, `player_command_contracts.py`
- `assets/web/dm/index.html` (monster-turn lane, lines 835–912)
- `tests/test_dm_combat_service.py`,
  `tests/test_dm_map_attack_automation.py`,
  `tests/test_monster_stat_blocks.py`,
  `tests/test_lan_attack_request.py`

### 12.3 Validation for the next pass

- `python3 -m py_compile scripts/audit/monster_capability_audit.py`
- `python3 -m py_compile scripts/audit/monster_backend_inventory.py`
- run the audit scripts against the live `Monsters/` directory
- spot-check the report against five canonical monsters (skeleton,
  goblin-warrior, adult-red-dragon, beholder, archmage)
- `git diff --check` and `git status --short` to confirm only the
  intended files changed

### 12.4 Out of scope for the next pass

- no edits to `Monsters/*.yaml`
- no schema implementation
- no UI work
- no new `/dm/monster` route
- no changes to the existing DM monster routes
- no `/dm/map` deprecation

---

## Appendix A — Cross-references

- `majorTODO.md` — durable platform tracker; this plan should be
  pointed to from Section 4 (corrective product passes) or Section 5
  (long-term direction), not Section 3 (current stabilization), because
  it is a deferred multi-phase initiative rather than an active
  stabilization slice.
- `docs/dm-web-migration.md` — DM web console + backend service
  authority; describes the existing combat-service seam this plan builds
  on.
- `docs/shop_inventory_design.md` — example of a frozen design contract
  doc in this repo; this plan follows the same flat `docs/` placement
  convention.
- `Monsters/README.md` — current YAML schema documentation.
- `AGENTS.md`, `CLAUDE.md`, `GEMINI.md` — agent guardrails consulted
  while writing this plan.
