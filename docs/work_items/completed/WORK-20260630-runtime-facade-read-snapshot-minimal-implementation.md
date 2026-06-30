# WORK-20260630-runtime-facade-read-snapshot-minimal-implementation: Runtime facade read snapshot minimal implementation

## Status

Completed.

## Type

Bounded implementation pass.

## Goal

Implement the minimal `ServerRuntimeFacade.read_snapshot()` boundary authorized by the snapshot-boundary readiness decision.

## Initial Repository State

Initial `git status --short`:

```text
?? docs/bug_reports/inbox/BUG-20260626-dmcontrol-terrain-not-visible.md
?? logs/context/
```

Local `HEAD` was verified as `c22e725`.

The current-work ledger was `Idle` and explicitly allowed opening `WORK-20260630-runtime-facade-read-snapshot-minimal-implementation` as the next bounded implementation slice.

## Files Inspected

- `docs/work_items/current_work.md`
- `docs/planning/living_docs/server_runtime_snapshot_boundary_readiness_decision_20260630.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-snapshot-boundary-readiness-decision.md`
- `docs/planning/living_docs/server_runtime_snapshot_boundary_checkpoint_20260630.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-snapshot-boundary-checkpoint.md`
- `docs/architecture/server_runtime_facade_command_inventory_20260630.md`
- `docs/architecture/server_runtime_extraction_decision_20260628.md`
- `docs/agent_tasks/templates/task-packet.md`
- `server_runtime.py`, targeted ranges only
- `tests/test_server_runtime.py`, targeted ranges only
- `dnd_initative_tracker.py`, targeted ranges only
- `combat_service.py`, targeted ranges only

## Targeted Source/Test Ranges Inspected

- `server_runtime.py` lines 1-220: runtime command/snapshot contracts, status constants, command constants, facade lifecycle/readiness, and queue adapter setup.
- `server_runtime.py` lines 700-780: spell-color direct facade path and previously fail-closed `read_snapshot(...)`.
- `server_runtime.py` lines 740-1120 after edit: snapshot failure helpers, parameter resolution, delegation, and failure mapping.
- `tests/test_server_runtime.py` lines 1-230: package re-export expectations, facade construction imports, snapshot test helpers, and new focused snapshot tests.
- `tests/test_server_runtime.py` lines 3140-3580: existing feature command tests confirming later imports are method-local and unrelated to this pass.
- `dnd_initative_tracker.py` lines 140-200: `_current_request_wants_tactical_map()`.
- `dnd_initative_tracker.py` lines 1490-1545: adjacent cache reuse comment context.
- `dnd_initative_tracker.py` lines 8388-8565: `_dm_console_snapshot()` and `_dm_console_snapshot_payload()`.
- `dnd_initative_tracker.py` lines 21430-21460: cached DM snapshot prebuild/reuse comment context.
- `dnd_initative_tracker.py` lines 46745-46875: `_dm_tactical_snapshot_from_lan_snapshot()` and `_dm_tactical_snapshot()`.
- `combat_service.py` lines 190-530: `CombatService.combat_snapshot()` and adjacent post-mutation snapshot pattern.

## Files Changed

- `server_runtime.py`
- `tests/test_server_runtime.py`
- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-read-snapshot-minimal-implementation.md`

During the pass, `docs/work_items/active/WORK-20260630-runtime-facade-read-snapshot-minimal-implementation.md` was created and then removed before completion so no active work item remains.

## Implementation

`RuntimeSnapshotResult` now preserves the existing `success` and `data` fields and adds defaulted `status`, `message`, `error`, and `metadata` fields for fail-closed snapshot results.

`ServerRuntimeFacade.read_snapshot(...)` now:

- Fails closed before runtime readiness with `runtime_not_ready`.
- Fails closed for unsupported snapshot types with `snapshot_type_unsupported`.
- Fails closed for unsupported static hydration params with `snapshot_params_invalid`.
- Fails closed when required legacy references are missing.
- Delegates `combat` to `lan_controller._dm_service.combat_snapshot()`.
- Delegates `tactical` to `lan_controller.app._dm_tactical_snapshot()`.
- Delegates `dm_console` to `lan_controller._dm_console_snapshot(include_tactical=<resolved bool>)`.
- Resolves DM-console tactical inclusion only from explicit `params["include_tactical"]` or allowed explicit `params["workspace"]` values.
- Returns no partial payload on builder failure.

No HTTP route handlers, WebSocket behavior, queue behavior, gameplay behavior, cache TTLs, one-shot cache behavior, static hydration behavior, or legacy snapshot builders were changed.

## Tests Added

Focused coverage was added in `tests/test_server_runtime.py` for:

- Fail-closed behavior before readiness.
- Unsupported snapshot mode fail-closed behavior.
- Combat snapshot delegation and payload return.
- Tactical snapshot delegation and payload return.
- DM-console delegation with explicit `include_tactical=False` and `include_tactical=True`.
- Static hydration request fail-closed behavior.
- Builder exception fail-closed behavior with empty `data`.

## Validation

Validation run during the pass:

```text
timeout 10s .venv/bin/python -m py_compile server_runtime.py tests/test_server_runtime.py
```

Result: passed.

```text
timeout 30s .venv/bin/python -m pytest tests/test_server_runtime.py -q
```

Result: `65 passed, 29 subtests passed in 0.81s`.

Final validation was run after this completed work item and ledger update.

## Ledger Update

`docs/work_items/current_work.md` was returned to Idle after completion.

Allowed next action is constrained to a bounded route-read adoption decision or evidence/smoke pass before any route read migration.

## Untouched Pre-existing Untracked Paths

The expected pre-existing untracked paths remained outside this pass:

- `docs/bug_reports/inbox/BUG-20260626-dmcontrol-terrain-not-visible.md`
- `logs/context/`
