# WORK-20260629-runtime-facade-queue-adapter-evidence

## Status

Completed

## Title

Runtime facade queue adapter evidence

## Goal

Formulate a detailed design and gather file-level evidence for adapting mutating and gameplay facade commands onto the existing LanController._actions queue.

This is an evidence/planning slice only. It must define the threading boundary, queue-wait mechanism, and status synchronization between the FastAPI request thread and the Tk event loop before any gameplay or stateful mutation route is migrated.

## Strategic Lane

ASGI server first, runtime as a service.

## Source Context

This work follows:

- docs/work_items/completed/WORK-20260628-runtime-facade-skeleton.md
- docs/work_items/completed/WORK-20260628-runtime-facade-contracts.md
- docs/work_items/completed/WORK-20260628-command-queue-semantics.md
- docs/work_items/completed/WORK-20260628-command-queue-observability-foundation.md
- docs/work_items/completed/WORK-20260629-runtime-facade-next-boundary-evidence.md

## Required Evidence Questions

Answer these from current repo files, not old plans or memory:

1. How does LanController._actions enqueue, store, drain, complete, and report action status today?
2. What fields exist in the action-state registry and how are queue_size and queue_wait_ms calculated?
3. Which thread owns LanController._tick and which thread handles FastAPI requests?
4. What minimal adapter shape would allow ServerRuntimeFacade.submit_command to enqueue future gameplay/stateful commands without moving authority away from the Tk thread?
5. What timeout, failure, and trace semantics should the adapter preserve or add?
6. What is the first safe implementation slice after this evidence pass?
7. What exact files should that implementation slice inspect/edit?
8. What bounded validation commands should that implementation slice use?

## Non-Goals

Do not implement app changes in this slice.

Do not:
- migrate another route,
- add queue adapter infrastructure,
- add snapshot cache infrastructure,
- alter gameplay, combat, tactical, LAN, Tk, or WebSocket behavior,
- triage unrelated bugs,
- touch logs/context/,
- touch docs/bug_reports/inbox/BUG-20260626-dmcontrol-terrain-not-visible.md,
- revive old plans, majorTODO.md, runtime reports, or completed work,
- run browser smoke,
- deploy,
- push.

## Expected Deliverable

Update this work item with a compact evidence report and one recommended next implementation work item, only if implementation is justified by current evidence.

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
1. the queue-adapter evidence report is written here,
2. the threading safety boundary is documented from the LanController._actions path,
3. one bounded next work item is recommended,
4. validation passes,
5. the ledger is updated to show this item completed or the next item active.

---

## Evidence Report

### Current LanController Queue Flow
- **Enqueue:** Action requests received over WebSockets (`dnd_initative_tracker.py` under `LanController._ws_read_loop`) are validated, logged, and acknowledged. A unique `action_id` is assigned. The action is registered as `"pending"` in `self._action_states` (under `self._action_states_lock`). The client is immediately sent an `action_ack` with `status: "accepted"`. Finally, the raw action dict is pushed into the `self._actions` queue.
- **Store:** Actions are stored in `self._actions`, which is an instance of a thread-safe `queue.Queue`.
- **Drain:** Drained periodically on the Tk/GUI event loop thread during the execution of `LanController._tick()`. It pulls items off the queue using `self._actions.get_nowait()` in a loop until a `queue.Empty` exception is raised.
- **Execution & Completion:** Each dequeued message is applied using `self._tracker._lan_apply_action(msg)`. 
  - If execution completes successfully, the action state registry is updated with `"status": "completed"` and `"result": {"status": result_status}`.
  - If execution raises an exception, the error is caught, and the registry is updated with `"status": "completed"` and `"result": {"status": "error", "reason": type(exc).__name__}`.
  - In both cases, if the request came via a WebSocket, a synchronous ack is transmitted to the client using `self._send_action_ack_sync()`.

### Action State Registry / Status Findings
- **Registry Fields:** Within `self._action_states` (which maps `action_id` to a dict):
  - Initial fields: `{"status": "pending", "received_at_ns": msg["_received_at_ns"], "command": typ, "ws_id": ws_id, "cid": claimed_cid}`
  - Updated completion/failure fields: `{"status": "completed", "result": {"status": result_status_or_error}, "completed_at_ns": time.perf_counter_ns()}`
  - Size limitation: Cleaned up to retain a maximum of `self._action_history_limit = 500` entries.
