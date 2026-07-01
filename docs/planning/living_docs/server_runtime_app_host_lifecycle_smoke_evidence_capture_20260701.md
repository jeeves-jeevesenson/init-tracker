# Server Runtime App-Host Lifecycle Smoke Evidence Capture - 2026-07-01

## Status

Checkpoint/evidence document only. This document does not authorize app implementation, test edits, log edits, route registration changes, route body movement, app factory behavior changes, launch command changes, lifespan behavior changes, readiness behavior changes, Uvicorn host changes, snapshot warm-up changes, cache ownership changes, response payload changes, WebSocket behavior changes, queue behavior changes, command semantic changes, production operations, deploys, commits, pushes, SSH, service restarts, or gameplay behavior changes.

## Decision Summary

Live `UvicornServerHost` smoke evidence is now captured.

The evidence closes the host-boundary live startup/browser-route gap left by `WORK-20260701-app-host-runtime-lifecycle-minimal-implementation` and identified again by `WORK-20260701-app-host-route-registration-planning-checkpoint`.

The smoke proves the existing host-boundary slice is smoke-supported. It does not justify route-registration implementation next. Remaining slow evidence points at snapshot/LAN hot-path behavior, not host/server lifecycle ownership.

Recommended next work item:

`WORK-20260701-app-host-runtime-lifecycle-deploy-guidance-checkpoint`

That next item should be docs/evidence only and must not deploy or change production topology. A bounded snapshot/LAN hot-path wait evidence checkpoint is a secondary option only if the developer wants more latency proof before deploy guidance.

## Evidence Inspected

Documents inspected:

- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260701-app-host-route-registration-planning-checkpoint.md`
- `docs/planning/living_docs/server_runtime_app_host_route_registration_planning_checkpoint_20260701.md`
- `docs/work_items/completed/WORK-20260701-app-host-runtime-lifecycle-minimal-implementation.md`
- `docs/work_items/completed/WORK-20260701-app-host-runtime-lifecycle-post-implementation-checkpoint.md`
- `docs/planning/living_docs/server_runtime_app_host_lifecycle_post_implementation_checkpoint_20260701.md`

Evidence logs inspected:

- `logs/smoke/WORK-20260701-app-host-runtime-lifecycle-smoke-evidence-capture_smoke-server_20260701-155344.log`
- `logs/debug-trace-20260701-155344.jsonl`

The log inspections used only `head`, `tail`, and `sed` excerpts. The logs were not edited.

## Smoke Facts

The smoke log records:

- headless tracker startup
- debug trace creation at `logs/debug-trace-20260701-155344.jsonl`
- DM operator surface advertised at `/dm`
- player LAN surface advertised at `/`
- LAN server hoisted at port `8787`
- browser WebSocket sessions connected
- claim, unclaim, restored-claim, and disconnect activity
- shutdown logged as `LAN server be lowerin' sails (stoppin').`

The debug trace records:

- `GET /` HTTP 200
- `GET /dm` HTTP 200
- `GET /api/dm/combat` HTTP 200
- `GET /api/dm/combat?workspace=dmcontrol` HTTP 200
- final workspace route duration about `33.512 ms`
- `_dm_console_snapshot_payload` duration about `24.610 ms`
- `_dm_console_snapshot` duration about `24.841 ms`
- `_lan_snapshot` slow spans around `391.315 ms` and `398.044 ms`

## What The Smoke Proves

The live smoke proves actual headless startup and Uvicorn-thread hosting worked after the `UvicornServerHost` boundary.

It proves representative browser and API behavior still worked in the observed smoke:

- player page serving
- DM operator page serving
- DM combat route serving
- browser WebSocket connections
- claim/unclaim/restored-claim flows
- disconnect cleanup logging
- debug trace writing
- shutdown request logging

This is the missing live evidence that the earlier no-socket unit tests could not provide.

## What The Smoke Does Not Prove

The smoke does not prove route-registration extraction safety. It does not move route registration, extract route bodies, compare route inventories before and after extraction, or reduce the route-registration coupling already documented in the route-registration planning checkpoint.

The smoke does not prove snapshot/LAN hot paths are cheap. `_lan_snapshot` still produced slow spans around `391-398 ms`, and earlier completed docs already identified the tactical/LAN snapshot chain as the remaining read-model latency area.

The smoke does not prove queue-wait behavior is a current failure. It includes browser claim activity and DM combat reads, but it does not isolate queue-backed command wait time or justify changing queue semantics.

The smoke does not authorize deploys. It supports a deploy-guidance checkpoint only.

## Route-Registration Decision

Do not proceed directly to route-registration implementation.

The route-registration planning checkpoint remains valid: the future safe shape is registration-only, preserves route bodies, and must protect auth/session behavior, WebSockets, queues, snapshot/cache ownership, payloads, response statuses, hidden information, and gameplay authority.

The new smoke evidence removes one blocker, but it does not create route-inventory proof or extraction safety proof. Route-registration implementation would still be a high-blast-radius ownership move and should not be the next repo action.

## Remaining Latency Evidence

The remaining evidence target is snapshot/LAN hot-path wait behavior.

Known evidence from this smoke:

- final `GET /api/dm/combat?workspace=dmcontrol` returned HTTP 200 in about `33.512 ms`
- `_dm_console_snapshot_payload` and `_dm_console_snapshot` were about `24-25 ms`
- `_lan_snapshot` still had slow standalone spans around `391-398 ms`

If the developer wants latency proof before deploy guidance, the bounded next checkpoint should record whether snapshot/LAN wait behavior is still only localized read-model latency or whether it creates user-visible or server-wide responsiveness risk. It should not change snapshot schemas, cache ownership, TTLs, threadpool usage, queue behavior, payloads, or gameplay behavior.

## Recommended Next Work Item

`WORK-20260701-app-host-runtime-lifecycle-deploy-guidance-checkpoint`

Recommended goal:

Complete a docs/evidence-only deploy-guidance checkpoint for the smoke-supported `UvicornServerHost` host-boundary slice. The checkpoint should use the current production runbook and local production-environment documentation if opened, decide whether the host-boundary slice is ready for developer-controlled deploy guidance, and explicitly preserve the ban on deploys, restarts, SSH, production topology changes, app code edits, route changes, cache changes, payload changes, WebSocket changes, queue changes, and gameplay changes.

Secondary option:

`WORK-20260701-snapshot-lan-hot-path-wait-evidence-checkpoint`

Use this only if the developer wants more latency evidence before deploy guidance. It should be evidence-only and bounded to the observed snapshot/LAN hot-path wait signal.

## Deferred Scope

Deferred unless a separate active work item explicitly authorizes it:

- route-registration implementation
- route body movement
- `init_tracker_server/routes/` creation
- app implementation
- test edits
- log edits
- app factory, launch command, lifespan, readiness, or `UvicornServerHost` changes
- snapshot warm-up, cache ownership, TTL, schema, payload, or static hydration changes
- queue behavior, queue-wait behavior, async command acceptance semantics, or command semantics changes
- WebSocket, auth, claims, reconnect, hidden-information, persistence, or gameplay behavior changes
- deploys, restarts, SSH, service changes, production topology changes, commits, or pushes
