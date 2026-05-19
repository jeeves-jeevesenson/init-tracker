# DM / LAN Spell Engine Living Plan

_Last updated: 2026-05-19_

This document is the coordination point for future agents working on spell functionality, player LAN spell casting, DM Toolbox rest controls, and related combat latency. Keep it current after every pass. Do not treat it as a static spec.

## Current operating context

The live tester notes indicate that spell functionality is not failing as isolated one-off spells. The failures cluster around shared spell primitives:

- AoE placement appears but resolves to nothing.
- Some spells enter an AoE/targeting state and trap the player there.
- Reset Turn can leave local AoE/concentration ghosts on the map until page reload.
- Manual Override spell-slot `+1` appears to do nothing.
- Some range/origin checks reject adjacent targets incorrectly.
- Summon placement appears to accept clicks but spawned creatures do not appear on other clients.
- Player-side menu/drop-up needs an obvious visible button.
- The tester perceived delay and ambiguity: some actions looked broken, then later completed.

Primary tester evidence is in the raw note file supplied May 19, 2026. Agents should read that file before changing implementation. The important issue is the pattern, not the wording.

## Design directive from project owner

The spell system must be backend-heavy, efficient, and primitive-driven.

Do **not** implement spells as a growing pile of `if spell_name == ...` branches. Most spells share mechanics with only a different "coat of paint." The desired engine is:

```text
spell data
→ normalized/compiled backend spell plan
→ generic validation
→ generic target acquisition
→ generic save/attack/effect resolver
→ mutation bundle
→ one commit
→ one broadcast/snapshot
→ explicit result back to client
```

The anti-pattern is:

```text
if Fireball...
if Shatter...
if Thunderwave...
if Slow...
if Banishment...
if Glyph...
```

Small spell-specific overrides are allowed only when a generic primitive cannot model the spell. Any override must be documented in a registry table and covered by a targeted test.

## Rules research anchors

These references are here so future agents do not guess spell rules or invent inconsistent targeting behavior.

### Spell descriptions and shared spellcasting frame

D&D spell descriptions expose common fields: name, level, school, casting time, range, components, duration, and effect text. Backend code should normalize those fields into cast plans instead of repeatedly interpreting raw text at cast time.

Reference:
- D&D Beyond Basic Rules 2014, Chapter 10: Spellcasting — https://www.dndbeyond.com/sources/dnd/basic-rules-2014/spellcasting
- 5e SRD spellcasting mirror — https://5thsrd.org/spellcasting/casting_a_spell/

### Range and self-origin spells

Important rule: normal ranged spells target either a creature/object or a point in space. Self-origin cones and lines have range `Self`; their point of origin is the caster.

Implementation consequence:

- `Fireball`: point-origin AoE within spell range.
- `Thunderwave`, `Burning Hands`, `Lightning Bolt` style spells: caster-origin directional area.
- Do not use the same origin/range code for point AoEs and self-origin directional AoEs.

### Areas of effect

AoE shapes should be represented by a small shape primitive set:

- cone
- cube
- cylinder
- line
- sphere

Every AoE has a point of origin. AoE effects expand in straight lines from that origin, and total cover/blocked line of effect excludes cells/targets.

Implementation consequence:

- A generic `resolve_area_targets(...)` function should compute target sets for all AoE spells.
- Spell code should feed shape/dimensions/origin into the primitive resolver.
- Shape math and line-of-effect rules should not live inside individual spell handlers.

### Concentration

Concentration can be ended at any time without an action. Casting another concentration spell ends the prior concentration spell. Losing concentration ends the spell.

Implementation consequence:

- Concentration state must be backend authoritative.
- Recasting a concentration spell should remove/expire prior concentration effects owned by that caster.
- Local AoE ghosts from cancelled or failed casts must be cleared.
- Persistent concentration AoEs must be linked to concentration ownership so they can be removed automatically.

### Resting and long rest

2014 Basic Rules long rest baseline: a long rest is at least 8 hours. At the end, a character regains all lost HP and regains spent Hit Dice up to half their total Hit Dice, minimum one. The spellcasting rules also imply long-rest resource recovery for spell slots where class features grant slots by long rest.

Implementation consequence:

- DM Toolbox Long Rest must not be HP-only.
- It should restore HP, spell slots, long-rest resource pools, death saves/turn-local state, and optionally concentration/persistent effects.
- Hit Dice recovery should be explicit because 2014 and 2024 rules differ. Default to project/table rules, not silent assumptions.

Reference:
- D&D Beyond Basic Rules 2014, Chapter 8: Adventuring / Resting — https://www.dndbeyond.com/sources/dnd/basic-rules-2014/adventuring

