# PLAN-20260530-black-tan-vda-scorcher-automation — Black and Tan automation and VDA Scorcher lore enemy

## Status

Promoted to Active.

See work item: `docs/work_items/active/WORK-20260530-black-tan-vda-scorcher-automation.md`.

## Last updated

2026-05-30.

## Owner roles

- Developer: product/lore owner; decides final lore/stat balance and whether this becomes active work.
- Planning Tool: scope, evidence, gates, acceptance criteria, and Orchestrator handoff.
- Orchestrator: may promote this into one or more work items only after checking `docs/work_items/current_work.md`.
- Implementation agent: only acts after Orchestrator creates/promotes a work item.
- Developer smoke tester: confirms browser behavior in `/dmcontrol` and any DM cockpit entry points.

## Goal

Add a new Black and Tan / VDA lore enemy, the **Black and Tan VDA Scorcher**, and finish the existing Black and Tan package so the DM no longer sees manual-action reminders for ammunition, consumables, healing, temp HP, reactions, saves, area effects, or emergency faction protocols. Monster control should be trackable and executable through the DM console, especially `/dmcontrol`.

## Scope

1. Existing Black and Tan enemies:
   - `Black and Tan Constable`
   - `Black and Tan Rifleman`
   - `Black and Tan Shield Trooper`
   - `Black and Tan Suppression Gunner`
   - `Black and Tan Field Medic`
   - `Black and Tan Lieutenant`
   - `Black and Tan Captain`
   - `Black and Tan Major`

2. New lore enemy:
   - proposed slug: `black-and-tan-vda-scorcher`
   - proposed display name: `Black and Tan VDA Scorcher`
   - files to add:
     - `Monsters/black-and-tan-vda-scorcher.yaml`
     - `monster_capabilities/vandergraff/black-and-tan-vda-scorcher.yaml`
   - source: developer-provided Balleymena/VDA lore in this request.
   - proposed role: slow heavy flamethrower/area-denial unit with protective suit, rebreather hood, tank pack, and emergency fire-immunity implant protocol.

3. Automation surfaces:
   - backend monster capability execution in `dnd_initative_tracker.py`
   - capability summarization in `monster_capability_service.py`
   - `/dmcontrol` action cards, target selection, result application, resource display, and browser smoke
   - monster capability tests and quality-gate scripts

4. Faction protocol:
   - "Foreman breaks the glass" / "Scorched Earth Protocol" applies 15 minutes of fire immunity to eligible VDA / Black and Tan troopers.
   - In combat, 15 minutes should be represented as 150 rounds unless the app already has a better duration model.
   - This is table-specific homebrew, not an official D&D 2014 or 2024 rule.

## Non-goals

- Do not rebalance every firearm rule in the app.
- Do not replace player-side D&D 2014 behavior with D&D 2024 behavior.
- Do not implement ships, boarding, surfaces, or structure-object experimental systems as part of this work.
- Do not make a full VDA faction bestiary yet. This plan adds one Scorcher and makes existing Black and Tans automation-complete.
- Do not treat old reports as current truth unless revalidated against the current repo/context.
- Do not commit, push, deploy, or mark active work without developer/Orchestrator promotion.

## Source evidence

### Repo/workflow evidence inspected

- Uploaded repo zip: `/mnt/data/init-tracker-main (4).zip`, extracted for read-only inspection.
- `scripts/chatgpt_context_refresher.sh` and `scripts/agent_context_bundle.sh` exist, but both fail in the uploaded zip because it is not a Git checkout (`fatal: not a git repository`). Treat them as unavailable for current-state proof in this session.
- `docs/work_items/current_work.md` currently lists:
  - status: Active
  - current work item: `ITR-20260529-A0-08: Add current work ledger and long-term planning GPT workflow`
  - active gate: `A0: Agent Workflow`
  - allowed next action: complete documentation/templates for work-item and planning lifecycle.
- Existing Black and Tan stat files:
  - `Monsters/black-and-tan-captain.yaml`
  - `Monsters/black-and-tan-constable.yaml`
  - `Monsters/black-and-tan-field-medic.yaml`
  - `Monsters/black-and-tan-lieutenant.yaml`
  - `Monsters/black-and-tan-major.yaml`
  - `Monsters/black-and-tan-rifleman.yaml`
  - `Monsters/black-and-tan-shield-trooper.yaml`
  - `Monsters/black-and-tan-suppression-gunner.yaml`
