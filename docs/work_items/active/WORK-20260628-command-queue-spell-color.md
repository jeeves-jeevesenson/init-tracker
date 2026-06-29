# WORK-20260628-command-queue-spell-color: Spell color command boundary

- **Status:** Active
- **Gate:** Spell Color Command Boundary Gate
- **Opened:** 2026-06-28
- **Executor:** AGY by explicit bounded implementation task.
- **Migration lane:** Server-runtime extraction.
- **Previous slice:** `WORK-20260628-command-queue-slice-selection`, completed in `22d5637` and closed in `116d111`.
- **Scope JSON:** `docs/agent_tasks/scopes/WORK-20260628-command-queue-spell-color.json`

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

Move only `POST /api/spells/{spell_id}/color` behind the runtime facade command boundary.

The selected route currently validates payload, calls `self.app._save_spell_color(spell_id, payload.get("color"))`, maps exceptions to HTTP errors, and returns `{"ok": True, "spell": result}`.

This slice should preserve that behavior while routing the mutation through `ServerRuntimeFacade.submit_command(...)`.

## Selected route evidence

Bounded inspection found the route in `dnd_initative_tracker.py` around the selected spell-color route block:

- route: `POST /api/spells/{spell_id}/color`
- current mutation: `self.app._save_spell_color(spell_id, payload.get("color"))`
- selected because it is low-risk metadata mutation, not combat, tactical map, turn order, or frontend behavior.

## Intended implementation shape

A future implementation task should make the smallest behavior-preserving change, likely:

1. Extend `ServerRuntimeFacade` with a narrow way to execute one command type for spell color update.
2. Instantiate or attach a facade reference in `LanController` without disturbing current server lifecycle.
3. Change only the selected route body to submit a `RuntimeCommand` instead of directly calling `_save_spell_color`.
4. Preserve existing HTTP status/error behavior.
5. Add focused tests for the facade command path and/or the selected route handler behavior.

This is not a broad queue implementation. If a real queue object, background worker, or cross-thread execution becomes necessary, stop and report before implementing.

## Source documents to read first

- `AGENTS.md`
- `.agents/CONTEXT.md`
- `docs/work_items/current_work.md`
- `docs/work_items/active/WORK-20260628-command-queue-spell-color.md`
- `docs/agent_tasks/scopes/WORK-20260628-command-queue-spell-color.json`
- `docs/work_items/completed/WORK-20260628-command-queue-slice-selection.md`
- `docs/architecture/server_runtime_extraction_decision_20260628.md`
- `docs/planning/living_docs/server_runtime_extraction_living_plan_20260628.md`
- `server_runtime.py`
- `dnd_initative_tracker.py`
- `tests/test_server_app.py`

## Likely allowed implementation files

The AGY task packet must still name exact files, but intended scope is:

- `server_runtime.py`
- `dnd_initative_tracker.py`
- one focused test file, likely `tests/test_server_runtime.py`
- `docs/work_items/active/WORK-20260628-command-queue-spell-color.md`

## Forbidden scope

- Do not triage unrelated bug inbox dirt.
- Do not edit `logs/context/`.
- Do not edit `docs/work_items/current_work.md` during implementation.
- Do not edit `server_app.py`.
- Do not edit `serve_headless.py`.
- Do not edit frontend assets.
- Do not edit YAML/data files.
- Do not edit production/deployment config.
- Do not migrate any route except the selected spell-color route body.
- Do not edit tactical map routes.
- Do not edit DM combat turn routes.
- Do not edit player cache refresh routes.
- Do not edit shop routes.
- Do not edit WebSocket action dispatch.
- Do not implement snapshot cache.
- Do not implement broad command queue infrastructure.
- Do not add background workers.
- Do not alter combat rules, player command logic, monster control behavior, tactical map behavior, or turn advancement.
- Do not run broad test suites.
- Do not run browser smoke unless explicitly authorized.
- Do not push, deploy, restart services, alter DNS/FQDNs, or touch production topology.
- Do not inspect old plans, old bugs, `majorTODO.md`, runtime reports, or logs unless explicitly named by a bounded task packet.

## Acceptance criteria

A future implementation pass must prove:

1. `POST /api/spells/{spell_id}/color` uses the runtime facade command boundary.
2. Existing response shape is preserved: `{"ok": True, "spell": result}`.
3. Existing error mapping is preserved for invalid payload, missing spell id, not found, invalid color, runtime failure, and generic failure.
4. No other route is migrated.
5. No snapshot cache, tactical/map behavior, combat rule, frontend, or deploy work is performed.
6. Focused tests cover the command boundary for the selected spell-color path.
7. `scripts/agent_scope_validate.py docs/agent_tasks/scopes/WORK-20260628-command-queue-spell-color.json` passes before staging.

## Validation for this opening commit

Run:

    git status --short
    python3 -m json.tool docs/agent_tasks/scopes/WORK-20260628-command-queue-spell-color.json >/dev/null
    timeout 10s git diff --check
    git diff -- docs/work_items/current_work.md docs/work_items/active/WORK-20260628-command-queue-spell-color.md docs/agent_tasks/scopes/WORK-20260628-command-queue-spell-color.json

## Completion criteria

- Spell color command-boundary implementation evidence is written back to this work item.
- Scope validator passes before implementation commit staging.
- `current_work.md` is updated only when closing this work item.

## Implementation Evidence

### 1. Facade Command Integration
The spell color command type has been defined in `server_runtime.py`:
- `COMMAND_UPDATE_SPELL_COLOR = "update_spell_color"`
- Implemented in `ServerRuntimeFacade.submit_command(...)`. It checks the command type, retrieves the tracker app instance from the attached `lan_controller`, and invokes `app._save_spell_color(spell_id, color)`.

### 2. Route Delegation
In `dnd_initative_tracker.py`:
- Imported `RuntimeCommand` and `COMMAND_UPDATE_SPELL_COLOR` from `server_runtime`.
- Attached the facade reference `self._runtime = self._fastapi_app.state.runtime` on the `LanController` instance.
- Migrated only the `POST /api/spells/{spell_id}/color` route to build a `RuntimeCommand` and submit it to the facade via `self._runtime.submit_command(command)`.

### 3. Preserved Validation and Mappings
- Non-dict payload triggers HTTP 400.
- Empty spell_id triggers HTTP 400.
- Exception mappings (FileNotFoundError -> 404, ValueError -> 400, RuntimeError -> 500, other Exceptions -> 500) are fully preserved.
- The returned JSON success shape `{"ok": True, "spell": result}` is fully preserved.

### 4. Focused Verification
The implementation is covered by unit tests in `tests/test_server_runtime.py`:
- `test_spell_color_command_execution`: Verifies command executes by calling the hook on a mock controller/app.
- `test_unknown_command_fails_closed`: Verifies unknown commands raise `NotImplementedError`.
- `test_facade_without_lan_controller_fails`: Verifies error handling when `lan_controller` is not configured.
- `test_facade_without_app_fails`: Verifies error handling when `app` is missing.
- `test_no_queue_or_cache_behavior_introduced`: Verifies no queue/cache behavior is added.
- `test_route_level_behavior_mapping`: Verifies that the route-level logic and exception to HTTP status mapping match perfectly.