## Current issue map from tester notes

### P0: AoE spell placement resolves to nothing

Reported examples:

- Fireball
- Glyph of Warding
- Lightning Bolt
- Wall of Fire
- Wall of Force
- Disintegrate
- Synaptic Shock / Synaptic Static equivalent
- Thunderwave
- Shatter
- Sleet Storm
- Control Water
- Create/Destroy Water

Observed user flow:

```text
Cast Spell clicked
modal closes
AoE preview appears
player clicks/places/confirms AoE
nothing appears in battle log
no damage/effect is applied
no useful toast/error appears
```

Correct behavior:

Every AoE placement must produce exactly one explicit result:

- applied to N targets,
- no targets in area,
- created persistent effect,
- opened manual resolution prompt,
- rejected with a reason,
- unsupported and requires DM/manual resolution.

Silent success/failure is not acceptable.

### P0: Pending AoE/concentration cleanup broken

Observed:

- Reset Turn after an AoE can leave the AoE on the map.
- Reloading the page clears some ghosts.
- Concentration-style effects may linger incorrectly.

Correct behavior:

- Pending local placement ghosts clear on cancel, reset turn, rejected cast, and successful authoritative update.
- Authoritative persistent effects remain only when the backend created them.
- Concentration-linked persistent effects clear when concentration ends or is replaced.

### P0: Modal/targeting state traps player

Reported examples:

- Dispel Magic
- Slow
- Phantasmal Killer
- Dimension Door

Correct behavior:

- The player can always cancel out of spell targeting.
- Reset Turn must clear pending client-side spell interaction state.
- Utility/manual spells must not enter broken AoE placement just because the spell data is ambiguous.

### P1: Manual Override spell slots look dead

Reported:

- Vicnor: Manual Override spell slot `+1` did nothing, repeatable, no error.

Correct behavior:

- `+1` on depleted slot restores one current slot and updates immediately.
- `+1` on full slot displays `Already at max slots`.
- Backend returns before/after counts.
- Battle log or admin log records the override.
- No silent no-op.

### P1: Range/origin false rejection

Reported:

- Fount of Moonlight says a target is too far away even when adjacent.

Correct behavior:

- Self buffs should not ask for hostile target selection unless the spell plan says there is a reaction/secondary target.
- Self-origin auras should use caster origin.
- Melee-adjacent checks must use the app's grid/cell distance consistently.

### P1: Summons do not appear authoritatively

Reported:

- Create Undead requests placement, player shift-clicks open spaces, but no undead appear on other sites.

Correct behavior:

- Summon placement must either create authoritative spawned combatants and broadcast them, or create a DM-facing pending summon request.
- Do not allow local-only summon ghosts.

### P2: Player-side visible menu button

Reported:

- Player forgot how to open drop-up menu.

Correct behavior:

- Add visible `Menu` / `More` button that opens the existing player-side menu.
- Keep existing shortcut/gesture.

## Backend architecture target

### Core objects

Introduce a small backend spell engine layer. Preferred names are flexible, but the responsibilities should stay clear.

```python
@dataclass(frozen=True)
class CompiledSpellPlan:
    spell_id: str
    name: str
    level: int | None
    casting_time: str | None
    action_cost: str  # action | bonus_action | reaction | longer | none/manual
    range: SpellRange
    concentration: bool
    duration: str | None
    targeting: TargetingPlan
    resolution: tuple[ResolutionStep, ...]
    persistence: PersistencePlan | None = None
    summon: SummonPlan | None = None
    manual: ManualPlan | None = None
```

```python
@dataclass
class SpellCastContext:
    caster_cid: int
    spell_id: str
    cast_level: int | None
    origin: Point | None
    direction: Direction | None
    selected_target_cids: list[int]
    client_request_id: str | None
    map_revision: int | None
    combat_revision: int | None
```

```python
@dataclass
class SpellCastResult:
    ok: bool
    status: str
    spell_id: str
    spell_name: str
    caster_cid: int | None
    message: str
    target_cids: list[int]
    aoe_ids_added: list[str]
    aoe_ids_removed: list[str]
    hp_changes: list[dict]
    conditions_added: list[dict]
    resources_spent: list[dict]
    log_entries: list[str]
    reason: str | None = None
    needs_manual_damage: bool = False
    needs_target: bool = False
    needs_placement: bool = False
    needs_dm_action: bool = False
```

