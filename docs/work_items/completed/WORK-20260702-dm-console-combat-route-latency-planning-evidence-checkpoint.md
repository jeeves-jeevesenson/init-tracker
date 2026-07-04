# WORK-20260702-dm-console-combat-route-latency-planning-evidence-checkpoint

Status: Completed

## Goal

Complete a bounded Codex docs/evidence planning checkpoint for the remaining DM console combat route/read-model latency after commit `d16a2aa`.

This checkpoint decided what the next safe development lane should be. It did not implement a fix, optimize latency, edit app code, edit tests, edit logs, start the server, run browser smoke, deploy, restart services, SSH, push, commit, alter production topology, patch the small smoke bug, or change routes, route registration, route bodies, payloads, snapshot schemas, cache behavior, TTLs, static hydration, WebSockets, auth/claims/reconnect, queue behavior, command semantics, persistence, or gameplay behavior.

## Files Inspected

- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260702-snapshot-lan-resource-pools-ttl-rebuild-smoke-evidence-capture.md`
- `docs/planning/living_docs/snapshot_lan_resource_pools_ttl_rebuild_smoke_evidence_capture_20260702.md`
- `docs/runtime_reports/snapshot_lan_resource_pools_ttl_rebuild_smoke_evidence_20260702.md`
- `docs/work_items/completed/WORK-20260702-snapshot-lan-resource-pools-ttl-rebuild-minimal-implementation.md`
- `docs/runtime_reports/snapshot_lan_resource_pools_ttl_rebuild_minimal_implementation_20260702.md`
- `docs/work_items/completed/WORK-20260702-snapshot-lan-resource-pools-hot-path-cache-smoke-evidence-capture.md`
- `docs/runtime_reports/snapshot_lan_resource_pools_hot_path_cache_smoke_evidence_20260702.md`
- `docs/work_items/completed/WORK-20260701-snapshot-lan-hot-path-targeted-instrumentation-evidence.md`
- `docs/runtime_reports/snapshot_lan_hot_path_targeted_instrumentation_evidence_20260701.md`
- `logs/smoke/WORK-20260702-snapshot-lan-resource-pools-ttl-rebuild-smoke-evidence-capture_smoke-server_20260702-193152.log`, using `head` and `tail` only
- `logs/debug-trace-20260702-193152.jsonl`, using `head`, `tail`, and `grep` only
- `scripts/snapshot_lan_hot_path_latency_harness.py`
- `dnd_initative_tracker.py`, limited to `_dm_combat_read_snapshot_in_threadpool`, the `GET /api/dm/combat` route/read seam, `_dm_console_snapshot`, `_dm_console_snapshot_payload`, `dm.console.combat_snapshot`, `_dm_tactical_snapshot_from_lan_snapshot`, and `_dm_tactical_snapshot`
- `server_runtime.py`, limited to `ServerRuntimeFacade.read_snapshot`, DM console include-tactical resolution, and trace-context forwarding

No `majorTODO.md`, old plans, unrelated runtime reports, unrelated logs, browser assets, tests, production files, `docs/bug_reports/inbox/BUG-20260626-dmcontrol-terrain-not-visible.md`, or `logs/context/` files were inspected or edited.

## Files Changed

- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260702-dm-console-combat-route-latency-planning-evidence-checkpoint.md`
- `docs/planning/living_docs/dm_console_combat_route_latency_planning_evidence_checkpoint_20260702.md`
- `docs/runtime_reports/dm_console_combat_route_latency_planning_evidence_20260702.md`

The active work item copy was created while the task was open and removed after completion.

## Evidence Decision

Keep commit `d16a2aa`.

Resource-pools improved materially and should not be reopened from this checkpoint:

- prior `lan.snapshot.resource_pools` p95 `759.372 ms` and `>=250 ms` count `83`
- new `lan.snapshot.resource_pools` p95 `137.346 ms` and `>=250 ms` count `4`
- new trace load shape was heavier at `212` combatants, `10` players, and `202` monsters

The remaining slow path is now DM console combat route/read-model latency:

- `dm.console.combat_snapshot`: count `54`, p50 `839.307 ms`, p95 `2038.109 ms`, max `2204.090 ms`
- `_dm_console_snapshot_payload`: count `56`, p50 `901.847 ms`, p95 `2089.417 ms`, max `2317.861 ms`
- `_dm_console_snapshot`: count `51`, p50 `854.435 ms`, p95 `2103.137 ms`, max `2319.635 ms`
- `http.request:/api/dm/combat`: count `30`, p50 `1003.165 ms`, p95 `3454.867 ms`, max `4262.795 ms`

The trace and seam inspection show `_dm_console_snapshot_payload()` wraps `dm_service.combat_snapshot()` with `dm.console.combat_snapshot`, then optionally adds tactical data. `ServerRuntimeFacade.read_snapshot()` only forwards `include_tactical` and `_trace_context` into `_dm_console_snapshot()`, and the route already offloads `runtime.read_snapshot()` through the existing threadpool helper.

