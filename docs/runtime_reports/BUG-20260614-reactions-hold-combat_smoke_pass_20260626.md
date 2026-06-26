# Runtime Smoke Pass: BUG-20260614-reactions-hold-combat

- **Date**: 2026-06-26
- **Smoke type**: Developer-led browser smoke
- **Server log**: logs/smoke/BUG-20260626-player-map-drag-pan-broken_smoke-server_20260626-092459.log
- **Result**: Pass with unrelated/new visual aura bug captured separately.

## Smoke observations

- Player/LAN map drag panning works after the emergency pointer-capture fix.
- WASD panning still works.
- Reaction smoke resumed after the panning blocker was fixed.
- Dorian cast with Dorian and Eldramar present.
- Eldramar did not receive an allied Counterspell prompt.
- No waiting-state combat stall was reported during this smoke pass.

## Blocking regression resolved during smoke

The player/LAN drag-panning regression discovered during this smoke was captured and fixed under:

- docs/runtime_reports/BUG-20260626-player-map-drag-pan-broken_capture_20260626-084603.md
- docs/runtime_reports/BUG-20260626-player-map-drag-pan-broken_fix_20260626.md
- docs/bug_reports/resolved/BUG-20260626-player-map-drag-pan-broken.md

## Non-blocking follow-up captured separately

A new aura positioning bug was observed after smoke passed:

- docs/bug_reports/inbox/BUG-20260626-aura-of-protection-grid-snap.md

This follow-up does not block closing BUG-20260614-reactions-hold-combat.
