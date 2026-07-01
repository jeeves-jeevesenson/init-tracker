# Server Runtime App-Host Lifecycle Deploy Guidance Checkpoint - 2026-07-01

## Status

Checkpoint/evidence document only. This document does not authorize app implementation, test edits, log edits, route registration changes, route body movement, app factory behavior changes, launch command changes, lifespan behavior changes, readiness behavior changes, Uvicorn host changes, snapshot warm-up changes, cache ownership changes, response payload changes, WebSocket behavior changes, queue behavior changes, command semantic changes, production operations, deploys, commits, pushes, SSH, service restarts, topology changes, or gameplay behavior changes.

## Decision Summary

Developer-approved deploy guidance is justified for the package host-boundary slice.

The previous deploy-guidance blocker was missing live `UvicornServerHost` startup/browser-route evidence. The smoke evidence capture now records live headless startup, LAN server hoist on port `8787`, `/` and `/dm` serving, representative `/api/dm/combat` HTTP 200 responses, browser WebSocket claim/unclaim/restored-claim/disconnect activity, debug trace creation, and shutdown logging.

This is deploy guidance only. It is not a deploy authorization, not a production command plan for agents, not route-registration approval, and not a blanket claim that every production recovery gate is complete.

## Candidate Scope

The current host-boundary candidate history observed from Git metadata includes:

- `ba4fe0f` - lifecycle checkpoint selecting the minimal host boundary
- `14932cb` - minimal implementation adding `init_tracker_server.host.UvicornServerHost`
- `c535c64` - ledger cleanup with no app behavior change
- `a97bbd7` - post-implementation checkpoint
- `8757e59` - route-registration planning checkpoint
- `fa92cc3` - live host smoke evidence capture

The host-boundary app behavior change is `14932cb`: move Uvicorn config/server/thread/stop-request mechanics into the package host boundary while preserving the broader legacy runtime surface.

The Orchestrator/developer must still verify the exact approved branch, final commit, and production baseline before any deploy.

## Evidence Basis

Implementation validation already recorded:

- Python compile passed for edited/adjacent server files.
- `tests/test_server_host.py` passed.
- `tests/test_server_runtime.py` passed.
- `timeout 10s git diff --check` passed after the implementation docs update.

Smoke evidence now recorded:

- Headless tracker started.
- Debug trace was written to `logs/debug-trace-20260701-155344.jsonl`.
- DM operator surface was advertised at `/dm`.
- Player LAN surface was advertised at `/`.
- LAN server hoisted on port `8787`.
- Browser WebSocket sessions connected.
- Claim, unclaim, restored-claim, and disconnect activity was recorded.
- `GET /`, `GET /dm`, `GET /api/dm/combat`, and `GET /api/dm/combat?workspace=dmcontrol` returned HTTP 200 in representative trace evidence.
- Shutdown logging was recorded.

Runbook evidence:

- `docs/agent_ops/production_update_runbook.md` exists.
- It requires developer approval for production updates.
- It forbids agents from deploying, restarting services, or pushing code unless explicitly instructed.
- It requires approved branch/commit verification, production backup, bounded validation, and developer-owned browser smoke.
- It states environment-specific production details belong in local gitignored docs, not tracked guidance.

Recovery constraint evidence:

- `docs/production_recovery_living_doc_20260526.md` still treats stable deployment, browser smoke, core workflow verification, and responsiveness as production-readiness constraints.
- This checkpoint does not reopen old recovery gates and does not claim every gate is complete.

## Intentionally Preserved Behavior

The deploy candidate intentionally preserved:

- app creation and health/readiness routes in `init_tracker_server.app`
- lifespan readiness toggling and runtime start/shutdown behavior
- `server_app.py` compatibility shim behavior
- all non-health route registration in `LanController.start()`
- route bodies, middleware, static mounts, and route-local helper closures
- route-local DM-combat read offload and tactical serialization
- initial snapshot warm-up and legacy cache ownership
- snapshot schemas, response payloads, TTLs, and static hydration behavior
- launch commands and `serve_headless.py` behavior
- WebSocket behavior, auth, claims, reconnect, and hidden-information handling
- queue behavior, command semantics, and async command acceptance behavior
- Tk polling, persistence, shutdown join/cancellation semantics, and gameplay authority

