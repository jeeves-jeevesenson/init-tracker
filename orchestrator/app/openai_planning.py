from __future__ import annotations

import json
import logging
from typing import Any

from openai import OpenAI

from .config import Settings
from .openai_control_plane import apply_openai_request_controls, select_model_for_stage
from .schema_validation import validate_strict_json_schema

_ALLOWED_WORKERS = {"initiative-smith", "tracker-engineer"}
_ALLOWED_SCOPE_CLASS = {"broad", "narrow"}
_ALLOWED_TASK_TYPE = {
    "bugfix",
    "feature",
    "refactor",
    "migration",
    "ops",
    "investigation",
    "docs",
    "test",
}
_ALLOWED_DIFFICULTY = {"small", "medium", "large", "xlarge"}
_ALLOWED_REASONING_EFFORT = {"low", "medium", "high"}
_INTERNAL_LABEL_TERMS = {
    "initiative smith",
    "initiative tracker engineer",
    "initiative-smith",
    "tracker-engineer",
}

_logger = logging.getLogger("orchestrator.openai")

INTERNAL_TASK_PLAN_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "objective",
        "scope",
        "non_goals",
        "acceptance_criteria",
        "validation_guidance",
        "implementation_brief",
        "task_type",
        "difficulty",
        "repo_areas",
        "execution_risks",
        "reviewer_focus",
        "recommended_scope_class",
        "recommended_worker",
        "internal_routing_metadata",
    ],
    "properties": {
        "objective": {"type": "string", "minLength": 1},
        "scope": {"type": "array", "items": {"type": "string"}},
        "non_goals": {"type": "array", "items": {"type": "string"}},
        "acceptance_criteria": {"type": "array", "items": {"type": "string"}},
        "validation_guidance": {"type": "array", "items": {"type": "string"}},
        "implementation_brief": {"type": "string", "minLength": 1},
        "task_type": {"type": "string", "enum": sorted(_ALLOWED_TASK_TYPE)},
        "difficulty": {"type": "string", "enum": sorted(_ALLOWED_DIFFICULTY)},
        "repo_areas": {"type": "array", "items": {"type": "string"}},
        "execution_risks": {"type": "array", "items": {"type": "string"}},
        "reviewer_focus": {"type": "array", "items": {"type": "string"}},
        "recommended_scope_class": {"type": ["string", "null"], "enum": [*sorted(_ALLOWED_SCOPE_CLASS), None]},
        "recommended_worker": {"type": ["string", "null"], "enum": [*sorted(_ALLOWED_WORKERS), None]},
        "internal_routing_metadata": {
            "anyOf": [
                {
                    "type": "object",
                    "additionalProperties": {"type": ["string", "number", "boolean", "null"]},
                },
                {"type": "null"},
            ]
        },
    },
}

WORKER_BRIEF_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "objective",
        "concise_scope",
        "implementation_brief",
        "acceptance_criteria",
        "validation_commands",
        "non_goals",
        "target_branch",
        "repo_grounded_hints",
    ],
    "properties": {
        "objective": {"type": "string", "minLength": 1},
        "concise_scope": {"type": "array", "items": {"type": "string"}},
        "implementation_brief": {"type": "string", "minLength": 1},
        "acceptance_criteria": {"type": "array", "items": {"type": "string"}},
        "validation_commands": {"type": "array", "items": {"type": "string"}},
        "non_goals": {"type": "array", "items": {"type": "string"}},
        "target_branch": {"type": "string", "minLength": 1},
        "repo_grounded_hints": {"type": "array", "items": {"type": "string"}},
    },
}

