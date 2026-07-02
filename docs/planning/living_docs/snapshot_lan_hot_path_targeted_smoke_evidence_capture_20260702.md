# Snapshot/LAN Hot-Path Targeted Smoke Evidence Capture - 2026-07-02

## Status

Docs/evidence checkpoint completed. This document does not authorize app implementation, latency optimization, tests, route movement, payload/schema changes, cache changes, WebSocket changes, queue changes, production operations, deploys, restarts, SSH, pushes, commits, topology changes, or gameplay changes.

## Evidence Inputs

- Smoke log: `logs/smoke/WORK-20260701-snapshot-lan-hot-path-targeted-smoke-evidence-capture_smoke-server_20260702-090629.log`
- Debug trace: `logs/debug-trace-20260702-090629.jsonl`
- Harness: `scripts/snapshot_lan_hot_path_latency_harness.py`

The smoke log head/tail records headless startup, debug trace creation, `/dm` and `/` surface advertisement, LAN server hoist on port `8787`, two browser LAN sessions connected, and one LAN session disconnected. It does not show claim/unclaim events in the captured tail.

## Decision Summary

The new trace attribution is effective enough to narrow the next lane.

`lan.snapshot.resource_pools` is now the most actionable recurring substep. It has the same `>=250 ms` slow count as `_lan_snapshot`, nearly the same `>=1000 ms` very-slow count, and appears across steady-state and route-visible contexts rather than only startup.

`lan.snapshot.static_fields` should be handled separately. Its p95 is effectively flat at `0.215 ms`, while its max `25435.836 ms` is tied to the startup `lan_startup_seed` static include path. Combining that startup-only behavior with steady-state LAN snapshot latency would blur the next decision.

Direct implementation remains deferred. The next safe item is a planning/implementation-decision checkpoint focused on resource-pool latency, not a fix.

## Harness Facts

- Input parsed cleanly: `18,136` valid JSON objects and `0` malformed/non-object lines.
- `_lan_snapshot`: count `491`, p50 `5.428 ms`, p95 `813.985 ms`, max `25896.642 ms`, `140` samples at or above `250 ms`, `10` at or above `1000 ms`.
- `lan.snapshot.resource_pools`: count `491`, p50 `0.087 ms`, p95 `785.645 ms`, max `2823.251 ms`, `140` samples at or above `250 ms`, `9` at or above `1000 ms`.
- `lan.snapshot.static_fields`: count `491`, p50 `0.089 ms`, p95 `0.215 ms`, max `25435.836 ms`.
- `dm.tactical.from_lan_snapshot`: count `48`, p50 `0.082 ms`, p95 `0.188 ms`, max `0.815 ms`.
- `dm.console.combat_snapshot`: count `68`, p50 `30.868 ms`, p95 `62.909 ms`, max `199.749 ms`.
- `http.request:/api/dm/combat`: count `48`, p50 `69.298 ms`, p95 `1175.067 ms`, max `1258.921 ms`.

## Caller And Context Interpretation

Slow `_lan_snapshot` cases appear under:

- `lan_tick_update`
- `dm_console_route_tactical`
- `lan_force_state_broadcast`
- `lan_startup_seed`

The steady-state signal is not isolated to one route wrapper. The resource-pool subspan shows repeated rebuild/cached-mode timing spikes while other LAN subspans are mostly sub-millisecond in the inspected samples.

The DM tactical extraction span is fast in this trace, so the route-visible `/api/dm/combat` p95 is best interpreted as a symptom of nested snapshot work rather than tactical payload extraction itself.

## Planning Questions Answered

What did the targeted smoke prove still works?

It proves basic headless startup, debug trace creation, `/dm` and `/` advertisement, LAN hoist on port `8787`, and browser LAN WebSocket connection/disconnect behavior for this run. It does not prove fresh claim/unclaim behavior because the smoke tail does not show those events.

What did the new instrumentation isolate?

It isolates recurring `_lan_snapshot` latency to caller/context labels and substep spans, with `lan.snapshot.resource_pools` as the clearest recurring substep and `lan.snapshot.static_fields` as a separate startup-seed outlier.

Is `lan.snapshot.resource_pools` isolated enough for a narrow planning/implementation-decision checkpoint?

Yes. It is isolated enough to justify a focused decision pass that inspects the resource-pool construction path and selects or rejects a safe implementation slice. It is not enough to implement directly in this evidence checkpoint.

Should startup-only `static_fields` behavior be separated from steady-state LAN snapshot latency?

Yes. Its outlier profile is startup-specific, while the resource-pool profile recurs across contexts relevant to steady-state latency.

Is direct implementation justified now?

No. Direct implementation would still require choosing a behavior-preserving lever around resource-pool building, cache/static boundaries, payload shape, and startup versus steady-state semantics. That selection should be made in a separate planning/implementation-decision item.

What exact next work item should be recommended?

`WORK-20260702-snapshot-lan-resource-pools-latency-planning-checkpoint`

## Deferred Scope

Do not use this evidence checkpoint as authorization for:

- resource-pools implementation
- startup static-fields implementation
- cache ownership or TTL changes
- static hydration or snapshot warm-up changes
- schema or response payload changes
- route registration changes or route body movement
- broader offload or facade-owned cache
- WebSocket, queue, auth, claims, reconnect, persistence, production, or gameplay changes
- server start, browser smoke, deploy, restart, SSH, push, commit, or production topology changes
- patching the small smoke bug

## Recommended Next Item

`WORK-20260702-snapshot-lan-resource-pools-latency-planning-checkpoint`

Type: docs/planning implementation-decision checkpoint.

Goal: decide whether the isolated `lan.snapshot.resource_pools` evidence supports a narrow implementation work item, and if so define the smallest behavior-preserving slice. Keep startup static-fields analysis separate.
