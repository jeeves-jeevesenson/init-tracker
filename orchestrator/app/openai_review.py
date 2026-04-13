from __future__ import annotations

import json
from typing import Any

from openai import OpenAI

from .config import Settings
from .schema_validation import validate_strict_json_schema

_ALLOWED_SCOPE_STATUS = {"met", "partial", "drifted", "blocked"}
_ALLOWED_MERGE_RECOMMENDATION = {"merge_ready", "review_required", "do_not_merge"}
_ALLOWED_DECISION = {"continue", "revise", "audit", "escalate", "complete"}
_ALLOWED_REASONING_EFFORT = {"low", "medium", "high"}

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


def summarize_work_update(*, settings: Settings, update_context: str) -> dict[str, Any]:
    validate_strict_json_schema(schema_name="pr_review_artifact", schema=REVIEW_ARTIFACT_SCHEMA)
    if not settings.openai_api_key:
        artifact = _fallback_review_artifact(update_context)
        return {
            "review_artifact": artifact,
            "summary_bullets": artifact["summary"],
            "next_action": artifact["decision"],
        }

    client = OpenAI(api_key=settings.openai_api_key)
    response = client.responses.create(
        **_response_payload(
            model=settings.openai_review_model,
            update_context=update_context,
            settings=settings,
            reasoning_effort=settings.openai_review_reasoning_effort,
        )
    )
    parsed = _extract_structured_object(response, stage="review")
    if settings.openai_enable_background_requests and not parsed:
        response_id = getattr(response, "id", None)
        raise RuntimeError(
            "OpenAI background responses require async completion handling before review can continue"
            f" (response_id={response_id or 'unknown'})"
        )

    artifact = _validate_review_artifact(parsed)
    next_action = artifact["decision"]

    return {
        "review_artifact": artifact,
        "summary_bullets": artifact["summary"],
        "next_action": next_action,
    }
