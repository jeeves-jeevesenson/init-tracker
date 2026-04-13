from __future__ import annotations

import json
from typing import Any

from openai import OpenAI

from .config import Settings

_ALLOWED_SCOPE_STATUS = {"met", "partially_met", "not_met", "unclear"}
_ALLOWED_MERGE_RECOMMENDATION = {"merge_ready", "review_required", "do_not_merge"}
_ALLOWED_SEND_BACK = {"send_back", "not_needed"}
_ALLOWED_REASONING_EFFORT = {"low", "medium", "high"}

REVIEW_ARTIFACT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "what_changed",
        "scope_status",
        "likely_risks",
        "missing_validation",
        "merge_recommendation",
        "send_back_recommendation",
        "concise_summary",
    ],
    "properties": {
        "what_changed": {"type": "array", "items": {"type": "string"}},
        "scope_status": {"type": "string", "enum": sorted(_ALLOWED_SCOPE_STATUS)},
        "likely_risks": {"type": "array", "items": {"type": "string"}},
        "missing_validation": {"type": "array", "items": {"type": "string"}},
        "merge_recommendation": {
            "type": "string",
            "enum": sorted(_ALLOWED_MERGE_RECOMMENDATION),
        },
        "send_back_recommendation": {"type": "string", "enum": sorted(_ALLOWED_SEND_BACK)},
        "concise_summary": {"type": "array", "items": {"type": "string"}},
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
    concise_summary = _coerce_string_list(raw.get("concise_summary"), "concise_summary")[:4]
    what_changed = _coerce_string_list(raw.get("what_changed"), "what_changed")[:8]
    likely_risks = _coerce_string_list(raw.get("likely_risks"), "likely_risks")[:8]
    missing_validation = _coerce_string_list(raw.get("missing_validation"), "missing_validation")[:8]
    if not concise_summary:
        concise_summary = ["Review completed; see artifact for details."]
    return {
        "what_changed": what_changed,
        "scope_status": _coerce_enum(raw.get("scope_status"), field_name="scope_status", allowed=_ALLOWED_SCOPE_STATUS),
        "likely_risks": likely_risks,
        "missing_validation": missing_validation,
        "merge_recommendation": _coerce_enum(
            raw.get("merge_recommendation"),
            field_name="merge_recommendation",
            allowed=_ALLOWED_MERGE_RECOMMENDATION,
        ),
        "send_back_recommendation": _coerce_enum(
            raw.get("send_back_recommendation"),
            field_name="send_back_recommendation",
            allowed=_ALLOWED_SEND_BACK,
        ),
        "concise_summary": concise_summary,
    }


def _fallback_review_artifact(update_context: str) -> dict[str, Any]:
    lines = [line.strip() for line in update_context.splitlines() if line.strip()]
    bullets = lines[:3] or ["No update details were provided."]
    return {
        "what_changed": bullets,
        "scope_status": "unclear",
        "likely_risks": [],
        "missing_validation": ["Validation evidence not supplied in event context."],
        "merge_recommendation": "review_required",
        "send_back_recommendation": "not_needed",
        "concise_summary": bullets,
    }


def summarize_work_update(*, settings: Settings, update_context: str) -> dict[str, Any]:
    if not settings.openai_api_key:
        artifact = _fallback_review_artifact(update_context)
        return {
            "review_artifact": artifact,
            "summary_bullets": artifact["concise_summary"],
            "next_action": "review",
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
    if artifact["send_back_recommendation"] == "send_back":
        next_action = "send_back_to_agent"
    elif artifact["merge_recommendation"] == "do_not_merge":
        next_action = "blocked"
    else:
        next_action = "review"

    return {
        "review_artifact": artifact,
        "summary_bullets": artifact["concise_summary"],
        "next_action": next_action,
    }
