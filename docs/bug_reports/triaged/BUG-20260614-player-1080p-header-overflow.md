# BUG-20260614-player-1080p-header-overflow

- **Title**: On a 1080p display, the player had to zoom the web page to 90% to see the Battle Log button in the top panel.
- **Surface**: player web index / player-side UI
- **Source**: Jun 13 live player smoke test
- **Severity**: P2
- **Type**: Layout issue / UX issue

## Observed Behavior
At 1080p and 100% browser zoom, the player page top panel/header overflowed or clipped important controls. The Battle Log button was not visible/reachable until the player reduced browser zoom to 90%.

## Expected Behavior
At 1080p and 100% zoom, critical controls such as Battle Log should be visible or reachable through wrapping, scrolling, responsive collapse, or another accessible layout.

## Reproduction Notes
On a 1080p display, the player had to zoom the web page to 90% to see the Battle Log button in the top panel.

## Evidence
- **Available**: General report of visibility issue at 1080p.
- **Needed**: Browser/device, exact viewport, screenshot at 100% zoom.

## Suspected Area
Header layout, responsive design / CSS.
