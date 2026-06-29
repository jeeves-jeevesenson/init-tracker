# WORK-20260629-runtime-facade-queue-command-selection

## Status

Completed

## Title

Runtime facade queue command selection

## Goal

Choose the first low-risk production command to route through the new ServerRuntimeFacade queue adapter seam.

This is an evidence/planning slice only. It must not migrate a route or edit app code. The deliverable is a recommended next implementation work item with exact scope, files, and validation.

## Strategic Lane

ASGI server first, runtime as a service.

## Source Context

This work follows:

- docs/work_items/completed/WORK-20260629-runtime-facade-queue-adapter.md
- docs/work_items/completed/WORK-20260629-runtime-facade-queue-adapter-evidence.md
- docs/work_items/completed/WORK-20260629-runtime-facade-next-boundary-evidence.md
- docs/work_items/completed/WORK-20260628-command-queue-semantics.md
- docs/work_items/completed/WORK-20260628-command-queue-observability-foundation.md

## Required Evidence Questions

Answer these from current repo files, not old plans or memory:

1. Which existing HTTP routes mutate gameplay, combat, tactical, or shared runtime state outside the facade?
2. Which candidate route has the smallest payload shape and narrowest state mutation?
3. Which candidate route already maps cleanly to the existing LanController._actions / _lan_apply_action command dictionary shape?
4. Which candidate has focused tests or can be covered with a small new focused test?
5. Which candidate should be explicitly rejected as too broad or risky for the first queue-backed migration?
6. What is the recommended first production queue-backed facade command?
7. What exact files should the next implementation slice inspect/edit?
8. What bounded validation commands should the next implementation slice use?

## Non-Goals

Do not:
- edit app code,
- edit tests,
- migrate any route,
- add new queue infrastructure,
- change the queue adapter seam,
- implement snapshot cache or read-boundary changes,
- alter gameplay, combat, tactical, LAN, Tk, or WebSocket behavior,
- triage unrelated bugs,
- touch logs/context/,
- touch docs/bug_reports/inbox/BUG-20260626-dmcontrol-terrain-not-visible.md,
- revive old plans, majorTODO.md, runtime reports, or completed work,
- run browser smoke,
- deploy,
- push.

## Expected Deliverable

Append an evidence report to this work item with:

- Candidate Route Inventory
- Rejected Candidates
- Recommended First Queue-Backed Command
- Rationale
- Proposed next work item ID
- Proposed goal
- Files to inspect first
- Allowed files to edit
- Forbidden scope
- Validation commands
- Close criteria

## Validation

Validation commands for this evidence/planning slice:

    git status --short
    timeout 10s git diff --check

## Close Criteria

This work item can close when:

1. the candidate selection evidence report is written here,
2. one first production queue-backed command is recommended,
3. the next implementation slice is scoped with exact files and validation,
4. validation passes,
5. the ledger is updated to show this item completed or the next item active.

---

## Evidence Report

