# WORK-20260628-server-runtime-roadmap: Server runtime extraction roadmap

- **Status:** Active
- **Gate:** Server Runtime Roadmap Gate
- **Opened:** 2026-06-28
- **Executor:** Orchestrator/developer no-AGY docs workflow unless the developer explicitly authorizes an AGY task.
- **Source commits:**
  - `a210eca` imported external server-runtime research docs.
  - `5e3d522` closed the research import work item.

## Goal

Turn the newly imported external research into a concise, repo-specific server-runtime extraction roadmap.

This is a planning and documentation pass only. It must not implement app code.

## Source documents to read first

- `docs/architecture/server_runtime_extraction_decision_20260628.md`
- `docs/planning/living_docs/server_runtime_extraction_living_plan_20260628.md`
- `docs/planning/research/external/20260628/README.md`
- `docs/planning/research/external/20260628/init_tracker_web_server_extraction_plan_20260628.md`
- `docs/planning/research/external/20260628/script_hosted_runtime_asgi_host_research_20260628.md`
- `docs/work_items/current_work.md`

## Allowed edit files

- `docs/work_items/current_work.md`
- `docs/work_items/active/WORK-20260628-server-runtime-roadmap.md`
- `docs/architecture/server_runtime_extraction_decision_20260628.md`
- `docs/planning/living_docs/server_runtime_extraction_living_plan_20260628.md`

## Forbidden scope

- Do not edit app/runtime/frontend/test code.
- Do not start implementation of app factory, runtime facade, queue, cache, or route migration.
- Do not revive old bugs, old plans, runtime reports, `majorTODO.md`, or completed/superseded docs unless explicitly referenced by the imported research or this work item.
- Do not push, deploy, restart services, or run browser smoke.
- Do not spend AGY quota unless the developer explicitly requests an AGY task.

## Required roadmap outputs

Update the allowed docs so they clearly identify:

1. The repo-specific target architecture in one page or less.
2. The non-negotiable decision list.
3. The first 3-5 milestones in safe order.
4. The first candidate implementation work item, but only as a future item, not active work.
5. Validation gates for future code work.
6. Explicit not-now items, including real engine migration and broad frontend redesign.

## Validation

Run these commands:

    git status --short
    timeout 10s git diff --check
    git diff -- docs/work_items/current_work.md docs/work_items/active/WORK-20260628-server-runtime-roadmap.md docs/architecture/server_runtime_extraction_decision_20260628.md docs/planning/living_docs/server_runtime_extraction_living_plan_20260628.md

## Completion criteria

- The architecture decision and living plan are concise enough for future AGY task packets.
- The next implementation candidate is identified but not opened as active work.
- `current_work.md` is updated when this work item is completed.
- Validation commands above pass.