```python
@dataclass
class MutationBundle:
    hp_changes: list[HpChange]
    conditions_added: list[ConditionChange]
    conditions_removed: list[ConditionChange]
    resources_spent: list[ResourceChange]
    spell_slots_changed: list[SpellSlotChange]
    aoes_added: list[MapEffect]
    aoes_removed: list[str]
    spawned_combatants: list[Combatant]
    concentration_changes: list[ConcentrationChange]
    log_entries: list[str]
```

### Status values

Use explicit spell result statuses. Suggested enum values:

```text
CAST_APPLIED
CAST_CREATED_PERSISTENT_EFFECT
CAST_NEEDS_MANUAL_DAMAGE
CAST_NEEDS_TARGET
CAST_NEEDS_PLACEMENT
CAST_NO_TARGETS
CAST_REJECTED
CAST_COUNTERSPELL_PENDING
CAST_SUMMON_PENDING_DM
CAST_SUMMON_CREATED
CAST_UTILITY_LOGGED
CAST_CANCELLED
```

The frontend should show the message and clear/retain pending state based on this status.

### Primitive taxonomy

Classify spells into these primitives before implementing details:

1. `single_target_attack`
2. `single_target_save`
3. `multi_target_selected`
4. `point_aoe_instant`
5. `self_origin_directional_aoe`
6. `persistent_area_effect`
7. `self_buff`
8. `target_buff_or_debuff`
9. `utility_manual`
10. `summon`
11. `movement_or_teleport`
12. `reaction_or_triggered_effect`

A spell may combine primitives, but the cast pipeline should still use reusable steps.

## Performance requirements

These are hard requirements unless a future measured report proves otherwise.

- No YAML parsing during a cast.
- No spell index rebuild during a cast.
- No repeated player profile load during a cast.
- No repeated target scanning per effect step.
- No broadcast from inside low-level resolver helpers.
- No full snapshot rebuild until all mutations are committed.
- No frontend-only authority for AoE, summon, spell-slot, HP, or concentration state.
- No silent no-op paths.
- Every cast/override/rest action must return an explicit result object or websocket ack.

Desired hot path:

```text
receive cast request
lookup compiled plan O(1)
validate resources/action/range
compute target set once
build mutation bundle
commit mutations
append log entries
broadcast once
return explicit result/snapshot/patch
```

## Existing code surfaces to inspect first

### Backend

- `dnd_initative_tracker.py`
  - `_handle_cast_spell_request`
  - `_handle_cast_aoe_request`
  - `_lan_auto_resolve_cast_aoe`
  - `_lan_prompt_manual_aoe_damage`
  - `_map_spell_effect_targets`
  - `_register_map_spell_effect`
  - `_clear_map_spell_effect`
  - `_spell_presets_payload`
  - LAN websocket send/broadcast helpers
- `player_command_service.py`
  - `manual_override_spell_slot`
  - `manual_override_resource_pool`
  - `reset_turn`
- `combat_service.py`
  - `batch_long_rest_heal`
  - future rest/resource service seams
- `monster_capability_service.py`
  - useful reference for capability result modeling, not a direct copy target

### Frontend

- `assets/web/lan/index.html`
  - cast modal
  - pending AoE placement
  - pending target selection
  - manual override controls
  - reset-turn controls
  - websocket message handling
- DM console toolbox area where rest controls should land later.

Frontend work should be mostly result rendering and pending-state cleanup. Do not move authority into JavaScript.

## Pass plan

### Pass 0 — Baseline and guardrails

Goal: establish current behavior and prevent broad wandering.

Tasks:

- Run focused current tests and record baseline failures.
- Add/refresh a runtime report under `docs/runtime_reports/`.
- Capture grep map of current spell routes/handlers.
- Do not add new features in this pass.

Suggested checks:

```bash
python -m py_compile dnd_initative_tracker.py player_command_service.py combat_service.py
python -m pytest -q tests/test_dm_console_asset_syntax.py
python -m pytest -q tests/test_dm_control_apply_results.py
```

Add more focused tests as discovered, but do not block on unrelated historical failures.

### Pass 1 — Explicit spell result contract

Goal: no spell action can silently vanish.

Tasks:

- Introduce `SpellCastResult` or equivalent serializable result.
- Make AoE and targeted spell handlers return/send explicit results.
- Add websocket/client ack message such as `spell_cast_result`.
- Include `ok`, `status`, `message`, `spell_name`, `target_count`, and `reason`.
- Add battle-log entry for `CAST_NO_TARGETS` and unsupported/manual outcomes.

Acceptance:

- Fireball on empty area says `Fireball hit no targets.`
- Unsupported/manual spell says what it needs.
- Rejected placement gives a reason.
- Tester never sees "nothing happened" with no toast/log/ack.

