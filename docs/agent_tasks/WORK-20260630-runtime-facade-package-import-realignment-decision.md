Task ID:
WORK-20260630-runtime-facade-package-import-realignment-decision

Repo path:
~/src/init-tracker

Mode:
Codex bounded planning/documentation pass only.

Goal / gate / work item:
Open the package-internal import realignment decision slice for the runtime facade package boundary.

Source document:
- `docs/work_items/current_work.md`
- `docs/planning/living_docs/server_runtime_package_boundary_plan_20260630.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-runtime-reexport-boundary.md`
- `docs/planning/living_docs/server_runtime_package_import_realignment_decision_20260630.md`
- `docs/work_items/active/WORK-20260630-runtime-facade-package-import-realignment-decision.md`

Files to inspect first:
- `docs/work_items/current_work.md`
- `docs/planning/living_docs/server_runtime_package_boundary_plan_20260630.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-runtime-reexport-boundary.md`
- `init_tracker_server/runtime.py`
- `init_tracker_server/app.py`

Allowed files:
- `docs/work_items/current_work.md`
- `docs/work_items/active/WORK-20260630-runtime-facade-package-import-realignment-decision.md`
- `docs/planning/living_docs/server_runtime_package_import_realignment_decision_20260630.md`
- `docs/agent_tasks/WORK-20260630-runtime-facade-package-import-realignment-decision.md`

Forbidden scope:
- Do not edit app/runtime implementation files.
- Do not edit tests.
- Do not modify `server_runtime.py`.
- Do not modify `init_tracker_server/app.py`.
- Do not modify `init_tracker_server/runtime.py`.
- Do not modify `server_app.py`.
- Do not modify `dnd_initative_tracker.py`.
- Do not modify `combat_service.py`.
- Do not reopen old plans.
- Do not use `majorTODO.md`.
- Do not use completed work as active work except as source evidence.
- Do not touch inbox bugs.
- Do not choose the next direct route migration.
- Do not inspect broad unrelated files.
- Do not run full test suites.
- Do not push, deploy, restart services, change ports, or run browser smoke.
- Do not use AGY or Gemini.

Decision made:
Approve a minimal later implementation slice that updates only `init_tracker_server/app.py` so `ServerRuntimeFacade` is imported from `init_tracker_server.runtime` instead of `server_runtime.py`, while keeping `server_runtime.py` as the implementation source.

Later implementation boundary:
- Preserve public compatibility.
- Keep `server_runtime.py` as implementation source.
- No snapshot implementation.
- No direct-route migration.
- No route offload.
- No instrumentation change.

Validation commands:
- `git status --short`
- `timeout 10s git diff --check`

Stop / logging conditions:
- Stop if `docs/work_items/current_work.md` does not match the expected Idle / no active work state.
- Stop if the package-boundary plan or runtime re-export completion doc is missing.
- Stop if files outside the named inspect list are needed.
- Stop after writing the decision docs and running validation.

Final report requirements:
- Files read.
- Files changed.
- Decision made.
- Exact next implementation task recommended.
- Validation command output.
- `git status --short` after the pass.
