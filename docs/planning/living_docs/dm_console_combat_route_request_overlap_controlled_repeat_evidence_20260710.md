# DM Console Combat Route Request Overlap Controlled Repeat Evidence

Date: 2026-07-10

Work item: `WORK-20260708-dm-console-combat-route-request-overlap-controlled-repeat-evidence`

Status: Completed evidence gate; ledger paused

## Decision

Select lane 1. The controlled repeat confirms that synchronous combat mutation and broadcast work repeatedly delays `/api/dm/combat` GET coroutine progress after worker-side snapshot completion.

This is a planning authorization only. The exact next work item is `WORK-20260710-combat-mutation-event-loop-containment-decision`, type planning/evidence. No implementation task is opened or authorized by this checkpoint.

## Basis

- `128` GET samples substantially exceed the prior six-request evidence set.
- `11/128` GETs had at least a `250 ms` gap from outer `_dm_console_snapshot` completion to response-build start.
- `9/11` of those gaps overlapped active synchronous mutation requests, and `5/11` overlapped force-state broadcast work.
- Repeated lifecycle/turn examples occurred around one combat start, two set-turn requests, and multiple next-turn requests.
- The slowest GET's outer snapshot completed at `03:55:18.963Z`, but response build did not start until `03:55:21.124Z` while a set-turn request remained active. Its `1,736.946 ms` force broadcast contained a `1,580.751 ms` DM broadcast snapshot payload; the same mutation then spent `809.859 ms` building the later DM snapshot before the GET resumed.
- In the combat-start example, the GET outer snapshot and the `2,134.049 ms` force broadcast ended together at `03:53:17.397Z`; the mutation then performed a `778.571 ms` DM snapshot, and the GET route resumed at `03:53:19.059Z` as mutation-side DM broadcast work completed.
- A movement example did not have a post-snapshot gap, but its response build completed about `1,581 ms` before HTTP completion while the `1,114.312 ms` movement force broadcast ran. This is a separate post-build event-loop progress stall.

The conclusion does not depend on similar aggregate maxima. It depends on repeated request-level timestamp enclosure joined by trace/action IDs, plus the named architecture assessment's established fact that these direct mutation/broadcast paths execute synchronously on the ASGI loop.

## Scale And Attribution Boundary

The `212`-combatant (`10` player / `202` monster) shape remains intrinsically expensive:

- service-call p50 was `783.876 ms`;
- route-read p50 was `873.309 ms`;
- `44/128` GETs exceeded one second;
- only `10/44` slow GETs overlapped an HTTP mutation over their full lifetime;
- only `11/44` slow GETs overlapped a force broadcast over their full lifetime.

Therefore the trace supports two simultaneous conclusions:

1. Read-model/tactical cost explains most baseline and one-second GET latency.
2. Synchronous writes add a distinct, repeatedly reproduced coroutine-progress stall after worker snapshot completion or after response build.

The raw service-call-to-response-build gap must not be labeled pure event-loop delay because it includes remaining tactical serialization. The outer snapshot-completion gap is the planning gate's cleaner proxy. Missing thread IDs, task IDs, span parent IDs, monotonic timestamps, and an explicit event-loop-lag span limit scheduler-level precision, but do not erase the repeated write-enclosed post-snapshot gaps.

## Exact Next Planning Scope

`WORK-20260710-combat-mutation-event-loop-containment-decision` must remain a bounded planning/evidence item that:

- selects the coherent combat lifecycle/turn family shown by `POST /api/dm/combat/start`, `POST /api/dm/combat/set-turn`, and `POST /api/dm/combat/next-turn`;
- identifies the existing authoritative action-queue seam for that family;
- defines how the synchronous queue wait could run outside the ASGI event loop without moving authority to an arbitrary worker thread;
- preserves current HTTP status codes, response payloads, auth, claims, hidden information, persistence, visibility, reconnect, and gameplay behavior;
- defines future instrumentation for queue wait, command execution, broadcast snapshot build, fanout scheduling, event-loop lag, and total HTTP time;
- keeps synchronous HTTP compatibility and excludes public `202`/status semantics from the first containment slice;
- stops at a planning decision and does not implement the seam.

Movement and monster capability/resource routes corroborate the broad scheduling issue but are not part of the first coherent family. No explicit HP-change route occurred in this capture, so HP handling is not evidence-proven scope.

## Deferred Scope

- No application or server code change.
- No route, schema, queue, cache, WebSocket, auth, claim, reconnect, persistence, visibility, or gameplay change.
- No resource-pools implementation; that lane remains closed.
- No startup static-fields work.
- No terrain inbox bug work.
- No deployment, restart, SSH, commit, or push.

## Durable Evidence

- [Completed work item](../../work_items/completed/WORK-20260708-dm-console-combat-route-request-overlap-controlled-repeat-evidence.md)
- [Runtime report](../../runtime_reports/dm_console_combat_route_request_overlap_controlled_repeat_evidence_20260710.md)
- `logs/debug-trace-20260710-223521.jsonl`
- `logs/smoke/WORK-20260708-dm-console-combat-route-request-overlap-controlled-repeat-evidence_smoke-server_20260710-223521.log`
