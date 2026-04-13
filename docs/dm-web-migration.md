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
| Add NPC/enemy combatant | `POST /api/dm/combat/combatants` |
| Set combatant initiative | `POST /api/dm/combat/combatants/{cid}/initiative` |
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
- **Set Initiative** – update the initiative roll for any combatant in the
  encounter, with immediate re-sort and broadcast
- **Add Combatant** – add a new NPC/enemy (name, HP, max HP, AC, initiative,
  ally flag) directly from the web console without opening the desktop app
- **Remove Combatant** – remove any combatant from the initiative list with
  a confirmation prompt
- **Battle Log** – last 30 lines from the tracker's history file
- **Real-time updates** – receives instant snapshots via WebSocket (`/ws/dm`);
  falls back to 2.5-second polling if WebSocket is unavailable

Mutations from the DM console call the backend API, which updates the same
in-memory `InitiativeTracker` state that the desktop app reads.  The
WebSocket broadcast after each mutation ensures the player LAN client also
receives the update immediately, and the DM console `/ws/dm` channel
receives its own snapshot push without waiting for the next poll.

---

## Desktop Next Turn is now routed through CombatService

The desktop "Next Turn" button (`Space` shortcut), the map-window DM panel
"Next Turn" button, and the LAN player `end_turn` action all now call
`_next_turn_via_service()` instead of `_next_turn()` directly.

`_next_turn_via_service()` (defined in `InitiativeTracker`):
- Checks for `self._lan._dm_service`; if present, routes through
  `CombatService.next_turn()`, acquiring the service lock and triggering
  `_lan_force_state_broadcast()` after each mutation.
- Falls back to the direct `_next_turn()` call when the LAN server is not
  running (desktop-only mode, unit tests).

Effect: the DM web console and player clients now receive immediate state
pushes after desktop-originated turn advances, and concurrent desktop + web
mutations are serialised through the same lock.

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
- PC creation from YAML profiles (desktop-only; `POST /api/encounter/players/add`
  covers web-initiated PC adds)
- Complex HP mutation dialogs (damage/heal tool, spell attack flows) — these
  still call tracker engine methods directly; they trigger
  `_lan_force_state_broadcast()` after mutations so the web surface stays
  current via broadcast

---

## Hybrid concurrency model

Both the desktop UI and the DM web console can mutate combat state
concurrently.  The current safeguard model:

- HTTP route handlers run on the FastAPI thread and call tracker methods
  through `CombatService`, which holds a `threading.Lock`.
- Desktop-originated `_next_turn_via_service()` also acquires this lock,
  serialising concurrent desktop + web turn advances.
- Each mutation calls `_lan_force_state_broadcast()` which pushes updated
  state to all player WebSocket clients **and** to all connected DM
  WebSocket clients (`/ws/dm`).
- The desktop UI re-reads its state from the same `combatants` dict and
  `_rebuild_table()` call.

**Remaining hybrid risk**: Desktop-originated HP/condition mutations
(damage tool, attack flows) still call tracker engine methods directly and
do not acquire the `CombatService` lock.  A simultaneous desktop HP mutation
and web HP mutation could still race.  This is an acceptable risk for the
single-session LAN use case and is a recommended target for the next slice.

---

## YAML save / load compatibility

The `CombatService` mutations modify the in-memory `Combatant` objects that
the existing `_save_session()` / `_load_session()` serialisation paths
already serialise.  There are no schema changes.  Saving after DM console
mutations will correctly persist any HP, temp HP, condition, initiative, or
combatant-list changes made via the web.

---

## Recommended next migration targets

1. **Desktop HP mutation routing**: Route the desktop damage/heal tool and
   attack-flow HP mutations through `CombatService.adjust_hp()` so the
   service lock covers desktop-originated HP changes too.

2. **Monster-library-backed NPC creation**: Extend `POST /api/dm/combat/combatants`
   to accept a `monster_slug` or `monster_name` and populate the combatant
   from the YAML monster library, matching the desktop monster-add workflow.

3. **Token refresh**: The DM console does not yet auto-renew the admin token
   before expiry.  Add a background refresh 2 minutes before the 15-minute
   expiry window.

4. **Snapshot enhancements**: Additional fields (e.g. per-combatant AC tooltip,
   resource pools) can be added as the DM console grows.

---

## How to launch

1. Start the desktop app (`python dnd_initative_tracker.py`).
2. Enable the LAN server from the app (Settings → LAN Server → Start).
3. On any device on the same LAN, navigate to `http://<ip>:<port>/dm`.
4. If an admin password is configured, enter it when prompted.
5. The console will auto-populate with live combat state.
