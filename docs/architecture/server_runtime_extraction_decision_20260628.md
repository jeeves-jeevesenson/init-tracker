# Server Runtime Extraction Decision — 2026-06-28

Status: planning decision recorded from imported external research.

Source work item: `docs/work_items/active/WORK-20260628-port-external-research.md`

Raw imported research:
- `docs/planning/research/external/20260628/init_tracker_web_server_extraction_plan_20260628.md`
- `docs/planning/research/external/20260628/script_hosted_runtime_asgi_host_research_20260628.md`
- `docs/planning/research/external/20260628/long_term_architecture_agent_workflow_plan_20260628.pdf`

## Decision

The durable architectural direction is:

**ASGI server first; runtime as a service.**

The web server should eventually own process startup, health, HTTP routes, WebSocket lifecycle, and backpressure. The legacy tracker/runtime should become a callable runtime service behind a narrow facade. Heavy or blocking work should be isolated behind explicit command queue and snapshot-cache boundaries.

## Repo-grounded current posture

This decision does not claim implementation is active. In the imported repo snapshot, `docs/work_items/current_work.md` was idle before this research-port item was activated.

Existing repo seams that make this direction plausible:
- `serve_headless.py` proves a headless host path exists, but it still preserves a tracker-owned/Tk-shaped lifecycle.
- `tk_compat.py` provides `HeadlessRoot` compatibility rather than removing the old event-loop assumptions.
- `combat_service.py` is already a backend/service seam for combat/session state.
- `player_command_service.py` is already a backend-authoritative seam for player-originated commands.
- `docs/runtime_reports/final_playability_latency_amputation_20260522.md` records latency symptoms around tactical snapshot builds, LAN snapshot builds, and queue waits.
- `docs/runtime_reports/hotfix_dm_map_combat_lite_regression_20260523.md` records the workspace-aware combat-lite vs. tactical-payload contract.

## Implementation sequencing

Do not start with a real engine migration.

Preferred order:
1. Persist research and decisions in repo docs.
2. Create a living plan with gates and non-goals.
3. Create one bounded work item per gate.
4. Introduce an ASGI app factory and lifespan shell only after a work item is active.
5. Introduce runtime facade and command queue in a later gate.
6. Harden snapshot cache and workspace contracts after the facade exists.
7. Revisit renderer/runtime replacement only after server ownership and runtime isolation are real.

## Non-goals for the current work item

- No edits to app code.
- No route migration.
- No `serve_headless.py` refactor.
- No production deploy, service restart, DNS/FQDN/topology change, or push.
- No broad repo scan or revival of old plans outside the current work ledger.

## Planning commitments

Future implementation work must use AGY by default and must be bounded by a task packet or active work item.

Any AGY task spawned from this decision must name exact files to inspect and exact files allowed to edit. It must not ask AGY to look around, review the repo, run all tests, or continue until done.

## First candidate gates

1. **Research Port Gate** — import raw research, write decision digest, write living plan, activate ledger.
2. **Architecture Shell Gate** — design-only pass for app factory, lifespan, health endpoints, runtime service boundary.
3. **Server Ownership Shell Gate** — code pass for app factory and health endpoints, with bounded validation.
4. **Runtime Facade Gate** — code pass to introduce facade/queue skeleton without broad route migration.
5. **Snapshot Contract Gate** — code pass to formalize combat-lite vs. tactical workspace snapshots.


---

<!-- ROADMAP_SYNTHESIS_20260628_START -->
## Repo-specific roadmap synthesis, 2026-06-28

### Target architecture

The target architecture is **ASGI server first, runtime as a service**.

FastAPI/Uvicorn should own process startup, health endpoints, HTTP routing, WebSocket lifecycle, and shutdown. The current tracker/runtime should sit behind a small runtime facade that exposes command submission, read-model snapshot access, health/readiness state, and event publication. Route handlers should become thin adapters: validate request, choose snapshot contract or command type, call the facade, return response.

The first extraction should stay conservative. It should preserve the existing runtime and current gameplay behavior while changing ownership boundaries. The objective is not to rewrite the engine, redesign the frontend, or move all domain logic at once. The objective is to stop normal HTTP/WebSocket responsiveness from being downstream of tracker-shaped blocking work.

### Non-negotiable decisions

1. **ASGI owns lifecycle in the future hosted path.** Server startup/shutdown should move toward an application factory and lifespan-managed runtime service.
2. **Runtime access must narrow.** New server routes should not grow more direct calls into tracker internals.
3. **Mutations become commands.** Player and DM mutations should pass through a queue/facade boundary before touching authoritative state.
4. **Reads use explicit snapshot contracts.** Combat-lite and tactical/map snapshots must remain separate contracts, with workspace-aware tactical behavior preserved.
5. **Blocking containment is temporary.** Threadpool/offload is allowed as a transition tool, not as the final architecture.
6. **The repo ledger controls activation.** Imported research and this decision doc are planning inputs only until `docs/work_items/current_work.md` activates a specific implementation item.
7. **Real engine/runtime replacement is not now.** Engine migration, TypeScript runtime work, and broad frontend redesign remain future exploration until the server/runtime boundary is stable.

### First future implementation candidate

The first implementation candidate should be a narrow **server-first health/app-factory shell**. It should add the smallest factory/lifespan seam needed to prove that the ASGI layer can own health/readiness and hold a runtime service object without migrating gameplay routes yet.

That future task should not start until opened as its own active work item. It should name exact files, explicit validation, and a rollback plan.
<!-- ROADMAP_SYNTHESIS_20260628_END -->
