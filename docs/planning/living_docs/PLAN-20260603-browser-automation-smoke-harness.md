# PLAN-20260603-browser-automation-smoke-harness

## ID and Title

PLAN-20260603-browser-automation-smoke-harness: Browser Automation Smoke Harness for `/dmcontrol` and LAN Regression Flows

## Status

Promoted

This plan was promoted to [WORK-20260603-browser-smoke-harness-scorcher-ignite-ground](../../work_items/active/WORK-20260603-browser-smoke-harness-scorcher-ignite-ground.md) on 2026-06-04.

## Last Updated

2026-06-03

## Owner Roles

- Developer: product owner, final approver, and decision maker for when to promote this plan.
- Planning Tool: evidence review, scope control, architecture plan, work-item proposal, and living-document governance.
- Orchestrator/Gemini: implementation executor only if the developer promotes the proposed work item.
- Codex: not assigned unless the developer explicitly requests Codex.
- Browser smoke agent: bounded local validation runner that reports artifacts and pass/fail without asking the developer to manually inspect source.

## Goal

Create a small, deterministic browser automation smoke harness so agents can run the current high-fatigue UI smoke flows locally before asking the developer for final approval.

The first target is the current Scorcher gate:

**Black and Tan VDA Scorcher Ignite Ground / Apply Result browser smoke** on `/dmcontrol`.

*Note (2026-06-04): While Scorcher is the first pilot, the foundational goal is a whole-app local browser/AI smoke harness capable of DM + player role testing. The harness structure should be designed for extensibility and not hard-coded for the pilot scenario.*

## Scope

In scope:

- Local-only Playwright or equivalent browser automation.
- Starting the app with the existing headless smoke command.
- Connecting to `http://127.0.0.1:8787/dmcontrol` while the server binds to `0.0.0.0`.
- Adding stable selectors and smoke-only helper state where canvas assertions need logical state.
- Deterministically seeding a Scorcher encounter/map state.
- Running one bounded Scorcher Ignite Ground scenario.
- Capturing screenshots, Playwright traces, browser console/page errors, failed requests, backend stdout/stderr, debug trace JSONL, and a machine-readable result summary.
- Reporting a clear pass/fail result for agents and Orchestrator.

## Non-Goals

- Do not replace developer product approval.
- Do not depend on production services.
- Do not SSH, deploy, push, restart production, or change topology.
- Do not create broad exploratory UI tests.
- Do not mix this planning work with Scorcher implementation fixes.
- Do not create a full E2E suite before the first small smoke target passes.
- Do not require the developer to manually code-review browser/source changes.
- Do not silently mark Scorcher work complete because a smoke script exists.
- Do not activate the proposed work item unless the developer explicitly promotes it.

## Source Evidence

Current session and repo evidence inspected:

- Uploaded repo snapshot: `init-tracker-wip-black-tan-scorcher-unsmoked-20260603.zip`.
- Evergreen workflow/repo-shape knowledge: `planning_tool_knowledge_repo_shape.md`.
- `docs/work_items/current_work.md` marks current work as:
  - Status: Active.
  - Work item: `WORK-20260530-black-tan-vda-scorcher-automation`.
  - Active gate: `Gate 5I-R: Final Scorcher smoke audit`.
  - Allowed next action: final browser smoke and completion decision.
- `scripts/chatgpt_context_refresher.sh` and `scripts/agent_context_bundle.sh` exist, but in the uploaded zip both fail because the archive is not a Git checkout (`fatal: not a git repository`). This limits current-state evidence to inspected files and command output, not branch/commit/dirty-state claims.
- `requirements.txt` already includes `playwright`.
- `scripts/validation/lan-smoke-playwright.py` is an existing Python Playwright smoke precedent using `playwright.sync_api`.
- `serve_headless.py` supports the requested headless local server command and writes an opt-in debug trace when `INIT_TRACKER_DEBUGGING=1`.
- `runtime_config.py` shows debug traces default to a `logs/debug-trace-*.jsonl` path when `configure_debug_trace()` is enabled without an explicit `log_dir`.
- `assets/web/dmcontrol/index.html` currently has only ordinary `id=` selectors and no `data-testid` occurrences in `assets/`.
- `/dmcontrol` currently includes:
  - `mapCanvas`, `activeActorPanel`, `activeActionsPanel`, `resolutionModal`, `modalBody`, `modalFooter`, and `modalApplyBtn`.
  - AoE state helpers: `enterAoePlacementMode`, `confirmAoePlacement`, `unlockAoePlacement`, `renderAoeResolutionModal`, `applyAoeResolutionResultsFromModal`, `renderAoePreview`, and `aoeContainsGridPoint`.
  - Canvas pointer handling that confirms AoE placement on map click when `aoePlacementMode` is active.
- Backend route evidence:
  - `/api/dm/monster-capabilities/{cid}/resolve-targets` calls `_dm_monster_capability_resolve_targets`.
  - `_dm_monster_capability_resolve_targets` supports `area_hazard`, returns `hazard_placed_count`, and includes a snapshot.
  - Ignite Ground persistent placement currently uses `_resolve_aoe_cells()` and `_upsert_map_hazard(... kind="fire" ...)`.
