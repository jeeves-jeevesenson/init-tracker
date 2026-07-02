# WORK-20260701-snapshot-lan-hot-path-latency-planning-checkpoint

Status: Completed

## Goal

Complete a bounded Codex docs/planning checkpoint for the snapshot/LAN hot-path latency evidence.

This checkpoint decided the smallest safe future lane from the controlled evidence. It did not implement, optimize, instrument, deploy, restart, SSH, push, commit, or change app code, tests, logs, production configuration, route registration, route bodies, payloads, cache ownership, TTLs, snapshot schemas, static hydration, WebSocket behavior, queue behavior, command semantics, auth/claims/reconnect, launch commands, lifespan behavior, readiness behavior, shutdown behavior, `UvicornServerHost`, persistence, production topology, or gameplay behavior.

## Files Inspected

- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260701-snapshot-lan-hot-path-controlled-evidence-checkpoint.md`
- `docs/planning/living_docs/snapshot_lan_hot_path_controlled_evidence_checkpoint_20260701.md`
- `docs/runtime_reports/snapshot_lan_hot_path_controlled_evidence_20260701.md`
- `docs/work_items/completed/WORK-20260701-snapshot-lan-hot-path-latency-measurement-harness.md`
- `docs/planning/living_docs/snapshot_lan_hot_path_latency_measurement_harness_20260701.md`
- `docs/runtime_reports/snapshot_lan_hot_path_latency_measurement_20260701.md`
- `docs/work_items/completed/WORK-20260701-snapshot-lan-hot-path-wait-evidence-checkpoint.md`
- `docs/planning/living_docs/snapshot_lan_hot_path_wait_evidence_checkpoint_20260701.md`
- `scripts/snapshot_lan_hot_path_latency_harness.py`
- `dnd_initative_tracker.py`, only targeted excerpts for `_lan_snapshot`, `_dm_tactical_snapshot`, `_dm_console_snapshot`, `_dm_console_snapshot_payload`, and the immediate `lan.snapshot.build` adjacency needed to interpret the evidence label
- `server_runtime.py`, only `ServerRuntimeFacade.read_snapshot` and related snapshot contract seams

No `majorTODO.md`, old plans, unrelated runtime reports, tests, browser assets, production files, smoke logs, debug traces, `docs/bug_reports/inbox/BUG-20260626-dmcontrol-terrain-not-visible.md`, or `logs/context/` files were inspected or edited.

## Files Changed

- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260701-snapshot-lan-hot-path-latency-planning-checkpoint.md`
- `docs/planning/living_docs/snapshot_lan_hot_path_latency_planning_checkpoint_20260701.md`

No active work item copy was left after completion.

## Evidence Summary

The latency signal is real and repeatable across the two named traces.

First harness report, `logs/debug-trace-20260701-155344.jsonl`:

- `_lan_snapshot`: `2118` samples, p50 `90.765 ms`, p95 `524.684 ms`, max `25282.205 ms`, `967` samples at or above `250 ms`, `17` at or above `1000 ms`.
- `_dm_tactical_snapshot`: `177` samples, p95 `1005.679 ms`.
- `_dm_console_snapshot`: `202` samples, p95 `1020.172 ms`.
- `_dm_console_snapshot_payload`: `222` samples, p95 `1018.191 ms`.
- `lan.snapshot.build`: `25` samples, p95 `880.831 ms`.
- `/api/dm/combat`: `176` samples, p95 `1048.359 ms`.

Controlled evidence report, `logs/debug-trace-20260701-191158.jsonl`:

- `_lan_snapshot`: `1075` samples, p50 `98.260 ms`, p95 `1220.955 ms`, max `24704.439 ms`, `435` samples at or above `250 ms`, `80` at or above `1000 ms`.
- `_dm_tactical_snapshot`: `55` samples, p50 `1197.004 ms`, p95 `2313.119 ms`.
- `_dm_console_snapshot`: `79` samples, p50 `1212.072 ms`, p95 `2376.749 ms`.
- `_dm_console_snapshot_payload`: `99` samples, p50 `323.099 ms`, p95 `2224.006 ms`.
- `lan.snapshot.build`: `31` samples, p50 `426.811 ms`, p95 `1433.860 ms`.
- `/api/dm/combat`: `53` samples, p50 `1326.809 ms`, p95 `2858.221 ms`.

The controlled smoke also confirmed the host/browser/LAN path worked in the tested run: headless startup, debug trace creation, `/dm` and `/` surface advertising, LAN hoist on port `8787`, browser LAN connection, claim/unclaim flows, and John Twilight attack weapon resolution.

## Bottleneck Interpretation

