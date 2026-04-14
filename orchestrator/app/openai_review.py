from __future__ import annotations

import json
import logging
from typing import Any

from openai import OpenAI

from .config import Settings
from .openai_control_plane import apply_openai_request_controls, select_model_for_stage
from .schema_validation import validate_strict_json_schema

_ALLOWED_SCOPE_STATUS = {"met", "partial", "drifted", "blocked"}
_ALLOWED_MERGE_RECOMMENDATION = {"merge_ready", "review_required", "do_not_merge"}
_ALLOWED_DECISION = {"continue", "revise", "audit", "escalate", "complete"}
_ALLOWED_GOVERNOR_DECISION = {
    "wait",
    "request_revision",
    "escalate_human",
    "ready_for_review",
    "approve_and_merge",
    "complete_without_merge",
}
_ALLOWED_REASONING_EFFORT = {"low", "medium", "high"}
_logger = logging.getLogger("orchestrator.openai")

REVIEW_ARTIFACT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "decision",
        "status",
        "confidence",
        "scope_alignment",
        "acceptance_assessment",
        "risk_findings",
        "merge_recommendation",
        "revision_instructions",
        "audit_recommendation",
        "next_slice_hint",
        "summary",
    ],
    "properties": {
        "decision": {"type": "string", "enum": sorted(_ALLOWED_DECISION)},
        "status": {"type": "string", "enum": sorted(_ALLOWED_SCOPE_STATUS)},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "scope_alignment": {"type": "array", "items": {"type": "string"}},
        "acceptance_assessment": {"type": "array", "items": {"type": "string"}},
        "risk_findings": {"type": "array", "items": {"type": "string"}},
        "merge_recommendation": {
            "type": "string",
            "enum": sorted(_ALLOWED_MERGE_RECOMMENDATION),
        },
        "revision_instructions": {"type": "array", "items": {"type": "string"}},
        "audit_recommendation": {"type": "string"},
        "next_slice_hint": {"type": "string"},
        "summary": {"type": "array", "items": {"type": "string"}},
    },
}

REVIEW_SYSTEM_PROMPT = (
    "You are a PR/workflow reviewer for an orchestrator control plane. "
    "Return strict JSON matching the schema with clear merge/send-back recommendations."
)
GOVERNOR_SYSTEM_PROMPT = (
    "You are a PR governor for an orchestrator control plane. "
    "Decide safe, idempotent next action for autonomous PR progression."
)
REVIEW_BATCH_SYSTEM_PROMPT = (
    "You synthesize actionable GitHub PR review feedback into one concise top-level @copilot continuation comment. "
    "De-duplicate overlaps and keep output bounded."
)

GOVERNOR_ARTIFACT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "decision",
        "summary",
        "revision_requests",
        "escalation_reason",
    ],
    "properties": {
        "decision": {"type": "string", "enum": sorted(_ALLOWED_GOVERNOR_DECISION)},
        "summary": {"type": "array", "items": {"type": "string"}},
        "revision_requests": {"type": "array", "items": {"type": "string"}},
        "escalation_reason": {"type": "string"},
    },
}

REVIEW_BATCH_ARTIFACT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "summary",
        "batched_items",
        "comment_body",
        "should_trigger_copilot",
    ],
    "properties": {
        "summary": {"type": "array", "items": {"type": "string"}},
        "batched_items": {"type": "array", "items": {"type": "string"}},
        "comment_body": {"type": "string"},
        "should_trigger_copilot": {"type": "boolean"},
    },
}


def _extract_text(response: Any) -> str:
    output_text = getattr(response, "output_text", None)
    if isinstance(output_text, str) and output_text.strip():
        return output_text

    output = getattr(response, "output", None)
    if isinstance(output, list):
        parts: list[str] = []
        for item in output:
            content = getattr(item, "content", None)
            if not isinstance(content, list):
                continue
            for chunk in content:
                text = getattr(chunk, "text", None)
                if isinstance(text, str):
                    parts.append(text)
        if parts:
            return "\n".join(parts)
    return ""


def _extract_json_block(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if len(lines) >= 3:
            return "\n".join(lines[1:-1]).strip()
    return stripped


def _coerce_string_list(value: Any, field_name: str) -> list[str]:
    if not isinstance(value, list):
        raise RuntimeError(f"OpenAI review response field '{field_name}' must be an array")
    result: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str):
            raise RuntimeError(f"OpenAI review response field '{field_name}[{index}]' must be a string")
        stripped = item.strip()
        if stripped:
            result.append(stripped)
    return result