- Session route evidence:
  - `/api/dm/sessions/new`, `/api/dm/sessions`, `/api/dm/sessions/save`, `/api/dm/sessions/load`, `/api/dm/sessions/quick-save`, and `/api/dm/sessions/quick-load` exist.
  - There is no confirmed general-purpose smoke fixture route in the inspected repo.
- Existing browser-smoke pattern evidence:
  - `scripts/validation/lan-smoke-playwright.py` uses direct Python Playwright, custom route mocks, page error collection, and deterministic test helpers exposed from the LAN page.
- External Playwright evidence, accessed 2026-06-03:
  - Playwright Python locators documentation recommends stable test IDs and `page.get_by_test_id()`.
  - Playwright trace documentation supports saving traces with screenshots/snapshots for post-run debugging.
  - Playwright video documentation supports recording video to a directory and saving it after browser context close.
  - Playwright events documentation supports subscribing to page/network/browser events.
  - Playwright library documentation distinguishes direct library automation from fully managed Playwright Test runners. The repo already has direct Python library precedent, so the first harness should follow that convention.

## Research Agenda

### R-001 — Current context and active-work boundary

Question: What is the active work item, current gate, and workflow boundary?

Findings:

- `current_work.md` confirms Scorcher is still active at Gate 5I-R.
- The developer’s request is planning only, not implementation activation.
- The plan must not mark a browser-smoke work item active.
- The uploaded zip is not a Git checkout, so branch/commit/dirty-state claims are unknown.

Decision:

- Treat current work as Scorcher final smoke gate, not as completed.
- Build this plan as a proposed future harness that can be promoted after the developer decides what to do with current Scorcher work.

### R-002 — Existing automation convention

Question: Does the repo already prefer Playwright or another browser automation framework?

Findings:

- `requirements.txt` includes `playwright`.
- `scripts/validation/lan-smoke-playwright.py` already uses Python Playwright directly.
- No `package.json`, Playwright config, or JS/TS Playwright runner was found in the inspected root.
- The existing Playwright script is a bounded validation script, not a broad E2E suite.

Decision:

- Use Python Playwright direct-library style first.
- Do not introduce Node/`@playwright/test` for the first slice unless Orchestrator finds a newer repo convention in current context.
- A future pytest/Playwright migration can be considered after the first bounded smoke target works.

### R-003 — `/dmcontrol` Scorcher scenario boundary

Question: What is the first smoke scenario and what must be asserted?

Findings:

- `/dmcontrol` currently has AoE state and resolution modal logic in one large HTML file.
- The backend can resolve monster capability targets and place hazards for `area_hazard`.
- Existing selectors are fragile for dynamic action cards because rendered action cards do not expose stable test IDs.
- Canvas-rendered map/hazards cannot be reliably asserted through DOM selectors alone.
- A smoke helper similar to the LAN spellbook test helper is the cleanest way to expose logical state while still using real browser clicks.

Decision:

- First smoke target is `scorcher-ignite-ground-zero-target-hazard`.
- It must assert UI state and backend state:
  - `/dmcontrol` loads.
  - Scorcher is active and action list is visible.
  - Ignite Ground enters AoE targeting.
  - The harness clicks an empty 10-foot square.
  - The modal shows zero affected creatures.
  - Apply Result succeeds.
  - Fire hazards appear in the tactical map state.
  - Modal/tray closes.
  - AoE preview state clears.
  - No console/page/network errors occur.
  - Debug/backend logs include successful hazard placement.

### R-004 — Fixture/state strategy

Question: How should the scenario get deterministic state without production services?

Findings:

- Session persistence routes can load/save named snapshots, but loading requires a file inside the runtime saves directory.
- Current inspected repo has no confirmed dev fixture route that can atomically create the exact Scorcher/map state.
- Existing LAN Playwright smoke uses a test helper and mocked route strategy rather than production data.
- For `/dmcontrol`, route-mocking the backend would not verify real hazard placement; the first target needs real backend state mutation.

Decision:

- Prefer a debug-only smoke fixture route or script, enabled only when `INIT_TRACKER_DEBUGGING=1` and a smoke fixture flag is set.
- The fixture must seed the real backend with:
  - A blank session.
  - Tactical map grid.
  - One active Black and Tan VDA Scorcher combatant.
  - Optional non-target combatants placed away from the target square.
  - Empty cells for a 10-foot square that should have zero targets.
  - Known actor/action IDs returned in the fixture response.
- Fallback: copy a deterministic JSON session fixture into the runtime saves directory discovered by `/api/dm/sessions`, then load it through `/api/dm/sessions/load`.
- Do not seed state through broad UI clicking in the first harness; that would make the smoke brittle and would test setup flows instead of Scorcher Apply Result behavior.

### R-005 — Selector and observability strategy

Question: What selectors/logs are required for a reliable bounded smoke?

Findings:

