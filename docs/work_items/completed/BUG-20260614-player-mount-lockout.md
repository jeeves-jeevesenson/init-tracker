# Completed Work Item: BUG-20260614-player-mount-lockout

- **ID**: BUG-20260614-player-mount-lockout
- **Title**: Player mount lockout / movement failure
- **Source**: [docs/bug_reports/triaged/BUG-20260614-player-mount-lockout.md](../bug_reports/triaged/BUG-20260614-player-mount-lockout.md)
- **Status**: Completed
- **Completion Date**: 2026-06-17
- **Severity**: P1

## Goal
Restore movement capability and ensure the mount interaction completes or fails gracefully without locking the player.

## Outcome
The reported mount lockout was primarily caused by a turn-gate blocker that prevented the target of a mount request from responding off-turn. This blocked the completion of the mount interaction and could lead to perceived movement lockouts (as riders cannot move themselves).

The blocker was fixed by exempting `mount_response` from the turn gate and hardening the authorization to ensure only the intended mount or an admin can respond.

The original rider-follow desync bug was not reproduced during final smoke testing, and debug traces confirmed that the server correctly broadcasts both rider and mount updates together.

## Evidence / Reports
- [Evidence Report](../../runtime_reports/BUG-20260614-player-mount-lockout_evidence_20260616.md)
- [Instrumentation Plan](../../runtime_reports/BUG-20260614-player-mount-lockout_instrumentation_plan_20260617.md)
- [Instrumentation Patch Report](../../runtime_reports/BUG-20260614-player-mount-lockout_instrumentation_patch_20260617.md)
- [Off-turn Fix & Hardening Report](../../runtime_reports/BUG-20260614-player-mount-lockout_accept_offturn_fix_20260617.md)
- [Smoke Pass Report](../../runtime_reports/BUG-20260614-player-mount-lockout_smoke_pass_20260617.md)

## Status Checklist
- [x] Blocker fix implemented
- [x] Authorization hardened
- [x] Unittest coverage added (6 tests)
- [x] Developer smoke passed
- [x] Debug trace verified synchronized broadcast

**Note**: Temporary instrumentation added during this task remains in the codebase but is debug-gated. It can be removed in a future cleanup task if desired.
