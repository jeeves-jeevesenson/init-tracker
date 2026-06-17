# Instrumentation Plan: BUG-20260614-player-mount-lockout

## Goal
Observe the desync between mount movement and rider follow in a headless environment. Determine whether the failure is in server state mutation, snapshot change detection, websocket broadcast payload, or frontend stale render state.

## Code Path Map
1. **Command Entry**: `LanController._ws_on_message` -> `self._actions.append(msg)`
2. **Execution (Tk Thread)**: `LanController._tick` -> `InitiativeTracker._lan_apply_action(msg)`
3. **Movement Dispatch**: `_lan_apply_action` -> `PlayerCommandService.dispatch_movement_action_command` -> `svc.move`
4. **State Mutation**: `PlayerCommandService.move` -> `InitiativeTracker._lan_try_move`
   - **Update Mount**: `self._lan_positions[cid] = (col, row)` (`dnd_initative_tracker.py:46112`)
   - **Update Rider**: `self._lan_positions[int(rider_cid)] = (col, row)` (`dnd_initative_tracker.py:46114`)
5. **Detection & Broadcast (Tk Thread)**: `LanController._tick` (after action processing)
   - **Snapshot**: `snap = self.app._lan_snapshot()` (`dnd_initative_tracker.py:7224`)
   - **Compare**: `units_snapshot, unit_updates = self._build_unit_updates(prev_snap, snap)` (`dnd_initative_tracker.py:7266`)
   - **Broadcast**: `self._broadcast_payload({"type": "unit_update", "updates": unit_updates})` (`dnd_initative_tracker.py:7270`)
6. **Frontend Reception**: `assets/web/lan/index.html` -> `socket.onmessage`
   - **Apply**: `applyUnitUpdates(updates)` -> `state.units` updated.
   - **Render**: `draw()` -> uses `u.pos` for each unit.

## State Fields to Inspect
- **Mount (Bottom)**: `cid`, `pos`, `mounted_by_cid`, `mount_controller_mode`
- **Rider (Top)**: `cid`, `pos`, `rider_cid`
- **Server Internal**: `InitiativeTracker._lan_positions` (dict of cid to tuple)
- **Snapshot Payload**: `units` list in the `state` or `unit_update` message.

## Expected State Transitions
| Stage | Mount Pos | Rider Pos | Broadcast Expected? |
|-------|-----------|-----------|---------------------|
| **Initial (Mounted)** | (5, 5) | (5, 5) | N/A |
| **After `_lan_try_move`** | (6, 5) | (6, 5) | Yes (Internal state updated) |
| **After `_tick` Snapshot** | (6, 5) | (6, 5) | Yes (Snapshot should detect change) |
| **Websocket Message** | N/A | N/A | `unit_update` with both CIDs |
| **Frontend Render** | (6, 5) | (6, 5) | Vicnor drawn over John at (6, 5) |

## Evidence Capture Strategy
Add temporary high-frequency logging to the following points (to be implemented in next pass):

### Backend (`dnd_initative_tracker.py`)
1. **`_lan_try_move`**: Log `f"MUTATE: cid={cid} pos={col},{row} rider={rider_cid}"`
2. **`_lan_snapshot`**: Log `f"SNAPSHOT: positions={self._lan_positions}"`
3. **`_tick` (Broadcast block)**: Log `f"BROADCAST: updates={unit_updates}"`

### Frontend (`assets/web/lan/index.html`)
1. **`onmessage`**: Log `f"WS_RECV: {msg.type} updates={msg.updates.length}"`
2. **`applyUnitUpdates`**: Log `f"UI_APPLY: cid={u.cid} pos={u.pos.col},{u.pos.row}"`

## Key Questions for Evidence
- **Divergence Point**: Does `_lan_positions` contain the rider's new coordinates immediately after the mount moves?
- **Comparison failure**: Does `_build_unit_updates` return an empty list even when `_lan_positions` has changed?
- **Missing Broadcast**: Does `_tick` skip the broadcast block entirely for some moves?
- **Frontend Drop**: Does the frontend receive the rider update but fail to apply it to `state.units`?

## Recommended Next Bounded Task
Implement a **Temporary Instrumentation Patch** adding the specific log lines identified above. Run a live reproduction where John moves Vicnor, and capture the combined server/client log trace.

## Risks & Unknowns
- **Headless `_rebuild_table`**: I confirmed `_rebuild_table` is silent in headless mode. While `_tick` *should* detect changes via polling snapshots, the lack of an explicit broadcast trigger in the `move` path might be introducing a race condition or causing updates to be coalesced/skipped.
- **Rider Movement Rules**: If the rider attempts to move and is rejected, ensure the rejection toast doesn't interfere with subsequent follow updates.