- **Metrics Calculation:**
  - `queue_size`: Determined by querying `self._actions.qsize()`.
  - `queue_wait_ms`: Computed upon dequeue in `_tick` as `round((time.perf_counter_ns() - received_at_ns) / 1_000_000.0, 3)`.

### Thread Authority Findings
- **Tk Event Loop Thread:** Owns `LanController._tick` and is the absolute authority for mutating gameplay, combat, and tactical state (in `dnd_initative_tracker.py`).
- **FastAPI / ASGI Threads:** Async event loop tasks managed by Uvicorn process HTTP/REST endpoints. These run concurrently to the main GUI thread.

### Proposed Minimal Queue Adapter Shape
To submit gameplay commands from the request thread without violating the Tk threading boundary, a facade-side adapter can be integrated within `ServerRuntimeFacade.submit_command`:
1. **Command Mapping:** Map the `RuntimeCommand` into the dictionary format expected by `_lan_apply_action`.
2. **Registry Reservation:** Under `self.lan_controller._action_states_lock`, register a new `action_id` in `self._action_states` with `"status": "pending"`, setting `_received_at_ns` to the current nanoseconds.
3. **Queue Insertion:** Call `self.lan_controller._actions.put(msg)` to place the action on the Tk queue.
4. **Await Loop:** Poll or wait for the status of `action_id` in `self._action_states` to transition to `"completed"` under lock. To keep thread safety, the request thread polls with a short sleep (e.g., 5-10ms) up to a defined timeout duration.

### Timeout / Failure / Trace Semantics
- **Timeout Semantics:** A wait timeout (default 5000ms) is enforced. If the command does not complete within this period, the facade stops waiting, records `STATUS_TIMED_OUT` in the trace, and raises a `TimeoutError` (returning HTTP 504 Gateway Timeout).
- **Failure Semantics:** If the Tk thread encounters an exception during execution, it catches the error and sets `"result": {"status": "error", "reason": type(exc).__name__}`. The adapter detects this error state, extracts the exception reason, and raises a corresponding exception (e.g. `ValueError`, `RuntimeError`) to maintain downstream FastAPI exception mapping.
- **Trace Semantics:** Records a standard `RuntimeCommandTrace` with the appropriate status (`completed`, `failed`, or `timed_out`), `duration_ms` of the entire wait cycle, `error_class` name if unsuccessful, and queue telemetry inside `metadata`.

### Recommended First Implementation Slice
- **Proposed next work item ID:** WORK-20260629-runtime-facade-queue-adapter
- **Proposed goal:** Implement the facade-side queue adapter seam (`_submit_to_lan_queue`) in `ServerRuntimeFacade` and add targeted unit tests to validate enqueuing, thread polling, timeout enforcement, exception propagation, and trace logging using a mock `LanController` wrapper.
- **Files to inspect first:**
  - `server_runtime.py`
  - `tests/test_server_runtime.py`
  - `dnd_initative_tracker.py`
- **Allowed files to edit:**
  - `server_runtime.py`
  - `tests/test_server_runtime.py`
- **Forbidden scope:**
  - Do not edit `dnd_initative_tracker.py`.
  - Do not migrate any actual FastAPI routes/endpoints.
  - Do not implement snapshot cache or read boundary modifications.
  - Do not alter gameplay rules, tactical state, or WebSocket messaging.
- **Validation commands:**
  - `python3 -m py_compile server_runtime.py tests/test_server_runtime.py`
  - `python3 -m unittest tests/test_server_runtime.py`
  - `git status --short`
  - `timeout 10s git diff --check`
- **Close criteria:**
  - `ServerRuntimeFacade._submit_to_lan_queue` is implemented and integrated for test/gameplay command types.
  - Unit tests prove that commands wait, complete, timeout, propagate errors, and write traces correctly.
  - No production routes are mutated or migrated.
  - Scoped validation passes.

