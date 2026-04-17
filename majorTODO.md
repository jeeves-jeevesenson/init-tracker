# Master Web-First Migration and Execution Tracker

## 1. Title and purpose

This file is the long-lived master migration and execution tracker for moving `init-tracker` away from its current Tkinter/canvas-heavy desktop host toward a web-first architecture, with an eventual backend/runtime transition that is no longer tightly coupled to Python or Tk.

All future broad migration tasks should inspect the repo first, then consult and update this file before and after implementation.

`todo.md` remains the active feature/backlog board for smaller or non-platform slices. `majorTODO.md` owns the multi-phase migration plan, current-state snapshot, risks, decision history, and major-pass backlog for the platform rewrite.

When this file and older migration notes disagree, treat the code, tests, and this file as the source of truth. Older docs should be treated as historical context unless they are revalidated.

## 2. Snapshot of current repo reality

### Confirmed current state

- The app is still fundamentally a Python desktop host. `helper_script.py` defines `InitiativeTracker(tk.Tk)`, and `dnd_initative_tracker.py` subclasses it to add LAN/web/server logic.
- The codebase is still monolithic in the critical runtime paths:
  - `dnd_initative_tracker.py`: 40,896 lines
  - `helper_script.py`: 15,444 lines
  - `assets/web/lan/index.html`: 24,496 lines
  - `assets/web/dm/index.html`: 1,107 lines
- Tk, FastAPI routes, WebSocket handling, combat logic, persistence, and payload shaping are still mixed inside the Python host process.
- A real backend/service seam already exists for part of the combat/session model:
  - `combat_service.py` exposes a `CombatService` with an `RLock`.
  - `LanController` mounts DM API routes under `/api/dm/...` and a DM WebSocket at `/ws/dm`.
  - Service methods currently cover combat snapshots, start/end combat, next/prev turn, set turn, HP/temp HP/conditions, add/remove combatants, set/roll initiative, deep damage, healing, long-rest batch healing, and encounter population for player profiles and monster specs.
- Desktop and LAN code already route some mutations through service wrappers when the service is available:
  - `_next_turn_via_service()`
  - `_prev_turn_via_service()`
  - `_start_combat_via_service()`
  - `_set_turn_here_via_service()`
  - `_apply_damage_via_service()`
  - `_apply_heal_via_service()`
  - `_add_player_profile_combatants_via_service()`
  - `_add_monster_spec_combatants_via_service()`
- The project already has multiple browser surfaces, not just the player map:
  - `/` player LAN client
  - `/dm` DM console
  - `/new_character`
  - `/edit_character`
  - `/shop`
  - `/shop_admin`
- The web stack is still static-file based. There is no `package.json`, no frontend build system, and no separate frontend repository. The browser surfaces are hand-authored HTML/CSS/JS served by the Python process.
- Networking/live-sync is already substantial:
  - `/ws` player WebSocket
  - `/ws/dm` DM WebSocket
  - `/api/admin/login`, `/api/admin/refresh`, `/api/admin/sessions`
  - `/api/push/subscribe`
  - service worker registration in `assets/web/lan/index.html`
  - claim persistence with `client_id` / `claim_rev`
  - reconnect recovery using `state_request`, `grid_request`, and `terrain_request`
  - battle-log subscription and append flow
- Persistence is still local-file and YAML-heavy:
  - runtime content is seeded to a user data directory
  - player, spell, monster, item, and shop data are YAML-backed
  - atomic YAML writes already exist for multiple paths
  - session saves are JSON snapshots with `SESSION_SNAPSHOT_SCHEMA_VERSION = 2`
  - session snapshots preserve a canonical map payload while maintaining legacy compatibility projections
- A canonical map-domain seam already exists:
  - `map_state.py` defines `MapState`, `MapQueryAPI`, delta helpers, canonical-only layers, and legacy conversion helpers
  - `_capture_canonical_map_state()` and `_apply_canonical_map_state()` already bridge canonical map data with legacy/Tk state
- The current test surface is broad and useful:
  - `113` Python test files
  - focused migration-relevant tests exist for combat service, DM auth refresh, encounter population routes, session save/load, canonical map state, LAN reconnect recovery, LAN attack requests, LAN spell targeting, LAN reactions, condition icon payloads, token image overlays, character routes, shop routes, and shop admin/catalog APIs
- Current CI is narrower than the test surface:
  - `.github/workflows/lan-inline-script-check.yml` validates LAN inline script syntax and runs a Playwright smoke test
  - there is no broad default CI run of the full Python test suite

### Confirmed partial migrations / hybrid slices

