# WORK-20260629-runtime-facade-next-boundary-evidence

## Status

Completed

## Title

Runtime facade next boundary evidence

## Goal

Choose the next safest bounded server-runtime extraction step after the command queue observability foundation.

This is an evidence/planning slice only. It should identify whether the next work item should be:
1. command trace/status read access hardening,
2. queue-adapter evidence before gameplay/stateful command migration,
3. snapshot/read-boundary preparation,
4. or another narrower prerequisite supported by current repo evidence.

## Strategic Lane

ASGI server first, runtime as a service.

## Source Context

Use the current work ledger and the completed server-runtime extraction work items as the migration source of truth.

Relevant completed items:
- docs/work_items/completed/WORK-20260628-runtime-facade-skeleton.md
- docs/work_items/completed/WORK-20260628-runtime-facade-contracts.md
- docs/work_items/completed/WORK-20260628-command-queue-slice-selection.md
- docs/work_items/completed/WORK-20260628-command-queue-spell-color.md
- docs/work_items/completed/WORK-20260628-command-queue-semantics.md
- docs/work_items/completed/WORK-20260628-command-queue-observability-foundation.md
- docs/work_items/completed/WORK-20260628-server-runtime-roadmap.md

## Required Evidence Questions

Answer these from current repo files, not from old plans or memory:

1. What runtime-facade surface exists now?
2. What command trace/status access exists now?
3. What routes currently read or mutate runtime/game state outside the facade?
4. What existing LAN/Tk queue mechanism must remain authoritative for gameplay/stateful mutations?
5. What is the lowest-risk next bounded work item?
6. What exact files should that next work item inspect/edit?
7. What validation commands should that next work item use?

## Non-Goals

Do not implement app changes in this slice.

Do not:
- migrate another route,
- add queue infrastructure,
- add a snapshot cache,
- alter gameplay/combat/tactical behavior,
- triage unrelated bugs,
- touch logs/context/,
- touch docs/bug_reports/inbox/BUG-20260626-dmcontrol-terrain-not-visible.md,
- revive old plans, majorTODO.md, runtime reports, or completed work,
- run browser smoke,
- deploy,
- push.

## Expected Deliverable

Update this work item with a compact evidence report and one recommended next work item.

The recommendation must include:
- proposed work item ID,
- goal,
- files to inspect first,
- allowed files to edit,
- forbidden scope,
- validation commands,
- close criteria.

## Validation

Validation commands for this evidence/planning slice:

    git status --short
    timeout 10s git diff --check

## Close Criteria

This work item can close when:
1. the evidence report is written here,
2. one bounded next work item is recommended,
3. validation passes,
4. the ledger is updated to show this item completed or the next item active.

---

## Evidence Report

### Current Facade Surface
- **Dataclasses & Types:**
  - `RuntimeCommand`: Encapsulates command type and payload.
  - `RuntimeCommandResult`: Holds success flag, message, and return data.
  - `RuntimeCommandTrace`: Records command execution observability.
  - `RuntimeSnapshotRequest` / `RuntimeSnapshotResult`: Placeholders for read snapshots.
- **Constants:**
  - Command statuses: `STATUS_ACCEPTED`, `STATUS_QUEUED`, `STATUS_DISPATCHING`, `STATUS_COMPLETED`, `STATUS_FAILED`, `STATUS_TIMED_OUT`.
  - Commands: `COMMAND_UPDATE_SPELL_COLOR` = `"update_spell_color"`.
- **Facade API:**
  - `ServerRuntimeFacade` holds `lan_controller` and initializes `_ready = False` and `last_command_trace = None`.
  - `start()`, `shutdown()`, and `is_ready()` manage lifespan.
  - `submit_command(command)` handles `COMMAND_UPDATE_SPELL_COLOR` synchronously by directly invoking the `app._save_spell_color` hook, tracks performance metrics, saves trace details, and propagates exceptions.
  - `read_snapshot(request)` raises `NotImplementedError`.

### Current Trace / Status Access
- Command execution traces are written to the `last_command_trace` attribute of `ServerRuntimeFacade`.
- Traces capture `command_type`, `status` (`completed` or `failed`), `duration_ms`, `error_class`, and a `metadata` dictionary.
- There is currently no API endpoint or route to query these traces or obtain history/telemetry.

### Route and Runtime Boundary Findings
- All FastAPI endpoints except `POST /api/spells/{spell_id}/color` currently bypass the facade entirely, accessing `LanController` or the `InitiativeTracker` app in-memory.
- Identified boundary-crossing routes include:
  - Spells: `GET /api/spells`, `GET /api/spells/{spell_id}`
  - Shop: `GET /api/shop/catalog`, `PUT /api/shop/catalog`, `POST /api/shop/players/{name}/purchase`, etc.
  - Characters: `GET /api/characters`, `POST /api/characters`, `PUT /api/characters/{name}`, equip/unequip inventory routes, etc.
  - Encounter / Players: `POST /api/players/cache/refresh`, `GET /api/players/list`, `POST /api/encounter/players/add`.
- Direct thread-unsafe state mutations are done inline on HTTP request threads rather than being delegated to the main thread.

### LAN/Tk Queue Authority Findings
- Threading authority for gameplay/tactical mutations is the main GUI thread running the Tkinter event loop.
- The authoritative queue is `LanController._actions: queue.Queue[Dict[str, Any]]`, matched with `self._action_states` and `self._action_states_lock`.
- Actions are placed on `_actions` by async WebSocket handlers, and dequeued/dispatched in the Tk loop periodically via `LanController._tick` invoking `_tracker._lan_apply_action(msg)`.

### Recommended Next Work Item
- **Proposed next work item ID:** `WORK-20260629-runtime-facade-queue-adapter-evidence`
- **Proposed goal:** Formulate a detailed design and gather file-level evidence for adapting mutating/gameplay facade commands onto the existing `LanController._actions` queue. It will define the threading boundaries, queue-wait mechanism, and status synchronization between the FastAPI request thread and the Tk event loop, establishing the necessary architectural safety evidence before migrating any gameplay mutations.
- **Files to inspect first:**
  - `docs/work_items/current_work.md`
  - `docs/work_items/active/WORK-20260629-runtime-facade-queue-adapter-evidence.md`
  - `server_runtime.py`
  - `dnd_initative_tracker.py` (specifically `LanController._actions`, `LanController._tick`, and WebSocket action dispatching methods)
  - `tests/test_server_runtime.py`
- **Allowed files to edit:**
  - `docs/work_items/active/WORK-20260629-runtime-facade-queue-adapter-evidence.md`
  - `docs/work_items/current_work.md` (ledger updates only)
- **Forbidden scope:**
  - Do not edit app code.
  - Do not edit tests.
  - Do not migrate any routes.
  - Do not implement queue infrastructure.
  - Do not implement snapshot cache.
  - Do not alter gameplay, combat, tactical, LAN, Tk, or WebSocket behavior.
- **Validation commands:**
  - `git status --short`
  - `timeout 10s git diff --check`
- **Close criteria:**
  - The queue-adapter evidence report is written to the work item file.
  - The threading safety boundary is documented based on the `LanController._actions` code path.
  - The ledger is updated to show the work item completed.
