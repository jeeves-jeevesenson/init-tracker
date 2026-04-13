from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

from sqlmodel import Session, select

from .config import Settings
from .copilot_identity import is_copilot_actor
from .discord_notify import notify_discord
from .github_dispatch import (
    build_dispatch_payload_summary,
    describe_dispatch_mode,
    dispatch_task_to_github_copilot,
)
from .models import (
    APPROVAL_APPROVED,
    APPROVAL_PENDING,
    APPROVAL_REJECTED,
    RUN_STATUS_AWAITING_WORKER_START,
    RUN_STATUS_AWAITING_REVIEW,
    RUN_STATUS_BLOCKED,
    RUN_STATUS_COMPLETED,
    RUN_STATUS_DISPATCH_REQUESTED,
    RUN_STATUS_DISPATCHED,
    RUN_STATUS_FAILED,
    RUN_STATUS_MANUAL_DISPATCH_NEEDED,
    RUN_STATUS_PR_OPENED,
    RUN_STATUS_QUEUED,
    RUN_STATUS_WORKER_FAILED,
    RUN_STATUS_WORKING,
    TASK_STATUS_APPROVED,
    TASK_STATUS_AWAITING_WORKER_START,
    TASK_STATUS_AWAITING_APPROVAL,
    TASK_STATUS_BLOCKED,
    TASK_STATUS_COMPLETED,
    TASK_STATUS_DISPATCH_REQUESTED,
    TASK_STATUS_DISPATCHED,
    TASK_STATUS_FAILED,
    TASK_STATUS_MANUAL_DISPATCH_NEEDED,
    TASK_STATUS_PLANNING,
    TASK_STATUS_PR_OPENED,
    TASK_STATUS_RECEIVED,
    TASK_STATUS_WORKER_FAILED,
    TASK_STATUS_WORKING,
    AgentRun,
    TaskPacket,
)
from .openai_planning import plan_task_packet
from .openai_review import summarize_work_update


ISSUE_REF_RE = re.compile(r"#(\d+)")
APPROVE_RE = re.compile(r"(?im)(^|\n)\s*/approve\b")
REJECT_RE = re.compile(r"(?im)(^|\n)\s*/reject\b")
WORKER_START_FAILURE_RE = re.compile(
    r"(?is)(encountered an error.*unable to start working|unable to start working|agent failed to start)"
)

CUSTOM_AGENT_INITIATIVE_SMITH = "Initiative Smith"
CUSTOM_AGENT_TRACKER_ENGINEER = "Initiative Tracker Engineer"
WORKER_SLUG_TO_CUSTOM_AGENT = {
    "initiative-smith": CUSTOM_AGENT_INITIATIVE_SMITH,
    "tracker-engineer": CUSTOM_AGENT_TRACKER_ENGINEER,
}
CUSTOM_AGENT_OVERRIDE_LABELS = {
    "agent:initiative-smith": "initiative-smith",
    "agent:tracker-engineer": "tracker-engineer",
}
WORKER_AUTO_BROAD_KEYWORDS = (
    "migration",
    "architecture",
    "refactor",
    "stabilization",
    "stabilize",
    "foundation",
    "multi-system",
    "cross-system",
    "end-to-end",
    "broad implementation",
)
WORKER_AUTO_NARROW_KEYWORDS = (
    "bug",
    "fix",
    "follow-up",
    "follow up",
    "polish",
    "contained",
    "subsystem",
    "hardening",
    "patch",
    "narrow",
)
def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _labels(payload_issue: dict[str, Any]) -> set[str]:
    labels = payload_issue.get("labels") or []
    result: set[str] = set()
    for label in labels:
        if isinstance(label, dict) and isinstance(label.get("name"), str):
            result.add(label["name"])
    return result


def _repo_name(payload: dict[str, Any]) -> str:
    repo = payload.get("repository") or {}
    return str(repo.get("full_name") or "")


def _issue_number(payload: dict[str, Any]) -> int | None:
    issue = payload.get("issue") or {}
    number = issue.get("number")
    return int(number) if isinstance(number, int) else None


def _get_task_by_repo_issue(session: Session, *, github_repo: str, github_issue_number: int) -> TaskPacket | None:
    query = (
        select(TaskPacket)
        .where(TaskPacket.github_repo == github_repo)
        .where(TaskPacket.github_issue_number == github_issue_number)
        .limit(1)
    )
    return session.exec(query).first()


def _latest_run_for_task(session: Session, task_id: int) -> AgentRun | None:
    query = (
        select(AgentRun)
        .where(AgentRun.task_packet_id == task_id)
        .order_by(AgentRun.created_at.desc())
        .limit(1)
    )
    return session.exec(query).first()


def _save(session: Session, *objects: Any) -> None:
    for obj in objects:
        session.add(obj)
    session.commit()
    for obj in objects:
        session.refresh(obj)


def _is_copilot_actor(*, settings: Settings, login: str | None, display_name: str | None) -> bool:
    return is_copilot_actor(
        login=login,
        display_name=display_name,
        configured_login=settings.copilot_dispatch_assignee,
    )


