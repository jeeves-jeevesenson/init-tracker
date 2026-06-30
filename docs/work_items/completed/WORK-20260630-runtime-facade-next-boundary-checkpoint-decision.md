# WORK-20260630-runtime-facade-next-boundary-checkpoint-decision: Runtime facade next boundary checkpoint decision

## Status

Completed.

## Type

Evidence/planning decision only. No app implementation.

## Goal

Use the newly committed runtime facade queue migration checkpoint to choose exactly one next bounded server-runtime extraction lane:

- A. one more static map route migration;
- B. `ServerRuntimeFacade` command inventory/consolidation;
- C. app-host/runtime-service package-boundary planning.

## Initial State

Expected checkpoint commit was present at HEAD:

`9a3cd62 WORK-20260630-runtime-facade-queue-migration-checkpoint: document queue migration checkpoint`

Initial `git status --short` output:

```text
?? docs/bug_reports/inbox/BUG-20260626-dmcontrol-terrain-not-visible.md
?? logs/context/
```

`docs/work_items/current_work.md` was `Idle`, so the decision slice could proceed.

## Files Inspected

- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-queue-migration-checkpoint.md`
- `docs/planning/living_docs/server_runtime_facade_queue_migration_checkpoint_20260630.md`
- `docs/architecture/server_runtime_extraction_decision_20260628.md`
- `docs/planning/living_docs/server_runtime_extraction_living_plan_20260628.md`
- `server_runtime.py` through targeted command/facade inventory only.
- `dnd_initative_tracker.py` through targeted route/action inventory only.
- `tests/test_server_runtime.py` through targeted migrated-command/test inventory only.

## Files Edited

- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-next-boundary-checkpoint-decision.md`

## Option A: One More Static Map Route Migration

Recommendation: wait.

The inspected route inventory confirms the simple static map route loop has consumed the obvious low-risk candidates:

- `POST /api/dm/map/obstacles/cell`
- `POST /api/dm/map/terrain/cell`
- `POST /api/dm/map/elevation/cell`
- `POST /api/dm/map/settings`
- `POST /api/dm/map/backgrounds`
- `DELETE /api/dm/map/backgrounds/{bid}`
- `POST /api/dm/map/backgrounds/{bid}/order`
- `POST /api/dm/map/hazards`
- `DELETE /api/dm/map/hazards/{hazard_id}`
- `POST /api/dm/map/features`
- `DELETE /api/dm/map/features/{feature_id}`

Remaining direct static-map-looking candidates are structures:

- `POST /api/dm/map/structures`
- `POST /api/dm/map/structures/{structure_id}/move`
- `DELETE /api/dm/map/structures/{structure_id}`

These should not be treated as the same risk class as cells/backgrounds/hazards/features. The named-file evidence shows structure upsert/move/remove uses multi-cell `occupied_offsets`, canonical map capture, preset payloads, blocker semantics, `_move_map_structure(...)`, hydration, and broadcast behavior. The move route can return blocker details. That is medium risk, not the next obvious low-risk endpoint slice.

Ship, structure-template, and boarding-link routes are even less suitable as a quick endpoint slice:

- `POST /api/dm/map/ships`
- `POST /api/dm/map/ships/{structure_id}/maneuver`
- `POST /api/dm/map/ships/{source_structure_id}/weapons/fire`
- `POST /api/dm/map/ships/{source_structure_id}/ram`
- `POST /api/dm/map/structure-templates/{template_id}/instantiate`
- `POST /api/dm/map/boarding-links`
- `POST /api/dm/map/boarding-links/{link_id}/status`
- `DELETE /api/dm/map/boarding-links/{link_id}`

Those routes involve ship engagement state, placement preview/blockers, ship weapons/ramming, template placement, boarding link state, and synchronization/broadcast behavior. They need fresh evidence before implementation.

Conclusion: option A should wait because no remaining low-risk static map route is supported by the named-file evidence. The next route migration is likely structures, but it deserves a separate evidence/planning slice after the command boundary is made easier to reason about.

## Option B: ServerRuntimeFacade Command Inventory/Consolidation

Recommendation: select.

The command boundary is now large enough that consolidation should happen before more migration. `server_runtime.py` now exposes a migrated command set covering spell color, combatant facing/place, overlays, AoE remove/move, map cells, settings, backgrounds, hazards, and features. The route layer in `dnd_initative_tracker.py` maps many HTTP handlers to `RuntimeCommand(...)` plus repeated timeout/value/error mapping, while older spell-color command execution still differs from the newer queue-backed command family.

