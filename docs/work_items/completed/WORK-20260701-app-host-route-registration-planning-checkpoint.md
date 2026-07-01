# WORK-20260701-app-host-route-registration-planning-checkpoint

Status: Completed

## Goal

Complete a bounded docs/evidence planning checkpoint for route-registration ownership after the package host boundary.

This checkpoint mapped current route-registration ownership, route group coupling, a future package-boundary route-registration shape, and whether route-registration ownership implementation is the safest next slice.

This was a docs/evidence checkpoint only. No app code, tests, route registration, route bodies, app factory behavior, launch commands, lifespan behavior, readiness behavior, `UvicornServerHost`, snapshot warm-up, cache ownership, response payloads, WebSocket behavior, queue behavior, command semantics, persistence, production topology, deploys, commits, pushes, SSH, or gameplay behavior were changed.

## Files Inspected

- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260701-app-host-runtime-lifecycle-post-implementation-checkpoint.md`
- `docs/planning/living_docs/server_runtime_app_host_lifecycle_post_implementation_checkpoint_20260701.md`
- `docs/work_items/completed/WORK-20260701-app-host-runtime-lifecycle-minimal-implementation.md`
- `docs/work_items/completed/WORK-20260701-app-host-runtime-lifecycle-checkpoint.md`
- `docs/planning/living_docs/server_runtime_app_host_lifecycle_checkpoint_20260701.md`
- `init_tracker_server/app.py`
- `server_app.py`
- `init_tracker_server/host.py`
- `dnd_initative_tracker.py`, limited to route registration, `create_app` use, `LanController.start()`, and `LanController.stop()` seams

No old plans, `majorTODO.md`, runtime reports, historical notes, app source outside the named files, tests, production files, browser assets, `docs/bug_reports/inbox/BUG-20260626-dmcontrol-terrain-not-visible.md`, or `logs/context/` were inspected.

## Files Changed

- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260701-app-host-route-registration-planning-checkpoint.md`
- `docs/planning/living_docs/server_runtime_app_host_route_registration_planning_checkpoint_20260701.md`

The active work item copy was opened and removed as part of the ledger transition from active to completed.

## Planning Decision

Route-registration ownership implementation is not the safest immediate next implementation slice.

The future move is plausible, but only as a registration-only seam that preserves the current route bodies and behavior. The immediate blocker is evidence, not design: the previous `UvicornServerHost` implementation still has no recorded live server smoke log/debug trace. Route registration touches the largest remaining `LanController.start()` surface, including WebSockets, queue-backed command submission, admin/session auth, static mounts, route-local helper closures, DM snapshot/cache reads, and initial LAN snapshot seeding adjacency. That is too much blast radius to change before proving the new host boundary under live startup/readiness conditions.

Recommended next work item:

`WORK-20260701-app-host-runtime-lifecycle-smoke-evidence-capture`

That next item should be evidence-only. It should record developer smoke for startup/readiness and key unchanged routes after `UvicornServerHost`. It should not move route registration or route bodies.

Queue-wait evidence is deferred because this checkpoint found no new queue-wait behavior. Deploy guidance is deferred until host-boundary smoke evidence exists. No further migration for now is acceptable if smoke evidence is not available, but the best next bounded work is still smoke evidence capture.

## Current Route Registration Ownership

Package-owned today:

- `init_tracker_server.app.create_app(...)` creates the FastAPI app.
- `init_tracker_server.app.app_lifespan(...)` toggles readiness and calls `runtime.start()` / `runtime.shutdown()`.
- `create_app(...)` initializes `app.state.ready`, `app.state.lan_controller`, and `app.state.runtime`.
- `create_app(...)` registers only `/health`, `/api/health`, `/ready`, and `/api/ready`.

Compatibility shim:

- `server_app.py` only re-exports `app_lifespan` and `create_app` from `init_tracker_server.app`.

Package host boundary:

- `init_tracker_server.host.UvicornServerHost` accepts an already-created and already-registered ASGI app.
- It owns Uvicorn config/server/thread mechanics and stop request.
- It does not create the app, mount static assets, register routes, seed snapshots, own queues, own WebSockets, or own runtime/gameplay authority.

Legacy-owned today:

- `LanController.start()` imports FastAPI dependencies, imports `create_app` through the shim, calls `create_app(lan_controller=self)`, mirrors `self._runtime`, registers middleware, mounts static assets, defines route-local helper closures, registers all non-health routes, seeds `_cached_snapshot` / `_cached_pcs`, delegates host startup to `UvicornServerHost`, and starts Tk polling.
- `LanController.stop()` requests stop through `self._server_host.request_stop()` when present and keeps the legacy `_uvicorn_server.should_exit` fallback.

## Coupled Registration Blocks

Dependency, middleware, static, and helper setup in `LanController.start()` is coupled to lazy FastAPI imports, module-level type resolver globals, `server_runtime` command constants, current request path tracking, debug tracing, static asset paths, profile picture cache sync, HTML shell validation, and no-cache headers.

