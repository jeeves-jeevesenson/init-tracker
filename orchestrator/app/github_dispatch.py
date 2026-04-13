from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import httpx

from .config import Settings
from .copilot_identity import normalize_configured_copilot_login, normalize_login
from .models import TaskPacket


@dataclass
class DispatchResult:
    attempted: bool
    accepted: bool
    manual_required: bool
    state: str
    summary: str
    api_status_code: int | None = None
    dispatch_id: str | None = None
    dispatch_url: str | None = None


def _build_headers(settings: Settings) -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if settings.github_api_token:
        headers["Authorization"] = f"Bearer {settings.github_api_token}"
    return headers


def _build_agent_assignment_payload(settings: Settings, task: TaskPacket) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "target_repo": settings.copilot_target_repo or task.github_repo,
        "base_branch": settings.copilot_target_branch,
    }
    if settings.copilot_custom_instructions:
        payload["custom_instructions"] = settings.copilot_custom_instructions
    if settings.copilot_custom_agent:
        payload["custom_agent"] = settings.copilot_custom_agent
    if settings.copilot_model:
        payload["model"] = settings.copilot_model
    return payload


def _extract_assignee_logins(payload: dict[str, Any]) -> set[str]:
    assignees = payload.get("assignees") or []
    return {
        str(item.get("login"))
        for item in assignees
        if isinstance(item, dict) and isinstance(item.get("login"), str)
    }


def _task_packet_comment(task: TaskPacket, *, target_branch: str) -> str:
    packet = {
        "task_packet_id": task.id,
        "title": task.title,
        "normalized_task_text": task.normalized_task_text,
        "acceptance_criteria": json.loads(task.acceptance_criteria_json or "[]"),
        "validation_commands": json.loads(task.validation_commands_json or "[]"),
        "target_branch": target_branch,
    }
    return (
        "Orchestrator dispatch packet for GitHub Copilot coding agent.\n\n"
        "```json\n"
        f"{json.dumps(packet, indent=2)}\n"
        "```"
    )


def dispatch_task_to_github_copilot(*, settings: Settings, task: TaskPacket) -> DispatchResult:
    if not settings.github_api_token:
        return DispatchResult(
            attempted=False,
            accepted=False,
            manual_required=True,
            state="blocked",
            summary="GitHub API token missing; task remains approved for manual dispatch.",
        )

    api_base = settings.github_api_url.rstrip("/")
    repo_path = task.github_repo
    issue_number = task.github_issue_number

    assign_url = f"{api_base}/repos/{repo_path}/issues/{issue_number}/assignees"
    comment_url = f"{api_base}/repos/{repo_path}/issues/{issue_number}/comments"

    try:
        with httpx.Client(timeout=15.0) as client:
            request_payload = {
                "assignees": [],
                "agent_assignment": _build_agent_assignment_payload(settings, task),
            }
            expected_assignee_login, normalization_applied = normalize_configured_copilot_login(
                settings.copilot_dispatch_assignee
            )
            request_payload["assignees"] = [expected_assignee_login]
            assign_response = client.post(
                assign_url,
                headers=_build_headers(settings),
                json=request_payload,
            )
            if assign_response.status_code >= 400:
                details = assign_response.text[:500]
                manual = assign_response.status_code in {401, 403, 404, 422}
                return DispatchResult(
                    attempted=True,
                    accepted=False,
                    manual_required=manual,
                    state="blocked" if manual else "failed",
                    summary=(
                        "GitHub Copilot dispatch assignment failed "
                        f"({assign_response.status_code}): {details}"
                    ),
                    api_status_code=assign_response.status_code,
                )

            assign_payload = (
                assign_response.json()
                if assign_response.headers.get("content-type", "").startswith("application/json")
                else {}
            )
            raw_assignee_logins = sorted(_extract_assignee_logins(assign_payload))
            assignee_logins = {normalize_login(login) for login in raw_assignee_logins}
            if expected_assignee_login not in assignee_logins:
                return DispatchResult(
                    attempted=True,
                    accepted=False,
                    manual_required=True,
                    state="blocked",
                    summary=(
                        "GitHub accepted the request but Copilot assignee was not applied; "
                        "manual dispatch needed. "
                        f"expected={expected_assignee_login}; "
                        f"actual={raw_assignee_logins or ['(none)']}; "
                        f"normalization_applied={normalization_applied}"
                    ),
                    api_status_code=assign_response.status_code,
                )

            dispatch_id = str(assign_payload.get("id")) if assign_payload.get("id") is not None else None
            dispatch_url = assign_payload.get("html_url")
            comment_warning: str | None = None
            comment_response = client.post(
                comment_url,
                headers=_build_headers(settings),
                json={"body": _task_packet_comment(task, target_branch=settings.copilot_target_branch)},
            )
            if comment_response.status_code >= 400:
                comment_warning = (
                    f" Task packet comment failed ({comment_response.status_code}): "
                    f"{comment_response.text[:200]}"
                )
            return DispatchResult(
                attempted=True,
                accepted=True,
                manual_required=False,
                state="accepted",
                summary=(
                    "Copilot assignment request accepted via issues assignee API"
                    f" for {expected_assignee_login}."
                    f"{comment_warning or ''}"
                ),
                api_status_code=assign_response.status_code,
                dispatch_id=dispatch_id,
                dispatch_url=dispatch_url,
            )
    except Exception as exc:
        return DispatchResult(
            attempted=True,
            accepted=False,
            manual_required=True,
            state="blocked",
            summary=f"Dispatch request failed: {exc}",
        )
