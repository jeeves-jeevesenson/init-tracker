# Evidence Report: BUG-20260614-player-mount-lockout

## Summary
The reported issue is a movement desync and perceived lockout during ordinary mount interactions (e.g., Rider = Vicnor, Mount = John Twilight). Current hypothesis focuses on a potential **Missing State Broadcast** in the backend after a token move, or a **Missing Local Prediction** in the frontend for riders/mounts, leading to stale visual state.

## Observed Symptoms (Corrected)
- **Normal Pairing**: Vicnor (Top/Rider) is mounted on John Twilight (Bottom/Mount).
- **Mount Moves, Rider Stays**: When John (bottom) moves, his token moves on his screen, but Vicnor (top) often does not follow immediately.
- **Stale View**: On Vicnor's screen, John may appear not to have moved at all, or John moves but Vicnor is left behind.
- **Late Snap**: Vicnor's token only updates/snaps to the correct position later, typically at the start of Vicnor's turn or when another action triggers a server broadcast.
- **Lockout Perception**: The rider (Vicnor) is intentionally blocked by the backend from moving themselves ("Rider movement uses the mount"), and because they are a PC-to-PC pair ("independent" mode), the rider also cannot move the mount. This is expected behavior that feels like a "lockout" when the mount's movement is desynced.

## Code Observations (Potential Root Causes)
- **Broadcast Gap Hypothesis**: `PlayerCommandService.move()` in `player_command_service.py` calls `_lan_try_move()` but does **not** explicitly trigger a `_lan_force_state_broadcast()`.
- **Headless Broadcast Hypothesis**: `InitiativeTracker._lan_try_move()` calls `self._rebuild_table()`. In `helper_script.py`, `_rebuild_table()` returns immediately if `host_mode != "desktop"` and does **not** broadcast. In a headless production environment, this may mean a successful move results in zero websocket updates to other clients.
- **Frontend Prediction Hypothesis**: The frontend `move` handler in `assets/web/lan/index.html` contains local prediction logic (applying `unit_update` immediately), but this logic is guarded by `if (isPlanning)`, which is FALSE for normal players.

## Rejected/Demoted Hypothesis
- **Mutual Mount Loop**: While theoretically possible, this was not the cause of the reported live-session bug. The issue occurs with ordinary, one-way mounting.

## Key Evidence Questions for Next Pass
- **Authoritative State**: Is the rider's position supposed to be calculated by the client based on the mount, or is the server supposed to broadcast explicit coordinates for both?
- **Broadcast Payload**: Does a full `state` broadcast correctly include both updated positions?
- **Frontend Sync**: Does the frontend `draw()` logic correctly position a rider over their mount even if their individual `pos` is stale?

## Recommended Next Bounded Task
**Evidence Capture & Instrumentation**:
1. Evidence/instrumentation around what happens when bottom/mount moves while top/rider is mounted.
2. Compare backend coordinates, websocket/broadcast payloads, and frontend render state for both bottom and top.
3. Determine whether the failure is server state, broadcast payload, or frontend stale local render state.

## Developer Browser-Smoke Questions
- When the bottom moves, does the rider see the bottom move but stay behind, or does the bottom not move at all on the rider's screen?
- Does clicking "Refresh" in the browser immediately fix the position? (If yes, it confirms the state is correct on the server but wasn't broadcast).
