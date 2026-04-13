from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import httpx

from .config import Settings
from .copilot_identity import normalize_configured_copilot_login, normalize_copilot_login
from .models import TaskPacket

_SUGGESTED_ACTORS_QUERY = """
query($owner: String!, $name: String!) {
  repository(owner: $owner, name: $name) {
    suggestedActors(capabilities: [CAN_BE_ASSIGNED], first: 100) {
      nodes {
        login
        __typename
        ... on Bot {
          id
        }
      }
    }
  }
}
"""


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
    selected_custom_agent = task.selected_custom_agent or settings.copilot_custom_agent
    payload: dict[str, Any] = {
        "target_repo": settings.copilot_target_repo or task.github_repo,
        "base_branch": settings.copilot_target_branch,
    }
    if settings.copilot_custom_instructions:
        payload["custom_instructions"] = settings.copilot_custom_instructions
    if settings.enable_github_custom_agent_dispatch and selected_custom_agent:
        payload["custom_agent"] = selected_custom_agent
    if settings.copilot_model:
        payload["model"] = settings.copilot_model
    return payload


def _dispatch_mode(settings: Settings, task: TaskPacket) -> tuple[str, str | None]:
    selected_custom_agent = task.selected_custom_agent or settings.copilot_custom_agent
    if not settings.enable_github_custom_agent_dispatch:
        return "plain_copilot_fallback", None
    if selected_custom_agent:
        return "custom_agent_launch", selected_custom_agent
    return "plain_copilot_no_custom_agent", None


def describe_dispatch_mode(settings: Settings, task: TaskPacket) -> str:
    mode, requested_custom_agent = _dispatch_mode(settings, task)
    return (
        f"dispatch_mode={mode}; "
        f"internal_selected_custom_agent={task.selected_custom_agent or '(none)'}; "
        f"requested_custom_agent={requested_custom_agent or '(none)'}"
    )


def build_dispatch_request_payload(settings: Settings, task: TaskPacket) -> dict[str, Any]:
    expected_assignee_login, _ = normalize_configured_copilot_login(settings.copilot_dispatch_assignee)
    return {
        "assignees": [expected_assignee_login],
        "agent_assignment": _build_agent_assignment_payload(settings, task),
    }


def build_dispatch_payload_summary(settings: Settings, task: TaskPacket) -> dict[str, Any]:
    payload = build_dispatch_request_payload(settings, task)
    dispatch_mode, _ = _dispatch_mode(settings, task)
    payload["dispatch_mode_summary"] = describe_dispatch_mode(settings, task)
    payload["github_execution_mode"] = dispatch_mode
    return payload


def _extract_assignee_logins(payload: dict[str, Any]) -> set[str]:
    assignees = payload.get("assignees") or []
    return {
        str(item.get("login"))
        for item in assignees
        if isinstance(item, dict) and isinstance(item.get("login"), str)
    }


def _load_worker_brief(task: TaskPacket, *, target_branch: str) -> dict[str, Any]:
    if task.worker_brief_json:
        try:
            parsed = json.loads(task.worker_brief_json)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
    return {
        "objective": task.title or "Implement task objective",
        "concise_scope": [],
        "implementation_brief": task.normalized_task_text or "",
        "acceptance_criteria": json.loads(task.acceptance_criteria_json or "[]"),
        "validation_commands": json.loads(task.validation_commands_json or "[]"),
        "non_goals": [],
        "target_branch": target_branch,
        "repo_grounded_hints": [],
    }


def _task_packet_comment(task: TaskPacket, *, target_branch: str, execution_mode: str) -> str:
    worker_brief = _load_worker_brief(task, target_branch=target_branch)
    packet = {
        "task_packet_id": task.id,
        "objective": worker_brief.get("objective"),
        "concise_scope": worker_brief.get("concise_scope") or [],
        "implementation_brief": worker_brief.get("implementation_brief"),
        "acceptance_criteria": worker_brief.get("acceptance_criteria") or [],
        "validation_commands": worker_brief.get("validation_commands") or [],
        "non_goals": worker_brief.get("non_goals") or [],
        "target_branch": worker_brief.get("target_branch") or target_branch,
        "repo_grounded_hints": worker_brief.get("repo_grounded_hints") or [],
        "execution_mode": execution_mode,
    }
    return (
        "Orchestrator dispatch packet for GitHub Copilot coding agent.\n\n"
        "```json\n"
        f"{json.dumps(packet, indent=2)}\n"
        "```"
    )


def _extract_repo_owner_name(repo_path: str) -> tuple[str, str] | None:
    owner, sep, name = repo_path.partition("/")
    if not sep or not owner or not name:
        return None
    return owner, name


def _extract_suggested_actor_logins(payload: dict[str, Any]) -> list[str]:
    nodes = (
        (((payload.get("data") or {}).get("repository") or {}).get("suggestedActors") or {}).get("nodes")
        or []
    )
    logins: list[str] = []
    for node in nodes:
        if isinstance(node, dict) and isinstance(node.get("login"), str):
            logins.append(node["login"])
    return sorted(set(logins))


def _suggested_actors_summary(actor_logins: list[str]) -> str:
    return f"suggestedActors={actor_logins or ['(none)']}"


