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
  - player movement / perform-action family:
    ``move``, ``cycle_movement_mode``, and ``perform_action``
  - player AoE manipulation family:
    ``aoe_move`` and ``aoe_remove``
  - player bard/glamour specialty family:
    ``command_resolve``, ``bardic_inspiration_grant``,
    ``bardic_inspiration_use``, ``mantle_of_inspiration``,
    ``beguiling_magic_restore``, and ``beguiling_magic_use``
  - player summon/echo specialty family:
    ``echo_summon``, ``echo_swap``, ``dismiss_summons``,
    ``dismiss_persistent_summon``, ``reappear_persistent_summon``,
    ``assign_pre_summon``, and ``echo_tether_response``
  - player initiative/reaction specialty family:
    ``initiative_roll`` and ``hellish_rebuke_resolve``
  - player wild-shape family:
    ``wild_shape_apply``, ``wild_shape_pool_set_current``,
    ``wild_shape_revert``, ``wild_shape_regain_use``,
    ``wild_shape_regain_spell``, and ``wild_shape_set_known``
  - player turn-local / mobility-lite commands:
    ``mount_request``, ``mount_response``, ``dismount``, ``dash``,
    ``use_action``, ``use_bonus_action``, ``stand_up``, and ``reset_turn``
  - utility/admin player-path commands:
    ``set_color``, ``set_facing``, ``set_auras_enabled``, and
    ``reset_player_characters``
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
  - player "reaction response" lifecycle and trigger-specific resolution:
    request-id lookup, reactor-cid match, and shield / hellish rebuke /
    absorb elements / interception handling

Still tracker-owned (delegated to by this service):
  - deep attack adjudication (damage math, spell riders, weapon mastery,
    opportunity attack halting)
  - deep spell adjudication (save rolls, spell mark/curse state, healing
    and damage resolution)

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

import random
import asyncio
import math
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Optional

