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
| Advance to next turn | `POST /api/dm/combat/next-turn` |
| Adjust combatant HP | `POST /api/dm/combat/combatants/{cid}/hp` |
| Add/remove condition | `POST /api/dm/combat/combatants/{cid}/condition` |
| Set temporary HP | `POST /api/dm/combat/combatants/{cid}/temp-hp` |
| Real-time DM state push | `WS /ws/dm[?token=…]` |

The **snapshot shape** (from `GET /api/dm/combat`):

```json
{
  "in_combat": true,
  "round": 3,
  "turn": 7,
  "active_cid": 2,
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
- All combatant creation, initiative rolling, and encounter setup

The desktop app now **shares** the initiative/turn, HP, and condition
authority with the DM web console – they operate on the same in-memory
state through the same `_next_turn()` / `_apply_damage_to_combatant()` /
`_ensure_condition_stack()` methods.

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

**Remaining risk**: The `CombatService` lock only covers mutations that go
through the service.  Desktop-originated mutations (button clicks in the
Tkinter UI) do not acquire this lock, so a simultaneous desktop + web
mutation could still race.  This is an acceptable risk for the single-session
LAN use case.

---

## YAML save / load compatibility

The `CombatService` mutations modify the in-memory `Combatant` objects that
the existing `_save_session()` / `_load_session()` serialisation paths
already serialise.  There are no schema changes.  Saving after DM console
mutations will correctly persist any HP, temp HP, or condition changes made
via the web.

---

## Recommended next migration targets

1. **Combatant creation / encounter start**: Expose encounter setup
   (add combatants, roll initiative, start/stop combat) through the service
   so the DM console can manage a full session.

2. **Desktop rewiring**: Route the desktop "Next Turn" button and HP/condition
   mutations through `CombatService` explicitly so the service lock covers
   desktop-originated mutations too.

3. **Token refresh**: The DM console does not yet auto-renew the admin token
   before expiry.  Add a background refresh 2 minutes before the 15-minute
   expiry window.

4. **Snapshot enhancements**: Add `up_next_cid` / `up_next_name` to the
   snapshot payload so the DM console can show the upcoming combatant.

---

## How to launch

1. Start the desktop app (`python dnd_initative_tracker.py`).
2. Enable the LAN server from the app (Settings → LAN Server → Start).
3. On any device on the same LAN, navigate to `http://<ip>:<port>/dm`.
4. If an admin password is configured, enter it when prompted.
5. The console will auto-populate with live combat state.
