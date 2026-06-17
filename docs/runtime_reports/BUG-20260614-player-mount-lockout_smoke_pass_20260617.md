# Smoke Pass Report: BUG-20260614-player-mount-lockout_smoke_pass_20260617

## Summary
Developer smoke testing on 2026-06-17 was successful following the off-turn `mount_response` blocker fix and hardening pass.

## Smoke Test Evidence
- **Date**: 2026-06-17
* **Latest smoke log path**: `logs/smoke/BUG-20260614-player-mount-lockout_smoke-server_20260617-133212.log`
* **Latest debug trace path**: `logs/debug-trace-20260617-133212.jsonl`

## Results
- **Off-turn mount acceptance**: Worked as expected. John Twilight was able to accept Vicnor's mount request while it was Vicnor's turn. No "Not yer turn" blocker was observed.
- **Mount flow**: The interaction completed successfully. The `mount_response` was correctly handled by the backend.
- **Rider-follow behavior**: The debug trace showed that when the bottom (mount) character moved, both the bottom and top (rider) positions were updated in the server state and broadcast together in a single `unit_update` batch.
- **Original rider-follow desync**: Not reproduced. The positions remained in sync across both clients during the smoke test.

## Status
- [x] Blocker fix verified
- [x] Authorization hardening verified
- [x] Trace confirmed synchronized broadcast
- [x] Smoke passed
