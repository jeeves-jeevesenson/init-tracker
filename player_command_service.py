"""Backend-authoritative seam for player-originated combat commands.

This module owns the explicit backend entry points for the player combat
commands that were previously adjudicated inline by
``InitiativeTracker._lan_apply_action()``.  Each entry point here defines a
single authoritative flow: pre-condition validation, prompt/reaction state
management, and delegation to the tracker's detailed adjudication logic.

Ownership model after this migration pass
-----------------------------------------
Service-owned (this module):
  - player "end turn" gate (turn ownership, summon turn logic)
  - player "manual override HP" (HP/temp-HP deltas; prefers
    ``CombatService.manual_override`` when available, falls back to direct
    mutation for legacy/desktop-only runtime)
  - player "attack request" envelope: stale-reaction-offer expiry, pending
    reaction-gate check, delegation to ``InitiativeTracker._adjudicate_attack_request``
  - player "spell target request" envelope: delegation to
    ``InitiativeTracker._adjudicate_spell_target_request``
  - player "reaction response" lifecycle: request-id lookup, reactor-cid
    match, delegation to ``InitiativeTracker._adjudicate_reaction_response``

Still tracker-owned (delegated to by this service):
  - deep attack adjudication (damage math, spell riders, reaction offer
    creation, weapon mastery, opportunity attack halting)
  - deep spell adjudication (save rolls, spell mark/curse state, healing
    and damage resolution)
  - trigger-specific reaction resolution (shield, hellish rebuke, absorb
    elements, interception, sentinel)

Authority note
--------------
Prompt/reaction state is exposed to this service via the ``PromptState``
accessor.  The underlying storage (``_pending_reaction_offers`` and the
per-trigger resolution dicts such as ``_pending_shield_resolutions``,
``_pending_hellish_rebuke_resolutions``, ``_pending_absorb_elements_resolutions``,
``_pending_interception_resolutions``) remains on the tracker instance so
that save/load, expiry sweeps, and reconnect flows that already read those
attributes keep working without additional rewiring.  ``PromptState`` makes
ownership explicit and gives the service a single place to reason about
prompt lifecycle in future passes.

Usage::

    service = PlayerCommandService(tracker)
    service.end_turn(cid=1, claimed_cid=1, current_cid=1, ws_id=99, is_admin=False)
    service.manual_override_hp(cid=1, hp_delta=-3, temp_hp_delta=0, ws_id=99)
    service.attack_request(msg, cid=1, ws_id=99, is_admin=False)
    service.spell_target_request(msg, cid=1, ws_id=99, is_admin=False)
    service.reaction_response(msg, cid=1, ws_id=99)
"""
from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:
    from dnd_initative_tracker import InitiativeTracker


class PromptState:
    """Backend-owned accessor for pending reaction/prompt state.

    Wraps the tracker's existing ``_pending_reaction_offers`` dict and the
    per-trigger resolution dicts so the player command service can reason
    about prompt lifecycle without reaching into tracker attribute names
    directly.
    """

    _GATING_RESOLUTION_ATTRS = (
        "_pending_hellish_rebuke_resolutions",
        "_pending_absorb_elements_resolutions",
        "_pending_interception_resolutions",
    )

    def __init__(self, tracker: "InitiativeTracker") -> None:
        self._tracker = tracker

    @property
    def offers(self) -> Dict[str, Dict[str, Any]]:
        offers = self._tracker.__dict__.get("_pending_reaction_offers")
        if not isinstance(offers, dict):
            offers = {}
            try:
                self._tracker.__dict__["_pending_reaction_offers"] = offers
            except Exception:
                pass
        return offers

    def get_offer(self, request_id: str) -> Optional[Dict[str, Any]]:
        return self.offers.get(str(request_id))

    def expire_offers(self) -> None:
        """Purge expired pending offers via the tracker helper.

        Accesses ``self.offers`` first so that the ``_pending_reaction_offers``
        attribute is materialized on the tracker before the helper's own
        ``getattr`` touches it.  Without this, a fresh tracker instance (e.g.
        ``object.__new__(InitiativeTracker)`` under test) would hit Tk's
        ``__getattr__`` forwarder and recurse.
        """
        _ = self.offers  # materialize the dict on the tracker's __dict__
        expire = self._tracker.__dict__.get("_expire_reaction_offers")
        if expire is None:
            cls_method = getattr(type(self._tracker), "_expire_reaction_offers", None)
            if callable(cls_method):
                expire = cls_method.__get__(self._tracker, type(self._tracker))
        if callable(expire):
            try:
                expire()
            except Exception:
                pass

    def has_pending_attacker_gate(self, attacker_cid: int) -> bool:
        """Return True if a reaction trigger is actively blocking this attacker.

        Mirrors the pending-hellish-rebuke / absorb-elements / interception gate
        that used to be inlined at the top of the ``attack_request`` branch of
        ``_lan_apply_action``.  An attacker must wait until their outstanding
        reaction prompts resolve before launching a new attack.
        """
        try:
            attacker_cid_int = int(attacker_cid)
        except Exception:
            return False
        tracker_dict = self._tracker.__dict__
        for attr in self._GATING_RESOLUTION_ATTRS:
            bucket = tracker_dict.get(attr)
            if not isinstance(bucket, dict):
                continue
            for pending in bucket.values():
                if not isinstance(pending, dict):
                    continue
                status = str(pending.get("status") or "").strip().lower()
                if status not in ("offered", "accepted"):
                    continue
                raw_attacker = pending.get("attacker_cid")
                try:
                    pending_attacker = int(raw_attacker) if raw_attacker is not None else None
                except Exception:
                    continue
                if pending_attacker is not None and pending_attacker == attacker_cid_int:
                    return True
        return False


