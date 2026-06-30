Task ID:
WORK-20260630-runtime-facade-package-import-realignment

Repo path:
~/src/init-tracker

Mode:
Codex bounded implementation pass.

Goal / gate / work item:
Implement the approved package-internal import realignment so `init_tracker_server/app.py` imports `ServerRuntimeFacade` through `init_tracker_server.runtime` instead of directly from `server_runtime.py`.

Source documents:
- `docs/work_items/current_work.md`
- `docs/planning/living_docs/server_runtime_package_import_realignment_decision_20260630.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-package-import-realignment-decision.md`
- `docs/planning/living_docs/server_runtime_package_boundary_plan_20260630.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-runtime-reexport-boundary.md`
- `init_tracker_server/runtime.py`
- `init_tracker_server/app.py`
- `server_runtime.py`
- `server_app.py`

Files to inspect first:
- `docs/work_items/current_work.md`
- `docs/planning/living_docs/server_runtime_package_import_realignment_decision_20260630.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-package-import-realignment-decision.md`
- `init_tracker_server/runtime.py`
- `init_tracker_server/app.py`
- `server_app.py`

Allowed files:
- `init_tracker_server/app.py`
- `docs/work_items/current_work.md`
- `docs/work_items/active/WORK-20260630-runtime-facade-package-import-realignment.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-package-import-realignment.md`
- `docs/agent_tasks/WORK-20260630-runtime-facade-package-import-realignment.md`

Forbidden scope:
- Do not edit `server_runtime.py`.
- Do not edit `init_tracker_server/runtime.py`.
- Do not edit `server_app.py` unless validation proves an import compatibility issue and work stops before editing.
- Do not edit tests.
- Do not implement snapshots, migrate routes, alter queue/WebSocket/gameplay behavior, or change deployment topology.
- Do not use AGY or Gemini.
- Do not push, deploy, restart services, change ports, run browser smoke, or run broad tests.

Validation commands:
- `git status --short`
- `timeout 10s git diff --check`
- `timeout 10s .venv/bin/python -m py_compile init_tracker_server/app.py init_tracker_server/runtime.py server_app.py`
- `timeout 10s .venv/bin/python - <<'PY'
import init_tracker_server.app as package_app
import init_tracker_server.runtime as package_runtime
import server_runtime

assert package_app.ServerRuntimeFacade is package_runtime.ServerRuntimeFacade
assert package_runtime.ServerRuntimeFacade is server_runtime.ServerRuntimeFacade

import server_app
assert hasattr(server_app, "create_app")

print("package runtime import boundary ok")
PY`
- `timeout 30s .venv/bin/python -m pytest tests/test_server_runtime.py -q`

Stop / logging conditions:
- Stop if `current_work.md` does not allow the package import realignment.
- Stop if the decision doc is missing or does not approve the import realignment.
- Stop if implementation requires files outside the allowed list.
- Stop if validation fails.
- Stop immediately after listed validation and final report.
