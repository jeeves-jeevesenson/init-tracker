# DM Console Combat Service Read-Model Implementation-Decision Planning - 2026-07-07

## Scope

This runtime report records a bounded docs/planning implementation-decision checkpoint using already accepted targeted smoke/debug-trace evidence.

No app code, tests, scripts, logs, browser assets, production configuration, routes, route registration, route bodies, payloads, snapshot schemas, cache behavior, resource-pools behavior, TTLs, static hydration, startup static-fields behavior, WebSocket behavior, queue behavior, launch/readiness/shutdown behavior, production topology, deploy, restart, SSH, push, commit, persistence, visibility/hidden-information behavior, map/terrain behavior, monster control, encounter state semantics, small smoke bug behavior, or gameplay behavior changed.

## Evidence Files

- Smoke log: `logs/smoke/WORK-20260702-dm-console-combat-read-model-targeted-smoke-evidence-capture_smoke-server_20260707-105332.log`
- Debug trace: `logs/debug-trace-20260707-105332.jsonl`
- Latest accepted evidence commit: `b486764`
- Latest instrumentation commit: `e05fb8f`

## Smoke Facts

The smoke log records headless tracker startup, debug trace creation, `/dm` and `/` advertisement, LAN hoist on port `8787`, browser LAN sessions, one LAN disconnect, and Dorian claim. The captured tail does not show unclaim before `Ctrl+C`.

The targeted trace remains the accepted latency input for this planning decision.

## Harness Summary

Harness command:

```bash
.venv/bin/python scripts/snapshot_lan_hot_path_latency_harness.py logs/debug-trace-20260707-105332.jsonl
```

Input parse result:

- valid JSON objects: `45,277`
- malformed/non-object lines: `0`

Load shape:

- combatants: `112`
- players: `10`
- monsters: `102`

Key rows used for the decision:

| Target | Count | p50 | p95 | Max |
| --- | ---: | ---: | ---: | ---: |
| `combat_service.combat_snapshot` | `44` | `269.380 ms` | `500.641 ms` | `660.390 ms` |
| `dm.console.combat_snapshot.service_call` | `41` | `270.945 ms` | `501.904 ms` | `660.880 ms` |
| `dm.console.combat_snapshot.copy` | `41` | `0.080 ms` | `0.719 ms` | `0.910 ms` |
| `dm.console.snapshot.payload` | `36` | `328.183 ms` | `647.329 ms` | `664.048 ms` |
| `dm.console.route_read_snapshot` | `25` | `352.772 ms` | `851.266 ms` | `987.922 ms` |
| `http.request:/api/dm/combat` | `25` | `385.621 ms` | `936.898 ms` | `1039.199 ms` |
| `dm.console.route_payload_proxy` | `25` | n/a | `0.514 ms` | n/a |
| `dm.console.snapshot.cache_check` | `39` | n/a | `0.914 ms` | n/a |
| `dm.console.payload.tactical_merge` | `41` | n/a | `4.043 ms` | n/a |
| `dm.console.payload.pending_prompts` | `41` | n/a | `0.927 ms` | n/a |
| `dm.console.payload.size_proxy` | `41` | n/a | `1.000 ms` | n/a |
| `lan.snapshot.resource_pools` | `1140` | `0.084 ms` | `14.497 ms` | `806.993 ms` |
| `lan.snapshot.units` | `1140` | `1.811 ms` | `21.864 ms` | `51.668 ms` |

Startup-only `lan.snapshot.static_fields` remains separate and deferred.

## Source-Seam Summary

Narrow source inspection found that `_dm_console_snapshot_payload()` records the expensive service call around `dm_service.combat_snapshot()`, then performs cheap result copy, optional tactical merge, pending-prompt merge, and size proxy work.

`CombatService.combat_snapshot()` builds the DM combat read model directly from tracker state. It gets combatants and display order, then builds each combatant row with derived role, passive perception, defense lists, state markers, AC modifiers, conditions, monster resources, current-turn markers, and speed/resource fields. It also computes up-next information and reads a bounded battle-log tail.

The accepted evidence plus this source shape points to service-internal read-model composition and repeated per-combatant derived helper work, not route infrastructure.

## Decision

Recommend a future narrow implementation slice.

The exact future seam should be `CombatService.combat_snapshot()` service-internal read-model composition, using a transient per-call composition context or equivalent helper/pre-indexing approach that emits the same output contract while reducing repeated derived helper work under large combatant counts.

The next recommendation is implementation, not more smoke evidence, not another planning checkpoint, and not broad instrumentation.

Recommended next work item:

`WORK-20260707-dm-console-combat-service-read-model-composition-minimal-implementation`

## Required Protections

The future implementation must preserve:

- exact DM combat snapshot payload keys, values, ordering, and schemas
- route behavior, route registration, route bodies, and HTTP mappings
- cache behavior, TTLs, static hydration, and startup static-fields behavior
- resource-pools behavior
- WebSocket behavior, queue behavior, auth/claims/reconnect behavior, and persistence
- visibility rules, hidden-information rules, monster visibility, tactical visibility, map/terrain behavior, monster control, encounter state semantics, player command behavior, combat mutation behavior, and gameplay/resource behavior
- production topology, deploy/restart/SSH behavior, launch commands, lifespan behavior, readiness behavior, and shutdown semantics

## Future Allowed Edit List

Recommended exact edit list for the future implementation:

- `combat_service.py`
- `dnd_initative_tracker.py`, only if a narrow read-only helper seam is required for `CombatService.combat_snapshot()`
- `tests/test_server_runtime.py`
- `tests/test_combat_service.py`, if focused service-contract coverage is added

No scripts, logs, route registration files, browser assets, production files, or unrelated docs should be edited by that implementation item unless its active packet explicitly changes scope.

## Validation

Required validation for this planning checkpoint:

```bash
.venv/bin/python scripts/snapshot_lan_hot_path_latency_harness.py logs/debug-trace-20260707-105332.jsonl
timeout 10s git diff --check
git status --short
```

Results are recorded in the final agent report.

Future implementation validation should add focused compile and unit/contract tests for edited Python files and a developer-owned post-implementation smoke/harness evidence run before claiming latency improvement.
