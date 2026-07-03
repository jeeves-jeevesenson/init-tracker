# WORK-20260702-snapshot-lan-resource-pools-ttl-rebuild-smoke-evidence-capture

Status: Completed

## Goal

Complete a bounded Codex docs/evidence checkpoint for the post-implementation smoke evidence from commit `d16a2aa`.

This checkpoint recorded what the fresh smoke trace proves, compared the new `lan.snapshot.resource_pools` latency against the prior `20260702-123404` evidence, and selected the next safe step. It did not implement another fix, optimize latency, edit app code, edit tests, edit logs, start the server, run browser smoke, deploy, restart services, SSH, push, commit, alter production topology, patch the small smoke bug, or change routes, route registration, route bodies, payloads, snapshot schemas, cache behavior, TTLs, static hydration, WebSockets, auth/claims/reconnect, queue behavior, command semantics, persistence, or gameplay behavior.

## Files Inspected

- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260702-snapshot-lan-resource-pools-ttl-rebuild-minimal-implementation.md`
- `docs/planning/living_docs/snapshot_lan_resource_pools_ttl_rebuild_minimal_implementation_20260702.md`
- `docs/runtime_reports/snapshot_lan_resource_pools_ttl_rebuild_minimal_implementation_20260702.md`
- `docs/work_items/completed/WORK-20260702-snapshot-lan-resource-pools-ttl-rebuild-planning-checkpoint.md`
- `docs/planning/living_docs/snapshot_lan_resource_pools_ttl_rebuild_planning_checkpoint_20260702.md`
- `docs/runtime_reports/snapshot_lan_resource_pools_hot_path_cache_smoke_evidence_20260702.md`
- `docs/work_items/completed/WORK-20260702-snapshot-lan-resource-pools-hot-path-cache-smoke-evidence-capture.md`
- `logs/smoke/WORK-20260702-snapshot-lan-resource-pools-ttl-rebuild-smoke-evidence-capture_smoke-server_20260702-193152.log`, using `head` and `tail` only
- `logs/debug-trace-20260702-193152.jsonl`, using `head`, `tail`, and `grep` only
- `scripts/snapshot_lan_hot_path_latency_harness.py`

No `majorTODO.md`, old plans, unrelated runtime reports, unrelated logs, browser assets, app code, tests, production files, `docs/bug_reports/inbox/BUG-20260626-dmcontrol-terrain-not-visible.md`, or `logs/context/` files were inspected or edited.

## Files Changed

- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260702-snapshot-lan-resource-pools-ttl-rebuild-smoke-evidence-capture.md`
- `docs/planning/living_docs/snapshot_lan_resource_pools_ttl_rebuild_smoke_evidence_capture_20260702.md`
- `docs/runtime_reports/snapshot_lan_resource_pools_ttl_rebuild_smoke_evidence_20260702.md`

No active work item copy was left after completion.

## Smoke Evidence Decision

This checkpoint used the fresh evidence run at `20260702-193152` for implementation commit `d16a2aa`.

The smoke log proves the basic headless/browser/LAN path still works after the `ttl_rebuild` base-normalization refinement:

- Headless tracker started.
- Debug trace was created at `logs/debug-trace-20260702-193152.jsonl`.
- DM operator surface was advertised on `/dm`.
- Player LAN surface was advertised on `/`.
- LAN server was hoisted on port `8787`.
- Browser LAN session connected from `10.3.25.162`.
- The LAN session claimed Dorian.
- The pasted smoke tail does not show an unclaim or disconnect before `Ctrl+C`.

This run proves fresh LAN startup, connection, and one player claim path for Dorian. It does not claim broader gameplay coverage, unclaim coverage, disconnect coverage, or browser smoke beyond what the captured log shows.

## Post-Implementation Latency Decision

The harness parsed `57,592` valid JSON objects with `0` malformed/non-object lines.

Key harness rows:

- `_lan_snapshot`: count `359`, p50 `59.421 ms`, p95 `247.959 ms`, max `24782.192 ms`, `17` samples at or above `250 ms`, `2` at or above `1000 ms`.
- `lan.snapshot.resource_pools`: count `359`, p50 `0.309 ms`, p95 `137.346 ms`, max `1006.718 ms`, `4` samples at or above `250 ms`, `1` at or above `1000 ms`.
- `dm.tactical.from_lan_snapshot`: count `32`, p50 `0.108 ms`, p95 `22.713 ms`, max `37.688 ms`.
- `lan.snapshot.units`: count `359`, p50 `41.883 ms`, p95 `47.763 ms`, max `89.288 ms`.
- `dm.console.combat_snapshot`: count `54`, p50 `839.307 ms`, p95 `2038.109 ms`, max `2204.090 ms`.
- `http.request:/api/dm/combat`: count `30`, p50 `1003.165 ms`, p95 `3454.867 ms`, max `4262.795 ms`.

