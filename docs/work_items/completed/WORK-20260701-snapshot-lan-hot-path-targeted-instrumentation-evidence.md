# WORK-20260701-snapshot-lan-hot-path-targeted-instrumentation-evidence

Status: Completed

## Goal

Add narrow debug-trace attribution around the snapshot/LAN hot path so future latency decisions can identify caller and subcomponent causes.

This was a Codex targeted instrumentation/evidence slice only. It did not optimize latency, change app behavior, deploy, start the server, run browser smoke, commit, push, SSH, restart services, alter production topology, or patch the small controlled-smoke bug.

## Files Inspected

- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260701-snapshot-lan-hot-path-latency-planning-checkpoint.md`
- `docs/runtime_reports/snapshot_lan_hot_path_controlled_evidence_20260701.md`
- `docs/planning/living_docs/snapshot_lan_hot_path_latency_planning_checkpoint_20260701.md`
- `docs/work_items/completed/WORK-20260701-snapshot-lan-hot-path-controlled-evidence-checkpoint.md`
- `docs/work_items/completed/WORK-20260701-snapshot-lan-hot-path-latency-measurement-harness.md`
- `docs/runtime_reports/snapshot_lan_hot_path_latency_measurement_20260701.md`
- `scripts/snapshot_lan_hot_path_latency_harness.py`
- `dnd_initative_tracker.py`, limited to `_lan_snapshot`, `_dm_tactical_snapshot`, `_dm_console_snapshot`, `_dm_console_snapshot_payload`, direct snapshot caller/callee seams, and existing trace helper usage at those seams
- `server_runtime.py`, limited to `ServerRuntimeFacade.read_snapshot` and snapshot contract seams
- `runtime_config.py`, limited to existing `debug_event`, `timed_span`, `trace_timed`, and context helper behavior
- `tests/test_server_runtime.py`, limited to focused validation/test-double compatibility checks for the facade snapshot seams

No `majorTODO.md`, old plans, unrelated runtime reports, browser assets, production files, smoke logs, debug traces, `docs/bug_reports/inbox/BUG-20260626-dmcontrol-terrain-not-visible.md`, or `logs/context/` files were inspected or edited.

## Files Changed

- `dnd_initative_tracker.py`
- `server_runtime.py`
- `scripts/snapshot_lan_hot_path_latency_harness.py`
- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260701-snapshot-lan-hot-path-targeted-instrumentation-evidence.md`
- `docs/planning/living_docs/snapshot_lan_hot_path_targeted_instrumentation_evidence_20260701.md`
- `docs/runtime_reports/snapshot_lan_hot_path_targeted_instrumentation_evidence_20260701.md`

No active work item copy was left after completion.

## Instrumentation Added

Added low-cardinality caller/context labels through the snapshot path:

- `_lan_snapshot(..., scope=...)` now accepts an optional internal trace-only scope.
- `ServerRuntimeFacade.read_snapshot()` consumes private `_trace_context` request params for supported facade read contexts and passes them to the legacy snapshot builder only as `scope`.
- `GET /api/dm/combat` now labels facade snapshot reads as `dm_console_route` or `dm_console_route_tactical`.
- DM WebSocket initial and subscribe-map snapshots are labeled `dm_ws_connect` and `dm_ws_subscribe_map`.
- LAN startup, idle-cache, polling update, force-state broadcast, planning snapshot, AoE-entry tactical reads, and DM broadcast snapshot builds have fixed internal scope labels.

Added broad debug spans:

- `dm.console.combat_snapshot`
- `dm.console.tactical_snapshot`
- `dm.tactical.from_lan_snapshot`
- `lan.snapshot.map_window`
- `lan.snapshot.canonical_map`
- `lan.snapshot.aoes`
- `lan.snapshot.auras`
- `lan.snapshot.units`
- `lan.snapshot.tactical_payload`
- `lan.snapshot.static_fields`
- `lan.snapshot.resource_pools`

Extended aggregate trace counts:

- `combatant_count`
- `player_count`
- `monster_count`
- `map_aoe_count`
- `pending_prompt_count`
- `pending_reaction_count`
- `websocket_client_count`
- `dm_websocket_client_count`
- `total_websocket_client_count`

The instrumentation does not log player names, secrets, full payloads, or large data structures.

## Harness Update

`scripts/snapshot_lan_hot_path_latency_harness.py` now includes the new span names in its target table and adds a caller/context breakdown when trace records contain `scope` or `snapshot_caller`.

The harness still accepts existing traces that do not contain the new labels. Those traces should show zero-count rows for new spans and a clear `No caller/context labels found in these traces.` message.

## Evidence Decision

Instrumentation is added, but no latency fix is selected.

Existing traces can only prove backward-compatible parsing because they were captured before these labels existed. A developer-run targeted smoke trace with the new instrumentation is still required before choosing any cache, offload, schema, payload, route, WebSocket, queue, or gameplay implementation.

## Preserved Behavior

No routes, route registration, route bodies, response payloads, snapshot schemas, cache ownership, cache TTLs, static hydration behavior, WebSocket behavior, queue behavior, command semantics, auth/claims/reconnect behavior, launch commands, lifespan/readiness/shutdown behavior, `UvicornServerHost`, persistence, production topology, deploy/restart/SSH behavior, or gameplay behavior were intentionally changed.

The small smoke bug was not patched.

## Recommended Next Work

Recommended next work item:

`WORK-20260701-snapshot-lan-hot-path-targeted-smoke-evidence-capture`

Recommended goal:

Run a developer-owned targeted smoke/evidence capture with debug trace enabled, then run the updated harness against the new trace to decide whether any implementation lane is justified. The next item should still be evidence-only unless the new labels isolate a specific safe implementation lever.

## Ledger Update

`docs/work_items/current_work.md` was returned to Idle with no active work item.

The completed table now includes this instrumentation/evidence item. The allowed next action is developer-run targeted smoke/evidence capture with the new instrumentation, deploy-prep review if still desired, pause/no further migration, or a separate deferred bug-capture item if the small smoke bug remains relevant.

`majorTODO.md` was not inspected or updated because it was outside this task's allowed edit list.

## Validation

Required validation commands:

```bash
.venv/bin/python -m py_compile dnd_initative_tracker.py server_runtime.py scripts/snapshot_lan_hot_path_latency_harness.py
.venv/bin/python scripts/snapshot_lan_hot_path_latency_harness.py logs/debug-trace-20260701-191158.jsonl
timeout 90s .venv/bin/python -m pytest tests/test_server_runtime.py
timeout 10s git diff --check
git status --short
```

Results are recorded in the final agent report.
