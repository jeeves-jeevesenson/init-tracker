# BUG-20260626-aura-of-protection-grid-snap: Aura of Protection grid snap offset

## Status

Active.

## Source

- Bug report: `docs/bug_reports/triaged/BUG-20260626-aura-of-protection-grid-snap.md`

## Goal

Confirm whether Dorian's Aura of Protection is actually anchored/evaluated at the wrong location or whether only the rendered aura/grid overlay is visually offset.

Then make the narrowest safe fix.

## Classification Rule

- If the stored aura anchor, token attachment, measured affected area, saving throw bonus application, or targeting/combat state is wrong, this is a gameplay correctness bug.
- If the aura remains logically centered on Dorian and only the displayed circle/grid snap is offset, this is a visual/rendering bug.

## Expected Behavior

Dorian's Aura of Protection should remain centered on Dorian's token center across pan/zoom/grid rendering.

## Scope

Allowed:
- Aura of Protection positioning/anchor/rendering code.
- Narrow evidence capture needed to distinguish visual offset from gameplay anchor/effect offset.
- Focused validation.

Forbidden:
- Broad combat rewrites.
- Broad targeting/effect-radius rewrites.
- Opportunistic UI cleanup.
- Old inbox/completed bug revival.
- Deploy/restart/push.

## Validation

- `git status --short`
- `timeout 10s git diff --check`
- Any existing focused validation discovered for aura/token rendering only.
- Developer browser smoke remains required for visual confirmation.
