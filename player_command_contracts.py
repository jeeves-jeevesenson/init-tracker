"""Canonical contracts for migrated player combat commands and prompts.

This module defines the backend-owned contract shapes for the migrated
player-command slice:

- request envelopes for attack / spell target / reaction response /
  end turn / manual override commands
- result/event payload finalizers for attack / spell target / prompt flows
- canonical pending-prompt records with lifecycle and resume metadata

The runtime remains dict-based today, so these helpers intentionally return
plain dictionaries that can be serialized, copied into snapshots, and
projected back into temporary legacy compatibility views without requiring a
full typed-runtime migration in this pass.
"""

from __future__ import annotations

import copy
import time
from typing import Any, Dict, Iterable, List, Optional, Sequence


PLAYER_COMMAND_CONTRACT_VERSION = 1
PROMPT_SCHEMA_VERSION = 1


SPECIAL_REACTION_TRIGGERS = {
    "shield",
    "hellish_rebuke",
    "absorb_elements",
    "interception",
}
ACTIVE_PROMPT_STATES = {"offered", "accepted"}


ATTACK_REQUEST_FIELDS: Sequence[str] = (
    "type",
    "target_cid",
    "weapon_id",
    "weapon_name",
    "weapon",
    "attack_roll",
    "roll",
    "hit",
    "critical",
    "damage_entries",
    "damage_type_override",
    "attack_count",
    "attack_spend",
    "spend",
    "attack_origin_cid",
    "reaction_request_id",
    "opportunity_attack",
    "prompt_attacker_cid",
    "consumes_pool",
    "consumes_pool_id",
    "consumes_pool_cost",
    "consumes_pool_always",
    "mastery_free_attack",
    "bonus_sequence_id",
    "bonus_sequence_total",
    "bonus_sequence_start",
    "mastery_free_attack",
    "damage_type_override",
    "stunning_strike",
    "_shield_resolution_done",
    "_absorb_elements_resolution_done",
    "_interception_resolution_done",
    "_interception_reduction",
    "_interception_reactor_cid",
)

SPELL_TARGET_REQUEST_FIELDS: Sequence[str] = (
    "type",
    "target_cid",
    "spell_slug",
    "spell_id",
    "spell_name",
    "spell_mode",
    "mode",
    "attack_roll",
    "roll",
    "hit",
    "critical",
    "damage_entries",
    "healing_entries",
    "damage_type",
    "save_type",
    "save_dc",
    "slot_level",
    "prompt_for_damage",
    "prompt_for_healing",
    "prompt_attacker_cid",
    "shot_index",
    "shot_total",
    "polymorph_form_id",
    "destination_col",
    "destination_row",
    "_shield_resolution_done",
    "_absorb_elements_resolution_done",
)

REACTION_RESPONSE_FIELDS: Sequence[str] = (
    "type",
    "request_id",
    "choice",
    "slot_level",
    "target_cid",
)

END_TURN_FIELDS: Sequence[str] = ("type",)
MANUAL_OVERRIDE_FIELDS: Sequence[str] = ("type", "hp_delta", "temp_hp_delta")
REACTION_PREFS_UPDATE_FIELDS: Sequence[str] = ("type", "prefs")
MANUAL_OVERRIDE_SPELL_SLOT_FIELDS: Sequence[str] = ("type", "slot_level", "delta")
MANUAL_OVERRIDE_RESOURCE_POOL_FIELDS: Sequence[str] = ("type", "pool_id", "delta")
LAY_ON_HANDS_USE_FIELDS: Sequence[str] = ("type", "target_cid", "amount", "cure_poisoned")
INVENTORY_ADJUST_CONSUMABLE_FIELDS: Sequence[str] = ("type", "consumable_id", "id", "delta")
USE_CONSUMABLE_FIELDS: Sequence[str] = ("type", "consumable_id", "id")
SECOND_WIND_USE_FIELDS: Sequence[str] = ("type", "healing_roll", "roll", "rolled")
ACTION_SURGE_USE_FIELDS: Sequence[str] = ("type",)
STAR_ADVANTAGE_USE_FIELDS: Sequence[str] = ("type",)
MONK_PATIENT_DEFENSE_FIELDS: Sequence[str] = ("type", "mode")
MONK_STEP_OF_WIND_FIELDS: Sequence[str] = ("type", "mode")
MONK_ELEMENTAL_ATTUNEMENT_FIELDS: Sequence[str] = ("type", "mode")
MONK_ELEMENTAL_BURST_FIELDS: Sequence[str] = ("type", "damage_type", "movement_mode", "payload")
MONK_UNCANNY_METABOLISM_FIELDS: Sequence[str] = ("type",)


