# Master Web-First Migration and Execution Tracker

## 1. Title and purpose

This file is the long-lived master migration and execution tracker for moving `init-tracker` away from its current Tkinter/canvas-heavy desktop host toward a web-first architecture, with an eventual backend/runtime transition that is no longer tightly coupled to Python or Tk.

All future broad migration tasks should inspect the repo first, then consult and update this file before and after implementation.

`todo.md` remains the active feature/backlog board for smaller or non-platform slices. `majorTODO.md` owns the multi-phase migration plan, current-state snapshot, risks, decision history, and major-pass backlog for the platform rewrite.

When this file and older migration notes disagree, treat the code, tests, and this file as the source of truth. Older docs should be treated as historical context unless they are revalidated.

## 2. Snapshot of current repo reality

### Confirmed current state

- The app can now launch in two host modes. The desktop mode is the historical Python/Tk host (`helper_script.py` defines `InitiativeTracker(tk.Tk)`, and `dnd_initative_tracker.py` subclasses it to add LAN/web/server logic). The new headless mode is reached via `serve_headless.py` (or by setting `INIT_TRACKER_HEADLESS=1` before importing the tracker), in which `tk_compat.HeadlessRoot` substitutes for `tk.Tk` and provides a real `after()`/`mainloop()` scheduler. Backend authority and the same `InitiativeTracker` class are reused in both modes; only the host shell differs.
- The codebase is still monolithic in the critical runtime paths:
  - `dnd_initative_tracker.py`: 43,324 lines
  - `helper_script.py`: 15,505 lines
  - `assets/web/lan/index.html`: 24,635 lines
  - `assets/web/dm/index.html`: 4,817 lines
- Tk, FastAPI routes, WebSocket handling, combat logic, persistence, and payload shaping are still mixed inside the Python host process.
- A real backend/service seam already exists for part of the combat/session model:
  - `combat_service.py` exposes a `CombatService` with an `RLock`.
  - `LanController` mounts DM API routes under `/api/dm/...` and a DM WebSocket at `/ws/dm`.
  - Service methods currently cover combat snapshots, start/end combat, next/prev turn, set turn, HP/temp HP/conditions, add/remove combatants, set/roll initiative, deep damage, healing, long-rest batch healing, and encounter population for player profiles and monster specs.
- A second backend seam now exists for player-originated combat/resource commands:
  - `player_command_service.py` exposes `PlayerCommandService` (envelope: gates, validation, toasts, service-vs-fallback dispatch) and `PromptState` (accessor for pending reaction/prompt state).
- `_lan_apply_action()` delegates `attack_request`, `spell_target_request`, `reaction_response`, `end_turn`, `move`, `cycle_movement_mode`, `perform_action`, `aoe_move`, `aoe_remove`, `manual_override_hp`, `manual_override_spell_slot`, `manual_override_resource_pool`, `reaction_prefs_update`, `mount_request`, `mount_response`, `dismount`, `dash`, `use_action`, `use_bonus_action`, `stand_up`, `reset_turn`, `lay_on_hands_use`, `inventory_adjust_consumable`, `use_consumable`, `second_wind_use`, `action_surge_use`, `star_advantage_use`, `monk_patient_defense`, `monk_step_of_wind`, `monk_elemental_attunement`, `monk_elemental_burst`, `monk_uncanny_metabolism`, `echo_summon`, `echo_swap`, `dismiss_summons`, `dismiss_persistent_summon`, `reappear_persistent_summon`, `assign_pre_summon`, `echo_tether_response`, `initiative_roll`, `hellish_rebuke_resolve`, `set_color`, `set_facing`, `set_auras_enabled`, and `reset_player_characters` through the service; movement/action, AoE manipulation, turn-local/mobility-lite, fighter/monk resource-actions, summon/echo specialty, initiative/reaction specialty, and utility/admin commands now flow through family dispatcher branches keyed by `MOVEMENT_ACTION_COMMAND_TYPES`, `AOE_MANIPULATION_COMMAND_TYPES`, `TURN_LOCAL_COMMAND_TYPES`, `FIGHTER_MONK_RESOURCE_ACTION_TYPES`, `SUMMON_ECHO_SPECIALTY_COMMAND_TYPES`, `INITIATIVE_REACTION_SPECIALTY_COMMAND_TYPES`, and `UTILITY_ADMIN_COMMAND_TYPES`, and the former ~2600 lines of inline combat adjudication now live in named `InitiativeTracker._adjudicate_attack_request` / `_adjudicate_spell_target_request` methods plus service-owned trigger-specific `reaction_response` handlers.
  - `player_command_contracts.py` now defines versioned request/result/event/prompt builders for the migrated player command slice, including attack/spell/resource request contracts, result payload finalizers, reaction-offer events, prompt snapshots, and structured resume dispatch objects.
  - migrated prompt state is now canonically stored in tracker-owned `_pending_prompts` records with stable prompt ids, lifecycle metadata, response metadata, and resume metadata; legacy `_pending_*` prompt/reaction dicts remain as compatibility projections derived from that canonical store.
  - reconnect and save/load now preserve migrated pending prompts explicitly (`you.pending_prompts` / `you.pending_prompt` on reconnect payloads and `combat.pending_prompts` in session snapshots).
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
  - `/dm` DM console dashboard
  - `/dm/map` dedicated DM map workspace
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
  - DM-owned session save/load is now also web-operable via authenticated routes (`GET /api/dm/sessions`, `POST /api/dm/sessions/save`, `POST /api/dm/sessions/load`, `POST /api/dm/sessions/quick-save`, `POST /api/dm/sessions/quick-load`) that reuse `_save_session_to_path` / `_load_session_from_path` / `_session_quicksave_path`; Tk file-dialog flows remain as a compatibility entrypoint, not the only operational path.
  - session restore now applies combat/map/prompt/log state through a backend-owned `_apply_session_snapshot_authoritative_state()` helper plus state-only `_remove_combatants_from_runtime_state()` cleanup; Tk map/log/table refresh is a best-effort compatibility adapter layered after canonical restore rather than the owner of restore semantics.
- A canonical map-domain seam already exists:
  - `map_state.py` defines `MapState`, `MapQueryAPI`, delta helpers, canonical-only layers, and legacy conversion helpers
  - `_capture_canonical_map_state()` and `_apply_canonical_map_state()` already bridge canonical map data with legacy/Tk state
- The current test surface is broad and useful:
  - `113` Python test files
  - focused migration-relevant tests exist for combat service, DM auth refresh, encounter population routes, session save/load, canonical map state, LAN reconnect recovery, LAN attack requests, LAN spell targeting, LAN reactions, condition icon payloads, token image overlays, character routes, shop routes, and shop admin/catalog APIs
- Current CI is narrower than the test surface:
  - `.github/workflows/lan-inline-script-check.yml` validates LAN inline script syntax and runs a Playwright smoke test
  - there is no broad default CI run of the full Python test suite
- Install/update/launch flow has a new safety baseline (2026-04-18 pass):
  - `update_checker.py` now points at the live repo (`jeeves-jeevesenson/init-tracker`) and only offers in-app script execution for managed installs whose git `origin` matches that repository.
  - Linux/Windows updater scripts now explicitly verify repo identity and refuse to mutate installs that point at a different remote, instead of pulling whichever repo happened to be configured.
  - quick-install/update paths now use explicit `origin/main` fast-forward updates, and managed launchers now expose headless/browser-first entrypoints alongside desktop compatibility launchers.

### Confirmed partial migrations / hybrid slices