def _coerce_enum(value: Any, *, field_name: str, allowed: set[str]) -> str:
    if not isinstance(value, str):
        raise RuntimeError(f"OpenAI review response field '{field_name}' must be a string")
    normalized = value.strip().lower()
    if normalized not in allowed:
        raise RuntimeError(f"OpenAI review response field '{field_name}' is invalid")
    return normalized


def _extract_structured_object(response: Any, *, stage: str) -> dict[str, Any]:
    for attribute in ("output_parsed", "parsed"):
        parsed_value = getattr(response, attribute, None)
        if isinstance(parsed_value, dict):
            return parsed_value

    text = _extract_text(response)
    if not text:
        raise RuntimeError(f"OpenAI {stage} response did not include text output")
    try:
        parsed = json.loads(_extract_json_block(text))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"OpenAI {stage} response was not valid JSON") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError(f"OpenAI {stage} response must be a JSON object")
    return parsed


def _response_payload(
    *,
    model: str,
    update_context: str,
    settings: Settings,
    reasoning_effort: str,
    stage: str,
    repo: str | None,
    previous_response_id: str | None,
    model_tier: str,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": model,
        "input": [
            {
                "role": "system",
                "content": [{"type": "input_text", "text": REVIEW_SYSTEM_PROMPT}],
            },
            {
                "role": "user",
                "content": [{"type": "input_text", "text": update_context}],
            },
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "pr_review_artifact",
                "strict": True,
                "schema": REVIEW_ARTIFACT_SCHEMA,
            }
        },
    }
    normalized_effort = reasoning_effort.strip().lower()
    if normalized_effort in _ALLOWED_REASONING_EFFORT:
        payload["reasoning"] = {"effort": normalized_effort}
    if settings.openai_enable_background_requests:
        payload["background"] = True
    request_controls = apply_openai_request_controls(
        payload=payload,
        settings=settings,
        stage=stage,
        repo=repo,
        previous_response_id=previous_response_id,
    )
    request_controls["model_tier"] = model_tier
    payload["_openai_request_controls"] = request_controls
    return payload


def _validate_review_artifact(raw: dict[str, Any]) -> dict[str, Any]:
    summary = _coerce_string_list(raw.get("summary"), "summary")[:4]
    if not summary:
        summary = ["Review completed; see artifact for details."]
    confidence_value = raw.get("confidence")
    if not isinstance(confidence_value, (int, float)):
        raise RuntimeError("OpenAI review response field 'confidence' must be a number")
    confidence = min(1.0, max(0.0, float(confidence_value)))
    return {
        "decision": _coerce_enum(raw.get("decision"), field_name="decision", allowed=_ALLOWED_DECISION),
        "status": _coerce_enum(raw.get("status"), field_name="status", allowed=_ALLOWED_SCOPE_STATUS),
        "confidence": confidence,
        "scope_alignment": _coerce_string_list(raw.get("scope_alignment"), "scope_alignment")[:8],
        "acceptance_assessment": _coerce_string_list(raw.get("acceptance_assessment"), "acceptance_assessment")[:8],
        "risk_findings": _coerce_string_list(raw.get("risk_findings"), "risk_findings")[:8],
        "merge_recommendation": _coerce_enum(
            raw.get("merge_recommendation"),
            field_name="merge_recommendation",
            allowed=_ALLOWED_MERGE_RECOMMENDATION,
        ),
        "revision_instructions": _coerce_string_list(raw.get("revision_instructions"), "revision_instructions")[:10],
        "audit_recommendation": str(raw.get("audit_recommendation") or ""),
        "next_slice_hint": str(raw.get("next_slice_hint") or ""),
        "summary": summary,
    }


def _fallback_review_artifact(update_context: str) -> dict[str, Any]:
    lines = [line.strip() for line in update_context.splitlines() if line.strip()]
    bullets = lines[:3] or ["No update details were provided."]
    return {
        "decision": "revise",
        "status": "partial",
        "confidence": 0.2,
        "scope_alignment": bullets,
        "acceptance_assessment": bullets,
        "risk_findings": ["Validation evidence not supplied in event context."],
        "merge_recommendation": "review_required",
        "revision_instructions": ["Collect stronger validation evidence before merge."],
        "audit_recommendation": "",
        "next_slice_hint": "",
        "summary": bullets,
    }


