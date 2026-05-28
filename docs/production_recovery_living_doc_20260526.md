# Production Recovery Living Document — 2026-05-26

## A. Executive Goal
Reliable real-table D&D combat support where the DM can see/use maps, players can see/use spells and core actions, normal combat is responsive, and experimental tactical/ship/surface systems cannot break core play.

## B. Definition of Production-Ready
An `init-tracker` release is considered production-ready only when:
- **Map Viability**: The DM can reliably view and interact with the tactical grid on `/dm/map` and `/dmcontrol`.
- **Capability Survival**: Spells, resource pools, and inventory are visible, manageable, and castable for all players; data is never clobbered by high-frequency updates.
- **Responsiveness**: Ordinary hot-path actions (Move, Attack, Cast, Next Turn) respond in `< 1000ms` (Gate 3 requirement).
- **Clean Separation**: Experimental tactical/ship/surface systems do not leak into the combat-lite hot path.
- **Stable Deployment**: The production runbook is verified, and the server starts cleanly in a headless Linux environment.
- **Verified Smoke**: All core workflows have passed manual browser smoke tests recorded in `docs/runtime_reports/`.

## C. Source / Test / Smoke Matrix

| Product Surface | Current Status | Primary Source | Primary Tests | Required Browser Smoke | Known Blocker | Next Gate |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **DM Cockpit (/dm)** | Verified by unit tests only | `assets/web/dm/index.html` | `tests/test_lan_snapshot_static.py` | Load /dm, check roster visibility and encounter start. | None | G-1 |
| **DM Map (/dm/map)** | Contradicted | `assets/web/dm/index.html` | `tests/test_dm_tactical_map_routes.py` | Load /dm/map, verify grid render and token drag. | C-004 | G-1 |
| **DM Control (/dmcontrol)** | Contradicted | `assets/web/dmcontrol/index.html` | `tests/test_dm_tactical_map_routes.py` | Load /dmcontrol, move a monster, activate ability. | C-002 | G-1 |
| **LAN Player Page** | Needs browser smoke | `assets/web/lan/index.html` | `tests/test_lan_snapshot_cache.py` | Load LAN, verify HP bar and turn indicator. | None | G-2 |
| **Spells / Manage Spells** | Known P0 history / needs revalidation | `monster_capability_service.py` | `tests/test_lan_spellbook_contract_ui.py` | Add "Destructive Wave" to Paladin, verify it appears. | C-005 | G-2 |
| **Resource Pools** | Verified by unit tests only | `dnd_initative_tracker.py` | `tests/test_resource_pool_accounting.py` | Use "Action Surge", verify decrement and toast. | None | G-4 |
| **Inventory / Equipment** | Verified by unit tests only | `player_command_service.py` | `tests/test_items_weapon_resolution.py` | Equip weapon in LAN, verify in Attack dropdown. | None | G-4 |
| **Attacks / Resolution** | Needs browser smoke | `combat_service.py` | `tests/test_lan_attack_request.py` | Perform melee attack, check log and damage apply. | None | G-3 |
| **Action Idempotency / Ack** | Verified by unit tests only | `dnd_initative_tracker.py` | `tests/test_lan_movement_action_dispatch.py` | Double-click move; verify only one move executes. | None | G-3 |
| **Snapshot / Cache / Payload** | Verified by unit tests only | `dnd_initative_tracker.py` | `tests/test_lan_snapshot_cache.py` | Verify reconnecting client sees same state. | ADR-0002 | G-2 |
| **Performance / Latency** | Known P0 history / needs revalidation | `runtime_config.py` | `tests/test_trace_latency_summary.py` | Run `scripts/trace_latency_summary.py` post-smoke. | 11s wild-shape | G-3 |
| **Long Rest** | Verified by unit tests only | `combat_service.py` | `tests/test_lan_long_rest_semantics.py` | Apply long rest, check HP/slots/resources restored. | None | G-4 |
| **Pact Slots** | Verified by unit tests only | `dnd_initative_tracker.py` | `tests/test_pact_magic_spell_slots.py` | Cast Warlock spell, check slot count decrement. | None | G-4 |
| **Old Man Fury / Flurry** | Needs browser smoke | `combat_service.py` | `tests/test_monk_features.py` | Use "Flurry of Blows", verify extra attack granted. | None | G-4 |
| **Experimental: Ships** | Unknown | `ship_blueprints.py` | `tests/test_lan_snapshot_static.py` | None (Quarantined) | Default OFF | G-5 |
| **Experimental: Surfaces** | Unknown | `map_state.py` | `tests/test_lan_snapshot_static.py` | None (Quarantined) | Default OFF | G-5 |
| **Experimental: Boarding** | Unknown | `combat_service.py` | `tests/test_boarding_logic.py` | None (Quarantined) | Default OFF | G-5 |
| **Experimental: Objects** | Unknown | `map_state.py` | `tests/test_structure_objects.py` | None (Quarantined) | Default OFF | G-5 |
| **Monster-Pilot** | Contradicted | `dnd_initative_tracker.py` | N/A | Verify legacy route is unreachable if removed. | C-003 | G-5 |
| **Deployment / Server** | Needs browser smoke | `serve_headless.py` | N/A | Server starts < 30s, reachable via public IP. | C-007 | G-6 |

