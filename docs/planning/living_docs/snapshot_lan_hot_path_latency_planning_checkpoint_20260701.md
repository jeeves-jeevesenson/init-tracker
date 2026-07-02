# Snapshot/LAN Hot-Path Latency Planning Checkpoint - 2026-07-01

## Status

Docs/planning checkpoint only. This document does not authorize app implementation, optimization, tests, log edits, route registration changes, route body movement, cache ownership changes, TTL changes, snapshot schema changes, response payload changes, static hydration changes, WebSocket behavior changes, queue behavior changes, command semantic changes, auth/claims/reconnect changes, launch/readiness/shutdown changes, `UvicornServerHost` changes, production operations, deploys, commits, pushes, SSH, service restarts, topology changes, or gameplay changes.

## Decision Summary

The current evidence supports a targeted instrumentation evidence slice as the next safe lane.

It does not support direct latency implementation. The traces show repeated and material latency in `_lan_snapshot`, `_dm_tactical_snapshot`, `_dm_console_snapshot`, `_dm_console_snapshot_payload`, `lan.snapshot.build`, and `/api/dm/combat`, but they do not isolate whether the dominant cause is repeated calls, expensive internal `_lan_snapshot` work, broadcast-context building, tactical workspace polling, cache/static hydration adjacency, or caller overlap.

Recommended next work item:

`WORK-20260701-snapshot-lan-hot-path-targeted-instrumentation-evidence`

Recommended goal:

Add narrow additive trace instrumentation to attribute snapshot/LAN hot-path latency by caller context and `_lan_snapshot` subcomponent, then capture and summarize bounded evidence with the existing harness. Do not change behavior.

## Evidence Facts

The first harness report from `logs/debug-trace-20260701-155344.jsonl` found:

- `_lan_snapshot`: `2118` samples, p50 `90.765 ms`, p95 `524.684 ms`, max `25282.205 ms`, `967` samples at or above `250 ms`, `17` at or above `1000 ms`.
- `_dm_tactical_snapshot`: `177` samples, p95 `1005.679 ms`.
- `_dm_console_snapshot`: `202` samples, p95 `1020.172 ms`.
- `_dm_console_snapshot_payload`: `222` samples, p95 `1018.191 ms`.
- `lan.snapshot.build`: `25` samples, p95 `880.831 ms`.
- `/api/dm/combat`: `176` samples, p95 `1048.359 ms`.

The controlled evidence report from `logs/debug-trace-20260701-191158.jsonl` found:

- `_lan_snapshot`: `1075` samples, p50 `98.260 ms`, p95 `1220.955 ms`, max `24704.439 ms`, `435` samples at or above `250 ms`, `80` at or above `1000 ms`.
- `_dm_tactical_snapshot`: `55` samples, p50 `1197.004 ms`, p95 `2313.119 ms`.
- `_dm_console_snapshot`: `79` samples, p50 `1212.072 ms`, p95 `2376.749 ms`.
- `_dm_console_snapshot_payload`: `99` samples, p50 `323.099 ms`, p95 `2224.006 ms`.
- `lan.snapshot.build`: `31` samples, p50 `426.811 ms`, p95 `1433.860 ms`.
- `/api/dm/combat`: `53` samples, p50 `1326.809 ms`, p95 `2858.221 ms`.

Both traces were parse-clean for the harness. The controlled smoke passed by developer report and showed the host/browser/LAN path still works for the tested path.

## Planning Questions

What does the evidence say is slow, and how repeatable is it?

The repeated slow targets are `_lan_snapshot`, `_dm_tactical_snapshot`, `_dm_console_snapshot_payload`, `_dm_console_snapshot`, `lan.snapshot.build`, and `/api/dm/combat`. The signal is repeatable across two named traces, with `_lan_snapshot` showing `2118` samples in the first trace and `1075` in the controlled trace, plus p95 values of `524.684 ms` and `1220.955 ms` respectively. The controlled trace also made route-visible latency clearer, with `/api/dm/combat` p95 `2858.221 ms`.

Which spans appear to be primary bottlenecks versus nested or secondary symptoms?