`_lan_snapshot` is the strongest primary bottleneck candidate. It has the highest sample count, repeated slow and very-slow samples in both traces, and representative route-chain evidence where `_lan_snapshot` accounts for almost all of a slow tactical `/api/dm/combat?workspace=dmcontrol` request.

`_dm_tactical_snapshot`, `_dm_console_snapshot_payload`, `_dm_console_snapshot`, and `/api/dm/combat` are route-visible and user-visible symptoms, but the inspected code shows they are largely wrappers around the tactical/LAN snapshot path when tactical data is requested. In particular, `_dm_tactical_snapshot()` calls `_lan_snapshot(include_static=False, hydrate_static=False)`, and `ServerRuntimeFacade.read_snapshot(dm_console)` delegates to `lan_controller._dm_console_snapshot(include_tactical=...)`.

`lan.snapshot.build` is important evidence for broadcast-side snapshot construction, but current evidence still does not distinguish whether the dominant problem is repeated `_lan_snapshot` calls, expensive internal `_lan_snapshot` substeps, broadcast-context building, tactical workspace polling, or overlap among those callers.

`_load_player_yaml_cache` is not selected as a primary lane from the current reports. Its p95 is sub-millisecond in both harness summaries, despite isolated large max/hang-candidate outliers.

## Decision

The next safe lane is targeted instrumentation evidence, not implementation and not another broad design checkpoint.

Direct cache, offload, schema, payload, TTL, static hydration, route, facade-cache, queue, WebSocket, or gameplay implementation is not justified from this checkpoint. The evidence proves repeated latency and identifies `_lan_snapshot` as the strongest candidate, but it still lacks the exact attribution needed to choose a safe behavior-changing lever.

The instrumentation should be narrow and additive. It should answer which caller context and which internal `_lan_snapshot` substeps dominate slow windows without changing runtime semantics.

## Missing Evidence

Implementation remains unjustified until a future evidence slice can answer:

- whether slow `_lan_snapshot` samples are dominated by route reads, LAN broadcasts, or another caller
- whether the same slow windows are startup-era, steady-state, or both
- whether repeated calls are rebuilding the same dynamic state within a short window
- how much time is spent in canonical map capture/apply, AoE normalization, active aura context, combatant unit assembly, ship/structure projection, static cache hydration, resource pool payloads, and JSON/broadcast adjacency
- whether include flags, static cache hit/miss state, invalidation domains, combatant/unit counts, map entity counts, WebSocket client counts, or workspace polling correlate with slow spans
- whether health/readiness and non-workspace combat reads remain responsive during slow windows
- whether route-local tactical serialization is preventing overlap or merely queuing slow tactical reads

## Future Slice Constraints

If opened, the next instrumentation item should protect:

- `server_runtime.py` facade behavior and snapshot contracts
- `/api/dm/combat` route behavior, status mapping, payload shape, and route-local offload/serialization posture
- snapshot schemas and response payloads
- cache ownership, TTLs, cache invalidation behavior, static hydration, and snapshot warm-up ownership
- WebSocket, auth, claims, reconnect, hidden-information, queue, command, persistence, launch, readiness, shutdown, `UvicornServerHost`, production topology, and gameplay behavior
- logs and existing runtime evidence files

No implementation lane is selected now. If later instrumentation justifies implementation, the smallest safe implementation should be a separate item, should stay legacy-owned at the proven hotspot, should preserve payloads and cache semantics, and should not move cache ownership into `ServerRuntimeFacade`.

## Small Smoke Bug

The small controlled-smoke bug should remain deferred as a separate bug-capture item if it recurs or if the developer chooses to prioritize it. It was not patched here, and it should not be folded into the latency instrumentation lane.

## Recommended Next Work

Recommended next work item, if latency work continues:

`WORK-20260701-snapshot-lan-hot-path-targeted-instrumentation-evidence`

Recommended goal:

Add the narrowest additive trace instrumentation needed to attribute snapshot/LAN hot-path latency by caller context and `_lan_snapshot` subcomponent, then capture and summarize bounded evidence with the existing harness. Preserve all route, payload, cache, WebSocket, queue, production, and gameplay behavior.

If latency work is not needed before deploy-prep review, pausing remains acceptable. Direct implementation remains deferred.

## Ledger Update

`docs/work_items/current_work.md` was returned to Idle with no active work item.

The completed table now includes this checkpoint. The allowed next actions are deploy-prep review, pause/no further migration, the targeted instrumentation evidence item if latency work continues, or a separate deferred bug-capture item if the small smoke bug remains relevant.

## Validation

Required validation commands:

- `git status --short`
- `timeout 10s git diff --check`

No tests, smoke, server commands, browser commands, deploy commands, production commands, restarts, SSH, pushes, or commits were run by this checkpoint.