def _copy(value: Any) -> Any:
    try:
        return copy.deepcopy(value)
    except Exception:
        return value


def _contract(schema: str) -> Dict[str, Any]:
    return {"schema": str(schema), "version": int(PLAYER_COMMAND_CONTRACT_VERSION)}


def _prompt_lifecycle(
    state: str,
    *,
    accepted_choice: Optional[str] = None,
    response_details: Optional[Dict[str, Any]] = None,
    created_at: Optional[float] = None,
    updated_at: Optional[float] = None,
    resolved_at: Optional[float] = None,
) -> Dict[str, Any]:
    created = float(created_at if created_at is not None else time.time())
    updated = float(updated_at if updated_at is not None else created)
    lifecycle: Dict[str, Any] = {
        "state": str(state or "offered"),
        "created_at": created,
        "updated_at": updated,
        "accepted_choice": str(accepted_choice) if accepted_choice else None,
        "response_details": _copy(response_details) if isinstance(response_details, dict) else {},
    }
    if resolved_at is not None:
        lifecycle["resolved_at"] = float(resolved_at)
    return lifecycle


def _sanitize_damage_entries(entries: Any) -> List[Dict[str, Any]]:
    sanitized: List[Dict[str, Any]] = []
    if not isinstance(entries, list):
        return sanitized
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        out: Dict[str, Any] = {}
        if "amount" in entry:
            out["amount"] = entry.get("amount")
        if "type" in entry:
            out["type"] = entry.get("type")
        if out:
            sanitized.append(out)
    return sanitized


def _project_payload(msg: Dict[str, Any], fields: Sequence[str], forced_type: str) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"type": str(forced_type)}
    if not isinstance(msg, dict):
        return payload
    for key in fields:
        if key == "type":
            continue
        if key not in msg:
            continue
        payload[key] = _copy(msg.get(key))
    if "damage_entries" in payload:
        payload["damage_entries"] = _sanitize_damage_entries(payload.get("damage_entries"))
    if "healing_entries" in payload:
        payload["healing_entries"] = _sanitize_damage_entries(payload.get("healing_entries"))
    return payload


def build_command_request_contract(
    command_type: str,
    payload: Dict[str, Any],
    *,
    cid: Optional[int],
    ws_id: Any,
    is_admin: bool,
) -> Dict[str, Any]:
    return {
        "contract": _contract(f"player_command.{str(command_type)}.request"),
        "command_type": str(command_type),
        "actor": {
            "cid": int(cid) if cid is not None else None,
            "ws_id": ws_id,
            "is_admin": bool(is_admin),
        },
        "payload": _copy(payload) if isinstance(payload, dict) else {},
    }


def build_attack_request_contract(
    msg: Dict[str, Any],
    *,
    cid: Optional[int],
    ws_id: Any,
    is_admin: bool,
) -> Dict[str, Any]:
    return build_command_request_contract(
        "attack_request",
        _project_payload(msg, ATTACK_REQUEST_FIELDS, "attack_request"),
        cid=cid,
        ws_id=ws_id,
        is_admin=is_admin,
    )


def build_spell_target_request_contract(
    msg: Dict[str, Any],
    *,
    cid: Optional[int],
    ws_id: Any,
    is_admin: bool,
) -> Dict[str, Any]:
    return build_command_request_contract(
        "spell_target_request",
        _project_payload(msg, SPELL_TARGET_REQUEST_FIELDS, "spell_target_request"),
        cid=cid,
        ws_id=ws_id,
        is_admin=is_admin,
    )