### 1. Existing Mutating HTTP Routes
A comprehensive analysis of [dnd_initative_tracker.py](file:///home/a2-jeeves@iamjeeves.dev/src/init-tracker/dnd_initative_tracker.py) shows that all HTTP routes mutating state outside of the facade fall into three categories:
1. **DM Combat & Tactical Routes:** (`/api/dm/...`)
   - `POST /api/dm/combat/next-turn` (advances turn)
   - `POST /api/dm/combat/prev-turn` (reverts turn)
   - `POST /api/dm/combat/set-turn` (sets active turn to specific combatant)
   - `POST /api/dm/combat/combatants/{cid}/hp` (adjusts HP)
   - `POST /api/dm/combat/combatants/{cid}/condition` (adds/removes conditions)
   - `POST /api/dm/combat/combatants/{cid}/temp-hp` and `POST /api/dm/combat/combatants/{cid}/temp-hp-adjust` (sets/adjusts temporary HP)
   - `POST /api/dm/combat/start` and `POST /api/dm/combat/end` (starts/ends combat encounters)
   - `POST /api/dm/combat/long-rest` (authoritative long rest)
   - `POST /api/dm/encounter/players/add` and `POST /api/dm/encounter/monsters/add` (adds entities to combat roster)
   - `POST /api/dm/map/combatants/{cid}/move` and `POST /api/dm/map/combatants/{cid}/place` (positions tokens on tactical map)
   - `POST /api/dm/map/combatants/{cid}/facing` (sets combatant token facing direction)
   - `POST /api/dm/combat/monster-attacks/resolve` and `POST /api/dm/combat/monster-attacks/apply-damage` (resolves monster actions/attacks)
   - `POST /api/dm/combat/combatants/{cid}/perform-action` (executes combatant actions)
   - `POST /api/dm/monster-capabilities/{cid}/execute` and `POST /api/dm/monster-capabilities/{cid}/resolve-targets` (monster spell/action targeting)
   - `POST /api/dm/combat/resolve-monster-prompt` (resolves pending decision prompts)
2. **Player & Character YAML Profile Routes:** (`/api/characters/...` and `/api/players/...`)
   - `POST /api/players/{name}/spells` and `POST /api/players/{name}/spellbook` (saves player YAML spell profile config)
   - `POST /api/characters` (creates character file)
   - `PUT /api/characters/{name}` and `POST /api/characters/{name}/overwrite` (updates/overwrites character file)
   - `POST /api/characters/{name}/inventory/items/{instance_id}/equip` etc. (equips/unequips/attunes items in character inventory)
   - `POST /api/characters/upload` (saves uploaded character YAML)
   - `POST /api/shop/players/{name}/purchase` (mutates wealth and adds items to profile)
3. **Shared Config & Utilities Routes:**
   - `POST /api/players/cache/refresh` (clears and rebuilds players profiles cache)
   - `PUT /api/shop/catalog` (saves shop catalog YAML on disk)
   - `POST /api/push/subscribe` (saves push subscriptions on player profiles)

### 2. Candidate Route Inventory
The following routes are candidate mutating operations for queue-backed migration:
- **`POST /api/dm/map/combatants/{cid}/facing`:** Sets a combatant's facing direction.
  - *Payload:* `{"facing_deg": int}`
  - *State Mutation:* Updates combatant `facing_deg` attribute, updates map UI token dictionary, and broadcasts new state. Very narrow.
  - *Queue Mapping:* Already maps natively to the existing `"set_facing"` message in `_ACTION_MESSAGE_TYPES` and the `"set_facing"` action handler inside `_lan_apply_action`.
- **`POST /api/dm/map/combatants/{cid}/move`:** Moves a combatant on the map.
  - *Payload:* `{"col": int, "row": int}`
  - *State Mutation:* Changes grid coordinates of token.
  - *Queue Mapping:* Maps to `"move"` action type. However, movement consumes movement budget and rules logic which makes it moderately complex.

### 3. Rejected Candidates
- **`POST /api/dm/combat/next-turn` (and other turn/start/end routes):** Rejected for the first queue-backed slice due to broad combat state mutation, reactions polling, and high risk of deadlock.
- **`POST /api/dm/combat/combatants/{cid}/hp`:** Rejected because HP changes trigger complex combat rules (incapacitation, death saves, unconscious transitions) that are too risky for a first slice.
- **`POST /api/players/cache/refresh` (and other YAML routes):** Rejected because they only mutate file/cache state on disk and do not execute on the Tk event loop/thread via `_lan_apply_action`.

### 4. Recommended First Queue-Backed Command
- **Command:** `POST /api/dm/map/combatants/{cid}/facing`
- **Command Type Constant:** `COMMAND_SET_FACING = "set_facing"`

### 5. Rationale
1. **Narrow Payload & State Mutation:** The payload is a single integer (`facing_deg`), and the mutation only affects the facing degree attribute on a single combatant.
2. **Clean Queue Mapping:** The `"set_facing"` message is already part of the `_ACTION_MESSAGE_TYPES` list and is processed by `_lan_apply_action` under administrative bypass (making it fully compatible with DM actions).
3. **Minimal Test Surface:** Testing enqueuing, polling, and success of setting facing is straightforward and can leverage the existing `_submit_to_lan_queue` unit testing structure.

---

## Proposed Next Work Item

### Proposed next work item ID
`WORK-20260629-runtime-facade-queue-command-facing`

### Proposed goal
Migrate the `POST /api/dm/map/combatants/{cid}/facing` endpoint to execute through the `ServerRuntimeFacade` using the new `_submit_to_lan_queue` queue adapter.

### Files to inspect first
- [server_runtime.py](file:///home/a2-jeeves@iamjeeves.dev/src/init-tracker/server_runtime.py)
- [tests/test_server_runtime.py](file:///home/a2-jeeves@iamjeeves.dev/src/init-tracker/tests/test_server_runtime.py)
- [dnd_initative_tracker.py](file:///home/a2-jeeves@iamjeeves.dev/src/init-tracker/dnd_initative_tracker.py) (lines 4724-4752: `dm_set_combatant_facing` and lines 42788-42820: `_handle_set_facing_request`)

### Allowed files to edit
- [server_runtime.py](file:///home/a2-jeeves@iamjeeves.dev/src/init-tracker/server_runtime.py)
- [tests/test_server_runtime.py](file:///home/a2-jeeves@iamjeeves.dev/src/init-tracker/tests/test_server_runtime.py)
- [dnd_initative_tracker.py](file:///home/a2-jeeves@iamjeeves.dev/src/init-tracker/dnd_initative_tracker.py)

### Forbidden scope
- Do not migrate any other FastAPI routes.
- Do not alter existing `set_facing` execution logic inside the Tk thread handler `_handle_set_facing_request`.
- Do not implement snapshot cache or read boundary changes.
- Do not touch logs/context/ or unrelated bug reports.

### Validation commands
```bash
python3 -m py_compile server_runtime.py tests/test_server_runtime.py dnd_initative_tracker.py
.venv/bin/python -m unittest tests/test_server_runtime.py
git status --short
timeout 10s git diff --check
```

### Close criteria
1. `POST /api/dm/map/combatants/{cid}/facing` is successfully routed through `self._runtime.submit_command` using `COMMAND_SET_FACING`.
2. Unit tests in `tests/test_server_runtime.py` verify that `COMMAND_SET_FACING` is processed through the queue adapter, waits for completion on the authoritative Tk thread, and returns the expected result structure.
3. No other routes are migrated and gameplay behavior is preserved.
4. Validation commands pass.



---

## Completion Evidence

Completed by AGY evidence pass `AGY-20260629-runtime-facade-queue-command-selection`.

### Candidate Routes Considered

- `POST /api/dm/map/combatants/{cid}/facing`
  - Recommended.
  - Payload: `{"facing_deg": int}`.
  - Narrow mutation: updates facing for one combatant, GUI map facing state, and state broadcast.
  - Maps directly to existing LAN action message type `set_facing`.

- `POST /api/dm/map/combatants/{cid}/move`
  - Deferred.
  - Maps to existing `move`, but movement has broader movement-budget, turn, and hazard implications.

- `POST /api/dm/combat/next-turn`
  - Deferred.
  - Turn advancement is broader combat-state transition logic.

- `POST /api/players/cache/refresh`
  - Rejected for this lane.
  - It is not a Tk queue/gameplay authority mutation.

### Recommendation

Recommended next work item:

`WORK-20260629-runtime-facade-queue-command-facing`

Goal: migrate `POST /api/dm/map/combatants/{cid}/facing` to execute through `ServerRuntimeFacade` using the new `_submit_to_lan_queue` adapter.

### Validation

AGY reported:

- `timeout 10s git diff --check`
  - clean output