`_lan_snapshot` is the primary bottleneck candidate. It is called by `_dm_tactical_snapshot(include_static=False, hydrate_static=False)` and is present in representative route-chain evidence where it accounts for nearly all of a slow tactical workspace request. `_dm_tactical_snapshot`, `_dm_console_snapshot_payload`, `_dm_console_snapshot`, and `/api/dm/combat` appear to be nested route-visible symptoms when tactical data is requested. `lan.snapshot.build` points at broadcast-side snapshot construction and may be primary for broadcast windows, but current evidence cannot separate it from `_lan_snapshot` internal work. `_load_player_yaml_cache` is not selected as primary because its p95 is sub-millisecond in both reports despite isolated max outliers.

Is the next safe lane implementation, targeted instrumentation, or a narrower design checkpoint?

The next safe lane is targeted instrumentation. A narrower design checkpoint would mostly restate the same attribution gap, and implementation is not yet justified. The future instrumentation should be additive trace evidence only, focused on caller context and internal `_lan_snapshot` substeps.

If implementation is not yet justified, what exact evidence is still missing?

Missing evidence includes caller attribution, startup-versus-steady-state attribution, route-versus-broadcast attribution, substep timings inside `_lan_snapshot`, cache/static hydration state, invalidation domains, include flags, combatant/unit/map entity counts, WebSocket client counts, workspace polling context, and health/readiness responsiveness during slow windows.

If a future implementation lane is justified, what is the smallest safe slice?

No implementation lane is justified now. If later instrumentation proves a specific hotspot, the smallest safe implementation should be separate, legacy-owned at the proven hotspot, and limited to one caller/context or one internal `_lan_snapshot` subcomponent. It must preserve payload schemas, cache ownership, TTLs, static hydration, route behavior, WebSockets, queues, production behavior, and gameplay behavior. It must not move cache ownership into `ServerRuntimeFacade`.

What files and behaviors must be explicitly protected in the next slice?

Protect `server_runtime.py` facade behavior and snapshot contracts, `/api/dm/combat` route behavior and payload/status mapping, existing cache ownership and TTLs, static hydration and snapshot warm-up, WebSocket/claims/reconnect behavior, queue and command semantics, auth/hidden-information behavior, launch/readiness/shutdown behavior, `UvicornServerHost`, persistence, production topology, logs, and gameplay behavior.

Should the small smoke bug be captured separately now, deferred, or ignored unless it recurs?

Defer it as a separate bug-capture item unless it recurs or the developer chooses to prioritize it. It should not be ignored permanently, but it should not be patched or folded into the latency instrumentation lane.

What exact next work item should be recommended?

`WORK-20260701-snapshot-lan-hot-path-targeted-instrumentation-evidence`

## Targeted Instrumentation Shape

The future instrumentation item should be narrow and evidence-only. It should capture:

- caller context for `_lan_snapshot`, such as tactical read, LAN broadcast build, or other caller
- `_lan_snapshot` flags, including `include_static` and `hydrate_static`
- static cache hit/miss and invalidation context already available near the snapshot path
- counts for combatants, units, AoEs, structures/ships, map entities, and WebSocket clients
- bounded subspans inside `_lan_snapshot` for canonical map capture/apply, AoE normalization, active aura context, unit assembly, ship/structure projection, static component handling, and resource pools
- route context correlation for `/api/dm/combat?workspace=dmcontrol`
- whether slow windows are startup-era or steady-state

It should not change payloads, schemas, cache behavior, TTLs, route behavior, threadpool behavior, WebSocket behavior, queue behavior, production topology, or gameplay behavior.

## Deferred Scope

Deferred until stronger evidence exists:

- cache implementation or ownership moves
- TTL changes
- snapshot schema or response payload changes
- static hydration changes
- snapshot warm-up ownership changes
- route registration or route body movement
- broader `run_in_threadpool` adoption
- lower-level tactical/LAN offload
- queue-wait or async command behavior changes
- WebSocket, auth, claims, reconnect, or hidden-information changes
- launch, lifespan, readiness, shutdown, or `UvicornServerHost` changes
- production deploy, restart, SSH, push, commit, topology, persistence, or gameplay changes
