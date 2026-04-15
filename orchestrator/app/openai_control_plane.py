from __future__ import annotations

import hashlib
import logging
from typing import Any

from .config import Settings

_logger = logging.getLogger("orchestrator.openai")

_FLAGSHIP_STAGES = {"planner", "reviewer", "governor", "continuation_audit"}
_HELPER_STAGES = {"worker_brief", "normalization", "summarization", "routing", "review_batching"}


def select_model_for_stage(*, settings: Settings, stage: str, fallback_model: str) -> tuple[str, str]:
    normalized_stage = (stage or "").strip().lower()
    flagship_model = (settings.openai_flagship_model or "").strip() or fallback_model
    helper_model = (settings.openai_helper_model or "").strip() or flagship_model
    if normalized_stage in _HELPER_STAGES:
        return helper_model, "helper"
    if normalized_stage in _FLAGSHIP_STAGES:
        return flagship_model, "flagship"
    return fallback_model, "default"


def build_prompt_cache_key(*, stage: str, repo: str | None = None) -> str:
    normalized_stage = (stage or "unknown").strip().lower().replace(" ", "_")
    normalized_repo = (repo or "global").strip().lower()
    cache_seed = f"orchestrator.openai.v1:{normalized_stage}:{normalized_repo}"
    cache_hash = hashlib.sha1(cache_seed.encode("utf-8")).hexdigest()[:16]
    return f"orchestrator:{normalized_stage}:{cache_hash}"


def fingerprint_text(value: str | None) -> str | None:
    text = (value or "").strip()
    if not text:
        return None
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def extract_usage_metrics(response: Any) -> dict[str, int | None]:
    usage = getattr(response, "usage", None)
    if usage is None:
        usage = {}
    if not isinstance(usage, dict):
        usage = {
            "input_tokens": getattr(usage, "input_tokens", None),
            "output_tokens": getattr(usage, "output_tokens", None),
            "total_tokens": getattr(usage, "total_tokens", None),
            "input_tokens_details": getattr(usage, "input_tokens_details", None),
        }
    details = usage.get("input_tokens_details")
    cached_tokens: int | None = None
    if isinstance(details, dict):
        raw_cached = details.get("cached_tokens")
        cached_tokens = int(raw_cached) if isinstance(raw_cached, int) else None
    elif details is not None:
        raw_cached = getattr(details, "cached_tokens", None)
        cached_tokens = int(raw_cached) if isinstance(raw_cached, int) else None
    input_tokens = usage.get("input_tokens")
    output_tokens = usage.get("output_tokens")
    total_tokens = usage.get("total_tokens")
    return {
        "input_tokens": int(input_tokens) if isinstance(input_tokens, int) else None,
        "output_tokens": int(output_tokens) if isinstance(output_tokens, int) else None,
        "total_tokens": int(total_tokens) if isinstance(total_tokens, int) else None,
        "cached_input_tokens": cached_tokens,
    }


def validate_replay_items(items: list[dict[str, Any]]) -> dict[str, Any]:
    assistant_message_indexes: list[int] = []
    reasoning_count = 0
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        item_type = str(item.get("type") or "").strip().lower()
        if item_type == "reasoning":
            reasoning_count += 1
            continue
        if item_type != "message":
            continue
        role = str(item.get("role") or "").strip().lower()
        if role == "assistant":
            assistant_message_indexes.append(index)
    if not assistant_message_indexes:
        return {"ok": True}
    if reasoning_count < len(assistant_message_indexes):
        return {
            "ok": False,
            "error_code": "missing_reasoning_pair",
            "missing_reasoning_for_message_indexes": assistant_message_indexes[reasoning_count:],
            "assistant_message_count": len(assistant_message_indexes),
            "reasoning_item_count": reasoning_count,
        }
    return {"ok": True}


def preflight_validate_replay_payload(payload: dict[str, Any]) -> dict[str, Any]:
    input_payload = payload.get("input")
    if not isinstance(input_payload, list):
        return {"ok": True, "mode": "no_replay"}
    replay_like_items = [item for item in input_payload if isinstance(item, dict) and item.get("type") in {"message", "reasoning"}]
    if not replay_like_items:
        return {"ok": True, "mode": "fresh_prompt"}
    validation = validate_replay_items(replay_like_items)
    if validation.get("ok"):
        return {"ok": True, "mode": "replay"}
    non_replay_items = [item for item in input_payload if item not in replay_like_items]
    if non_replay_items:
        payload["input"] = non_replay_items
        return {
            "ok": False,
            "mode": "fallback_fresh_prompt",
            "error_code": validation.get("error_code"),
            "details": validation,
            "fallback_taken": "dropped_malformed_replay_items",
        }
    return {
        "ok": False,
        "mode": "replay_blocked",
        "error_code": validation.get("error_code"),
        "details": validation,
        "fallback_taken": "none",
    }


def apply_openai_request_controls(
    *,
    payload: dict[str, Any],
    settings: Settings,
    stage: str,
    repo: str | None = None,
    previous_response_id: str | None = None,
) -> dict[str, Any]:
    cache_key: str | None = None
    used_previous_response_id = False
    normalized_prev = (previous_response_id or "").strip()

    if settings.openai_enable_prompt_caching:
        cache_key = build_prompt_cache_key(stage=stage, repo=repo)
        payload["prompt_cache_key"] = cache_key
        retention = (settings.openai_prompt_cache_retention or "").strip()
        if retention:
            payload["prompt_cache_retention"] = retention

    if settings.openai_enable_response_chaining and normalized_prev:
        payload["previous_response_id"] = normalized_prev
        used_previous_response_id = True

    replay_validation = preflight_validate_replay_payload(payload)
    if not replay_validation.get("ok") and replay_validation.get("mode") == "replay_blocked":
        raise RuntimeError(
            "Malformed OpenAI replay payload blocked before API call: "
            f"{replay_validation.get('error_code') or 'invalid_replay_payload'}"
        )

    _logger.info(
        "openai_request_controls stage=%s cache_attempted=%s cache_key=%s previous_response_attempted=%s",
        stage,
        settings.openai_enable_prompt_caching,
        cache_key or "",
        bool(settings.openai_enable_response_chaining and normalized_prev),
    )
    return {
        "stage": stage,
        "prompt_cache_attempted": bool(settings.openai_enable_prompt_caching),
        "prompt_cache_key": cache_key,
        "prompt_cache_retention": (settings.openai_prompt_cache_retention or "").strip() or None,
        "previous_response_id_attempted": bool(settings.openai_enable_response_chaining and normalized_prev),
        "used_previous_response_id": used_previous_response_id,
        "previous_response_id": normalized_prev or None,
        "replay_validation": replay_validation,
    }