The current evidence is enough to focus the next lane on DM console combat read-model attribution, but not enough for direct behavior-preserving optimization. The body of `dm_service.combat_snapshot()` remains opaque in this trace, and the `http.request:/api/dm/combat` p95/max still may include response serialization, request overlap, or large tactical response effects.

## Span Classification

Primary current span:

- `dm.console.combat_snapshot`, because its p50/p95 are already hundreds to thousands of milliseconds and it nearly matches the `_dm_console_snapshot_payload` and `_dm_console_snapshot` wrapper timings.

Route-visible/wrapper symptoms:

- `_dm_console_snapshot_payload`, because it is the immediate wrapper around combat snapshot assembly plus optional tactical/pending prompt merge.
- `_dm_console_snapshot`, because it mostly delegates to `_dm_console_snapshot_payload()` after a short cache check.
- `http.request:/api/dm/combat`, because it includes the route-visible result of read-model work plus response serialization and request scheduling effects.

Nested or bounded spans that should not be the next primary lane:

- `_dm_tactical_snapshot`, because inspected samples are materially smaller than the route/read-model total and tactical extraction is separate from combat snapshot assembly.
- `dm.tactical.from_lan_snapshot`, because the harness row is comparatively small: count `32`, p50 `0.108 ms`, p95 `22.713 ms`, max `37.688 ms`.
- `lan.snapshot.units`, because it became visible but bounded: count `359`, p50 `41.883 ms`, p95 `47.763 ms`, max `89.288 ms`.

Startup-only `lan.snapshot.static_fields` remains a separate startup outlier and should stay deferred unless explicitly reopened.

## Answers

1. What remains slow is the DM console combat route/read-model path: `dm.console.combat_snapshot`, `_dm_console_snapshot_payload`, `_dm_console_snapshot`, and `http.request:/api/dm/combat`.
2. It is isolated enough for targeted attribution/evidence, not direct implementation. The trace points at `dm.console.combat_snapshot`, but it does not split the internals of `dm_service.combat_snapshot()`.
3. `dm.console.combat_snapshot` appears primary. `_dm_console_snapshot_payload`, `_dm_console_snapshot`, and `http.request:/api/dm/combat` are wrapper/route-visible symptoms. `_dm_tactical_snapshot`, `dm.tactical.from_lan_snapshot`, and `lan.snapshot.units` are nested or bounded in this trace.
4. Yes. The `212`-combatant / `202`-monster shape means the next lane should focus on scale/read-model composition rather than route infrastructure.
5. The next safe work item should be targeted DM console combat read-model attribution/evidence. It should not be direct optimization or implementation planning for a specific fix yet.
6. Future slices must protect app behavior, routes, route bodies, route registration, payload schemas, snapshot schemas, cache behavior, TTLs, resource-pools behavior, static hydration, WebSockets, queues, auth/claims/reconnect, command semantics, persistence, production topology, deployment/restart behavior, and gameplay behavior unless explicitly scoped.
7. Yes. Startup-only `lan.snapshot.static_fields` should remain deferred separately.
8. Yes. The small smoke bug should remain deferred as separate bug-capture scope and was not patched.
9. Recommended next work item: `WORK-20260702-dm-console-combat-read-model-targeted-instrumentation-evidence`.

## Recommended Next Work

Recommended next work item:

`WORK-20260702-dm-console-combat-read-model-targeted-instrumentation-evidence`

Recommended type:

Targeted attribution/evidence, not latency optimization and not gameplay implementation.

Recommended goal:

Add or use narrow low-cardinality attribution around the DM console combat read-model composition path so the next evidence run can separate internal `dm_service.combat_snapshot()` work from route/read wrappers, optional tactical response costs, response serialization, and request overlap. The next item should preserve route behavior, payload shape, cache behavior, WebSocket behavior, queue behavior, auth/claims/reconnect, persistence, production topology, and gameplay semantics.

## Deferred Scope

Remain forbidden until a new active work item authorizes the specific change:

- direct DM console combat read-model optimization
- route migration, route registration changes, or route body movement
- another resource-pools implementation or cache refinement
- cache ownership or cache TTL changes
- snapshot schema or response payload changes
- startup static-fields implementation
- broad snapshot/LAN optimization
- static hydration or snapshot warm-up ownership changes
- broader offload or facade-owned cache
- WebSocket, queue, auth, claims, reconnect, command semantic, persistence, production, or gameplay changes
- server start, browser smoke, deploy, restart, SSH, push, commit, or topology changes
- patching the small smoke bug inside this latency lane

## Ledger Update

`docs/work_items/current_work.md` was returned to Idle with no active work item.

The completed table now includes this planning/evidence checkpoint. The allowed next action is targeted DM console combat read-model attribution/evidence if latency work continues, deploy-prep review if still desired, pause/no further migration, or a separate deferred bug-capture item for the small smoke bug.

`majorTODO.md` was not inspected or updated because it was outside this task's allowed edit list.

## Validation

Required validation commands:

```bash
.venv/bin/python scripts/snapshot_lan_hot_path_latency_harness.py logs/debug-trace-20260702-193152.jsonl
timeout 10s git diff --check
git status --short
```

Results are recorded in the final agent report.
