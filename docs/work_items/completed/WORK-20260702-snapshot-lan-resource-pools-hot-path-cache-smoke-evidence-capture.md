# WORK-20260702-snapshot-lan-resource-pools-hot-path-cache-smoke-evidence-capture

Status: Completed

## Goal

Complete a bounded Codex docs/evidence checkpoint for the post-implementation smoke evidence from commit `95bbdf6`.

This checkpoint decided what the fresh smoke proves, whether the new dedicated resource-pools cache-hit path is fast enough to keep, what slow path remains, and what the next safe work item should be. It did not implement a fix, optimize latency, edit app code, edit tests, edit logs, start the server, run browser smoke, deploy, restart services, SSH, push, commit, alter production topology, patch the small smoke bug, or change routes, route registration, route bodies, payloads, snapshot schemas, cache ownership, cache TTLs, static hydration, WebSockets, auth/claims/reconnect, queue behavior, command semantics, persistence, or gameplay behavior.

## Files Inspected

- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260702-snapshot-lan-resource-pools-hot-path-cache-minimal-implementation.md`
- `docs/planning/living_docs/snapshot_lan_resource_pools_hot_path_cache_minimal_implementation_20260702.md`
- `docs/runtime_reports/snapshot_lan_resource_pools_hot_path_cache_minimal_implementation_20260702.md`
- `docs/work_items/completed/WORK-20260702-snapshot-lan-resource-pools-latency-planning-checkpoint.md`
- `docs/planning/living_docs/snapshot_lan_resource_pools_latency_planning_checkpoint_20260702.md`
- `docs/runtime_reports/snapshot_lan_hot_path_targeted_smoke_evidence_20260702.md`
- `logs/smoke/WORK-20260702-snapshot-lan-resource-pools-hot-path-cache-smoke-evidence-capture_smoke-server_20260702-123404.log`, using `head` and `tail` only
- `logs/debug-trace-20260702-123404.jsonl`, using `head`, `tail`, and `grep` only
- `scripts/snapshot_lan_hot_path_latency_harness.py`

No `majorTODO.md`, old plans, unrelated runtime reports, unrelated logs, browser assets, app code, tests, production files, `docs/bug_reports/inbox/BUG-20260626-dmcontrol-terrain-not-visible.md`, or `logs/context/` files were inspected or edited.

## Files Changed

- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260702-snapshot-lan-resource-pools-hot-path-cache-smoke-evidence-capture.md`
- `docs/planning/living_docs/snapshot_lan_resource_pools_hot_path_cache_smoke_evidence_capture_20260702.md`
- `docs/runtime_reports/snapshot_lan_resource_pools_hot_path_cache_smoke_evidence_20260702.md`

No active work item copy was left after completion.

## Smoke Evidence Decision

This checkpoint used the fresh evidence run at `20260702-123404`.

The earlier aborted smoke start at `20260702-104233` was intentionally not treated as evidence for this task.

The smoke log proves the basic headless/browser/LAN path still works for the post-implementation build:

- Headless tracker started.
- Debug trace was created at `logs/debug-trace-20260702-123404.jsonl`.
- DM operator surface was advertised on `/dm`.
- Player LAN surface was advertised on `/`.
- LAN server was hoisted on port `8787`.
- Browser LAN sessions connected.
- One LAN session claimed Eldramar.
- That claimed LAN session later disconnected while still claimed as Eldramar.

This run proves fresh LAN claim coverage for one player identity and disconnect-while-claimed logging. It does not claim broader gameplay coverage, unclaim coverage, or browser smoke beyond what the captured log shows.

## Post-Implementation Latency Decision

The harness parsed `14,040` valid JSON objects with `0` malformed/non-object lines.

Key harness rows:

- `_lan_snapshot`: count `280`, p50 `6.799 ms`, p95 `842.408 ms`, max `24640.335 ms`, `83` samples at or above `250 ms`, `3` at or above `1000 ms`.
- `lan.snapshot.resource_pools`: count `280`, p50 `0.092 ms`, p95 `759.372 ms`, max `2836.852 ms`, `83` samples at or above `250 ms`, `2` at or above `1000 ms`.
- `lan.snapshot.static_fields`: count `280`, p50 `0.090 ms`, p95 `0.264 ms`, max `24202.351 ms`.
- `dm.tactical.from_lan_snapshot`: count `31`, p50 `0.080 ms`, p95 `0.252 ms`, max `0.260 ms`.
- `dm.console.combat_snapshot`: count `53`, p50 `26.693 ms`, p95 `94.884 ms`, max `150.560 ms`.
- `http.request:/api/dm/combat`: count `31`, p50 `79.313 ms`, p95 `1184.073 ms`, max `1280.097 ms`.

