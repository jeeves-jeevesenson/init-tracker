# WORK-20260603-browser-smoke-harness-scorcher-ignite-ground

## ID and Title

WORK-20260603-browser-smoke-harness-scorcher-ignite-ground: Browser Automation Smoke Harness Foundation (Pilot: Scorcher Ignite Ground)

## Status

Active

## Active Gate

Gate 1 — Instrumentation

## Note (2026-06-04)

Gate 0 (Architecture/Planning) is closed. Gate 1 (Instrumentation) is ready for implementation.

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
- **Deterministic Scenario Setup/Reset**: Atomic seeding of specific combat/map states via fixtures.
- **Scripted Combat Actions**: Explicit sequences of capability selection, targeting, and resolution.
- **Observable Pass/Fail Checks**: Assertions against both DOM state and logical application state (via helpers).
- **Debug Trace and Smoke Log Collection**: Aggregation of server logs, browser console errors, network failures, and debug-trace JSONL.
- **Bug Evidence Output**: Clear artifacts (screenshots, traces, summaries) for developer and future agent diagnosis.

## Scope (Implementation Slice 1: Pilot)

In scope for the pilot:

- Gate 1: `/dmcontrol` stable test IDs.
- Debug-gated smoke helper foundation (designed for extensibility).
- Deterministic fixture strategy (seeding Scorcher).
- One pilot scenario: Scorcher Ignite Ground.

## Non-Goals

- No full autonomous AI explorer in the first implementation gate.
- No CI integration yet.
- No production dependency or deployment changes.
- No LAN sync testing in the first pilot gate.
- No broad app suite before the pilot harness is verified.
- No persistent browser automation expansion beyond the first scenario until stable.

## Gates

### Gate 0 — Current-state refresh and scope confirmation

**Status: Completed**

Purpose:
- Confirm repo state and automation conventions.
- **Design the harness foundation** so it is extensible to other scenarios and roles (DM/Player) and not hard-coded for Scorcher only.
- Define the minimal harness architecture, scenario format, and role model.

Findings:
- **Repo state confirmed**: Tree is clean. Recent Scorcher automation work (WORK-20260530-black-tan-vda-scorcher-automation) is completed and committed.
- **Automation convention confirmed**: Existing `scripts/validation/lan-smoke-playwright.py` uses `playwright.sync_api`. The harness will follow this direct-library Python style.
- **Dependencies confirmed**: `playwright` is present in `requirements.txt`.
- **Minimal implementation target**:
  - Harness: `scripts/validation/browser-smoke-harness.py`.
  - Instrumentation: Add `data-testid` to `assets/web/dmcontrol/index.html` and expose `window.__dmcontrolSmoke`.
  - Fixture: Add a debug-only POST route `/api/dev/smoke-fixtures/dmcontrol-scorcher-ignite-ground` in `dnd_initative_tracker.py`.

### Proposed Architecture

#### 1. Harness Runner (`scripts/validation/browser-smoke-harness.py`)
- **Library**: `playwright.sync_api`.
- **Server Lifecycle**: Starts `serve_headless.py` as a subprocess; waits for "Headless tracker started." and HTTP 200.
- **Role Management**: Manages multiple `BrowserContext` instances. Maps roles (e.g., `dm`, `player1`) to specific pages and URLs.
- **Scenario Discovery**: Loads scenario classes from `scripts/validation/scenarios/`.

#### 2. Scenario Model (`scripts/validation/scenarios/`)
- **Definition**: Each scenario is a Python class defining its required roles, setup steps (fixtures), and action sequence.
- **State Seeding**: Scenarios call backend fixture routes to ensure deterministic starting state.
- **Assertions**: Verify UI state (DOM), logical state (`window.__dmcontrolSmoke`), and backend response.

#### 3. Role Model
- **`dm`**: Connects to `http://HOST:PORT/dmcontrol`. Uses DM authority.
- **`player`**: Connects to `http://HOST:PORT/` (LAN surface). Uses player-limited view.
- **Multi-Role Support**: Harness can synchronize actions between a DM and multiple players to test LAN synchronization.

