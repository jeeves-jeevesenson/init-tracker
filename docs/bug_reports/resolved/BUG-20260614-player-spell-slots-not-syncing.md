# BUG-20260614-player-spell-slots-not-syncing

- **Title**: Spell slots do not update on UI or manual override menu after casting or manual override.
- **Surface**: player web index / player-side UI
- **Source**: Jun 13 live player smoke test
- **Severity**: P1
- **Type**: Combat correctness issue / Resource sync issue

## Observed Behavior
Casting spells from the player side does not visibly decrement spell slots in the player UI. Spell slot override shows on the log but does not update on the UI or in the manual override menu. Using spells also does not update the UI slots or manual override menu.

## Expected Behavior
When a spell that consumes a spell slot is cast, the player UI should update to show the reduced slot count. Manual override should immediately update the visible UI and the values shown when reopening the manual override menu. Log/backend/player UI/manual override menu should agree.

## Reproduction Notes
Player spell slots do not seem to be used when casting spells. Spell slot override shows on the log but does not update on the UI or in the manual override menu. Using spells also does not update the UI slots or manual override menu.

## Evidence
- **Available**: General report of spell slot sync failure.
- **Needed**: Character/class, spell level used, whether refresh updates the UI, battle.log/resource log lines, client_errors entries.

## Suspected Area
Resource sync between backend and player UI, specifically spell slots.

## Resolution
Resolved on 2026-06-14.

Fixed by ensuring `_save_player_spell_slots` triggers an authoritative static refresh, repairing the LAN projection cache to correctly patch resource pools and clear stale JSON payloads, and accumulating invalidation domains to prevent concurrent write clobbering. Developer-led browser smoke confirmed that spell slots now update correctly in both the main UI and the manual override menu.
