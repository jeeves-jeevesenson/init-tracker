# WORK-20260630-runtime-facade-command-inventory-consolidation: ServerRuntimeFacade command inventory consolidation

## Status

Completed.

## Type

Docs-only consolidation. No app/source/test implementation.

## Goal

Create a durable `ServerRuntimeFacade` command inventory documenting the currently migrated queue-backed command boundary after the completed static map route migration sequence.

## Scope

- Created `docs/architecture/server_runtime_facade_command_inventory_20260630.md`.
- Documented migrated route-command mappings, command constants/action names, payload/result keys, response shapes, timeout/error behavior, trace/telemetry expectations, and focused tests.
- Documented direct/not-yet-queue-backed route risks from named files only.
- Documented naming/documentation gaps without changing source.
- Updated `docs/work_items/current_work.md` while leaving Current Status as `Idle`.

## Non-Goals / Forbidden Scope

- No app/source/test implementation.
- Did not edit `server_runtime.py`.
- Did not edit `dnd_initative_tracker.py`.
- Did not edit `tests/test_server_runtime.py`.
- Did not implement route migration.
- Did not create `init_tracker_server/`.
- Did not create package-boundary source files.
- Did not touch `docs/bug_reports/inbox/BUG-20260626-dmcontrol-terrain-not-visible.md`.
- Did not edit `logs/context/`.
- Did not inspect old plans, `majorTODO.md`, runtime reports, archived docs, broad logs, or unrelated files.
- Did not run full test suites.
- Did not push, deploy, restart services, SSH elsewhere, or alter production topology.

## Files Inspected

- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-next-boundary-checkpoint-decision.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-queue-migration-checkpoint.md`
- `docs/planning/living_docs/server_runtime_facade_queue_migration_checkpoint_20260630.md`
- `docs/architecture/server_runtime_extraction_decision_20260628.md`
- `docs/planning/living_docs/server_runtime_extraction_living_plan_20260628.md`
- `server_runtime.py`
- `dnd_initative_tracker.py`
- `tests/test_server_runtime.py`

## Files Edited

- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-command-inventory-consolidation.md`
- `docs/architecture/server_runtime_facade_command_inventory_20260630.md`

## Migrated Command Families Documented

- Spell color.
- Combatant map facing.
- Combatant place/reposition.
- Aura overlays.
- AoE remove/move.
- Static map cells: obstacle, terrain, elevation.
- Map settings.
- Background upsert/remove/order.
- Hazard upsert/remove.
- Feature upsert/remove.

## Direct Route / Risk Findings

Confirmed direct or not-yet-queue-backed candidates from named-file evidence include rules-aware combatant movement, AoE creation, structures, ships, structure templates, boarding links, turn/combat mutations, HP/combat state paths, and broader WebSocket/LAN action convergence.

The inventory marks unknowns explicitly where named-file evidence did not support a complete route or package-boundary claim.

## Recommended Next Action

Recommended next planning/evidence item:

`WORK-20260630-runtime-facade-package-boundary-readiness`

Purpose: decide whether app-host/runtime-service package-boundary planning can proceed from the now-durable command inventory, or whether command semantics cleanup planning should happen first.

## Validation

Required validation:

- `git status --short`
- `timeout 10s git diff --check`
