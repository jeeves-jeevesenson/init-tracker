# WORK-20260628-runtime-facade-contracts: Runtime facade command and snapshot contracts

- **Status:** Completed
- **Gate:** Runtime Facade Contracts Gate
- **Opened:** 2026-06-28
- **Executor:** AGY by explicit bounded task packet.
- **Migration lane:** Server-runtime extraction.
- **Previous slice:** `WORK-20260628-runtime-facade-skeleton`, completed in `ac210c6`.
- **Scope JSON:** `docs/agent_tasks/scopes/WORK-20260628-runtime-facade-contracts.json`

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

Define the explicit runtime facade contract surface for future command submission and snapshot reads.

This is a narrow contract slice. It should make the next command-queue and snapshot-contract work easier, but must not implement a queue, cache, or migrate gameplay routes.

## Source documents to read first

- `AGENTS.md`
- `.agents/CONTEXT.md`
- `docs/work_items/current_work.md`
- `docs/work_items/active/WORK-20260628-runtime-facade-contracts.md`
- `docs/agent_tasks/scopes/WORK-20260628-runtime-facade-contracts.json`
- `docs/architecture/server_runtime_extraction_decision_20260628.md`
- `docs/planning/living_docs/server_runtime_extraction_living_plan_20260628.md`
- `server_runtime.py`
- `tests/test_server_app.py`

## Candidate implementation intent

A future implementation task may add small explicit contract types around `ServerRuntimeFacade`, such as:

- command request/result dataclasses or enums
- snapshot request/result dataclasses or enums
- facade methods that expose command/snapshot contract boundaries
- behavior-preserving placeholder behavior only if tests prove it is intentional and narrow

This is contract shape only. It must not enqueue commands, build snapshots, call tracker gameplay internals, or migrate route handlers.

## Likely allowed implementation files

The AGY task packet must still name exact files, but intended scope is:

- `server_runtime.py`
- `tests/test_server_app.py`
- `docs/work_items/active/WORK-20260628-runtime-facade-contracts.md`

## Forbidden scope

- Do not triage unrelated bug inbox dirt.
- Do not edit `logs/context/`.
- Do not edit `docs/work_items/current_work.md` during implementation.
- Do not migrate gameplay routes.
- Do not implement a command queue.
- Do not implement snapshot caching.
- Do not build tactical/map/combat snapshots.
- Do not edit route handlers.
- Do not edit `server_app.py` unless a later explicit task scope allows it.
- Do not edit frontend assets.
- Do not edit combat rules, player command logic, monster control behavior, tactical map behavior, YAML data, or production deployment config.
- Do not run broad test suites.
- Do not run browser smoke unless explicitly authorized.
- Do not push, deploy, restart services, alter DNS/FQDNs, or touch production topology.
- Do not inspect old plans, old bugs, `majorTODO.md`, runtime reports, or logs unless explicitly named by a bounded task packet.

## Acceptance criteria

A future implementation pass must prove:

1. The runtime facade has explicit command/snapshot contract surface.
2. The contract surface is behavior-preserving and does not mutate tracker state.
3. No command queue is implemented.
4. No snapshot cache is implemented.
5. No gameplay routes are migrated.
6. Focused tests cover the contract surface.
7. `scripts/agent_scope_validate.py docs/agent_tasks/scopes/WORK-20260628-runtime-facade-contracts.json` passes before staging.

## Validation for this opening commit

Run:

    git status --short
    python3 -m json.tool docs/agent_tasks/scopes/WORK-20260628-runtime-facade-contracts.json >/dev/null
    timeout 10s git diff --check
    git diff -- docs/work_items/current_work.md docs/work_items/active/WORK-20260628-runtime-facade-contracts.md docs/agent_tasks/scopes/WORK-20260628-runtime-facade-contracts.json

## Completion criteria

- Contract implementation evidence is written back to this work item.
- The scope validator passes before implementation commit staging.
- `current_work.md` is updated only when closing this work item.

## Implementation Evidence

- **Contract Types Defined in `server_runtime.py`:**
  - `RuntimeCommand`: frozen dataclass representing a command structure.
  - `RuntimeCommandResult`: frozen dataclass representing the status result of command execution.
  - `RuntimeSnapshotRequest`: frozen dataclass representing a request for a state snapshot.
  - `RuntimeSnapshotResult`: frozen dataclass containing the retrieved state snapshot data.

- **Facade Methods Exposed:**
  - `submit_command(self, command: RuntimeCommand) -> RuntimeCommandResult` - raises `NotImplementedError`
  - `read_snapshot(self, request: RuntimeSnapshotRequest) -> RuntimeSnapshotResult` - raises `NotImplementedError`

- **Tests Added in `tests/test_server_app.py`:**
  - `test_command_contract_constructible`
  - `test_command_result_constructible`
  - `test_snapshot_request_constructible`
  - `test_snapshot_result_constructible`
  - `test_facade_methods_fail_closed_and_no_mutation`

- **Validation:**
  - All 8 unit tests in `tests/test_server_app.py` run successfully.
  - Scope validation passes without errors.


## Completion Evidence

- Completed in `2244f09`.
- Added explicit runtime facade contract dataclasses:
  - `RuntimeCommand`
  - `RuntimeCommandResult`
  - `RuntimeSnapshotRequest`
  - `RuntimeSnapshotResult`
- Added `ServerRuntimeFacade.submit_command()` and `ServerRuntimeFacade.read_snapshot()` as fail-closed contract boundaries.
- Added focused tests for contract construction and fail-closed facade methods.
- Validation passed before implementation commit:
  - `python3 -m py_compile server_runtime.py server_app.py serve_headless.py dnd_initative_tracker.py`
  - `.venv/bin/python -m pytest tests/test_server_app.py`
  - `scripts/agent_scope_validate.py docs/agent_tasks/scopes/WORK-20260628-runtime-facade-contracts.json`
- No gameplay route migration, command queue, snapshot cache, frontend work, unrelated inbox dirt, `logs/context/`, or `current_work.md` implementation edits.