def build_reaction_response_contract(
    msg: Dict[str, Any],
    *,
    cid: Optional[int],
    ws_id: Any,
) -> Dict[str, Any]:
    return build_command_request_contract(
        "reaction_response",
        _project_payload(msg, REACTION_RESPONSE_FIELDS, "reaction_response"),
        cid=cid,
        ws_id=ws_id,
        is_admin=False,
    )


def build_end_turn_contract(
    *,
    cid: Optional[int],
    ws_id: Any,
    is_admin: bool,
) -> Dict[str, Any]:
    return build_command_request_contract(
        "end_turn",
        {"type": "end_turn"},
        cid=cid,
        ws_id=ws_id,
        is_admin=is_admin,
    )


def build_manual_override_contract(
    *,
    cid: Optional[int],
    ws_id: Any,
    is_admin: bool,
    hp_delta: Any,
    temp_hp_delta: Any,
) -> Dict[str, Any]:
    return build_command_request_contract(
        "manual_override_hp",
        {
            "type": "manual_override_hp",
            "hp_delta": hp_delta,
            "temp_hp_delta": temp_hp_delta,
        },
        cid=cid,
        ws_id=ws_id,
        is_admin=is_admin,
    )


def build_manual_override_spell_slot_contract(
    msg: Dict[str, Any],
    *,
    cid: Optional[int],
    ws_id: Any,
    is_admin: bool,
) -> Dict[str, Any]:
    return build_command_request_contract(
        "manual_override_spell_slot",
        _project_payload(msg, MANUAL_OVERRIDE_SPELL_SLOT_FIELDS, "manual_override_spell_slot"),
        cid=cid,
        ws_id=ws_id,
        is_admin=is_admin,
    )


def build_manual_override_resource_pool_contract(
    msg: Dict[str, Any],
    *,
    cid: Optional[int],
    ws_id: Any,
    is_admin: bool,
) -> Dict[str, Any]:
    return build_command_request_contract(
        "manual_override_resource_pool",
        _project_payload(msg, MANUAL_OVERRIDE_RESOURCE_POOL_FIELDS, "manual_override_resource_pool"),
        cid=cid,
        ws_id=ws_id,
        is_admin=is_admin,
    )


def build_reaction_prefs_update_contract(
    msg: Dict[str, Any],
    *,
    cid: Optional[int],
    ws_id: Any,
    is_admin: bool,
) -> Dict[str, Any]:
    return build_command_request_contract(
        "reaction_prefs_update",
        _project_payload(msg, REACTION_PREFS_UPDATE_FIELDS, "reaction_prefs_update"),
        cid=cid,
        ws_id=ws_id,
        is_admin=is_admin,
    )


def build_lay_on_hands_use_contract(
    msg: Dict[str, Any],
    *,
    cid: Optional[int],
    ws_id: Any,
    is_admin: bool,
) -> Dict[str, Any]:
    return build_command_request_contract(
        "lay_on_hands_use",
        _project_payload(msg, LAY_ON_HANDS_USE_FIELDS, "lay_on_hands_use"),
        cid=cid,
        ws_id=ws_id,
        is_admin=is_admin,
    )


def build_inventory_adjust_consumable_contract(
    msg: Dict[str, Any],
    *,
    cid: Optional[int],
    ws_id: Any,
    is_admin: bool,
) -> Dict[str, Any]:
    return build_command_request_contract(
        "inventory_adjust_consumable",
        _project_payload(msg, INVENTORY_ADJUST_CONSUMABLE_FIELDS, "inventory_adjust_consumable"),
        cid=cid,
        ws_id=ws_id,
        is_admin=is_admin,
    )


def build_use_consumable_contract(
    msg: Dict[str, Any],
    *,
    cid: Optional[int],
    ws_id: Any,
    is_admin: bool,
) -> Dict[str, Any]:
    return build_command_request_contract(
        "use_consumable",
        _project_payload(msg, USE_CONSUMABLE_FIELDS, "use_consumable"),
        cid=cid,
        ws_id=ws_id,
        is_admin=is_admin,
    )