### Pass 2 — AoE primitive resolver

Goal: one reliable backend path for point AoEs and self-origin directional AoEs.

Tasks:

- Implement/normalize area target acquisition by shape.
- Separate point-origin AoE from self-origin directional AoE.
- Compute target set once per cast.
- Ensure friendly-fire behavior is explicit in plan/result.
- Ensure no-target result is distinct from resolver failure.

Primitive coverage:

- `point_aoe_instant`: Fireball, Shatter, Synaptic Static.
- `self_origin_directional_aoe`: Thunderwave, Burning Hands, Lightning Bolt, Gust of Wind.
- `persistent_area_effect`: Wall of Fire, Wall of Force, Sleet Storm, Create/Destroy Water.

Acceptance:

- Point AoE with targets resolves or opens manual damage prompt.
- Point AoE with no targets gives explicit no-target result.
- Directional AoE uses caster origin and direction.
- Persistent effect creates authoritative map effect or explicit manual/unsupported result.

### Pass 3 — Pending state and cleanup

Goal: spell modal, AoE placement, and reset/cancel cannot trap the player.

Tasks:

- Define frontend cleanup behavior by backend status.
- Clear pending local AoE placement on cancel, reset-turn, rejected cast, no-target result, and successful authoritative update.
- Keep only authoritative backend AoEs after server ack.
- Add explicit `cancel_spell_cast` or reuse existing reset/cancel command with backend ack if needed.
- Link concentration effects to caster/concentration state.

Acceptance:

- Reset Turn clears abandoned placement ghosts.
- Page reload is not required to escape a stuck AoE.
- Dimension Door / Dispel Magic / Slow / Phantasmal Killer do not trap the modal.

### Pass 4 — Concentration and persistent effects

Goal: concentration effects behave predictably and do not leak.

Tasks:

- Add backend concentration ownership model if missing.
- When a caster starts a concentration spell, end prior concentration and remove linked AoEs/effects.
- Add explicit `Drop Concentration` path.
- Make persistent map effects distinguish:
  - pending local preview,
  - authoritative active effect,
  - expired/removed effect.

Acceptance:

- Casting a new concentration spell removes prior concentration-linked effect.
- Dropping concentration removes linked persistent effect.
- Reset Turn does not leave pending local concentration AoE ghosts.

### Pass 5 — Manual Override spell slots and resources

Goal: manual resource controls visibly work and never silently no-op.

Tasks:

- Backend returns before/after values for spell-slot/resource override.
- Frontend updates immediately from result or authoritative snapshot.
- Full-slot increment gives a visible `Already at max` result.
- Add logging/audit line for manual override.

Acceptance:

- `+1` on depleted slot increments.
- `+1` on full slot explains why it did nothing.
- No error text absence on failed/rejected override.

### Pass 6 — Summon primitive

Goal: summon spells are authoritative or explicitly DM-pending.

Tasks:

- Model summon as a backend primitive.
- Decide per spell/plan whether player can spawn directly or creates a DM pending request.
- Authoritative spawn must create combatants, assign owner/source spell, place tokens, broadcast once.
- DM-pending request must appear somewhere visible to DM.

Acceptance:

- Create Undead / Summon Construct no longer create local-only ghosts.
- Spawned units appear on all clients, or the caster receives `DM must place summon` result.

### Pass 7 — DM Toolbox Long Rest

Goal: DM can reset player resources from the DM console/toolbox.

Minimum button:

```text
DM Toolbox
  Rest Controls
    Long Rest Players
```

Confirmation options:

```text
[x] Restore HP
[x] Restore spell slots
[x] Restore long-rest resource pools
[x] Clear death saves / turn state
[x] Clear temp HP
[x] End concentration effects
[x] Remove concentration AoEs
[ ] Include NPC allies
[ ] Include enemies
```

Backend route shape:

```http
POST /api/dm/combat/long-rest
```

Payload shape:

```json
{
  "scope": "players",
  "restore_hp": true,
  "restore_spell_slots": true,
  "restore_long_rest_resources": true,
  "clear_death_saves": true,
  "clear_turn_state": true,
  "clear_temp_hp": true,
  "end_concentration": true,
  "remove_concentration_aoes": true,
  "include_npc_allies": false,
  "include_enemies": false,
  "hit_dice_rule": "table_default"
}
```

Return shape:

```json
{
  "ok": true,
  "status": "LONG_REST_APPLIED",
  "message": "Long Rest applied to 4 players.",
  "rested": [
    {
      "cid": 1,
      "name": "Vicnor",
      "hp_before": 12,
      "hp_after": 34,
      "spell_slots_restored": true,
      "resource_pools_restored": ["example_resource"]
    }
  ],
  "snapshot": {}
}
```

