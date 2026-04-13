"""Canonical backend service seam for combat/session state.

This module is the authoritative source of truth for the migrated combat/session
slice.  Both the desktop UI and the DM web console read from and write through
this service rather than owning separate state.

Ownership model after this migration pass (Slice 6)
-----------------------------------------------------
Backend-owned (this service + API routes):
  - combat lifecycle: start (begin initiative turn order), end (reset turn state)
  - initiative order / turn order
  - current combatant / round / turn counters
  - up-next combatant preview
  - HP adjustments (damage and healing) for any combatant
  - condition add/remove/toggle for any combatant
  - temp HP set/clear and delta-adjust for any combatant
  - recent event/battle-log lines
  - combatant creation / encounter population (quick-add via backend API)
  - initiative set / update for existing combatants
  - combatant removal

Desktop-routed through this service (Slice 6):
  - desktop Next Turn routes through CombatService.next_turn() via
    _next_turn_via_service() so the lock, log, and broadcast paths are shared
  - LAN player "end turn" routes through _next_turn_via_service()
  - LAN player manual_override_hp routes through CombatService.adjust_hp /
    adjust_temp_hp so the service lock and broadcast cover player-originated
    HP/temp-HP overrides
  - Desktop HP adjust, condition set, and temp HP set have _*_via_service()
    wrappers available for progressive adoption

Still hybrid / desktop-primary:
  - Full Tkinter canvas UI rendering
  - Map / battle-map state
  - Player-facing LAN client (existing /ws WebSocket + /lan routes)
  - Character editor, shop, spell/resource management
  - YAML-backed save/load (unchanged; mutations here persist via existing path)
  - Full monster-spec / player-profile based combatant creation (desktop only)
  - Advanced initiative manipulation (set-turn-here, prev-turn, start/reset)
  - Deep combat engine damage paths (_apply_damage_to_target_with_temp_hp)
    still mutate state directly; these are candidates for future slices

Next recommended migration targets:
  - Route deep combat engine damage/heal paths through service wrappers
  - Expose full initiative-roll support so DM web can trigger rolls
  - Player-facing LAN client state sync improvements

Usage (from LanController routes):
  service = CombatService(tracker_instance)
  snap = service.combat_snapshot()
  service.start_combat()
  service.next_turn()
  service.adjust_hp(cid=3, delta=-5)
  service.set_condition(cid=3, ctype="poisoned", action="add")
  service.end_combat()
"""
from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    # Avoid circular import at runtime; the tracker module imports helper_script
    # which defines ConditionStack / Combatant used below.
    from dnd_initative_tracker import InitiativeTracker


# Conditions recognised by the tracker engine (subset shown in DM console).
# Full list lives in helper_script.CONDITIONS_META.
KNOWN_CONDITIONS = {
    "blinded",
    "charmed",
    "deafened",
    "exhaustion",
    "frightened",
    "grappled",
    "incapacitated",
    "invisible",
    "paralyzed",
    "petrified",
    "poisoned",
    "prone",
    "restrained",
    "stunned",
    "unconscious",
}


