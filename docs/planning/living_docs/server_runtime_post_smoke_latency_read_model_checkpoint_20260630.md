# Server Runtime Post-Smoke Latency Read-Model Checkpoint - 2026-06-30

## Status

Checkpoint/decision document only. This document does not authorize app implementation, test edits, route migration, route-side offload, instrumentation, harness code, cache behavior changes, TTL changes, invalidation changes, snapshot schema changes, queue behavior changes, LAN controller behavior changes, Tk behavior changes, WebSocket changes, gameplay changes, browser smoke, server starts, deploys, commits, pushes, or production commands.

## Decision Summary

Selected next implementation lane:

`WORK-20260630-runtime-facade-server-responsiveness-evidence-harness`

The completed mode-aware DM-console cache refinement at `fcf96d9` passed smoke and improved the observed `GET /api/dm/combat?workspace` route posture in the new trace, but it did not prove that the ASGI app remains responsive while heavier runtime work is occurring. The safest next implementation is therefore a bounded server-responsiveness evidence harness, not another cache escalation, route-side read offload, route migration, or high-risk gameplay route move.

The future harness should prove whether health/readiness/combat HTTP handling remains responsive while known heavier runtime work is occurring. It should produce route-level evidence for `/health`, `/api/health`, `/ready`, `/api/ready`, `GET /api/dm/combat`, and `GET /api/dm/combat?workspace` under controlled overlap with heavier runtime work. This checkpoint does not implement that harness.

## Evidence Inspected

Documents inspected:

- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-dm-console-read-model-cache-refinement-minimal-implementation.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-dm-console-read-model-cache-refinement-decision.md`
- `docs/planning/living_docs/server_runtime_dm_console_read_model_cache_refinement_decision_20260630.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-latency-read-model-followup-decision.md`
- `docs/planning/living_docs/server_runtime_latency_read_model_followup_decision_20260630.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-route-read-adoption-minimal-implementation.md`
- `docs/planning/living_docs/server_runtime_snapshot_boundary_checkpoint_20260630.md`
- `docs/planning/living_docs/server_runtime_snapshot_boundary_readiness_decision_20260630.md`

Logs inspected with `grep`, `head`, `tail`, and `sed` only:

- `logs/debug-trace-20260630-183429.jsonl`
- `logs/smoke/WORK-20260630-runtime-facade-dm-console-read-model-cache-refinement-minimal-implementation_smoke-server_20260630-183429.log`

Source sections inspected:

- `server_runtime.py`: `ServerRuntimeFacade.read_snapshot()` and adjacent snapshot validation/dispatch helpers only.
- `dnd_initative_tracker.py`: `GET /api/dm/combat`, `_cached_dm_snapshot` metadata initialization, `_dm_console_snapshot()`, `_dm_console_snapshot_payload()`, `_dm_tactical_snapshot()`, `_lan_snapshot()`, and the DM-console prebuild metadata assignment in `_lan_force_state_broadcast()`.

`init_tracker_server/app.py` was not inspected because the current app-host/runtime boundary was already described by the named planning docs and no additional topology evidence was needed for this decision.

## What The fcf96d9 Smoke Proves

The completed work item records the required smoke evidence:

- Developer reported: "dm worked fine."
- Headless server started and advertised the DM operator and player LAN surfaces.
- LAN session connected and claimed `Dorian`.
- `GET /api/dm/combat?workspace` returned HTTP 200.
- No stale tactical/non-tactical cross-mode data was reported.
- No developer-reported responsiveness problem occurred during this smoke.

The debug trace supports that the mode-aware cache refinement did not break the adopted DM-combat read route. Examples from `logs/debug-trace-20260630-183429.jsonl`:

- Non-workspace `GET /api/dm/combat` returned HTTP 200 in about `2.958 ms`.
- A workspace `GET /api/dm/combat?workspace` returned HTTP 200 in about `29.112 ms`, with `_dm_console_snapshot` about `21.770 ms`, `_dm_console_snapshot_payload` about `21.548 ms`, `combat_service.combat_snapshot` about `17.620 ms`, `_dm_tactical_snapshot` about `3.585 ms`, and `_lan_snapshot` about `3.355 ms`.
- Several later workspace reads returned HTTP 200 in roughly `29-70 ms` with payload size around `73627` bytes.

Inference: the fcf96d9 refinement is behaviorally smoke-passed and the trace contains clear examples where the route-compatible DM-console read path is no longer paying the earlier 1+ second cost on every workspace poll.

## What The fcf96d9 Smoke Does Not Prove

The smoke does not prove that DM-console snapshot generation is solved. The same trace still contains route-context outliers:

- One `GET /api/dm/combat?workspace` returned HTTP 200 in about `608.765 ms`; the nested `_dm_tactical_snapshot` span was about `567.347 ms`.
- Another `GET /api/dm/combat?workspace` returned HTTP 200 in about `600.000 ms`; `_dm_console_snapshot` was about `592.069 ms`, `_dm_console_snapshot_payload` about `591.659 ms`, `_dm_tactical_snapshot` about `562.216 ms`, and `_lan_snapshot` about `561.754 ms`.

The smoke also does not prove ASGI/event-loop responsiveness under heavy runtime work:

- The trace contains no `/health`, `/api/health`, `/ready`, or `/api/ready` HTTP samples.
- The trace shows many standalone `_lan_snapshot` slow spans around `370-500 ms` and a startup hang-candidate `_lan_snapshot` span around `24196.532 ms`, but there is no paired health/readiness/combat probe proving whether unrelated HTTP handling stayed responsive during those spans.

The smoke does not prove synchronous queue behavior is or is not a current HTTP bottleneck:

- The trace includes WebSocket action queue waits, including about `414.949 ms`, `120.395 ms`, and `548.266 ms`.
- It does not provide focused route-level evidence for facade queue-backed HTTP commands waiting synchronously while health/readiness/combat reads are probed.

The smoke does not justify concluding that route-side read offload is safe or necessary:

- Offload could reduce request-thread blocking symptoms, but this trace does not isolate event-loop blocking from snapshot-generation cost.
- Legacy tracker/Tk-owned state concurrency risk remains unresolved.

## Bottleneck Assessment

### 1. DM-console snapshot generation

Current finding: still a proven local bottleneck in the slow route-context examples, but no longer the only immediate decision driver.

Slow `GET /api/dm/combat?workspace` outliers are still dominated by `_dm_console_snapshot_payload()` calling `_dm_tactical_snapshot()`, which calls `_lan_snapshot(include_static=False, hydrate_static=False)`. However, the new trace also contains many fast route reads. That mixed result means the cache refinement helped enough to pause before escalating cache behavior.

### 2. ASGI/event-loop blocking

Current finding: not proven, but important enough to measure next.

There is no health/readiness evidence in the fcf96d9 trace. Because the trace still contains standalone heavy `_lan_snapshot` work and some route-context slow reads, the next safe step is to capture direct responsiveness evidence instead of assuming the app remains responsive.

### 3. Synchronous queue wait behavior

Current finding: known architectural risk, not established as the immediate HTTP bottleneck by this smoke.

The prior snapshot-boundary checkpoint documents that facade queue-backed routes synchronously wait for `LanController._action_states`, and the new trace shows WebSocket action queue waits. But this task's smoke evidence does not directly show queue-backed HTTP routes blocking health/readiness/combat reads. The harness should include enough overlap to make that visible before changing queue behavior.

### 4. Route ownership / import topology

Current finding: not the immediate bottleneck.

The route uses `ServerRuntimeFacade.read_snapshot()` for `GET /api/dm/combat`, and `read_snapshot()` remains a validation/dispatch wrapper delegating to legacy snapshot helpers. Prior package-boundary docs already record that package-local app code imports the facade through `init_tracker_server.runtime`. The trace points to snapshot-builder spans, not import topology or app-host ownership, as the observed latency source.

### 5. Remaining high-risk direct gameplay routes

Current finding: not the next lane.

Remaining high-risk direct gameplay routes are still deferred. Moving them now would widen gameplay ownership while the server responsiveness question is unresolved. The next work should measure HTTP responsiveness under heavier runtime work before selecting more route migration or direct gameplay-route extraction.

## Cache Escalation Decision

Further cache escalation is not justified now.

Do not increase the DM-console cache TTL, move cache ownership into `ServerRuntimeFacade`, introduce facade-owned read-model caching, reuse `_lan._cached_snapshot` directly as a route tactical read model, or add a new invalidation framework from this evidence alone.

Rationale:

- The fcf96d9 cache refinement passed smoke and produced many fast route-context reads.
- Remaining slow spans still implicate tactical/LAN snapshot work, but cache escalation would require stronger freshness and invalidation evidence than this smoke provides.
- The next unknown is not merely "can this route be faster"; it is whether core HTTP endpoints stay responsive while known heavier runtime work overlaps.

## Route-Side Read Offload Decision

Route-side read offload is not justified now.

It needs evidence first. A threadpool/offload path could hide blocking symptoms without reducing snapshot cost, and it may introduce concurrency hazards around legacy tracker/Tk-owned state. If the responsiveness harness proves health/readiness/combat requests stall behind snapshot or queue work, route-side offload can be reopened as a transition mitigation with explicit rollback and thread-safety constraints.

## Recommended Next Work Item

Exact recommended next work item ID:

`WORK-20260630-runtime-facade-server-responsiveness-evidence-harness`

Recommended future goal:

Create a bounded evidence harness proving whether health/readiness/combat HTTP handling remains responsive while known heavier runtime work is occurring.

Recommended future evidence targets:

- `/health`
- `/api/health`
- `/ready`
- `/api/ready`
- `GET /api/dm/combat`
- `GET /api/dm/combat?workspace`
- At least one controlled overlap with heavier known runtime work such as tactical/LAN snapshot building or queue-dispatched runtime work.

The future work item should stop after producing evidence and a narrow decision. It should not combine the harness with cache escalation, offload, route migration, gameplay behavior changes, or topology changes.

## Exact Deferred Scope

Deferred unless a separate active work item explicitly authorizes it:

- App implementation in this checkpoint.
- Test edits in this checkpoint.
- Cache TTL increase.
- Facade-owned snapshot cache.
- Durable polling/read-model cache.
- `_lan._cached_snapshot` route-side reuse.
- New invalidation framework.
- Route-side read offload or threadpool execution.
- More read-route adoption.
- High-risk direct gameplay route migration.
- Player-command routes.
- Combat mutation routes.
- Rules-aware move.
- AoE create.
- Structures, ships, and boarding links.
- Static hydration contract changes.
- Snapshot schema or response payload changes.
- Queue behavior changes.
- LAN controller behavior changes.
- Tk behavior changes.
- WebSocket behavior changes.
- Combat/gameplay behavior changes.
- App-host/package topology changes.
- Launcher changes.
- Browser smoke, server starts, deploys, commits, pushes, and production commands.

## Validation Expectation For This Checkpoint

Required validation for this docs/evidence checkpoint:

```bash
git status --short
timeout 10s git diff --check
```

