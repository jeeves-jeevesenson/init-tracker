# WORK-20260708-dm-console-combat-route-request-overlap-controlled-repeat-evidence

Status: Completed

## Goal

Complete the controlled-repeat evidence gate for `/api/dm/combat` request overlap and decide whether synchronous combat writes or force-state broadcasts repeatedly delay GET coroutine progress on the ASGI event loop.

## Files Inspected

- `docs/agent_tasks/templates/task-packet.md`
- `docs/work_items/current_work.md`
- `docs/architecture/Init-Tracker-Updated-Migration-Assessment-2026-07-09.md`
- `docs/work_items/completed/WORK-20260708-dm-console-combat-route-request-overlap-planning-checkpoint-followup.md`
- `docs/planning/living_docs/dm_console_combat_route_request_overlap_planning_checkpoint_followup_20260708.md`
- `scripts/snapshot_lan_hot_path_latency_harness.py`
- `logs/smoke/WORK-20260708-dm-console-combat-route-request-overlap-controlled-repeat-evidence_smoke-server_20260710-223521.log`
- `logs/debug-trace-20260710-223521.jsonl`

## Files Changed

- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260708-dm-console-combat-route-request-overlap-controlled-repeat-evidence.md`
- `docs/planning/living_docs/dm_console_combat_route_request_overlap_controlled_repeat_evidence_20260710.md`
- `docs/runtime_reports/dm_console_combat_route_request_overlap_controlled_repeat_evidence_20260710.md`

## Evidence Summary

- The harness parsed `163,466` valid JSON objects with zero blank, malformed, or non-object entries.
- The trace contains `128` GET `/api/dm/combat` route samples. `126` requested tactical workspace data and `2` were non-tactical.
- Peak route context was `212` combatants: `10` players and `202` monsters.
- HTTP request p50/p95/max was `934.286 / 2,980.334 / 4,039.319 ms`.
- Route-read p50/p95/max was `873.309 / 2,883.876 / 3,970.152 ms`.
- Combat service-call p50/p95/max was `783.876 / 1,754.951 / 3,400.598 ms` across `159` service-call contexts.
- Threadpool dispatch queue p95/max was `2.326 / 15.882 ms`; route response build p95/max was `1.879 / 39.296 ms`. Neither explains the multi-second route outliers.
- There were `14` operational force-state broadcast contexts, plus two startup no-client force-broadcast spans. Broadcast-context `_lan_snapshot` max was `1,564.516 ms`; broadcast-context `lan.snapshot.resource_pools` max was `1,502.333 ms`.

## Correlation Result

All `44` GETs with an HTTP span duration of at least `1,000 ms` were joined by GET trace ID to HTTP request start/end and the queue, route-read, service-call, response-build, mutation-request, and broadcast timelines.

The requested service-completion-to-response-build gap was at least `100 ms` for `57/128` GETs (`44.531%`) and at least `250 ms` for `16/128` (`12.500%`). Those raw gaps include remaining tactical/read-model work. Respectively `12` and `11` overlapped an active mutation or force broadcast.

The cleaner outer `_dm_console_snapshot` completion-to-response-build gap was at least `100 ms` for `13/128` GETs (`10.156%`) and at least `250 ms` for `11/128` (`8.594%`). `9` in each threshold group overlapped an active synchronous mutation, and `5` overlapped force-broadcast work. The repetitions include combat start, two set-turn requests, multiple next-turn requests, movement, and monster capability/resource writes.

This confirms repeated write-induced stalls at the evidence-gate level. It does not attribute all slow GETs to writes: `44` GETs exceeded one second, while only `10` overlapped an HTTP mutation and `11` overlapped a force broadcast over their full lifetime. The `212`-combatant tactical/read-model cost explains most baseline latency. The separate post-snapshot gaps show the additional scheduling stall.

Detailed correlations, the ten slowest-request table, exact mutation routes, and limitations are recorded in [the runtime report](../../runtime_reports/dm_console_combat_route_request_overlap_controlled_repeat_evidence_20260710.md).

## Decision

Selected outcome 1: repeated write-induced stalls are confirmed. Authorize only a bounded combat-mutation containment planning/evidence item:

- **Next work item:** `WORK-20260710-combat-mutation-event-loop-containment-decision`
- **Type:** Planning/evidence only
- **Initial family:** `POST /api/dm/combat/start`, `POST /api/dm/combat/set-turn`, and `POST /api/dm/combat/next-turn`
- **Not authorized:** application implementation, broad mutation migration, public `202` command semantics, deployment, restart, commit, or push

The ledger remains paused with no active item or gate. Resource-pools remains closed. Startup static fields and the terrain inbox bug remain separate.

## Validation

- `timeout 120s .venv/bin/python scripts/snapshot_lan_hot_path_latency_harness.py logs/debug-trace-20260710-223521.jsonl`: passed with `163,466` valid objects, zero malformed entries, and the recorded latency values.
- `timeout 10s git diff --check`: required after the documentation update.
- `git status --short`: required for the final report.

No application, browser, test-suite, deployment, restart, SSH, commit, or push action was run.
