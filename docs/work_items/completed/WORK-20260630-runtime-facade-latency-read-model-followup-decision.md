# WORK-20260630-runtime-facade-latency-read-model-followup-decision

Status: Completed

## Goal

Complete a bounded latency/read-model follow-up decision for `GET /api/dm/combat` and snapshot hot paths after the first route-read adoption.

This was a planning/evidence-only pass. No app code, tests, routes, cache behavior, queue behavior, LAN controller behavior, Tk behavior, WebSockets, gameplay logic, browser assets, server starts, deploys, pushes, or production commands were changed or run.

## Source Documents

- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-route-read-adoption-minimal-implementation.md`
- `docs/planning/living_docs/server_runtime_route_read_adoption_decision_20260630.md`
- `docs/planning/living_docs/server_runtime_snapshot_boundary_readiness_decision_20260630.md`
- `docs/planning/living_docs/server_runtime_snapshot_boundary_checkpoint_20260630.md`
- `logs/debug-trace-20260630-164720.jsonl`
- `logs/smoke/WORK-20260630-runtime-facade-route-read-adoption-minimal-implementation_smoke-server_20260630-164720.log`

## Files Changed

- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-latency-read-model-followup-decision.md`
- `docs/planning/living_docs/server_runtime_latency_read_model_followup_decision_20260630.md`

## Evidence Inspected

Logs were inspected only with `grep`, `head`, `tail`, and `sed`.

Code inspection stayed limited to:

- `server_runtime.py`: `read_snapshot()` only.
- `dnd_initative_tracker.py`: `GET /api/dm/combat`, `_current_request_wants_tactical_map()`, `_dm_console_snapshot()`, `_dm_console_snapshot_payload()`, `_dm_tactical_snapshot()`, `_lan_snapshot()`, and `_lan_snapshot` call sites named by the task.
- `combat_service.py`: `CombatService.combat_snapshot()` only.

## Decision

Selected next slice: cache/read-model refinement, starting with a bounded decision/spec work item.

Exact recommended next work item ID:

`WORK-20260630-runtime-facade-dm-console-read-model-cache-refinement-decision`

Rationale:

- The existing debug trace is sufficient to avoid another evidence-capture pass.
- `GET /api/dm/combat` route reads already expose the hot path; another narrow read-route adoption would spread the same latency pattern before reducing it.
- Route-side read offload would only hide request-thread blocking and introduces concurrency risk around legacy tracker/Tk-owned state; it should remain a later transition mitigation.
- The hottest route-context work is the DM console composite payload, especially tactical/LAN snapshot construction below `_dm_console_snapshot_payload()`.

## Key Evidence

The route-read adoption smoke completed successfully: the headless tracker started, DM and player LAN surfaces were advertised, LAN sessions connected, and a session claimed Fred.

The debug trace showed `GET /api/dm/combat` returning HTTP 200. Workspace route reads ranged from about 112 ms to 1.416 s:

- `112.959 ms`
- `112.756 ms`
- `254.325 ms`
- `280.869 ms`
- `893.591 ms`
- `1010.931 ms`
- `1066.479 ms`
- `1149.322 ms`
- `1170.187 ms`
- `1247.723 ms`
- `1416.111 ms`

The hottest route-context example was:

- `GET /api/dm/combat?workspace`: `http.request` `1415.720 ms`
- `_dm_console_snapshot`: `1396.260 ms`
- `_dm_console_snapshot_payload`: `1395.968 ms`
- `_dm_tactical_snapshot`: `1305.780 ms`
- `_lan_snapshot`: `1305.254 ms`
- `combat_service.combat_snapshot`: `89.599 ms`

Overall snapshot hot-path observations:

- `_lan_snapshot` had a startup hang-candidate span of `25739.757 ms` and later standalone slow/hang spans, including `2742.220 ms`, `1433.258 ms`, and repeated `385-390 ms` spans.
- `_dm_console_snapshot` route-context spans reached `1396.260 ms`.
- `_dm_tactical_snapshot` route-context spans reached `1305.780 ms`.
- `combat_service.combat_snapshot` was not the dominant route bottleneck; observed route-context spans were generally about `80-175 ms`, with overall trace spans reaching about `269 ms`.

## Deferred Scope

Deferred from this work item and from the immediate next action unless separately authorized:

- App implementation.
- Test edits.
- Route migration.
- Another read-route adoption.
- Route-side threadpool/offload implementation or planning beyond the later deferred note.
- New instrumentation.
- Cache implementation, cache TTL changes, cache invalidation changes, or facade-owned cache movement.
- Snapshot builder rewrites.
- Queue behavior, LAN controller behavior, Tk behavior, WebSocket behavior, player-command routes, combat mutation routes, direct gameplay route migration, rules-aware move, AoE create, structures, ships, boarding links, static hydration contracts, browser smoke, server starts, deploys, pushes, and production commands.

## Next Safe Action

Open `WORK-20260630-runtime-facade-dm-console-read-model-cache-refinement-decision`.

That next decision should define one safe cache/read-model refinement target for the DM console composite path, including freshness expectations, invalidation boundaries, route/facade contract shape, rollback posture, and focused validation before any code implementation.

## Validation

Required validation commands:

- `git status --short`
- `timeout 10s git diff --check`