from player_command_contracts import (
    ACTIVE_PROMPT_STATES,
    AOE_MANIPULATION_COMMAND_TYPES,
    BARD_GLAMOUR_SPECIALTY_COMMAND_TYPES,
    FIGHTER_MONK_RESOURCE_ACTION_TYPES,
    INITIATIVE_REACTION_SPECIALTY_COMMAND_TYPES,
    MOVEMENT_ACTION_COMMAND_TYPES,
    SPECIAL_REACTION_TRIGGERS,
    SPELL_LAUNCH_COMMAND_TYPES,
    SUMMON_ECHO_SPECIALTY_COMMAND_TYPES,
    TURN_LOCAL_COMMAND_TYPES,
    UTILITY_ADMIN_COMMAND_TYPES,
    WILD_SHAPE_COMMAND_TYPES,
    apply_resume_dispatch,
    build_aoe_move_contract,
    build_aoe_remove_contract,
    build_attack_request_contract,
    build_action_surge_use_contract,
    build_bardic_inspiration_grant_contract,
    build_bardic_inspiration_use_contract,
    build_beguiling_magic_restore_contract,
    build_beguiling_magic_use_contract,
    build_cast_aoe_contract,  # noqa: F401 — also used for counterspell AoE resume_dispatch
    build_cast_spell_contract,
    build_command_resolve_contract,
    build_cycle_movement_mode_contract,
    build_dash_contract,
    build_dispatch_result,
    build_dismiss_persistent_summon_contract,
    build_dismiss_summons_contract,
    build_dismount_contract,
    build_echo_summon_contract,
    build_echo_swap_contract,
    build_echo_tether_response_contract,
    build_end_turn_contract,
    build_hellish_rebuke_resolve_start_payload,
    build_hellish_rebuke_resolve_contract,
    build_initiative_roll_contract,
    build_inventory_adjust_consumable_contract,
    build_lay_on_hands_use_contract,
    build_monk_elemental_attunement_contract,
    build_monk_elemental_burst_contract,
    build_monk_patient_defense_contract,
    build_monk_step_of_wind_contract,
    build_monk_uncanny_metabolism_contract,
    build_mantle_of_inspiration_contract,
    build_manual_override_contract,
    build_manual_override_resource_pool_contract,
    build_manual_override_spell_slot_contract,
    build_mount_request_contract,
    build_mount_response_contract,
    build_move_contract,
    build_perform_action_contract,
    build_prompt_record,
    build_prompt_snapshot,
    build_reaction_offer_event,
    build_reaction_prefs_update_contract,
    build_reaction_response_contract,
    build_reappear_persistent_summon_contract,
    build_reset_player_characters_contract,
    build_reset_turn_contract,
    build_resume_dispatch,
    build_set_auras_enabled_contract,
    build_set_color_contract,
    build_set_facing_contract,
    build_second_wind_use_contract,
    build_spell_target_request_contract,
    build_stand_up_contract,
    build_star_advantage_use_contract,
    build_assign_pre_summon_contract,
    build_use_action_contract,
    build_use_bonus_action_contract,
    build_use_consumable_contract,
    build_wild_shape_apply_contract,
    build_wild_shape_pool_set_current_contract,
    build_wild_shape_regain_spell_contract,
    build_wild_shape_regain_use_contract,
    build_wild_shape_revert_contract,
    build_wild_shape_set_known_contract,
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
    logic still lives on the tracker for attack/spell adjudication
    (``_adjudicate_attack_request``, ``_adjudicate_spell_target_request``),
    and trigger-specific reaction resolution now lives in this service while
    still calling tracker runtime helpers. Every migrated player command enters
    through this service so that
    future passes can evolve the tracker-side implementation without moving
    the transport/authority boundary again.
    """

    _FIGHTER_MONK_RESOURCE_ACTION_HANDLERS = {
        command_type: command_type for command_type in FIGHTER_MONK_RESOURCE_ACTION_TYPES
    }
    _MOVEMENT_ACTION_COMMAND_HANDLERS = {
        command_type: command_type for command_type in MOVEMENT_ACTION_COMMAND_TYPES
    }
    _AOE_MANIPULATION_COMMAND_HANDLERS = {
        command_type: command_type for command_type in AOE_MANIPULATION_COMMAND_TYPES
    }
    _BARD_GLAMOUR_SPECIALTY_COMMAND_HANDLERS = {
        command_type: command_type for command_type in BARD_GLAMOUR_SPECIALTY_COMMAND_TYPES
    }
    _SUMMON_ECHO_SPECIALTY_COMMAND_HANDLERS = {
        command_type: command_type for command_type in SUMMON_ECHO_SPECIALTY_COMMAND_TYPES
    }
    _INITIATIVE_REACTION_SPECIALTY_COMMAND_HANDLERS = {
        command_type: command_type for command_type in INITIATIVE_REACTION_SPECIALTY_COMMAND_TYPES
    }
    _UTILITY_ADMIN_COMMAND_HANDLERS = {
        command_type: command_type for command_type in UTILITY_ADMIN_COMMAND_TYPES
    }
    _TURN_LOCAL_COMMAND_HANDLERS = {
        command_type: command_type for command_type in TURN_LOCAL_COMMAND_TYPES
    }
    _WILD_SHAPE_COMMAND_HANDLERS = {
        command_type: command_type for command_type in WILD_SHAPE_COMMAND_TYPES
    }
    _SPELL_LAUNCH_COMMAND_HANDLERS = {
        command_type: command_type for command_type in SPELL_LAUNCH_COMMAND_TYPES
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

    def _tracker_module(self):
        module_candidates = [
            str(getattr(type(self._tracker), "__module__", "") or "").strip(),
            str(getattr(getattr(self._tracker, "_lan_apply_action", None), "__module__", "") or "").strip(),
            "dnd_initative_tracker",
        ]
        for module_name in module_candidates:
            if not module_name:
                continue
            module = sys.modules.get(module_name)
            if module is not None:
                return module
        return None

    def _ask_yes_no(self, title: str, prompt: str) -> bool:
        modules = [
            self._tracker_module(),
            sys.modules.get("dnd_initative_tracker"),
        ]
        for module in modules:
            messagebox = getattr(module, "messagebox", None) if module is not None else None
            askyesno = getattr(messagebox, "askyesno", None)
            if not callable(askyesno):
                continue
            try:
                return bool(askyesno(title, prompt))
            except Exception:
                continue
        return False

    def _coerce_optional_int(self, value: Any) -> Optional[int]:
        try:
            return int(value)
        except Exception:
            return None

    def _parse_int(self, value: Any, fallback: Optional[int] = None) -> Optional[int]:
        try:
            return int(value)
        except Exception:
            return fallback

    def _lan_log_warning(self, message: str) -> None:
        lan = self._tracker.__dict__.get("_lan")
        append_log = getattr(lan, "_append_lan_log", None) if lan is not None else None
        if callable(append_log):
            try:
                append_log(message, level="warning")
            except Exception:
                pass

    def _normalize_cid(self, value: Any, context: str) -> Optional[int]:
        module = self._tracker_module()
        normalize = getattr(module, "_normalize_cid_value", None) if module is not None else None
        if callable(normalize):
            try:
                return normalize(value, context, log_fn=self._lan_log_warning)
            except Exception:
                pass
        return self._coerce_optional_int(value)

    def allow_prompt_claim_override(
        self,
        msg: Dict[str, Any],
        *,
        action_type: str,
        cid: Optional[int],
        claimed: Optional[int],
    ) -> bool:
        """Return True when a prompt follow-up may bypass claim mismatch gating.

        This owns the action-family-specific prompt override rules that were
        previously embedded in the shared `_lan_apply_action()` claim gate.
        """
        if not isinstance(msg, dict):
            return False
        if cid is None or claimed is None or int(cid) == int(claimed):
            return False
        command_type = str(action_type or "").strip().lower()
        if command_type not in {"attack_request", "spell_target_request"}:
            return False
        prompt_attacker_cid = self._normalize_cid(
            msg.get("prompt_attacker_cid"),
            f"{command_type}.prompt_attacker_cid",
        )
        if prompt_attacker_cid is None or int(prompt_attacker_cid) != int(cid):
            return False

        current_turn_cid = self._normalize_cid(
            getattr(self._tracker, "current_cid", None),
            f"{command_type}.prompt.current_cid",
        )
        if current_turn_cid is not None and int(current_turn_cid) == int(cid):
            return True

        if command_type == "attack_request":
            return str(msg.get("opportunity_attack") or "").strip().lower() in ("1", "true", "yes", "on")

        target_cid_for_prompt = self._normalize_cid(
            msg.get("target_cid"),
            "spell_target_request.prompt_target_cid",
        )
        if target_cid_for_prompt is None:
            return False
        spell_slug_for_prompt = str(msg.get("spell_slug") or "").strip().lower()
        spell_id_for_prompt = str(msg.get("spell_id") or "").strip().lower()
        aoes = self._tracker.__dict__.get("_lan_aoes", {})
        if not isinstance(aoes, dict):
            return False
        compute_included = getattr(self._tracker, "_lan_compute_included_units_for_aoe", None)
        for prompt_aoe in list(aoes.values()):
            if not isinstance(prompt_aoe, dict):
                continue
            if not bool(prompt_aoe.get("over_time")) and not bool(prompt_aoe.get("persistent")):
                continue
            owner_cid = self._normalize_cid(
                prompt_aoe.get("owner_cid"),
                "spell_target_request.prompt.owner_cid",
            )
            if owner_cid is None or int(owner_cid) != int(prompt_attacker_cid):
                continue
            aoe_slug = str(prompt_aoe.get("spell_slug") or "").strip().lower()
            aoe_id = str(prompt_aoe.get("spell_id") or "").strip().lower()
            if spell_slug_for_prompt and aoe_slug and aoe_slug != spell_slug_for_prompt:
                continue
            if spell_id_for_prompt and aoe_id and aoe_id != spell_id_for_prompt:
                continue
            try:
                included = compute_included(prompt_aoe) if callable(compute_included) else []
            except Exception:
                included = []
            for value in included if isinstance(included, list) else []:
                included_cid = self._normalize_cid(value, "spell_target_request.prompt.included")
                if included_cid is not None and int(included_cid) == int(target_cid_for_prompt):
                    return True
        return False

    def create_reaction_offer(
        self,
        reactor_cid: int,
        trigger: str,
        source_cid: int,
        target_cid: int,
        allowed_choices: list[Dict[str, Any]],
        ws_ids: list[int],
        *,
        extra_payload: Optional[Dict[str, Any]] = None,
        resolution: Optional[Dict[str, Any]] = None,
        resume_dispatch: Optional[Dict[str, Any]] = None,
        prompt_id: Optional[str] = None,
    ) -> Optional[str]:
        resolved_ws_ids: list[int] = []
        for ws_id in ws_ids or []:
            try:
                resolved_ws_ids.append(int(ws_id))
            except Exception:
                continue
        self._oplog(
            "reaction_offer:create "
            f"trigger={str(trigger)} reactor_cid={int(reactor_cid)} source_cid={int(source_cid)} "
            f"target_cid={int(target_cid)} ws_ids={resolved_ws_ids}",
            level="info",
        )
        if not allowed_choices:
            self._oplog("reaction_offer:create skipped (no allowed choices)", level="warning")
            return None
        if not resolved_ws_ids:
            self._oplog("reaction_offer:create skipped (no websocket targets)", level="warning")
            return None
        prompt = self.prompts.create_reaction_offer(
            reactor_cid=int(reactor_cid),
            trigger=str(trigger),
            source_cid=int(source_cid),
            target_cid=int(target_cid),
            allowed_choices=list(allowed_choices or []),
            ws_ids=resolved_ws_ids,
            extra_payload=dict(extra_payload) if isinstance(extra_payload, dict) else None,
            resolution=dict(resolution) if isinstance(resolution, dict) else None,
            resume_dispatch=dict(resume_dispatch) if isinstance(resume_dispatch, dict) else None,
            prompt_id=str(prompt_id).strip() if prompt_id else None,
        )
        payload = build_reaction_offer_event(prompt)
        lan = self._tracker.__dict__.get("_lan")
        loop = getattr(lan, "_loop", None) if lan is not None else None
        send_async = getattr(lan, "_send_async", None) if lan is not None else None
        if callable(send_async):
            for ws_id in resolved_ws_ids:
                try:
                    maybe_coro = send_async(int(ws_id), payload)
                    if asyncio.iscoroutine(maybe_coro):
                        if isinstance(loop, asyncio.AbstractEventLoop) and loop.is_running():
                            asyncio.run_coroutine_threadsafe(maybe_coro, loop)
                        else:
                            asyncio.run(maybe_coro)
                except Exception as exc:
                    self._oplog(
                        f"reaction_offer:send failed ws_id={int(ws_id)} trigger={str(trigger)} ({exc})",
                        level="warning",
                    )
        return str(payload.get("request_id") or "")

    def maybe_offer_absorb_elements(
        self,
        victim_cid: int,
        attacker_cid: Optional[int],
        *,
        pending_msg: Optional[Dict[str, Any]],
        damage_entries: list[Dict[str, Any]],
    ) -> Optional[str]:
        t = self._tracker
        attacker_cid = self._normalize_cid(attacker_cid, "absorb_elements.attacker")
        if attacker_cid is None:
            return None
        if int(attacker_cid) == int(victim_cid):
            return None
        victim = t.combatants.get(int(victim_cid))
        attacker = t.combatants.get(int(attacker_cid))
        if victim is None or attacker is None:
            return None
        trigger_types = t._absorb_elements_trigger_types(damage_entries)
        if not trigger_types:
            return None
        mode = t._reaction_mode_for(int(victim_cid), "absorb_elements", default="ask")
        if mode == "off":
            return None
        can_offer, _reason = t._can_offer_absorb_elements_reaction(victim, trigger_types)
        if not can_offer:
            return None
        ws_targets = t._find_ws_for_cid(int(victim_cid))
        choices = [
            {
                "kind": f"cast_absorb_elements_{dtype}",
                "label": f"Absorb Elements ({dtype.title()})",
                "mode": mode,
            }
            for dtype in trigger_types
        ]
        choices.extend(
            [
                {"kind": "absorb_elements_decline", "label": "No", "mode": "ask"},
                {"kind": "absorb_elements_never", "label": "No (don't ask again)", "mode": "ask"},
            ]
        )
        resume_dispatch = None
        if isinstance(pending_msg, dict):
            pending_type = str(pending_msg.get("type") or "").strip().lower()
            if pending_type == "attack_request":
                resume_dispatch = build_resume_dispatch(
                    "attack_request",
                    actor_cid=int(attacker_cid),
                    ws_id=pending_msg.get("_ws_id"),
                    is_admin=bool(str(pending_msg.get("admin_token") or "").strip()),
                    payload=build_attack_request_contract(
                        pending_msg,
                        cid=int(attacker_cid),
                        ws_id=pending_msg.get("_ws_id"),
                        is_admin=bool(str(pending_msg.get("admin_token") or "").strip()),
                    )["payload"],
                )
            elif pending_type == "spell_target_request":
                resume_dispatch = build_resume_dispatch(
                    "spell_target_request",
                    actor_cid=int(attacker_cid),
                    ws_id=pending_msg.get("_ws_id"),
                    is_admin=bool(str(pending_msg.get("admin_token") or "").strip()),
                    payload=build_spell_target_request_contract(
                        pending_msg,
                        cid=int(attacker_cid),
                        ws_id=pending_msg.get("_ws_id"),
                        is_admin=bool(str(pending_msg.get("admin_token") or "").strip()),
                    )["payload"],
                )
        return self.create_reaction_offer(
            int(victim_cid),
            "absorb_elements",
            int(attacker_cid),
            int(victim_cid),
            choices,
            ws_targets,
            extra_payload={
                "prompt": f"You took {', '.join(dtype.title() for dtype in trigger_types)} damage from {getattr(attacker, 'name', 'an attacker')}. Cast Absorb Elements?",
            },
            resolution={
                "victim_cid": int(victim_cid),
                "attacker_cid": int(attacker_cid),
                "trigger_types": list(trigger_types),
            },
            resume_dispatch=resume_dispatch,
        )

    def maybe_offer_hellish_rebuke(
        self,
        victim_cid: int,
        attacker_cid: Optional[int],
        damage_total: int,
    ) -> Optional[str]:
        if int(damage_total or 0) <= 0:
            return None
        t = self._tracker
        attacker_cid = self._normalize_cid(attacker_cid, "hellish_rebuke.attacker")
        if attacker_cid is None:
            return None
        if int(attacker_cid) == int(victim_cid):
            return None
        victim = t.combatants.get(int(victim_cid))
        attacker = t.combatants.get(int(attacker_cid))
        if victim is None or attacker is None:
            return None
        mode = t._reaction_mode_for(int(victim_cid), "hellish_rebuke", default="ask")
        if mode == "off":
            return None
        can_offer, _reason = t._can_offer_hellish_rebuke_reaction(victim)
        if not can_offer:
            return None
        positions = dict(getattr(t, "_lan_positions", {}) or {})
        victim_pos = positions.get(int(victim_cid)) or t._lan_current_position(int(victim_cid))
        attacker_pos = positions.get(int(attacker_cid)) or t._lan_current_position(int(attacker_cid))
        if victim_pos is None or attacker_pos is None:
            return None
        dist_ft = math.hypot(
            float(victim_pos[0]) - float(attacker_pos[0]),
            float(victim_pos[1]) - float(attacker_pos[1]),
        ) * t._lan_feet_per_square()
        if dist_ft - 60.0 > 1e-6:
            return None
        ws_targets = t._find_ws_for_cid(int(victim_cid))
        choices = [
            {"kind": "cast_hellish_rebuke", "label": "Hellish Rebuke", "mode": mode},
            {"kind": "decline", "label": "No", "mode": "ask"},
            {"kind": "never", "label": "No (don't ask again)", "mode": "ask"},
        ]
        pre_id = uuid.uuid4().hex
        req_id = self.create_reaction_offer(
            int(victim_cid),
            "hellish_rebuke",
            int(attacker_cid),
            int(attacker_cid),
            choices,
            ws_targets,
            extra_payload={
                "prompt": f"You took damage from {getattr(attacker, 'name', 'an attacker')}. React with Hellish Rebuke?",
            },
            prompt_id=pre_id,
            resolution={
                "victim_cid": int(victim_cid),
                "attacker_cid": int(attacker_cid),
                "spell_id": "hellish-rebuke",
                "max_range_ft": 60,
                "player_visible": build_hellish_rebuke_resolve_start_payload(
                    request_id=pre_id,
                    caster_cid=int(victim_cid),
                    attacker_cid=int(attacker_cid),
                    target_cid=int(attacker_cid),
                ),
            },
        )
        if req_id:
            self._oplog(
                "reaction_offer:hellish_rebuke pending "
                f"request_id={req_id} victim={int(victim_cid)} attacker={int(attacker_cid)} dist_ft={dist_ft:.1f}",
                level="info",
            )
        return req_id

    def maybe_offer_interception(
        self,
        victim_cid: int,
        attacker_cid: Optional[int],
        *,
        pending_msg: Optional[Dict[str, Any]],
        damage_entries: list[Dict[str, Any]],
    ) -> Optional[str]:
        t = self._tracker
        attacker_cid = self._normalize_cid(attacker_cid, "interception.attacker")
        if attacker_cid is None or int(attacker_cid) == int(victim_cid):
            return None
        victim = t.combatants.get(int(victim_cid))
        attacker = t.combatants.get(int(attacker_cid))
        if victim is None or attacker is None:
            return None
        if int(sum(int((entry or {}).get("amount") or 0) for entry in damage_entries if isinstance(entry, dict))) <= 0:
            return None
        positions = dict(getattr(t, "_lan_positions", {}) or {})
        victim_pos = positions.get(int(victim_cid)) or t._lan_current_position(int(victim_cid))
        if victim_pos is None:
            return None
        fps = t._lan_feet_per_square()
        best_reactor: Optional[Any] = None
        for reactor_cid, reactor in list(t.combatants.items()):
            try:
                rcid = int(reactor_cid)
            except Exception:
                continue
            if rcid in (int(victim_cid), int(attacker_cid)):
                continue
            if t._lan_is_friendly_unit(int(rcid)) != t._lan_is_friendly_unit(int(victim_cid)):
                continue
            if not t._can_offer_interception_reaction(reactor):
                continue
            reactor_pos = positions.get(int(rcid)) or t._lan_current_position(int(rcid))
            if not (isinstance(reactor_pos, tuple) and len(reactor_pos) == 2):
                continue
            dist_ft = max(
                abs(int(reactor_pos[0]) - int(victim_pos[0])),
                abs(int(reactor_pos[1]) - int(victim_pos[1])),
            ) * fps
            if dist_ft - 5.0 > 1e-6:
                continue
            best_reactor = reactor
            break
        if best_reactor is None:
            return None
        mode = t._reaction_mode_for(int(getattr(best_reactor, "cid", 0) or 0), "interception", default="ask")
        if mode == "off":
            return None
        ws_targets = t._find_ws_for_cid(int(getattr(best_reactor, "cid", 0) or 0))
        choices = [
            {"kind": "interception_yes", "label": "Interception", "mode": mode},
            {"kind": "interception_no", "label": "No", "mode": "ask"},
            {"kind": "interception_never", "label": "No (don't ask again)", "mode": "ask"},
        ]
        resume_dispatch = None
        if isinstance(pending_msg, dict):
            resume_dispatch = build_resume_dispatch(
                "attack_request",
                actor_cid=int(attacker_cid),
                ws_id=pending_msg.get("_ws_id"),
                is_admin=bool(str(pending_msg.get("admin_token") or "").strip()),
                payload=build_attack_request_contract(
                    pending_msg,
                    cid=int(attacker_cid),
                    ws_id=pending_msg.get("_ws_id"),
                    is_admin=bool(str(pending_msg.get("admin_token") or "").strip()),
                )["payload"],
            )
        return self.create_reaction_offer(
            int(getattr(best_reactor, "cid", 0) or 0),
            "interception",
            int(attacker_cid),
            int(victim_cid),
            choices,
            ws_targets,
            extra_payload={
                "prompt": f"{getattr(victim, 'name', 'Ally')} was hit by {getattr(attacker, 'name', 'an attacker')}. Use Interception?",
            },
            resolution={
                "reactor_cid": int(getattr(best_reactor, "cid", 0) or 0),
                "victim_cid": int(victim_cid),
                "attacker_cid": int(attacker_cid),
            },
            resume_dispatch=resume_dispatch,
        )

    def maybe_offer_spell_stopper(
        self,
        reactor_cid: int,
        source_cid: Optional[int],
        target_cid: Optional[int],
        *,
        pending_msg: Optional[Dict[str, Any]],
    ) -> Optional[str]:
        """Offer Fred's Spell Stopper reaction to interrupt a hostile spellcast."""
        t = self._tracker
        reactor_cid = self._normalize_cid(reactor_cid, "spell_stopper.reactor")
        if reactor_cid is None:
            return None
        reactor = t.combatants.get(int(reactor_cid))
        if reactor is None:
            return None
        
        mode = t._reaction_mode_for(int(reactor_cid), "spell_stopper", default="ask")
        if mode == "off":
            return None
        
        can_offer, _reason = t._can_offer_spell_stopper_reaction(reactor, source_cid)
        if not can_offer:
            return None
        
        ws_targets = t._find_ws_for_cid(int(reactor_cid))
        choices = [
            {"kind": "spell_stopper_yes", "label": "Spell Stopper", "mode": mode},
            {"kind": "spell_stopper_decline", "label": "No", "mode": "ask"},
            {"kind": "spell_stopper_never", "label": "No (don't ask again)", "mode": "ask"},
        ]
        
        resume_dispatch = None
        if isinstance(pending_msg, dict):
            pending_type = str(pending_msg.get("type") or "").strip().lower()
            if pending_type == "spell_target_request":
                resume_dispatch = build_resume_dispatch(
                    "spell_target_request",
                    actor_cid=self._normalize_cid(source_cid, "spell_stopper.source"),
                    ws_id=pending_msg.get("_ws_id"),
                    is_admin=bool(str(pending_msg.get("admin_token") or "").strip()),
                    payload=build_spell_target_request_contract(
                        pending_msg,
                        cid=self._normalize_cid(source_cid, "spell_stopper.source"),
                        ws_id=pending_msg.get("_ws_id"),
                        is_admin=bool(str(pending_msg.get("admin_token") or "").strip()),
                    )["payload"],
                )
        
        source_name = t._pc_name_for(int(source_cid)) if source_cid is not None else "Caster"
        target_name = t._pc_name_for(int(target_cid)) if target_cid is not None else "Target"
        
        return self.create_reaction_offer(
            int(reactor_cid),
            "spell_stopper",
            int(source_cid) if source_cid is not None else 0,
            int(target_cid) if target_cid is not None else 0,
            choices,
            ws_targets,
            extra_payload={
                "prompt": f"{source_name} is casting a spell at {target_name}. Use Spell Stopper?",
            },
            resolution={
                "reactor_cid": int(reactor_cid),
                "source_cid": int(source_cid) if source_cid is not None else 0,
                "target_cid": int(target_cid) if target_cid is not None else 0,
            },
            resume_dispatch=resume_dispatch,
        )

    def maybe_offer_counterspell(
        self,
        reactor_cid: int,
        source_cid: Optional[int],
        target_cid: Optional[int],
        *,
        pending_msg: Optional[Dict[str, Any]],
    ) -> Optional[str]:
        """Offer Counterspell reaction to interrupt a hostile spellcast.

        Bounded core: auto-succeeds on accept; no Intelligence-save contest branch.
        """
        t = self._tracker
        reactor_cid = self._normalize_cid(reactor_cid, "counterspell.reactor")
        if reactor_cid is None:
            return None
        reactor = t.combatants.get(int(reactor_cid))
        if reactor is None:
            return None

        mode = t._reaction_mode_for(int(reactor_cid), "counterspell", default="ask")
        if mode == "off":
            return None

        can_offer, _reason = t._can_offer_counterspell_reaction(reactor, source_cid)
        if not can_offer:
            return None

        ws_targets = t._find_ws_for_cid(int(reactor_cid))
        choices = [
            {"kind": "counterspell_yes", "label": "Counterspell", "mode": mode},
            {"kind": "counterspell_decline", "label": "No", "mode": "ask"},
            {"kind": "counterspell_never", "label": "No (don't ask again)", "mode": "ask"},
        ]

        resume_dispatch = None
        if isinstance(pending_msg, dict):
            pending_type = str(pending_msg.get("type") or "").strip().lower()
            actor_cid_norm = self._normalize_cid(source_cid, "counterspell.source")
            if pending_type == "spell_target_request":
                resume_dispatch = build_resume_dispatch(
                    "spell_target_request",
                    actor_cid=actor_cid_norm,
                    ws_id=pending_msg.get("_ws_id"),
                    is_admin=bool(str(pending_msg.get("admin_token") or "").strip()),
                    payload=build_spell_target_request_contract(
                        pending_msg,
                        cid=actor_cid_norm,
                        ws_id=pending_msg.get("_ws_id"),
                        is_admin=bool(str(pending_msg.get("admin_token") or "").strip()),
                    )["payload"],
                )
            elif pending_type == "cast_aoe":
                resume_dispatch = build_resume_dispatch(
                    "cast_aoe",
                    actor_cid=actor_cid_norm,
                    ws_id=pending_msg.get("_ws_id"),
                    is_admin=bool(str(pending_msg.get("admin_token") or "").strip()),
                    payload=build_cast_aoe_contract(
                        pending_msg,
                        cid=actor_cid_norm,
                        ws_id=pending_msg.get("_ws_id"),
                        is_admin=bool(str(pending_msg.get("admin_token") or "").strip()),
                    )["payload"],
                )

        source_name = t._pc_name_for(int(source_cid)) if source_cid is not None else "Caster"
        target_name = t._pc_name_for(int(target_cid)) if target_cid is not None else "Target"

        return self.create_reaction_offer(
            int(reactor_cid),
            "counterspell",
            int(source_cid) if source_cid is not None else 0,
            int(target_cid) if target_cid is not None else 0,
            choices,
            ws_targets,
            extra_payload={
                "prompt": f"{source_name} is casting a spell at {target_name}. Counterspell?",
            },
            resolution={
                "reactor_cid": int(reactor_cid),
                "source_cid": int(source_cid) if source_cid is not None else 0,
                "target_cid": int(target_cid) if target_cid is not None else 0,
            },
            resume_dispatch=resume_dispatch,
        )

    def _resolve_pc_name(self, cid: Optional[int]) -> str:
        if cid is None:
            return ""
        resolver = getattr(self._tracker, "_pc_name_for", None)
        if callable(resolver):
            try:
                return str(resolver(int(cid)) or "")
            except Exception:
                pass
        combatants = getattr(self._tracker, "combatants", {}) or {}
        combatant = combatants.get(int(cid))
        return str(getattr(combatant, "name", "") or "")

    def _move_log(self, ws_id: Any, event: str, **fields: Any) -> None:
        lan = getattr(self._tracker, "_lan", None)
        log_fn = getattr(lan, "_move_debug_log", None) if lan is not None else None
        if not callable(log_fn):
            return
        payload = {"event": str(event), "type": "move", "ws_id": ws_id, **fields}
        try:
            log_fn(payload, level="info")
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
        if command_type == "cast_aoe":
            return self.cast_aoe(payload, cid=actor_cid, ws_id=ws_id, is_admin=is_admin, claimed=actor_cid)
        return build_dispatch_result(
            "resume_dispatch",
            False,
            reason="unsupported_resume_command",
            resume_dispatch=resume_dispatch,
        )

    # ------------------------------------------------------------------
    # movement / perform-action commands
    # ------------------------------------------------------------------

    def dispatch_movement_action_command(
        self,
        msg: Dict[str, Any],
        *,
        cid: Optional[int],
        ws_id: Any,
        is_admin: bool,
    ) -> Dict[str, Any]:
        command_type = str(msg.get("type") if isinstance(msg, dict) else "").strip().lower()
        handler_name = self._MOVEMENT_ACTION_COMMAND_HANDLERS.get(command_type)
        if not handler_name:
            return build_dispatch_result(
                "movement_action_command",
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

    def move(
        self,
        msg: Dict[str, Any],
        *,
        cid: Optional[int],
        ws_id: Any,
        is_admin: bool,
    ) -> Dict[str, Any]:
        t = self._tracker
        request_contract = build_move_contract(
            msg,
            cid=cid,
            ws_id=ws_id,
            is_admin=is_admin,
        )
        if cid is None:
            msg["_move_applied"] = False
            msg["_move_reject_reason"] = "missing_cid"
            return build_dispatch_result("move", False, reason="missing_cid", request=request_contract)
        try:
            cid_int = int(cid)
        except Exception:
            msg["_move_applied"] = False
            msg["_move_reject_reason"] = "invalid_cid"
            return build_dispatch_result("move", False, reason="invalid_cid", request=request_contract)
        combatants = getattr(t, "combatants", {}) or {}
        mover = combatants.get(cid_int)
        if mover is None:
            msg["_move_applied"] = False
            msg["_move_reject_reason"] = "combatant_missing"
            self._toast(ws_id, "That scallywag ain’t in combat no more.")
            return build_dispatch_result("move", False, reason="combatant_missing", request=request_contract)

        to = msg.get("to") if isinstance(msg.get("to"), dict) else {}
        try:
            col = int(to.get("col"))
            row = int(to.get("row"))
        except Exception:
            msg["_move_applied"] = False
            msg["_move_reject_reason"] = "invalid_target"
            self._move_log(ws_id, "lan_move_reject", reason="invalid_target", to=to)
            self._toast(ws_id, "Pick a valid square, matey.")
            return build_dispatch_result(
                "move",
                False,
                reason="invalid_target",
                request=request_contract,
            )

        if self._coerce_optional_int(getattr(mover, "rider_cid", None)) is not None:
            self._toast(ws_id, "Rider movement uses the mount, matey.")
            return build_dispatch_result("move", False, reason="rider_direct_move", request=request_contract)

        _cols, _rows, _obstacles, _rough_terrain, positions = t._lan_live_map_data()
        before_pos = positions.get(cid_int)
        mw = getattr(t, "_map_window", None)
        map_ready = False
        try:
            map_ready = bool(mw is not None and mw.winfo_exists())
        except Exception:
            map_ready = False
        map_token_pos = None
        if map_ready:
            try:
                tok = (getattr(mw, "unit_tokens", {}) or {}).get(cid_int)
                if isinstance(tok, dict):
                    map_token_pos = {"col": tok.get("col"), "row": tok.get("row")}
            except Exception:
                map_token_pos = None
        self._move_log(
            ws_id,
            "lan_move_attempt",
            cid=cid_int,
            to={"col": col, "row": row},
            before_pos=before_pos,
            map_ready=map_ready,
            map_token_pos=map_token_pos,
            move_remaining=getattr(mover, "move_remaining", None),
        )

        current_cid = self._coerce_optional_int(getattr(t, "current_cid", None))
        owner_cid, echo_cid, breaks_echo_tether = t._johns_echo_tether_move_details(cid_int, int(col), int(row))
        is_owner_turn = bool(owner_cid is not None and current_cid is not None and int(owner_cid) == int(current_cid))
        should_prompt_echo_warning = bool(
            not is_admin
            and breaks_echo_tether
            and ws_id is not None
            and owner_cid is not None
            and echo_cid is not None
            and int(cid_int) in (int(owner_cid), int(echo_cid))
            and is_owner_turn
        )
        if should_prompt_echo_warning:
            request_id = f"echo_tether:{int(time.time()*1000)}:{int(cid_int)}:{int(col)}:{int(row)}"
            pending_confirms = getattr(t, "_pending_echo_tether_confirms", None)
            if not isinstance(pending_confirms, dict):
                pending_confirms = {}
                setattr(t, "_pending_echo_tether_confirms", pending_confirms)
            pending_confirms[request_id] = {
                "cid": int(cid_int),
                "col": int(col),
                "row": int(row),
                "ws_id": int(ws_id),
            }
            lan = getattr(t, "_lan", None)
            send_prompt = getattr(lan, "send_echo_tether_prompt", None) if lan is not None else None
            try:
                if callable(send_prompt):
                    send_prompt(int(ws_id), request_id)
                else:
                    raise RuntimeError("missing send_echo_tether_prompt")
            except Exception:
                loop = getattr(lan, "_loop", None) if lan is not None else None
                send_async = getattr(lan, "_send_async", None) if lan is not None else None
                if loop and callable(send_async):
                    try:
                        asyncio.run_coroutine_threadsafe(
                            send_async(
                                int(ws_id),
                                {
                                    "type": "echo_tether_prompt",
                                    "request_id": request_id,
                                    "text": "Warning. Moving here will destroy your echo. Proceed?",
                                },
                            ),
                            loop,
                        )
                    except Exception:
                        pass
            return build_dispatch_result(
                "move",
                True,
                request=request_contract,
                pending_confirmation=True,
                request_id=request_id,
                to={"col": int(col), "row": int(row)},
            )

        ok, reason, cost = t._lan_try_move(cid_int, int(col), int(row))
        if not ok:
            msg["_move_applied"] = False
            msg["_move_reject_reason"] = str(reason or "move_rejected")
            cols_after, rows_after, _obs_after, _rough_after, positions_after = t._lan_live_map_data()
            after_pos = positions_after.get(cid_int)
            self._move_log(
                ws_id,
                "lan_move_result",
                ok=False,
                reason=reason,
                cost=cost,
                before_pos=before_pos,
                after_pos=after_pos,
                grid={"cols": cols_after, "rows": rows_after},
            )
            self._toast(ws_id, reason or "Can’t move there.")
            return build_dispatch_result(
                "move",
                False,
                reason=str(reason or "move_rejected"),
                request=request_contract,
                cost=int(cost or 0),
                to={"col": int(col), "row": int(row)},
                before_pos=before_pos,
                after_pos=after_pos,
            )

        msg["_move_applied"] = True
        msg["_move_reject_reason"] = None
        cols_after, rows_after, _obs_after, _rough_after, positions_after = t._lan_live_map_data()
        after_pos = positions_after.get(cid_int)
        map_token_pos_after = None
        if map_ready:
            try:
                tok = (getattr(mw, "unit_tokens", {}) or {}).get(cid_int)
                if isinstance(tok, dict):
                    map_token_pos_after = {"col": tok.get("col"), "row": tok.get("row")}
            except Exception:
                map_token_pos_after = None
        self._move_log(
            ws_id,
            "lan_move_result",
            ok=True,
            reason=None,
            cost=cost,
            before_pos=before_pos,
            after_pos=after_pos,
            map_token_pos_before=map_token_pos,
            map_token_pos_after=map_token_pos_after,
            grid={"cols": cols_after, "rows": rows_after},
        )

        if breaks_echo_tether:
            try:
                t._enforce_johns_echo_tether(int(cid_int))
            except Exception:
                pass
        expire_offers = getattr(t, "_expire_reaction_offers", None)
        if callable(expire_offers):
            try:
                expire_offers()
            except Exception:
                pass

        mover = combatants.get(cid_int)
        lan_is_friendly_unit = getattr(t, "_lan_is_friendly_unit", None)
        feet_per_square = getattr(t, "_lan_feet_per_square", None)
        build_oa_choices = getattr(t, "_build_oa_reaction_choices", None)
        find_ws_for_cid = getattr(t, "_find_ws_for_cid", None)
        if (
            mover is not None
            and isinstance(before_pos, tuple)
            and isinstance(after_pos, tuple)
            and callable(lan_is_friendly_unit)
            and callable(feet_per_square)
            and callable(build_oa_choices)
            and callable(find_ws_for_cid)
        ):
            fps = feet_per_square()
            mover_friendly = bool(lan_is_friendly_unit(int(cid_int)))
            for other_cid, other in list(combatants.items()):
                try:
                    ocid = int(other_cid)
                except Exception:
                    continue
                if ocid == int(cid_int):
                    continue
                if bool(lan_is_friendly_unit(int(ocid))) == mover_friendly:
                    continue
                if int(getattr(other, "reaction_remaining", 0) or 0) <= 0:
                    continue
                reactor_pos = positions_after.get(int(ocid))
                if not (isinstance(reactor_pos, tuple) and len(reactor_pos) == 2):
                    continue
                start_dist = max(
                    abs(int(before_pos[0]) - int(reactor_pos[0])),
                    abs(int(before_pos[1]) - int(reactor_pos[1])),
                )
                end_dist = max(
                    abs(int(after_pos[0]) - int(reactor_pos[0])),
                    abs(int(after_pos[1]) - int(reactor_pos[1])),
                )
                start_ft = float(start_dist) * fps
                end_ft = float(end_dist) * fps
                if not (start_ft <= fps + 1e-6 and end_ft > fps + 1e-6):
                    continue
                if bool(getattr(mover, "disengage_active", False)):
                    continue
                choices = build_oa_choices(other, include_war_caster=True)
                if not choices:
                    continue
                ws_targets = find_ws_for_cid(int(ocid))
                self.create_reaction_offer(int(ocid), "leave_reach", int(cid_int), int(cid_int), choices, ws_targets)

        self._toast(ws_id, f"Moved ({cost} ft).")
        return build_dispatch_result(
            "move",
            True,
            request=request_contract,
            cost=int(cost or 0),
            to={"col": int(col), "row": int(row)},
            before_pos=before_pos,
            after_pos=after_pos,
        )

    def cycle_movement_mode(
        self,
        msg: Dict[str, Any],
        *,
        cid: Optional[int],
        ws_id: Any,
        is_admin: bool,
    ) -> Dict[str, Any]:
        t = self._tracker
        request_contract = build_cycle_movement_mode_contract(
            msg,
            cid=cid,
            ws_id=ws_id,
            is_admin=is_admin,
        )
        if cid is None:
            return build_dispatch_result("cycle_movement_mode", False, reason="missing_cid", request=request_contract)
        try:
            cid_int = int(cid)
        except Exception:
            return build_dispatch_result("cycle_movement_mode", False, reason="invalid_cid", request=request_contract)
        combatants = getattr(t, "combatants", {}) or {}
        c = combatants.get(cid_int)
        if c is None:
            return build_dispatch_result("cycle_movement_mode", False, reason="combatant_missing", request=request_contract)

        modes = ["normal"]
        if int(getattr(c, "swim_speed", 0) or 0) > 0:
            modes.append("swim")
        if int(getattr(c, "fly_speed", 0) or 0) > 0:
            modes.append("fly")
        if int(getattr(c, "burrow_speed", 0) or 0) > 0:
            modes.append("burrow")
        current_mode = t._normalize_movement_mode(getattr(c, "movement_mode", "normal"))
        try:
            idx = modes.index(current_mode)
        except ValueError:
            idx = 0
        next_mode = modes[(idx + 1) % len(modes)]
        t._set_movement_mode(int(cid_int), next_mode)
        rebuild = getattr(t, "_rebuild_table", None)
        if callable(rebuild):
            try:
                rebuild(scroll_to_current=True)
            except Exception:
                pass
        label = next_mode.title()
        movement_mode_label = getattr(t, "_movement_mode_label", None)
        if callable(movement_mode_label):
            try:
                label = str(movement_mode_label(next_mode) or label)
            except Exception:
                label = next_mode.title()
        self._toast(ws_id, f"Movement mode: {label}.")
        return build_dispatch_result(
            "cycle_movement_mode",
            True,
            request=request_contract,
            movement_mode=next_mode,
        )

    def perform_action(
        self,
        msg: Dict[str, Any],
        *,
        cid: Optional[int],
        ws_id: Any,
        is_admin: bool,
    ) -> Dict[str, Any]:
        t = self._tracker
        request_contract = build_perform_action_contract(
            msg,
            cid=cid,
            ws_id=ws_id,
            is_admin=is_admin,
        )
        if cid is None:
            return build_dispatch_result("perform_action", False, reason="missing_cid", request=request_contract)
        try:
            cid_int = int(cid)
        except Exception:
            return build_dispatch_result("perform_action", False, reason="invalid_cid", request=request_contract)
        combatants = getattr(t, "combatants", {}) or {}
        c = combatants.get(cid_int)
        if c is None:
            return build_dispatch_result("perform_action", False, reason="combatant_missing", request=request_contract)

        spend_raw = str(msg.get("spend") or "action").lower()
        if spend_raw in ("bonus", "bonus_action"):
            spend = "bonus"
        elif spend_raw == "reaction":
            spend = "reaction"
        else:
            spend = "action"
        action_name = str(msg.get("action") or msg.get("name") or "").strip()
        action_entry = t._find_action_entry(c, spend, action_name)
        if not action_entry:
            self._toast(ws_id, "That action ain't in yer sheet, matey.")
            return build_dispatch_result(
                "perform_action",
                False,
                reason="action_missing",
                request=request_contract,
                action_name=action_name,
                spend=spend,
            )
        if t._is_create_undead_uncommanded_this_turn(c) and t._action_name_key(action_name) != "dodge":
            self._toast(ws_id, "Uncommanded created undead can only Dodge, matey.")
            return build_dispatch_result(
                "perform_action",
                False,
                reason="created_undead_uncommanded",
                request=request_contract,
                action_name=action_name,
                spend=spend,
            )
        if t._mount_action_is_restricted(c, action_name):
            self._toast(ws_id, "Mounted steed can only Dash, Disengage, or Dodge while rider is active.")
            return build_dispatch_result(
                "perform_action",
                False,
                reason="mount_restricted",
                request=request_contract,
                action_name=action_name,
                spend=spend,
            )

        action_key = t._action_name_key(action_name)
        if action_key in {"collect yourself (otto's dance)", "collect yourself"} and not t._target_has_otto_dance_active(c):
            self._toast(ws_id, "Ye ain't under Otto's dance right now.")
            return build_dispatch_result(
                "perform_action",
                False,
                reason="otto_not_active",
                request=request_contract,
                action_name=action_name,
                spend=spend,
            )

        action_uses = action_entry.get("uses") if isinstance(action_entry.get("uses"), dict) else {}
        action_pool_id = str(action_uses.get("pool") or action_uses.get("id") or "").strip()
        try:
            action_pool_cost = int(action_uses.get("cost", 1))
        except Exception:
            action_pool_cost = 1
        action_pool_cost = max(1, action_pool_cost)
        player_name = self._resolve_pc_name(cid_int)
        if action_pool_id:
            ok_pool, pool_err = t._consume_resource_pool_for_cast(
                caster_name=player_name,
                pool_id=action_pool_id,
                cost=action_pool_cost,
            )
            if not ok_pool:
                self._toast(ws_id, pool_err)
                return build_dispatch_result(
                    "perform_action",
                    False,
                    reason="action_pool_unavailable",
                    request=request_contract,
                    action_name=action_name,
                    pool_id=action_pool_id,
                    pool_cost=action_pool_cost,
                )

        consume_one_of = action_entry.get("consume_one_of") if isinstance(action_entry.get("consume_one_of"), list) else []
        if consume_one_of:
            one_of_ok = False
            one_of_errors = []
            for choice in consume_one_of:
                if not isinstance(choice, dict):
                    continue
                choice_type = str(choice.get("type") or "").strip().lower()
                if choice_type == "spell_slot":
                    min_level = self._parse_int(choice.get("min_level"), 1) or 1
                    ok_slot, slot_err, _spent_slot = t._consume_spell_slot_for_cast(player_name, min_level, min_level)
                    if ok_slot:
                        one_of_ok = True
                        break
                    one_of_errors.append(slot_err)
                elif choice_type == "pool":
                    choice_pool = str(choice.get("pool") or "").strip()
                    choice_cost = self._parse_int(choice.get("cost"), 1) or 1
                    ok_pool, pool_err = t._consume_resource_pool_for_cast(player_name, choice_pool, choice_cost)
                    if ok_pool:
                        one_of_ok = True
                        break
                    one_of_errors.append(pool_err)
            if not one_of_ok:
                self._toast(
                    ws_id,
                    next((entry for entry in one_of_errors if entry), "No valid resource option available, matey."),
                )
                return build_dispatch_result(
                    "perform_action",
                    False,
                    reason="resource_choice_unavailable",
                    request=request_contract,
                    action_name=action_name,
                    spend=spend,
                )

        grant_extra_action = action_key == "action surge"
        if grant_extra_action:
            c.action_remaining = int(getattr(c, "action_remaining", 0) or 0) + 1
            c.action_total = int(getattr(c, "action_total", 1) or 1) + 1
            spend_label = "free action"
        elif spend == "bonus":
            if not t._use_bonus_action(c):
                self._toast(ws_id, "No bonus actions left, matey.")
                return build_dispatch_result(
                    "perform_action",
                    False,
                    reason="no_bonus_action",
                    request=request_contract,
                    action_name=action_name,
                    spend=spend,
                )
            spend_label = "bonus action"
        elif spend == "reaction":
            if not t._use_reaction(c):
                self._toast(ws_id, "No reactions left, matey.")
                return build_dispatch_result(
                    "perform_action",
                    False,
                    reason="no_reaction",
                    request=request_contract,
                    action_name=action_name,
                    spend=spend,
                )
            spend_label = "reaction"
        else:
            if not t._use_action(c):
                self._toast(ws_id, "No actions left, matey.")
                return build_dispatch_result(
                    "perform_action",
                    False,
                    reason="no_action",
                    request=request_contract,
                    action_name=action_name,
                    spend=spend,
                )
            spend_label = "action"

        if action_key == "dash":
            try:
                base_speed = int(t._mode_speed(c))
            except Exception:
                base_speed = int(getattr(c, "speed", 30) or 30)
            try:
                total_before = int(getattr(c, "move_total", 0) or 0)
                remaining_before = int(getattr(c, "move_remaining", 0) or 0)
                setattr(c, "move_total", total_before + base_speed)
                setattr(c, "move_remaining", remaining_before + base_speed)
                t._log(
                    f"{c.name} dashed (move {remaining_before}/{total_before} -> {c.move_remaining}/{c.move_total})",
                    cid=cid_int,
                )
                self._toast(ws_id, f"Dashed ({spend_label}).")
                t._rebuild_table(scroll_to_current=True)
            except Exception as exc:
                return build_dispatch_result(
                    "perform_action",
                    False,
                    reason="dash_effect_failed",
                    error=str(exc),
                    request=request_contract,
                    action_name=action_name,
                    spend=spend,
                )
        elif grant_extra_action:
            t._log(
                f"{c.name} used {action_name} ({spend_label}) and gained 1 extra action",
                cid=cid_int,
            )
            self._toast(ws_id, "Action Surge used: +1 action.")
            t._rebuild_table(scroll_to_current=True)
        else:
            if action_key == "rage":
                setattr(c, "rage_active", True)
                stacks = getattr(c, "condition_stacks", None)
                if not isinstance(stacks, list):
                    stacks = []
                    setattr(c, "condition_stacks", stacks)
                if not t._has_condition(c, "rage"):
                    next_sid = int(t.__dict__.get("_next_stack_id", 1) or 1)
                    setattr(t, "_next_stack_id", int(next_sid) + 1)
                    tracker_module = self._tracker_module()
                    condition_stack_cls = getattr(getattr(tracker_module, "base", None), "ConditionStack", None)
                    if callable(condition_stack_cls):
                        stacks.append(condition_stack_cls(sid=int(next_sid), ctype="rage", remaining_turns=None))
                if not any(
                    isinstance(hook, dict)
                    and str(hook.get("type") or "").strip().lower() == "rage_upkeep"
                    for hook in list(getattr(c, "_feature_turn_hooks", []) or [])
                ):
                    t._register_combatant_turn_hook(
                        c,
                        {"type": "rage_upkeep", "when": "end_turn", "source": "rage"},
                    )
            action_effect = str(action_entry.get("effect") or "").strip().lower()
            if action_key in {"collect yourself (otto's dance)", "collect yourself"}:
                passed, summary = t._attempt_otto_collect_self_action(c)
                t._log(summary, cid=cid_int)
                self._toast(ws_id, summary)
                t._rebuild_table(scroll_to_current=True)
                return build_dispatch_result(
                    "perform_action",
                    True,
                    request=request_contract,
                    action_name=action_name,
                    spend=spend,
                    action_key=action_key,
                    passed=bool(passed),
                )
            if action_key == "command created undead":
                commanded_count = int(t._command_created_undead_for_caster(int(cid_int)))
                t._log(
                    f"{c.name} commands created undead ({commanded_count} unit{'s' if commanded_count != 1 else ''}).",
                    cid=cid_int,
                )
                self._toast(ws_id, f"Commanded {commanded_count} created undead.")
                t._rebuild_table(scroll_to_current=True)
                return build_dispatch_result(
                    "perform_action",
                    True,
                    request=request_contract,
                    action_name=action_name,
                    spend=spend,
                    action_key=action_key,
                    commanded_count=commanded_count,
                )
            if action_key == "disengage":
                setattr(c, "disengage_active", True)
                feet_per_square = getattr(t, "_lan_feet_per_square", None)
                unit_has_sentinel_feat = getattr(t, "_unit_has_sentinel_feat", None)
                build_oa_choices = getattr(t, "_build_oa_reaction_choices", None)
                find_ws_for_cid = getattr(t, "_find_ws_for_cid", None)
                lan_is_friendly_unit = getattr(t, "_lan_is_friendly_unit", None)
                if (
                    callable(feet_per_square)
                    and callable(unit_has_sentinel_feat)
                    and callable(build_oa_choices)
                    and callable(find_ws_for_cid)
                    and callable(lan_is_friendly_unit)
                ):
                    fps = feet_per_square()
                    mover_pos = dict(t.__dict__.get("_lan_positions", {}) or {}).get(int(cid_int))
                    if isinstance(mover_pos, tuple) and len(mover_pos) == 2:
                        for other_cid, other in list(combatants.items()):
                            try:
                                ocid = int(other_cid)
                            except Exception:
                                continue
                            if ocid == int(cid_int):
                                continue
                            if bool(lan_is_friendly_unit(ocid)) == bool(lan_is_friendly_unit(int(cid_int))):
                                continue
                            if not unit_has_sentinel_feat(other):
                                continue
                            if int(getattr(other, "reaction_remaining", 0) or 0) <= 0:
                                continue
                            opos = dict(t.__dict__.get("_lan_positions", {}) or {}).get(ocid)
                            if not (isinstance(opos, tuple) and len(opos) == 2):
                                continue
                            dist_ft = max(
                                abs(int(mover_pos[0]) - int(opos[0])),
                                abs(int(mover_pos[1]) - int(opos[1])),
                            ) * fps
                            if dist_ft - 8.0 > 1e-6:
                                continue
                            choices = build_oa_choices(other, include_war_caster=False)
                            if not choices:
                                continue
                            ws_targets = find_ws_for_cid(ocid)
                            self.create_reaction_offer(ocid, "sentinel_disengage", int(cid_int), int(cid_int), choices, ws_targets)
            if action_effect in ("recover_spell_slots", "recover_spell_slot") or action_key in (
                "arcane recovery",
                "natural recovery (recover spell slots)",
            ):
                recover_cfg: Dict[str, Any] = {}
                if action_effect in ("recover_spell_slots", "recover_spell_slot"):
                    recover_cfg = dict(action_entry)
                if not recover_cfg:
                    profile = t._profile_for_player_name(player_name)
                    feature_name_key = t._action_name_key(action_name)
                    if isinstance(profile, dict):
                        for feature in profile.get("features") if isinstance(profile.get("features"), list) else []:
                            if not isinstance(feature, dict):
                                continue
                            if t._action_name_key(feature.get("name")) != feature_name_key:
                                continue
                            automation = feature.get("automation") if isinstance(feature.get("automation"), dict) else {}
                            if isinstance(automation.get("recover_spell_slots"), dict):
                                recover_cfg = dict(automation.get("recover_spell_slots") or {})
                                break
                if recover_cfg:
                    profile = t._profile_for_player_name(player_name)
                    if isinstance(profile, dict):
                        ok_recover, recover_err, recovered_levels = t._recover_spell_slots(player_name, profile, recover_cfg)
                        if ok_recover:
                            recovered_text = ", ".join(f"L{lvl}" for lvl in recovered_levels)
                            t._log(f"{c.name} recovers spell slots ({recovered_text}).", cid=cid_int)
                            self._toast(ws_id, f"Recovered spell slots: {recovered_text}.")
                        else:
                            self._toast(ws_id, recover_err or "Could not recover spell slots, matey.")
            t._log(f"{c.name} used {action_name} ({spend_label})", cid=cid_int)
            self._toast(ws_id, f"Used {action_name}.")
            t._rebuild_table(scroll_to_current=True)

        return build_dispatch_result(
            "perform_action",
            True,
            request=request_contract,
            action_name=action_name,
            action_key=action_key,
            spend=spend,
        )

    # ------------------------------------------------------------------
    # wild-shape commands
    # ------------------------------------------------------------------

    def dispatch_wild_shape_command(
        self,
        msg: Dict[str, Any],
        *,
        cid: Optional[int],
        ws_id: Any,
        is_admin: bool,
    ) -> Dict[str, Any]:
        command_type = str(msg.get("type") if isinstance(msg, dict) else "").strip().lower()
        handler_name = self._WILD_SHAPE_COMMAND_HANDLERS.get(command_type)
        if not handler_name:
            return build_dispatch_result(
                "wild_shape_command",
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

    def wild_shape_apply(
        self,
        msg: Dict[str, Any],
        *,
        cid: Optional[int],
        ws_id: Any,
        is_admin: bool,
    ) -> Dict[str, Any]:
        t = self._tracker
        request_contract = build_wild_shape_apply_contract(
            msg,
            cid=cid,
            ws_id=ws_id,
            is_admin=is_admin,
        )
        if cid is None:
            return build_dispatch_result("wild_shape_apply", False, reason="missing_cid", request=request_contract)
        try:
            cid_int = int(cid)
        except Exception:
            return build_dispatch_result("wild_shape_apply", False, reason="invalid_cid", request=request_contract)
        beast_id = str(msg.get("beast_id") or "").strip()
        if not beast_id:
            self._toast(ws_id, "Pick a beast form first, matey.")
            return build_dispatch_result("wild_shape_apply", False, reason="missing_beast_id", request=request_contract)
        combatants = getattr(t, "combatants", {}) or {}
        c = combatants.get(cid_int)
        if c is None:
            return build_dispatch_result("wild_shape_apply", False, reason="combatant_missing", request=request_contract)
        require_bonus_action = bool(getattr(t, "in_combat", False))
        if require_bonus_action and int(getattr(c, "bonus_action_remaining", 0) or 0) <= 0:
            self._toast(ws_id, "No bonus actions left, matey.")
            return build_dispatch_result(
                "wild_shape_apply",
                False,
                reason="no_bonus_action",
                request=request_contract,
                beast_id=beast_id,
            )
        ok, err = t._apply_wild_shape(int(cid_int), beast_id)
        if not ok:
            self._toast(ws_id, err or "Could not Wild Shape, matey.")
            return build_dispatch_result(
                "wild_shape_apply",
                False,
                reason="apply_failed",
                error=str(err or ""),
                request=request_contract,
                beast_id=beast_id,
            )
        if require_bonus_action and not t._use_bonus_action(c):
            self._toast(ws_id, "Could not spend bonus action for Wild Shape, matey.")
            return build_dispatch_result(
                "wild_shape_apply",
                False,
                reason="bonus_action_spend_failed",
                request=request_contract,
                beast_id=beast_id,
            )
        if require_bonus_action:
            setattr(c, "bonus_action_remaining", 0)
        self._toast(ws_id, "Wild Shape activated.")
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
            "wild_shape_apply",
            True,
            request=request_contract,
            beast_id=beast_id,
            require_bonus_action=require_bonus_action,
        )

    def wild_shape_pool_set_current(
        self,
        msg: Dict[str, Any],
        *,
        cid: Optional[int],
        ws_id: Any,
        is_admin: bool,
    ) -> Dict[str, Any]:
        t = self._tracker
        request_contract = build_wild_shape_pool_set_current_contract(
            msg,
            cid=cid,
            ws_id=ws_id,
            is_admin=is_admin,
        )
        if cid is None:
            return build_dispatch_result(
                "wild_shape_pool_set_current",
                False,
                reason="missing_cid",
                request=request_contract,
            )
        try:
            cid_int = int(cid)
        except Exception:
            return build_dispatch_result(
                "wild_shape_pool_set_current",
                False,
                reason="invalid_cid",
                request=request_contract,
            )
        try:
            desired_current = int(msg.get("current"))
        except Exception:
            self._toast(ws_id, "Pick a valid Wild Shape uses value, matey.")
            return build_dispatch_result(
                "wild_shape_pool_set_current",
                False,
                reason="invalid_current",
                request=request_contract,
            )
        player_name = t._pc_name_for(int(cid_int))
        ok_pool, pool_err, new_cur = t._set_wild_shape_pool_current(player_name, desired_current)
        if not ok_pool:
            self._toast(ws_id, pool_err or "Could not update Wild Shape uses, matey.")
            return build_dispatch_result(
                "wild_shape_pool_set_current",
                False,
                reason="pool_update_failed",
                error=str(pool_err or ""),
                request=request_contract,
                requested_current=desired_current,
            )
        c = (getattr(t, "combatants", {}) or {}).get(cid_int)
        if c is not None:
            setattr(c, "wild_shape_pool_current", int(new_cur if new_cur is not None else 0))
        self._toast(ws_id, "Wild Shape uses updated.")
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
            "wild_shape_pool_set_current",
            True,
            request=request_contract,
            requested_current=desired_current,
            current=int(new_cur if new_cur is not None else 0),
        )

    def wild_shape_revert(
        self,
        msg: Dict[str, Any],
        *,
        cid: Optional[int],
        ws_id: Any,
        is_admin: bool,
    ) -> Dict[str, Any]:
        t = self._tracker
        request_contract = build_wild_shape_revert_contract(
            msg,
            cid=cid,
            ws_id=ws_id,
            is_admin=is_admin,
        )
        if cid is None:
            return build_dispatch_result("wild_shape_revert", False, reason="missing_cid", request=request_contract)
        try:
            cid_int = int(cid)
        except Exception:
            return build_dispatch_result("wild_shape_revert", False, reason="invalid_cid", request=request_contract)
        combatants = getattr(t, "combatants", {}) or {}
        c = combatants.get(cid_int)
        if c is None:
            return build_dispatch_result("wild_shape_revert", False, reason="combatant_missing", request=request_contract)
        require_bonus_action = bool(getattr(t, "in_combat", False))
        if require_bonus_action and int(getattr(c, "bonus_action_remaining", 0) or 0) <= 0:
            self._toast(ws_id, "No bonus actions left, matey.")
            return build_dispatch_result(
                "wild_shape_revert",
                False,
                reason="no_bonus_action",
                request=request_contract,
            )
        ok, err = t._revert_wild_shape(int(cid_int))
        if not ok:
            self._toast(ws_id, err or "Could not revert Wild Shape, matey.")
            return build_dispatch_result(
                "wild_shape_revert",
                False,
                reason="revert_failed",
                error=str(err or ""),
                request=request_contract,
            )
        if require_bonus_action:
            setattr(c, "bonus_action_remaining", max(0, int(getattr(c, "bonus_action_remaining", 0) or 0) - 1))
            log = getattr(t, "_log", None)
            if callable(log):
                try:
                    log(f"{getattr(c, 'name', 'Player')} used a bonus action to revert Wild Shape.", cid=cid_int)
                except Exception:
                    pass
        self._toast(ws_id, "Reverted Wild Shape.")
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
            "wild_shape_revert",
            True,
            request=request_contract,
            require_bonus_action=require_bonus_action,
        )

    def wild_shape_regain_use(
        self,
        msg: Dict[str, Any],
        *,
        cid: Optional[int],
        ws_id: Any,
        is_admin: bool,
    ) -> Dict[str, Any]:
        t = self._tracker
        request_contract = build_wild_shape_regain_use_contract(
            msg,
            cid=cid,
            ws_id=ws_id,
            is_admin=is_admin,
        )
        if cid is None:
            return build_dispatch_result("wild_shape_regain_use", False, reason="missing_cid", request=request_contract)
        try:
            cid_int = int(cid)
        except Exception:
            return build_dispatch_result("wild_shape_regain_use", False, reason="invalid_cid", request=request_contract)
        combatants = getattr(t, "combatants", {}) or {}
        c = combatants.get(cid_int)
        if c is None:
            return build_dispatch_result("wild_shape_regain_use", False, reason="combatant_missing", request=request_contract)
        if bool(getattr(c, "wild_resurgence_turn_used", False)):
            self._toast(ws_id, "Wild Resurgence already used this turn, matey.")
            return build_dispatch_result(
                "wild_shape_regain_use",
                False,
                reason="wild_resurgence_already_used",
                request=request_contract,
            )
        player_name = t._pc_name_for(int(cid_int))
        ok_slot, err_slot, spent_level = t._consume_spell_slot_for_wild_shape_regain(player_name)
        if not ok_slot:
            self._toast(ws_id, err_slot)
            return build_dispatch_result(
                "wild_shape_regain_use",
                False,
                reason="spell_slot_unavailable",
                error=str(err_slot or ""),
                request=request_contract,
            )
        profile = t._profile_for_player_name(player_name)
        pools = t._normalize_player_resource_pools(profile if isinstance(profile, dict) else {})
        wild = next((p for p in pools if str(p.get("id") or "").lower() == "wild_shape"), None)
        if not isinstance(wild, dict):
            self._toast(ws_id, "No Wild Shape pool found, matey.")
            return build_dispatch_result(
                "wild_shape_regain_use",
                False,
                reason="wild_shape_pool_missing",
                request=request_contract,
            )
        ok_pool, pool_err, new_cur = t._set_wild_shape_pool_current(player_name, int(wild.get("current", 0) or 0) + 1)
        if not ok_pool:
            self._toast(ws_id, pool_err)
            return build_dispatch_result(
                "wild_shape_regain_use",
                False,
                reason="pool_update_failed",
                error=str(pool_err or ""),
                request=request_contract,
            )
        setattr(c, "wild_resurgence_turn_used", True)
        setattr(c, "wild_shape_pool_current", int(new_cur if new_cur is not None else getattr(c, "wild_shape_pool_current", 0) or 0))
        log = getattr(t, "_log", None)
        if callable(log):
            try:
                log(f"{getattr(c, 'name', 'Player')} recovered one Wild Shape use via Wild Resurgence.", cid=cid_int)
            except Exception:
                pass
        self._toast(ws_id, f"Recovered one Wild Shape use (spent level {int(spent_level or 1)} slot).")
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
            "wild_shape_regain_use",
            True,
            request=request_contract,
            spent_level=int(spent_level or 1),
            current=int(new_cur if new_cur is not None else 0),
        )

    def wild_shape_regain_spell(
        self,
        msg: Dict[str, Any],
        *,
        cid: Optional[int],
        ws_id: Any,
        is_admin: bool,
    ) -> Dict[str, Any]:
        t = self._tracker
        request_contract = build_wild_shape_regain_spell_contract(
            msg,
            cid=cid,
            ws_id=ws_id,
            is_admin=is_admin,
        )
        if cid is None:
            return build_dispatch_result("wild_shape_regain_spell", False, reason="missing_cid", request=request_contract)
        try:
            cid_int = int(cid)
        except Exception:
            return build_dispatch_result("wild_shape_regain_spell", False, reason="invalid_cid", request=request_contract)
        combatants = getattr(t, "combatants", {}) or {}
        c = combatants.get(cid_int)
        if c is None:
            return build_dispatch_result("wild_shape_regain_spell", False, reason="combatant_missing", request=request_contract)
        if bool(getattr(c, "wild_resurgence_slot_used", False)):
            self._toast(ws_id, "Wild Shape spell-slot exchange already used this long rest, matey.")
            return build_dispatch_result(
                "wild_shape_regain_spell",
                False,
                reason="wild_resurgence_slot_already_used",
                request=request_contract,
            )
        player_name = t._pc_name_for(int(cid_int))
        profile = t._profile_for_player_name(player_name)
        pools = t._normalize_player_resource_pools(profile if isinstance(profile, dict) else {})
        wild = next((p for p in pools if str(p.get("id") or "").lower() == "wild_shape"), None)
        if not isinstance(wild, dict) or int(wild.get("current", 0) or 0) <= 0:
            self._toast(ws_id, "No Wild Shape uses to spend, matey.")
            return build_dispatch_result(
                "wild_shape_regain_spell",
                False,
                reason="no_wild_shape_uses",
                request=request_contract,
            )
        ok_spell, err_spell = t._regain_first_level_spell_slot(player_name)
        if not ok_spell:
            self._toast(ws_id, err_spell)
            return build_dispatch_result(
                "wild_shape_regain_spell",
                False,
                reason="spell_regain_failed",
                error=str(err_spell or ""),
                request=request_contract,
            )
        ok_pool, pool_err, new_cur = t._set_wild_shape_pool_current(player_name, int(wild.get("current", 0) or 0) - 1)
        if not ok_pool:
            self._toast(ws_id, pool_err)
            return build_dispatch_result(
                "wild_shape_regain_spell",
                False,
                reason="pool_update_failed",
                error=str(pool_err or ""),
                request=request_contract,
            )
        setattr(c, "wild_resurgence_slot_used", True)
        setattr(c, "wild_shape_pool_current", int(new_cur if new_cur is not None else getattr(c, "wild_shape_pool_current", 0) or 0))
        log = getattr(t, "_log", None)
        if callable(log):
            try:
                log(f"{getattr(c, 'name', 'Player')} recovered one level 1 spell slot via Wild Resurgence.", cid=cid_int)
            except Exception:
                pass
        self._toast(ws_id, "Recovered one level 1 spell slot.")
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
            "wild_shape_regain_spell",
            True,
            request=request_contract,
            current=int(new_cur if new_cur is not None else 0),
        )

    def wild_shape_set_known(
        self,
        msg: Dict[str, Any],
        *,
        cid: Optional[int],
        ws_id: Any,
        is_admin: bool,
    ) -> Dict[str, Any]:
        t = self._tracker
        request_contract = build_wild_shape_set_known_contract(
            msg,
            cid=cid,
            ws_id=ws_id,
            is_admin=is_admin,
        )
        if cid is None:
            return build_dispatch_result("wild_shape_set_known", False, reason="missing_cid", request=request_contract)
        try:
            cid_int = int(cid)
        except Exception:
            return build_dispatch_result("wild_shape_set_known", False, reason="invalid_cid", request=request_contract)
        player_name = t._pc_name_for(int(cid_int))
        profile = t._profile_for_player_name(player_name)
        if not isinstance(profile, dict):
            self._toast(ws_id, "No player profile found, matey.")
            return build_dispatch_result(
                "wild_shape_set_known",
                False,
                reason="profile_missing",
                request=request_contract,
            )
        druid_level = t._druid_level_from_profile(profile)
        if druid_level < 2:
            self._toast(ws_id, "Only druids can manage Wild Shapes, matey.")
            return build_dispatch_result(
                "wild_shape_set_known",
                False,
                reason="not_a_druid",
                request=request_contract,
            )
        known_limit = t._wild_shape_known_limit(druid_level)
        requested = msg.get("known")
        if not isinstance(requested, list):
            requested = []
        available_forms = [
            entry
            for entry in t._wild_shape_available_forms(profile, known_only=False, include_locked=True)
            if isinstance(entry, dict)
        ]
        allowed_ids = {
            t._wild_shape_identifier_key(entry.get("id"))
            for entry in available_forms
        }
        allowed_ids.discard("")
        alias_map = t._wild_shape_alias_lookup(available_forms)
        deduped: list[str] = []
        for raw in requested:
            beast_id = alias_map.get(t._wild_shape_identifier_key(raw))
            if not beast_id or beast_id in deduped:
                continue
            if beast_id not in allowed_ids:
                continue
            deduped.append(beast_id)
            if len(deduped) >= known_limit:
                break
        known_map = t.__dict__.get("_wild_shape_known_by_player")
        if not isinstance(known_map, dict):
            known_map = {}
            t._wild_shape_known_by_player = known_map
        known_map[player_name.strip().lower()] = deduped

        player_path = t._find_player_profile_path(player_name)
        if not isinstance(player_path, Path):
            c = (getattr(t, "combatants", {}) or {}).get(cid_int)
            if c is not None:
                player_path = t._find_player_profile_path(getattr(c, "name", ""))
        if not isinstance(player_path, Path):
            t._load_player_yaml_cache(force_refresh=True)
            player_path = t._find_player_profile_path(player_name)
        raw_payload = t._player_yaml_cache_by_path.get(player_path) if isinstance(player_path, Path) else None
        if not (isinstance(player_path, Path) and isinstance(raw_payload, dict)):
            self._toast(ws_id, "Could not locate yer player file for Wild Shape save, matey.")
            return build_dispatch_result(
                "wild_shape_set_known",
                False,
                reason="player_yaml_missing",
                request=request_contract,
            )
        updated_payload = dict(raw_payload)
        updated_payload["learned_wild_shapes"] = list(deduped)
        updated_payload["prepared_wild_shapes"] = list(deduped)
        t._store_character_yaml(player_path, updated_payload)
        t._load_player_yaml_cache(force_refresh=True)

        self._toast(ws_id, "Wild Shape forms updated.")
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
            "wild_shape_set_known",
            True,
            request=request_contract,
            known=list(deduped),
            known_limit=int(known_limit),
        )

    # ------------------------------------------------------------------
    # AoE manipulation commands (aoe_move / aoe_remove)
    # ------------------------------------------------------------------

    def dispatch_aoe_manipulation_command(
        self,
        msg: Dict[str, Any],
        *,
        cid: Optional[int],
        ws_id: Any,
        is_admin: bool,
        claimed: Optional[int] = None,
    ) -> Dict[str, Any]:
        command_type = str(msg.get("type") if isinstance(msg, dict) else "").strip().lower()
        handler_name = self._AOE_MANIPULATION_COMMAND_HANDLERS.get(command_type)
        if not handler_name:
            return build_dispatch_result(
                "aoe_manipulation_command",
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
            claimed=claimed,
        )

    def aoe_move(
        self,
        msg: Dict[str, Any],
        *,
        cid: Optional[int],
        ws_id: Any,
        is_admin: bool,
        claimed: Optional[int] = None,
    ) -> Dict[str, Any]:
        t = self._tracker
        request_contract = build_aoe_move_contract(
            msg,
            cid=cid,
            ws_id=ws_id,
            is_admin=is_admin,
        )
        handler = getattr(t, "_handle_aoe_move_request", None)
        if not callable(handler):
            return build_dispatch_result(
                "aoe_move",
                False,
                reason="handler_missing",
                request=request_contract,
            )
        try:
            handler(
                msg if isinstance(msg, dict) else {},
                cid=cid,
                ws_id=ws_id,
                is_admin=is_admin,
                claimed=claimed,
            )
        except Exception as exc:
            self._oplog(f"aoe_move handler raised: {exc}", level="warning")
            return build_dispatch_result(
                "aoe_move",
                False,
                reason="exception",
                error=str(exc),
                request=request_contract,
            )
        return build_dispatch_result(
            "aoe_move",
            True,
            request=request_contract,
        )

    def aoe_remove(
        self,
        msg: Dict[str, Any],
        *,
        cid: Optional[int],
        ws_id: Any,
        is_admin: bool,
        claimed: Optional[int] = None,
    ) -> Dict[str, Any]:
        t = self._tracker
        request_contract = build_aoe_remove_contract(
            msg,
            cid=cid,
            ws_id=ws_id,
            is_admin=is_admin,
        )
        handler = getattr(t, "_handle_aoe_remove_request", None)
        if not callable(handler):
            return build_dispatch_result(
                "aoe_remove",
                False,
                reason="handler_missing",
                request=request_contract,
            )
        try:
            handler(
                msg if isinstance(msg, dict) else {},
                cid=cid,
                ws_id=ws_id,
                is_admin=is_admin,
                claimed=claimed,
            )
        except Exception as exc:
            self._oplog(f"aoe_remove handler raised: {exc}", level="warning")
            return build_dispatch_result(
                "aoe_remove",
                False,
                reason="exception",
                error=str(exc),
                request=request_contract,
            )
        return build_dispatch_result(
            "aoe_remove",
            True,
            request=request_contract,
        )

    # ------------------------------------------------------------------
    # spell-launch commands (cast_spell / cast_aoe)
    # ------------------------------------------------------------------

    def dispatch_spell_launch_command(
        self,
        msg: Dict[str, Any],
        *,
        cid: Optional[int],
        ws_id: Any,
        is_admin: bool,
        claimed: Optional[int] = None,
    ) -> Dict[str, Any]:
        command_type = str(msg.get("type") if isinstance(msg, dict) else "").strip().lower()
        handler_name = self._SPELL_LAUNCH_COMMAND_HANDLERS.get(command_type)
        if not handler_name:
            return build_dispatch_result(
                "spell_launch_command",
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
            claimed=claimed,
        )

    def cast_spell(
        self,
        msg: Dict[str, Any],
        *,
        cid: Optional[int],
        ws_id: Any,
        is_admin: bool,
        claimed: Optional[int] = None,
    ) -> Dict[str, Any]:
        t = self._tracker
        request_contract = build_cast_spell_contract(
            msg,
            cid=cid,
            ws_id=ws_id,
            is_admin=is_admin,
        )
        handler = getattr(t, "_handle_cast_spell_request", None)
        if not callable(handler):
            return build_dispatch_result(
                "cast_spell",
                False,
                reason="handler_missing",
                request=request_contract,
            )
        try:
            handler(
                msg if isinstance(msg, dict) else {},
                cid=cid,
                ws_id=ws_id,
                is_admin=is_admin,
                claimed=claimed,
            )
        except Exception as exc:
            self._oplog(f"cast_spell handler raised: {exc}", level="warning")
            return build_dispatch_result(
                "cast_spell",
                False,
                reason="exception",
                error=str(exc),
                request=request_contract,
            )
        return build_dispatch_result(
            "cast_spell",
            True,
            request=request_contract,
        )

    def cast_aoe(
        self,
        msg: Dict[str, Any],
        *,
        cid: Optional[int],
        ws_id: Any,
        is_admin: bool,
        claimed: Optional[int] = None,
    ) -> Dict[str, Any]:
        t = self._tracker
        request_contract = build_cast_aoe_contract(
            msg,
            cid=cid,
            ws_id=ws_id,
            is_admin=is_admin,
        )
        handler = getattr(t, "_handle_cast_aoe_request", None)
        if not callable(handler):
            return build_dispatch_result(
                "cast_aoe",
                False,
                reason="handler_missing",
                request=request_contract,
            )
        try:
            handler(
                msg if isinstance(msg, dict) else {},
                cid=cid,
                ws_id=ws_id,
                is_admin=is_admin,
                claimed=claimed,
            )
        except Exception as exc:
            self._oplog(f"cast_aoe handler raised: {exc}", level="warning")
            return build_dispatch_result(
                "cast_aoe",
                False,
                reason="exception",
                error=str(exc),
                request=request_contract,
            )
        return build_dispatch_result(
            "cast_aoe",
            True,
            request=request_contract,
        )

    # ------------------------------------------------------------------
    # bard/glamour specialty commands
    # ------------------------------------------------------------------

    def dispatch_bard_glamour_specialty_command(
        self,
        msg: Dict[str, Any],
        *,
        cid: Optional[int],
        ws_id: Any,
        is_admin: bool,
    ) -> Dict[str, Any]:
        command_type = str(msg.get("type") if isinstance(msg, dict) else "").strip().lower()
        handler_name = self._BARD_GLAMOUR_SPECIALTY_COMMAND_HANDLERS.get(command_type)
        if not handler_name:
            return build_dispatch_result(
                "bard_glamour_specialty_command",
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

    def command_resolve(
        self,
        msg: Dict[str, Any],
        *,
        cid: Optional[int],
        ws_id: Any,
        is_admin: bool,
    ) -> Dict[str, Any]:
        t = self._tracker
        request_contract = build_command_resolve_contract(
            msg,
            cid=cid,
            ws_id=ws_id,
            is_admin=is_admin,
        )
        handler = getattr(t, "_handle_command_resolve_request", None)
        if not callable(handler):
            return build_dispatch_result(
                "command_resolve",
                False,
                reason="handler_missing",
                request=request_contract,
            )
        try:
            handler(msg if isinstance(msg, dict) else {}, cid=cid, ws_id=ws_id, is_admin=is_admin)
        except Exception as exc:
            self._oplog(f"command_resolve handler raised: {exc}", level="warning")
            return build_dispatch_result(
                "command_resolve",
                False,
                reason="exception",
                error=str(exc),
                request=request_contract,
            )
        return build_dispatch_result(
            "command_resolve",
            True,
            request=request_contract,
        )

    def bardic_inspiration_grant(
        self,
        msg: Dict[str, Any],
        *,
        cid: Optional[int],
        ws_id: Any,
        is_admin: bool,
    ) -> Dict[str, Any]:
        t = self._tracker
        request_contract = build_bardic_inspiration_grant_contract(
            msg,
            cid=cid,
            ws_id=ws_id,
            is_admin=is_admin,
        )
        handler = getattr(t, "_handle_bardic_inspiration_grant_request", None)
        if not callable(handler):
            return build_dispatch_result(
                "bardic_inspiration_grant",
                False,
                reason="handler_missing",
                request=request_contract,
            )
        try:
            handler(msg if isinstance(msg, dict) else {}, cid=cid, ws_id=ws_id, is_admin=is_admin)
        except Exception as exc:
            self._oplog(f"bardic_inspiration_grant handler raised: {exc}", level="warning")
            return build_dispatch_result(
                "bardic_inspiration_grant",
                False,
                reason="exception",
                error=str(exc),
                request=request_contract,
            )
        return build_dispatch_result(
            "bardic_inspiration_grant",
            True,
            request=request_contract,
        )

    def bardic_inspiration_use(
        self,
        msg: Dict[str, Any],
        *,
        cid: Optional[int],
        ws_id: Any,
        is_admin: bool,
    ) -> Dict[str, Any]:
        t = self._tracker
        request_contract = build_bardic_inspiration_use_contract(
            msg,
            cid=cid,
            ws_id=ws_id,
            is_admin=is_admin,
        )
        handler = getattr(t, "_handle_bardic_inspiration_use_request", None)
        if not callable(handler):
            return build_dispatch_result(
                "bardic_inspiration_use",
                False,
                reason="handler_missing",
                request=request_contract,
            )
        try:
            handler(msg if isinstance(msg, dict) else {}, cid=cid, ws_id=ws_id, is_admin=is_admin)
        except Exception as exc:
            self._oplog(f"bardic_inspiration_use handler raised: {exc}", level="warning")
            return build_dispatch_result(
                "bardic_inspiration_use",
                False,
                reason="exception",
                error=str(exc),
                request=request_contract,
            )
        return build_dispatch_result(
            "bardic_inspiration_use",
            True,
            request=request_contract,
        )

    def mantle_of_inspiration(
        self,
        msg: Dict[str, Any],
        *,
        cid: Optional[int],
        ws_id: Any,
        is_admin: bool,
    ) -> Dict[str, Any]:
        t = self._tracker
        request_contract = build_mantle_of_inspiration_contract(
            msg,
            cid=cid,
            ws_id=ws_id,
            is_admin=is_admin,
        )
        handler = getattr(t, "_handle_mantle_of_inspiration_request", None)
        if not callable(handler):
            return build_dispatch_result(
                "mantle_of_inspiration",
                False,
                reason="handler_missing",
                request=request_contract,
            )
        try:
            handler(msg if isinstance(msg, dict) else {}, cid=cid, ws_id=ws_id, is_admin=is_admin)
        except Exception as exc:
            self._oplog(f"mantle_of_inspiration handler raised: {exc}", level="warning")
            return build_dispatch_result(
                "mantle_of_inspiration",
                False,
                reason="exception",
                error=str(exc),
                request=request_contract,
            )
        return build_dispatch_result(
            "mantle_of_inspiration",
            True,
            request=request_contract,
        )

    def beguiling_magic_restore(
        self,
        msg: Dict[str, Any],
        *,
        cid: Optional[int],
        ws_id: Any,
        is_admin: bool,
    ) -> Dict[str, Any]:
        t = self._tracker
        request_contract = build_beguiling_magic_restore_contract(
            msg,
            cid=cid,
            ws_id=ws_id,
            is_admin=is_admin,
        )
        handler = getattr(t, "_handle_beguiling_magic_restore_request", None)
        if not callable(handler):
            return build_dispatch_result(
                "beguiling_magic_restore",
                False,
                reason="handler_missing",
                request=request_contract,
            )
        try:
            handler(msg if isinstance(msg, dict) else {}, cid=cid, ws_id=ws_id, is_admin=is_admin)
        except Exception as exc:
            self._oplog(f"beguiling_magic_restore handler raised: {exc}", level="warning")
            return build_dispatch_result(
                "beguiling_magic_restore",
                False,
                reason="exception",
                error=str(exc),
                request=request_contract,
            )
        return build_dispatch_result(
            "beguiling_magic_restore",
            True,
            request=request_contract,
        )

    def beguiling_magic_use(
        self,
        msg: Dict[str, Any],
        *,
        cid: Optional[int],
        ws_id: Any,
        is_admin: bool,
    ) -> Dict[str, Any]:
        t = self._tracker
        request_contract = build_beguiling_magic_use_contract(
            msg,
            cid=cid,
            ws_id=ws_id,
            is_admin=is_admin,
        )
        handler = getattr(t, "_handle_beguiling_magic_use_request", None)
        if not callable(handler):
            return build_dispatch_result(
                "beguiling_magic_use",
                False,
                reason="handler_missing",
                request=request_contract,
            )
        try:
            handler(msg if isinstance(msg, dict) else {}, cid=cid, ws_id=ws_id, is_admin=is_admin)
        except Exception as exc:
            self._oplog(f"beguiling_magic_use handler raised: {exc}", level="warning")
            return build_dispatch_result(
                "beguiling_magic_use",
                False,
                reason="exception",
                error=str(exc),
                request=request_contract,
            )
        return build_dispatch_result(
            "beguiling_magic_use",
            True,
            request=request_contract,
        )

    # ------------------------------------------------------------------
    # summon/echo specialty commands
    # ------------------------------------------------------------------

    def dispatch_summon_echo_specialty_command(
        self,
        msg: Dict[str, Any],
        *,
        cid: Optional[int],
        ws_id: Any,
        is_admin: bool,
        claimed: Optional[int] = None,
    ) -> Dict[str, Any]:
        command_type = str(msg.get("type") if isinstance(msg, dict) else "").strip().lower()
        handler_name = self._SUMMON_ECHO_SPECIALTY_COMMAND_HANDLERS.get(command_type)
        if not handler_name:
            return build_dispatch_result(
                "summon_echo_specialty_command",
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
            claimed=claimed,
        )

    def echo_summon(
        self,
        msg: Dict[str, Any],
        *,
        cid: Optional[int],
        ws_id: Any,
        is_admin: bool,
        claimed: Optional[int] = None,
    ) -> Dict[str, Any]:
        t = self._tracker
        request_contract = build_echo_summon_contract(
            msg,
            cid=cid,
            ws_id=ws_id,
            is_admin=is_admin,
        )
        handler = getattr(t, "_handle_echo_summon_request", None)
        if not callable(handler):
            return build_dispatch_result(
                "echo_summon",
                False,
                reason="handler_missing",
                request=request_contract,
            )
        try:
            handler(msg if isinstance(msg, dict) else {}, cid=cid, ws_id=ws_id, is_admin=is_admin)
        except Exception as exc:
            self._oplog(f"echo_summon handler raised: {exc}", level="warning")
            return build_dispatch_result(
                "echo_summon",
                False,
                reason="exception",
                error=str(exc),
                request=request_contract,
            )
        return build_dispatch_result("echo_summon", True, request=request_contract)

    def echo_swap(
        self,
        msg: Dict[str, Any],
        *,
        cid: Optional[int],
        ws_id: Any,
        is_admin: bool,
        claimed: Optional[int] = None,
    ) -> Dict[str, Any]:
        t = self._tracker
        request_contract = build_echo_swap_contract(
            msg,
            cid=cid,
            ws_id=ws_id,
            is_admin=is_admin,
        )
        handler = getattr(t, "_handle_echo_swap_request", None)
        if not callable(handler):
            return build_dispatch_result(
                "echo_swap",
                False,
                reason="handler_missing",
                request=request_contract,
            )
        try:
            handler(msg if isinstance(msg, dict) else {}, cid=cid, ws_id=ws_id, is_admin=is_admin)
        except Exception as exc:
            self._oplog(f"echo_swap handler raised: {exc}", level="warning")
            return build_dispatch_result(
                "echo_swap",
                False,
                reason="exception",
                error=str(exc),
                request=request_contract,
            )
        return build_dispatch_result("echo_swap", True, request=request_contract)

    def dismiss_summons(
        self,
        msg: Dict[str, Any],
        *,
        cid: Optional[int],
        ws_id: Any,
        is_admin: bool,
        claimed: Optional[int] = None,
    ) -> Dict[str, Any]:
        t = self._tracker
        request_contract = build_dismiss_summons_contract(
            msg,
            cid=cid,
            ws_id=ws_id,
            is_admin=is_admin,
        )
        handler = getattr(t, "_handle_dismiss_summons_request", None)
        if not callable(handler):
            return build_dispatch_result(
                "dismiss_summons",
                False,
                reason="handler_missing",
                request=request_contract,
            )
        try:
            handler(
                msg if isinstance(msg, dict) else {},
                cid=cid,
                ws_id=ws_id,
                is_admin=is_admin,
                claimed=claimed,
            )
        except Exception as exc:
            self._oplog(f"dismiss_summons handler raised: {exc}", level="warning")
            return build_dispatch_result(
                "dismiss_summons",
                False,
                reason="exception",
                error=str(exc),
                request=request_contract,
            )
        return build_dispatch_result("dismiss_summons", True, request=request_contract)

    def dismiss_persistent_summon(
        self,
        msg: Dict[str, Any],
        *,
        cid: Optional[int],
        ws_id: Any,
        is_admin: bool,
        claimed: Optional[int] = None,
    ) -> Dict[str, Any]:
        t = self._tracker
        request_contract = build_dismiss_persistent_summon_contract(
            msg,
            cid=cid,
            ws_id=ws_id,
            is_admin=is_admin,
        )
        handler = getattr(t, "_handle_dismiss_persistent_summon_request", None)
        if not callable(handler):
            return build_dispatch_result(
                "dismiss_persistent_summon",
                False,
                reason="handler_missing",
                request=request_contract,
            )
        try:
            handler(
                msg if isinstance(msg, dict) else {},
                cid=cid,
                ws_id=ws_id,
                is_admin=is_admin,
                claimed=claimed,
            )
        except Exception as exc:
            self._oplog(f"dismiss_persistent_summon handler raised: {exc}", level="warning")
            return build_dispatch_result(
                "dismiss_persistent_summon",
                False,
                reason="exception",
                error=str(exc),
                request=request_contract,
            )
        return build_dispatch_result("dismiss_persistent_summon", True, request=request_contract)

    def reappear_persistent_summon(
        self,
        msg: Dict[str, Any],
        *,
        cid: Optional[int],
        ws_id: Any,
        is_admin: bool,
        claimed: Optional[int] = None,
    ) -> Dict[str, Any]:
        t = self._tracker
        request_contract = build_reappear_persistent_summon_contract(
            msg,
            cid=cid,
            ws_id=ws_id,
            is_admin=is_admin,
        )
        handler = getattr(t, "_handle_reappear_persistent_summon_request", None)
        if not callable(handler):
            return build_dispatch_result(
                "reappear_persistent_summon",
                False,
                reason="handler_missing",
                request=request_contract,
            )
        try:
            handler(
                msg if isinstance(msg, dict) else {},
                cid=cid,
                ws_id=ws_id,
                is_admin=is_admin,
                claimed=claimed,
            )
        except Exception as exc:
            self._oplog(f"reappear_persistent_summon handler raised: {exc}", level="warning")
            return build_dispatch_result(
                "reappear_persistent_summon",
                False,
                reason="exception",
                error=str(exc),
                request=request_contract,
            )
        return build_dispatch_result("reappear_persistent_summon", True, request=request_contract)

    def assign_pre_summon(
        self,
        msg: Dict[str, Any],
        *,
        cid: Optional[int],
        ws_id: Any,
        is_admin: bool,
        claimed: Optional[int] = None,
    ) -> Dict[str, Any]:
        t = self._tracker
        request_contract = build_assign_pre_summon_contract(
            msg,
            cid=cid,
            ws_id=ws_id,
            is_admin=is_admin,
        )
        handler = getattr(t, "_handle_assign_pre_summon_request", None)
        if not callable(handler):
            return build_dispatch_result(
                "assign_pre_summon",
                False,
                reason="handler_missing",
                request=request_contract,
            )
        try:
            handler(msg if isinstance(msg, dict) else {}, cid=cid, ws_id=ws_id, is_admin=is_admin)
        except Exception as exc:
            self._oplog(f"assign_pre_summon handler raised: {exc}", level="warning")
            return build_dispatch_result(
                "assign_pre_summon",
                False,
                reason="exception",
                error=str(exc),
                request=request_contract,
            )
        return build_dispatch_result("assign_pre_summon", True, request=request_contract)

    def echo_tether_response(
        self,
        msg: Dict[str, Any],
        *,
        cid: Optional[int],
        ws_id: Any,
        is_admin: bool,
        claimed: Optional[int] = None,
    ) -> Dict[str, Any]:
        t = self._tracker
        request_contract = build_echo_tether_response_contract(
            msg,
            cid=cid,
            ws_id=ws_id,
            is_admin=is_admin,
        )
        handler = getattr(t, "_handle_echo_tether_response_request", None)
        if not callable(handler):
            return build_dispatch_result(
                "echo_tether_response",
                False,
                reason="handler_missing",
                request=request_contract,
            )
        try:
            handler(msg if isinstance(msg, dict) else {}, cid=cid, ws_id=ws_id, is_admin=is_admin)
        except Exception as exc:
            self._oplog(f"echo_tether_response handler raised: {exc}", level="warning")
            return build_dispatch_result(
                "echo_tether_response",
                False,
                reason="exception",
                error=str(exc),
                request=request_contract,
            )
        return build_dispatch_result("echo_tether_response", True, request=request_contract)

    # ------------------------------------------------------------------
    # initiative/reaction specialty commands
    # ------------------------------------------------------------------

    def dispatch_initiative_reaction_specialty_command(
        self,
        msg: Dict[str, Any],
        *,
        cid: Optional[int],
        ws_id: Any,
        is_admin: bool,
    ) -> Dict[str, Any]:
        command_type = str(msg.get("type") if isinstance(msg, dict) else "").strip().lower()
        handler_name = self._INITIATIVE_REACTION_SPECIALTY_COMMAND_HANDLERS.get(command_type)
        if not handler_name:
            return build_dispatch_result(
                "initiative_reaction_specialty_command",
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

    def initiative_roll(
        self,
        msg: Dict[str, Any],
        *,
        cid: Optional[int],
        ws_id: Any,
        is_admin: bool,
    ) -> Dict[str, Any]:
        t = self._tracker
        request_contract = build_initiative_roll_contract(
            msg,
            cid=cid,
            ws_id=ws_id,
            is_admin=is_admin,
        )
        handler = getattr(t, "_handle_initiative_roll_request", None)
        if not callable(handler):
            return build_dispatch_result(
                "initiative_roll",
                False,
                reason="handler_missing",
                request=request_contract,
            )
        try:
            handler(msg if isinstance(msg, dict) else {}, cid=cid, ws_id=ws_id, is_admin=is_admin)
        except Exception as exc:
            self._oplog(f"initiative_roll handler raised: {exc}", level="warning")
            return build_dispatch_result(
                "initiative_roll",
                False,
                reason="exception",
                error=str(exc),
                request=request_contract,
            )
        return build_dispatch_result(
            "initiative_roll",
            True,
            request=request_contract,
        )

    def hellish_rebuke_resolve(
        self,
        msg: Dict[str, Any],
        *,
        cid: Optional[int],
        ws_id: Any,
        is_admin: bool,
    ) -> Dict[str, Any]:
        t = self._tracker
        request_contract = build_hellish_rebuke_resolve_contract(
            msg,
            cid=cid,
            ws_id=ws_id,
            is_admin=is_admin,
        )
        handler = getattr(t, "_handle_hellish_rebuke_resolve_request", None)
        if not callable(handler):
            return build_dispatch_result(
                "hellish_rebuke_resolve",
                False,
                reason="handler_missing",
                request=request_contract,
            )
        try:
            handler(msg if isinstance(msg, dict) else {}, cid=cid, ws_id=ws_id, is_admin=is_admin)
        except Exception as exc:
            self._oplog(f"hellish_rebuke_resolve handler raised: {exc}", level="warning")
            return build_dispatch_result(
                "hellish_rebuke_resolve",
                False,
                reason="exception",
                error=str(exc),
                request=request_contract,
            )
        return build_dispatch_result(
            "hellish_rebuke_resolve",
            True,
            request=request_contract,
        )

    # ------------------------------------------------------------------
    # utility/admin commands
    # ------------------------------------------------------------------

    def dispatch_utility_admin_command(
        self,
        msg: Dict[str, Any],
        *,
        cid: Optional[int],
        ws_id: Any,
        is_admin: bool,
        claimed: Optional[int] = None,
    ) -> Dict[str, Any]:
        command_type = str(msg.get("type") if isinstance(msg, dict) else "").strip().lower()
        handler_name = self._UTILITY_ADMIN_COMMAND_HANDLERS.get(command_type)
        if not handler_name:
            return build_dispatch_result(
                "utility_admin_command",
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
            claimed=claimed,
        )

    def set_color(
        self,
        msg: Dict[str, Any],
        *,
        cid: Optional[int],
        ws_id: Any,
        is_admin: bool,
        claimed: Optional[int] = None,
    ) -> Dict[str, Any]:
        t = self._tracker
        request_contract = build_set_color_contract(
            msg,
            cid=cid,
            ws_id=ws_id,
            is_admin=is_admin,
        )
        handler = getattr(t, "_handle_set_color_request", None)
        if not callable(handler):
            return build_dispatch_result(
                "set_color",
                False,
                reason="handler_missing",
                request=request_contract,
            )
        try:
            handler(msg if isinstance(msg, dict) else {}, cid=cid, ws_id=ws_id, is_admin=is_admin)
        except Exception as exc:
            self._oplog(f"set_color handler raised: {exc}", level="warning")
            return build_dispatch_result(
                "set_color",
                False,
                reason="exception",
                error=str(exc),
                request=request_contract,
            )
        return build_dispatch_result(
            "set_color",
            True,
            request=request_contract,
        )

    def set_facing(
        self,
        msg: Dict[str, Any],
        *,
        cid: Optional[int],
        ws_id: Any,
        is_admin: bool,
        claimed: Optional[int] = None,
    ) -> Dict[str, Any]:
        t = self._tracker
        request_contract = build_set_facing_contract(
            msg,
            cid=cid,
            ws_id=ws_id,
            is_admin=is_admin,
        )
        handler = getattr(t, "_handle_set_facing_request", None)
        if not callable(handler):
            return build_dispatch_result(
                "set_facing",
                False,
                reason="handler_missing",
                request=request_contract,
            )
        try:
            handler(
                msg if isinstance(msg, dict) else {},
                cid=cid,
                ws_id=ws_id,
                is_admin=is_admin,
                claimed=claimed,
            )
        except Exception as exc:
            self._oplog(f"set_facing handler raised: {exc}", level="warning")
            return build_dispatch_result(
                "set_facing",
                False,
                reason="exception",
                error=str(exc),
                request=request_contract,
            )
        return build_dispatch_result(
            "set_facing",
            True,
            request=request_contract,
        )

    def set_auras_enabled(
        self,
        msg: Dict[str, Any],
        *,
        cid: Optional[int],
        ws_id: Any,
        is_admin: bool,
        claimed: Optional[int] = None,
    ) -> Dict[str, Any]:
        t = self._tracker
        request_contract = build_set_auras_enabled_contract(
            msg,
            cid=cid,
            ws_id=ws_id,
            is_admin=is_admin,
        )
        handler = getattr(t, "_handle_set_auras_enabled_request", None)
        if not callable(handler):
            return build_dispatch_result(
                "set_auras_enabled",
                False,
                reason="handler_missing",
                request=request_contract,
            )
        try:
            handler(msg if isinstance(msg, dict) else {}, cid=cid, ws_id=ws_id, is_admin=is_admin)
        except Exception as exc:
            self._oplog(f"set_auras_enabled handler raised: {exc}", level="warning")
            return build_dispatch_result(
                "set_auras_enabled",
                False,
                reason="exception",
                error=str(exc),
                request=request_contract,
            )
        return build_dispatch_result(
            "set_auras_enabled",
            True,
            request=request_contract,
        )

    def reset_player_characters(
        self,
        msg: Dict[str, Any],
        *,
        cid: Optional[int],
        ws_id: Any,
        is_admin: bool,
        claimed: Optional[int] = None,
    ) -> Dict[str, Any]:
        t = self._tracker
        request_contract = build_reset_player_characters_contract(
            msg,
            cid=cid,
            ws_id=ws_id,
            is_admin=is_admin,
        )
        handler = getattr(t, "_handle_reset_player_characters_request", None)
        if not callable(handler):
            return build_dispatch_result(
                "reset_player_characters",
                False,
                reason="handler_missing",
                request=request_contract,
            )
        try:
            handler(msg if isinstance(msg, dict) else {}, cid=cid, ws_id=ws_id, is_admin=is_admin)
        except Exception as exc:
            self._oplog(f"reset_player_characters handler raised: {exc}", level="warning")
            return build_dispatch_result(
                "reset_player_characters",
                False,
                reason="exception",
                error=str(exc),
                request=request_contract,
            )
        return build_dispatch_result(
            "reset_player_characters",
            True,
            request=request_contract,
        )

    # ------------------------------------------------------------------
    # turn-local / mobility-lite commands
    # ------------------------------------------------------------------

    def dispatch_turn_local_command(
        self,
        msg: Dict[str, Any],
        *,
        cid: Optional[int],
        ws_id: Any,
        is_admin: bool,
    ) -> Dict[str, Any]:
        command_type = str(msg.get("type") if isinstance(msg, dict) else "").strip().lower()
        handler_name = self._TURN_LOCAL_COMMAND_HANDLERS.get(command_type)
        if not handler_name:
            return build_dispatch_result(
                "turn_local_command",
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

    def mount_request(
        self,
        msg: Dict[str, Any],
        *,
        cid: Optional[int],
        ws_id: Any,
        is_admin: bool,
    ) -> Dict[str, Any]:
        t = self._tracker
        request_contract = build_mount_request_contract(
            msg,
            cid=cid,
            ws_id=ws_id,
            is_admin=is_admin,
        )
        combatants = getattr(t, "combatants", {}) or {}
        rider_cid = self._coerce_optional_int(msg.get("rider_cid"))
        mount_cid = self._coerce_optional_int(msg.get("mount_cid"))
        if mount_cid is None:
            self._toast(ws_id, "Pick rider and mount first, matey.")
            return build_dispatch_result("mount_request", False, reason="missing_mount_cid", request=request_contract)
        if not is_admin:
            if cid is None:
                self._toast(ws_id, "Claim a character first, matey.")
                return build_dispatch_result("mount_request", False, reason="missing_cid", request=request_contract)
            if rider_cid is not None and int(rider_cid) != int(cid):
                self._toast(ws_id, "Ye can only mount with yer own token.")
                return build_dispatch_result("mount_request", False, reason="rider_claim_mismatch", request=request_contract)
            rider_cid = int(cid)
        if rider_cid is None:
            self._toast(ws_id, "Pick rider and mount first, matey.")
            return build_dispatch_result("mount_request", False, reason="missing_rider_cid", request=request_contract)

        rider = combatants.get(int(rider_cid))
        mount = combatants.get(int(mount_cid))
        if rider is None or mount is None:
            self._toast(ws_id, "Invalid mount target.")
            return build_dispatch_result("mount_request", False, reason="invalid_mount_target", request=request_contract)
        if int(rider_cid) == int(mount_cid):
            self._toast(ws_id, "Ye cannot mount yerself.")
            return build_dispatch_result("mount_request", False, reason="self_mount", request=request_contract)
        if bool(getattr(rider, "rider_cid", None)) or bool(getattr(rider, "mounted_by_cid", None)):
            self._toast(ws_id, "Ye be already mounted.")
            return build_dispatch_result("mount_request", False, reason="rider_already_mounted", request=request_contract)
        if bool(getattr(mount, "mounted_by_cid", None)) or bool(getattr(mount, "rider_cid", None)):
            self._toast(ws_id, "That creature be already tied up in a mount.")
            return build_dispatch_result("mount_request", False, reason="mount_occupied", request=request_contract)

        _cols, _rows, _obs, _rough, positions = t._lan_live_map_data()
        rider_pos = positions.get(int(rider_cid))
        mount_pos = positions.get(int(mount_cid))
        if rider_pos is None or mount_pos is None or tuple(rider_pos) != tuple(mount_pos):
            self._toast(ws_id, "Rider and mount must share a square.")
            return build_dispatch_result("mount_request", False, reason="different_square", request=request_contract)

        pending_mount_requests = t.__dict__.get("_pending_mount_requests")
        if not isinstance(pending_mount_requests, dict):
            pending_mount_requests = {}
            t.__dict__["_pending_mount_requests"] = pending_mount_requests

        summoned_by_cid = self._coerce_optional_int(getattr(mount, "summoned_by_cid", None))
        auto_accept = summoned_by_cid is not None and int(summoned_by_cid) == int(rider_cid)
        request_id = f"mount:{int(time.time() * 1000)}:{int(rider_cid)}:{int(mount_cid)}"
        pending_mount_requests[request_id] = {
            "rider_cid": int(rider_cid),
            "mount_cid": int(mount_cid),
            "requester_ws": ws_id,
        }
        if auto_accept:
            t._accept_mount(int(rider_cid), int(mount_cid), ws_id, auto=True)
            pending_mount_requests.pop(request_id, None)
            return build_dispatch_result(
                "mount_request",
                True,
                request=request_contract,
                request_id=request_id,
                auto_accept=True,
            )

        if not bool(getattr(mount, "is_pc", False)):
            pending_mount_requests.pop(request_id, None)
            approved = self._ask_yes_no(
                "Mount Request",
                f"{getattr(rider, 'name', 'A rider')} is trying to mount {getattr(mount, 'name', 'a creature')}. Allow?",
            )
            if approved:
                t._accept_mount(int(rider_cid), int(mount_cid), ws_id, auto=False)
                return build_dispatch_result(
                    "mount_request",
                    True,
                    request=request_contract,
                    request_id=request_id,
                    dm_approved=True,
                )
            passed = self._ask_yes_no(
                "Mount Request",
                f"{getattr(rider, 'name', 'Rider')} vs {getattr(mount, 'name', 'Creature')}: Pass or Fail?\n\n"
                "Yes = Pass (allow mount)\nNo = Fail (deny mount)",
            )
            if passed:
                t._accept_mount(int(rider_cid), int(mount_cid), ws_id, auto=False)
                return build_dispatch_result(
                    "mount_request",
                    True,
                    request=request_contract,
                    request_id=request_id,
                    dm_approved=True,
                )
            self._toast(ws_id, "Mount request declined.")
            return build_dispatch_result(
                "mount_request",
                False,
                reason="declined",
                request=request_contract,
                request_id=request_id,
            )

        target_ws_ids = t._find_ws_for_cid(int(mount_cid)) if bool(getattr(mount, "is_pc", False)) else []
        payload = {
            "type": "mount_prompt",
            "request_id": request_id,
            "rider_cid": int(rider_cid),
            "mount_cid": int(mount_cid),
            "rider_name": str(getattr(rider, "name", "Rider")),
        }
        lan = t.__dict__.get("_lan")
        loop = getattr(lan, "_loop", None) if lan is not None else None
        send_async = getattr(lan, "_send_async", None) if lan is not None else None
        broadcast_payload = getattr(lan, "_broadcast_payload", None) if lan is not None else None
        if target_ws_ids and loop and callable(send_async):
            for target_ws_id in target_ws_ids:
                try:
                    asyncio.run_coroutine_threadsafe(send_async(int(target_ws_id), payload), loop)
                except Exception:
                    pass
        elif callable(broadcast_payload):
            try:
                broadcast_payload({**payload, "to_admin": True})
            except Exception:
                pass
        self._toast(ws_id, "Mount request sent.")
        return build_dispatch_result(
            "mount_request",
            True,
            request=request_contract,
            request_id=request_id,
            prompt_sent=True,
        )

    def mount_response(
        self,
        msg: Dict[str, Any],
        *,
        cid: Optional[int],
        ws_id: Any,
        is_admin: bool,
    ) -> Dict[str, Any]:
        t = self._tracker
        request_contract = build_mount_response_contract(
            msg,
            cid=cid,
            ws_id=ws_id,
            is_admin=is_admin,
        )
        request_id = str(msg.get("request_id") or "").strip()
        pending_mount_requests = t.__dict__.get("_pending_mount_requests")
        pending = (
            pending_mount_requests.pop(request_id, None)
            if isinstance(pending_mount_requests, dict)
            else None
        )
        if not pending:
            self._toast(ws_id, "Mount request expired.")
            return build_dispatch_result("mount_response", False, reason="request_expired", request=request_contract)
        if bool(msg.get("accept")):
            t._accept_mount(
                int(pending.get("rider_cid")),
                int(pending.get("mount_cid")),
                pending.get("requester_ws"),
                auto=False,
            )
            return build_dispatch_result(
                "mount_response",
                True,
                request=request_contract,
                request_id=request_id,
                accepted=True,
            )
        requester_ws = pending.get("requester_ws")
        if requester_ws is not None:
            self._toast(int(requester_ws), "Mount request declined.")
        return build_dispatch_result(
            "mount_response",
            True,
            request=request_contract,
            request_id=request_id,
            accepted=False,
        )

    def dismount(
        self,
        msg: Dict[str, Any],
        *,
        cid: Optional[int],
        ws_id: Any,
        is_admin: bool,
    ) -> Dict[str, Any]:
        del msg, is_admin
        t = self._tracker
        request_contract = build_dismount_contract(
            {"type": "dismount"},
            cid=cid,
            ws_id=ws_id,
            is_admin=False,
        )
        combatants = getattr(t, "combatants", {}) or {}
        if cid is None:
            return build_dispatch_result("dismount", False, reason="missing_cid", request=request_contract)
        try:
            cid_int = int(cid)
        except Exception:
            return build_dispatch_result("dismount", False, reason="invalid_cid", request=request_contract)
        rider = combatants.get(cid_int)
        if rider is None:
            return build_dispatch_result("dismount", False, reason="combatant_missing", request=request_contract)
        mount_cid = self._coerce_optional_int(getattr(rider, "rider_cid", None))
        if mount_cid is None:
            self._toast(ws_id, "Ye are not mounted.")
            return build_dispatch_result("dismount", False, reason="not_mounted", request=request_contract)
        mount = combatants.get(int(mount_cid))
        if mount is None:
            setattr(rider, "rider_cid", None)
            return build_dispatch_result(
                "dismount",
                True,
                request=request_contract,
                mount_missing_cleanup=True,
            )
        cost = int(t._mount_cost(rider))
        if int(getattr(rider, "move_remaining", 0) or 0) < cost:
            self._toast(ws_id, f"Not enough movement to dismount (need {cost} ft).")
            return build_dispatch_result(
                "dismount",
                False,
                reason="insufficient_movement",
                request=request_contract,
                cost=cost,
            )
        rider.move_remaining = max(0, int(getattr(rider, "move_remaining", 0) or 0) - cost)
        setattr(rider, "rider_cid", None)
        setattr(mount, "mounted_by_cid", None)
        setattr(mount, "mount_shared_turn", False)
        setattr(mount, "mount_controller_mode", "independent")
        t._restore_mount_initiative(int(rider.cid), int(mount.cid))
        log = getattr(t, "_log", None)
        if callable(log):
            try:
                log(f"{rider.name} dismounts from {mount.name}.", cid=rider.cid)
            except Exception:
                pass
        broadcast = getattr(t, "_lan_force_state_broadcast", None)
        if callable(broadcast):
            try:
                broadcast()
            except Exception:
                pass
        return build_dispatch_result(
            "dismount",
            True,
            request=request_contract,
            mount_cid=int(mount.cid),
            cost=cost,
            move_remaining=int(getattr(rider, "move_remaining", 0) or 0),
        )

    def dash(
        self,
        msg: Dict[str, Any],
        *,
        cid: Optional[int],
        ws_id: Any,
        is_admin: bool,
    ) -> Dict[str, Any]:
        t = self._tracker
        request_contract = build_dash_contract(
            msg,
            cid=cid,
            ws_id=ws_id,
            is_admin=is_admin,
        )
        combatants = getattr(t, "combatants", {}) or {}
        if cid is None:
            return build_dispatch_result("dash", False, reason="missing_cid", request=request_contract)
        try:
            cid_int = int(cid)
        except Exception:
            return build_dispatch_result("dash", False, reason="invalid_cid", request=request_contract)
        c = combatants.get(cid_int)
        if c is None:
            return build_dispatch_result("dash", False, reason="combatant_missing", request=request_contract)
        spend = str(msg.get("spend") or "").strip().lower()
        if spend not in ("action", "bonus"):
            self._toast(ws_id, "Choose action or bonus action, matey.")
            return build_dispatch_result("dash", False, reason="invalid_spend", request=request_contract)
        if spend == "action":
            if not t._use_action(c):
                self._toast(ws_id, "No actions left, matey.")
                return build_dispatch_result("dash", False, reason="no_action", request=request_contract)
            spend_label = "action"
        else:
            if not t._use_bonus_action(c):
                self._toast(ws_id, "No bonus actions left, matey.")
                return build_dispatch_result("dash", False, reason="no_bonus_action", request=request_contract)
            spend_label = "bonus action"
        try:
            base_speed = int(t._mode_speed(c))
        except Exception:
            base_speed = int(getattr(c, "speed", 30) or 30)
        if bool(getattr(c, "speed_zero_until_turn_end", False)):
            self._toast(ws_id, "Yer speed is 0 until turn end.")
            return build_dispatch_result("dash", False, reason="speed_zero", request=request_contract)
        try:
            total_before = int(getattr(c, "move_total", 0) or 0)
            remaining_before = int(getattr(c, "move_remaining", 0) or 0)
            setattr(c, "move_total", total_before + base_speed)
            setattr(c, "move_remaining", remaining_before + base_speed)
            log = getattr(t, "_log", None)
            if callable(log):
                try:
                    log(
                        f"{c.name} dashed (move {remaining_before}/{total_before} -> {c.move_remaining}/{c.move_total})",
                        cid=cid_int,
                    )
                except Exception:
                    pass
            self._toast(ws_id, f"Dashed ({spend_label}).")
            rebuild = getattr(t, "_rebuild_table", None)
            if callable(rebuild):
                try:
                    rebuild(scroll_to_current=True)
                except Exception:
                    pass
        except Exception as exc:
            return build_dispatch_result(
                "dash",
                False,
                reason="dash_failed",
                error=str(exc),
                request=request_contract,
            )
        return build_dispatch_result(
            "dash",
            True,
            request=request_contract,
            spend=spend,
            move_total=int(getattr(c, "move_total", 0) or 0),
            move_remaining=int(getattr(c, "move_remaining", 0) or 0),
        )

    def use_action(
        self,
        msg: Dict[str, Any],
        *,
        cid: Optional[int],
        ws_id: Any,
        is_admin: bool,
    ) -> Dict[str, Any]:
        t = self._tracker
        request_contract = build_use_action_contract(
            msg,
            cid=cid,
            ws_id=ws_id,
            is_admin=is_admin,
        )
        combatants = getattr(t, "combatants", {}) or {}
        if cid is None:
            return build_dispatch_result("use_action", False, reason="missing_cid", request=request_contract)
        try:
            cid_int = int(cid)
        except Exception:
            return build_dispatch_result("use_action", False, reason="invalid_cid", request=request_contract)
        c = combatants.get(cid_int)
        if c is None:
            return build_dispatch_result("use_action", False, reason="combatant_missing", request=request_contract)
        if not t._use_action(c):
            self._toast(ws_id, "No actions left, matey.")
            return build_dispatch_result("use_action", False, reason="no_action", request=request_contract)
        self._toast(ws_id, "Action used.")
        rebuild = getattr(t, "_rebuild_table", None)
        if callable(rebuild):
            try:
                rebuild(scroll_to_current=True)
            except Exception:
                pass
        return build_dispatch_result(
            "use_action",
            True,
            request=request_contract,
            action_remaining=int(getattr(c, "action_remaining", 0) or 0),
        )

    def use_bonus_action(
        self,
        msg: Dict[str, Any],
        *,
        cid: Optional[int],
        ws_id: Any,
        is_admin: bool,
    ) -> Dict[str, Any]:
        t = self._tracker
        request_contract = build_use_bonus_action_contract(
            msg,
            cid=cid,
            ws_id=ws_id,
            is_admin=is_admin,
        )
        combatants = getattr(t, "combatants", {}) or {}
        if cid is None:
            return build_dispatch_result("use_bonus_action", False, reason="missing_cid", request=request_contract)
        try:
            cid_int = int(cid)
        except Exception:
            return build_dispatch_result("use_bonus_action", False, reason="invalid_cid", request=request_contract)
        c = combatants.get(cid_int)
        if c is None:
            return build_dispatch_result("use_bonus_action", False, reason="combatant_missing", request=request_contract)
        if not t._use_bonus_action(c):
            self._toast(ws_id, "No bonus actions left, matey.")
            return build_dispatch_result("use_bonus_action", False, reason="no_bonus_action", request=request_contract)
        self._toast(ws_id, "Bonus action used.")
        rebuild = getattr(t, "_rebuild_table", None)
        if callable(rebuild):
            try:
                rebuild(scroll_to_current=True)
            except Exception:
                pass
        return build_dispatch_result(
            "use_bonus_action",
            True,
            request=request_contract,
            bonus_action_remaining=int(getattr(c, "bonus_action_remaining", 0) or 0),
        )

    def stand_up(
        self,
        msg: Dict[str, Any],
        *,
        cid: Optional[int],
        ws_id: Any,
        is_admin: bool,
    ) -> Dict[str, Any]:
        t = self._tracker
        request_contract = build_stand_up_contract(
            msg,
            cid=cid,
            ws_id=ws_id,
            is_admin=is_admin,
        )
        combatants = getattr(t, "combatants", {}) or {}
        if cid is None:
            return build_dispatch_result("stand_up", False, reason="missing_cid", request=request_contract)
        try:
            cid_int = int(cid)
        except Exception:
            return build_dispatch_result("stand_up", False, reason="invalid_cid", request=request_contract)
        c = combatants.get(cid_int)
        if c is None:
            return build_dispatch_result("stand_up", False, reason="combatant_missing", request=request_contract)
        if not t._has_condition(c, "prone"):
            return build_dispatch_result("stand_up", False, reason="not_prone", request=request_contract)
        eff = int(t._effective_speed(c))
        if eff <= 0:
            self._toast(ws_id, "Can't stand up right now (speed is 0).")
            return build_dispatch_result("stand_up", False, reason="speed_zero", request=request_contract)
        cost = max(0, eff // 2)
        if int(getattr(c, "move_remaining", 0) or 0) < cost:
            self._toast(ws_id, f"Not enough movement to stand (need {cost} ft).")
            return build_dispatch_result(
                "stand_up",
                False,
                reason="insufficient_movement",
                request=request_contract,
                cost=cost,
            )
        c.move_remaining = int(getattr(c, "move_remaining", 0) or 0) - cost
        t._remove_condition_type(c, "prone")
        log = getattr(t, "_log", None)
        if callable(log):
            try:
                log(f"stood up (spent {cost} ft, prone removed)", cid=c.cid)
            except Exception:
                pass
        self._toast(ws_id, "Stood up.")
        rebuild = getattr(t, "_rebuild_table", None)
        if callable(rebuild):
            try:
                rebuild(scroll_to_current=True)
            except Exception:
                pass
        return build_dispatch_result(
            "stand_up",
            True,
            request=request_contract,
            cost=cost,
            move_remaining=int(getattr(c, "move_remaining", 0) or 0),
        )

    def reset_turn(
        self,
        msg: Dict[str, Any],
        *,
        cid: Optional[int],
        ws_id: Any,
        is_admin: bool,
    ) -> Dict[str, Any]:
        t = self._tracker
        request_contract = build_reset_turn_contract(
            msg,
            cid=cid,
            ws_id=ws_id,
            is_admin=is_admin,
        )
        if cid is None:
            return build_dispatch_result("reset_turn", False, reason="missing_cid", request=request_contract)
        try:
            cid_int = int(cid)
        except Exception:
            return build_dispatch_result("reset_turn", False, reason="invalid_cid", request=request_contract)
        if not t._lan_restore_turn_snapshot(cid_int):
            self._toast(ws_id, "No turn snapshot yet, matey.")
            return build_dispatch_result("reset_turn", False, reason="snapshot_missing", request=request_contract)
        c = (getattr(t, "combatants", {}) or {}).get(cid_int)
        log = getattr(t, "_log", None)
        if c is not None and callable(log):
            try:
                log(f"{c.name} reset their turn snapshot.", cid=cid_int)
            except Exception:
                pass
        self._toast(ws_id, "Turn reset.")
        rebuild = getattr(t, "_rebuild_table", None)
        if callable(rebuild):
            try:
                rebuild(scroll_to_current=True)
            except Exception:
                pass
        return build_dispatch_result("reset_turn", True, request=request_contract)

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

    def _resolve_reaction_response(
        self,
        msg: Dict[str, Any],
        *,
        cid: int,
        ws_id: Any,
        offer: Dict[str, Any],
        request_id: str,
    ) -> Dict[str, Any]:
        choice = str(msg.get("choice") or "").strip().lower()
        trigger = str(offer.get("trigger") or "").strip().lower()
        if trigger == "shield":
            return self._resolve_shield_reaction(
                msg,
                request_id=request_id,
                offer=offer,
                choice=choice,
                ws_id=ws_id,
            )
        if trigger == "hellish_rebuke":
            return self._resolve_hellish_rebuke_reaction(
                msg,
                request_id=request_id,
                offer=offer,
                choice=choice,
                ws_id=ws_id,
            )
        if trigger == "absorb_elements":
            return self._resolve_absorb_elements_reaction(
                msg,
                request_id=request_id,
                offer=offer,
                choice=choice,
                ws_id=ws_id,
            )
        if trigger == "interception":
            return self._resolve_interception_reaction(
                msg,
                request_id=request_id,
                offer=offer,
                choice=choice,
                ws_id=ws_id,
            )
        if trigger == "spell_stopper":
            return self._resolve_spell_stopper_reaction(
                msg,
                request_id=request_id,
                offer=offer,
                choice=choice,
                ws_id=ws_id,
            )
        if trigger == "counterspell":
            return self._resolve_counterspell_reaction(
                msg,
                request_id=request_id,
                offer=offer,
                choice=choice,
                ws_id=ws_id,
            )
        if choice in ("", "decline", "ignore"):
            self.prompts.pop_prompt(request_id)
            return {"ok": True, "trigger": trigger, "choice": choice, "prompt_state": "declined"}
        self.prompts.set_lifecycle_state(request_id, "accepted", accepted_choice=choice)
        return {"ok": True, "trigger": trigger, "choice": choice, "prompt_state": "accepted"}

    def _resolve_shield_reaction(
        self,
        msg: Dict[str, Any],
        *,
        request_id: str,
        offer: Dict[str, Any],
        choice: str,
        ws_id: Any,
    ) -> Dict[str, Any]:
        t = self._tracker
        pending = self.prompts.get_resolution(request_id)
        resume_dispatch = self.prompts.get_resume_dispatch(request_id)
        if not isinstance(pending, dict):
            self._toast(ws_id, "That Shield offer expired, matey.")
            return {"ok": False, "reason": "expired_offer", "trigger": "shield", "choice": choice}
        reactor_cid = self._normalize_cid(offer.get("reactor_cid"), "reaction_response.shield.reactor")
        reactor = t.combatants.get(int(reactor_cid)) if reactor_cid is not None else None
        if reactor is None:
            self.prompts.pop_prompt(request_id)
            return {"ok": False, "reason": "reactor_missing", "trigger": "shield", "choice": choice}
        if choice in ("shield_never", "never"):
            t._set_reaction_prefs(int(reactor_cid), {"shield": "off"})
        if choice in ("shield_yes", "shield_cast", "shield"):
            if not t._use_reaction(reactor):
                self._toast(ws_id, "No reactions left for Shield, matey.")
                choice = "shield_no"
            else:
                ok_cast, err_cast = t._consume_shield_cast(reactor)
                if not ok_cast:
                    self._toast(ws_id, err_cast or "Could not cast Shield, matey.")
                    choice = "shield_no"
                else:
                    t._shield_effect_start(reactor)
                    t._log(
                        f"{getattr(reactor, 'name', 'Target')} casts Shield.",
                        cid=int(getattr(reactor, "cid", 0) or 0),
                    )
        self.prompts.pop_prompt(request_id)
        if isinstance(resume_dispatch, dict):
            flags = dict(resume_dispatch.get("flags") if isinstance(resume_dispatch.get("flags"), dict) else {})
            flags["_shield_resolution_done"] = True
            resume_dispatch["flags"] = flags
            self._oplog(
                f"reaction_offer:shield resolved request_id={request_id} choice={choice}",
                level="info",
            )
            return {
                "ok": True,
                "trigger": "shield",
                "choice": choice,
                "prompt_state": "resolved",
                "resume_dispatch": resume_dispatch,
            }
        return {"ok": True, "trigger": "shield", "choice": choice, "prompt_state": "resolved"}

    def _resolve_hellish_rebuke_reaction(
        self,
        msg: Dict[str, Any],
        *,
        request_id: str,
        offer: Dict[str, Any],
        choice: str,
        ws_id: Any,
    ) -> Dict[str, Any]:
        t = self._tracker
        pending = self.prompts.get_resolution(request_id)
        if not isinstance(pending, dict):
            self._toast(ws_id, "That Hellish Rebuke offer expired, matey.")
            return {"ok": False, "reason": "expired_offer", "trigger": "hellish_rebuke", "choice": choice}
        reactor_cid = self._normalize_cid(offer.get("reactor_cid"), "reaction_response.hellish_rebuke.reactor")
        reactor = t.combatants.get(int(reactor_cid)) if reactor_cid is not None else None
        if reactor is None:
            self.prompts.pop_prompt(request_id)
            return {"ok": False, "reason": "reactor_missing", "trigger": "hellish_rebuke", "choice": choice}
        if choice in ("never", "hellish_rebuke_never"):
            self.prompts.pop_prompt(request_id)
            t._set_reaction_prefs(int(reactor_cid), {"hellish_rebuke": "off"})
            return {"ok": True, "trigger": "hellish_rebuke", "choice": choice, "prompt_state": "declined"}
        if choice in ("", "decline", "ignore", "hellish_rebuke_no"):
            self.prompts.pop_prompt(request_id)
            return {"ok": True, "trigger": "hellish_rebuke", "choice": choice, "prompt_state": "declined"}
        if choice not in ("cast_hellish_rebuke", "hellish_rebuke", "hellish_rebuke_yes"):
            return {"ok": True, "trigger": "hellish_rebuke", "choice": choice}
        if not t._use_reaction(reactor):
            self._toast(ws_id, "No reactions left for Hellish Rebuke, matey.")
            return {"ok": False, "reason": "reaction_unavailable", "trigger": "hellish_rebuke", "choice": choice}
        attacker_cid = self._normalize_cid(pending.get("attacker_cid"), "reaction_response.hellish_rebuke.attacker")
        if attacker_cid is None or int(attacker_cid) not in t.combatants:
            self._toast(ws_id, "The attacker is gone; Hellish Rebuke fizzles.")
            return {"ok": False, "reason": "attacker_missing", "trigger": "hellish_rebuke", "choice": choice}
        self.prompts.set_lifecycle_state(
            request_id,
            "accepted",
            accepted_choice=choice,
            response_details={"reaction_spent": True},
        )
        self._oplog(
            "reaction_offer:hellish_rebuke accepted "
            f"request_id={request_id} reactor={int(reactor_cid)} attacker={int(attacker_cid)}",
            level="info",
        )
        lan = t.__dict__.get("_lan")
        loop = getattr(lan, "_loop", None) if lan is not None else None
        send_async = getattr(lan, "_send_async", None) if lan is not None else None
        if ws_id is not None and callable(send_async) and loop:
            try:
                asyncio.run_coroutine_threadsafe(
                    send_async(
                        int(ws_id),
                        build_hellish_rebuke_resolve_start_payload(
                            request_id=str(request_id),
                            caster_cid=int(reactor_cid),
                            attacker_cid=int(attacker_cid),
                            target_cid=int(attacker_cid),
                        ),
                    ),
                    loop,
                )
            except Exception:
                pass
        return {"ok": True, "trigger": "hellish_rebuke", "choice": choice, "prompt_state": "accepted"}

    def _resolve_absorb_elements_reaction(
        self,
        msg: Dict[str, Any],
        *,
        request_id: str,
        offer: Dict[str, Any],
        choice: str,
        ws_id: Any,
    ) -> Dict[str, Any]:
        t = self._tracker
        pending = self.prompts.get_resolution(request_id)
        resume_dispatch = self.prompts.get_resume_dispatch(request_id)
        if not isinstance(pending, dict):
            self._toast(ws_id, "That Absorb Elements offer expired, matey.")
            return {"ok": False, "reason": "expired_offer", "trigger": "absorb_elements", "choice": choice}
        reactor_cid = self._normalize_cid(offer.get("reactor_cid"), "reaction_response.absorb_elements.reactor")
        reactor = t.combatants.get(int(reactor_cid)) if reactor_cid is not None else None
        if reactor is None:
            self.prompts.pop_prompt(request_id)
            return {"ok": False, "reason": "reactor_missing", "trigger": "absorb_elements", "choice": choice}
        if choice in ("absorb_elements_never", "never"):
            t._set_reaction_prefs(int(reactor_cid), {"absorb_elements": "off"})
        flags = dict(
            resume_dispatch.get("flags")
            if isinstance(resume_dispatch, dict) and isinstance(resume_dispatch.get("flags"), dict)
            else {}
        )
        flags["_absorb_elements_resolution_done"] = True
        if choice in ("absorb_elements_never", "never", "", "decline", "ignore", "absorb_elements_decline"):
            self.prompts.pop_prompt(request_id)
            if isinstance(resume_dispatch, dict):
                resume_dispatch["flags"] = flags
                return {
                    "ok": True,
                    "trigger": "absorb_elements",
                    "choice": choice,
                    "prompt_state": "declined",
                    "resume_dispatch": resume_dispatch,
                }
            return {"ok": True, "trigger": "absorb_elements", "choice": choice, "prompt_state": "declined"}
        if not choice.startswith("cast_absorb_elements_"):
            self.prompts.pop_prompt(request_id)
            if isinstance(resume_dispatch, dict):
                resume_dispatch["flags"] = flags
                return {
                    "ok": True,
                    "trigger": "absorb_elements",
                    "choice": choice,
                    "prompt_state": "resolved",
                    "resume_dispatch": resume_dispatch,
                }
            return {"ok": True, "trigger": "absorb_elements", "choice": choice, "prompt_state": "resolved"}
        chosen_type = t._canonical_damage_type(choice.replace("cast_absorb_elements_", "", 1))
        allowed_types = {
            t._canonical_damage_type(item)
            for item in (pending.get("trigger_types") if isinstance(pending.get("trigger_types"), list) else [])
        }
        allowed_types = {item for item in allowed_types if item}
        if chosen_type not in allowed_types:
            self._toast(ws_id, "That damage type is invalid for Absorb Elements.")
            self.prompts.pop_prompt(request_id)
            if isinstance(resume_dispatch, dict):
                resume_dispatch["flags"] = flags
                return {
                    "ok": False,
                    "reason": "invalid_damage_type",
                    "trigger": "absorb_elements",
                    "choice": choice,
                    "resume_dispatch": resume_dispatch,
                }
            return {"ok": False, "reason": "invalid_damage_type", "trigger": "absorb_elements", "choice": choice}
        if not t._use_reaction(reactor):
            self._toast(ws_id, "No reactions left for Absorb Elements, matey.")
            self.prompts.pop_prompt(request_id)
            if isinstance(resume_dispatch, dict):
                resume_dispatch["flags"] = flags
                return {
                    "ok": False,
                    "reason": "reaction_unavailable",
                    "trigger": "absorb_elements",
                    "choice": choice,
                    "resume_dispatch": resume_dispatch,
                }
            return {"ok": False, "reason": "reaction_unavailable", "trigger": "absorb_elements", "choice": choice}
        try:
            slot_level = int(msg.get("slot_level")) if msg.get("slot_level") is not None else 1
        except Exception:
            slot_level = 1
        slot_level = max(1, min(9, int(slot_level)))
        player_name = t._pc_name_for(int(reactor.cid))
        ok_slot, slot_err, spent_level = t._consume_spell_slot_for_cast(player_name, slot_level, 1)
        if not ok_slot:
            self._toast(ws_id, slot_err or "Could not cast Absorb Elements, matey.")
            self.prompts.pop_prompt(request_id)
            if isinstance(resume_dispatch, dict):
                resume_dispatch["flags"] = flags
                return {
                    "ok": False,
                    "reason": "slot_unavailable",
                    "trigger": "absorb_elements",
                    "choice": choice,
                    "resume_dispatch": resume_dispatch,
                }
            return {"ok": False, "reason": "slot_unavailable", "trigger": "absorb_elements", "choice": choice}
        spend_level = int(spent_level) if spent_level is not None else int(slot_level)
        t._activate_absorb_elements(reactor, chosen_type, max(1, int(spend_level)))
        t._log(
            f"{getattr(reactor, 'name', 'Target')} casts Absorb Elements ({chosen_type.title()}).",
            cid=int(getattr(reactor, "cid", 0) or 0),
        )
        self.prompts.pop_prompt(request_id)
        if isinstance(resume_dispatch, dict):
            resume_dispatch["flags"] = flags
            return {
                "ok": True,
                "trigger": "absorb_elements",
                "choice": choice,
                "prompt_state": "resolved",
                "resume_dispatch": resume_dispatch,
            }
        return {"ok": True, "trigger": "absorb_elements", "choice": choice, "prompt_state": "resolved"}

    def _resolve_interception_reaction(
        self,
        msg: Dict[str, Any],
        *,
        request_id: str,
        offer: Dict[str, Any],
        choice: str,
        ws_id: Any,
    ) -> Dict[str, Any]:
        t = self._tracker
        pending = self.prompts.get_resolution(request_id)
        resume_dispatch = self.prompts.get_resume_dispatch(request_id)
        if not isinstance(pending, dict):
            self._toast(ws_id, "That Interception offer expired, matey.")
            return {"ok": False, "reason": "expired_offer", "trigger": "interception", "choice": choice}
        reactor_cid = self._normalize_cid(offer.get("reactor_cid"), "reaction_response.interception.reactor")
        reactor = t.combatants.get(int(reactor_cid)) if reactor_cid is not None else None
        if reactor is None:
            self.prompts.pop_prompt(request_id)
            return {"ok": False, "reason": "reactor_missing", "trigger": "interception", "choice": choice}
        if choice in ("interception_never", "never"):
            t._set_reaction_prefs(int(reactor_cid), {"interception": "off"})
        flags = dict(
            resume_dispatch.get("flags")
            if isinstance(resume_dispatch, dict) and isinstance(resume_dispatch.get("flags"), dict)
            else {}
        )
        flags["_interception_resolution_done"] = True
        if choice in ("interception_never", "never", "", "decline", "ignore", "interception_no"):
            self.prompts.pop_prompt(request_id)
            if isinstance(resume_dispatch, dict):
                resume_dispatch["flags"] = flags
                return {
                    "ok": True,
                    "trigger": "interception",
                    "choice": choice,
                    "prompt_state": "declined",
                    "resume_dispatch": resume_dispatch,
                }
            return {"ok": True, "trigger": "interception", "choice": choice, "prompt_state": "declined"}
        if choice not in ("interception_yes", "interception"):
            self.prompts.pop_prompt(request_id)
            if isinstance(resume_dispatch, dict):
                resume_dispatch["flags"] = flags
                return {
                    "ok": True,
                    "trigger": "interception",
                    "choice": choice,
                    "prompt_state": "resolved",
                    "resume_dispatch": resume_dispatch,
                }
            return {"ok": True, "trigger": "interception", "choice": choice, "prompt_state": "resolved"}
        if not t._use_reaction(reactor):
            self._toast(ws_id, "No reactions left for Interception, matey.")
            self.prompts.pop_prompt(request_id)
            if isinstance(resume_dispatch, dict):
                resume_dispatch["flags"] = flags
                return {
                    "ok": False,
                    "reason": "reaction_unavailable",
                    "trigger": "interception",
                    "choice": choice,
                    "resume_dispatch": resume_dispatch,
                }
            return {"ok": False, "reason": "reaction_unavailable", "trigger": "interception", "choice": choice}
        reduction_roll = int(random.randint(1, 10))
        reduction = int(reduction_roll) + int(t._interception_reduction_bonus(reactor))
        self.prompts.pop_prompt(request_id)
        if isinstance(resume_dispatch, dict):
            flags["_interception_reduction"] = max(0, int(reduction))
            flags["_interception_reactor_cid"] = int(reactor_cid)
            resume_dispatch["flags"] = flags
            return {
                "ok": True,
                "trigger": "interception",
                "choice": choice,
                "prompt_state": "resolved",
                "resume_dispatch": resume_dispatch,
            }
        return {"ok": True, "trigger": "interception", "choice": choice, "prompt_state": "resolved"}

    def _resolve_spell_stopper_reaction(
        self,
        msg: Dict[str, Any],
        *,
        request_id: str,
        offer: Dict[str, Any],
        choice: str,
        ws_id: Any,
    ) -> Dict[str, Any]:
        """Resolve Fred's Spell Stopper reaction.
        
        On accept (spell_stopper_yes):
        - Spend the spell_stopper_reaction pool
        - Mark spell as interrupted (canceled, slot preserved)
        """
        t = self._tracker
        pending = self.prompts.get_resolution(request_id)
        resume_dispatch = self.prompts.get_resume_dispatch(request_id)
        if not isinstance(pending, dict):
            self._toast(ws_id, "That Spell Stopper offer expired, matey.")
            return {"ok": False, "reason": "expired_offer", "trigger": "spell_stopper", "choice": choice}
        
        reactor_cid = self._normalize_cid(offer.get("reactor_cid"), "reaction_response.spell_stopper.reactor")
        reactor = t.combatants.get(int(reactor_cid)) if reactor_cid is not None else None
        if reactor is None:
            self.prompts.pop_prompt(request_id)
            return {"ok": False, "reason": "reactor_missing", "trigger": "spell_stopper", "choice": choice}
        
        if choice in ("spell_stopper_never", "never"):
            t._set_reaction_prefs(int(reactor_cid), {"spell_stopper": "off"})
        
        flags = dict(
            resume_dispatch.get("flags")
            if isinstance(resume_dispatch, dict) and isinstance(resume_dispatch.get("flags"), dict)
            else {}
        )
        flags["_spell_stopper_resolution_done"] = True
        
        if choice in ("spell_stopper_never", "never", "", "decline", "ignore", "spell_stopper_no", "spell_stopper_decline"):
            self.prompts.pop_prompt(request_id)
            if isinstance(resume_dispatch, dict):
                resume_dispatch["flags"] = flags
                return {
                    "ok": True,
                    "trigger": "spell_stopper",
                    "choice": choice,
                    "prompt_state": "declined",
                    "resume_dispatch": resume_dispatch,
                }
            return {"ok": True, "trigger": "spell_stopper", "choice": choice, "prompt_state": "declined"}
        
        if choice not in ("spell_stopper_yes", "spell_stopper"):
            self.prompts.pop_prompt(request_id)
            if isinstance(resume_dispatch, dict):
                resume_dispatch["flags"] = flags
                return {
                    "ok": True,
                    "trigger": "spell_stopper",
                    "choice": choice,
                    "prompt_state": "resolved",
                    "resume_dispatch": resume_dispatch,
                }
            return {"ok": True, "trigger": "spell_stopper", "choice": choice, "prompt_state": "resolved"}
        
        # spell_stopper_yes: spend reaction + pool
        if not t._use_reaction(reactor):
            self._toast(ws_id, "No reactions left for Spell Stopper, matey.")
            self.prompts.pop_prompt(request_id)
            if isinstance(resume_dispatch, dict):
                resume_dispatch["flags"] = flags
                return {
                    "ok": False,
                    "reason": "reaction_unavailable",
                    "trigger": "spell_stopper",
                    "choice": choice,
                    "resume_dispatch": resume_dispatch,
                }
            return {"ok": False, "reason": "reaction_unavailable", "trigger": "spell_stopper", "choice": choice}
        
        # Spend the spell_stopper_reaction pool
        player_name = self._tracker._pc_name_for(int(reactor_cid))
        pool_ok, pool_msg = t._consume_resource_pool_for_cast(player_name, "spell_stopper_reaction", 1)
        if not pool_ok:
            self._toast(ws_id, f"Could not spend Spell Stopper pool: {pool_msg}")
            self.prompts.pop_prompt(request_id)
            if isinstance(resume_dispatch, dict):
                resume_dispatch["flags"] = flags
                return {
                    "ok": False,
                    "reason": "pool_unavailable",
                    "trigger": "spell_stopper",
                    "choice": choice,
                    "resume_dispatch": resume_dispatch,
                }
            return {"ok": False, "reason": "pool_unavailable", "trigger": "spell_stopper", "choice": choice}
        
        # Mark spell as interrupted: set flag to prevent damage/effects
        flags["_spell_stopped_by_spell_stopper"] = True
        t._log(
            f"{getattr(reactor, 'name', 'Reactor')} slashes with Spell Stopper, cutting off the spell!",
            cid=int(getattr(reactor, "cid", 0) or 0),
        )
        
        self.prompts.pop_prompt(request_id)
        if isinstance(resume_dispatch, dict):
            resume_dispatch["flags"] = flags
            self._oplog(
                f"reaction_offer:spell_stopper resolved request_id={request_id} choice={choice} reactor={int(reactor_cid)}",
                level="info",
            )
            return {
                "ok": True,
                "trigger": "spell_stopper",
                "choice": choice,
                "prompt_state": "resolved",
                "resume_dispatch": resume_dispatch,
            }
        return {"ok": True, "trigger": "spell_stopper", "choice": choice, "prompt_state": "resolved"}

    def _resolve_counterspell_reaction(
        self,
        msg: Dict[str, Any],
        *,
        request_id: str,
        offer: Dict[str, Any],
        choice: str,
        ws_id: Any,
    ) -> Dict[str, Any]:
        """Resolve a Counterspell reaction offer.

        On accept (counterspell_yes): spend a 3rd+ slot + reaction, mark the
        triggering spell as countered (no effect, no target damage applied).
        Bounded core: no Intelligence-save contest for higher-level spells;
        counterspell auto-succeeds.
        """
        t = self._tracker
        pending = self.prompts.get_resolution(request_id)
        resume_dispatch = self.prompts.get_resume_dispatch(request_id)
        if not isinstance(pending, dict):
            self._toast(ws_id, "That Counterspell offer expired, matey.")
            return {"ok": False, "reason": "expired_offer", "trigger": "counterspell", "choice": choice}

        reactor_cid = self._normalize_cid(offer.get("reactor_cid"), "reaction_response.counterspell.reactor")
        reactor = t.combatants.get(int(reactor_cid)) if reactor_cid is not None else None
        if reactor is None:
            self.prompts.pop_prompt(request_id)
            return {"ok": False, "reason": "reactor_missing", "trigger": "counterspell", "choice": choice}

        if choice in ("counterspell_never", "never"):
            t._set_reaction_prefs(int(reactor_cid), {"counterspell": "off"})

        flags = dict(
            resume_dispatch.get("flags")
            if isinstance(resume_dispatch, dict) and isinstance(resume_dispatch.get("flags"), dict)
            else {}
        )
        flags["_counterspell_resolution_done"] = True

        if choice in ("counterspell_never", "never", "", "decline", "ignore", "counterspell_no", "counterspell_decline"):
            self.prompts.pop_prompt(request_id)
            if isinstance(resume_dispatch, dict):
                resume_dispatch["flags"] = flags
                return {
                    "ok": True,
                    "trigger": "counterspell",
                    "choice": choice,
                    "prompt_state": "declined",
                    "resume_dispatch": resume_dispatch,
                }
            return {"ok": True, "trigger": "counterspell", "choice": choice, "prompt_state": "declined"}

        if choice not in ("counterspell_yes", "counterspell"):
            self.prompts.pop_prompt(request_id)
            if isinstance(resume_dispatch, dict):
                resume_dispatch["flags"] = flags
                return {
                    "ok": True,
                    "trigger": "counterspell",
                    "choice": choice,
                    "prompt_state": "resolved",
                    "resume_dispatch": resume_dispatch,
                }
            return {"ok": True, "trigger": "counterspell", "choice": choice, "prompt_state": "resolved"}

        # counterspell_yes: spend reaction + 3rd-level (or lowest available >=3) slot
        if not t._use_reaction(reactor):
            self._toast(ws_id, "No reactions left for Counterspell, matey.")
            self.prompts.pop_prompt(request_id)
            if isinstance(resume_dispatch, dict):
                resume_dispatch["flags"] = flags
                return {
                    "ok": False,
                    "reason": "reaction_unavailable",
                    "trigger": "counterspell",
                    "choice": choice,
                    "resume_dispatch": resume_dispatch,
                }
            return {"ok": False, "reason": "reaction_unavailable", "trigger": "counterspell", "choice": choice}

        player_name = t._pc_name_for(int(reactor_cid))
        slot_ok, slot_msg, _spent_level = t._consume_spell_slot_for_cast(
            player_name,
            t._COUNTERSPELL_MIN_SLOT,
            t._COUNTERSPELL_MIN_SLOT,
        )
        if not slot_ok:
            self._toast(ws_id, f"Could not spend Counterspell slot: {slot_msg}")
            self.prompts.pop_prompt(request_id)
            if isinstance(resume_dispatch, dict):
                resume_dispatch["flags"] = flags
                return {
                    "ok": False,
                    "reason": "slot_unavailable",
                    "trigger": "counterspell",
                    "choice": choice,
                    "resume_dispatch": resume_dispatch,
                }
            return {"ok": False, "reason": "slot_unavailable", "trigger": "counterspell", "choice": choice}

        # Constitution-save contest (2024 counterspell per Spells/counterspell.yaml):
        # the caster rolls CON save vs. counterspeller's spell save DC. On fail the
        # spell dissipates and its slot is refunded; on success the spell proceeds.
        source_cid_norm = self._normalize_cid(offer.get("source_cid"), "reaction_response.counterspell.source")
        caster = t.combatants.get(int(source_cid_norm)) if source_cid_norm is not None else None
        reactor_profile = t._profile_for_player_name(t._pc_name_for(int(reactor_cid)))
        try:
            dc = int(
                t._compute_spell_save_dc(reactor_profile if isinstance(reactor_profile, dict) else {})
                or 0
            )
        except Exception:
            dc = 0
        if dc <= 0:
            dc = 8 + t._COUNTERSPELL_MIN_SLOT  # safe fallback so the contest still resolves
        save_mod = int(t._combatant_save_modifier(caster, "con")) if caster is not None else 0
        save_roll, _alt = t._roll_save_with_mode(caster, "con") if caster is not None else (10, 10)
        save_total = int(save_roll) + int(save_mod)
        contest_success = save_total < int(dc)  # counterspell succeeds on caster's failure

        reactor_name = getattr(reactor, "name", "Reactor")
        caster_name = getattr(caster, "name", "the caster") if caster is not None else "the caster"
        t._log(
            f"{reactor_name} casts Counterspell (DC {dc}); "
            f"{caster_name}'s CON save: {save_roll}+{save_mod}={save_total}",
            cid=int(getattr(reactor, "cid", 0) or 0),
        )

        if contest_success:
            flags["_spell_counterspelled"] = True
            t._log(
                f"{caster_name} fails the save; the spell was countered!",
                cid=int(getattr(reactor, "cid", 0) or 0),
            )
            # Refund the caster's slot per YAML ("If that spell was cast with a spell slot,
            # the slot isn't expended"). Best-effort: only applies when a slot_level is
            # known on the resume payload. The AoE insertion fires BEFORE consumption so
            # no refund is needed there; this refund targets the targeted path.
            refund_level: Optional[int] = None
            refund_provenance: Optional[Dict[str, Any]] = None
            if isinstance(resume_dispatch, dict):
                payload = resume_dispatch.get("payload") if isinstance(resume_dispatch.get("payload"), dict) else {}
                try:
                    refund_level = int(payload.get("slot_level"))
                except Exception:
                    refund_level = None
                refund_provenance = payload.get("_spell_resource_spend_provenance") if isinstance(payload.get("_spell_resource_spend_provenance"), dict) else None
            if caster is not None and (
                (refund_level is not None and refund_level > 0)
                or isinstance(refund_provenance, dict)
            ):
                caster_name_for_refund = t._pc_name_for(int(getattr(caster, "cid", 0) or 0))
                refunder = getattr(t, "_refund_spell_slot", None)
                if callable(refunder) and caster_name_for_refund:
                    try:
                        effective_refund_level = int(refund_level or 0)
                        if effective_refund_level <= 0 and isinstance(refund_provenance, dict):
                            try:
                                effective_refund_level = int(refund_provenance.get("slot_level") or 0)
                            except Exception:
                                effective_refund_level = 0
                        if effective_refund_level > 0:
                            refunder(
                                caster_name_for_refund,
                                int(effective_refund_level),
                                refund_provenance,
                            )
                    except Exception:
                        pass
        else:
            t._log(
                f"{caster_name} succeeds on the save; Counterspell fails!",
                cid=int(getattr(caster, "cid", 0) or 0) if caster is not None else int(getattr(reactor, "cid", 0) or 0),
            )

        self.prompts.pop_prompt(request_id)
        if isinstance(resume_dispatch, dict):
            resume_dispatch["flags"] = flags
            self._oplog(
                (
                    f"reaction_offer:counterspell resolved request_id={request_id} "
                    f"choice={choice} reactor={int(reactor_cid)} "
                    f"dc={dc} save_total={save_total} countered={bool(contest_success)}"
                ),
                level="info",
            )
            return {
                "ok": True,
                "trigger": "counterspell",
                "choice": choice,
                "prompt_state": "resolved",
                "resume_dispatch": resume_dispatch,
                "contest": {
                    "dc": int(dc),
                    "save_roll": int(save_roll),
                    "save_mod": int(save_mod),
                    "save_total": int(save_total),
                    "countered": bool(contest_success),
                },
            }
        return {
            "ok": True,
            "trigger": "counterspell",
            "choice": choice,
            "prompt_state": "resolved",
            "contest": {
                "dc": int(dc),
                "save_roll": int(save_roll),
                "save_mod": int(save_mod),
                "save_total": int(save_total),
                "countered": bool(contest_success),
            },
        }

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
          - trigger-specific reaction resolution (shield, hellish rebuke,
            absorb elements, interception, generic accept/decline)
        """
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
        adjudicate_result = self._resolve_reaction_response(
            msg,
            cid=reactor_got,
            ws_id=ws_id,
            offer=dict(prompt),
            request_id=request_id,
        )
        if not isinstance(adjudicate_result, dict):
            adjudicate_result = {}
        resolve_ok = bool(adjudicate_result.get("ok", True))
        reason = str(adjudicate_result.get("reason") or "").strip().lower()
        resume_dispatch = None
        resume_dispatch = adjudicate_result.get("resume_dispatch") or adjudicate_result.get("resume")
        resume_result = self._dispatch_resume(resume_dispatch) if isinstance(resume_dispatch, dict) else None
        result_kwargs: Dict[str, Any] = {
            "request": request_contract,
            "prompt_id": request_id,
            "resume_dispatched": bool(resume_result),
            "resume_result": resume_result,
        }
        if reason:
            result_kwargs["reason"] = reason
        if "trigger" in adjudicate_result:
            result_kwargs["trigger"] = adjudicate_result.get("trigger")
        if "choice" in adjudicate_result:
            result_kwargs["choice"] = adjudicate_result.get("choice")
        if "prompt_state" in adjudicate_result:
            result_kwargs["prompt_state"] = adjudicate_result.get("prompt_state")
        if "contest" in adjudicate_result:
            result_kwargs["contest"] = adjudicate_result.get("contest")
        return build_dispatch_result(
            "reaction_response",
            resolve_ok,
            **result_kwargs,
        )