- DM combat state has a real browser console and service-owned API surface, and `/dm` can now run the ordinary encounter loop plus routine tactical play and the current advanced ship/map prep slices for bug testing (load/resume or start blank session, populate from player profiles or monster specs, start/end combat, operate turns, manage initiative/HP/temp HP/conditions, save/restore, place/move/facing-manage combatants, place templates/ships with ship placement preview, manage boarding links, reorder background layers, execute ship engagement maneuver/fire/ram flows, and actively run enemy turns via monster attack resolution/manual damage, `perform_action`, and targeted spell requests) without dropping back to Tk-first controls for those high-value workflows. The desktop host process still owns the runtime and the remaining advanced authoring/polish map workflows plus long-tail monster prompt/cast UX parity.
- Encounter population for player profiles and monster specs is already partially migrated through `CombatService`, but summon/generated combatant paths remain outside that seam.
- `MapState` is a real canonical model, but map editing/rendering authority is still not web-primary; the Tk map window and legacy LAN fields still participate in canonical capture/projection.
- Character creation/editing and shop/admin flows are already browser-reachable and API-backed, but they still live inside the same Python host and write to the same local YAML/content model.
- The LAN player client is already feature-rich, including attacks, spell targeting, reactions, inventory, condition icons, token portraits, reconnect recovery, and notifications. Authoritative action processing for combat plus the migrated movement/action, AoE manipulation, wild-shape, resource/consumable, turn-local, fighter/monk action, spell-launch, bard/glamour specialty, summon/echo specialty, initiative/reaction specialty, and utility/admin slices (`attack_request`, `spell_target_request`, `reaction_response`, `end_turn`, `move`, `cycle_movement_mode`, `perform_action`, `aoe_move`, `aoe_remove`, `wild_shape_apply`, `wild_shape_pool_set_current`, `wild_shape_revert`, `wild_shape_regain_use`, `wild_shape_regain_spell`, `wild_shape_set_known`, `manual_override_hp`, `manual_override_spell_slot`, `manual_override_resource_pool`, `reaction_prefs_update`, `mount_request`, `mount_response`, `dismount`, `dash`, `use_action`, `use_bonus_action`, `stand_up`, `reset_turn`, `lay_on_hands_use`, `inventory_adjust_consumable`, `use_consumable`, `second_wind_use`, `action_surge_use`, `star_advantage_use`, `monk_patient_defense`, `monk_step_of_wind`, `monk_elemental_attunement`, `monk_elemental_burst`, `monk_uncanny_metabolism`, `cast_spell`, `cast_aoe`, `command_resolve`, `bardic_inspiration_grant`, `bardic_inspiration_use`, `mantle_of_inspiration`, `beguiling_magic_restore`, `beguiling_magic_use`, `echo_summon`, `echo_swap`, `dismiss_summons`, `dismiss_persistent_summon`, `reappear_persistent_summon`, `assign_pre_summon`, `echo_tether_response`, `initiative_roll`, `hellish_rebuke_resolve`, `set_color`, `set_facing`, `set_auras_enabled`, `reset_player_characters`) now enters through `PlayerCommandService`; movement/action, AoE manipulation, wild-shape, turn-local/mobility-lite, fighter/monk resource-actions, spell-launch, bard/glamour specialty, summon/echo specialty, initiative/reaction specialty, and utility/admin routes dispatch through family branches in `_lan_apply_action()`, and the deep combat/cast/specialty rules logic lives in `_adjudicate_*` / `_handle_*_request` tracker methods. The older `cast_aoe_adjust` reference appears stale on this branch; no live handler or test coverage for it currently exists.
- Reaction resume for the migrated slice is no longer transport-recursive: shield, absorb elements, and interception now return structured resume dispatches that `PlayerCommandService` executes directly instead of recursively re-entering `_lan_apply_action(resume_msg)`.

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
- There is no full shared typed schema layer across frontend/backend yet. The migrated player combat slice now has a versioned contract module (`player_command_contracts.py`), but the rest of the repo still uses mostly implicit payload shaping.
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
- `_ACTION_MESSAGE_TYPES` is still large. `_lan_apply_action()` now routes combat-adjudicating plus migrated movement/action, AoE manipulation, wild-shape, resource/consumable, turn-local, fighter/monk, spell-launch, bard/glamour specialty, summon/echo specialty, initiative/reaction specialty, and utility/admin slices (`attack_request`, `spell_target_request`, `reaction_response`, `end_turn`, `move`, `cycle_movement_mode`, `perform_action`, `aoe_move`, `aoe_remove`, `wild_shape_apply`, `wild_shape_pool_set_current`, `wild_shape_revert`, `wild_shape_regain_use`, `wild_shape_regain_spell`, `wild_shape_set_known`, `manual_override_hp`, `manual_override_spell_slot`, `manual_override_resource_pool`, `reaction_prefs_update`, `mount_request`, `mount_response`, `dismount`, `dash`, `use_action`, `use_bonus_action`, `stand_up`, `reset_turn`, `lay_on_hands_use`, `inventory_adjust_consumable`, `use_consumable`, `second_wind_use`, `action_surge_use`, `star_advantage_use`, `monk_patient_defense`, `monk_step_of_wind`, `monk_elemental_attunement`, `monk_elemental_burst`, `monk_uncanny_metabolism`, `cast_spell`, `cast_aoe`, `command_resolve`, `bardic_inspiration_grant`, `bardic_inspiration_use`, `mantle_of_inspiration`, `beguiling_magic_restore`, `beguiling_magic_use`, `echo_summon`, `echo_swap`, `dismiss_summons`, `dismiss_persistent_summon`, `reappear_persistent_summon`, `assign_pre_summon`, `echo_tether_response`, `initiative_roll`, `hellish_rebuke_resolve`, `set_color`, `set_facing`, `set_auras_enabled`, `reset_player_characters`) through `PlayerCommandService`.
- `_lan_apply_action()` still mixes shared claim/admin/turn gating with branch routing, and several non-migrated command paths remain outside family dispatch.

### `PlayerCommandService` player-command seam

Confirmed leverage:
- `player_command_service.py` owns envelope logic for migrated player combat plus movement/action, AoE manipulation, wild-shape, resource/consumable, turn-local, self-state, spell-launch, bard/glamour specialty, summon/echo specialty, and initiative/reaction specialty commands: turn/claim validation, pending-reaction attacker gate, reactor-cid match, move/mobility/action-economy orchestration, AoE manipulation request dispatch, wild-shape/YAML/resource orchestration, manual override/resource/inventory orchestration, spell-launch/specialty dispatch, and `CombatService` manual-override dispatch/fallback mutation.
- `player_command_contracts.py` owns the explicit request/result/event/prompt builders for the migrated player command slice.
- `PromptState` now treats `_pending_prompts` as the canonical prompt store for the migrated slice and projects legacy `_pending_*` reaction dictionaries from that state for compatibility.
- deep adjudication lives in named `InitiativeTracker._adjudicate_attack_request` / `_adjudicate_spell_target_request` methods, while trigger-specific `reaction_response` resolution now lives in `PlayerCommandService`.
- migrated reconnect and session save/load now preserve pending prompt state explicitly via prompt snapshots and `combat.pending_prompts`.
- service-dispatched resume replaced transport recursion for the migrated reaction resume path.
- `_lan_apply_action()` now routes movement/action, AoE manipulation, wild-shape, turn-local/mobility-lite, spell-launch, bard/glamour specialty, summon/echo specialty, initiative/reaction specialty, and utility/admin families through `PlayerCommandService` family dispatchers instead of keeping those branches inline.
- the `attack_request` / `spell_target_request` prompt-claim override gate now delegates from `_lan_apply_action()` to `PlayerCommandService.allow_prompt_claim_override(...)`, reducing command-family prompt leakage in the shared claim gate.

Remaining coupling:
- prompt/reaction storage still lives on `InitiativeTracker`, and legacy `_pending_*` dictionaries still exist as compatibility projections for older save/load and helper code.
- the canonical reaction-offer creation/emission boundary now lives on `PlayerCommandService` (`create_reaction_offer`, `maybe_offer_absorb_elements`, `maybe_offer_hellish_rebuke`, `maybe_offer_interception`), but compatibility wrappers (`InitiativeTracker._create_reaction_offer` / `_maybe_offer_*`) still exist and trigger qualification still depends on tracker combat/map helpers.
- hellish rebuke still uses a dedicated follow-up `hellish_rebuke_resolve` command path; it now dispatches through `PlayerCommandService` and reads canonical prompt resolution metadata, but the broader prompt family is not yet fully collapsed into one generic handler.
- the adjudicate methods remain on `InitiativeTracker`, so they still bind to other tracker concerns (Tk, map helpers, YAML caches). Extracting them fully belongs to a later pass once prompt creation and deeper adjudication ownership are moved off tracker helpers.

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

Why it matters: shield, absorb elements, hellish rebuke, sentinel, interception, opportunity attacks, and pending reaction offers already form a primitive interrupt system. Lifecycle (offer → resolve → resume) is now explicit for the migrated reaction slice via canonical prompt records plus service-dispatched resume, but broader prompt-like flows still mix canonical prompt records with legacy projections and tracker-local helpers.

Mitigation: keep extending the canonical prompt/resolution model with request ids, eligibility, expiry, and outcomes; reduce the remaining legacy prompt projections; and converge the still-special-case follow-up prompt flows on the same service-owned lifecycle.

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

Current reality (2026-04-18):
- the ordinary encounter loop now satisfies this for browser-first bug testing; remaining gaps are deeper DM/tactical tools rather than baseline encounter operation.

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

Current state: `CombatService` exists and owns a meaningful slice, and the migrated player combat command slice now has explicit contracts plus canonical prompt records. Many other player-command and prompt flows still resolve in the tracker monolith.

Next likely major pass: extend backend authority past the migrated combat slice, starting with the next `_lan_apply_action()` player-command families and the remaining tracker-owned prompt creation entry points.

Blockers / dependencies: contract formalization, reaction-model cleanup, careful regression coverage.

### Workstream: Encounter creation and population

Desired end state: encounter assembly is API/service-owned regardless of whether units come from player profiles, monster specs, summons, or generated sources.

Current state: player-profile and monster-spec population have service seams; summon/generated creation does not.

Next likely major pass: migrate summon/generated combatant creation and any remaining desktop-only encounter population paths.

Blockers / dependencies: source-content references, generated-entity schema decisions, save/load compatibility.

### Workstream: Session persistence

Desired end state: versioned runtime encounter/session documents that are UI-agnostic and map-canonical.

Current state: session snapshots already exist and preserve canonical map state; the migrated player-command slice now also persists canonical pending prompt records through `combat.pending_prompts` while projecting legacy prompt dictionaries for compatibility. Web-owned DM session save/load/quick-save/quick-load/list routes now reuse the same `_save_session_to_path` / `_load_session_from_path` / `_session_quicksave_path` helpers, so backend-initiated persistence is possible without invoking Tk file dialogs. Restore semantics now run through `_apply_session_snapshot_authoritative_state()` and state-only cleanup in `_remove_combatants_from_runtime_state()`, while `_open_map_mode()` / `_load_history_into_log()` / `_rebuild_table()` remain optional Tk compatibility refreshes layered on top. Focused fixture-style tests now lock the schema-v2 snapshot projection and reconnect prompt payload shapes the web slice depends on.