- Existing Black and Tan capability overlays:
  - `monster_capabilities/vandergraff/black-and-tan-captain.yaml`
  - `monster_capabilities/vandergraff/black-and-tan-constable.yaml`
  - `monster_capabilities/vandergraff/black-and-tan-field-medic.yaml`
  - `monster_capabilities/vandergraff/black-and-tan-lieutenant.yaml`
  - `monster_capabilities/vandergraff/black-and-tan-major.yaml`
  - `monster_capabilities/vandergraff/black-and-tan-rifleman.yaml`
  - `monster_capabilities/vandergraff/black-and-tan-shield-trooper.yaml`
  - `monster_capabilities/vandergraff/black-and-tan-suppression-gunner.yaml`
- Existing Black and Tan tests:
  - `tests/test_black_and_tan_capabilities.py`
  - `tests/test_black_and_tan_controlled_burst.py`
  - `tests/test_black_and_tan_expansion.py`
  - `tests/test_black_and_tan_rough_arrest.py`
- Runtime smoke template:
  - `docs/runtime_reports/black_and_tan_dmconsole_smoke_TEMPLATE.md`
- Relevant backend/UI files:
  - `dnd_initative_tracker.py`
  - `monster_capability_service.py`
  - `assets/web/dmcontrol/index.html`
  - `scripts/audit/monster_capability_inventory.py`
  - `scripts/audit/monster_capability_quality_gate.py`

### Current automation facts from source inspection

- Monster capability API routes exist for listing, retrieving, executing, resolving target results, recharge, and effect changes.
- `_monster_capability_ensure_ammo_state` seeds current/max ammo from `mechanics.magazine_capacity`, and seeds reserve magazines for `5.56` only. `.45` reserves are explicitly deferred/unknown in current code.
- Firearm reload consumes reserve mags by ammo type and refills the selected firearm. Loose ammo support is noted as not yet in schema.
- `monster_capability_service.py` adds "Track ammunition manually." when a capability mentions ammo/magazine and the resource state does not already include ammo keys.
- Save/area actions can be represented with damage/effects, target rows, outcome rows, and `apply_damage` / `apply_effects`, but several Black and Tan save/area actions are still marked `executable: false`.
- Current tests intentionally assert some Black and Tan actions remain non-executable, especially field medic assists, command/reaction abilities, major save action, suppression gunner area abilities, and shield/command reactions. This plan intentionally supersedes those assertions after promotion.

### Manual/reminder gaps found in current Black and Tan overlays

- Shared reminders:
  - `vandergraff-drill`: reminder-only +1 to attack near officer.
  - `fire-discipline`: ammunition tracking reminder.
- Constable:
  - `rough-arrest`: manual/assisted Grappled condition after Baton.
- Rifleman:
  - primarily ammo reminder; otherwise closest to automated.
- Shield Trooper:
  - `interpose-shield`: manual damage reduction.
- Suppression Gunner:
  - `suppressive-fire`: manual area/save resolution; ammo cost 10.
  - `automatic-sweep`: manual area/save resolution; ammo cost 10.
- Field Medic:
  - `field-treatment`: manual healing.
  - `smoke-canister`: manual smoke/obscurity.
  - `stimulant-ampoule`: manual temp HP/movement.
  - `keep-officer-breathing`: manual HP adjustment reaction.
- Lieutenant:
  - `direct-fire`: manual ally reaction/attack.
  - `get-down`: manual save bonus.
- Captain:
  - `condemn-target`: manual damage tracking.
  - `coordinated-volley`: manual ally movement/brace.
  - `not-yet`: manual save bonus.
- Major:
  - `make-an-example`: marked `save_ability` but manual.
  - `command-fire`: manual ally reaction.
  - `countermand`: manual reroll.
  - `duck-behind-them`: manual AC bonus/damage transfer.

## Research agenda

### R-001 — Problem framing

Question: What does "no manual steps left" mean for this package?

Answer for this plan:
- No Black and Tan action, bonus action, reaction, consumable, ammo use, or faction protocol should require the DM to leave `/dmcontrol` and remember a text-only instruction.
- Passive traits may remain displayed only if they are truly informational, but combat-affecting traits such as Vandergraff Drill, Fire Discipline, Baton and Boot, and protocol fire immunity must be either automated or converted into explicit backend-assisted controls.