def build_second_wind_use_contract(
    msg: Dict[str, Any],
    *,
    cid: Optional[int],
    ws_id: Any,
    is_admin: bool,
) -> Dict[str, Any]:
    return build_command_request_contract(
        "second_wind_use",
        _project_payload(msg, SECOND_WIND_USE_FIELDS, "second_wind_use"),
        cid=cid,
        ws_id=ws_id,
        is_admin=is_admin,
    )


def build_action_surge_use_contract(
    msg: Dict[str, Any],
    *,
    cid: Optional[int],
    ws_id: Any,
    is_admin: bool,
) -> Dict[str, Any]:
    return build_command_request_contract(
        "action_surge_use",
        _project_payload(msg, ACTION_SURGE_USE_FIELDS, "action_surge_use"),
        cid=cid,
        ws_id=ws_id,
        is_admin=is_admin,
    )


def build_star_advantage_use_contract(
    msg: Dict[str, Any],
    *,
    cid: Optional[int],
    ws_id: Any,
    is_admin: bool,
) -> Dict[str, Any]:
    return build_command_request_contract(
        "star_advantage_use",
        _project_payload(msg, STAR_ADVANTAGE_USE_FIELDS, "star_advantage_use"),
        cid=cid,
        ws_id=ws_id,
        is_admin=is_admin,
    )


def build_monk_patient_defense_contract(
    msg: Dict[str, Any],
    *,
    cid: Optional[int],
    ws_id: Any,
    is_admin: bool,
) -> Dict[str, Any]:
    return build_command_request_contract(
        "monk_patient_defense",
        _project_payload(msg, MONK_PATIENT_DEFENSE_FIELDS, "monk_patient_defense"),
        cid=cid,
        ws_id=ws_id,
        is_admin=is_admin,
    )


def build_monk_step_of_wind_contract(
    msg: Dict[str, Any],
    *,
    cid: Optional[int],
    ws_id: Any,
    is_admin: bool,
) -> Dict[str, Any]:
    return build_command_request_contract(
        "monk_step_of_wind",
        _project_payload(msg, MONK_STEP_OF_WIND_FIELDS, "monk_step_of_wind"),
        cid=cid,
        ws_id=ws_id,
        is_admin=is_admin,
    )


def build_monk_elemental_attunement_contract(
    msg: Dict[str, Any],
    *,
    cid: Optional[int],
    ws_id: Any,
    is_admin: bool,
) -> Dict[str, Any]:
    return build_command_request_contract(
        "monk_elemental_attunement",
        _project_payload(msg, MONK_ELEMENTAL_ATTUNEMENT_FIELDS, "monk_elemental_attunement"),
        cid=cid,
        ws_id=ws_id,
        is_admin=is_admin,
    )


def build_monk_elemental_burst_contract(
    msg: Dict[str, Any],
    *,
    cid: Optional[int],
    ws_id: Any,
    is_admin: bool,
) -> Dict[str, Any]:
    return build_command_request_contract(
        "monk_elemental_burst",
        _project_payload(msg, MONK_ELEMENTAL_BURST_FIELDS, "monk_elemental_burst"),
        cid=cid,
        ws_id=ws_id,
        is_admin=is_admin,
    )


def build_monk_uncanny_metabolism_contract(
    msg: Dict[str, Any],
    *,
    cid: Optional[int],
    ws_id: Any,
    is_admin: bool,
) -> Dict[str, Any]:
    return build_command_request_contract(
        "monk_uncanny_metabolism",
        _project_payload(msg, MONK_UNCANNY_METABOLISM_FIELDS, "monk_uncanny_metabolism"),
        cid=cid,
        ws_id=ws_id,
        is_admin=is_admin,
    )


def build_dispatch_result(command_type: str, ok: bool, **fields: Any) -> Dict[str, Any]:
    payload = {
        "contract": _contract(f"player_command.{str(command_type)}.dispatch_result"),
        "command_type": str(command_type),
        "ok": bool(ok),
    }
    payload.update({str(key): _copy(value) for key, value in fields.items()})
    return payload


