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
| Go back to previous turn | `POST /api/dm/combat/prev-turn` |
| Set active combatant / turn | `POST /api/dm/combat/set-turn` |
| Adjust combatant HP | `POST /api/dm/combat/combatants/{cid}/hp` |
| Add/remove condition | `POST /api/dm/combat/combatants/{cid}/condition` |
| Set temporary HP | `POST /api/dm/combat/combatants/{cid}/temp-hp` |
| Adjust temporary HP (delta) | `POST /api/dm/combat/combatants/{cid}/temp-hp-adjust` |
| Add combatant | `POST /api/dm/combat/combatants` |
| Set initiative | `POST /api/dm/combat/combatants/{cid}/initiative` |
| Roll initiative (service-owned d20 path) | `POST /api/dm/combat/combatants/{cid}/initiative/roll` |
| List parsed monster attacks for a non-PC actor | `GET /api/dm/combat/combatants/{cid}/monster-attacks` |
| Resolve monster attack sequence (hit/miss + damage templates) | `POST /api/dm/combat/monster-attacks/resolve` |
| Apply manual monster attack damage | `POST /api/dm/combat/monster-attacks/apply-damage` |
| Execute non-PC perform_action command | `POST /api/dm/combat/combatants/{cid}/perform-action` |
| Execute non-PC targeted spell command | `POST /api/dm/combat/combatants/{cid}/spell-target` |
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

In addition to the HTTP endpoints above, the canonical service seam now owns
core encounter population for:

- YAML-backed **player-profile combatants** via
  `CombatService.add_player_profile_combatants()`
- **Monster-spec combatants** via
  `CombatService.add_monster_spec_combatants()`

---

## What the DM web UI can do

The DM web surface now has two DM entry points:

- `http://<lan-ip>:<port>/dm` — DM dashboard for initiative/session/control flow
- `http://<lan-ip>:<port>/dm/map` — dedicated DM map workspace with a full-size
  central tactical lane

Both routes use the same backend snapshot/mutation authority (`/api/dm/...`,
`/ws/dm`) and the same browser tactical logic.

The DM routes provide:

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
- **◀ Prev Turn** – goes back to the previous combatant's turn on the backend
- **Set Turn** – set the active combatant/turn to any combatant in the
  initiative list (per-combatant button shown during active combat)
- **HP Adjustment** – apply damage (negative) or healing (positive)
- **Set Temp HP** – set (or clear) temporary HP for any combatant
- **Add / Remove Condition** – apply any of the 15 standard D&D 5e conditions
- **Map bootstrap/setup** – create a new blank tactical map and set grid
  dimensions directly from DM web routes (no Tk map-size prompt required)
- **Tactical token control** – place/reposition, rules-aware move, and facing
  updates for combatants on the tactical map
- **Battlefield prep controls** – obstacle cell block/clear and rough-terrain
  cell edits (ground/water/clear)
- **Map authoring controls** – feature place/remove, structure place/move/remove,
  elevation cell edits, and background-layer asset/position/scale/lock/order
  updates from the browser tactical card
- **Live tactical effects** – hazard placement/removal (preset-backed),
  AoE placement/move/removal, and aura-overlay toggle
- **Advanced ship/template deployment** – browse structure templates and ship
  blueprints, preview ship placement blockers, instantiate templates/ships at a
  target cell/facing, and create/update/remove boarding links from DM web
  routes
- **Ship engagement operations** – load ship engagement summaries and run
  maneuver preview/apply, weapon fire, and ram actions from DM web routes
- **Monster turn controls** – select an enemy combatant as actor, load parsed
  monster attack options, resolve attack sequences, apply manual damage,
  execute `perform_action`, and run targeted spell requests through
  authenticated backend routes and existing snapshot/broadcast updates
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
  other admin-protected routes). While authenticated, the `/dm` client now
  schedules a bounded background refresh before expiry and replaces its
  in-memory token when refresh succeeds. If refresh fails because of token
  expiry/backend rejection, or repeated refresh-request transport failures
  exhaust retries, the console clears stale auth state and returns to the
  login overlay.

