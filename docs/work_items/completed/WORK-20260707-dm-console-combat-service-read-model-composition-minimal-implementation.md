# WORK-20260707-dm-console-combat-service-read-model-composition-minimal-implementation

Status: Completed

## Goal

Implement the smallest safe refinement for DM console combat read-model latency by reducing repeated per-call/per-combatant derived helper work inside `CombatService.combat_snapshot()`.

## Files Inspected

- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260707-dm-console-combat-service-read-model-implementation-decision-planning-checkpoint.md`
- `docs/planning/living_docs/dm_console_combat_service_read_model_implementation_decision_planning_checkpoint_20260707.md`
- `docs/runtime_reports/dm_console_combat_service_read_model_implementation_decision_planning_20260707.md`
- `docs/work_items/completed/WORK-20260702-dm-console-combat-read-model-targeted-smoke-evidence-capture.md`
- `docs/runtime_reports/dm_console_combat_read_model_targeted_smoke_evidence_20260707.md`
- `combat_service.py`, limited to `CombatService.combat_snapshot()` and direct helper-call context
- `dnd_initative_tracker.py`, limited to `_dm_console_snapshot()`, `_dm_console_snapshot_payload()`, and direct helper definitions used by `combat_snapshot()`
- `tests/test_server_runtime.py`, limited to existing DM console/combat snapshot/read-model route patterns
- `tests/test_dm_combat_service.py`, limited to existing `combat_snapshot()` contract-test patterns for reference only
- `helper_script.py`, limited to `_display_order()` for direct helper context

## Files Changed

- `combat_service.py`
- `tests/test_server_runtime.py`
- `docs/work_items/current_work.md`
- `docs/work_items/active/WORK-20260707-dm-console-combat-service-read-model-composition-minimal-implementation.md` (created while active, removed at completion)
- `docs/work_items/completed/WORK-20260707-dm-console-combat-service-read-model-composition-minimal-implementation.md`
- `docs/planning/living_docs/dm_console_combat_service_read_model_composition_minimal_implementation_20260707.md`
- `docs/runtime_reports/dm_console_combat_service_read_model_composition_minimal_implementation_20260707.md`

## Implementation

`CombatService.combat_snapshot()` now creates a transient per-call composition context local to one snapshot call.

The context captures tracker helper callables once, stages ordered combatant entries once, caches passive perception, defense-list, and AC-modifier helper results in per-call dictionaries, and pre-indexes `_monster_resource_state` once by combatant id. Combatant row projection still uses the same helper return values, row key order, top-level key order, turn-order list, up-next helper, battle-log helper, hidden-state marker logic, conditions, resource values, and current-turn markers as before.

The concrete repeated work reduced is the previous per-combatant filtering scan over every `_monster_resource_state` key. The snapshot now performs one pass over resource keys and then does per-row dictionary lookup/copy. Helper callable lookup is also moved out of the per-row path, and per-call helper-result maps prevent duplicate derived helper calls within one snapshot call.

No persistent cache, cross-request cache, TTL change, route change, response schema change, snapshot schema change, combat-state change, turn/initiative ordering change, visibility/hidden-information change, tactical change, resource-pools change, startup static-fields change, or gameplay/resource behavior change was introduced.

## Tests

Focused coverage was added in `tests/test_server_runtime.py` for:

- stable `combat_snapshot()` top-level key order, combatant row key order, turn order, row order, battle-log limit, and monster-resource values
- visibility-sensitive hidden markers staying scoped to the hidden combatant and not broadening into non-hidden rows or tactical payloads
- DM console route snapshot top-level structure and non-tactical read context remaining stable
- per-call context transience by mutating passive perception, AC modifier, defenses, and monster resources between two snapshot calls and verifying the second call sees new state while the first payload remains unchanged

## Deferred

Resource-pools remains closed. Startup-only `lan.snapshot.static_fields` was not touched. The small smoke bug was not patched. Browser smoke, server start, deploy, restart, SSH, push, commit, route migration, route registration changes, route body movement, cache ownership/TTL changes, resource-pools changes, WebSocket/queue/auth/reconnect changes, and gameplay changes remain out of scope.

## Validation

Required validation commands:

```bash
.venv/bin/python -m py_compile combat_service.py dnd_initative_tracker.py
timeout 90s .venv/bin/python -m pytest tests/test_server_runtime.py
.venv/bin/python scripts/snapshot_lan_hot_path_latency_harness.py logs/debug-trace-20260707-105332.jsonl
timeout 10s git diff --check
git status --short
```

Results are recorded in the final agent report.

## Recommended Next Work

Developer-run targeted smoke evidence capture with a fresh debug trace and the existing latency harness before claiming latency improvement.