- DM combat state has a real browser console and service-owned API surface, but the desktop host process still owns the runtime and many adjacent workflows.
- Encounter population for player profiles and monster specs is already partially migrated through `CombatService`, but summon/generated combatant paths remain outside that seam.
- `MapState` is a real canonical model, but map editing/rendering authority is still not web-primary; the Tk map window and legacy LAN fields still participate in canonical capture/projection.
- Character creation/editing and shop/admin flows are already browser-reachable and API-backed, but they still live inside the same Python host and write to the same local YAML/content model.
- The LAN player client is already feature-rich, including attacks, spell targeting, reactions, inventory, condition icons, token portraits, reconnect recovery, and notifications, but much of the authoritative action processing is still centralized inside `_lan_apply_action()` in `dnd_initative_tracker.py`.

### Confirmed desktop-owned or desktop-primary areas

- Full Tkinter widget tree and desktop menus
- Tk canvas rendering and map-window tooling
- many combat-adjacent workflows still initiated from desktop dialogs/widgets
- desktop-owned save/load entrypoints
- portions of summon, mount, reaction, and spell-specific adjudication that still depend on mixed tracker methods instead of a clean backend boundary

### Confirmed docs drift / contradictions

- `docs/dm-web-migration.md` is valuable context, but it is partially stale. It still lists initiative-roll support as a recommended next target even though `CombatService.roll_initiative()` and `POST /api/dm/combat/combatants/{cid}/initiative/roll` already exist in code.
- `README.md` still correctly describes the project as desktop-first, but it under-represents how much browser/API surface already exists.

### Future proposals or assumptions that are not true yet

- There is no standalone backend process independent of the Tk host today.
- There is no non-Python runtime today.
- There is no versioned contract package or strongly typed shared schema layer across frontend/backend today.
- There is no modular frontend build pipeline yet.

## 3. Migration principles

- No blind rewrite. Replace the current app by strangler slices that preserve behavior and keep the repo runnable.
- Authority before UI polish. The migration priority is moving state ownership and command handling behind explicit backend boundaries, not restyling screens.
- Web-first ownership, not web-themed desktop support. Once a feature slice is migrated, new work should target the web owner first.
- No new desktop-first features in migration slices unless they are strictly required for compatibility or safe handoff.
- Avoid dual-write state. One slice, one authoritative owner.
- Preserve current behavior with tests before changing internals, especially for combat resolution, claims, reconnect, save/load, and hidden-information rules.
- Keep rendering as a client concern. The backend should own combat/map state and adjudication, not canvas instructions or widget behavior.
- Prefer explicit contracts over implicit shared-object mutation. Web payloads should become versionable commands/events, not snapshots of Tk internals.
- Keep YAML, session, and LAN compatibility intact until a replacement path is validated and intentionally adopted.
- When a slice is migrated, remove or quarantine the old fallback path instead of leaving two peer owners indefinitely.
- Make the desktop a temporary adapter. It may remain useful as a host shell for a while, but it should trend toward consumer/launcher status rather than authoritative runtime status.
- Future tasks must update this file. Major implementation work that changes migration reality is not complete until `majorTODO.md` is updated honestly.

## 4. Target architecture

### Recommended end state

- **Frontend**
  - DM and player experiences become first-class web applications, split into maintainable modules instead of giant inline HTML documents.
  - Shared client helpers should cover contracts, validation, and state normalization.
  - A typed frontend codebase is recommended once contracts stabilize, but framework choice should follow the authority cleanup, not precede it.
- **Backend authority**
  - A standalone encounter/combat authority service owns encounter lifecycle, combat state, effect resolution, prompts/reactions, map-linked state, and persistence orchestration.
  - The backend contains no Tk widget logic and no browser rendering logic.
  - The service may remain Python during intermediate phases, but the boundary must be explicit enough that a later language swap is an implementation change, not another rewrite.
- **Contracts**
  - HTTP routes should handle coarse read/write workflows.
  - WebSocket traffic should carry versioned command and event payloads for live combat/play state.
  - Contracts should be explicit about hidden-information boundaries, pending prompts, claim identity, reconnect recovery, and event ordering.
- **Persistence**
  - Runtime encounter/session persistence should be versioned and independent from UI implementation details.
  - Content sources such as monster/spell/item/player YAML should be treated as importable content definitions during transition, not as the same thing as live runtime state.
  - Session snapshots should converge on a canonical encounter+map model with migrations from older versions.
- **Live sync**
  - The server should be authoritative for claims, turn state, combat results, and prompt lifecycle.
  - Clients can keep ephemeral UI state, but not authoritative combat decisions.
  - Prefer authoritative events plus targeted resync over increasingly complicated client-side repair logic.
