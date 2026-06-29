# Living Plan: Server Runtime Extraction

- **Status:** Active Planning
- **Date Opened:** 2026-06-28
- **Source Research:** `docs/planning/research/external/20260628/`
- **Decision Doc:** `docs/architecture/server_runtime_extraction_decision_20260628.md`
- **Current Work Item:** `docs/work_items/active/WORK-20260628-port-external-research.md`

---

## Mission

Make the project durable for a future server-resident runtime by first extracting and documenting the web-server/runtime boundary.

The target architecture is **ASGI server first; runtime as a service**.

---

## Source of Truth

Active work is controlled by:
- `docs/work_items/current_work.md`
- active work item documents under `docs/work_items/active/`

Research inputs are stored under:
- `docs/planning/research/external/20260628/`

Long-term architecture direction is summarized in:
- `docs/architecture/server_runtime_extraction_decision_20260628.md`

---

## Current Gate: Research Port Gate

### Goal

Persist external research in the repository and create durable summaries that can survive chat deletion.

### Acceptance Criteria

- Raw research files are copied under `docs/planning/research/external/20260628/`.
- A README in that directory explains source, use, and trust boundary.
- A decision document exists under `docs/architecture/`.
- This living plan exists under `docs/planning/living_docs/`.
- `docs/work_items/current_work.md` points at `WORK-20260628-port-external-research`.
- Validation passes:
  - `git status --short`
  - `timeout 10s git diff --check`

---

## Gate 2: Architecture Shell Planning

### Goal

Design the minimum ASGI app-factory/lifespan shell without implementation.

### Acceptance Criteria

- One active work item names exact files to inspect.
- The work item proposes an app factory, lifespan-owned runtime object, and health/readiness endpoints.
- No app code is changed in the planning pass.

---

## Gate 3: Server Ownership Shell

### Goal

Implement the smallest possible server-first shell.

### Acceptance Criteria

- A factory-backed ASGI app can start.
- Health/readiness endpoints are explicit.
- Existing launch behavior is preserved or wrapped.
- Validation is bounded and named in the work item.

---

## Gate 4: Runtime Facade and Command Queue

### Goal

Introduce a narrow facade between HTTP/WebSocket surfaces and the legacy runtime.

### Acceptance Criteria

- The facade owns command submission and snapshot reads.
- Mutating paths begin moving through the facade in small slices.
- Queue depth, command age, and snapshot-build duration become observable or at least loggable.

---

## Gate 5: Snapshot Contract Hardening

### Goal

Formalize combat-lite vs. tactical workspace payload rules.

### Acceptance Criteria

- Normal combat polling does not build tactical snapshots unless explicitly required.
- `/dm/map`, `/dmcontrol`, and map mutation routes retain tactical payload access.
- Cache invalidation rules are documented and tested in scoped tests.

---

## Non-Goals

- No real game engine migration in this plan.
- No TypeScript/runtime rewrite as a near-term implementation task.
- No broad route migration without an active scoped work item.
- No production deploys or restarts from research work.
- No use of raw imported research as a substitute for current repo evidence.

---

## Handoff to Orchestrator

Next safe action after the Research Port Gate is validated:

1. Commit the documentation import as one focused docs commit, or
2. Keep it uncommitted and ask AGY for a bounded architecture-shell planning task.

Do not start app implementation until the developer approves a new active work item for a named gate.


---

<!-- PHASED_ROADMAP_20260628_START -->
## Phased repo roadmap, 2026-06-28

This roadmap converts the imported external research into repo-specific execution order. It is not an active implementation task list. Each phase requires a separate work item before code changes.

### Phase 0: Documentation and activation discipline

Status: completed by the research import and this roadmap pass.

Exit condition:
- External research is stored under `docs/planning/research/external/20260628/`.
- Architecture and living-plan docs identify the target boundary and safe sequence.
- `current_work.md` is the only activation source.

### Phase 1: Server-first health and app factory shell

Goal:
- Introduce or formalize a FastAPI app factory/lifespan seam.
- Add or confirm bounded health/readiness endpoints.
- Keep existing runtime behavior intact.
- Keep `serve_headless.py` compatible while moving toward server-owned lifecycle.

Validation gate:
- Scoped import/compile checks for touched files.
- Health endpoint smoke using a local headless server command only when explicitly authorized.
- No browser readiness claim from unit tests alone.

Not in scope:
- Route migration.
- Runtime facade behavior changes.
- Queue/cache implementation.
- Frontend redesign.

### Phase 2: Runtime facade skeleton

Goal:
- Create the narrow object the ASGI layer will eventually depend on.
- Define command submission, snapshot read, health/readiness, and shutdown methods.
- Initially delegate to existing services/runtime without changing gameplay semantics.

Validation gate:
- Scoped compile checks.
- Focused unit tests for facade construction and method contracts only.

Not in scope:
- Moving every route.
- Changing combat rules.
- Optimizing tactical map generation.

### Phase 3: Command queue for hot mutations

Goal:
- Move selected high-value mutations through the runtime facade queue.
- Start with a tiny route slice, chosen by evidence from current repo behavior.
- Preserve existing locking and state authority rules.

Validation gate:
- Focused route/service tests for the migrated command path.
- Queue-depth/command-age logging or metrics where practical.
- Explicit timeout wrappers on all validation.

Not in scope:
- Broad route migration.
- Full async rewrite.
- New gameplay features.

### Phase 4: Snapshot contract hardening

Goal:
- Make combat-lite versus tactical/map snapshot behavior explicit and testable.
- Preserve workspace-aware tactical requests for `/dm/map` and `/dmcontrol`.
- Avoid rebuilding heavy tactical payloads for ordinary combat polling.

Validation gate:
- Tests proving combat-lite routes do not include tactical payloads unless required.
- Tests proving map/control workspaces still receive tactical data.
- Scoped performance evidence before claiming latency improvement.

### Phase 5: Route migration and legacy shrink

Goal:
- Gradually move route slices behind the facade after the app factory, facade skeleton, queue, and snapshot contracts exist.
- Remove direct tracker access from routes only in bounded slices.

Validation gate:
- One route group per task.
- Focused tests only.
- Developer browser smoke when UI behavior is affected.

### Explicit not-now items

- Real engine migration.
- TypeScript runtime rewrite.
- Broad frontend redesign.
- Full test-suite runs as routine validation.
- Production deploy/restart/DNS/FQDN changes.
- AGY broad repo discovery tasks.

### Candidate next work item, not active

`WORK-20260628-server-first-health-shell`

Purpose:
- Add the first app-factory/lifespan/health shell needed for server-owned lifecycle, with compatibility preserved.

This candidate must be opened separately before implementation.
<!-- PHASED_ROADMAP_20260628_END -->