To configure an admin password, use the existing admin password configuration
in the desktop app settings.

---

## What the desktop still owns

The following areas remain desktop-primary (hybrid) after this pass:

- Full Tkinter canvas rendering and all desktop UI widgets
- Advanced Tk map editor workflows (template/ship blueprint authoring and edit
  tooling, higher-fidelity tactical overlays/debug tooling, and desktop tactical
  authoring conveniences beyond the browser tactical card)
- Full monster-action UX parity for every prompt-heavy or bespoke spell/action
  branch (browser currently covers enemy attack resolution/manual damage,
  `perform_action`, and targeted spell requests, but not every specialized cast
  path or rich prompt workflow)
- Player-facing LAN client at `/` (existing WebSocket + `/ws` routes)
- Character editor, sheet management (`/edit_character`, `/new_character`)
- Shop, item and spell management
- YAML-backed save / load (files are still owned by the desktop flow)
- Summon-driven, mount, and other generated combatant creation paths outside
  the migrated encounter-population entry points
- LAN claimed-player initiative prompt UX and response workflow
- Remaining spell-specific deep damage callers (Heat Metal, Hellish Rebuke,
  weapon-mastery attack paths) still call `_apply_damage_to_target_with_temp_hp`
  directly — these are candidates for future slices

The desktop app now **shares** the initiative/turn, HP, condition, and
deep damage/heal authority with the DM web console – they operate on the
same in-memory state through the same `_next_turn()` /
`_apply_damage_to_target_with_temp_hp()` / `_apply_heal_to_combatant()` /
`_ensure_condition_stack()` methods.

The player-facing LAN client reconnect path now keeps the connection UI in a
recovering state until fresh reconnect claim/snapshot/grid signals arrive, and
uses bounded `/ws` recovery requests (`state_request`, `grid_request`,
`terrain_request`) before escalating to another reconnect attempt.

### Desktop-routed through CombatService (Slice 9)

The following desktop/LAN-originated mutations now route through
`CombatService` when the service is running:

- **Desktop Start/Reset** → `_start_combat_via_service()` → `CombatService.start_combat()`
- **Desktop Prev Turn** → `_prev_turn_via_service()` → `CombatService.prev_turn()`
- **Desktop Next Turn** → `_next_turn_via_service()` → `CombatService.next_turn()`
- **Desktop Set Turn Here** → `_set_turn_here_via_service()` → `CombatService.set_turn_here()`
- **LAN player "end turn"** → `_next_turn_via_service()` → `CombatService.next_turn()`
- **LAN player manual HP override** → `CombatService.adjust_hp()` /
  `CombatService.adjust_temp_hp()`
- **LAN initiative prompt response (`initiative_roll`)** →
  `_set_initiative_via_service()` → `CombatService.set_initiative()`
- **Desktop `_adjust_hp_via_service()`** → `CombatService.adjust_hp()` (wrapper
  available for progressive adoption by other desktop code paths)
- **Encounter player-profile population** →
  `_add_player_profile_combatants_via_service()` →
  `CombatService.add_player_profile_combatants()` — current core callers:
  `/api/encounter/players/add` and desktop roster-manager “Add to Combat”
- **Encounter monster-spec population** →
  `_add_monster_spec_combatants_via_service()` →
  `CombatService.add_monster_spec_combatants()` — current core callers:
  desktop `Bulk Add…` monster-spec rows and `Random Enemies…`
- **Desktop `_set_condition_via_service()`** → `CombatService.set_condition()`
  (wrapper available for progressive adoption)
- **Desktop `_set_temp_hp_via_service()`** → `CombatService.set_temp_hp()`
  (wrapper available for progressive adoption)
- **Deep combat damage** → `_apply_damage_via_service()` →
  `CombatService.apply_damage()` — routes all identified core callers:
  attack resolution, spell AoE damage, start-of-turn damage riders,
  end-turn save-rider fail damage, end-of-turn damage riders, and the
  `_apply_damage_to_combatant` alias (Slice 9); Heat Metal, Hellish Rebuke,
  and weapon-mastery attack paths (Slice 10)
