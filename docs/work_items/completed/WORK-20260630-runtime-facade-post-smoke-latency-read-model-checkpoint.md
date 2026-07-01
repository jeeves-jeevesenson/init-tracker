# WORK-20260630-runtime-facade-post-smoke-latency-read-model-checkpoint

Status: Completed

## Goal

Complete a bounded post-smoke latency/read-model checkpoint using the completed mode-aware DM-console cache refinement smoke evidence at `fcf96d9`.

This was a docs/evidence/decision pass only. No app code, tests, instrumentation, harness code, cache behavior, route-side offload, route migration, app-host changes, launcher changes, gameplay behavior, server starts, browser smoke, deploys, commits, or pushes were changed or run.

## Files Changed

- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-post-smoke-latency-read-model-checkpoint.md`
- `docs/planning/living_docs/server_runtime_post_smoke_latency_read_model_checkpoint_20260630.md`

Removed the active work item copy after completion:

- `docs/work_items/active/WORK-20260630-runtime-facade-post-smoke-latency-read-model-checkpoint.md`

## Evidence Inspected

Documents:

- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-dm-console-read-model-cache-refinement-minimal-implementation.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-dm-console-read-model-cache-refinement-decision.md`
- `docs/planning/living_docs/server_runtime_dm_console_read_model_cache_refinement_decision_20260630.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-latency-read-model-followup-decision.md`
- `docs/planning/living_docs/server_runtime_latency_read_model_followup_decision_20260630.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-route-read-adoption-minimal-implementation.md`
- `docs/planning/living_docs/server_runtime_snapshot_boundary_checkpoint_20260630.md`
- `docs/planning/living_docs/server_runtime_snapshot_boundary_readiness_decision_20260630.md`

Logs inspected with `grep`, `head`, `tail`, and `sed` only:

- `logs/debug-trace-20260630-183429.jsonl`
- `logs/smoke/WORK-20260630-runtime-facade-dm-console-read-model-cache-refinement-minimal-implementation_smoke-server_20260630-183429.log`

Source sections:

- `server_runtime.py`: `ServerRuntimeFacade.read_snapshot()` and adjacent snapshot validation/dispatch helpers only.
- `dnd_initative_tracker.py`: `GET /api/dm/combat`, `_cached_dm_snapshot` metadata initialization, `_dm_console_snapshot()`, `_dm_console_snapshot_payload()`, `_dm_tactical_snapshot()`, `_lan_snapshot()`, and the DM-console prebuild metadata assignment in `_lan_force_state_broadcast()`.

## Decision

Selected next implementation lane:

`WORK-20260630-runtime-facade-server-responsiveness-evidence-harness`

The fcf96d9 smoke proves the mode-aware DM-console cache refinement is behaviorally smoke-passed: the server started, DM/player surfaces were advertised, a LAN session claimed `Dorian`, `GET /api/dm/combat?workspace` returned HTTP 200, and no stale tactical/non-tactical cross-mode issue or developer-visible responsiveness problem was reported.

The smoke does not prove ASGI/event-loop responsiveness or health/readiness responsiveness while heavier runtime work is occurring. The trace contains no `/health`, `/api/health`, `/ready`, or `/api/ready` route samples, and it still contains route-context `GET /api/dm/combat?workspace` outliers around `600 ms` dominated by `_dm_tactical_snapshot()` / `_lan_snapshot()`.

## Rejected / Deferred Lanes

Further cache escalation is not justified now. The cache refinement passed smoke and produced many fast route reads, but TTL increases, facade-owned cache, durable read-model cache, `_lan._cached_snapshot` route reuse, or new invalidation would require stronger freshness/invalidation evidence.

Route-side read offload is not justified now. It remains a possible transition mitigation only after direct responsiveness evidence shows health/readiness/combat HTTP handling stalls behind heavier runtime work.

More read-route adoption and high-risk direct gameplay-route migration remain deferred because they would widen route ownership before the server responsiveness question is measured.

Route ownership/import topology is not the apparent bottleneck. The observed slow route spans point to snapshot-builder work, not the package/app-host boundary.

## Ledger Update

`docs/work_items/current_work.md` was returned to Idle.

Allowed next action is to open:

`WORK-20260630-runtime-facade-server-responsiveness-evidence-harness`

Do not proceed to cache escalation, route-side offload, route migration, app-host changes, launcher changes, direct gameplay-route migration, player-command routes, combat mutation routes, rules-aware move, AoE create, structures, ships, boarding links, static hydration changes, queue behavior changes, WebSocket behavior changes, or production work without a new active work item.

## Validation

Required validation commands:

- `git status --short`
- `timeout 10s git diff --check`

Results:

- `git status --short` showed only the expected docs changes plus the known baseline untracked dirt: `docs/bug_reports/inbox/BUG-20260626-dmcontrol-terrain-not-visible.md` and `logs/context/`.
- `timeout 10s git diff --check` passed with no output.
