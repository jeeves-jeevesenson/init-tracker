# DM Console Combat Service Read-Model Composition Minimal Implementation - 2026-07-07

## Scope

This runtime report records the narrow behavior-preserving implementation pass for `WORK-20260707-dm-console-combat-service-read-model-composition-minimal-implementation`.

No route behavior, route registration, route body, response payload schema, snapshot schema, combat state semantic, turn order, initiative order, visibility/hidden-information behavior, tactical behavior, map/terrain behavior, monster control, encounter state semantic, player command behavior, combat mutation behavior, gameplay/resource behavior, resource-pools behavior, cache behavior, TTL, persistent cache, cross-request cache, WebSocket behavior, auth/claims/reconnect behavior, queue behavior, persistence, startup static-fields behavior, production topology, deploy/restart/SSH behavior, launch/readiness/shutdown behavior, browser asset, server start, browser smoke, push, commit, log edit, or small smoke bug behavior changed.

## Implementation Summary

`CombatService.combat_snapshot()` now uses a transient per-call composition context to reduce repeated read-model derivation overhead:

- helper callables are captured once per call
- ordered entries are staged once per call
- passive perception, defense-list, and AC-modifier helper results are cached only for the current call
- `_monster_resource_state` is indexed once by combatant id instead of scanned once per combatant row

Payload shape, ordering, values, hidden-state handling, tactical behavior, and gameplay semantics are preserved by continuing to use the same tracker helper return values and row construction contract.

## Test Coverage Added

Focused `tests/test_server_runtime.py` coverage verifies:

- `combat_snapshot()` top-level key order, combatant row key order, row order, turn order, battle-log limit, and monster resource values
- hidden-state markers are not broadened to non-hidden rows and tactical data is not introduced
- `/api/dm/combat` route test harness preserves top-level snapshot structure and non-tactical read context
- per-call context does not leak across calls when helper results/resource state change

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

## Follow-Up

Recommended next work is developer-run targeted smoke evidence capture with a fresh debug trace and the existing latency harness. Resource-pools remains closed, startup static-fields remains untouched/deferred, and the small smoke bug remains unpatched.
