# WORK-20260701-snapshot-lan-hot-path-controlled-evidence-checkpoint

Status: Completed

## Goal

Complete a bounded controlled-evidence checkpoint using the controlled smoke run and snapshot/LAN hot-path latency harness output.

This was a Codex docs/evidence checkpoint only. It did not change app implementation, tests, logs, production configuration, route registration, route bodies, launch commands, lifespan behavior, readiness behavior, `UvicornServerHost`, snapshot warm-up, cache ownership, TTLs, snapshot schemas, response payloads, static hydration, WebSocket behavior, auth/claims/reconnect, queue behavior, command semantics, persistence, shutdown semantics, production topology, deploys, restarts, SSH, pushes, commits, optimization, or gameplay behavior.

## Files Inspected

- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260701-snapshot-lan-hot-path-latency-measurement-harness.md`
- `docs/runtime_reports/snapshot_lan_hot_path_latency_measurement_20260701.md`
- `logs/smoke/WORK-20260701-snapshot-lan-hot-path-controlled-evidence-checkpoint_smoke-server_20260701-191158.log`, using only `head` and `tail`
- `logs/debug-trace-20260701-191158.jsonl`, using only `head` and `tail`, plus the required harness command
- `scripts/snapshot_lan_hot_path_latency_harness.py`
- `docs/planning/living_docs/snapshot_lan_hot_path_latency_measurement_harness_20260701.md`
- `docs/work_items/completed/WORK-20260701-snapshot-lan-hot-path-wait-evidence-checkpoint.md`
- `docs/planning/living_docs/snapshot_lan_hot_path_wait_evidence_checkpoint_20260701.md`

No app source, tests, browser assets, production files, `majorTODO.md`, old plans, old runtime reports outside the named source documents, `docs/bug_reports/inbox/BUG-20260626-dmcontrol-terrain-not-visible.md`, `logs/context/`, smoke logs, or debug traces were edited.

## Files Changed

- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260701-snapshot-lan-hot-path-controlled-evidence-checkpoint.md`
- `docs/planning/living_docs/snapshot_lan_hot_path_controlled_evidence_checkpoint_20260701.md`
- `docs/runtime_reports/snapshot_lan_hot_path_controlled_evidence_20260701.md`

No active work item copy was left after completion.

## Controlled Smoke Evidence

The controlled smoke passed by developer report.

The smoke log records:

- Headless tracker started.
- Debug trace was created at `logs/debug-trace-20260701-191158.jsonl`.
- DM operator surface was advertised at `/dm`.
- Player LAN surface was advertised at `/`.
- LAN server hoisted on port `8787`.
- Browser LAN session connected.
- Claim/unclaim flows were logged for Dorian, Old Man, Johnny Morris, Throat Goat, and John Twilight.
- Attack weapon resolution was logged for John Twilight.

A small bug was observed during smoke and intentionally deferred. It was not patched in this lane. If it remains relevant, capture it as a separate bug item later rather than folding it into latency work.

## Latency Evidence

Required harness command:

```bash
.venv/bin/python scripts/snapshot_lan_hot_path_latency_harness.py logs/debug-trace-20260701-191158.jsonl
```

Key results:

- `_lan_snapshot`: `1075` samples, p50 `98.260 ms`, p95 `1220.955 ms`, max `24704.439 ms`, `435` samples at or above `250 ms`, `80` at or above `1000 ms`, `11` trace hang candidates.
- `_dm_tactical_snapshot`: `55` samples, p50 `1197.004 ms`, p95 `2313.119 ms`, max `2536.769 ms`.
- `_dm_console_snapshot`: `79` samples, p50 `1212.072 ms`, p95 `2376.749 ms`, max `2638.671 ms`.
- `_dm_console_snapshot_payload`: `99` samples, p50 `323.099 ms`, p95 `2224.006 ms`, max `2638.226 ms`.
- `lan.snapshot.build`: `31` samples, p50 `426.811 ms`, p95 `1433.860 ms`, max `2037.209 ms`.
- `http.request:/api/dm/combat`: `53` samples, p50 `1326.809 ms`, p95 `2858.221 ms`, max `2941.737 ms`.
- Malformed or non-object JSONL lines: `0`.

Compared with the first harness report, this controlled run keeps the same qualitative signal but makes it more actionable: route-level `/api/dm/combat` latency, tactical snapshot latency, DM-console snapshot latency, `lan.snapshot.build`, and `_lan_snapshot` all show repeated material latency in the same controlled smoke window.

## Decision

The controlled evidence proves the host/browser/LAN path still works while the latency signal remains real and material.

It is sufficient to justify a future snapshot/LAN latency planning/design lane. It is not sufficient to authorize direct implementation. The evidence confirms repeated latency but still does not isolate the safest code lever among cache ownership, TTLs, schema/payload shape, static hydration, snapshot warm-up, LAN broadcast behavior, tactical snapshot work, route-local behavior, offload/threading posture, WebSocket activity, queue behavior, or gameplay-triggered invalidation.

The next lane should be snapshot/LAN latency planning, not targeted app instrumentation, not direct optimization, and not no further work if the developer wants to act on latency. Deferred bug capture is separate and should only become the next lane if the small smoke bug is more urgent than latency planning.

## Recommended Next Work

Recommended next work item, if latency work continues:

`WORK-20260701-snapshot-lan-hot-path-latency-planning-checkpoint`

Recommended goal:

Use the controlled evidence to plan the smallest safe snapshot/LAN latency intervention. The checkpoint should map the hot-path ownership and decide whether the next step is a narrow implementation candidate, a targeted instrumentation-only task, or no latency work. It should inspect only the minimal named app files needed for planning and should not change app behavior.

If deploy-prep review is higher priority, pausing latency work remains acceptable.

## Must Remain Forbidden

Forbidden until a planning checkpoint explicitly authorizes implementation:

- snapshot/LAN latency implementation or optimization
- targeted app instrumentation
- route registration changes or route body movement
- launch command, lifespan, readiness, shutdown, or `UvicornServerHost` changes
- snapshot warm-up changes
- cache ownership changes, including moving cache ownership into `ServerRuntimeFacade`
- TTL changes
- snapshot schema, response payload, or static hydration changes
- broader `run_in_threadpool` adoption or lower-level tactical/LAN offload
- WebSocket, auth, claims, reconnect, hidden-information, or queue behavior changes
- command semantics, persistence, or gameplay behavior changes
- production topology changes, deploys, restarts, SSH, pushes, or commits
- patching the small smoke bug inside the latency lane

## Ledger Update

`docs/work_items/current_work.md` was returned to Idle with no active work item.

The completed table now includes this checkpoint. The allowed next actions are deploy-prep review, pause/no further migration, `WORK-20260701-snapshot-lan-hot-path-latency-planning-checkpoint` if the developer wants latency work, or a separate deferred bug-capture item if the small smoke bug remains relevant.

## Validation

Required validation commands:

- `.venv/bin/python scripts/snapshot_lan_hot_path_latency_harness.py logs/debug-trace-20260701-191158.jsonl`
- `timeout 10s git diff --check`
- `git status --short`

Results are recorded in the final agent report.
