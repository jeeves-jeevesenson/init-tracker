# Server Runtime Facade Queue Migration Checkpoint - 2026-06-30

## Current Status

Latest known local commit at the time of this checkpoint:

`66fd48c WORK-20260630-runtime-facade-queue-command-feature-remove: queue feature removal`

Ledger status:

- `docs/work_items/current_work.md` is `Idle`.
- No active work item is open.
- This checkpoint is docs/planning only; no app/source implementation was performed.

The route-migration loop is intentionally paused after `WORK-20260630-runtime-facade-queue-command-feature-remove`. The completed low-risk static map queue-command sequence now needs to be reconciled with the broader server-runtime extraction direction before selecting another implementation slice.

## Queue-Backed Production Routes Completed

The following production routes are now routed through `ServerRuntimeFacade.submit_command(...)` and the Tk/LanController queue seam where confirmed by the completed work ledger, completed work docs, route inventory, command constants, and focused test inventory.

### Spell

- `POST /api/spells/{spell_id}/color`
  - Command: `COMMAND_UPDATE_SPELL_COLOR = "update_spell_color"`

### Combatant Map Actions

- `POST /api/dm/map/combatants/{cid}/facing`
  - Command: `COMMAND_SET_FACING = "set_facing"`
- `POST /api/dm/map/combatants/{cid}/place`
  - Command: `COMMAND_PLACE_COMBATANT = "place_combatant"`

### Overlays

- `POST /api/dm/map/overlays/auras`
  - Command: `COMMAND_SET_AURAS_ENABLED = "set_auras_enabled"`

### AoE Remove/Move

- `DELETE /api/dm/map/aoes/{aid}`
  - Command: `COMMAND_REMOVE_AOE = "aoe_remove"`
- `POST /api/dm/map/aoes/{aid}/move`
  - Command: `COMMAND_MOVE_AOE = "aoe_move"`

### Static Map Cells

- `POST /api/dm/map/obstacles/cell`
  - Command: `COMMAND_SET_OBSTACLE = "set_obstacle"`
- `POST /api/dm/map/terrain/cell`
  - Command: `COMMAND_SET_TERRAIN = "set_terrain"`
- `POST /api/dm/map/elevation/cell`
  - Command: `COMMAND_SET_ELEVATION = "set_elevation"`

### Map Settings

- `POST /api/dm/map/settings`
  - Command: `COMMAND_SET_MAP_SETTINGS = "set_map_settings"`

### Backgrounds

- `POST /api/dm/map/backgrounds`
  - Command: `COMMAND_UPSERT_MAP_BACKGROUND = "upsert_map_background"`
- `DELETE /api/dm/map/backgrounds/{bid}`
  - Command: `COMMAND_REMOVE_MAP_BACKGROUND = "remove_map_background"`
- `POST /api/dm/map/backgrounds/{bid}/order`
  - Command: `COMMAND_SET_MAP_BACKGROUND_ORDER = "set_map_background_order"`

### Hazards

- `POST /api/dm/map/hazards`
  - Command: `COMMAND_UPSERT_MAP_HAZARD = "upsert_map_hazard"`
- `DELETE /api/dm/map/hazards/{hazard_id}`
  - Command: `COMMAND_REMOVE_MAP_HAZARD = "remove_map_hazard"`

### Features

- `POST /api/dm/map/features`
  - Command: `COMMAND_UPSERT_MAP_FEATURE = "upsert_map_feature"`
- `DELETE /api/dm/map/features/{feature_id}`
  - Command: `COMMAND_REMOVE_MAP_FEATURE = "remove_map_feature"`

## Remaining Direct Or Not-Yet-Selected Candidates

This list is limited to candidates supported by the named source docs and named code/test files inspected for this checkpoint. It is not a full repo inventory.

### Confirmed Direct Routes In Inspected Route Inventory

- `POST /api/dm/map/combatants/{cid}/move`
  - Still calls `self.app._dm_move_combatant_on_map(...)` directly.
  - Prior selection docs classify this as high risk because it is rules-aware movement tied to pathfinding, movement budgets, mounts/riders, hazards, turn state, and reaction/opportunity prompts.
- `POST /api/dm/map/aoes`
  - Still calls `self.app._dm_create_aoe_on_map(payload)` directly.
  - Prior selection docs classify this as high risk because AoE creation can enter spell preset, resource, summon, reaction, and counterspell pipelines.
- `POST /api/dm/map/structures`
  - Still calls `self.app._dm_upsert_structure_on_map(...)` directly.
- `POST /api/dm/map/structures/{structure_id}/move`
  - Still calls `self.app._dm_move_structure_on_map(...)` directly.
- `DELETE /api/dm/map/structures/{structure_id}`
  - Still calls `self.app._dm_remove_structure_on_map(...)` directly.

### Other Structure/Ship-Related Direct Routes Observed

These were visible in the inspected route section, but were not evaluated as low-risk queue migration candidates in the recent completed selection docs:

- `POST /api/dm/map/ships`
- `POST /api/dm/map/ships/{structure_id}/maneuver`
- `POST /api/dm/map/ships/{source_structure_id}/weapons/fire`
- `POST /api/dm/map/ships/{source_structure_id}/ram`
- `POST /api/dm/map/structure-templates/{template_id}/instantiate`
- `POST /api/dm/map/boarding-links`
- `POST /api/dm/map/boarding-links/{link_id}/status`
- `DELETE /api/dm/map/boarding-links/{link_id}`

### LAN Action Types Visible But Not Selected Here

