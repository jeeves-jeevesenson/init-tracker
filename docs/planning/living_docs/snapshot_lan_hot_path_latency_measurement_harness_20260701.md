# Snapshot/LAN Hot-Path Latency Measurement Harness - 2026-07-01

## Status

Tooling/evidence document only. This document does not authorize app implementation, test edits, log edits, route registration changes, route body movement, launch command changes, lifespan behavior changes, readiness behavior changes, Uvicorn host changes, snapshot warm-up changes, cache ownership changes, TTL changes, snapshot schema changes, response payload changes, static hydration changes, WebSocket behavior changes, queue behavior changes, command semantic changes, production operations, deploys, commits, pushes, SSH, service restarts, topology changes, or gameplay behavior changes.

## Decision Summary

A bounded standard-library harness now exists for summarizing snapshot/LAN hot-path latency from existing debug-trace JSONL files:

`scripts/snapshot_lan_hot_path_latency_harness.py`

The first run against `logs/debug-trace-20260701-155344.jsonl` confirms repeated `_lan_snapshot` latency and related tactical/DM-console route spikes. The evidence is still one mixed smoke trace and is not isolated enough for implementation.

Recommended next work, if latency continues, is a controlled evidence/planning checkpoint using the harness across deliberately captured traces. Do not start cache/offload/schema/payload/route/TTL/WebSocket/queue implementation from this single trace summary.

## Harness Behavior

The harness:

- accepts one or more debug trace JSONL paths as positional arguments
- fails with a clear non-zero error if an input file is missing
- parses JSONL safely and counts malformed or non-object lines instead of failing the run
- uses only the Python standard library
- does not start the server
- does not require browser automation
- does not edit or mutate logs
- reports count, min, p50, p95, max, configurable threshold counts, and trace diagnostic counts
- optionally writes a JSON summary with `--json-output`

Percentiles use deterministic nearest-rank ordering over sorted `span.end` durations. `slow.span`, `very_slow.span`, and `hang_candidate.span` trace events are counted separately and are not used as latency samples.

## First Measurement

Command:

```bash
.venv/bin/python scripts/snapshot_lan_hot_path_latency_harness.py logs/debug-trace-20260701-155344.jsonl
```

Key results:

- `_lan_snapshot`: `2118` samples, p50 `90.765 ms`, p95 `524.684 ms`, max `25282.205 ms`, `967` samples at or above `250 ms`, `17` at or above `1000 ms`
- `_dm_tactical_snapshot`: `177` samples, p95 `1005.679 ms`, max `1357.979 ms`
- `_dm_console_snapshot`: `202` samples, p95 `1020.172 ms`, max `1395.289 ms`
- `_dm_console_snapshot_payload`: `222` samples, p95 `1018.191 ms`, max `1394.707 ms`
- `http.request:/api/dm/combat`: `176` samples, p95 `1048.359 ms`, max `1404.445 ms`
- malformed or non-object JSONL lines: `0`

## Interpretation

The repeated `_lan_snapshot` signal is confirmed. It is not a one-line artifact and not only an instrumentation diagnostic count.

The evidence is still mixed. The trace contains startup-era cache/player-load work, browser WebSocket activity, workspace polling, route reads, LAN broadcasts, claim/reconnect behavior, and game-state changes. The harness makes the signal easier to compare across traces, but this single run does not prove which implementation lever is safest.

## Decision

Do not implement latency fixes from this item.

The correct use of the new harness is future controlled evidence: compare deliberately captured traces, correlate route and snapshot targets, then decide whether a narrow implementation candidate exists.

## Recommended Next Work

If the developer wants more latency work:

`WORK-20260701-snapshot-lan-hot-path-controlled-evidence-checkpoint`

Recommended goal:

Run the harness against one or more intentionally captured traces and decide whether the latency is isolated enough to justify a specific implementation. Preserve the existing bans on app behavior changes, route movement, cache/TTL/schema/payload changes, offload expansion, WebSocket/queue changes, launch/readiness/shutdown changes, production operations, and gameplay changes unless a later task explicitly authorizes them.

If deploy-prep review is the priority, pausing latency work remains acceptable.
