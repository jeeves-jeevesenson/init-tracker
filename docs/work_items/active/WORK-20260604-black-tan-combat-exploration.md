# WORK-20260604-black-tan-combat-exploration

## ID and Title

WORK-20260604-black-tan-combat-exploration: AI/Browser-Driven Combat Bug Exploration (All Players vs All Black and Tans)

## Status

Active

## Active Gate

Gate 0 — Scenario inventory and scope definition

## Product Goal

Let an agent run a larger deterministic combat scenario through the app as DM/browser automation, with enough evidence collection to find and report bugs. This uses the foundational browser smoke harness established in WORK-20260603.

## First Bounded Scenario

"All selected combatants vs all Black and Tan enemies."

The scenario will seed a combat session containing the full roster of available player characters and all Black and Tan monster types. The automation will then cycle through combat rounds, exercising the UI and backend logic, while recording failures, console errors, and screenshots.

## Parent Plan

[PLAN-20260603-browser-automation-smoke-harness.md](../../planning/living_docs/PLAN-20260603-browser-automation-smoke-harness.md)

## Inventory Summary

### Black and Tan Monsters (9)
- `Monsters/black-and-tan-captain.yaml`
- `Monsters/black-and-tan-constable.yaml`
- `Monsters/black-and-tan-field-medic.yaml`
- `Monsters/black-and-tan-lieutenant.yaml`
- `Monsters/black-and-tan-major.yaml`
- `Monsters/black-and-tan-rifleman.yaml`
- `Monsters/black-and-tan-scorcher.yaml` (vda-scorcher)
- `Monsters/black-and-tan-shield-trooper.yaml`
- `Monsters/black-and-tan-suppression-gunner.yaml`

### Player Combatants (11)
- `players/dorian_vandergraff.yaml`
- `players/eldramar_thunderclopper.yaml`
- `players/fred_figglehorn.yaml`
- `players/John_Twilight.yaml`
- `players/johnny_morris.yaml`
- `players/malagrou.yaml`
- `players/oldahhman.yaml`
- `players/throat_goat.yaml`
- `players/vicnor.yaml`
- `players/стихия.yaml`
- `players/Character_Template.yaml` (Excluding README/todo)

## Gate Progress

### Gate 0: Scenario Inventory and Scope Definition (ACTIVE)
- [x] Define roster for all combatants vs all Black and Tans
- [x] Identify fixture strategy (extending smoke fixture API)
- [x] Define automation boundary (multi-round combat)
- [x] Define evidence output (logs/screenshots/traces)
- [ ] Identify and document risks

### Gate 1: Deterministic All-vs-Black-and-Tan Fixture
- [ ] Implement fixture seeding for full roster
- [ ] Verify map placement and initative order
- [ ] Validate snapshot consistency

### Gate 2: Harness Scenario Runner for Multi-Round Combat
- [ ] Implement multi-round cycle logic
- [ ] Handle action selection and resolution
- [ ] Verify turn advancement

### Gate 3: Bug Evidence / Report Output
- [ ] aggregate console/page/backend errors
- [ ] Generate summary report of "weird behavior"
- [ ] Capture trace evidence for identified issues

### Gate 4: Developer Smoke and Closure
- [ ] Review exploration findings with developer
- [ ] Close work item

## Non-Goals
- No generic whole-app explorer yet.
- No autonomous free-form AI decision loop yet.
- No LAN sync/player-role work yet unless explicitly reopened.
- No CI integration.
- No production/deploy work.
- No broad bug fixing during exploration setup.

## Validation Strategy
- `scripts/validation/browser-smoke-harness.py --scenario black-tan-all-vs-all`
- verify artifact generation under `logs/browser-smoke/`
- check `summary.json` for failure counts
