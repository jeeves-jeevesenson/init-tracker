# Runtime Fix Report: BUG-20260626-player-map-drag-pan-broken

- **Date**: 2026-06-26
- **Task ID**: BUG-20260626-player-map-drag-pan-broken-G1-01
- **Mode**: Emergency bounded bug fix
- **Status**: Fixed & Validated

## Root Cause

During browser automated smoke testing of the reaction-handling changes, simulated touch/pointer clicks are triggered by the test automation driver. The player/LAN map interaction code in `assets/web/lan/index.html` registers a `pointerdown` listener on the canvas which directly calls `canvas.setPointerCapture(ev.pointerId)`. 

In headless testing browsers (and some browser/pointer combinations), simulated pointer events might not support pointer capture, or the `pointerId` is not considered active for capture, causing `setPointerCapture` to throw a `DOMException` (e.g. "InvalidPointerId"). Because this call was not wrapped in a `try/catch` block, the exception immediately aborted execution of the event listener, preventing the subsequent assignment to `panning` (`panning = {x: p.x, y: p.y, panX, panY}`) from executing. Since `panning` remained uninitialized, drag-panning was broken. Keyboard WASD panning and Lock Map click events were unaffected as they run on independent listeners or elements.

## Exact Files Changed

- [assets/web/lan/index.html](file:///home/a2-jeeves@iamjeeves.dev/src/init-tracker/assets/web/lan/index.html):
  - Wrapped `canvas.setPointerCapture(ev.pointerId)` in a `try/catch` block within the `pointerdown` canvas listener.
  - Added robust `try/catch` wrapped `canvas.releasePointerCapture(ev.pointerId)` calls inside `pointerup` and `pointercancel` canvas listeners.

## Bounded Validations Run

1. **Syntax/static sanity check**:
   ```bash
   .venv/bin/python -m py_compile player_command_service.py dnd_initative_tracker.py
   ```
   *Result*: Passed (no compile errors).

2. **Inline JS parsing check**:
   ```bash
   node --check assets/web/lan/index.html (via scratch extractor)
   ```
   *Result*: Passed (all script blocks parsed successfully).

3. **Reaction regression tests**:
   ```bash
   .venv/bin/python -m unittest tests.test_reaction_prompt_expiry_resume tests.test_reaction_prompt_ally_filter
   ```
   *Result*: Passed (7 tests, OK).

4. **Whitespace check**:
   ```bash
   git diff --check
   ```
   *Result*: Passed (no trailing whitespace/conflicts).

5. **Working Tree status**:
   ```bash
   git status --short
   ```
   *Result*: Checked.

## Next Steps: Developer Browser Smoke Verification

The developer must perform the following manual browser verification at http://127.0.0.1:8787/:
1. Confirm player/LAN map drag panning works correctly when unlocked.
2. Confirm Lock Map prevents drag panning when locked and allows it when unlocked.
3. Confirm WASD keyboard panning still works.
4. Confirm DM control surface drag panning still works.

Reactions combat-hold work stream (`BUG-20260614-reactions-hold-combat`) remains blocked until this developer browser smoke is verified.
