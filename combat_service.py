"""Canonical backend service seam for combat/session state.

This module is the authoritative source of truth for the migrated combat/session
slice.  Both the desktop UI and the DM web console read from and write through
this service rather than owning separate state.

Ownership model after this migration pass
-----------------------------------------------------
Backend-owned (this service + API routes):
  - combat lifecycle: start (begin initiative turn order), end (reset turn state)
  - initiative order / turn order (forward and backward)
  - set-turn-here / select active combatant
  - current combatant / round / turn counters
  - up-next combatant preview
  - HP adjustments (damage and healing) for any combatant
  - condition add/remove/toggle for any combatant
  - temp HP set/clear and delta-adjust for any combatant
  - recent event/battle-log lines
  - combatant creation / encounter population (quick-add via backend API)
  - combatant creation / encounter population from player profiles
  - combatant creation / encounter population from monster specs
  - initiative set / update for existing combatants
  - initiative roll for existing combatants
  - combatant removal
  - prev-turn (go back one step in initiative order)
  - deep combat damage with temp HP absorption (apply_damage) — Slice 9
  - healing (apply_heal) — Slice 9

Desktop-routed through this service (Slice 9):
  - desktop Next Turn routes through CombatService.next_turn() via
    _next_turn_via_service() so the lock, log, and broadcast paths are shared
  - desktop Prev Turn routes through CombatService.prev_turn() via
    _prev_turn_via_service() so the lock and broadcast paths are shared
  - desktop Start/Reset routes through CombatService.start_combat() via
    _start_combat_via_service() so the lock and broadcast paths are shared
  - desktop Set Turn Here routes through CombatService.set_turn_here() via
    _set_turn_here_via_service() so the lock and broadcast paths are shared
  - LAN player "end turn" routes through _next_turn_via_service()
  - LAN player manual_override_hp routes through CombatService.adjust_hp /
    adjust_temp_hp so the service lock and broadcast cover player-originated
    HP/temp-HP overrides
  - Desktop HP adjust, condition set, and temp HP set have _*_via_service()
    wrappers available for progressive adoption
  - Deep combat damage (_apply_damage_to_target_with_temp_hp) routes through
    CombatService.apply_damage via _apply_damage_via_service() for all
    identified core callers: attack resolution, spell AoE, start/end-of-turn
    damage riders (Slice 9), Heat Metal, Hellish Rebuke, weapon-mastery
    attack paths (Slice 10)
  - Healing (_apply_heal_to_combatant) routes through
    CombatService.apply_heal via _apply_heal_via_service() — wrapper
    available (Slice 9); heal dialog, Second Wind, and Lay on Hands now
    route through the wrapper (Slice 10); Uncanny Metabolism, healing
    consumable use, spell healing resolution (Cure Wounds / Healing Word),
    Mantle of Inspiration temp HP, and Patient Defense Focus temp HP now
    route through the wrapper (Slice 11)

Still hybrid / desktop-primary:
  - Full Tkinter canvas UI rendering
  - Map / battle-map state
  - Player-facing LAN client (existing /ws WebSocket + /lan routes)
  - Character editor, shop, spell/resource management
  - YAML-backed save/load (unchanged; mutations here persist via existing path)
  - Spell/summon-generated combatant creation outside the migrated encounter
    population entry points
  - Long rest batch HP restore now routes through
    CombatService.batch_long_rest_heal() → apply_heal() (Slice 12)
  - Wild Shape temp HP lifecycle now routes through service-owned temp HP setters

Next recommended migration targets:
  - Player-facing LAN client state sync improvements

Usage (from LanController routes):
  service = CombatService(tracker_instance)
  snap = service.combat_snapshot()
  service.start_combat()
  service.next_turn()
  service.prev_turn()
  service.set_turn_here(cid=2)
  service.adjust_hp(cid=3, delta=-5)
  service.add_player_profile_combatants(["Fighter"])
  service.add_monster_spec_combatants([{"name": "Goblin 1", "monster_slug": "goblin", "initiative": 12}])
  service.apply_damage(cid=3, raw_damage=12)
  service.apply_heal(cid=3, amount=8)
  service.set_condition(cid=3, ctype="poisoned", action="add")
  service.end_combat()
"""
from __future__ import annotations

