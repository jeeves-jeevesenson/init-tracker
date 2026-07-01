# Snapshot/LAN Hot-Path Wait Evidence Checkpoint - 2026-07-01

## Status

Checkpoint/evidence document only. This document does not authorize app implementation, test edits, log edits, route registration changes, route body movement, launch command changes, lifespan behavior changes, readiness behavior changes, Uvicorn host changes, snapshot warm-up changes, cache ownership changes, TTL changes, snapshot schema changes, response payload changes, static hydration changes, WebSocket behavior changes, queue behavior changes, command semantic changes, production operations, deploys, commits, pushes, SSH, service restarts, topology changes, or gameplay behavior changes.

## Decision Summary

The remaining `_lan_snapshot` latency evidence is real, repeated, and worth measuring more carefully.

It is not isolated enough to justify implementation. The evidence comes from one live smoke/debug trace with mixed startup, browser activity, workspace reads, LAN broadcasts, and claim/reconnect activity. It identifies a real hot-path risk, not a host-boundary deploy blocker.

Recommended next work item:

`WORK-20260701-snapshot-lan-hot-path-latency-measurement-harness`

The next item should be a bounded measurement harness. It should not change app behavior. If the developer does not want latency work before deploy approval, pausing latency work is also acceptable. Direct latency implementation is not recommended from the current evidence.

## Evidence Inspected

Documents inspected:

- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260701-app-host-runtime-lifecycle-smoke-evidence-capture.md`
- `docs/planning/living_docs/server_runtime_app_host_lifecycle_smoke_evidence_capture_20260701.md`
- `docs/work_items/completed/WORK-20260701-app-host-runtime-lifecycle-deploy-guidance-checkpoint.md`
- `docs/planning/living_docs/server_runtime_app_host_lifecycle_deploy_guidance_checkpoint_20260701.md`

Evidence logs inspected:

- `logs/debug-trace-20260701-155344.jsonl`
- `logs/smoke/WORK-20260701-app-host-runtime-lifecycle-smoke-evidence-capture_smoke-server_20260701-155344.log`

The log inspections used only `grep`, `tail`, and `sed` excerpts. The logs were not edited.

## Evidence Facts

Smoke log facts:

- Headless tracker started.
- Debug trace path was `logs/debug-trace-20260701-155344.jsonl`.
- DM operator surface was advertised at `/dm`.
- Player LAN surface was advertised at `/`.
- LAN server hoisted on port `8787`.
- Browser LAN sessions connected, claimed, unclaimed, restored claims, disconnected, and shutdown was logged.
- The smoke log does not include latency summaries.

Debug trace facts:

- `_lan_snapshot` completed `2118` times in the trace.
- `_lan_snapshot` emitted `924` `slow.span` events.
- `_lan_snapshot` emitted `128` `very_slow.span` events.
- `_lan_snapshot` emitted `2` `hang_candidate.span` events.
- The two hang candidates were `25282.205 ms` during startup-era zero-combatant work and `2633.355 ms` with `15` combatants, `10` players, `5` monsters, and `1` WebSocket client.
- Repeated `_lan_snapshot` slow spans appeared in the `369-499 ms` band, including the final two smoke-capture summaries at `391.315 ms` and `398.044 ms`.
- Repeated `_lan_snapshot` very-slow spans appeared above `500 ms`, with representative values above `1000 ms` and a route-chain `_lan_snapshot` at `1357.249 ms`.
- `_dm_tactical_snapshot` completed `177` times and had `33` slow plus `47` very-slow span events.
- `_dm_console_snapshot_payload` completed `222` times and had `38` slow plus `47` very-slow span events.
- `_dm_console_snapshot` completed `202` times and had `38` slow plus `47` very-slow span events.
- `lan.snapshot.build` had `4` slow plus `8` very-slow span events.
- `/api/dm/combat` completed `176` times with HTTP 200, including `173` workspace requests and `3` non-workspace requests.
- `/api/dm/combat` had `41` slow route spans and `46` very-slow route spans in the trace excerpts.

Representative slow route chain:

- `trace-838f27bc83384fb29c749971cac12c28`
- `_lan_snapshot`: `1357.249 ms`
- `_dm_tactical_snapshot`: `1357.979 ms`
- `_dm_console_snapshot_payload`: `1394.707 ms`
- `_dm_console_snapshot`: `1395.289 ms`
- `GET /api/dm/combat?workspace=dmcontrol`: HTTP 200, `1405.132 ms`

Representative fast route with adjacent standalone slow LAN work:

- `_lan_snapshot` inside `_dm_tactical_snapshot`: `3.923 ms`
- `_dm_tactical_snapshot`: `4.149 ms`
- `_dm_console_snapshot_payload`: `24.610 ms`
- `_dm_console_snapshot`: `24.841 ms`
- `GET /api/dm/combat?workspace=dmcontrol`: HTTP 200, `33.512 ms`
- Immediately afterward, standalone `_lan_snapshot` spans were `391.315 ms` and `398.044 ms`.

## Interpretation

The signal is repeated and material. It is not a one-line artifact.

The signal is also mixed. The trace includes startup behavior, browser WebSockets, claim/reconnect operations, combat/session state changes, workspace polling, route-local offload behavior, tactical serialization effects, LAN broadcasts, and dynamic snapshot cache activity. This makes it unsuitable for selecting a code fix without a narrower harness.

The best interpretation is that snapshot/LAN latency is a known hot-path risk. It is separate from the host/server lifecycle ownership question already answered by the app-host smoke and deploy-guidance checkpoints.

## Decision

Do not start snapshot/LAN latency implementation from this checkpoint.

Open a bounded measurement harness only if the developer wants to act on the latency evidence before deploy approval or before future route/snapshot work. Otherwise, pause/no immediate latency work is acceptable.

The measurement harness should answer:

- how often `_lan_snapshot` exceeds `100 ms`, `500 ms`, and `1000 ms` under controlled polling and browser activity
- whether slow `_lan_snapshot` spans correlate with workspace reads, LAN broadcasts, cache misses, dynamic-only rebuilds, WebSocket activity, or game-state changes
- whether health/readiness and non-workspace reads remain responsive during slow snapshot windows
- whether the prior route-local offload and tactical serialization posture is still sufficient
- whether there is a narrow implementation candidate after measurement

## Recommended Next Work

`WORK-20260701-snapshot-lan-hot-path-latency-measurement-harness`

Recommended goal:

Add or run a bounded, timeout-controlled evidence harness against an already-running local server to measure snapshot/LAN hot-path latency without changing app behavior. Capture route timings, trace spans, and context for `/api/dm/combat?workspace=dmcontrol`, standalone LAN snapshot/broadcast activity, health/readiness responsiveness, `_lan_snapshot`, `lan.snapshot.build`, `_dm_tactical_snapshot`, `_dm_console_snapshot_payload`, and `_dm_console_snapshot`.

Future harness constraints:

- scripts/docs-only changes only, unless a later developer task explicitly expands scope
- no app-runtime behavior changes
- no production commands
- no broad test sweeps
- no cache, TTL, payload, schema, WebSocket, queue, route, launch, readiness, or gameplay changes
- timeout-bound all diagnostics

## Deferred Scope

Deferred until better evidence exists:

- snapshot/LAN latency implementation
- cache ownership changes
- TTL changes
- snapshot schema changes
- response payload changes
- static hydration changes
- snapshot warm-up changes
- broader threadpool/offload adoption
- queue-wait behavior changes
- WebSocket, auth, claims, reconnect, or hidden-information changes
- route registration changes
- route body movement
- app-host, launch, lifespan, readiness, or shutdown behavior changes
- gameplay, persistence, production deploy, restart, SSH, push, commit, or topology changes
