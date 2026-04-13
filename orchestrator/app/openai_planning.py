from __future__ import annotations

import json
from typing import Any

from openai import OpenAI

from .config import Settings

PLANNING_SYSTEM_PROMPT = (
    "You are a software task planner for an orchestrator. "
    "Return strict JSON with keys: objective (string), scope (array of strings), "
    "non_goals (array of strings), acceptance_criteria (array of strings), "
    "validation_guidance (array of strings), implementation_brief (string)."
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


def plan_task_packet(*, settings: Settings, repo: str, issue_number: int, issue_title: str, issue_body: str) -> dict[str, Any]:
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required for planning")

    client = OpenAI(api_key=settings.openai_api_key)
    user_prompt = (
        f"Repository: {repo}\n"
        f"Issue: #{issue_number}\n"
        f"Title: {issue_title}\n\n"
        "Issue body:\n"
        f"{issue_body or '(empty)'}"
    )
    response = client.responses.create(
        model=settings.openai_planning_model,
        input=[
            {
                "role": "system",
                "content": [{"type": "input_text", "text": PLANNING_SYSTEM_PROMPT}],
            },
            {
                "role": "user",
                "content": [{"type": "input_text", "text": user_prompt}],
            },
        ],
    )
    text = _extract_text(response)
    if not text:
        raise RuntimeError("OpenAI planning response did not include text output")

    parsed = json.loads(_extract_json_block(text))
    required_keys = {
        "objective",
        "scope",
        "non_goals",
        "acceptance_criteria",
        "validation_guidance",
        "implementation_brief",
    }
    missing = sorted(required_keys - set(parsed.keys()))
    if missing:
        raise RuntimeError(f"OpenAI planning response missing keys: {', '.join(missing)}")
    return parsed
