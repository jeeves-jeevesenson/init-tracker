# Production Recovery Living Document — 2026-05-26

## A. Executive Goal
Reliable real-table D&D combat support where the DM can see/use maps, players can see/use spells and core actions, normal combat is responsive, and experimental tactical/ship/surface systems cannot break core play.

## B. Source / Test / Smoke Matrix

| Product Surface | Current Status | Primary Source | Primary Tests | Required Smoke | Known Blocker | Next Gate |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **DM Cockpit (/dm)** | Verified | `assets/web/dm/index.html` | `tests/test_lan_snapshot_static.py` | Load /dm, check roster visibility. | None | G-1 |
| **DM Map (/dm/map)** | Contradicted | `assets/web/dm/index.html` | `tests/test_dm_tactical_map_routes.py` | Load /dm/map, verify grid render. | C-004 | G-1 |
| **DM Control (/dmcontrol)** | Contradicted | `assets/web/dmcontrol/index.html` | `tests/test_dm_tactical_map_routes.py` | Load /dmcontrol, move a monster. | C-002 | G-1 |
| **LAN Player Page** | Verified | `assets/web/lan/index.html` | `tests/test_lan_snapshot_cache.py` | Load LAN, verify HP bar. | None | G-2 |
| **Spells / Manage Spells** | brittle | `monster_capability_service.py` | `tests/test_lan_spellbook_contract_ui.py` | Add a spell to a PC, verify it appears. | C-005 | G-2 |
| **Resource Pools** | Verified | `dnd_initative_tracker.py` | `tests/test_resource_pool_accounting.py` | Use "Action Surge", verify it decrements. | None | G-4 |
| **Inventory / Equipment** | Verified | `player_command_service.py` | `tests/test_items_weapon_resolution.py` | Equip weapon in LAN, verify in Attack. | None | G-4 |
| **Attacks / Resolution** | brittle | `combat_service.py` | `tests/test_lan_attack_request.py` | Perform melee attack, check log. | None | G-3 |
| **Action Idempotency** | Verified | `dnd_initative_tracker.py` | `tests/test_lan_movement_action_dispatch.py` | Double-click move, only one move occurs. | None | G-3 |
| **Performance / Latency** | **Blocked** | `runtime_config.py` | `tests/test_trace_latency_summary.py` | Run `scripts/trace_latency_summary.py`. | 11s wild-shape lookup | G-3 |
| **Long Rest** | Verified | `combat_service.py` | `tests/test_lan_long_rest_semantics.py` | Apply long rest, check HP/slots. | None | G-4 |
| **Pact Slots** | Verified | `dnd_initative_tracker.py` | `tests/test_pact_magic_spell_slots.py` | Cast Warlock spell, check slot count. | None | G-4 |
| **Experimental: Ships** | **Quarantine** | `ship_blueprints.py` | `tests/test_lan_snapshot_static.py` | None | Default OFF | G-5 |
| **Experimental: Surfaces** | **Quarantine** | `map_state.py` | `tests/test_lan_snapshot_static.py` | None | Default OFF | G-5 |
| **Deployment** | brittle | `serve_headless.py` | N/A | Server starts in < 30s. | C-007 | G-6 |

## C. Product Surface Decision Table

| Feature / System | Decision | Why | Source / Flag | Risk |
| :--- | :--- | :--- | :--- | :--- |
| **Tactical Map Projections** | **Keep Core** | Essential for DM map usage. | `INIT_TRACKER_ENABLE_TACTICAL_MAP` | High latency if not gated. |
| **Ship / Boarding** | **Quarantine** | Experimental, high overhead. | `INIT_TRACKER_ENABLE_SHIP_SURFACES` | Performance leakage. |
| **Surfaces / Terrain** | **Quarantine** | Experimental. | `INIT_TRACKER_ENABLE_SHIP_SURFACES` | Performance leakage. |
| **Monster-Pilot** | **Remove Later** | Redundant with /dmcontrol. | `/api/dm/monster-pilot` | Code clutter. |
| **Wild-Shape / Transformations** | **Keep Core** | Core Druid mechanics. | `combat_service.py` | High lookup latency (11s). |

## D. Explicit Map Contract

| Endpoint / Surface | Current Behavior | Intended Behavior | Test Coverage |
| :--- | :--- | :--- | :--- |
| `/api/dm/combat` | Combat-lite (no map) | Combat-lite (no map) | `tests/test_dm_tactical_map_routes.py` |
| `?workspace=dmcontrol` | Forces Tactical Snapshot | Forces Tactical Snapshot | `tests/test_dm_tactical_map_routes.py` |
| `/dmcontrol` | Polling (2s), HTTP GET | Polling (2s), HTTP GET | None (Manual smoke) |
| `/ws/dm?workspace=map` | WS, marked is_map_client | WS, marked is_map_client | `tests/test_dm_tactical_map_routes.py` |

## E. Performance Gate (G-3)
- **Hot Actions**: Move, Attack, Cast, Next Turn must be `< 1000ms`.
- **Blocker**: `tests/test_wild_shape.py` attack tests taking `11.682s`.
- **Requirement**: No ordinary action over `5000ms` for Gate 3 pass.
- **Trace Evidence**: `scripts/trace_latency_summary.py` must show `zero` ordinary `_dm_tactical_snapshot` calls.

## F. Contradiction Register

| ID | Claim | Conflict | Impact | Resolution |
| :--- | :--- | :--- | :--- | :--- |
| **C-001** | Tests call `lan._dm_console_snapshot` | Method does not exist (it's a local closure). | Broken tests. | Fix to `_dm_console_snapshot_payload`. |
| **C-002** | `/dmcontrol` uses WebSockets | Frontend uses polling; backend supports WS workspace. | Doc confusion. | Clarify: `/dmcontrol` frontend polls. |
| **C-004** | Map is "Completed" | DM report: "unable to use map". | Critical failure. | Gate 1 must restore map interaction. |
| **C-006** | Ships/Surfaces are quarantined | They still leak into `_lan_snapshot` if not gated. | Performance smell. | Harden `if not ship_surfaces_enabled()` checks. |

## G. Release Gates

### Gate 1: Map Surface Contract
- **Allowed**: `dnd_initative_tracker.py`, `assets/web/dmcontrol/index.html`.
- **Forbidden**: `spell_engine_primitives.py`.
- **Tests**: Fix `tests/test_dm_tactical_map_routes.py`.
- **Smoke**: Verify monster movement on `/dmcontrol`.

### Gate 2: Spell / Capability Contract
- **Goal**: First-load data never empty.
- **Rules**: ADR-0002 (Non-clobber) and ADR-0003 (Capability survival).
- **Tests**: `tests/test_lan_spellbook_contract_ui.py`.

### Gate 3: Combat Responsiveness
- **Goal**: Hot actions `< 5000ms`.
- **Evidence**: Trace report showing zero leaked tactical builds.

... (Additional Gates 4-6)
