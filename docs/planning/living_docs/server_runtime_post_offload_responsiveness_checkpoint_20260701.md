# Server Runtime Post-Offload Responsiveness Checkpoint - 2026-07-01

## Status

Checkpoint/decision document only. This document does not authorize app implementation, test edits, script edits, runtime behavior changes, snapshot schema changes, response payload changes, cache TTL changes, cache ownership changes, route ownership changes, threadpool behavior changes, route migration, app-host/runtime lifecycle implementation, browser asset edits, deploys, commits, pushes, production commands, service restarts, or SSH.

## Decision Summary

The completed DM-console read offload plus tactical workspace serialization resolved the shared health/readiness responsiveness problem enough to stop offload work for now.

The next recommended work item is:

`WORK-20260701-app-host-runtime-lifecycle-checkpoint`

The recommended next lane is docs/planning, not implementation. It should decide the app-host/runtime lifecycle direction before more offload, route migration, lower-level tactical/LAN work, queue-wait behavior changes, or async command acceptance semantics.

## Evidence Inspected

Documents inspected:

- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-dm-console-read-offload-minimal-implementation.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-route-read-offload-decision.md`
- `docs/planning/living_docs/server_runtime_route_read_offload_decision_20260630.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-server-responsiveness-evidence-harness.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-post-smoke-latency-read-model-checkpoint.md`
- `docs/planning/living_docs/server_runtime_post_smoke_latency_read_model_checkpoint_20260630.md`
- `docs/agent_tasks/templates/task-packet.md`

No app code, tests, scripts, old plans, old bugs, runtime reports, `majorTODO.md`, broad repo history, `docs/bug_reports/inbox/BUG-20260626-dmcontrol-terrain-not-visible.md`, or `logs/context/` were inspected.

## What The Offload Sequence Proved

The original responsiveness problem was not just a slow DM route. The valid pre-offload harness showed shared p95/max spikes across health, readiness, plain combat, and workspace combat probes. Every probe still returned HTTP 200, but p95 values were around `890-899 ms` and max values were around `976-977 ms` across all endpoints.

The route-read offload decision correctly narrowed the first implementation to the `GET /api/dm/combat` route call to `ServerRuntimeFacade.read_snapshot(dm_console)`. It deferred lower-level tactical/LAN offload, global facade offload, cache ownership changes, TTL changes, schema changes, queue behavior changes, app-host changes, and gameplay work.

The completed implementation preserved route auth/readiness checks, explicit `include_tactical` context, response payloads, and HTTP mappings. After initial smoke exposed repeated `workspace=dmcontrol` timeouts under overlapping tactical polls, the implementation added route-helper-local serialization for tactical workspace offloads only. Plain non-tactical reads remained unguarded.

The final smoke then showed the intended result: health, readiness, and plain combat no longer spiked in lockstep with tactical workspace reads under the bounded harness profile.

Final post-offload harness summary:

- `/health`: p95 `27.914 ms`, max `43.049 ms`.
- `/api/health`: p95 `27.878 ms`, max `42.897 ms`.
- `/ready`: p95 `28.769 ms`, max `43.147 ms`.
- `/api/ready`: p95 `28.494 ms`, max `42.996 ms`.
- `/api/dm/combat`: p95 `30.410 ms`, max `45.908 ms`.
- `/api/dm/combat?workspace=dmcontrol`: p95 `790.840 ms`, max `1092.869 ms`.

## What Remains Slow

The tactical workspace route remains the slow path:

`GET /api/dm/combat?workspace=dmcontrol`

The final direct check returned HTTP 200 in `0.888537s`. The final harness recorded p95 about `791 ms` and max about `1093 ms` for this endpoint.

This is acceptable evidence to stop shared-responsiveness offload work, but it is not evidence that tactical workspace snapshots are cheap. The known expensive chain remains:

`_dm_console_snapshot_payload()` -> `_dm_tactical_snapshot()` -> `_lan_snapshot()`

The final evidence also does not eliminate historical concerns from the prior decision docs:

- Standalone `_lan_snapshot` slow spans existed in earlier traces.
- Queue wait behavior remains an architectural risk, but was not proven by final smoke to be the current health/readiness bottleneck.
- Legacy tracker/Tk-owned state remains a thread/lifecycle constraint for any future lower-level offload or runtime ownership change.

## Why Not More Offload Now

More offload is not justified by the final evidence.

The original offload objective was to protect the ASGI event loop and shared health/readiness responsiveness while the existing DM-console read-model path runs. The final smoke achieved that bounded objective. Additional offload would now target a different problem: reducing tactical workspace route latency or changing lower-level legacy snapshot execution.

That different problem requires different evidence and design constraints. Lower-level tactical/LAN offload would affect legacy tracker state, possible Tk-owned map-window state, broadcast/WebSocket/read contexts, cache interactions, and cancellation/shutdown semantics. A global facade executor would create a runtime scheduling contract. Neither is justified by the final smoke alone.

## Why App-Host / Runtime Lifecycle Planning Next

The current runtime-facade sequence has already established:

- A package/app-factory boundary.
- A runtime re-export/import boundary.
- Facade command and snapshot contracts.
- Queue-backed command migration for selected low-risk routes.
- DM-console read adoption through `ServerRuntimeFacade.read_snapshot()`.
- Mode-aware DM-console cache refinement.
- Route-local read offload and tactical serialization.

The next unresolved question is not which one route should be offloaded next. It is how the web app host and runtime service should own lifecycle, startup/readiness, shutdown, request isolation, scheduling, traceability, cancellation, and legacy Tk/tracker interaction as the system moves toward a backend-owned web-first product.

Therefore the next lane should be:

`WORK-20260701-app-host-runtime-lifecycle-checkpoint`

That work should be docs/planning only unless a later active task explicitly authorizes implementation.

## Evidence Required Before Reopening Deferred Areas

Lower-level tactical/LAN work should require:

- Fresh harness evidence showing tactical/LAN snapshot work still causes server-wide or user-visible responsiveness failures after the route-local offload.
- Debug traces tying the regression to `_dm_tactical_snapshot()` / `_lan_snapshot()` rather than route auth, cache reuse, queue waits, or browser behavior.
- A thread/lifecycle safety plan for legacy tracker state and any Tk-owned state.
- Browser smoke criteria for tactical correctness, stale data, hidden information, reconnect, and map visibility.

Queue-wait behavior should require:

- Focused route-level evidence from queue-backed HTTP commands showing long synchronous queue waits.
- Concurrent health/readiness probes proving whether queue waits degrade unrelated HTTP responsiveness.
- Command trace evidence distinguishing queue wait, command execution, snapshot generation, and client/browser delay.

Async command acceptance semantics should require:

- A separate command-lifecycle decision covering accepted/pending/result states.
- Timeout, cancellation, duplicate/idempotency, reconnect, persistence, and failure-visibility rules.
- Browser UX expectations for pending commands and eventual failure.
- Compatibility constraints for existing synchronous routes and tests.

Broad offload or facade-owned executor work should require:

- Evidence that the localized route offload is insufficient.
- Saturation/cancellation/shutdown semantics.
- Trace propagation requirements.
- A rollback plan and focused smoke acceptance criteria.

## Deferred Scope

Deferred unless a separate active work item explicitly authorizes it:

- App implementation.
- Runtime lifecycle implementation.
- Test edits.
- Script edits.
- Snapshot schema changes.
- Response payload changes.
- Cache TTL changes.
- Cache ownership changes.
- Route ownership changes.
- Threadpool behavior changes.
- More route migration.
- Broad offload.
- Global facade-owned cache.
- Static tactical/map queue migration.
- Lower-level tactical/LAN offload.
- Queue-wait behavior changes.
- Async command acceptance semantics.
- Player-command routes.
- Combat mutation routes.
- Rules-aware movement.
- AoE creation.
- Structures, ships, and boarding links.
- Browser assets.
- Production operations, commits, pushes, service restarts, deploys, or SSH.

## Validation Expectation For This Checkpoint

Required validation:

```bash
git status --short
timeout 10s git diff --check
```
