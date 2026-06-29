# WORK-20260628-command-queue-slice-selection: Command queue slice selection

- **Status:** Completed
- **Gate:** Command Queue Slice Selection Gate
- **Opened:** 2026-06-28
- **Executor:** AGY by explicit bounded evidence task, or developer no-agent command inventory if chosen.
- **Migration lane:** Server-runtime extraction.
- **Previous slice:** `WORK-20260628-runtime-facade-contracts`, completed in `2244f09`.
- **Scope JSON:** `docs/agent_tasks/scopes/WORK-20260628-command-queue-slice-selection.json`

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

Inventory current mutating route/action seams and select exactly one low-risk command-queue candidate for the next implementation slice.

This is an evidence/planning work item. It must not implement a command queue, migrate routes, change app behavior, or edit runtime code.

## Current evidence

A bounded decorator search found:

- `server_app.py` currently exposes only health/readiness endpoints.
- `dnd_initative_tracker.py` has no decorator-style route registrations.
- `server_runtime.py` now exposes fail-closed command/snapshot facade contracts.

Therefore the route/action ownership seam must be identified from current repo files before choosing a queue slice.

## Source documents to read first

- `AGENTS.md`
- `.agents/CONTEXT.md`
- `docs/work_items/current_work.md`
- `docs/work_items/active/WORK-20260628-command-queue-slice-selection.md`
- `docs/agent_tasks/scopes/WORK-20260628-command-queue-slice-selection.json`
- `docs/architecture/server_runtime_extraction_decision_20260628.md`
- `docs/planning/living_docs/server_runtime_extraction_living_plan_20260628.md`
- `server_runtime.py`
- `server_app.py`
- `serve_headless.py`
- `dnd_initative_tracker.py`

## Evidence task intent

The future bounded task should identify:

1. Where HTTP/server routes or local action endpoints are actually registered today.
2. Which paths/actions are mutating versus read-only.
3. Which mutating path is smallest and lowest risk for a first command-queue slice.
4. Which exact files a future implementation task would need.
5. Which focused tests already exist or would need to be added.
6. Why other candidates were rejected for the first slice.

## Selection criteria

Prefer a candidate that:

- is small and easy to test,
- has low gameplay-rule risk,
- has minimal frontend/UI impact,
- already has focused tests or can get focused tests,
- can pass through `ServerRuntimeFacade.submit_command()` later without broad route migration,
- does not require tactical map snapshot changes.

Avoid candidates that:

- touch tactical map rendering,
- touch monster/player combat rules deeply,
- require broad frontend smoke,
- require workspace-aware snapshot behavior,
- require production/deploy changes.

## Likely allowed edit files for the evidence task

The future AGY task should edit only:

- `docs/work_items/active/WORK-20260628-command-queue-slice-selection.md`

It may inspect the named source files above. If it needs to inspect additional files to locate routes, it must report the exact missing file/path and stop or request an expanded scope.

## Forbidden scope

- Do not edit app/runtime source.
- Do not edit `server_runtime.py`.
- Do not edit `server_app.py`.
- Do not edit `serve_headless.py`.
- Do not edit `dnd_initative_tracker.py`.
- Do not edit tests.
- Do not edit `docs/work_items/current_work.md` during evidence capture.
- Do not implement command queue.
- Do not migrate gameplay routes.
- Do not implement snapshot cache.
- Do not edit frontend assets.
- Do not edit combat rules, player command logic, monster control behavior, tactical map behavior, YAML data, or production deployment config.
- Do not run broad test suites.
- Do not run browser smoke unless explicitly authorized.
- Do not push, deploy, restart services, alter DNS/FQDNs, or touch production topology.
- Do not inspect old plans, old bugs, `majorTODO.md`, runtime reports, or logs unless explicitly named by a bounded task packet.

## Acceptance criteria

A future evidence task must produce:

1. A concise route/action inventory based on named repo files.
2. A mutating/read-only classification for discovered candidates.
3. Exactly one recommended first command-queue implementation slice.
4. Exact proposed files for that future implementation slice.
5. Exact proposed validation for that future implementation slice.
6. A clear “not selected yet” list for higher-risk candidates.
7. `scripts/agent_scope_validate.py docs/agent_tasks/scopes/WORK-20260628-command-queue-slice-selection.json` passes.

## Validation for this opening commit

Run:

    git status --short
    python3 -m json.tool docs/agent_tasks/scopes/WORK-20260628-command-queue-slice-selection.json >/dev/null
    timeout 10s git diff --check
    git diff -- docs/work_items/current_work.md docs/work_items/active/WORK-20260628-command-queue-slice-selection.md docs/agent_tasks/scopes/WORK-20260628-command-queue-slice-selection.json

## Completion criteria

- The selected candidate and evidence are written into this work item.
- No source code changes are made.
- `current_work.md` is updated only when closing this work item.

## Slice Selection Evidence

