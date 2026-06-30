# WORK-20260630-runtime-facade-runtime-import-boundary-plan: Runtime facade import-boundary decision

## Status

Completed.

## Type

Planning/evidence only. No source implementation.

## Goal

Decide the safest runtime facade ownership/import-boundary slice after the new `init_tracker_server` package skeleton.

## Initial Repository State

Initial `git status --short`:

```text
?? docs/bug_reports/inbox/BUG-20260626-dmcontrol-terrain-not-visible.md
?? logs/context/
```

Initial `HEAD` evidence:

```text
cdcfc45 WORK-20260630-runtime-facade-package-skeleton: add package app factory shim
```

The current-work ledger was `Idle` at the start of this pass.

## Files Inspected

- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-package-skeleton.md`
- `docs/planning/living_docs/server_runtime_package_boundary_plan_20260630.md`
- `docs/architecture/server_runtime_facade_command_inventory_20260630.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-package-boundary-plan.md`
- `docs/architecture/server_runtime_extraction_decision_20260628.md`
- `docs/planning/living_docs/server_runtime_extraction_living_plan_20260628.md`
- `init_tracker_server/__init__.py`
- `init_tracker_server/app.py`
- `server_app.py`
- `server_runtime.py`
- `tests/test_server_health.py`
- `tests/test_server_runtime.py`
- `tests/test_headless_host.py`
- `tests/test_server_app.py`, discovered by the targeted `from server_runtime` import grep.

## Files Changed

- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-runtime-import-boundary-plan.md`

No source files, tests, routes, runtime contracts, command behavior, imports, deployment files, bug inbox files, or logs were changed.

## Evidence Summary

`init_tracker_server/app.py` currently imports `ServerRuntimeFacade` directly from `server_runtime.py`.

`server_app.py` is already a compatibility shim that re-exports `app_lifespan` and `create_app` from `init_tracker_server.app`.

`server_runtime.py` still owns the concrete runtime facade implementation, command/result/trace/snapshot dataclasses, lifecycle status constants, command constants, queue submission helper, timeout/error mapping, command dispatch branches, trace updates, and fail-closed snapshot method.

Targeted import grep found current direct `server_runtime` consumers:

- `dnd_initative_tracker.py`
- `init_tracker_server/app.py`
- `tests/test_server_runtime.py`
- `tests/test_server_app.py`

No `import server_runtime` module import form was found by the targeted grep; current consumers use `from server_runtime import ...`.

## Option Comparison

### Option A: Minimal package re-export boundary

Recommendation: choose this option next.

This would add `init_tracker_server/runtime.py` as a package-owned import boundary that imports and re-exports `ServerRuntimeFacade` and the existing command/snapshot contract names from `server_runtime.py`. `server_runtime.py` remains the implementation source for now.

This is the safest next slice because it creates the desired package import location without moving the high-churn implementation, without changing direct legacy imports, and without normalizing command constants, result keys, trace names, timeout behavior, queue behavior, route behavior, or snapshot behavior.

### Option B: Move `ServerRuntimeFacade` implementation into `init_tracker_server/runtime.py`

Recommendation: wait.

The implementation is still coupled to command contract definitions, command constants, queue adapter behavior, trace semantics, and many direct tests. The targeted import grep shows direct `server_runtime` consumers in app/package code, tracker route code, and tests. Moving the implementation now would force a compatibility shim plus broader import/test churn in the same pass, increasing risk without providing behavior value beyond what Option A can provide.

### Option C: Defer runtime import-boundary implementation

Recommendation: wait.

The existing package-boundary plan and command inventory are sufficient for a minimal re-export boundary. Known command-semantics gaps are real, but Option A avoids semantics cleanup entirely by preserving `server_runtime.py` as the source of truth. Deferring to another docs-only pass would not materially reduce risk for the next implementation step.

## Selected Recommended Next Work Item

ID: `WORK-20260630-runtime-facade-runtime-reexport-boundary`

Title: Add package runtime re-export boundary

Type: Focused implementation slice.

Goal: Add `init_tracker_server/runtime.py` as the stable package import boundary for the existing runtime facade and command/snapshot contracts while preserving `server_runtime.py` as the implementation source and compatibility import location.

## Exact Files The Next Task Should Inspect

- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-runtime-import-boundary-plan.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-package-skeleton.md`
- `docs/planning/living_docs/server_runtime_package_boundary_plan_20260630.md`
- `docs/architecture/server_runtime_facade_command_inventory_20260630.md`
- `init_tracker_server/__init__.py`
- `init_tracker_server/app.py`
- `server_app.py`
- `server_runtime.py`
- `tests/test_server_health.py`
- `tests/test_server_app.py`
- `tests/test_server_runtime.py`
- `tests/test_headless_host.py`
- Targeted grep only for `from server_runtime` import consumers, excluding `.git`, `.venv`, `logs`, and `majorTODO.md`.

## Exact Allowed Files The Next Task Should Edit

- `init_tracker_server/runtime.py`
- `init_tracker_server/__init__.py`
- `init_tracker_server/app.py`
- `tests/test_server_app.py`
- `tests/test_server_health.py`
- `docs/work_items/current_work.md`
- `docs/work_items/active/WORK-20260630-runtime-facade-runtime-reexport-boundary.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-runtime-reexport-boundary.md`

The next implementation should avoid editing tests unless needed to prove the package re-export contract and app factory import boundary.

## Explicit Forbidden Scope For The Next Task

- Do not edit `server_runtime.py`.
- Do not edit `server_app.py`.
- Do not edit `dnd_initative_tracker.py`.
- Do not move `ServerRuntimeFacade`.
- Do not split command dataclasses, status constants, command constants, snapshot contracts, queue adapter logic, or trace logic out of `server_runtime.py`.
- Do not change imports outside package-side code and targeted tests.
- Do not change command constants, command action strings, `submit_command` behavior, timeout/error behavior, trace behavior, route behavior, WebSocket behavior, snapshot/cache behavior, gameplay behavior, saved-data/YAML compatibility, deployment topology, launchers, production runbooks, or production services.
- Do not migrate routes.
- Do not touch `docs/bug_reports/inbox/BUG-20260626-dmcontrol-terrain-not-visible.md`.
- Do not edit `logs/context/`.
- Do not inspect old plans, `majorTODO.md`, runtime reports, archived docs, broad logs, or unrelated files.
- Do not run full test suites.
- Do not commit, push, deploy, restart services, SSH elsewhere, or alter production topology.

## Suggested Validation For The Next Task

- `python3 -m py_compile init_tracker_server/__init__.py init_tracker_server/app.py init_tracker_server/runtime.py tests/test_server_app.py tests/test_server_health.py`
- `timeout 30s python3 -m unittest tests.test_server_health tests.test_server_app`
- `timeout 30s python3 -m unittest tests.test_server_runtime`
- `timeout 10s git diff --check`
- `git status --short`

## Validation For This Planning Pass

Required validation:

- `git status --short`
- `timeout 10s git diff --check`

Validation output is recorded in the final report for this pass.

## Stop Conditions

No stop condition was hit.

The ledger was `Idle`, the package skeleton and package-boundary docs were present, the decision did not require source/test edits, and import usage was determinable from named files plus targeted greps.