def dispatch_task_to_github_copilot(*, settings: Settings, task: TaskPacket) -> DispatchResult:
    dispatch_mode, _ = _dispatch_mode(settings, task)
    dispatch_mode_summary = describe_dispatch_mode(settings, task)
    if not settings.github_api_token:
        return DispatchResult(
            attempted=False,
            accepted=False,
            manual_required=True,
            state="blocked",
            summary=(
                "GitHub API token missing; task remains approved for manual dispatch. "
                f"{dispatch_mode_summary}"
            ),
        )

    api_base = settings.github_api_url.rstrip("/")
    repo_path = task.github_repo
    issue_number = task.github_issue_number
    repo_parts = _extract_repo_owner_name(repo_path)
    if repo_parts is None:
        return DispatchResult(
            attempted=False,
            accepted=False,
            manual_required=True,
            state="blocked",
            summary=f"Invalid task repository path for dispatch: {repo_path!r}. {dispatch_mode_summary}",
        )
    owner, name = repo_parts

    assign_url = f"{api_base}/repos/{repo_path}/issues/{issue_number}/assignees"
    comment_url = f"{api_base}/repos/{repo_path}/issues/{issue_number}/comments"
    graphql_url = f"{api_base}/graphql"
    expected_assignee_login, normalization_applied = normalize_configured_copilot_login(
        settings.copilot_dispatch_assignee
    )

    try:
        with httpx.Client(timeout=15.0) as client:
            preflight_response = client.post(
                graphql_url,
                headers=_build_headers(settings),
                json={
                    "query": _SUGGESTED_ACTORS_QUERY,
                    "variables": {"owner": owner, "name": name},
                },
            )
            if preflight_response.status_code >= 400:
                details = preflight_response.text[:500]
                return DispatchResult(
                    attempted=True,
                    accepted=False,
                    manual_required=True,
                    state="blocked",
                    summary=(
                        "GitHub Copilot preflight suggestedActors query failed "
                        f"({preflight_response.status_code}): {details}. "
                        f"{dispatch_mode_summary}"
                    ),
                    api_status_code=preflight_response.status_code,
                )

            preflight_payload = (
                preflight_response.json()
                if preflight_response.headers.get("content-type", "").startswith("application/json")
                else {}
            )
            if preflight_payload.get("errors"):
                return DispatchResult(
                    attempted=True,
                    accepted=False,
                    manual_required=True,
                    state="blocked",
                    summary=(
                        "GitHub Copilot preflight suggestedActors query returned errors: "
                        f"{str(preflight_payload.get('errors'))[:500]}. "
                        f"{dispatch_mode_summary}"
                    ),
                    api_status_code=preflight_response.status_code,
                )
            suggested_actor_logins = _extract_suggested_actor_logins(preflight_payload)
            preflight_summary = _suggested_actors_summary(suggested_actor_logins)
            normalized_suggested_actor_logins = {
                normalize_copilot_login(login) for login in suggested_actor_logins
            }
            if expected_assignee_login not in normalized_suggested_actor_logins:
                return DispatchResult(
                    attempted=True,
                    accepted=False,
                    manual_required=True,
                    state="blocked",
                    summary=(
                        "Copilot cloud agent not enabled or not assignable in this repository. "
                        f"{preflight_summary}. "
                        f"{dispatch_mode_summary}"
                    ),
                    api_status_code=preflight_response.status_code,
                )

            request_payload = build_dispatch_request_payload(settings, task)
            requested_custom_agent = (request_payload.get("agent_assignment") or {}).get("custom_agent")
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
                        f"({assign_response.status_code}): {details} "
                        f"{preflight_summary}. "
                        f"{dispatch_mode_summary}"
                    ),
                    api_status_code=assign_response.status_code,
                )

            assign_payload = (
                assign_response.json()
                if assign_response.headers.get("content-type", "").startswith("application/json")
                else {}
            )
            raw_assignee_logins = sorted(_extract_assignee_logins(assign_payload))
            assignee_logins = {normalize_copilot_login(login) for login in raw_assignee_logins}
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
                        f"normalization_applied={normalization_applied}; "
                        f"{preflight_summary}. "
                        f"{dispatch_mode_summary}"
                    ),
                    api_status_code=assign_response.status_code,
                )

            dispatch_id = str(assign_payload.get("id")) if assign_payload.get("id") is not None else None
            dispatch_url = assign_payload.get("html_url")
            comment_warning: str | None = None
            comment_response = client.post(
                comment_url,
                headers=_build_headers(settings),
                json={
                    "body": _task_packet_comment(
                        task,
                        target_branch=settings.copilot_target_branch,
                        execution_mode=dispatch_mode,
                    )
                },
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
                    f" custom_agent={requested_custom_agent or '(none)'}."
                    f" {preflight_summary}."
                    f" {dispatch_mode_summary}."
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
            summary=f"Dispatch request failed: {exc}. {dispatch_mode_summary}",
        )


def mark_pr_ready_for_review(*, settings: Settings, repo: str, pr_number: int) -> tuple[bool, str]:
    """Attempt to convert a draft PR to ready-for-review.

    Returns (success, message).  Safe to call when the PR is already non-draft.
    """
    if not settings.github_api_token:
        return False, "GitHub API token missing; cannot un-draft PR"
    api_base = settings.github_api_url.rstrip("/")
    url = f"{api_base}/repos/{repo}/pulls/{pr_number}"
    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.patch(
                url,
                headers=_build_headers(settings),
                json={"draft": False},
            )
            if response.status_code >= 400:
                return False, f"GitHub returned {response.status_code} when un-drafting PR #{pr_number}: {response.text[:300]}"
            return True, f"PR #{pr_number} marked ready for review"
    except Exception as exc:
        return False, f"Failed to un-draft PR #{pr_number}: {exc}"
