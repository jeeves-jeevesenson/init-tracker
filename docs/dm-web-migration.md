# DM Web Console – Migration Boundary Documentation

## Summary

This document describes the migration passes that establish a canonical
backend/service seam for combat/session state and deliver a real DM browser
console backed by that service.

---

## What is now backend/service-owned

The following slice of combat/session state is now authoritatively owned by
`combat_service.py` (`CombatService`) and exposed through HTTP API routes:

| Capability | Endpoint |
|---|---|
| Read combat/session snapshot | `GET /api/dm/combat` |
| Start combat (begin initiative turn order) | `POST /api/dm/combat/start` |
| End combat (reset turn state) | `POST /api/dm/combat/end` |
| Advance to next turn | `POST /api/dm/combat/next-turn` |
| Adjust combatant HP | `POST /api/dm/combat/combatants/{cid}/hp` |
| Add/remove condition | `POST /api/dm/combat/combatants/{cid}/condition` |
| Set temporary HP | `POST /api/dm/combat/combatants/{cid}/temp-hp` |
| Adjust temporary HP (delta) | `POST /api/dm/combat/combatants/{cid}/temp-hp-adjust` |
| Add combatant | `POST /api/dm/combat/combatants` |
| Set initiative | `POST /api/dm/combat/combatants/{cid}/initiative` |
| Remove combatant | `DELETE /api/dm/combat/combatants/{cid}` |
| Real-time DM state push | `WS /ws/dm[?token=…]` |

The **snapshot shape** (from `GET /api/dm/combat`):

```json
{
  "in_combat": true,
  "round": 3,
  "turn": 7,
  "active_cid": 2,
  "up_next_cid": 1,
  "up_next_name": "Fighter",
  "turn_order": [2, 1, 3],
  "combatants": [
    {
      "cid": 2,
      "name": "Goblin",
      "hp": 5,
      "max_hp": 7,
      "temp_hp": 0,
      "ac": 13,
      "initiative": 18,
      "is_pc": false,
      "role": "enemy",
      "conditions": [{"type": "poisoned", "remaining_turns": 2}],
      "is_current": true
    }
  ],
  "battle_log": ["Goblin took 3 damage", "--- ROUND 3 ---"]
}
```

`CombatService` delegates **all game logic** to the existing
`InitiativeTracker` engine (same code path the desktop uses), ensuring
there is only one source of truth.

---

## What the DM web UI can do

The DM console lives at `http://<lan-ip>:<port>/dm` and provides:

- **Initiative order** – all combatants in order with current-turn marker
- **HP display** – current / max HP with visual health bar, temp HP
- **Conditions** – active conditions shown as chips per combatant
- **Round / turn counter**
- **Current combatant** highlight and name display
- **Up-next combatant** – shows the next combatant in initiative order so the
  DM can alert the incoming player
- **⚔ Start Combat** – starts the initiative turn cycle (shown when combatants
  are present but combat has not started yet); delegates to the same
  `_start_turns()` logic used by the desktop Start/Reset button
- **✕ End Combat** – ends the active combat, resetting turn state while
  preserving the combatant list for review
- **▶ Next Turn** – advances the initiative order on the backend
- **HP Adjustment** – apply damage (negative) or healing (positive)
- **Set Temp HP** – set (or clear) temporary HP for any combatant
- **Add / Remove Condition** – apply any of the 15 standard D&D 5e conditions
- **Battle Log** – last 30 lines from the tracker's history file
- **Real-time updates** – receives instant snapshots via WebSocket (`/ws/dm`);
  falls back to 2.5-second polling if WebSocket is unavailable

Mutations from the DM console call the backend API, which updates the same
in-memory `InitiativeTracker` state that the desktop app reads.  The
WebSocket broadcast after each mutation ensures the player LAN client also
receives the update immediately, and the DM console `/ws/dm` channel
receives its own snapshot push without waiting for the next poll.

---

## Authentication

The DM console uses the same admin-token system as the rest of the LAN
server:

- **No admin password configured** (default): The DM console is accessible
  to anyone on the LAN.  This matches the existing LAN trust model.
- **Admin password configured**: The DM console shows a password prompt.
  Entering the correct password issues a token (valid 15 minutes, same as
  other admin-protected routes).

To configure an admin password, use the existing admin password configuration
in the desktop app settings.

---

## What the desktop still owns

The following areas remain desktop-primary (hybrid) after this pass:

- Full Tkinter canvas rendering and all desktop UI widgets
- Map / battle-map editing and tactical view
- Player-facing LAN client at `/` (existing WebSocket + `/ws` routes)
- Character editor, sheet management (`/edit_character`, `/new_character`)
- Shop, item and spell management
- YAML-backed save / load (files are still owned by the desktop flow)
- Full monster-spec / player-profile based combatant creation (desktop only)
- Advanced initiative manipulation (set-turn-here, prev-turn, start/reset)
- Deep combat engine damage paths (`_apply_damage_to_target_with_temp_hp` and
  related spell/attack damage application) still mutate state directly

The desktop app now **shares** the initiative/turn, HP, and condition
authority with the DM web console – they operate on the same in-memory
state through the same `_next_turn()` / `_apply_damage_to_combatant()` /
`_ensure_condition_stack()` methods.

### Desktop-routed through CombatService (Slice 6)

The following desktop/LAN-originated mutations now route through
`CombatService` when the service is running:

- **Desktop Next Turn** → `_next_turn_via_service()` → `CombatService.next_turn()`
- **LAN player "end turn"** → `_next_turn_via_service()` → `CombatService.next_turn()`
- **LAN player manual HP override** → `CombatService.adjust_hp()` /
  `CombatService.adjust_temp_hp()`
- **Desktop `_adjust_hp_via_service()`** → `CombatService.adjust_hp()` (wrapper
  available for progressive adoption by other desktop code paths)
- **Desktop `_set_condition_via_service()`** → `CombatService.set_condition()`
  (wrapper available for progressive adoption)
- **Desktop `_set_temp_hp_via_service()`** → `CombatService.set_temp_hp()`
  (wrapper available for progressive adoption)

All wrappers fall back to direct mutation + broadcast when the service is
not running (e.g. LAN server not started).

---

## Hybrid concurrency model

Both the desktop UI and the DM web console can mutate combat state
concurrently.  The current safeguard model:

- HTTP route handlers run on the FastAPI thread and call tracker methods
  directly, following the same pattern as existing LAN HTTP routes
  (e.g., `/api/encounter/players/add`).
- `CombatService` holds a `threading.Lock` that serialises concurrent
  mutations (next-turn, HP adjust, condition, temp HP) from the web API.
- Each mutation calls `_lan_force_state_broadcast()` which pushes updated
  state to all player WebSocket clients **and** to all connected DM
  WebSocket clients (`/ws/dm`).
- The desktop UI re-reads its state from the same `combatants` dict and
  `_rebuild_table()` call.

**Remaining risk**: The `CombatService` lock covers all mutations that go
through the service, including web-originated and the newly-routed
desktop/LAN paths (Next Turn, manual HP override).  Desktop-originated
mutations that do **not** yet use the `_*_via_service()` wrappers (e.g.
deep combat engine damage from spell/attack resolution) do not acquire
this lock, so a simultaneous desktop engine mutation + web mutation could
still race.  This is an acceptable risk for the single-session LAN use
case, and the wrapper adoption can continue incrementally.

---

## YAML save / load compatibility

The `CombatService` mutations modify the in-memory `Combatant` objects that
the existing `_save_session()` / `_load_session()` serialisation paths
already serialise.  There are no schema changes.  Saving after DM console
mutations will correctly persist any HP, temp HP, or condition changes made
via the web.

---

## Recommended next migration targets

1. **Deep combat engine routing**: Adopt `_adjust_hp_via_service()` and
   `_set_condition_via_service()` in the combat engine's damage/heal paths
   (`_apply_damage_to_target_with_temp_hp`, `_apply_heal_to_combatant`,
   spell effect condition application) so the service lock covers
   engine-originated mutations too.

2. **Initiative-roll support**: Expose full initiative-roll support through
   the backend service so the DM web console can trigger initiative rolls
   without Tkinter fallback.

3. **Token refresh**: The DM console does not yet auto-renew the admin token
   before expiry.  Add a background refresh 2 minutes before the 15-minute
   expiry window.

4. **Snapshot enhancements**: Additional fields (e.g. per-combatant AC tooltip,
   resource pools) can be added as the DM console grows.

5. **Player-facing LAN client state sync**: Improve broadcast reliability
   and reconnect behavior for the player-facing LAN WebSocket client.

---

## How to launch

1. Start the desktop app (`python dnd_initative_tracker.py`).
2. Enable the LAN server from the app (Settings → LAN Server → Start).
3. On any device on the same LAN, navigate to `http://<ip>:<port>/dm`.
4. If an admin password is configured, enter it when prompted.
5. The console will auto-populate with live combat state.
