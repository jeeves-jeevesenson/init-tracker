# WORK-20260701-app-host-runtime-lifecycle-smoke-evidence-capture

Status: Completed

## Goal

Open and complete a bounded evidence-only work item recording live `UvicornServerHost` smoke evidence after the package host boundary and route-registration planning checkpoint.

This checkpoint decides whether the smoke closes the live host-boundary evidence gap identified by `WORK-20260701-app-host-route-registration-planning-checkpoint`, what behavior the smoke proves still works, what latency evidence remains, and what the next safe repo action should be.

This was docs/evidence capture only. No app code, tests, logs, route registration, route bodies, app factory behavior, launch commands, lifespan behavior, readiness behavior, `UvicornServerHost`, snapshot warm-up, cache ownership, TTLs, response payloads, WebSocket behavior, queue behavior, command semantics, persistence, production topology, deploys, commits, pushes, SSH, service restarts, or gameplay behavior were changed.

## Files Inspected

- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260701-app-host-route-registration-planning-checkpoint.md`
- `docs/planning/living_docs/server_runtime_app_host_route_registration_planning_checkpoint_20260701.md`
- `logs/smoke/WORK-20260701-app-host-runtime-lifecycle-smoke-evidence-capture_smoke-server_20260701-155344.log`, using only `head`, `tail`, and `sed`
- `logs/debug-trace-20260701-155344.jsonl`, using only `head`, `tail`, and `sed`
- `docs/work_items/completed/WORK-20260701-app-host-runtime-lifecycle-minimal-implementation.md`
- `docs/work_items/completed/WORK-20260701-app-host-runtime-lifecycle-post-implementation-checkpoint.md`
- `docs/planning/living_docs/server_runtime_app_host_lifecycle_post_implementation_checkpoint_20260701.md`

No app source, tests, browser assets, production files, `majorTODO.md`, old runtime reports, old plans, `docs/bug_reports/inbox/BUG-20260626-dmcontrol-terrain-not-visible.md`, or `logs/context/` were edited.

## Files Changed

- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260701-app-host-runtime-lifecycle-smoke-evidence-capture.md`
- `docs/planning/living_docs/server_runtime_app_host_lifecycle_smoke_evidence_capture_20260701.md`

No active work item copy was left after completion.

## Evidence Files

Smoke log:

`logs/smoke/WORK-20260701-app-host-runtime-lifecycle-smoke-evidence-capture_smoke-server_20260701-155344.log`

Debug trace:

`logs/debug-trace-20260701-155344.jsonl`

Both required evidence files existed. No substitute evidence was invented.

## Smoke Evidence Recorded

The smoke log records live headless startup:

- `Headless tracker started.`
- Debug trace path: `logs/debug-trace-20260701-155344.jsonl`.
- DM operator surface advertised at `/dm`.
- Player LAN surface advertised at `/`.
- LAN server hoisted at `http://10.3.25.235:8787/`.

The smoke log records browser WebSocket activity:

- Two LAN browser sessions connected at `15:54:39`.
- A session claimed John Twilight, unclaimed John Twilight, then claimed Johnny Morris.
- Later sessions restored the Johnny Morris claim, unclaimed, claimed Old Man, restored Old Man, and disconnected.

The debug trace records representative HTTP route behavior:

- `GET /` returned HTTP 200 with route durations around `20.976 ms` and `9.724 ms`.
- `GET /dm` returned HTTP 200 with route durations around `4.931 ms` and `2.779 ms`.
- `GET /api/dm/combat` returned HTTP 200 without `workspace` early in the smoke.
- `GET /api/dm/combat?workspace=dmcontrol` returned HTTP 200; the final recorded workspace request completed in about `33.512 ms`.

The final traced workspace request records:

- `_dm_console_snapshot_payload`: about `24.610 ms`.
- `_dm_console_snapshot`: about `24.841 ms`.
- `GET /api/dm/combat?workspace=dmcontrol`: HTTP 200, about `33.512 ms`.

The debug trace also records remaining LAN snapshot hot-path latency:

- `_lan_snapshot`: `391.315 ms`, marked `slow.span`.
- `_lan_snapshot`: `398.044 ms`, marked `slow.span`.

The smoke log records shutdown:

- `LAN server be lowerin' sails (stoppin').`

## Decision

This smoke closes the live `UvicornServerHost` evidence gap identified by the route-registration planning checkpoint.