Page, static shell, rules, admin, LAN-log, client-log, spell, shop, and character API routes are coupled to `self.cfg`, host allowlist checks, admin token state, push subscriptions, YAML/spell/shop/character helpers on `self.app`, assigned-character host identity, and the existing `self._runtime.submit_command(...)` path for spell color.

The player `/ws` route is tightly coupled to `LanController` WebSocket state: `_clients`, `_ws_send_locks`, `_clients_meta`, `_client_hosts`, `_claims`, client-id reconnect maps, claim revisions, `_cached_snapshot`, `_cached_pcs`, static/dynamic payload builders, battle-log subscribers, planning chat state, `_actions`, `_action_states`, and Tk-thread processing through the existing polling path.

DM console setup and `GET /api/dm/combat` are coupled to local `CombatService` construction, `_check_dm_auth`, route-local `_dm_console_snapshot`, `RuntimeSnapshotRequest`, `_dm_combat_read_snapshot_in_threadpool(...)`, route-local tactical serialization, runtime readiness error mapping, and legacy DM snapshot/cache ownership.

DM combat, encounter, monster capability, tactical map, structures, ships, boarding links, AoE, overlays, combatant, and session routes are coupled to admin/session auth, direct `self.app` gameplay/service helpers, `_dm_service`, `self._runtime.submit_command(...)` for migrated queue-backed commands, command timeout/error mapping, and post-mutation `_dm_console_snapshot(...)` payloads.

The DM `/ws/dm` route is coupled to admin token query auth, `_dm_ws_clients`, `_dm_ws_is_map`, `_ws_send_locks`, route-local DM snapshot building, tactical-map subscription state, and serialized WebSocket send helpers.

The post-registration section is adjacent to snapshot warm-up and runtime hosting: `LanController.start()` seeds `_cached_snapshot` and `_cached_pcs` before passing the already-registered app to `UvicornServerHost`, then starts Tk polling with `self.app.after(60, self._tick)`.

## Safe Future Route-Registration Shape

A safe future move should separate registration orchestration from route-body movement.

The smallest plausible route-registration implementation after smoke evidence would be:

- Preserve `init_tracker_server.app.create_app(...)` health/readiness behavior and app-state initialization.
- Keep route bodies and route-local helper closures in legacy ownership for the slice.
- Extract the legacy registration block out of `LanController.start()` into one named registrar seam that accepts the already-created app and the `LanController` instance.
- Let the package boundary call or coordinate that registrar explicitly, so package-owned app creation can see route registration as a contract without owning route bodies yet.
- Preserve route registration order: middleware, static mounts, page/static routes, general APIs, player WebSocket, DM routes, DM WebSocket.
- Keep snapshot warm-up outside route registration for now; it should remain legacy-owned and run after registration and before host startup.
- Keep `UvicornServerHost` accepting an already-registered app.
- Do not create `init_tracker_server/routes/` or move route bodies in the first slice.
- Add route-inventory/registration tests only in a separately authorized implementation item.

The future seam should prove route inventory preservation before and after extraction. It should not change route paths, methods, dependency behavior, response payloads, HTTP status mappings, auth/session behavior, WebSocket state, queue behavior, runtime command semantics, cache behavior, static hydration, or gameplay authority.

## Not Next

Route-registration implementation is not selected next because host-boundary live smoke evidence is still missing and the registration block has high coupling.

Queue-wait evidence is not selected next because this planning pass did not find a new queue-wait signal or queue behavior change.

Deploy guidance is not selected next because the prior host-boundary implementation changed startup mechanics and has no recorded live smoke evidence.

No further migration is not the strongest recommendation, because the package-boundary route-registration problem remains real. It is acceptable only if developer smoke evidence cannot be captured now.

## Required Forbidden Scope For The Next Slice

The next slice must explicitly forbid:

- app code edits
- test edits unless the developer opens a separate implementation item
- route registration changes
- route body movement
- `init_tracker_server/routes/` creation
- app factory behavior changes
- launch command changes
- lifespan/readiness behavior changes
- `UvicornServerHost` changes
- snapshot warm-up, cache ownership, TTL, schema, payload, static hydration, or response changes
- WebSocket behavior changes
- queue behavior, queue-wait, async command acceptance, and command semantic changes
- auth/claims/reconnect/session behavior changes
- player-command routes, combat mutation routes, tactical/map gameplay routes, AoE/structure/ship/boarding-link work
- production deploys, restarts, SSH, topology changes, commits, and pushes

For the recommended smoke-evidence item, the only allowed output should be docs/evidence updates using developer-provided or developer-run smoke output.

## Ledger Update

`docs/work_items/current_work.md` was returned to Idle with no active work item. The completed table now includes this checkpoint.

Allowed next action is to open `WORK-20260701-app-host-runtime-lifecycle-smoke-evidence-capture` as evidence-only, or to stop migration work until that smoke evidence is available.

## Validation

Required validation commands:

- `git status --short`
- `timeout 10s git diff --check`

Results are recorded in the final agent report.