import random
import threading
import os
import time
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
        self._lock = threading.RLock()

    @staticmethod
    def _perf_debug_enabled() -> bool:
        return os.getenv("LAN_PERF_DEBUG") == "1"

    def _perf_log(self, label: str, started_at: float, **fields: Any) -> None:
        if started_at <= 0.0:
            return
        elapsed_ms = (time.perf_counter() - started_at) * 1000.0
        extras = " ".join(f"{key}={value}" for key, value in fields.items())
        message = f"LAN_PERF {label} elapsed_ms={elapsed_ms:.2f}"
        if extras:
            message = f"{message} {extras}"
        oplog = getattr(self._tracker, "_oplog", None)
        if callable(oplog):
            try:
                oplog(message, level="info")
            except Exception:
                pass

    def _broadcast_tracker_state(self, *, include_static: bool = False) -> None:
        """Broadcast tracker state with compatibility fallback for legacy stubs."""
        t = self._tracker
        broadcast = getattr(t, "_lan_force_state_broadcast", None)
        if not callable(broadcast):
            return
        try:
            broadcast(include_static=bool(include_static))
        except TypeError:
            try:
                broadcast()
            except Exception:
                pass
        except Exception:
            pass

    def _refresh_tracker_outputs(self) -> None:
        """Refresh desktop UI and LAN state without blocking server threads."""
        t = self._tracker

        hold_factory = getattr(t, "_player_yaml_cache_hold", None)

        def _refresh() -> None:
            hold_cm = hold_factory() if callable(hold_factory) else None
            try:
                if hold_cm is not None:
                    hold_cm.__enter__()
                try:
                    t._rebuild_table(scroll_to_current=True)
                except Exception:
                    pass
                self._broadcast_tracker_state(include_static=False)
            finally:
                if hold_cm is not None:
                    try:
                        hold_cm.__exit__(None, None, None)
                    except Exception:
                        pass

        after = getattr(t, "after", None)
        if callable(after) and threading.current_thread() is not threading.main_thread():
            try:
                after(0, _refresh)
                return
            except Exception:
                pass
        _refresh()

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
                              speed, passive_perception,
                              temp_hp, defenses, concentration/state markers,
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

        def _role_for_combatant(combatant: Any) -> str:
            if bool(getattr(combatant, "is_pc", False)):
                return "pc"
            if bool(getattr(combatant, "ally", False)):
                return "ally"
            role_for_name = getattr(t, "_role_for_name", None)
            if callable(role_for_name):
                try:
                    role = str(role_for_name(str(getattr(combatant, "name", "") or "")) or "").strip().lower()
                except Exception:
                    role = ""
                if role in {"pc", "ally", "enemy"}:
                    return role
            return "enemy"

        def _titleize_key(value: Any) -> str:
            text = str(value or "").strip().replace("_", " ").replace("-", " ")
            return " ".join(part.capitalize() for part in text.split())

        def _passive_perception_for(combatant: Any) -> Optional[int]:
            getter = getattr(t, "_observer_passive_perception", None)
            if not callable(getter):
                return None
            try:
                value = int(getter(combatant))
            except Exception:
                return None
            return value if value > 0 else None

        def _defense_lists_for(combatant: Any) -> Dict[str, List[str]]:
            empty = {
                "damage_resistances": [],
                "damage_immunities": [],
                "damage_vulnerabilities": [],
                "condition_immunities": [],
            }
            getter = getattr(t, "_combatant_defense_sets", None)
            if not callable(getter):
                return empty
            try:
                raw = getter(combatant)
            except Exception:
                return empty
            if not isinstance(raw, dict):
                return empty

            def _normalize_list(key: str) -> List[str]:
                values = raw.get(key) or set()
                if not isinstance(values, (list, tuple, set)):
                    return []
                return sorted(
                    {
                        str(item).strip().lower()
                        for item in values
                        if str(item or "").strip()
                    }
                )

            return {
                "damage_resistances": _normalize_list("damage_resistances"),
                "damage_immunities": _normalize_list("damage_immunities"),
                "damage_vulnerabilities": _normalize_list("damage_vulnerabilities"),
                "condition_immunities": _normalize_list("condition_immunities"),
            }

        def _state_markers_for(combatant: Any) -> List[Dict[str, Any]]:
            markers: List[Dict[str, Any]] = []
            concentration_spell = _titleize_key(getattr(combatant, "concentration_spell", ""))
            if bool(getattr(combatant, "concentrating", False)):
                markers.append(
                    {
                        "key": "concentration",
                        "label": "Concentration",
                        "detail": concentration_spell or None,
                        "tone": "accent",
                    }
                )
            if bool(getattr(combatant, "is_hidden", False)):
                markers.append({"key": "hidden", "label": "Hidden", "detail": None, "tone": "neutral"})
            if bool(getattr(combatant, "is_wild_shaped", False)):
                form_name = str(
                    getattr(combatant, "wild_shape_form_name", "")
                    or getattr(combatant, "wild_shape_form", "")
                    or ""
                ).strip()
                markers.append(
                    {
                        "key": "wild_shape",
                        "label": "Wild Shape",
                        "detail": form_name or None,
                        "tone": "accent",
                    }
                )
            if getattr(combatant, "summoned_by_cid", None) is not None:
                summon_source = _titleize_key(getattr(combatant, "summon_source_spell", ""))
                markers.append(
                    {
                        "key": "summoned",
                        "label": "Summoned",
                        "detail": summon_source or None,
                        "tone": "warn",
                    }
                )
            if getattr(combatant, "mounted_by_cid", None) is not None:
                markers.append({"key": "mounted", "label": "Mounted", "detail": None, "tone": "neutral"})
            elif bool(getattr(combatant, "is_mount", False)):
                markers.append({"key": "mount", "label": "Mount", "detail": None, "tone": "neutral"})
            return markers

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
            ac_modifier_getter = getattr(t, "_combatant_ac_modifier", None)
            if callable(ac_modifier_getter):
                try:
                    ac += int(ac_modifier_getter(c) or 0)
                except Exception:
                    pass
            temp_hp = int(getattr(c, "temp_hp", 0) or 0)
            initiative = int(getattr(c, "initiative", 0) or 0)
            is_pc = bool(getattr(c, "is_pc", False))
            role = _role_for_combatant(c)
            passive_perception = _passive_perception_for(c)
            defense_lists = _defense_lists_for(c)
            state_markers = _state_markers_for(c)

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
                        "label": _titleize_key(ctype),
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
                    "speed": int(getattr(c, "speed", 0) or 0),
                    "swim_speed": int(getattr(c, "swim_speed", 0) or 0),
                    "fly_speed": int(getattr(c, "fly_speed", 0) or 0),
                    "burrow_speed": int(getattr(c, "burrow_speed", 0) or 0),
                    "climb_speed": int(getattr(c, "climb_speed", 0) or 0),
                    "passive_perception": passive_perception,
                    "damage_vulnerabilities": defense_lists["damage_vulnerabilities"],
                    "damage_resistances": defense_lists["damage_resistances"],
                    "damage_immunities": defense_lists["damage_immunities"],
                    "condition_immunities": defense_lists["condition_immunities"],
                    "concentrating": bool(getattr(c, "concentrating", False)),
                    "concentration_spell": str(getattr(c, "concentration_spell", "") or "") or None,
                    "state_markers": state_markers,
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
        perf_start = time.perf_counter() if self._perf_debug_enabled() else 0.0
        try:
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
                self._broadcast_tracker_state(include_static=False)
                return {"ok": True, "snapshot": self.combat_snapshot()}
        finally:
            self._perf_log("CombatService.next_turn", perf_start)

    def prev_turn(self) -> Dict[str, Any]:
        """Go back to the previous combatant's turn.

        Delegates to ``_prev_turn()`` on the tracker (same method the desktop
        Prev Turn button invokes), then broadcasts state to all LAN clients
        and returns the updated snapshot.

        Returns: {ok, snapshot}  or  {ok: False, error: str}
        """
        with self._lock:
            t = self._tracker
            try:
                t._prev_turn()
            except Exception as exc:
                return {"ok": False, "error": str(exc), "snapshot": self.combat_snapshot()}
            try:
                t._rebuild_table(scroll_to_current=True)
            except Exception:
                pass
            self._broadcast_tracker_state(include_static=False)
            return {"ok": True, "snapshot": self.combat_snapshot()}

    def set_turn_here(self, cid: int) -> Dict[str, Any]:
        """Set the active combatant to the one identified by ``cid``.

        This is the backend-owned equivalent of the desktop "Set Turn Here"
        button.  It sets ``current_cid``, ensures ``turn_num >= 1``, runs
        ``_enter_turn_with_auto_skip`` when available, then rebuilds the table
        and broadcasts state.

        Args:
            cid: The combatant ID to make active.

        Returns: {ok, cid, previous_cid, snapshot}
          or  {ok: False, error: str}
        """
        with self._lock:
            t = self._tracker
            if not getattr(t, "in_combat", False):
                return {"ok": False, "error": "No active combat."}

            combatants = getattr(t, "combatants", {}) or {}
            cid = int(cid)
            if cid not in combatants:
                return {"ok": False, "error": f"Combatant {cid} not found."}

            previous_cid = getattr(t, "current_cid", None)
            t.current_cid = cid
            if int(getattr(t, "turn_num", 0) or 0) <= 0:
                t.turn_num = 1

            # Run start-of-turn effects (auto-skip stunned/paralyzed, etc.)
            enter = getattr(t, "_enter_turn_with_auto_skip", None)
            if callable(enter):
                try:
                    enter(starting=True)
                except Exception:
                    pass

            try:
                t._log(
                    f"Turn set to {getattr(combatants.get(cid), 'name', 'Combatant')} (cid {cid}).",
                    cid=cid,
                )
            except Exception:
                pass
            try:
                t._rebuild_table(scroll_to_current=True)
            except Exception:
                pass
            self._broadcast_tracker_state(include_static=False)
            return {
                "ok": True,
                "cid": cid,
                "previous_cid": int(previous_cid) if previous_cid is not None else None,
                "snapshot": self.combat_snapshot(),
            }

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
            self._broadcast_tracker_state(include_static=False)
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
            self._broadcast_tracker_state(include_static=False)

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
            self._broadcast_tracker_state(include_static=False)
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

            direction = "gained" if delta > 0 else ("lost" if delta < 0 else "adjusted by 0")
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
            self._broadcast_tracker_state(include_static=False)
            return {
                "ok": True,
                "cid": int(cid),
                "temp_hp_before": old_temp,
                "temp_hp_after": new_temp,
                "delta": int(delta),
            }

    def manual_override(
        self, cid: int, hp_delta: int = 0, temp_hp_delta: int = 0
    ) -> Dict[str, Any]:
        """Atomically apply HP and/or temp-HP deltas under a single lock acquisition.

        This is the backend equivalent of the LAN player ``manual_override_hp``
        action.  Both deltas are applied inside one locked section so no other
        service-routed mutation can interleave between them.

        Args:
            cid:           Combatant ID.
            hp_delta:      Regular HP delta (negative = damage, positive = heal).
            temp_hp_delta: Temporary HP delta (positive = add, negative = remove).

        Returns: {ok, cid, hp_before, hp_after, temp_hp_before, temp_hp_after}
          or  {ok: False, error: str}
        """
        with self._lock:
            t = self._tracker
            combatants = getattr(t, "combatants", {}) or {}
            c = combatants.get(int(cid))
            if c is None:
                return {"ok": False, "error": f"Combatant {cid} not found."}

            # HP adjustment
            old_hp = int(getattr(c, "hp", 0) or 0)
            max_hp = int(getattr(c, "max_hp", old_hp) or old_hp)
            new_hp = old_hp
            if hp_delta != 0:
                new_hp = max(0, old_hp + int(hp_delta))
                if max_hp > 0:
                    new_hp = min(new_hp, max_hp)
                setattr(c, "hp", new_hp)

            # Temp HP adjustment
            old_temp = int(getattr(c, "temp_hp", 0) or 0)
            new_temp = old_temp
            if temp_hp_delta != 0:
                new_temp = max(0, old_temp + int(temp_hp_delta))
                setattr(c, "temp_hp", new_temp)

            # Log, rebuild, broadcast once for both changes
            updates: List[str] = []
            if hp_delta != 0:
                updates.append(f"HP {old_hp}→{new_hp} ({hp_delta:+d})")
            if temp_hp_delta != 0:
                updates.append(f"Temp HP {old_temp}→{new_temp} ({temp_hp_delta:+d})")
            try:
                t._log(
                    f"{getattr(c, 'name', 'Combatant')} manual override: {', '.join(updates)}.",
                    cid=int(cid),
                )
            except Exception:
                pass
            try:
                t._rebuild_table(scroll_to_current=True)
            except Exception:
                pass
            self._broadcast_tracker_state(include_static=False)
            return {
                "ok": True,
                "cid": int(cid),
                "hp_before": old_hp,
                "hp_after": new_hp,
                "temp_hp_before": old_temp,
                "temp_hp_after": new_temp,
            }

    # ------------------------------------------------------------------
    # Deep combat damage / heal (Slice 9)
    # ------------------------------------------------------------------

    def apply_damage(
        self, cid: int, raw_damage: int, *, _broadcast: bool = True
    ) -> Dict[str, Any]:
        """Apply raw damage to combatant ``cid`` using the canonical deep
        damage path with temp HP absorption.

        This delegates to the tracker's ``_apply_damage_to_target_with_temp_hp``
        which handles temp HP absorption order, monster phase refresh,
        star-advantage removal, on-damage save riders, damage-clear condition
        riders, and polymorph temp-HP checks.

        The service acquires the lock (re-entrant — safe to call from within
        other service methods such as ``next_turn`` when end-of-turn effects
        trigger damage), then optionally rebuilds the table and broadcasts
        state.

        Args:
            cid:         Combatant ID.
            raw_damage:  Raw damage amount (before temp HP absorption).
            _broadcast:  If False, skip rebuild/broadcast after the mutation.
                         Callers inside a composite mutation (turn-transition,
                         AoE loop) should pass ``_broadcast=False`` and let
                         the outer operation broadcast once.

        Returns: {ok, cid, temp_absorbed, hp_damage, hp_after}
          or  {ok: False, error: str}
        """
        with self._lock:
            t = self._tracker
            combatants = getattr(t, "combatants", {}) or {}
            c = combatants.get(int(cid))
            if c is None:
                return {"ok": False, "error": f"Combatant {cid} not found."}

            raw_damage = max(0, int(raw_damage or 0))
            if raw_damage == 0:
                return {
                    "ok": True,
                    "cid": int(cid),
                    "temp_absorbed": 0,
                    "hp_damage": 0,
                    "hp_after": int(getattr(c, "hp", 0) or 0),
                }

            try:
                damage_state = t._apply_damage_to_target_with_temp_hp(c, raw_damage)
            except Exception as exc:
                return {"ok": False, "error": f"Damage application failed: {exc}"}

            if _broadcast:
                try:
                    t._rebuild_table(scroll_to_current=True)
                except Exception:
                    pass
                self._broadcast_tracker_state(include_static=False)
            return {
                "ok": True,
                "cid": int(cid),
                "temp_absorbed": int(damage_state.get("temp_absorbed", 0)),
                "hp_damage": int(damage_state.get("hp_damage", 0)),
                "hp_after": int(damage_state.get("hp_after", 0)),
            }

    def apply_heal(
        self, cid: int, amount: int, *, is_temp_hp: bool = False, _broadcast: bool = True
    ) -> Dict[str, Any]:
        """Apply healing to combatant ``cid``.

        Delegates to the tracker's ``_apply_heal_to_combatant`` which handles
        regular healing (clamped to current + amount, with monster phase refresh)
        or temp HP setting when ``is_temp_hp=True``.

        Negative ``amount`` values are rejected — callers needing negative HP
        deltas should use ``adjust_hp()`` or ``apply_damage()`` instead.

        Args:
            cid:         Combatant ID.
            amount:      Healing amount (regular) or absolute temp HP value.
                         Must be >= 0.
            is_temp_hp:  If True, sets temp HP to ``amount`` instead of healing.
            _broadcast:  If False, skip rebuild/broadcast after the mutation.
                         Callers inside a composite mutation should pass
                         ``_broadcast=False`` and let the outer operation
                         broadcast once.

        Returns: {ok, cid, hp_before, hp_after, temp_hp_before, temp_hp_after}
          or  {ok: False, error: str}
        """
        with self._lock:
            t = self._tracker
            combatants = getattr(t, "combatants", {}) or {}
            c = combatants.get(int(cid))
            if c is None:
                return {"ok": False, "error": f"Combatant {cid} not found."}

            amount = int(amount)
            if amount < 0:
                return {
                    "ok": False,
                    "error": "Healing amount must be non-negative. Use adjust_hp() for negative deltas.",
                }

            hp_before = int(getattr(c, "hp", 0) or 0)
            temp_hp_before = int(getattr(c, "temp_hp", 0) or 0)

            try:
                success = t._apply_heal_to_combatant(int(cid), amount, is_temp_hp=is_temp_hp)
            except Exception as exc:
                return {"ok": False, "error": f"Heal application failed: {exc}"}

            if not success:
                return {"ok": False, "error": f"Combatant {cid} could not be healed."}

            hp_after = int(getattr(c, "hp", 0) or 0)
            temp_hp_after = int(getattr(c, "temp_hp", 0) or 0)

            label = "temp HP set" if is_temp_hp else "healed"
            try:
                t._log(
                    f"{getattr(c, 'name', 'Combatant')} {label} by {amount}"
                    f" (HP {hp_before}→{hp_after}, temp {temp_hp_before}→{temp_hp_after}).",
                    cid=int(cid),
                )
            except Exception:
                pass
            if _broadcast:
                try:
                    t._rebuild_table(scroll_to_current=True)
                except Exception:
                    pass
                self._broadcast_tracker_state(include_static=False)
            return {
                "ok": True,
                "cid": int(cid),
                "hp_before": hp_before,
                "hp_after": hp_after,
                "temp_hp_before": temp_hp_before,
                "temp_hp_after": temp_hp_after,
            }

    # ------------------------------------------------------------------
    # Long Rest batch HP restoration (Slice 12)
    # ------------------------------------------------------------------

    def batch_long_rest_heal(
        self, targets: Dict[int, int]
    ) -> Dict[str, Any]:
        """Restore HP for multiple combatants as part of a Long Rest.

        Uses the canonical ``apply_heal`` path (with ``_broadcast=False``) for
        each target, then performs a single rebuild + broadcast at the end to
        keep the batch efficient.

        Args:
            targets: Mapping of ``{cid: max_hp_value}`` where each
                     combatant's HP should be restored to ``max_hp_value``.
                     The method computes the heal amount (``max_hp - current_hp``)
                     internally and skips already-full targets truthfully.

        Returns:
            ``{ok, results: [{cid, hp_before, hp_after, skipped}], healed, skipped}``
        """
        with self._lock:
            t = self._tracker
            combatants = getattr(t, "combatants", {}) or {}
            results = []
            healed_count = 0
            skipped_count = 0

            for cid, target_max_hp in targets.items():
                cid = int(cid)
                c = combatants.get(cid)
                if c is None:
                    continue
                target_max_hp = int(target_max_hp)
                current_hp = int(getattr(c, "hp", 0) or 0)
                heal_needed = max(0, target_max_hp - current_hp)

                if heal_needed == 0:
                    results.append({
                        "cid": cid,
                        "hp_before": current_hp,
                        "hp_after": current_hp,
                        "skipped": True,
                    })
                    skipped_count += 1
                    continue

                res = self.apply_heal(cid=cid, amount=heal_needed, _broadcast=False)
                hp_after = int(getattr(c, "hp", 0) or 0)
                results.append({
                    "cid": cid,
                    "hp_before": current_hp,
                    "hp_after": hp_after,
                    "skipped": False,
                })
                if res.get("ok"):
                    healed_count += 1

            # Single outer rebuild + broadcast for the entire batch
            try:
                t._rebuild_table(scroll_to_current=True)
            except Exception:
                pass
            self._broadcast_tracker_state(include_static=False)

            return {
                "ok": True,
                "results": results,
                "healed": healed_count,
                "skipped": skipped_count,
            }

    def start_combat(self) -> Dict[str, Any]:
        """Start combat by beginning the initiative turn order.

        Delegates to ``_start_turns()`` on the tracker — the same method
        the desktop Start/Reset button uses.  Sets ``in_combat = True`` so
        the DM web surface and LAN clients see an active combat state.

        Requires at least one combatant to be present in the initiative list.
        Returns: {ok, snapshot}  or  {ok: False, error: str}
        """
        perf_start = time.perf_counter() if self._perf_debug_enabled() else 0.0
        try:
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
                self._broadcast_tracker_state(include_static=False)
                return {"ok": True, "snapshot": self.combat_snapshot()}
        finally:
            self._perf_log("CombatService.start_combat", perf_start)

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
            self._broadcast_tracker_state(include_static=False)
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
            self._broadcast_tracker_state(include_static=False)
            return {"ok": True, "cid": cid, "snapshot": self.combat_snapshot()}

    def add_player_profile_combatants(
        self,
        names: List[Any],
        *,
        skip_existing: bool = False,
    ) -> Dict[str, Any]:
        """Add encounter combatants from YAML-backed player profiles.

        This is the canonical service-owned encounter population path for
        player-profile combatants. It reuses the tracker's existing
        ``_create_pc_from_profile`` helper so all player normalization,
        temp-HP/max-HP setup, feature state copying, and startup summons stay
        truthful, while the service owns the outer lock/rebuild/broadcast
        boundary.

        Args:
            names: Player profile names to add.
            skip_existing: When True, skip profile names that are already
                present in the encounter by display name (used by the existing
                HTTP encounter-player route). When False, creation is delegated
                to the tracker helper, preserving its current duplicate-name
                behavior for desktop flows.

        Returns:
            ``{ok, added, skipped, created, snapshot}``
        """
        perf_start = time.perf_counter() if self._perf_debug_enabled() else 0.0
        try:
            if not isinstance(names, list):
                return {"ok": False, "error": "names must be a list."}

            with self._lock:
                t = self._tracker
                hold_factory = getattr(t, "_player_yaml_cache_hold", None)
                hold_cm = hold_factory() if callable(hold_factory) else None
                if hold_cm is not None:
                    hold_cm.__enter__()
                try:
                    load_cache = getattr(t, "_load_player_yaml_cache", None)
                    if callable(load_cache):
                        try:
                            load_cache(force_refresh=False)
                        except TypeError:
                            load_cache()
                        except Exception:
                            pass

                    create_pc = getattr(t, "_create_pc_from_profile", None)
                    if not callable(create_pc):
                        return {"ok": False, "error": "Player-profile creation is unavailable."}

                    requested_names = [str(raw_name or "").strip() for raw_name in names]
                    requested_names = [name for name in requested_names if name]
                    profiles = getattr(t, "_player_yaml_data_by_name", {}) or {}
                    if requested_names and callable(load_cache):
                        missing = [name for name in requested_names if not isinstance(profiles.get(name), dict)]
                        if missing:
                            try:
                                load_cache(force_refresh=True)
                            except TypeError:
                                load_cache()
                            except Exception:
                                pass
                            profiles = getattr(t, "_player_yaml_data_by_name", {}) or {}

                    existing_names = set()
                    if skip_existing:
                        existing_names = {
                            str(getattr(c, "name", "")).strip().lower()
                            for c in (getattr(t, "combatants", {}) or {}).values()
                            if str(getattr(c, "name", "")).strip()
                        }

                    added: List[str] = []
                    skipped: List[str] = []
                    created: List[Dict[str, Any]] = []

                    for name in requested_names:
                        profile = profiles.get(name)
                        if not isinstance(profile, dict):
                            skipped.append(name)
                            continue
                        if skip_existing and name.lower() in existing_names:
                            skipped.append(name)
                            continue
                        try:
                            cid = create_pc(name, profile, from_normalized_cache=True)
                        except TypeError:
                            # Back-compat: older tracker shims may not accept
                            # from_normalized_cache. Fall back to positional call.
                            try:
                                cid = create_pc(name, profile)
                            except Exception:
                                cid = None
                        except Exception:
                            cid = None
                        if isinstance(cid, int):
                            added.append(name)
                            created.append({"cid": cid, "name": name})
                            if skip_existing:
                                existing_names.add(name.lower())
                        else:
                            skipped.append(name)

                    if created:
                        self._refresh_tracker_outputs()

                    return {
                        "ok": True,
                        "added": added,
                        "skipped": skipped,
                        "created": created,
                        "snapshot": self.combat_snapshot(),
                    }
                finally:
                    if hold_cm is not None:
                        try:
                            hold_cm.__exit__(None, None, None)
                        except Exception:
                            pass
        finally:
            self._perf_log(
                "CombatService.add_player_profile_combatants",
                perf_start,
                requested=(len(names) if isinstance(names, list) else 0),
                skip_existing=bool(skip_existing),
            )

    def add_monster_spec_combatants(self, entries: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Add encounter combatants from monster specs.

        This is the canonical service-owned encounter population path for the
        core monster-spec encounter flows used by the desktop bulk/random add
        tools. Callers provide fully resolved encounter entry fields (name,
        initiative, overrides) and the service owns the lock/rebuild/broadcast
        boundary.

        Each entry should include:
          ``name`` (display name), ``monster_slug`` (lookup key), and
          ``initiative``. Optional override fields mirror
          ``InitiativeTracker._create_monster_spec_combatant``.

        Returns:
            ``{ok, added, skipped, snapshot}``
        """
        perf_start = time.perf_counter() if self._perf_debug_enabled() else 0.0
        try:
            if not isinstance(entries, list):
                return {"ok": False, "error": "entries must be a list."}

            with self._lock:
                t = self._tracker
                find_spec = getattr(t, "_find_monster_spec_by_slug", None)
                create_monster = getattr(t, "_create_monster_spec_combatant", None)
                if not callable(find_spec) or not callable(create_monster):
                    return {"ok": False, "error": "Monster-spec creation is unavailable."}

                added: List[Dict[str, Any]] = []
                skipped: List[Dict[str, Any]] = []

                for entry in entries:
                    if not isinstance(entry, dict):
                        skipped.append({"reason": "invalid_entry"})
                        continue

                    name = str(entry.get("name") or "").strip()
                    monster_slug = str(entry.get("monster_slug") or "").strip().lower()
                    if not name or not monster_slug:
                        skipped.append(
                            {
                                "name": name or None,
                                "monster_slug": monster_slug or None,
                                "reason": "missing_name_or_slug",
                            }
                        )
                        continue

                    try:
                        initiative = int(entry.get("initiative"))
                    except Exception:
                        skipped.append(
                            {
                                "name": name,
                                "monster_slug": monster_slug,
                                "reason": "invalid_initiative",
                            }
                        )
                        continue

                    spec = find_spec(monster_slug)
                    if spec is None:
                        skipped.append(
                            {
                                "name": name,
                                "monster_slug": monster_slug,
                                "reason": "monster_not_found",
                            }
                        )
                        continue

                    try:
                        cid = create_monster(
                            name=name,
                            monster_spec=spec,
                            hp=entry.get("hp"),
                            speed=entry.get("speed"),
                            swim_speed=entry.get("swim_speed"),
                            fly_speed=entry.get("fly_speed"),
                            burrow_speed=entry.get("burrow_speed"),
                            climb_speed=entry.get("climb_speed"),
                            movement_mode=entry.get("movement_mode"),
                            initiative=initiative,
                            dex=entry.get("dex"),
                            ally=bool(entry.get("ally", False)),
                            saving_throws=entry.get("saving_throws"),
                            ability_mods=entry.get("ability_mods"),
                            actions=entry.get("actions"),
                            bonus_actions=entry.get("bonus_actions"),
                            reactions=entry.get("reactions"),
                            roll=entry.get("roll"),
                            nat20=entry.get("nat20"),
                        )
                    except Exception:
                        cid = None

                    if isinstance(cid, int):
                        added.append(
                            {
                                "cid": cid,
                                "name": name,
                                "monster_slug": monster_slug,
                            }
                        )
                    else:
                        skipped.append(
                            {
                                "name": name,
                                "monster_slug": monster_slug,
                                "reason": "create_failed",
                            }
                        )

                if added:
                    self._refresh_tracker_outputs()

                return {
                    "ok": True,
                    "added": added,
                    "skipped": skipped,
                    "snapshot": self.combat_snapshot(),
                }
        finally:
            self._perf_log(
                "CombatService.add_monster_spec_combatants",
                perf_start,
                requested=(len(entries) if isinstance(entries, list) else 0),
            )

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
            self._broadcast_tracker_state(include_static=False)
            return {
                "ok": True,
                "cid": int(cid),
                "initiative_before": old_init,
                "initiative_after": initiative,
                "snapshot": self.combat_snapshot(),
            }

    def roll_initiative(self, cid: int, modifier: Optional[int] = None) -> Dict[str, Any]:
        """Roll and apply initiative for an existing combatant.

        The rolled total is applied through ``set_initiative()`` so initiative
        ordering, table rebuild, and broadcast behavior stay canonical.
        """
        try:
            cid = int(cid)
        except Exception:
            return {"ok": False, "error": "cid must be an integer."}

        with self._lock:
            t = self._tracker
            combatants = getattr(t, "combatants", {}) or {}
            c = combatants.get(cid)
            if c is None:
                return {"ok": False, "error": f"Combatant {cid} not found."}

            if modifier is None:
                init_mod = int(getattr(c, "dex", 0) or 0)
            else:
                try:
                    init_mod = int(modifier)
                except Exception:
                    return {"ok": False, "error": "modifier must be an integer."}

            roll = random.randint(1, 20)
            total = roll + init_mod
            setattr(c, "roll", roll)
            setattr(c, "nat20", bool(roll == 20))

            result = self.set_initiative(cid=cid, initiative=total)
            if not result.get("ok"):
                return result

            return {
                "ok": True,
                "cid": int(cid),
                "roll": roll,
                "initiative_modifier": init_mod,
                "initiative_before": result.get("initiative_before"),
                "initiative_after": result.get("initiative_after"),
                "snapshot": result.get("snapshot"),
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
            self._broadcast_tracker_state(include_static=False)
            return {"ok": True, "cid": cid, "snapshot": self.combat_snapshot()}
