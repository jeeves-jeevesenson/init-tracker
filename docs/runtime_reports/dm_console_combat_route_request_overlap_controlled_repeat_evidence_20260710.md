# DM Console Combat Route Request Overlap Controlled Repeat Evidence

Date: 2026-07-10 local capture date (`2026-07-11` UTC trace timestamps)

Work item: `WORK-20260708-dm-console-combat-route-request-overlap-controlled-repeat-evidence`

## Outcome

Selected lane 1: repeated write-induced stalls are confirmed. Recommend `WORK-20260710-combat-mutation-event-loop-containment-decision`, type planning/evidence only. No implementation is authorized.

## Inputs And Method

- Trace: `logs/debug-trace-20260710-223521.jsonl`
- Smoke log: `logs/smoke/WORK-20260708-dm-console-combat-route-request-overlap-controlled-repeat-evidence_smoke-server_20260710-223521.log`
- Summary harness: `scripts/snapshot_lan_hot_path_latency_harness.py`
- Dense GET window: `2026-07-11T03:51:29.943Z` through `2026-07-11T03:56:06.834Z`

The analysis streamed the trace and paired `http.request.start/end`, named span start/end records, mutation HTTP intervals, force-broadcast intervals, and DM broadcast snapshot work by timestamp and trace/action ID. All `44` GETs with an `http.request` span of at least `1,000 ms` were classified. The report uses the harness's `span.end` HTTP duration for percentile and slow-request ordering; `http.request.end` wall time is slightly larger and supplies the interval endpoints.

Percentiles use the harness's deterministic nearest-rank method. Correlation does not use similar aggregate maxima as proof.

## Verified Trace Summary

| Measure | Count | p50 | p95 | Max |
| --- | ---: | ---: | ---: | ---: |
| Valid JSON objects | 163,466 | - | - | - |
| Malformed/non-object entries | 0 | - | - | - |
| `http.request:/api/dm/combat` | 128 | 934.286 ms | 2,980.334 ms | 4,039.319 ms |
| `dm.console.route_read_snapshot` | 128 | 873.309 ms | 2,883.876 ms | 3,970.152 ms |
| `dm.console.combat_snapshot.service_call` | 159 | 783.876 ms | 1,754.951 ms | 3,400.598 ms |
| `dm.console.threadpool_dispatch_queue` | 128 | 0.305 ms | 2.326 ms | 15.882 ms |
| `dm.console.route_response_build` | 128 | 0.404 ms | 1.879 ms | 39.296 ms |

The service-call row includes route, DM broadcast, later DM snapshot, and WebSocket-connect contexts; the GET route count remains `128`. Route context reached `212` combatants: `10` players and `202` monsters. Of the GETs, `126` were tactical and `2` non-tactical.

There are `16` outer `_lan_force_state_broadcast` completions, but two are startup no-client skips. The `14` operational broadcast contexts match the reported sample count. For those contexts:

- `_lan_snapshot` max: `1,564.516 ms`;
- `lan.snapshot.resource_pools` max: `1,502.333 ms`;
- `_dm_console_snapshot_payload` with `dm_broadcast_snapshot` context: `14` samples, p50 `893.963 ms`, p95/max `1,980.109 ms`.

Three operational force broadcasts have null trace/action IDs, including the aggregate broadcast-context maxima. Those spans support only temporal correlation and were not treated as request-ID proof.

## Gap Counts

| Gap measure | Threshold | Count / 128 | Percent | Mutation overlap | Force overlap | Mutation or force overlap |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Service completion to response-build start | 100 ms | 57 | 44.531% | 10 | 8 | 12 |
| Service completion to response-build start | 250 ms | 16 | 12.500% | 9 | 8 | 11 |
| Outer snapshot completion to response-build start | 100 ms | 13 | 10.156% | 9 | 5 | 9 |
| Outer snapshot completion to response-build start | 250 ms | 11 | 8.594% | 9 | 5 | 9 |

Overlap columns are not mutually exclusive. The service gap is the requested measure but includes tactical/read-model work after the service call. The outer `_dm_console_snapshot` end is the cleaner worker-completion proxy. `dm.console.route_read_snapshot` ends only after the await resumes, so its end-to-response-build gap is normally `0-2 ms` and cannot measure the blocked-resume interval itself.

Among the `44` GETs lasting at least one second, `10` overlapped a gameplay mutation HTTP request anywhere in their lifetime and `11` overlapped a force broadcast. Thus `34/44` had no mutation HTTP overlap and `33/44` had no force-broadcast overlap. Read-model scale explains most slow totals; the clean post-snapshot subset isolates the repeated scheduling problem.

## Ten Slowest GET Correlations

`Svc gap` is service completion to response-build start. `Snap gap` is outer `_dm_console_snapshot` completion to response-build start. `Post-build` is response-build completion to `http.request.end`. Broadcast durations are full outer spans; parenthetical values identify the part directly overlapping the isolated gap where available.

