# Server Runtime App-Host Route-Registration Planning Checkpoint - 2026-07-01

## Status

Checkpoint/decision document only. This document does not authorize app implementation, test edits, route registration changes, route body movement, app factory behavior changes, launch command changes, lifespan behavior changes, readiness behavior changes, Uvicorn host changes, snapshot warm-up changes, cache ownership changes, response payload changes, WebSocket behavior changes, queue behavior changes, command semantic changes, production operations, deploys, commits, pushes, SSH, or gameplay behavior changes.

## Decision Summary

Route registration remains legacy-owned in `LanController.start()` except for the package-owned health/readiness routes in `init_tracker_server.app.create_app(...)`.

A future route-registration ownership move can be designed safely only if it is registration-only: preserve route bodies, route-local helper closures, payloads, auth/session behavior, WebSocket state, queues, snapshot/cache ownership, and gameplay authority. The future seam should make package-owned app creation coordinate route registration through an explicit registrar contract, while the legacy controller continues to supply the route bodies for that slice.

Do not implement that move next. The next safest work item is evidence capture for the existing host boundary:

`WORK-20260701-app-host-runtime-lifecycle-smoke-evidence-capture`

Reason: the `UvicornServerHost` implementation still lacks recorded live startup/readiness smoke evidence, and route registration has high coupling to the largest remaining legacy server surface.

## Evidence Inspected

Documents inspected:

- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260701-app-host-runtime-lifecycle-post-implementation-checkpoint.md`
- `docs/planning/living_docs/server_runtime_app_host_lifecycle_post_implementation_checkpoint_20260701.md`
- `docs/work_items/completed/WORK-20260701-app-host-runtime-lifecycle-minimal-implementation.md`
- `docs/work_items/completed/WORK-20260701-app-host-runtime-lifecycle-checkpoint.md`
- `docs/planning/living_docs/server_runtime_app_host_lifecycle_checkpoint_20260701.md`

Code inspected:

- `init_tracker_server/app.py`
- `server_app.py`
- `init_tracker_server/host.py`
- `dnd_initative_tracker.py`, limited to route registration, `create_app` use, `LanController.start()`, and `LanController.stop()` seams

No old plans, `majorTODO.md`, runtime reports, historical notes, app source outside the named files, tests, production files, browser assets, bug inbox files, or log directories were inspected.

## Current Ownership Map

Package app factory ownership:

- `init_tracker_server.app.create_app(lan_controller=None)` constructs `FastAPI(lifespan=app_lifespan)`.
- It initializes `app.state.ready = False`, `app.state.lan_controller`, and `app.state.runtime = ServerRuntimeFacade(lan_controller=lan_controller)`.
- It registers `/health`, `/api/health`, `/ready`, and `/api/ready`.
- `app_lifespan(...)` calls `runtime.start()`, sets readiness true, then on shutdown clears readiness and calls `runtime.shutdown()`.

Compatibility ownership:

- `server_app.py` is only a compatibility shim re-exporting `app_lifespan` and `create_app`.

Package host ownership:

- `init_tracker_server.host.UvicornServerHost` owns Uvicorn config/server/thread mechanics and stop request for an already-created app.
- It does not own route registration, app creation, route bodies, snapshot warm-up, queues, WebSockets, or gameplay authority.

Legacy route-registration ownership:

- `LanController.start()` calls `create_app(lan_controller=self)`, mirrors `self._runtime`, mounts static assets, registers middleware, defines route-local helpers, registers all non-health HTTP and WebSocket routes, seeds `_cached_snapshot` / `_cached_pcs`, delegates hosting to `UvicornServerHost`, and starts Tk polling.
- `LanController.stop()` delegates stop request to `self._server_host.request_stop()` when present and retains the legacy `_uvicorn_server.should_exit` fallback.

## Route Registration Inventory

Package-owned routes:

- `GET /health`
- `GET /api/health`
- `GET /ready`
- `GET /api/ready`

Legacy-owned middleware and mounts:

- request path/debug middleware
- stale asset cache-control middleware
- `/assets` static mount
- `/monsters/images` static mount

Legacy-owned page/static routes:

- `/`
- `/planning`
- `/new_character`
- `/edit_character`
- `/shop_admin`
- `/shop`
- `/config`
- `/sw.js`
- `/rules.pdf`
- `/dm`
- `/dmcontrol`
- `/dm/map`

Legacy-owned general API groups:

- rules status, table of contents, and spell-page metadata
- push subscription
- admin login, refresh, and sessions
- LAN logs and client-log ingestion
- spells
- shop catalog and player shop state
- character CRUD/import/export/equipment/spellbook/player cache
- monster lookup

Legacy-owned WebSockets:

- `/ws`
- `/ws/dm`

Legacy-owned DM/combat/session/map API groups:

- DM combat snapshot and turn/combatant/session mutations
- encounter player/monster add routes
- monster attacks and monster capabilities
- monster pilot routes
- developer smoke fixture routes
- tactical preset/blueprint/template/boarding-link reads
- map new/settings/obstacle/terrain/hazard/feature/structure/ship/boarding/elevation/background/AoE/aura routes
- combatant add/initiative/delete routes
- DM session new/list/save/load/quick-save/quick-load routes

## Coupling Findings

The dependency and setup block is not just registration. It performs lazy FastAPI imports, exposes FastAPI classes in module globals for nested route type resolution, imports runtime command constants, creates the package app, mirrors `self._runtime`, configures request-path/debug middleware, syncs profile picture cache, computes asset paths, mounts static directories, and defines HTML shell loaders.

The page/static/general API routes depend heavily on `LanController` and tracker state: `self.cfg`, `self._ws_debug_enabled`, `self.html_injected_base_url()`, host allowlist checks, rules-PDF resolution, admin password/token state, push subscription persistence, YAML/spell helpers, shop catalog persistence, character APIs, assigned-character lookup by host, and direct `self.app` helpers.

The player `/ws` route is a combined registration/body/authority block. It handles host authorization, connection registries, send locks, metadata, reverse DNS, cached snapshot initial sends, static/dynamic payload builders, client-id registration, claim restore, claim/unclaim, planning chat, battle-log subscriptions, idempotent action acceptance, `_action_states`, `_actions.put(msg)`, and cleanup.

The DM console block builds a local `CombatService`, installs it on `self` and `self.app`, defines `_check_dm_auth`, binds `_dm_console_snapshot`, defines DM HTML loaders, performs `RuntimeSnapshotRequest` reads through route-local threadpool offload, and maps runtime readiness failures to HTTP responses.

The DM mutation/map/session routes mix several authority paths. Some call `_dm_service`; some call direct `self.app` helpers; some submit `RuntimeCommand` instances through `self._runtime.submit_command(...)`; most return post-mutation `_dm_console_snapshot(...)`. This means registration movement must not alter auth token generation, timeout/error handling, queue-backed command behavior, snapshot construction, or response shapes.

The DM `/ws/dm` route is coupled to admin token query auth, `_dm_ws_clients`, `_dm_ws_is_map`, `_ws_send_locks`, tactical snapshot inclusion, serialized send helpers, and subscription messages.

Snapshot warm-up is not route registration but is adjacent to it in `LanController.start()`. `_cached_snapshot` and `_cached_pcs` are seeded after all routes are registered and before `UvicornServerHost.start()`. That order should remain unchanged in any first route-registration seam.

Tk polling is also adjacent. `self.app.after(60, self._tick)` starts after the host starts and should remain legacy-owned until a separate runtime scheduling item exists.

## Future Registration-Only Move

The lowest-risk future route-registration implementation, after host smoke evidence, should not create route modules or move route bodies.

Recommended target shape:

- Keep `create_app(...)` as the app factory for health/readiness and app-state/runtime attachment.
- Add an explicit route-registration contract between package app creation and legacy route registration.
- Extract the current `LanController.start()` registration block into one named registrar seam that accepts the FastAPI app and the `LanController`.
- Keep all handler bodies and local helper closures in legacy ownership for that slice.
- Keep static mounts and middleware in the same relative order.
- Keep `CombatService` setup, `_check_dm_auth`, `_dm_console_snapshot`, WebSocket handlers, queue-backed command submissions, and direct gameplay helpers behaviorally unchanged.
- Keep snapshot warm-up and Tk polling outside the registration contract.
- Keep `UvicornServerHost` hosting an already-registered app.
- Preserve all existing route paths, methods, names, payloads, status mappings, dependency behavior, auth behavior, and response schemas.
- Add focused route-inventory validation in the future implementation item so route count/path/method preservation is testable.

This would move ownership toward the package boundary by making route registration an explicit contract, but it would not claim package ownership of route bodies, runtime authority, queues, WebSockets, snapshots, cache, or gameplay.

## Why Not Implement Route Registration Next

Route-registration extraction would require touching the largest remaining `LanController.start()` region. Even if route bodies stay in place, the extraction is adjacent to static mounts, middleware, WebSockets, queue submission, auth/session handling, DM snapshots, cache warm-up, and Tk polling.

The host-boundary implementation is still only unit-validated in the recorded docs. No live startup/readiness smoke log/debug trace is recorded. That makes another app-host implementation slice premature.

Queue-wait evidence is not the best next slice because no queue behavior changed here and this planning pass did not discover a queue-specific failure signal.

Deploy guidance is not justified because deploy readiness should not be inferred without host-boundary live smoke evidence.

No further migration is acceptable if smoke cannot be captured, but it does not close the known evidence gap.

## Recommended Next Work Item

`WORK-20260701-app-host-runtime-lifecycle-smoke-evidence-capture`

Goal:

Record bounded developer smoke evidence for the existing `UvicornServerHost` boundary after the minimal implementation. The evidence should cover live startup/readiness and representative unchanged routes. It should document whether actual Uvicorn-thread startup and readiness behavior are proven, without changing app code.

Suggested evidence targets, if the developer opens that work:

- startup without dependency errors
- `/health`
- `/api/health`
- `/ready`
- `/api/ready`
- `/dm`
- `/api/dm/combat`
- `/api/dm/combat?workspace=dmcontrol`
- shutdown request behavior if already covered by the developer smoke procedure

This is not a validation command list for this checkpoint. It is a future work-item recommendation only.

## Forbidden Next-Slice Scope

The next slice must forbid route migration, route body movement, route registration changes, `init_tracker_server/routes/` creation, app factory behavior changes, launch command changes, lifespan/readiness behavior changes, Uvicorn host changes, snapshot warm-up changes, cache ownership/TTL/schema/payload/static hydration changes, WebSocket behavior changes, queue behavior changes, async command acceptance changes, command semantic changes, auth/claims/reconnect/session behavior changes, player-command route work, combat mutation route work, tactical/map gameplay route work, production topology changes, deploys, restarts, SSH, commits, and pushes.

For smoke evidence capture, app code and tests should remain unchanged.

