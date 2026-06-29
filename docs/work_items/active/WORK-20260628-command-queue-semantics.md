# WORK-20260628-command-queue-semantics: Command queue semantics

- **Status:** Active
- **Gate:** Command Queue Semantics Gate
- **Opened:** 2026-06-28
- **Executor:** AGY by explicit bounded evidence/design task, or developer no-agent design patch if chosen.
- **Migration lane:** Server-runtime extraction.
- **Previous slice:** `WORK-20260628-command-queue-spell-color`, completed in `fa1e79f` and closed in `72c8b57`.
- **Scope JSON:** `docs/agent_tasks/scopes/WORK-20260628-command-queue-semantics.json`

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

Define the minimal command queue semantics needed before moving more mutations through the runtime facade.

This is an evidence/design work item. It must not implement queue infrastructure, migrate routes, or change runtime behavior.

## Current evidence

Bounded inspection found:

- `LanController.__init__` initializes the existing LAN action queue as `self._actions`.
- The WebSocket path acknowledges accepted action messages and enqueues them into `self._actions`.
- `LanController._tick` drains actions on the Tk thread, computes queue wait timing, and dispatches actions to tracker behavior.
- `ServerRuntimeFacade.submit_command(...)` currently handles the spell-color command synchronously by calling the tracker app hook directly.

## Design questions to answer

A future evidence/design task should answer:

1. Should runtime facade commands reuse the existing LAN action queue, introduce a separate runtime queue, or define a facade-owned abstraction over the existing queue first?
2. Which thread is authoritative for mutating tracker state?
3. What is the minimal command lifecycle: accepted, queued, dispatching, completed, failed?
4. Should synchronous HTTP routes wait for completion, return accepted, or use a hybrid model?
5. What failure behavior should be preserved for HTTP routes that currently map exceptions directly?
6. What observability is required now: queue depth, command age, dispatch duration, status map, log/debug trace fields?
7. Which next implementation slice is safest after semantics are defined?

## Source documents to read first

- `AGENTS.md`
- `.agents/CONTEXT.md`
- `docs/work_items/current_work.md`
- `docs/work_items/active/WORK-20260628-command-queue-semantics.md`
- `docs/agent_tasks/scopes/WORK-20260628-command-queue-semantics.json`
- `docs/work_items/completed/WORK-20260628-command-queue-spell-color.md`
- `docs/work_items/completed/WORK-20260628-command-queue-slice-selection.md`
- `docs/architecture/server_runtime_extraction_decision_20260628.md`
- `docs/planning/living_docs/server_runtime_extraction_living_plan_20260628.md`
- `server_runtime.py`
- `dnd_initative_tracker.py`

## Evidence/design task intent

The future task should append a section named:

`## Command Queue Semantics Decision`

It should include:

1. Existing queue/threading evidence from named files.
2. Proposed minimal command lifecycle.
3. Proposed threading authority boundary.
4. Proposed HTTP command behavior for synchronous metadata routes versus async player/WebSocket actions.
5. Proposed failure and timeout semantics.
6. Proposed observability fields.
7. Exactly one next implementation candidate.
8. Proposed scope JSON shape and validation for that implementation candidate.

## Likely allowed edit files for the evidence/design task

The future AGY task should edit only:

- `docs/work_items/active/WORK-20260628-command-queue-semantics.md`

It may inspect only the named source files above. If more files are required, it must stop and report the exact missing file/path needed.

## Forbidden scope

- Do not edit app/runtime source.
- Do not edit `server_runtime.py`.
- Do not edit `dnd_initative_tracker.py`.
- Do not edit `server_app.py`.
- Do not edit `serve_headless.py`.
- Do not edit tests.
- Do not edit `docs/work_items/current_work.md` during evidence capture.
- Do not implement command queue infrastructure.
- Do not migrate routes.
- Do not change runtime behavior.
- Do not implement snapshot cache.
- Do not add background workers.
- Do not edit frontend assets.
- Do not edit YAML/data files.
- Do not edit production/deployment config.
- Do not run broad test suites.
- Do not run browser smoke unless explicitly authorized.
- Do not push, deploy, restart services, alter DNS/FQDNs, or touch production topology.
- Do not inspect old plans, old bugs, `majorTODO.md`, runtime reports, or logs unless explicitly named by a bounded task packet.

