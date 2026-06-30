Task ID:
WORK-20260630-runtime-facade-snapshot-boundary-checkpoint

Repo path:
~/src/init-tracker

Mode:
Codex bounded planning/documentation pass only.

Goal / gate / work item:
Create the durable snapshot/read-model boundary checkpoint for the server runtime extraction lane. Do not implement `read_snapshot()`, route offload, instrumentation, or any route migration.

Source documents:
- `docs/work_items/current_work.md`
- `docs/planning/living_docs/server_runtime_package_boundary_plan_20260630.md`
- `docs/planning/living_docs/server_runtime_package_import_realignment_decision_20260630.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-package-import-realignment.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-queue-migration-checkpoint.md`
- `docs/architecture/server_runtime_facade_command_inventory_20260630.md`
- `docs/architecture/server_runtime_extraction_decision_20260628.md`
- `server_runtime.py`
- `dnd_initative_tracker.py`
- `combat_service.py`
- `AGENTS.md`
- `docs/agent_tasks/templates/task-packet.md`

Files inspected first:
- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-package-import-realignment.md`
- `docs/planning/living_docs/server_runtime_package_boundary_plan_20260630.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-queue-migration-checkpoint.md`
- `docs/architecture/server_runtime_facade_command_inventory_20260630.md`
- `server_runtime.py`
- `dnd_initative_tracker.py`
- `combat_service.py`

Allowed files:
- `docs/work_items/current_work.md`
- `docs/work_items/active/WORK-20260630-runtime-facade-snapshot-boundary-checkpoint.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-snapshot-boundary-checkpoint.md`
- `docs/planning/living_docs/server_runtime_snapshot_boundary_checkpoint_20260630.md`
- `docs/agent_tasks/WORK-20260630-runtime-facade-snapshot-boundary-checkpoint.md`

Forbidden scope:
- No app/runtime implementation file edits.
- No `read_snapshot()` implementation.
- No snapshot code.
- No route offload.
- No instrumentation.
- No route migration.
- No tests.
- No broad repo scan.
- No production deployment, push, service restart, topology change, or browser smoke.

Validation commands:
- `git status --short`
- `timeout 10s git diff --check`

Stop / logging conditions:
- Stop if the ledger does not allow this checkpoint pass.
- Stop if required source docs are missing.
- Stop if implementation edits are needed.
- Stop after required validation and report.