- `data-testid` is absent from the inspected assets.
- Dynamic action cards are rendered from JavaScript and currently only have class names and click handlers.
- Canvas-rendered map state requires either pixel inspection or exposed logical state. Pixel inspection should be avoided for the first smoke because it is brittle and hard for agents to interpret.
- Existing LAN smoke exposes `window.__lanSpellbookTest`, which is a useful precedent.

Decision:

- Add stable test IDs for DOM controls and a smoke-only `window.__dmcontrolSmoke` helper for logical canvas/map state.
- Keep helpers gated by query param and/or debugging flag. They must not affect normal UI behavior.
- Browser automation must collect console, page errors, failed requests, bad status responses, screenshots, traces, server stdout/stderr, and debug trace JSONL.

### R-006 — Work-item proposal and gates

Question: What is the smallest promotable implementation work?

Decision:

- Proposed first work item: `WORK-20260603-browser-smoke-harness-scorcher-ignite-ground`.
- Scope: instrumentation + fixture + one scenario only.
- It should not expand into LAN sync, multiple monsters, broad regression matrices, visual diffing, or production test infrastructure until the first scenario is reliable.

## Recommended Automation Architecture

### Harness form

Create a Python Playwright script:

`./scripts/validation/dmcontrol-smoke-playwright.py`

Initial CLI:

```bash
.venv/bin/python scripts/validation/dmcontrol-smoke-playwright.py \
  --scenario scorcher-ignite-ground \
  --base-url http://127.0.0.1:8787 \
  --artifact-dir logs/browser-smoke/scorcher-ignite-ground/$(date +%Y%m%d-%H%M%S)
```

Recommended options:

- `--scenario scorcher-ignite-ground`
- `--base-url http://127.0.0.1:8787`
- `--artifact-dir <path>`
- `--start-server`
- `--server-host 0.0.0.0`
- `--server-port 8787`
- `--headful` for local diagnosis only
- `--timeout-ms 30000`
- `--keep-server` only for diagnosis
- `--json-summary <path>` optional override

The first implementation may either:

1. Start and stop the server itself, or
2. Connect to an already-running server.

The preferred agent command is one script that starts and stops the server itself so the developer is not asked to manage the process.

### Server startup

Baseline command requested by the developer:

```bash
INIT_TRACKER_DEBUGGING=1 .venv/bin/python serve_headless.py --host 0.0.0.0 --port 8787
```

Harness behavior:

- Bind can remain `0.0.0.0`.
- Playwright should connect to `http://127.0.0.1:8787/dmcontrol?smoke=1`.
- The harness should wait for either:
  - stdout line `Headless tracker started.`, and
  - an HTTP 200 from `/dmcontrol`.
- The harness should capture stdout/stderr to artifact files.
- The harness should terminate the process at the end unless `--keep-server` is set.

Recommended isolation extension when promoted:

```bash
INIT_TRACKER_DEBUGGING=1 \
INIT_TRACKER_DATA_DIR=.tmp/browser-smoke/data \
INIT_TRACKER_LOG_DIR=.tmp/browser-smoke/logs \
.venv/bin/python serve_headless.py --host 0.0.0.0 --port 8787
```

The exact extra environment variables must be validated against current `runtime_config.py` before implementation. The baseline command remains valid.

### Browser connection

Use Chromium through Python Playwright, matching existing repo convention.

Minimum browser setup:

- `browser = playwright.chromium.launch(headless=True)`
- `context = browser.new_context(record_video_dir=...)` only when video is enabled or on failure.
- `context.tracing.start(screenshots=True, snapshots=True, sources=True)` if supported by installed Playwright.
- `page = context.new_page()`
- `page.goto(f"{base_url}/dmcontrol?smoke=1", wait_until="domcontentloaded")`

Event collection:

- `page.on("console", ...)`
- `page.on("pageerror", ...)`
- `page.on("requestfailed", ...)`
- `page.on("response", ...)` for HTTP `>= 400`
- optional WebSocket logging if current Playwright API and repo need it

Console policy:

- `error` console messages fail the smoke unless allowlisted by exact message.
- `warning` messages are recorded but do not fail unless known harmful.
- Page errors always fail.
- Failed network requests fail unless explicitly allowlisted.
- HTTP 4xx/5xx responses fail unless expected by setup.

### Artifact layout

Each run writes a unique artifact directory:

```text
logs/browser-smoke/scorcher-ignite-ground/YYYYMMDD-HHMMSS/
  summary.json
  summary.md
  server.stdout.log
  server.stderr.log
  console.jsonl
  page-errors.jsonl
  network-failures.jsonl
  bad-responses.jsonl
  trace.zip
  screenshots/
    01-dmcontrol-loaded.png
    02-scorcher-actions-visible.png
    03-ignite-ground-aiming.png
    04-aoe-modal-zero-targets.png
    05-after-apply-hazards.png
  debug-trace/
    debug-trace-*.jsonl
```

`summary.json` must include:

```json
{
  "ok": true,
  "scenario": "scorcher-ignite-ground",
  "base_url": "http://127.0.0.1:8787",
  "started_server": true,
  "artifact_dir": "logs/browser-smoke/scorcher-ignite-ground/...",
  "assertions": [
    {"name": "dmcontrol_loaded", "ok": true},
    {"name": "scorcher_present", "ok": true},
    {"name": "ignite_ground_visible", "ok": true},
    {"name": "aoe_mode_entered", "ok": true},
    {"name": "zero_targets", "ok": true},
    {"name": "apply_result_ok", "ok": true},
    {"name": "hazards_created", "ok": true},
    {"name": "modal_closed", "ok": true},
    {"name": "aoe_cleared", "ok": true},
    {"name": "no_console_errors", "ok": true},
    {"name": "debug_trace_hazard_placement", "ok": true}
  ],
  "hazard_count_before": 0,
  "hazard_count_after": 4,
  "console_error_count": 0,
  "page_error_count": 0,
  "failed_request_count": 0,
  "bad_response_count": 0
}
```

`summary.md` should be paste-ready for Orchestrator and the developer.

## Required Repo Changes by Phase

### Phase 0 — Pre-implementation recon only

No code edits.

Required current-state commands in a real Git checkout:

```bash
scripts/chatgpt_context_refresher.sh
scripts/agent_context_bundle.sh
cat docs/work_items/current_work.md
git status --short
```

Expected outcome:

- Confirm active work.
- Confirm whether Scorcher work should be committed/completed first.
- Confirm there is no newer browser automation convention.

### Phase 1 — Stable selectors and smoke helper

Files likely touched:

- `assets/web/dmcontrol/index.html`
- `tests/test_dm_console_asset_syntax.py` or adjacent asset syntax tests
- possibly a new focused test that verifies required `data-testid` strings exist

Add stable test IDs:

- `dmcontrol-root`
- `dmcontrol-status`
- `dmcontrol-map-canvas`
- `dmcontrol-active-actor-panel`
- `dmcontrol-active-actions-panel`
- `dmcontrol-action-card-ignite-ground`
- `dmcontrol-action-card-flamethrower-burst`
- `dmcontrol-selected-capability-summary`
- `dmcontrol-aoe-status`
- `dmcontrol-resolution-modal`
- `dmcontrol-modal-title`
- `dmcontrol-modal-body`
- `dmcontrol-aoe-affected-count`
- `dmcontrol-apply-result`
- `dmcontrol-cancel-action`
- `dmcontrol-back-to-aiming`

Action card test ID rule:

```text
data-testid="dmcontrol-action-card-${capability_id}"
```

For capability IDs, sanitize only if needed, but prefer the exact action ID already used by the backend (`ignite-ground`, `flamethrower-burst`, etc.).

Add a smoke helper:

```javascript
window.__dmcontrolSmoke = {
  ready(),
  snapshot(),
  gridToClient(col, row),
  clickGridCell(col, row),
  actionVisible(actionId),
  modalActive(),
  aoeState(),
  hazards(),
  hazardsInCells(cells),
  consoleSafeState()
}
```

Helper constraints:

- Must be enabled only for `?smoke=1` or equivalent debug-only mode.
- Must not mutate state except for explicit click helpers that route through real browser events.
- Must return logical state derived from the same `state` object the UI uses.
- Must expose enough information to assert canvas-rendered hazards without pixel inspection.
- Must not be required for normal user flows.

### Phase 2 — Deterministic fixture/state seeding

Preferred fixture implementation:

- Add a debug-only route such as:
  - `POST /api/dev/smoke-fixtures/dmcontrol-scorcher-ignite-ground`
- Enable only when:
  - `INIT_TRACKER_DEBUGGING=1`, and
  - optionally `INIT_TRACKER_ENABLE_SMOKE_FIXTURES=1`.
- Return:
  - `ok`
  - `snapshot`
  - `actor_cid`
  - `actor_name`
  - `capability_ids`
  - `ignite_ground_empty_origin`
  - `expected_hazard_cells`
  - `expected_hazard_count`

Example response shape:

```json
{
  "ok": true,
  "fixture": "dmcontrol-scorcher-ignite-ground",
  "actor_cid": 1,
  "actor_name": "Black and Tan VDA Scorcher",
  "capability_ids": {
    "ignite_ground": "ignite-ground"
  },
  "ignite_ground_empty_origin": {"col": 8, "row": 8},
  "expected_hazard_cells": [
    {"col": 7, "row": 7},
    {"col": 8, "row": 7},
    {"col": 7, "row": 8},
    {"col": 8, "row": 8}
  ],
  "snapshot": {}
}
```

Fallback fixture implementation:

- Add a deterministic session JSON fixture under:
  - `scripts/validation/fixtures/dmcontrol_scorcher_ignite_ground_session.json`
- Harness calls `/api/dm/sessions` to discover `saves_dir`.
- Harness copies the fixture into `saves_dir`.
- Harness calls `/api/dm/sessions/load`.
- Harness validates the returned snapshot.

Preferred route is better because session snapshots can drift and are harder to maintain.

### Phase 3 — Harness shell and artifact collector