- **Healing** → `_apply_heal_via_service()` → `CombatService.apply_heal()` —
  wrapper available (Slice 9); heal dialog, Second Wind (LAN), and
  Lay on Hands (LAN) now route through the wrapper (Slice 10);
  Uncanny Metabolism, healing consumable use (potion etc.),
  spell healing resolution (Cure Wounds / Healing Word), Mantle of
  Inspiration temp HP, and Patient Defense Focus temp HP now route
  through the wrapper (Slice 11)
- **Long Rest batch HP restore** → `CombatService.batch_long_rest_heal()` →
  `apply_heal(_broadcast=False)` per target with single outer
  rebuild/broadcast (Slice 12)

All wrappers fall back to direct mutation + broadcast when the service is
not running (e.g. LAN server not started).

---

## Hybrid concurrency model

Both the desktop UI and the DM web console can mutate combat state
concurrently.  The current safeguard model:

- HTTP route handlers run on the FastAPI thread and call tracker methods
  directly, following the same pattern as existing LAN HTTP routes
  (e.g., `/api/encounter/players/add`).
- `CombatService` holds a `threading.RLock` (re-entrant) that serialises
  concurrent mutations (next-turn, prev-turn, set-turn-here, HP adjust,
  condition, temp HP, encounter population, deep damage, heal) from the web
  API and desktop-routed paths. The RLock is re-entrant so that end-of-turn
  or start-of-turn effects that trigger damage (which acquires the lock
  via `apply_damage`) can safely nest inside `next_turn` (which already
  holds the lock).
- Each mutation calls `_lan_force_state_broadcast()` which pushes updated
  state to all player WebSocket clients **and** to all connected DM
  WebSocket clients (`/ws/dm`).
- The desktop UI re-reads its state from the same `combatants` dict and
  `_rebuild_table()` call.

**Remaining risk**: The `CombatService` lock now covers all mutations that
go through the service, including web-originated, desktop-routed paths
(Start/Reset, Prev Turn, Next Turn, Set Turn Here, manual HP override),
player-profile encounter population, monster-spec encounter population,
all identified deep damage callers, all commonly used heal callers
(heal dialog, Second Wind, Lay on Hands, Uncanny Metabolism, healing
consumable use, spell healing resolution, Mantle of Inspiration temp HP,
Patient Defense Focus temp HP), Long Rest batch HP restoration
(Slice 12), and Wild Shape temp-HP apply/revert lifecycle routing.
This remains an acceptable risk for the single-session LAN use case.

---

## YAML save / load compatibility

The `CombatService` mutations modify the in-memory `Combatant` objects that
the existing `_save_session()` / `_load_session()` serialisation paths
already serialise.  There are no schema changes.  Saving after DM console
mutations will correctly persist any HP, temp HP, or condition changes made
via the web.

---

## Recommended next migration targets

1. **Tk-host/runtime extraction readiness**: start demoting Tk from runtime
   authority for the already migrated DM workflows while preserving existing
   backend snapshot/broadcast ownership.

2. **Residual advanced authoring parity**: close only the remaining high-value
   desktop-primary authoring/polish workflows (template/blueprint authoring/edit
   and overlay/debug UX) as needed for ongoing browser-first validation.

3. **Snapshot enhancements**: add operator-facing fields as needed
   (for example richer tactical metadata or resource tooltips) while keeping
   backend-owned authority.

4. **Token refresh diagnostics**: proactive DM token renewal is in place;
   follow-up telemetry can make refresh failures easier to diagnose in live LAN
   use.

5. **Player-facing LAN client state sync**: continue reconnect hardening and
   broadcast reliability work for `/ws`.

---

## How to launch

There are now two host modes. Both run the same `InitiativeTracker`
backend authority and serve the same `/dm`, `/dm/map`, and `/` web surfaces.

### Desktop / Tk host (compatibility entrypoint)