The trace tail shows the new dedicated cache-hit path is fast when it is used:

- `resource_pool_mode=dedicated_cache_hit` completes around `0.081-0.097 ms`.

The trace tail also shows the remaining slow path:

- `resource_pool_mode=ttl_rebuild` completes around `368.002-380.124 ms`.

The evidence is mixed in the intended way:

- The narrow cache refinement is worth keeping because the dedicated cache-hit path is cheap.
- The steady-state slow samples are still dominated by `ttl_rebuild`, not by tactical extraction or the static-field startup outlier.
- `lan.snapshot.resource_pools` still matches `_lan_snapshot` exactly at the `>=250 ms` threshold and nearly matches it at `>=1000 ms`, so resource-pools rebuild work remains the main nested cause of the slow `_lan_snapshot` samples in this run.

## Answers

1. The post-implementation smoke proves headless startup, debug-trace creation, `/dm` and `/` advertisement, LAN hoist on port `8787`, browser LAN session connection, one Eldramar claim, and disconnect while claimed still work for commit `95bbdf6`.
2. The dedicated resource-pools cache/refinement improved the cache-hit path enough to keep because the new `dedicated_cache_hit` mode is sub-millisecond in the trace tail. This checkpoint does not claim a full end-to-end latency win because `ttl_rebuild` still dominates the slow tail.
3. The remaining slow path is `resource_pool_mode=ttl_rebuild` inside `lan.snapshot.resource_pools`, which still drives the repeated slow `_lan_snapshot` samples and the route-visible `/api/dm/combat` p95.
4. Yes. `ttl_rebuild` is now isolated enough as the next actionable issue, but the next step should be planning/implementation-decision only, not direct optimization from this task.
5. The implementation should be kept, not reverted. The smoke evidence supports the narrow refinement because the dedicated cache-hit path is fast and no new behavioral break is shown in the captured smoke. Any revision should wait for a focused `ttl_rebuild` planning checkpoint.
6. The next work item should be a `ttl_rebuild` planning checkpoint, not a follow-up implementation and not more evidence, because the evidence already isolates the remaining issue clearly enough for a bounded planning pass.
7. Yes. The startup-only `lan.snapshot.static_fields` outlier should remain deferred separately. Its p95 is still low, its max remains a `lan_startup_seed` startup artifact, and it should not be mixed into the steady-state `ttl_rebuild` lane.
8. Yes. The small smoke bug should remain deferred as separate bug-capture scope. It was not patched here.
9. Recommended next work item: `WORK-20260702-snapshot-lan-resource-pools-ttl-rebuild-planning-checkpoint`.

## Recommended Next Work

Recommended next work item:

`WORK-20260702-snapshot-lan-resource-pools-ttl-rebuild-planning-checkpoint`

Recommended type:

Docs/planning implementation-decision checkpoint, not implementation.

Recommended goal:

Use the fresh post-implementation smoke evidence from commit `95bbdf6`, the existing latency harness, and only the minimal resource-pools rebuild seam needed for decision-making to determine whether `resource_pool_mode=ttl_rebuild` has a safe narrow follow-up implementation lever. Preserve the kept dedicated cache-hit path, keep startup-only `lan.snapshot.static_fields` deferred separately, and do not authorize direct optimization until that planning checkpoint is complete.

## Deferred Scope

Remain forbidden until a new active work item authorizes the specific change:

- app-code implementation
- tests changes
- log edits
- server start, browser smoke, deploy, restart, SSH, push, commit, or production topology changes
- direct `ttl_rebuild` implementation
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

The completed table now includes this post-implementation smoke evidence checkpoint. The allowed next action is a `ttl_rebuild` planning/implementation-decision checkpoint, deploy-prep review if still desired, pause/no further migration, or a separate deferred bug-capture item for the small smoke bug.

`majorTODO.md` was not inspected or updated because it was outside this task's allowed edit list.

## Validation

Required validation commands:

```bash
.venv/bin/python scripts/snapshot_lan_hot_path_latency_harness.py logs/debug-trace-20260702-123404.jsonl
timeout 10s git diff --check
git status --short
```

Results are recorded in the final agent report.
