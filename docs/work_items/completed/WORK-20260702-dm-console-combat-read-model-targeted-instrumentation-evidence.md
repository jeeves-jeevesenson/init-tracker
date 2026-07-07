# WORK-20260702-dm-console-combat-read-model-targeted-instrumentation-evidence

Status: Completed

## Goal

Add narrow debug-trace attribution around the DM console combat read-model path so future latency decisions can identify which route/read-model substeps inside `/api/dm/combat`, `_dm_console_snapshot()`, `_dm_console_snapshot_payload()`, and the outer DM console combat/tactical composition path are expensive.

This was instrumentation/evidence only. It did not optimize latency, change route behavior, move route bodies, change route registration, change response payload schemas, change snapshot schemas, change resource-pools/cache/TTL/static-fields behavior, change WebSocket/queue/auth/claims/reconnect behavior, change persistence, change visibility/gameplay semantics, start the server, run browser smoke, deploy, restart services, SSH, push, commit, or patch the small smoke bug.

## Files Inspected

- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260702-dm-console-combat-route-latency-planning-evidence-checkpoint.md`
- `docs/runtime_reports/dm_console_combat_route_latency_planning_evidence_20260702.md`
- `dnd_initative_tracker.py`, limited to the `/api/dm/combat` read route, `_dm_combat_read_snapshot_in_threadpool()`, `_dm_console_snapshot()`, `_dm_console_snapshot_payload()`, `_dm_tactical_snapshot()`, `_dm_tactical_snapshot_from_lan_snapshot()`, and existing trace/count seams
- `server_runtime.py`, limited to `ServerRuntimeFacade.read_snapshot()` and existing `_trace_context` forwarding
- `scripts/snapshot_lan_hot_path_latency_harness.py`
- `tests/test_server_runtime.py`, limited to existing DM route/read snapshot and cache regression patterns
- `combat_service.py`, inspect-only for the direct `dm_service.combat_snapshot()` helper and its pre-existing `combat_service.combat_snapshot` trace decorator

No `majorTODO.md`, old plans, unrelated runtime reports, unrelated logs, browser assets, production files, `docs/bug_reports/inbox/BUG-20260626-dmcontrol-terrain-not-visible.md`, or `logs/context/` files were inspected or edited.

## Files Changed

- `dnd_initative_tracker.py`
- `scripts/snapshot_lan_hot_path_latency_harness.py`
- `docs/work_items/current_work.md`
- `docs/work_items/active/WORK-20260702-dm-console-combat-read-model-targeted-instrumentation-evidence.md` (created while active, removed at completion)
- `docs/work_items/completed/WORK-20260702-dm-console-combat-read-model-targeted-instrumentation-evidence.md`
- `docs/planning/living_docs/dm_console_combat_read_model_targeted_instrumentation_evidence_20260702.md`
- `docs/runtime_reports/dm_console_combat_read_model_targeted_instrumentation_evidence_20260702.md`

`server_runtime.py` and `tests/test_server_runtime.py` were inspected but not changed.

## Instrumentation Added

New route/read wrapper spans:

- `dm.console.route_read_snapshot`
- `dm.console.route_payload_proxy`

New `_dm_console_snapshot()` wrapper spans:

- `dm.console.snapshot.cache_check`
- `dm.console.snapshot.payload`

New `_dm_console_snapshot_payload()` / combat composition spans:

- `dm.console.combat_snapshot.service_call`
- `dm.console.combat_snapshot.copy`
- `dm.console.combat_snapshot.provided_copy`
- `dm.console.tactical_snapshot.provided_copy`
- `dm.console.payload.tactical_merge`
- `dm.console.payload.pending_prompts`
- `dm.console.payload.size_proxy`

Harness target additions:

- all new spans above
- pre-existing `combat_service.combat_snapshot`, which is the service method decorator span nested under the outer `dm.console.combat_snapshot` service call when debug tracing is enabled

Existing spans retained:

- `http.request:/api/dm/combat`
- `_dm_console_snapshot`
- `_dm_console_snapshot_payload`
- `dm.console.combat_snapshot`
- `dm.console.tactical_snapshot`
- `_dm_tactical_snapshot`
- `dm.tactical.from_lan_snapshot`
- LAN snapshot subspans already summarized by the harness

## Labels And Counters

Common low-cardinality labels on the new DM console spans:

- `scope`
- `snapshot_caller`
- `include_tactical`
- `counts`

`counts` continues to come from the existing `_debug_trace_counts()` helper and includes:

- `combatant_count`
- `player_count`
- `monster_count`
- `map_aoe_count`
- `pending_prompt_count`
- `pending_reaction_count`
- `websocket_client_count`
- `dm_websocket_client_count`
- `total_websocket_client_count`

Route-specific labels:

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

Payload-size proxy events:

- event `snapshot.payload_proxy` with `span=dm.console.route_payload_proxy`
- event `snapshot.payload_proxy` with `span=dm.console.payload.size_proxy`

Payload-size proxy `sizes` keys:

- `payload_top_level_key_count`
- `payload_combatant_count`
- `payload_turn_order_count`
- `payload_battle_log_count`
- `payload_pending_prompt_count`
- `payload_tactical_key_count`
- `payload_tactical_unit_count`
- `payload_tactical_aoe_count`
- `payload_tactical_grid_cell_count`

The proxy reads only already-built dictionaries/lists and does not serialize payloads, log player names, monster names, hidden fields, secrets, tokens, raw responses, or large structures.

## Evidence Decision

Instrumentation was added and the harness was extended to summarize the new span names while remaining backward-compatible with older traces that do not contain them.

No latency fix is selected yet. The new DM console read-model instrumentation still needs a developer-run targeted smoke/debug trace before any implementation, optimization, cache, route, offload, schema, payload, WebSocket, queue, visibility, or gameplay decision.

Because `combat_service.py` was outside the allowed edit list, this slice did not add true service-internal substep spans inside `CombatService.combat_snapshot()`. The harness now summarizes its pre-existing `combat_service.combat_snapshot` decorator span and the wrapper adds `dm.console.combat_snapshot.service_call` plus copy/provided-copy attribution around the call. A later service-internal attribution pass should explicitly scope `combat_service.py` if the new smoke shows the service call itself is the expensive child.

## Validation

Required validation commands:

```bash
.venv/bin/python -m py_compile dnd_initative_tracker.py server_runtime.py scripts/snapshot_lan_hot_path_latency_harness.py
.venv/bin/python scripts/snapshot_lan_hot_path_latency_harness.py logs/debug-trace-20260702-193152.jsonl
timeout 90s .venv/bin/python -m pytest tests/test_server_runtime.py
timeout 10s git diff --check
git status --short
```

Focused validation passed. The harness compatibility run against `logs/debug-trace-20260702-193152.jsonl` parsed the old trace successfully; the old trace predates the new spans, so the newly added target rows are expected to be empty until a fresh developer-run smoke captures them.

## Recommended Next Work

Recommended next work item:

`WORK-20260702-dm-console-combat-read-model-targeted-smoke-evidence-capture`

Recommended type:

Evidence capture, not planning, optimization, or implementation.

Recommended goal:

Run a developer-owned targeted DM console combat smoke/debug-trace capture with the new instrumentation, then summarize the trace with the updated harness to decide whether a later implementation should focus on `CombatService.combat_snapshot()`, wrapper/cache/pending-prompt work, tactical route reads, route serialization/response-size effects, route overlap, DM websocket/broadcast adjacency, or another measured child span.

## Ledger Update

`docs/work_items/current_work.md` was returned to Idle with no active work item.

The completed table now includes this instrumentation/evidence checkpoint. The allowed next action is developer-run targeted DM console combat read-model smoke/evidence capture using the new instrumentation, deploy-prep review if still desired, pause/no further migration, or a separate deferred bug-capture item if the small smoke bug remains relevant.

`majorTODO.md` was not inspected or updated because it was outside this task's allowed edit list.