Important: do not wire this to only `batch_long_rest_heal()`. That method is useful but incomplete.

Acceptance:

- DM can apply long rest to player characters.
- Spell slots reset.
- HP resets.
- Long-rest resources reset.
- One log entry and one broadcast.
- DM sees a summary of affected characters.

### Pass 8 — Player visible menu button

Goal: small usability improvement.

Tasks:

- Add visible `Menu` / `More` button to player LAN page.
- It opens the existing drop-up menu.
- Preserve existing shortcut/gesture.

Acceptance:

- New testers can find the menu without knowing hidden controls.

## Test plan by primitive

Do not start by writing one test per spell. Start with primitive tests.

Suggested tests:

```text
test_spell_result_no_silent_success
test_point_aoe_damage_applies_and_logs
test_point_aoe_no_targets_reports_no_targets
test_self_origin_line_uses_caster_origin
test_self_origin_cone_uses_caster_origin
test_persistent_concentration_aoe_registers_authoritative_effect
test_recasting_concentration_removes_old_bound_aoe
test_cancel_spell_cast_clears_pending_aoe
test_reset_turn_clears_pending_local_spell_state
test_manual_spell_slot_increment_reports_before_after
test_manual_spell_slot_increment_at_max_reports_noop
test_summon_spell_returns_spawned_cids_or_dm_required
test_dm_toolbox_long_rest_restores_hp_slots_resources
test_dm_toolbox_long_rest_broadcasts_once
```

After primitive tests pass, add thin smoke tests for reported spells:

```text
Fireball
Glyph of Warding
Thunderwave
Lightning Bolt
Slow
Banishment
Mirror Image
Dimension Door
Create Undead
Fount of Moonlight
Wall of Fire
Wall of Force
```

## Agent rules

Every agent working this area must follow these rules:

1. Read this document first.
2. Read the tester notes before changing spell behavior.
3. Prefer backend primitives over frontend hacks.
4. Do not add one-off spell branches unless documented and tested.
5. Do not parse YAML or rebuild spell indexes in the cast hot path.
6. Do not broadcast from low-level helpers.
7. Do not rebuild snapshots more than needed.
8. Every user-visible action needs explicit success/failure/pending feedback.
9. Keep frontend authority thin: UI selects intent, backend resolves truth.
10. Preserve live-play responsiveness as a first-class requirement.
11. Update this document after every pass.
12. Write a runtime report for any pass that changes cast behavior, snapshot behavior, or broadcast timing.

## Runtime report template

Create reports under:

```text
docs/runtime_reports/spell_engine_pass_YYYYMMDD_HHMM.md
```

Template:

```markdown
# Spell Engine Pass YYYY-MM-DD HH:MM

## Goal

## Files changed

## Behavior changed

## Primitive(s) touched

## Tester issue(s) addressed

## Performance notes

## Validation

## Known failures / deferred work

## Next recommended pass
```

## Definition of done for this initiative

The initiative is not done until all of these are true:

- Fireball-style point AoEs never silently do nothing.
- Thunderwave/Lightning Bolt-style self-origin directional AoEs use caster origin correctly.
- Persistent concentration AoEs are authoritative and clean up correctly.
- Reset/cancel cannot leave local spell ghosts that require reload.
- Manual Override spell slots visibly work or visibly explain no-op.
- Summon placement either creates authoritative combatants or creates a DM-visible pending request.
- DM Toolbox has a Long Rest Players action that restores HP, spell slots, and long-rest resources.
- Player LAN page has an obvious menu button.
- Core spell cast path uses compiled/normalized plans and generic primitives.
- Cast hot path performs one mutation commit and one broadcast/snapshot.
- Focused primitive tests and reported-spell smoke tests pass or have documented baseline exceptions.

## Open questions for project owner

These should be answered before or during implementation, not guessed by agents:

1. Rules baseline: 2014, 2024, or hybrid per spell data?
2. Long Rest Hit Dice rule: 2014 half total, 2024 all spent, or table custom?
3. Should player-controlled summons be allowed to spawn directly, or always require DM approval?
4. Should DM Long Rest include NPC allies by default?
5. Should DM Long Rest clear temp HP by default?
6. Should reset-turn ever remove already-authoritative persistent AoEs, or only pending local ghosts?
7. Which spells are intentionally manual-only for the table?

Until answered, implement safe defaults and surface explicit messages rather than pretending automation exists.