### R-002 — Source/repo truth

Questions:
- Which Black and Tan stat blocks and overlays exist?
- Which actions are still manual?
- What backend capability primitives already exist?

Status: initial pass complete from uploaded repo zip. Findings are listed above.

### R-003 — Runtime/log/smoke evidence

Questions:
- Do current `/dmcontrol` cards expose ammo state once initialized?
- Do save/area abilities work if `executable: true` and called through target resolution?
- Does resource state survive turn changes/session save-load as expected?
- Does the UI still label resource-backed actions as manual before the first execution seeds ammo?

Status: not complete. Needs an actual local run and browser smoke.

### R-004 — Capability schema design

Questions:
- Which generic mechanics are missing for full automation?
- Which can be represented by existing `save_ability`, `modifier`, `firearm_reload`, `riders`, and effect application?
- Which require new backend contracts?

Required schema additions or normalizations:
- `resources` / `consumables` at capability or monster level:
  - ammo type
  - magazine capacity
  - reserve mags
  - loose charges/fuel
  - uses per encounter/rest/day
  - reload/refuel action cost
- `heal` utility:
  - target mode
  - formula
  - one-use-per-target or one-use-per-encounter rules
- `temp_hp` utility:
  - target mode
  - amount/formula
  - optional movement rider
- `condition_apply` and `condition_remove`:
  - condition
  - duration
  - save/outcome trigger
- `reaction_grant` / `ally_command`:
  - choose ally
  - spend actor resource
  - spend ally reaction if required
  - launch linked attack/move/brace workflow
- `damage_reduction`:
  - trigger: ally hit
  - amount
  - range/adjacency requirement
  - target attack id/log reference where possible
- `save_bonus` / `ac_bonus` / `reroll` one-shot modifiers:
  - reaction timing
  - target ally
  - amount
  - consumed on save/attack resolution
- `area_hazard`:
  - smoke/heavily obscured
  - suppressive cube
  - fire cone/line/ground patch
  - duration
  - map marker if supported; otherwise persistent encounter note tied to effect id
- `faction_protocol`:
  - action button in DM toolbox or actor/faction section
  - applies effect to all eligible combatants
  - duration tracking and log line

### R-005 — Options and tradeoffs

Option A: data-only patch.
- Pros: fast, adds Scorcher and flips some actions to executable.
- Cons: still leaves true automation gaps, especially healing/temp HP/reactions/protocol, and risks hiding manual work under misleading buttons.
- Decision: reject as final approach; acceptable only for a research prototype.

Option B: generic monster automation layer first, then Black and Tans.
- Pros: fixes underlying model; reusable for future homebrew and imported monsters.
- Cons: larger gate.
- Decision: preferred.

Option C: bespoke Black and Tan-only hardcoded handlers.
- Pros: fast for this package.
- Cons: likely creates brittle special cases and future maintenance debt.
- Decision: reject except for small faction protocol routing if no generic faction-event primitive exists yet.

### R-006 — Proposed gates and acceptance criteria

See Implementation gates and Validation requirements.

## Research log

### 2026-05-30 — R-001/R-002 initial repo pass

Findings:
- The uploaded zip is not a Git checkout; context refresher and bundle scripts are unavailable as current-state proof.
- `docs/work_items/current_work.md` currently blocks direct promotion because A0 workflow work is active.
- Eight Black and Tan stat blocks and eight matching `monster_capabilities/vandergraff` overlays already exist.
- There is already meaningful Black and Tan automation: executable firearm/melee attacks, composite multiattack, controlled burst modifier, reload action, ammo current/max state, jam risk, sequence state, and assisted multi-target target resolution.
- The remaining problem is not "no data exists"; it is incomplete automation contracts for resources, consumables, allies, reactions, area hazards, and faction-wide effects.
- Existing tests currently assert some manual behavior. Those tests should be updated only after the work is promoted.

Decision:
- Plan should be a new living doc and not an active implementation task until Orchestrator promotes it.

