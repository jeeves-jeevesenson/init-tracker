# Snapshot/LAN Hot-Path Targeted Instrumentation Evidence - 2026-07-01

## Scope

This report records the instrumentation/evidence slice for snapshot/LAN hot-path attribution.

No server smoke, browser smoke, deploy, restart, SSH, push, commit, production topology change, route movement, payload/schema change, cache behavior change, WebSocket behavior change, queue behavior change, or gameplay change was performed.

## Instrumentation

New trace labels identify caller/context for `_lan_snapshot` and nested snapshot builders. New spans split broad `_lan_snapshot` work into map-window sync, canonical map capture/apply, AoE normalization, aura expansion, unit assembly, tactical payload composition, static field handling, and resource pool handling.

DM console wrapper spans separate combat snapshot work from tactical snapshot work. Tactical wrapper spans separate LAN snapshot build from tactical payload extraction.

Counts are aggregate only and intentionally omit names, secrets, full payloads, and large objects.

## Existing Trace Compatibility

The required harness run against `logs/debug-trace-20260701-191158.jsonl` is expected to remain backward-compatible with old traces. Because that trace predates the new labels, the new span rows should have zero counts and the caller/context breakdown should report no labels.

The first trace, `logs/debug-trace-20260701-155344.jsonl`, was not part of the required validation commands for this slice. It remains a useful optional compatibility check if the developer wants it later.

## Evidence Decision

No latency implementation is selected from this slice.

The new instrumentation still needs a developer-run smoke trace before any implementation decision. That smoke should exercise DM console route reads, tactical map reads, LAN updates, DM WebSocket updates, and player WebSocket presence enough for the new labels and counters to populate.

## Recommended Next Evidence

Run a developer-owned targeted smoke/evidence capture with debug tracing enabled, then run:

```bash
.venv/bin/python scripts/snapshot_lan_hot_path_latency_harness.py <new-debug-trace.jsonl>
```

Use the caller/context breakdown and subspan rows to decide whether a separate implementation work item is justified.