- **Rendering**
  - Map rendering, token portraits, condition badges, overlays, and animations stay client-side.
  - The backend ships spatial state, adjudication results, and metadata, not drawing commands.
- **Testing**
  - Core engine/domain tests: deterministic combat, prompts, and map-domain behavior
  - Contract tests: HTTP + WebSocket payload schemas and fixture replays
  - Persistence tests: session migrations, YAML compatibility, snapshot round-trips
  - Browser tests: DM/player high-value smoke flows
  - Focused CI for migrated slices, not only inline-script checks

### Why this target fits this repo

- The repo already has real web surfaces and a partial backend seam, so the fastest safe path is to keep extracting authority out of the monolith instead of starting over.
- `CombatService` and `MapState` show that repo-grounded seams already exist.
- The current risk is not lack of functionality; it is mixed ownership. Explicit contracts and smaller runtime modules make AI-assisted iteration much safer.
- A later language transition will only be credible if combat/session authority is already separated from Tk and file-layout assumptions first.

## 5. Confirmed migration seam map

### `combat_service.py` and DM API routes

Confirmed leverage:
- Real service object with lock-protected mutation methods
- Real DM HTTP API and DM WebSocket
- Real desktop/LAN wrappers already routing some mutations through the service
- Focused validation in `tests/test_dm_combat_service.py` and `tests/test_encounter_population_routes.py`

Remaining coupling:
- The service still delegates to the tracker engine rather than owning a standalone domain model
- Many player/LAN adjudication flows still bypass a clean service command boundary
- Fallback direct-mutation paths still exist when the service is unavailable

### `MapState` / canonical map seam

Confirmed leverage:
- Canonical map model in `map_state.py`
- delta helpers and query API already exist
- session snapshot v2 carries canonical map state
- migration coverage exists in `tests/test_map_state_foundation.py` and `tests/test_session_save_load.py`

Remaining coupling:
- Tk map-window state still participates in canonical capture
- legacy LAN fields are still projected alongside canonical-only layers
- rendering/editor ownership is still not web-primary

### `LanController` transport seam

Confirmed leverage:
- One place owns HTTP route mounting, admin auth, WebSocket setup, claims, reconnect, and live broadcast plumbing
- `/ws` and `/ws/dm` already separate player and DM channels
- reconnect/claim recovery is already validated in `tests/test_lan_reconnect_recovery.py`

Remaining coupling:
- `_ACTION_MESSAGE_TYPES` is large and `_lan_apply_action()` remains a monolithic dispatcher for authoritative player actions
- transport, authorization, and domain logic are still too co-located

### Schema-backed browser content tools

Confirmed leverage:
- `/api/characters/schema` plus `assets/web/new_character/schema.json`
- browser create/edit flows in `assets/web/new_character/*` and `assets/web/edit_character/*`
- focused route coverage in `tests/test_edit_character_routes.py`

Remaining coupling:
- content editing still depends on local YAML writes in the Python host
- these tools do not yet imply a clean runtime encounter authority boundary

### Shop/admin browser slice

Confirmed leverage:
- `/shop`, `/shop_admin`, `/api/shop/...`, and revision-aware save/validate flows already exist
- tests exist for shell pages, catalog API behavior, and admin flows

Remaining coupling:
- still lives inside the desktop-hosted Python runtime
- not directly reusable as the combat authority layer, but useful proof that browser-first slices can land in this repo

### YAML cache and atomic-write seam

Confirmed leverage:
- player, spell, item, and shop content already use cache/refresh/index helpers and atomic writes
- tests exist for local YAML seeding/sync behavior in `tests/test_local_yaml_storage.py`

Remaining coupling:
- runtime authority is still tied to local filesystem assumptions
- live encounter state and source content are not fully separated conceptually

### Tightly coupled zones that remain high-risk

- `_lan_apply_action()` in `dnd_initative_tracker.py`
- Tk map window export/hydration behavior
- desktop session/menu flows that still act as primary user workflows
- summon/generated combatant creation paths outside the current service seam
- giant inline browser clients, especially `assets/web/lan/index.html`

## 6. Problem / risk inventory

### Concurrency and partial lock coverage

Why it matters: desktop UI paths and FastAPI/WebSocket paths can still touch the same in-memory tracker state, and only service-routed mutations benefit from `CombatService`'s `RLock`.

Mitigation: move all authoritative combat/session mutations behind one backend owner; remove per-slice direct-mutation fallbacks once migrated; add focused concurrency/reentrancy tests around nested turn/effect flows.

### Client/server state drift