def _extract_repo_from_context(update_context: str) -> str | None:
    try:
        parsed = json.loads(update_context)
    except Exception:
        return None
    if isinstance(parsed, dict):
        repo = parsed.get("repo")
        if isinstance(repo, str) and repo.strip():
            return repo.strip()
    return None


def summarize_work_update(
    *,
    settings: Settings,
    update_context: str,
    previous_response_id: str | None = None,
) -> dict[str, Any]:
    validate_strict_json_schema(schema_name="pr_review_artifact", schema=REVIEW_ARTIFACT_SCHEMA)
    if not settings.openai_api_key:
        artifact = _fallback_review_artifact(update_context)
        return {
            "review_artifact": artifact,
            "summary_bullets": artifact["summary"],
            "next_action": artifact["decision"],
            "openai_meta": {
                "stage": "reviewer",
                "model_tier": "fallback",
                "model": None,
                "response_id": None,
                "prompt_cache_attempted": False,
                "previous_response_id_attempted": False,
            },
        }

    review_model, model_tier = select_model_for_stage(
        settings=settings,
        stage="reviewer",
        fallback_model=settings.openai_review_model,
    )
    repo = _extract_repo_from_context(update_context)
    client = OpenAI(api_key=settings.openai_api_key)
    payload = _response_payload(
        model=review_model,
        update_context=update_context,
        settings=settings,
        reasoning_effort=settings.openai_review_reasoning_effort,
        stage="reviewer",
        repo=repo,
        previous_response_id=previous_response_id,
        model_tier=model_tier,
    )
    request_controls = payload.pop("_openai_request_controls", {})
    response = client.responses.create(**payload)
    parsed = _extract_structured_object(response, stage="review")
    if settings.openai_enable_background_requests and not parsed:
        response_id = getattr(response, "id", None)
        raise RuntimeError(
            "OpenAI background responses require async completion handling before review can continue"
            f" (response_id={response_id or 'unknown'})"
        )

    artifact = _validate_review_artifact(parsed)
    next_action = artifact["decision"]
    response_id = getattr(response, "id", None)
    _logger.info(
        "openai_call stage=reviewer model=%s response_id=%s model_tier=%s",
        review_model,
        response_id or "",
        model_tier,
    )

    return {
        "review_artifact": artifact,
        "summary_bullets": artifact["summary"],
        "next_action": next_action,
        "openai_meta": {
            **request_controls,
            "stage": "reviewer",
            "model_tier": model_tier,
            "model": review_model,
            "response_id": response_id,
        },
    }


def _governor_response_payload(
    *,
    model: str,
    update_context: str,
    settings: Settings,
    reasoning_effort: str,
    stage: str,
    repo: str | None,
    previous_response_id: str | None,
    model_tier: str,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": model,
        "input": [
            {
                "role": "system",
                "content": [{"type": "input_text", "text": GOVERNOR_SYSTEM_PROMPT}],
            },
            {
                "role": "user",
                "content": [{"type": "input_text", "text": update_context}],
            },
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "pr_governor_artifact",
                "strict": True,
                "schema": GOVERNOR_ARTIFACT_SCHEMA,
            }
        },
    }
    normalized_effort = reasoning_effort.strip().lower()
    if normalized_effort in _ALLOWED_REASONING_EFFORT:
        payload["reasoning"] = {"effort": normalized_effort}
    if settings.openai_enable_background_requests:
        payload["background"] = True
    request_controls = apply_openai_request_controls(
        payload=payload,
        settings=settings,
        stage=stage,
        repo=repo,
        previous_response_id=previous_response_id,
    )
    request_controls["model_tier"] = model_tier
    payload["_openai_request_controls"] = request_controls
    return payload


def _validate_governor_artifact(raw: dict[str, Any]) -> dict[str, Any]:
    summary = _coerce_string_list(raw.get("summary"), "summary")[:5]
    if not summary:
        summary = ["Governor decision generated."]
    return {
        "decision": _coerce_enum(
            raw.get("decision"),
            field_name="decision",
            allowed=_ALLOWED_GOVERNOR_DECISION,
        ),
        "summary": summary,
        "revision_requests": _coerce_string_list(raw.get("revision_requests"), "revision_requests")[:10],
        "escalation_reason": str(raw.get("escalation_reason") or ""),
    }


