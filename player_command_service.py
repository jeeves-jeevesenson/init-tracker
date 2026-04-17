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
import time
import uuid
from typing import TYPE_CHECKING, Any, Dict, Optional

from player_command_contracts import (
    ACTIVE_PROMPT_STATES,
    SPECIAL_REACTION_TRIGGERS,
    apply_resume_dispatch,
    build_attack_request_contract,
    build_dispatch_result,
    build_end_turn_contract,
    build_manual_override_contract,
    build_prompt_record,
    build_prompt_snapshot,
    build_reaction_offer_event,
    build_reaction_response_contract,
    build_resume_dispatch,
    build_spell_target_request_contract,
    prompt_resume_legacy_message,
    update_prompt_record,
)

if TYPE_CHECKING:
    from dnd_initative_tracker import InitiativeTracker


class PromptState:
    """Backend-owned accessor for pending reaction/prompt state.

    Canonical authority lives in the tracker-owned ``_pending_prompts`` store.
    Legacy tracker dicts (``_pending_reaction_offers`` and the per-trigger
    resolution buckets) remain as compatibility projections so save/load,
    reconnect, and still-mixed legacy code paths continue to function during
    this migration slice.
    """

    _PROMPT_STORE_ATTR = "_pending_prompts"
    _LEGACY_OFFERS_ATTR = "_pending_reaction_offers"
    _LEGACY_TRIGGER_ATTRS = {
        "shield": "_pending_shield_resolutions",
        "hellish_rebuke": "_pending_hellish_rebuke_resolutions",
        "absorb_elements": "_pending_absorb_elements_resolutions",
        "interception": "_pending_interception_resolutions",
    }
    _GATING_TRIGGERS = {"hellish_rebuke", "absorb_elements", "interception"}

    def __init__(self, tracker: "InitiativeTracker") -> None:
        self._tracker = tracker

    def _tracker_dict(self) -> Dict[str, Any]:
        return self._tracker.__dict__

    def _materialize_legacy_dict(self, attr: str) -> Dict[str, Dict[str, Any]]:
        value = self._tracker_dict().get(attr)
        if not isinstance(value, dict):
            value = {}
            try:
                self._tracker_dict()[attr] = value
            except Exception:
                pass
        return value

    def _prompt_store(self) -> Dict[str, Dict[str, Any]]:
        store = self._tracker_dict().get(self._PROMPT_STORE_ATTR)
        if not isinstance(store, dict):
            store = {}
            try:
                self._tracker_dict()[self._PROMPT_STORE_ATTR] = store
            except Exception:
                pass
        self._import_legacy_state(store)
        self._sync_legacy_views(store)
        return store

    def _prompt_from_legacy(self, request_id: str) -> Optional[Dict[str, Any]]:
        tracker_dict = self._tracker_dict()
        offers = tracker_dict.get(self._LEGACY_OFFERS_ATTR)
        shield = tracker_dict.get(self._LEGACY_TRIGGER_ATTRS["shield"])
        hellish = tracker_dict.get(self._LEGACY_TRIGGER_ATTRS["hellish_rebuke"])
        absorb = tracker_dict.get(self._LEGACY_TRIGGER_ATTRS["absorb_elements"])
        interception = tracker_dict.get(self._LEGACY_TRIGGER_ATTRS["interception"])

        offer = offers.get(request_id) if isinstance(offers, dict) and isinstance(offers.get(request_id), dict) else {}
        shield_ctx = shield.get(request_id) if isinstance(shield, dict) and isinstance(shield.get(request_id), dict) else {}
        hellish_ctx = hellish.get(request_id) if isinstance(hellish, dict) and isinstance(hellish.get(request_id), dict) else {}
        absorb_ctx = absorb.get(request_id) if isinstance(absorb, dict) and isinstance(absorb.get(request_id), dict) else {}
        interception_ctx = (
            interception.get(request_id)
            if isinstance(interception, dict) and isinstance(interception.get(request_id), dict)
            else {}
        )
        if not any(isinstance(value, dict) and value for value in (offer, shield_ctx, hellish_ctx, absorb_ctx, interception_ctx)):
            return None

        trigger = str(offer.get("trigger") or "").strip().lower()
        if not trigger:
            if shield_ctx:
                trigger = "shield"
            elif hellish_ctx:
                trigger = "hellish_rebuke"
            elif absorb_ctx:
                trigger = "absorb_elements"
            elif interception_ctx:
                trigger = "interception"

        def _safe_int(value: Any) -> Optional[int]:
            try:
                return int(value) if value is not None else None
            except Exception:
                return None

        reactor_cid = _safe_int(offer.get("reactor_cid"))
        if reactor_cid is None and trigger == "hellish_rebuke":
            reactor_cid = _safe_int(hellish_ctx.get("victim_cid"))
        if reactor_cid is None and trigger == "interception":
            reactor_cid = _safe_int(interception_ctx.get("reactor_cid"))

        source_cid = _safe_int(offer.get("source_cid"))
        target_cid = _safe_int(offer.get("target_cid"))
        if source_cid is None and trigger in {"hellish_rebuke", "absorb_elements", "interception"}:
            source_cid = _safe_int((hellish_ctx or absorb_ctx or interception_ctx).get("attacker_cid"))
        if target_cid is None and trigger == "hellish_rebuke":
            target_cid = _safe_int(hellish_ctx.get("attacker_cid"))
        if target_cid is None and trigger == "interception":
            target_cid = _safe_int(interception_ctx.get("victim_cid"))

        lifecycle_state = str(
            offer.get("status")
            or hellish_ctx.get("status")
            or absorb_ctx.get("status")
            or interception_ctx.get("status")
            or "offered"
        ).strip().lower() or "offered"
        accepted_choice = str(offer.get("accepted_choice") or "").strip() or None

        prompt_text = str(offer.get("prompt") or "").strip()
        metadata: Dict[str, Any] = {}
        if prompt_text:
            metadata["prompt"] = prompt_text
        for key, value in offer.items():
            if key in {
                "reactor_cid",
                "trigger",
                "source_cid",
                "target_cid",
                "choices",
                "status",
                "expires_at",
                "accepted_choice",
                "prompt",
            }:
                continue
            metadata[str(key)] = value

        resolution: Dict[str, Any] = {}
        resume_dispatch: Optional[Dict[str, Any]] = None
        if trigger == "shield" and shield_ctx:
            legacy_msg = shield_ctx.get("msg") if isinstance(shield_ctx.get("msg"), dict) else {}
            legacy_cid = _safe_int(legacy_msg.get("cid"))
            if str(legacy_msg.get("type") or "").strip().lower() == "attack_request":
                resume_dispatch = build_resume_dispatch(
                    "attack_request",
                    actor_cid=legacy_cid,
                    ws_id=legacy_msg.get("_ws_id"),
                    is_admin=bool(str(legacy_msg.get("admin_token") or "").strip()),
                    payload=build_attack_request_contract(
                        legacy_msg,
                        cid=legacy_cid,
                        ws_id=legacy_msg.get("_ws_id"),
                        is_admin=bool(str(legacy_msg.get("admin_token") or "").strip()),
                    )["payload"],
                )
            elif str(legacy_msg.get("type") or "").strip().lower() == "spell_target_request":
                resume_dispatch = build_resume_dispatch(
                    "spell_target_request",
                    actor_cid=legacy_cid,
                    ws_id=legacy_msg.get("_ws_id"),
                    is_admin=bool(str(legacy_msg.get("admin_token") or "").strip()),
                    payload=build_spell_target_request_contract(
                        legacy_msg,
                        cid=legacy_cid,
                        ws_id=legacy_msg.get("_ws_id"),
                        is_admin=bool(str(legacy_msg.get("admin_token") or "").strip()),
                    )["payload"],
                )
        elif trigger == "hellish_rebuke" and hellish_ctx:
            resolution.update(
                {
                    "victim_cid": _safe_int(hellish_ctx.get("victim_cid")),
                    "attacker_cid": _safe_int(hellish_ctx.get("attacker_cid")),
                    "spell_id": str(hellish_ctx.get("spell_id") or "hellish-rebuke"),
                    "max_range_ft": int(hellish_ctx.get("max_range_ft", 60) or 60),
                    "player_visible": {
                        "type": "hellish_rebuke_resolve_start",
                        "request_id": str(request_id),
                        "caster_cid": _safe_int(hellish_ctx.get("victim_cid")),
                        "attacker_cid": _safe_int(hellish_ctx.get("attacker_cid")),
                        "target_cid": _safe_int(hellish_ctx.get("attacker_cid")),
                        "spell_id": str(hellish_ctx.get("spell_id") or "hellish-rebuke"),
                        "spell_slug": "hellish-rebuke",
                        "action_type": "reaction",
                        "max_range_ft": int(hellish_ctx.get("max_range_ft", 60) or 60),
                    },
                }
            )
        elif trigger == "absorb_elements" and absorb_ctx:
            legacy_msg = absorb_ctx.get("msg") if isinstance(absorb_ctx.get("msg"), dict) else {}
            legacy_cid = _safe_int(legacy_msg.get("cid"))
            resolution.update(
                {
                    "victim_cid": _safe_int(absorb_ctx.get("victim_cid")),
                    "attacker_cid": _safe_int(absorb_ctx.get("attacker_cid")),
                    "trigger_types": list(absorb_ctx.get("trigger_types") if isinstance(absorb_ctx.get("trigger_types"), list) else []),
                }
            )
            if legacy_msg:
                resume_dispatch = build_resume_dispatch(
                    str(legacy_msg.get("type") or "attack_request").strip().lower() or "attack_request",
                    actor_cid=legacy_cid,
                    ws_id=legacy_msg.get("_ws_id"),
                    is_admin=bool(str(legacy_msg.get("admin_token") or "").strip()),
                    payload=(
                        build_attack_request_contract(
                            legacy_msg,
                            cid=legacy_cid,
                            ws_id=legacy_msg.get("_ws_id"),
                            is_admin=bool(str(legacy_msg.get("admin_token") or "").strip()),
                        )["payload"]
                        if str(legacy_msg.get("type") or "").strip().lower() == "attack_request"
                        else build_spell_target_request_contract(
                            legacy_msg,
                            cid=legacy_cid,
                            ws_id=legacy_msg.get("_ws_id"),
                            is_admin=bool(str(legacy_msg.get("admin_token") or "").strip()),
                        )["payload"]
                    ),
                )
        elif trigger == "interception" and interception_ctx:
            legacy_msg = interception_ctx.get("msg") if isinstance(interception_ctx.get("msg"), dict) else {}
            legacy_cid = _safe_int(legacy_msg.get("cid"))
            resolution.update(
                {
                    "reactor_cid": _safe_int(interception_ctx.get("reactor_cid")),
                    "victim_cid": _safe_int(interception_ctx.get("victim_cid")),
                    "attacker_cid": _safe_int(interception_ctx.get("attacker_cid")),
                }
            )
            if legacy_msg:
                resume_dispatch = build_resume_dispatch(
                    "attack_request",
                    actor_cid=legacy_cid,
                    ws_id=legacy_msg.get("_ws_id"),
                    is_admin=bool(str(legacy_msg.get("admin_token") or "").strip()),
                    payload=build_attack_request_contract(
                        legacy_msg,
                        cid=legacy_cid,
                        ws_id=legacy_msg.get("_ws_id"),
                        is_admin=bool(str(legacy_msg.get("admin_token") or "").strip()),
                    )["payload"],
                )

        expires_at = None
        try:
            if offer.get("expires_at") is not None:
                expires_at = float(offer.get("expires_at"))
        except Exception:
            expires_at = None

        return build_prompt_record(
            prompt_id=str(request_id),
            prompt_kind="reaction",
            trigger=trigger,
            reactor_cid=reactor_cid,
            eligible_actor_cids=[reactor_cid] if reactor_cid is not None else [],
            source_cid=source_cid,
            target_cid=target_cid,
            allowed_choices=offer.get("choices") if isinstance(offer.get("choices"), list) else [],
            ws_ids=[],
            prompt_text=prompt_text,
            metadata=metadata,
            resolution=resolution,
            resume_dispatch=resume_dispatch,
            created_at=time.time(),
            expires_at=expires_at,
            lifecycle_state=lifecycle_state,
            accepted_choice=accepted_choice,
        )

    def _import_legacy_state(self, store: Dict[str, Dict[str, Any]]) -> None:
        tracker_dict = self._tracker_dict()
        request_ids = set(store.keys())
        offers = tracker_dict.get(self._LEGACY_OFFERS_ATTR)
        if isinstance(offers, dict):
            request_ids.update(str(key) for key in offers.keys())
        for attr in self._LEGACY_TRIGGER_ATTRS.values():
            bucket = tracker_dict.get(attr)
            if isinstance(bucket, dict):
                request_ids.update(str(key) for key in bucket.keys())
        for request_id in request_ids:
            request_id = str(request_id or "").strip()
            if not request_id or request_id in store:
                continue
            prompt = self._prompt_from_legacy(request_id)
            if isinstance(prompt, dict):
                store[request_id] = prompt

    def _sync_legacy_views(self, store: Dict[str, Dict[str, Any]]) -> None:
        offers: Dict[str, Dict[str, Any]] = {}
        shield: Dict[str, Dict[str, Any]] = {}
        hellish: Dict[str, Dict[str, Any]] = {}
        absorb: Dict[str, Dict[str, Any]] = {}
        interception: Dict[str, Dict[str, Any]] = {}

        for request_id, prompt in list(store.items()):
            if not isinstance(prompt, dict):
                continue
            lifecycle = prompt.get("lifecycle") if isinstance(prompt.get("lifecycle"), dict) else {}
            state = str(lifecycle.get("state") or "offered").strip().lower()
            trigger = str(prompt.get("trigger") or "").strip().lower()
            metadata = prompt.get("metadata") if isinstance(prompt.get("metadata"), dict) else {}
            if state == "offered" or (state == "accepted" and trigger not in SPECIAL_REACTION_TRIGGERS):
                offer_payload: Dict[str, Any] = {
                    "reactor_cid": prompt.get("reactor_cid"),
                    "trigger": trigger,
                    "source_cid": prompt.get("source_cid"),
                    "target_cid": prompt.get("target_cid"),
                    "choices": [dict(choice) for choice in prompt.get("allowed_choices") if isinstance(choice, dict)]
                    if isinstance(prompt.get("allowed_choices"), list)
                    else [],
                    "status": state,
                    "expires_at": prompt.get("expires_at"),
                }
                accepted_choice = lifecycle.get("accepted_choice")
                if accepted_choice:
                    offer_payload["accepted_choice"] = accepted_choice
                if str(prompt.get("prompt") or "").strip():
                    offer_payload["prompt"] = str(prompt.get("prompt") or "").strip()
                for key, value in metadata.items():
                    offer_payload[str(key)] = value
                offers[str(request_id)] = offer_payload

            resolution = prompt.get("resolution") if isinstance(prompt.get("resolution"), dict) else {}
            if trigger == "shield":
                legacy_msg = prompt_resume_legacy_message(prompt)
                if legacy_msg:
                    shield[str(request_id)] = {"msg": legacy_msg}
            elif trigger == "hellish_rebuke":
                hellish[str(request_id)] = {
                    "victim_cid": resolution.get("victim_cid"),
                    "attacker_cid": resolution.get("attacker_cid"),
                    "spell_id": str(resolution.get("spell_id") or "hellish-rebuke"),
                    "max_range_ft": int(resolution.get("max_range_ft", 60) or 60),
                    "status": state,
                }
            elif trigger == "absorb_elements":
                legacy_msg = prompt_resume_legacy_message(prompt)
                absorb[str(request_id)] = {
                    "victim_cid": resolution.get("victim_cid"),
                    "attacker_cid": resolution.get("attacker_cid"),
                    "trigger_types": list(resolution.get("trigger_types") if isinstance(resolution.get("trigger_types"), list) else []),
                    "msg": legacy_msg,
                    "status": state,
                }
            elif trigger == "interception":
                legacy_msg = prompt_resume_legacy_message(prompt)
                interception[str(request_id)] = {
                    "reactor_cid": resolution.get("reactor_cid"),
                    "victim_cid": resolution.get("victim_cid"),
                    "attacker_cid": resolution.get("attacker_cid"),
                    "msg": legacy_msg,
                    "status": state,
                }

        tracker_dict = self._tracker_dict()
        tracker_dict[self._LEGACY_OFFERS_ATTR] = offers
        tracker_dict[self._LEGACY_TRIGGER_ATTRS["shield"]] = shield
        tracker_dict[self._LEGACY_TRIGGER_ATTRS["hellish_rebuke"]] = hellish
        tracker_dict[self._LEGACY_TRIGGER_ATTRS["absorb_elements"]] = absorb
        tracker_dict[self._LEGACY_TRIGGER_ATTRS["interception"]] = interception

    @property
    def offers(self) -> Dict[str, Dict[str, Any]]:
        _ = self._prompt_store()
        return self._materialize_legacy_dict(self._LEGACY_OFFERS_ATTR)

    def all_prompts(self) -> Dict[str, Dict[str, Any]]:
        return dict(self._prompt_store())

    def replace_prompts(self, prompts: Dict[str, Dict[str, Any]]) -> None:
        store = {}
        if isinstance(prompts, dict):
            for key, value in prompts.items():
                if isinstance(value, dict):
                    store[str(key)] = dict(value)
        self._tracker_dict()[self._PROMPT_STORE_ATTR] = store
        self._import_legacy_state(store)
        self._sync_legacy_views(store)

    def create_reaction_offer(
        self,
        *,
        reactor_cid: int,
        trigger: str,
        source_cid: int,
        target_cid: int,
        allowed_choices: list[dict[str, Any]],
        ws_ids: list[int],
        extra_payload: Optional[Dict[str, Any]] = None,
        expires_in_seconds: float = 12.0,
    ) -> Dict[str, Any]:
        now = float(time.time())
        prompt_id = uuid.uuid4().hex
        metadata = dict(extra_payload) if isinstance(extra_payload, dict) else {}
        prompt = build_prompt_record(
            prompt_id=prompt_id,
            prompt_kind="reaction",
            trigger=str(trigger),
            reactor_cid=int(reactor_cid),
            eligible_actor_cids=[int(reactor_cid)],
            source_cid=int(source_cid),
            target_cid=int(target_cid),
            allowed_choices=list(allowed_choices or []),
            ws_ids=list(ws_ids or []),
            prompt_text=str(metadata.get("prompt") or ""),
            metadata=metadata,
            created_at=now,
            expires_at=now + max(0.0, float(expires_in_seconds)),
            lifecycle_state="offered",
        )
        store = self._prompt_store()
        store[str(prompt_id)] = prompt
        self._sync_legacy_views(store)
        return dict(prompt)

    def get_offer(self, request_id: str) -> Optional[Dict[str, Any]]:
        return self.offers.get(str(request_id))

    def get_prompt(self, request_id: str) -> Optional[Dict[str, Any]]:
        return self._prompt_store().get(str(request_id))

    def build_offer_event(self, request_id: str) -> Optional[Dict[str, Any]]:
        prompt = self.get_prompt(request_id)
        if not isinstance(prompt, dict):
            return None
        return build_reaction_offer_event(prompt)

    def attach_resolution(
        self,
        request_id: str,
        *,
        resolution: Optional[Dict[str, Any]] = None,
        resume_dispatch: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        store = self._prompt_store()
        prompt = store.get(str(request_id))
        if not isinstance(prompt, dict):
            return None
        merged_resolution = dict(prompt.get("resolution") if isinstance(prompt.get("resolution"), dict) else {})
        if isinstance(resolution, dict):
            merged_resolution.update(dict(resolution))
        prompt = update_prompt_record(
            prompt,
            resolution=merged_resolution,
            resume_dispatch=resume_dispatch if resume_dispatch is not None else prompt.get("resume"),
        )
        store[str(request_id)] = prompt
        self._sync_legacy_views(store)
        return dict(prompt)

    def set_lifecycle_state(
        self,
        request_id: str,
        state: str,
        *,
        accepted_choice: Optional[str] = None,
        response_details: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        store = self._prompt_store()
        prompt = store.get(str(request_id))
        if not isinstance(prompt, dict):
            return None
        prompt = update_prompt_record(
            prompt,
            lifecycle_state=str(state),
            accepted_choice=accepted_choice,
            response_details=response_details,
        )
        store[str(request_id)] = prompt
        self._sync_legacy_views(store)
        return dict(prompt)

    def get_resolution(self, request_id: str) -> Optional[Dict[str, Any]]:
        prompt = self.get_prompt(request_id)
        if not isinstance(prompt, dict):
            return None
        resolution = prompt.get("resolution")
        return dict(resolution) if isinstance(resolution, dict) else {}

    def get_resume_dispatch(self, request_id: str) -> Optional[Dict[str, Any]]:
        prompt = self.get_prompt(request_id)
        if not isinstance(prompt, dict):
            return None
        resume_dispatch = prompt.get("resume")
        return dict(resume_dispatch) if isinstance(resume_dispatch, dict) else None

    def pop_prompt(self, request_id: str) -> Optional[Dict[str, Any]]:
        store = self._prompt_store()
        prompt = store.pop(str(request_id), None)
        self._sync_legacy_views(store)
        return dict(prompt) if isinstance(prompt, dict) else None

    def expire_offers(self) -> None:
        store = self._prompt_store()
        now = float(time.time())
        expired_ids = []
        for request_id, prompt in list(store.items()):
            if not isinstance(prompt, dict):
                continue
            expires_at = prompt.get("expires_at")
            try:
                exp_val = float(expires_at) if expires_at is not None else 0.0
            except Exception:
                exp_val = 0.0
            if exp_val <= 0 or exp_val > now:
                continue
            expired_ids.append(str(request_id))
        for request_id in expired_ids:
            store.pop(str(request_id), None)
        if expired_ids:
            self._sync_legacy_views(store)

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
        for prompt in self._prompt_store().values():
            if not isinstance(prompt, dict):
                continue
            trigger = str(prompt.get("trigger") or "").strip().lower()
            if trigger not in self._GATING_TRIGGERS:
                continue
            lifecycle = prompt.get("lifecycle") if isinstance(prompt.get("lifecycle"), dict) else {}
            status = str(lifecycle.get("state") or "").strip().lower()
            if status not in ACTIVE_PROMPT_STATES:
                continue
            resolution = prompt.get("resolution") if isinstance(prompt.get("resolution"), dict) else {}
            raw_attacker = resolution.get("attacker_cid")
            try:
                pending_attacker = int(raw_attacker) if raw_attacker is not None else None
            except Exception:
                continue
            if pending_attacker is not None and pending_attacker == attacker_cid_int:
                return True
        return False

    def player_visible_prompts_for_actor(self, actor_cid: Optional[int]) -> list[Dict[str, Any]]:
        if actor_cid is None:
            return []
        try:
            actor_cid_int = int(actor_cid)
        except Exception:
            return []
        visible: list[Dict[str, Any]] = []
        for prompt in self._prompt_store().values():
            if not isinstance(prompt, dict):
                continue
            lifecycle = prompt.get("lifecycle") if isinstance(prompt.get("lifecycle"), dict) else {}
            state = str(lifecycle.get("state") or "offered").strip().lower()
            if state not in ACTIVE_PROMPT_STATES:
                continue
            eligible = prompt.get("eligible_actor_cids") if isinstance(prompt.get("eligible_actor_cids"), list) else []
            if int(actor_cid_int) not in [int(value) for value in eligible if value is not None]:
                continue
            visible.append(build_prompt_snapshot(prompt))
        visible.sort(key=lambda item: float(item.get("created_at") or 0.0))
        return visible


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

    def _dispatch_resume(self, resume_dispatch: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        if not isinstance(resume_dispatch, dict):
            return build_dispatch_result("resume_dispatch", False, reason="missing_resume_dispatch")
        command_type = str(resume_dispatch.get("command_type") or "").strip().lower()
        actor_cid = resume_dispatch.get("actor_cid")
        ws_id = resume_dispatch.get("ws_id")
        is_admin = bool(resume_dispatch.get("is_admin"))
        payload = apply_resume_dispatch(resume_dispatch)
        if not isinstance(payload, dict):
            return build_dispatch_result(
                "resume_dispatch",
                False,
                reason="invalid_resume_payload",
                resume_dispatch=resume_dispatch,
            )
        if command_type == "attack_request":
            return self.attack_request(payload, cid=actor_cid, ws_id=ws_id, is_admin=is_admin)
        if command_type == "spell_target_request":
            return self.spell_target_request(payload, cid=actor_cid, ws_id=ws_id, is_admin=is_admin)
        return build_dispatch_result(
            "resume_dispatch",
            False,
            reason="unsupported_resume_command",
            resume_dispatch=resume_dispatch,
        )

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
        request_contract = build_end_turn_contract(cid=cid, ws_id=ws_id, is_admin=is_admin)
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
                return build_dispatch_result("end_turn", False, reason="not_your_turn", request=request_contract)

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
            return build_dispatch_result(
                "end_turn",
                False,
                reason="end_turn_failed",
                error=str(exc),
                request=request_contract,
            )
        return build_dispatch_result("end_turn", True, request=request_contract)

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
        request_contract = build_manual_override_contract(
            cid=cid,
            ws_id=ws_id,
            is_admin=False,
            hp_delta=hp_delta,
            temp_hp_delta=temp_hp_delta,
        )
        combatants = getattr(t, "combatants", {}) or {}
        if cid is None:
            return build_dispatch_result("manual_override_hp", False, reason="missing_cid", request=request_contract)
        try:
            cid_int = int(cid)
        except Exception:
            return build_dispatch_result("manual_override_hp", False, reason="invalid_cid", request=request_contract)
        c = combatants.get(cid_int)
        if c is None:
            return build_dispatch_result(
                "manual_override_hp",
                False,
                reason="combatant_missing",
                request=request_contract,
            )
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
            return build_dispatch_result("manual_override_hp", False, reason="no_delta", request=request_contract)

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
                return build_dispatch_result(
                    "manual_override_hp",
                    True,
                    via="combat_service",
                    result=res,
                    request=request_contract,
                )

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
        return build_dispatch_result(
            "manual_override_hp",
            True,
            via="fallback",
            cid=cid_int,
            hp_before=old_hp,
            hp_after=new_hp,
            temp_hp_before=old_temp_hp,
            temp_hp_after=new_temp_hp,
            request=request_contract,
        )

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
        request_contract = build_attack_request_contract(msg, cid=cid, ws_id=ws_id, is_admin=is_admin)
        combatants = getattr(t, "combatants", {}) or {}
        if cid is None:
            return build_dispatch_result("attack_request", False, reason="missing_cid", request=request_contract)
        try:
            cid_int = int(cid)
        except Exception:
            return build_dispatch_result("attack_request", False, reason="invalid_cid", request=request_contract)
        if cid_int not in combatants:
            return build_dispatch_result(
                "attack_request",
                False,
                reason="combatant_missing",
                request=request_contract,
            )
        self.prompts.expire_offers()
        if self.prompts.has_pending_attacker_gate(cid_int):
            self._toast(ws_id, "Hold fast — waiting on a reaction to resolve.")
            return build_dispatch_result(
                "attack_request",
                False,
                reason="pending_reaction",
                request=request_contract,
            )
        adjudicate = getattr(t, "_adjudicate_attack_request", None)
        if not callable(adjudicate):
            return build_dispatch_result("attack_request", False, reason="no_adjudicator", request=request_contract)
        # Let adjudicator exceptions propagate so existing observers (test
        # frameworks, tracker oplog) see the same error surface they did when
        # this logic was inline in ``_lan_apply_action``.
        adjudicate(msg, cid=cid_int, ws_id=ws_id, is_admin=bool(is_admin))
        return build_dispatch_result("attack_request", True, request=request_contract)

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
        request_contract = build_spell_target_request_contract(msg, cid=cid, ws_id=ws_id, is_admin=is_admin)
        combatants = getattr(t, "combatants", {}) or {}
        if cid is None:
            return build_dispatch_result("spell_target_request", False, reason="missing_cid", request=request_contract)
        try:
            cid_int = int(cid)
        except Exception:
            return build_dispatch_result("spell_target_request", False, reason="invalid_cid", request=request_contract)
        if cid_int not in combatants:
            return build_dispatch_result(
                "spell_target_request",
                False,
                reason="combatant_missing",
                request=request_contract,
            )
        adjudicate = getattr(t, "_adjudicate_spell_target_request", None)
        if not callable(adjudicate):
            return build_dispatch_result(
                "spell_target_request",
                False,
                reason="no_adjudicator",
                request=request_contract,
            )
        adjudicate(msg, cid=cid_int, ws_id=ws_id, is_admin=bool(is_admin))
        return build_dispatch_result("spell_target_request", True, request=request_contract)

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
        request_contract = build_reaction_response_contract(msg, cid=cid, ws_id=ws_id)
        request_id = str(msg.get("request_id") or "").strip()
        if not request_id:
            return build_dispatch_result(
                "reaction_response",
                False,
                reason="missing_request_id",
                request=request_contract,
            )
        prompt = self.prompts.get_prompt(request_id)
        if not isinstance(prompt, dict):
            return build_dispatch_result("reaction_response", False, reason="no_offer", request=request_contract)
        try:
            reactor_expected = int(prompt.get("reactor_cid") or -1)
            reactor_got = int(cid if cid is not None else -1)
        except Exception:
            return build_dispatch_result("reaction_response", False, reason="invalid_reactor", request=request_contract)
        if reactor_expected != reactor_got:
            return build_dispatch_result(
                "reaction_response",
                False,
                reason="reactor_mismatch",
                request=request_contract,
            )
        adjudicate = getattr(t, "_adjudicate_reaction_response", None)
        if not callable(adjudicate):
            return build_dispatch_result("reaction_response", False, reason="no_adjudicator", request=request_contract)
        adjudicate_result = adjudicate(
            msg,
            cid=reactor_got,
            ws_id=ws_id,
            offer=dict(prompt),
            request_id=request_id,
        )
        resume_dispatch = None
        if isinstance(adjudicate_result, dict):
            resume_dispatch = adjudicate_result.get("resume_dispatch") or adjudicate_result.get("resume")
        resume_result = self._dispatch_resume(resume_dispatch) if isinstance(resume_dispatch, dict) else None
        return build_dispatch_result(
            "reaction_response",
            True,
            request=request_contract,
            prompt_id=request_id,
            resume_dispatched=bool(resume_result),
            resume_result=resume_result,
        )
