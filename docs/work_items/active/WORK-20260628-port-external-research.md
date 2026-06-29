# Work Item: WORK-20260628-port-external-research - Port External Server Runtime Research

- **Status:** Completed
- **Source:** Developer-provided external research uploaded on 2026-06-28
- **Assigned To:** Orchestrator / developer shell patch
- **Mode:** Workflow/Admin + Planning

---

## Goal

Port the developer's external research into durable repository files and create a bounded planning foundation for later server-runtime extraction work.

This work item is intentionally documentation-only. It does not authorize app implementation.

---

## Scope & Non-Goals

### In Scope

- Copy raw external research into `docs/planning/research/external/20260628/`.
- Write an import README with source/trust-boundary notes.
- Write a decision digest in `docs/architecture/server_runtime_extraction_decision_20260628.md`.
- Write a living plan in `docs/planning/living_docs/server_runtime_extraction_living_plan_20260628.md`.
- Update `docs/work_items/current_work.md` so this research-port item is active.

### Non-Goals

- No app code changes.
- No test changes.
- No route migration.
- No `serve_headless.py` refactor.
- No production deploy, service restart, SSH, DNS/FQDN/topology change, or push.
- No broad repo scan.
- No revival of old plans, bugs, runtime reports, or `majorTODO.md` outside this work item.

---

## Technical Constraints

### Allowed Files

- `docs/planning/research/external/20260628/README.md`
- `docs/planning/research/external/20260628/init_tracker_web_server_extraction_plan_20260628.md`
- `docs/planning/research/external/20260628/script_hosted_runtime_asgi_host_research_20260628.md`
- `docs/planning/research/external/20260628/long_term_architecture_agent_workflow_plan_20260628.pdf`
- `docs/architecture/server_runtime_extraction_decision_20260628.md`
- `docs/planning/living_docs/server_runtime_extraction_living_plan_20260628.md`
- `docs/work_items/active/WORK-20260628-port-external-research.md`
- `docs/work_items/current_work.md`

### Forbidden Scope

- No files outside the allowed list.
- No app/runtime/source/test changes.
- No edits to credentials, hostnames, ports, production docs, deploy scripts, or service topology.
- No use of AGY unless the developer explicitly chooses to spend AGY on follow-up research normalization.

---

## Execution Plan

1. Copy raw research files into the external research import folder.
2. Add an import README that records provenance and trust boundary.
3. Add the server runtime extraction decision digest.
4. Add the living plan with staged gates and non-goals.
5. Activate this work item in `docs/work_items/current_work.md`.
6. Run bounded docs validation.

---

## Validation & Evidence

### Required Validation

```bash
git status --short
timeout 10s git diff --check
```

### Smoke Check Requirement

No browser smoke. This is a documentation/workflow import only.

### Completion Notes

Completed on 2026-06-28.

Evidence:
- Imported research docs committed in `a210eca`.
- `timeout 10s git diff --check` passed before commit.
- Remaining untracked `docs/bug_reports/inbox/BUG-20260626-dmcontrol-terrain-not-visible.md` and `logs/context/` were intentionally not staged.

---

## Next Step After Completion

Either:
1. Commit this documentation import as one focused docs commit, or
2. Open a new bounded Architecture Shell Planning work item.

Do not start implementation from this work item.
