# BUG-20260614-player-1080p-header-overflow

- **Title**: On a 1080p display, the player had to zoom the web page to 90% to see the Battle Log button in the top panel.
- **Surface**: player web index / player-side UI
- **Source**: Jun 13 live player smoke test
- **Severity**: P2
- **Type**: Layout issue / UX issue

## Observed Behavior
At 1080p and 100% browser zoom, the player page top panel/header overflowed or clipped important controls. The Battle Log button was not visible/reachable until the player reduced browser zoom to 90%.

## Resolution Summary
The header overflow was caused by missing horizontal width constraints on the root and major top-level containers (`html`, `body`, `.app`, `.topbar`). Without these constraints, the flex-column layout allowed children to expand horizontally beyond the viewport if their content (20+ buttons in `topbar-main-row`) exceeded 1920px.

The fix involved adding `width: 100%` to `html`, `body`, and `.topbar`, and `width: 100%; max-width: 100vw;` to `.app`. Additionally, `box-sizing: border-box` was added to `.topbar` to ensure padding does not cause additional overflow. These constraints force the `topbar-main-row` to respect the viewport width and wrap its contents correctly.

- **Fix Commit**: `2453a16 Constrain player header layout at 1080p`
- **Resolution Date**: 2026-06-17

## Smoke Pass Evidence
- **Viewport**: 1920x1080 / 100% zoom
- **Result**: PASS. Battle Log and all header buttons are visible and reachable through wrapping.
- **Accepted Trade-off**: 150% zoom overflow is out-of-scope.
- **Logs**:
  - Smoke log: `logs/smoke/BUG-20260614-player-1080p-header-overflow_smoke-server_20260617-135340.log`
  - Debug trace: `logs/debug-trace-20260617-135340.jsonl`

## Expected Behavior
At 1080p and 100% zoom, critical controls such as Battle Log should be visible or reachable through wrapping, scrolling, responsive collapse, or another accessible layout.

## Reproduction Notes
On a 1080p display, the player had to zoom the web page to 90% to see the Battle Log button in the top panel.

## Evidence
- **Available**: General report of visibility issue at 1080p.
- **Needed**: Browser/device, exact viewport, screenshot at 100% zoom.

## Suspected Area
Header layout, responsive design / CSS.
