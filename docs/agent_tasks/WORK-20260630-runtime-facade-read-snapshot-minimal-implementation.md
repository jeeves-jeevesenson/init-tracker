# WORK-20260630-runtime-facade-read-snapshot-minimal-implementation

## Executor

Codex

## Mode

Bounded implementation pass.

## Goal

Implement the minimal `ServerRuntimeFacade.read_snapshot()` boundary approved by the snapshot-boundary readiness decision.

## Source documents

- `docs/work_items/current_work.md`
- `docs/planning/living_docs/server_runtime_snapshot_boundary_readiness_decision_20260630.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-snapshot-boundary-readiness-decision.md`
- `docs/planning/living_docs/server_runtime_snapshot_boundary_checkpoint_20260630.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-snapshot-boundary-checkpoint.md`
- `docs/architecture/server_runtime_facade_command_inventory_20260630.md`
- `docs/architecture/server_runtime_extraction_decision_20260628.md`
- `server_runtime.py`
- `tests/test_server_runtime.py`

## Files changed

- `server_runtime.py`
- `tests/test_server_runtime.py`
- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-read-snapshot-minimal-implementation.md`

## Forbidden scope

No route adoption, direct-route migration, route offload, instrumentation, queue/WebSocket/gameplay/Tk/LAN changes, cache relocation, cache TTL changes, static hydration, deployment, push, browser smoke, AGY, or Gemini.

## Implemented behavior

`ServerRuntimeFacade.read_snapshot()` now supports the approved minimal modes:

- `combat`
- `tactical`
- `dm_console`

It fails closed before readiness, for unsupported modes, static hydration requests, missing legacy references, and builder failures. It delegates to existing legacy builders and does not create façade-owned cache behavior.

## Validation

- `git status --short`
- `timeout 10s git diff --check`
- `timeout 10s .venv/bin/python -m py_compile server_runtime.py tests/test_server_runtime.py`
- `timeout 30s .venv/bin/python -m pytest tests/test_server_runtime.py -q`

## Result

Implementation completed with focused tests. Validation reported:

- `65 passed, 29 subtests passed`
- pre-existing untracked `docs/bug_reports/inbox/BUG-20260626-dmcontrol-terrain-not-visible.md` and `logs/context/` remained untouched.