## D. Explicit Map Contract

| Endpoint / Surface | Current Source Behavior | Intended Behavior | Required Test | Required Browser Smoke | Contradiction Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `/api/dm/combat` | Combat-lite (no map) | Combat-lite (no map) | `test_dm_tactical_map_routes` | Verify `/dm` loads without map state. | None |
| `/api/dm/combat?workspace=dmcontrol` | Forces Tactical Snapshot | Forces Tactical Snapshot | `test_dmcontrol_workspace_query` | Verify `/dmcontrol` loads grid/tokens. | C-002 |
| `/api/dm/combat/next-turn` | Combat-lite (no map) | Combat-lite (no map) | `test_next_turn_is_combat_lite` | Verify advance turn is fast in `/dm`. | None |
| `/api/dm/combat/next-turn?workspace=dmcontrol` | Forces Tactical Snapshot | Forces Tactical Snapshot | `test_dmcontrol_next_turn_tactical` | Verify advance turn refreshes map in `/dmcontrol`. | None |
| `/dm/map` | Forces Tactical Snapshot | Forces Tactical Snapshot | `test_dm_map_route_forces_tactical` | Verify map workspace render. | C-004 |
| `/api/dm/map/*` | Always Tactical | Always Tactical | `test_map_api_routes_tactical` | Verify manual move on grid. | None |
| `/dmcontrol` | Polling (2s), HTTP GET | Polling (2s), HTTP GET | `test_dmcontrol_polling_snapshot` | Verify monster turn dashboard updates. | C-002 |
| `/ws/dm` | Combat-lite by default | Combat-lite by default | `test_ws_default_is_lite` | Verify PC turn updates are fast. | None |
| `/ws/dm?workspace=map` | Marked `is_map_client` | Marked `is_map_client` | `test_ws_map_workspace_subscription` | Verify `/dm/map` receives WS updates. | None |
| `/ws/dm?workspace=dmcontrol` | Marked `is_map_client` | Marked `is_map_client` | `test_ws_dmcontrol_subscription` | Verify `/dmcontrol` (if it opens WS) receives state. | C-002 |

## E. Product Surface Decision Table

| Feature / System | Decision | Why | Source / Flag | Required Test | Quarantine / Deactivation Mechanism |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Tactical Map** | **Keep Core** | Essential for DM. | `INIT_TRACKER_ENABLE_TACTICAL_MAP` | `test_dm_tactical_map_routes` | Default OFF for non-map routes via flag check in `_dm_console_snapshot_payload`. |
| **Ship / Boarding** | **Quarantine** | Experimental, high lag. | `INIT_TRACKER_ENABLE_SHIP_SURFACES` | `test_lan_snapshot_static` | Strict `if not ship_surfaces_enabled()` in `_lan_force_state_broadcast` and `_dm_tactical_snapshot`. |
| **Surfaces / Terrain** | **Quarantine** | Experimental. | `INIT_TRACKER_ENABLE_SHIP_SURFACES` | `test_lan_snapshot_static` | Strict `if not ship_surfaces_enabled()` gate in `map_state.py` builders. |
| **Structures / Objects** | **Quarantine** | Experimental. | `INIT_TRACKER_ENABLE_SHIP_SURFACES` | `test_structure_objects` | Gate token synthesis in `_dm_tactical_snapshot`. |
| **Monster-Pilot** | **Remove Later** | Redundant. | `/api/dm/monster-pilot` | N/A | Delete routes and `_dm_monster_pilot_*` methods in `InitiativeTracker`. |
| **Wild-Shape** | **Keep Core** | Core Druid. | `combat_service.py` | `test_wild_shape` | Optimize lookup; ensure no tactical builds occur in HP refresh. |

