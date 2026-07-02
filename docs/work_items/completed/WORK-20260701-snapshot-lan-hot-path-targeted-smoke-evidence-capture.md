# WORK-20260701-snapshot-lan-hot-path-targeted-smoke-evidence-capture

Status: Completed

## Goal

Complete a bounded Codex docs/evidence checkpoint using the new snapshot/LAN trace attribution from commit `f16dc71`.

This checkpoint decided what the targeted smoke proves, what the new attribution isolates, and what the next safe work item should be. It did not implement a fix, optimize latency, edit app code, edit tests, edit logs, start the server, run browser smoke, deploy, restart services, SSH, push, commit, alter production topology, patch the small smoke bug, or change route registration, route bodies, launch commands, lifespan/readiness/shutdown behavior, `UvicornServerHost`, snapshot warm-up, cache ownership, cache TTLs, snapshot schemas, response payloads, static hydration, WebSockets, auth/claims/reconnect, queue behavior, command semantics, persistence, or gameplay behavior.

## Files Inspected

- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260701-snapshot-lan-hot-path-targeted-instrumentation-evidence.md`
- `docs/planning/living_docs/snapshot_lan_hot_path_targeted_instrumentation_evidence_20260701.md`
- `docs/runtime_reports/snapshot_lan_hot_path_targeted_instrumentation_evidence_20260701.md`
- `docs/work_items/completed/WORK-20260701-snapshot-lan-hot-path-latency-planning-checkpoint.md`
- `docs/planning/living_docs/snapshot_lan_hot_path_latency_planning_checkpoint_20260701.md`
- `logs/smoke/WORK-20260701-snapshot-lan-hot-path-targeted-smoke-evidence-capture_smoke-server_20260702-090629.log`, using `head` and `tail`
- `logs/debug-trace-20260702-090629.jsonl`, using `head` and `grep`
- `scripts/snapshot_lan_hot_path_latency_harness.py`

No `majorTODO.md`, old plans, unrelated runtime reports, unrelated logs, browser assets, app code, tests, production files, `docs/bug_reports/inbox/BUG-20260626-dmcontrol-terrain-not-visible.md`, or `logs/context/` files were inspected or edited.

## Files Changed

- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260701-snapshot-lan-hot-path-targeted-smoke-evidence-capture.md`
- `docs/planning/living_docs/snapshot_lan_hot_path_targeted_smoke_evidence_capture_20260702.md`
- `docs/runtime_reports/snapshot_lan_hot_path_targeted_smoke_evidence_20260702.md`

No active work item copy was left after completion.

## Smoke Evidence Decision

The targeted smoke proves the basic headless/browser/LAN surface path still works for this run:

- Headless tracker started.
- Debug trace was created at `logs/debug-trace-20260702-090629.jsonl`.
- DM operator surface was advertised on `/dm`.
- Player LAN surface was advertised on `/`.
- LAN server was hoisted on port `8787`.
- Browser LAN sessions connected.
- The pasted smoke tail shows one LAN session disconnected.

The pasted smoke tail does not show claim/unclaim events for this run, so this checkpoint does not claim fresh claim/unclaim coverage.

## Latency Evidence Decision

The harness parsed `18,136` valid JSON objects with `0` malformed/non-object lines.

Key harness rows:

- `_lan_snapshot`: count `491`, p50 `5.428 ms`, p95 `813.985 ms`, max `25896.642 ms`, `140` samples at or above `250 ms`, `10` at or above `1000 ms`.
- `lan.snapshot.resource_pools`: count `491`, p50 `0.087 ms`, p95 `785.645 ms`, max `2823.251 ms`, `140` samples at or above `250 ms`, `9` at or above `1000 ms`.
- `lan.snapshot.static_fields`: count `491`, p50 `0.089 ms`, p95 `0.215 ms`, max `25435.836 ms`.
- `dm.tactical.from_lan_snapshot`: count `48`, p50 `0.082 ms`, p95 `0.188 ms`, max `0.815 ms`.
- `dm.console.combat_snapshot`: count `68`, p50 `30.868 ms`, p95 `62.909 ms`, max `199.749 ms`.
- `http.request:/api/dm/combat`: count `48`, p50 `69.298 ms`, p95 `1175.067 ms`, max `1258.921 ms`.

