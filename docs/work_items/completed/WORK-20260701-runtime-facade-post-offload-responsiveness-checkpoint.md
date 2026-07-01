# WORK-20260701-runtime-facade-post-offload-responsiveness-checkpoint

Status: Completed

## Goal

Complete a bounded post-offload responsiveness checkpoint using the completed DM-console read offload implementation and final smoke evidence.

This was a docs/evidence decision pass only. No app code, tests, scripts, runtime behavior, snapshot schemas, response payloads, cache TTLs, cache ownership, route ownership, threadpool behavior, app-host lifecycle implementation, route migration, gameplay work, browser assets, deploys, commits, pushes, or production commands were changed or run.

## Files Changed

- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260701-runtime-facade-post-offload-responsiveness-checkpoint.md`
- `docs/planning/living_docs/server_runtime_post_offload_responsiveness_checkpoint_20260701.md`

No active work item copy was left after completion.

## Evidence Inspected

Documents:

- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-dm-console-read-offload-minimal-implementation.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-route-read-offload-decision.md`
- `docs/planning/living_docs/server_runtime_route_read_offload_decision_20260630.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-server-responsiveness-evidence-harness.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-post-smoke-latency-read-model-checkpoint.md`
- `docs/planning/living_docs/server_runtime_post_smoke_latency_read_model_checkpoint_20260630.md`
- `docs/agent_tasks/templates/task-packet.md`

No app source, tests, scripts, old plans, old bugs, runtime reports, `majorTODO.md`, broad repo history, `docs/bug_reports/inbox/BUG-20260626-dmcontrol-terrain-not-visible.md`, or `logs/context/` were inspected.

## Decision

Route-local offload plus tactical workspace serialization resolved the shared health/readiness responsiveness problem enough to stop offload work for now.

The next recommended work item is:

`WORK-20260701-app-host-runtime-lifecycle-checkpoint`

This should be a bounded docs/planning slice. It should not begin app-host/runtime lifecycle implementation.

## Evidence Summary

Before offload, the valid responsiveness harness showed no HTTP failures but shared p95/max spikes across all health, readiness, and combat probes:

- `/health`: p95 `898.975 ms`, max `976.759 ms`.
- `/api/health`: p95 `897.679 ms`, max `976.826 ms`.
- `/ready`: p95 `896.786 ms`, max `977.464 ms`.
- `/api/ready`: p95 `897.209 ms`, max `976.381 ms`.
- `/api/dm/combat`: p95 `898.410 ms`, max `977.185 ms`.
- `/api/dm/combat?workspace=dmcontrol`: p95 `890.811 ms`, max `976.909 ms`.

That evidence justified a narrow route-side offload because slow route-context workspace reads were dominated by:

`_dm_console_snapshot_payload()` -> `_dm_tactical_snapshot()` -> `_lan_snapshot()`

The completed implementation then offloaded only `GET /api/dm/combat`'s synchronous `ServerRuntimeFacade.read_snapshot(dm_console)` call through Starlette `run_in_threadpool`, preserving route auth, readiness checks, explicit `include_tactical` params, response payloads, and HTTP status mappings. A follow-up fix serialized tactical workspace offloads only, after smoke evidence showed overlapping tactical snapshot builders could create repeated `workspace=dmcontrol` timeouts.

The final developer smoke passed. Direct route checks returned:

- `/api/dm/combat`: HTTP 200 in `0.025270s`.
- `/api/dm/combat?workspace=dmcontrol`: HTTP 200 in `0.888537s`.

Final harness evidence:

- `/health`: 120 samples, 0 failures, p50 `9.164 ms`, p95 `27.914 ms`, max `43.049 ms`.
- `/api/health`: 120 samples, 0 failures, p50 `9.631 ms`, p95 `27.878 ms`, max `42.897 ms`.
- `/ready`: 120 samples, 0 failures, p50 `9.475 ms`, p95 `28.769 ms`, max `43.147 ms`.
- `/api/ready`: 120 samples, 0 failures, p50 `10.023 ms`, p95 `28.494 ms`, max `42.996 ms`.
- `/api/dm/combat`: 120 samples, 0 failures, p50 `12.063 ms`, p95 `30.410 ms`, max `45.908 ms`.
- `/api/dm/combat?workspace=dmcontrol`: 120 samples, 0 failures, p50 `12.725 ms`, p95 `790.840 ms`, max `1092.869 ms`.