Next likely major pass: no immediate persistence-seam follow-up is required for the ordinary DM encounter loop; revisit session-safety/UX improvements only if browser bug testing shows operator confusion around dirty-state, quick-save, or restore visibility.

Blockers / dependencies: authoritative encounter schema, remaining DM web encounter-loop gaps, persistence UX decisions.

### Workstream: DM web console

Desired end state: the DM can run standard encounters from the browser without relying on desktop widgets for ordinary operation.

<<<<<<< HEAD
Current state: the DM web surface now splits into `/dm` (dashboard-oriented encounter/session controls) and `/dm/map` (dedicated map workspace). `/dm` supports snapshot viewing, turn control, HP/temp HP, conditions, add/remove combatants, set/roll initiative, auth refresh handling, session save/load/quick-save/quick-load/list, browser-triggered new blank session, and browser encounter population for the common player-profile and monster-spec paths via authenticated `/api/dm/encounter/*` routes. `/dm/map` reuses the same backend snapshot/actions and DM tactical cards but promotes map setup, tactical battlefield controls, and monster-turn controls into a full-size central operator lane so the DM can run map-first encounters in practical browser space. Browser-owned map setup includes creating a blank map and setting tactical grid dimensions through authenticated `/api/dm/map/new` and `/api/dm/map/settings` routes, so ordinary DM map creation no longer depends on Tk map-size prompts. The DM can place/reposition tokens, move them using the existing rules-aware path, update facing, paint/clear obstacle and rough-terrain cells, place/remove tactical hazards from preset-backed payloads, place/remove features, place/move/remove structures, set elevation cells, place/update/remove/reorder background layers from `/assets`, place/move/remove AoE effects, and toggle aura overlays through authenticated `/api/dm/map/*` routes that reuse tracker-owned map helpers plus the existing LAN/DM broadcast path. Advanced browser tactical authoring now also covers structure-template placement, ship-blueprint listing/placement preview/instantiation, boarding-link create/status/remove, and ship engagement summary/maneuver/fire/ram flows without Tk controls. Browser monster-turn controls now cover enemy actor selection plus authenticated monster attack option loading, attack resolution/manual damage apply, `perform_action`, and targeted spell-target requests through `/api/dm/combat/*` routes while preserving existing backend adjudication/state broadcast patterns. After a web-triggered load, the tracker restores canonical combat/map/prompt/log state without depending on Tk widget mutation as the authoritative path, then broadcasts refreshed state to LAN clients and pushes a refreshed DM snapshot to connected DM WebSocket clients. Focused reconnect/session contract fixtures now guard the prompt/map/claim payloads this slice depends on.
=======
Current state: `/dm` now supports snapshot viewing, turn control, HP/temp HP, conditions, add/remove combatants, set/roll initiative, auth refresh handling, session save/load/quick-save/quick-load/list, browser-triggered new blank session, browser encounter population for the common player-profile and monster-spec paths via authenticated `/api/dm/encounter/*` routes, and a tactical map card driven by combined DM snapshots that include `tactical_map`. A map-first companion route `/dm/map` serves the same DM HTML shell with a `body.map-mode` CSS class that hides the encounter/session setup cards (tagged via `data-dm-card="setup"`), widens the tactical canvas, and exposes a topbar toggle between the full console and the map view; the DM HTTP snapshot poll now defers to the DM WebSocket whenever it is connected so live play drops a redundant snapshot serialization per tick. Browser-owned map setup now includes creating a blank map and setting tactical grid dimensions through authenticated `/api/dm/map/new` and `/api/dm/map/settings` routes, so ordinary DM map creation no longer depends on Tk map-size prompts. The DM can place/reposition tokens, move them using the existing rules-aware path, update facing, paint/clear obstacle and rough-terrain cells, place/remove tactical hazards from preset-backed payloads, place/remove features, place/move/remove structures, set elevation cells, place/update/remove/reorder background layers from `/assets`, place/move/remove AoE effects, and toggle aura overlays through authenticated `/api/dm/map/*` routes that reuse tracker-owned map helpers plus the existing LAN/DM broadcast path. Advanced browser tactical authoring now also covers structure-template placement, ship-blueprint listing/placement preview/instantiation, boarding-link create/status/remove, and ship engagement summary/maneuver/fire/ram flows without Tk controls. Browser monster-turn controls now cover enemy actor selection plus authenticated monster attack option loading, attack resolution/manual damage apply, `perform_action`, and targeted spell-target requests through `/api/dm/combat/*` routes while preserving existing backend adjudication/state broadcast patterns. After a web-triggered load, the tracker restores canonical combat/map/prompt/log state without depending on Tk widget mutation as the authoritative path, then broadcasts refreshed state to LAN clients and pushes a refreshed DM snapshot to connected DM WebSocket clients. Focused reconnect/session contract fixtures now guard the prompt/map/claim payloads this slice depends on.
>>>>>>> 1ec22f4 (Stabilize DM map workspace route and live refresh behavior)

Next likely major pass: close the remaining desktop-primary tactical **authoring/polish** gaps (template/blueprint authoring/editing and higher-fidelity overlay/debug tooling) only as needed, then pivot primary migration effort to Tk-optional/headless host extraction.

Blockers / dependencies: Phase 1 authority completeness (done for migrated slices), unresolved desktop-only encounter authoring tools, pending encounter schema decisions.

### Workstream: Player / LAN client

Desired end state: player interactions are web-first and backend-authoritative, with reconnect-safe prompts and minimal client-side adjudication.

Current state: the LAN client is feature-rich and battle-tested in focused areas. The combat-adjudicating player command slice now has explicit contracts, a canonical prompt model, reconnect-safe prompt snapshots, and service-dispatched resume handling, and the adjacent movement/action, AoE manipulation, wild-shape, turn-local/mobility-lite, fighter/monk resource-action, spell-launch (`cast_spell` / `cast_aoe`), bard/glamour specialty, summon/echo specialty, initiative/reaction specialty (`initiative_roll` / `hellish_rebuke_resolve`), and utility/admin (`set_color` / `set_facing` / `set_auras_enabled` / `reset_player_characters`) families now dispatch through `PlayerCommandService` via shared family routers. The old `cast_aoe_adjust` TODO reference is stale on this branch.

Next likely major pass: continue shrinking `_lan_apply_action()` by extracting the next non-migrated inline command branches and remaining tracker-owned prompt creation entry points behind explicit service seams.

Blockers / dependencies: prompt model, contract fixtures, hidden-information safeguards.

### Workstream: Map and rendering

Desired end state: canonical map state is authoritative and web renderers/editors consume it directly.

Current state: `MapState` is real, and tactical DM browser control now covers ordinary map bootstrap plus common encounter prep and live-play battlefield effects across both `/dm` and the dedicated `/dm/map` workspace: combined DM snapshots carry canonical tactical state to the DM web surface, and blank-map creation, grid-dimension setup, token placement/movement/facing, obstacle + rough-terrain cell edits, hazard placement/removal, feature placement/removal, structure placement/move/removal, elevation edits, background-layer updates/reordering, AoE placement/move/removal, aura-overlay toggles, structure-template placement, ship-blueprint placement preview/instantiation, boarding-link create/status/remove, and ship engagement maneuver/fire/ram all run through backend-owned helpers without Tk controls. Tk map tooling still participates in canonical capture/hydration and remains desktop-primary for advanced authoring/polish workflows (template/blueprint authoring/editing and higher-fidelity tactical overlays/debug tooling). **2026-04-21 stabilization/perf pass:** DM/LAN live broadcast now reuses the LAN-built tactical snapshot for DM WS payloads (instead of recomputing a second tactical snapshot), map-focused DM helpers now broadcast tactical updates with `include_static=False`, and DM session-load flow no longer performs a redundant second DM WS push after the LAN broadcast.

Next likely major pass: if parity follow-up is still needed, migrate one remaining advanced authoring/polish slice; otherwise pivot map/runtime ownership work toward Tk-optional host extraction while preserving canonical map-state authority.

Blockers / dependencies: authority cleanup, payload/perf work, map-editor UX decisions.

### Workstream: Contracts, auth, and live sync

Desired end state: versioned HTTP/WebSocket commands/events with clean separation between DM/admin and player capabilities.

Current state: routes and WebSockets already exist, admin token refresh exists, claim recovery exists, and the migrated player combat slice now has explicit contract builders and prompt snapshots. Many other contracts remain implicit and embedded in large handlers or inline clients.

Next likely major pass: extend explicit command/result/event contracts beyond the migrated player combat slice and converge more reconnect/prompt payloads on the same schema.

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

Pass-shape labels are heuristic:
- `Broad migration pass`: vertical multi-file migration across the active runtime path
- `Seam hardening pass`: contracts, compatibility, validation, persistence, or deprecation-heavy work

1. **Complete backend authority routing for remaining core combat/session mutations**
   - Priority: `P0`
   - Rationale: this is the prerequisite for every honest web-first claim.
   - Likely pass shape: `Broad migration pass`
   - Dependencies: existing `CombatService`, service wrappers, current DM combat tests
   - Exit criteria: migrated core combat/session mutations no longer depend on peer direct-mutation ownership during normal service-backed operation; targeted service tests pass.