Create:

- `scripts/validation/dmcontrol-smoke-playwright.py`

Minimum behavior:

- Parse CLI args.
- Create artifact dir.
- Start server or connect to existing server.
- Wait for readiness.
- Open `/dmcontrol?smoke=1`.
- Start trace collection.
- Register event collectors.
- Write summary files.
- Stop trace and close context on both pass and fail.
- Shut down server unless `--keep-server`.

No Scorcher-specific assertions are required in this phase beyond "page loads and artifacts are written."

### Phase 4 — First Scorcher scenario

Implement only:

- `scorcher-ignite-ground`

No broad matrix, no LAN sync, no Flamethrower, no Tank Bash, no Scorched Earth, no visual diffing.

### Phase 5 — Gate integration

After the first smoke target is reliable:

- Add the smoke command to `scripts/agent_gate_validate.sh` only if the developer approves.
- Or add a separate optional command:
  - `scripts/validation/run-browser-smoke.sh scorcher-ignite-ground`
- Do not make every unit-test gate require browser smoke until runtime cost and flake behavior are known.

### Phase 6 — Later expansion only after approval

Possible future scenarios:

- Flamethrower cone multi-target save flow.
- Tank Bash single-target Apply Result.
- Swap Tank/reload state.
- Scorched Earth Protocol.
- LAN/DM synchronization.
- Persistent hazard visibility on LAN player page.
- Regression smoke after map/DM-control changes.

## Selector/Test-ID Strategy

Use this priority:

1. User-facing role/text locators where stable and semantically important.
2. `data-testid` for dynamic cards, modal internals, and controls whose text may change.
3. Smoke helper logical state for canvas-only map assertions.
4. CSS selectors only as a last resort and only for fixed structure.

Do not rely on:

- Raw class names for dynamic action cards.
- Long CSS chains.
- Pixel colors for the first smoke.
- Text that the developer frequently changes for UX copy.

Required selector contract:

```text
dmcontrol-root
dmcontrol-map-canvas
dmcontrol-active-actor-panel
dmcontrol-active-actions-panel
dmcontrol-action-card-ignite-ground
dmcontrol-resolution-modal
dmcontrol-aoe-affected-count
dmcontrol-apply-result
```

Required logical contract:

```javascript
window.__dmcontrolSmoke.snapshot()
```

Must expose:

```json
{
  "ready": true,
  "activeCid": 1,
  "activeName": "Black and Tan VDA Scorcher",
  "selectedCapabilityId": "ignite-ground",
  "aoePlacementMode": {
    "active": true,
    "capabilityId": "ignite-ground",
    "shape": "square",
    "size": 10,
    "confirmed": false,
    "lockedCursorGridPos": null
  },
  "modal": {
    "active": false,
    "title": ""
  },
  "hazards": [],
  "units": []
}
```

## Deterministic Fixture/State Strategy

The fixture must set a known state without relying on production data or manual UI setup.

Minimum state:

- New blank session.
- Combat started.
- Active actor: Black and Tan VDA Scorcher.
- Scorcher has `ignite-ground` in visible actions.
- Tactical map enabled in the DM-control snapshot.
- Map grid large enough for a 10-foot square.
- Scorcher token placed at a known cell.
- Empty target square placed away from all units.
- Existing hazards count known before apply.
- Fuel/action resources sufficient for Ignite Ground.
- No pending prompts that block Apply Result.
- No modal already open.

The fixture should return all dynamic IDs needed by the smoke script. The harness should never guess actor CID from text alone if the fixture can return it.

## First Smoke Scenario Specification

Scenario ID:

`scorcher-ignite-ground-zero-target-hazard`

Preconditions:

- Server running locally with `INIT_TRACKER_DEBUGGING=1`.
- Browser opens `/dmcontrol?smoke=1`.
- Fixture route or fixture session loads successfully.
- Scorcher is active.
- No console/page/network errors during setup.

Steps:

1. Navigate to `/dmcontrol?smoke=1`.
2. Wait for `window.__dmcontrolSmoke.ready() === true`.
3. Seed or load fixture.
4. Wait until active actor panel names the Scorcher.
5. Assert `dmcontrol-action-card-ignite-ground` is visible.
6. Take screenshot `02-scorcher-actions-visible.png`.
7. Click `dmcontrol-action-card-ignite-ground`.
8. Assert `window.__dmcontrolSmoke.aoeState().active === true`.
9. Assert AoE shape is `square` and size is `10`.
10. Move/click the fixture-provided empty origin cell through real browser pointer events.
11. Assert modal opens.
12. Assert affected target count is `0`.
13. Take screenshot `04-aoe-modal-zero-targets.png`.
14. Click `dmcontrol-apply-result`.
15. Wait for `/api/dm/monster-capabilities/{cid}/resolve-targets?workspace=dmcontrol` response with `ok: true`.
16. Wait for snapshot update.
17. Assert hazard count increased by expected count.
18. Assert expected cells contain fire hazards.
19. Assert modal is closed.
20. Assert AoE placement mode is cleared.
21. Assert no stale selected capability preview remains if expected by the current UX.
22. Take screenshot `05-after-apply-hazards.png`.
23. Assert no page errors, console errors, failed requests, or unexpected 4xx/5xx responses.
24. Parse debug trace/server logs and assert successful hazard placement evidence is present.

