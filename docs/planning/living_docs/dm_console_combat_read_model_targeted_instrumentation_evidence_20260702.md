# DM Console Combat Read-Model Targeted Instrumentation Evidence - 2026-07-02

## Scope

This document records a bounded instrumentation/evidence slice for the remaining DM console combat route/read-model latency.

The slice added low-cardinality debug-trace attribution only. It did not optimize latency, change route behavior, move route bodies, alter route registration, change response payloads, change snapshot schemas, change resource-pools/cache/TTL/static-fields behavior, change WebSocket/queue/auth/claims/reconnect behavior, change visibility/gameplay semantics, start the server, run browser smoke, deploy, restart, SSH, push, commit, or patch the small smoke bug.

## Prior Evidence

The prior planning checkpoint kept commit `d16a2aa` because resource-pools improved materially, while the remaining slow route/read-model path was:

- `dm.console.combat_snapshot`: p95 `2038.109 ms`
- `_dm_console_snapshot_payload`: p95 `2089.417 ms`
- `_dm_console_snapshot`: p95 `2103.137 ms`
- `http.request:/api/dm/combat`: p95 `3454.867 ms`

The accepted trace shape included `212` combatants and `202` monsters, but did not split the route/read-model path enough to select a direct optimization.

## Instrumentation Shape

Route-level attribution:

- `http.request:/api/dm/combat` remains the route-visible wrapper span from existing middleware.
- `dm.console.route_read_snapshot` now wraps the route's offloaded `runtime.read_snapshot(dm_console)` body.
- `dm.console.route_payload_proxy` now emits a cheap payload-size proxy event after a successful route read and before returning the existing payload.

`_dm_console_snapshot()` attribution:

- `dm.console.snapshot.cache_check` wraps the existing short one-shot cache check.
- `dm.console.snapshot.payload` wraps the existing `_dm_console_snapshot_payload()` delegation when the cache does not return.
- Existing cache-hit behavior is unchanged; cache-hit debug events now use the same low-cardinality count labels.

`_dm_console_snapshot_payload()` attribution:

- `dm.console.combat_snapshot` remains the outer combat snapshot composition span.
- `dm.console.combat_snapshot.service_call` wraps the direct `dm_service.combat_snapshot()` call.
- `dm.console.combat_snapshot.copy` measures dict-copy cost for service-returned snapshots.
- `dm.console.combat_snapshot.provided_copy` measures dict-copy cost for caller-provided combat snapshots.
- `dm.console.tactical_snapshot` remains the optional tactical snapshot builder span.
- `dm.console.tactical_snapshot.provided_copy` measures dict-copy cost for caller-provided tactical snapshots.
- `dm.console.payload.tactical_merge` measures adding/removing the `tactical_map` key.
- `dm.console.payload.pending_prompts` measures the existing pending-prompt merge.
- `dm.console.payload.size_proxy` emits a cheap payload-size proxy event after payload assembly.

Harness additions:

- all new spans above
- pre-existing `combat_service.combat_snapshot`, which is the direct service method decorator span

## Labels

Common labels:

- `scope`
- `snapshot_caller`
- `include_tactical`
- `counts`

`counts` uses the existing `_debug_trace_counts()` helper and includes combatant/player/monster/AoE/prompt/reaction/WebSocket scale counters.

Route labels:

- `route=/api/dm/combat`
- `method=GET`
- `read_in_threadpool=True`
- `serialized_tactical_read=<bool>`

Source labels:

- `source=builder`
- `source=service`
- `source=provided`
- `source=tracker`
- `source=disabled`

Payload proxy `sizes` keys:

- `payload_top_level_key_count`
- `payload_combatant_count`
- `payload_turn_order_count`
- `payload_battle_log_count`
- `payload_pending_prompt_count`
- `payload_tactical_key_count`
- `payload_tactical_unit_count`
- `payload_tactical_aoe_count`
- `payload_tactical_grid_cell_count`

## Limitations

`combat_service.py` was outside the allowed edit list. This slice therefore did not add true internal substep spans inside `CombatService.combat_snapshot()`.

The updated harness can now summarize the existing `combat_service.combat_snapshot` decorator span and the new wrapper-level `dm.console.combat_snapshot.service_call` span. If a fresh smoke shows that service call is still the expensive child, the next planning/implementation decision should explicitly scope a service-internal instrumentation or optimization pass.

## Decision

No latency fix is selected.

The instrumentation is now in place for a developer-run targeted smoke/evidence capture. The next work should be evidence capture, not implementation.

Recommended next work item:

`WORK-20260702-dm-console-combat-read-model-targeted-smoke-evidence-capture`

Recommended type:

Evidence capture.