2. **Extend explicit command/result/event contracts across the remaining DM and player combat flows**
   - Priority: `P0`
   - Rationale: contract drift is the main blocker for safe AI-assisted extraction and later language/runtime change.
   - Likely pass shape: `Seam hardening pass`
   - Dependencies: item 1
   - Exit criteria: migrated commands/events are documented and fixture-backed beyond the already-migrated player combat slice; contract-sensitive tests cover reconnect, hidden-info handling, and prompt payloads.

3. **Make the DM web console capable of running a standard encounter loop without Tk-first controls**
   - Priority: `P1`
   - Rationale: the DM surface is the clearest place to make web-first ownership real.
   - Likely pass shape: `Broad migration pass`
   - Dependencies: items 1-2
   - Exit criteria: standard encounter setup, turn control, initiative management, HP/condition changes, and session save/load work from the browser path for migrated slices.
   - Status (2026-04-18): **Ordinary browser encounter-loop parity plus routine tactical token control landed.** `/dm` can now load/quick-load or start a blank session, populate encounters from YAML-backed player profiles and monster specs, start/end combat, operate turns, set/roll initiative, adjust HP/temp HP/conditions, save/restore sessions, place/move/re-face combatants on the tactical map, and run bounded enemy turns (monster attack resolve/apply-damage, `perform_action`, targeted `spell-target`) without depending on Tk-first controls for routine play. Remaining DM browser work is advanced tactical authoring/polish plus long-tail monster prompt/cast parity, not the baseline encounter loop.

4. **Extract the next player-command families out of `_lan_apply_action()` without reopening the migrated combat command boundary**
   - Priority: `P1`
   - Rationale: `_lan_apply_action()` is the largest remaining authority bottleneck in the player path.
   - Likely pass shape: `Broad migration pass`
   - Dependencies: items 1-2
   - Exit criteria: a new non-combat player-command slice (for example movement, mount, AoE/spell-launch, summons, or consumables) is handled by explicit backend command handlers/services; the already-migrated combat commands stay on the current contract boundary.

5. **Extend the explicit prompt / reaction / interrupt state model beyond the migrated reaction slice**
   - Priority: `P1`
   - Rationale: reaction-heavy combat is already present and too subtle to leave embedded in ad hoc transport handlers.
   - Likely pass shape: `Seam hardening pass`
   - Dependencies: items 2 and 4
   - Exit criteria: the canonical prompt schema covers more than the current migrated reaction offers, legacy prompt dicts are further reduced, and prompt lifecycle tests remain independent of UI code.

6. **Migrate summon/generated combatant creation onto the backend authority seam**
   - Priority: `P2`
   - Rationale: encounter population is only partially migrated today.
   - Likely pass shape: `Seam hardening pass`
   - Dependencies: items 1-2
   - Exit criteria: generated/summoned combatants use the same encounter authority model and persistence semantics as player-profile and monster-spec additions.

7. **Expose backend-owned session persistence APIs and shrink desktop-only save/load ownership**
   - Priority: `P2`
   - Rationale: web-primary DM operation is incomplete until persistence is also web-ownable.
   - Likely pass shape: `Seam hardening pass`
   - Dependencies: items 1-3
   - Exit criteria: migrated encounter/session save-load flows can be invoked from backend/web paths without depending on Tk dialogs as the authoritative entrypoint.
   - Status (2026-04-18): **Backend-owned restore seam and contract fixtures landed.** DM save/load/quick-save/quick-load/list remain authenticated `/api/dm/sessions/*` routes, and restore now applies canonical session state through `_apply_session_snapshot_authoritative_state()` plus `_remove_combatants_from_runtime_state()` before any optional Tk refresh runs. Focused tests now lock `SESSION_SNAPSHOT_SCHEMA_VERSION = 2` snapshot projections and reconnect prompt payload shapes. Remaining work for the DM browser slice is encounter-loop parity and UX, not save/load ownership.

8. **Move tactical map authority and editing to canonical web-first flows**
   - Priority: `P2`
   - Rationale: the map is large and high-risk, but it cannot remain desktop-authoritative forever.
   - Likely pass shape: `Broad migration pass`
   - Dependencies: items 2, 4, 5, and 7
   - Exit criteria: at least one meaningful tactical slice is fully web-owned on `MapState`, with Tk no longer acting as the primary source for that slice.
   - Status (2026-04-18): **Routine tactical control plus two advanced map/ship browser slices are landed in `/dm`.** The browser DM flow now handles blank-map initialization, grid-dimension updates, token placement/reposition, rules-aware movement, facing updates, obstacle and rough-terrain cell edits, hazard placement/removal, feature placement/removal, structure placement/move/removal, elevation edits, background-layer updates/reordering, AoE placement/move/removal, aura-overlay toggles, structure-template placement, ship-blueprint listing/placement preview/instantiation, boarding-link create/status/remove, and ship engagement summary/maneuver/fire/ram through authenticated backend routes tied to canonical map helpers and existing LAN/DM snapshot broadcast paths. Remaining work is narrower advanced authoring/polish parity (template/blueprint authoring/editing and higher-fidelity overlays/debug UX), not high-value ship/map staging operations.

9. **Modularize LAN and DM web clients into maintainable source modules**
   - Priority: `P3`
   - Rationale: `assets/web/lan/index.html` and inline browser logic are too large for sustained migration velocity.
   - Likely pass shape: `Seam hardening pass`
   - Dependencies: items 2-5
   - Exit criteria: migrated browser surfaces are split into smaller modules with shared client helpers; behavior remains regression-covered.

10. **Demote the desktop app to compatibility shell and prepare the standalone backend/runtime transition**
    - Priority: `P3`
    - Rationale: only after authority and web ownership are real does a runtime/language transition become an engineering task instead of a rewrite.
    - Likely pass shape: `Broad migration pass`
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