## Acceptance criteria

A future evidence/design task must produce:

1. A concise command queue semantics decision based on named repo files.
2. Clear threading authority statement.
3. Clear HTTP/WebSocket command lifecycle proposal.
4. Clear failure/timeout behavior proposal.
5. Clear observability proposal.
6. Exactly one recommended next implementation slice.
7. No source code changes.
8. `scripts/agent_scope_validate.py docs/agent_tasks/scopes/WORK-20260628-command-queue-semantics.json` passes.

## Validation for this opening commit

Run:

    git status --short
    python3 -m json.tool docs/agent_tasks/scopes/WORK-20260628-command-queue-semantics.json >/dev/null
    timeout 10s git diff --check
    git diff -- docs/work_items/current_work.md docs/work_items/active/WORK-20260628-command-queue-semantics.md docs/agent_tasks/scopes/WORK-20260628-command-queue-semantics.json

## Completion criteria

- Queue semantics decision is written into this work item.
- No source code changes are made.
- `current_work.md` is updated only when closing this work item.

## Command Queue Semantics Decision

### 1. Existing Evidence
- **Existing LAN/WebSocket Action Queue Initialization:**
  In `dnd_initative_tracker.py` around lines 1973-1975, the action queue `self._actions` is initialized as a thread-safe `queue.Queue` within `LanController.__init__`. An action state registry `self._action_states` is created alongside `self._action_states_lock` to track action lifecycles.
- **Existing Action Enqueue Behavior:**
  In the WebSocket receiver path under `dnd_initative_tracker.py` around lines 3935-3998, incoming actions undergo idempotency and duplicate checking. If valid, the state is registered as `"pending"`, an immediate `action_ack` with `status: "accepted"` is sent back to the WebSocket client, and the message is put onto `self._actions`.
- **Existing Tk-Thread Action Dispatch Behavior:**
  In `dnd_initative_tracker.py` around lines 7054-7185, the Tk event loop periodically ticks (`LanController._tick`) on the main GUI thread, draining the `self._actions` queue. It calculates `queue_wait_ms`, emits a `ws.action.dispatch.start` debug event, applies the action via `_tracker._lan_apply_action(msg)`, updates the state in `self._action_states`, and sends the final `action_ack` with status `"completed"` and the result or error.
- **Existing Runtime Facade Synchronous Command Behavior:**
  In `server_runtime.py` around lines 58-77, the facade method `submit_command` currently routes `COMMAND_UPDATE_SPELL_COLOR` synchronously. It accesses the tracker app from `lan_controller` and invokes `app._save_spell_color` directly on the caller thread.

### 2. Decision: Queue Model
**Selected Model:** A facade-owned command gateway that initially executes synchronous metadata commands and later adapts selected async commands onto the existing LAN queue.
**Rationale:**
- Reusing the LAN queue directly for simple metadata operations (like spell color) would add unnecessary serialization delay and couple simple configuration modifications to the active Tk event loop schedule.
- Implementing a separate runtime queue now would introduce multi-queue synchronization complexity and split-brain risks, since the GUI thread is the single authority for game state.
- A gateway model allows metadata operations to execute synchronously via the facade immediately, while keeping a clear evolutionary path to adapt heavier gameplay-related commands (like combat movement) onto the existing single-threaded LAN queue, avoiding concurrent mutation hazards.

### 3. Threading Authority
- **State Mutation Owner:** The main GUI/Tkinter event-loop thread remains the absolute authority for mutating tracker state (`dnd_initative_tracker.py`).
- **Implications for Routing:** Any command that alters game-rules, combat order, or map layout must not be executed directly on the ASGI request handler thread. Instead, the facade must queue/route these commands to the GUI thread (e.g. by adapting them to `self._actions`). Only read-only snapshots and non-gameplay metadata mutations (e.g., spell color configuration) can execute outside the Tk-thread context under safety-guaranteeing parameters.

### 4. Command Lifecycle
- **Statuses Defined:**
  - `accepted`: Command received and validated by the ASGI gateway.
  - `queued`: Placed in the queue, awaiting dispatcher pickup.
  - `dispatching`: Dequeued and currently executing on the authoritative thread.
  - `completed`: Successfully executed; return payload is populated.
  - `failed`: Exception encountered during execution; error details recorded.
  - `timed_out`: Command exceeded max queue wait time before completion.