PROGRAM_PLAN_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "normalized_program_objective",
        "definition_of_done",
        "non_goals",
        "milestones",
        "slices",
        "current_slice_brief",
        "acceptance_criteria",
        "risk_profile",
        "recommended_worker",
        "recommended_scope_class",
        "continuation_hints",
    ],
    "properties": {
        "normalized_program_objective": {"type": "string", "minLength": 1},
        "definition_of_done": {"type": "array", "items": {"type": "string"}},
        "non_goals": {"type": "array", "items": {"type": "string"}},
        "milestones": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["key", "title", "goal"],
                "properties": {
                    "key": {"type": "string", "minLength": 1},
                    "title": {"type": "string", "minLength": 1},
                    "goal": {"type": "string", "minLength": 1},
                },
            },
        },
        "slices": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "slice_number",
                    "milestone_key",
                    "title",
                    "objective",
                    "acceptance_criteria",
                    "non_goals",
                    "expected_file_zones",
                    "continuation_hint",
                    "slice_type",
                ],
                "properties": {
                    "slice_number": {"type": "integer", "minimum": 1},
                    "milestone_key": {"type": "string", "minLength": 1},
                    "title": {"type": "string", "minLength": 1},
                    "objective": {"type": "string", "minLength": 1},
                    "acceptance_criteria": {"type": "array", "items": {"type": "string"}},
                    "non_goals": {"type": "array", "items": {"type": "string"}},
                    "expected_file_zones": {"type": "array", "items": {"type": "string"}},
                    "continuation_hint": {"type": "string"},
                    "slice_type": {"type": "string", "enum": ["implementation", "audit"]},
                },
            },
        },
        "current_slice_brief": {"type": "string", "minLength": 1},
        "acceptance_criteria": {"type": "array", "items": {"type": "string"}},
        "risk_profile": {"type": "array", "items": {"type": "string"}},
        "recommended_worker": {"type": ["string", "null"], "enum": [*sorted(_ALLOWED_WORKERS), None]},
        "recommended_scope_class": {"type": ["string", "null"], "enum": [*sorted(_ALLOWED_SCOPE_CLASS), None]},
        "continuation_hints": {"type": "array", "items": {"type": "string"}},
    },
}

PLANNING_SYSTEM_PROMPT = (
    "You are the internal planner for a software orchestrator. "
    "Produce a strict JSON object matching the provided schema. "
    "Prioritize repository-grounded execution guidance, concrete acceptance criteria, "
    "and deterministic task classification."
)

WORKER_BRIEF_SYSTEM_PROMPT = (
    "You are generating a worker brief for plain GitHub Copilot execution. "
    "Return strict JSON matching the worker brief schema. "
    "Exclude orchestration-only metadata and never mention internal worker personas. "
    "Keep output concise and execution-focused."
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
        raise RuntimeError(f"Planning output field '{field_name}' must be an array")
    result: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str):
            raise RuntimeError(f"Planning output field '{field_name}[{index}]' must be a string")
        stripped = item.strip()
        if stripped:
            result.append(stripped)
    return result


def _coerce_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise RuntimeError(f"Planning output field '{field_name}' must be a string")
    stripped = value.strip()
    if not stripped:
        raise RuntimeError(f"Planning output field '{field_name}' must not be empty")
    return stripped