- Overall status: `Hybrid migration in progress. Web surfaces are real, and the DM web split (`/dm` dashboard + `/dm/map` dedicated map workspace) now covers ordinary encounter operation, bounded enemy monster-turn execution, and the highest-value advanced map/ship staging workflows (including layer reorder and ship engagement maneuver/fire/ram), but Tk desktop still hosts the runtime and remains the primary owner for advanced authoring/polish map workflows, long-tail monster prompt/cast parity, and adjacent desktop-only surfaces. The migrated player combat + movement/action + resource/consumable + turn-local/mobility-lite + adjacent fighter/monk resource-action + spell-launch + bard/glamour specialty + summon/echo specialty + initiative/reaction specialty + utility/admin command slices now have explicit backend contracts, canonical prompt records, and service-dispatched reaction resume.`
- Completed major passes:
  - `CombatService` and `/api/dm/...` / `/ws/dm` exist for a meaningful combat/session slice.
  - desktop/LAN wrappers already route multiple core combat mutations through the service seam.
  - player-profile and monster-spec encounter population already have service-owned entry points.
  - canonical `MapState` plus session snapshot v2 and migration coverage already exist.
  - browser-backed character create/edit and shop/admin slices already exist.
  - LAN reconnect recovery, hidden-AC-safe attack resolution, spell targeting, reactions, token portraits, and condition-icon payloads all have focused coverage.
  - **Player combat commands now enter through `PlayerCommandService` (new `player_command_service.py`):**
    - `attack_request`, `spell_target_request`, `reaction_response`, `end_turn`, `manual_override_hp` all dispatch through the service envelope.
    - The ~2600 lines of deep adjudication that used to live inline inside `_lan_apply_action()` are now owned by named `InitiativeTracker._adjudicate_attack_request` / `_adjudicate_spell_target_request` methods plus service-owned trigger-specific `reaction_response` handlers.
    - Pending reaction/prompt state (`_pending_reaction_offers`, `_pending_shield_resolutions`, `_pending_hellish_rebuke_resolutions`, `_pending_absorb_elements_resolutions`, `_pending_interception_resolutions`) has a `PromptState` accessor that owns lifecycle concerns (lookup, expiry sweep, attacker-gate check).
    - The `attack_request` pending-reaction attacker gate (the block that used to stall a new attack while a previous reaction was outstanding) now lives in `PromptState.has_pending_attacker_gate()`.
    - `manual_override_hp` continues to prefer the existing `CombatService.manual_override` entry point with the same direct-mutation fallback the inline branch had.
  - **Player resource/consumable/self-state command family now also dispatches through `PlayerCommandService` (2026-04-17):**
    - migrated command branches: `manual_override_spell_slot`, `manual_override_resource_pool`, `reaction_prefs_update`, `lay_on_hands_use`, `inventory_adjust_consumable`, and `use_consumable`.
    - `_lan_apply_action()` now treats those branches as transport/delegation glue instead of authoritative mutation owners.
    - request contracts for the migrated family are now explicit in `player_command_contracts.py` alongside the combat command contracts.
  - **Adjacent fighter/monk resource-action command family now dispatches through `PlayerCommandService` (2026-04-17):**
    - migrated command branches: `second_wind_use`, `action_surge_use`, `star_advantage_use`, `monk_patient_defense`, `monk_step_of_wind`, `monk_elemental_attunement`, `monk_elemental_burst`, and `monk_uncanny_metabolism`.
    - `_lan_apply_action()` now routes those commands through a single family dispatch branch (`typ in FIGHTER_MONK_RESOURCE_ACTION_TYPES` → `dispatch_fighter_monk_resource_action(...)`) instead of one per-command transport branch.
    - request contracts for this family are explicit in `player_command_contracts.py`, and focused coverage exists in `tests/test_lan_action_surge_pool.py`, `tests/test_lan_aoe_auto_resolution.py`, `tests/test_lan_action_message_types_allowlist.py`, `tests/test_player_command_contracts.py`, and `tests/test_lan_fighter_monk_resource_dispatch.py`.
  - **Adjacent turn-local / mobility-lite command family now dispatches through `PlayerCommandService` (2026-04-17):**
    - migrated command branches: `mount_request`, `mount_response`, `dismount`, `dash`, `use_action`, `use_bonus_action`, `stand_up`, and `reset_turn`.
    - `_lan_apply_action()` now routes those commands through a single family dispatch branch (`typ in TURN_LOCAL_COMMAND_TYPES` → `dispatch_turn_local_command(...)`) instead of per-command inline ownership.
    - request contracts for this family are explicit in `player_command_contracts.py`, and focused coverage exists in `tests/test_mounting.py`, `tests/test_lan_turn_local_command_dispatch.py`, `tests/test_player_command_contracts.py`, and `tests/test_lan_action_message_types_allowlist.py`.
  - **Adjacent movement / perform-action command family now dispatches through `PlayerCommandService` (2026-04-17):**
    - migrated command branches: `move`, `cycle_movement_mode`, and `perform_action`.
    - `_lan_apply_action()` now routes those commands through a single family dispatch branch (`typ in MOVEMENT_ACTION_COMMAND_TYPES` → `dispatch_movement_action_command(...)`) instead of inline ownership.
    - request contracts for this family are explicit in `player_command_contracts.py`, and focused coverage exists in `tests/test_lan_movement_action_dispatch.py`, `tests/test_lan_movement_mode_cycle.py`, `tests/test_lan_reaction_action.py`, `tests/test_lan_reaction_prompts.py`, `tests/test_echo_knight.py`, `tests/test_player_command_contracts.py`, and `tests/test_lan_action_message_types_allowlist.py`.
  - **Bounded wild-shape command family now dispatches through `PlayerCommandService` (2026-04-17):**
    - migrated command branches: `wild_shape_apply`, `wild_shape_pool_set_current`, `wild_shape_revert`, `wild_shape_regain_use`, `wild_shape_regain_spell`, and `wild_shape_set_known`.
    - `_lan_apply_action()` now routes those commands through a single family dispatch branch (`typ in WILD_SHAPE_COMMAND_TYPES` → `dispatch_wild_shape_command(...)`) instead of inline ownership.
    - request contracts for this family are explicit in `player_command_contracts.py`, tracker wild-shape helpers remain as compatibility adapters for YAML/runtime coupling, and focused coverage exists in `tests/test_wild_shape.py`, `tests/test_player_command_contracts.py`, and `tests/test_lan_action_message_types_allowlist.py`.
  - **Bounded spell-launch command family now dispatches through `PlayerCommandService` (2026-04-17):**
    - migrated command branches: `cast_spell` and `cast_aoe` (~1080 lines of previously-inline adjudication).
    - `_lan_apply_action()` now routes those commands through a single family dispatch branch (`typ in SPELL_LAUNCH_COMMAND_TYPES` → `dispatch_spell_launch_command(...)`); deep adjudication lives in `InitiativeTracker._handle_cast_spell_request` / `_handle_cast_aoe_request` helpers that the service delegates to.
    - request contracts for this family are explicit in `player_command_contracts.py` (`build_cast_spell_contract`, `build_cast_aoe_contract`, `SPELL_LAUNCH_COMMAND_TYPES`), and focused coverage exists in `tests/test_player_command_contracts.py`, `tests/test_lan_action_message_types_allowlist.py`, `tests/test_lan_aoe_auto_resolution.py`, `tests/test_lan_aoe_over_time.py`, and `tests/test_concentration_enforcement.py`.
    - summon/echo spawning and broader specialty resolves remained inline as deliberate out-of-scope at that point in the migration; bounded AoE manipulation, bard/glamour specialty, and summon/echo specialty families landed in subsequent passes.
  - **Bounded AoE manipulation command family now dispatches through `PlayerCommandService` (2026-04-17):**
    - migrated command branches: `aoe_move` and `aoe_remove`.
    - `_lan_apply_action()` now routes those commands through a single family dispatch branch (`typ in AOE_MANIPULATION_COMMAND_TYPES` → `dispatch_aoe_manipulation_command(...)`); the existing map-heavy bodies live in `InitiativeTracker._handle_aoe_move_request` / `_handle_aoe_remove_request` helpers that the service delegates to.
    - request contracts for this family are explicit in `player_command_contracts.py` (`build_aoe_move_contract`, `build_aoe_remove_contract`, `AOE_MANIPULATION_COMMAND_TYPES`), and focused coverage exists in `tests/test_lan_aoe_manipulation_dispatch.py`, `tests/test_player_command_contracts.py`, `tests/test_lan_aoe_over_time.py`, `tests/test_concentration_enforcement.py`, and `tests/test_spell_rotation_parity.py`.
    - the older `cast_aoe_adjust` TODO reference appears stale on this branch; no live handler or focused tests for it exist in the current repo state.
  - **Bounded bard/glamour specialty command family now dispatches through `PlayerCommandService` (2026-04-17):**
    - migrated command branches: `command_resolve`, `bardic_inspiration_grant`, `bardic_inspiration_use`, `mantle_of_inspiration`, `beguiling_magic_restore`, and `beguiling_magic_use`.
    - `_lan_apply_action()` now routes those commands through a single family dispatch branch (`typ in BARD_GLAMOUR_SPECIALTY_COMMAND_TYPES` → `dispatch_bard_glamour_specialty_command(...)`) instead of inline ownership.
    - deep adjudication bodies moved into named tracker helpers (`_handle_command_resolve_request`, `_handle_bardic_inspiration_grant_request`, `_handle_bardic_inspiration_use_request`, `_handle_mantle_of_inspiration_request`, `_handle_beguiling_magic_restore_request`, `_handle_beguiling_magic_use_request`) that the service delegates to.
    - request contracts for this family are explicit in `player_command_contracts.py`, and focused coverage exists in `tests/test_command_spell.py`, `tests/test_mantle_of_inspiration.py`, `tests/test_beguiling_magic.py`, `tests/test_bardic_inspiration_temp_pool.py`, `tests/test_lan_bard_glamour_specialty_dispatch.py`, `tests/test_lan_action_message_types_allowlist.py`, and `tests/test_player_command_contracts.py`.
  - **Bounded summon/echo specialty command family now dispatches through `PlayerCommandService` (2026-04-18):**
    - migrated command branches: `echo_summon`, `echo_swap`, `dismiss_summons`, `dismiss_persistent_summon`, `reappear_persistent_summon`, `assign_pre_summon`, and `echo_tether_response`.
    - `_lan_apply_action()` now routes those commands through a single family dispatch branch (`typ in SUMMON_ECHO_SPECIALTY_COMMAND_TYPES` → `dispatch_summon_echo_specialty_command(...)`) instead of inline ownership.
    - deep adjudication bodies moved into named tracker helpers (`_handle_echo_summon_request`, `_handle_echo_swap_request`, `_handle_dismiss_summons_request`, `_handle_dismiss_persistent_summon_request`, `_handle_reappear_persistent_summon_request`, `_handle_assign_pre_summon_request`, `_handle_echo_tether_response_request`) that the service delegates to.
    - request contracts for this family are explicit in `player_command_contracts.py`, and focused coverage exists in `tests/test_lan_summon_echo_specialty_dispatch.py`, `tests/test_echo_knight.py`, `tests/test_lan_action_message_types_allowlist.py`, and `tests/test_player_command_contracts.py`.
  - **Bounded initiative/reaction specialty command family now dispatches through `PlayerCommandService` (2026-04-17):**
    - migrated command branches: `initiative_roll` and `hellish_rebuke_resolve`.
    - `_lan_apply_action()` now routes those commands through a single family dispatch branch (`typ in INITIATIVE_REACTION_SPECIALTY_COMMAND_TYPES` → `dispatch_initiative_reaction_specialty_command(...)`) instead of inline ownership.
    - deep adjudication bodies moved into named tracker helpers (`_handle_initiative_roll_request`, `_handle_hellish_rebuke_resolve_request`) that the service delegates to.
    - request contracts for this family are explicit in `player_command_contracts.py`, and focused coverage exists in `tests/test_lan_initiative_reaction_specialty_dispatch.py`, `tests/test_hellish_rebuke_reaction.py`, and `tests/test_player_command_contracts.py`.
  - **Bounded utility/admin command family now dispatches through `PlayerCommandService` (2026-04-17):**
    - migrated command branches: `set_color`, `set_facing`, `set_auras_enabled`, and `reset_player_characters`.
    - `_lan_apply_action()` now routes those commands through a single family dispatch branch (`typ in UTILITY_ADMIN_COMMAND_TYPES` → `dispatch_utility_admin_command(...)`) instead of inline ownership.
    - runtime bodies moved into named tracker helpers (`_handle_set_color_request`, `_handle_set_facing_request`, `_handle_set_auras_enabled_request`, `_handle_reset_player_characters_request`) that the service delegates to.
    - request contracts for this family are explicit in `player_command_contracts.py`, and focused coverage exists in `tests/test_lan_utility_admin_dispatch.py`, `tests/test_lan_movement_mode_cycle.py`, `tests/test_lan_auras_toggle.py`, and `tests/test_player_command_contracts.py`.
  - **Migrated player combat contracts and canonical prompt records now exist (2026-04-17):**
    - `player_command_contracts.py` defines explicit request/result/event/prompt builders for the migrated player combat slice.
    - `PromptState` now treats `_pending_prompts` as the canonical backend-owned prompt store and projects legacy `_pending_*` dictionaries from that state for compatibility.
    - migrated reconnect payloads now expose `you.pending_prompts` / `you.pending_prompt`, and session snapshots persist `combat.pending_prompts`.
    - shield / absorb elements / interception resume no longer recurse through `_lan_apply_action(resume_msg)`; `PlayerCommandService` dispatches a structured resume object instead.
  - **Combat-trigger prompt creation now atomically owned by `PromptState` (2026-04-17):**
    - `PromptState.create_reaction_offer` now accepts optional `prompt_id`, `resolution`, and `resume_dispatch` parameters, threading them through to `build_prompt_record` in one step.
    - The tracker's `_create_reaction_offer` wrapper now accepts the same optional params and passes them through, eliminating all post-creation `prompts.attach_resolution(...)` calls at call sites.
    - Five call sites updated: shield offer in `_adjudicate_attack_request`, shield offer in `_adjudicate_spell_target_request`, `_maybe_offer_absorb_elements`, `_maybe_offer_hellish_rebuke`, and `_maybe_offer_interception`.
    - For hellish rebuke, the prompt_id is pre-generated before the call so `player_visible` (needed for reconnect `next_step` in the prompt snapshot) can be built atomically at creation time.
    - Remaining tracker-owned entry points at this stage were `sentinel_hit_other` / `leave_reach` / `sentinel_disengage` OA reaction offers plus `_create_reaction_offer` / `_maybe_offer_*`.
  - **Prompt-override claim gate now dispatches through `PlayerCommandService` (2026-04-17):**
    - `_lan_apply_action()` no longer embeds the action-family-specific `prompt_override_ok` branch for `attack_request` / `spell_target_request`.
    - new `PlayerCommandService.allow_prompt_claim_override(...)` owns that prompt-follow-up rule set (turn-owner follow-up, OA follow-up, and persistent AoE follow-up target inclusion checks).
    - focused regression coverage for the new service-owned gate lives in `tests/test_player_command_contracts.py` (`PlayerCommandServicePromptOverrideTests`) in addition to existing LAN attack/spell prompt override tests.
  - **Prompt/reaction offer creation + emission now routes through service-owned entry points (2026-04-17):**
    - `PlayerCommandService` now owns reaction-offer creation/emission via `create_reaction_offer(...)`.
    - `PlayerCommandService` now owns the three tracker-local offer builders via service entry points: `maybe_offer_absorb_elements(...)`, `maybe_offer_hellish_rebuke(...)`, and `maybe_offer_interception(...)`.
    - tracker adjudicators and movement/perform-action OA sentinel call sites now invoke service-owned prompt entry points instead of tracker-owned `_create_reaction_offer` / `_maybe_offer_*`.
    - tracker `_create_reaction_offer` / `_maybe_offer_*` remain only as compatibility delegates to the service boundary.
    - focused boundary coverage added in `tests/test_player_command_contracts.py` (`PlayerCommandServiceReactionOfferOwnershipTests`) and existing reaction suites continue covering behavior.
  - **Trigger-specific reaction resolution now runs through service-owned handlers (2026-04-18):**
    - `PlayerCommandService.reaction_response(...)` now resolves shield / hellish rebuke / absorb elements / interception via service-owned `_resolve_*_reaction` helpers instead of delegating those branches to `InitiativeTracker._adjudicate_reaction_response`.
    - reaction-response dispatch results now carry prompt lifecycle metadata (`trigger`, `choice`, `prompt_state`) from the service resolver, while shield/absorb/interception resume dispatch behavior remains intact.
    - `InitiativeTracker._adjudicate_reaction_response` remains only as a compatibility wrapper that forwards to the service-owned resolver.
    - focused ownership coverage was extended in `tests/test_player_command_contracts.py` (`ReactionResumeDispatchTests.test_reaction_response_resolution_no_longer_uses_tracker_adjudicator`) and existing shield/absorb/hellish/interception suites continue to cover behavior.
  - **First web-owned DM session persistence vertical slice landed (2026-04-17):**
    - new authenticated routes on `LanController._fastapi_app`: `GET /api/dm/sessions` (list saves + quick-save metadata + default filename), `POST /api/dm/sessions/save` (accepts optional `filename`/`label`), `POST /api/dm/sessions/load` (reloads by filename and broadcasts), `POST /api/dm/sessions/quick-save`, and `POST /api/dm/sessions/quick-load`.
    - all five routes share the `_check_dm_auth(request)` admin-token gate, reuse existing `_save_session_to_path` / `_load_session_from_path` / `_session_saves_dir` / `_session_quicksave_path` / `_session_default_filename` helpers, and validate filenames through `_SESSION_FILENAME_RE` plus `Path.relative_to(saves_dir.resolve())` to prevent path-traversal escape.
    - load-path routes push a fresh `CombatService.combat_snapshot()` to the DM WebSocket via `_push_dm_snapshot_to_ws_clients` and call `_lan_force_state_broadcast()` so LAN clients see restored state without a Tk event.
    - `assets/web/dm/index.html` gained a "Session Persistence" mut-card with Quick Save / Quick Load, named Save (filename input + label), and Load (dropdown of discovered snapshots + Refresh) controls; destructive loads prompt `confirm()` and `startAutoRefresh()` now populates the list on login.
    - focused coverage added in `tests/test_dm_session_persistence_routes.py` (16 fastapi/httpx-gated route tests covering list/save/load/quick flows, auth, and path-traversal rejection, plus a fastapi-free HTML-surface test).
    - Tk file-dialog save/load remains as a compatibility entrypoint; the DM browser console is now honestly able to drive the encounter-loop save/load cycle without Tk being the primary owner.
  - **Session restore is now backend-owned first, Tk refresh second (2026-04-18):**
    - `_load_session_from_path()` / `_apply_session_snapshot()` now route restore semantics through `_apply_session_snapshot_authoritative_state()`, which applies combat/map/prompt/log state without relying on Tk widget mutation.
    - `_remove_combatants_from_runtime_state()` now handles state-only combatant cleanup so restore can clear existing encounter state without using map-window token/canvas mutation as the authoritative mechanism.
    - `_refresh_session_snapshot_tk_compatibility()` is now the thin desktop adapter for `_open_map_mode()`, `_load_history_into_log()`, and `_rebuild_table()` when Tk widgets actually exist.
    - focused coverage was extended in `tests/test_session_save_load.py` for a headless restore path plus a schema-v2 snapshot projection, and in `tests/test_lan_reconnect_recovery.py` for claim/turn/map/prompt reconnect payload shape.
  - **DM browser core encounter-loop parity landed for ordinary operation (2026-04-18):**
    - new authenticated DM routes: `GET /api/dm/encounter/options`, `POST /api/dm/encounter/players/add`, `POST /api/dm/encounter/monsters/add`, and `POST /api/dm/sessions/new`.
    - the new encounter routes reuse the existing tracker/service encounter seams instead of inventing browser-only logic: player-profile population goes through `_add_player_profile_combatants_via_service(...)`, monster-spec population goes through `_add_monster_spec_combatants_via_service(...)`, and blank-session reset goes through `_new_session_apply_blank_state(confirm=False)`.
    - `assets/web/dm/index.html` now exposes player-profile encounter assembly, monster-spec group assembly, initiative rolling, and a browser-owned "New Blank Session" action alongside the earlier persistence/start-end/turn controls.
    - the DM console refreshes encounter setup options via `/api/dm/encounter/options` and re-syncs those choices when encounter membership changes, so post-load/add/remove/reset browser state stays aligned with backend authority.
    - focused coverage landed in `tests/test_dm_encounter_loop_routes.py` (fastapi/httpx-gated route tests plus a fastapi-free HTML-surface test), while existing `CombatService*PopulationTests`, `CombatServiceStartCombatTests`, `CombatServiceEndCombatTests`, and `SessionSaveLoadTests.test_new_session_apply_blank_state_clears_combat_map_and_log` continue to cover the reused backend seams.
  - **DM browser routine tactical map operation landed (2026-04-18):**
    - combined DM snapshots now include a `tactical_map` payload sourced from `_lan_snapshot(include_static=False, hydrate_static=False)` via `_dm_tactical_snapshot()` and `LanController._dm_console_snapshot_payload()`, so the DM console receives map-linked combat state over the same polling/WebSocket surface it already uses.
    - new authenticated routes on `LanController._fastapi_app`: `POST /api/dm/map/combatants/{cid}/move`, `POST /api/dm/map/combatants/{cid}/place`, and `POST /api/dm/map/combatants/{cid}/facing`.
    - those routes reuse tracker-owned map semantics instead of browser-only logic: rules-aware movement routes through `_lan_try_move()`, placement/reposition routes through destination validation plus canonical position mutation helpers, and facing routes reuse the same facing/AoE synchronization semantics already used by LAN/admin control paths.
    - `assets/web/dm/index.html` now includes a lightweight tactical map canvas plus controls for selecting a combatant, targeting a cell, placing/repositioning, spending movement, and updating facing during ordinary map-backed combat.
    - focused coverage landed in `tests/test_dm_tactical_map_routes.py`, including fastapi/httpx-gated route tests, a fastapi-free HTML-surface test, direct tracker helper tests, and a combined DM snapshot contract test.
  - **DM browser advanced composition + ship engagement operations slice landed (2026-04-18):**
    - new authenticated routes on `LanController._fastapi_app`: `GET /api/dm/map/ships/{structure_id}/engagement`, `POST /api/dm/map/ships/{structure_id}/maneuver-preview`, `POST /api/dm/map/ships/{structure_id}/maneuver`, `POST /api/dm/map/ships/{source_structure_id}/weapons/fire`, `POST /api/dm/map/ships/{source_structure_id}/ram`, and `POST /api/dm/map/backgrounds/{bid}/order`.
    - new tracker helpers back those routes via canonical semantics (`_dm_ship_engagement_summary`, `_dm_ship_maneuver_on_map`, `_dm_ship_fire_weapon_on_map`, `_dm_ship_ram_on_map`, `_dm_reorder_background_layer`) and preserve LAN/DM synchronization through the existing snapshot + broadcast paths.
    - `assets/web/dm/index.html` now exposes browser controls for ship engagement source/target staging, maneuver preview/apply, weapon fire, ram actions, and background-layer stack reordering.
    - focused coverage extended in `tests/test_dm_tactical_map_routes.py` for route/auth/helper/HTML surfaces, plus focused regression runs for `tests/test_ship_engagement_gameplay.py`, `tests/test_map_state_foundation.py`, and `tests/test_session_save_load.py`.
  - **Dedicated DM map workspace landed (2026-04-18):**
    - new DM route `GET /dm/map` serves the same DM tactical/session application shell in map-workspace mode while `/dm` remains dashboard-oriented.
    - `assets/web/dm/index.html` now supports workspace mode injection (`data-dm-workspace`) and promotes map setup + tactical map + monster-turn controls into a full-size central workspace lane on `/dm/map`, while preserving the existing backend-owned `/api/dm/*` snapshot/mutation paths and DM/LAN broadcast semantics.
    - focused route/HTML assertions were added to `tests/test_dm_tactical_map_routes.py` for `/dm` vs `/dm/map` workspace mode rendering.
  - **Core combat/resource fundamentals bug-fix pass landed for browser bug testing (2026-04-18):**
    - no-weapon `attack_request` now synthesizes an unarmed-strike fallback instead of hard-failing with "No weapon configured"; monk-style unarmed defaults are preserved.
    - shared resource-pool accounting now resolves `current` via normalized max defaults when YAML omits it, and materializes missing derived non-inventory pools before consume/set mutation paths.
    - pact-magic runtime paths now stay playable for pact-only casters: profile payload projection can expose runtime pact slots for LAN clients, and spell-slot consumption can spend `pact_magic_slots` when no standard slot is available.
    - focused regression coverage now includes `tests/test_resource_pool_accounting.py` (new), plus an added no-weapon unarmed fallback assertion in `tests/test_lan_attack_request.py`; existing action-surge and pact-slot suites remain green.
  - **LAN browser AoE/summon action-flow reliability bug-fix pass landed for bug testing (2026-04-18):**
    - AoE cast submission now keeps a short-lived sync ghost overlay (`pendingAoeCastSyncGhost`) between placement submit and authoritative AoE state arrival, so the map no longer flashes through contradictory "placed → missing → reappeared" visuals during normal cast completion races.
    - summon/custom-summon cast submission now closes cast modal surfaces before entering summon placement mode, so placement is the single active interaction state instead of a stale-open modal + placement hybrid.
    - cast-interaction reset now explicitly clears the AoE sync ghost path, keeping cancellation/open/close transitions deterministic.
    - focused browser regression coverage was extended in `tests/test_lan_cast_modal_regression.py` for AoE post-submit sync handling and summon modal-close-on-placement behavior.
  - **First Tk-optional/headless host extraction pass landed (2026-04-18):**
    - `tk_compat.py` now exposes a real `HeadlessRoot` class that stands in for `tk.Tk` with a thread-safe `after()` scheduler, working `mainloop()`/`quit()`/`destroy()`/`update()` semantics, and `after_cancel`/`after_idle` parity with the subset of Tk that the runtime actually uses.
    - `tk_compat.load_tk_modules()` honors a new `INIT_TRACKER_HEADLESS=1` env flag (and `is_headless_env()` helper). When set, it forces the dummy widget set with `tk.Tk` swapped for `HeadlessRoot` and overrides `sys.modules["tkinter*"]` so subsequent `import tkinter` lookups resolve to the headless modules instead of constructing a real root window.
    - new `serve_headless.py` entrypoint sets the env flag before importing the tracker, instantiates the same `InitiativeTracker` runtime authority used by desktop mode, supports `--host`/`--port`/`--no-auto-lan` overrides, installs SIGINT/SIGTERM signal handlers, prints the DM/LAN URLs, and runs `app.mainloop()` (which is now a real headless event loop, not Tk's).
    - desktop `main()` in `dnd_initative_tracker.py` is unchanged: when `INIT_TRACKER_HEADLESS` is unset and tkinter is importable, the existing Tk path is preserved as a compatibility entrypoint.
    - focused coverage landed in `tests/test_headless_host.py`: scheduler ordering + cancel + clean `quit()`, env-flag detection, and a subprocess-isolated end-to-end check that constructs a real `InitiativeTracker`, starts the LAN server on a loopback port, and confirms `GET /dm` returns 200 with no Tk window opened.
    - residual coupling intentionally remaining after this pass: `helper_script.InitiativeTracker(tk.Tk)` and the `dnd_initative_tracker.InitiativeTracker` subclass still inherit from `tk.Tk` (now `HeadlessRoot` under the headless flag), `_build_ui()` still constructs widget objects (now no-op `_DummyTkWidget` instances), and many tracker dialogs/menus still issue Tk method calls that are absorbed as no-ops. This is acceptable for the "make Tk optional as a host" milestone; full structural decoupling of widget construction from runtime authority is still pending.
  - **Host-mode seam landed to gate startup Tk construction (2026-04-18):**
    - `helper_script.InitiativeTracker.__init__` now sets `self.host_mode = "headless" if tk_compat.is_headless_env() else "desktop"` immediately after `super().__init__()`, and gates `self.title()/self.geometry()/self.iconphoto()`, `self._build_ui()`, `self._open_starting_players_dialog()`, and `self._rebuild_table()` on `host_mode == "desktop"`. In headless mode, the constructor calls a new `_init_headless_state_stubs()` helper that only creates the StringVar mirrors the runtime paths (turn tracker, movement mode, monster library filters) actually push values into. No widgets, no Treeview, no log Text, no menus, no monster dropdown construction.
    - `dnd_initative_tracker.InitiativeTracker.__init__` similarly gates `self.title(...)`, `self._install_lan_menu()`, and `self.after(0, self._install_monster_dropdown_widget)` on `host_mode == "desktop"`. LAN construction, quick-save autoload, update checks, and `POC_AUTO_START_LAN` remain unconditional — the runtime authority still boots identically in both modes.
    - `_append_log_line` was adjusted so file history is written in both host modes, while Text widget writes only happen in desktop mode (previously the whole method short-circuited when the log Text widget was absent, so headless mode silently dropped history writes). `_apply_name_tags_in_range`, `_load_history_into_log`, and `_rebuild_table` gate widget work on `host_mode == "desktop"` (the previous `hasattr(self, "log_text"/"tree")` guards were unreliable because `_DummyTkWidget.__getattr__` makes `hasattr()` always return True in headless mode).
    - `tests/test_headless_host.py` was extended so the subprocess smoke test asserts `app.host_mode == "headless"`, that `tree`/`log_text`/`_lan_url_mode_var`/`_monster_combo` are absent from `app.__dict__`, and that `app._log(...)`, `app._rebuild_table()`, and `app._update_turn_ui()` don't crash under headless construction.
  - **Bounded runtime desktop-surface seam pass landed (2026-04-18):**
    - `helper_script.InitiativeTracker` now exposes an explicit runtime host boundary via `_host_supports_desktop_widgets()` and `_allow_desktop_runtime_surface(surface_name)`.
    - map-window construction/use now routes through that boundary in both classes: `helper_script.InitiativeTracker._open_map_mode()` and `dnd_initative_tracker.InitiativeTracker._open_map_mode()` return immediately in headless mode, so headless no longer creates a dummy `_map_window` during runtime.
    - high-value runtime desktop-only dialog/menu surfaces now explicitly gate on the host boundary: `_show_dm_up_alert_dialog`, `_install_lan_menu`, `_prompt_set_lan_https_public_url`, `_save_session_dialog`, `_load_session_dialog`, `_open_roster_manager`, `_show_lan_url`, `_show_lan_qr`, and `_session_restore_supports_tk_refresh`.
    - focused seam coverage now includes `HeadlessRuntimeSurfaceGuardTests` plus additional subprocess assertions in `tests/test_headless_host.py` that guarded runtime calls execute safely in headless mode while keeping `_map_window` unopened.
  - **Final bounded B host/runtime follow-up pass landed (2026-04-18):**
    - the remaining high-value dialog/popup/helper entrypoints in both tracker layers now route through the explicit host boundary instead of relying on dummy-widget absorption in headless mode.
    - `helper_script.py` now explicitly host-gates long-tail desktop dialogs/tools: long-rest confirm, starting-player roster, monster/library info dialogs, combatant-info/stat-block dialogs, random enemy + bulk add, and damage/heal/condition/move tools.
    - `dnd_initative_tracker.py` now explicitly host-gates remaining desktop-only runtime dialogs/helpers: LAN sessions/admin assignment/YAML player manager windows, monster library/stat-block windows, map attack tool dialog, About/update-log/update-check UI helpers, and update-offer/update-workflow prompts.
    - headless behavior for runtime helpers that previously surfaced `messagebox` popups is now explicit: quick-save/quick-load and LAN initiative prompting keep backend behavior but route status/error feedback to ops/log paths when desktop dialogs are unavailable.
    - startup update-check now skips desktop update prompts in headless mode and logs availability instead of attempting dialog-driven workflow.
    - focused seam coverage was expanded in `tests/test_headless_host.py` (unit + subprocess no-op calls for newly gated surfaces) and `tests/test_startup_update_behavior.py` (headless update-offer startup/confirm behavior).
- In-progress pass: `None. Bounded host/runtime seam work for Tk-optional headless operation is now complete enough.`
- Next recommended pass: `Pivot back to backend-authority extraction (player-command/encounter/runtime ownership cleanup) while leaving remaining Tk map-editor internals as isolated desktop-only legacy cleanup.`
- Blocked items:
  - `Broad YAML-backed validation still depends on python3-yaml in the test environment. Minimal Debian-style environments without that package leave item-backed and monster-backed combat suites partially unrunnable even though the migrated combat service/tests can now import without real Tk.`
  - `No hard architecture blocker is confirmed yet, but framework/runtime choice should remain deferred until contracts stabilize.`
- Decisions made:
  - `majorTODO.md` is the master migration tracker for platform work.
  - authority cleanup comes before framework/language churn.
  - rendering remains client-side.
  - YAML/session compatibility is preserved until replacement paths are validated.
  - older migration docs are historical context when they drift from code/tests.
  - **Player command service seam uses a thin envelope + delegate pattern (updated 2026-04-18).** The service validates turn ownership, reaction-gating, and prompt lifecycle; attack/spell deep rules still delegate to extracted tracker methods, while trigger-specific reaction resolution is now service-owned. This keeps the authority boundary explicit while preserving runtime behavior.
  - **Canonical prompt records now live in tracker-owned `_pending_prompts` with compatibility projections (2026-04-17).** `PromptState` still uses the tracker instance for storage and compatibility, but the canonical shape for the migrated slice is now the prompt record rather than the legacy `_pending_*` dictionaries.
  - **Migrated reaction resume now returns structured dispatch metadata instead of transport recursion (2026-04-17).** Resume for shield / absorb elements / interception is now backend/service owned, not a recursive `_lan_apply_action(resume_msg)` side effect.
  - **Resource/consumable extraction follows the same service-envelope pattern (2026-04-17).** `PlayerCommandService` now owns validation/mutation orchestration/result shaping for slot/pool overrides, reaction preference updates, Lay on Hands, and consumable inventory/use, while tracker helpers remain compatibility/persistence adapters.
  - **Fighter/monk resource-action extraction follows the same service-envelope pattern (2026-04-17).** `PlayerCommandService` now owns validation/mutation orchestration/result shaping for second wind/action surge/star advantage and monk focus actions, while tracker helpers remain compatibility adapters for map/effect/runtime coupling.
  - **Wild-shape extraction follows the same service-envelope pattern (2026-04-17).** `PlayerCommandService` now owns validation/mutation orchestration/result shaping for `wild_shape_apply`, `wild_shape_pool_set_current`, `wild_shape_revert`, `wild_shape_regain_use`, `wild_shape_regain_spell`, and `wild_shape_set_known`, while tracker helpers remain compatibility adapters for YAML persistence, runtime beast-form mutation, and player-profile lookups.
  - **Spell-launch extraction follows the same service-envelope pattern (2026-04-17).** `PlayerCommandService.dispatch_spell_launch_command` owns the transport/authority boundary for `cast_spell` / `cast_aoe`; the deep adjudication bodies moved verbatim into `InitiativeTracker._handle_cast_spell_request` / `_handle_cast_aoe_request` methods, preserving user-visible behavior while advancing the service authority surface. Map-heavy AoE manipulation and summon/echo spawning remained inline until dedicated future passes.
  - **AoE manipulation extraction follows the same service-envelope pattern (2026-04-17).** `PlayerCommandService.dispatch_aoe_manipulation_command` now owns the transport/authority boundary for `aoe_move` / `aoe_remove`; the deep map-heavy bodies moved verbatim into `InitiativeTracker._handle_aoe_move_request` / `_handle_aoe_remove_request` methods, preserving user-visible AoE move/remove behavior while shrinking `_lan_apply_action()`.
  - **Bard/glamour specialty extraction follows the same service-envelope pattern (2026-04-17).** `PlayerCommandService.dispatch_bard_glamour_specialty_command` now owns the transport/authority boundary for `command_resolve`, bardic inspiration grant/use, mantle of inspiration, and beguiling magic restore/use; deep adjudication bodies moved into dedicated `_handle_*_request` tracker helpers to preserve user-visible behavior while shrinking `_lan_apply_action()`.
  - **Summon/echo specialty extraction follows the same service-envelope pattern (2026-04-18).** `PlayerCommandService.dispatch_summon_echo_specialty_command` now owns the transport/authority boundary for `echo_summon`, `echo_swap`, `dismiss_summons`, `dismiss_persistent_summon`, `reappear_persistent_summon`, `assign_pre_summon`, and `echo_tether_response`; deep adjudication bodies moved into dedicated `_handle_*_request` tracker helpers to preserve user-visible behavior while shrinking `_lan_apply_action()`.
  - **Utility/admin extraction follows the same service-envelope pattern (2026-04-17).** `PlayerCommandService.dispatch_utility_admin_command` now owns the transport/authority boundary for `set_color`, `set_facing`, `set_auras_enabled`, and `reset_player_characters`; deep runtime bodies moved into dedicated `_handle_*_request` tracker helpers to preserve user-visible behavior while shrinking `_lan_apply_action()`.
  - **Combat-trigger prompt creation is now atomic in `PromptState` (2026-04-17).** The separate two-step create+attach_resolution pattern for shield, absorb_elements, hellish_rebuke, and interception prompt offers is replaced by a single atomic `PromptState.create_reaction_offer` call that includes `resolution` and `resume_dispatch` at creation time. For hellish_rebuke, the prompt_id is pre-generated so the `player_visible` reconnect field can be included at creation.
  - **Turn-local / mobility-lite extraction follows the same service-envelope pattern (2026-04-17).** `PlayerCommandService` now owns validation/mutation orchestration/result shaping for mount request/response, dismount, dash, action/bonus-action spending, stand up, and turn reset, while tracker helpers remain compatibility adapters for live map state, mount initiative, and snapshot restore.
  - **DM session persistence is now web-operable first, Tk file dialog second (2026-04-17).** Authenticated DM routes under `/api/dm/sessions/...` reuse the existing `_save_session_to_path` / `_load_session_from_path` / `_session_quicksave_path` helpers rather than reimplementing snapshot semantics; the Tk file dialog remains only as a compatibility entrypoint. This locks the first honest web vertical slice into the DM console while preserving the existing JSON snapshot schema (`SESSION_SNAPSHOT_SCHEMA_VERSION = 2`).
- Open questions:
  - `When should the backend leave the Tk process: after DM web-primary parity, or only after player command extraction too?`
  - `When is it worth introducing a typed frontend build pipeline for LAN/DM clients?`
  - `Which generated combatant paths should be migrated first after core encounter population: summons, mounts, echoes, ship-linked entities, or something else?`
  - `What is the minimum acceptable web map/editor parity before desktop map ownership can be demoted?`
  - `Should the adjudicate_* tracker methods be moved fully onto PlayerCommandService or a domain engine, or remain on InitiativeTracker until the Tk/YAML coupling is addressed in its own pass?`

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

### Pivot from host seam to authority extraction

The Tk host seam is now bounded enough for normal headless DM-browser operation: launch/startup, core runtime mutation paths, and the long-tail desktop dialog/popup helpers are explicitly routed through `_allow_desktop_runtime_surface(...)` rather than dummy-widget no-op behavior.

What is architecturally meaningful next:
- resume backend-authority extraction work (player-command and encounter/runtime ownership) instead of further Tk host-surface chasing.
- keep `/dm` + existing API/service routes as the operator surface and avoid introducing new desktop-first ownership.
- treat remaining Tk coupling as desktop-only legacy internals (mainly `BattleMapWindow`/map-editor dialog stacks) unless a concrete headless/runtime regression appears.

Recommended validation:
- `python3 -m py_compile` on touched Python files.
- focused `python3 -m unittest` for host/runtime seams and the specific authority slice being migrated.
- when optional FastAPI/HTTP deps are missing, prioritize equivalent non-HTTP seam tests so migration assertions remain enforceable.

Deferred:
- full Tk removal or class hierarchy rewrite.
- player-web tactical/editor parity expansion outside scoped authority passes.