The inspected `_lan_apply_action` inventory includes action branches beyond the migrated route-command family, including:

- `manual_override_hp`
- `manual_override_spell_slot`
- `manual_override_resource_pool`
- `attack_request`
- `spell_target_request`
- `lay_on_hands_use`
- `inventory_adjust_consumable`
- `use_consumable`
- `reload_weapon`
- `end_turn`

These indicate HP/resource/combat/turn paths exist, but this checkpoint did not inspect their route surfaces or domain semantics beyond the named inventory. Treat the remaining turn/combat mutation scope as unknown until a focused evidence slice names exact files and routes.

### Unknowns

- Full WebSocket/LAN convergence scope was not inventoried in this checkpoint.
- Snapshot/cache read-model contracts were not re-inventoried beyond the architecture/living-plan direction.
- Package-boundary candidates under a future `init_tracker_server/` shape were not inspected or created.

## Risk Classification

### Low Risk

Static metadata and map UI mutations similar to already completed cells/backgrounds/hazards/features are low risk when they:

- mutate static map metadata or presentation state;
- do not spend resources;
- do not enter prompt/reaction/counterspell flows;
- do not depend on turn order or movement budgets;
- can safely execute on the Tk/main thread through the existing LanController queue authority.

No additional low-risk candidate should be assumed to remain without a fresh planning slice, because the recent sequence has already consumed the obvious single-cell/background/hazard/feature candidates.

### Medium Risk

Structures are medium risk if the currently direct structure routes are confirmed to be limited to static map administration. The inspected route docs and prior selection docs show they involve multi-cell dimensions, `occupied_offsets`, collision/blocker semantics, and returned blockers. That makes them higher risk than simple cells/features even if they remain map-static.

Ship, structure-template, and boarding-link routes should not be treated as equivalent to simple static structure CRUD without focused evidence. The inspected route names and helper calls suggest additional ship/boarding semantics.

### High Risk

The following should not be selected without a new evidence/planning slice:

- `POST /api/dm/map/aoes`
- `POST /api/dm/map/combatants/{cid}/move`
- prompt/reaction/counterspell paths
- turn, HP, resource, attack, spell-target, reload, consumable, and combat-state paths
- broad WebSocket/LAN convergence

These paths can involve blocking prompts, reaction/counterspell decisions, resource spending, turn authority, pathfinding, hazards, mounts/riders, and hidden-state/persistence concerns. Migrating them through the queue seam is strategically aligned, but selecting them without fresh route-specific evidence would convert the incremental command-boundary work into an unsafe broad runtime rewrite.

## Command Semantics Now Proven

The completed queue-backed slices have proven the following semantics in the local repo:

- Command constants/action names exist in `server_runtime.py` for each migrated route family.
- `ServerRuntimeFacade.submit_command(...)` delegates each migrated command to `_submit_to_lan_queue(...)`, except the older spell-color command which uses the facade command boundary with direct app helper execution.
- Production route handlers construct `RuntimeCommand(...)`, pass the command to `self._runtime.submit_command(...)`, and map success/error results back to HTTP response semantics.
- Tk/LanController queue authority remains intact: queue-backed commands are applied by `_lan_apply_action(...)` on the Tk/main thread using the existing `_actions` flow.
- Timeout and error mapping are established in route handlers:
  - `TimeoutError` maps to HTTP 504.
  - `ValueError` maps to HTTP 400.
  - unexpected exceptions map to HTTP 500.
- Validation and domain failure mapping are established through result payloads such as `place_result`, `remove_result`, `move_result`, `obstacle_result`, `terrain_result`, `elevation_result`, `settings_result`, `background_result`, `remove_background_result`, `reorder_background_result`, `hazard_result`, and `feature_result`.
- Queue wait telemetry and trace expectations are covered through `RuntimeCommandTrace`, including `queue_size`, `queue_wait_ms`, `completed`, `failed`, and `timed_out` status paths.
- Focused tests in `tests/test_server_runtime.py` cover success, validation failure, trace/telemetry, and route-level behavior mapping for the migrated command families through the current feature-removal slice.

## Reconciliation With Deep Research

The deep research direction remains strategically aligned:

- ASGI server first.
- Runtime as a service.
- Explicit runtime command boundary.
- Cached read models and explicit snapshot contracts.
- Event publication as a later boundary-hardening step.
- No TypeScript/game-engine rewrite as the near-term answer.

The research is partly stale versus current local repo state because it predates the later local queue-command migration chain. The correct interpretation is not that the repo should pivot blindly into broad `init_tracker_server/` restructuring. The local queue-backed facade migrations are already the tactical extraction seam that builds the runtime command boundary incrementally while preserving behavior.

The next decision is not "continue the old route loop forever" versus "start a big rewrite." The real decision is which bounded next step best advances server-runtime extraction after this completed low-risk migration sequence.

## Recommended Next Decision Options

A. Continue one more static map slice only if a low-risk candidate remains and the ledger authorizes a planning slice.

B. Consolidate `ServerRuntimeFacade` command inventory and route-command documentation before more migrations.

C. Start app-host/runtime-service package boundary planning for `init_tracker_server/` as a separate planning/evidence item.

## Recommended Next Action

Recommended next planning slice:

`WORK-20260630-runtime-facade-next-boundary-checkpoint-decision`

Goal for that slice: decide between one more static map migration, `ServerRuntimeFacade`/command inventory consolidation, or app-host/runtime-service package boundary planning. It should be evidence/planning only unless the ledger explicitly opens a bounded implementation item afterward.