def _fallback_governor_artifact(update_context: str) -> dict[str, Any]:
    try:
        parsed = json.loads(update_context)
    except Exception:
        parsed = {}
    if not isinstance(parsed, dict):
        parsed = {}
    pr = parsed.get("pr") if isinstance(parsed.get("pr"), dict) else {}
    unresolved = parsed.get("unresolved_copilot_findings")
    unresolved_count = len(unresolved) if isinstance(unresolved, list) else 0
    checks_passed = bool(parsed.get("checks_passed"))
    draft = bool(pr.get("draft"))
    guarded = bool(parsed.get("guarded_paths_touched"))
    decision = "wait"
    if guarded:
        decision = "escalate_human"
    elif unresolved_count > 0:
        decision = "request_revision"
    elif checks_passed and not draft:
        decision = "approve_and_merge"
    elif checks_passed and draft:
        decision = "ready_for_review"
    return {
        "decision": decision,
        "summary": ["Governor fallback decision generated from available context."],
        "revision_requests": [],
        "escalation_reason": "",
    }


def summarize_governor_update(
    *,
    settings: Settings,
    update_context: str,
    previous_response_id: str | None = None,
) -> dict[str, Any]:
    validate_strict_json_schema(schema_name="pr_governor_artifact", schema=GOVERNOR_ARTIFACT_SCHEMA)
    if not settings.openai_api_key:
        artifact = _fallback_governor_artifact(update_context)
        return {
            "governor_artifact": artifact,
            "summary_bullets": artifact["summary"],
            "next_action": artifact["decision"],
            "openai_meta": {
                "stage": "continuation_audit",
                "model_tier": "fallback",
                "model": None,
                "response_id": None,
                "prompt_cache_attempted": False,
                "previous_response_id_attempted": False,
            },
        }

    governor_model, model_tier = select_model_for_stage(
        settings=settings,
        stage="continuation_audit",
        fallback_model=settings.openai_review_model,
    )
    repo = _extract_repo_from_context(update_context)
    client = OpenAI(api_key=settings.openai_api_key)
    payload = _governor_response_payload(
        model=governor_model,
        update_context=update_context,
        settings=settings,
        reasoning_effort=settings.openai_review_reasoning_effort,
        stage="continuation_audit",
        repo=repo,
        previous_response_id=previous_response_id,
        model_tier=model_tier,
    )
    request_controls = payload.pop("_openai_request_controls", {})
    response = client.responses.create(**payload)
    parsed = _extract_structured_object(response, stage="governor")
    if settings.openai_enable_background_requests and not parsed:
        response_id = getattr(response, "id", None)
        raise RuntimeError(
            "OpenAI background responses require async completion handling before governor can continue"
            f" (response_id={response_id or 'unknown'})"
        )

    artifact = _validate_governor_artifact(parsed)
    response_id = getattr(response, "id", None)
    _logger.info(
        "openai_call stage=continuation_audit model=%s response_id=%s model_tier=%s",
        governor_model,
        response_id or "",
        model_tier,
    )
    return {
        "governor_artifact": artifact,
        "summary_bullets": artifact["summary"],
        "next_action": artifact["decision"],
        "openai_meta": {
            **request_controls,
            "stage": "continuation_audit",
            "model_tier": model_tier,
            "model": governor_model,
            "response_id": response_id,
        },
    }


def _review_batch_response_payload(
    *,
    model: str,
    update_context: str,
    settings: Settings,
    reasoning_effort: str,
    stage: str,
    repo: str | None,
    previous_response_id: str | None,
    model_tier: str,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": model,
        "input": [
            {
                "role": "system",
                "content": [{"type": "input_text", "text": REVIEW_BATCH_SYSTEM_PROMPT}],
            },
            {
                "role": "user",
                "content": [{"type": "input_text", "text": update_context}],
            },
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "pr_review_batch_artifact",
                "strict": True,
                "schema": REVIEW_BATCH_ARTIFACT_SCHEMA,
            }
        },
    }
    normalized_effort = reasoning_effort.strip().lower()
    if normalized_effort in _ALLOWED_REASONING_EFFORT:
        payload["reasoning"] = {"effort": normalized_effort}
    if settings.openai_enable_background_requests:
        payload["background"] = True
    request_controls = apply_openai_request_controls(
        payload=payload,
        settings=settings,
        stage=stage,
        repo=repo,
        previous_response_id=previous_response_id,
    )
    request_controls["model_tier"] = model_tier
    payload["_openai_request_controls"] = request_controls
    return payload