- **Application Scope:**
  - *Now (Synchronous routes)*: A command executes immediately, transitioning instantly: `accepted` -> `dispatching` -> `completed` or `failed`. Queue-related states (`queued`, `timed_out`) do not apply.
  - *Now (WebSocket actions)*: Websocket messages map to `accepted` (on immediate ack) -> `pending` (while queued/dispatching) -> `completed` / `error` (on execution finish).
  - *Future (Full async routing)*: All async endpoints will fully leverage the complete status set.

### 5. HTTP Behavior
- **Synchronous Metadata Routes:** Routes such as `POST /api/spells/{spell_id}/color` should remain synchronous, blocking the request thread until the facade completes the command and returns the final JSON outcome.
- **WebSocket/Player Actions:** Actions received over WebSocket (e.g., combatant movement) should remain asynchronous: immediately acknowledge receipt with `accepted`, then push updates and final execution results back to the client via asynchronous WebSocket frames.
- **Future Mutations Model:** A **hybrid model** is selected. Non-blocking metadata changes remain synchronous for developer simplicity. Gameplay mutations (like moving a combatant or advancing a turn) will return HTTP 202 (Accepted) immediately with a command ID, allowing clients to poll execution status or listen for WebSocket/push-channel confirmation.

### 6. Failure and Timeout Behavior
- **HTTP Exception Mapping:** Exceptions raised during synchronous commands must propagate back to the FastAPI handler, which maps specific classes (e.g., `ValueError` -> HTTP 400, `FileNotFoundError` -> HTTP 404, `RuntimeError` -> HTTP 500).
- **Timeout Semantics:** A maximum queue wait timeout (e.g., 5000ms) will be enforced for queued async commands. If the command exceeds this timeout, it will abort with `timed_out` status, returning HTTP 504 to prevent cascading queues.
- **Preserved Behavior:** API contract compatibility must be strictly preserved; all HTTP routes must continue to map identical exceptions to identical status codes as they do today.

### 7. Observability
- **Minimum Observability Fields:**
  - `command_type`: Command identifier.
  - `action_id`: Unique trace ID.
  - `queue_depth`: Queue size during enqueue/dequeue.
  - `queue_wait_ms`: Time spent waiting in queue.
  - `dispatch_duration_ms`: Duration of handler execution.
  - `result_status`: Status result (`completed`, `failed`, `timed_out`).
  - `error_class`: Name of the raised exception if failed.
- **Existing Evidence:** In `dnd_initative_tracker.py` around lines 7098-7114, `queue_wait_ms` is computed using `time.perf_counter_ns()` relative to the enqueued timestamp `_received_at_ns`, and `queue_size` is read via `self._actions.qsize()`, which are logged under the `ws.action.dispatch.start` debug event.

### 8. Exactly One Next Implementation Candidate
- **Candidate Name:** Observability and Lifecycle Foundations for Spell Color Facade
- **Work Item ID:** `WORK-20260628-command-queue-observability-foundation`
- **Description:** Implement minimal standard observability logging and lifecycle status structures in `ServerRuntimeFacade.submit_command` for the spell-color route. This will record command start, duration, status, and error details to a standardized debug logger without changing the synchronous execution topology yet.

### 9. Proposed Future Work Item
- **Work Item ID:** `WORK-20260628-command-queue-observability-foundation`
- **Likely Allowed Files:**
  - `server_runtime.py`
  - `tests/test_server_runtime.py`
- **Forbidden Files:**
  - `dnd_initative_tracker.py`
  - `server_app.py`
  - `serve_headless.py`
  - `docs/work_items/current_work.md`
- **Scoped Validation Commands:**
  - `python3 -m py_compile server_runtime.py`
  - `python3 -m unittest tests/test_server_runtime.py`
  - `python3 scripts/agent_scope_validate.py docs/agent_tasks/scopes/WORK-20260628-command-queue-observability-foundation.json`
- **Scope Validator Guidance:** The scope validator must verify that only `server_runtime.py` and `tests/test_server_runtime.py` are edited. No new endpoints, queues, threads, or changes to existing routes or state authority are allowed.
