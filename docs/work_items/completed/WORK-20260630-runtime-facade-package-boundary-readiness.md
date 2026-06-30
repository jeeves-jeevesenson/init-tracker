# WORK-20260630-runtime-facade-package-boundary-readiness: Runtime facade package-boundary readiness

## Status

Completed.

## Type

Planning/evidence only. No app/source/test implementation.

## Goal

Decide whether the repo is ready to plan the `init_tracker_server/` app-host/runtime-service package boundary, or whether a smaller command-semantics cleanup/planning step must happen first.

## Initial Repository State

Initial `git status --short`:

```text
?? docs/bug_reports/inbox/BUG-20260626-dmcontrol-terrain-not-visible.md
?? logs/context/
```

Initial `HEAD` evidence:

```text
6704c13 WORK-20260630-runtime-facade-command-inventory-consolidation: document facade command inventory
```

The current-work ledger was `Idle` at the start of this pass.

## Files Inspected

- `docs/work_items/current_work.md`
- `docs/architecture/server_runtime_facade_command_inventory_20260630.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-command-inventory-consolidation.md`
- `docs/planning/living_docs/server_runtime_facade_queue_migration_checkpoint_20260630.md`
- `docs/architecture/server_runtime_extraction_decision_20260628.md`
- `docs/planning/living_docs/server_runtime_extraction_living_plan_20260628.md`
- `server_app.py`
- `server_runtime.py`
- `serve_headless.py`
- `dnd_initative_tracker.py`, limited to host/lifecycle/server startup references
- `tests/test_server_health.py`
- `tests/test_headless_host.py`

## Files Changed

- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-package-boundary-readiness.md`
- `docs/work_items/active/WORK-20260630-runtime-facade-package-boundary-readiness.md`

## Readiness Finding

The repo is ready for an app-host/runtime-service package-boundary planning item.

The command boundary is documented enough for planning because `docs/architecture/server_runtime_facade_command_inventory_20260630.md` now records migrated route-command mappings, command constants, payload keys, result keys, response shapes, timeout/error mapping, trace expectations, focused tests, direct-route risks, and known naming gaps.

The command-semantics gaps are real but do not need to block package-boundary planning:

- Result keys are family-specific rather than uniform, including `place_result`, `remove_result`, `move_result`, `obstacle_result`, `terrain_result`, `elevation_result`, `settings_result`, `background_result`, `remove_background_result`, `reorder_background_result`, `hazard_result`, and `feature_result`.
- Action names are not uniformly namespaced, for example `aoe_remove` / `aoe_move` versus `set_*`, `upsert_*`, and `remove_*`.
- Trace event naming remains LanController/WebSocket-shaped with `ws.action.dispatch.start` and `ws.action.dispatch.end`, even for facade-submitted HTTP commands.
- Spell color uses the facade command boundary but is not queue-backed.

Those gaps should be treated as package-boundary planning inputs and future contract-normalization candidates, not as a prerequisite docs-only cleanup. A separate semantics cleanup pass would likely rename or normalize contracts before the package ownership boundary is defined, which risks churn in the wrong layer.

## Host/Lifecycle Evidence

- `server_app.py` defines `create_app(lan_controller=None)` and attaches `app.state.runtime = ServerRuntimeFacade(lan_controller=lan_controller)`.
- `server_app.py` defines an ASGI lifespan that starts the runtime facade, sets `app.state.ready = True`, then clears readiness and shuts down the runtime facade on exit.
- `server_app.py` owns `/health`, `/api/health`, `/ready`, and `/api/ready`.
- `serve_headless.py` sets `INIT_TRACKER_HEADLESS=1`, imports `dnd_initative_tracker` after setting the env var, constructs `InitiativeTracker()`, optionally starts LAN through existing tracker behavior, and enters `app.mainloop()`.
- `dnd_initative_tracker.py` LAN startup imports `create_app`, builds `self._fastapi_app = create_app(lan_controller=self)`, assigns `self._runtime = self._fastapi_app.state.runtime`, registers route handlers on that app, and starts Uvicorn in a LanController-owned thread.
- `tests/test_server_health.py` verifies factory readiness behavior and health/readiness endpoint responses.
- `tests/test_headless_host.py` verifies headless env detection, `HeadlessRoot` scheduling, desktop-surface guards, and a subprocess launch that starts LAN and receives HTTP 200 from `/dm`.

## Readiness Questions

### 1. Is the command boundary documented enough to support package-boundary planning?

Yes. The command inventory is sufficient for package-boundary planning because it distinguishes queue-backed commands, the spell-color direct-facade exception, shared timeout/error/trace semantics, direct/not-yet-queue-backed routes, and known unknowns.

It is not sufficient for source movement or package implementation. The next item must remain planning/evidence only unless a later work item explicitly authorizes source edits.

### 2. Are there unresolved command-semantics gaps that should be planned before package-boundary work?

No separate prerequisite planning item is recommended. The unresolved semantics gaps should be captured as package-boundary constraints:

- do not normalize result keys during package-boundary planning;
- do not rename command constants or action names during package-boundary planning;
- do not convert spell color to queue-backed behavior during package-boundary planning;
- do not rename LanController/WebSocket trace events during package-boundary planning;
- explicitly define where future contract normalization would live.

### 3. What exact boundaries would an `init_tracker_server/` planning item need to define?

The next package-boundary planning item should define these boundaries without creating package files:

- App host boundary: app factory ownership, lifespan ownership, health/readiness ownership, Uvicorn startup expectations, and route registration ownership.
- Runtime service boundary: the service object ASGI code depends on, including start/shutdown/readiness, command submission, snapshot/read-model access, and future event publication.
- Command contract boundary: where `RuntimeCommand`, `RuntimeCommandResult`, `RuntimeCommandTrace`, command constants, timeout/error mapping, and queue metadata contracts should live.
- Legacy runtime adapter boundary: how current LanController/Tk queue authority remains behind the runtime service without importing tracker internals into app-host code.
- Headless host boundary: how `serve_headless.py` and `INIT_TRACKER_HEADLESS` remain compatibility launch seams while future server-owned startup is planned.
- Route adapter boundary: how route modules should validate requests, call the runtime service, map errors, and preserve current response shapes without owning runtime mutation.
- Health/readiness boundary: how `/health`, `/api/health`, `/ready`, and `/api/ready` preserve current semantics while moving toward package ownership.
- Test/smoke boundary: which focused validations protect app factory, lifespan, headless launch, and current route behavior.
- Import direction boundary: which imports are allowed from future `init_tracker_server/` code into existing modules, and which tracker-to-server imports must be temporary compatibility only.
- Out-of-package boundary: what remains in legacy tracker/runtime files until later implementation slices.

### 4. What should remain explicitly out of scope for package-boundary planning?

The next item should not:

- edit `server_app.py`, `server_runtime.py`, `serve_headless.py`, `dnd_initative_tracker.py`, or tests;
- create `init_tracker_server/`;
- create package-boundary source files;
- implement runtime/service/app-host behavior;
- migrate routes;
- normalize command result keys;
- rename command constants or action names;
- convert spell color to queue-backed behavior;
- rename trace events;
- modify health/readiness behavior;
- modify headless startup behavior;
- change Uvicorn ownership;
- touch production deployment, service restart, SSH, DNS/FQDN, or topology;
- inspect old plans, `majorTODO.md`, runtime reports, archived docs, broad logs, or unrelated files unless explicitly named.

### 5. What validation/smoke expectations must be preserved?

For any later implementation that touches `server_app.py`, preserve focused validation of:

- `create_app()` construction;
- lifespan startup setting readiness true;
- lifespan shutdown setting readiness false;
- `/health` and `/api/health` returning HTTP 200 with `{"status": "healthy", "ready": true}` inside lifespan;
- `/ready` and `/api/ready` returning HTTP 200 with `{"status": "ready"}` inside lifespan;
- `/ready` returning HTTP 503 with `{"status": "not ready"}` before lifespan startup.

For any later implementation that touches `serve_headless.py`, headless startup, or LanController server startup, preserve focused validation of:

- `INIT_TRACKER_HEADLESS=1` being set before importing `dnd_initative_tracker`;
- `HeadlessRoot` replacing Tk in headless mode;
- full `InitiativeTracker()` construction in headless mode;
- LAN startup serving `/dm` with HTTP 200 in the subprocess smoke path;
- clean shutdown of LAN/headless mainloop.

For any later implementation that changes route registration or route modules, preserve current route behavior with focused route tests for affected endpoints only. Do not substitute broad test suites for targeted route behavior checks, and do not claim browser readiness from Python tests alone.

## Required Decision

Recommended next work item:

- Proposed ID: `WORK-20260630-runtime-facade-package-boundary-plan`
- Title: App-host/runtime-service package-boundary planning
- Type: planning/evidence

This is option A.

## Why This Is Next

The command inventory has already consolidated the necessary command-boundary evidence. The next architectural risk is not another route slice or another inventory pass; it is defining the future package ownership boundary so subsequent implementation does not move files or normalize contracts in an ad hoc order.

Package-boundary planning can explicitly preserve current behavior while deciding where app-host, runtime-service, command-contract, legacy-adapter, route-adapter, health/readiness, and headless compatibility responsibilities belong.

## Why The Other Options Wait

Option B, command-semantics cleanup planning, should wait because the known semantics gaps are documented and can be handled as constraints inside the package-boundary plan. Planning cleanup first would risk optimizing names and result shapes before ownership boundaries are defined.

Option C, another route migration/evidence slice, should wait because the obvious low-risk static map route sequence has already been consumed. Remaining direct candidates include rules-aware movement, AoE creation, structures, ships, boarding links, turn/combat mutations, and HP/combat state paths. Those need fresh route-specific evidence before implementation, and they should not interrupt package-boundary planning.

## Next Task Packet

Recommended next task:

`WORK-20260630-runtime-facade-package-boundary-plan`

Title:

App-host/runtime-service package-boundary planning.

Type:

Planning/evidence only.

Files the next task should inspect first:

- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-package-boundary-readiness.md`
- `docs/architecture/server_runtime_facade_command_inventory_20260630.md`
- `docs/architecture/server_runtime_extraction_decision_20260628.md`
- `docs/planning/living_docs/server_runtime_extraction_living_plan_20260628.md`
- `server_app.py`
- `server_runtime.py`
- `serve_headless.py`
- `dnd_initative_tracker.py`, limited to app factory import, route registration, LanController server startup, Uvicorn lifecycle, and `_runtime` assignment
- `tests/test_server_health.py`
- `tests/test_headless_host.py`