Deploy must not alter these.

## Remaining Risks

Snapshot/LAN hot-path latency remains the main known technical risk. The live smoke recorded `_lan_snapshot` slow spans around `391-398 ms`. Earlier post-offload evidence recorded tactical `/api/dm/combat?workspace=dmcontrol` p95 around `791 ms` and max around `1093 ms`, while health/readiness and plain combat routes were not locked in the same slow path.

This latency risk is separate from host/server lifecycle ownership. The smoke evidence supports the host boundary, not broad read-model performance closure.

Route-registration extraction remains deferred. The live smoke did not move registration, did not compare route inventories after extraction, and did not reduce the coupling in `LanController.start()`.

Production details remain developer-controlled. The tracked runbook is sanitized; any real deploy must use approved local production details and must not guess hostnames, accounts, paths, ports beyond the documented app behavior, credentials, service model, or topology.

## Deploy Guidance Decision

Deploy guidance is justified now.

More evidence is not required before handing deploy-prep guidance to the Orchestrator/developer because the missing host-boundary live smoke gap is closed.

Actual deploy remains blocked until the developer explicitly approves it and the runbook pre-checks are complete.

The developer may still request a bounded snapshot/LAN hot-path wait evidence checkpoint before deploy approval if they want stronger latency proof.

## Pre-Deploy Checks To Request

Before any real deploy, request confirmation of:

1. Developer approval for the exact production deploy or deploy-prep action.
2. Approved branch and exact commit range against the production baseline.
3. Inclusion of the host-boundary app change commit `14932cb` and smoke evidence commit `fa92cc3`, plus any follow-up docs commit the developer wants included.
4. Clean staging/worktree for deploy purposes, excluding unrelated bug inbox files, `logs/context/`, smoke logs, and debug traces unless explicitly approved.
5. Recorded local validation or developer-approved fresh equivalent for Python compile, `tests/test_server_host.py`, `tests/test_server_runtime.py`, and `timeout 10s git diff --check`.
6. Acceptance of the recorded smoke evidence or an explicit request for fresh smoke.
7. Presence of `docs/agent_ops/production_update_runbook.md`.
8. Availability of developer-controlled local production details for host/account/path/venv/log/process/rollback information.
9. A backup plan for the current production app before changes.
10. A bounded post-update validation plan covering startup, health/readiness, `/`, `/dm`, `/api/dm/combat`, `/api/dm/combat?workspace=dmcontrol`, browser claim/reconnect behavior, logs, and rollback criteria.
11. A named developer browser-smoke owner.
12. No agent-run production command, SSH, restart, push, topology change, or deploy unless a separate task explicitly authorizes it.

## Do Not Change During Deploy

Do not combine deploy prep with route registration, route migration, route body movement, `init_tracker_server/routes/` creation, broader threadpool/offload work, facade-owned cache, TTL changes, snapshot schema changes, static hydration changes, payload changes, WebSocket changes, auth/claims/reconnect changes, queue-wait behavior, async command semantics, launch command changes, lifespan/readiness changes, shutdown semantics, tactical/LAN lower-level work, player-command routes, combat mutation routes, AoE/structure/ship/boarding-link work, or gameplay behavior.

Deploy should be only the developer-approved application update using the existing runbook and approved branch.

## Recommended Next Work

No app implementation is recommended before deploy-guidance handoff.

The next action should be Orchestrator/developer deploy-prep review, or pause/no further migration.

Secondary option if the developer wants more latency proof before deploy approval:

`WORK-20260701-snapshot-lan-hot-path-wait-evidence-checkpoint`

That checkpoint should be evidence-only and limited to snapshot/LAN hot-path wait behavior.
