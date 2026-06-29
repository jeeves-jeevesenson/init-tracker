# WORK-20260628-command-queue-observability-foundation: Command queue observability foundation

- **Status:** Active
- **Gate:** Command Queue Observability Foundation Gate
- **Opened:** 2026-06-28
- **Executor:** AGY by explicit bounded implementation task.
- **Migration lane:** Server-runtime extraction.
- **Previous slice:** `WORK-20260628-command-queue-semantics`, completed in `8e533fa` and closed in `8522198`.
- **Scope JSON:** `docs/agent_tasks/scopes/WORK-20260628-command-queue-observability-foundation.json`

## Migration Mode Override

The developer is in the middle of the server-runtime extraction migration.

The active strategic lane is:

**ASGI server first, runtime as a service.**

Do not recommend triaging unrelated bug inbox dirt, logs, cleanup, deploy, or random repo maintenance unless the developer explicitly asks.

Known unrelated dirt:

- `docs/bug_reports/inbox/BUG-20260626-dmcontrol-terrain-not-visible.md`
- `logs/context/`

These are not blockers and are not this work item.

## Goal

Add a minimal lifecycle/observability foundation inside the runtime facade for the existing synchronous spell-color command path.

This slice must not migrate another route, introduce a real queue, edit `dnd_initative_tracker.py`, or change runtime topology.

## Current decision basis

`WORK-20260628-command-queue-semantics` selected:

- Queue model: facade-owned command gateway.
- Metadata commands may remain synchronous.
- Future gameplay/stateful commands should adapt onto the existing LAN/Tk action queue.
- Threading authority for gameplay/combat/tactical state remains the main GUI/Tk thread.
- Next implementation candidate: `WORK-20260628-command-queue-observability-foundation`.

## Intended implementation shape

A future implementation task should make the smallest testable change, likely:

1. Add explicit command status/lifecycle constants or a small result/trace structure in `server_runtime.py`.
2. Add timing/status/error observability around `ServerRuntimeFacade.submit_command(...)` for the existing `COMMAND_UPDATE_SPELL_COLOR` path.
3. Preserve current synchronous behavior and exception propagation.
4. Do not add a real queue, background worker, thread, endpoint, route, or queue adaptation.
5. Extend `tests/test_server_runtime.py` to cover lifecycle/observability behavior.

## Source documents to read first

- `AGENTS.md`
- `.agents/CONTEXT.md`
- `docs/work_items/current_work.md`
- `docs/work_items/active/WORK-20260628-command-queue-observability-foundation.md`
- `docs/agent_tasks/scopes/WORK-20260628-command-queue-observability-foundation.json`
- `docs/work_items/completed/WORK-20260628-command-queue-semantics.md`
- `docs/work_items/completed/WORK-20260628-command-queue-spell-color.md`
- `server_runtime.py`
- `tests/test_server_runtime.py`

## Allowed implementation files

The AGY task may edit only:

- `server_runtime.py`
- `tests/test_server_runtime.py`
- `docs/work_items/active/WORK-20260628-command-queue-observability-foundation.md`

## Forbidden scope

- Do not edit `docs/work_items/current_work.md` during implementation.
- Do not edit `dnd_initative_tracker.py`.
- Do not edit `server_app.py`.
- Do not edit `serve_headless.py`.
- Do not edit frontend assets.
- Do not edit YAML/data files.
- Do not edit production/deployment config.
- Do not edit unrelated bug inbox dirt.
- Do not edit `logs/context/`.
- Do not migrate routes.
- Do not add endpoints.
- Do not implement a real command queue.
- Do not add background workers.
- Do not add new threads.
- Do not add async task scheduling.
- Do not implement snapshot cache.
- Do not change read snapshot behavior.
- Do not alter combat rules, player command logic, monster control behavior, tactical map behavior, turn advancement, or WebSocket action dispatch.
- Do not run broad test suites.
- Do not run browser smoke unless explicitly authorized.
- Do not push, deploy, restart services, alter DNS/FQDNs, or touch production topology.
- Do not inspect old plans, old bugs, `majorTODO.md`, runtime reports, or logs unless explicitly named by a bounded task packet.

## Acceptance criteria

A future implementation pass must prove:

1. Existing spell-color command success behavior is preserved.
2. Existing exception propagation for spell-color command is preserved.
3. Unknown command still fails closed.
4. Minimal lifecycle/observability structures exist for command type, status, duration, and error class.
5. No queue infrastructure, route migration, endpoint changes, snapshot cache, background worker, thread, frontend, tactical/map/combat, or deploy behavior is introduced.
6. Focused tests cover the new lifecycle/observability behavior.
7. `scripts/agent_scope_validate.py docs/agent_tasks/scopes/WORK-20260628-command-queue-observability-foundation.json` passes before staging.

## Validation for this opening commit

Run:

    git status --short
    python3 -m json.tool docs/agent_tasks/scopes/WORK-20260628-command-queue-observability-foundation.json >/dev/null
    timeout 10s git diff --check
    git diff -- docs/work_items/current_work.md docs/work_items/active/WORK-20260628-command-queue-observability-foundation.md docs/agent_tasks/scopes/WORK-20260628-command-queue-observability-foundation.json

## Completion criteria

- Implementation evidence is written into this work item.
- Scope validator passes before implementation commit staging.
- `current_work.md` is updated only when closing this work item.

## Implementation Evidence

### 1. In-Process Observability Structures
We introduced:
- Command lifecycle status constants: `STATUS_ACCEPTED`, `STATUS_QUEUED`, `STATUS_DISPATCHING`, `STATUS_COMPLETED`, `STATUS_FAILED`, and `STATUS_TIMED_OUT`.
- The `RuntimeCommandTrace` dataclass containing `command_type`, `status`, `duration_ms`, `error_class`, and `metadata`.
- A `last_command_trace` attribute initialized to `None` on the `ServerRuntimeFacade`.

### 2. Trace Recording and Lifecycle Updates
We updated `ServerRuntimeFacade.submit_command` to record execution traces:
- Successfully processed spell-color commands record a trace with `STATUS_COMPLETED`, the measured `duration_ms` in milliseconds, and `error_class=None`.
- Commands that fail with an exception record a trace with `STATUS_FAILED`, the measured `duration_ms`, and the name of the caught exception (`error_class=exc.__class__.__name__`), and then propagate the exception unaltered.
- Unknown commands fail closed by raising `NotImplementedError` and trace the failure.

### 3. Verification & Validation
- Unit tests added to `tests/test_server_runtime.py` covering successful spell-color traces, exception-raising spell-color traces, unknown commands, and verification that no forbidden queue/cache attributes are introduced.
- Bounded validations run and passed (compiling, tests, scope validation, and git check diff).