Open questions:
- Should the new Scorcher be CR 6, CR 7, or CR 8?
- Should baseline suit protection grant fire resistance before the glass breaks, or only fire immunity after the protocol?
- Should the VDA Scorcher be tagged as `vandergraff_black_and_tans`, `vda`, or both?
- Should existing capability overlay license remain `CC-BY-4.0` or use a table-local/homebrew tag for developer-owned lore?

## Decisions

1. Target behavior is table-specific homebrew on top of the existing app's D&D-like combat model. No official 2014/2024 rules migration is part of this plan.
2. Add one new lore enemy now: `Black and Tan VDA Scorcher`.
3. Treat "Foreman breaks the glass" as a faction protocol/event, not an individual Scorcher-only action.
4. Prefer generic automation primitives over hardcoded one-off Black and Tan handlers.
5. The acceptance gate is user-visible: Black and Tan DM-control cards must no longer show "Manual" or "Track ammunition manually" for capabilities that the DM is expected to execute.
6. Resource tracking must initialize when combatants are added or capabilities are summarized, not only after the first execution; otherwise the UI can still show manual ammo before an action is clicked.
7. Existing tests that assert manual status are expected to be changed by the future work item.

## Open questions

1. Final enemy name:
   - recommended: `Black and Tan VDA Scorcher`
   - alternatives: `VDA Scorcher Unit`, `Vandergraff Scorcher`, `Black and Tan Shore Scorcher`
2. Final CR/balance target:
   - recommended starting point: CR 7, between Suppression Gunner CR 6 and Lieutenant CR 7, but slower and more area-denial focused.
3. Baseline defenses:
   - recommended: fire resistance from heavy protective gear, upgraded to fire immunity for 15 minutes after Scorched Earth Protocol.
   - stricter lore reading: no special fire defense until protocol triggers.
4. Protocol scope:
   - all VDA troopers only?
   - all Black and Tans?
   - all enemies with `faction: vandergraff_black_and_tans` and/or `faction_tags: [vda]`?
5. Does "rubber hoods over their heads that connect to some sort of bag" mean protection against gas/poison as a mechanical trait?
6. Does Balleymena shore/offshore drilling require swim speed, difficult-terrain immunity in shallow water/mud, or just descriptive equipment?
7. Should Scorcher fuel tanks be lootable, dangerous, or intentionally non-lootable?

## Proposed VDA Scorcher design target

This is a design target, not implementation.

```yaml
name: Black and Tan VDA Scorcher
slug: black-and-tan-vda-scorcher
role: heavy area-denial / terror patrol
recommended_cr: "7"
recommended_ac: "18"
recommended_hp: 126
recommended_speed:
  Normal: 20 ft.
tags:
  - vandergraff_black_and_tans
  - vda
  - balleymena
  - scorched_earth_protocol
traits:
  - Heavy Protective Rig: disadvantage on Dexterity (Stealth); cannot Dash unless the DM overrides.
  - Sealed Hood and Tank Bag: advantage/resistance against inhaled gas/poison if the table wants that lore reflected.
  - Fireproofed Suit: recommended baseline fire resistance; protocol upgrades to fire immunity.
  - Protocol Implant: eligible for Scorched Earth Protocol.
actions:
  - Flamethrower Burst: cone, Dex save, fire damage, fuel cost.
  - Sweeping Burn: line or wider cone, higher fuel cost, area damage.
  - Ignite Ground: creates a temporary burning area hazard.
  - Heavy Glove / Tank Bash: melee fallback.
bonus_actions:
  - Brace Hose: next flamethrower action gets better DC/range or avoids self-risk.
  - Refuel / Swap Tank: consumes reserve tank/fuel canister.
reactions:
  - Emergency Vent: smoke/obscuring burst or one-shot resistance/immunity if allowed.
resources:
  - loaded_fuel: tracked like ammo.
  - reserve_tanks: tracked like magazines.
  - emergency_implant: set by faction protocol, not individually clicked.
```

Automation-specific Scorcher requirements:
- Flamethrower fuel is not manual text. It appears in the action card and decrements when fire actions resolve.
- Refuel consumes reserve tanks and updates `/dmcontrol`.
- Fire cone/line uses the same multi-target resolution tray as existing area actions, with explicit fail/success/no-effect rows.
- Ignite Ground creates an area hazard marker or persistent encounter effect visible to the DM.
- Scorched Earth Protocol applies and displays duration on all eligible tokens.
- Fire immunity is included in damage resolution if the app has resistance/immunity hooks for combatants; if not, a narrowly scoped resistance/immunity condition/effect must be added before claiming completion.