Why it matters: the player client already maintains significant local UI state, while server snapshots mix canonical state, compatibility projections, claims, and repair messages.

Mitigation: define versioned command/result/event contracts; keep adjudication server-side; limit client-owned state to ephemeral UI workflow state.

### Desktop/web hybrid drift

Why it matters: leaving both Tk and web as writable peers for the same slice invites parity bugs and stale behavior.

Mitigation: declare a primary owner per migrated slice; stop adding new desktop-only behavior for migrated areas; delete or isolate old fallback paths once parity is validated.

### Persistence and save/load regressions

Why it matters: the repo combines YAML source content, player caches, shop catalog YAML, session JSON snapshots, and canonical map migration logic. Small mistakes can silently corrupt long-lived campaign data.

Mitigation: keep backward-compatible migrations; preserve existing snapshot and YAML tests; add golden fixtures before changing persistence boundaries; separate content definitions from live runtime state intentionally.

### Rendering ownership confusion

Why it matters: `MapState` is canonical enough to be useful, but the Tk map window still exports and hydrates runtime layers. That is a classic ownership trap.

Mitigation: treat map rendering as a client concern only; server owns canonical map state and queries; stop depending on Tk export paths as soon as the web map/editor can render the same state.

### Reconnect and claim behavior regressions

Why it matters: `client_id`, `claim_rev`, reconnect recovery, and state/grid/terrain repair already have subtle semantics. Breaking them damages real table usage quickly.

Mitigation: preserve these semantics with explicit contract fixtures and replay tests before refactoring transport or authority code.

### Partial migration trap

Why it matters: wrappers that fall back to direct mutation are useful short term, but deadly long term if both paths linger.

Mitigation: every major migration pass must name which fallback paths it deletes, not just which wrappers it adds.

### Security and hidden-information boundaries

Why it matters: the repo already contains hidden-AC-safe attack handling, admin tokens, DM routes, and player claims. A sloppy rewrite can leak hidden stats or over-authorize player actions.

Mitigation: keep adjudication and hidden information server-side; explicitly separate DM/admin commands from claimed-player commands; preserve targeted hidden-info tests.

### Reaction / interrupt complexity

Why it matters: shield, absorb elements, hellish rebuke, sentinel, interception, opportunity attacks, and pending reaction offers already form a primitive interrupt system.

Mitigation: move toward an explicit prompt/resolution model with request ids, eligibility, expiry, and outcomes; do not bury this logic in UI handlers during migration.

### Map/combat coupling

Why it matters: movement, hazards, auras, AoEs, boarding, ships, and start/end-turn hooks span combat and spatial state. Moving one side without the other creates brittle behavior.

Mitigation: keep `MapState` and `MapQueryAPI` as pure domain seams; make combat authority ask map-domain queries instead of reaching into UI/rendering state.

### Performance and payload size

Why it matters: the player LAN client is huge, snapshots are rich, and overlays/portraits/logs can grow payload and render cost quickly.

Mitigation: split web clients into modules, define payload budgets, prefer targeted deltas where helpful, and add browser smoke/perf checks for migrated map/combat slices.

### Test gap versus CI reality

Why it matters: the repo has strong focused tests, but CI currently validates only a thin slice by default.

Mitigation: promote migrated-slice tests into CI as authority moves; keep focused validation commands attached to each phase and backlog item.

### Premature framework or language churn

Why it matters: jumping to a new frontend stack or new backend language before authority boundaries are stable would create two simultaneous rewrites.

Mitigation: clean the domain/contract boundary first; only then introduce a new build/runtime stack if it materially helps the next phase.

## 7. Domain model direction

This section describes the canonical model the migration should move toward. It is a direction, not a claim that the repo already has this exact schema today.

### Encounter

- `encounter_id`, metadata, rules/options, content references, session metadata
- roster of combatants and non-combat map entities
- combat state and map state packaged together but not conflated
- explicit save/load versioning

### Combatant

- stable `combatant_id`
- `source_type`: player profile, monster spec, summon/generated, structure-linked, temporary/generated effect actor
- identity, allegiance, visibility, controller/claim metadata
- stats needed for adjudication, not UI-only projections
- optional link back to source content id or player profile slug

### Initiative / turn state

- initiative value, order, current combatant, round, turn index
- start-of-turn and end-of-turn effect checkpoints
- explicit turn history and reversal support if kept

### HP, temp HP, and resources

- current/max HP, temp HP, damage application results
- action / bonus action / reaction state
- attack-resource pools and feature/resource pools
- spell-slot and class-resource state where relevant to combat

### Conditions and effects