The new load shape was much heavier than the prior comparator. Caller/context rows show steady-state samples with `212` combatants, `10` players, and `202` monsters.

Compared with the prior `20260702-123404` post-cache evidence, `lan.snapshot.resource_pools` improved materially:

- p95 improved from `759.372 ms` to `137.346 ms`.
- max improved from `2836.852 ms` to `1006.718 ms`.
- samples at or above `250 ms` improved from `83` to `4`.
- samples at or above `1000 ms` improved from `2` to `1`.
- p50 moved from `0.092 ms` to `0.309 ms`, which is still sub-millisecond and not the decision driver.

The trace tail also shows `resource_pool_result=ttl_rebuild_base_cache_all_hit` with `lan.snapshot.resource_pools` around `123.166 ms` in a `212`-combatant state, so the new base-normalization reuse is being exercised in the expected lane.

The remaining startup-only `lan.snapshot.static_fields` max is still separate. Its max remains startup-shaped at `24337.370 ms` and was not touched by this checkpoint.

## Answers

1. The post-implementation smoke proves headless startup, debug-trace creation, `/dm` and `/` advertisement, LAN hoist on port `8787`, browser LAN session connection from `10.3.25.162`, and Dorian claim still work for commit `d16a2aa`.
2. Yes. The `d16a2aa` `ttl_rebuild` refinement improved `lan.snapshot.resource_pools` materially versus the prior `20260702-123404` evidence: p95 fell from `759.372 ms` to `137.346 ms`, and `>=250 ms` samples fell from `83` to `4`.
3. Yes. The improvement is strong enough to keep `d16a2aa`, especially because it occurred under a heavier `212`-combatant / `202`-monster load shape.
4. The next visible slow path is no longer resource-pools. The route-visible slow rows are `dm.console.combat_snapshot` and `http.request:/api/dm/combat`, while `lan.snapshot.units` is now a non-trivial but sub-100 ms LAN substep.
5. The heavier load shape strengthens the resource-pools keep decision because the improved p95 and slow-threshold counts held under more combatants. It also means the DM console route numbers should be treated as evidence for a planning/evidence checkpoint, not immediate implementation.
6. The next work item should be DM console combat route planning/evidence. It should not be another resource-pools refinement, LAN units implementation, or direct implementation from this checkpoint.
7. Yes. Startup-only `lan.snapshot.static_fields` should remain deferred separately.
8. Yes. The small smoke bug should remain deferred as separate bug-capture scope and was not patched.
9. Recommended next work item: `WORK-20260702-dm-console-combat-route-latency-planning-evidence-checkpoint`.

## Recommended Next Work

Recommended next work item:

`WORK-20260702-dm-console-combat-route-latency-planning-evidence-checkpoint`

Recommended type:

Docs/evidence planning checkpoint, not implementation.

Recommended goal:

Use the `20260702-193152` trace, the existing latency harness output, and only the minimal DM console combat route/read-model evidence needed to decide whether the remaining route-visible latency is primarily route serialization, nested snapshot work, combat snapshot construction, load-shape artifact, or another bounded seam. Preserve the kept `d16a2aa` resource-pools refinement, keep startup-only `lan.snapshot.static_fields` deferred separately, and do not authorize direct optimization until that planning/evidence checkpoint is complete.

## Deferred Scope

Remain forbidden until a new active work item authorizes the specific change:

- app-code implementation
- tests changes
- log edits
- server start, browser smoke, deploy, restart, SSH, push, commit, or production topology changes
- another resource-pools implementation
- startup static-fields implementation
- broad snapshot/LAN optimization
- route registration changes or route body movement
- payload/schema changes
- cache ownership moves or cache TTL changes
- static hydration or snapshot warm-up ownership changes
- WebSocket, queue, auth, claims, reconnect, command semantic, persistence, or gameplay changes
- patching the small smoke bug inside this latency lane

## Ledger Update

`docs/work_items/current_work.md` was returned to Idle with no active work item.

The completed table now includes this post-implementation smoke evidence checkpoint. The allowed next action is a DM console combat route docs/evidence planning checkpoint if latency work continues, deploy-prep review if still desired, pause/no further migration, or a separate deferred bug-capture item for the small smoke bug.

`majorTODO.md` was not inspected or updated because it was outside this task's allowed edit list.

## Validation

Required validation commands:

```bash
.venv/bin/python scripts/snapshot_lan_hot_path_latency_harness.py logs/debug-trace-20260702-193152.jsonl
timeout 10s git diff --check
git status --short
```

Results are recorded in the final agent report.
