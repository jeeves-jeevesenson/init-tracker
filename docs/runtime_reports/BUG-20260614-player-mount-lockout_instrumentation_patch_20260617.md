# Instrumentation Patch Report: BUG-20260614-player-mount-lockout

## Summary
**Note: This is temporary evidence instrumentation only. Root cause is not confirmed.**

Instrumentation has been added to both the backend and frontend to capture evidence of mount-follow desync. All logs are marked with `BUG-20260614-MOUNT-FOLLOW`.

## Exact Log Markers Added
- **Backend (Python)**: `debug_event("mount.follow.trace", marker="BUG-20260614-MOUNT-FOLLOW", ...)`
- **Frontend (JS)**: `console.log("[BUG-20260614-MOUNT-FOLLOW] ...")`

## How to Enable Logging

### Backend
Enable debug mode via environment variable:
```bash
export INIT_TRACKER_DEBUGGING=1
```
Logs will be written to `logs/debug-trace-YYYYMMDD-HHMMSS.jsonl`.

### Frontend
Enable frontend logging via browser console:
```javascript
localStorage.setItem("BUG-20260614-MOUNT-FOLLOW", "1");
location.reload();
```

## Files and Functions Changed

### Backend
1. **`player_command_service.py`**
   - `move()`: Added `step="command_start"` to log the initial receipt of the movement command.
2. **`dnd_initative_tracker.py`**
   - `_lan_try_move()`: Added `step="mutate_start"` and `step="mutate_end"` to capture `self._lan_positions` before and after the server updates the rider and mount coordinates.
   - `LanController._tick()`: Added `step="broadcast_unit_update"` inside the polling-broadcast block to log the actual updates being sent to clients.

### Frontend
1. **`assets/web/lan/index.html`**
   - WebSocket "message" event listener: Added `WS_RECV` to log the arrival of `state` or `unit_update` messages.
   - `applyUnitUpdates()`: Added `UI_APPLY` to log when a specific CID's position is updated in the local UI state.

## Interpretation Guide
A successful mount-follow should produce a trace like this:
1. `command_start`: Server receives "move" from Mount.
2. `mutate_start`: Server begins updating positions.
3. `mutate_end`: Server confirms `_lan_positions` updated for both Mount and Rider.
4. `broadcast_unit_update`: Server polling detects the change and broadcasts both CIDs.
5. `WS_RECV`: Rider's client receives the update.
6. `UI_APPLY`: Rider's client applies the new position.

## Developer Smoke Action
1. Enable debug mode and start the server.
2. Connect two clients: one as **John Twilight** (Mount), one as **Vicnor** (Rider).
3. Enable frontend logging on the Rider's client.
4. Perform a mount interaction.
5. **Move John Twilight.**
6. Observe the server logs and Rider's browser console.

## Root Cause Decision Logic
- **Server State Divergence**: If `mutate_end` shows the Rider at the wrong position, the backend logic in `_lan_try_move` is faulty.
- **Websocket Payload Gap**: If `mutate_end` is correct but `broadcast_unit_update` is missing or does not include the Rider's CID, the polling snapshot/comparison logic is failing.
- **Frontend Stale Render State**: If `WS_RECV` shows the update arrived but `UI_APPLY` doesn't fire or shows wrong data, the frontend state management is at fault.