Allowed files the next task should edit:

- `docs/work_items/current_work.md`
- `docs/work_items/active/WORK-20260630-runtime-facade-package-boundary-plan.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-package-boundary-plan.md`
- `docs/architecture/server_runtime_package_boundary_plan_20260630.md`

Explicit forbidden scope for the next task:

- Do not edit `server_app.py`.
- Do not edit `server_runtime.py`.
- Do not edit `serve_headless.py`.
- Do not edit `dnd_initative_tracker.py`.
- Do not edit tests.
- Do not create `init_tracker_server/`.
- Do not create package-boundary source files.
- Do not implement runtime/service/app-host behavior.
- Do not migrate routes.
- Do not rename command constants, action names, result keys, or trace events.
- Do not convert spell color to queue-backed behavior.
- Do not change health/readiness behavior.
- Do not change headless startup or Uvicorn ownership.
- Do not inspect old plans, `majorTODO.md`, runtime reports, archived docs, broad logs, or unrelated files unless explicitly named.
- Do not run full test suites.
- Do not push, deploy, restart services, SSH elsewhere, or alter production topology.

## Validation

Required validation for this pass:

- `git status --short`
- `timeout 10s git diff --check`

## Stop Conditions

No stop condition was hit.

The ledger was Idle, the command inventory document was present, the readiness decision did not require source/test edits, and host/lifecycle evidence was determinable from the named files.
