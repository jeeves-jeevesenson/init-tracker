# BUG-20260614-player-mount-lockout

- **Title**: Mounting did not work when pressed on both sides, and the player could not move afterward.
- **Surface**: player web index / player-side UI
- **Source**: Jun 13 live player smoke test
- **Severity**: P1
- **Type**: Blocker / UX issue

## Observed Behavior
A player attempted a mount interaction. The mount flow did not complete successfully even when both sides/participants pressed the mount control. After the failed mount attempt, the player was unable to move. This may indicate the player-side mount request/response flow can leave movement/input state stuck after failure or incomplete confirmation.

## Expected Behavior
A valid mount flow should complete when both participants confirm. If the flow fails or is cancelled, movement should remain available and the player should not be left locked.

## Reproduction Notes
Mounting did not work when pressed on both sides, and the player could not move afterward.

## Evidence
- **Available**: General report of failure.
- **Needed**: Character/mount pair, whether both were claimed by players, whether refreshing cleared the lockout, client_errors entries near the event.

## Suspected Area
Player-side mount request/response flow, movement/input state management.
