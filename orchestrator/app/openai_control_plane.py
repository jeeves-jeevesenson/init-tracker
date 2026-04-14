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
    }
