# BUG-20260626-aura-of-protection-grid-snap

## Triage Disposition

- **Status**: Triaged unresolved
- **Triage Date**: 2026-06-26
- **Disposition**: Bounded visual-rendering fix candidate.
- **Reason**: Screenshot evidence exists and expected behavior is clear: aura should stay centered on Dorian.

## Summary

Dorian's Aura of Protection visual appears snapped to the wrong grid position instead of staying centered on Dorian.

## User-visible impact

Aura placement is visually misleading. The aura should communicate Dorian's actual protection radius, but an offset circle can make affected/not-affected positioning unclear.

## Observed behavior

During player/LAN smoke after the reactions closeout passed, Dorian's Aura of Protection circle appeared offset from Dorian's token. The aura looked snapped to a nearby grid coordinate rather than centered on the character.

## Expected behavior

Dorian's Aura of Protection should always be centered on Dorian.

## Reproduction steps

1. Open the player/LAN surface.
2. View Dorian while Aura of Protection is displayed.
3. Observe whether the aura circle is centered on Dorian's token center.
4. Pan/zoom if needed and verify the aura remains centered on Dorian rather than snapping to a grid offset.

## Environment

- Observed during developer browser smoke on 2026-06-26.
- Surface likely Player/LAN root surface, but DM/player comparison is still needed.

## Evidence provided

- Developer screenshot in ChatGPT conversation showing Aura of Protection visibly offset from Dorian.
- Developer note: “dorians aura of protection snaps to the wrong grid, it should always be centered on him always.”

## Missing evidence

- Whether the offset occurs on DM surface, Player/LAN surface, or both.
- Whether the offset changes with zoom/pan.
- Whether the aura uses token grid coordinates, token pixel center, or another snapped origin.
- Whether other aura/effect circles have the same issue.

## Suspected areas / hypotheses

- Aura/effect rendering may be using snapped grid coordinates instead of the token center.
- The aura origin may be based on top-left/token cell coordinates rather than the rendered token center.
- Player/LAN and DM surface rendering may have diverged.

## Orchestrator handoff

This is an inbox bug only. Do not make it active while closing BUG-20260614-reactions-hold-combat unless the developer explicitly promotes it.

## Do not assume

Do not assume this is related to reactions, Counterspell, or the map drag-panning pointer-capture fix without evidence.
