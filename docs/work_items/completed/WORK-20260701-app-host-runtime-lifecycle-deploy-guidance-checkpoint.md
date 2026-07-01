# WORK-20260701-app-host-runtime-lifecycle-deploy-guidance-checkpoint

Status: Completed

## Goal

Complete a bounded docs/evidence-only deploy-guidance checkpoint for the package host boundary migration through the live smoke evidence capture.

This checkpoint decides whether the current pushed migration state is ready for developer-approved deploy guidance, what evidence supports it, what risks remain, and what exact deploy-prep guidance should be handed back to the Orchestrator/developer.

This checkpoint did not deploy, restart services, SSH, alter production topology, push, commit, edit app code, edit tests, edit logs, change route registration, move route bodies, create `init_tracker_server/routes/`, change launch commands, change lifespan/readiness behavior, change `UvicornServerHost`, change snapshot warm-up, change cache ownership, change snapshot schemas, change response payloads, change static hydration, change WebSocket behavior, change auth/claims/reconnect, change queue behavior, change command semantics, change persistence, change shutdown join/cancellation semantics, or change gameplay behavior.

## Files Inspected

- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260701-app-host-runtime-lifecycle-smoke-evidence-capture.md`
- `docs/planning/living_docs/server_runtime_app_host_lifecycle_smoke_evidence_capture_20260701.md`
- `docs/work_items/completed/WORK-20260701-app-host-route-registration-planning-checkpoint.md`
- `docs/planning/living_docs/server_runtime_app_host_route_registration_planning_checkpoint_20260701.md`
- `docs/work_items/completed/WORK-20260701-app-host-runtime-lifecycle-post-implementation-checkpoint.md`
- `docs/work_items/completed/WORK-20260701-app-host-runtime-lifecycle-minimal-implementation.md`
- `docs/agent_ops/production_update_runbook.md`
- `docs/production_recovery_living_doc_20260526.md`, limited to existing deploy/recovery constraints
- `git log --oneline -n 20`, only to identify current candidate commit metadata

No app source, tests, browser assets, logs, production config, `majorTODO.md`, old plans, old reports, broad repo search, `docs/bug_reports/inbox/BUG-20260626-dmcontrol-terrain-not-visible.md`, or `logs/context/` was inspected or edited.

## Files Changed

- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260701-app-host-runtime-lifecycle-deploy-guidance-checkpoint.md`
- `docs/planning/living_docs/server_runtime_app_host_lifecycle_deploy_guidance_checkpoint_20260701.md`

The active work item copy was opened and removed as part of the active-to-completed ledger transition.

## Deploy Candidate Scope

Within the package host-boundary scope, the current pushed candidate history inspected from `git log --oneline -n 20` includes:

- `ba4fe0f` - `WORK-20260701-app-host-runtime-lifecycle-checkpoint: select minimal host boundary`
- `14932cb` - `WORK-20260701-app-host-runtime-lifecycle-minimal-implementation: add package host boundary`
- `c535c64` - `ITR-20260701-ledger-cleanup: clear completed host lifecycle action`
- `a97bbd7` - `WORK-20260701-app-host-runtime-lifecycle-post-implementation-checkpoint: select route registration planning`
- `8757e59` - `WORK-20260701-app-host-route-registration-planning-checkpoint: select smoke evidence capture`
- `fa92cc3` - `WORK-20260701-app-host-runtime-lifecycle-smoke-evidence-capture: record live host smoke`

The only app-behavior implementation commit in that host-boundary sequence is `14932cb`. It added package-owned `init_tracker_server.host.UvicornServerHost` for Uvicorn config/server/thread/stop-request mechanics and delegated `LanController.start()` / `stop()` to it.

The deploy-guidance checkpoint itself is not committed by this agent. The Orchestrator/developer must verify the exact approved branch, final commit, and production baseline before any real deploy.

## Supporting Evidence

Implementation validation recorded by `WORK-20260701-app-host-runtime-lifecycle-minimal-implementation`:

- `py_compile` passed for edited and adjacent Python files.
- `tests/test_server_host.py` passed with faked Uvicorn, event loop creation, and thread creation.
- `tests/test_server_runtime.py` passed after the implementation.
- `timeout 10s git diff --check` passed after the implementation docs update.

Post-implementation checkpoint evidence:

- `UvicornServerHost` moved only Uvicorn config/server/thread/start-stop mechanics out of legacy ownership.
- Route registration, route bodies, app factory ownership, launch commands, lifespan behavior, snapshot warm-up/cache ownership, Tk polling, queue behavior, WebSocket behavior, auth/claims/reconnect, hidden-information handling, persistence, and gameplay authority were preserved.
- Deploy guidance was deferred at that time only because no live host-boundary smoke log/debug trace was recorded yet.