class PlayerCommandService:
    """Backend authority for player-originated combat commands.

    This seam makes player-command adjudication explicit.  The deep rules
    logic still lives on the tracker (``_adjudicate_attack_request``,
    ``_adjudicate_spell_target_request``, ``_adjudicate_reaction_response``),
    but every migrated player command enters through this service so that
    future passes can evolve the tracker-side implementation without moving
    the transport/authority boundary again.
    """

    def __init__(self, tracker: "InitiativeTracker") -> None:
        if tracker is None:
            raise ValueError("PlayerCommandService requires a tracker instance.")
        self._tracker = tracker
        self.prompts = PromptState(tracker)
        self._lock = threading.RLock()

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _combat_service(self):
        return self._tracker.__dict__.get("_dm_service")

    def _toast(self, ws_id: Any, message: str) -> None:
        lan = self._tracker.__dict__.get("_lan")
        toast = None
        if lan is not None:
            toast = getattr(lan, "toast", None)
        if callable(toast):
            try:
                toast(ws_id, message)
            except Exception:
                pass

    def _oplog(self, message: str, level: str = "info") -> None:
        oplog = self._tracker.__dict__.get("_oplog")
        if oplog is None:
            cls_method = getattr(type(self._tracker), "_oplog", None)
            if callable(cls_method):
                oplog = cls_method.__get__(self._tracker, type(self._tracker))
        if callable(oplog):
            try:
                oplog(message, level=level)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # end_turn
    # ------------------------------------------------------------------

    def end_turn(
        self,
        *,
        cid: Optional[int],
        claimed_cid: Optional[int],
        current_cid: Optional[int],
        ws_id: Any,
        is_admin: bool,
    ) -> Dict[str, Any]:
        """Backend authority for the player "end turn" command.

        Owns turn-ownership validation (including shared-turn summon logic),
        wild_resurgence state reset, polymorph tick, and routes the turn
        advance through ``_next_turn_via_service`` so the CombatService
        lock/broadcast path is shared with DM/desktop callers.
        """
        t = self._tracker
        in_combat = bool(getattr(t, "in_combat", False))
        if in_combat:
            can_end_shared = False
            check_shared = getattr(t, "_is_valid_summon_turn_for_controller", None)
            if callable(check_shared):
                try:
                    can_end_shared = bool(check_shared(claimed_cid, cid, current_cid))
                except Exception:
                    can_end_shared = False
            if cid is None or (current_cid != int(cid) and not can_end_shared):
                self._toast(ws_id, "Not yer turn yet, matey.")
                return {"ok": False, "reason": "not_your_turn"}

        try:
            combatants = getattr(t, "combatants", {}) or {}
            for combatant in combatants.values():
                try:
                    setattr(combatant, "wild_resurgence_turn_used", False)
                except Exception:
                    pass
            t._next_turn_via_service()
            tick = getattr(t, "_tick_polymorph_durations", None)
            if callable(tick):
                try:
                    tick()
                except Exception:
                    pass
            self._toast(ws_id, "Turn ended.")
        except Exception as exc:
            self._oplog(f"LAN end turn failed: {exc}", level="warning")
            return {"ok": False, "reason": "end_turn_failed", "error": str(exc)}
        return {"ok": True}

    # ------------------------------------------------------------------
    # manual_override_hp
    # ------------------------------------------------------------------

    def manual_override_hp(
        self,
        *,
        cid: Optional[int],
        hp_delta: Any,
        temp_hp_delta: Any,
        ws_id: Any,
    ) -> Dict[str, Any]:
        """Backend authority for the player "manual override HP" command.

        Prefers the canonical ``CombatService.manual_override`` entry point so
        HP and temp-HP deltas land atomically under the service lock, and
        falls back to direct mutation + broadcast when the DM combat service
        is not available (e.g. tracker-only test runs or LAN not started).
        """
        t = self._tracker
        combatants = getattr(t, "combatants", {}) or {}
        if cid is None:
            return {"ok": False, "reason": "missing_cid"}
        try:
            cid_int = int(cid)
        except Exception:
            return {"ok": False, "reason": "invalid_cid"}
        c = combatants.get(cid_int)
        if c is None:
            return {"ok": False, "reason": "combatant_missing"}
        try:
            hp_delta_int = int(hp_delta or 0)
        except Exception:
            hp_delta_int = 0
        try:
            temp_hp_delta_int = int(temp_hp_delta or 0)
        except Exception:
            temp_hp_delta_int = 0
        if hp_delta_int == 0 and temp_hp_delta_int == 0:
            self._toast(ws_id, "Pick a non-zero override amount, matey.")
            return {"ok": False, "reason": "no_delta"}

        svc = self._combat_service()
        if svc is not None:
            try:
                res = svc.manual_override(
                    cid=cid_int, hp_delta=hp_delta_int, temp_hp_delta=temp_hp_delta_int,
                )
            except Exception as exc:
                self._oplog(
                    f"PlayerCommandService manual_override_hp via CombatService failed: {exc}",
                    level="warning",
                )
                res = None
            if isinstance(res, dict) and res.get("ok"):
                self._toast(ws_id, "Manual override applied.")
                return {"ok": True, "via": "combat_service", "result": res}

        # Fallback: CombatService unavailable — direct mutation + broadcast.
        old_hp = int(getattr(c, "hp", 0) or 0)
        max_hp = int(getattr(c, "max_hp", old_hp) or old_hp)
        old_temp_hp = int(getattr(c, "temp_hp", 0) or 0)
        new_hp = max(0, old_hp + hp_delta_int)
        if max_hp > 0:
            new_hp = min(new_hp, max_hp)
        new_temp_hp = max(0, old_temp_hp + temp_hp_delta_int)
        setattr(c, "hp", int(new_hp))
        setattr(c, "temp_hp", int(new_temp_hp))
        updates: list[str] = []
        if hp_delta_int != 0:
            updates.append(f"HP {old_hp}->{new_hp} ({hp_delta_int:+d})")
        if temp_hp_delta_int != 0:
            updates.append(f"Temp HP {old_temp_hp}->{new_temp_hp} ({temp_hp_delta_int:+d})")
        log = getattr(t, "_log", None)
        if callable(log):
            try:
                log(
                    f"{getattr(c, 'name', 'Player')} manual override: {', '.join(updates)}.",
                    cid=cid_int,
                )
            except Exception:
                pass
        self._toast(ws_id, "Manual override applied.")
        rebuild = getattr(t, "_rebuild_table", None)
        if callable(rebuild):
            try:
                rebuild(scroll_to_current=True)
            except Exception:
                pass
        broadcast = getattr(t, "_lan_force_state_broadcast", None)
        if callable(broadcast):
            try:
                broadcast()
            except Exception:
                pass
        return {
            "ok": True,
            "via": "fallback",
            "cid": cid_int,
            "hp_before": old_hp,
            "hp_after": new_hp,
            "temp_hp_before": old_temp_hp,
            "temp_hp_after": new_temp_hp,
        }

    # ------------------------------------------------------------------
    # attack_request
    # ------------------------------------------------------------------

    def attack_request(
        self,
        msg: Dict[str, Any],
        *,
        cid: Optional[int],
        ws_id: Any,
        is_admin: bool,
    ) -> Dict[str, Any]:
        """Backend authority envelope for the player "attack request" command.

        Owns:
          - combatant presence check
          - expiry sweep of stale reaction offers
          - pending-reaction attacker gate (blocks new attacks while a
            previous attack is waiting on a reactor)

        Delegates the deep attack adjudication to
        ``InitiativeTracker._adjudicate_attack_request``.
        """
        t = self._tracker
        combatants = getattr(t, "combatants", {}) or {}
        if cid is None:
            return {"ok": False, "reason": "missing_cid"}
        try:
            cid_int = int(cid)
        except Exception:
            return {"ok": False, "reason": "invalid_cid"}
        if cid_int not in combatants:
            return {"ok": False, "reason": "combatant_missing"}
        self.prompts.expire_offers()
        if self.prompts.has_pending_attacker_gate(cid_int):
            self._toast(ws_id, "Hold fast — waiting on a reaction to resolve.")
            return {"ok": False, "reason": "pending_reaction"}
        adjudicate = getattr(t, "_adjudicate_attack_request", None)
        if not callable(adjudicate):
            return {"ok": False, "reason": "no_adjudicator"}
        # Let adjudicator exceptions propagate so existing observers (test
        # frameworks, tracker oplog) see the same error surface they did when
        # this logic was inline in ``_lan_apply_action``.
        adjudicate(msg, cid=cid_int, ws_id=ws_id, is_admin=bool(is_admin))
        return {"ok": True}

    # ------------------------------------------------------------------
    # spell_target_request
    # ------------------------------------------------------------------

    def spell_target_request(
        self,
        msg: Dict[str, Any],
        *,
        cid: Optional[int],
        ws_id: Any,
        is_admin: bool,
    ) -> Dict[str, Any]:
        """Backend authority envelope for the player "spell target request" command.

        Owns combatant presence validation.  Delegates deep single-target spell
        adjudication (saves, damage/healing, mark state, reaction offers) to
        ``InitiativeTracker._adjudicate_spell_target_request``.
        """
        t = self._tracker
        combatants = getattr(t, "combatants", {}) or {}
        if cid is None:
            return {"ok": False, "reason": "missing_cid"}
        try:
            cid_int = int(cid)
        except Exception:
            return {"ok": False, "reason": "invalid_cid"}
        if cid_int not in combatants:
            return {"ok": False, "reason": "combatant_missing"}
        adjudicate = getattr(t, "_adjudicate_spell_target_request", None)
        if not callable(adjudicate):
            return {"ok": False, "reason": "no_adjudicator"}
        adjudicate(msg, cid=cid_int, ws_id=ws_id, is_admin=bool(is_admin))
        return {"ok": True}

    # ------------------------------------------------------------------
    # reaction_response
    # ------------------------------------------------------------------

    def reaction_response(
        self,
        msg: Dict[str, Any],
        *,
        cid: Optional[int],
        ws_id: Any,
    ) -> Dict[str, Any]:
        """Backend authority envelope for the player "reaction response" command.

        Owns:
          - request-id presence
          - offer lookup via ``PromptState``
          - reactor-cid match against the stored offer

        Delegates trigger-specific reaction resolution (shield, hellish rebuke,
        absorb elements, interception, generic accept/decline) to
        ``InitiativeTracker._adjudicate_reaction_response``.
        """
        t = self._tracker
        request_id = str(msg.get("request_id") or "").strip()
        if not request_id:
            return {"ok": False, "reason": "missing_request_id"}
        offer = self.prompts.get_offer(request_id)
        if not isinstance(offer, dict):
            return {"ok": False, "reason": "no_offer"}
        try:
            reactor_expected = int(offer.get("reactor_cid") or -1)
            reactor_got = int(cid if cid is not None else -1)
        except Exception:
            return {"ok": False, "reason": "invalid_reactor"}
        if reactor_expected != reactor_got:
            return {"ok": False, "reason": "reactor_mismatch"}
        adjudicate = getattr(t, "_adjudicate_reaction_response", None)
        if not callable(adjudicate):
            return {"ok": False, "reason": "no_adjudicator"}
        adjudicate(
            msg,
            cid=reactor_got,
            ws_id=ws_id,
            offer=dict(offer),
            request_id=request_id,
        )
        return {"ok": True}
