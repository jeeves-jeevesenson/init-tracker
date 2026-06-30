# WORK-20260630-runtime-facade-package-import-realignment: Runtime facade package import realignment

## Status

Completed.

## Type

Focused implementation slice.

## Goal

Implement the approved package-internal import realignment so `init_tracker_server/app.py` imports `ServerRuntimeFacade` through the package runtime boundary instead of directly from `server_runtime.py`.

## Initial Repository State

Initial `git status --short`:

```text
?? docs/bug_reports/inbox/BUG-20260626-dmcontrol-terrain-not-visible.md
?? logs/context/
```

The current-work ledger allowed opening `WORK-20260630-runtime-facade-package-import-realignment` as the next action, and the decision document approved only this import realignment.

## Files Inspected

- `docs/work_items/current_work.md`
- `docs/planning/living_docs/server_runtime_package_import_realignment_decision_20260630.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-package-import-realignment-decision.md`
- `docs/planning/living_docs/server_runtime_package_boundary_plan_20260630.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-runtime-reexport-boundary.md`
- `docs/agent_tasks/templates/task-packet.md`
- `docs/agent_tasks/WORK-20260630-runtime-facade-package-import-realignment-decision.md`
- `init_tracker_server/runtime.py`
- `init_tracker_server/app.py`
- `server_app.py`

## Files Changed

- `init_tracker_server/app.py`
- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-package-import-realignment.md`
- `docs/agent_tasks/WORK-20260630-runtime-facade-package-import-realignment.md`

## Import Change

`init_tracker_server/app.py` now imports the facade through the package runtime boundary:

```python
from .runtime import ServerRuntimeFacade
```

It no longer imports `ServerRuntimeFacade` directly from `server_runtime.py`.

## Compatibility Preserved

- `server_runtime.py` remains the implementation source.
- `init_tracker_server/runtime.py` was not changed.
- `server_app.py` was not changed.
- `app.state.runtime = ServerRuntimeFacade(lan_controller=lan_controller)` behavior is preserved, with `ServerRuntimeFacade` resolved through `init_tracker_server.runtime`.
- No route, queue, snapshot, WebSocket, gameplay, LAN controller, Tk, DM/player surface, deployment, topology, port, or service behavior was changed.

## Validation

Required validation was run after the implementation and ledger updates:

- `git status --short`
- `timeout 10s git diff --check`
- `timeout 10s .venv/bin/python -m py_compile init_tracker_server/app.py init_tracker_server/runtime.py server_app.py`
- `timeout 10s .venv/bin/python - <<'PY' ...`
- `timeout 30s .venv/bin/python -m pytest tests/test_server_runtime.py -q`

Results:

```text
py_compile: passed
import identity check: package runtime import boundary ok
pytest tests/test_server_runtime.py -q: 58 passed, 29 subtests passed
```

Final command output is recorded in the final report for this pass.

## Remaining Inline / Out Of Scope

All runtime implementation remains in `server_runtime.py`.

No commands or branches were migrated. No handlers, dispatchers, contracts, routes, snapshots, direct-route offloads, or instrumentation were introduced or changed.

## Ledger Update

`docs/work_items/current_work.md` was returned to Idle after completion and now recommends opening a separate snapshot-boundary checkpoint/planning pass next. Snapshot implementation remains explicitly deferred.

## Untouched Pre-existing Untracked Paths

The pre-existing untracked inbox bug and context logs remained untouched:

- `docs/bug_reports/inbox/BUG-20260626-dmcontrol-terrain-not-visible.md`
- `logs/context/`

## Next Broad Pass

Open a snapshot-boundary checkpoint/planning pass to decide the next package-runtime read-model boundary step before implementing any snapshot work.
