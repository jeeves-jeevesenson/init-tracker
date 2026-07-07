# DM Console Combat Read-Model Targeted Instrumentation Evidence - 2026-07-02

## Scope

This runtime report records the code/docs evidence from a bounded instrumentation-only slice.

No server smoke or browser smoke was run. No production operation, deploy, restart, SSH, push, commit, route behavior change, route movement, route registration change, response payload/schema change, snapshot schema change, resource-pools/cache/TTL/static-fields change, WebSocket/queue/auth/claims/reconnect change, visibility/gameplay change, startup static-fields touch, or small smoke bug patch occurred.

## Instrumentation Added

New spans:

- `dm.console.route_read_snapshot`
- `dm.console.route_payload_proxy`
- `dm.console.snapshot.cache_check`
- `dm.console.snapshot.payload`
- `dm.console.combat_snapshot.service_call`
- `dm.console.combat_snapshot.copy`
- `dm.console.combat_snapshot.provided_copy`
- `dm.console.tactical_snapshot.provided_copy`
- `dm.console.payload.tactical_merge`
- `dm.console.payload.pending_prompts`
- `dm.console.payload.size_proxy`

Harness target additions:

- all new spans above
- existing `combat_service.combat_snapshot`

Common labels:

- `scope`
- `snapshot_caller`
- `include_tactical`
- `counts`

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

Payload proxy event:

- `snapshot.payload_proxy`

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

## Harness Compatibility

The harness was updated by extending `TARGET_SPANS`; parser behavior and input requirements were otherwise unchanged. Older traces that do not contain the new spans still parse and report zero-count rows for the new targets.

Required compatibility command:

```bash
.venv/bin/python scripts/snapshot_lan_hot_path_latency_harness.py logs/debug-trace-20260702-193152.jsonl
```

Result: passed. The old trace parsed successfully; it predates the new spans, so the newly added target rows are expected to be empty until a fresh targeted smoke is captured.

## Validation

Required validation commands:

```bash
.venv/bin/python -m py_compile dnd_initative_tracker.py server_runtime.py scripts/snapshot_lan_hot_path_latency_harness.py
.venv/bin/python scripts/snapshot_lan_hot_path_latency_harness.py logs/debug-trace-20260702-193152.jsonl
timeout 90s .venv/bin/python -m pytest tests/test_server_runtime.py
timeout 10s git diff --check
git status --short
```

Result: passed.

## Evidence Decision

Instrumentation added. Harness remains compatible with the required old trace.

No latency fix is selected. The new DM console instrumentation still needs developer-run targeted smoke/debug-trace evidence before any implementation decision.

Recommended next work item:

`WORK-20260702-dm-console-combat-read-model-targeted-smoke-evidence-capture`

Recommended type:

Evidence capture.
