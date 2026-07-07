# DM Console Combat Service Read-Model Implementation-Decision Planning Checkpoint - 2026-07-07

## Scope

This document records a bounded Codex docs/planning implementation-decision checkpoint for the DM console combat service/read-model latency isolated by targeted smoke evidence.

No app implementation, optimization, tests, script edits, log edits, server start, smoke run, deploy, restart, SSH, push, commit, route change, route registration change, route body movement, response payload/schema change, snapshot schema change, resource-pools/cache/TTL/static-fields change, WebSocket/queue/auth/claims/reconnect change, persistence change, production topology change, visibility/hidden-information change, map/terrain/monster-control change, encounter state change, small smoke bug patch, or gameplay behavior change occurred.

## Evidence Inputs

- Latest accepted evidence commit: `b486764`
- Latest instrumentation commit: `e05fb8f`
- Smoke log: `logs/smoke/WORK-20260702-dm-console-combat-read-model-targeted-smoke-evidence-capture_smoke-server_20260707-105332.log`
- Targeted debug trace: `logs/debug-trace-20260707-105332.jsonl`

The smoke log records headless tracker startup, debug trace creation, `/dm` and `/` advertisement, LAN hoist on port `8787`, browser LAN sessions, one LAN disconnect, and Dorian claim. The captured smoke tail does not show unclaim before `Ctrl+C`.

The trace tail records steady rows with `112` combatants, `10` players, and `102` monsters.

## Harness Evidence

The harness parsed `45,277` valid JSON objects and `0` malformed/non-object lines.

Primary remaining rows:

| Target | Count | p50 | p95 | Max |
| --- | ---: | ---: | ---: | ---: |
| `combat_service.combat_snapshot` | `44` | `269.380 ms` | `500.641 ms` | `660.390 ms` |
| `dm.console.combat_snapshot.service_call` | `41` | `270.945 ms` | `501.904 ms` | `660.880 ms` |
| `dm.console.snapshot.payload` | `36` | `328.183 ms` | `647.329 ms` | `664.048 ms` |
| `dm.console.route_read_snapshot` | `25` | `352.772 ms` | `851.266 ms` | `987.922 ms` |
| `http.request:/api/dm/combat` | `25` | `385.621 ms` | `936.898 ms` | `1039.199 ms` |

Ruled-out primary rows:

| Target | p95 |
| --- | ---: |
| `dm.console.route_payload_proxy` | `0.514 ms` |
| `dm.console.snapshot.cache_check` | `0.914 ms` |
| `dm.console.combat_snapshot.copy` | `0.719 ms` |
| `dm.console.payload.tactical_merge` | `4.043 ms` |
| `dm.console.payload.pending_prompts` | `0.927 ms` |
| `dm.console.payload.size_proxy` | `1.000 ms` |
| `lan.snapshot.resource_pools` | `14.497 ms` |
| `lan.snapshot.units` | `21.864 ms` |

Startup-only `lan.snapshot.static_fields` remains separate and deferred.

## Source-Seam Findings

The route/read wrapper remains a symptom, not the selected implementation seam:

- `GET /api/dm/combat` builds a `RuntimeSnapshotRequest(snapshot_type="dm_console")`, forwards `include_tactical`, and reads through the existing threadpool route helper.
- `_dm_console_snapshot()` does a short existing cache check before delegating to `_dm_console_snapshot_payload()`.
- `_dm_console_snapshot_payload()` wraps `dm_service.combat_snapshot()` in `dm.console.combat_snapshot.service_call`, copies the result cheaply, optionally adds tactical data, merges pending prompts, and records a size proxy.
- The cheap wrapper spans in the accepted trace rule out cache check, copy, tactical merge, pending prompts, size proxy, and route payload proxy as primary targets.

The isolated implementation seam is inside `CombatService.combat_snapshot()`:

- It constructs a fresh DM combat read-model payload from tracker state on every service call.
- It builds ordered combatants, then emits one row per combatant.
- Per combatant, it derives role, passive perception, defenses, state markers, AC modifier, conditions, monster resources, speed values, concentration state, identity fields, and current-turn markers.
- Direct helper calls include tracker display ordering, passive perception, defense set construction, AC modifier collection, next-turn peek, and battle-log tail reading.
- The `112`-combatant / `102`-monster shape makes the expensive class most likely per-call read-model composition with repeated per-combatant derived helper work and payload construction. The accepted evidence does not point at route infrastructure, response payload proxy work, resource-pools, LAN units, cache lookup, copy, or tactical merge as the primary issue.

## Implementation Decision

`combat_service.combat_snapshot` / `dm.console.combat_snapshot.service_call` is isolated enough to justify a future narrow implementation slice.

The future implementation should target a behavior-preserving service-internal read-model composition seam:

`CombatService.combat_snapshot()` should be refactored only enough to reduce repeated per-call/per-combatant derived-read work during construction of the existing DM combat snapshot. The preferred shape is a transient per-call composition context or helper local to the service that pre-reads or pre-indexes data already used by the method, then emits the same dictionary shape, keys, values, ordering, and hidden-information behavior.

The implementation must not introduce cross-snapshot stale data, cache TTLs, payload/schema changes, route changes, gameplay-rule changes, or dual ownership. Any reuse must be limited to the duration of one `combat_snapshot()` call unless a later active item explicitly authorizes broader cache behavior.

## Questions Answered

1. Yes. The accepted trace isolates `combat_service.combat_snapshot` / `dm.console.combat_snapshot.service_call` well enough for a future narrow behavior-preserving implementation slice.
2. Target `CombatService.combat_snapshot()` service-internal read-model composition. Use a transient per-call composition context/pre-indexing seam to reduce repeated per-combatant derived helper work while preserving the exact output contract.
3. Route payload proxy, combat snapshot copy, cache check, tactical merge, pending prompts, size proxy, resource-pools, LAN units, and route infrastructure are ruled out as primary bottlenecks by the accepted p95 rows.
4. The `112`-combatant / `102`-monster shape points to scale/read-model composition, repeated per-combatant helper work, and payload construction. Response serialization may still contribute to route-visible `http.request:/api/dm/combat`, but the primary measured child is the service call.
5. Future implementation should inspect `combat_service.py` at `CombatService.combat_snapshot()` first, then `dnd_initative_tracker.py` at `_dm_console_snapshot_payload()`, `_dm_console_snapshot()`, and the direct helper calls used by the service snapshot only as needed.
6. Future implementation should be allowed to edit `combat_service.py`, `dnd_initative_tracker.py` only if a narrow read-only helper seam is necessary, `tests/test_server_runtime.py`, and a new `tests/test_combat_service.py` if focused service contract coverage is needed.
7. Future work should keep routes, route registration, route bodies, payload schemas, snapshot schemas, cache behavior, TTLs, resource-pools behavior, startup static-fields behavior, static hydration, WebSockets, queues, auth/claims/reconnect, persistence, visibility rules, hidden-information rules, monster visibility, tactical visibility, map/terrain behavior, monster control, encounter state semantics, player command behavior, combat mutation behavior, production topology, deploy/restart/SSH behavior, and gameplay/resource behavior forbidden.
8. Future validation should require compile checks for edited Python files, focused contract/regression tests that prove `CombatService.combat_snapshot()` output equivalence for representative players/monsters/conditions/resources/turn order, focused DM console route snapshot regression if `dnd_initative_tracker.py` is touched, and developer-owned smoke/harness evidence on a fresh trace after implementation.
9. The next work item should be implementation, not more evidence, not another planning checkpoint, and not standalone instrumentation. Additional internal instrumentation is optional only if the implementation slice cannot preserve behavior under focused tests.
10. Startup-only `lan.snapshot.static_fields` and the small smoke bug should remain deferred separately.
11. Recommended next work item: `WORK-20260707-dm-console-combat-service-read-model-composition-minimal-implementation`.

## Recommended Future Work Item

`WORK-20260707-dm-console-combat-service-read-model-composition-minimal-implementation`

Type: narrow implementation.

Goal: Implement a behavior-preserving reduction of per-call/per-combatant read-model composition cost inside `CombatService.combat_snapshot()` under the existing `combat_service.combat_snapshot` / `dm.console.combat_snapshot.service_call` seam. Preserve exact snapshot shape, route behavior, cache behavior, hidden-information behavior, visibility rules, combat semantics, and gameplay/resource behavior.

## Future Validation Requirements

Recommended focused validation for the future implementation:

```bash
.venv/bin/python -m py_compile combat_service.py dnd_initative_tracker.py
timeout 90s .venv/bin/python -m pytest tests/test_server_runtime.py tests/test_combat_service.py
.venv/bin/python scripts/snapshot_lan_hot_path_latency_harness.py logs/debug-trace-20260707-105332.jsonl
timeout 10s git diff --check
git status --short
```

If `tests/test_combat_service.py` is not created by the implementation, omit that path and run the exact focused test file(s) changed or relied on. After implementation, developer-owned smoke should capture a fresh debug trace and rerun the harness against that fresh trace before claiming latency improvement.

## Deferred Scope

Remain deferred until a new active work item explicitly authorizes the specific change:

- route migration, route body movement, or route registration changes
- response payload/schema or snapshot schema changes
- resource-pools/cache/TTL/static-fields changes
- static hydration or startup static-fields work
- broader offload, facade-owned cache, or route infrastructure changes
- WebSocket, queue, auth, claims, reconnect, command semantic, persistence, production, launch/readiness/shutdown, deploy/restart/SSH, or topology changes
- visibility, hidden-information, map/terrain, monster-control, encounter-state, player-command, combat-mutation, or gameplay/resource behavior changes
- patching the small smoke bug inside this latency lane
