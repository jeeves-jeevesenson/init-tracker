"""Canonical backend service seam for combat/session state.

This module is the authoritative source of truth for the migrated combat/session
slice.  Both the desktop UI and the DM web console read from and write through
this service rather than owning separate state.

Ownership model after this migration pass
------------------------------------------
Backend-owned (this service + API routes):
  - initiative order / turn order
  - current combatant / round / turn counters
  - HP adjustments (damage and healing) for any combatant
  - condition add/remove/toggle for any combatant
  - recent event/battle-log lines

Still hybrid / desktop-primary:
  - Full Tkinter canvas UI rendering
  - Map / battle-map state
  - Player-facing LAN client (existing /ws WebSocket + /lan routes)
  - Character editor, shop, spell/resource management
  - YAML-backed save/load (unchanged; mutations here persist via existing path)

Next recommended migration targets:
  - HP/condition mutations from desktop directly wired through this service
  - A real-time WebSocket push from service → DM console
  - Parity with the full set of desktop DM actions

Usage (from LanController routes):
  service = CombatService(tracker_instance)
  snap = service.combat_snapshot()
  service.next_turn()
  service.adjust_hp(cid=3, delta=-5)
  service.set_condition(cid=3, ctype="poisoned", action="add")
"""
from __future__ import annotations

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
            "in_combat":   bool,
            "round":       int,
            "turn":        int,
            "active_cid":  int | None,
            "turn_order":  [int, ...],
            "combatants":  [{cid, name, hp, max_hp, ac, role,
                             is_pc, conditions, initiative}, ...],
            "battle_log":  [str, ...],    # last 30 lines
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