- explicit effect objects with source, type, remaining duration, stacking rules, cleanup groups, and mechanical modifiers
- condition display metadata kept separate from effect authority
- durable effect keys for prompts, badges, save hooks, and reaction triggers

### Reactions, interrupts, and prompts

- authoritative prompt queue or resolution stack
- prompt id, trigger, eligible actor(s), expiry, required input, allowed outcomes
- support for reaction offers, save prompts, damage follow-ups, initiative prompts, mount prompts, and other interruptible combat UX

### Map-linked state

- token position, facing, movement budget, occupancy, and controller context
- hazards, structures, elevation, boarding links, and aura-relevant metadata
- map-linked effect hooks should reference canonical map entities, not canvas ids

### Logs and history

- structured event history for replay/debugging
- human-readable battle log derived from events, not the only record
- enough structured history to support reconnect, debugging, and save/load trust

### Session snapshots

- versioned runtime encounter snapshot
- canonical map state embedded or referenced cleanly
- pending prompts and unresolved interrupts captured safely
- no dependence on Tk widget state

## 8. Migration phases

### Phase 1 — Finish backend authority seams for combat/session

Objective: make combat/session mutation authority explicit and backend-owned for the remaining core non-map slices.

Why it comes first: a web-first UI is only honest if the backend, not the Tk host, is the primary owner of combat decisions.

Scope:
- finish routing remaining core combat/session mutations through a backend authority seam
- formalize current DM and LAN command/result payloads for migrated slices
- reduce direct tracker mutation from web/player paths where the service boundary already exists

Dependencies:
- existing `CombatService`
- existing service wrappers in `dnd_initative_tracker.py`
- existing migration tests around DM combat service and encounter routes

Completion signals:
- migrated combat/session operations no longer rely on peer direct-mutation paths during normal service-backed operation
- service-backed tests cover the migrated commands
- this file and `todo.md` reflect the new ownership honestly

Main risks:
- concurrency regressions
- save/load compatibility drift
- hidden-info leakage from rushed contract changes

### Phase 2 — Make the DM web UI the primary operator surface for standard encounters

Objective: allow a DM to run the common encounter loop from the browser without depending on Tk-first widgets for normal combat operation.

Why it comes second: once authority is real, the highest-value UI shift is moving the DM workflow to the web.

Scope:
- encounter setup and population for common paths
- start/end combat, initiative, turn control, HP/temp HP, conditions, logs
- session save/load access from web-owned flows
- operational visibility for auth/session state and recovery

Dependencies:
- Phase 1 authority cleanup
- current DM console routes and WebSocket
- current session persistence seam

Completion signals:
- a standard encounter can be created, run, saved, and restored from the DM web surface without depending on Tk-first controls
- desktop remains available only as compatibility host for still-unmigrated slices

Main risks:
- parity gaps between Tk and web
- stale hybrid ownership if desktop workflows continue evolving in parallel

### Phase 3 — Move player combat command handling behind explicit backend contracts

Objective: extract player-facing combat adjudication out of the monolithic LAN action handler and into explicit backend command handlers/services.

Why it comes in this order: once the DM loop is web-primary, player commands become the next largest remaining authority leak.

Scope:
- player combat commands such as attack, spell targeting, reactions, end-turn, and adjacent combat prompts
- reconnect-safe prompt state
- command validation and hidden-information-safe result payloads

Dependencies:
- Phase 1 contract and authority work
- existing `/ws` claim/reconnect plumbing
- focused LAN combat tests

Completion signals:
- migrated player combat commands are adjudicated by explicit backend handlers rather than `_lan_apply_action()` branches
- reaction/prompt state is no longer implicitly owned by browser/Tk glue

Main risks:
- reaction/interrupt regressions
- reconnect behavior drift
- accidental behavior changes in complex spell/feature paths

### Phase 4 — Move map/tactical ownership to canonical web-first state and rendering

Objective: make the canonical map model the primary tactical authority and shift rendering/editor workflows to the web.

Why it comes after Phases 1-3: map/rendering is large, and it should consume already-stabilized encounter and player-command authority.

Scope:
- web map rendering
- web map editing/authoring
- hazard/structure/boarding flows through canonical state
- movement and tactical queries via `MapState` / `MapQueryAPI`

Dependencies:
- `MapState` seam and session snapshot compatibility
- player and DM authority cleanup from prior phases

Completion signals:
- canonical map state is no longer hydrated from Tk as a primary source for migrated slices
- web clients can render and manipulate the migrated map layers from canonical payloads

Main risks:
- map/combat coupling regressions
- performance/payload growth
- visual parity and usability gaps

### Phase 5 — Retire desktop authority and extract runtime/process boundaries

