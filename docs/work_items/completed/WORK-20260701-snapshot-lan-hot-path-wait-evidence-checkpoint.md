# WORK-20260701-snapshot-lan-hot-path-wait-evidence-checkpoint

Status: Completed

## Goal

Complete a bounded docs/evidence checkpoint for the remaining snapshot/LAN hot-path latency observed after the app-host runtime lifecycle work.

This checkpoint decides whether the observed `_lan_snapshot` slow spans are a real next development priority, what evidence exists, and whether the next lane should be a measurement harness, a focused planning checkpoint, no immediate latency work, or implementation later.

This was docs/evidence only. No app code, tests, logs, deployment configuration, route registration, route bodies, launch commands, lifespan behavior, readiness behavior, `UvicornServerHost`, snapshot warm-up, cache ownership, snapshot schemas, response payloads, static hydration, WebSocket behavior, auth/claims/reconnect, queue behavior, command semantics, persistence, shutdown semantics, production topology, deploys, restarts, SSH, pushes, commits, or gameplay behavior were changed.

## Files Inspected

- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260701-app-host-runtime-lifecycle-smoke-evidence-capture.md`
- `docs/planning/living_docs/server_runtime_app_host_lifecycle_smoke_evidence_capture_20260701.md`
- `docs/work_items/completed/WORK-20260701-app-host-runtime-lifecycle-deploy-guidance-checkpoint.md`
- `docs/planning/living_docs/server_runtime_app_host_lifecycle_deploy_guidance_checkpoint_20260701.md`
- `logs/debug-trace-20260701-155344.jsonl`, using only `grep`, `tail`, and `sed`
- `logs/smoke/WORK-20260701-app-host-runtime-lifecycle-smoke-evidence-capture_smoke-server_20260701-155344.log`, using only `grep` and `sed`

No app source, tests, browser assets, production files, `majorTODO.md`, old plans, old reports, `docs/bug_reports/inbox/BUG-20260626-dmcontrol-terrain-not-visible.md`, or `logs/context/` were inspected or edited.

## Files Changed

- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260701-snapshot-lan-hot-path-wait-evidence-checkpoint.md`
- `docs/planning/living_docs/snapshot_lan_hot_path_wait_evidence_checkpoint_20260701.md`

No active work item copy was left after completion.

## Evidence Files

Smoke log:

`logs/smoke/WORK-20260701-app-host-runtime-lifecycle-smoke-evidence-capture_smoke-server_20260701-155344.log`

Debug trace:

`logs/debug-trace-20260701-155344.jsonl`

Both named evidence files existed. No substitute evidence was invented.

## Exact Latency Evidence

The smoke log records a single live headless smoke run:

- Headless tracker started and wrote `logs/debug-trace-20260701-155344.jsonl`.
- The LAN server was hoisted at `15:54:36` local time on port `8787`.
- Browser LAN sessions connected, claimed, unclaimed, restored claims, disconnected, and shutdown was logged at `16:12:08`.
- The smoke log itself does not contain latency summaries; latency evidence comes from the matching debug trace.

The debug trace records broad `_lan_snapshot` activity:

- `grep -c '"event":"span.end".*"span":"_lan_snapshot"' logs/debug-trace-20260701-155344.jsonl` returned `2118`.
- `grep -c '"event":"slow.span".*"span":"_lan_snapshot"' logs/debug-trace-20260701-155344.jsonl` returned `924`.
- `grep -c '"event":"very_slow.span".*"span":"_lan_snapshot"' logs/debug-trace-20260701-155344.jsonl` returned `128`.
- `grep -c '"event":"hang_candidate.span".*"span":"_lan_snapshot"' logs/debug-trace-20260701-155344.jsonl` returned `2`.

Representative `_lan_snapshot` evidence:

- `2026-07-01T20:54:36.343Z`: `_lan_snapshot` hang candidate, `25282.205 ms`, zero combatants, zero players, zero monsters, zero WebSocket clients. This began before LAN hoist completed and is startup-era evidence, not an isolated user route.
- `2026-07-01T20:55:34.882Z`: `_lan_snapshot` hang candidate, `2633.355 ms`, `15` combatants, `10` players, `5` monsters, `1` WebSocket client.
- Repeated slow spans around `369-499 ms`, including `369.579 ms`, `370.107 ms`, `391.768 ms`, `498.787 ms`, and the final two smoke-capture summaries at `391.315 ms` and `398.044 ms`.
- Repeated very-slow spans above `500 ms`, including `1026.898 ms`, `1289.419 ms`, `1357.249 ms`, and multiple `800-1100 ms` entries during workspace and broadcast activity.

The debug trace also records related snapshot-route chain evidence:

- `grep -c '"event":"span.end".*"span":"_dm_tactical_snapshot"' logs/debug-trace-20260701-155344.jsonl` returned `177`.
- `_dm_tactical_snapshot` had `33` `slow.span` events and `47` `very_slow.span` events.
- `grep -c '"event":"span.end".*"span":"_dm_console_snapshot"' logs/debug-trace-20260701-155344.jsonl` returned `202`.
- `_dm_console_snapshot` had `38` `slow.span` events and `47` `very_slow.span` events.
- `grep -c '"event":"span.end".*"span":"_dm_console_snapshot_payload"' logs/debug-trace-20260701-155344.jsonl` returned `222`.
- `_dm_console_snapshot_payload` had `38` `slow.span` events and `47` `very_slow.span` events.
- `lan.snapshot.build` had `4` `slow.span` events and `8` `very_slow.span` events.

The clearest route-chain example is `trace-838f27bc83384fb29c749971cac12c28` at `2026-07-01T20:56:47Z`:

- `_lan_snapshot`: `1357.249 ms`
- `_dm_tactical_snapshot`: `1357.979 ms`
- `_dm_console_snapshot_payload`: `1394.707 ms`
- `_dm_console_snapshot`: `1395.289 ms`
- `GET /api/dm/combat?workspace=dmcontrol`: HTTP 200, `1405.132 ms`

The final recorded workspace request shows the opposite case, where the route was fast while standalone LAN snapshot work remained slow immediately afterward:

- `_lan_snapshot` inside `_dm_tactical_snapshot`: `3.923 ms`
- `_dm_tactical_snapshot`: `4.149 ms`
- `_dm_console_snapshot_payload`: `24.610 ms`
- `_dm_console_snapshot`: `24.841 ms`
- `GET /api/dm/combat?workspace=dmcontrol`: HTTP 200, `33.512 ms`
- Immediately after that request, standalone `_lan_snapshot` spans were `391.315 ms` and `398.044 ms`.

The debug trace records `176` `GET /api/dm/combat` HTTP 200 completions, `173` of them with `query_keys:["workspace"]`. Route-level evidence included `41` slow route spans and `46` very-slow route spans for `/api/dm/combat`; the largest representative route completion observed in the extracted lines was the `1405.132 ms` workspace request above.

## Decision

The `_lan_snapshot` latency evidence is real and repeated enough to justify more measurement.

It is not isolated enough to justify implementation yet. The evidence comes from one live smoke/debug trace with mixed startup, browser WebSocket activity, workspace polling, broadcast work, claim/reconnect activity, and game-state changes. It proves repeated hot-path latency exists, but it does not isolate which trigger dominates, how often it appears under controlled load, whether it is user-visible in normal play, or whether it still creates server-wide responsiveness risk after the previous DM-console offload and tactical serialization work.

This is not a blocker to continued development or deploy-prep review for the host-boundary slice. It is a known snapshot/LAN hot-path risk. The completed deploy-guidance checkpoint remains valid: more latency evidence is optional before developer deploy approval, not required to close the host-boundary smoke gap.