## F. Release Gates

### Gate 1: Map Surface Contract Restoration
- **Goal**: DM can reliably use `/dm/map` and `/dmcontrol`.
- **Allowed Files**:
  - `dnd_initative_tracker.py`
  - `assets/web/dmcontrol/index.html`
  - `tests/test_dm_tactical_map_routes.py`
  - `docs/production_recovery_living_doc_20260526.md`
  - `docs/runtime_reports/gate1_map_surface_contract_*.md`
- **Forbidden Scope**: No changes to spell engine, combat service, or performance flags.
- **Required Unit Tests**: Fix `tests/test_dm_tactical_map_routes.py` (replace invalid `_dm_console_snapshot` calls).
- **Required Browser Smoke**: Move monster in `/dmcontrol`, Verify grid tokens in `/dm/map`.
- **Pass Criteria**: `test_dm_tactical_map_routes` passes; smoke tests successful.
- **Fail Criteria**: AttributeError persists; `/dmcontrol` remains blank.
- **Rollback**: Revert `dnd_initative_tracker.py` changes.

### Gate 2: Spell / Capability Contract Stabilization
- **Goal**: Capability data (spells/resources) survives all updates.
- **Allowed Files**: `monster_capability_service.py`, `spell_engine_primitives.py`, `assets/web/lan/index.html`.
- **Forbidden Scope**: No changes to map grid or movement logic.
- **Required Unit Tests**: `tests/test_lan_spellbook_contract_ui.py`, `tests/test_lan_snapshot_cache.py`.
- **Required Browser Smoke**: Add spell in "Manage Spells", verify it persists after HP damage update.
- **Pass Criteria**: ADR-0002/0003 verified; first-load never empty.
- **Fail Criteria**: Empty spell panel after reconnect.
- **Rollback**: Revert `monster_capability_service.py`.

### Gate 3: Combat Responsiveness
- **Goal**: Hot actions `< 5000ms` for table use; targeted `< 1000ms`.
- **Allowed Files**: `runtime_config.py`, `combat_service.py`, `scripts/trace_latency_summary.py`.
- **Forbidden Scope**: No UI re-styling or feature addition.
- **Required Unit Tests**: `tests/test_trace_latency_summary.py`.
- **Required Browser Smoke**: Rapid sequence of Move -> Attack -> End Turn.
- **Required Trace Evidence**: `scripts/trace_latency_summary.py` shows zero `static_plus_dynamic` builds in hot path.
- **Pass Criteria**: All hot actions `< 5000ms` (measured); wild-shape attack `< 3000ms`.
- **Fail Criteria**: Any hot action `> 5000ms`.
- **Rollback**: Disable experimental flags.

### Gate 4: Resource / Rest / Pact Mechanics
- **Goal**: Mechanics correctness for long rest and resource pools.
- **Allowed Files**: `combat_service.py`, `player_command_service.py`.
- **Forbidden Scope**: No map or networking changes.
- **Required Unit Tests**: `tests/test_resource_pool_accounting.py`, `tests/test_pact_magic_spell_slots.py`.
- **Required Browser Smoke**: Perform Long Rest, verify HP/slots/pools reset.
- **Pass Criteria**: 100% pass on resource/rest unit tests.
- **Fail Criteria**: Long rest fails to restore Warlock slots.

### Gate 5: Experimental Feature Quarantine
- **Goal**: Strict isolation of ships/surfaces.
- **Allowed Files**: `dnd_initative_tracker.py`, `runtime_config.py`.
- **Required Unit Tests**: `tests/test_lan_snapshot_static.py` (verifying flag gate).
- **Pass Criteria**: Zero `_dm_tactical_snapshot` calls when flags are `false`.
- **Fail Criteria**: Tactical builds occurring in `combat-lite` path.