#### 4. Fixture Strategy
- **Backend Routes**: `/api/dev/smoke-fixtures/{scenario_id}`.
- **Gating**: Only active when `INIT_TRACKER_DEBUGGING=1`.
- **Payload**: Fixtures should return actor CIDs and initial snapshots to avoid fragile text-based lookups in the harness.

#### 5. Observability and Instrumentation
- **DOM**: Stable `data-testid` attributes on interactive elements (Action cards, modals, apply buttons).
- **Canvas/Logic**: `window.__dmcontrolSmoke` helper on the DM page to expose logical map state (hazards, actor grid positions) without brittle pixel inspection.

#### 6. Artifact Layout
Unique timestamped directories under `logs/browser-smoke/{scenario_id}/`:
- `summary.json` / `summary.md` (Pass/Fail and assertion details).
- `server.stdout.log` / `server.stderr.log`.
- `browser-console.jsonl` / `page-errors.jsonl`.
- `screenshots/` (Key flow steps and failure states).
- `trace.zip` (Playwright trace for deep debugging).
- `debug-trace.jsonl` (Backend activity trace).

#### 7. Manual vs. Automated Boundaries
- **Automated**: Deterministic happy paths, regression smoke, LAN state synchronization.
- **Manual**: UI polish/aesthetics, complex exploratory testing, nuanced timing/interruption scenarios.

### Implementation Gate Recommendation: Gate 1 — Instrumentation

Tasks:
- [ ] Add stable `data-testid` attributes to `/dmcontrol`.
- [ ] Add `window.__dmcontrolSmoke` helper to `/dmcontrol`.
- [ ] Implement `/api/dev/smoke-fixtures/dmcontrol-scorcher-ignite-ground` in `dnd_initative_tracker.py`.
- [ ] Run asset syntax checks.

Validation:
- `python3 -m pytest tests/test_dm_console_asset_syntax.py`
- Manual verification of fixture route (returns 200/JSON in debug mode).

Tasks:
- [x] Run context refresh (`scripts/chatgpt_context_refresher.sh`).
- [x] Confirm repo state (clean tree, recent Scorcher work committed).
- [x] Confirm current automation conventions (Python Playwright library style).
- [x] Define harness foundation architecture (Scenario, Role, Actor models).
- [x] Prepare Gate 1 task list.

### Gate 1 — Instrumentation

**Status: Completed (Frontend)**

Tasks:
- [x] Add stable `data-testid` attributes to `/dmcontrol`.
- [x] Add debug-gated `window.__dmcontrolSmoke` helper.
- [x] Run asset syntax checks.

Notes (2026-06-04):
- Frontend data-testid hooks added for action cards, map, resolution modal, and apply button.
- `window.__dmcontrolSmoke` added providing logical state (active actor, selected action, modal status, hazard count).
- Backend fixture route still pending (Gate 2).
- Harness runner/scenario files still pending (Gate 3/4).

### Gate 2 — Deterministic Scorcher fixture

**Status: Completed**

Tasks:
- [x] Implement debug-only route `POST /api/dev/smoke-fixtures/dmcontrol-scorcher-ignite-ground`.
- [x] Route seeds a clean 20x20 grid with Scorcher at (5,5) and target at (7,5).
- [x] Add backend tests for fixture route (`tests/test_scorcher_smoke_fixture.py`).

Notes (2026-06-04):
- Route added to `LanController` in `dnd_initative_tracker.py`.
- Gated by `INIT_TRACKER_DEBUGGING` via `runtime_config.debugging_env_enabled()`.
- Successfully verified with `tests/test_scorcher_smoke_fixture.py`.
- Fixture returns `actor_cid`, `target_cid`, and `expected_action` for harness consumption.

### Gate 3 — Harness shell and artifacts

**Status: Pending**

Tasks:
- [ ] Add Playwright smoke script shell.
- [ ] Implement artifact collector (logs, screenshots, traces).

### Gate 4 — First Scorcher smoke scenario

**Status: Pending**

Tasks:
- [ ] Implement `scorcher-ignite-ground` scenario.
- [ ] Verify pass/fail and artifact generation.

## Validation

```bash
scripts/chatgpt_context_refresher.sh
cat docs/work_items/current_work.md
git status --short
git log --oneline -5
```
