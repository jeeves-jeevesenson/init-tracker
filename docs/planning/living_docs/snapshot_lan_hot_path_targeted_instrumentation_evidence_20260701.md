# Snapshot/LAN Hot-Path Targeted Instrumentation Evidence - 2026-07-01

## Status

Targeted instrumentation/evidence slice completed. This document does not authorize latency optimization or any app behavior change.

## What Changed

The snapshot/LAN hot path now has additive debug-trace attribution at existing snapshot seams.

Caller/context attribution:

- `_lan_snapshot` accepts an optional trace-only `scope`.
- DM console route reads label facade requests as `dm_console_route` or `dm_console_route_tactical`.
- DM WebSocket snapshots label `dm_ws_connect` and `dm_ws_subscribe_map`.
- LAN startup, idle cache refresh, polling update, force-state broadcast, planning snapshot, AoE tactical lookup, and DM broadcast snapshot builds use fixed internal scope labels.
- `ServerRuntimeFacade.read_snapshot()` passes only whitelisted private `_trace_context` labels to the legacy snapshot builders.

Subcomponent spans:

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

Aggregate counters:

- combatants, players, monsters
- map AoEs
- pending prompts and pending reactions
- LAN WebSocket clients, DM WebSocket clients, and total WebSocket clients

## Harness Behavior

The latency harness now summarizes the new span names and prints a caller/context breakdown when new labels are present.

Old traces remain parse-compatible. They predate the new labels, so they can only prove the harness still handles prior evidence; they cannot prove the new attribution works in a live run.

## Decision

No latency fix is selected.

The next evidence gap is a developer-run smoke trace with this instrumentation enabled. That trace should be summarized by the updated harness before choosing any implementation lane.

## Explicitly Deferred

- cache ownership changes
- TTL changes
- snapshot schema or response payload changes
- static hydration changes
- route registration or route body movement
- broader offload or lower-level LAN/tactical offload
- WebSocket, queue, auth, claims, reconnect, launch, readiness, shutdown, production, persistence, or gameplay changes
- patching the small controlled-smoke bug

## Recommended Next Work

`WORK-20260701-snapshot-lan-hot-path-targeted-smoke-evidence-capture`

The next item should capture a fresh developer-run debug trace using the new labels and run the updated harness against it. Implementation remains deferred until that evidence identifies a specific safe lever.