### Gate 6: Production Deployment Runbook
- **Goal**: Reliable headless start.
- **Allowed Files**: `serve_headless.py`, `requirements.txt`.
- **Required Trace Evidence**: Startup log showing zero errors.
- **Pass Criteria**: Server starts in `< 30s` on Linux; accessible via LAN.

## G. Contradiction Register

| ID | Claim | Conflict | Impact | Resolution |
| :--- | :--- | :--- | :--- | :--- |
| **C-001** | Tests call `lan._dm_console_snapshot` | Method does not exist (it's a local closure). | Broken tests. | Fix to `_dm_console_snapshot_payload`. |
| **C-002** | `/dmcontrol` uses WebSockets | Frontend uses polling; backend supports WS workspace. | Doc confusion. | Clarify: `/dmcontrol` frontend polls. |
| **C-003** | `/api/dm/monster-pilot` is active | Replaced by `/dmcontrol` and monster-capability API. | Code clutter. | Gate 5: Remove legacy routes. |
| **C-004** | Map is "Completed" | DM report: "unable to use map". | Critical failure. | Gate 1 must restore map interaction. |
| **C-005** | Spells are resolved | Recurrent first-load clobber issues. | Brittle UI. | Gate 2: Enforce ADR-0002. |
| **C-006** | Ships are quarantined | They still leak into `_lan_snapshot` if not strictly gated. | Performance smell. | Harden `if not ship_surfaces_enabled()` checks. |
| **C-007** | Production is ready | No systemd or verified runbook. | Deployment risk. | Gate 6: Finalize runbook. |

## H. Smoke Findings Added 2026-05-27 — Gate 3 Post-Patch

Source report:
- `docs/runtime_reports/gate3_postpatch_smoke_20260527.md`

Current Gate 3 decision:
- Gate 3 remains OPEN.
- G3-03 should be preserved as a partial latency improvement because post-patch trace showed `static_plus_dynamic builds: 0`.
- Gate 3 is not ready because Long Rest remains catastrophically slow and combat loop still feels mildly laggy.

Fresh trace:
- `logs/debug-trace-20260527-102803.jsonl`

Key trace findings:
- `combat_service.long_rest`: ~31.4s
- top `http.request`: ~31.6s
- `_load_player_yaml_cache`: ~10.2s
- `_lan_snapshot`: ~8.2s
- `player_command.cast_aoe`: ~3.9s max observed
- `static_plus_dynamic builds`: 0
- queue waits over 1000ms: none
- queue waits over 5000ms: none

Backlog captured from smoke:
- BUG-20260527-01: Long Rest latency P0.
- BUG-20260527-02: Free spells can be added but cannot be selected for removal.
- BUG-20260527-03: Switching characters can temporarily render spell list empty until refresh.
- BUG-20260527-04: Wild Shape resets movement instead of preserving distance already moved.
- BUG-20260527-05: Flurry/Fury targeting overlay can trap movement after target death.
- BUG-20260527-06: Conditions/effects render incorrectly in DM console and prone movement is not enforced.
- BUG-20260527-07: Lightning Bolt passed-save damage was inconsistent across identical enemies.
- BUG-20260527-08: Resource pool UI updates slowly after use.

Next recommended task:
- Gate 3 Long Rest latency root-cause and narrow fix.
- Do not bundle the unrelated smoke bugs into the Long Rest fix.

## I. Smoke Finding Added 2026-05-28 — Gate 3 Long Rest G3-10

Source report:
- `docs/runtime_reports/gate3_longrest_g310_smoke_20260528.md`

Decision:
- G3-10 reduced Long Rest from ~31s pre-fix and ~15–16s during failed deferred attempts to ~1.25s in live trace.
- This clears the Gate 3 hard fail threshold for Long Rest, pending continued regression checks.
- The fix uses deferred/bulk persistence, so durability after restart is a required smoke condition.

Fresh trace:
- `logs/debug-trace-20260528-123238.jsonl`

Key trace findings:
- `combat_service.long_rest`: ~1.25s
- `/api/dm/combat` max during smoke: ~1.28s
- `static_plus_dynamic builds`: 0
- queue waits over 1000ms: none
- queue waits over 5000ms: none

Regression guardrail:
- Do not accept future Long Rest changes unless live trace keeps `combat_service.long_rest < 5000ms` and restored state survives restart.
