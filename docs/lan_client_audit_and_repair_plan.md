# LAN Client Audit and Repair Plan

## 1. Current Checkpoint
- **Current Commit**: `b511c93` (Verify DM firearm ammo and map controls)
- **Dirty Files**: None (at start of audit)
- **Relevant Recent Commits**:
    - `5eb0bc4` Add DM control map pan and zoom
    - `1160fc9` Add DM-side firearm ammo and reload tracking
    - `9cc15d7` Rescue Black and Tan DM control live behavior

## 2. Executive Summary
The LAN client (`assets/web/lan/index.html`) is a feature-rich but architectural monolithic hotspot. It is currently "usable" but extremely fragile due to imperative state management and a 26k+ line single-file structure. 

**Top 5 Likely Blockers:**
1. **State Inconsistency (Confirmed by Code):** Manual state merging in `ws.onmessage` is highly susceptible to missing updates or preserving stale data.
2. **Reconnection Fragility (Confirmed by Code/Tests):** Complex multi-timer recovery logic suggests a history of race conditions and sync failures.
3. **UI/Map Desync (Suspected):** Map pan/zoom and token interactions lack the polish and feedback (Mode Banners) found in the recently stabilized `/dmcontrol`.
4. **Maintenance Burden (Confirmed):** 26,000 lines in one file makes debugging and adding features (like Firearm UI) risky.
5. **Targeting Mode Confusion (Suspected):** Lack of clear "Targeting Mode" indicators for players often leads to accidental token drags instead of target selection.

**Confidence Level:**
- Architecture: High (Confirmed by inspection)
- Bug Classes: Medium-High (Confirmed by code patterns and user report)
- Performance: Medium (Needs runtime measurement)

## 3. Architecture Map
- **Key Functions**:
    - `connect()`: WebSocket lifecycle management.
    - `ws.onmessage`: Massive central dispatcher for all backend state.
    - `draw()`: Main canvas render loop (units, AOE, map).
    - `updateHud()`: Updates top bar and status displays.
    - `populateActionSelect()` / `refreshWeaponSelectors()`: Manual UI sync for inventory/actions.
- **Backend Routes**:
    - WebSocket: `/ws`
    - Static Data: Sent on `client_hello`.
    - Player Actions: POSTs to various `/api/player/...` (e.g., `/api/players/*/spellbook`).
- **State Flow**: Backend Snapshot → JSON → `ws.onmessage` → Global `state` variable → `scheduleUiFlush` → `draw()`/`updateHud()`.

## 4. Bug Inventory

| ID | Title | Severity | Evidence | Likely Cause | Recommended Fix |
|:---|:---|:---:|:---|:---|:---|
| B1 | Stale State Overwrite | P0 | `ws.onmessage` manual merge | Preserve `oldSpellPresets` etc. manually | Move to a cleaner "apply delta" or full replace with reactive markers. |
| B2 | Targeting Mode Confusion | P1 | Inspection vs `/dmcontrol` | No Mode Banner | Implement `/dmcontrol` style Mode Banner. |
| B3 | Reconnect Race Conditions | P1 | `scripts/validation/lan-recovery-smoke.py` | Multiple timers/states | Simplify to a single recovery state machine. |
| B4 | Layout Overflow | P1 | Massive CSS in `index.html` | Unmanaged monolithic CSS | Break out CSS or move to more robust flex/grid layouts. |
| B5 | Action Card Readability | P2 | Comparison with `/dmcontrol` | Minimalist lists | Port `/dmcontrol` action card style to LAN. |
| B6 | Map Pan/Zoom Jitter | P2 | Code inspection | Imperative pan/zoom logic | Align with `/dmcontrol` stabilized map logic. |

## 5. Repair Phases

### Pass 3B: LAN Safety and Mode Clarity
- **Goal**: Add Mode Banners and basic static validation.
- **Tasks**:
    - Port `/dmcontrol` Mode Banner to LAN.
    - Add explicit `TARGETING` and `RESOLVING` states.
    - Integrate `node --check` into standard dev workflow.

### Pass 3B: LAN Combat Unblock (Current)
- **Goal**: Resolve P0 blockers preventing basic combat actions in LAN.
- **Root Causes Identified**:
    - `_lan_snapshot` in `dnd_initative_tracker.py` was missing `player_profiles`, `player_spells`, and `resource_pools`, causing blank UI sections and missing action data.
    - Lack of Unarmed Strike fallback for weaponless characters.
- **Fixed**:
    - Restored missing player data fields to `_lan_snapshot`.
    - Added 1.0s throttle for resource pool calculation to maintain performance.
    - Added Unarmed Strike fallback to player profile generation.
    - Fixed `LanController` AttributeErrors and test stability.
- **Impact**: Resource Pools should now render, spellcasters should see their spells, and all characters should have at least one attack action (Unarmed Strike) available even without weapons.

### Pass 3C: State Sync Refactor (Next)
- **Goal**: Stabilize WebSocket snapshot ingestion and handle Mode Banners (deferred from 3B).
- **Tasks**:
    - Audit `ws.onmessage` for every field in `state`.
    - Ensure `static_data` doesn't get stomped by partial updates.
    - Simplify `reconnectRecovery` timers.

### Pass 3D: Map and Targeting Polish
- **Goal**: Align map interaction with `/dmcontrol`.
- **Tasks**:
    - Port stabilized pan/zoom logic.
    - Fix token click vs drag priority.
    - Visual feedback for "valid target candidates".

### Pass 3E: Action and Inventory Cards
- **Goal**: Modernize the action selection UI.
- **Tasks**:
    - Replace simple selects/lists with rich Action Cards.
    - Add "Execute" button clarity.
    - Improve mobile responsiveness of the bottom tray.

### Pass 3F: LAN Firearm UI
- **Goal**: Enable player-side ammo tracking and reloading.
- **Tasks**:
    - Port DM-side ammo UI to LAN action cards.
    - Implement "Reload" action visibility.

## 6. Testing Strategy
- **Cheap Checks**: Always run the JS syntax check (see `GEMINI.md`).
- **Targeted Tests**:
    - `scripts/validation/lan-recovery-smoke.py`
    - `scripts/validation/lan-smoke-playwright.py`
- **Manual Smoke Checklist**:
    - [ ] Pan/Zoom doesn't "snap" after a state update.
    - [ ] Targeting mode clears on Escape.
    - [ ] Action cards reflect current ammo count.
    - [ ] Reconnect doesn't reload the entire page.

## 7. Deferred Items
- **Full File Decomposition**: Breaking the 26k line file into modules (needs careful handling of global state).
- **AOE/SAM-7 Implementation**: Complex templates deferred until basic targeting is stable.
- **Visual Facelift**: Full CSS overhaul deferred until layout is stable.

## 8. Questions for User
- Are there specific mobile devices where the layout breaks most severely?
- Does the "State becomes stale" bug happen mostly after a short disconnect, or even during active sessions?
- Which LAN feature is currently the "most broken" for players?
