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
  - player resource/inventory/self-state commands:
    ``manual_override_spell_slot``, ``manual_override_resource_pool``,
    ``reaction_prefs_update``, ``inventory_adjust_consumable``,
    ``use_consumable``, ``lay_on_hands_use``, ``second_wind_use``,
    ``action_surge_use``, ``star_advantage_use``, ``monk_patient_defense``,
    ``monk_step_of_wind``, ``monk_elemental_attunement``,
    ``monk_elemental_burst``, and ``monk_uncanny_metabolism``
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
import random
from typing import TYPE_CHECKING, Any, Dict, Optional

from player_command_contracts import (
    ACTIVE_PROMPT_STATES,
    FIGHTER_MONK_RESOURCE_ACTION_TYPES,
    SPECIAL_REACTION_TRIGGERS,
    apply_resume_dispatch,
    build_attack_request_contract,
    build_action_surge_use_contract,
    build_dispatch_result,
    build_end_turn_contract,
    build_inventory_adjust_consumable_contract,
    build_lay_on_hands_use_contract,
    build_monk_elemental_attunement_contract,
    build_monk_elemental_burst_contract,
    build_monk_patient_defense_contract,
    build_monk_step_of_wind_contract,
    build_monk_uncanny_metabolism_contract,
    build_manual_override_contract,
    build_manual_override_resource_pool_contract,
    build_manual_override_spell_slot_contract,
    build_prompt_record,
    build_prompt_snapshot,
    build_reaction_offer_event,
    build_reaction_prefs_update_contract,
    build_reaction_response_contract,
    build_resume_dispatch,
    build_second_wind_use_contract,
    build_spell_target_request_contract,
    build_star_advantage_use_contract,
    build_use_consumable_contract,
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
        prompt_id: Optional[str] = None,
        resolution: Optional[Dict[str, Any]] = None,
        resume_dispatch: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        now = float(time.time())
        prompt_id = str(prompt_id).strip() if prompt_id else uuid.uuid4().hex
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
            resolution=dict(resolution) if isinstance(resolution, dict) else None,
            resume_dispatch=dict(resume_dispatch) if isinstance(resume_dispatch, dict) else None,
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

    _FIGHTER_MONK_RESOURCE_ACTION_HANDLERS = {
        command_type: command_type for command_type in FIGHTER_MONK_RESOURCE_ACTION_TYPES
    }

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
    # resource / consumable / self-state commands
    # ------------------------------------------------------------------

    def dispatch_fighter_monk_resource_action(
        self,
        msg: Dict[str, Any],
        *,
        cid: Optional[int],
        ws_id: Any,
        is_admin: bool,
    ) -> Dict[str, Any]:
        command_type = str(msg.get("type") if isinstance(msg, dict) else "").strip().lower()
        handler_name = self._FIGHTER_MONK_RESOURCE_ACTION_HANDLERS.get(command_type)
        if not handler_name:
            return build_dispatch_result(
                "fighter_monk_resource_action",
                False,
                reason="unsupported_command",
                received_type=command_type,
            )
        handler = getattr(self, handler_name, None)
        if not callable(handler):
            return build_dispatch_result(
                command_type,
                False,
                reason="handler_missing",
            )
        return handler(
            msg if isinstance(msg, dict) else {},
            cid=cid,
            ws_id=ws_id,
            is_admin=is_admin,
        )

    def manual_override_spell_slot(
        self,
        msg: Dict[str, Any],
        *,
        cid: Optional[int],
        ws_id: Any,
        is_admin: bool,
    ) -> Dict[str, Any]:
        t = self._tracker
        request_contract = build_manual_override_spell_slot_contract(
            msg,
            cid=cid,
            ws_id=ws_id,
            is_admin=is_admin,
        )
        if cid is None:
            return build_dispatch_result("manual_override_spell_slot", False, reason="missing_cid", request=request_contract)
        try:
            cid_int = int(cid)
        except Exception:
            return build_dispatch_result("manual_override_spell_slot", False, reason="invalid_cid", request=request_contract)
        try:
            slot_level = int(msg.get("slot_level"))
            slot_delta = int(msg.get("delta"))
        except Exception:
            self._toast(ws_id, "Pick a valid slot level and amount, matey.")
            return build_dispatch_result("manual_override_spell_slot", False, reason="invalid_slot_args", request=request_contract)
        if slot_level < 1 or slot_level > 9 or slot_delta == 0:
            self._toast(ws_id, "Pick a valid slot level and amount, matey.")
            return build_dispatch_result("manual_override_spell_slot", False, reason="invalid_slot_args", request=request_contract)
        try:
            player_name = t._pc_name_for(cid_int)
            _resolved_name, slots = t._resolve_spell_slot_profile(player_name)
        except Exception as exc:
            self._toast(ws_id, str(exc) or "No spell slots set up for that caster, matey.")
            return build_dispatch_result(
                "manual_override_spell_slot",
                False,
                reason="resolve_spell_slots_failed",
                error=str(exc),
                request=request_contract,
            )
        entry = slots.get(str(slot_level))
        if not isinstance(entry, dict):
            self._toast(ws_id, "No spell slots at that level, matey.")
            return build_dispatch_result("manual_override_spell_slot", False, reason="slot_level_missing", request=request_contract)
        old_current = int(entry.get("current", 0) or 0)
        max_current = int(entry.get("max", 0) or 0)
        if max_current <= 0:
            self._toast(ws_id, "No spell slots at that level, matey.")
            return build_dispatch_result("manual_override_spell_slot", False, reason="slot_level_missing", request=request_contract)
        new_current = max(0, min(max_current, old_current + slot_delta))
        entry["current"] = int(new_current)
        slots[str(slot_level)] = entry
        try:
            t._save_player_spell_slots(player_name, slots)
        except Exception as exc:
            self._toast(ws_id, "Could not update spell slots, matey.")
            return build_dispatch_result(
                "manual_override_spell_slot",
                False,
                reason="save_spell_slots_failed",
                error=str(exc),
                request=request_contract,
            )
        c = (getattr(t, "combatants", {}) or {}).get(cid_int)
        actor_name = getattr(c, "name", player_name or "Player")
        log = getattr(t, "_log", None)
        if callable(log):
            try:
                log(
                    f"{actor_name} manual override: level {slot_level} spell slots {old_current}->{new_current} ({slot_delta:+d}).",
                    cid=cid_int,
                )
            except Exception:
                pass
        self._toast(ws_id, f"Level {slot_level} spell slots updated.")
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
            "manual_override_spell_slot",
            True,
            request=request_contract,
            slot_level=slot_level,
            slot_delta=slot_delta,
            before=old_current,
            after=new_current,
        )

    def manual_override_resource_pool(
        self,
        msg: Dict[str, Any],
        *,
        cid: Optional[int],
        ws_id: Any,
        is_admin: bool,
    ) -> Dict[str, Any]:
        t = self._tracker
        request_contract = build_manual_override_resource_pool_contract(
            msg,
            cid=cid,
            ws_id=ws_id,
            is_admin=is_admin,
        )
        if cid is None:
            return build_dispatch_result("manual_override_resource_pool", False, reason="missing_cid", request=request_contract)
        try:
            cid_int = int(cid)
        except Exception:
            return build_dispatch_result("manual_override_resource_pool", False, reason="invalid_cid", request=request_contract)
        player_name = t._pc_name_for(cid_int)
        pool_id = str(msg.get("pool_id") or "").strip()
        try:
            pool_delta = int(msg.get("delta"))
        except Exception:
            pool_delta = 0
        if not pool_id or pool_delta == 0:
            self._toast(ws_id, "Pick a valid pool and amount, matey.")
            return build_dispatch_result("manual_override_resource_pool", False, reason="invalid_pool_args", request=request_contract)
        profile = t._profile_for_player_name(player_name)
        pools = t._normalize_player_resource_pools(profile if isinstance(profile, dict) else {})
        pool = next((entry for entry in pools if str(entry.get("id") or "").strip().lower() == pool_id.lower()), None)
        if not isinstance(pool, dict):
            self._toast(ws_id, "That resource pool could not be found, matey.")
            return build_dispatch_result("manual_override_resource_pool", False, reason="pool_missing", request=request_contract)
        if bool(pool.get("derived_from_inventory")) or str(pool_id).strip().lower().startswith("consumable:"):
            self._toast(ws_id, "Consumable counts come from inventory. Adjust inventory instead, matey.")
            return build_dispatch_result(
                "manual_override_resource_pool",
                False,
                reason="pool_derived_from_inventory",
                request=request_contract,
            )
        old_current = int(pool.get("current", 0) or 0)
        max_current = int(pool.get("max", 0) or 0)
        new_current = max(0, old_current + pool_delta)
        if max_current > 0:
            new_current = min(new_current, max_current)
        ok_pool, pool_err = t._set_player_resource_pool_current(player_name, pool_id, int(new_current))
        if not ok_pool:
            self._toast(ws_id, pool_err or "Could not update resource pools, matey.")
            return build_dispatch_result(
                "manual_override_resource_pool",
                False,
                reason="pool_update_failed",
                error=str(pool_err or ""),
                request=request_contract,
            )
        c = (getattr(t, "combatants", {}) or {}).get(cid_int)
        actor_name = getattr(c, "name", player_name or "Player")
        pool_label = str(pool.get("label") or pool_id)
        log = getattr(t, "_log", None)
        if callable(log):
            try:
                log(
                    f"{actor_name} manual override: {pool_label} {old_current}->{new_current} ({pool_delta:+d}).",
                    cid=cid_int,
                )
            except Exception:
                pass
        self._toast(ws_id, f"{pool_label} updated.")
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
            "manual_override_resource_pool",
            True,
            request=request_contract,
            pool_id=pool_id,
            pool_label=pool_label,
            pool_delta=pool_delta,
            before=old_current,
            after=new_current,
        )

    def reaction_prefs_update(
        self,
        msg: Dict[str, Any],
        *,
        cid: Optional[int],
        ws_id: Any,
        is_admin: bool,
    ) -> Dict[str, Any]:
        t = self._tracker
        request_contract = build_reaction_prefs_update_contract(
            msg,
            cid=cid,
            ws_id=ws_id,
            is_admin=is_admin,
        )
        if cid is None:
            return build_dispatch_result("reaction_prefs_update", False, reason="missing_cid", request=request_contract)
        try:
            cid_int = int(cid)
        except Exception:
            return build_dispatch_result("reaction_prefs_update", False, reason="invalid_cid", request=request_contract)
        prefs = msg.get("prefs") if isinstance(msg.get("prefs"), dict) else {}
        t._set_reaction_prefs(cid_int, prefs)
        return build_dispatch_result(
            "reaction_prefs_update",
            True,
            request=request_contract,
            updated_keys=sorted([str(key) for key in prefs.keys()]),
        )

    def lay_on_hands_use(
        self,
        msg: Dict[str, Any],
        *,
        cid: Optional[int],
        ws_id: Any,
        is_admin: bool,
    ) -> Dict[str, Any]:
        t = self._tracker
        request_contract = build_lay_on_hands_use_contract(
            msg,
            cid=cid,
            ws_id=ws_id,
            is_admin=is_admin,
        )
        combatants = getattr(t, "combatants", {}) or {}
        if cid is None:
            return build_dispatch_result("lay_on_hands_use", False, reason="missing_cid", request=request_contract)
        try:
            cid_int = int(cid)
        except Exception:
            return build_dispatch_result("lay_on_hands_use", False, reason="invalid_cid", request=request_contract)
        c = combatants.get(cid_int)
        if c is None:
            return build_dispatch_result("lay_on_hands_use", False, reason="combatant_missing", request=request_contract)
        player_name = t._pc_name_for(cid_int)
        profile = t._profile_for_player_name(player_name)
        if not isinstance(profile, dict):
            self._toast(ws_id, "No player profile found, matey.")
            return build_dispatch_result("lay_on_hands_use", False, reason="missing_profile", request=request_contract)
        paladin_level = t._class_level_from_profile(profile, "paladin")
        if paladin_level < 1:
            self._toast(ws_id, "Only paladins can use Lay on Hands, matey.")
            return build_dispatch_result("lay_on_hands_use", False, reason="not_paladin", request=request_contract)
        try:
            target_cid = int(msg.get("target_cid"))
        except Exception:
            target_cid = None
        target = combatants.get(int(target_cid)) if target_cid is not None else None
        if target is None:
            self._toast(ws_id, "Pick a valid target, matey.")
            return build_dispatch_result("lay_on_hands_use", False, reason="invalid_target", request=request_contract)
        cure_poisoned = bool(msg.get("cure_poisoned") is True)
        try:
            heal_amount = int(msg.get("amount", 0))
        except Exception:
            heal_amount = 0
        if cure_poisoned:
            heal_amount = 5
        if heal_amount <= 0:
            self._toast(ws_id, "Healing amount must be at least 1, matey.")
            return build_dispatch_result("lay_on_hands_use", False, reason="invalid_amount", request=request_contract)
        in_combat = bool(getattr(t, "in_combat", False))
        if in_combat and int(getattr(c, "bonus_action_remaining", 0) or 0) <= 0:
            self._toast(ws_id, "No bonus actions left, matey.")
            return build_dispatch_result("lay_on_hands_use", False, reason="no_bonus_action", request=request_contract)
        ok_pool, pool_err = t._consume_resource_pool_for_cast(player_name, "lay_on_hands", heal_amount)
        if not ok_pool:
            self._toast(ws_id, pool_err or "No Lay on Hands points remain, matey.")
            return build_dispatch_result(
                "lay_on_hands_use",
                False,
                reason="pool_exhausted",
                error=str(pool_err or ""),
                request=request_contract,
            )
        if in_combat:
            t._use_bonus_action(c)
        actual_heal = 0
        if cure_poisoned:
            t._remove_condition_type(target, "poisoned")
            log = getattr(t, "_log", None)
            if callable(log):
                try:
                    log(
                        f"{getattr(c, 'name', 'Player')} uses Lay on Hands on {getattr(target, 'name', 'Target')} "
                        f"to remove Poisoned (5 points spent).",
                        cid=int(target.cid),
                    )
                except Exception:
                    pass
            self._toast(ws_id, "Lay on Hands: removed Poisoned.")
        else:
            cur_hp = int(getattr(target, "hp", 0) or 0)
            max_hp = int(getattr(target, "max_hp", cur_hp) or cur_hp)
            actual_heal = max(0, min(heal_amount, max(0, max_hp - cur_hp)))
            t._apply_heal_via_service(int(target.cid), actual_heal)
            log = getattr(t, "_log", None)
            if callable(log):
                try:
                    log(
                        f"{getattr(c, 'name', 'Player')} uses Lay on Hands on {getattr(target, 'name', 'Target')} "
                        f"for {actual_heal} HP ({heal_amount} points spent).",
                        cid=int(target.cid),
                    )
                except Exception:
                    pass
            self._toast(ws_id, f"Lay on Hands: healed {actual_heal} HP.")
        rebuild = getattr(t, "_rebuild_table", None)
        if callable(rebuild):
            try:
                rebuild(scroll_to_current=True)
            except Exception:
                pass
        return build_dispatch_result(
            "lay_on_hands_use",
            True,
            request=request_contract,
            target_cid=int(target.cid),
            points_spent=int(heal_amount),
            healed=int(actual_heal),
            cured_poisoned=bool(cure_poisoned),
        )

    def inventory_adjust_consumable(
        self,
        msg: Dict[str, Any],
        *,
        cid: Optional[int],
        ws_id: Any,
        is_admin: bool,
    ) -> Dict[str, Any]:
        t = self._tracker
        request_contract = build_inventory_adjust_consumable_contract(
            msg,
            cid=cid,
            ws_id=ws_id,
            is_admin=is_admin,
        )
        combatants = getattr(t, "combatants", {}) or {}
        if cid is None:
            return build_dispatch_result("inventory_adjust_consumable", False, reason="missing_cid", request=request_contract)
        try:
            cid_int = int(cid)
        except Exception:
            return build_dispatch_result("inventory_adjust_consumable", False, reason="invalid_cid", request=request_contract)
        c = combatants.get(cid_int)
        if c is None:
            return build_dispatch_result("inventory_adjust_consumable", False, reason="combatant_missing", request=request_contract)
        player_name = t._pc_name_for(cid_int)
        consumable_id = str(msg.get("consumable_id") or msg.get("id") or "").strip().lower()
        try:
            delta = int(msg.get("delta"))
        except Exception:
            delta = 0
        if not consumable_id or delta == 0:
            self._toast(ws_id, "Pick a consumable and amount, matey.")
            return build_dispatch_result("inventory_adjust_consumable", False, reason="invalid_args", request=request_contract)
        ok_inv, inv_err, quantity = t._adjust_inventory_consumable_quantity(player_name, consumable_id, delta)
        if not ok_inv:
            self._toast(ws_id, inv_err or "Could not update inventory, matey.")
            return build_dispatch_result(
                "inventory_adjust_consumable",
                False,
                reason="inventory_update_failed",
                error=str(inv_err or ""),
                request=request_contract,
            )
        registry_item = t._consumables_registry_payload().get(consumable_id, {})
        item_name = str((registry_item or {}).get("name") or consumable_id).strip() or consumable_id
        actor_name = getattr(c, "name", player_name or "Player")
        log = getattr(t, "_log", None)
        if callable(log):
            try:
                log(
                    f"{actor_name} adjusted inventory: {item_name} ({delta:+d}), now {int(quantity)}.",
                    cid=cid_int,
                )
            except Exception:
                pass
        self._toast(ws_id, f"{item_name}: {int(quantity)} in inventory.")
        rebuild = getattr(t, "_rebuild_table", None)
        if callable(rebuild):
            try:
                rebuild(scroll_to_current=True)
            except Exception:
                pass
        return build_dispatch_result(
            "inventory_adjust_consumable",
            True,
            request=request_contract,
            consumable_id=consumable_id,
            delta=delta,
            quantity=int(quantity),
        )

    def use_consumable(
        self,
        msg: Dict[str, Any],
        *,
        cid: Optional[int],
        ws_id: Any,
        is_admin: bool,
    ) -> Dict[str, Any]:
        t = self._tracker
        request_contract = build_use_consumable_contract(
            msg,
            cid=cid,
            ws_id=ws_id,
            is_admin=is_admin,
        )
        combatants = getattr(t, "combatants", {}) or {}
        if cid is None:
            return build_dispatch_result("use_consumable", False, reason="missing_cid", request=request_contract)
        try:
            cid_int = int(cid)
        except Exception:
            return build_dispatch_result("use_consumable", False, reason="invalid_cid", request=request_contract)
        c = combatants.get(cid_int)
        if c is None:
            return build_dispatch_result("use_consumable", False, reason="combatant_missing", request=request_contract)
        player_name = t._pc_name_for(cid_int)
        consumable_id = str(msg.get("consumable_id") or msg.get("id") or "").strip().lower()
        if not consumable_id:
            self._toast(ws_id, "Pick a consumable first, matey.")
            return build_dispatch_result("use_consumable", False, reason="missing_consumable_id", request=request_contract)
        ok_use, use_err, actual_heal = t._use_inventory_consumable(player_name, consumable_id, c)
        if not ok_use:
            self._toast(ws_id, use_err or "Could not use consumable, matey.")
            return build_dispatch_result(
                "use_consumable",
                False,
                reason="consumable_use_failed",
                error=str(use_err or ""),
                request=request_contract,
            )
        registry_item = t._consumables_registry_payload().get(consumable_id, {})
        item_name = str((registry_item or {}).get("name") or consumable_id).strip() or consumable_id
        log = getattr(t, "_log", None)
        if callable(log):
            try:
                log(
                    f"{getattr(c, 'name', 'Player')} uses {item_name} and heals {int(actual_heal)} HP.",
                    cid=cid_int,
                )
            except Exception:
                pass
        self._toast(ws_id, f"{item_name}: healed {int(actual_heal)} HP.")
        rebuild = getattr(t, "_rebuild_table", None)
        if callable(rebuild):
            try:
                rebuild(scroll_to_current=True)
            except Exception:
                pass
        return build_dispatch_result(
            "use_consumable",
            True,
            request=request_contract,
            consumable_id=consumable_id,
            healed=int(actual_heal),
        )

    def second_wind_use(
        self,
        msg: Dict[str, Any],
        *,
        cid: Optional[int],
        ws_id: Any,
        is_admin: bool,
    ) -> Dict[str, Any]:
        t = self._tracker
        request_contract = build_second_wind_use_contract(
            msg,
            cid=cid,
            ws_id=ws_id,
            is_admin=is_admin,
        )
        combatants = getattr(t, "combatants", {}) or {}
        if cid is None:
            return build_dispatch_result("second_wind_use", False, reason="missing_cid", request=request_contract)
        try:
            cid_int = int(cid)
        except Exception:
            return build_dispatch_result("second_wind_use", False, reason="invalid_cid", request=request_contract)
        c = combatants.get(cid_int)
        if c is None:
            return build_dispatch_result("second_wind_use", False, reason="combatant_missing", request=request_contract)
        player_name = t._pc_name_for(cid_int)
        profile = t._profile_for_player_name(player_name)
        if not isinstance(profile, dict):
            self._toast(ws_id, "No player profile found, matey.")
            return build_dispatch_result("second_wind_use", False, reason="missing_profile", request=request_contract)
        fighter_level = int(t._fighter_level_from_profile(profile) or 0)
        if fighter_level < 1:
            self._toast(ws_id, "Only fighters can use Second Wind, matey.")
            return build_dispatch_result("second_wind_use", False, reason="not_fighter", request=request_contract)
        ok_pool, pool_err = t._consume_resource_pool_for_cast(player_name, "second_wind", 1)
        if not ok_pool:
            self._toast(ws_id, pool_err or "No Second Wind uses remain, matey.")
            return build_dispatch_result(
                "second_wind_use",
                False,
                reason="pool_exhausted",
                error=str(pool_err or ""),
                request=request_contract,
            )
        healing_roll = None
        for key in ("healing_roll", "roll", "rolled"):
            value = msg.get(key)
            if value in (None, ""):
                continue
            try:
                healing_roll = int(value)
            except Exception:
                healing_roll = None
            break
        if healing_roll is None:
            hp_gain = int(sum(random.randint(1, 10) for _ in range(1)) + fighter_level)
        else:
            hp_gain = int(max(1, healing_roll) + fighter_level)
        cur_hp = int(getattr(c, "hp", 0) or 0)
        max_hp = int(getattr(c, "max_hp", cur_hp) or cur_hp)
        actual_heal = max(0, min(hp_gain, max(0, max_hp - cur_hp)))
        t._apply_heal_via_service(cid_int, actual_heal)
        if bool(getattr(t, "in_combat", False)) and int(getattr(c, "bonus_action_remaining", 0) or 0) > 0:
            t._use_bonus_action(c)
        log = getattr(t, "_log", None)
        if callable(log):
            try:
                log(
                    f"{getattr(c, 'name', 'Player')} uses Second Wind and regains {hp_gain} HP.",
                    cid=cid_int,
                )
            except Exception:
                pass
        self._toast(ws_id, f"Second Wind: regained {hp_gain} HP.")
        rebuild = getattr(t, "_rebuild_table", None)
        if callable(rebuild):
            try:
                rebuild(scroll_to_current=True)
            except Exception:
                pass
        return build_dispatch_result(
            "second_wind_use",
            True,
            request=request_contract,
            healed=int(actual_heal),
            rolled_heal=int(hp_gain),
            fighter_level=int(fighter_level),
        )

    def action_surge_use(
        self,
        msg: Dict[str, Any],
        *,
        cid: Optional[int],
        ws_id: Any,
        is_admin: bool,
    ) -> Dict[str, Any]:
        t = self._tracker
        request_contract = build_action_surge_use_contract(
            msg,
            cid=cid,
            ws_id=ws_id,
            is_admin=is_admin,
        )
        combatants = getattr(t, "combatants", {}) or {}
        if cid is None:
            return build_dispatch_result("action_surge_use", False, reason="missing_cid", request=request_contract)
        try:
            cid_int = int(cid)
        except Exception:
            return build_dispatch_result("action_surge_use", False, reason="invalid_cid", request=request_contract)
        c = combatants.get(cid_int)
        if c is None:
            return build_dispatch_result("action_surge_use", False, reason="combatant_missing", request=request_contract)
        player_name = t._pc_name_for(cid_int)
        profile = t._profile_for_player_name(player_name)
        if not isinstance(profile, dict):
            self._toast(ws_id, "No player profile found, matey.")
            return build_dispatch_result("action_surge_use", False, reason="missing_profile", request=request_contract)
        fighter_level = int(t._fighter_level_from_profile(profile) or 0)
        if fighter_level < 2:
            self._toast(ws_id, "Only fighters level 2+ can use Action Surge, matey.")
            return build_dispatch_result("action_surge_use", False, reason="fighter_level_too_low", request=request_contract)
        ok_pool, pool_err = t._consume_resource_pool_for_cast(player_name, "action_surge", 1)
        if not ok_pool:
            self._toast(ws_id, pool_err or "No Action Surge uses remain, matey.")
            return build_dispatch_result(
                "action_surge_use",
                False,
                reason="pool_exhausted",
                error=str(pool_err or ""),
                request=request_contract,
            )
        c.action_remaining = int(getattr(c, "action_remaining", 0) or 0) + 1
        c.action_total = int(getattr(c, "action_total", 1) or 1) + 1
        log = getattr(t, "_log", None)
        if callable(log):
            try:
                log(
                    f"{getattr(c, 'name', 'Player')} uses Action Surge and gains 1 action.",
                    cid=cid_int,
                )
            except Exception:
                pass
        self._toast(ws_id, "Action Surge used: +1 action.")
        rebuild = getattr(t, "_rebuild_table", None)
        if callable(rebuild):
            try:
                rebuild(scroll_to_current=True)
            except Exception:
                pass
        return build_dispatch_result(
            "action_surge_use",
            True,
            request=request_contract,
            action_remaining=int(getattr(c, "action_remaining", 0) or 0),
            action_total=int(getattr(c, "action_total", 0) or 0),
        )

    def star_advantage_use(
        self,
        msg: Dict[str, Any],
        *,
        cid: Optional[int],
        ws_id: Any,
        is_admin: bool,
    ) -> Dict[str, Any]:
        t = self._tracker
        request_contract = build_star_advantage_use_contract(
            msg,
            cid=cid,
            ws_id=ws_id,
            is_admin=is_admin,
        )
        combatants = getattr(t, "combatants", {}) or {}
        if cid is None:
            return build_dispatch_result("star_advantage_use", False, reason="missing_cid", request=request_contract)
        try:
            cid_int = int(cid)
        except Exception:
            return build_dispatch_result("star_advantage_use", False, reason="invalid_cid", request=request_contract)
        c = combatants.get(cid_int)
        if c is None:
            return build_dispatch_result("star_advantage_use", False, reason="combatant_missing", request=request_contract)
        player_name = t._pc_name_for(cid_int)
        ok_pool, pool_err = t._consume_resource_pool_for_cast(player_name, "star_advantage", 1)
        if not ok_pool:
            self._toast(ws_id, pool_err or "No Star Advantage charges remain, matey.")
            return build_dispatch_result(
                "star_advantage_use",
                False,
                reason="pool_exhausted",
                error=str(pool_err or ""),
                request=request_contract,
            )
        setattr(
            c,
            "pending_star_advantage_charge",
            {
                "name": "Star Advantage",
                "source": "Melvin's Magic Hat",
            },
        )
        log = getattr(t, "_log", None)
        if callable(log):
            try:
                log(
                    f"{getattr(c, 'name', 'Player')} readies Star Advantage.",
                    cid=cid_int,
                )
            except Exception:
                pass
        self._toast(ws_id, "Star Advantage readied.")
        return build_dispatch_result("star_advantage_use", True, request=request_contract)

    def monk_patient_defense(
        self,
        msg: Dict[str, Any],
        *,
        cid: Optional[int],
        ws_id: Any,
        is_admin: bool,
    ) -> Dict[str, Any]:
        t = self._tracker
        request_contract = build_monk_patient_defense_contract(
            msg,
            cid=cid,
            ws_id=ws_id,
            is_admin=is_admin,
        )
        combatants = getattr(t, "combatants", {}) or {}
        if cid is None:
            return build_dispatch_result("monk_patient_defense", False, reason="missing_cid", request=request_contract)
        try:
            cid_int = int(cid)
        except Exception:
            return build_dispatch_result("monk_patient_defense", False, reason="invalid_cid", request=request_contract)
        c = combatants.get(cid_int)
        if c is None:
            return build_dispatch_result("monk_patient_defense", False, reason="combatant_missing", request=request_contract)
        if not bool(getattr(c, "is_pc", False)):
            self._toast(ws_id, "Only player characters can use Monk Focus actions, matey.")
            return build_dispatch_result("monk_patient_defense", False, reason="not_player_character", request=request_contract)
        try:
            player_name = t._pc_name_for(cid_int)
        except Exception:
            player_name = ""
        profile = t._profile_for_player_name(player_name)
        if not isinstance(profile, dict):
            self._toast(ws_id, "No player profile found, matey.")
            return build_dispatch_result("monk_patient_defense", False, reason="missing_profile", request=request_contract)
        monk_level = int(t._class_level_from_profile(profile, "monk") or 0)
        if monk_level < 2:
            self._toast(ws_id, "Only monks level 2+ can use Patient Defense, matey.")
            return build_dispatch_result("monk_patient_defense", False, reason="monk_level_too_low", request=request_contract)
        mode = str(msg.get("mode") or "free").strip().lower()
        if mode not in ("free", "focus"):
            mode = "free"
        if not t._use_bonus_action(c):
            self._toast(ws_id, "No bonus actions left, matey.")
            return build_dispatch_result("monk_patient_defense", False, reason="no_bonus_action", request=request_contract)
        if mode == "focus":
            ok_pool, pool_err = t._consume_resource_pool_for_cast(player_name, "focus_points", 1)
            if not ok_pool:
                self._toast(ws_id, pool_err or "No Focus Points remain, matey.")
                return build_dispatch_result(
                    "monk_patient_defense",
                    False,
                    reason="pool_exhausted",
                    error=str(pool_err or ""),
                    request=request_contract,
                )
            setattr(c, "disengage_active", True)
            log = getattr(t, "_log", None)
            if callable(log):
                try:
                    log(
                        f"{c.name} used Patient Defense (Disengage + Dodge) (bonus action, 1 Focus)",
                        cid=cid_int,
                    )
                except Exception:
                    pass
            if monk_level >= 10:
                ma_die = 8 if monk_level >= 5 else 6
                temp_roll = random.randint(1, ma_die) + random.randint(1, ma_die)
                current_temp_hp = int(getattr(c, "temp_hp", 0) or 0)
                applied_temp = max(current_temp_hp, temp_roll)
                t._apply_heal_via_service(cid_int, applied_temp, is_temp_hp=True)
                if callable(log):
                    try:
                        log(
                            f"{c.name} gained Monk Focus temp HP: {temp_roll} (2d{ma_die}; current temp HP {getattr(c, 'temp_hp', 0)}).",
                            cid=cid_int,
                        )
                    except Exception:
                        pass
            self._toast(ws_id, "Patient Defense used (1 Focus).")
        else:
            setattr(c, "disengage_active", True)
            log = getattr(t, "_log", None)
            if callable(log):
                try:
                    log(f"{c.name} used Patient Defense (Disengage) (bonus action)", cid=cid_int)
                except Exception:
                    pass
            self._toast(ws_id, "Patient Defense used.")
        rebuild = getattr(t, "_rebuild_table", None)
        if callable(rebuild):
            try:
                rebuild(scroll_to_current=True)
            except Exception:
                pass
        return build_dispatch_result(
            "monk_patient_defense",
            True,
            request=request_contract,
            mode=mode,
        )

    def monk_step_of_wind(
        self,
        msg: Dict[str, Any],
        *,
        cid: Optional[int],
        ws_id: Any,
        is_admin: bool,
    ) -> Dict[str, Any]:
        t = self._tracker
        request_contract = build_monk_step_of_wind_contract(
            msg,
            cid=cid,
            ws_id=ws_id,
            is_admin=is_admin,
        )
        combatants = getattr(t, "combatants", {}) or {}
        if cid is None:
            return build_dispatch_result("monk_step_of_wind", False, reason="missing_cid", request=request_contract)
        try:
            cid_int = int(cid)
        except Exception:
            return build_dispatch_result("monk_step_of_wind", False, reason="invalid_cid", request=request_contract)
        c = combatants.get(cid_int)
        if c is None:
            return build_dispatch_result("monk_step_of_wind", False, reason="combatant_missing", request=request_contract)
        if not bool(getattr(c, "is_pc", False)):
            self._toast(ws_id, "Only player characters can use Monk Focus actions, matey.")
            return build_dispatch_result("monk_step_of_wind", False, reason="not_player_character", request=request_contract)
        try:
            player_name = t._pc_name_for(cid_int)
        except Exception:
            player_name = ""
        profile = t._profile_for_player_name(player_name)
        if not isinstance(profile, dict):
            self._toast(ws_id, "No player profile found, matey.")
            return build_dispatch_result("monk_step_of_wind", False, reason="missing_profile", request=request_contract)
        monk_level = int(t._class_level_from_profile(profile, "monk") or 0)
        if monk_level < 2:
            self._toast(ws_id, "Only monks level 2+ can use Step of the Wind, matey.")
            return build_dispatch_result("monk_step_of_wind", False, reason="monk_level_too_low", request=request_contract)
        mode = str(msg.get("mode") or "free").strip().lower()
        if mode not in ("free", "focus"):
            mode = "free"
        if not t._use_bonus_action(c):
            self._toast(ws_id, "No bonus actions left, matey.")
            return build_dispatch_result("monk_step_of_wind", False, reason="no_bonus_action", request=request_contract)
        if mode == "focus":
            ok_pool, pool_err = t._consume_resource_pool_for_cast(player_name, "focus_points", 1)
            if not ok_pool:
                self._toast(ws_id, pool_err or "No Focus Points remain, matey.")
                return build_dispatch_result(
                    "monk_step_of_wind",
                    False,
                    reason="pool_exhausted",
                    error=str(pool_err or ""),
                    request=request_contract,
                )
        try:
            base_speed = int(t._mode_speed(c))
        except Exception:
            base_speed = int(getattr(c, "speed", 30) or 30)
        total = int(getattr(c, "move_total", 0) or 0)
        rem = int(getattr(c, "move_remaining", 0) or 0)
        setattr(c, "move_total", total + base_speed)
        setattr(c, "move_remaining", rem + base_speed)
        log = getattr(t, "_log", None)
        if callable(log):
            try:
                if mode == "focus":
                    log(f"{c.name} used Step of the Wind (Dash + Disengage) (bonus action, 1 Focus)", cid=cid_int)
                else:
                    log(f"{c.name} used Step of the Wind (Dash) (bonus action)", cid=cid_int)
                log(f"{c.name} jump distance doubled (not automated).", cid=cid_int)
            except Exception:
                pass
        self._toast(ws_id, "Step of the Wind used.")
        rebuild = getattr(t, "_rebuild_table", None)
        if callable(rebuild):
            try:
                rebuild(scroll_to_current=True)
            except Exception:
                pass
        return build_dispatch_result(
            "monk_step_of_wind",
            True,
            request=request_contract,
            mode=mode,
            move_total=int(getattr(c, "move_total", 0) or 0),
            move_remaining=int(getattr(c, "move_remaining", 0) or 0),
        )

    def monk_elemental_attunement(
        self,
        msg: Dict[str, Any],
        *,
        cid: Optional[int],
        ws_id: Any,
        is_admin: bool,
    ) -> Dict[str, Any]:
        t = self._tracker
        request_contract = build_monk_elemental_attunement_contract(
            msg,
            cid=cid,
            ws_id=ws_id,
            is_admin=is_admin,
        )
        combatants = getattr(t, "combatants", {}) or {}
        if cid is None:
            return build_dispatch_result("monk_elemental_attunement", False, reason="missing_cid", request=request_contract)
        try:
            cid_int = int(cid)
        except Exception:
            return build_dispatch_result("monk_elemental_attunement", False, reason="invalid_cid", request=request_contract)
        c = combatants.get(cid_int)
        if c is None:
            return build_dispatch_result("monk_elemental_attunement", False, reason="combatant_missing", request=request_contract)
        if not bool(getattr(c, "is_pc", False)):
            self._toast(ws_id, "Only player characters can use Monk Focus actions, matey.")
            return build_dispatch_result("monk_elemental_attunement", False, reason="not_player_character", request=request_contract)
        try:
            player_name = t._pc_name_for(cid_int)
        except Exception:
            player_name = ""
        profile = t._profile_for_player_name(player_name)
        if not isinstance(profile, dict):
            self._toast(ws_id, "No player profile found, matey.")
            return build_dispatch_result("monk_elemental_attunement", False, reason="missing_profile", request=request_contract)
        monk_level = int(t._class_level_from_profile(profile, "monk") or 0)
        if monk_level < 3:
            self._toast(ws_id, "Only monks with Warrior of the Elements can use Elemental Attunement, matey.")
            return build_dispatch_result("monk_elemental_attunement", False, reason="monk_level_too_low", request=request_contract)
        mode = str(msg.get("mode") or "activate").strip().lower()
        currently_active = bool(t._elemental_attunement_active(c))
        if mode == "deactivate":
            if currently_active:
                setattr(c, "elemental_attunement_active", False)
                log = getattr(t, "_log", None)
                if callable(log):
                    try:
                        log(f"{c.name} ended Elemental Attunement.", cid=cid_int)
                    except Exception:
                        pass
                self._toast(ws_id, "Elemental Attunement ended.")
                rebuild = getattr(t, "_rebuild_table", None)
                if callable(rebuild):
                    try:
                        rebuild(scroll_to_current=True)
                    except Exception:
                        pass
                return build_dispatch_result("monk_elemental_attunement", True, request=request_contract, mode="deactivate")
            self._toast(ws_id, "Elemental Attunement is not active.")
            return build_dispatch_result(
                "monk_elemental_attunement",
                False,
                reason="not_active",
                request=request_contract,
            )
        if currently_active:
            self._toast(ws_id, "Elemental Attunement is already active.")
            return build_dispatch_result("monk_elemental_attunement", False, reason="already_active", request=request_contract)
        ok_pool, pool_err = t._consume_resource_pool_for_cast(player_name, "focus_points", 1)
        if not ok_pool:
            self._toast(ws_id, pool_err or "No Focus Points remain, matey.")
            return build_dispatch_result(
                "monk_elemental_attunement",
                False,
                reason="pool_exhausted",
                error=str(pool_err or ""),
                request=request_contract,
            )
        setattr(c, "elemental_attunement_active", True)
        log = getattr(t, "_log", None)
        if callable(log):
            try:
                log(f"{c.name} activated Elemental Attunement (1 Focus).", cid=cid_int)
            except Exception:
                pass
        self._toast(ws_id, "Elemental Attunement activated.")
        rebuild = getattr(t, "_rebuild_table", None)
        if callable(rebuild):
            try:
                rebuild(scroll_to_current=True)
            except Exception:
                pass
        return build_dispatch_result("monk_elemental_attunement", True, request=request_contract, mode="activate")

    def monk_elemental_burst(
        self,
        msg: Dict[str, Any],
        *,
        cid: Optional[int],
        ws_id: Any,
        is_admin: bool,
    ) -> Dict[str, Any]:
        t = self._tracker
        request_contract = build_monk_elemental_burst_contract(
            msg,
            cid=cid,
            ws_id=ws_id,
            is_admin=is_admin,
        )
        combatants = getattr(t, "combatants", {}) or {}
        if cid is None:
            return build_dispatch_result("monk_elemental_burst", False, reason="missing_cid", request=request_contract)
        try:
            cid_int = int(cid)
        except Exception:
            return build_dispatch_result("monk_elemental_burst", False, reason="invalid_cid", request=request_contract)
        c = combatants.get(cid_int)
        if c is None:
            return build_dispatch_result("monk_elemental_burst", False, reason="combatant_missing", request=request_contract)
        if not bool(getattr(c, "is_pc", False)):
            self._toast(ws_id, "Only player characters can use Monk Focus actions, matey.")
            return build_dispatch_result("monk_elemental_burst", False, reason="not_player_character", request=request_contract)
        try:
            player_name = t._pc_name_for(cid_int)
        except Exception:
            player_name = ""
        profile = t._profile_for_player_name(player_name)
        if not isinstance(profile, dict):
            self._toast(ws_id, "No player profile found, matey.")
            return build_dispatch_result("monk_elemental_burst", False, reason="missing_profile", request=request_contract)
        monk_level = int(t._class_level_from_profile(profile, "monk") or 0)
        if monk_level < 3:
            self._toast(ws_id, "Only monks with Warrior of the Elements can use Elemental Burst, matey.")
            return build_dispatch_result("monk_elemental_burst", False, reason="monk_level_too_low", request=request_contract)
        payload = msg.get("payload") if isinstance(msg.get("payload"), dict) else {}
        damage_type = str(msg.get("damage_type") or payload.get("damage_type") or "").strip().lower()
        if damage_type not in {"acid", "cold", "fire", "lightning", "thunder"}:
            self._toast(ws_id, "Pick a valid Elemental Burst damage type, matey.")
            return build_dispatch_result("monk_elemental_burst", False, reason="invalid_damage_type", request=request_contract)
        if int(getattr(c, "action_remaining", 0) or 0) <= 0:
            self._toast(ws_id, "No actions left, matey.")
            return build_dispatch_result("monk_elemental_burst", False, reason="no_actions_remaining", request=request_contract)
        ok_pool, pool_err = t._consume_resource_pool_for_cast(player_name, "focus_points", 2)
        if not ok_pool:
            self._toast(ws_id, pool_err or "Need 2 Focus Points for Elemental Burst, matey.")
            return build_dispatch_result(
                "monk_elemental_burst",
                False,
                reason="pool_exhausted",
                error=str(pool_err or ""),
                request=request_contract,
            )
        if not t._use_action(c):
            self._toast(ws_id, "No actions left, matey.")
            return build_dispatch_result("monk_elemental_burst", False, reason="cannot_spend_action", request=request_contract)
        movement_mode = str(msg.get("movement_mode") or payload.get("movement_mode") or "").strip().lower()
        if movement_mode not in ("push", "pull"):
            movement_mode = ""
        martial_die = int(t._monk_martial_arts_die(monk_level))
        save_dc = int(t._monk_save_dc_for_profile(profile))
        cols, rows, _obstacles, _rough, positions = t._lan_live_map_data()
        try:
            cx = float(payload.get("cx"))
            cy = float(payload.get("cy"))
        except Exception:
            origin = positions.get(cid_int)
            if isinstance(origin, tuple) and len(origin) == 2:
                cx, cy = float(origin[0]), float(origin[1])
            else:
                cx = max(0.0, (int(cols) - 1) / 2.0) if int(cols) > 0 else 0.0
                cy = max(0.0, (int(rows) - 1) / 2.0) if int(rows) > 0 else 0.0
        try:
            feet_per_square = 5.0
            mw = getattr(t, "_map_window", None)
            if mw is not None and hasattr(mw, "winfo_exists") and mw.winfo_exists():
                feet_per_square = float(getattr(mw, "feet_per_square", feet_per_square) or feet_per_square)
        except Exception:
            feet_per_square = 5.0
        feet_per_square = max(1.0, float(feet_per_square))
        aoe = {
            "kind": "sphere",
            "name": "Elemental Burst",
            "cx": float(cx),
            "cy": float(cy),
            "radius_ft": 20.0,
            "radius_sq": max(0.5, float(20.0 / feet_per_square)),
            "dc": int(save_dc),
            "save_type": "dex",
            "damage_type": str(damage_type),
            "half_on_pass": True,
        }
        fail_effects: list[Dict[str, Any]] = [{"effect": "damage", "damage_type": str(damage_type), "dice": f"3d{int(martial_die)}"}]
        if movement_mode:
            fail_effects.append({"effect": "forced_movement", "mode": str(movement_mode), "distance_ft": 10, "origin": "aoe_center"})
        preset = {
            "name": "Elemental Burst",
            "automation": "full",
            "tags": ["aoe", "automation_full"],
            "mechanics": {
                "automation": "full",
                "sequence": [
                    {
                        "check": {"kind": "saving_throw", "ability": "dex", "dc": int(save_dc)},
                        "outcomes": {
                            "fail": fail_effects,
                            "success": [{"effect": "damage", "damage_type": str(damage_type), "dice": f"3d{int(martial_die)}", "multiplier": 0.5}],
                        },
                    }
                ],
            },
        }
        resolved = t._lan_auto_resolve_cast_aoe(
            0,
            aoe,
            caster=c,
            spell_slug="monk-elemental-burst",
            spell_id="monk-elemental-burst",
            slot_level=None,
            preset=preset,
        )
        if resolved:
            rider_text = f", {movement_mode} 10 ft on failed save" if movement_mode else ""
            log = getattr(t, "_log", None)
            if callable(log):
                try:
                    log(
                        f"{c.name} used Elemental Burst ({damage_type.title()}, 3d{int(martial_die)}, DC {int(save_dc)}{rider_text}) "
                        f"(Magic Action, 2 Focus).",
                        cid=cid_int,
                    )
                except Exception:
                    pass
            self._toast(ws_id, "Elemental Burst cast.")
        else:
            self._toast(ws_id, "Elemental Burst failed to resolve, matey.")
        rebuild = getattr(t, "_rebuild_table", None)
        if callable(rebuild):
            try:
                rebuild(scroll_to_current=True)
            except Exception:
                pass
        return build_dispatch_result(
            "monk_elemental_burst",
            bool(resolved),
            request=request_contract,
            damage_type=damage_type,
            movement_mode=movement_mode,
            save_dc=save_dc,
            martial_die=martial_die,
        )

    def monk_uncanny_metabolism(
        self,
        msg: Dict[str, Any],
        *,
        cid: Optional[int],
        ws_id: Any,
        is_admin: bool,
    ) -> Dict[str, Any]:
        t = self._tracker
        request_contract = build_monk_uncanny_metabolism_contract(
            msg,
            cid=cid,
            ws_id=ws_id,
            is_admin=is_admin,
        )
        combatants = getattr(t, "combatants", {}) or {}
        if cid is None:
            return build_dispatch_result("monk_uncanny_metabolism", False, reason="missing_cid", request=request_contract)
        try:
            cid_int = int(cid)
        except Exception:
            return build_dispatch_result("monk_uncanny_metabolism", False, reason="invalid_cid", request=request_contract)
        c = combatants.get(cid_int)
        if c is None:
            return build_dispatch_result("monk_uncanny_metabolism", False, reason="combatant_missing", request=request_contract)
        if not bool(getattr(c, "is_pc", False)):
            self._toast(ws_id, "Only player characters can use Monk Focus actions, matey.")
            return build_dispatch_result("monk_uncanny_metabolism", False, reason="not_player_character", request=request_contract)
        try:
            player_name = t._pc_name_for(cid_int)
        except Exception:
            player_name = ""
        profile = t._profile_for_player_name(player_name)
        if not isinstance(profile, dict):
            self._toast(ws_id, "No player profile found, matey.")
            return build_dispatch_result("monk_uncanny_metabolism", False, reason="missing_profile", request=request_contract)
        monk_level = int(t._class_level_from_profile(profile, "monk") or 0)
        if monk_level < 2:
            self._toast(ws_id, "Only monks can use Uncanny Metabolism, matey.")
            return build_dispatch_result("monk_uncanny_metabolism", False, reason="monk_level_too_low", request=request_contract)
        if not t._use_bonus_action(c):
            self._toast(ws_id, "No bonus actions left, matey.")
            return build_dispatch_result("monk_uncanny_metabolism", False, reason="no_bonus_action", request=request_contract)
        ok_pool, pool_err = t._consume_resource_pool_for_cast(player_name, "uncanny_metabolism", 1)
        if not ok_pool:
            self._toast(ws_id, pool_err or "Uncanny Metabolism is spent, matey.")
            return build_dispatch_result(
                "monk_uncanny_metabolism",
                False,
                reason="pool_exhausted",
                error=str(pool_err or ""),
                request=request_contract,
            )
        pools = t._normalize_player_resource_pools(profile)
        focus_pool = next((entry for entry in pools if str(entry.get("id") or "").strip().lower() == "focus_points"), None)
        focus_max = 0
        try:
            focus_max = max(0, int((focus_pool or {}).get("max", 0) or 0))
        except Exception:
            focus_max = 0
        if focus_max > 0:
            t._set_player_resource_pool_current(player_name, "focus_points", focus_max)
        martial_die = int(t._monk_martial_arts_die(monk_level))
        heal_amount = int(random.randint(1, int(martial_die)))
        hp_now = int(getattr(c, "hp", 0) or 0)
        hp_max = int(getattr(c, "max_hp", hp_now) or hp_now)
        actual_heal = max(0, min(heal_amount, max(0, hp_max - hp_now)))
        t._apply_heal_via_service(cid_int, actual_heal)
        log = getattr(t, "_log", None)
        if callable(log):
            try:
                log(
                    f"{c.name} used Uncanny Metabolism: restored Focus and healed {int(heal_amount)} HP.",
                    cid=cid_int,
                )
            except Exception:
                pass
        self._toast(ws_id, "Uncanny Metabolism used.")
        rebuild = getattr(t, "_rebuild_table", None)
        if callable(rebuild):
            try:
                rebuild(scroll_to_current=True)
            except Exception:
                pass
        return build_dispatch_result(
            "monk_uncanny_metabolism",
            True,
            request=request_contract,
            healed=int(actual_heal),
            rolled_heal=int(heal_amount),
            focus_refilled_to=int(focus_max),
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
