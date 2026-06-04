# WORK-20260603-browser-smoke-harness-scorcher-ignite-ground

## ID and Title

WORK-20260603-browser-smoke-harness-scorcher-ignite-ground: Browser Automation Smoke Harness Foundation (Pilot: Scorcher Ignite Ground)

## Status

Completed

## Active Gate

None (All implementation gates closed)

## Note (2026-06-04)

Gate 0 (Architecture/Planning), Gate 1 (Instrumentation), Gate 2 (Fixtures), Gate 3 (Harness shell and artifacts), and Gate 4 (Pilot scenario implementation) are closed. The browser smoke harness foundation is established with the first pilot scenario.

## Product Goal

Establish a foundational whole-app local browser/AI smoke harness capable of exercising the entire application as both DM and Player roles over time. This harness allows agents to run high-fatigue UI smoke flows locally and provide deterministic pass/fail evidence to the developer.

## Pilot Scenario

The first deterministic pilot scenario is the **Black and Tan VDA Scorcher Ignite Ground / Apply Result** on `/dmcontrol`. This scenario serves to validate the harness foundation and instrumentation strategy.

## Parent Plan

[PLAN-20260603-browser-automation-smoke-harness.md](../../planning/living_docs/PLAN-20260603-browser-automation-smoke-harness.md)

## Future-Facing Harness Requirements

The harness architecture must support:
- **DM Browser Role**: Automation for the DM control surface and map.
- **Player Browser Role(s)**: Multi-role support for one or more player views (LAN).
- **Role-Based Artifacts**: Separate logs/screenshots per role.
- **Scenario Registry**: Plug-and-play scenarios.

## Gate Progress

### Gate 0: Architecture and Planning
- [x] Define harness CLI shape
- [x] Define artifact directory layout
- [x] Define role model (DM/Player)

### Gate 1: Instrumentation
- [x] Add `data-smoke` attributes to DM Control surface
- [x] Add instrumentation hooks for modal state
- [x] Add instrumentation hooks for result application

### Gate 2: Fixtures
- [x] Implement `/api/dev/smoke-fixtures/dmcontrol-scorcher-ignite-ground`
- [x] Verify fixture seeds correct combat and map state

### Gate 3: Harness Shell and Artifacts
- [x] Implement `scripts/validation/browser-smoke-harness.py`
- [x] Implement CLI entrypoint (`--list-scenarios`, `--scenario`, `--base-url`)
- [x] Implement artifact collector (timestamped directories, `summary.json`)
- [x] Implement architectural support for DM/Player roles
- [x] Add tests for harness shell (`tests/test_browser_smoke_harness.py`)

### Gate 4: Pilot Scenario Implementation
- [x] Implement Scorcher Ignite Ground scenario logic
- [x] Automate DM login and map interaction
- [x] Verify Ignite Ground result application
- [x] Capture pass/fail evidence artifacts

## Validation

- `python3 -m unittest tests/test_browser_smoke_harness.py` (Passes)
- `python3 -m unittest tests/test_scorcher_smoke_fixture.py` (Passes)
- `scripts/validation/browser-smoke-harness.py --scenario scorcher-ignite-ground --start-server` (Passes locally)
- **Latest Artifact (Pass):** `logs/browser-smoke/scorcher-ignite-ground/20260604_142105/`

## Commitment

```bash
git add scripts/validation/browser-smoke-harness.py tests/test_browser_smoke_harness.py docs/work_items/active/WORK-20260603-browser-smoke-harness-scorcher-ignite-ground.md docs/work_items/current_work.md
git commit -m "Implement Scorcher browser smoke scenario"
```