## Risks

- The active work ledger currently points to A0 workflow work, so direct implementation could violate process.
- Some current Black and Tan tests intentionally assert non-executable/manual status; changing behavior without updating tests will fail.
- Generic reaction/ally-command automation can become large if it tries to solve every D&D reaction edge case at once.
- Area hazard support may touch map state and performance-sensitive `/dmcontrol` updates.
- Ammo/resource state may not currently initialize early enough for UI summaries, causing false manual warnings before first use.
- The app may not have a complete damage-type resistance/immunity application path for monsters; protocol fire immunity must be verified in actual damage resolution.
- Scorcher flamethrower balance can swing encounters hard because repeat AoE fire attacks punish clustered players.

## Implementation gates

### Gate 0 — Promotion and context refresh

Entry criteria:
- Developer or Orchestrator explicitly promotes this plan after checking `docs/work_items/current_work.md`.
- If A0 workflow is still active, Orchestrator must ask whether to pause/supersede/branch rather than silently starting this.

Tasks:
- Run `scripts/chatgpt_context_refresher.sh` or `scripts/agent_context_bundle.sh` from a real Git checkout.
- Re-read `docs/work_items/current_work.md`.
- Confirm no newer Black and Tan work item supersedes this plan.

Exit criteria:
- Current state is documented in the promoted work item.

### Gate 1 — No-manual audit baseline

Tasks:
- Add/extend an audit that reports all Black and Tan capabilities with:
  - `warning` containing "Manual"
  - `manual_instructions`
  - executable action/bonus_action/reaction marked `false`
  - ammo or consumable actions without initialized resource schema
- Create a failing expected report before fixes.

Exit criteria:
- The audit gives a deterministic list of remaining manual gaps.

### Gate 2 — Resource and consumable initialization

Tasks:
- Add explicit ammo/reserve metadata to every Black and Tan firearm and consumable action.
- Seed `.45` reserve magazines, 5.56 reserve magazines, smoke canisters, stimulant ampoules, medic kits/uses, suppression ammo, Scorcher fuel, and reserve tanks when combatants are added or summarized.
- Ensure UI summaries do not show "Track ammunition manually" once resource schema is present.
- Add save/load coverage if monster resource state is persisted.

Exit criteria:
- Ammo and consumables are visible and update in `/dmcontrol` before the first attack is made.

### Gate 3 — Generic execution primitives

Tasks:
- Add/normalize backend mechanics for:
  - healing
  - temp HP
  - condition application
  - damage reduction
  - AC/save/reroll one-shot modifiers
  - ally reaction/commanded attack or movement
  - area hazard/smoke
  - faction protocol effect application
- Keep primitives generic enough for other monsters.

Exit criteria:
- Each primitive has direct unit tests and one Black and Tan consumer test.

### Gate 4 — Convert existing Black and Tans

Tasks:
- Convert all current manual Black and Tan capabilities to executable or automated passive mechanics.
- Update tests that currently assert non-executable status.
- Add tests that assert no executable Black and Tan action/bonus action/reaction remains manual.

Exit criteria:
- Existing eight Black and Tans can run their full listed actions from `/dmcontrol`.

### Gate 5 — Add VDA Scorcher and Scorched Earth Protocol

Tasks:
- Add Scorcher monster stat YAML.
- Add Scorcher capability overlay.
- Add faction/protocol metadata to eligible troops.
- Add the protocol trigger control.
- Add tests for Scorcher resource use, fire AoE resolution, refuel, and protocol fire immunity duration.

Exit criteria:
- Scorcher appears in monster library, can be added to combat, and can complete a turn without manual instructions.

### Gate 6 — Quality gate, regression tests, browser smoke

Tasks:
- Run targeted tests:
  - `tests/test_black_and_tan_capabilities.py`
  - `tests/test_black_and_tan_controlled_burst.py`
  - `tests/test_black_and_tan_expansion.py`
  - `tests/test_black_and_tan_rough_arrest.py`
  - new Scorcher tests
  - monster capability quality gate
- Run browser smoke using `docs/runtime_reports/black_and_tan_dmconsole_smoke_TEMPLATE.md`.

