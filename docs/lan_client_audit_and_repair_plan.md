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

### Pass 3C: LAN Spell/Action Audit & Critical Fixes (CURRENT)
- [x] **Spell Automation Audit:** Created `docs/lan_player_spell_automation_audit.md` to track status of player spells.
- [x] **Unarmed Strike Fallback:** Ensured all characters have Unarmed Strike in LAN attack options, even if no weapon is configured/inventory is empty.
- [x] **Targeting Toast Fix:** Bypass token ownership checks ("Arrr, that token ain't yers") when in spell/attack targeting mode.
- [x] **Resource/Concentration Desync:** Trigger HUD update on `static_data` arrival and show "Active" concentration status if spell name is missing.
- [x] **Performance Optimization:** Consolidated redundant UI rebuilds and state broadcasts during AOE/spell resolution.
- [x] **Data Correction:** Added Cleric (Tempest) to `Destructive Wave` class list.

#### User Live Test Notes (May 16, 2026)
- Old Man weapon issue confirmed (missing Unarmed fallback).
- Spell targeting toasts were intrusive/wrong context.
- Resource pools were desynced (reappeared only after action).
- AOE latency was significant (traced to redundant broadcasts per target).
- Concentration panel was sometimes empty for active spells.
- Destructive Wave was missing for Stihiya.
- Vicnor's pistol was missing (likely due to inventory/attacks mapping).

### Pass 3D: LAN Live-Game Readiness Smoke (CURRENT)
- [x] **Smoke Test Checklist:** Verified Unarmed Strike fallback, spell targeting toasts, and resource sync.
- [x] **Ship Contact Semantics:** Fixed a pre-existing regression in `_lan_snapshot` where `ship_state` was incorrectly assigned, resolving 1 test failure.
- [x] **Spell Audit Refinement:** Categorized player spells into "Game Ready" vs "Use with Caution" for tomorrow's session.
- [x] **Performance Verification:** Confirmed redundant broadcasts are removed from AOE/Shatter resolution paths.

### Pass 3E: LAN Action and Inventory Cards (Next)
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
