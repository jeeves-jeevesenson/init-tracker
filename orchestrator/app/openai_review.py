from __future__ import annotations

import json
from typing import Any

from openai import OpenAI

from .config import Settings

REVIEW_SYSTEM_PROMPT = (
    "You are an orchestration reviewer. Return strict JSON with keys: "
    "summary_bullets (array of <=5 concise strings), next_action (one of review, send_back_to_agent, blocked, merge_ready-ish)."
)


def _extract_text(response: Any) -> str:
    output_text = getattr(response, "output_text", None)
    if output_text:
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


def summarize_work_update(*, settings: Settings, update_context: str) -> dict[str, Any]:
    if not settings.openai_api_key:
        bullets = [line.strip() for line in update_context.splitlines() if line.strip()][:3]
        return {"summary_bullets": bullets or ["No update details were provided."], "next_action": "review"}

    client = OpenAI(api_key=settings.openai_api_key)
    response = client.responses.create(
        model=settings.openai_review_model,
        input=[
            {
                "role": "system",
                "content": [{"type": "input_text", "text": REVIEW_SYSTEM_PROMPT}],
            },
            {
                "role": "user",
                "content": [{"type": "input_text", "text": update_context}],
            },
        ],
    )
    text = _extract_text(response)
    if not text:
        raise RuntimeError("OpenAI review response did not include text output")

    parsed = json.loads(_extract_json_block(text))
    bullets = parsed.get("summary_bullets")
    if not isinstance(bullets, list):
        raise RuntimeError("OpenAI review response missing summary_bullets")
    next_action = parsed.get("next_action")
    if not isinstance(next_action, str):
        raise RuntimeError("OpenAI review response missing next_action")
    return {"summary_bullets": bullets, "next_action": next_action}
