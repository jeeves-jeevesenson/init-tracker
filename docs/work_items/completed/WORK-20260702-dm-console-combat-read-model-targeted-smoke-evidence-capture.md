# WORK-20260702-dm-console-combat-read-model-targeted-smoke-evidence-capture

Status: Completed

## Goal

Complete a bounded Codex docs/evidence checkpoint for the DM console combat read-model targeted smoke/debug trace captured after instrumentation commit `e05fb8f`.

This was docs/evidence only. It did not implement a fix, optimize latency, edit app code, edit tests, edit logs, start the server, run browser smoke, deploy, restart services, SSH, push, commit, alter production topology, patch the small smoke bug, or change routes, route registration, route bodies, payload schemas, snapshot schemas, resource-pools behavior, cache behavior, TTLs, static hydration, startup static-fields behavior, WebSocket behavior, queue behavior, command semantics, persistence, visibility rules, hidden-information rules, map/terrain behavior, monster control, encounter state semantics, launch commands, lifespan behavior, readiness behavior, shutdown semantics, or gameplay behavior.

## Files Inspected

- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260702-dm-console-combat-read-model-targeted-instrumentation-evidence.md`
- `docs/planning/living_docs/dm_console_combat_read_model_targeted_instrumentation_evidence_20260702.md`
- `docs/runtime_reports/dm_console_combat_read_model_targeted_instrumentation_evidence_20260702.md`
- `docs/work_items/completed/WORK-20260702-dm-console-combat-route-latency-planning-evidence-checkpoint.md`
- `docs/runtime_reports/dm_console_combat_route_latency_planning_evidence_20260702.md`
- `docs/work_items/completed/WORK-20260702-snapshot-lan-resource-pools-ttl-rebuild-smoke-evidence-capture.md`
- `docs/runtime_reports/snapshot_lan_resource_pools_ttl_rebuild_smoke_evidence_20260702.md`
- `logs/smoke/WORK-20260702-dm-console-combat-read-model-targeted-smoke-evidence-capture_smoke-server_20260707-105332.log`, using `head` and `tail`
- `logs/debug-trace-20260707-105332.jsonl`, using `head`, `tail`, and `grep`
- `scripts/snapshot_lan_hot_path_latency_harness.py`

`dnd_initative_tracker.py` was not inspected because the named docs, script, smoke log, and trace excerpts were sufficient to interpret the evidence. No `majorTODO.md`, old plans, unrelated runtime reports, unrelated logs, browser assets, app code, tests, production files, `docs/bug_reports/inbox/BUG-20260626-dmcontrol-terrain-not-visible.md`, or `logs/context/` files were inspected or edited.

## Files Changed

- `docs/work_items/current_work.md`
- `docs/work_items/active/WORK-20260702-dm-console-combat-read-model-targeted-smoke-evidence-capture.md` (created while active, removed at completion)
- `docs/work_items/completed/WORK-20260702-dm-console-combat-read-model-targeted-smoke-evidence-capture.md`
- `docs/planning/living_docs/dm_console_combat_read_model_targeted_smoke_evidence_capture_20260707.md`
- `docs/runtime_reports/dm_console_combat_read_model_targeted_smoke_evidence_20260707.md`

## Evidence Files

- Smoke log: `logs/smoke/WORK-20260702-dm-console-combat-read-model-targeted-smoke-evidence-capture_smoke-server_20260707-105332.log`
- Debug trace: `logs/debug-trace-20260707-105332.jsonl`

## Smoke Evidence Decision

The targeted smoke proves the basic headless/browser/LAN path still works with instrumentation commit `e05fb8f`:

- Headless tracker started.
- Debug trace was created at `logs/debug-trace-20260707-105332.jsonl`.
- DM operator surface was advertised on `/dm`.
- Player LAN surface was advertised on `/`.
- LAN server was hoisted on port `8787`.
- Browser LAN sessions connected.
- One LAN session disconnected.
- One LAN session claimed Dorian.
- The captured smoke tail does not show unclaim before `Ctrl+C`.
- The trace tail shows `http.request.end` for `/api/dm/combat` with `status_code=200` and `response_bytes=303029`.

This proves the captured startup, LAN session, Dorian claim, and DM combat read path still function in the smoke run. It does not claim broader gameplay, unclaim coverage, full disconnect semantics, production readiness, or browser smoke coverage beyond the captured evidence.

## Harness Summary

The harness parsed `45,277` valid JSON objects with `0` malformed/non-object lines.

Steady rows show a load shape of `112` combatants, `10` players, and `102` monsters.

Key latency rows:

| Target | Count | p50 | p95 | Max | >=250ms | >=1000ms | Decision |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `_lan_snapshot` | `1140` | `4.443 ms` | `52.504 ms` | `24923.044 ms` | `4` | `1` | Mostly bounded in steady rows; one startup outlier remains separate. |
| `lan.snapshot.resource_pools` | `1140` | `0.084 ms` | `14.497 ms` | `806.993 ms` | `4` | `0` | Resource-pools remains closed. |
| `lan.snapshot.units` | `1140` | `1.811 ms` | `21.864 ms` | `51.668 ms` | `0` | `0` | Not the primary latency lane. |
| `_dm_console_snapshot` | `39` | `329.854 ms` | `648.836 ms` | `665.728 ms` | not primary | not primary | Wrapper around the payload/service path. |
| `_dm_console_snapshot_payload` | `41` | `326.950 ms` | `620.516 ms` | `663.121 ms` | not primary | not primary | Wrapper around combat service call plus cheap merge work. |
| `combat_service.combat_snapshot` | `44` | `269.380 ms` | `500.641 ms` | `660.390 ms` | primary | not primary | Primary remaining actionable span. |
| `dm.console.combat_snapshot` | `41` | `279.927 ms` | `504.178 ms` | `662.108 ms` | primary | not primary | Outer composition span that tracks the service call. |
| `dm.console.combat_snapshot.service_call` | `41` | `270.945 ms` | `501.904 ms` | `660.880 ms` | primary | not primary | Primary remaining actionable wrapper around the service call. |
| `dm.console.combat_snapshot.copy` | `41` | `0.080 ms` | `0.719 ms` | `0.910 ms` | `0` | `0` | Ruled out as primary. |
| `dm.console.route_read_snapshot` | `25` | `352.772 ms` | `851.266 ms` | `987.922 ms` | wrapper | wrapper | Route-side wrapper around the read path. |
| `dm.console.route_payload_proxy` | `25` | `0.186 ms` | `0.514 ms` | `25.874 ms` | `0` | `0` | Ruled out as primary. |
| `dm.console.snapshot.cache_check` | `39` | `0.099 ms` | `0.914 ms` | `15.383 ms` | `0` | `0` | Ruled out as primary. |
| `dm.console.snapshot.payload` | `36` | `328.183 ms` | `647.329 ms` | `664.048 ms` | wrapper | wrapper | Payload wrapper around the service/read-model path. |
| `dm.console.payload.tactical_merge` | `41` | `0.074 ms` | `4.043 ms` | `21.184 ms` | `0` | `0` | Ruled out as primary. |
| `dm.console.payload.pending_prompts` | `41` | `0.093 ms` | `0.927 ms` | `1.099 ms` | `0` | `0` | Ruled out as primary. |
| `dm.console.payload.size_proxy` | `41` | `0.157 ms` | `1.000 ms` | `1.467 ms` | `0` | `0` | Ruled out as primary. |
| `http.request:/api/dm/combat` | `25` | `385.621 ms` | `936.898 ms` | `1039.199 ms` | route-visible | route-visible | Route-visible symptom, not the next service seam itself. |

Startup-only `lan.snapshot.static_fields` remains a separate startup outlier with max `24475.459 ms`.

## Span Classification

Primary remaining actionable span:

- `combat_service.combat_snapshot` / `dm.console.combat_snapshot.service_call`. The service call p50/p95/max nearly match `dm.console.combat_snapshot` and drive most of `_dm_console_snapshot_payload`, `_dm_console_snapshot`, and route read timing.

Wrappers or route-visible symptoms:

- `_dm_console_snapshot_payload`
- `_dm_console_snapshot`
- `dm.console.snapshot.payload`
- `dm.console.route_read_snapshot`
- `http.request:/api/dm/combat`

Ruled out as primary bottlenecks:

- `dm.console.route_payload_proxy`
- `dm.console.combat_snapshot.copy`
- `dm.console.snapshot.cache_check`
- `dm.console.payload.tactical_merge`
- `dm.console.payload.pending_prompts`
- `dm.console.payload.size_proxy`
- `lan.snapshot.resource_pools`
- `lan.snapshot.units`

The `112`-combatant / `102`-monster load shape points toward scale/read-model composition in the combat service path, not route infrastructure, response proxy bookkeeping, resource-pools, cache checks, or payload merge wrappers.

## Answers

1. The targeted smoke proves headless startup, debug-trace creation, `/dm` and `/` advertisement, LAN hoist on port `8787`, browser LAN sessions, one LAN disconnect, Dorian claim, and successful `/api/dm/combat` HTTP 200 still work in this run.
2. Primary bottlenecks are `combat_service.combat_snapshot`, `dm.console.combat_snapshot.service_call`, and the matching outer `dm.console.combat_snapshot` row. `_dm_console_snapshot_payload`, `_dm_console_snapshot`, `dm.console.snapshot.payload`, `dm.console.route_read_snapshot`, and `http.request:/api/dm/combat` are wrappers or route-visible symptoms.
3. Yes. `combat_service.combat_snapshot` / `dm.console.combat_snapshot.service_call` is now the primary remaining actionable span.
4. Yes. Route payload proxy, copy, cache check, tactical merge, pending prompts, and size proxy are all too small to be primary bottlenecks in this trace.
5. Yes. The `112`-combatant / `102`-monster load shape points toward scale/read-model composition.
6. Direct implementation is not justified by this docs/evidence task. The next item should be a combat service/read-model implementation-decision planning checkpoint because the evidence isolates the expensive service call but does not document an already-clear behavior-preserving seam.
7. Yes. Resource-pools should remain closed.
8. Yes. Startup-only `lan.snapshot.static_fields` should remain deferred separately.
9. Yes. The small smoke bug should remain deferred as separate bug-capture scope and was not patched.
10. Recommended next work item: `WORK-20260707-dm-console-combat-service-read-model-implementation-decision-planning-checkpoint`.

## Decision

Keep instrumentation commit `e05fb8f`.

Do not authorize direct implementation from this checkpoint.

The remaining latency is isolated enough for a narrow implementation-decision planning checkpoint focused on the combat service/read-model path, but the task did not inspect or authorize service-internal app-code changes. The next planning checkpoint should decide whether the safe seam is service-internal composition, data pre-indexing, read-model caching, payload assembly strategy, or another behavior-preserving option after inspecting the specifically scoped service code.

## Recommended Next Work

Recommended next work item:

`WORK-20260707-dm-console-combat-service-read-model-implementation-decision-planning-checkpoint`

Recommended type:

Planning / implementation decision, not implementation.

Recommended goal:

Use the accepted targeted smoke evidence and narrowly scoped combat service/read-model code inspection to select or reject a behavior-preserving implementation seam for the `combat_service.combat_snapshot` / `dm.console.combat_snapshot.service_call` latency. The checkpoint should preserve routes, route registration, route bodies, response payload schemas, snapshot schemas, resource-pools behavior, cache behavior, TTLs, startup static-fields behavior, WebSockets, queues, auth/claims/reconnect, persistence, visibility, hidden-information rules, map/terrain behavior, monster control, encounter state semantics, production topology, deployment behavior, and gameplay semantics unless a later active item explicitly scopes a change.

## Deferred Scope

Remain deferred until explicitly authorized by a new active work item:

- direct combat service/read-model implementation
- route migration, route body movement, or route registration changes
- response payload/schema or snapshot schema changes
- resource-pools/cache/TTL/static-fields changes
- static hydration or startup static-fields work
- broader offload or facade-owned cache
- WebSocket, queue, auth, claims, reconnect, command semantic, persistence, production, launch/readiness/shutdown, or gameplay changes
- browser smoke, server start, deploy, restart, SSH, push, commit, or topology changes
- patching the small smoke bug inside this latency lane

## Ledger Update

`docs/work_items/current_work.md` was returned to Idle with no active work item.

The completed table now includes this targeted smoke evidence checkpoint. The allowed next action is a narrow combat service/read-model implementation-decision planning checkpoint if latency work continues, Orchestrator/developer deploy-prep review if still desired, pause/no further migration, or a separate deferred bug-capture item for the small smoke bug.

`majorTODO.md` was not inspected or updated because it was outside this task's allowed edit list.

## Validation

Required validation commands:

```bash
.venv/bin/python scripts/snapshot_lan_hot_path_latency_harness.py logs/debug-trace-20260707-105332.jsonl
timeout 10s git diff --check
git status --short
```

Results are recorded in the final agent report.