class CombatService:
    """Thin service wrapper that exposes canonical combat/session operations.

    The service delegates to the existing ``InitiativeTracker`` game engine so
    that no combat rules are duplicated here.  It is safe to call from the
    FastAPI/background thread following the same pattern as the existing HTTP
    route handlers in ``LanController``.
    """

    def __init__(self, tracker: "InitiativeTracker") -> None:
        if tracker is None:
            raise ValueError("CombatService requires an InitiativeTracker instance.")
        self._tracker = tracker
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Read: snapshot
    # ------------------------------------------------------------------

    def combat_snapshot(self) -> Dict[str, Any]:
        """Return a stable, DM-focused snapshot of the current combat state.

        Pulls from the tracker's in-memory combatant list rather than the
        full LAN snapshot (which includes map/AoE data the DM console does not
        need).  This keeps the read fast and independent of map-window state.

        Shape:
          {
            "in_combat":    bool,
            "round":        int,
            "turn":         int,
            "active_cid":   int | None,
            "up_next_cid":  int | None,
            "up_next_name": str | None,
            "turn_order":   [int, ...],
            "combatants":   [{cid, name, hp, max_hp, ac, role,
                              is_pc, conditions, initiative}, ...],
            "battle_log":   [str, ...],    # last 30 lines
          }
        """
        t = self._tracker
        combatants = getattr(t, "combatants", {}) or {}
        current_cid = getattr(t, "current_cid", None)
        round_num = int(getattr(t, "round_num", 0) or 0)
        turn_num = int(getattr(t, "turn_num", 0) or 0)
        in_combat = bool(getattr(t, "in_combat", False))

        # Build ordered list using the tracker's display ordering when available
        try:
            ordered_cids: List[int] = [
                int(c.cid)
                for c in t._display_order()
                if getattr(c, "cid", None) is not None
            ]
        except Exception:
            ordered_cids = sorted(combatants.keys())

        combatant_rows: List[Dict[str, Any]] = []
        for cid in ordered_cids:
            c = combatants.get(cid)
            if c is None:
                continue
            hp = int(getattr(c, "hp", 0) or 0)
            max_hp = int(getattr(c, "max_hp", hp) or hp)
            ac = int(getattr(c, "ac", 0) or 0)
            temp_hp = int(getattr(c, "temp_hp", 0) or 0)
            initiative = int(getattr(c, "initiative", 0) or 0)
            is_pc = bool(getattr(c, "is_pc", False))
            role = str(
                (getattr(t, "_name_role_memory", {}) or {}).get(
                    str(getattr(c, "name", "") or ""), "enemy"
                )
                or "enemy"
            )

            # Conditions: extract from condition_stacks
            stacks = list(getattr(c, "condition_stacks", []) or [])
            conditions: List[Dict[str, Any]] = []
            for st in stacks:
                ctype = str(getattr(st, "ctype", "") or "")
                remaining = getattr(st, "remaining_turns", None)
                if not ctype:
                    continue
                conditions.append(
                    {
                        "type": ctype,
                        "remaining_turns": remaining,
                    }
                )

            combatant_rows.append(
                {
                    "cid": int(cid),
                    "name": str(getattr(c, "name", "") or ""),
                    "hp": hp,
                    "max_hp": max_hp,
                    "temp_hp": temp_hp,
                    "ac": ac,
                    "initiative": initiative,
                    "is_pc": is_pc,
                    "role": role,
                    "conditions": conditions,
                    "is_current": current_cid is not None and int(cid) == int(current_cid),
                }
            )

        # Up-next combatant (useful for "you're up after X" display in DM console)
        up_next_cid: Optional[int] = None
        up_next_name: Optional[str] = None
        try:
            peek = getattr(t, "_peek_next_turn_cid", None)
            if callable(peek):
                raw_next = peek(current_cid)
                if raw_next is not None:
                    up_next_cid = int(raw_next)
                    up_next_c = combatants.get(up_next_cid)
                    if up_next_c is not None:
                        up_next_name = str(getattr(up_next_c, "name", "") or "")
        except Exception:
            pass

        # Battle log: last 30 lines from the tracker's history file
        battle_log: List[str] = []
        try:
            battle_log = t._lan_battle_log_lines(limit=30)
        except Exception:
            battle_log = []

        return {
            "in_combat": in_combat,
            "round": round_num,
            "turn": turn_num,
            "active_cid": int(current_cid) if current_cid is not None else None,
            "up_next_cid": up_next_cid,
            "up_next_name": up_next_name,
            "turn_order": ordered_cids,
            "combatants": combatant_rows,
            "battle_log": battle_log,
        }

    # ------------------------------------------------------------------
    # Write: mutations
    # ------------------------------------------------------------------

    def next_turn(self) -> Dict[str, Any]:
        """Advance to the next combatant's turn.

        Delegates to ``_next_turn()`` on the tracker (same method the desktop
        Next Turn button invokes), then broadcasts state to all LAN clients and
        returns the updated snapshot.
        """
        with self._lock:
            t = self._tracker
            try:
                t._next_turn()
            except Exception as exc:
                return {"ok": False, "error": str(exc), "snapshot": self.combat_snapshot()}
            try:
                t._rebuild_table(scroll_to_current=True)
            except Exception:
                pass
            try:
                t._lan_force_state_broadcast()
            except Exception:
                pass
            return {"ok": True, "snapshot": self.combat_snapshot()}

    def adjust_hp(self, cid: int, delta: int) -> Dict[str, Any]:
        """Adjust HP for combatant ``cid`` by ``delta`` (negative = damage, positive = healing).

        Clamps result to [0, max_hp].  Delegates to the same logic used by
        manual_override_hp in _lan_apply_action.
        """
        with self._lock:
            t = self._tracker
            combatants = getattr(t, "combatants", {}) or {}
            c = combatants.get(int(cid))
            if c is None:
                return {"ok": False, "error": f"Combatant {cid} not found."}

            old_hp = int(getattr(c, "hp", 0) or 0)
            max_hp = int(getattr(c, "max_hp", old_hp) or old_hp)
            new_hp = max(0, old_hp + int(delta))
            if max_hp > 0:
                new_hp = min(new_hp, max_hp)
            setattr(c, "hp", new_hp)

            direction = "healed" if delta > 0 else "damaged"
            try:
                t._log(
                    f"{getattr(c, 'name', 'Combatant')} {direction} by {abs(delta)}"
                    f" (HP {old_hp} → {new_hp}).",
                    cid=int(cid),
                )
            except Exception:
                pass
            try:
                t._rebuild_table(scroll_to_current=True)
            except Exception:
                pass
            try:
                t._lan_force_state_broadcast()
            except Exception:
                pass
            return {
                "ok": True,
                "cid": int(cid),
                "hp_before": old_hp,
                "hp_after": new_hp,
                "delta": int(delta),
            }

    def set_condition(
        self,
        cid: int,
        ctype: str,
        action: str,
        remaining_turns: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Add or remove a condition from combatant ``cid``.

        Args:
            cid:            Combatant ID.
            ctype:          Condition key (e.g. ``"poisoned"``).
            action:         ``"add"`` or ``"remove"``.
            remaining_turns: How many turns the condition lasts (None = indefinite).

        Delegates to ``_ensure_condition_stack`` / ``_remove_condition_type``
        which are the same helpers used throughout the tracker engine.
        """
        with self._lock:
            t = self._tracker
            combatants = getattr(t, "combatants", {}) or {}
            c = combatants.get(int(cid))
            if c is None:
                return {"ok": False, "error": f"Combatant {cid} not found."}

            ctype_key = str(ctype or "").strip().lower()
            if not ctype_key:
                return {"ok": False, "error": "Condition type must not be empty."}

            action_key = str(action or "").strip().lower()
            if action_key not in ("add", "remove"):
                return {"ok": False, "error": "Action must be 'add' or 'remove'."}

            if action_key == "add":
                try:
                    t._ensure_condition_stack(c, ctype_key, remaining_turns)
                except Exception as exc:
                    return {"ok": False, "error": str(exc)}
                try:
                    t._log(
                        f"{getattr(c, 'name', 'Combatant')} gained condition: {ctype_key}.",
                        cid=int(cid),
                    )
                except Exception:
                    pass
            else:
                try:
                    t._remove_condition_type(c, ctype_key)
                except Exception as exc:
                    return {"ok": False, "error": str(exc)}
                try:
                    t._log(
                        f"{getattr(c, 'name', 'Combatant')} lost condition: {ctype_key}.",
                        cid=int(cid),
                    )
                except Exception:
                    pass

            try:
                t._rebuild_table(scroll_to_current=True)
            except Exception:
                pass
            try:
                t._lan_force_state_broadcast()
            except Exception:
                pass

            return {
                "ok": True,
                "cid": int(cid),
                "ctype": ctype_key,
                "action": action_key,
            }

    def set_temp_hp(self, cid: int, amount: int) -> Dict[str, Any]:
        """Set temporary HP for combatant ``cid`` to ``amount`` (0 clears temp HP).

        Unlike HP adjustments, temp HP is set to an absolute value rather than
        adjusted by a delta.  Setting to 0 removes all temporary HP.
        """
        with self._lock:
            t = self._tracker
            combatants = getattr(t, "combatants", {}) or {}
            c = combatants.get(int(cid))
            if c is None:
                return {"ok": False, "error": f"Combatant {cid} not found."}

            amount = max(0, int(amount))
            old_temp = int(getattr(c, "temp_hp", 0) or 0)
            setattr(c, "temp_hp", amount)

            try:
                t._log(
                    f"{getattr(c, 'name', 'Combatant')} temp HP set to {amount}"
                    f" (was {old_temp}).",
                    cid=int(cid),
                )
            except Exception:
                pass
            try:
                t._rebuild_table(scroll_to_current=True)
            except Exception:
                pass
            try:
                t._lan_force_state_broadcast()
            except Exception:
                pass
            return {
                "ok": True,
                "cid": int(cid),
                "temp_hp_before": old_temp,
                "temp_hp_after": amount,
            }

    def adjust_temp_hp(self, cid: int, delta: int) -> Dict[str, Any]:
        """Adjust temporary HP for combatant ``cid`` by ``delta``.

        Unlike ``set_temp_hp`` which sets an absolute value, this method
        applies a delta (positive to add, negative to remove temp HP).
        The result is clamped to a minimum of 0.  This is the temp-HP
        counterpart to ``adjust_hp``.

        Returns: {ok, cid, temp_hp_before, temp_hp_after, delta}
          or  {ok: False, error: str}
        """
        with self._lock:
            t = self._tracker
            combatants = getattr(t, "combatants", {}) or {}
            c = combatants.get(int(cid))
            if c is None:
                return {"ok": False, "error": f"Combatant {cid} not found."}

            old_temp = int(getattr(c, "temp_hp", 0) or 0)
            new_temp = max(0, old_temp + int(delta))
            setattr(c, "temp_hp", new_temp)

            direction = "gained" if delta > 0 else "lost"
            try:
                t._log(
                    f"{getattr(c, 'name', 'Combatant')} {direction} {abs(delta)}"
                    f" temp HP ({old_temp} → {new_temp}).",
                    cid=int(cid),
                )
            except Exception:
                pass
            try:
                t._rebuild_table(scroll_to_current=True)
            except Exception:
                pass
            try:
                t._lan_force_state_broadcast()
            except Exception:
                pass
            return {
                "ok": True,
                "cid": int(cid),
                "temp_hp_before": old_temp,
                "temp_hp_after": new_temp,
                "delta": int(delta),
            }

    def start_combat(self) -> Dict[str, Any]:
        """Start combat by beginning the initiative turn order.

        Delegates to ``_start_turns()`` on the tracker — the same method
        the desktop Start/Reset button uses.  Sets ``in_combat = True`` so
        the DM web surface and LAN clients see an active combat state.

        Requires at least one combatant to be present in the initiative list.
        Returns: {ok, snapshot}  or  {ok: False, error: str}
        """
        with self._lock:
            t = self._tracker
            combatants = getattr(t, "combatants", {}) or {}
            if not combatants:
                return {"ok": False, "error": "No combatants in the initiative list."}
            try:
                t._start_turns()
            except Exception:
                return {"ok": False, "error": "Could not start combat.", "snapshot": self.combat_snapshot()}
            # Explicitly mark in_combat so the flag is truthful for this session.
            t.in_combat = True
            try:
                t._lan_force_state_broadcast()
            except Exception:
                pass
            return {"ok": True, "snapshot": self.combat_snapshot()}

    def end_combat(self) -> Dict[str, Any]:
        """End the current combat, resetting turn tracking.

        Clears the active combatant turn, marks ``in_combat = False``, and
        broadcasts the updated state to all connected clients.  The
        combatant list and battle log are preserved so the DM can review
        the final encounter state.

        Returns: {ok, snapshot}
        """
        with self._lock:
            t = self._tracker
            old_round = int(getattr(t, "round_num", 1) or 1)
            t.in_combat = False
            t.current_cid = None
            try:
                t._log(f"--- COMBAT ENDED (after round {old_round}) ---")
            except Exception:
                pass
            try:
                t._rebuild_table(scroll_to_current=True)
            except Exception:
                pass
            try:
                t._lan_force_state_broadcast()
            except Exception:
                pass
            return {"ok": True, "snapshot": self.combat_snapshot()}

    # ------------------------------------------------------------------
    # Encounter setup: combatant management
    # ------------------------------------------------------------------

    def add_combatant(
        self,
        name: str,
        hp: int,
        initiative: int,
        *,
        max_hp: Optional[int] = None,
        ac: int = 10,
        speed: int = 30,
        ally: bool = False,
        is_pc: bool = False,
    ) -> Dict[str, Any]:
        """Add a combatant to the encounter via the backend service path.

        This is a lightweight quick-add that creates a minimal combatant
        (name, HP, initiative, AC, speed, ally/is_pc flags).  For full
        monster-spec or player-profile based creation, use the desktop UI.

        Args:
            name:       Combatant display name.
            hp:         Starting HP (also used as max_hp when max_hp is None).
            initiative: Initiative value (higher goes earlier).
            max_hp:     Maximum HP; defaults to hp when omitted.
            ac:         Armour class (default 10).
            speed:      Movement speed in feet (default 30).
            ally:       True for allied NPCs; False for enemies (default False).
            is_pc:      True for player characters (default False).

        Returns: {ok, cid, snapshot}  or  {ok: False, error: str}
        """
        name = str(name or "").strip()
        if not name:
            return {"ok": False, "error": "Combatant name must not be empty."}
        try:
            hp = max(0, int(hp))
        except Exception:
            return {"ok": False, "error": "hp must be a non-negative integer."}
        try:
            initiative = int(initiative)
        except Exception:
            return {"ok": False, "error": "initiative must be an integer."}
        if max_hp is None:
            max_hp = hp
        try:
            max_hp = max(0, int(max_hp))
        except Exception:
            max_hp = hp
        # Enforce invariant: 0 <= hp <= max_hp
        if max_hp > 0:
            hp = min(hp, max_hp)
        try:
            ac = max(0, int(ac))
        except Exception:
            ac = 10
        try:
            speed = max(0, int(speed))
        except Exception:
            speed = 30

        with self._lock:
            t = self._tracker
            try:
                cid = t._create_combatant(
                    name=name,
                    hp=hp,
                    speed=speed,
                    initiative=initiative,
                    dex=None,
                    ally=bool(ally),
                    is_pc=bool(is_pc),
                )
            except Exception:
                return {"ok": False, "error": "Could not add combatant."}

            # Set max_hp and ac after creation (not all tracker builds accept them
            # as _create_combatant kwargs).
            c = (getattr(t, "combatants", {}) or {}).get(cid)
            if c is not None:
                if not hasattr(c, "max_hp") or getattr(c, "max_hp", None) is None:
                    setattr(c, "max_hp", max_hp)
                if not hasattr(c, "ac") or getattr(c, "ac", None) is None:
                    setattr(c, "ac", ac)
                else:
                    # Overwrite AC if caller passed a non-default value.
                    if ac != 10:
                        setattr(c, "ac", ac)

            try:
                t._log(
                    f"Combatant added via backend: {name} (HP {hp}, init {initiative}).",
                    cid=cid,
                )
            except Exception:
                pass
            try:
                t._rebuild_table(scroll_to_current=True)
            except Exception:
                pass
            try:
                t._lan_force_state_broadcast()
            except Exception:
                pass
            return {"ok": True, "cid": cid, "snapshot": self.combat_snapshot()}

    def set_initiative(self, cid: int, initiative: int) -> Dict[str, Any]:
        """Update the initiative value for an existing combatant.

        Triggers a table rebuild and state broadcast so desktop and web
        consumers see the updated initiative order immediately.

        Args:
            cid:        Combatant ID.
            initiative: New initiative value.

        Returns: {ok, cid, initiative_before, initiative_after, snapshot}
          or  {ok: False, error: str}
        """
        try:
            initiative = int(initiative)
        except Exception:
            return {"ok": False, "error": "initiative must be an integer."}

        with self._lock:
            t = self._tracker
            combatants = getattr(t, "combatants", {}) or {}
            c = combatants.get(int(cid))
            if c is None:
                return {"ok": False, "error": f"Combatant {cid} not found."}

            old_init = int(getattr(c, "initiative", 0) or 0)
            c.initiative = initiative

            try:
                t._log(
                    f"{getattr(c, 'name', 'Combatant')} initiative changed:"
                    f" {old_init} → {initiative}.",
                    cid=int(cid),
                )
            except Exception:
                pass
            try:
                t._rebuild_table(scroll_to_current=True)
            except Exception:
                pass
            try:
                t._lan_force_state_broadcast()
            except Exception:
                pass
            return {
                "ok": True,
                "cid": int(cid),
                "initiative_before": old_init,
                "initiative_after": initiative,
                "snapshot": self.combat_snapshot(),
            }

    def remove_combatant(self, cid: int) -> Dict[str, Any]:
        """Remove a combatant from the encounter.

        Delegates to ``_remove_combatants_with_lan_cleanup`` when available
        (preferred: properly handles LAN aoe / tracking cleanup), otherwise
        falls back to a direct combatants-dict pop.

        Returns: {ok, cid, snapshot}  or  {ok: False, error: str}
        """
        with self._lock:
            t = self._tracker
            combatants = getattr(t, "combatants", {}) or {}
            cid = int(cid)
            c = combatants.get(cid)
            if c is None:
                return {"ok": False, "error": f"Combatant {cid} not found."}

            name = str(getattr(c, "name", "") or "")
            cleanup = getattr(t, "_remove_combatants_with_lan_cleanup", None)
            if callable(cleanup):
                try:
                    cleanup([cid])
                except Exception:
                    return {"ok": False, "error": "Could not remove combatant."}
            else:
                combatants.pop(cid, None)
                if getattr(t, "current_cid", None) == cid:
                    t.current_cid = None

            try:
                t._log(f"Combatant removed via backend: {name} (cid {cid}).")
            except Exception:
                pass
            try:
                t._rebuild_table(scroll_to_current=True)
            except Exception:
                pass
            try:
                t._lan_force_state_broadcast()
            except Exception:
                pass
            return {"ok": True, "cid": cid, "snapshot": self.combat_snapshot()}
