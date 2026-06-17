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

## Symptom Model
- Vicnor (Rider) mounted on John Twilight (Mount).
- John moves. John's token moves fine (on John's screen).
- Vicnor's token does not follow John immediately.
- Vicnor appears stale until his turn or a later update causes a "snap" to the correct square.
- Perception of lockout occurs because Vicnor cannot move himself (D&D rules) and cannot move John ("independent" PC mode).

## Reproduction / Evidence Needed
- [x] Evidence report corrected: See [docs/runtime_reports/BUG-20260614-player-mount-lockout_evidence_20260616.md](../../runtime_reports/BUG-20260614-player-mount-lockout_evidence_20260616.md)
- [ ] Verify mounted rider-follow state/broadcast/render behavior via instrumentation.
- [ ] Confirm if refreshing browser resolves stale position.

## Implementation Status
- [x] Corrected symptom model documented
- [ ] Root cause not confirmed
- [ ] Reproduction still needed
- [ ] Mounted rider-follow broadcast/render/state sync hypothesis pending evidence
- [ ] Fix implemented
- [ ] Verification / Smoke test passed

**Note**: Implementation is not yet started. This item is in the **Evidence / reproduction gate**.

## Next Orchestrator Action
Evidence/instrumentation around what happens when bottom/mount moves while top/rider is mounted. Compare backend coordinates, websocket/broadcast payloads, and frontend render state for both bottom and top to determine whether the failure is server state, broadcast payload, or frontend stale local render state.
