# BUG-20260614-player-spell-slots-not-syncing

- **Title**: Player spell slot/resource sync does not update UI after cast or manual override.
- **Status**: Active
- **Source bug**: [docs/bug_reports/inbox/BUG-20260614-player-spell-slots-not-syncing.md](../bug_reports/inbox/BUG-20260614-player-spell-slots-not-syncing.md)
- **Scope**: player web index/player UI resource synchronization only.

## Initial Gate: Gate 1 — Evidence capture and bounded fix plan

### Goal
Identify why spell slot casts and manual slot overrides appear in logs/API responses but do not refresh player UI or manual override menu state.

### Non-goals
- Do not change DM-side automation.
- Do not change monster AI.
- Do not change AoE targeting.
- Do not change mount behavior.
- Do not change 1080p layout.

## Plan

### Gate 1: Evidence capture and bounded fix plan
- [ ] Reproduce the issue using browser smoke or manual inspection of resource sync payloads.
- [ ] Inspect `assets/web/lan/index.html` (player UI) resource update logic.
- [ ] Verify if manual override menu state is correctly hydrated from backend state.
- [ ] Propose a bounded fix plan.

### Gate 2: Implementation and Validation
- [ ] (TBD)