def build_resume_dispatch(
    command_type: str,
    *,
    actor_cid: Optional[int],
    ws_id: Any,
    is_admin: bool,
    payload: Dict[str, Any],
    flags: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "contract": _contract("player_command.resume_dispatch"),
        "command_type": str(command_type),
        "actor_cid": int(actor_cid) if actor_cid is not None else None,
        "ws_id": ws_id,
        "is_admin": bool(is_admin),
        "payload": _copy(payload) if isinstance(payload, dict) else {},
        "flags": _copy(flags) if isinstance(flags, dict) else {},
    }


def apply_resume_dispatch(resume_dispatch: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not isinstance(resume_dispatch, dict):
        return None
    payload = _copy(resume_dispatch.get("payload")) if isinstance(resume_dispatch.get("payload"), dict) else {}
    flags = _copy(resume_dispatch.get("flags")) if isinstance(resume_dispatch.get("flags"), dict) else {}
    if not isinstance(payload, dict):
        return None
    payload.update(flags)
    return payload


def build_prompt_record(
    *,
    prompt_id: str,
    prompt_kind: str,
    trigger: str,
    reactor_cid: Optional[int],
    eligible_actor_cids: Optional[Iterable[int]],
    source_cid: Optional[int],
    target_cid: Optional[int],
    allowed_choices: Optional[Sequence[Dict[str, Any]]],
    ws_ids: Optional[Iterable[int]],
    prompt_text: str = "",
    metadata: Optional[Dict[str, Any]] = None,
    resolution: Optional[Dict[str, Any]] = None,
    resume_dispatch: Optional[Dict[str, Any]] = None,
    created_at: Optional[float] = None,
    expires_at: Optional[float] = None,
    lifecycle_state: str = "offered",
    accepted_choice: Optional[str] = None,
    response_details: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    created = float(created_at if created_at is not None else time.time())
    choices: List[Dict[str, Any]] = []
    for entry in allowed_choices or []:
        if not isinstance(entry, dict):
            continue
        choices.append(
            {
                "kind": str(entry.get("kind") or "").strip(),
                "label": str(entry.get("label") or "").strip() or str(entry.get("kind") or "").strip(),
                "mode": str(entry.get("mode") or "ask").strip().lower() or "ask",
            }
        )
    normalized_ws_ids: List[int] = []
    for ws_id in ws_ids or []:
        try:
            normalized_ws_ids.append(int(ws_id))
        except Exception:
            continue
    eligible: List[int] = []
    for actor_cid in eligible_actor_cids or []:
        try:
            eligible.append(int(actor_cid))
        except Exception:
            continue
    if reactor_cid is not None:
        try:
            reactor_int = int(reactor_cid)
        except Exception:
            reactor_int = None
        if reactor_int is not None and reactor_int not in eligible:
            eligible.append(reactor_int)
    else:
        reactor_int = None
    mode = "ask" if any(str(choice.get("mode") or "ask") == "ask" for choice in choices) else "auto"
    record: Dict[str, Any] = {
        "schema": "player_command.prompt",
        "schema_version": int(PROMPT_SCHEMA_VERSION),
        "contract": _contract("player_command.prompt"),
        "prompt_id": str(prompt_id or "").strip(),
        "request_id": str(prompt_id or "").strip(),
        "prompt_kind": str(prompt_kind or "").strip() or "reaction",
        "trigger": str(trigger or "").strip(),
        "reactor_cid": reactor_int,
        "eligible_actor_cids": eligible,
        "source_cid": int(source_cid) if source_cid is not None else None,
        "target_cid": int(target_cid) if target_cid is not None else None,
        "ws_ids": normalized_ws_ids,
        "allowed_choices": choices,
        "mode": mode,
        "prompt": str(prompt_text or "").strip(),
        "created_at": created,
        "updated_at": created,
        "expires_at": float(expires_at) if expires_at is not None else None,
        "metadata": _copy(metadata) if isinstance(metadata, dict) else {},
        "resolution": _copy(resolution) if isinstance(resolution, dict) else {},
        "resume": _copy(resume_dispatch) if isinstance(resume_dispatch, dict) else None,
        "lifecycle": _prompt_lifecycle(
            str(lifecycle_state or "offered"),
            accepted_choice=accepted_choice,
            response_details=response_details,
            created_at=created,
            updated_at=created,
        ),
    }
    return record


def update_prompt_record(
    prompt: Dict[str, Any],
    *,
    lifecycle_state: Optional[str] = None,
    accepted_choice: Optional[str] = None,
    response_details: Optional[Dict[str, Any]] = None,
    resolution: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    resume_dispatch: Optional[Dict[str, Any]] = None,
    expires_at: Optional[float] = None,
) -> Dict[str, Any]:
    updated = _copy(prompt) if isinstance(prompt, dict) else {}
    now = float(time.time())
    lifecycle = updated.get("lifecycle") if isinstance(updated.get("lifecycle"), dict) else {}
    lifecycle = _copy(lifecycle)
    if lifecycle_state is not None:
        lifecycle["state"] = str(lifecycle_state or "offered")
    lifecycle["updated_at"] = now
    if accepted_choice is not None:
        lifecycle["accepted_choice"] = str(accepted_choice or "").strip() or None
    if response_details is not None:
        lifecycle["response_details"] = _copy(response_details) if isinstance(response_details, dict) else {}
    if lifecycle.get("state") not in ACTIVE_PROMPT_STATES:
        lifecycle["resolved_at"] = now
    updated["lifecycle"] = lifecycle
    updated["updated_at"] = now
    if resolution is not None:
        updated["resolution"] = _copy(resolution) if isinstance(resolution, dict) else {}
    if metadata is not None:
        updated["metadata"] = _copy(metadata) if isinstance(metadata, dict) else {}
    if resume_dispatch is not None:
        updated["resume"] = _copy(resume_dispatch) if isinstance(resume_dispatch, dict) else None
    if expires_at is not None:
        updated["expires_at"] = float(expires_at)
    return updated


def build_reaction_offer_event(prompt: Dict[str, Any]) -> Dict[str, Any]:
    prompt_id = str(prompt.get("prompt_id") or prompt.get("request_id") or "").strip()
    allowed_choices = list(prompt.get("allowed_choices") if isinstance(prompt.get("allowed_choices"), list) else [])
    payload: Dict[str, Any] = {
        "type": "reaction_offer",
        "contract": _contract("player_command.reaction_offer"),
        "request_id": prompt_id,
        "prompt_id": prompt_id,
        "prompt_kind": str(prompt.get("prompt_kind") or "reaction"),
        "trigger": str(prompt.get("trigger") or ""),
        "reactor_cid": prompt.get("reactor_cid"),
        "source_cid": prompt.get("source_cid"),
        "target_cid": prompt.get("target_cid"),
        "choices": [
            {
                "kind": str(choice.get("kind") or "").strip(),
                "label": str(choice.get("label") or "").strip(),
            }
            for choice in allowed_choices
            if isinstance(choice, dict)
        ],
        "mode": str(prompt.get("mode") or "ask"),
        "created_at": prompt.get("created_at"),
        "expires_at": prompt.get("expires_at"),
        "lifecycle_state": str(((prompt.get("lifecycle") or {}).get("state") if isinstance(prompt.get("lifecycle"), dict) else "offered") or "offered"),
    }
    prompt_text = str(prompt.get("prompt") or "").strip()
    if prompt_text:
        payload["prompt"] = prompt_text
    metadata = prompt.get("metadata") if isinstance(prompt.get("metadata"), dict) else {}
    for key, value in metadata.items():
        if key in {"type", "request_id", "prompt_id", "prompt_kind", "choices", "mode"}:
            continue
        payload[str(key)] = _copy(value)
    auto_choices = [choice for choice in allowed_choices if isinstance(choice, dict) and str(choice.get("mode") or "ask") == "auto"]
    ask_choices = [choice for choice in allowed_choices if isinstance(choice, dict) and str(choice.get("mode") or "ask") == "ask"]
    if not ask_choices and len(auto_choices) == 1:
        payload["auto_choice"] = str(auto_choices[0].get("kind") or "").strip()
    return payload


def build_prompt_snapshot(prompt: Dict[str, Any]) -> Dict[str, Any]:
    lifecycle = prompt.get("lifecycle") if isinstance(prompt.get("lifecycle"), dict) else {}
    resolution = prompt.get("resolution") if isinstance(prompt.get("resolution"), dict) else {}
    snapshot: Dict[str, Any] = {
        "contract": _contract("player_command.prompt_snapshot"),
        "prompt_id": str(prompt.get("prompt_id") or prompt.get("request_id") or "").strip(),
        "request_id": str(prompt.get("prompt_id") or prompt.get("request_id") or "").strip(),
        "prompt_kind": str(prompt.get("prompt_kind") or "reaction"),
        "trigger": str(prompt.get("trigger") or ""),
        "reactor_cid": prompt.get("reactor_cid"),
        "eligible_actor_cids": _copy(prompt.get("eligible_actor_cids") if isinstance(prompt.get("eligible_actor_cids"), list) else []),
        "source_cid": prompt.get("source_cid"),
        "target_cid": prompt.get("target_cid"),
        "choices": _copy(prompt.get("allowed_choices") if isinstance(prompt.get("allowed_choices"), list) else []),
        "mode": str(prompt.get("mode") or "ask"),
        "prompt": str(prompt.get("prompt") or ""),
        "created_at": prompt.get("created_at"),
        "expires_at": prompt.get("expires_at"),
        "lifecycle": _copy(lifecycle),
        "metadata": _copy(prompt.get("metadata") if isinstance(prompt.get("metadata"), dict) else {}),
    }
    player_visible_next_step = resolution.get("player_visible") if isinstance(resolution.get("player_visible"), dict) else None
    if player_visible_next_step:
        snapshot["next_step"] = _copy(player_visible_next_step)
    return snapshot


def finalize_attack_result_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    result = _copy(payload) if isinstance(payload, dict) else {}
    result["contract"] = _contract("player_command.attack_result")
    if "damage_entries" in result:
        result["damage_entries"] = _sanitize_damage_entries(result.get("damage_entries"))
    if "riders" in result and isinstance(result.get("riders"), list):
        result["riders"] = _copy(result.get("riders"))
    return result


def finalize_spell_target_result_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    result = _copy(payload) if isinstance(payload, dict) else {}
    result["contract"] = _contract("player_command.spell_target_result")
    if "damage_entries" in result:
        result["damage_entries"] = _sanitize_damage_entries(result.get("damage_entries"))
    if "healing_entries" in result:
        result["healing_entries"] = _sanitize_damage_entries(result.get("healing_entries"))
    return result


def build_spell_target_rejection_payload(
    *,
    attacker_cid: int,
    target_cid: int,
    spell_name: str,
    spell_slug: Optional[str],
    spell_id: Optional[str],
    reason: str,
) -> Dict[str, Any]:
    return finalize_spell_target_result_payload(
        {
            "type": "spell_target_result",
            "ok": False,
            "attacker_cid": int(attacker_cid),
            "target_cid": int(target_cid),
            "spell_name": str(spell_name or ""),
            "spell_slug": str(spell_slug) if spell_slug else None,
            "spell_id": str(spell_id) if spell_id else None,
            "reason": str(reason or ""),
        }
    )


def build_hellish_rebuke_resolve_start_payload(
    *,
    request_id: str,
    caster_cid: int,
    attacker_cid: int,
    target_cid: int,
) -> Dict[str, Any]:
    return {
        "type": "hellish_rebuke_resolve_start",
        "contract": _contract("player_command.hellish_rebuke_resolve_start"),
        "request_id": str(request_id or "").strip(),
        "caster_cid": int(caster_cid),
        "attacker_cid": int(attacker_cid),
        "target_cid": int(target_cid),
        "spell_id": "hellish-rebuke",
        "spell_slug": "hellish-rebuke",
        "action_type": "reaction",
        "max_range_ft": 60,
    }


def prompt_resume_legacy_message(prompt: Dict[str, Any]) -> Dict[str, Any]:
    resume_dispatch = prompt.get("resume") if isinstance(prompt.get("resume"), dict) else None
    return apply_resume_dispatch(resume_dispatch) or {}
