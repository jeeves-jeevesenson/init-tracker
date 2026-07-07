# WORK-20260707-dm-console-combat-service-read-model-implementation-decision-planning-checkpoint

Status: Completed

## Goal

Complete a bounded Codex docs/planning implementation-decision checkpoint for the DM console combat service/read-model latency isolated by the targeted smoke evidence at commit `b486764`, preserving instrumentation commit `e05fb8f`.

This checkpoint did not implement a latency fix, optimize app code, edit tests, edit scripts, edit logs, start the server, run smoke, deploy, restart services, SSH, push, commit, alter production topology, patch the small smoke bug, or change routes, route registration, route bodies, response payload schemas, snapshot schemas, combat state semantics, turn order, initiative ordering, hidden-information rules, monster visibility, tactical visibility, map/terrain behavior, monster control, encounter state semantics, player command behavior, combat mutation behavior, gameplay/resource behavior, resource-pools behavior, cache behavior, TTLs, static hydration, startup static-fields behavior, WebSocket behavior, queue behavior, command semantics, persistence, launch commands, lifespan behavior, readiness behavior, shutdown semantics, deploy command, restart behavior, SSH behavior, or production topology.

## Files Inspected

- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260702-dm-console-combat-read-model-targeted-smoke-evidence-capture.md`
- `docs/planning/living_docs/dm_console_combat_read_model_targeted_smoke_evidence_capture_20260707.md`
- `docs/runtime_reports/dm_console_combat_read_model_targeted_smoke_evidence_20260707.md`
- `docs/work_items/completed/WORK-20260702-dm-console-combat-read-model-targeted-instrumentation-evidence.md`
- `docs/runtime_reports/dm_console_combat_read_model_targeted_instrumentation_evidence_20260702.md`
- `docs/work_items/completed/WORK-20260702-dm-console-combat-route-latency-planning-evidence-checkpoint.md`
- `docs/runtime_reports/dm_console_combat_route_latency_planning_evidence_20260702.md`
- `docs/work_items/completed/WORK-20260702-snapshot-lan-resource-pools-ttl-rebuild-smoke-evidence-capture.md`
- `docs/runtime_reports/snapshot_lan_resource_pools_ttl_rebuild_smoke_evidence_20260702.md`
- `logs/smoke/WORK-20260702-dm-console-combat-read-model-targeted-smoke-evidence-capture_smoke-server_20260707-105332.log`, using `head` and `tail`
- `logs/debug-trace-20260707-105332.jsonl`, using `head`, `tail`, `grep`, and bounded `grep | head` span samples
- `scripts/snapshot_lan_hot_path_latency_harness.py`
- `dnd_initative_tracker.py`, limited to `/api/dm/combat`, `_dm_console_snapshot()`, `_dm_console_snapshot_payload()`, the `dm.console.combat_snapshot` / `dm.console.combat_snapshot.service_call` spans, and direct helper calls used by the service snapshot as needed
- `combat_service.py`, limited to `CombatService.combat_snapshot()`

No `majorTODO.md`, old plans, unrelated runtime reports, unrelated logs, browser assets, tests, production files, `docs/bug_reports/inbox/BUG-20260626-dmcontrol-terrain-not-visible.md`, or `logs/context/` files were inspected or edited.

## Files Changed

- `docs/work_items/current_work.md`
- `docs/work_items/active/WORK-20260707-dm-console-combat-service-read-model-implementation-decision-planning-checkpoint.md` (created while active, removed at completion)
- `docs/work_items/completed/WORK-20260707-dm-console-combat-service-read-model-implementation-decision-planning-checkpoint.md`
- `docs/planning/living_docs/dm_console_combat_service_read_model_implementation_decision_planning_checkpoint_20260707.md`
- `docs/runtime_reports/dm_console_combat_service_read_model_implementation_decision_planning_20260707.md`

## Evidence Facts Recorded

- Latest accepted evidence commit: `b486764`
- Latest instrumentation commit: `e05fb8f`
- Targeted smoke trace: `logs/debug-trace-20260707-105332.jsonl`
- Smoke log: `logs/smoke/WORK-20260702-dm-console-combat-read-model-targeted-smoke-evidence-capture_smoke-server_20260707-105332.log`
- Harness parsed `45,277` valid JSON objects and `0` malformed/non-object lines.
- Load shape: `112` combatants, `10` players, `102` monsters.
- `combat_service.combat_snapshot`: count `44`, p50 `269.380 ms`, p95 `500.641 ms`, max `660.390 ms`.
- `dm.console.combat_snapshot.service_call`: count `41`, p50 `270.945 ms`, p95 `501.904 ms`, max `660.880 ms`.
- `dm.console.combat_snapshot.copy`: count `41`, p50 `0.080 ms`, p95 `0.719 ms`, max `0.910 ms`.
- `dm.console.snapshot.payload`: count `36`, p50 `328.183 ms`, p95 `647.329 ms`, max `664.048 ms`.
- `dm.console.route_read_snapshot`: count `25`, p50 `352.772 ms`, p95 `851.266 ms`, max `987.922 ms`.
- `http.request:/api/dm/combat`: count `25`, p50 `385.621 ms`, p95 `936.898 ms`, max `1039.199 ms`.
- `dm.console.route_payload_proxy` p95 `0.514 ms`.
- `dm.console.snapshot.cache_check` p95 `0.914 ms`.
- `dm.console.payload.tactical_merge` p95 `4.043 ms`.
- `dm.console.payload.pending_prompts` p95 `0.927 ms`.
- `dm.console.payload.size_proxy` p95 `1.000 ms`.
- `lan.snapshot.resource_pools` p95 `14.497 ms`.
- `lan.snapshot.units` p95 `21.864 ms`.
- Resource-pools remains closed.
- Startup-only `lan.snapshot.static_fields` remains separate and deferred.
- The small smoke bug remains deferred separately.

## Decision

Recommend a future narrow implementation slice.

`combat_service.combat_snapshot` / `dm.console.combat_snapshot.service_call` is isolated enough to justify implementation because the accepted trace shows the service call p50/p95/max nearly matching the primary service span and driving the wrapper/route-visible rows, while the measured wrapper, cache, copy, merge, proxy, resource-pools, and LAN unit spans are too small to be primary bottlenecks.

The future implementation seam should be:

`CombatService.combat_snapshot()` service-internal read-model composition, limited to reducing repeated per-call/per-combatant derived helper work with a transient per-call composition context or equivalent helper/pre-indexing approach. The output dictionary shape, keys, values, ordering, visibility behavior, hidden-information behavior, and gameplay semantics must remain identical.

## Ruled-Out Primary Bottlenecks

The accepted evidence rules out these as primary next implementation targets:

- `dm.console.route_payload_proxy`
- `dm.console.combat_snapshot.copy`
- `dm.console.snapshot.cache_check`
- `dm.console.payload.tactical_merge`
- `dm.console.payload.pending_prompts`
- `dm.console.payload.size_proxy`
- `lan.snapshot.resource_pools`
- `lan.snapshot.units`
- route infrastructure, route registration, and route body placement

## Load-Shape Interpretation

The `112`-combatant / `102`-monster shape points to service read-model composition under scale. `CombatService.combat_snapshot()` builds one row per combatant and derives per-row role, passive perception, defenses, state markers, AC modifiers, conditions, monster resources, and turn metadata from tracker state. The evidence supports a class of issue around repeated per-combatant derived helper work and payload construction rather than resource-pools, cache checks, tactical merge, route payload proxy bookkeeping, or route infrastructure.

## Future Implementation Scope

Recommended next work item:

`WORK-20260707-dm-console-combat-service-read-model-composition-minimal-implementation`

Recommended type:

Narrow implementation.

Code areas to inspect first:

- `combat_service.py` at `CombatService.combat_snapshot()`
- `dnd_initative_tracker.py` at `_dm_console_snapshot_payload()` and `_dm_console_snapshot()`
- `dnd_initative_tracker.py` helper seams directly used by `CombatService.combat_snapshot()` only as needed: display order, passive perception, defense sets, AC modifiers, up-next turn peek, and battle-log tail reading
- `tests/test_server_runtime.py`
- new `tests/test_combat_service.py` if service-level contract coverage is added

Allowed future implementation edit list:

- `combat_service.py`
- `dnd_initative_tracker.py`, only if a narrow read-only helper seam is required for `CombatService.combat_snapshot()`
- `tests/test_server_runtime.py`
- `tests/test_combat_service.py`, if focused service-contract coverage is added

Forbidden future implementation scope unless a later active packet explicitly changes it:

- route migration, route body movement, route registration changes, route infrastructure changes
- response payload/schema or snapshot schema changes
- cache behavior, cache ownership, TTL, resource-pools, static hydration, or startup static-fields changes
- WebSocket, queue, auth, claims, reconnect, command semantic, persistence, production topology, launch/readiness/shutdown, deploy/restart/SSH behavior changes
- visibility rules, hidden-information rules, monster visibility, tactical visibility, map/terrain behavior, monster control, encounter state semantics, player command behavior, combat mutation behavior, gameplay/resource behavior
- small smoke bug patching in this latency lane

## Validation Recommendation For Future Implementation

Future implementation should require:

- `py_compile` on edited Python files.
- Focused contract tests proving `CombatService.combat_snapshot()` output equivalence for representative players, monsters, conditions, resources, turn order, battle log, and current/up-next state.
- Focused DM console route snapshot regression if `dnd_initative_tracker.py` is touched.
- Existing harness run against the accepted trace to keep parser interpretation stable.
- Developer-owned post-implementation smoke/debug-trace capture and harness run before claiming latency improvement.

## Answers

1. Yes. The service call is isolated enough for a future narrow implementation slice.
2. Target `CombatService.combat_snapshot()` service-internal read-model composition.
3. Route payload proxy, copy, cache check, tactical merge, pending prompts, size proxy, resource-pools, LAN units, and route infrastructure are ruled out as primary bottlenecks.
4. The `112`/`102` shape points to scale/read-model composition, repeated per-combatant derived helper work, and payload construction.
5. Inspect `combat_service.py` first, then the narrow DM console wrapper and direct tracker helpers listed above.
6. Allow edits only to `combat_service.py`, narrowly to `dnd_initative_tracker.py` if needed, and focused tests.
7. Keep all route, payload/schema, cache/TTL/resource-pools/static-fields, WebSocket/queue/auth/persistence/production, visibility, hidden-information, map, monster-control, combat mutation, and gameplay behavior changes forbidden.
8. Require focused compile, service contract tests, DM console route regression if touched, harness parsing, and developer-owned post-implementation smoke/harness evidence.
9. Recommend implementation next, not more evidence, not narrower planning, and not standalone instrumentation.
10. Yes. Startup static-fields and the small smoke bug remain deferred separately.
11. Recommended next item is `WORK-20260707-dm-console-combat-service-read-model-composition-minimal-implementation`.

## Ledger Update

`docs/work_items/current_work.md` was returned to Idle with no active work item.

The completed table now includes this implementation-decision planning checkpoint. The allowed next action is a narrow combat service read-model composition implementation item if latency work continues, Orchestrator/developer deploy-prep review if still desired, pause/no further migration, or a separate deferred bug-capture item for the small smoke bug.

`majorTODO.md` was not inspected or updated because it was outside this task's allowed edit list.

## Validation

Required validation commands:

```bash
.venv/bin/python scripts/snapshot_lan_hot_path_latency_harness.py logs/debug-trace-20260707-105332.jsonl
timeout 10s git diff --check
git status --short
```

Results are recorded in the final agent report.
