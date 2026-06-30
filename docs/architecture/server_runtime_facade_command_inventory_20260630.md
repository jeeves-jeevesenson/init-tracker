# ServerRuntimeFacade Command Inventory - 2026-06-30

## 1. Purpose and scope

This document is a current command-boundary inventory for the existing `ServerRuntimeFacade` surface. It records the route-to-command mappings and queue-backed behavior currently present after the completed static map route migration sequence.

This is not a new architecture rewrite, not source consolidation, and not authorization for a route migration. No source behavior is changed by this document.

The inventory is limited to evidence from:

- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-next-boundary-checkpoint-decision.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-queue-migration-checkpoint.md`
- `docs/planning/living_docs/server_runtime_facade_queue_migration_checkpoint_20260630.md`
- `docs/architecture/server_runtime_extraction_decision_20260628.md`
- `docs/planning/living_docs/server_runtime_extraction_living_plan_20260628.md`
- `server_runtime.py`
- `dnd_initative_tracker.py`
- `tests/test_server_runtime.py`

## 2. Current command boundary summary

The current migrated route pattern is:

`FastAPI route -> ServerRuntimeFacade.submit_command(...) -> queue/Tk/LanController authority path -> legacy runtime mutation -> response/snapshot/trace`

For the newer migrated map families, `dnd_initative_tracker.py` route handlers build a `RuntimeCommand`, call `self._runtime.submit_command(...)`, and map the facade result into an HTTP response. `server_runtime.py` submits those command messages through `_submit_to_lan_queue(...)`. The LanController queue dispatches the message back onto the Tk/main-thread authority path, where `InitiativeTracker._lan_apply_action(...)` calls the legacy helper and writes command-family result data into `_action_states`.

This is a tactical extraction seam that supports the broader ASGI/server-first, runtime-as-service direction recorded in `docs/architecture/server_runtime_extraction_decision_20260628.md` and `docs/planning/living_docs/server_runtime_extraction_living_plan_20260628.md`. It narrows mutation access incrementally while preserving the legacy runtime as the current authority.

One older facade command differs from that queue-backed pattern: spell color uses `ServerRuntimeFacade.submit_command(...)` but still executes by calling the app helper through `lan_controller.app`, not by round-tripping through `_actions` and `_lan_apply_action(...)`.

## 3. Queue-backed command inventory

### Spell color

| Field | Current evidence |
| --- | --- |
| HTTP route or producer | `POST /api/spells/{spell_id}/color` |
| Command constant/action | `COMMAND_UPDATE_SPELL_COLOR = "update_spell_color"` |
| Source locations | `dnd_initative_tracker.py:update_spell_color`; `server_runtime.py:submit_command` |
| Payload keys | `spell_id`, `color` |
| Result keys | `spell` in `RuntimeCommandResult.data` |
| Response shape | `{ok: true, spell}` |
| Timeout behavior | No queue timeout path is used for this command because it does not call `_submit_to_lan_queue(...)`. |
| Validation/error mapping | Invalid payload or missing `spell_id` -> HTTP 400; `FileNotFoundError` -> HTTP 404; `ValueError` -> HTTP 400; `RuntimeError` and unexpected exceptions -> HTTP 500. |
| Trace/telemetry | `RuntimeCommandTrace` is written with `completed` or `failed`; no queue metadata such as `queue_size` or `queue_wait_ms` is expected for this direct facade command. |
| Focused tests | `test_spell_color_command_execution`, `test_route_level_behavior_mapping`, `test_spell_color_lifecycle_observability_success`, `test_spell_color_lifecycle_observability_failure` |

### Combatant map actions: facing

| Field | Current evidence |
| --- | --- |
| HTTP route or producer | `POST /api/dm/map/combatants/{cid}/facing` |
| Command constant/action | `COMMAND_SET_FACING = "set_facing"` |
| Source locations | `dnd_initative_tracker.py:dm_set_combatant_facing`; `server_runtime.py:submit_command`; `server_runtime.py:_submit_to_lan_queue`; `dnd_initative_tracker.py:_lan_apply_action` through generic LanController dispatch and existing `set_facing` handling |
| Payload keys | `cid`, `facing_deg`, `admin_token` |
| Result keys | Generic queue result under `result`; route reads state from the combatant object after command completion. |
| Response shape | `{ok: true, cid, facing_deg, snapshot}` |
| Timeout behavior | `TimeoutError` from queue wait maps to HTTP 504. |
| Validation/error mapping | Route-level invalid payload, missing/invalid `facing_deg`, and missing combatant map to HTTP 400; `ValueError` from command execution maps to HTTP 400; unexpected exceptions map to HTTP 500. |
| Trace/telemetry | Queue-backed trace includes `queue_size`, `action_id`, and `queue_wait_ms` on completion; failure/timeout updates `RuntimeCommandTrace.status` and `error_class`. LanController emits `ws.action.dispatch.start` / `ws.action.dispatch.end` with queue wait fields. |
| Focused tests | `test_set_facing_command_success`; route mapping coverage is indirectly represented by migrated route pattern tests, with explicit route-level coverage stronger for other map commands. |

### Combatant map actions: place/reposition

| Field | Current evidence |
| --- | --- |
| HTTP route or producer | `POST /api/dm/map/combatants/{cid}/place` |
| Command constant/action | `COMMAND_PLACE_COMBATANT = "place_combatant"` |
| Source locations | `dnd_initative_tracker.py:dm_place_combatant_on_map`; `server_runtime.py:submit_command`; `server_runtime.py:_submit_to_lan_queue`; `dnd_initative_tracker.py:_lan_apply_action` |
| Payload keys | `cid`, `col`, `row`, `admin_token` |
| Result keys | `place_result` with observed keys `ok`, `cid`, `col`, `row`, and possibly `error` |
| Response shape | `{ok: true, cid, col, row, snapshot}` |
| Timeout behavior | `TimeoutError` from queue wait maps to HTTP 504. |
| Validation/error mapping | Invalid payload or non-integer coordinates map to HTTP 400; `place_result.ok == false` maps to `ValueError` unless the error text starts with `Failed to place combatant:`, which maps to `RuntimeError`; route maps `ValueError` to HTTP 400 and unexpected/runtime failure to HTTP 500. |
| Trace/telemetry | Queue-backed trace includes `queue_size`, `action_id`, and `queue_wait_ms`; validation/runtime failure rewrites the trace as `failed` with `ValueError` or `RuntimeError`; timeout rewrites it as `timed_out`. |
| Focused tests | `test_place_combatant_command_success`, `test_place_combatant_command_validation_failure`, `test_place_route_level_behavior_mapping` |

### Map overlays: aura overlays

| Field | Current evidence |
| --- | --- |
| HTTP route or producer | `POST /api/dm/map/overlays/auras` |
| Command constant/action | `COMMAND_SET_AURAS_ENABLED = "set_auras_enabled"` |
| Source locations | `dnd_initative_tracker.py:dm_set_auras_overlay`; `server_runtime.py:submit_command`; `server_runtime.py:_submit_to_lan_queue`; `dnd_initative_tracker.py:_lan_apply_action` permits no-claim admin-style handling for `set_auras_enabled` |
| Payload keys | `enabled`, `admin_token` |
| Result keys | Generic queue result under `result`; route reads `_lan_auras_enabled` from the app after command completion. |
| Response shape | `{ok: true, enabled, snapshot}` |
| Timeout behavior | `TimeoutError` maps to HTTP 504. |
| Validation/error mapping | Invalid payload maps to HTTP 400; `ValueError` maps to HTTP 400; unexpected exceptions map to HTTP 500. |
| Trace/telemetry | Queue-backed trace includes `queue_size`, `action_id`, and `queue_wait_ms`; LanController dispatch trace includes queue wait metadata. |
| Focused tests | `test_set_auras_enabled_command_success`, `test_auras_route_level_behavior_mapping` |

### AoE remove/move

| Field | AoE remove | AoE move |
| --- | --- | --- |
| HTTP route or producer | `DELETE /api/dm/map/aoes/{aid}` | `POST /api/dm/map/aoes/{aid}/move` |
| Command constant/action | `COMMAND_REMOVE_AOE = "aoe_remove"` | `COMMAND_MOVE_AOE = "aoe_move"` |
| Source locations | `dnd_initative_tracker.py:dm_remove_aoe`; `server_runtime.py:submit_command`; `dnd_initative_tracker.py:_lan_apply_action` | `dnd_initative_tracker.py:dm_move_aoe`; `server_runtime.py:submit_command`; `dnd_initative_tracker.py:_lan_apply_action` |
| Payload keys | `aid`, `admin_token` | `aid`, `admin_token`, plus the route forwards the request payload keys with `**payload` |
| Result keys | `remove_result` with observed keys `ok`, `aid`, maybe `error` | `move_result` with observed keys `ok`, `aid`, `aoe`, maybe `error` |
| Response shape | `{ok: true, aid, snapshot}` | `{ok: true, aid, aoe, snapshot}` |
| Timeout behavior | `TimeoutError` maps to HTTP 504. | `TimeoutError` maps to HTTP 504. |
| Validation/error mapping | Queue result failure or missing result maps to `ValueError`/`RuntimeError`; route maps `ValueError` to HTTP 400 and unexpected exceptions to HTTP 500. | Invalid payload maps to HTTP 400; queue result failure or missing result maps to `ValueError`/`RuntimeError`; route maps `ValueError` to HTTP 400 and unexpected exceptions to HTTP 500. |
| Trace/telemetry | Queue-backed trace includes `queue_size`, `action_id`, `queue_wait_ms`, and failed/timed-out status transitions. | Same. |
| Focused tests | `test_remove_aoe_command_success`, `test_remove_aoe_command_validation_failure`, `test_remove_aoe_route_level_behavior_mapping` | `test_move_aoe_command_success`, `test_move_aoe_command_validation_failure`, `test_move_aoe_route_level_behavior_mapping` |

### Static map cells: obstacle, terrain, elevation

| Field | Obstacle | Terrain | Elevation |
| --- | --- | --- | --- |
| HTTP route or producer | `POST /api/dm/map/obstacles/cell` | `POST /api/dm/map/terrain/cell` | `POST /api/dm/map/elevation/cell` |
| Command constant/action | `COMMAND_SET_OBSTACLE = "set_obstacle"` | `COMMAND_SET_TERRAIN = "set_terrain"` | `COMMAND_SET_ELEVATION = "set_elevation"` |
| Source locations | `dnd_initative_tracker.py:dm_set_obstacle_cell`; `server_runtime.py:submit_command`; `dnd_initative_tracker.py:_lan_apply_action` | `dnd_initative_tracker.py:dm_set_terrain_cell`; `server_runtime.py:submit_command`; `dnd_initative_tracker.py:_lan_apply_action` | `dnd_initative_tracker.py:dm_set_map_elevation`; `server_runtime.py:submit_command`; `dnd_initative_tracker.py:_lan_apply_action` |
| Payload keys | `col`, `row`, `blocked`, `admin_token` | `col`, `row`, `is_rough`, `movement_type`, `color`, `label`, `admin_token` | `col`, `row`, `elevation`, `admin_token` |
| Result keys | `obstacle_result` with `ok`, `col`, `row`, `blocked`, maybe `error` | `terrain_result` with `ok`, `col`, `row`, `is_rough`, `movement_type`, maybe `error` | `elevation_result` with `ok`, `col`, `row`, `elevation`, maybe `error` |
| Response shape | `{ok: true, col, row, blocked, snapshot}` | `{ok: true, col, row, is_rough, movement_type, snapshot}` | `{ok: true, col, row, elevation, snapshot}` |
| Timeout behavior | `TimeoutError` maps to HTTP 504. | `TimeoutError` maps to HTTP 504. | `TimeoutError` maps to HTTP 504. |
| Validation/error mapping | Invalid payload or non-integer coordinates map to HTTP 400; command `ValueError` maps to HTTP 400; unexpected exceptions map to HTTP 500. | Same, plus route normalizes booleans and optional terrain metadata before command submission. | Same, plus missing `elevation` maps to HTTP 400. |
| Trace/telemetry | Queue-backed trace includes `queue_size`, `action_id`, `queue_wait_ms`, and failed/timed-out status transitions. | Same. | Same. |
| Focused tests | `test_set_obstacle_command_success`, `test_set_obstacle_command_validation_failure`, `test_set_obstacle_route_level_behavior_mapping` | `test_set_terrain_command_success`, `test_set_terrain_command_validation_failure`, `test_set_terrain_route_level_behavior_mapping` | `test_set_elevation_command_success`, `test_set_elevation_command_validation_failure`, `test_set_elevation_route_level_behavior_mapping` |

### Map settings

| Field | Current evidence |
| --- | --- |
| HTTP route or producer | `POST /api/dm/map/settings` |
| Command constant/action | `COMMAND_SET_MAP_SETTINGS = "set_map_settings"` |
| Source locations | `dnd_initative_tracker.py:dm_set_map_settings`; `server_runtime.py:submit_command`; `dnd_initative_tracker.py:_lan_apply_action` |
| Payload keys | `cols`, `rows`, `admin_token` |
| Result keys | `settings_result` with `ok`, `grid`, maybe `error` |
| Response shape | `{ok: true, grid, snapshot}` |
| Timeout behavior | `TimeoutError` maps to HTTP 504. |
| Validation/error mapping | Non-dict payload maps to HTTP 400; queue/facade `ValueError` maps to HTTP 400; route also checks `settings_result.ok` and maps false result to HTTP 400; unexpected exceptions map to HTTP 500. |
| Trace/telemetry | Queue-backed trace includes `queue_size`, `action_id`, and `queue_wait_ms`; failed/timed-out traces preserve command type and exception class. |
| Focused tests | `test_set_map_settings_success`, `test_set_map_settings_validation_failure`, `test_set_map_settings_route_level_behavior_mapping` |

### Backgrounds: upsert, remove, order

| Field | Upsert | Remove | Order |
| --- | --- | --- | --- |
| HTTP route or producer | `POST /api/dm/map/backgrounds` | `DELETE /api/dm/map/backgrounds/{bid}` | `POST /api/dm/map/backgrounds/{bid}/order` |
| Command constant/action | `COMMAND_UPSERT_MAP_BACKGROUND = "upsert_map_background"` | `COMMAND_REMOVE_MAP_BACKGROUND = "remove_map_background"` | `COMMAND_SET_MAP_BACKGROUND_ORDER = "set_map_background_order"` |
| Source locations | `dnd_initative_tracker.py:dm_upsert_background`; `server_runtime.py:submit_command`; `dnd_initative_tracker.py:_lan_apply_action` | `dnd_initative_tracker.py:dm_remove_background`; `server_runtime.py:submit_command`; `dnd_initative_tracker.py:_lan_apply_action` | `dnd_initative_tracker.py:dm_reorder_background`; `server_runtime.py:submit_command`; `dnd_initative_tracker.py:_lan_apply_action` |
| Payload keys | `asset_path`, `bid`, `x`, `y`, `scale_pct`, `trans_pct`, `locked`, `admin_token` | `bid`, `admin_token` | `bid`, `direction`, `admin_token` |
| Result keys | `background_result` with `ok`, `background`, maybe `error` | `remove_background_result` with `ok`, `bid`, maybe `error` | `reorder_background_result` with `ok`, `bid`, `background`, `backgrounds`, maybe `error` |
| Response shape | `{ok: true, background, snapshot}` | `{ok: true, bid, snapshot}` | `{ok: true, bid, background, backgrounds, snapshot}` |
| Timeout behavior | `TimeoutError` maps to HTTP 504. | Same. | Same. |
| Validation/error mapping | Invalid payload or missing `asset_path` maps to HTTP 400; result false maps to HTTP 400; `ValueError` maps to HTTP 400; unexpected exceptions map to HTTP 500. | Result false maps to HTTP 400; `ValueError` maps to HTTP 400; unexpected exceptions map to HTTP 500. | Invalid payload or missing `direction` maps to HTTP 400; result false maps to HTTP 400; `ValueError` maps to HTTP 400; unexpected exceptions map to HTTP 500. |
| Trace/telemetry | Queue-backed trace includes `queue_size`, `action_id`, `queue_wait_ms`, and failed/timed-out status transitions. | Same. | Same. |
| Focused tests | `test_upsert_background_success`, `test_upsert_background_validation_failure`, `test_upsert_background_route_level_behavior_mapping` | `test_remove_background_success`, `test_remove_background_validation_failure`, `test_remove_background_route_level_behavior_mapping` | `test_reorder_background_success`, `test_reorder_background_validation_failure`, `test_reorder_background_route_level_behavior_mapping` |

### Hazards: upsert, remove

| Field | Upsert | Remove |
| --- | --- | --- |
| HTTP route or producer | `POST /api/dm/map/hazards` | `DELETE /api/dm/map/hazards/{hazard_id}` |
| Command constant/action | `COMMAND_UPSERT_MAP_HAZARD = "upsert_map_hazard"` | `COMMAND_REMOVE_MAP_HAZARD = "remove_map_hazard"` |
| Source locations | `dnd_initative_tracker.py:dm_upsert_hazard`; `server_runtime.py:submit_command`; `dnd_initative_tracker.py:_lan_apply_action` | `dnd_initative_tracker.py:dm_remove_hazard`; `server_runtime.py:submit_command`; `dnd_initative_tracker.py:_lan_apply_action` |
| Payload keys | `col`, `row`, `hazard_id`, `kind`, `tactical_preset_id`, `count`, `name`, `payload`, `admin_token` | `hazard_id`, `admin_token` |
| Result keys | `hazard_result` with `ok`, `hazard_id`, `hazard`, maybe `error` | `hazard_result` with `ok`, `hazard_id`, maybe `error` |
| Response shape | `{ok: true, hazard_id, hazard, snapshot}` | `{ok: true, hazard_id, snapshot}` |
| Timeout behavior | `TimeoutError` maps to HTTP 504. | Same. |
| Validation/error mapping | Invalid payload, non-integer coordinates, or non-object nested `payload` map to HTTP 400; result false maps to HTTP 400; `ValueError` maps to HTTP 400; unexpected exceptions map to HTTP 500. | Result false maps to HTTP 400; `ValueError` maps to HTTP 400; unexpected exceptions map to HTTP 500. |
| Trace/telemetry | Queue-backed trace includes `queue_size`, `action_id`, `queue_wait_ms`, and failed/timed-out status transitions. | Same. |
| Focused tests | `test_upsert_hazard_success`, `test_upsert_hazard_validation_failure`, `test_upsert_hazard_route_level_behavior_mapping` | `test_remove_hazard_success`, `test_remove_hazard_validation_failure`, `test_remove_hazard_route_level_behavior_mapping` |

### Features: upsert, remove

| Field | Upsert | Remove |
| --- | --- | --- |
| HTTP route or producer | `POST /api/dm/map/features` | `DELETE /api/dm/map/features/{feature_id}` |
| Command constant/action | `COMMAND_UPSERT_MAP_FEATURE = "upsert_map_feature"` | `COMMAND_REMOVE_MAP_FEATURE = "remove_map_feature"` |
| Source locations | `dnd_initative_tracker.py:dm_upsert_feature`; `server_runtime.py:submit_command`; `dnd_initative_tracker.py:_lan_apply_action` | `dnd_initative_tracker.py:dm_remove_feature`; `server_runtime.py:submit_command`; `dnd_initative_tracker.py:_lan_apply_action` |
| Payload keys | `col`, `row`, `feature_id`, `kind`, `tactical_preset_id`, `count`, `name`, `payload`, `admin_token` | `feature_id`, `admin_token` |
| Result keys | `feature_result` with `ok`, `feature_id`, `feature`, maybe `error` | `feature_result` with `ok`, `feature_id`, maybe `error` |
| Response shape | `{ok: true, feature_id, feature, snapshot}` | `{ok: true, feature_id, snapshot}` |
| Timeout behavior | `TimeoutError` maps to HTTP 504. | Same. |
| Validation/error mapping | Invalid payload, non-integer coordinates, or non-object nested `payload` map to HTTP 400; result false maps to HTTP 400; `ValueError` maps to HTTP 400; unexpected exceptions map to HTTP 500. | Result false maps to HTTP 400; `ValueError` maps to HTTP 400; unexpected exceptions map to HTTP 500. |
| Trace/telemetry | Queue-backed trace includes `queue_size`, `action_id`, `queue_wait_ms`, and failed/timed-out status transitions. | Same. |
| Focused tests | `test_upsert_feature_success`, `test_upsert_feature_validation_failure`, `test_upsert_feature_route_level_behavior_mapping` | `test_remove_feature_success`, `test_remove_feature_validation_failure`, `test_remove_feature_route_level_behavior_mapping` |

## 4. Shared semantics now proven

The current source and focused tests prove these recurring semantics:

- Command constants are explicit strings in `server_runtime.py` and are imported by route handlers and tests.
- Migrated route handlers construct `RuntimeCommand(...)` and delegate through `ServerRuntimeFacade.submit_command(...)`.
- Newer migrated map commands preserve Tk/LanController authority by submitting to `_actions` and applying mutation through `_lan_apply_action(...)`.
- `_submit_to_lan_queue(...)` creates `action_id`, trace id, `_received_at_ns`, `_claimed_cid`, and an `_action_states` entry before queueing.
- Queue wait telemetry is recorded in facade traces as `queue_wait_ms` when completion timing is available.
- LanController dispatch emits `ws.action.dispatch.start` and `ws.action.dispatch.end` debug events with `queue_size`, optional `queue_wait_ms`, and `slow_queue_wait` when wait time exceeds 5000 ms.
- Timeout from the route-facing command path maps to HTTP 504 where route-level handling applies.
- Validation/domain failure maps to HTTP 400 where route-level handling applies.
- Unexpected runtime failure maps to HTTP 500 where route-level handling applies.
- Focused unit tests in `tests/test_server_runtime.py` cover command success, validation failure, route-level mapping, queue timeout, mapped queue errors, and trace metadata for the migrated command families.

## 5. Direct/non-queue routes and risk notes

This section is limited to named-file evidence. It is not a whole-repo route inventory.

### Confirmed direct or not-yet-queue-backed candidates

- `POST /api/dm/map/combatants/{cid}/move` directly calls `self.app._dm_move_combatant_on_map(...)`. It is a rules-aware combatant movement candidate and should not be treated as equivalent to place/facing.
- `POST /api/dm/map/aoes` directly calls `self.app._dm_create_aoe_on_map(payload)`. It remains separate from the migrated AoE move/remove commands.
- `POST /api/dm/map/structures` directly calls `self.app._dm_upsert_structure_on_map(...)` and validates `anchor_col`, `anchor_row`, optional object payload, and optional `occupied_offsets`.
- `POST /api/dm/map/structures/{structure_id}/move` directly calls `self.app._dm_move_structure_on_map(...)` and may include `blockers` in its response.
- `DELETE /api/dm/map/structures/{structure_id}` directly calls `self.app._dm_remove_structure_on_map(...)`.
- `POST /api/dm/map/ships` directly calls ship blueprint placement and returns ship/structure payloads plus snapshot.
- `POST /api/dm/map/ships/{structure_id}/maneuver` directly calls ship maneuver execution and can return blockers and target cells on failure.
- `POST /api/dm/map/ships/{source_structure_id}/weapons/fire` directly calls ship weapon resolution.
- `POST /api/dm/map/ships/{source_structure_id}/ram` directly calls ship ram resolution.
- `POST /api/dm/map/structure-templates/{template_id}/instantiate` directly calls structure template placement and can return blockers.
- `POST /api/dm/map/boarding-links`, `POST /api/dm/map/boarding-links/{link_id}/status`, and `DELETE /api/dm/map/boarding-links/{link_id}` directly call boarding-link helpers.
- `POST /api/dm/combat/next-turn`, `POST /api/dm/combat/prev-turn`, and `POST /api/dm/combat/set-turn` call `_dm_service` directly. These are direct turn/combat mutation routes, not facade commands.
- `POST /api/dm/combat/combatants/{cid}/hp`, `POST /api/dm/combat/combatants/{cid}/condition`, `POST /api/dm/combat/combatants/{cid}/temp-hp`, and `POST /api/dm/combat/combatants/{cid}/temp-hp-adjust` call `_dm_service` directly. These are HP/combat state mutation paths, not facade commands.
- `POST /api/dm/combat/start` and `POST /api/dm/combat/end` call `_dm_service` directly. These are combat state mutation paths, not facade commands.

### WebSocket/LAN convergence evidence

The named files show the LanController `_tick()` path dispatching queued WebSocket/action messages and facade-submitted queue messages through `_tracker._lan_apply_action(msg)`. It records `_action_states` completion and emits `ws.action.dispatch.start` / `ws.action.dispatch.end`.

The same `_lan_apply_action(...)` method includes non-facade action families such as manual HP/resource overrides, spell slot overrides, attack requests, spell target requests, movement action commands, consumables, reload weapon, and end turn. This confirms there is a broader LAN command convergence surface, but exact HTTP route mapping and migration scope for those families were not fully inventoried in this pass.

### Unknowns from this pass

- Full WebSocket/LAN convergence scope is unknown beyond the named `_tick()` and `_lan_apply_action(...)` evidence.
- Direct route inventory outside the named route windows is unknown.
- Snapshot/cache read-model migration boundaries are unknown beyond the architecture direction and existing queue checkpoint docs.
- Package-boundary shape for a future app-host/runtime-service split is not determined by this document.

## 6. Naming and documentation gaps

- Command constant names mix domain nouns and verb phrases but are mostly consistent: `COMMAND_SET_*`, `COMMAND_UPSERT_*`, `COMMAND_REMOVE_*`, plus older `COMMAND_UPDATE_SPELL_COLOR`, `COMMAND_PLACE_COMBATANT`, `COMMAND_MOVE_AOE`, and `COMMAND_TEST_QUEUE`.
- Action names are not uniformly namespaced. Examples include `aoe_remove` / `aoe_move` while most map commands use `set_*`, `upsert_*`, or `remove_*`.
- Spell color is documented with the command boundary but is not queue-backed; future docs should keep that distinction explicit.
- Route-level tests are named inconsistently: some include `_command_success`, some omit `_command_` such as `test_upsert_background_success` and `test_set_map_settings_success`.
- Result key naming is family-specific and not uniform: `remove_result`, `move_result`, `obstacle_result`, `terrain_result`, `elevation_result`, `settings_result`, `background_result`, `remove_background_result`, `reorder_background_result`, `hazard_result`, `feature_result`, and `place_result`.
- Hazard and feature remove reuse `hazard_result` and `feature_result` rather than remove-specific result keys, while background removal uses `remove_background_result`.
- Trace event naming is still LanController/WebSocket shaped (`ws.action.dispatch.start` / `ws.action.dispatch.end`) even when the producer is a facade-submitted HTTP route command.
- Documentation coverage before this inventory was spread across completed work docs, living docs, source branches, and tests; route-command mapping was implicit rather than durable in one architecture document.

## 7. Recommended next step after inventory

Recommended next planning/evidence item:

`WORK-20260630-runtime-facade-package-boundary-readiness`

The next decision should target app-host/runtime-service package-boundary readiness, not app implementation. This inventory makes the current command boundary explicit enough to ask whether package-boundary planning can start safely, or whether a smaller command semantics cleanup planning slice should come first.

The planning question should be:

Can the repo define an app-host/runtime-service package boundary around the current facade/queue/snapshot contracts without source changes, or do result-key naming, trace naming, and the spell-color direct-facade exception need a separate semantics-cleanup plan before package-boundary work?

One more static route evidence slice is lower priority unless a developer explicitly wants to continue route migration next. The named evidence suggests the obvious low-risk static map route sequence has already been consumed; remaining structure/ship/boarding and rules-aware movement/AoE creation paths need fresh evidence before implementation.