Objective: make the desktop host non-authoritative, then prepare or execute a backend/runtime transition behind stable contracts.

Why it comes last: language/runtime changes are only safe after the authority and contract seams are already stable.

Scope:
- desktop demotion or retirement for migrated slices
- standalone backend/service runtime
- persistence/runtime cleanup
- optional backend language transition

Dependencies:
- Phases 1-4
- stable contract and persistence layers

Completion signals:
- Tk is not the authority for migrated combat/session/map workflows
- backend runtime can evolve independently from desktop UI concerns
- a language transition, if desired, is a bounded swap rather than a rewrite

Main risks:
- operational deployment complexity
- migration fatigue leading to half-retired legacy paths

## 9. Major workstreams

### Workstream: Combat authority

Desired end state: one backend-owned combat/turn/effect authority surface shared by DM and player clients.

Current state: `CombatService` exists and owns a meaningful slice, but many player-command and prompt flows still resolve in the tracker monolith.

Next likely major pass: migrate player combat-adjudication commands and prompt state onto explicit backend handlers.

Blockers / dependencies: contract formalization, reaction-model cleanup, careful regression coverage.

### Workstream: Encounter creation and population

Desired end state: encounter assembly is API/service-owned regardless of whether units come from player profiles, monster specs, summons, or generated sources.

Current state: player-profile and monster-spec population have service seams; summon/generated creation does not.

Next likely major pass: migrate summon/generated combatant creation and any remaining desktop-only encounter population paths.

Blockers / dependencies: source-content references, generated-entity schema decisions, save/load compatibility.

### Workstream: Session persistence

Desired end state: versioned runtime encounter/session documents that are UI-agnostic and map-canonical.

Current state: session snapshots already exist and preserve canonical map state, but save/load entrypoints remain desktop-centric and runtime state is still closely tied to the tracker class.

Next likely major pass: expose session save/load through backend-owned APIs and shrink assumptions about Tk-owned state.

Blockers / dependencies: authoritative encounter schema, pending-prompt serialization decisions.

### Workstream: DM web console

Desired end state: the DM can run standard encounters from the browser without relying on desktop widgets for ordinary operation.

Current state: `/dm` already supports snapshot viewing, turn control, HP/temp HP, conditions, add/remove combatants, initiative, and auth refresh handling.

Next likely major pass: complete encounter/session operational parity for the browser path and make it the default operator workflow for migrated slices.

Blockers / dependencies: Phase 1 authority completeness, session save/load exposure, unresolved desktop-only encounter tools.

### Workstream: Player / LAN client

Desired end state: player interactions are web-first and backend-authoritative, with reconnect-safe prompts and minimal client-side adjudication.

Current state: the LAN client is feature-rich and battle-tested in focused areas, but `_lan_apply_action()` still owns too much domain logic.

Next likely major pass: pull attack/spell/reaction/end-turn command handling behind backend command handlers and shrink browser/Tk coupling.

Blockers / dependencies: prompt model, contract fixtures, hidden-information safeguards.

### Workstream: Map and rendering

Desired end state: canonical map state is authoritative and web renderers/editors consume it directly.

Current state: `MapState` is real, but Tk map tooling still participates in canonical capture/hydration and remains desktop-primary.

Next likely major pass: migrate one meaningful tactical slice end-to-end on canonical state without relying on Tk render/export ownership.

Blockers / dependencies: authority cleanup, payload/perf work, map-editor UX decisions.

### Workstream: Contracts, auth, and live sync

Desired end state: versioned HTTP/WebSocket commands/events with clean separation between DM/admin and player capabilities.

Current state: routes and WebSockets already exist, admin token refresh exists, claim recovery exists, but many contracts are implicit and embedded in large handlers or inline clients.

Next likely major pass: define and enforce explicit migrated command/result/event shapes for the combat authority slices.

Blockers / dependencies: agreement on canonical encounter/prompt model, removal of duplicate legacy payload semantics.

### Workstream: Test harness and CI

Desired end state: migrated slices have deterministic domain tests, contract fixtures, browser smoke, and CI coverage that matches the risk.

Current state: strong focused tests exist, but default CI coverage is thinner than the migration risk surface.

Next likely major pass: promote migrated slice tests into CI as part of each major authority move, starting with DM combat and player command contracts.

Blockers / dependencies: stable fixtures and clear migration boundaries.

### Workstream: Deprecation and operational safety

Desired end state: the repo can safely retire legacy owners without losing trusted save/load, auth, or table-side behavior.

Current state: desktop fallback paths, LAN trust-model assumptions, and local-file persistence still constrain how aggressively migration can proceed.