def _is_worker_start_failure_comment(comment_body: str) -> bool:
    return bool(WORKER_START_FAILURE_RE.search(comment_body or ""))


def _parse_approval_command(comment_body: str) -> bool | None:
    if APPROVE_RE.search(comment_body):
        return True
    if REJECT_RE.search(comment_body):
        return False
    return None


def _worker_display_name(task: TaskPacket) -> str:
    return task.selected_custom_agent or "Unassigned worker"


def _normalize_worker_slug(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower().replace("_", "-")
    return normalized if normalized in WORKER_SLUG_TO_CUSTOM_AGENT else None


def _normalize_scope_class(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    if normalized in {"broad", "narrow"}:
        return normalized
    if normalized in {"large", "cross-cutting", "cross_cutting"}:
        return "broad"
    if normalized in {"small", "focused", "contained"}:
        return "narrow"
    return None


def _infer_deterministic_route_from_text(task: TaskPacket) -> tuple[str | None, str | None, str | None]:
    text = " ".join(
        [
            task.title or "",
            task.raw_body or "",
            task.normalized_task_text or "",
        ]
    ).lower()
    broad_hits = sum(1 for keyword in WORKER_AUTO_BROAD_KEYWORDS if keyword in text)
    narrow_hits = sum(1 for keyword in WORKER_AUTO_NARROW_KEYWORDS if keyword in text)
    if narrow_hits > broad_hits:
        return (
            "tracker-engineer",
            "narrow",
            "Deterministic routing matched narrow/focused keywords",
        )
    if broad_hits > narrow_hits:
        return (
            "initiative-smith",
            "broad",
            "Deterministic routing matched broad-scope keywords",
        )
    return None, None, None


def _resolve_override(
    *,
    issue_labels: set[str],
    settings: Settings,
) -> tuple[str | None, str | None]:
    selected_override_labels = sorted(label for label in issue_labels if label in CUSTOM_AGENT_OVERRIDE_LABELS)
    if len(selected_override_labels) > 1:
        return (
            None,
            "Multiple agent override labels found; keep only one of "
            "agent:initiative-smith or agent:tracker-engineer",
        )

    unknown_agent_labels = sorted(
        label
        for label in issue_labels
        if label.startswith("agent:")
        and label not in {settings.task_label, settings.task_approved_label}
        and label not in CUSTOM_AGENT_OVERRIDE_LABELS
    )
    if unknown_agent_labels:
        return (
            None,
            f"Unsupported agent override label(s): {', '.join(unknown_agent_labels)}. "
            "Supported overrides: agent:initiative-smith, agent:tracker-engineer",
        )

    if selected_override_labels:
        return selected_override_labels[0], None
    return None, None


def _apply_worker_selection(
    *,
    task: TaskPacket,
    settings: Settings,
    issue_labels: set[str],
) -> None:
    override_label, override_error = _resolve_override(issue_labels=issue_labels, settings=settings)
    if override_error:
        task.selected_custom_agent = None
        task.worker_selection_mode = "override_invalid"
        task.worker_selection_reason = override_error
        task.worker_override_label = override_label
        return

    if override_label:
        worker_slug = CUSTOM_AGENT_OVERRIDE_LABELS[override_label]
        task.selected_custom_agent = WORKER_SLUG_TO_CUSTOM_AGENT[worker_slug]
        task.worker_selection_mode = "override"
        task.worker_selection_reason = f"Manual override label applied: {override_label}"
        task.worker_override_label = override_label
        return

    worker_slug, scope_class, reason = _infer_deterministic_route_from_text(task)
    planner_worker_slug = _normalize_worker_slug(task.recommended_worker)
    planner_scope_class = _normalize_scope_class(task.recommended_scope_class)
    if worker_slug is None:
        if planner_worker_slug is None:
            worker_slug = "tracker-engineer"
            scope_class = "narrow"
            reason = "Deterministic routing defaulted to narrow/focused scope"
        else:
            worker_slug = planner_worker_slug
            reason = "Auto-routing used OpenAI planning recommendation as deterministic tiebreaker"
            if planner_scope_class is None:
                planner_scope_class = "broad" if worker_slug == "initiative-smith" else "narrow"
            scope_class = planner_scope_class
    else:
        if planner_worker_slug and planner_worker_slug != worker_slug:
            reason = (
                f"{reason}; planner hint ({planner_worker_slug}) ignored because deterministic route took precedence"
            )

    task.recommended_worker = worker_slug
    task.recommended_scope_class = scope_class
    task.selected_custom_agent = WORKER_SLUG_TO_CUSTOM_AGENT[worker_slug]
    task.worker_selection_mode = "automatic"
    task.worker_selection_reason = reason
    task.worker_override_label = None


def _mark_worker_started(
    session: Session,
    *,
    task: TaskPacket,
    reason: str,
) -> None:
    if task.approval_state != APPROVAL_APPROVED:
        return
    if task.id is None:
        return
    run = _latest_run_for_task(session, task.id)
    if run is None:
        return
    if run.status in {RUN_STATUS_PR_OPENED, RUN_STATUS_AWAITING_REVIEW, RUN_STATUS_COMPLETED}:
        return
    run.status = RUN_STATUS_WORKING
    run.last_summary = reason
    run.updated_at = _utc_now()
    task.status = TASK_STATUS_WORKING
    task.latest_summary = reason
    task.updated_at = _utc_now()
    _save(session, run, task)
    notify_discord(
        f"Worker started: {task.github_repo}#{task.github_issue_number} -> {_worker_display_name(task)}"
    )


def _mark_worker_failed(
    session: Session,
    *,
    task: TaskPacket,
    reason: str,
) -> None:
    if task.approval_state != APPROVAL_APPROVED:
        return
    if task.id is None:
        return
    run = _latest_run_for_task(session, task.id)
    if run is None:
        return
    if run.status in {RUN_STATUS_PR_OPENED, RUN_STATUS_AWAITING_REVIEW, RUN_STATUS_COMPLETED}:
        return
    run.status = RUN_STATUS_WORKER_FAILED
    run.last_summary = reason
    run.updated_at = _utc_now()
    task.status = TASK_STATUS_WORKER_FAILED
    task.latest_summary = reason
    task.updated_at = _utc_now()
    _save(session, run, task)
    notify_discord(
        f"Worker started but failed: {task.github_repo}#{task.github_issue_number} -> {_worker_display_name(task)}"
    )


def _render_normalized_text(plan: dict[str, Any]) -> str:
    scope_lines = "\n".join(f"- {item}" for item in plan.get("scope", []))
    non_goal_lines = "\n".join(f"- {item}" for item in plan.get("non_goals", []))
    acceptance_lines = "\n".join(f"- {item}" for item in plan.get("acceptance_criteria", []))
    validation_lines = "\n".join(f"- {item}" for item in plan.get("validation_guidance", []))
    return (
        f"Objective:\n{plan.get('objective', '')}\n\n"
        f"Scope:\n{scope_lines or '- (none)'}\n\n"
        f"Non-goals:\n{non_goal_lines or '- (none)'}\n\n"
        f"Implementation brief:\n{plan.get('implementation_brief', '')}\n\n"
        f"Acceptance criteria:\n{acceptance_lines or '- (none)'}\n\n"
        f"Validation guidance:\n{validation_lines or '- (none)'}"
    )


def _parse_json_object(raw_json: str | None) -> dict[str, Any] | None:
    if not raw_json:
        return None
    try:
        parsed = json.loads(raw_json)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _default_worker_brief(task: TaskPacket, internal_plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "objective": internal_plan.get("objective") or task.title or "",
        "concise_scope": internal_plan.get("scope") or [],
        "implementation_brief": internal_plan.get("implementation_brief") or "",
        "acceptance_criteria": internal_plan.get("acceptance_criteria") or [],
        "validation_commands": internal_plan.get("validation_guidance") or [],
        "non_goals": internal_plan.get("non_goals") or [],
        "target_branch": "main",
        "repo_grounded_hints": internal_plan.get("repo_areas") or [],
    }


def _extract_plan_artifacts(task: TaskPacket, plan_payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    if isinstance(plan_payload.get("internal_plan"), dict):
        internal_plan = plan_payload["internal_plan"]
    else:
        internal_plan = plan_payload

    worker_brief = (
        plan_payload.get("worker_brief")
        if isinstance(plan_payload.get("worker_brief"), dict)
        else _default_worker_brief(task, internal_plan)
    )
    return internal_plan, worker_brief


def task_to_dict(task: TaskPacket, latest_run: AgentRun | None = None) -> dict[str, Any]:
    dispatch_payload_summary: dict[str, Any] | None = None
    if latest_run and latest_run.dispatch_payload_json:
        try:
            dispatch_payload_summary = json.loads(latest_run.dispatch_payload_json)
        except json.JSONDecodeError:
            dispatch_payload_summary = {"raw": latest_run.dispatch_payload_json}

    internal_plan = _parse_json_object(task.internal_plan_json)
    worker_brief = _parse_json_object(task.worker_brief_json)
    routing = {
        "recommended_worker": task.recommended_worker,
        "recommended_scope_class": task.recommended_scope_class,
        "selected_custom_agent": task.selected_custom_agent,
        "worker_selection_mode": task.worker_selection_mode,
        "worker_selection_reason": task.worker_selection_reason,
        "worker_override_label": task.worker_override_label,
    }
    github_execution_mode = (
        dispatch_payload_summary.get("github_execution_mode")
        if isinstance(dispatch_payload_summary, dict)
        else None
    )

    return {
        "id": task.id,
        "github_repo": task.github_repo,
        "github_issue_number": task.github_issue_number,
        "github_issue_node_id": task.github_issue_node_id,
        "title": task.title,
        "raw_body": task.raw_body,
        "internal_plan": internal_plan,
        "worker_brief": worker_brief,
        "routing": routing,
        "github_execution_mode": github_execution_mode,
        "internal_plan_json": task.internal_plan_json,
        "worker_brief_json": task.worker_brief_json,
        "normalized_task_text": task.normalized_task_text,
        "acceptance_criteria_json": task.acceptance_criteria_json,
        "validation_commands_json": task.validation_commands_json,
        "recommended_worker": task.recommended_worker,
        "recommended_scope_class": task.recommended_scope_class,
        "selected_custom_agent": task.selected_custom_agent,
        "worker_selection_mode": task.worker_selection_mode,
        "worker_selection_reason": task.worker_selection_reason,
        "worker_override_label": task.worker_override_label,
        "status": task.status,
        "approval_state": task.approval_state,
        "priority": task.priority,
        "latest_summary": task.latest_summary,
        "worker_state": latest_run.status if latest_run else None,
        "dispatch_payload_summary": dispatch_payload_summary,
        "pr_linkage": (
            {"github_pr_number": latest_run.github_pr_number, "github_dispatch_url": latest_run.github_dispatch_url}
            if latest_run
            else None
        ),
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "updated_at": task.updated_at.isoformat() if task.updated_at else None,
        "latest_run": run_to_dict(latest_run) if latest_run else None,
    }


def run_to_dict(run: AgentRun | None) -> dict[str, Any] | None:
    if run is None:
        return None
    dispatch_payload_summary: dict[str, Any] | None = None
    if run.dispatch_payload_json:
        try:
            dispatch_payload_summary = json.loads(run.dispatch_payload_json)
        except json.JSONDecodeError:
            dispatch_payload_summary = {"raw": run.dispatch_payload_json}
    review_artifact = _parse_json_object(run.review_artifact_json)
    return {
        "id": run.id,
        "task_packet_id": run.task_packet_id,
        "provider": run.provider,
        "github_repo": run.github_repo,
        "github_issue_number": run.github_issue_number,
        "github_pr_number": run.github_pr_number,
        "github_dispatch_id": run.github_dispatch_id,
        "github_dispatch_url": run.github_dispatch_url,
        "selected_custom_agent": run.selected_custom_agent,
        "worker_selection_mode": run.worker_selection_mode,
        "dispatch_payload_summary": dispatch_payload_summary,
        "review_artifact": review_artifact,
        "review_artifact_json": run.review_artifact_json,
        "status": run.status,
        "last_summary": run.last_summary,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "updated_at": run.updated_at.isoformat() if run.updated_at else None,
    }


def list_tasks(session: Session, *, limit: int = 100) -> list[TaskPacket]:
    query = select(TaskPacket).order_by(TaskPacket.created_at.desc()).limit(limit)
    return list(session.exec(query).all())


def get_task_with_latest_run(session: Session, task_id: int) -> tuple[TaskPacket | None, AgentRun | None]:
    task = session.get(TaskPacket, task_id)
    if task is None or task.id is None:
        return task, None
    return task, _latest_run_for_task(session, task.id)


def _run_planning(
    session: Session,
    *,
    settings: Settings,
    task: TaskPacket,
    issue_labels: set[str],
) -> None:
    previous_status = task.status
    previous_approval_state = task.approval_state
    previous_summary = task.latest_summary or ""
    had_successful_plan = bool(task.normalized_task_text)

    task.status = TASK_STATUS_PLANNING
    task.updated_at = _utc_now()
    _save(session, task)
    try:
        plan_payload = plan_task_packet(
            settings=settings,
            repo=task.github_repo,
            issue_number=task.github_issue_number,
            issue_title=task.title,
            issue_body=task.raw_body,
        )
        internal_plan, worker_brief = _extract_plan_artifacts(task, plan_payload)
        task.internal_plan_json = json.dumps(internal_plan, ensure_ascii=False)
        task.worker_brief_json = json.dumps(worker_brief, ensure_ascii=False)
        task.normalized_task_text = _render_normalized_text(internal_plan)
        task.acceptance_criteria_json = json.dumps(worker_brief.get("acceptance_criteria") or [], ensure_ascii=False)
        task.validation_commands_json = json.dumps(worker_brief.get("validation_commands") or [], ensure_ascii=False)
        task.recommended_worker = _normalize_worker_slug(internal_plan.get("recommended_worker"))
        task.recommended_scope_class = _normalize_scope_class(internal_plan.get("recommended_scope_class"))
        _apply_worker_selection(task=task, settings=settings, issue_labels=issue_labels)
        task.status = TASK_STATUS_AWAITING_APPROVAL
        task.approval_state = APPROVAL_PENDING
        task.latest_summary = (
            "Task planned and awaiting approval"
            f" (worker={_worker_display_name(task)}, selection={task.worker_selection_mode or 'unknown'})"
        )
        task.updated_at = _utc_now()
        _save(session, task)
        if previous_status != TASK_STATUS_AWAITING_APPROVAL:
            notify_discord(
                f"Task planned / awaiting approval: {task.github_repo}#{task.github_issue_number} -> {_worker_display_name(task)}"
            )
    except Exception as exc:
        if had_successful_plan and previous_status in {
            TASK_STATUS_AWAITING_APPROVAL,
            TASK_STATUS_APPROVED,
            TASK_STATUS_DISPATCH_REQUESTED,
            TASK_STATUS_AWAITING_WORKER_START,
            TASK_STATUS_DISPATCHED,
            TASK_STATUS_WORKING,
            TASK_STATUS_WORKER_FAILED,
            TASK_STATUS_PR_OPENED,
            TASK_STATUS_MANUAL_DISPATCH_NEEDED,
            TASK_STATUS_BLOCKED,
            TASK_STATUS_COMPLETED,
        }:
            task.status = previous_status
            task.approval_state = previous_approval_state
            task.latest_summary = (
                "Planning retry failed after a previous successful plan; "
                f"keeping current state ({previous_status}): {exc}"
            )
            task.updated_at = _utc_now()
            _save(session, task)
            return

        task.status = TASK_STATUS_FAILED
        task.latest_summary = f"Planning failed: {exc}"
        task.updated_at = _utc_now()
        _save(session, task)
        if previous_status == TASK_STATUS_FAILED and previous_summary.startswith("Planning failed:"):
            return
        notify_discord(
            f"Task failed during planning: {task.github_repo}#{task.github_issue_number} ({exc})"
        )


def _create_or_update_task_from_issue(
    session: Session,
    *,
    github_repo: str,
    issue: dict[str, Any],
) -> tuple[TaskPacket, bool]:
    issue_number = int(issue["number"])
    task = _get_task_by_repo_issue(session, github_repo=github_repo, github_issue_number=issue_number)
    created = False
    if task is None:
        task = TaskPacket(
            github_repo=github_repo,
            github_issue_number=issue_number,
            status=TASK_STATUS_RECEIVED,
            approval_state=APPROVAL_PENDING,
        )
        created = True

    task.github_issue_node_id = issue.get("node_id")
    task.title = str(issue.get("title") or "")
    task.raw_body = str(issue.get("body") or "")
    task.updated_at = _utc_now()
    _save(session, task)
    return task, created


def process_issue_event(session: Session, *, settings: Settings, payload: dict[str, Any], action: str | None) -> None:
    github_repo = _repo_name(payload)
    issue = payload.get("issue") or {}
    if not github_repo or not isinstance(issue, dict) or not isinstance(issue.get("number"), int):
        return

    labels = _labels(issue)
    has_task_label = settings.task_label in labels
    if not has_task_label:
        return

    task, created = _create_or_update_task_from_issue(session, github_repo=github_repo, issue=issue)
    if created:
        notify_discord(f"Task packet created: {task.github_repo}#{task.github_issue_number}")

    label_name = ((payload.get("label") or {}).get("name") if isinstance(payload.get("label"), dict) else None)
    should_replan = action in {"opened", "edited", "reopened"} or (
        action == "labeled" and label_name == settings.task_label
    )

    if should_replan:
        _run_planning(session, settings=settings, task=task, issue_labels=labels)
    else:
        _apply_worker_selection(task=task, settings=settings, issue_labels=labels)
        task.updated_at = _utc_now()
        _save(session, task)

    if action == "labeled":
        if label_name == settings.task_approved_label:
            process_approval(session, settings=settings, task=task, approved=True, source="label")
    elif action == "assigned":
        assignee = payload.get("assignee") or {}
        assignee_login = assignee.get("login") if isinstance(assignee, dict) else None
        assignee_name = assignee.get("name") if isinstance(assignee, dict) else None
        if _is_copilot_actor(settings=settings, login=assignee_login, display_name=assignee_name):
            actor = assignee_login or assignee_name or "copilot"
            _mark_worker_started(
                session,
                task=task,
                reason=f"Worker start signal: issue assigned to {actor}",
            )


def process_approval(
    session: Session,
    *,
    settings: Settings,
    task: TaskPacket,
    approved: bool,
    source: str,
) -> None:
    if approved:
        if task.status in {
            TASK_STATUS_DISPATCH_REQUESTED,
            TASK_STATUS_AWAITING_WORKER_START,
            TASK_STATUS_DISPATCHED,
            TASK_STATUS_WORKING,
            TASK_STATUS_WORKER_FAILED,
            TASK_STATUS_PR_OPENED,
            TASK_STATUS_COMPLETED,
        }:
            return
        if not task.selected_custom_agent:
            task.approval_state = APPROVAL_PENDING
            task.status = TASK_STATUS_BLOCKED
            task.latest_summary = (
                "Approval blocked: no valid worker selected. "
                f"{task.worker_selection_reason or 'Set agent:initiative-smith or agent:tracker-engineer'}"
            )
            task.updated_at = _utc_now()
            _save(session, task)
            notify_discord(
                f"Task approval blocked by worker selection: {task.github_repo}#{task.github_issue_number}"
            )
            return
        task.approval_state = APPROVAL_APPROVED
        task.status = TASK_STATUS_APPROVED
        task.latest_summary = f"Approved via {source}; worker={_worker_display_name(task)}"
        task.updated_at = _utc_now()
        _save(session, task)
        notify_discord(f"Task approved: {task.github_repo}#{task.github_issue_number} -> {_worker_display_name(task)}")
        dispatch_task_if_ready(session, settings=settings, task=task)
        return

    task.approval_state = APPROVAL_REJECTED
    task.status = TASK_STATUS_BLOCKED
    task.latest_summary = f"Rejected via {source}"
    task.updated_at = _utc_now()
    _save(session, task)
    notify_discord(f"Task rejected: {task.github_repo}#{task.github_issue_number}")


def process_issue_comment_event(session: Session, *, settings: Settings, payload: dict[str, Any], action: str | None) -> None:
    if action != "created":
        return
    issue = payload.get("issue") or {}
    if isinstance(issue, dict) and issue.get("pull_request") is not None:
        return

    github_repo = _repo_name(payload)
    issue_number = _issue_number(payload)
    if not github_repo or issue_number is None:
        return

    task = _get_task_by_repo_issue(session, github_repo=github_repo, github_issue_number=issue_number)
    if task is None:
        return

    comment = payload.get("comment") or {}
    body = str(comment.get("body") or "")
    if not body:
        return

    approved = _parse_approval_command(body)
    if approved is None:
        user = comment.get("user") if isinstance(comment, dict) else None
        commenter_login = user.get("login") if isinstance(user, dict) else None
        commenter_name = user.get("name") if isinstance(user, dict) else None
        if _is_copilot_actor(settings=settings, login=commenter_login, display_name=commenter_name):
            actor = commenter_login or commenter_name or "copilot"
            if _is_worker_start_failure_comment(body):
                _mark_worker_failed(
                    session,
                    task=task,
                    reason=f"Worker failed after start attempt: {actor} reported startup failure.",
                )
            else:
                _mark_worker_started(
                    session,
                    task=task,
                    reason=f"Worker start signal: activity comment from {actor}",
                )
        return

    process_approval(session, settings=settings, task=task, approved=approved, source="comment")


def dispatch_task_if_ready(session: Session, *, settings: Settings, task: TaskPacket) -> None:
    if task.id is None:
        return
    if task.approval_state != APPROVAL_APPROVED:
        return
    latest_run = _latest_run_for_task(session, task.id)
    if latest_run and latest_run.status in {
        RUN_STATUS_DISPATCH_REQUESTED,
        RUN_STATUS_AWAITING_WORKER_START,
        RUN_STATUS_DISPATCHED,
        RUN_STATUS_WORKING,
        RUN_STATUS_WORKER_FAILED,
        RUN_STATUS_PR_OPENED,
        RUN_STATUS_AWAITING_REVIEW,
        RUN_STATUS_COMPLETED,
    }:
        return

    dispatch_mode_summary = describe_dispatch_mode(settings, task)
    run = AgentRun(
        task_packet_id=task.id,
        provider="github_copilot",
        github_repo=task.github_repo,
        github_issue_number=task.github_issue_number,
        selected_custom_agent=task.selected_custom_agent,
        worker_selection_mode=task.worker_selection_mode,
        dispatch_payload_json=json.dumps(build_dispatch_payload_summary(settings, task), ensure_ascii=False),
        status=RUN_STATUS_QUEUED,
        last_summary="Dispatch queued",
    )
    _save(session, run)

    run.status = RUN_STATUS_DISPATCH_REQUESTED
    run.last_summary = (
        "Dispatch requested via GitHub issue assignment API"
        f" (worker={_worker_display_name(task)})"
        f" ({dispatch_mode_summary})"
    )
    run.updated_at = _utc_now()
    task.status = TASK_STATUS_DISPATCH_REQUESTED
    task.latest_summary = (
        f"Dispatch requested for {_worker_display_name(task)}; awaiting GitHub acceptance "
        f"({dispatch_mode_summary})"
    )
    task.updated_at = _utc_now()
    _save(session, run, task)

    result = dispatch_task_to_github_copilot(settings=settings, task=task)
    result_summary = (
        f"{result.summary} "
        f"(dispatch_state={result.state}, api_status={result.api_status_code if result.api_status_code is not None else 'n/a'})"
    )
    if result.accepted:
        run.status = RUN_STATUS_AWAITING_WORKER_START
        run.last_summary = result_summary
        run.github_dispatch_id = result.dispatch_id
        run.github_dispatch_url = result.dispatch_url
        run.updated_at = _utc_now()

        task.status = TASK_STATUS_AWAITING_WORKER_START
        task.latest_summary = f"{result_summary} Awaiting worker-start signal."
        task.updated_at = _utc_now()
        _save(session, run, task)
        notify_discord(
            "Task dispatched: "
            f"{task.github_repo}#{task.github_issue_number} -> {_worker_display_name(task)} "
            f"({dispatch_mode_summary})"
        )
        return

    if result.manual_required:
        run.status = RUN_STATUS_MANUAL_DISPATCH_NEEDED
        run.last_summary = result_summary
        run.github_dispatch_id = result.dispatch_id
        run.github_dispatch_url = result.dispatch_url
        run.updated_at = _utc_now()

        task.status = TASK_STATUS_MANUAL_DISPATCH_NEEDED
        task.latest_summary = result_summary
        task.updated_at = _utc_now()
        _save(session, run, task)
        notify_discord(
            "Manual dispatch needed: "
            f"{task.github_repo}#{task.github_issue_number} -> {_worker_display_name(task)} "
            f"({dispatch_mode_summary})"
        )
        return

    run.status = RUN_STATUS_FAILED
    run.last_summary = result_summary
    run.updated_at = _utc_now()

    task.status = TASK_STATUS_FAILED
    task.latest_summary = result_summary
    task.updated_at = _utc_now()
    _save(session, run, task)
    notify_discord(
        "Task failed to dispatch: "
        f"{task.github_repo}#{task.github_issue_number} -> {_worker_display_name(task)} "
        f"({dispatch_mode_summary})"
    )


def _task_for_pr_payload(session: Session, *, github_repo: str, pr_payload: dict[str, Any]) -> TaskPacket | None:
    body = str(pr_payload.get("body") or "")
    title = str(pr_payload.get("title") or "")
    refs = ISSUE_REF_RE.findall(f"{title}\n{body}")
    for issue_ref in refs:
        task = _get_task_by_repo_issue(session, github_repo=github_repo, github_issue_number=int(issue_ref))
        if task is not None:
            return task

    query = (
        select(TaskPacket)
        .where(TaskPacket.github_repo == github_repo)
        .where(
            TaskPacket.status.in_(
                [
                    TASK_STATUS_DISPATCH_REQUESTED,
                    TASK_STATUS_AWAITING_WORKER_START,
                    TASK_STATUS_DISPATCHED,
                    TASK_STATUS_WORKING,
                    TASK_STATUS_WORKER_FAILED,
                    TASK_STATUS_PR_OPENED,
                    TASK_STATUS_MANUAL_DISPATCH_NEEDED,
                ]
            )
        )
        .order_by(TaskPacket.updated_at.desc())
        .limit(1)
    )
    return session.exec(query).first()


def _summarize_and_store(
    session: Session,
    *,
    settings: Settings,
    task: TaskPacket,
    run: AgentRun,
    context: str,
    run_status: str,
) -> None:
    try:
        summary = summarize_work_update(settings=settings, update_context=context)
        artifact = summary.get("review_artifact") if isinstance(summary.get("review_artifact"), dict) else {}
        bullets = summary.get("summary_bullets") or artifact.get("concise_summary") or []
        next_action = summary.get("next_action") or artifact.get("merge_recommendation") or "review"
        rendered = "\n".join(f"- {line}" for line in bullets)
        full_summary = f"{rendered}\nNext action: {next_action}".strip()
        run.review_artifact_json = json.dumps(artifact, ensure_ascii=False) if artifact else None
    except Exception as exc:
        full_summary = f"Summary unavailable: {exc}"
        run.review_artifact_json = json.dumps(
            {
                "what_changed": [],
                "scope_status": "unclear",
                "likely_risks": [],
                "missing_validation": [],
                "merge_recommendation": "review_required",
                "send_back_recommendation": "not_needed",
                "concise_summary": [str(exc)],
            },
            ensure_ascii=False,
        )

    run.status = run_status
    run.last_summary = full_summary
    run.updated_at = _utc_now()

    task.latest_summary = full_summary
    task.updated_at = _utc_now()
    _save(session, run, task)


def _review_summary_suffix(run: AgentRun) -> str:
    artifact = _parse_json_object(run.review_artifact_json)
    if not artifact:
        return ""
    concise = artifact.get("concise_summary")
    if isinstance(concise, list) and concise:
        first = str(concise[0]).strip()
        if first:
            return f" | {first[:140]}"
    return ""


def process_pull_request_event(
    session: Session,
    *,
    settings: Settings,
    payload: dict[str, Any],
    action: str | None,
) -> None:
    github_repo = _repo_name(payload)
    pr = payload.get("pull_request") or {}
    if not github_repo or not isinstance(pr, dict):
        return

    task = _task_for_pr_payload(session, github_repo=github_repo, pr_payload=pr)
    if task is None or task.id is None:
        return

    run = _latest_run_for_task(session, task.id)
    if run is None:
        run = AgentRun(
            task_packet_id=task.id,
            provider="github_copilot",
            github_repo=task.github_repo,
            github_issue_number=task.github_issue_number,
            status=RUN_STATUS_WORKING,
        )
        _save(session, run)

    pr_number = pr.get("number")
    if isinstance(pr_number, int):
        run.github_pr_number = pr_number

    html_url = str(pr.get("html_url") or "")
    if action in {"opened", "reopened", "ready_for_review"}:
        context = (
            f"PR update for {github_repo}#{task.github_issue_number}\n"
            f"Action: {action}\n"
            f"PR: #{pr.get('number')} {pr.get('title')}\n"
            f"URL: {html_url}"
        )
        _summarize_and_store(
            session,
            settings=settings,
            task=task,
            run=run,
            context=context,
            run_status=RUN_STATUS_PR_OPENED,
        )
        task.status = TASK_STATUS_PR_OPENED
        task.updated_at = _utc_now()
        _save(session, task)
        notify_discord(
            f"PR opened / ready for review: {github_repo} PR #{pr.get('number')} -> {_worker_display_name(task)}"
            f"{_review_summary_suffix(run)}"
        )
        return

    if action == "closed":
        merged = bool(pr.get("merged"))
        if merged:
            run.status = RUN_STATUS_COMPLETED
            run.last_summary = f"PR merged: {html_url}" if html_url else "PR merged"
            run.updated_at = _utc_now()
            task.status = TASK_STATUS_COMPLETED
            task.latest_summary = run.last_summary
            task.updated_at = _utc_now()
            _save(session, run, task)
            notify_discord(f"Task completed: {github_repo}#{task.github_issue_number}")
            return

        run.status = RUN_STATUS_BLOCKED
        run.last_summary = f"PR closed without merge: {html_url}" if html_url else "PR closed without merge"
        run.updated_at = _utc_now()
        task.status = TASK_STATUS_BLOCKED
        task.latest_summary = run.last_summary
        task.updated_at = _utc_now()
        _save(session, run, task)
        notify_discord(f"Task blocked (PR closed): {github_repo}#{task.github_issue_number}")
        return

    run.status = RUN_STATUS_WORKING
    run.last_summary = f"PR action observed: {action}"
    run.updated_at = _utc_now()
    task.status = TASK_STATUS_WORKING
    task.latest_summary = run.last_summary
    task.updated_at = _utc_now()
    _save(session, run, task)


def process_workflow_run_event(
    session: Session,
    *,
    settings: Settings,
    payload: dict[str, Any],
    action: str | None,
) -> None:
    github_repo = _repo_name(payload)
    workflow_run = payload.get("workflow_run") or {}
    if not github_repo or not isinstance(workflow_run, dict):
        return

    pr_entries = workflow_run.get("pull_requests") or []
    pr_numbers = [pr.get("number") for pr in pr_entries if isinstance(pr, dict) and isinstance(pr.get("number"), int)]
    if not pr_numbers:
        return

    query = (
        select(AgentRun)
        .where(AgentRun.github_repo == github_repo)
        .where(AgentRun.github_pr_number.in_(pr_numbers))
        .order_by(AgentRun.updated_at.desc())
        .limit(1)
    )
    run = session.exec(query).first()
    if run is None:
        return

    task = session.get(TaskPacket, run.task_packet_id)
    if task is None:
        return

    conclusion = str(workflow_run.get("conclusion") or "")
    status = str(workflow_run.get("status") or "")
    name = str(workflow_run.get("name") or "workflow")
    html_url = str(workflow_run.get("html_url") or "")

    context = (
        f"Workflow update for {github_repo}#{task.github_issue_number}\n"
        f"Action: {action}\n"
        f"Workflow: {name}\n"
        f"Status: {status}\n"
        f"Conclusion: {conclusion}\n"
        f"Run URL: {html_url}"
    )

    if status == "completed" and conclusion == "success":
        _summarize_and_store(
            session,
            settings=settings,
            task=task,
            run=run,
            context=context,
            run_status=RUN_STATUS_AWAITING_REVIEW,
        )
        task.status = TASK_STATUS_PR_OPENED
        task.updated_at = _utc_now()
        _save(session, task)
        notify_discord(
            f"Checks complete and ready for review: {github_repo} PR #{run.github_pr_number} -> {_worker_display_name(task)}"
            f"{_review_summary_suffix(run)}"
        )
        return

    if status == "completed" and conclusion in {"failure", "cancelled", "timed_out", "startup_failure"}:
        _summarize_and_store(
            session,
            settings=settings,
            task=task,
            run=run,
            context=context,
            run_status=RUN_STATUS_BLOCKED,
        )
        task.status = TASK_STATUS_BLOCKED
        task.updated_at = _utc_now()
        _save(session, task)
        notify_discord(
            f"Checks failed / task blocked: {github_repo} PR #{run.github_pr_number} -> {_worker_display_name(task)}"
            f"{_review_summary_suffix(run)}"
        )
        return

    run.status = RUN_STATUS_WORKING
    run.last_summary = f"Workflow update observed: {name} ({status}/{conclusion or 'n/a'})"
    run.updated_at = _utc_now()
    task.status = TASK_STATUS_WORKING
    task.latest_summary = run.last_summary
    task.updated_at = _utc_now()
    _save(session, run, task)