Expected pass result:

- `summary.json.ok === true`
- `hazard_count_after > hazard_count_before`
- `hazard_placed_count >= 1`
- `console_error_count === 0`
- `page_error_count === 0`
- `failed_request_count === 0`
- `bad_response_count === 0`
- Modal closed and AoE state cleared.

Failure behavior:

- Save all artifacts.
- Write the failing assertion and last known smoke snapshot into `summary.json` and `summary.md`.
- Exit nonzero.
- Do not ask the developer to inspect source manually.
- Orchestrator may ask for logs/screenshots/artifacts if needed.

## Commands Agents Should Run

### Install/verify browser dependency

Only if Playwright browsers are not already installed:

```bash
.venv/bin/python -m playwright install chromium
```

### Start local server manually

```bash
INIT_TRACKER_DEBUGGING=1 .venv/bin/python serve_headless.py --host 0.0.0.0 --port 8787
```

### Run smoke against an already-running server

```bash
.venv/bin/python scripts/validation/dmcontrol-smoke-playwright.py \
  --scenario scorcher-ignite-ground \
  --base-url http://127.0.0.1:8787 \
  --artifact-dir logs/browser-smoke/scorcher-ignite-ground/$(date +%Y%m%d-%H%M%S)
```

### Preferred one-shot agent command after implementation

```bash
INIT_TRACKER_DEBUGGING=1 \
.venv/bin/python scripts/validation/dmcontrol-smoke-playwright.py \
  --start-server \
  --server-host 0.0.0.0 \
  --server-port 8787 \
  --scenario scorcher-ignite-ground \
  --artifact-dir logs/browser-smoke/scorcher-ignite-ground/$(date +%Y%m%d-%H%M%S)
```

### Report command

```bash
cat logs/browser-smoke/scorcher-ignite-ground/*/summary.md
```

Agents must paste the summary and artifact paths into Orchestrator. They should not ask the developer to manually repeat the smoke unless the harness fails due a product decision or a true unsupported manual judgment.

## Pass/Fail Criteria

### Pass

All must be true:

- Server starts or already-running server is reachable.
- `/dmcontrol?smoke=1` loads.
- Fixture loads deterministic Scorcher state.
- Scorcher action list is visible.
- Ignite Ground card is visible and selectable.
- AoE targeting mode activates.
- 10-foot square placement can be selected on empty cells.
- Modal shows zero affected creatures.
- Apply Result returns `ok: true`.
- Backend reports hazard placement or the updated tactical map contains expected hazards.
- Persistent fire hazards appear in logical map state.
- Apply Result modal/tray closes or clears.
- AoE placement state is cleared.
- No stale targeting preview remains.
- No browser page errors occur.
- No unallowlisted console errors occur.
- No unallowlisted failed network requests or 4xx/5xx responses occur.
- Debug/backend logs include successful hazard placement evidence.
- `summary.json` and screenshots/traces are written.

### Fail

Any of these fail the smoke:

- Page fails to load.
- Fixture fails to seed.
- Scorcher is missing.
- Ignite Ground is missing.
- Action selection does not enter AoE mode.
- Canvas click does not confirm the AoE.
- Modal does not open.
- Affected-target count is not deterministic.
- Apply Result errors or times out.
- Hazard count does not increase.
- Expected hazard cells are not present.
- Modal remains active after success.
- AoE state remains active after success.
- Console/page/network errors occur.
- Artifacts are missing.
- Harness required the developer to manually inspect source or manually repeat the flow.

## Risks and Mitigations

### Risk: Fixture route becomes production attack surface

Mitigation:

- Enable only in debug/smoke mode.
- Reject unless `INIT_TRACKER_DEBUGGING=1` and optional `INIT_TRACKER_ENABLE_SMOKE_FIXTURES=1`.
- Do not expose in production runbooks.
- Add a unit/route test that the fixture route is unavailable when smoke fixtures are disabled.

### Risk: Canvas assertions are brittle

Mitigation:

- Do not start with pixel diffs.
- Use real pointer events for interaction.
- Use `window.__dmcontrolSmoke` for logical state assertions.
- Keep screenshots for diagnosis, not primary pass/fail.

### Risk: Test IDs accidentally become implementation coupling

Mitigation:

- Use test IDs only for automation contract boundaries.
- Keep user-facing role/text locators where stable.
- Avoid long CSS chains.
- Add a simple test that required test IDs exist.

### Risk: Smoke becomes too broad

Mitigation:

- First work item only covers Scorcher Ignite Ground zero-target hazard flow.
- Additional scenarios require separate promotion or explicit developer approval.
- Do not add LAN sync in the first work item.

### Risk: Harness masks real UX failure by using helper methods too heavily

Mitigation:

- Use helper methods for coordinate conversion and logical assertions only.
- Perform actual clicks through Playwright pointer/locator actions.
- Do not call internal action functions like `selectCapability()` or `applyAoeResolutionResultsFromModal()` directly in the pass path.

### Risk: Backend logs are insufficient to prove hazard placement

Mitigation:

- Prefer API response and tactical map snapshot assertions first.
- Add debug event around hazard placement only if missing.
- Copy debug trace into artifacts.

### Risk: Current Scorcher work is still uncommitted or incomplete

Mitigation:

- Orchestrator must check `current_work.md` and current Git status before promoting this plan.
- The developer must decide whether to finish/commit current Scorcher work first.

## Implementation Gates

### Gate 0 — Current-state refresh and scope confirmation

Allowed work:

- Run context scripts in a real Git checkout.
- Read `current_work.md`.
- Confirm existing automation conventions.
- Confirm whether current Scorcher work is complete except final smoke.

Validation:

```bash
scripts/chatgpt_context_refresher.sh
scripts/agent_context_bundle.sh
cat docs/work_items/current_work.md
git status --short
```

Completion:

- Orchestrator knows whether to finish current Scorcher work, promote this plan, or defer.

### Gate 1 — `/dmcontrol` test IDs and smoke helper

Allowed work:

- Add stable `data-testid` attributes.
- Add debug-gated `window.__dmcontrolSmoke`.
- Add focused tests/syntax checks.

Not allowed:

- No fixture route.
- No Playwright scenario yet.
- No Scorcher behavior changes beyond observability hooks.

Validation:

- Existing browser asset syntax tests pass.
- Required test IDs are present.
- `window.__dmcontrolSmoke` is absent or inert unless smoke/debug mode is active.
- Normal `/dmcontrol` loads unchanged.

### Gate 2 — Deterministic Scorcher fixture

Allowed work:

- Add debug-only fixture route or fixture-load strategy.
- Add route gating tests.
- Add fixture response contract.

Not allowed:

- No broad encounter builder rewrite.
- No production fixture route.

Validation:

- Fixture route returns expected actor/action IDs in debug mode.
- Fixture route is unavailable when disabled.
- Snapshot contains Scorcher, tactical map, and expected empty square.

### Gate 3 — Harness shell and artifacts

Allowed work:

- Add Playwright smoke script.
- Start/connect to server.
- Collect artifacts.
- Open `/dmcontrol?smoke=1`.

Not allowed:

- No full Scorcher assertions yet.

Validation:

- Script exits 0 on page-load smoke.
- Script exits nonzero on unreachable server.
- Artifacts are written on both pass and fail.

### Gate 4 — First Scorcher smoke scenario

Allowed work:

- Implement `scorcher-ignite-ground` scenario only.
- Use real browser clicks and fixture state.
- Assert UI, backend response, hazards, and logs.

Validation:

```bash
INIT_TRACKER_DEBUGGING=1 \
.venv/bin/python scripts/validation/dmcontrol-smoke-playwright.py \
  --start-server \
  --server-host 0.0.0.0 \
  --server-port 8787 \
  --scenario scorcher-ignite-ground \
  --artifact-dir logs/browser-smoke/scorcher-ignite-ground/$(date +%Y%m%d-%H%M%S)
```

Completion:

- Summary says pass.
- Artifacts exist.
- Orchestrator can paste summary to developer.

### Gate 5 — Optional gate-validator integration

Allowed work only after Gate 4 is reliable:

- Add an optional browser smoke command to agent validation flow.
- Keep it opt-in if runtime cost/flakiness is high.

Not allowed:

- Do not make browser smoke mandatory for every code pass without developer approval.

## Validation Requirements

Before implementation:

- Current context scripts in real Git checkout.
- `docs/work_items/current_work.md`.
- `git status --short`.
- Confirm whether current Scorcher work is to be completed/committed before new harness work.
- Confirm no newer browser automation convention has appeared.

During implementation:

- Unit/route tests for fixture gating.
- Asset syntax tests for changed browser HTML.
- Existing Scorcher backend tests still pass.
- Existing `scripts/validation/lan-smoke-playwright.py` remains unaffected.
- No unrelated files edited.

After implementation:

- Run the new Playwright smoke and inspect only the generated summary/artifact paths.
- Orchestrator reports pass/fail with:
  - command run,
  - exit code,
  - artifact dir,
  - summary excerpt,
  - console/page/network error counts,
  - hazard count before/after,
  - debug trace evidence.
- Developer is asked for product approval only after automation has run.

## Browser Smoke Requirements

Required for the first scenario:

- `/dmcontrol` loads without console/page/network errors.
- Fixture creates active Scorcher.
- Action list is visible.
- Ignite Ground can be selected.
- AoE mode visibly/logically activates.
- Empty 10-foot square can be clicked.
- Zero targets are shown.
- Apply Result succeeds.
- Fire hazards appear in map state.
- Modal/tray closes.
- AoE state clears.
- Debug trace or backend logs show hazard placement.
- Screenshots and trace are saved.

