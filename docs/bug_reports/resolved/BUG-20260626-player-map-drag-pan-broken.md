# BUG-20260626-player-map-drag-pan-broken

## Resolution Summary

- **Status**: Resolved
- **Resolution Date**: 2026-06-26
- **Resolved during**: BUG-20260614-reactions-hold-combat browser smoke
- **Severity**: Smoke blocker / player-surface navigation regression

## Observed behavior

On the Player/LAN root surface at `http://127.0.0.1:8787/`, drag panning the map was broken. Lock Map made no difference. WASD panning still worked. DM control surface drag panning still worked.

## Fix summary

The player/LAN canvas pointer handlers in `assets/web/lan/index.html` were hardened so `setPointerCapture` and `releasePointerCapture` failures do not abort drag-panning state setup/cleanup in browser smoke or simulated pointer contexts.

## Evidence

- Capture report: `docs/runtime_reports/BUG-20260626-player-map-drag-pan-broken_capture_20260626-084603.md`
- Fix report: `docs/runtime_reports/BUG-20260626-player-map-drag-pan-broken_fix_20260626.md`
- Smoke log: `logs/smoke/BUG-20260626-player-map-drag-pan-broken_smoke-server_20260626-092459.log`

## Validation

- `timeout 30s .venv/bin/python -m py_compile player_command_service.py dnd_initative_tracker.py`
- `timeout 30s .venv/bin/python -m unittest tests.test_reaction_prompt_expiry_resume tests.test_reaction_prompt_ally_filter`
- `timeout 10s git diff --check`
- Developer smoke confirmed Player/LAN drag panning works.
- Developer smoke confirmed reaction validation could proceed after this blocker was fixed.

## Resolution Status

Resolved and folded into the reactions closeout as a smoke-blocker fix.