### 1. Route/action seam inventory
The routes and action seams are currently registered as follows:
- **HTTP / Server Routes**:
  - Dynamic registration within the `start` method of `LanController` in `dnd_initative_tracker.py` around `LanController.start`. This registers endpoints for the player web page, character editors, shop, and DM console routes.
  - The `server_app.py` ASGI factory exposes only health and readiness endpoints: `/health`, `/api/health`, `/ready`, and `/api/ready`. No other routes exist there.
- **Local Action Seams**:
  - The WebSocket endpoint `/ws` in `dnd_initative_tracker.py` around the `/ws` endpoint receives messages of type matching `_ACTION_MESSAGE_TYPES` and puts them into `self._actions`, which is a `queue.Queue`.
  - The Tk event loop thread in `LanController._tick` pulls actions from `self._actions` via `get_nowait` and dispatches them to the InitiativeTracker `_lan_apply_action` method for execution on the main GUI/tracker thread.

### 2. Candidate classification
Below is the classification of mutating candidate routes:

| Candidate | File/Seam | Mutating/Read-only | Risk | Testability | Selected/Not Selected | Reason |
| --- | --- | --- | --- | --- | --- | --- |
| `POST /api/spells/{spell_id}/color` | `dnd_initative_tracker.py:3155` | Mutating | Low | High | Selected | Smallest safe candidate. Only updates custom display color metadata of a spell. Zero impact on gameplay mechanics or map state. |
| `POST /api/players/cache/refresh` | `dnd_initative_tracker.py:3184` | Mutating | Low | Medium | Not Selected | Requires file I/O and rebuilding player roster cache. Spell color metadata is simpler and more isolated. |
| `POST /api/push/subscribe` | `dnd_initative_tracker.py:2857` | Mutating | Low | Low | Not Selected | Involves browser push notification metadata configuration. |
| `POST /api/dm/combat/next-turn` | `dnd_initative_tracker.py:4159` | Mutating | High | Medium | Not Selected | High gameplay-rule risk (advances combat turn, triggers reactions/saves). |
| `POST /api/dm/map/combatants/{cid}/move` | `dnd_initative_tracker.py:4658` | Mutating | High | Medium | Not Selected | Touches tactical map rendering and grid coordinate validation. |

### 3. Selected next slice
The selected candidate is `POST /api/spells/{spell_id}/color` in `LanController`.
- **Rationale**: It is the smallest and safest mutating action. It modifies a simple YAML/JSON metadata attribute (display color of a spell) and has no dependency on combat rules, turn orders, initiative state, or tactical map grids. It does not affect active combatants or trigger reactions. It is easily simulated and tested via a single mock command payload.
- **Future Work Item ID Suggestion**: `WORK-20260628-command-queue-spell-color`

### 4. Proposed future implementation scope
- **Exact files likely needed**:
  - `server_runtime.py` (to define command contracts and implement facade command dispatching)
  - `dnd_initative_tracker.py` (to delegate the route request to `ServerRuntimeFacade`)
  - `tests/test_server_runtime.py` (to verify facade command integration and execution)
- **Exact files forbidden**:
  - `serve_headless.py`
  - Gameplay engines and combat logic files (e.g., `combat_service.py` or specific combat rules in `dnd_initative_tracker.py` outside of the API route delegation)
  - Frontend assets (`static/`, `templates/`, HTML, CSS, JS)
- **Proposed scope validator forbidden pattern categories**:
  - Adding new FastAPI route decorators in application source.
  - Introducing snapshot-cache implementation markers.
  - Introducing async or deque-based command queue structures.
  - Touching combat turn advancement.
  - Touching combatant movement.
  - Touching tactical/map behavior.
- **Proposed validation commands**:
  - `python3 -m py_compile server_runtime.py dnd_initative_tracker.py`
  - `python3 -m unittest tests/test_server_runtime.py`
  - `python3 scripts/agent_scope_validate.py docs/agent_tasks/scopes/WORK-20260628-command-queue-spell-color.json`

### 5. Rejected candidates
- `POST /api/players/cache/refresh`: Rejected because it interacts with player profile disk storage and cache rebuilds, which carries I/O and synchronization overhead.
- `POST /api/dm/combat/next-turn`: Rejected because turn advancement affects multiple sub-components (monsters, active players, reaction prompts, log writers), representing high gameplay risk.
- `POST /api/dm/map/combatants/{cid}/move`: Rejected because it relies on tactical grid layout coordinates, movement speed rules, and map workspace updates, violating our selection guidelines.


## Completion Evidence

- Completed in `22d5637`.
- Inventory found that `server_app.py` only owns health/readiness endpoints.
- Evidence identified dynamic HTTP/server route registration and WebSocket action seams in `LanController`.
- Selected `POST /api/spells/{spell_id}/color` as the lowest-risk first command-queue candidate.
- Suggested next work item: `WORK-20260628-command-queue-spell-color`.
- Scope validation passed after evidence wording repair:
  - `scripts/agent_scope_validate.py docs/agent_tasks/scopes/WORK-20260628-command-queue-slice-selection.json`
- No source code, tests, current_work implementation changes, unrelated inbox dirt, or `logs/context/` edits.
