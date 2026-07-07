# DM Console Combat Service Read-Model Composition Minimal Implementation - 2026-07-07

## Scope

This document records the bounded implementation selected by the completed planning checkpoint at commit `18c19c3`.

The implementation is limited to `CombatService.combat_snapshot()` service-internal read-model composition and focused regression coverage in `tests/test_server_runtime.py`.

## Implementation Seam

`CombatService.combat_snapshot()` now builds a local transient composition context per call:

- tracker helper callables for role, passive perception, defenses, and AC modifiers are read once per snapshot call
- ordered combatant entries are staged once from the existing display-order result
- passive perception, defense-list, and AC-modifier values are cached in dictionaries scoped to the current snapshot call
- monster resource state is indexed once by combatant id, replacing repeated per-combatant scans over every resource-state key

The context disappears when `combat_snapshot()` returns. No persistent cache, cross-request cache, cache TTL, route behavior, route registration, route body, payload schema, snapshot schema, visibility rule, hidden-information rule, tactical behavior, resource-pools behavior, startup static-fields behavior, WebSocket behavior, queue behavior, persistence, production topology, or gameplay behavior changed.

## Behavior Preservation

The row projection still delegates rule-owned values to the existing tracker helpers and preserves existing normalization. Top-level snapshot key order, combatant row key order, turn-order list, row order, active/up-next fields, battle-log tail, hidden-state markers, condition projection, monster resource keys/values, and current-turn markers remain stable.

## Tests

`tests/test_server_runtime.py` now includes focused regressions for payload shape/order, visibility-sensitive fields, DM console route top-level structure, and context transience across two snapshot calls.

## Next Step

Run developer-owned targeted smoke evidence capture with a fresh debug trace and the existing latency harness before claiming latency improvement.