Route-registration planning evidence:

- Route registration remains legacy-owned in `LanController.start()` except for package-owned health/readiness routes in `init_tracker_server.app.create_app(...)`.
- Any future route-registration move must be registration-only and preserve route bodies, payloads, auth/session behavior, WebSockets, queues, snapshot/cache ownership, and gameplay authority.
- Route-registration implementation was explicitly not selected as the next action.

Live smoke evidence recorded by `WORK-20260701-app-host-runtime-lifecycle-smoke-evidence-capture`:

- Headless tracker startup was recorded.
- Debug trace creation was recorded at `logs/debug-trace-20260701-155344.jsonl`.
- DM operator surface was advertised at `/dm`.
- Player LAN surface was advertised at `/`.
- LAN server was hoisted on port `8787`.
- Browser WebSocket sessions connected.
- Claim, unclaim, restored-claim, and disconnect activity was recorded.
- `GET /`, `GET /dm`, `GET /api/dm/combat`, and `GET /api/dm/combat?workspace=dmcontrol` returned HTTP 200 in representative trace evidence.
- Shutdown logging was recorded.

Production guidance evidence:

- `docs/agent_ops/production_update_runbook.md` exists and states that developer approval is required before production updates, agents must not deploy/restart/push unless explicitly instructed, branch/commit must be approved, production backup is required, bounded validation should be planned, browser smoke is developer-owned, and environment-specific details belong in gitignored local docs rather than tracked guidance.
- `docs/production_recovery_living_doc_20260526.md` still treats stable deployment and verified browser smoke as production-readiness constraints. This checkpoint does not claim all recovery gates are closed.

## Decision

Developer-approved deploy guidance is justified now for the host-boundary slice.

The earlier blocker was missing live `UvicornServerHost` startup/browser-route evidence. That blocker is now closed by the recorded smoke evidence. The current evidence is sufficient to hand deploy-prep guidance to the Orchestrator/developer for the host-boundary migration state, provided the developer still approves the exact branch/commit and performs the production runbook steps.

This is not a deploy authorization. It is not a production-ready claim for every recovery gate. It does not authorize agents to deploy, restart, SSH, push, change production topology, or run production commands. Actual deploy remains blocked until explicit developer approval and the runbook pre-checks are satisfied.

More evidence is not required before deploy guidance, but the developer may still choose to request a bounded snapshot/LAN hot-path wait evidence checkpoint before approving a real deploy.

## Behavior Intentionally Preserved

The deploy guidance depends on preserving the narrowness of the host-boundary slice:

- package app creation through `init_tracker_server.app.create_app(...)`
- health/readiness route wiring and payloads
- lifespan readiness toggling and runtime start/shutdown behavior
- `server_app.py` compatibility shim behavior
- route registration, route bodies, middleware, static mounts, and route-local helper closures in `LanController.start()`
- route-local DM-combat read offload and tactical serialization behavior
- initial `_cached_snapshot` / `_cached_pcs` seeding in `LanController.start()`
- DM-console snapshot/cache ownership in legacy tracker paths
- existing host, port, log level, access-log, thread name, daemon-thread behavior, and `serve_headless.py` launch behavior
- Tk polling startup through `self.app.after(60, self._tick)`
- queue state, command semantics, WebSocket state, auth/claims/reconnect behavior, hidden-information handling, persistence, and gameplay authority
- shutdown join/cancellation semantics

Deploy must preserve these. It should apply the approved branch only; it should not become an opportunity to refactor routes, cache, queue, WebSocket, runtime, or gameplay behavior.

## Known Risks

Snapshot/LAN hot-path latency remains the main technical risk. The live smoke recorded `_lan_snapshot` slow spans around `391-398 ms`. Earlier post-offload evidence recorded tactical `/api/dm/combat?workspace=dmcontrol` p95 around `791 ms` and max around `1093 ms`, while health/readiness and plain combat routes were no longer locked in the same slow path. This is a read-model/snapshot risk, not host/server lifecycle ownership evidence.

The smoke is representative, not exhaustive. It proves observed startup/browser-route/WebSocket behavior after `UvicornServerHost`, but it does not prove every player command, every DM mutation route, every map route, every production environment detail, or every recovery gate.

Route-registration extraction remains high risk and not approved. The live smoke does not prove route-inventory preservation after extraction because no extraction happened.

Production environment details are not in tracked docs. The runbook is sanitized and explicitly says hostnames, IPs, account details, and other environment-specific details belong in `docs/local/production_environment.md`. Any deploy prep must use the developer-approved local production details; agents must not guess them.

