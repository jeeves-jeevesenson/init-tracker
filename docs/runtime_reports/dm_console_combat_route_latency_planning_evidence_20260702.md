# DM Console Combat Route Latency Planning Evidence - 2026-07-02

## Scope

This runtime report records a bounded docs/evidence planning checkpoint using already captured smoke and debug-trace evidence from commit `d16a2aa`.

No app code, tests, logs, browser assets, production configuration, routes, payloads, cache behavior, WebSocket behavior, queue behavior, launch/readiness/shutdown behavior, production topology, deploy, restart, SSH, push, commit, persistence, startup static-fields behavior, resource-pools behavior, small smoke bug behavior, or gameplay behavior changed.

## Evidence Files

- Smoke log: `logs/smoke/WORK-20260702-snapshot-lan-resource-pools-ttl-rebuild-smoke-evidence-capture_smoke-server_20260702-193152.log`
- Debug trace: `logs/debug-trace-20260702-193152.jsonl`

## Smoke Facts

The smoke log records:

- Headless tracker started.
- Debug trace was created.
- DM operator surface advertised on `/dm`.
- Player LAN surface advertised on `/`.
- LAN server hoisted on port `8787`.
- Browser LAN session connected from `10.3.25.162`.
- LAN session claimed Dorian.
- The captured smoke tail does not show an unclaim or disconnect before `Ctrl+C`.

This proves the accepted post-implementation run did not break the captured startup/LAN claim path. It does not claim broader gameplay, unclaim, disconnect, or browser-smoke coverage.

## Harness Summary

Harness command:

```bash
.venv/bin/python scripts/snapshot_lan_hot_path_latency_harness.py logs/debug-trace-20260702-193152.jsonl
```

Input parse result from the prior smoke evidence:

- valid JSON objects: `57,592`
- malformed/non-object lines: `0`

Key latency rows:

| Target | Count | p50 | p95 | Max | Decision |
| --- | ---: | ---: | ---: | ---: | --- |
| `lan.snapshot.resource_pools` | `359` | `0.309 ms` | `137.346 ms` | `1006.718 ms` | Improved materially; keep `d16a2aa` and do not reopen resource-pools. |
| `dm.console.combat_snapshot` | `54` | `839.307 ms` | `2038.109 ms` | `2204.090 ms` | Primary visible slow read-model span. |
| `_dm_console_snapshot_payload` | `56` | `901.847 ms` | `2089.417 ms` | `2317.861 ms` | Wrapper around combat snapshot plus optional tactical/pending prompt work. |
| `_dm_console_snapshot` | `51` | `854.435 ms` | `2103.137 ms` | `2319.635 ms` | Wrapper around payload after cache check. |
| `http.request:/api/dm/combat` | `30` | `1003.165 ms` | `3454.867 ms` | `4262.795 ms` | Route-visible symptom including response serialization/scheduling. |
| `dm.tactical.from_lan_snapshot` | `32` | `0.108 ms` | `22.713 ms` | `37.688 ms` | Not the primary lane. |
| `lan.snapshot.units` | `359` | `41.883 ms` | `47.763 ms` | `89.288 ms` | Visible but bounded. |

The caller/context rows show steady-state samples with `212` combatants, `10` players, and `202` monsters.

## Route/Read Seam Evidence

Narrow code-seam inspection showed:

- `GET /api/dm/combat` uses `RuntimeSnapshotRequest(snapshot_type="dm_console")` and offloads `runtime.read_snapshot()` through `_dm_combat_read_snapshot_in_threadpool()`.
- Tactical DM combat reads are serialized only when `include_tactical` is true.
- `ServerRuntimeFacade.read_snapshot()` validates the snapshot request, resolves `include_tactical`, forwards supported `_trace_context`, and calls `lan_controller._dm_console_snapshot(...)`.
- `_dm_console_snapshot()` only performs the existing short one-shot cache check before delegating to `_dm_console_snapshot_payload()`.
- `_dm_console_snapshot_payload()` records `dm.console.combat_snapshot` around `dm_service.combat_snapshot()`, then optionally records tactical snapshot work and merges pending prompts.
- `_dm_tactical_snapshot()` builds from `_lan_snapshot(include_static=False, hydrate_static=False)` and then runs the small `dm.tactical.from_lan_snapshot` extraction span.

## Decision

Keep commit `d16a2aa`.

Do not authorize another resource-pools implementation.

Do not authorize direct DM console combat read-model optimization yet.

The next safe work item is:

`WORK-20260702-dm-console-combat-read-model-targeted-instrumentation-evidence`

Type: targeted attribution/evidence.

Purpose: split the currently opaque `dm_service.combat_snapshot()` body and route-visible response cost enough to identify a later behavior-preserving implementation seam.

## Deferred

Remain deferred until explicitly authorized by a new active work item:

- direct read-model optimization
- startup static-fields implementation
- resource-pools behavior or cache behavior changes
- cache ownership or cache TTL changes
- snapshot schema or response payload changes
- route registration or route body movement
- broader offload or facade-owned cache
- WebSocket, queue, auth, claims, reconnect, command, persistence, production, or gameplay changes
- server start, browser smoke, deploy, restart, SSH, push, commit, or topology changes
- patching the small smoke bug