Next likely major pass: make deprecation criteria explicit per slice and attach them to backlog exit criteria.

Blockers / dependencies: parity proof, regression confidence, clear compatibility policy.

## 10. Ordered backlog

Owner labels are heuristic:
- `Initiative Smith`: broad vertical migration pass
- `Tracker Engineer`: seam hardening, compatibility, contracts, validation, or deprecation-heavy pass

1. **Complete backend authority routing for remaining core combat/session mutations**
   - Priority: `P0`
   - Rationale: this is the prerequisite for every honest web-first claim.
   - Likely scope owner: `Initiative Smith`
   - Dependencies: existing `CombatService`, service wrappers, current DM combat tests
   - Exit criteria: migrated core combat/session mutations no longer depend on peer direct-mutation ownership during normal service-backed operation; targeted service tests pass.

2. **Define explicit command/result/event contracts for migrated DM and player combat flows**
   - Priority: `P0`
   - Rationale: contract drift is the main blocker for safe AI-assisted extraction and later language/runtime change.
   - Likely scope owner: `Tracker Engineer`
   - Dependencies: item 1
   - Exit criteria: migrated commands/events are documented and fixture-backed; contract-sensitive tests cover reconnect, hidden-info handling, and prompt payloads.

3. **Make the DM web console capable of running a standard encounter loop without Tk-first controls**
   - Priority: `P1`
   - Rationale: the DM surface is the clearest place to make web-first ownership real.
   - Likely scope owner: `Initiative Smith`
   - Dependencies: items 1-2
   - Exit criteria: standard encounter setup, turn control, initiative management, HP/condition changes, and session save/load work from the browser path for migrated slices.

4. **Extract player combat adjudication out of `_lan_apply_action()` for attack, spell, end-turn, and manual override flows**
   - Priority: `P1`
   - Rationale: `_lan_apply_action()` is the largest remaining authority bottleneck in the player path.
   - Likely scope owner: `Initiative Smith`
   - Dependencies: items 1-2
   - Exit criteria: migrated player combat commands are handled by explicit backend command handlers/services; `_lan_apply_action()` is reduced to transport/adaptation for those commands.

5. **Introduce an explicit prompt / reaction / interrupt state model**
   - Priority: `P1`
   - Rationale: reaction-heavy combat is already present and too subtle to leave embedded in ad hoc transport handlers.
   - Likely scope owner: `Tracker Engineer`
   - Dependencies: items 2 and 4
   - Exit criteria: reaction offers and similar prompts have authoritative ids, lifecycle state, expiry semantics, and test coverage independent of UI code.

6. **Migrate summon/generated combatant creation onto the backend authority seam**
   - Priority: `P2`
   - Rationale: encounter population is only partially migrated today.
   - Likely scope owner: `Tracker Engineer`
   - Dependencies: items 1-2
   - Exit criteria: generated/summoned combatants use the same encounter authority model and persistence semantics as player-profile and monster-spec additions.

7. **Expose backend-owned session persistence APIs and shrink desktop-only save/load ownership**
   - Priority: `P2`
   - Rationale: web-primary DM operation is incomplete until persistence is also web-ownable.
   - Likely scope owner: `Tracker Engineer`
   - Dependencies: items 1-3
   - Exit criteria: migrated encounter/session save-load flows can be invoked from backend/web paths without depending on Tk dialogs as the authoritative entrypoint.

8. **Move tactical map authority and editing to canonical web-first flows**
   - Priority: `P2`
   - Rationale: the map is large and high-risk, but it cannot remain desktop-authoritative forever.
   - Likely scope owner: `Initiative Smith`
   - Dependencies: items 2, 4, 5, and 7
   - Exit criteria: at least one meaningful tactical slice is fully web-owned on `MapState`, with Tk no longer acting as the primary source for that slice.

9. **Modularize LAN and DM web clients into maintainable source modules**
   - Priority: `P3`
   - Rationale: `assets/web/lan/index.html` and inline browser logic are too large for sustained migration velocity.
   - Likely scope owner: `Tracker Engineer`
   - Dependencies: items 2-5
   - Exit criteria: migrated browser surfaces are split into smaller modules with shared client helpers; behavior remains regression-covered.

10. **Demote the desktop app to compatibility shell and prepare the standalone backend/runtime transition**
    - Priority: `P3`
    - Rationale: only after authority and web ownership are real does a runtime/language transition become an engineering task instead of a rewrite.
    - Likely scope owner: `Initiative Smith`
    - Dependencies: items 1-9
    - Exit criteria: Tk is no longer authoritative for migrated slices; the backend can be extracted or ported behind stable contracts.

## 11. Do not do this yet