Exit criteria:
- No Black and Tan card needed for normal combat shows a manual badge/instruction.
- Browser smoke is recorded.

## Validation requirements

Automated validation:
- Unit/contract tests for resource initialization, ammo spend, reload/refuel, healing, temp HP, conditions, area save resolution, reaction grants, damage reduction, one-shot save/AC/reroll modifiers, and protocol duration.
- A package-level test that iterates all `monster_capabilities/vandergraff/black-and-tan-*.yaml` files and fails if an action/bonus_action/reaction expected to be executable still has manual warnings.
- A Scorcher-specific test that verifies:
  - overlay matches slug
  - fuel initializes
  - Flamethrower Burst spends fuel
  - Refuel consumes reserve tank
  - protocol applies fire immunity to Scorcher
  - protocol expires after the configured duration.
- Capability quality gate must pass after reports are regenerated.

Manual/developer validation:
- Developer confirms lore naming and whether baseline suit protection is resistance or only protocol immunity.
- Developer confirms Scorcher CR/feel after at least one encounter smoke.

## Browser smoke requirements

Use `/dmcontrol` unless the promoted work item chooses a newer monster-control surface.

Minimum smoke:
1. Start a combat with one PC target and one of each Black and Tan type.
2. Open `/dmcontrol`.
3. Confirm every Black and Tan card shows resource counters where applicable.
4. For each Black and Tan:
   - run Multiattack where present
   - run firearm attack
   - run reload
   - run one special action
   - run one reaction/bonus action if present
   - confirm HP/conditions/resources update without leaving `/dmcontrol`
5. Add the VDA Scorcher.
6. Use Flamethrower Burst against multiple targets.
7. Use Ignite Ground or equivalent area hazard.
8. Use Refuel.
9. Trigger Scorched Earth Protocol.
10. Apply fire damage to an eligible troop and confirm immunity blocks it or is visibly applied through the app's damage flow.
11. Confirm the battle log describes fuel, ammo, healing, conditions, reactions, and protocol effects.
12. Confirm no normal Black and Tan action card still says "Manual Assist", "Track ammunition manually", or equivalent.
13. Fill in `docs/runtime_reports/black_and_tan_dmconsole_smoke_TEMPLATE.md` or create a dated report from it.

## Completion criteria

This plan is complete only when:

- A promoted work item implements the automation gates or explicitly supersedes this plan.
- Existing eight Black and Tans and the new VDA Scorcher can be controlled in `/dmcontrol` without manual combat steps for their listed capabilities.
- Ammo, fuel, magazines, reserve tanks, smoke canisters, stimulant ampoules, healing uses, temp HP, damage reductions, ally commands, save/AC/reroll reactions, and protocol fire immunity are tracked in app state.
- Tests pass and browser smoke is recorded.
- The developer approves the Scorcher lore/stat feel.

## Reopen conditions

Reopen this plan only if:
1. A Black and Tan or VDA Scorcher action regresses to manual-only.
2. Ammo/fuel/consumable tracking desyncs between backend and `/dmcontrol`.
3. Scorched Earth Protocol fails to apply, display, block fire damage, or expire correctly.
4. The developer adds more VDA lore requiring additional enemy types.
5. A future monster-control rewrite changes the capability contract.

## Orchestrator handoff

I created/updated a planning document at: `docs/planning/living_docs/PLAN-20260530-black-tan-vda-scorcher-automation.md`.

Please read it, check `docs/work_items/current_work.md`, and decide whether to promote any gate/work item, request more research, create a Gemini task, use Codex, or ask for developer smoke.

Do not implement directly from this plan while `ITR-20260529-A0-08` remains the active work item unless the developer explicitly authorizes starting this as the next active work. If promoted, begin with Gate 0 and then Gate 1. Do not jump straight to adding the Scorcher YAML until the automation contract for existing Black and Tans is understood, because the developer's main requirement is "no manual steps left."

## Paste-ready proposed work item title

`ITR-20260530-MONSTER-01: Automate Black and Tan monster control and add VDA Scorcher`

## Refusal/end-state rule

If this plan is marked Completed, Superseded, Archived, or reaches the completion criteria above, Orchestrator should refuse to continue from it unless the developer explicitly reopens it with new evidence or a new planning question.