The final evidence proves the previous shared health/readiness lockstep spikes were removed in the bounded smoke profile. It does not prove tactical workspace snapshot generation is cheap.

## Decision Questions

Did route-local offload plus tactical serialization resolve the shared health/readiness responsiveness problem enough to stop offload work for now?

Yes. The final harness shows health, readiness, and non-tactical combat remained responsive while tactical workspace reads still had high outliers. The problem changed from shared server responsiveness spikes to a localized tactical workspace read-model cost. More offload is not justified from this evidence alone.

What remains slow or spiky after the final smoke?

`/api/dm/combat?workspace=dmcontrol` remains slow/spiky: p95 about `791 ms`, max about `1093 ms`, and the direct route check was about `889 ms`. The known underlying cost is still the tactical/LAN snapshot chain when a workspace payload is requested. Prior trace evidence also recorded standalone `_lan_snapshot` slow spans and queue-wait risks, but the final smoke does not prove those are currently degrading health/readiness.

Does the evidence justify app-host/runtime lifecycle realignment as the next lane?

Yes, as planning only. The current sequence has a package boundary, facade contracts, queue-backed command migration, read-snapshot adoption, cache refinement, route-local offload, and tactical serialization. The remaining risk is now less "which route should be offloaded next" and more "what runtime host owns lifecycle, scheduling, shutdown/cancellation, request isolation, and legacy thread interaction." A bounded app-host/runtime lifecycle checkpoint should define that direction before more route/offload work.

What evidence would be required later before reopening lower-level tactical/LAN work, queue-wait behavior, or async command acceptance semantics?

Reopen lower-level tactical/LAN work only with fresh trace plus harness evidence showing tactical/LAN snapshot work still creates user-visible or server-wide responsiveness problems after the route-local offload, and with explicit thread/lifecycle safety constraints for legacy tracker/Tk-owned state.

Reopen queue-wait behavior only with focused route-level evidence showing queue-backed HTTP commands synchronously wait long enough to degrade health/readiness, command latency, or browser-visible behavior, including trace spans tying the delay to queue wait rather than snapshot generation.

Reopen async command acceptance semantics only with a separate command-lifecycle decision covering accepted/pending/result status, cancellation, timeout, failure visibility, idempotency, browser UX, and persistence/reconnect safety. The current smoke evidence is not enough to change command acceptance semantics.

## Deferred Scope

Deferred unless a separate active work item explicitly authorizes it:

- App implementation.
- Test edits.
- Script edits.
- Runtime behavior changes.
- Snapshot schema changes.
- Response payload changes.
- Cache TTL changes.
- Cache ownership changes.
- Route ownership changes.
- Threadpool behavior changes.
- App-host/runtime lifecycle implementation.
- Route migration.
- Broad offload.
- Global facade-owned cache.
- Lower-level `_dm_tactical_snapshot()` or `_lan_snapshot()` offload.
- Static tactical/map queue migration.
- Rules-aware movement.
- AoE creation.
- Structures, ships, and boarding links.
- Player-command routes.
- Combat mutation routes.
- Queue-wait behavior changes.
- Async command acceptance semantics.
- Browser assets.
- Deploys, commits, pushes, production commands, service restarts, or SSH.

## Ledger Update

`docs/work_items/current_work.md` was returned to Idle.

Allowed next action is to open:

`WORK-20260701-app-host-runtime-lifecycle-checkpoint`

That next work item should be docs/planning only unless a separate task explicitly authorizes implementation.

## Validation

Required validation commands:

- `git status --short`
- `timeout 10s git diff --check`

Results are recorded in the final agent report.