The next lane should be a bounded measurement harness, not a planning checkpoint and not implementation. A planning checkpoint would be premature without isolated measurement. Direct implementation would be riskier because the current evidence touches snapshot building, tactical workspace reads, LAN broadcasts, cache behavior, and route timing without proving the smallest safe intervention.

## Decision Questions

What exact latency evidence exists for `_lan_snapshot` and related snapshot spans?

The named debug trace contains `2118` `_lan_snapshot` completions, `924` `_lan_snapshot` slow spans, `128` `_lan_snapshot` very-slow spans, and `2` `_lan_snapshot` hang-candidate spans. Related evidence includes repeated slow/very-slow `_dm_tactical_snapshot`, `_dm_console_snapshot_payload`, `_dm_console_snapshot`, `lan.snapshot.build`, and `/api/dm/combat?workspace=dmcontrol` route spans, with one representative route chain taking `1405.132 ms` and `_lan_snapshot` contributing `1357.249 ms`.

Was the slow evidence isolated, repeated, or enough to justify more measurement?

It was repeated, not isolated. One smoke/debug trace is enough to justify a bounded measurement harness, but not enough to select implementation.

Is this a blocker to continued development, or just a known hot-path risk?

It is a known hot-path risk. It does not block host-boundary deploy-guidance handoff or unrelated bounded development, as long as future work does not change snapshot/cache/queue/WebSocket behavior without new evidence.

Should the next development lane be a bounded measurement harness, a planning checkpoint, no work for now, or implementation later?

Use a bounded measurement harness next if the developer wants to act on the latency signal. If the developer does not want latency work before deploy approval, pause/no immediate latency work is also acceptable. Do not start implementation from this checkpoint.

What exact next work item should be recommended?

`WORK-20260701-snapshot-lan-hot-path-latency-measurement-harness`

Recommended goal:

Create or run a bounded, timeout-controlled measurement harness for an already-running local server that captures route-level and trace-level timing for snapshot/LAN hot paths, especially `/api/dm/combat?workspace=dmcontrol`, standalone LAN snapshot broadcasts, `lan.snapshot.build`, `_dm_tactical_snapshot`, `_dm_console_snapshot_payload`, `_dm_console_snapshot`, health/readiness responsiveness during the same window, and WebSocket/client activity context. The item must produce evidence only and must not change app behavior.

Allowed implementation shape for that future item, if explicitly opened:

- scripts/docs-only harness work is acceptable
- no app-runtime behavior changes
- no route, payload, cache, TTL, snapshot schema, WebSocket, queue, launch, readiness, production, or gameplay changes
- all diagnostics must be timeout-bounded

What should remain forbidden until better evidence exists?

Forbidden until a measurement harness or equally strong evidence exists:

- snapshot/LAN latency implementation
- cache ownership moves
- TTL changes
- snapshot schema or response payload changes
- static hydration changes
- snapshot warm-up changes
- broader `run_in_threadpool` adoption
- lower-level tactical/LAN offload
- queue-wait or async command behavior changes
- WebSocket, auth, claims, reconnect, or hidden-information changes
- route registration or route body movement
- launch, lifespan, readiness, shutdown, or `UvicornServerHost` changes
- gameplay, persistence, production topology, deploy, restart, SSH, commit, or push work

## Ledger Update

`docs/work_items/current_work.md` was returned to Idle with no active work item.

The completed table now includes this checkpoint. The allowed next action is Orchestrator/developer deploy-prep review using the completed deploy-guidance checkpoint, pause/no further migration work, or open `WORK-20260701-snapshot-lan-hot-path-latency-measurement-harness` if the developer wants bounded latency measurement before any snapshot/LAN implementation decision.

## Validation

Required validation commands:

- `git status --short`
- `timeout 10s git diff --check`

No tests, smoke, server commands, deploy commands, production commands, service restarts, SSH, pushes, or commits were run by this checkpoint.

Results are recorded in the final agent report.
