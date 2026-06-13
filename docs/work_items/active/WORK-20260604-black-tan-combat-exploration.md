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

### Gate 0: Scenario Inventory and Scope Definition (COMPLETE)
- [x] Define roster for all combatants vs all Black and Tans
- [x] Identify fixture strategy (extending smoke fixture API)
- [x] Define automation boundary (multi-round combat)
- [x] Define evidence output (logs/screenshots/traces)
- [x] Identify and document risks

### Gate 1: Deterministic All-vs-Black-and-Tan Fixture (COMPLETE)
- [x] Implement fixture seeding for full roster
- [x] Verify map placement and initative order
- [x] Validate snapshot consistency

#### Gate 1 Results
- **Route Path:** `POST /api/dev/smoke-fixtures/black-tan-combat-exploration`
- **Final Roster:** 10 Players, 9 Black and Tan Monsters, 2 automatic Summons (Total 21 combatants).
- **Player Names:** Dorian, Eldramar, Fred, John Twilight, Johnny Morris, Malagrou, Old Man, Throat Goat, Vicnor, стихия.
- **Monster Slugs:** black-and-tan-captain, black-and-tan-constable, black-and-tan-field-medic, black-and-tan-lieutenant, black-and-tan-major, black-and-tan-rifleman, black-and-tan-vda-scorcher, black-and-tan-shield-trooper, black-and-tan-suppression-gunner.
- **Template Character:** Excluded (file not found in repo, confirmed 10 active players).
- **Automatic Summons:** Eldramar (Owl) and стихия (Raven) are automatically added by the engine.
- **Map Strategy:** 30x30 map. Players at cols 2-3, Monsters at cols 26-27. Deterministic non-overlapping rows.
- **Tests Passed:** `tests/test_black_tan_combat_fixture.py` (validated rejection when debugging off, success when on, counts, and placements).

### Gate 2: Harness Scenario Runner for Multi-Round Combat (COMPLETE)
- [x] Implement multi-round cycle logic
- [x] Handle action selection and resolution
- [x] Verify turn advancement

#### Gate 2 Results
- **Scenario ID:** `black-tan-combat-exploration`
- **Driving Policy:** Deterministic first-executable action selection. Handles AoE (clicks 15,15) and Single Target (clicks first candidate).
- **Control Flags:** Added `--max-rounds`, `--max-turns`, `--slow-mo-ms` to `browser-smoke-harness.py`.
- **Evidence Collection:** Per-turn `event_log.json`, failure/success screenshots, and extended `summary.json` metadata.
- **Helper Additions:** Enhanced `window.__dmcontrolSmoke` with `activeActorName`, `roundOrTurn`, `availableActions`, `combatantSummary`, `modalSummary`, and `targetPreviewMode`.

### Gate 3: Bug Evidence / Report Output (ACTIVE)
- [x] aggregate console/page/backend errors
- [x] Generate summary report of "weird behavior"
- [x] Capture trace evidence for identified issues (Screenshots captured; trace log skipped due to crash)
- [x] Fix BUG-20260604-SMOKE-01 (AoE state crash)

#### Gate 3 Evidence
- **Command Run:** `env INIT_TRACKER_DEBUGGING=1 .venv/bin/python scripts/validation/browser-smoke-harness.py --scenario black-tan-combat-exploration --max-rounds 1 --max-turns 40 --artifact-root logs/browser-smoke --base-url http://127.0.0.1:8787`
- **Artifact Path (Success 1):** `logs/browser-smoke/black-tan-combat-exploration/20260604_162348`
- **Artifact Path (Success 2):** `logs/browser-smoke/black-tan-combat-exploration/20260604_162411`
- **Status:** PASS
- **Rounds/Turns Completed:** Full scenario (40 turns requested, completed all active combatants).
- **Previous Fatal Error:** `Exploration loop failed: 'active'` (Fixed in commit a16a914)
- **Remaining Issues:**
  - `BUG-20260604-SMOKE-02`: Harness lacks support for `composite` action types (Multiattack). (Next blocker)

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
