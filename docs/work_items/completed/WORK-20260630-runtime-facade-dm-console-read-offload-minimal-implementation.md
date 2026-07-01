# WORK-20260630-runtime-facade-dm-console-read-offload-minimal-implementation

Status: Completed

## Goal

Implement the minimal route-read offload selected by `WORK-20260630-runtime-facade-route-read-offload-decision`.

Only the synchronous `ServerRuntimeFacade.read_snapshot(dm_console)` call inside `GET /api/dm/combat` was offloaded so the async route does not directly block the event loop while building DM-console snapshots.

## Files Changed

- `dnd_initative_tracker.py`
- `tests/test_server_runtime.py`
- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-dm-console-read-offload-minimal-implementation.md`

Removed the active work item copy after completion:

- `docs/work_items/active/WORK-20260630-runtime-facade-dm-console-read-offload-minimal-implementation.md`

## Implementation Summary

Added a narrow helper:

- `_dm_combat_read_snapshot_in_threadpool(runtime, snap_req)`

The helper lazily imports Starlette's `run_in_threadpool` and calls:

```python
await run_in_threadpool(runtime.read_snapshot, snap_req)
```

`GET /api/dm/combat` now:

- Keeps DM auth before offload.
- Keeps DM service availability checks before offload.
- Builds `RuntimeSnapshotRequest(snapshot_type="dm_console", params={"include_tactical": ...})` before offload.
- Offloads only the existing `self._runtime.read_snapshot(snap_req)` call.
- Preserves successful responses by returning `result.data`.
- Preserves `runtime_not_ready` to HTTP 503.
- Preserves other unsuccessful results and worker exceptions as generic HTTP 500.

## Follow-up 01 Smoke Triage

Developer smoke after the initial offload preserved health/readiness responsiveness, but repeated harness polling caused `/api/dm/combat?workspace=dmcontrol` to time out in 17 of 32 samples with a 2-second client timeout.

Root-cause hypothesis:

- Route-side offload moved slow tactical workspace reads out of the event loop, but also allowed overlapping `_dm_console_snapshot()` / `_dm_tactical_snapshot()` / `_lan_snapshot()` builds that the previous direct event-loop path effectively serialized.
- The mode-aware DM-console cache can still be reused, but overlapping tactical builders can miss the reuse opportunity and stampede the slow legacy snapshot chain.

Narrow follow-up fix:

- Added a route-helper-local tactical read serialization gate.
- `_dm_combat_read_snapshot_in_threadpool()` still offloads `runtime.read_snapshot(snap_req)` through Starlette `run_in_threadpool`.
- Only `dm_console` requests with `params["include_tactical"]` truthy take the serialization gate.
- Plain `/api/dm/combat` non-tactical reads continue to offload without the tactical gate, avoiding a new harness regression where the plain combat endpoint queues behind workspace reads.
- No cache TTL, cache ownership, cache metadata, snapshot schema, route payload, lower-level snapshot builder, queue, LAN, Tk, WebSocket, gameplay, launcher, deploy, or production-topology behavior was changed.

## Preserved Behavior

No changes were made to:

- `ServerRuntimeFacade.read_snapshot()` synchrony or contract.
- `_dm_console_snapshot()`.
- `_dm_console_snapshot_payload()`.
- `_dm_tactical_snapshot()`.
- `_lan_snapshot()`.
- Snapshot schemas or response payloads.
- Cache ownership, TTL, invalidation, or metadata.
- Queue behavior.
- LAN controller behavior outside the single route read.
- Tk, WebSocket, gameplay, combat, launcher, deploy, or production topology behavior.

## Tests Added

Focused coverage in `tests/test_server_runtime.py` now verifies:

- `GET /api/dm/combat` read behavior uses the route-local offload helper and the runtime read executes off the route thread.
- The route still builds `RuntimeSnapshotRequest(snapshot_type="dm_console")`.
- `include_tactical=True` is passed explicitly for `workspace=dmcontrol`.
- `include_tactical=False` is preserved for the plain route.
- Auth and DM service checks happen before offload.
- `runtime_not_ready` still maps to HTTP 503.
- Other snapshot failures still map to HTTP 500.
- Worker exceptions still map to HTTP 500.
- Concurrent tactical offloads do not enter `runtime.read_snapshot()` concurrently.

## Validation

Commands run:

- `timeout 10s .venv/bin/python -m py_compile dnd_initative_tracker.py tests/test_server_runtime.py`
- `timeout 30s .venv/bin/python -m pytest tests/test_server_runtime.py -q`
- `timeout 10s git diff --check`
- `git status --short`

Results:

- `py_compile` passed with no output.
- `pytest` passed: `74 passed, 29 subtests passed in 2.33s`.
- `git diff --check` passed with no output.
- `git status --short` showed the expected modified implementation/test/ledger files, the new completed work item doc, and known unrelated untracked baseline dirt under `docs/bug_reports/inbox/BUG-20260626-dmcontrol-terrain-not-visible.md` and `logs/context/`.

## Next Safe Action

Rerun bounded developer smoke/evidence for:

- `GET /api/dm/combat`
- `GET /api/dm/combat?workspace=dmcontrol`
- `scripts/server_responsiveness_harness.py` against an already-running headless server during heavier DM read-model activity

Do not proceed to global read offload, facade-owned cache, TTL changes, static hydration, route migration, player-command routes, combat mutation routes, lower-level snapshot offload, Tk/main-thread marshalling, queue behavior changes, or high-risk gameplay route work without a new active work item.

## Developer smoke follow-up — 2026-07-01

Evidence status: passed.

Evidence files:
- Harness JSONL: `logs/smoke/WORK-20260630-runtime-facade-server-responsiveness-evidence-harness_20260701-123121.jsonl`
- Smoke server log: `logs/smoke/WORK-20260630-runtime-facade-dm-console-read-offload-minimal-implementation_smoke-server_20260701-122906.log`
- Debug trace: `logs/debug-trace-20260701-122906.jsonl`

Direct route checks:
- `/api/dm/combat`: HTTP 200 in 0.025270s.
- `/api/dm/combat?workspace=dmcontrol`: HTTP 200 in 0.888537s.

Harness summary:
- `/health`: 120 samples, 0 failures, HTTP 200 for all samples, p50 9.164 ms, p95 27.914 ms, max 43.049 ms.
- `/api/health`: 120 samples, 0 failures, HTTP 200 for all samples, p50 9.631 ms, p95 27.878 ms, max 42.897 ms.
- `/ready`: 120 samples, 0 failures, HTTP 200 for all samples, p50 9.475 ms, p95 28.769 ms, max 43.147 ms.
- `/api/ready`: 120 samples, 0 failures, HTTP 200 for all samples, p50 10.023 ms, p95 28.494 ms, max 42.996 ms.
- `/api/dm/combat`: 120 samples, 0 failures, HTTP 200 for all samples, p50 12.063 ms, p95 30.410 ms, max 45.908 ms.
- `/api/dm/combat?workspace=dmcontrol`: 120 samples, 0 failures, HTTP 200 for all samples, p50 12.725 ms, p95 790.840 ms, max 1092.869 ms.

Conclusion:
- The route-local offload plus tactical read serialization passed bounded developer smoke.
- Health/readiness and non-tactical combat remained responsive.
- Tactical workspace reads can still be slower than plain reads, but the previous repeated timeout pattern was resolved.
- No cache TTL/ownership/schema, lower-level snapshot builder, queue, LAN, Tk, WebSocket, gameplay, deploy, or production behavior changed.
