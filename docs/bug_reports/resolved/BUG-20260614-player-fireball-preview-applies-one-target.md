# BUG-20260614-player-fireball-preview-applies-one-target

- **Title**: A player used Fireball to attack two people. The overlay said it would hit both targets. Once Fireball was cast, it only hit one target.
- **Surface**: player web index / player-side UI
- **Source**: Jun 13 live player smoke test
- **Severity**: P1
- **Type**: Combat correctness issue

## Observed Behavior
Player-side AoE preview and actual spell resolution disagree. The Fireball targeting overlay included two affected targets, but the resolved cast only applied to one target.

## Expected Behavior
The target set shown in the AoE preview should match the authoritative resolution. If two targets are shown as hit, both valid targets should be affected when the spell resolves.

## Reproduction Notes
A player used Fireball to attack two people. The overlay said it would hit both targets. Once Fireball was cast, it only hit one target.

## Evidence
- **Available**: General report of target count mismatch.
- **Needed**: Caster, target names, whether targets were monsters/players/mixed, battle.log lines for the cast, client_errors entries near cast, request payload if logged.

## Suspected Area
AoE preview logic vs backend spell resolution.
