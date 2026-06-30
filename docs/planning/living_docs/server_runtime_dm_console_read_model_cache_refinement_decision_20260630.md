# Server Runtime DM Console Read-Model Cache Refinement Decision - 2026-06-30

## Status

Planning/decision document only. This document does not authorize app implementation, test edits, route migration, route-side offload, instrumentation, cache behavior changes, TTL changes, invalidation changes, snapshot payload changes, queue behavior changes, LAN controller behavior changes, Tk behavior changes, WebSocket changes, gameplay logic changes, combat logic changes, browser smoke, server starts, deploys, commits, pushes, or production commands.

## Decision Summary

Selected next implementation slice:

`WORK-20260630-runtime-facade-dm-console-read-model-cache-refinement-minimal-implementation`

The smallest safe slice is a legacy-owned DM-console micro-cache refinement:

- Keep cache ownership in `LanController._dm_console_snapshot()` / the existing broadcast prebuild path for the first implementation.
- Keep `ServerRuntimeFacade.read_snapshot()` as a synchronous dispatcher to the legacy helper, not a cache owner.
- Refine the existing `_cached_dm_snapshot` reuse so it is tactical-mode-aware and can safely serve immediate duplicate consumers within the existing short freshness window.
- Do not broaden into a facade cache, route-side threadpool/offload, LAN dynamic snapshot cache, static hydration, response-schema changes, or gameplay ownership movement.

Rationale: the evidence shows repeated heavy `GET /api/dm/combat?workspace` reads are dominated by the DM-console composite tactical path below `_dm_console_snapshot_payload()`, especially `_dm_tactical_snapshot()` and `_lan_snapshot()`. Moving cache ownership into the facade would duplicate legacy invalidation authority before the data domains are cleanly separated. A narrow legacy helper refinement can reduce immediate duplicate rebuilds while preserving current route, payload, and gameplay behavior.

## Evidence Inspected

Source documents inspected:

- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-latency-read-model-followup-decision.md`
- `docs/planning/living_docs/server_runtime_latency_read_model_followup_decision_20260630.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-route-read-adoption-minimal-implementation.md`
- `docs/planning/living_docs/server_runtime_snapshot_boundary_readiness_decision_20260630.md`
- `docs/planning/living_docs/server_runtime_snapshot_boundary_checkpoint_20260630.md`
- `logs/debug-trace-20260630-164720.jsonl`
- `logs/smoke/WORK-20260630-runtime-facade-route-read-adoption-minimal-implementation_smoke-server_20260630-164720.log`

Trace and smoke logs were inspected with `head`, `tail`, `grep`, and `sed` only.

Source sections inspected:

- `server_runtime.py`: `read_snapshot()` and directly adjacent read-snapshot helpers.
- `dnd_initative_tracker.py`: `_current_request_wants_tactical_map()`, `GET /api/dm/combat`, `_dm_console_snapshot()`, `_dm_console_snapshot_payload()`, `_lan_snapshot()`, `_dm_tactical_snapshot()`, and existing `_cached_dm_snapshot` / `_cached_dm_snapshot_at` use.
- `combat_service.py`: `CombatService.combat_snapshot()`.

## Current DM Console Snapshot Cache Behavior

`GET /api/dm/combat` authenticates the DM request, builds `RuntimeSnapshotRequest(snapshot_type="dm_console", params={"include_tactical": _current_request_wants_tactical_map()})`, calls `self._runtime.read_snapshot(...)`, and returns `result.data`.

`ServerRuntimeFacade.read_snapshot()` validates readiness, params, static-hydration rejection, and snapshot type. For `dm_console`, it resolves `include_tactical`, then delegates to `lan_controller._dm_console_snapshot(include_tactical=include_tactical)`.

`LanController._dm_console_snapshot()` owns the current DM-console cache. If no explicit `combat_snapshot` or `tactical_snapshot` is supplied, it checks `_cached_dm_snapshot` and `_cached_dm_snapshot_at`; if the cached value is a dict and younger than `0.25` seconds, it clears `_cached_dm_snapshot` / `_cached_dm_snapshot_at` and returns that cached composite.

That current cache is therefore:

- Legacy-owned on the `LanController` instance.
- Very short-lived.
- One-shot, because it clears on first read.
- Composite, because it stores the full DM-console payload.
- Not currently keyed by `include_tactical`.

The current prebuild source is in the LAN broadcast path. After `_lan_force_state_broadcast()` builds a LAN snapshot, it can derive `tactical_snapshot` from that already-built LAN snapshot, build a DM console payload via `_dm_console_snapshot_payload(tactical_snapshot=..., include_tactical=...)`, stash it on `self._lan._cached_dm_snapshot` with `_cached_dm_snapshot_at = time.perf_counter()`, and push it to DM WebSocket clients.

`_dm_console_snapshot_payload()` builds the composite payload. It calls `CombatService.combat_snapshot()` unless a combat snapshot is supplied. When tactical inclusion is enabled, it calls the tracker's `_dm_tactical_snapshot()` unless a tactical snapshot is supplied. It always merges DM-visible pending prompts at the end.

`_dm_tactical_snapshot()` calls `_lan_snapshot(include_static=False, hydrate_static=False)`, then narrows the LAN snapshot to tactical/map keys.

## Latency Evidence

The route-read adoption smoke succeeded behaviorally: the headless tracker started, DM and player surfaces were advertised, LAN sessions connected, Fred was claimed, and the trace showed `GET /api/dm/combat` returning HTTP 200.

The trace showed small no-workspace reads around `2.611 ms`, `2.841 ms`, and `326.690 ms`, while workspace reads ranged from about `112.756 ms` to `1416.111 ms`.

Observed `GET /api/dm/combat?workspace` response times included:

- `280.869 ms`
- `254.325 ms`
- `1247.723 ms`
- `1416.111 ms`
- `1170.187 ms`
- `1149.322 ms`
- `1066.479 ms`
- `112.756 ms`
- `893.591 ms`
- `1010.931 ms`
- `112.959 ms`

The worst inspected workspace route-context span was:

- `http.request`: `1415.720 ms`
- `_dm_console_snapshot`: `1396.260 ms`
- `_dm_console_snapshot_payload`: `1395.968 ms`
- `combat_service.combat_snapshot`: `89.599 ms`
- `_dm_tactical_snapshot`: `1305.780 ms`
- `_lan_snapshot`: `1305.254 ms`

The trace also showed a later workspace request at about `1010.931 ms`, with `_dm_console_snapshot_payload` at `990.989 ms`, `_dm_tactical_snapshot` at `869.279 ms`, and `_lan_snapshot` at `868.837 ms`.

Inference from the trace: the hot cost is not the facade wrapper and not primarily `CombatService.combat_snapshot()`. It is repeated composite DM-console workspace reads rebuilding tactical/LAN state.

The trace also showed a mutation response and a following workspace GET occurring at the same timestamp boundary. The current one-shot cache can be consumed and cleared by the mutation response, leaving the immediate follow-up GET to rebuild the heavy tactical path. A same-TTL, mode-aware short reuse can target that duplicate-build pattern without introducing a broad stale read-model cache.

## Cache Safety Decision

Safe to cache or reuse in the next slice:

- A complete DM-console composite snapshot produced by `_dm_console_snapshot_payload()` only inside the existing legacy DM-console cache path.
- Only within the existing very short freshness window.
- Only when the requested `include_tactical` mode exactly matches the cached snapshot's tactical mode.
- Only when the cache was produced after the relevant mutation/broadcast state was already reflected.
- Only as a compatibility optimization for immediate duplicate DM-console consumers, not as a durable read model.

Unsafe to cache in the next slice:

- `ServerRuntimeFacade` results or route responses as a facade-owned cache.
- Standalone `combat` snapshots from `CombatService.combat_snapshot()`.
- A tactical payload for `include_tactical=False` requests.
- A non-tactical composite for `include_tactical=True` requests.
- Static-hydrated LAN payloads.
- `_lan_snapshot()` dynamic payloads as a new reusable tactical read model.
- Stale `pending_prompts`, prompt visibility, or hidden-information state across prompt mutations.
- Any payload produced by a failed builder as a fallback for later route reads.

Conditionally reusable but not selected for the first slice:

- A tactical subpayload derived from `_lan._cached_snapshot`. The trace suggests it could reduce cost, but the inspected scope does not establish sufficient invalidation/freshness guarantees for route reads. That belongs in a later read-model cache task after explicit versioning/invalidation is designed.

## Ownership Decision

Cache ownership should stay in the legacy helper for the first implementation slice.

Do not move cache ownership behind `ServerRuntimeFacade.read_snapshot()` yet.

Reasons:

- The facade currently owns request validation and dispatch semantics, not mutation-domain invalidation.
- The existing cache and prebuild path already live with the legacy state owner that knows when LAN broadcasts and DM WebSocket pushes occur.
- Moving cache state into the facade would require duplicating combat, tactical, pending-prompt, map, static, and mutation invalidation domains before they are cleanly separated.
- A facade cache would make stale tactical and pending-prompt failures harder to reason about during the migration.

The facade should continue to delegate `dm_console` reads to `LanController._dm_console_snapshot(include_tactical=...)` and should not grow cache fields or cache invalidation hooks in the next slice.

## Minimal Implementation Boundary For Next Work Item

Recommended next work item:

`WORK-20260630-runtime-facade-dm-console-read-model-cache-refinement-minimal-implementation`

Allowed implementation shape:

- Add tactical-mode metadata to the existing DM-console cached composite, such as a legacy-owned cached `include_tactical` marker.
- Update the existing prebuild store path to record the tactical mode for `_cached_dm_snapshot`.
- Update `_dm_console_snapshot()` so cached reuse requires the cached mode to match the requested `include_tactical` mode.
- Preserve the existing short freshness window unless the implementation task explicitly reopens TTL policy; the selected slice does not require a TTL increase.
- Prefer allowing more than one immediate read within that same short window only if the implementation also proves stale pre-mutation cache cannot survive into mutation responses.
- If stale pre-mutation cache safety cannot be proven within the named helper/prebuild boundaries, keep one-shot clearing and stop after the mode-aware correctness fix.
- Add focused tests for cache reuse, tactical-mode mismatch rebuild, expired cache rebuild, include-tactical payload shape, mutation-response freshness posture if touched, and facade delegation still not owning cache.

Likely implementation files for the next slice:

- `dnd_initative_tracker.py`
- Focused tests covering the helper/facade behavior
- Work-item and living-doc completion files

Do not edit `server_runtime.py` unless a focused test reveals the existing facade delegation fails to preserve the selected cache posture. The intended implementation is legacy-helper-owned.

## Correctness Constraints

`include_tactical` constraints:

- `GET /api/dm/combat` must continue to pass explicit `include_tactical` context into `RuntimeSnapshotRequest`.
- The cache key or metadata must distinguish `include_tactical=True` from `include_tactical=False`.
- `include_tactical=False` responses must not gain `tactical_map` from a cached tactical response.
- `include_tactical=True` responses must not reuse a cached non-tactical response that omits `tactical_map`.
- Unknown or missing facade params must continue to fail closed as currently implemented by `read_snapshot()`.

Combat-only read constraints:

- `SNAPSHOT_TYPE_COMBAT` must remain a direct `CombatService.combat_snapshot()` read.
- Combat-only facade reads must not consult `_cached_dm_snapshot`.
- Combat-only reads must not include `tactical_map`.
- The next slice must not normalize or reshape combat snapshot fields.

Stale tactical map constraints:

- Expired, missing, mismatched, or metadata-ambiguous cached DM snapshots must rebuild rather than return stale tactical data.
- Cached tactical data must not be used after map, position, turn-order, AoE, aura, structure, ship, boarding, resource, prompt, or combat mutations unless the cache was rebuilt after that mutation.
- A tactical builder failure must not fall back to an older cached tactical map. The existing builder behavior may remain as-is, but the new cache refinement must not introduce a stale fallback path.

Cache invalidation constraints:

- The next slice must preserve legacy cache ownership and the existing cache freshness posture.
- It must not introduce broad invalidation hooks in the facade.
- It must not depend on unverified route-side or threadpool behavior.
- If preserving mutation freshness requires broader invalidation outside the DM-console helper/prebuild path, the implementation must stop and open a separate invalidation-design item.

Mutation response constraints:

- Mutation responses that return DM-console snapshots must continue to reflect post-mutation state.
- A pre-mutation cached snapshot must not be returned after a mutation simply because it is younger than the freshness window.
- Any multi-read reuse must be limited to a cache produced after the mutation/broadcast state update that the response represents.

Fail-closed constraints:

- `ServerRuntimeFacade.read_snapshot()` must continue to fail closed for runtime-not-ready, unsupported snapshot types, invalid params, unavailable builders, and builder exceptions that escape the legacy helper.
- Cache metadata errors must degrade to a rebuild or facade failure, not to stale data.
- No partial payload should be returned by new cache code after an explicit cache-validation failure.

## Exact Deferred Scope

Deferred from the next implementation slice unless a separate active work item explicitly authorizes it:

- Facade-owned snapshot cache.
- TTL increase or durable polling cache.
- New invalidation framework.
- Direct reuse of `_lan._cached_snapshot` as a route tactical read model.
- Static hydration or static map cache contract changes.
- Route-side read offload or threadpool execution.
- Route migration beyond the already adopted `GET /api/dm/combat` path.
- Another read-route adoption.
- Response schema changes.
- WebSocket payload shape changes.
- LAN controller ownership migration.
- Queue behavior changes.
- Tk behavior changes.
- Combat mutation behavior changes.
- Gameplay logic changes.
- Hidden-information or auth behavior changes.
- New instrumentation or trace events.
- Browser smoke, server starts, deploys, commits, pushes, or production commands.

## Next Validation Expectations

The future implementation slice should use focused validation only.

Expected minimum validation:

```bash
git status --short
timeout 10s git diff --check
timeout 10s python3 -m py_compile dnd_initative_tracker.py
timeout 30s python3 -m unittest <focused cache/facade test target>
```

Do not run broad recursive tests or browser smoke for the minimal implementation unless the future active work item explicitly authorizes them.
