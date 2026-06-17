# BUG-20260614-player-1080p-header-overflow

- **Title**: 1080p header overflow / Battle Log invisible
- **Status**: Active
- **Source bug**: [docs/bug_reports/triaged/BUG-20260614-player-1080p-header-overflow.md](../bug_reports/triaged/BUG-20260614-player-1080p-header-overflow.md)
- **Scope**: player web index header layout only.

## Initial Gate: Gate 1 — Initial intake/reproduction/planning

### Goal
Identify the CSS/HTML cause of the header overflow on 1080p displays and propose a fix.

### Non-goals
- Do not change DM-side UI.
- Do not fix the bug in this pass.
- Do not remove the temporary debug-gated mount-follow instrumentation.

## Plan

### Gate 1: Initial intake/reproduction/planning
- [ ] Inspect `assets/web/lan/index.html` header structure.
- [ ] Identify the specific CSS rules causing overflow at 1920px width.
- [ ] Document reproduction steps or simulated viewport constraints.
- [ ] Propose a bounded fix plan (e.g., flexbox wrapping, media queries, or responsive collapse).

#### Suspected Root Cause
- TBD. Likely fixed-width containers or non-wrapping flex containers in the top panel.

#### Bounded Fix Plan
- TBD.

## Validation & Evidence

### Required Validation
- Node.js `--check` for inline JavaScript in `assets/web/lan/index.html` (if edited).

### Completion Evidence
```
(Pending research)
```

## Next Allowed Action
- Run the bounded initial diagnosis/planning task only.
