# Snapshot/LAN Resource-Pools Hot-Path Cache Smoke Evidence Capture - 2026-07-02

## Status

Docs/evidence post-implementation checkpoint completed. This document does not authorize app implementation, latency optimization, tests, log edits, route movement, payload/schema changes, cache ownership changes, cache TTL changes, static hydration changes, WebSocket changes, queue changes, production operations, deploys, restarts, SSH, pushes, commits, topology changes, or gameplay changes.

## Decision Summary

Keep the narrow legacy-owned resource-pools cache/refinement from commit `95bbdf6`.

The fresh smoke evidence proves the post-implementation build still starts headless, advertises `/dm` and `/`, hoists LAN on port `8787`, creates the debug trace, accepts browser LAN sessions, records an Eldramar claim, and records disconnect while claimed.

The new dedicated cache-hit path is fast enough to keep:

- trace tail `resource_pool_mode=dedicated_cache_hit`: about `0.081-0.097 ms`
- harness `lan.snapshot.resource_pools` p50: `0.092 ms`

The remaining steady-state slow path is still `resource_pool_mode=ttl_rebuild`:

- trace tail `resource_pool_mode=ttl_rebuild`: about `368.002-380.124 ms`
- harness `lan.snapshot.resource_pools`: count `280`, p95 `759.372 ms`, max `2836.852 ms`, `83` samples at or above `250 ms`, `2` at or above `1000 ms`
- harness `_lan_snapshot`: count `280`, p95 `842.408 ms`, `83` samples at or above `250 ms`, `3` at or above `1000 ms`

That is enough to keep the current refinement while selecting a narrow planning checkpoint for `ttl_rebuild` as the next safe lane. It is not authorization for direct additional optimization from this task.

Recommended next work item:

`WORK-20260702-snapshot-lan-resource-pools-ttl-rebuild-planning-checkpoint`

Recommended type: docs/planning implementation-decision checkpoint.

## Evidence Basis

Evidence run used:

- smoke log `logs/smoke/WORK-20260702-snapshot-lan-resource-pools-hot-path-cache-smoke-evidence-capture_smoke-server_20260702-123404.log`
- debug trace `logs/debug-trace-20260702-123404.jsonl`
- harness command `.venv/bin/python scripts/snapshot_lan_hot_path_latency_harness.py logs/debug-trace-20260702-123404.jsonl`

The earlier aborted `20260702-104233` start was intentionally excluded.

Smoke facts confirmed in the evidence run:

- headless tracker started
- debug trace created
- DM operator surface advertised on `/dm`
- player LAN surface advertised on `/`
- LAN server hoisted on port `8787`
- browser LAN sessions connected
- one LAN session claimed Eldramar
- the claimed Eldramar session later disconnected while still claimed

Harness parse result:

- `14,040` valid JSON objects
- `0` malformed/non-object lines

Supporting latency rows:

- `lan.snapshot.static_fields`: count `280`, p95 `0.264 ms`, max `24202.351 ms`
- `dm.tactical.from_lan_snapshot`: count `31`, p95 `0.252 ms`, max `0.260 ms`
- `dm.console.combat_snapshot`: count `53`, p95 `94.884 ms`, max `150.560 ms`
- `http.request:/api/dm/combat`: count `31`, p95 `1184.073 ms`, max `1280.097 ms`

The startup-only `lan.snapshot.static_fields` max remains separate from the steady-state resource-pools latency because its p95 stays low and its large max is still a `lan_startup_seed` startup artifact.

## Planning Questions

What did the post-implementation smoke prove still works?

It proved the basic post-implementation host/browser/LAN claim path still works for this run: headless startup, debug-trace creation, surface advertisement, LAN hoist, browser LAN session connection, one Eldramar claim, and disconnect while claimed.

Did the dedicated resource-pools cache/refinement improve the cache-hit path?

Yes, in the only sense this checkpoint can prove directly: when the dedicated cache-hit path is exercised, it is cheap and stable. The trace tail repeatedly shows `dedicated_cache_hit` around `0.08-0.10 ms`. This does not prove the overall trace is broadly faster because `ttl_rebuild` still dominates the slow tail.

What slow path remains after the implementation?

`resource_pool_mode=ttl_rebuild` remains the slow path inside `lan.snapshot.resource_pools`. It still accounts for the recurring slow steady-state samples that keep `_lan_snapshot` and route-visible `/api/dm/combat` latency elevated.

Is `ttl_rebuild` now isolated as the next actionable issue?

Yes, enough for a planning checkpoint. The new evidence separates cache-hit versus rebuild behavior clearly enough to focus the next lane on `ttl_rebuild` without reopening broader resource-pools attribution work.

Is the implementation good enough to keep, revert, or revise?

Keep it. The new dedicated cache-hit mode is fast, the captured smoke still shows expected basic behavior, and no evidence supports revert. Revision should be decided only after the dedicated `ttl_rebuild` planning checkpoint.

Should the next work item be planning, implementation decision, more evidence, or implementation?

Planning/implementation-decision only. More evidence is not needed to identify the remaining slow path, and this task does not authorize a follow-up implementation directly.

Should the startup-only static-fields outlier remain deferred separately?

Yes. Keep `lan.snapshot.static_fields` deferred separately because the large max remains startup-seed-specific while steady-state p95 stays low.

Should the small smoke bug remain separate?

Yes. Keep it as separate deferred bug-capture scope. Do not fold it into the `ttl_rebuild` lane.

## Deferred Scope

Remain deferred until separately authorized:

- direct `ttl_rebuild` implementation
- startup static-fields implementation
- broad snapshot/LAN optimization
- route registration changes or route body movement
- cache ownership changes
- cache TTL changes
- static hydration changes
- snapshot schema or response payload changes
- snapshot warm-up ownership changes
- WebSocket, queue, auth, claims, reconnect, command, persistence, production, or gameplay changes
- server start, browser smoke, deploy, restart, SSH, push, commit, or production topology changes
- patching the small smoke bug