| GET trace ID | UTC request start-end | HTTP span | Service | Svc gap | Snap gap | Build | Post-build | Overlapping write route/method | Overlapping broadcast work | Supports event-loop starvation |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- | --- |
| `trace-189ab8066bac432ebd7f91d948c796ee` | `03:55:17.152-03:55:21.234` | 4,039.319 ms | 1,730.060 ms | 2,240 ms | 2,161 ms | 0.411 ms | 110 ms | `POST /api/dm/combat/set-turn` | 1,736.946 ms force (467 ms in snap gap), then 809.859 ms mutation DM snapshot | Yes |
| `trace-3ba431f6ccd146e8ba7d3b88f371ad4e` | `03:53:15.158-03:53:19.119` | 3,933.677 ms | 1,973.168 ms | 1,882 ms | 1,663 ms | 0.380 ms | 59 ms | `POST /api/dm/combat/start` | 2,134.049 ms force, then 778.571 ms mutation DM snapshot | Yes |
| `trace-aa8fe2674ad24b73bcf125b47e8686e9` | `03:52:48.270-03:52:52.141` | 3,869.546 ms | 3,400.598 ms | 407 ms | 191 ms | 0.405 ms | 61 ms | None | None | No; read/scheduler cost without a write |
| `trace-f2e7090a555c42a5acdd4d6ff9315454` | `03:53:21.948-03:53:25.735` | 3,786.740 ms | 910.135 ms | 2,733 ms | 2,678 ms | 0.391 ms | 97 ms | `POST /api/dm/combat/set-turn` | 1,257.476 ms force (1,022 ms in snap gap) | Yes |
| `trace-58c7439ed7334708b91e5439136904f8` | `03:55:24.098-03:55:27.769` | 3,670.767 ms | 1,883.995 ms | 202 ms | 4 ms | 0.438 ms | 1,581 ms | `POST /api/dm/map/combatants/90/move` | 1,114.312 ms force during post-build gap | Yes, after response build |
| `trace-58e0ee6d362b42138e65b0d7bf490609` | `03:55:58.167-03:56:01.470` | 3,303.251 ms | 1,754.951 ms | 1,419 ms | 1,209 ms | 1.079 ms | 126 ms | `POST /api/dm/combat/next-turn` | 2,035.730 ms force (261 ms in snap gap) | Yes |
| `trace-176c0ed4ff314d82b8cd872c7eafb2e3` | `03:55:36.205-03:55:39.187` | 2,980.334 ms | 1,755.441 ms | 1,166 ms | 797 ms | 0.398 ms | 58 ms | None | None | No identifiable write |
| `trace-dc68905820734c8a94833b246e5cad24` | `03:55:04.209-03:55:07.166` | 2,952.324 ms | 1,597.207 ms | 1,253 ms | 994 ms | 1.168 ms | 64 ms | `POST /api/dm/combat/next-turn` | 1,649.470 ms force (114 ms in snap gap) | Yes |
| `trace-2616e6a59f464895a3313933f35b8a23` | `03:55:21.249-03:55:24.095` | 2,827.177 ms | 1,677.562 ms | 1,026 ms | 864 ms | 0.674 ms | 61 ms | None | None | No identifiable write |
| `trace-47f0f3112db74bc6a0d5bd68181840f2` | `03:54:07.251-03:54:09.693` | 2,441.790 ms | 1,236.616 ms | 1,139 ms | 2 ms | 0.889 ms | 57 ms | None; WebSocket-originated action only | 2,452.453 ms force overlaps earlier read work | No post-snapshot or post-build stall |

All ten have matching GET trace/action IDs across queue, route-read, service-call, and response-build spans. The table's support decision depends on overlap with the clean post-snapshot or post-build progress interval, not merely overlap somewhere in the GET.

## Exact Mutation Routes In The Dense Window

| Method and route | Count |
| --- | ---: |
| `POST /api/dm/encounter/players/add` | 1 |
| `POST /api/dm/encounter/monsters/add` | 1 |
| `POST /api/dm/combat/start` | 1 |
| `POST /api/dm/combat/set-turn` | 2 |
| `POST /api/dm/combat/next-turn` | 3 |
| `POST /api/dm/map/combatants/90/move` | 1 |
| `POST /api/dm/monster-capabilities/90/execute` | 2 |
| `POST /api/dm/monster-capabilities/90/resolve-targets` | 1 |
| `POST /api/dm/monster-capabilities/90/resource` | 1 |

A non-gameplay `POST /api/client-log` also occurred and is excluded from mutation counts. Non-HTTP WebSocket actions included `move`, `set_facing`, and `monk_elemental_burst`. No explicit HP-change route occurred, so HP changes are not proven by this capture.

Of the nine clean delayed GETs overlapping mutations, five align with combat lifecycle/turn writes (start, two set-turns, and two next-turns) and four with movement or monster capability/resource routes. Combat lifecycle/turn is the largest coherent first planning family; the evidence does not justify migrating every mutation together.

## Attribution And Limits

The `212`-combatant load explains high service/read-model durations without requiring a separate event-loop-stall conclusion. It does not explain the repeated gaps that begin after the outer worker snapshot has completed, nor the movement sample's `1,581 ms` post-build gap.

Tactical serialization prevents treating the raw service-to-build gap as pure resume delay. It does not prevent using `_dm_console_snapshot` completion as the cleaner worker-completion proxy. Resource-pool and force-broadcast maxima were not used as causal evidence merely because they are similar.

The trace lacks span-parent IDs, thread/task identity, a monotonic timestamp, and an explicit event-loop-lag/resume marker. Those omissions prevent attributing every gap and prevent scheduler-internal precision. They do not negate this gate because the named architecture assessment already establishes synchronous ASGI-loop execution for these direct writes/broadcasts, and nine repeated clean gaps are temporally enclosed by active mutation requests.

## Decision And Next Action

- **Decision lane:** 1, repeated write-induced stalls confirmed.
- **Exact next work item:** `WORK-20260710-combat-mutation-event-loop-containment-decision`.
- **Type:** Planning/evidence only.
- **Initial family:** combat start, set-turn, and next-turn.
- **Ledger state:** paused; no active item or gate.
- **Implementation:** not authorized or performed.

See the [completed work item](../work_items/completed/WORK-20260708-dm-console-combat-route-request-overlap-controlled-repeat-evidence.md) and [living planning record](../planning/living_docs/dm_console_combat_route_request_overlap_controlled_repeat_evidence_20260710.md).
