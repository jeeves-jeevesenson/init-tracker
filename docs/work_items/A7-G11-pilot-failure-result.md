# A7-G11 Three-Surface Pilot Failure Result

Date: `2026-07-16`

Task: `SMOKE-20260716-a7-three-surface-retry-g11`

Run ID: `20260716_145717`

Terminal classification: `fail`

## Result

The one-shot G11 headless workflow passed ordered steps 1 through 17. The
fixture reset and validation passed, all ten required players were added, and
all nine required Black-and-Tan enemies were added. Step 18,
`start-combat`, timed out after approximately 30 seconds.

Playwright resolved `#startCombatBtn` as visible, enabled, and stable. The
still-open DM toolbox overlaid that control, and `.toolbox-header` intercepted
normal pointer events. No combat-start HTTP request was sent. This is a
harness interaction defect; G11 did not prove an application defect.

The required correction is to use an existing normal UI control to clear the
toolbox obstruction, then issue one ordinary Playwright click on
`#startCombatBtn` within the single execution of the `start-combat` plan step.
Forced clicks, DOM evaluate-clicks, and dispatched click events remain
forbidden.

## Evidence

- Summary JSON: `logs/smoke/SMOKE-20260716-a7-three-surface-retry-g11_browser-artifacts/black-tan-three-surface-workflow/20260716_145717/summary.json`
- Summary Markdown: `logs/smoke/SMOKE-20260716-a7-three-surface-retry-g11_browser-artifacts/black-tan-three-surface-workflow/20260716_145717/summary.md`
- Failure screenshot: `logs/smoke/SMOKE-20260716-a7-three-surface-retry-g11_browser-artifacts/black-tan-three-surface-workflow/20260716_145717/terminal-selector-failure-start-combat.png`
- Browser trace: `logs/smoke/SMOKE-20260716-a7-three-surface-retry-g11_browser-artifacts/black-tan-three-surface-workflow/20260716_145717/browser-trace.zip`
- Role traces: recorded in the G11 summary for DM, DM control, and all ten player roles

## G12 Authorization

On 2026-07-16 the developer granted standing approval for bounded G12
autonomous stabilization: evidence-backed changes in the authorized harness
and test files, focused validation, ownership-verified localhost server and
headless browser execution, evidence inspection, durable reports, repetition
only after validated corrections, and one focused commit after terminal pass.
Push, deployment, scheduler, production, restart, and service mutation remain
unauthorized.