The production recovery living doc still records broader production-readiness constraints, including stable deployment, browser smoke, map viability, gameplay responsiveness, and verified core workflows. This checkpoint only supports deploy guidance for the host-boundary migration state.

## Required Pre-Deploy Checks For Orchestrator/Developer

Before any real deploy, the Orchestrator/developer should request and confirm:

1. Developer explicitly approves a production deploy or deploy-prep operation for the exact branch and commit.
2. The approved branch/commit range is identified against the production baseline. For this host-boundary scope, verify inclusion of `14932cb` and `fa92cc3`, and account for any docs-only checkpoint commit that follows this one.
3. The worktree and staged changes exclude unrelated or forbidden dirt, especially `docs/bug_reports/inbox/BUG-20260626-dmcontrol-terrain-not-visible.md`, `logs/context/`, smoke logs, and debug traces unless the developer explicitly asks to include docs evidence.
4. The deploy branch has the recorded local validation or a developer-approved fresh equivalent: Python compile for edited/adjacent server files, `tests/test_server_host.py`, `tests/test_server_runtime.py`, and `timeout 10s git diff --check`.
5. The live smoke evidence from `logs/smoke/WORK-20260701-app-host-runtime-lifecycle-smoke-evidence-capture_smoke-server_20260701-155344.log` and `logs/debug-trace-20260701-155344.jsonl` is accepted as sufficient host-boundary smoke evidence, or the developer requests a fresh smoke before deploy.
6. `docs/agent_ops/production_update_runbook.md` is present and is the active sanitized procedure.
7. Developer-controlled local production details are available from the appropriate local documentation, including production path, account/host, Python/venv path, log path, process management strategy, current branch, and rollback location.
8. A backup of the current production application directory is planned before applying changes.
9. A bounded production validation plan is chosen before restart, including startup success, health/readiness checks, `/`, `/dm`, `/api/dm/combat`, `/api/dm/combat?workspace=dmcontrol`, browser claim/reconnect behavior, and post-deploy log review.
10. The browser smoke owner is identified. Browser smoke remains developer-owned and is not replaced by this docs checkpoint.
11. Rollback criteria are explicit: startup failure, readiness failure, route 5xx, broken `/` or `/dm`, broken WebSocket claim/reconnect, unexpected queue/auth errors, or unacceptable hot-path latency during smoke.
12. No production command, SSH, restart, push, or topology change is performed by an agent unless a separate developer-approved task explicitly authorizes it.

## Explicitly Not To Change During Deploy

Do not change any of the following during deploy prep or deploy:

- app code
- tests
- logs or debug traces
- route registration
- route bodies
- `init_tracker_server/routes/`
- launch commands
- lifespan behavior
- readiness behavior
- `UvicornServerHost`
- snapshot warm-up
- cache ownership, TTLs, schemas, static hydration, or response payloads
- WebSocket behavior
- auth, claims, reconnect, or hidden-information behavior
- queue behavior, queue-wait behavior, async command acceptance, or command semantics
- persistence behavior
- shutdown join/cancellation semantics
- player-command routes, combat mutation routes, rules-aware movement, AoE creation, structures, ships, boarding links, or other gameplay behavior
- production topology

## Recommended Next Work

No app implementation work item is recommended before deploy guidance handoff.

The next action should be Orchestrator/developer deploy-prep review using the checks above, or pause with no further migration work.

If the developer wants more latency proof before approving a real deploy, open a bounded evidence-only checkpoint:

`WORK-20260701-snapshot-lan-hot-path-wait-evidence-checkpoint`

That item should record snapshot/LAN hot-path wait behavior only. It should not change cache ownership, TTLs, schemas, payloads, threadpool adoption, route registration, route bodies, queue behavior, WebSocket behavior, launch behavior, or gameplay behavior.

After a real deploy, if the developer supplies production smoke results, a separate docs-only post-deploy smoke evidence checkpoint would be appropriate. This checkpoint does not open that item.

## Ledger Update

`docs/work_items/current_work.md` was returned to Idle with no active work item.

The completed table now includes this deploy-guidance checkpoint. The allowed next action is developer/Orchestrator deploy-prep review using the recorded guidance, pause/no further migration, or a bounded snapshot/LAN hot-path wait evidence checkpoint only if the developer wants more latency proof before deploy approval.

## Validation

Required validation commands:

- `git status --short`
- `timeout 10s git diff --check`

No tests, smoke, deploy commands, production commands, service restarts, SSH, pushes, or commits were run by this checkpoint.

Results are recorded in the final agent report.
