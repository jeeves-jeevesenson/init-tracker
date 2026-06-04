# WORK-20260603-browser-smoke-harness-scorcher-ignite-ground

## ID and Title

WORK-20260603-browser-smoke-harness-scorcher-ignite-ground: Add bounded Playwright smoke for Scorcher Ignite Ground Apply Result

## Status

Active

## Active Gate

Gate 0 — Current-state refresh and scope confirmation

## Goal

Add a local-only Python Playwright smoke harness for `/dmcontrol` that seeds a deterministic Black and Tan VDA Scorcher encounter, performs Ignite Ground zero-target Apply Result, verifies persistent fire hazards, collects artifacts, and reports pass/fail without developer manual browser repetition.

## Parent Plan

[PLAN-20260603-browser-automation-smoke-harness.md](../../planning/living_docs/PLAN-20260603-browser-automation-smoke-harness.md)

## Scope (Implementation Slice 1)

In scope:

- Gate 1: `/dmcontrol` stable test IDs.
- Debug-gated smoke helper.
- Deterministic Scorcher fixture strategy.
- One Scorcher Ignite Ground Playwright scenario only.

## Non-Goals

- No LAN sync.
- No broad regression suite.
- No CI integration.
- No production dependency.
- No additional Scorcher action scenarios.
- No deployment changes.
- No browser automation expansion beyond the first scenario until stable.

## Gates

### Gate 0 — Current-state refresh and scope confirmation

**Status: Active**

Tasks:
- [ ] Run context refresh (`scripts/chatgpt_context_refresher.sh`).
- [ ] Confirm repo state (clean tree, recent Scorcher work committed).
- [ ] Confirm current automation conventions (Python Playwright library style).
- [ ] Prepare Gate 1 task list.

### Gate 1 — `/dmcontrol` test IDs and smoke helper

**Status: Pending**

Tasks:
- [ ] Add stable `data-testid` attributes to `/dmcontrol`.
- [ ] Add debug-gated `window.__dmcontrolSmoke` helper.
- [ ] Run asset syntax checks.

### Gate 2 — Deterministic Scorcher fixture

**Status: Pending**

Tasks:
- [ ] Add debug-only fixture route or fixture-load strategy.
- [ ] Add route gating tests.

### Gate 3 — Harness shell and artifacts

**Status: Pending**

Tasks:
- [ ] Add Playwright smoke script shell.
- [ ] Implement artifact collector (logs, screenshots, traces).

### Gate 4 — First Scorcher smoke scenario

**Status: Pending**

Tasks:
- [ ] Implement `scorcher-ignite-ground` scenario.
- [ ] Verify pass/fail and artifact generation.

## Validation

```bash
scripts/chatgpt_context_refresher.sh
cat docs/work_items/current_work.md
git status --short
git log --oneline -5
```