Future browser smoke requirements after separate approval:

- LAN page observes hazards if LAN sync is included.
- Flamethrower multi-target save flow.
- Tank Bash still works.
- Swap Tank still works.
- Scorched Earth Protocol still works.

## Completion Criteria

This plan is complete when:

- The living document exists at `docs/planning/living_docs/PLAN-20260603-browser-automation-smoke-harness.md`.
- Orchestrator has a paste-ready handoff.
- The proposed work item is documented but not activated.
- The developer has clear options:
  1. finish and commit current Scorcher work,
  2. promote browser smoke automation,
  3. keep this as future planning.

The proposed harness work item can be completed only when:

- One Scorcher Ignite Ground browser smoke runs locally through Playwright.
- It uses deterministic fixture state.
- It writes required artifacts.
- It fails nonzero on UI/backend/log regressions.
- It passes with no console/page/network errors.
- Orchestrator can report pass/fail without developer manual retesting.
- The developer approves the result.

## Reopen Conditions

Reopen this plan if:

- Developer wants Playwright Test/pytest instead of direct Python Playwright.
- The repo adds a newer browser automation convention.
- `/dmcontrol` is split out of single-file HTML before implementation.
- Fixture routes are rejected on security/design grounds.
- Scorcher scenario changes after current Gate 5I-R.
- Browser smoke is flaky or too slow to be useful.
- Agents still ask the developer to manually repeat routine smoke after implementation.
- A future production/deployment plan needs browser smoke in CI or server runbooks.

## Proposed First Implementation Work Item

Do not create this as active unless the developer explicitly promotes it.

Suggested path after promotion:

`docs/work_items/active/WORK-20260603-browser-smoke-harness-scorcher-ignite-ground.md`

Suggested title:

`WORK-20260603-browser-smoke-harness-scorcher-ignite-ground: Add bounded Playwright smoke for Scorcher Ignite Ground Apply Result`

Suggested goal:

Add a local-only Python Playwright smoke harness for `/dmcontrol` that seeds a deterministic Black and Tan VDA Scorcher encounter, performs Ignite Ground zero-target Apply Result, verifies persistent fire hazards, collects artifacts, and reports pass/fail without developer manual browser repetition.

Suggested scope:

- Add `/dmcontrol` test IDs and smoke helper.
- Add debug-only Scorcher smoke fixture.
- Add Playwright harness and artifact collector.
- Add only the first Scorcher Ignite Ground scenario.
- Add focused tests for selector/fixture gating.
- Document commands and artifact locations.

Suggested non-goals:

- No broad E2E suite.
- No production fixture endpoints.
- No LAN sync smoke.
- No Flamethrower/Tank Bash/Scorched Earth scenarios in first work item.
- No deployment or CI change unless separately approved.
- No completion of current Scorcher work unless developer decides to use the harness for that gate.

Suggested validation:

```bash
scripts/chatgpt_context_refresher.sh
scripts/agent_context_bundle.sh
cat docs/work_items/current_work.md
git status --short
.venv/bin/python -m pytest tests/test_dm_console_asset_syntax.py tests/test_scorcher_aoe_resolution.py tests/test_black_and_tan_gate_4.py
INIT_TRACKER_DEBUGGING=1 .venv/bin/python scripts/validation/dmcontrol-smoke-playwright.py --start-server --server-host 0.0.0.0 --server-port 8787 --scenario scorcher-ignite-ground --artifact-dir logs/browser-smoke/scorcher-ignite-ground/$(date +%Y%m%d-%H%M%S)
```

Suggested completion:

- Unit/syntax tests pass.
- Browser smoke summary passes.
- Artifacts are written.
- No console/page/network errors.
- Hazard placement is asserted.
- Orchestrator reports artifact paths and pass/fail.

## Orchestrator Handoff

I created/updated a planning document at: `docs/planning/living_docs/PLAN-20260603-browser-automation-smoke-harness.md`.

Please read it, check `docs/work_items/current_work.md`, and decide whether to:

1. Finish and commit the current Scorcher work.
2. Promote browser smoke automation into a new active work item.
3. Keep this as future planning only.

Current recommendation:

- Do not interrupt the current active Scorcher work item unless the developer explicitly promotes this harness now.
- If promoted, begin with Gate 0 and Gate 1 only.
- Keep the first implementation slice bounded to `/dmcontrol` test IDs, smoke helper, deterministic fixture, and one Scorcher Ignite Ground Playwright scenario.
- Do not expand into LAN sync, broad regression suites, CI, production, or additional Scorcher actions until the first scenario is stable.
- Do not ask the developer to manually inspect source. Ask for command output, artifact directories, smoke summaries, logs, screenshots, or product decisions.

## Refusal / End-State Rule

If this plan is marked Completed, Superseded, Archived, or reaches its completion criteria, Orchestrator should refuse to continue from it unless the developer explicitly reopens it.

Orchestrator must also refuse to implement from this plan while another active work item remains in `docs/work_items/current_work.md`, unless the developer explicitly promotes this work item or states that browser smoke automation should become the active next task.
