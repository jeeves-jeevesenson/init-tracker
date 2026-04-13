from __future__ import annotations

import json
from dataclasses import dataclass

import httpx

from .config import Settings
from .models import TaskPacket


@dataclass
class DispatchResult:
    success: bool
    manual_required: bool
    summary: str
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
            success=False,
            manual_required=True,
            summary="GitHub API token missing; task remains approved for manual dispatch.",
        )

    api_base = settings.github_api_url.rstrip("/")
    repo_path = task.github_repo
    issue_number = task.github_issue_number

    assign_url = f"{api_base}/repos/{repo_path}/issues/{issue_number}/assignees"
    comment_url = f"{api_base}/repos/{repo_path}/issues/{issue_number}/comments"

    try:
        with httpx.Client(timeout=15.0) as client:
            assign_response = client.post(
                assign_url,
                headers=_build_headers(settings),
                json={"assignees": [settings.copilot_dispatch_assignee]},
            )
            if assign_response.status_code >= 400:
                details = assign_response.text[:500]
                manual = assign_response.status_code in {401, 403, 404, 422}
                return DispatchResult(
                    success=False,
                    manual_required=manual,
                    summary=(
                        "GitHub Copilot dispatch assignment failed "
                        f"({assign_response.status_code}): {details}"
                    ),
                )

            comment_response = client.post(
                comment_url,
                headers=_build_headers(settings),
                json={"body": _task_packet_comment(task, target_branch=settings.copilot_target_branch)},
            )
            if comment_response.status_code >= 400:
                details = comment_response.text[:500]
                return DispatchResult(
                    success=False,
                    manual_required=comment_response.status_code in {401, 403, 404, 422},
                    summary=(
                        "Task packet comment failed after assignment "
                        f"({comment_response.status_code}): {details}"
                    ),
                )

            comment_payload = comment_response.json() if comment_response.headers.get("content-type", "").startswith("application/json") else {}
            dispatch_id = str(comment_payload.get("id")) if comment_payload.get("id") is not None else None
            dispatch_url = comment_payload.get("html_url")
            return DispatchResult(
                success=True,
                manual_required=False,
                summary=f"Dispatched via issue assignment to {settings.copilot_dispatch_assignee}.",
                dispatch_id=dispatch_id,
                dispatch_url=dispatch_url,
            )
    except Exception as exc:
        return DispatchResult(
            success=False,
            manual_required=True,
            summary=f"Dispatch request failed: {exc}",
        )
