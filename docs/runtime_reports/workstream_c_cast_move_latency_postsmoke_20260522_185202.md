# Workstream C — Post-smoke latency postmortem (2026-05-22)

## Symptom
User reported significant lag (10–15 seconds) when attempting to move a character (Johnny Morris) immediately after casting a spell (Blight).

## Timeline (from trace 20260522-185202)
- **23:59:08.000Z**: `cast_spell` (Blight) received.
- **23:59:09.082Z**: `cast_spell` dispatch completed (duration: 1082ms).
  - This action included a `player_yaml_write` to update slots/resources.
  - `player_yaml_write` invalidated the LAN static snapshot cache.
  - `_schedule_player_yaml_refresh` was called, scheduling a refresh in 200ms.
- **23:59:09.282Z**: `refresh` task started on the Tk thread.
  - Called `_lan_force_state_broadcast(include_static=True)`.
  - **lan.snapshot.build** started.
  - Rebuilt static component due to `player_yaml_write` invalidation.
  - `_player_profiles_payload` ran, re-loading all player profiles.
  - `_static_data_payload` built full monster choices (200+ specs).
  - **8312.9ms** elapsed in `lan.snapshot.build`.
- **23:59:12.651Z**: `move` message received by the server.
  - Trace ID: `trace-75dde60961ce485e8cd47d9e8babba47`
  - Action ID: `action-59b6d2f2e9cd4835a12cfefe85096881`
  - Enqueued in `self._actions` queue.
  - **Blocked**: The Tk thread was busy running the `refresh` task (specifically the slow snapshot build).
- **23:59:17.595Z**: `_lan_force_state_broadcast` completed (total 8465ms).
- **23:59:25.643Z**: `move` dispatch started.
  - **Queue wait: ~13 seconds**.
- **23:59:25.653Z**: `move` dispatch completed (duration: 10ms).

## Verdict
- **Movement is fast once dispatched.** The 10ms execution time confirms the backend logic for movement is not the bottleneck.
- **Latency is Queue/Event-loop Wait.** The action was stuck in the queue because the Tk main thread was blocked by a synchronous, heavy state broadcast triggered by a player YAML update.
- **Blocking Work**: `_lan_force_state_broadcast(include_static=True)` is too heavy for the main thread. Specifically, rebuilding the static snapshot (player profiles + monster choices) takes > 8 seconds.

## Root Cause
1. **Synchronous Heavy Work**: `_lan_force_state_broadcast` runs on the main thread and performs heavy I/O and processing (parsing all player YAMLs, iterating all monster specs).
2. **Coarse Invalidation**: Any `player_yaml_write` (like spending a spell slot) invalidates the ENTIRE static cache, forcing a full rebuild of profiles and monster data.
3. **Lack of Backpressure Visibility**: The trace did not explicitly record the time spent in the queue, making it harder to distinguish "slow execution" from "slow dispatch".

## Implementation Plan
1. **Tracing**: Add `queue_wait_ms` to `ws.action.dispatch` events to make this delay visible.
2. **Idempotency**: Add server-side `action_id` tracking to prevent duplicate execution during these long wait windows.
3. **Acknowledgement**: Send an immediate "received" ack to the client so the UI can show "processing" and prevent duplicate clicks.
4. **Optimization**: Investigate decoupling `include_static` broadcasts or refining invalidation domains.