def _fallback_review_batch_artifact(update_context: str) -> dict[str, Any]:
    try:
        parsed = json.loads(update_context)
    except Exception:
        parsed = {}
    if not isinstance(parsed, dict):
        parsed = {}
    unresolved = parsed.get("unresolved_findings")
    findings = [str(item).strip() for item in unresolved if str(item).strip()] if isinstance(unresolved, list) else []
    deduped: list[str] = []
    seen: set[str] = set()
    for finding in findings:
        key = " ".join(finding.split()).lower()
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(" ".join(finding.split()))
    batched_items = deduped[:12]
    should_trigger = bool(batched_items)
    if should_trigger:
        lines = ["@copilot Please apply the following review fixes in this PR branch:"]
        for index, item in enumerate(batched_items, start=1):
            lines.append(f"{index}. {item}")
        lines.append("")
        lines.append("If any item is invalid, explain briefly in PR comments.")
        comment_body = "\n".join(lines)
    else:
        comment_body = "@copilot Re-check this PR and post any remaining actionable findings."
    summary = ["Review feedback batched for one top-level continuation comment."]
    return {
        "summary": summary,
        "batched_items": batched_items,
        "comment_body": comment_body,
        "should_trigger_copilot": should_trigger,
    }


def _validate_review_batch_artifact(raw: dict[str, Any]) -> dict[str, Any]:
    summary = _coerce_string_list(raw.get("summary"), "summary")[:4]
    if not summary:
        summary = ["Review feedback batched for continuation."]
    batched_items = _coerce_string_list(raw.get("batched_items"), "batched_items")[:12]
    should_trigger = bool(raw.get("should_trigger_copilot"))
    comment_body = str(raw.get("comment_body") or "").strip()
    if should_trigger and not comment_body:
        raise RuntimeError("OpenAI review batch response field 'comment_body' must be non-empty when triggering")
    if not comment_body:
        comment_body = "@copilot Re-check this PR and post any remaining actionable findings."
    if not comment_body.startswith("@copilot"):
        comment_body = f"@copilot {comment_body}"
    return {
        "summary": summary,
        "batched_items": batched_items,
        "comment_body": comment_body,
        "should_trigger_copilot": should_trigger,
    }


def summarize_copilot_review_batch(
    *,
    settings: Settings,
    update_context: str,
    previous_response_id: str | None = None,
    force_flagship: bool = False,
) -> dict[str, Any]:
    validate_strict_json_schema(schema_name="pr_review_batch_artifact", schema=REVIEW_BATCH_ARTIFACT_SCHEMA)
    if not settings.openai_api_key:
        artifact = _fallback_review_batch_artifact(update_context)
        return {
            "review_batch_artifact": artifact,
            "summary_bullets": artifact["summary"],
            "next_action": "trigger" if artifact["should_trigger_copilot"] else "skip",
            "openai_meta": {
                "stage": "review_batching",
                "model_tier": "fallback",
                "model": None,
                "response_id": None,
                "prompt_cache_attempted": False,
                "previous_response_id_attempted": False,
            },
        }

    stage = "reviewer" if force_flagship else "review_batching"
    fallback_model = settings.openai_review_model if force_flagship else settings.openai_helper_model
    model, model_tier = select_model_for_stage(
        settings=settings,
        stage=stage,
        fallback_model=fallback_model,
    )
    repo = _extract_repo_from_context(update_context)
    client = OpenAI(api_key=settings.openai_api_key)
    payload = _review_batch_response_payload(
        model=model,
        update_context=update_context,
        settings=settings,
        reasoning_effort=settings.openai_review_reasoning_effort,
        stage=stage,
        repo=repo,
        previous_response_id=previous_response_id,
        model_tier=model_tier,
    )
    request_controls = payload.pop("_openai_request_controls", {})
    response = client.responses.create(**payload)
    parsed = _extract_structured_object(response, stage="review batching")
    if settings.openai_enable_background_requests and not parsed:
        response_id = getattr(response, "id", None)
        raise RuntimeError(
            "OpenAI background responses require async completion handling before review batching can continue"
            f" (response_id={response_id or 'unknown'})"
        )
    artifact = _validate_review_batch_artifact(parsed)
    response_id = getattr(response, "id", None)
    _logger.info(
        "openai_call stage=%s model=%s response_id=%s model_tier=%s",
        stage,
        model,
        response_id or "",
        model_tier,
    )
    return {
        "review_batch_artifact": artifact,
        "summary_bullets": artifact["summary"],
        "next_action": "trigger" if artifact["should_trigger_copilot"] else "skip",
        "openai_meta": {
            **request_controls,
            "stage": stage,
            "model_tier": model_tier,
            "model": model,
            "response_id": response_id,
        },
    }
