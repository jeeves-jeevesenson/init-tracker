# Snapshot/LAN Hot-Path Controlled Evidence Checkpoint - 2026-07-01

## Status

Checkpoint/evidence document only. This document does not authorize app implementation, test edits, log edits, route registration changes, route body movement, launch command changes, lifespan behavior changes, readiness behavior changes, Uvicorn host changes, snapshot warm-up changes, cache ownership changes, TTL changes, snapshot schema changes, response payload changes, static hydration changes, WebSocket behavior changes, queue behavior changes, command semantic changes, production operations, deploys, commits, pushes, SSH, service restarts, topology changes, optimization, or gameplay behavior changes.

## Decision Summary

The controlled smoke evidence confirms that the basic host/browser/LAN path still works:

- Headless tracker startup and debug trace creation worked.
- `/dm` and `/` were advertised.
- LAN hoisted on port `8787`.
- A browser LAN session connected.
- Claim/unclaim flows were logged for Dorian, Old Man, Johnny Morris, Throat Goat, and John Twilight.
- John Twilight attack weapon resolution was logged.
- The developer reported the controlled smoke passed.

The latency evidence is strong enough to justify a snapshot/LAN latency planning/design checkpoint. It is not isolated enough for direct implementation.

Recommended next work item, if latency work continues:

`WORK-20260701-snapshot-lan-hot-path-latency-planning-checkpoint`

Deferred bug capture remains separate. The small smoke bug was not patched and should be captured separately later if still relevant.

## Harness Evidence

Command:

```bash
.venv/bin/python scripts/snapshot_lan_hot_path_latency_harness.py logs/debug-trace-20260701-191158.jsonl
```

Controlled trace summary:

- `_lan_snapshot`: `1075` samples, p50 `98.260 ms`, p95 `1220.955 ms`, max `24704.439 ms`, `435` samples at or above `250 ms`, `80` at or above `1000 ms`.
- `_dm_tactical_snapshot`: `55` samples, p50 `1197.004 ms`, p95 `2313.119 ms`, max `2536.769 ms`.
- `_dm_console_snapshot`: `79` samples, p50 `1212.072 ms`, p95 `2376.749 ms`, max `2638.671 ms`.
- `_dm_console_snapshot_payload`: `99` samples, p50 `323.099 ms`, p95 `2224.006 ms`, max `2638.226 ms`.
- `lan.snapshot.build`: `31` samples, p50 `426.811 ms`, p95 `1433.860 ms`, max `2037.209 ms`.
- `http.request:/api/dm/combat`: `53` samples, p50 `1326.809 ms`, p95 `2858.221 ms`, max `2941.737 ms`.
- Malformed or non-object JSONL lines: `0`.

The controlled run therefore confirms repeated route-visible latency and repeated lower-level snapshot latency. It is not only a startup artifact or a single diagnostic line.

## What Remains Ambiguous

The controlled evidence does not yet isolate:

- how much of the route latency is caused by `_lan_snapshot` versus DM-console/tactical wrapper work
- how much of `_lan_snapshot` is `lan.snapshot.build` versus other snapshot/cache/broadcast-adjacent work
- whether startup-era outliers should be handled separately from steady-state play latency
- whether cache hits, cache misses, invalidation domains, static/dynamic rebuilds, or LAN broadcast timing dominate
- whether health/readiness responsiveness stays acceptable during the slow windows in this controlled run
- whether the safest intervention is planning-only, targeted instrumentation, cache/read-model work, route-local behavior, or no implementation
- whether the small observed smoke bug is related to latency or should remain an unrelated bug

These ambiguities are design/planning inputs, not permission to patch app code immediately.

## Decision Questions

What did the controlled smoke prove still works?

The controlled smoke proved the headless tracker can start, create the debug trace, advertise DM/player browser surfaces, hoist LAN on port `8787`, accept a browser LAN connection, perform claim/unclaim flows across the named characters, and resolve John Twilight attack weapons during the run. This supports continued host/browser/LAN confidence for the tested path.

What latency evidence was confirmed?

The controlled harness confirmed repeated material latency in `_lan_snapshot`, `_dm_tactical_snapshot`, `_dm_console_snapshot`, `_dm_console_snapshot_payload`, `lan.snapshot.build`, and `/api/dm/combat`, with zero malformed/non-object trace lines.

Is the latency isolated enough for implementation?

No. It is isolated enough to justify a planning/design checkpoint, but not implementation. The trace confirms a real hot path and route-visible latency, but not the smallest safe implementation lever.

Should the next lane be planning, targeted instrumentation, deferred bug capture, or no further work?

Use snapshot/LAN latency planning if latency work continues. Targeted instrumentation may be the output of that planning checkpoint, but should not be started before the planning checkpoint authorizes it. Deferred bug capture should be separate and only become next if the small smoke bug is more urgent. No further work is acceptable only if deploy-prep review or pause is preferred.

What exact next work item should be recommended?

`WORK-20260701-snapshot-lan-hot-path-latency-planning-checkpoint`

Recommended goal:

Use the controlled evidence to map hot-path ownership and select one of three outcomes: a narrow implementation candidate, a targeted instrumentation-only task, or no latency work for now. Preserve all behavior until a later authorized implementation item exists.

What must remain forbidden until planning authorizes implementation?

Direct latency implementation, targeted app instrumentation, cache ownership moves, TTL changes, snapshot schema changes, response payload changes, static hydration changes, snapshot warm-up changes, broader offload, route movement, WebSocket/auth/claims/reconnect changes, queue behavior changes, launch/readiness/shutdown changes, gameplay changes, production operations, and patching the small smoke bug inside the latency lane all remain forbidden.

## Next-Lane Shape

The next planning checkpoint should be narrow. It may inspect a minimal named set of app files only to map ownership and select the next safe lane. It should not edit app code.

Candidate outcomes from that planning checkpoint:

- a narrow implementation item, if the evidence and code ownership map identify a safe lever
- targeted instrumentation only, if the controlled evidence still lacks subcomponent attribution
- no latency implementation for now, if the risk is accepted or deploy-prep review is higher priority

Do not use this checkpoint to skip planning and start cache/offload/schema/route work.
