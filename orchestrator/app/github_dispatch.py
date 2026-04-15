from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

import httpx

from .config import Settings
from .copilot_identity import normalize_configured_copilot_login, normalize_copilot_login
from .github_auth import (
    build_dispatch_auth_headers,
    build_governor_auth_headers,
    dispatch_auth_label,
    governor_auth_mode_label,
    has_dispatch_auth,
    has_governor_auth,
    is_governor_app_mode,
    try_mint_governor_app_token,
)
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

_PULL_REQUEST_ID_QUERY = """
query($owner: String!, $name: String!, $number: Int!) {
  repository(owner: $owner, name: $name) {
    pullRequest(number: $number) {
      id
      isDraft
    }
  }
}
"""

_PULL_REQUEST_LINKED_ISSUES_QUERY = """
query($owner: String!, $name: String!, $number: Int!, $timelineLimit: Int!) {
  repository(owner: $owner, name: $name) {
    pullRequest(number: $number) {
      closingIssuesReferences(first: 20) {
        nodes {
          number
          repository {
            nameWithOwner
          }
        }
      }
      timelineItems(first: $timelineLimit, itemTypes: [CONNECTED_EVENT, CROSS_REFERENCED_EVENT]) {
        nodes {
          __typename
          ... on ConnectedEvent {
            subject {
              __typename
              ... on Issue {
                number
                repository {
                  nameWithOwner
                }
              }
            }
          }
          ... on CrossReferencedEvent {
            source {
              __typename
              ... on Issue {
                number
                repository {
                  nameWithOwner
                }
              }
            }
          }
        }
      }
    }
  }
}
"""

_MARK_PR_READY_MUTATION = """
mutation($pullRequestId: ID!) {
  markPullRequestReadyForReview(input: {pullRequestId: $pullRequestId}) {
    pullRequest {
      number
      isDraft
    }
  }
}
"""

logger = logging.getLogger(__name__)


def _github_debug_enabled(settings: Settings) -> bool:
    return bool(getattr(settings, "orchestrator_debug_github", False))


def _log_github_debug(
    settings: Settings,
    *,
    event: str,
    repo: str,
    issue_number: int | None = None,
    pr_number: int | None = None,
    auth_lane: str,
    api_type: str,
    success: bool,
    summary: str,
    postcondition: str | None = None,
    http_status: int | None = None,
    result_class: str | None = None,
) -> None:
    if not _github_debug_enabled(settings):
        return
    logger.info(
        "github_debug event=%s repo=%s issue_number=%s pr_number=%s auth_lane=%s api_type=%s success=%s http_status=%s result_class=%s postcondition=%s summary=%s",
        event,
        repo,
        issue_number if issue_number is not None else "n/a",
        pr_number if pr_number is not None else "n/a",
        auth_lane,
        api_type,
        success,
        http_status if http_status is not None else "n/a",
        result_class or "n/a",
        postcondition or "n/a",
        summary,
    )


def _log_github_action(
    *,
    action: str,
    repo: str,
    number: int,
    number_kind: str,
    auth_lane: str,
    api_type: str,
    success: bool,
    summary: str,
) -> None:
    level = logging.INFO if success else logging.WARNING
    logger.log(
        level,
        "github_action=%s repo=%s %s=%s auth_lane=%s api_type=%s success=%s summary=%s",
        action,
        repo,
        number_kind,
        number,
        auth_lane,
        api_type,
        success,
        summary,
    )


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


@dataclass
class PullRequestInspection:
    ok: bool
    changed_files: int | None
    commits: int | None
    draft: bool | None
    state: str | None
    merged: bool | None
    summary: str


def _build_dispatch_headers(settings: Settings) -> dict[str, str]:
    return build_dispatch_auth_headers(settings)


def _build_governor_headers(settings: Settings) -> dict[str, str]:
    return build_governor_auth_headers(settings)


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


def build_dispatch_payload_summary(
    settings: Settings,
    task: TaskPacket,
    *,
    linkage_tag: str | None = None,
) -> dict[str, Any]:
    payload = build_dispatch_request_payload(settings, task)
    if linkage_tag:
        payload["linkage_tag"] = linkage_tag
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


def _task_packet_comment(
    task: TaskPacket,
    *,
    target_branch: str,
    execution_mode: str,
    linkage_tag: str | None = None,
) -> str:
    worker_brief = _load_worker_brief(task, target_branch=target_branch)
    linkage_instruction = (
        f"When you open the PR, include this exact line in the PR body: `{linkage_tag}`"
        if linkage_tag
        else None
    )
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
        "pr_linkage_tag": linkage_tag,
        "pr_linkage_instruction": linkage_instruction,
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


