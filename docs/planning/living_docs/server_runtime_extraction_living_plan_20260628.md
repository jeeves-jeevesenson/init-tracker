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
