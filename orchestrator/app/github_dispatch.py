from __future__ import annotations

import json
import logging
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
    graphql_url = f"{api_base}/graphql"
    repo_parts = _extract_repo_owner_name(repo)
    if repo_parts is None:
        msg = f"Invalid repository path {repo!r}; cannot mark PR #{pr_number} ready for review"
        logger.warning(msg)
        return False, msg
    owner, name = repo_parts
    logger.info(
        "Attempting ready-for-review transition via GraphQL: repo=%s pr_number=%s",
        repo,
        pr_number,
    )
    try:
        with httpx.Client(timeout=15.0) as client:
            pr_query_response = client.post(
                graphql_url,
                headers=_build_headers(settings),
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
                logger.warning(
                    "Ready-for-review transition failed: repo=%s pr_number=%s error=%s",
                    repo,
                    pr_number,
                    msg,
                )
                return False, msg

            query_payload = pr_query_response.json()
            if query_payload.get("errors"):
                msg = (
                    f"GitHub GraphQL errors when preparing ready-for-review for PR #{pr_number}: "
                    f"{str(query_payload.get('errors'))[:300]}"
                )
                logger.warning(
                    "Ready-for-review transition failed: repo=%s pr_number=%s error=%s",
                    repo,
                    pr_number,
                    msg,
                )
                return False, msg

            pull_request = (((query_payload.get("data") or {}).get("repository") or {}).get("pullRequest") or {})
            pull_request_id = pull_request.get("id")
            if not isinstance(pull_request_id, str) or not pull_request_id.strip():
                msg = f"PR #{pr_number} not found via GraphQL; cannot mark ready for review"
                logger.warning(
                    "Ready-for-review transition failed: repo=%s pr_number=%s error=%s",
                    repo,
                    pr_number,
                    msg,
                )
                return False, msg

            if pull_request.get("isDraft") is False:
                msg = f"PR #{pr_number} is already ready for review"
                logger.info(
                    "Ready-for-review transition complete: repo=%s pr_number=%s result=%s",
                    repo,
                    pr_number,
                    msg,
                )
                return True, msg

            mutation_response = client.post(
                graphql_url,
                headers=_build_headers(settings),
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
                logger.warning(
                    "Ready-for-review transition failed: repo=%s pr_number=%s error=%s",
                    repo,
                    pr_number,
                    msg,
                )
                return False, msg

            mutation_payload = mutation_response.json()
            if mutation_payload.get("errors"):
                msg = (
                    f"GitHub GraphQL errors when marking PR #{pr_number} ready for review: "
                    f"{str(mutation_payload.get('errors'))[:300]}"
                )
                logger.warning(
                    "Ready-for-review transition failed: repo=%s pr_number=%s error=%s",
                    repo,
                    pr_number,
                    msg,
                )
                return False, msg

            msg = f"PR #{pr_number} marked ready for review"
            logger.info(
                "Ready-for-review transition complete: repo=%s pr_number=%s result=%s",
                repo,
                pr_number,
                msg,
            )
            return True, msg
    except Exception as exc:
        msg = f"Failed to mark PR #{pr_number} ready for review: {exc}"
        logger.warning(
            "Ready-for-review transition failed: repo=%s pr_number=%s error=%s",
            repo,
            pr_number,
            msg,
        )
        return False, msg


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
    if not settings.github_api_token:
        return False, "GitHub API token missing; cannot merge PR"
    api_base = settings.github_api_url.rstrip("/")
    url = f"{api_base}/repos/{repo}/pulls/{pr_number}/merge"
    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.put(
                url,
                headers=_build_headers(settings),
                json={"merge_method": merge_method},
            )
            if response.status_code in {200, 204}:
                return True, f"PR #{pr_number} merged successfully"
            detail = response.text[:300]
            return False, f"GitHub returned {response.status_code} when merging PR #{pr_number}: {detail}"
    except Exception as exc:
        return False, f"Failed to merge PR #{pr_number}: {exc}"


def inspect_pull_request(*, settings: Settings, repo: str, pr_number: int) -> PullRequestInspection:
    if not settings.github_api_token:
        return PullRequestInspection(
            ok=False,
            changed_files=None,
            commits=None,
            draft=None,
            state=None,
            merged=None,
            summary="GitHub API token missing; cannot inspect PR",
        )
    api_base = settings.github_api_url.rstrip("/")
    url = f"{api_base}/repos/{repo}/pulls/{pr_number}"
    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.get(url, headers=_build_headers(settings))
            if response.status_code >= 400:
                return PullRequestInspection(
                    ok=False,
                    changed_files=None,
                    commits=None,
                    draft=None,
                    state=None,
                    merged=None,
                    summary=f"GitHub returned {response.status_code} when inspecting PR #{pr_number}: {response.text[:300]}",
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
            summary=f"Failed to inspect PR #{pr_number}: {exc}",
        )


def remove_requested_reviewers(
    *,
    settings: Settings,
    repo: str,
    pr_number: int,
    reviewers: list[str],
) -> tuple[bool, str]:
    if not settings.github_api_token:
        return False, "GitHub API token missing; cannot remove PR reviewers"
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
                headers=_build_headers(settings),
                json={"reviewers": sanitized},
            )
            if response.status_code >= 400:
                return False, (
                    f"GitHub returned {response.status_code} when removing requested reviewers from PR #{pr_number}: "
                    f"{response.text[:300]}"
                )
            return True, f"Removed requested reviewers from PR #{pr_number}: {sanitized}"
    except Exception as exc:
        return False, f"Failed to remove requested reviewers from PR #{pr_number}: {exc}"


def request_reviewers(
    *,
    settings: Settings,
    repo: str,
    pr_number: int,
    reviewers: list[str],
) -> tuple[bool, str]:
    if not settings.github_api_token:
        return False, "GitHub API token missing; cannot request PR reviewers"
    sanitized = sorted({item.strip() for item in reviewers if isinstance(item, str) and item.strip()})
    if not sanitized:
        return True, "No reviewers requested"
    api_base = settings.github_api_url.rstrip("/")
    url = f"{api_base}/repos/{repo}/pulls/{pr_number}/requested_reviewers"
    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.post(
                url,
                headers=_build_headers(settings),
                json={"reviewers": sanitized},
            )
            if response.status_code >= 400:
                return False, f"GitHub returned {response.status_code} when requesting reviewers on PR #{pr_number}: {response.text[:300]}"
            return True, f"Requested reviewers for PR #{pr_number}: {sanitized}"
    except Exception as exc:
        return False, f"Failed to request reviewers for PR #{pr_number}: {exc}"


def list_pull_request_reviews(*, settings: Settings, repo: str, pr_number: int) -> tuple[list[dict[str, Any]], str]:
    if not settings.github_api_token:
        return [], "GitHub API token missing; cannot list PR reviews"
    api_base = settings.github_api_url.rstrip("/")
    url = f"{api_base}/repos/{repo}/pulls/{pr_number}/reviews?per_page=100"
    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.get(url, headers=_build_headers(settings))
            if response.status_code >= 400:
                return [], f"GitHub returned {response.status_code} when listing reviews for PR #{pr_number}: {response.text[:300]}"
            if not response.headers.get("content-type", "").startswith("application/json"):
                return [], f"GitHub returned non-JSON review list for PR #{pr_number}"
            payload = response.json()
            if not isinstance(payload, list):
                return [], f"GitHub returned invalid review list for PR #{pr_number}"
            reviews = [item for item in payload if isinstance(item, dict)]
            return reviews, f"Fetched {len(reviews)} reviews for PR #{pr_number}"
    except Exception as exc:
        return [], f"Failed to list reviews for PR #{pr_number}: {exc}"


def list_pull_request_review_comments(*, settings: Settings, repo: str, pr_number: int) -> tuple[list[dict[str, Any]], str]:
    if not settings.github_api_token:
        return [], "GitHub API token missing; cannot list PR review comments"
    api_base = settings.github_api_url.rstrip("/")
    url = f"{api_base}/repos/{repo}/pulls/{pr_number}/comments?per_page=100"
    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.get(url, headers=_build_headers(settings))
            if response.status_code >= 400:
                return [], (
                    f"GitHub returned {response.status_code} when listing review comments for PR #{pr_number}: "
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
        return [], f"Failed to list review comments for PR #{pr_number}: {exc}"


def list_pull_request_files(*, settings: Settings, repo: str, pr_number: int) -> tuple[list[str], str]:
    if not settings.github_api_token:
        return [], "GitHub API token missing; cannot list PR files"
    api_base = settings.github_api_url.rstrip("/")
    url = f"{api_base}/repos/{repo}/pulls/{pr_number}/files?per_page=100"
    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.get(url, headers=_build_headers(settings))
            if response.status_code >= 400:
                return [], f"GitHub returned {response.status_code} when listing files for PR #{pr_number}: {response.text[:300]}"
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
        return [], f"Failed to list files for PR #{pr_number}: {exc}"


def list_issue_comments(*, settings: Settings, repo: str, issue_number: int) -> tuple[list[dict[str, Any]], str]:
    if not settings.github_api_token:
        return [], "GitHub API token missing; cannot list issue comments"
    api_base = settings.github_api_url.rstrip("/")
    url = f"{api_base}/repos/{repo}/issues/{issue_number}/comments?per_page=100"
    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.get(url, headers=_build_headers(settings))
            if response.status_code >= 400:
                return [], f"GitHub returned {response.status_code} when listing issue comments #{issue_number}: {response.text[:300]}"
            if not response.headers.get("content-type", "").startswith("application/json"):
                return [], f"GitHub returned non-JSON issue comment list for issue #{issue_number}"
            payload = response.json()
            if not isinstance(payload, list):
                return [], f"GitHub returned invalid issue comment list for issue #{issue_number}"
            comments = [item for item in payload if isinstance(item, dict)]
            return comments, f"Fetched {len(comments)} comments for issue #{issue_number}"
    except Exception as exc:
        return [], f"Failed to list issue comments for issue #{issue_number}: {exc}"


def post_issue_comment(*, settings: Settings, repo: str, issue_number: int, body: str) -> tuple[bool, str]:
    if not settings.github_api_token:
        return False, "GitHub API token missing; cannot post issue comment"
    comment_body = str(body or "").strip()
    if not comment_body:
        return False, "Comment body is empty"
    api_base = settings.github_api_url.rstrip("/")
    url = f"{api_base}/repos/{repo}/issues/{issue_number}/comments"
    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.post(
                url,
                headers=_build_headers(settings),
                json={"body": comment_body},
            )
            if response.status_code >= 400:
                return False, f"GitHub returned {response.status_code} when posting issue comment on #{issue_number}: {response.text[:300]}"
            return True, f"Posted issue comment on #{issue_number}"
    except Exception as exc:
        return False, f"Failed to post issue comment on #{issue_number}: {exc}"


def submit_approving_review(
    *,
    settings: Settings,
    repo: str,
    pr_number: int,
    body: str = "Automated governor approval after successful checks and resolved findings.",
) -> tuple[bool, str]:
    if not settings.github_api_token:
        return False, "GitHub API token missing; cannot submit approving review"
    api_base = settings.github_api_url.rstrip("/")
    url = f"{api_base}/repos/{repo}/pulls/{pr_number}/reviews"
    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.post(
                url,
                headers=_build_headers(settings),
                json={"event": "APPROVE", "body": body},
            )
            if response.status_code >= 400:
                return False, f"GitHub returned {response.status_code} when submitting approval review for PR #{pr_number}: {response.text[:300]}"
            return True, f"Submitted approving review for PR #{pr_number}"
    except Exception as exc:
        return False, f"Failed to submit approving review for PR #{pr_number}: {exc}"


def run_preflight_checks(*, settings: Settings, repo: str | None = None) -> dict:
    """Run a preflight diagnostic against the current environment configuration.

    Returns a structured dict describing which capabilities are available for
    unattended trusted continuation. Intended for the GET /preflight endpoint.
    """
    result: dict = {
        "github_api_token": bool(settings.github_api_token),
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
        "capabilities": {},
        "blockers": [],
        "admin_prerequisites": [],
    }

    caps = result["capabilities"]
    blockers: list[str] = result["blockers"]
    prereqs: list[str] = result["admin_prerequisites"]

    caps["issue_creation"] = bool(settings.github_api_token)
    caps["pr_ready_for_review"] = bool(settings.github_api_token)
    caps["pr_merge"] = bool(settings.github_api_token)
    caps["dispatch"] = bool(settings.github_api_token)
    caps["governor_review_loop"] = bool(settings.github_api_token)
    caps["governor_auto_approval"] = bool(settings.github_api_token and settings.program_auto_merge)
    caps["unattended_single_slice_execution"] = bool(
        settings.github_api_token
        and settings.program_auto_approve
        and settings.program_auto_dispatch
        and settings.program_auto_merge
    )
    caps["next_slice_dispatch"] = bool(settings.github_api_token and settings.program_auto_continue and settings.program_auto_dispatch)
    caps["unattended_continuation"] = bool(
        settings.github_api_token
        and settings.program_auto_continue
        and settings.program_auto_dispatch
        and settings.program_auto_merge
        and settings.program_trusted_auto_confirm
    )

    if not settings.github_api_token:
        blockers.append("GITHUB_API_TOKEN not configured; all GitHub API operations will fail")
        prereqs.append("Set GITHUB_API_TOKEN to a fine-grained or classic token with repo:write and pull_requests:write scope")

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
