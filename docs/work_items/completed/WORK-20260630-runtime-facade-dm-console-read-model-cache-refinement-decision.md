# WORK-20260630-runtime-facade-dm-console-read-model-cache-refinement-decision

Status: Completed

## Goal

Complete a bounded planning/evidence-only cache/read-model refinement decision for the DM console snapshot path after the latency/read-model follow-up selected cache/read-model refinement as the next lane.

This pass decided the smallest safe implementation slice to reduce repeated/heavy `GET /api/dm/combat?workspace` snapshot cost without changing gameplay behavior or moving ownership too far at once.

No app code, tests, route behavior, cache behavior, TTLs, invalidation, payload schemas, queue behavior, LAN controller behavior, Tk behavior, WebSockets, gameplay logic, combat logic, deploys, commits, or pushes were changed.

## Files Changed

- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-dm-console-read-model-cache-refinement-decision.md`
- `docs/planning/living_docs/server_runtime_dm_console_read_model_cache_refinement_decision_20260630.md`

## Evidence Inspected

Documents:

- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-latency-read-model-followup-decision.md`
- `docs/planning/living_docs/server_runtime_latency_read_model_followup_decision_20260630.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-route-read-adoption-minimal-implementation.md`
- `docs/planning/living_docs/server_runtime_snapshot_boundary_readiness_decision_20260630.md`
- `docs/planning/living_docs/server_runtime_snapshot_boundary_checkpoint_20260630.md`
- `logs/debug-trace-20260630-164720.jsonl`
- `logs/smoke/WORK-20260630-runtime-facade-route-read-adoption-minimal-implementation_smoke-server_20260630-164720.log`

Logs were inspected only with `grep`, `head`, `tail`, and `sed`.

Code sections:

- `server_runtime.py`: `read_snapshot()` and directly adjacent read-snapshot helpers.
- `dnd_initative_tracker.py`: `_current_request_wants_tactical_map()`, `GET /api/dm/combat`, `_dm_console_snapshot()`, `_dm_console_snapshot_payload()`, `_lan_snapshot()`, `_dm_tactical_snapshot()`, and existing `_cached_dm_snapshot` / `_cached_dm_snapshot_at` use.
- `combat_service.py`: `CombatService.combat_snapshot()`.

## Current Cache / Read-Model Finding

`GET /api/dm/combat` now reads through `ServerRuntimeFacade.read_snapshot(snapshot_type="dm_console")`, but the facade delegates to `LanController._dm_console_snapshot(include_tactical=...)`.

The current DM-console cache lives in the legacy `LanController` helper path:

- `_cached_dm_snapshot`
- `_cached_dm_snapshot_at`

Current behavior is a very short-lived, one-shot composite cache. If the cached dict is younger than `0.25` seconds, `_dm_console_snapshot()` clears the cache and returns it. The cache is not currently keyed by `include_tactical`.

The LAN broadcast path can prebuild a DM console payload after building a LAN snapshot, store it on `self._lan._cached_dm_snapshot`, and push it to DM WebSocket clients. That prebuild is the right ownership location for the first cache refinement because it already lives near legacy state/broadcast authority.

## Latency Evidence

The smoke evidence confirmed `GET /api/dm/combat` and `GET /api/dm/combat?workspace` returned HTTP 200.

The debug trace showed workspace reads ranging from about `112.756 ms` to `1416.111 ms`.

Worst inspected workspace route-context span:

- `http.request`: `1415.720 ms`
- `_dm_console_snapshot`: `1396.260 ms`
- `_dm_console_snapshot_payload`: `1395.968 ms`
- `combat_service.combat_snapshot`: `89.599 ms`
- `_dm_tactical_snapshot`: `1305.780 ms`
- `_lan_snapshot`: `1305.254 ms`

Finding: the hot cost is repeated tactical/LAN snapshot construction under the DM-console composite path, not the facade wrapper and not primarily `CombatService.combat_snapshot()`.

## Decision

Selected next implementation slice:

`WORK-20260630-runtime-facade-dm-console-read-model-cache-refinement-minimal-implementation`

Recommended shape:

- Keep cache ownership in `LanController._dm_console_snapshot()` and the existing broadcast prebuild path.
- Keep `ServerRuntimeFacade.read_snapshot()` as a dispatcher; do not add facade cache state.
- Add tactical-mode metadata to the existing DM-console cached composite.
- Require cache reuse to match requested `include_tactical`.
- Preserve the existing short freshness posture unless a later task explicitly reopens TTL policy.
- Allow same-window immediate duplicate reuse only if stale pre-mutation cache cannot survive into mutation responses; otherwise stop after the mode-aware correctness fix.

## Deferred Scope

Deferred unless a separate active work item explicitly authorizes it:

- Facade-owned cache.
- TTL increase.
- New invalidation framework.
- Direct reuse of `_lan._cached_snapshot` as a route tactical read model.
- Static hydration changes.
- Route-side read offload.
- Another read-route adoption.
- Response schema changes.
- WebSocket payload shape changes.
- Queue behavior changes.
- Tk behavior changes.
- Combat mutation behavior changes.
- Gameplay logic changes.
- New instrumentation.
- Browser smoke, server starts, deploys, commits, pushes, or production commands.

## Ledger Update

`docs/work_items/current_work.md` was returned to Idle.

Allowed next action is to open:

`WORK-20260630-runtime-facade-dm-console-read-model-cache-refinement-minimal-implementation`

## Validation

Required validation commands:

- `git status --short`
- `timeout 10s git diff --check`