def dispatch_task_to_github_copilot(
    *,
    settings: Settings,
    task: TaskPacket,
    linkage_tag: str | None = None,
) -> DispatchResult:
    dispatch_mode, _ = _dispatch_mode(settings, task)
    dispatch_mode_summary = describe_dispatch_mode(settings, task)
    if not has_dispatch_auth(settings):
        result = DispatchResult(
            attempted=False,
            accepted=False,
            manual_required=True,
            state="blocked",
            summary=(
                "Dispatch auth failure: dispatch user token not configured; task remains approved for manual dispatch. "
                f"{dispatch_mode_summary}"
            ),
        )
        _log_github_action(
            action="issue_dispatch_assignment",
            repo=task.github_repo,
            number=int(task.github_issue_number),
            number_kind="issue_number",
            auth_lane="dispatch_user_token",
            api_type="GraphQL+REST",
            success=False,
            summary=result.summary,
        )
        return result

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
                headers=_build_dispatch_headers(settings),
                json={
                    "query": _SUGGESTED_ACTORS_QUERY,
                    "variables": {"owner": owner, "name": name},
                },
            )
            if preflight_response.status_code >= 400:
                details = preflight_response.text[:500]
                result = DispatchResult(
                    attempted=True,
                    accepted=False,
                    manual_required=True,
                    state="blocked",
                    summary=(
                        "Actor assignment preflight failed: GitHub suggestedActors query failed "
                        f"({preflight_response.status_code}): {details}. "
                        f"{dispatch_mode_summary}"
                    ),
                    api_status_code=preflight_response.status_code,
                )
                _log_github_action(
                    action="issue_dispatch_assignment",
                    repo=repo_path,
                    number=issue_number,
                    number_kind="issue_number",
                    auth_lane="dispatch_user_token",
                    api_type="GraphQL",
                    success=False,
                    summary=result.summary,
                )
                return result

            preflight_payload = (
                preflight_response.json()
                if preflight_response.headers.get("content-type", "").startswith("application/json")
                else {}
            )
            if preflight_payload.get("errors"):
                result = DispatchResult(
                    attempted=True,
                    accepted=False,
                    manual_required=True,
                    state="blocked",
                    summary=(
                        "Actor assignment preflight failed: GitHub suggestedActors query returned errors: "
                        f"{str(preflight_payload.get('errors'))[:500]}. "
                        f"{dispatch_mode_summary}"
                    ),
                    api_status_code=preflight_response.status_code,
                )
                _log_github_action(
                    action="issue_dispatch_assignment",
                    repo=repo_path,
                    number=issue_number,
                    number_kind="issue_number",
                    auth_lane="dispatch_user_token",
                    api_type="GraphQL",
                    success=False,
                    summary=result.summary,
                )
                return result
            suggested_actor_logins = _extract_suggested_actor_logins(preflight_payload)
            preflight_summary = _suggested_actors_summary(suggested_actor_logins)
            normalized_suggested_actor_logins = {
                normalize_copilot_login(login) for login in suggested_actor_logins
            }
            if expected_assignee_login not in normalized_suggested_actor_logins:
                result = DispatchResult(
                    attempted=True,
                    accepted=False,
                    manual_required=True,
                    state="blocked",
                    summary=(
                        "Actor assignment blocked: Copilot cloud agent not enabled or not assignable in this repository. "
                        f"{preflight_summary}. "
                        f"{dispatch_mode_summary}"
                    ),
                    api_status_code=preflight_response.status_code,
                )
                _log_github_action(
                    action="issue_dispatch_assignment",
                    repo=repo_path,
                    number=issue_number,
                    number_kind="issue_number",
                    auth_lane="dispatch_user_token",
                    api_type="GraphQL",
                    success=False,
                    summary=result.summary,
                )
                return result

            request_payload = build_dispatch_request_payload(settings, task)
            requested_custom_agent = (request_payload.get("agent_assignment") or {}).get("custom_agent")
            assign_response = client.post(
                assign_url,
                headers=_build_dispatch_headers(settings),
                json=request_payload,
            )
            if assign_response.status_code >= 400:
                details = assign_response.text[:500]
                manual = assign_response.status_code in {401, 403, 404, 422}
                result = DispatchResult(
                    attempted=True,
                    accepted=False,
                    manual_required=manual,
                    state="blocked" if manual else "failed",
                    summary=(
                        "Actor assignment failed: GitHub Copilot dispatch assignment failed "
                        f"({assign_response.status_code}): {details} "
                        f"{preflight_summary}. "
                        f"{dispatch_mode_summary}"
                    ),
                    api_status_code=assign_response.status_code,
                )
                _log_github_action(
                    action="issue_dispatch_assignment",
                    repo=repo_path,
                    number=issue_number,
                    number_kind="issue_number",
                    auth_lane="dispatch_user_token",
                    api_type="REST",
                    success=False,
                    summary=result.summary,
                )
                return result

            assign_payload = (
                assign_response.json()
                if assign_response.headers.get("content-type", "").startswith("application/json")
                else {}
            )
            raw_assignee_logins = sorted(_extract_assignee_logins(assign_payload))
            assignee_logins = {normalize_copilot_login(login) for login in raw_assignee_logins}
            if expected_assignee_login not in assignee_logins:
                result = DispatchResult(
                    attempted=True,
                    accepted=False,
                    manual_required=True,
                    state="blocked",
                    summary=(
                        "Actor assignment failed: GitHub accepted the request but Copilot assignee was not applied; "
                        "manual dispatch needed. "
                        f"expected={expected_assignee_login}; "
                        f"actual={raw_assignee_logins or ['(none)']}; "
                        f"normalization_applied={normalization_applied}; "
                        f"{preflight_summary}. "
                        f"{dispatch_mode_summary}"
                    ),
                    api_status_code=assign_response.status_code,
                )
                _log_github_action(
                    action="issue_dispatch_assignment",
                    repo=repo_path,
                    number=issue_number,
                    number_kind="issue_number",
                    auth_lane="dispatch_user_token",
                    api_type="REST",
                    success=False,
                    summary=result.summary,
                )
                return result

            dispatch_id = str(assign_payload.get("id")) if assign_payload.get("id") is not None else None
            dispatch_url = assign_payload.get("html_url")
            comment_warning: str | None = None
            comment_response = client.post(
                comment_url,
                headers=_build_dispatch_headers(settings),
                json={
                    "body": _task_packet_comment(
                        task,
                        target_branch=settings.copilot_target_branch,
                        execution_mode=dispatch_mode,
                        linkage_tag=linkage_tag,
                    )
                },
            )
            if comment_response.status_code >= 400:
                comment_warning = (
                    f" Task packet comment failed ({comment_response.status_code}): "
                    f"{comment_response.text[:200]}"
                )
            result = DispatchResult(
                attempted=True,
                accepted=True,
                manual_required=False,
                state="accepted",
                summary=(
                    "Actor assignment succeeded: Copilot assignment request accepted via issues assignee API"
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
            _log_github_action(
                action="issue_dispatch_assignment",
                repo=repo_path,
                number=issue_number,
                number_kind="issue_number",
                auth_lane="dispatch_user_token",
                api_type="GraphQL+REST",
                success=True,
                summary=result.summary,
            )
            return result
    except Exception as exc:
        result = DispatchResult(
            attempted=True,
            accepted=False,
            manual_required=True,
            state="blocked",
            summary=f"Dispatch auth/assignment failure: {exc}. {dispatch_mode_summary}",
        )
        _log_github_action(
            action="issue_dispatch_assignment",
            repo=repo_path,
            number=issue_number,
            number_kind="issue_number",
            auth_lane="dispatch_user_token",
            api_type="GraphQL+REST",
            success=False,
            summary=result.summary,
        )
        return result


def mark_pr_ready_for_review(*, settings: Settings, repo: str, pr_number: int) -> tuple[bool, str]:
    """Attempt to convert a draft PR to ready-for-review.

    Returns (success, message).  Safe to call when the PR is already non-draft.
    """
    action = "mark_pr_ready_for_review"
    _log_github_debug(
        settings,
        event="ready_for_review_attempted",
        repo=repo,
        pr_number=pr_number,
        auth_lane="dispatch_user_token",
        api_type="GraphQL",
        success=True,
        summary="Starting ready-for-review flow.",
    )
    if not has_dispatch_auth(settings):
        msg = (
            "Ready-for-review failure: dispatch user-token auth not configured; "
            "cannot mark PR ready for review"
        )
        _log_github_action(
            action=action,
            repo=repo,
            number=pr_number,
            number_kind="pr_number",
            auth_lane="dispatch_user_token",
            api_type="GraphQL",
            success=False,
            summary=msg,
        )
        return False, msg
    api_base = settings.github_api_url.rstrip("/")
    graphql_url = f"{api_base}/graphql"
    repo_parts = _extract_repo_owner_name(repo)
    if repo_parts is None:
        msg = f"Invalid repository path {repo!r}; cannot mark PR #{pr_number} ready for review"
        _log_github_action(
            action=action,
            repo=repo,
            number=pr_number,
            number_kind="pr_number",
            auth_lane="dispatch_user_token",
            api_type="GraphQL",
            success=False,
            summary=msg,
        )
        return False, msg
    owner, name = repo_parts
    logger.info(
        "github_action=%s repo=%s pr_number=%s auth_lane=dispatch_user_token api_type=GraphQL mutation=markPullRequestReadyForReview step=prepare",
        action,
        repo,
        pr_number,
    )
    try:
        with httpx.Client(timeout=15.0) as client:
            pr_query_response = client.post(
                graphql_url,
                headers=_build_dispatch_headers(settings),
                json={
                    "query": _PULL_REQUEST_ID_QUERY,
                    "variables": {"owner": owner, "name": name, "number": pr_number},
                },
            )
            if pr_query_response.status_code >= 400:
                msg = (
                    f"GitHub returned {pr_query_response.status_code} when preparing ready-for-review "
                    f"for PR #{pr_number}: {pr_query_response.text[:300]}"
                )
                _log_github_action(
                    action=action,
                    repo=repo,
                    number=pr_number,
                    number_kind="pr_number",
                    auth_lane="dispatch_user_token",
                    api_type="GraphQL",
                    success=False,
                    summary=f"Ready-for-review failure: {msg}",
                )
                return False, f"Ready-for-review failure: {msg}"
            _log_github_debug(
                settings,
                event="ready_for_review_node_lookup",
                repo=repo,
                pr_number=pr_number,
                auth_lane="dispatch_user_token",
                api_type="GraphQL",
                success=True,
                http_status=pr_query_response.status_code,
                result_class="query_ok",
                summary="PR node-id lookup attempted.",
            )

            query_payload = pr_query_response.json()
            if query_payload.get("errors"):
                msg = (
                    f"GitHub GraphQL errors when preparing ready-for-review for PR #{pr_number}: "
                    f"{str(query_payload.get('errors'))[:300]}"
                )
                _log_github_action(
                    action=action,
                    repo=repo,
                    number=pr_number,
                    number_kind="pr_number",
                    auth_lane="dispatch_user_token",
                    api_type="GraphQL",
                    success=False,
                    summary=f"Ready-for-review failure: {msg}",
                )
                return False, f"Ready-for-review failure: {msg}"

            pull_request = (((query_payload.get("data") or {}).get("repository") or {}).get("pullRequest") or {})
            pull_request_id = pull_request.get("id")
            if not isinstance(pull_request_id, str) or not pull_request_id.strip():
                msg = f"PR #{pr_number} not found via GraphQL; cannot mark ready for review"
                _log_github_action(
                    action=action,
                    repo=repo,
                    number=pr_number,
                    number_kind="pr_number",
                    auth_lane="dispatch_user_token",
                    api_type="GraphQL",
                    success=False,
                    summary=f"Ready-for-review failure: {msg}",
                )
                return False, f"Ready-for-review failure: {msg}"
            _log_github_debug(
                settings,
                event="ready_for_review_node_lookup",
                repo=repo,
                pr_number=pr_number,
                auth_lane="dispatch_user_token",
                api_type="GraphQL",
                success=True,
                result_class="node_found",
                summary=f"PR node id located; draft={pull_request.get('isDraft')!r}",
            )

            if pull_request.get("isDraft") is False:
                msg = f"PR #{pr_number} is already ready for review"
                _log_github_action(
                    action=action,
                    repo=repo,
                    number=pr_number,
                    number_kind="pr_number",
                    auth_lane="dispatch_user_token",
                    api_type="GraphQL",
                    success=True,
                    summary=f"{msg}; post_mutation_is_draft=False",
                )
                return True, msg

            mutation_response = client.post(
                graphql_url,
                headers=_build_dispatch_headers(settings),
                json={
                    "query": _MARK_PR_READY_MUTATION,
                    "variables": {"pullRequestId": pull_request_id},
                },
            )
            if mutation_response.status_code >= 400:
                msg = (
                    f"GitHub returned {mutation_response.status_code} when marking PR #{pr_number} ready for review: "
                    f"{mutation_response.text[:300]}"
                )
                _log_github_action(
                    action=action,
                    repo=repo,
                    number=pr_number,
                    number_kind="pr_number",
                    auth_lane="dispatch_user_token",
                    api_type="GraphQL",
                    success=False,
                    summary=f"Ready-for-review failure: mutation=markPullRequestReadyForReview; {msg}",
                )
                return False, f"Ready-for-review failure: {msg}"
            _log_github_debug(
                settings,
                event="ready_for_review_mutation_attempted",
                repo=repo,
                pr_number=pr_number,
                auth_lane="dispatch_user_token",
                api_type="GraphQL",
                success=True,
                http_status=mutation_response.status_code,
                result_class="mutation_http_ok",
                summary="markPullRequestReadyForReview mutation attempted.",
            )

            mutation_payload = mutation_response.json()
            if mutation_payload.get("errors"):
                msg = (
                    f"GitHub GraphQL errors when marking PR #{pr_number} ready for review: "
                    f"{str(mutation_payload.get('errors'))[:300]}"
                )
                _log_github_action(
                    action=action,
                    repo=repo,
                    number=pr_number,
                    number_kind="pr_number",
                    auth_lane="dispatch_user_token",
                    api_type="GraphQL",
                    success=False,
                    summary=f"Ready-for-review failure: mutation=markPullRequestReadyForReview; {msg}",
                )
                return False, f"Ready-for-review failure: {msg}"

            post_mutation_draft_state = (
                ((mutation_payload.get("data") or {}).get("markPullRequestReadyForReview") or {}).get("pullRequest")
                or {}
            ).get("isDraft")
            # Required postcondition verification: re-read PR draft state.
            verify_response = client.post(
                graphql_url,
                headers=_build_dispatch_headers(settings),
                json={
                    "query": _PULL_REQUEST_ID_QUERY,
                    "variables": {"owner": owner, "name": name, "number": pr_number},
                },
            )
            if verify_response.status_code >= 400:
                msg = (
                    f"GitHub returned {verify_response.status_code} when verifying ready-for-review "
                    f"for PR #{pr_number}: {verify_response.text[:300]}"
                )
                _log_github_action(
                    action=action,
                    repo=repo,
                    number=pr_number,
                    number_kind="pr_number",
                    auth_lane="dispatch_user_token",
                    api_type="GraphQL",
                    success=False,
                    summary=f"Ready-for-review failure: verify step; {msg}",
                )
                return False, f"Ready-for-review failure: {msg}"
            verify_payload = verify_response.json()
            if verify_payload.get("errors"):
                msg = (
                    f"GitHub GraphQL errors when verifying ready-for-review for PR #{pr_number}: "
                    f"{str(verify_payload.get('errors'))[:300]}"
                )
                _log_github_action(
                    action=action,
                    repo=repo,
                    number=pr_number,
                    number_kind="pr_number",
                    auth_lane="dispatch_user_token",
                    api_type="GraphQL",
                    success=False,
                    summary=f"Ready-for-review failure: verify step; {msg}",
                )
                return False, f"Ready-for-review failure: {msg}"
            post_verify_draft_state = (
                ((verify_payload.get("data") or {}).get("repository") or {}).get("pullRequest") or {}
            ).get("isDraft")
            if post_verify_draft_state is not False:
                msg = (
                    "Ready-for-review postcondition failed: expected draft=False after mutation, "
                    f"observed draft={post_verify_draft_state!r}"
                )
                _log_github_action(
                    action=action,
                    repo=repo,
                    number=pr_number,
                    number_kind="pr_number",
                    auth_lane="dispatch_user_token",
                    api_type="GraphQL",
                    success=False,
                    summary=msg,
                )
                return False, msg
            _log_github_debug(
                settings,
                event="ready_for_review_verified",
                repo=repo,
                pr_number=pr_number,
                auth_lane="dispatch_user_token",
                api_type="GraphQL",
                success=True,
                result_class="verified_non_draft",
                postcondition=f"isDraft={post_verify_draft_state!r}",
                summary="Ready-for-review postcondition verified; proceeding.",
            )

            msg = f"PR #{pr_number} marked ready for review"
            _log_github_action(
                action=action,
                repo=repo,
                number=pr_number,
                number_kind="pr_number",
                auth_lane="dispatch_user_token",
                api_type="GraphQL",
                success=True,
                summary=(
                    f"{msg}; mutation=markPullRequestReadyForReview; "
                    f"post_mutation_is_draft={post_mutation_draft_state!r}; "
                    f"post_verify_is_draft={post_verify_draft_state!r}"
                ),
            )
            return True, msg
    except Exception as exc:
        msg = f"Failed to mark PR #{pr_number} ready for review: {exc}"
        _log_github_action(
            action=action,
            repo=repo,
            number=pr_number,
            number_kind="pr_number",
            auth_lane="dispatch_user_token",
            api_type="GraphQL",
            success=False,
            summary=f"Ready-for-review failure: {msg}",
        )
        return False, f"Ready-for-review failure: {msg}"


def merge_pr(
    *,
    settings: Settings,
    repo: str,
    pr_number: int,
    merge_method: str = "squash",
) -> tuple[bool, str]:
    """Attempt to merge a PR via the GitHub REST API.

    Returns (success, message).

    Status codes:
    - 200/204: merged successfully
    - 403: insufficient token permissions (contents:write required)
    - 405: merge not allowed (protected branch, checks still running, etc.)
    - 409: merge conflict
    - 422: unprocessable (e.g., already merged, branch deleted)
    """
    if not has_dispatch_auth(settings):
        return False, "Merge failure: dispatch user-token auth not configured; cannot merge PR"
    _log_github_debug(
        settings,
        event="merge_attempted",
        repo=repo,
        pr_number=pr_number,
        auth_lane="dispatch_user_token",
        api_type="REST",
        success=True,
        summary="Starting merge flow with latest SHA fetch.",
    )
    api_base = settings.github_api_url.rstrip("/")
    pr_url = f"{api_base}/repos/{repo}/pulls/{pr_number}"
    merge_url = f"{api_base}/repos/{repo}/pulls/{pr_number}/merge"

    def _fetch_latest_head_and_merge_state(client: httpx.Client) -> tuple[str | None, bool | None, str]:
        response = client.get(pr_url, headers=_build_dispatch_headers(settings))
        if response.status_code >= 400:
            return None, None, (
                f"PR lifecycle automation failure: GitHub returned {response.status_code} when fetching PR #{pr_number} "
                f"before merge: {response.text[:300]}"
            )
        payload = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
        head = payload.get("head") if isinstance(payload.get("head"), dict) else {}
        head_sha = head.get("sha") if isinstance(head.get("sha"), str) else None
        merged_state = payload.get("merged")
        merged = bool(merged_state) if merged_state is not None else None
        if not head_sha:
            return None, merged, f"PR lifecycle automation failure: Missing head.sha for PR #{pr_number}; cannot merge"
        return head_sha, merged, "ok"

    def _attempt_merge(client: httpx.Client, *, head_sha: str) -> tuple[bool, int, str]:
        response = client.put(
            merge_url,
            headers=_build_dispatch_headers(settings),
            json={"merge_method": merge_method, "sha": head_sha},
        )
        if response.status_code in {200, 204}:
            return True, response.status_code, "ok"
        return False, response.status_code, response.text[:300]

    try:
        with httpx.Client(timeout=15.0) as client:
            first_head_sha, already_merged, first_fetch_msg = _fetch_latest_head_and_merge_state(client)
            if already_merged is True:
                msg = f"PR #{pr_number} already merged (merge_observed=True)"
                _log_github_action(
                    action="merge_pr",
                    repo=repo,
                    number=pr_number,
                    number_kind="pr_number",
                    auth_lane="dispatch_user_token",
                    api_type="REST",
                    success=True,
                    summary=msg,
                )
                return True, msg
            if first_head_sha is None:
                _log_github_action(
                    action="merge_pr",
                    repo=repo,
                    number=pr_number,
                    number_kind="pr_number",
                    auth_lane="dispatch_user_token",
                    api_type="REST",
                    success=False,
                    summary=first_fetch_msg,
                )
                return False, first_fetch_msg
            _log_github_debug(
                settings,
                event="merge_latest_sha_fetched",
                repo=repo,
                pr_number=pr_number,
                auth_lane="dispatch_user_token",
                api_type="REST",
                success=True,
                result_class="head_sha_loaded",
                summary=f"Fetched latest head SHA before merge: {first_head_sha}",
            )

            merged, status_code, detail = _attempt_merge(client, head_sha=first_head_sha)
            merge_attempt_sha = first_head_sha
            retry_used = False
            if not merged and status_code == 409:
                _log_github_debug(
                    settings,
                    event="merge_retry_409",
                    repo=repo,
                    pr_number=pr_number,
                    auth_lane="dispatch_user_token",
                    api_type="REST",
                    success=False,
                    http_status=409,
                    result_class="merge_conflict_retry",
                    summary="First merge attempt returned 409; retrying with refreshed SHA.",
                )
                refreshed_head_sha, _, refresh_msg = _fetch_latest_head_and_merge_state(client)
                if refreshed_head_sha is None:
                    _log_github_action(
                        action="merge_pr",
                        repo=repo,
                        number=pr_number,
                        number_kind="pr_number",
                        auth_lane="dispatch_user_token",
                        api_type="REST",
                        success=False,
                        summary=f"Merge retry prep failed after 409: {refresh_msg}",
                    )
                    return False, f"Merge retry prep failed after 409: {refresh_msg}"
                retry_used = True
                merge_attempt_sha = refreshed_head_sha
                merged, status_code, detail = _attempt_merge(client, head_sha=refreshed_head_sha)

            if not merged:
                msg = (
                    f"PR lifecycle automation failure: GitHub returned {status_code} when merging PR #{pr_number}: {detail} "
                    f"(merge_sha={merge_attempt_sha}, retry_used={retry_used})"
                )
                _log_github_action(
                    action="merge_pr",
                    repo=repo,
                    number=pr_number,
                    number_kind="pr_number",
                    auth_lane="dispatch_user_token",
                    api_type="REST",
                    success=False,
                    summary=msg,
                )
                return False, msg

            _, merged_after, verify_msg = _fetch_latest_head_and_merge_state(client)
            if merged_after is not True:
                msg = (
                    "PR lifecycle automation failure: Merge API returned success but merged postcondition verification "
                    f"did not observe merged=true for PR #{pr_number}. detail={verify_msg}"
                )
                _log_github_action(
                    action="merge_pr",
                    repo=repo,
                    number=pr_number,
                    number_kind="pr_number",
                    auth_lane="dispatch_user_token",
                    api_type="REST",
                    success=False,
                    summary=msg,
                )
                return False, msg
            _log_github_debug(
                settings,
                event="merge_verified",
                repo=repo,
                pr_number=pr_number,
                auth_lane="dispatch_user_token",
                api_type="REST",
                success=True,
                result_class="merged_true",
                postcondition="merged=true",
                summary=f"Merge verified after sha={merge_attempt_sha}",
            )
            msg = (
                f"PR #{pr_number} merged successfully "
                f"(merge_sha={merge_attempt_sha}, retry_used={retry_used}, merge_observed=True)"
            )
            _log_github_action(
                action="merge_pr",
                repo=repo,
                number=pr_number,
                number_kind="pr_number",
                auth_lane="dispatch_user_token",
                api_type="REST",
                success=True,
                summary=msg,
            )
            return True, msg
    except Exception as exc:
        msg = f"PR lifecycle automation failure: Failed to merge PR #{pr_number}: {exc}"
        _log_github_action(
            action="merge_pr",
            repo=repo,
            number=pr_number,
            number_kind="pr_number",
            auth_lane="dispatch_user_token",
            api_type="REST",
            success=False,
            summary=msg,
        )
        return False, msg


def inspect_pull_request(*, settings: Settings, repo: str, pr_number: int) -> PullRequestInspection:
    if not has_governor_auth(settings):
        return PullRequestInspection(
            ok=False,
            changed_files=None,
            commits=None,
            draft=None,
            state=None,
            merged=None,
            summary="Governor auth failure: auth not configured; cannot inspect PR",
        )
    api_base = settings.github_api_url.rstrip("/")
    url = f"{api_base}/repos/{repo}/pulls/{pr_number}"
    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.get(url, headers=_build_governor_headers(settings))
            if response.status_code >= 400:
                return PullRequestInspection(
                    ok=False,
                    changed_files=None,
                    commits=None,
                    draft=None,
                    state=None,
                    merged=None,
                    summary=f"PR lifecycle automation failure: GitHub returned {response.status_code} when inspecting PR #{pr_number}: {response.text[:300]}",
                )
            payload = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
            changed_files_raw = payload.get("changed_files")
            commits_raw = payload.get("commits")
            return PullRequestInspection(
                ok=True,
                changed_files=int(changed_files_raw) if isinstance(changed_files_raw, int) else None,
                commits=int(commits_raw) if isinstance(commits_raw, int) else None,
                draft=bool(payload.get("draft")) if payload.get("draft") is not None else None,
                state=str(payload.get("state") or "") or None,
                merged=bool(payload.get("merged")) if payload.get("merged") is not None else None,
                summary=f"PR #{pr_number} inspected successfully",
            )
    except Exception as exc:
        return PullRequestInspection(
            ok=False,
            changed_files=None,
            commits=None,
            draft=None,
            state=None,
            merged=None,
            summary=f"PR lifecycle automation failure: Failed to inspect PR #{pr_number}: {exc}",
        )


def list_recent_pull_requests(*, settings: Settings, repo: str, limit: int = 30) -> tuple[list[dict[str, Any]], str]:
    if not has_dispatch_auth(settings):
        return [], "Dispatch auth failure: dispatch user-token auth not configured; cannot list recent PRs"
    bounded_limit = max(1, min(int(limit or 30), 100))
    api_base = settings.github_api_url.rstrip("/")
    url = f"{api_base}/repos/{repo}/pulls?state=open&sort=created&direction=desc&per_page={bounded_limit}"
    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.get(url, headers=_build_dispatch_headers(settings))
            if response.status_code >= 400:
                return [], (
                    f"PR discovery failure: GitHub returned {response.status_code} when listing recent PRs: "
                    f"{response.text[:300]}"
                )
            if not response.headers.get("content-type", "").startswith("application/json"):
                return [], "PR discovery failure: GitHub returned non-JSON recent PR list"
            payload = response.json()
            if not isinstance(payload, list):
                return [], "PR discovery failure: GitHub returned invalid recent PR list"
            prs = [item for item in payload if isinstance(item, dict)]
            return prs, f"Fetched {len(prs)} recent PR candidates"
    except Exception as exc:
        return [], f"PR discovery failure: Failed to list recent PRs: {exc}"


def list_issue_timeline_events(
    *,
    settings: Settings,
    repo: str,
    issue_number: int,
    limit: int = 30,
) -> tuple[list[dict[str, Any]], str]:
    if not has_dispatch_auth(settings):
        return [], "Dispatch auth failure: dispatch user-token auth not configured; cannot list issue timeline events"
    bounded_limit = max(1, min(int(limit or 30), 100))
    api_base = settings.github_api_url.rstrip("/")
    url = f"{api_base}/repos/{repo}/issues/{issue_number}/timeline?per_page={bounded_limit}"
    headers = _build_dispatch_headers(settings)
    accept = headers.get("Accept")
    if accept:
        headers["Accept"] = f"{accept}, application/vnd.github+json"
    else:
        headers["Accept"] = "application/vnd.github+json"
    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.get(url, headers=headers)
            if response.status_code >= 400:
                return [], (
                    "PR association failure: GitHub returned "
                    f"{response.status_code} when listing timeline for issue #{issue_number}: {response.text[:300]}"
                )
            if not response.headers.get("content-type", "").startswith("application/json"):
                return [], f"PR association failure: GitHub returned non-JSON timeline for issue #{issue_number}"
            payload = response.json()
            if not isinstance(payload, list):
                return [], f"PR association failure: GitHub returned invalid timeline for issue #{issue_number}"
            events = [item for item in payload if isinstance(item, dict)]
            return events, f"Fetched {len(events)} timeline events for issue #{issue_number}"
    except Exception as exc:
        return [], f"PR association failure: Failed to list timeline for issue #{issue_number}: {exc}"


def lookup_pr_linked_issue_numbers(
    *,
    settings: Settings,
    repo: str,
    pr_number: int,
    timeline_limit: int = 40,
) -> tuple[set[int], str]:
    auth_lane = "dispatch_user_token"
    if not has_dispatch_auth(settings):
        summary = "Dispatch auth failure: dispatch user-token auth not configured; cannot query PR graph links"
        _log_github_debug(
            settings,
            event="lookup_pr_linked_issue_numbers",
            repo=repo,
            pr_number=pr_number,
            auth_lane=auth_lane,
            api_type="graphql",
            success=False,
            http_status=None,
            result_class="dispatch_auth_missing",
            summary=summary,
            postcondition="no_lookup_performed",
        )
        return set(), summary
    repo_parts = _extract_repo_owner_name(repo)
    if repo_parts is None:
        summary = f"PR association failure: Invalid repository path: {repo!r}"
        _log_github_debug(
            settings,
            event="lookup_pr_linked_issue_numbers",
            repo=repo,
            pr_number=pr_number,
            auth_lane=auth_lane,
            api_type="graphql",
            success=False,
            http_status=None,
            result_class="invalid_repo",
            summary=summary,
            postcondition="no_lookup_performed",
        )
        return set(), summary
    owner, name = repo_parts
    api_base = settings.github_api_url.rstrip("/")
    graphql_url = f"{api_base}/graphql"
    bounded_timeline_limit = max(1, min(int(timeline_limit or 40), 100))
    normalized_repo = repo.strip().lower()

    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.post(
                graphql_url,
                headers=_build_dispatch_headers(settings),
                json={
                    "query": _PULL_REQUEST_LINKED_ISSUES_QUERY,
                    "variables": {
                        "owner": owner,
                        "name": name,
                        "number": pr_number,
                        "timelineLimit": bounded_timeline_limit,
                    },
                },
            )
            if response.status_code >= 400:
                summary = (
                    "PR association failure: GitHub returned "
                    f"{response.status_code} when querying GraphQL links for PR #{pr_number}: {response.text[:300]}"
                )
                _log_github_debug(
                    settings,
                    event="lookup_pr_linked_issue_numbers",
                    repo=repo,
                    pr_number=pr_number,
                    auth_lane=auth_lane,
                    api_type="graphql",
                    success=False,
                    http_status=response.status_code,
                    result_class="http_error",
                    summary=summary,
                    postcondition="lookup_failed",
                )
                return set(), summary
            if not response.headers.get("content-type", "").startswith("application/json"):
                summary = f"PR association failure: GitHub returned non-JSON GraphQL response for PR #{pr_number}"
                _log_github_debug(
                    settings,
                    event="lookup_pr_linked_issue_numbers",
                    repo=repo,
                    pr_number=pr_number,
                    auth_lane=auth_lane,
                    api_type="graphql",
                    success=False,
                    http_status=response.status_code,
                    result_class="non_json_response",
                    summary=summary,
                    postcondition="lookup_failed",
                )
                return set(), summary
            payload = response.json()
            if not isinstance(payload, dict):
                summary = f"PR association failure: GitHub returned invalid GraphQL payload for PR #{pr_number}"
                _log_github_debug(
                    settings,
                    event="lookup_pr_linked_issue_numbers",
                    repo=repo,
                    pr_number=pr_number,
                    auth_lane=auth_lane,
                    api_type="graphql",
                    success=False,
                    http_status=response.status_code,
                    result_class="invalid_payload",
                    summary=summary,
                    postcondition="lookup_failed",
                )
                return set(), summary
            errors = payload.get("errors")
            if isinstance(errors, list) and errors:
                summary = f"PR association failure: GraphQL returned errors for PR #{pr_number}: {str(errors)[:300]}"
                _log_github_debug(
                    settings,
                    event="lookup_pr_linked_issue_numbers",
                    repo=repo,
                    pr_number=pr_number,
                    auth_lane=auth_lane,
                    api_type="graphql",
                    success=False,
                    http_status=response.status_code,
                    result_class="graphql_errors",
                    summary=summary,
                    postcondition="lookup_failed",
                )
                return set(), summary
            data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
            repository = data.get("repository") if isinstance(data.get("repository"), dict) else {}
            pr = repository.get("pullRequest") if isinstance(repository.get("pullRequest"), dict) else {}
            if not pr:
                summary = f"PR association failure: GraphQL returned no pullRequest node for PR #{pr_number}"
                _log_github_debug(
                    settings,
                    event="lookup_pr_linked_issue_numbers",
                    repo=repo,
                    pr_number=pr_number,
                    auth_lane=auth_lane,
                    api_type="graphql",
                    success=False,
                    http_status=response.status_code,
                    result_class="missing_pull_request",
                    summary=summary,
                    postcondition="lookup_failed",
                )
                return set(), summary

            linked_issue_numbers: set[int] = set()
            closing = pr.get("closingIssuesReferences") if isinstance(pr.get("closingIssuesReferences"), dict) else {}
            for node in closing.get("nodes") or []:
                if not isinstance(node, dict):
                    continue
                issue_number = node.get("number")
                repo_obj = node.get("repository") if isinstance(node.get("repository"), dict) else {}
                node_repo = str(repo_obj.get("nameWithOwner") or "").strip().lower()
                if isinstance(issue_number, int) and (not node_repo or node_repo == normalized_repo):
                    linked_issue_numbers.add(issue_number)

            timeline = pr.get("timelineItems") if isinstance(pr.get("timelineItems"), dict) else {}
            for node in timeline.get("nodes") or []:
                if not isinstance(node, dict):
                    continue
                typename = str(node.get("__typename") or "")
                issue_node: dict[str, Any] | None = None
                if typename == "ConnectedEvent":
                    subject = node.get("subject") if isinstance(node.get("subject"), dict) else {}
                    if str(subject.get("__typename") or "") == "Issue":
                        issue_node = subject
                elif typename == "CrossReferencedEvent":
                    source = node.get("source") if isinstance(node.get("source"), dict) else {}
                    if str(source.get("__typename") or "") == "Issue":
                        issue_node = source
                if issue_node is None:
                    continue
                issue_number = issue_node.get("number")
                repo_obj = issue_node.get("repository") if isinstance(issue_node.get("repository"), dict) else {}
                issue_repo = str(repo_obj.get("nameWithOwner") or "").strip().lower()
                if isinstance(issue_number, int) and (not issue_repo or issue_repo == normalized_repo):
                    linked_issue_numbers.add(issue_number)
            summary = (
                f"GraphQL linked-issue lookup resolved {len(linked_issue_numbers)} linked issue(s) "
                f"for PR #{pr_number}: {sorted(linked_issue_numbers)}"
            )
            _log_github_debug(
                settings,
                event="lookup_pr_linked_issue_numbers",
                repo=repo,
                pr_number=pr_number,
                auth_lane=auth_lane,
                api_type="graphql",
                success=True,
                http_status=response.status_code,
                result_class="linked_issues_resolved" if linked_issue_numbers else "linked_issues_empty",
                summary=summary,
                postcondition="lookup_completed",
            )
            return linked_issue_numbers, summary
    except Exception as exc:
        summary = f"PR association failure: Failed GraphQL linked-issue lookup for PR #{pr_number}: {exc}"
        _log_github_debug(
            settings,
            event="lookup_pr_linked_issue_numbers",
            repo=repo,
            pr_number=pr_number,
            auth_lane=auth_lane,
            api_type="graphql",
            success=False,
            http_status=None,
            result_class="exception",
            summary=summary,
            postcondition="lookup_failed",
        )
        return set(), summary


def remove_requested_reviewers(
    *,
    settings: Settings,
    repo: str,
    pr_number: int,
    reviewers: list[str],
) -> tuple[bool, str]:
    if not has_governor_auth(settings):
        return False, "Governor auth failure: auth not configured; cannot remove PR reviewers"
    sanitized = sorted({item.strip() for item in reviewers if isinstance(item, str) and item.strip()})
    if not sanitized:
        return True, "No reviewers requested for removal"
    api_base = settings.github_api_url.rstrip("/")
    url = f"{api_base}/repos/{repo}/pulls/{pr_number}/requested_reviewers"
    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.request(
                "DELETE",
                url,
                headers=_build_governor_headers(settings),
                json={"reviewers": sanitized},
            )
            if response.status_code >= 400:
                msg = (
                    f"PR lifecycle automation failure: GitHub returned {response.status_code} when removing requested reviewers from PR #{pr_number}: "
                    f"{response.text[:300]}"
                )
                _log_github_action(
                    action="remove_requested_reviewers",
                    repo=repo,
                    number=pr_number,
                    number_kind="pr_number",
                    auth_lane="governor",
                    api_type="REST",
                    success=False,
                    summary=msg,
                )
                return False, msg
            msg = f"Removed requested reviewers from PR #{pr_number}: {sanitized}"
            _log_github_action(
                action="remove_requested_reviewers",
                repo=repo,
                number=pr_number,
                number_kind="pr_number",
                auth_lane="governor",
                api_type="REST",
                success=True,
                summary=msg,
            )
            return True, msg
    except Exception as exc:
        msg = f"PR lifecycle automation failure: Failed to remove requested reviewers from PR #{pr_number}: {exc}"
        _log_github_action(
            action="remove_requested_reviewers",
            repo=repo,
            number=pr_number,
            number_kind="pr_number",
            auth_lane="governor",
            api_type="REST",
            success=False,
            summary=msg,
        )
        return False, msg


def request_reviewers(
    *,
    settings: Settings,
    repo: str,
    pr_number: int,
    reviewers: list[str],
) -> tuple[bool, str]:
    if not has_governor_auth(settings):
        return False, "Governor auth failure: auth not configured; cannot request PR reviewers"
    sanitized = sorted({item.strip() for item in reviewers if isinstance(item, str) and item.strip()})
    if not sanitized:
        return True, "No reviewers requested"
    api_base = settings.github_api_url.rstrip("/")
    url = f"{api_base}/repos/{repo}/pulls/{pr_number}/requested_reviewers"
    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.post(
                url,
                headers=_build_governor_headers(settings),
                json={"reviewers": sanitized},
            )
            if response.status_code >= 400:
                return False, f"PR lifecycle automation failure: GitHub returned {response.status_code} when requesting reviewers on PR #{pr_number}: {response.text[:300]}"
            return True, f"Requested reviewers for PR #{pr_number}: {sanitized}"
    except Exception as exc:
        return False, f"PR lifecycle automation failure: Failed to request reviewers for PR #{pr_number}: {exc}"


def list_pull_request_reviews(*, settings: Settings, repo: str, pr_number: int) -> tuple[list[dict[str, Any]], str]:
    if not has_governor_auth(settings):
        return [], "Governor auth failure: auth not configured; cannot list PR reviews"
    api_base = settings.github_api_url.rstrip("/")
    url = f"{api_base}/repos/{repo}/pulls/{pr_number}/reviews?per_page=100"
    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.get(url, headers=_build_governor_headers(settings))
            if response.status_code >= 400:
                return [], f"PR lifecycle automation failure: GitHub returned {response.status_code} when listing reviews for PR #{pr_number}: {response.text[:300]}"
            if not response.headers.get("content-type", "").startswith("application/json"):
                return [], f"GitHub returned non-JSON review list for PR #{pr_number}"
            payload = response.json()
            if not isinstance(payload, list):
                return [], f"GitHub returned invalid review list for PR #{pr_number}"
            reviews = [item for item in payload if isinstance(item, dict)]
            return reviews, f"Fetched {len(reviews)} reviews for PR #{pr_number}"
    except Exception as exc:
        return [], f"PR lifecycle automation failure: Failed to list reviews for PR #{pr_number}: {exc}"


def list_pull_request_review_comments(*, settings: Settings, repo: str, pr_number: int) -> tuple[list[dict[str, Any]], str]:
    if not has_governor_auth(settings):
        return [], "Governor auth failure: auth not configured; cannot list PR review comments"
    api_base = settings.github_api_url.rstrip("/")
    url = f"{api_base}/repos/{repo}/pulls/{pr_number}/comments?per_page=100"
    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.get(url, headers=_build_governor_headers(settings))
            if response.status_code >= 400:
                return [], (
                    f"PR lifecycle automation failure: GitHub returned {response.status_code} when listing review comments for PR #{pr_number}: "
                    f"{response.text[:300]}"
                )
            if not response.headers.get("content-type", "").startswith("application/json"):
                return [], f"GitHub returned non-JSON review comment list for PR #{pr_number}"
            payload = response.json()
            if not isinstance(payload, list):
                return [], f"GitHub returned invalid review comment list for PR #{pr_number}"
            comments = [item for item in payload if isinstance(item, dict)]
            return comments, f"Fetched {len(comments)} review comments for PR #{pr_number}"
    except Exception as exc:
        return [], f"PR lifecycle automation failure: Failed to list review comments for PR #{pr_number}: {exc}"


def list_pull_request_files(*, settings: Settings, repo: str, pr_number: int) -> tuple[list[str], str]:
    if not has_governor_auth(settings):
        return [], "Governor auth failure: auth not configured; cannot list PR files"
    api_base = settings.github_api_url.rstrip("/")
    url = f"{api_base}/repos/{repo}/pulls/{pr_number}/files?per_page=100"
    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.get(url, headers=_build_governor_headers(settings))
            if response.status_code >= 400:
                return [], f"PR lifecycle automation failure: GitHub returned {response.status_code} when listing files for PR #{pr_number}: {response.text[:300]}"
            if not response.headers.get("content-type", "").startswith("application/json"):
                return [], f"GitHub returned non-JSON file list for PR #{pr_number}"
            payload = response.json()
            if not isinstance(payload, list):
                return [], f"GitHub returned invalid file list for PR #{pr_number}"
            files = []
            for item in payload:
                if not isinstance(item, dict):
                    continue
                filename = item.get("filename")
                if isinstance(filename, str) and filename:
                    files.append(filename)
            return files, f"Fetched {len(files)} files for PR #{pr_number}"
    except Exception as exc:
        return [], f"PR lifecycle automation failure: Failed to list files for PR #{pr_number}: {exc}"


def list_issue_comments(*, settings: Settings, repo: str, issue_number: int) -> tuple[list[dict[str, Any]], str]:
    if not has_governor_auth(settings):
        return [], "Governor auth failure: auth not configured; cannot list issue comments"
    api_base = settings.github_api_url.rstrip("/")
    url = f"{api_base}/repos/{repo}/issues/{issue_number}/comments?per_page=100"
    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.get(url, headers=_build_governor_headers(settings))
            if response.status_code >= 400:
                return [], f"PR lifecycle automation failure: GitHub returned {response.status_code} when listing issue comments #{issue_number}: {response.text[:300]}"
            if not response.headers.get("content-type", "").startswith("application/json"):
                return [], f"GitHub returned non-JSON issue comment list for issue #{issue_number}"
            payload = response.json()
            if not isinstance(payload, list):
                return [], f"GitHub returned invalid issue comment list for issue #{issue_number}"
            comments = [item for item in payload if isinstance(item, dict)]
            return comments, f"Fetched {len(comments)} comments for issue #{issue_number}"
    except Exception as exc:
        return [], f"PR lifecycle automation failure: Failed to list issue comments for issue #{issue_number}: {exc}"


def post_issue_comment(*, settings: Settings, repo: str, issue_number: int, body: str) -> tuple[bool, str]:
    if not has_governor_auth(settings):
        return False, "Governor auth failure: auth not configured; cannot post issue comment"
    comment_body = str(body or "").strip()
    if not comment_body:
        return False, "Comment body is empty"
    api_base = settings.github_api_url.rstrip("/")
    url = f"{api_base}/repos/{repo}/issues/{issue_number}/comments"
    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.post(
                url,
                headers=_build_governor_headers(settings),
                json={"body": comment_body},
            )
            if response.status_code >= 400:
                msg = (
                    f"App-token governor failure: GitHub returned {response.status_code} "
                    f"when posting issue comment on #{issue_number}: {response.text[:300]}"
                )
                _log_github_action(
                    action="post_issue_comment",
                    repo=repo,
                    number=issue_number,
                    number_kind="issue_number",
                    auth_lane="governor",
                    api_type="REST",
                    success=False,
                    summary=msg,
                )
                return False, msg
            msg = f"Posted issue comment on #{issue_number}"
            _log_github_action(
                action="post_issue_comment",
                repo=repo,
                number=issue_number,
                number_kind="issue_number",
                auth_lane="governor",
                api_type="REST",
                success=True,
                summary=msg,
            )
            return True, msg
    except Exception as exc:
        msg = f"App-token governor failure: Failed to post issue comment on #{issue_number}: {exc}"
        _log_github_action(
            action="post_issue_comment",
            repo=repo,
            number=issue_number,
            number_kind="issue_number",
            auth_lane="governor",
            api_type="REST",
            success=False,
            summary=msg,
        )
        return False, msg


def post_copilot_follow_up_comment(
    *,
    settings: Settings,
    repo: str,
    issue_number: int,
    body: str,
) -> tuple[bool, str]:
    if not has_dispatch_auth(settings):
        msg = (
            "Copilot follow-up comment failure: dispatch user-token auth not configured; "
            "cannot post @copilot follow-up comment"
        )
        _log_github_action(
            action="post_copilot_follow_up_comment",
            repo=repo,
            number=issue_number,
            number_kind="issue_number",
            auth_lane="dispatch_user_token",
            api_type="REST",
            success=False,
            summary=msg,
        )
        return False, msg
    comment_body = str(body or "").strip()
    if not comment_body:
        msg = "Copilot follow-up comment failure: comment body is empty"
        _log_github_action(
            action="post_copilot_follow_up_comment",
            repo=repo,
            number=issue_number,
            number_kind="issue_number",
            auth_lane="dispatch_user_token",
            api_type="REST",
            success=False,
            summary=msg,
        )
        return False, msg
    api_base = settings.github_api_url.rstrip("/")
    url = f"{api_base}/repos/{repo}/issues/{issue_number}/comments"
    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.post(
                url,
                headers=_build_dispatch_headers(settings),
                json={"body": comment_body},
            )
            if response.status_code >= 400:
                msg = (
                    f"Copilot follow-up comment failure: GitHub returned {response.status_code} "
                    f"when posting issue comment on #{issue_number}: {response.text[:300]}"
                )
                _log_github_action(
                    action="post_copilot_follow_up_comment",
                    repo=repo,
                    number=issue_number,
                    number_kind="issue_number",
                    auth_lane="dispatch_user_token",
                    api_type="REST",
                    success=False,
                    summary=msg,
                )
                return False, msg
            msg = f"Posted @copilot follow-up comment on #{issue_number}"
            _log_github_action(
                action="post_copilot_follow_up_comment",
                repo=repo,
                number=issue_number,
                number_kind="issue_number",
                auth_lane="dispatch_user_token",
                api_type="REST",
                success=True,
                summary=msg,
            )
            return True, msg
    except Exception as exc:
        msg = f"Copilot follow-up comment failure: Failed to post issue comment on #{issue_number}: {exc}"
        _log_github_action(
            action="post_copilot_follow_up_comment",
            repo=repo,
            number=issue_number,
            number_kind="issue_number",
            auth_lane="dispatch_user_token",
            api_type="REST",
            success=False,
            summary=msg,
        )
        return False, msg


def submit_approving_review(
    *,
    settings: Settings,
    repo: str,
    pr_number: int,
    body: str = "Automated governor approval after successful checks and resolved findings.",
) -> tuple[bool, str]:
    if not has_governor_auth(settings):
        return False, "Governor auth failure: auth not configured; cannot submit approving review"
    api_base = settings.github_api_url.rstrip("/")
    url = f"{api_base}/repos/{repo}/pulls/{pr_number}/reviews"
    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.post(
                url,
                headers=_build_governor_headers(settings),
                json={"event": "APPROVE", "body": body},
            )
            if response.status_code >= 400:
                msg = (
                    f"Merge/approval failure: GitHub returned {response.status_code} when submitting "
                    f"approval review for PR #{pr_number}: {response.text[:300]}"
                )
                _log_github_action(
                    action="submit_approving_review",
                    repo=repo,
                    number=pr_number,
                    number_kind="pr_number",
                    auth_lane="governor",
                    api_type="REST",
                    success=False,
                    summary=msg,
                )
                return False, msg
            msg = f"Submitted approving review for PR #{pr_number}"
            _log_github_action(
                action="submit_approving_review",
                repo=repo,
                number=pr_number,
                number_kind="pr_number",
                auth_lane="governor",
                api_type="REST",
                success=True,
                summary=msg,
            )
            return True, msg
    except Exception as exc:
        msg = f"Merge/approval failure: Failed to submit approving review for PR #{pr_number}: {exc}"
        _log_github_action(
            action="submit_approving_review",
            repo=repo,
            number=pr_number,
            number_kind="pr_number",
            auth_lane="governor",
            api_type="REST",
            success=False,
            summary=msg,
        )
        return False, msg


def run_preflight_checks(*, settings: Settings, repo: str | None = None) -> dict:
    """Run a preflight diagnostic against the current environment configuration.

    Returns a structured dict describing which capabilities are available for
    unattended trusted continuation. Intended for the GET /preflight endpoint.
    """
    dispatch_ready = has_dispatch_auth(settings)
    governor_ready = has_governor_auth(settings)
    governor_is_app = is_governor_app_mode(settings)

    result: dict = {
        "github_auth_mode": governor_auth_mode_label(settings),  # legacy compatibility key
        "github_auth_available": governor_ready,  # legacy compatibility key
        "github_api_token": bool(settings.github_api_token),
        "dispatch_auth_mode": dispatch_auth_label(settings),
        "dispatch_user_token_present": bool(settings.github_dispatch_user_token),
        "dispatch_auth_ready": dispatch_ready,
        "user_token_lane_available": dispatch_ready,
        "governor_auth_mode": governor_auth_mode_label(settings),
        "governor_auth_ready": governor_ready,
        "governor_lane_available": governor_ready,
        "app_token_lane_available": False,
        "token_governor_lane_available": bool((not governor_is_app) and governor_ready),
        "governor_app_config_present": bool(
            settings.github_app_client_id
            and settings.github_app_installation_id
            and settings.github_app_private_key_path
        ),
        "auto_merge_enabled": settings.program_auto_merge,
        "auto_continue_enabled": settings.program_auto_continue,
        "auto_dispatch_enabled": settings.program_auto_dispatch,
        "auto_approve_enabled": settings.program_auto_approve,
        "trusted_kickoff_enabled": settings.program_trusted_auto_confirm,
        "trusted_kickoff_label": settings.trusted_kickoff_label,
        "dispatch_assignee": settings.copilot_dispatch_assignee,
        "copilot_target_branch": settings.copilot_target_branch,
        "governor": {
            "max_revision_cycles": max(1, int(getattr(settings, "governor_max_revision_cycles", 2) or 2)),
            "remove_reviewer_login": str(getattr(settings, "governor_remove_reviewer_login", "") or ""),
            "fallback_reviewer": getattr(settings, "governor_fallback_reviewer", None),
            "guarded_paths": [
                item.strip()
                for item in str(getattr(settings, "governor_guarded_paths", "") or "").split(",")
                if item.strip()
            ],
        },
        "debug": {
            "workflow_debug_enabled": bool(getattr(settings, "orchestrator_debug_workflow", False)),
            "github_debug_enabled": bool(getattr(settings, "orchestrator_debug_github", False)),
        },
        "capabilities": {},
        "blockers": [],
        "admin_prerequisites": [],
    }

    # App-mode token minting probe
    if governor_is_app:
        mint_ok, mint_msg = try_mint_governor_app_token(settings)
        result["app_token_mint"] = {"ok": mint_ok, "detail": mint_msg}
        result["app_outbound_auth_usable"] = mint_ok
        result["app_token_lane_available"] = bool(governor_ready and mint_ok)
    else:
        result["app_token_mint"] = {"ok": False, "detail": "Governor auth mode is not 'app'"}
        result["app_outbound_auth_usable"] = False

    caps = result["capabilities"]
    blockers: list[str] = result["blockers"]
    prereqs: list[str] = result["admin_prerequisites"]

    caps["issue_creation"] = dispatch_ready
    caps["dispatch"] = dispatch_ready
    caps["pr_ready_for_review"] = dispatch_ready
    caps["copilot_follow_up_comment"] = dispatch_ready
    caps["pr_merge"] = dispatch_ready
    caps["governor_review_loop"] = governor_ready
    caps["governor_auto_approval"] = bool(governor_ready and settings.program_auto_merge)
    caps["unattended_issue_dispatch_readiness"] = bool(dispatch_ready and settings.program_auto_dispatch)
    caps["unattended_draft_to_review_readiness"] = bool(
        dispatch_ready and settings.program_auto_dispatch and settings.program_auto_approve
    )
    caps["unattended_review_to_fix_comment_readiness"] = bool(
        dispatch_ready and settings.program_auto_dispatch and settings.program_auto_approve
    )
    caps["unattended_approve_merge_readiness"] = bool(
        dispatch_ready and governor_ready and settings.program_auto_approve and settings.program_auto_merge
    )
    caps["unattended_issue_to_pr_dispatch"] = bool(
        dispatch_ready and settings.program_auto_approve and settings.program_auto_dispatch
    )
    caps["unattended_pr_governance"] = bool(
        dispatch_ready and governor_ready and settings.program_auto_approve and settings.program_auto_merge
    )
    caps["unattended_single_slice_execution"] = bool(
        dispatch_ready
        and governor_ready
        and settings.program_auto_approve
        and settings.program_auto_dispatch
        and settings.program_auto_merge
    )
    caps["next_slice_dispatch"] = bool(dispatch_ready and settings.program_auto_continue and settings.program_auto_dispatch)
    caps["unattended_continuation"] = bool(
        dispatch_ready
        and governor_ready
        and settings.program_auto_continue
        and settings.program_auto_dispatch
        and settings.program_auto_merge
        and settings.program_trusted_auto_confirm
    )

    if not dispatch_ready:
        blockers.append(
            "Dispatch auth is not ready: set GITHUB_DISPATCH_USER_TOKEN "
            "(or legacy GITHUB_API_TOKEN fallback) for issue assignment/dispatch."
        )
        prereqs.append(
            "Configure GITHUB_DISPATCH_USER_TOKEN with a user token that can query suggested actors and assign issues."
        )

    if not governor_ready:
        if governor_is_app:
            blockers.append(
                "Governor auth is not ready: GITHUB_GOVERNOR_AUTH_MODE=app requires "
                "GITHUB_APP_CLIENT_ID, GITHUB_APP_INSTALLATION_ID, and GITHUB_APP_PRIVATE_KEY_PATH."
            )
            prereqs.append(
                "Configure GitHub App governor auth: GITHUB_GOVERNOR_AUTH_MODE=app plus "
                "GITHUB_APP_CLIENT_ID, GITHUB_APP_INSTALLATION_ID, and GITHUB_APP_PRIVATE_KEY_PATH."
            )
        else:
            blockers.append(
                "Governor auth is not ready: token mode requires GITHUB_API_TOKEN for PR lifecycle automation."
            )
            prereqs.append(
                "Set GITHUB_API_TOKEN for governor token mode or switch to app mode via GITHUB_GOVERNOR_AUTH_MODE=app."
            )
    elif governor_is_app:
        mint_ok = result["app_token_mint"]["ok"]
        if not mint_ok:
            blockers.append(f"Governor auth is not usable: app token minting failed: {result['app_token_mint']['detail']}")

    if not settings.program_auto_merge:
        blockers.append("PROGRAM_AUTO_MERGE=false (default); the orchestrator will not automatically merge PRs")
        prereqs.append(
            "Set PROGRAM_AUTO_MERGE=true in orchestrator environment to enable automatic PR merge for trusted programs. "
            "Requires the token to have contents:write permission on the target repository."
        )
    if not settings.program_auto_approve:
        blockers.append("PROGRAM_AUTO_APPROVE=false; governor cannot submit unattended approvals")
    guarded_paths = [
        item.strip()
        for item in str(getattr(settings, "governor_guarded_paths", "") or "").split(",")
        if item.strip()
    ]
    if not guarded_paths:
        blockers.append("GOVERNOR_GUARDED_PATHS is empty; sensitive-path escalation policy is not configured")
        prereqs.append("Set GOVERNOR_GUARDED_PATHS to include sensitive paths that require human review")

    if not settings.program_auto_continue:
        blockers.append("PROGRAM_AUTO_CONTINUE=false; next-slice creation is disabled")

    if not settings.program_auto_dispatch:
        blockers.append("PROGRAM_AUTO_DISPATCH=false; next-slice auto-dispatch is disabled")

    if not settings.program_trusted_auto_confirm:
        blockers.append("PROGRAM_TRUSTED_AUTO_CONFIRM=false; trusted kickoff auto-confirm is disabled")
        prereqs.append("Set PROGRAM_TRUSTED_AUTO_CONFIRM=true to allow trusted program kickoffs to skip manual approval")

    prereqs.append(
        "GitHub repository Actions settings: ensure 'Allow GitHub Actions to create and approve pull requests' is enabled "
        "under Settings > Actions > General if the orchestrator token is used for any workflow-triggering activity. "
        "If Copilot PRs trigger workflow approval gating (status='waiting'), check Settings > Actions > General > "
        "'Fork pull request workflows from outside collaborators' and set it to 'Require approval for first-time contributors "
        "who are new to GitHub' (least restrictive) or add the Copilot bot as a repository collaborator. "
        "If approvals are still required, treat it as configuration drift for unattended governor execution."
    )
    prereqs.append(
        "For auto-merge to work end-to-end: enable 'Allow auto-merge' under repository Settings > General. "
        "The orchestrator will attempt to merge directly via the API; GitHub will enforce required status checks."
    )

    return result