The previous gap was that the minimal host-boundary implementation had only no-socket unit evidence. This smoke now proves the package host boundary can run a live headless server, hoist the LAN service on port 8787, serve the DM and player browser surfaces, serve representative DM combat routes, support browser WebSocket claim/reclaim/disconnect activity, write debug traces, and log shutdown.

The smoke does not prove route-registration extraction is safe. It does not move routes, does not inventory route preservation after an extraction, and does not reduce the coupling documented in the route-registration planning checkpoint.

The smoke also does not prove snapshot/LAN hot paths are cheap. The remaining slow evidence is still read-model/snapshot behavior, especially `_lan_snapshot`, not host/server lifecycle ownership.

## Decision Questions

Does this smoke close the live `UvicornServerHost` evidence gap?

Yes. It closes the live startup/browser-route evidence gap left by the minimal host-boundary implementation and recorded by the route-registration planning checkpoint. It should be treated as smoke support for the host-boundary slice, not as a broader performance, route-registration, or production-deploy proof.

What behavior did smoke prove still works after the package host boundary?

Live headless startup, debug trace creation, LAN server hoist on port 8787, player `/` serving, DM `/dm` serving, DM combat HTTP serving, browser WebSocket connections, claim/unclaim/restored-claim flows, disconnect cleanup logging, and stop-request logging all still work in the observed smoke.

What remaining latency/hot-path evidence should be recorded?

The next latency evidence, if needed, should target snapshot/LAN hot-path wait behavior. The relevant spans are `_lan_snapshot` slow spans around `391-398 ms`, plus the broader known tactical workspace read-model path from earlier docs. This smoke does not show a new queue-wait failure, so queue behavior should not be changed from this evidence alone.

Does the evidence justify route-registration implementation next?

No. The smoke removes the host-boundary live evidence blocker, but route registration remains the largest coupled legacy server surface. The route-registration planning checkpoint already found that any future move must be registration-only and must preserve route bodies, payloads, WebSockets, queue behavior, auth/claims/reconnect, snapshot/cache ownership, and gameplay authority. This smoke does not add route-inventory or extraction safety evidence.

Should the next safe action be deploy guidance, queue/snapshot wait evidence, route-registration implementation planning, or no further migration work for now?

The next safe repo action should be deploy guidance as docs/evidence only. The reason is narrow: deploy guidance was previously deferred because live host-boundary smoke was missing, and that evidence now exists. A bounded snapshot/LAN hot-path wait evidence checkpoint is a secondary option only if the developer wants more latency proof before deploy guidance. Route-registration implementation is not next. No further migration work for now is also safe if the developer chooses to pause.

What exact next work item should be recommended?

`WORK-20260701-app-host-runtime-lifecycle-deploy-guidance-checkpoint`

Recommended goal:

Prepare docs/evidence-only deploy guidance for the smoke-supported `UvicornServerHost` host-boundary slice, using the current production runbook and local production-environment documentation if the developer opens that item. The checkpoint must not deploy, restart services, SSH, change production topology, move routes, edit app code, change payloads, change cache/queue/WebSocket behavior, or implement route registration.

## Deferred Scope

Deferred unless a separate active work item explicitly authorizes it:

- app implementation
- test edits
- log edits
- route registration changes
- route body movement
- `init_tracker_server/routes/` creation
- app factory behavior changes
- launch command changes
- lifespan/readiness behavior changes
- `UvicornServerHost` changes
- snapshot warm-up, cache ownership, TTL, schema, payload, or static hydration changes
- WebSocket behavior changes
- queue behavior, queue-wait, async command acceptance, and command semantic changes
- auth/claims/reconnect/session behavior changes
- player-command routes, combat mutation routes, tactical/map gameplay routes, AoE/structure/ship/boarding-link work
- production deploys, restarts, SSH, topology changes, commits, and pushes

## Ledger Update

`docs/work_items/current_work.md` was returned to Idle with no active work item.

The completed table now includes this work item. The allowed next action is to open `WORK-20260701-app-host-runtime-lifecycle-deploy-guidance-checkpoint` as docs/evidence only, pause/no further migration work, or open a bounded snapshot/LAN hot-path wait evidence checkpoint only if the developer wants more latency proof before deploy guidance.

## Validation

Required validation commands:

- `git status --short`
- `timeout 10s git diff --check`

Results are recorded in the final agent report.
