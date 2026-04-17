# Copilot instructions for this repository

## Mission
This repository is in a large-scale migration away from a Tkinter/canvas-heavy desktop host toward a production-ready web-first architecture with backend-owned combat/session authority. Treat this as migration and extraction work, not feature churn.

## Source of truth
- Inspect the current repository before making strong claims.
- Use the current repo contents and `majorTODO.md` as source of truth.
- Do not invent file paths, architecture, or completed work.
- When docs drift from code/tests, trust code/tests first and update `majorTODO.md` honestly.

## Working style
- Prefer broad, coherent migration passes over tiny cleanup-only slices when dependencies allow.
- Keep changes tightly scoped to the requested pass.
- Preserve behavior only when necessary to land the migration safely.
- Do not preserve legacy/Tk/desktop behavior as an end-state goal.
- The final target is production-ready and web-first, not a perpetual compatibility shell.

## Architecture direction
- Move authority out of desktop/UI-owned flows and into backend-owned services and explicit contracts.
- Keep rendering client-side and authority server-side.
- Prefer explicit command/result/event contracts over implicit shared-state mutation.
- Avoid long-lived dual ownership between desktop and web paths.
- Remove or quarantine old fallback paths once a migrated slice is validated.

## Priority areas
- Combat/session authority
- Player and DM command contracts
- Prompt/reaction lifecycle
- Persistence boundaries
- Player/LAN command extraction from monolithic handlers
- Testability in headless/minimal environments

## Current migration posture
- `majorTODO.md` is the master migration tracker.
- Update `majorTODO.md` after substantial migration passes.
- Use it to keep current state, risks, decisions, backlog, and next-pass recommendations aligned with the code.

## Validation
- Run focused validations during the work and a broader regression sweep at the end.
- Prefer the narrowest useful tests first, then a wider pass.
- Report exactly what changed, what remains rough, and follow-up risks.
- Be explicit about environment-caused failures versus code regressions.

## Guardrails
- Do not introduce new desktop-first features.
- Do not rewrite the map layer first unless the task explicitly requires it.
- Do not do speculative framework rewrites disconnected from the current repo.
- Do not claim a phase is complete unless code and tests support that claim.
- Keep hidden-information, auth/claims, reconnect behavior, and persistence safe.

## Operational notes
- This repo uses multiple agent tools. For major implementation passes, optimize for stable autonomous execution and clear end-of-pass reporting.
- When asked to work autonomously, inspect first, plan briefly, implement, validate, then update `majorTODO.md`.
