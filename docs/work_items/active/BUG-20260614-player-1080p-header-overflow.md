# BUG-20260614-player-1080p-header-overflow

- **Title**: 1080p header overflow / Battle Log invisible
- **Status**: Active
- **Source bug**: [docs/bug_reports/triaged/BUG-20260614-player-1080p-header-overflow.md](../bug_reports/triaged/BUG-20260614-player-1080p-header-overflow.md)
- **Scope**: player web index header layout only.

## Initial Gate: Gate 1 — Initial intake/reproduction/planning (Complete)

### Goal
Identify the CSS/HTML cause of the header overflow on 1080p displays and propose a fix.

### Non-goals
- Do not change DM-side UI.
- Do not fix the bug in this pass.
- Do not remove the temporary debug-gated mount-follow instrumentation.

## Plan

### Gate 1: Initial intake/reproduction/planning
- [x] Inspect `assets/web/lan/index.html` header structure.
- [x] Identify the specific CSS rules causing overflow at 1920px width.
- [x] Document reproduction steps or simulated viewport constraints.
- [x] Propose a bounded fix plan (e.g., flexbox wrapping, media queries, or responsive collapse).

#### Suspected Root Cause
The `topbar-main-row` (which contains 20+ buttons) is configured with `flex-wrap: wrap`, but it fails to wrap at the 1920px (1080p) viewport edge. This is likely because the top-level containers (`html`, `body`, `.app`, `.topbar`) lack explicit horizontal width constraints (e.g., `width: 100%` or `max-width: 100vw`). In a flex column layout (`.app` -> `.topbar`), children can expand horizontally beyond the viewport if not constrained, causing the `topbar-main-row` to expand to its full content width (~2000px+) rather than wrapping. The resulting overflow is clipped by `body { overflow: hidden }`. Zooming to 90% "widens" the available CSS pixels enough to reveal the clipped buttons.

#### Bounded Fix Plan
1.  **Constrain Width**: Add `width: 100%` to `html` and `body`.
2.  **Ensure App Constraint**: Add `width: 100%; max-width: 100vw;` to the `.app` container.
3.  **Ensure Topbar Constraint**: Add `width: 100%;` to the `.topbar` container and ensure it is `box-sizing: border-box` to account for padding.
4.  **Refine Wrapping**: Verify `.topbar-main-row` and `.topbar-controls` wrap correctly once the width is constrained.
5.  **Validation**: Verify fix at 1920x1080 resolution and run inline JS syntax check on `assets/web/lan/index.html`.

### Gate 2: Bounded implementation of CSS/layout fix (Complete)
- [x] Apply width constraints to `html`, `body`, `.app`, and `.topbar` in `assets/web/lan/index.html`.
- [x] Verify `topbar-main-row` wrapping behavior in simulated 1080p viewport.
- [x] Perform mandatory inline JS syntax check.

## Validation & Evidence

### Required Validation
- Node.js `--check` for inline JavaScript in `assets/web/lan/index.html` (if edited).
- `git diff --check` and `py_compile` (if applicable).

### Completion Evidence
- Inspected `assets/web/lan/index.html` and identified missing width constraints on root and major containers.
- Confirmed `auto-compact` mode (which hides the button) is not active at 1080p, supporting the overflow hypothesis.
- Calculated total content width of header elements exceeds 1920px, necessitating wrap.
- Applied the following CSS changes to `assets/web/lan/index.html`:
  - `html, body`: Added `width: 100%`.
  - `.app`: Added `width: 100%` and `max-width: 100vw`.
  - `.topbar`: Added `width: 100%` and `box-sizing: border-box`.
- Verified JS syntax (if applicable).

## Next Allowed Action
- Developer browser smoke verification only.