Evidence supporting consolidation now:

- Command constants and `submit_command(...)` branches are no longer a skeleton; they are a real route-authority surface.
- Route-to-command mapping is implicit across `server_runtime.py`, `dnd_initative_tracker.py`, and `tests/test_server_runtime.py`.
- Success payload names differ by family: `place_result`, `remove_result`, `move_result`, `obstacle_result`, `terrain_result`, `elevation_result`, `settings_result`, `background_result`, `remove_background_result`, `reorder_background_result`, `hazard_result`, and `feature_result`.
- Error semantics are repeated and should be documented as boundary rules before higher-risk migrations: `TimeoutError` maps to HTTP 504, `ValueError` maps to HTTP 400, and unexpected exceptions map to HTTP 500.
- Test inventory is substantial and command-specific; future route migrations need a durable naming and coverage map to avoid missing command constants, route mapping, result-key checks, and timeout/error tests.
- The command surface currently mixes direct facade execution for spell color with queue-backed LanController execution for the migrated map families. That can be acceptable temporarily, but it should be explicit before package-boundary planning or medium-risk route migrations.

Conclusion: option B is the best next lane because it lowers coordination risk without changing app behavior. It should be docs-only consolidation, not source consolidation, unless a later implementation work item explicitly authorizes code changes.

## Option C: App-Host/Runtime-Service Package-Boundary Planning

Recommendation: wait.

The architecture direction remains ASGI server first and runtime as a service. The server-first shell and runtime facade work already moved the repo in that direction, and package-boundary planning for `init_tracker_server/` or equivalent is still strategically valid.

It is too early for that lane as the immediate next item because the current command boundary still lacks a consolidated inventory. Starting package-boundary planning now would force the planning pass to reason about route ownership, command semantics, queue-backed versus direct command behavior, and test coverage from scattered source/test evidence. That increases the risk of designing a package boundary around an implicit or stale command map.

Conclusion: option C should wait until the command inventory is durable. Package-boundary planning becomes cleaner after the repo can point to a current command catalog that identifies migrated routes, remaining direct routes, error semantics, result payloads, and test coverage.

## Selected Next Work Item

Recommended next work item:

`WORK-20260630-runtime-facade-command-inventory-consolidation`

Title:

`ServerRuntimeFacade command inventory consolidation`

Type:

Docs-only consolidation. No app/source/test implementation.

Purpose:

Create a durable command inventory that maps migrated production routes to command constants, facade execution mode, queue action type, result payload key, route error mapping, and focused test coverage. Also document the still-direct route families and mark which future candidates require evidence before implementation.

## Proposed Next Task Scope

The next task should inspect exactly:

- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-queue-migration-checkpoint.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-next-boundary-checkpoint-decision.md`
- `docs/planning/living_docs/server_runtime_facade_queue_migration_checkpoint_20260630.md`
- `docs/architecture/server_runtime_extraction_decision_20260628.md`
- `docs/planning/living_docs/server_runtime_extraction_living_plan_20260628.md`
- `server_runtime.py` for command constants, `submit_command(...)`, `_submit_to_lan_queue(...)`, trace/status semantics, and direct spell-color handling.
- `dnd_initative_tracker.py` for only the migrated route handlers, remaining direct map route handlers, and `_lan_apply_action(...)` migrated command branches.
- `tests/test_server_runtime.py` for command imports, test names, route-command tests, success/failure/timeout coverage, and trace assertions.

The next task should be allowed to edit exactly:

- `docs/work_items/current_work.md`
- `docs/work_items/active/WORK-20260630-runtime-facade-command-inventory-consolidation.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-command-inventory-consolidation.md`
- `docs/planning/living_docs/server_runtime_facade_command_inventory_20260630.md`

The next task should not edit:

- `server_runtime.py`
- `dnd_initative_tracker.py`
- `tests/test_server_runtime.py`
- `docs/planning/living_docs/server_runtime_facade_queue_migration_checkpoint_20260630.md`
- package-boundary source files or any future `init_tracker_server/` package.

## Proposed Next Task Validation

Because the selected next item is docs-only, validation should be:

```text
git status --short
timeout 10s git diff --check
```

No Python tests are required for that docs-only pass unless its scope changes to source/test implementation, which this decision does not recommend.

## Stop Conditions

No stop condition was hit.

- Ledger was Idle.
- Checkpoint docs were present.
- Remaining route inventory was determinable from the named files.
- The decision did not require source/test edits.

## Validation

Required validation for this decision slice:

- `git status --short`
- `timeout 10s git diff --check`