- Do not rewrite the map renderer first. The map is too coupled and too large to be the opening move.
- Do not port the whole project to TypeScript or another language before finishing authority boundaries.
- Do not add new desktop-only features for slices that are supposed to be migrating to web ownership.
- Do not change combat/rules semantics just because infrastructure is moving.
- Do not leave long-lived dual owners for the same state slice.
- Do not treat giant snapshot payloads as the final contract design just because they already exist.
- Do not equate “served over HTTP” with “web-first architecture.” Backend ownership has to move too.
- Do not make the DM console a second rules engine.
- Do not break YAML or session compatibility casually during boundary cleanup.
- Do not create parallel planning docs that drift from this one unless there is a clearly narrower local purpose.

## 12. Progress tracking

- Overall status: `Hybrid migration in progress. Web surfaces are real, but Tk desktop still hosts the runtime and remains the primary owner for map and many adjacent workflows.`
- Completed major passes:
  - `CombatService` and `/api/dm/...` / `/ws/dm` exist for a meaningful combat/session slice.
  - desktop/LAN wrappers already route multiple core combat mutations through the service seam.
  - player-profile and monster-spec encounter population already have service-owned entry points.
  - canonical `MapState` plus session snapshot v2 and migration coverage already exist.
  - browser-backed character create/edit and shop/admin slices already exist.
  - LAN reconnect recovery, hidden-AC-safe attack resolution, spell targeting, reactions, token portraits, and condition-icon payloads all have focused coverage.
- In-progress pass: `None recorded in this tracker yet. Update this line when a major migration pass starts.`
- Next recommended pass: `Move player combat command adjudication and prompt authority behind explicit backend handlers/services.`
- Blocked items:
  - `No hard architecture blocker is confirmed yet, but framework/runtime choice should remain deferred until contracts stabilize.`
- Decisions made:
  - `majorTODO.md` is the master migration tracker for platform work.
  - authority cleanup comes before framework/language churn.
  - rendering remains client-side.
  - YAML/session compatibility is preserved until replacement paths are validated.
  - older migration docs are historical context when they drift from code/tests.
- Open questions:
  - `When should the backend leave the Tk process: after DM web-primary parity, or only after player command extraction too?`
  - `When is it worth introducing a typed frontend build pipeline for LAN/DM clients?`
  - `Which generated combatant paths should be migrated first after core encounter population: summons, mounts, echoes, ship-linked entities, or something else?`
  - `What is the minimum acceptable web map/editor parity before desktop map ownership can be demoted?`

## 13. Update protocol for future agents

1. Inspect the repo first. Do not update this file from memory or older notes alone.
2. Update the current-state snapshot before adding new plans if repo reality changed.
3. Mark completed versus partial honestly. “Partially migrated” is a valid state.
4. Do not mark a phase or backlog item done unless the code and relevant focused validation support that claim.
5. Update backlog priorities when dependencies change.
6. Preserve decision history. Add decisions instead of silently rewriting why the order changed.
7. Add newly discovered risks to the risk inventory instead of hiding them inside handoff prose.
8. When old docs drift from code/tests, note that here so future tasks do not re-import stale assumptions.
9. Keep this file concise enough to scan, but detailed enough that a future major pass can start from it without a separate handoff document.
10. After each substantial migration pass, update:
   - current-state snapshot
   - completed major passes
   - in-progress pass / next recommended pass
   - affected backlog items
   - any new decisions, blockers, or risks

## 14. Recommended immediate next pass

### Service-own player combat command adjudication and prompt state

This should be the next major implementation pass.

Why this is next:
- the repo already has a real DM/service seam
- the largest remaining authority leak is player combat logic embedded in `_lan_apply_action()`
- this pass moves the migration forward without forcing an early map rewrite or premature language/framework change

Recommended scope:
- migrate the combat-adjudicating player commands first, especially:
  - `attack_request`
  - `spell_target_request`
  - `reaction_response`
  - `end_turn`
  - closely related manual combat overrides and result payloads
- introduce explicit backend-owned pending prompt / reaction state for those commands
- keep transport/reconnect plumbing in place, but reduce `_lan_apply_action()` to validation/adaptation for migrated commands

Recommended validation:
- `tests/test_lan_attack_request.py`
- `tests/test_lan_spell_target_request.py`
- `tests/test_lan_reaction_prompts.py`
- `tests/test_lan_reconnect_recovery.py`
- `tests/test_dm_combat_service.py`
- any focused browser smoke needed if LAN payloads change

If this pass lands cleanly, the repo will have a much more credible authority boundary for the eventual web-first runtime and later backend/language transition.