def _coerce_optional_worker(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise RuntimeError("Planning output field 'recommended_worker' must be a string when provided")
    normalized = value.strip().lower().replace("_", "-")
    if normalized not in _ALLOWED_WORKERS:
        raise RuntimeError("Planning output field 'recommended_worker' is invalid")
    return normalized


def _coerce_scope_class(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise RuntimeError("Planning output field 'recommended_scope_class' must be a string")
    normalized = value.strip().lower()
    if normalized not in _ALLOWED_SCOPE_CLASS:
        raise RuntimeError("Planning output field 'recommended_scope_class' is invalid")
    return normalized


def _coerce_task_type(value: Any) -> str:
    if not isinstance(value, str):
        raise RuntimeError("Planning output field 'task_type' must be a string")
    normalized = value.strip().lower()
    if normalized not in _ALLOWED_TASK_TYPE:
        raise RuntimeError("Planning output field 'task_type' is invalid")
    return normalized


def _validate_schema_required_keys(*, schema_name: str, schema: dict[str, Any]) -> None:
    validate_strict_json_schema(schema_name=schema_name, schema=schema)


def _coerce_difficulty(value: Any) -> str:
    if not isinstance(value, str):
        raise RuntimeError("Planning output field 'difficulty' must be a string")
    normalized = value.strip().lower()
    if normalized not in _ALLOWED_DIFFICULTY:
        raise RuntimeError("Planning output field 'difficulty' is invalid")
    return normalized


def _coerce_optional_routing_metadata(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise RuntimeError("Planning output field 'internal_routing_metadata' must be an object when provided")
    normalized: dict[str, Any] = {}
    for key, raw in value.items():
        if not isinstance(key, str):
            continue
        if isinstance(raw, (str, int, float, bool)) or raw is None:
            normalized[key] = raw
    return normalized or None


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
    system_prompt: str,
    user_prompt: str,
    schema_name: str,
    schema: dict[str, Any],
    reasoning_effort: str,
    settings: Settings,
    stage: str,
    repo: str,
    previous_response_id: str | None,
    model_tier: str,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": model,
        "input": [
            {
                "role": "system",
                "content": [{"type": "input_text", "text": system_prompt}],
            },
            {
                "role": "user",
                "content": [{"type": "input_text", "text": user_prompt}],
            },
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": schema_name,
                "strict": True,
                "schema": schema,
            }
        },
    }
    if reasoning_effort in _ALLOWED_REASONING_EFFORT:
        payload["reasoning"] = {"effort": reasoning_effort}
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


def _invoke_structured_response(
    *,
    client: OpenAI,
    model: str,
    system_prompt: str,
    user_prompt: str,
    schema_name: str,
    schema: dict[str, Any],
    reasoning_effort: str,
    settings: Settings,
    stage: str,
    repo: str,
    previous_response_id: str | None = None,
    model_tier: str = "default",
) -> tuple[dict[str, Any], dict[str, Any]]:
    payload = _response_payload(
        model=model,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        schema_name=schema_name,
        schema=schema,
        reasoning_effort=reasoning_effort,
        settings=settings,
        stage=stage,
        repo=repo,
        previous_response_id=previous_response_id,
        model_tier=model_tier,
    )
    request_controls = payload.pop("_openai_request_controls", {})
    response = client.responses.create(**payload)
    parsed = _extract_structured_object(response, stage=stage)
    if settings.openai_enable_background_requests and not parsed:
        response_id = getattr(response, "id", None)
        raise RuntimeError(
            "OpenAI background responses require async completion handling before planning can continue"
            f" (response_id={response_id or 'unknown'})"
        )
    response_id = getattr(response, "id", None)
    _logger.info(
        "openai_call stage=%s model=%s response_id=%s model_tier=%s",
        stage,
        model,
        response_id or "",
        request_controls.get("model_tier", ""),
    )
    return parsed, {
        **request_controls,
        "model": model,
        "response_id": response_id,
        "stage": stage,
    }


def _validate_internal_plan(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "objective": _coerce_string(raw.get("objective"), "objective"),
        "scope": _coerce_string_list(raw.get("scope"), "scope"),
        "non_goals": _coerce_string_list(raw.get("non_goals"), "non_goals"),
        "acceptance_criteria": _coerce_string_list(raw.get("acceptance_criteria"), "acceptance_criteria"),
        "validation_guidance": _coerce_string_list(raw.get("validation_guidance"), "validation_guidance"),
        "implementation_brief": _coerce_string(raw.get("implementation_brief"), "implementation_brief"),
        "task_type": _coerce_task_type(raw.get("task_type")),
        "difficulty": _coerce_difficulty(raw.get("difficulty")),
        "repo_areas": _coerce_string_list(raw.get("repo_areas"), "repo_areas"),
        "execution_risks": _coerce_string_list(raw.get("execution_risks"), "execution_risks"),
        "reviewer_focus": _coerce_string_list(raw.get("reviewer_focus"), "reviewer_focus"),
        "recommended_scope_class": _coerce_scope_class(raw.get("recommended_scope_class")),
        "recommended_worker": _coerce_optional_worker(raw.get("recommended_worker")),
        "internal_routing_metadata": _coerce_optional_routing_metadata(raw.get("internal_routing_metadata")),
    }


def _validate_worker_brief(raw: dict[str, Any]) -> dict[str, Any]:
    objective = _coerce_string(raw.get("objective"), "objective")
    sanitized_objective = _sanitize_for_worker(objective)
    if not isinstance(sanitized_objective, str) or not sanitized_objective.strip():
        sanitized_objective = "Implement task objective"
    return {
        "objective": sanitized_objective,
        "concise_scope": _sanitize_for_worker(_coerce_string_list(raw.get("concise_scope"), "concise_scope")),
        "implementation_brief": _sanitize_for_worker(_coerce_string(raw.get("implementation_brief"), "implementation_brief")),
        "acceptance_criteria": _sanitize_for_worker(
            _coerce_string_list(raw.get("acceptance_criteria"), "acceptance_criteria")
        ),
        "validation_commands": _sanitize_for_worker(
            _coerce_string_list(raw.get("validation_commands"), "validation_commands")
        ),
        "non_goals": _sanitize_for_worker(_coerce_string_list(raw.get("non_goals"), "non_goals")),
        "target_branch": _coerce_string(raw.get("target_branch"), "target_branch"),
        "repo_grounded_hints": _sanitize_for_worker(
            _coerce_string_list(raw.get("repo_grounded_hints"), "repo_grounded_hints")
        ),
    }


def _sanitize_for_worker(value: str | list[str]) -> str | list[str]:
    if isinstance(value, list):
        return [str(item).replace("\r", "").strip() for item in value if item and not _contains_internal_label(item)]
    if _contains_internal_label(value):
        return ""
    return value


def _contains_internal_label(value: str) -> bool:
    lowered = value.lower()
    return any(term in lowered for term in _INTERNAL_LABEL_TERMS)


def _planning_reasoning_effort(settings: Settings, *, issue_title: str, issue_body: str) -> str:
    default_effort = (settings.openai_planning_reasoning_effort or "medium").strip().lower()
    if default_effort not in _ALLOWED_REASONING_EFFORT:
        default_effort = "medium"

    if not settings.openai_escalate_reasoning_for_broad_tasks:
        return default_effort

    broad_effort = (settings.openai_planning_broad_reasoning_effort or "high").strip().lower()
    if broad_effort not in _ALLOWED_REASONING_EFFORT:
        broad_effort = "high"

    signal_text = f"{issue_title}\n{issue_body}".lower()
    broad_markers = (
        "migration",
        "architecture",
        "broad",
        "cross-system",
        "cross system",
        "end-to-end",
        "refactor",
    )
    if any(marker in signal_text for marker in broad_markers):
        return broad_effort
    return default_effort


def _worker_brief_prompt(*, repo: str, issue_number: int, internal_plan: dict[str, Any], target_branch: str) -> str:
    return (
        f"Repository: {repo}\n"
        f"Issue: #{issue_number}\n"
        f"Target branch: {target_branch}\n"
        "Produce an execution brief for plain Copilot worker dispatch using the internal plan below. "
        "Do not include internal worker labels or orchestration metadata.\n\n"
        "Internal plan JSON:\n"
        f"{json.dumps(internal_plan, ensure_ascii=False, indent=2)}"
    )


def _internal_plan_prompt(*, repo: str, issue_number: int, issue_title: str, issue_body: str) -> str:
    return (
        f"Repository: {repo}\n"
        f"Issue: #{issue_number}\n"
        f"Title: {issue_title}\n\n"
        "Issue body:\n"
        f"{issue_body or '(empty)'}"
    )


def _build_worker_brief_fallback(*, internal_plan: dict[str, Any], target_branch: str) -> dict[str, Any]:
    return {
        "objective": _sanitize_for_worker(internal_plan.get("objective", "")) or "Implement task objective",
        "concise_scope": _sanitize_for_worker(internal_plan.get("scope") or []),
        "implementation_brief": _sanitize_for_worker(internal_plan.get("implementation_brief", ""))
        or "Implement requested scope.",
        "acceptance_criteria": _sanitize_for_worker(internal_plan.get("acceptance_criteria") or []),
        "validation_commands": _sanitize_for_worker(internal_plan.get("validation_guidance") or []),
        "non_goals": _sanitize_for_worker(internal_plan.get("non_goals") or []),
        "target_branch": target_branch,
        "repo_grounded_hints": _sanitize_for_worker(internal_plan.get("repo_areas") or []),
    }


def _validate_program_plan(raw: dict[str, Any], *, fallback_plan: dict[str, Any]) -> dict[str, Any]:
    slices = raw.get("slices")
    if not isinstance(slices, list) or not slices:
        slices = [
            {
                "slice_number": 1,
                "milestone_key": "M1",
                "title": "Initial implementation slice",
                "objective": fallback_plan.get("objective", ""),
                "acceptance_criteria": fallback_plan.get("acceptance_criteria", []),
                "non_goals": fallback_plan.get("non_goals", []),
                "expected_file_zones": fallback_plan.get("repo_areas", []),
                "continuation_hint": "",
                "slice_type": "implementation",
            }
        ]
    return {
        "normalized_program_objective": _coerce_string(
            raw.get("normalized_program_objective") or fallback_plan.get("objective"),
            "normalized_program_objective",
        ),
        "definition_of_done": _coerce_string_list(raw.get("definition_of_done"), "definition_of_done")
        or _coerce_string_list(fallback_plan.get("acceptance_criteria"), "acceptance_criteria"),
        "non_goals": _coerce_string_list(raw.get("non_goals"), "non_goals"),
        "milestones": raw.get("milestones") if isinstance(raw.get("milestones"), list) else [],
        "slices": slices,
        "current_slice_brief": _coerce_string(
            raw.get("current_slice_brief") or fallback_plan.get("implementation_brief"),
            "current_slice_brief",
        ),
        "acceptance_criteria": _coerce_string_list(raw.get("acceptance_criteria"), "acceptance_criteria"),
        "risk_profile": _coerce_string_list(raw.get("risk_profile"), "risk_profile"),
        "recommended_worker": _coerce_optional_worker(raw.get("recommended_worker")),
        "recommended_scope_class": _coerce_scope_class(raw.get("recommended_scope_class")),
        "continuation_hints": _coerce_string_list(raw.get("continuation_hints"), "continuation_hints"),
    }


def plan_task_packet(
    *,
    settings: Settings,
    repo: str,
    issue_number: int,
    issue_title: str,
    issue_body: str,
    previous_response_id: str | None = None,
) -> dict[str, Any]:
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required for planning")

    client = OpenAI(api_key=settings.openai_api_key)
    planning_effort = _planning_reasoning_effort(settings, issue_title=issue_title, issue_body=issue_body)
    planner_model, planner_tier = select_model_for_stage(
        settings=settings,
        stage="planner",
        fallback_model=settings.openai_planning_model,
    )
    worker_brief_model, worker_brief_tier = select_model_for_stage(
        settings=settings,
        stage="worker_brief",
        fallback_model=settings.openai_planning_model,
    )
    validate_strict_json_schema(schema_name="internal_task_plan", schema=INTERNAL_TASK_PLAN_SCHEMA)
    validate_strict_json_schema(schema_name="worker_execution_brief", schema=WORKER_BRIEF_SCHEMA)
    validate_strict_json_schema(schema_name="program_plan", schema=PROGRAM_PLAN_SCHEMA)

    chain_response_id = (previous_response_id or "").strip() or None
    internal_plan_raw, planner_meta = _invoke_structured_response(
        client=client,
        model=planner_model,
        system_prompt=PLANNING_SYSTEM_PROMPT,
        user_prompt=_internal_plan_prompt(
            repo=repo,
            issue_number=issue_number,
            issue_title=issue_title,
            issue_body=issue_body,
        ),
        schema_name="internal_task_plan",
        schema=INTERNAL_TASK_PLAN_SCHEMA,
        reasoning_effort=planning_effort,
        settings=settings,
        stage="planning",
        repo=repo,
        previous_response_id=chain_response_id,
        model_tier=planner_tier,
    )
    planner_meta["model_tier"] = planner_tier
    chain_response_id = planner_meta.get("response_id") or chain_response_id
    internal_plan = _validate_internal_plan(internal_plan_raw)

    worker_brief_raw: dict[str, Any]
    worker_brief_meta: dict[str, Any] = {
        "stage": "worker-brief",
        "model": worker_brief_model,
        "model_tier": worker_brief_tier,
        "response_id": None,
    }
    try:
        worker_brief_raw, worker_brief_meta = _invoke_structured_response(
            client=client,
            model=worker_brief_model,
            system_prompt=WORKER_BRIEF_SYSTEM_PROMPT,
            user_prompt=_worker_brief_prompt(
                repo=repo,
                issue_number=issue_number,
                internal_plan=internal_plan,
                target_branch=settings.copilot_target_branch,
            ),
            schema_name="worker_execution_brief",
            schema=WORKER_BRIEF_SCHEMA,
            reasoning_effort=settings.openai_planning_reasoning_effort,
            settings=settings,
            stage="worker-brief",
            repo=repo,
            previous_response_id=chain_response_id,
            model_tier=worker_brief_tier,
        )
        worker_brief_meta["model_tier"] = worker_brief_tier
        chain_response_id = worker_brief_meta.get("response_id") or chain_response_id
    except Exception:
        worker_brief_raw = _build_worker_brief_fallback(
            internal_plan=internal_plan,
            target_branch=settings.copilot_target_branch,
        )

    worker_brief = _validate_worker_brief(worker_brief_raw)

    program_plan_raw: dict[str, Any]
    program_plan_meta: dict[str, Any] = {
        "stage": "program-planning",
        "model": planner_model,
        "model_tier": planner_tier,
        "response_id": None,
    }
    try:
        program_plan_raw, program_plan_meta = _invoke_structured_response(
            client=client,
            model=planner_model,
            system_prompt=PLANNING_SYSTEM_PROMPT,
            user_prompt=(
                _internal_plan_prompt(
                    repo=repo,
                    issue_number=issue_number,
                    issue_title=issue_title,
                    issue_body=issue_body,
                )
                + "\n\nDecompose this into ordered milestone/slice program execution plan."
            ),
            schema_name="program_plan",
            schema=PROGRAM_PLAN_SCHEMA,
            reasoning_effort=planning_effort,
            settings=settings,
            stage="program-planning",
            repo=repo,
            previous_response_id=chain_response_id,
            model_tier=planner_tier,
        )
        program_plan_meta["model_tier"] = planner_tier
        chain_response_id = program_plan_meta.get("response_id") or chain_response_id
    except Exception:
        program_plan_raw = {
            "normalized_program_objective": internal_plan.get("objective", ""),
            "definition_of_done": internal_plan.get("acceptance_criteria", []),
            "non_goals": internal_plan.get("non_goals", []),
            "milestones": [{"key": "M1", "title": "Milestone 1", "goal": internal_plan.get("objective", "")}],
            "slices": [
                {
                    "slice_number": 1,
                    "milestone_key": "M1",
                    "title": "Initial implementation slice",
                    "objective": internal_plan.get("objective", ""),
                    "acceptance_criteria": internal_plan.get("acceptance_criteria", []),
                    "non_goals": internal_plan.get("non_goals", []),
                    "expected_file_zones": internal_plan.get("repo_areas", []),
                    "continuation_hint": "",
                    "slice_type": "implementation",
                }
            ],
            "current_slice_brief": internal_plan.get("implementation_brief", ""),
            "acceptance_criteria": internal_plan.get("acceptance_criteria", []),
            "risk_profile": internal_plan.get("execution_risks", []),
            "recommended_worker": internal_plan.get("recommended_worker"),
            "recommended_scope_class": internal_plan.get("recommended_scope_class"),
            "continuation_hints": [],
        }
    program_plan = _validate_program_plan(program_plan_raw, fallback_plan=internal_plan)

    return {
        "internal_plan": internal_plan,
        "worker_brief": worker_brief,
        "program_plan": program_plan,
        "planning_meta": {
            "model": planner_model,
            "reasoning_effort": planning_effort,
            "control_plane_mode": settings.openai_control_plane_mode,
            "helper_model": worker_brief_model,
            "openai_last_response_id": chain_response_id,
            "calls": [planner_meta, worker_brief_meta, program_plan_meta],
        },
    }
