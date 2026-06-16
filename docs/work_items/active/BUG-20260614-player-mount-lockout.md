# Active Work Item: BUG-20260614-player-mount-lockout

- **ID**: BUG-20260614-player-mount-lockout
- **Title**: Player mount lockout / movement failure
- **Source**: [docs/bug_reports/triaged/BUG-20260614-player-mount-lockout.md](../bug_reports/triaged/BUG-20260614-player-mount-lockout.md)
- **Status**: Active (Evidence / reproduction gate)
- **Severity**: P1

## Symptoms / Evidence
A player attempted a mount interaction. The mount flow did not complete successfully even when both sides/participants pressed the mount control. After the failed mount attempt, the player was unable to move. This may indicate the player-side mount request/response flow can leave movement/input state stuck after failure or incomplete confirmation.

## Goal
Restore movement capability and ensure the mount interaction completes or fails gracefully without locking the player.

## Reproduction / Evidence Needed
- Identify specific character/mount pair used.
- Confirm if both participants were player-claimed.
- Check if refreshing the browser clears the lockout.
- Inspect `client_errors` in logs for relevant entries during the lockout.
- Reproduce the lock state in a test or local browser session.

## Implementation Status
- [ ] Evidence captured / Reproduction confirmed
- [ ] Root cause identified
- [ ] Fix implemented
- [ ] Verification / Smoke test passed

**Note**: Implementation is not yet started. This item is in the **Evidence / reproduction gate**.

## Next Orchestrator Action
Perform bounded evidence capture or reproduction task for the mount lockout bug.
