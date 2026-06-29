# WORK-20260628-server-first-health-shell: Server-first health and app factory shell

- **Status:** Active
- **Gate:** Server Ownership Shell Gate
- **Opened:** 2026-06-28
- **Executor:** AGY by explicit bounded task packet, or developer no-agent patch if chosen.
- **Current phase:** Phase 1 from `docs/planning/living_docs/server_runtime_extraction_living_plan_20260628.md`

## Goal

Add the smallest server-first app-factory and health/readiness shell needed to start moving hosted runtime ownership toward ASGI.

This is a narrow foundation task. It must preserve existing `serve_headless.py` behavior and must not migrate gameplay routes yet.

## Source documents to read first

- `AGENTS.md`
- `docs/work_items/current_work.md`
- `docs/architecture/server_runtime_extraction_decision_20260628.md`
- `docs/planning/living_docs/server_runtime_extraction_living_plan_20260628.md`

## Files to inspect first for implementation

- `serve_headless.py`
- `dnd_initative_tracker.py`
- existing FastAPI/LAN server setup files named from `serve_headless.py` or `dnd_initative_tracker.py`
- existing health/status routes, if named by the inspected files

## Candidate allowed implementation scope

The eventual implementation task may edit only files explicitly named in its AGY task packet.

Expected likely scope:
- a new small app-factory module if needed
- `serve_headless.py` compatibility launcher changes if needed
- focused tests for app factory or health/readiness only
- this work item and `docs/work_items/current_work.md` for evidence updates

## Forbidden scope

- Do not migrate gameplay routes.
- Do not add runtime facade behavior beyond a placeholder/adapter needed for app startup.
- Do not implement command queue.
- Do not implement snapshot cache changes.
- Do not edit frontend assets.
- Do not edit combat rules, player command logic, monster control behavior, tactical map behavior, YAML data, or production deployment config.
- Do not run broad test suites.
- Do not run browser smoke unless the developer explicitly authorizes it.
- Do not push, deploy, restart services, alter DNS/FQDNs, or touch production topology.
- Do not inspect old plans, old bugs, `majorTODO.md`, runtime reports, or logs unless named by the AGY task packet.

## Implementation acceptance criteria

A future implementation pass must prove:

1. There is a repo-supported FastAPI app factory or equivalent server-owned construction seam.
2. There are bounded health/readiness endpoints or existing equivalents are clearly wired through the factory.
3. `serve_headless.py` remains the supported developer smoke launcher.
4. No gameplay behavior is intentionally changed.
5. Validation is scoped and timeout-bounded.

## Validation for the work item opening commit

Run:

    git status --short
    timeout 10s git diff --check
    git diff -- docs/work_items/current_work.md docs/work_items/active/WORK-20260628-server-first-health-shell.md

## Future implementation validation candidates

The AGY task packet must choose exact validation after inspecting named files. Likely candidates:

    timeout 10s .venv/bin/python -m py_compile serve_headless.py
    timeout 30s .venv/bin/python -m pytest <focused health/app-factory test file> -q

If no focused test exists and adding one is outside the chosen scope, AGY must stop and report missing validation rather than invent broad validation.

## Completion criteria

- Implementation evidence is written back to this work item.
- `current_work.md` is updated when complete.
- The developer performs browser smoke only if UI/runtime readiness needs to be claimed.
