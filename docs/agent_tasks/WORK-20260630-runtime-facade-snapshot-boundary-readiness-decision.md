Task ID:
WORK-20260630-runtime-facade-snapshot-boundary-readiness-decision

Repo path:
~/src/init-tracker

Mode:
Codex bounded planning/decision pass only.

Goal / gate / work item:
Create the durable readiness decision for a future `ServerRuntimeFacade.read_snapshot()` implementation before any implementation begins.

Source documents:
- `docs/work_items/current_work.md`
- `docs/planning/living_docs/server_runtime_snapshot_boundary_checkpoint_20260630.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-snapshot-boundary-checkpoint.md`
- `docs/planning/living_docs/server_runtime_package_boundary_plan_20260630.md`
- `docs/architecture/server_runtime_facade_command_inventory_20260630.md`
- `docs/architecture/server_runtime_extraction_decision_20260628.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-package-import-realignment.md`
- `server_runtime.py`
- `dnd_initative_tracker.py`
- `combat_service.py`
- `tests/test_server_runtime.py`
- `AGENTS.md`
- `docs/agent_tasks/templates/task-packet.md`

Files to inspect first:
- `docs/work_items/current_work.md`
- `docs/planning/living_docs/server_runtime_snapshot_boundary_checkpoint_20260630.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-snapshot-boundary-checkpoint.md`
- `server_runtime.py`
- `dnd_initative_tracker.py`
- `combat_service.py`
- `tests/test_server_runtime.py`

Allowed files:
- `docs/work_items/current_work.md`
- `docs/work_items/active/WORK-20260630-runtime-facade-snapshot-boundary-readiness-decision.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-snapshot-boundary-readiness-decision.md`
- `docs/planning/living_docs/server_runtime_snapshot_boundary_readiness_decision_20260630.md`
- `docs/agent_tasks/WORK-20260630-runtime-facade-snapshot-boundary-readiness-decision.md`

Forbidden scope:
- Do not implement `read_snapshot()`.
- Do not edit runtime/app/source/test behavior.
- Do not edit `server_runtime.py`.
- Do not edit `init_tracker_server/app.py`.
- Do not edit `init_tracker_server/runtime.py`.
- Do not edit `server_app.py`.
- Do not edit `dnd_initative_tracker.py`.
- Do not edit `combat_service.py`.
- Do not edit tests.
- Do not touch `docs/bug_reports/inbox/BUG-20260626-dmcontrol-terrain-not-visible.md`.
- Do not touch `logs/context/`.
- Do not add snapshot code, route offload, instrumentation, direct-route migration, queue behavior changes, WebSocket behavior changes, gameplay changes, LAN controller changes, Tk behavior changes, or deployment/topology changes.
- Do not use AGY.
- Do not use Gemini.
- Do not push, deploy, restart services, change ports, run browser smoke, or run broad tests.

Required decision contents:
- Current status.
- `RuntimeSnapshotRequest` semantics.
- `RuntimeSnapshotResult` semantics.
- Fail-open/fail-closed behavior.
- Cache/prebuild ownership and invalidation posture.
- Later implementation boundary.
- Later validation plan.
- Explicit deferred scope.
- Recommended exact next task.

Validation commands:
- `git status --short`
- `timeout 10s git diff --check`

Stop / logging conditions:
- Stop if `current_work.md` does not show snapshot-boundary readiness/decision as the allowed next action.
- Stop if the completed snapshot-boundary checkpoint is missing.
- Stop if required source docs are missing.
- Stop if implementation or source/test edits are needed.
- Stop after the listed validation commands and final report.

Final report requirements:
- Files read.
- Targeted source/test ranges inspected.
- Files changed.
- Snapshot request/result semantics decision.
- Fail behavior decision.
- Cache/prebuild ownership decision.
- Exact next task selected.
- Validation command output.
- `git status --short` after the pass.
- Whether the pre-existing untracked inbox bug and `logs/context/` remained untouched.