1. Start the desktop app (`python dnd_initative_tracker.py`).
2. Enable the LAN server from the app (LAN menu → Start LAN Server) if it
   did not auto-start.
3. On any device on the same LAN, navigate to `http://<ip>:<port>/dm` for the
   dashboard or `http://<ip>:<port>/dm/map` for the dedicated map workspace.
4. If an admin password is configured, enter it when prompted.
5. The console will auto-populate with live combat state.

### Headless / server host (Tk-optional entrypoint)

The first headless host extraction pass (2026-04-18) makes Tk optional
as the host shell. The headless mode does **not** open a Tk window and
does **not** require Tkinter to keep the process alive.

```bash
python3 serve_headless.py [--host 0.0.0.0] [--port 8787] [--no-auto-lan]
```

What happens under the hood:

- `serve_headless.py` sets `INIT_TRACKER_HEADLESS=1` before importing the
  tracker.
- `tk_compat.load_tk_modules()` then returns the headless module set with
  `tk.Tk` swapped for `tk_compat.HeadlessRoot`, which provides a real
  `after()`/`mainloop()` scheduler running on the main thread.
- The same `InitiativeTracker` runtime authority used in desktop mode is
  constructed, but startup now reads `self.host_mode`
  (`"headless"` when `INIT_TRACKER_HEADLESS=1`, else `"desktop"`) and
  skips the UI build for headless mode. The LAN poll tick, the
  FastAPI/uvicorn server thread, the DM/LAN WebSockets, and all
  backend-owned combat/session/map authority operate normally.
- `Ctrl+C` (or `SIGTERM`) shuts the LAN server down and exits cleanly.

The DM operator surface remains available at
`http://<host>:<port>/dm` and `http://<host>:<port>/dm/map` in both modes.

The host-mode seam (`self.host_mode`) now gates the following startup
blocks on `host_mode == "desktop"`:

- `self.title()`, `self.geometry()`, and `self.iconphoto()`
- `self._build_ui()` (the full Tk widget tree)
- `self._open_starting_players_dialog()` and the initial `_rebuild_table()`
- `self._install_lan_menu()` in `dnd_initative_tracker.InitiativeTracker`
- `self.after(0, self._install_monster_dropdown_widget)` swap

In headless mode, `_init_headless_state_stubs()` creates only the
`StringVar` mirrors that runtime paths (turn tracker, movement mode,
monster library filters) push values into, so those setters stay
side-effect-only without any widgets behind them.

The follow-on runtime seam pass adds an explicit desktop/headless
boundary for key widget-mutation paths:

- `helper_script.InitiativeTracker` now exposes
  `_host_supports_desktop_widgets()` +
  `_allow_desktop_runtime_surface(surface_name)` as the runtime host
  boundary.
- map-window construction now gates through that boundary in both
  classes (`helper_script._open_map_mode` and
  `dnd_initative_tracker._open_map_mode`), so headless runtime paths no
  longer instantiate a dummy map window.
- high-value desktop-only dialog/menu entrypoints now hard-gate on the
  boundary (`_show_dm_up_alert_dialog`, `_prompt_set_lan_https_public_url`,
  `_save_session_dialog`, `_load_session_dialog`, `_show_lan_url`,
  `_show_lan_qr`, `_open_roster_manager`, plus
  `_session_restore_supports_tk_refresh`).

Residual coupling worth knowing about:

- `helper_script.InitiativeTracker(tk.Tk)` and the
  `dnd_initative_tracker.InitiativeTracker` subclass still inherit from
  `tk.Tk` (which becomes `HeadlessRoot` in headless mode). Dropping the
  inheritance is a future structural pass.
- Many long-tail Tk dialogs/popup helpers (especially in
  `helper_script.py`) still call Tk directly and remain desktop-only;
  they now need the same explicit boundary treatment to remove the
  remaining dummy-widget runtime reliance.
- Features that only ever lived behind Tk dialogs (e.g. desktop map
  window UX, file-dialog driven save/load prompts) remain unreachable in
  headless mode by design; use `/api/dm/...` routes or `/dm`.