The new attribution isolates repeated slow `_lan_snapshot` samples under `lan_tick_update`, `dm_console_route_tactical`, `lan_force_state_broadcast`, and `lan_startup_seed` contexts. The most actionable recurring substep appears to be `lan.snapshot.resource_pools`: its slow count matches `_lan_snapshot` at the `>=250 ms` threshold and accounts for most of the p95 and very-slow behavior.

The large `lan.snapshot.static_fields` max appears tied to the `lan_startup_seed` startup static include path, not steady-state LAN snapshot latency. Startup static-fields behavior should be separated from the steady-state resource-pools lane.

## Answers

1. The targeted smoke proves headless startup, debug-trace creation, `/dm` and `/` advertisement, LAN hoist on port `8787`, and browser LAN WebSocket connection/disconnect behavior still work for this run.
2. The new instrumentation isolates the recurring steady-state slow path to `_lan_snapshot` subspans and points most strongly at `lan.snapshot.resource_pools`, with caller/context coverage across LAN tick update, tactical DM console route reads, force-state broadcast, and startup seed.
3. `lan.snapshot.resource_pools` is isolated enough for a narrow planning/implementation-decision checkpoint. It is not yet enough for direct implementation because the next pass still needs to decide the safe lever and protect payload/cache/schema/gameplay behavior.
4. Startup-only `lan.snapshot.static_fields` behavior should be separated from steady-state LAN snapshot latency.
5. Direct implementation is not justified from this checkpoint. The next work item should be a resource-pools latency planning checkpoint.
6. Recommended next work item: `WORK-20260702-snapshot-lan-resource-pools-latency-planning-checkpoint`.
7. Direct latency implementation, resource-pools implementation, startup static-fields implementation, cache ownership moves, TTL changes, static hydration changes, snapshot schema or response payload changes, route registration or route body movement, broader offload, facade-owned cache, WebSocket/queue/auth/claims/reconnect changes, launch/lifespan/readiness/shutdown changes, production operations, persistence changes, and gameplay behavior changes remain forbidden until a new active work item explicitly authorizes them.
8. The small smoke bug should stay deferred as separate bug-capture scope. It was not patched here.

## Recommended Next Work

Recommended next work item:

`WORK-20260702-snapshot-lan-resource-pools-latency-planning-checkpoint`

Recommended type:

Docs/planning implementation-decision checkpoint, not implementation.

Recommended goal:

Use the targeted smoke evidence and minimal focused code inspection, if authorized by that new item, to decide whether `lan.snapshot.resource_pools` has a safe narrow implementation lever. The checkpoint should explicitly separate steady-state resource-pool latency from startup static-fields behavior and should preserve all payload, schema, cache, route, WebSocket, queue, auth, persistence, production, and gameplay behavior.

## Deferred Scope

Remain forbidden until a new active work item authorizes the specific change:

- app-code implementation
- tests changes
- log edits
- server start, browser smoke, deploy, restart, SSH, push, commit, or production topology changes
- route registration changes or route body movement
- launch command, lifespan, readiness, shutdown, or `UvicornServerHost` changes
- snapshot warm-up ownership, cache ownership, cache TTL, static hydration, snapshot schema, or response payload changes
- WebSocket, auth, claims, reconnect, queue, command semantic, persistence, or gameplay changes
- broader `run_in_threadpool` adoption
- moving cache ownership into `ServerRuntimeFacade`
- patching the small smoke bug inside the latency lane

## Ledger Update

`docs/work_items/current_work.md` was returned to Idle with no active work item.

The completed table now includes this targeted-smoke evidence capture. The allowed next action is a resource-pools latency planning/implementation-decision checkpoint, deploy-prep review if still desired, pause/no further migration, or a separate deferred bug-capture item for the small smoke bug.

`majorTODO.md` was not inspected or updated because it was outside this task's allowed edit list.

## Validation

Required validation commands:

```bash
.venv/bin/python scripts/snapshot_lan_hot_path_latency_harness.py logs/debug-trace-20260702-090629.jsonl
timeout 10s git diff --check
git status --short
```

Results are recorded in the final agent report.
