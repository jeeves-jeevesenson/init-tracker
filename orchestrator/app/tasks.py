from __future__ import annotations

import json
import fnmatch
import hashlib
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlmodel import Session, select

from .config import Settings, get_settings
from .copilot_identity import is_copilot_actor
from .discord_notify import notify_discord
from .github_dispatch import (
    build_dispatch_payload_summary,
    describe_dispatch_mode,
    dispatch_task_to_github_copilot,
    inspect_pull_request,
    list_issue_comments,
    list_pull_request_files,
    list_pull_request_review_comments,
    list_pull_request_reviews,
    mark_pr_ready_for_review,
    merge_pr,
    post_copilot_follow_up_comment,
    remove_requested_reviewers,
    request_reviewers,
    submit_approving_review,
)
from .models import (
    APPROVAL_APPROVED,
    APPROVAL_PENDING,
    APPROVAL_REJECTED,
    BLOCKER_WAITING_FOR_PERMISSIONS,
    BLOCKER_WAITING_FOR_PR_READY,
    BLOCKER_WAITING_FOR_WORKFLOW_APPROVAL,
    BLOCKER_GUARDED_PATHS_REQUIRE_HUMAN,
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
    Program,
    TaskPacket,
)
from .openai_planning import plan_task_packet
from .openai_review import summarize_work_update
from .openai_review import summarize_governor_update
from .openai_review import summarize_copilot_review_batch
from .programs import (
    advance_program_on_pr_merge,
    apply_reviewer_decision,
    ensure_program_for_task,
    link_run_to_slice,
    mark_slice_approved,
)


ISSUE_REF_RE = re.compile(r"#(\d+)")
APPROVE_RE = re.compile(r"(?im)(^|\n)\s*/approve\b")
REJECT_RE = re.compile(r"(?im)(^|\n)\s*/reject\b")
WORKER_START_FAILURE_RE = re.compile(
    r"(?is)(encountered an error.*unable to start working|unable to start working|agent failed to start)"
)
WEAK_EVIDENCE_PREFIX = "Weak worker-start evidence:"
RECONCILIATION_INCOMPLETE_PREFIX = "Reconciliation incomplete:"

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
    weak: bool = False,
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
    if weak:
        run.status = RUN_STATUS_AWAITING_WORKER_START
        run.last_summary = (
            f"{WEAK_EVIDENCE_PREFIX} {reason}. "
            "Awaiting authoritative evidence: linked PR + checks/review."
        )
        run.updated_at = _utc_now()
        task.status = TASK_STATUS_AWAITING_WORKER_START
        task.latest_summary = run.last_summary
        task.updated_at = _utc_now()
    else:
        run.status = RUN_STATUS_WORKING
        run.last_summary = reason
        run.updated_at = _utc_now()
        task.status = TASK_STATUS_WORKING
        task.latest_summary = reason
        task.updated_at = _utc_now()
    _save(session, run, task)
    link_run_to_slice(session, run=run, task=task)
    if weak:
        notify_discord(
            "Weak worker-start evidence observed: "
            f"{task.github_repo}#{task.github_issue_number} -> {_worker_display_name(task)}"
        )
    else:
        notify_discord(
            f"Worker started: {task.github_repo}#{task.github_issue_number} -> {_worker_display_name(task)}"
        )


def _is_weak_worker_start_run(task: TaskPacket, run: AgentRun) -> bool:
    summary = (run.last_summary or task.latest_summary or "").lower()
    has_weak_summary = "worker start signal" in summary or WEAK_EVIDENCE_PREFIX.lower() in summary
    has_authoritative = bool(run.github_pr_number or run.review_artifact_json or run.continuation_decision)
    return has_weak_summary and not has_authoritative


def reconcile_stale_weak_evidence_run(
    session: Session,
    *,
    task: TaskPacket,
    run: AgentRun,
    trigger: str,
    force: bool = False,
) -> bool:
    if run.status in {RUN_STATUS_COMPLETED, RUN_STATUS_FAILED, RUN_STATUS_BLOCKED, RUN_STATUS_WORKER_FAILED}:
        return False
    if not _is_weak_worker_start_run(task, run):
        return False
    settings = get_settings()
    threshold_minutes = max(5, int(getattr(settings, "worker_weak_evidence_stale_minutes", 90) or 90))
    age = _utc_now() - _as_utc(run.updated_at or run.created_at)
    if not force and age < timedelta(minutes=threshold_minutes):
        return False
    missing: list[str] = []
    if not run.github_pr_number:
        missing.append("github_pr_number")
    if not run.review_artifact_json:
        missing.append("review_artifact_json")
    if not run.continuation_decision:
        missing.append("continuation_decision")
    reason = (
        "Stale weak worker-start evidence reconciled to blocked. "
        f"trigger={trigger}; missing={', '.join(missing) or 'none'}; "
        f"age_minutes={int(age.total_seconds() // 60)}"
    )
    run.status = RUN_STATUS_BLOCKED
    run.last_summary = reason
    run.updated_at = _utc_now()
    task.status = TASK_STATUS_BLOCKED
    task.latest_summary = reason
    task.updated_at = _utc_now()
    _save(session, run, task)
    link_run_to_slice(session, run=run, task=task)
    notify_discord(
        f"Stale weak evidence blocked: {task.github_repo}#{task.github_issue_number} -> {_worker_display_name(task)}"
    )
    return True


def mark_reconciliation_incomplete(
    session: Session,
    *,
    task: TaskPacket,
    summary: str,
) -> None:
    if task.id is None:
        return
    run = _latest_run_for_task(session, task.id)
    if run is None:
        return
    if run.status in {RUN_STATUS_COMPLETED, RUN_STATUS_FAILED}:
        return
    run.status = RUN_STATUS_BLOCKED
    run.last_summary = f"{RECONCILIATION_INCOMPLETE_PREFIX} {summary}"
    run.updated_at = _utc_now()
    task.status = TASK_STATUS_BLOCKED
    task.latest_summary = run.last_summary
    task.updated_at = _utc_now()
    _save(session, run, task)
    link_run_to_slice(session, run=run, task=task)


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
    link_run_to_slice(session, run=run, task=task)
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


def _as_utc(dt: datetime | None) -> datetime:
    if dt is None:
        return _utc_now()
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _parse_json_list(raw_json: str | None) -> list[Any]:
    if not raw_json:
        return []
    try:
        parsed = json.loads(raw_json)
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []


def _governor_guarded_patterns(settings: Settings) -> list[str]:
    raw = str(getattr(settings, "governor_guarded_paths", "") or "")
    return [item.strip() for item in raw.split(",") if item.strip()]


def _matches_guarded_path(path: str, guarded_patterns: list[str]) -> bool:
    normalized = path.strip().lstrip("/")
    for pattern in guarded_patterns:
        candidate = pattern.strip().lstrip("/")
        if not candidate:
            continue
        if fnmatch.fnmatch(normalized, candidate):
            return True
    return False


def _load_governor_state(run: AgentRun) -> dict[str, Any]:
    state = _parse_json_object(run.governor_state_json)
    if state is None:
        state = {}
    state.setdefault("pr_draft", None)
    state.setdefault("pr_state", None)
    state.setdefault("requested_reviewers", [])
    state.setdefault("changed_files", [])
    state.setdefault("copilot_review_observed", False)
    state.setdefault("unresolved_copilot_findings", [])
    state.setdefault("revision_cycle_count", 0)
    state.setdefault("guarded_paths_touched", False)
    state.setdefault("guarded_files", [])
    state.setdefault("last_event_key", "")
    state.setdefault("last_revision_comment_fingerprint", "")
    state.setdefault("last_revision_comment_body", "")
    state.setdefault("approval_submitted", False)
    state.setdefault("merge_completed", False)
    state.setdefault("waiting_for_revision_push", False)
    state.setdefault("reviewer_cleanup_result", "")
    state.setdefault("safe_draft_promoted", False)
    state.setdefault("safe_draft_promotion_failed", False)
    state.setdefault("fix_trigger_fingerprint", "")
    state.setdefault("review_harvest_summary", "")
    state.setdefault("review_batch_artifact", {})
    state.setdefault("checkpoints", {})
    return state


def _save_governor_state(run: AgentRun, state: dict[str, Any]) -> None:
    run.governor_state_json = json.dumps(state, ensure_ascii=False)


_governor_logger = logging.getLogger("orchestrator.governor")


def _set_checkpoint(
    state: dict[str, Any],
    *,
    name: str,
    success: bool,
    summary: str,
) -> None:
    checkpoints = state.setdefault("checkpoints", {})
    checkpoints[name] = {
        "success": bool(success),
        "summary": str(summary or ""),
        "updated_at": _utc_now().isoformat(),
    }


def safe_draft_can_be_promoted(
    *,
    pr_draft: bool,
    checks_passed: bool,
    guarded_paths_touched: bool,
    unresolved_findings: list[str],
    waiting_for_revision_push: bool,
) -> bool:
    """Deterministic predicate: can this safe draft PR be promoted to ready-for-review?

    Returns True only when ALL of the following hold:
    - PR is still a draft
    - All required checks are green (checks_passed)
    - No guarded paths are touched
    - No unresolved blocking findings
    - No outstanding revision request awaiting a new Copilot push
    """
    if not pr_draft:
        return False
    if not checks_passed:
        return False
    if guarded_paths_touched:
        return False
    if unresolved_findings:
        return False
    if waiting_for_revision_push:
        return False
    return True


def _copilot_findings_from_reviews(
    *,
    settings: Settings,
    reviews: list[dict[str, Any]],
    comments: list[dict[str, Any]],
) -> tuple[bool, list[str]]:
    findings: list[str] = []
    observed = False
    for review in reviews:
        user = review.get("user") if isinstance(review, dict) else None
        login = user.get("login") if isinstance(user, dict) else None
        if not _is_copilot_actor(settings=settings, login=login, display_name=None):
            continue
        observed = True
        body = str(review.get("body") or "").strip()
        state = str(review.get("state") or "").strip().upper()
        if body and state in {"COMMENTED", "CHANGES_REQUESTED"}:
            findings.append(body)
    for comment in comments:
        user = comment.get("user") if isinstance(comment, dict) else None
        login = user.get("login") if isinstance(user, dict) else None
        if not _is_copilot_actor(settings=settings, login=login, display_name=None):
            continue
        observed = True
        body = str(comment.get("body") or "").strip()
        if body:
            findings.append(body)
    deduped: list[str] = []
    seen: set[str] = set()
    for entry in findings:
        compact = " ".join(entry.split())
        if not compact:
            continue
        key = compact.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(compact)
    return observed, deduped[:20]


def _batched_revision_comment_body(*, governor_requests: list[str], copilot_findings: list[str]) -> str:
    lines = ["@copilot Please apply the following revisions in this PR branch:"]
    request_lines = governor_requests or copilot_findings
    for index, item in enumerate(request_lines[:12], start=1):
        lines.append(f"{index}. {item}")
    if len(lines) == 1:
        lines.append("1. Re-run your review, resolve outstanding findings, and update validation evidence.")
    return "\n".join(lines)


def _copilot_fix_trigger_body(*, findings: list[str]) -> str:
    """Build the deterministic @copilot fix-trigger comment for unresolved review findings."""
    lines = [
        "@copilot apply the unresolved review feedback on this pull request "
        "and push fixes directly to this branch.",
        "",
        "Focus on:",
    ]
    for finding in findings[:12]:
        lines.append(f"- {finding}")
    if not findings:
        lines.append("- Re-run your review, resolve outstanding findings, and update validation evidence.")
    lines.append("")
    lines.append(
        "If a finding is not valid, explain briefly in the PR conversation "
        "instead of changing code."
    )
    return "\n".join(lines)


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


def _run_governor_loop(
    session: Session,
    *,
    settings: Settings,
    task: TaskPacket,
    run: AgentRun,
    pr_payload: dict[str, Any],
    event_key: str,
    checks_passed: bool,
) -> None:
    pr_number = run.github_pr_number
    if not isinstance(pr_number, int):
        return
    state = _load_governor_state(run)
    if state.get("last_event_key") == event_key:
        return
    _set_checkpoint(
        state,
        name="issue_dispatched",
        success=bool(run.github_dispatch_id or run.github_dispatch_url or run.status != RUN_STATUS_QUEUED),
        summary="Dispatch evidence observed for run." if (run.github_dispatch_id or run.github_dispatch_url or run.status != RUN_STATUS_QUEUED) else "Dispatch evidence missing.",
    )
    _set_checkpoint(
        state,
        name="pr_discovered",
        success=True,
        summary=f"PR linkage discovered: #{pr_number}.",
    )
    event_has_push_signal = ":synchronize:" in event_key
    event_has_review_signal = ("pull_request_review:" in event_key) or ("pull_request_review_comment:" in event_key)

    pr_draft = bool(pr_payload.get("draft"))
    pr_state = str(pr_payload.get("state") or "open")
    _set_checkpoint(
        state,
        name="pr_ready_verified",
        success=not pr_draft,
        summary="PR is non-draft (ready for review)." if not pr_draft else "PR remains draft.",
    )
    requested_reviewers = []
    for item in pr_payload.get("requested_reviewers") or []:
        if isinstance(item, dict) and isinstance(item.get("login"), str):
            requested_reviewers.append(item["login"])

    changed_files = [path for path in _parse_json_list(json.dumps(state.get("changed_files", []))) if isinstance(path, str)]
    files, _ = list_pull_request_files(settings=settings, repo=task.github_repo, pr_number=pr_number)
    if files:
        changed_files = files
    guarded_patterns = _governor_guarded_patterns(settings)
    guarded_files = [path for path in changed_files if _matches_guarded_path(path, guarded_patterns)]
    guarded_paths_touched = bool(guarded_files)

    # --- Reviewer cleanup with truthful result tracking ---
    remove_login = str(getattr(settings, "governor_remove_reviewer_login", "") or "").strip()
    if remove_login and remove_login in {str(item).strip() for item in requested_reviewers}:
        cleanup_ok, cleanup_msg = remove_requested_reviewers(
            settings=settings,
            repo=task.github_repo,
            pr_number=pr_number,
            reviewers=[remove_login],
        )
        if cleanup_ok:
            requested_reviewers = [item for item in requested_reviewers if item != remove_login]
            state["reviewer_cleanup_result"] = f"removed:{remove_login}"
            _governor_logger.info("Governor reviewer cleanup: removed %s from PR #%s", remove_login, pr_number)
        else:
            state["reviewer_cleanup_result"] = f"failed:{cleanup_msg}"
            _governor_logger.warning("Governor reviewer cleanup failed for %s on PR #%s: %s", remove_login, pr_number, cleanup_msg)
    elif remove_login:
        state["reviewer_cleanup_result"] = "not_applicable:reviewer_not_present"
    else:
        state["reviewer_cleanup_result"] = "skipped:no_login_configured"

    reviews, reviews_msg = list_pull_request_reviews(settings=settings, repo=task.github_repo, pr_number=pr_number)
    review_comments, review_comments_msg = list_pull_request_review_comments(settings=settings, repo=task.github_repo, pr_number=pr_number)
    lower_reviews_msg = str(reviews_msg or "").lower()
    lower_review_comments_msg = str(review_comments_msg or "").lower()
    review_harvested = (
        "failure" not in lower_reviews_msg
        and "cannot list" not in lower_reviews_msg
        and "failure" not in lower_review_comments_msg
        and "cannot list" not in lower_review_comments_msg
    )
    state["review_harvest_summary"] = f"reviews={reviews_msg}; review_comments={review_comments_msg}"
    _set_checkpoint(
        state,
        name="review_harvested",
        success=review_harvested,
        summary=state["review_harvest_summary"],
    )
    copilot_review_observed, unresolved_findings = _copilot_findings_from_reviews(
        settings=settings,
        reviews=reviews,
        comments=review_comments,
    )

    # --- Update waiting_for_revision_push: clear when findings resolved ---
    waiting_for_revision_push = bool(state.get("waiting_for_revision_push"))
    if waiting_for_revision_push and not unresolved_findings:
        waiting_for_revision_push = False
        state["waiting_for_revision_push"] = False
        _set_checkpoint(
            state,
            name="copilot_push_rereview_observed",
            success=True,
            summary="Revision findings cleared after waiting for Copilot revision push.",
        )
    elif waiting_for_revision_push and (event_has_push_signal or event_has_review_signal):
        _set_checkpoint(
            state,
            name="copilot_push_rereview_observed",
            success=True,
            summary="Copilot push/re-review signal observed while waiting for revision.",
        )
    if not unresolved_findings:
        _set_checkpoint(
            state,
            name="continuation_comment_posted",
            success=True,
            summary="No actionable unresolved review findings; no continuation comment needed.",
        )

    # --- Deterministic fix-trigger for ready PRs with unresolved Copilot findings ---
    if (
        not pr_draft
        and copilot_review_observed
        and unresolved_findings
        and not guarded_paths_touched
    ):
        mixed_review_states = {
            str(item.get("state") or "").upper()
            for item in reviews
            if isinstance(item, dict) and isinstance(item.get("state"), str)
        }
        escalate_batch_model = bool(
            len(unresolved_findings) > 12
            or (len(reviews) + len(review_comments) > 80)
            or ("CHANGES_REQUESTED" in mixed_review_states and "APPROVED" in mixed_review_states)
        )
        batch_context = json.dumps(
            {
                "repo": task.github_repo,
                "issue_number": task.github_issue_number,
                "pr_number": pr_number,
                "unresolved_findings": unresolved_findings,
                "reviews": reviews[:50],
                "review_comments": review_comments[:120],
                "max_items": 12,
            },
            ensure_ascii=False,
        )
        batch_payload = summarize_copilot_review_batch(
            settings=settings,
            update_context=batch_context,
            previous_response_id=run.openai_last_response_id,
            force_flagship=escalate_batch_model,
        )
        batch_openai_meta = batch_payload.get("openai_meta") if isinstance(batch_payload, dict) else {}
        batch_response_id = batch_openai_meta.get("response_id") if isinstance(batch_openai_meta, dict) else None
        if isinstance(batch_response_id, str) and batch_response_id.strip():
            run.openai_last_response_id = batch_response_id.strip()
        batch_artifact = (
            batch_payload.get("review_batch_artifact")
            if isinstance(batch_payload.get("review_batch_artifact"), dict)
            else {}
        )
        state["review_batch_artifact"] = batch_artifact
        should_trigger_copilot = bool(batch_artifact.get("should_trigger_copilot"))
        trigger_body = str(batch_artifact.get("comment_body") or "").strip() or _copilot_fix_trigger_body(
            findings=unresolved_findings
        )
        if not trigger_body.startswith("@copilot"):
            trigger_body = f"@copilot {trigger_body}"
        trigger_fp = hashlib.sha1(trigger_body.encode("utf-8")).hexdigest()
        already_triggered = state.get("fix_trigger_fingerprint") == trigger_fp
        if should_trigger_copilot and not already_triggered:
            existing_comments, _ = list_issue_comments(
                settings=settings, repo=task.github_repo, issue_number=pr_number,
            )
            exists_remote = any(
                isinstance(c, dict) and str(c.get("body") or "").strip() == trigger_body.strip()
                for c in existing_comments
            )
            if not exists_remote:
                comment_ok, comment_msg = post_copilot_follow_up_comment(
                    settings=settings, repo=task.github_repo, issue_number=pr_number, body=trigger_body,
                )
                if not comment_ok:
                    _set_checkpoint(
                        state,
                        name="continuation_comment_posted",
                        success=False,
                        summary=comment_msg,
                    )
                    state["last_event_key"] = event_key
                    state["last_governor_decision"] = "copilot_follow_up_comment_failed"
                    state["last_governor_summary"] = [comment_msg]
                    run.last_summary = (
                        f"{run.last_summary or ''}\nGovernor: copilot_follow_up_comment_failed ({comment_msg})"
                    ).strip()
                    run.updated_at = _utc_now()
                    _save_governor_state(run, state)
                    _save(session, run)
                    return
            _set_checkpoint(
                state,
                name="continuation_comment_posted",
                success=True,
                summary="Batched top-level @copilot continuation comment posted (or already present remotely).",
            )
            state["fix_trigger_fingerprint"] = trigger_fp
            state["revision_cycle_count"] = int(state.get("revision_cycle_count") or 0) + 1
            state["waiting_for_revision_push"] = True
            waiting_for_revision_push = True
        elif should_trigger_copilot and already_triggered:
            _set_checkpoint(
                state,
                name="continuation_comment_posted",
                success=True,
                summary="Batched top-level @copilot continuation comment already posted for current fingerprint.",
            )
        else:
            _set_checkpoint(
                state,
                name="continuation_comment_posted",
                success=True,
                summary="No actionable/deduplicated continuation comment required this cycle.",
            )
        # Persist and short-circuit — no OpenAI call needed.
        state["pr_draft"] = pr_draft
        state["pr_state"] = pr_state
        state["requested_reviewers"] = requested_reviewers
        state["changed_files"] = changed_files
        state["copilot_review_observed"] = copilot_review_observed
        state["unresolved_copilot_findings"] = unresolved_findings
        state["guarded_paths_touched"] = guarded_paths_touched
        state["guarded_files"] = guarded_files
        state["last_event_key"] = event_key
        state["last_governor_decision"] = "fix_trigger_posted" if not already_triggered else "fix_trigger_waiting"
        state["last_governor_summary"] = [
            "Deterministic fix-trigger: posted @copilot fix request for unresolved review findings."
        ] if not already_triggered else [
            "Deterministic fix-trigger: waiting for Copilot push (trigger already posted)."
        ]
        max_cycles = max(1, int(getattr(settings, "governor_max_revision_cycles", 2) or 2))
        if int(state.get("revision_cycle_count") or 0) > max_cycles:
            state["last_governor_decision"] = "escalate_human"
            state["last_governor_summary"] = ["Max governor revision cycles exceeded."]
            if task.program_id:
                program = session.get(Program, task.program_id)
                if program is not None:
                    program.status = "blocked"
                    program.blocker_state_json = json.dumps(
                        {
                            "reason": "escalated_to_human",
                            "slice_id": task.program_slice_id,
                            "run_id": run.id,
                            "pr_number": pr_number,
                            "detail": "Max governor revision cycles exceeded.",
                        },
                        ensure_ascii=False,
                    )
                    program.latest_summary = "Max governor revision cycles exceeded."
                    program.updated_at = _utc_now()
                    _save(session, program)
        suffix = state["last_governor_summary"][0] if state["last_governor_summary"] else state["last_governor_decision"]
        run.last_summary = f"{run.last_summary or ''}\nGovernor: {state['last_governor_decision']} ({suffix})".strip()
        run.updated_at = _utc_now()
        _save_governor_state(run, state)
        _save(session, run)
        return

    # --- Deterministic safe-draft promotion (before OpenAI) ---
    if safe_draft_can_be_promoted(
        pr_draft=pr_draft,
        checks_passed=checks_passed,
        guarded_paths_touched=guarded_paths_touched,
        unresolved_findings=unresolved_findings,
        waiting_for_revision_push=waiting_for_revision_push,
    ):
        _governor_logger.info(
            "Governor deterministic promotion: PR #%s is safe draft with green checks, "
            "no guarded paths, no unresolved findings, no pending revision push — marking ready for review.",
            pr_number,
        )
        success, msg = mark_pr_ready_for_review(settings=settings, repo=task.github_repo, pr_number=pr_number)
        state["pr_draft"] = pr_draft
        state["pr_state"] = pr_state
        state["requested_reviewers"] = requested_reviewers
        state["changed_files"] = changed_files
        state["copilot_review_observed"] = copilot_review_observed
        state["unresolved_copilot_findings"] = unresolved_findings
        state["guarded_paths_touched"] = guarded_paths_touched
        state["guarded_files"] = guarded_files
        state["last_event_key"] = event_key
        if success:
            _set_checkpoint(
                state,
                name="pr_ready_verified",
                success=True,
                summary="Draft->ready transition completed and verified (draft=False).",
            )
            state["safe_draft_promoted"] = True
            state["safe_draft_promotion_failed"] = False
            state["last_governor_decision"] = "safe_draft_promoted"
            state["last_governor_summary"] = ["Deterministic safe-draft promotion: PR marked ready for review."]
            run.last_summary = f"{run.last_summary or ''}\nGovernor: safe_draft_promoted (deterministic policy)".strip()
            run.updated_at = _utc_now()
            _save_governor_state(run, state)
            _save(session, run)
            notify_discord(
                f"Governor auto-promoted draft PR #{pr_number} to ready for review: {task.github_repo}#{task.github_issue_number}"
            )
            _governor_logger.info("Governor: PR #%s successfully promoted to ready for review.", pr_number)
            return
        else:
            _set_checkpoint(
                state,
                name="pr_ready_verified",
                success=False,
                summary=f"Draft->ready transition failed: {msg}",
            )
            state["safe_draft_promoted"] = False
            state["safe_draft_promotion_failed"] = True
            state["last_governor_decision"] = "safe_draft_promotion_failed"
            state["last_governor_summary"] = [f"Deterministic safe-draft promotion failed: {msg}"]
            _governor_logger.warning("Governor: failed to promote PR #%s: %s", pr_number, msg)
            if task.program_id:
                program = session.get(Program, task.program_id)
                if program is not None:
                    program.status = "blocked"
                    program.blocker_state_json = json.dumps(
                        {
                            "reason": BLOCKER_WAITING_FOR_PR_READY,
                            "slice_id": task.program_slice_id,
                            "run_id": run.id,
                            "pr_number": pr_number,
                            "detail": msg,
                        },
                        ensure_ascii=False,
                    )
                    program.latest_summary = f"Draft PR #{pr_number} promotion failed: {msg}"
                    program.updated_at = _utc_now()
                    _save(session, program)
            run.last_summary = f"{run.last_summary or ''}\nGovernor: safe_draft_promotion_failed ({msg})".strip()
            run.updated_at = _utc_now()
            _save_governor_state(run, state)
            _save(session, run)
            return

    review_artifact = _parse_json_object(run.review_artifact_json) or {}
    governor_context = {
        "event_key": event_key,
        "repo": task.github_repo,
        "issue_number": task.github_issue_number,
        "pr_number": pr_number,
        "pr": {
            "draft": pr_draft,
            "state": pr_state,
            "requested_reviewers": requested_reviewers,
        },
        "checks_passed": checks_passed,
        "review_artifact": review_artifact,
        "copilot_review_observed": copilot_review_observed,
        "unresolved_copilot_findings": unresolved_findings,
        "changed_files": changed_files,
        "guarded_paths_touched": guarded_paths_touched,
        "guarded_files": guarded_files,
        "revision_cycle_count": int(state.get("revision_cycle_count") or 0),
    }
    decision_payload = summarize_governor_update(
        settings=settings,
        update_context=json.dumps(governor_context, ensure_ascii=False),
        previous_response_id=run.openai_last_response_id,
    )
    openai_meta = decision_payload.get("openai_meta") if isinstance(decision_payload, dict) else {}
    response_id = openai_meta.get("response_id") if isinstance(openai_meta, dict) else None
    if isinstance(response_id, str) and response_id.strip():
        run.openai_last_response_id = response_id.strip()
    artifact = decision_payload.get("governor_artifact") if isinstance(decision_payload, dict) else {}
    decision = str((artifact or {}).get("decision") or "wait")
    summary_bullets = artifact.get("summary") if isinstance(artifact.get("summary"), list) else []
    revision_requests = artifact.get("revision_requests") if isinstance(artifact.get("revision_requests"), list) else []
    escalation_reason = str(artifact.get("escalation_reason") or "")

    state["pr_draft"] = pr_draft
    state["pr_state"] = pr_state
    state["requested_reviewers"] = requested_reviewers
    state["changed_files"] = changed_files
    state["copilot_review_observed"] = copilot_review_observed
    state["unresolved_copilot_findings"] = unresolved_findings
    state["guarded_paths_touched"] = guarded_paths_touched
    state["guarded_files"] = guarded_files
    state["last_event_key"] = event_key
    state["last_governor_decision"] = decision
    state["last_governor_summary"] = summary_bullets

    if guarded_paths_touched:
        decision = "escalate_human"
        escalation_reason = escalation_reason or "Guarded paths changed; unattended approve/merge is blocked."
        if task.program_id:
            program = session.get(Program, task.program_id)
            if program is not None:
                program.status = "blocked"
                program.blocker_state_json = json.dumps(
                    {
                        "reason": BLOCKER_GUARDED_PATHS_REQUIRE_HUMAN,
                        "slice_id": task.program_slice_id,
                        "run_id": run.id,
                        "pr_number": pr_number,
                        "guarded_files": guarded_files,
                    },
                    ensure_ascii=False,
                )
                program.latest_summary = escalation_reason
                program.updated_at = _utc_now()
                _save(session, program)

    if decision == "request_revision":
        rendered_requests = [str(item).strip() for item in revision_requests if str(item).strip()]
        rendered_findings = [str(item).strip() for item in unresolved_findings if str(item).strip()]
        comment_body = _batched_revision_comment_body(
            governor_requests=rendered_requests,
            copilot_findings=rendered_findings,
        )
        fingerprint = hashlib.sha1(comment_body.encode("utf-8")).hexdigest()
        already_posted = state.get("last_revision_comment_fingerprint") == fingerprint
        if not already_posted:
            existing_comments, _ = list_issue_comments(settings=settings, repo=task.github_repo, issue_number=pr_number)
            exists_remote = any(
                isinstance(item, dict) and str(item.get("body") or "").strip() == comment_body.strip()
                for item in existing_comments
            )
            if not exists_remote:
                comment_ok, comment_msg = post_copilot_follow_up_comment(
                    settings=settings,
                    repo=task.github_repo,
                    issue_number=pr_number,
                    body=comment_body,
                )
                if not comment_ok:
                    _set_checkpoint(
                        state,
                        name="continuation_comment_posted",
                        success=False,
                        summary=comment_msg,
                    )
                    state["last_event_key"] = event_key
                    state["last_governor_decision"] = "copilot_follow_up_comment_failed"
                    state["last_governor_summary"] = [comment_msg]
                    run.last_summary = (
                        f"{run.last_summary or ''}\nGovernor: copilot_follow_up_comment_failed ({comment_msg})"
                    ).strip()
                    run.updated_at = _utc_now()
                    _save_governor_state(run, state)
                    _save(session, run)
                    return
            _set_checkpoint(
                state,
                name="continuation_comment_posted",
                success=True,
                summary="Top-level @copilot continuation comment posted for governor revision request.",
            )
            state["last_revision_comment_fingerprint"] = fingerprint
            state["last_revision_comment_body"] = comment_body
            state["revision_cycle_count"] = int(state.get("revision_cycle_count") or 0) + 1
            state["waiting_for_revision_push"] = True
            _set_checkpoint(
                state,
                name="copilot_push_rereview_observed",
                success=False,
                summary="Waiting for Copilot revision push/re-review after continuation comment.",
            )
        elif already_posted:
            _set_checkpoint(
                state,
                name="continuation_comment_posted",
                success=True,
                summary="Matching continuation comment already posted; no duplicate comment sent.",
            )
        max_cycles = max(1, int(getattr(settings, "governor_max_revision_cycles", 2) or 2))
        if int(state.get("revision_cycle_count") or 0) > max_cycles:
            decision = "escalate_human"
            escalation_reason = "Max governor revision cycles exceeded."

    if decision == "ready_for_review" and pr_draft:
        success, msg = mark_pr_ready_for_review(settings=settings, repo=task.github_repo, pr_number=pr_number)
        _set_checkpoint(
            state,
            name="pr_ready_verified",
            success=bool(success),
            summary=msg,
        )
        if not success:
            _governor_logger.warning("Governor: OpenAI-directed ready_for_review failed for PR #%s: %s", pr_number, msg)
    if decision == "approve_and_merge":
        ready_gate = bool((state.get("checkpoints") or {}).get("pr_ready_verified", {}).get("success"))
        harvest_gate = bool((state.get("checkpoints") or {}).get("review_harvested", {}).get("success"))
        pr_gate = bool((state.get("checkpoints") or {}).get("pr_discovered", {}).get("success"))
        dispatch_gate = bool((state.get("checkpoints") or {}).get("issue_dispatched", {}).get("success"))
        if (
            guarded_paths_touched
            or unresolved_findings
            or pr_draft
            or not checks_passed
            or waiting_for_revision_push
            or not ready_gate
            or not harvest_gate
            or not pr_gate
            or not dispatch_gate
        ):
            decision = "wait"
        else:
            if not bool(state.get("approval_submitted")):
                submit_approving_review(settings=settings, repo=task.github_repo, pr_number=pr_number)
                state["approval_submitted"] = True
            merged, merge_msg = merge_pr(settings=settings, repo=task.github_repo, pr_number=pr_number)
            _set_checkpoint(
                state,
                name="merge_attempted_latest_sha",
                success=bool(merged),
                summary=merge_msg,
            )
            if merged:
                state["merge_completed"] = True
                _set_checkpoint(
                    state,
                    name="merge_verified",
                    success=True,
                    summary="Merge completed and verified with merged=true postcondition.",
                )
            else:
                _set_checkpoint(
                    state,
                    name="merge_verified",
                    success=False,
                    summary=merge_msg,
                )
    if decision == "escalate_human" and task.program_id and not guarded_paths_touched:
        program = session.get(Program, task.program_id)
        if program is not None:
            program.status = "blocked"
            program.blocker_state_json = json.dumps(
                {
                    "reason": "escalated_to_human",
                    "slice_id": task.program_slice_id,
                    "run_id": run.id,
                    "pr_number": pr_number,
                    "detail": escalation_reason or "Governor requested escalation.",
                },
                ensure_ascii=False,
            )
            program.latest_summary = escalation_reason or "Governor requested escalation."
            program.updated_at = _utc_now()
            _save(session, program)
            fallback = str(getattr(settings, "governor_fallback_reviewer", "") or "").strip()
            if fallback:
                request_reviewers(
                    settings=settings,
                    repo=task.github_repo,
                    pr_number=pr_number,
                    reviewers=[fallback],
                )

    suffix = "; ".join(summary_bullets[:2]) if summary_bullets else decision
    run.last_summary = f"{run.last_summary or ''}\nGovernor: {decision} ({suffix})".strip()
    run.updated_at = _utc_now()
    _save_governor_state(run, state)
    _save(session, run)


def _extract_plan_artifacts(task: TaskPacket, plan_payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any] | None]:
    if isinstance(plan_payload.get("internal_plan"), dict):
        internal_plan = plan_payload["internal_plan"]
    else:
        internal_plan = plan_payload

    worker_brief = (
        plan_payload.get("worker_brief")
        if isinstance(plan_payload.get("worker_brief"), dict)
        else _default_worker_brief(task, internal_plan)
    )
    program_plan = plan_payload.get("program_plan") if isinstance(plan_payload.get("program_plan"), dict) else None
    return internal_plan, worker_brief, program_plan


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
        "program_id": task.program_id,
        "program_slice_id": task.program_slice_id,
        "task_kind": task.task_kind,
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
        "openai_last_response_id": task.openai_last_response_id,
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
    governor_state = _parse_json_object(run.governor_state_json)
    return {
        "id": run.id,
        "task_packet_id": run.task_packet_id,
        "program_id": run.program_id,
        "program_slice_id": run.program_slice_id,
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
        "governor_state": governor_state,
        "governor_state_json": run.governor_state_json,
        "openai_last_response_id": run.openai_last_response_id,
        "continuation_decision": run.continuation_decision,
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
    run = _latest_run_for_task(session, task.id)
    if task is not None and run is not None:
        reconcile_stale_weak_evidence_run(session, task=task, run=run, trigger="inspection")
        run = _latest_run_for_task(session, task.id)
        task = session.get(TaskPacket, task_id)
    return task, run


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
            previous_response_id=task.openai_last_response_id,
        )
        internal_plan, worker_brief, program_plan = _extract_plan_artifacts(task, plan_payload)
        task.internal_plan_json = json.dumps(internal_plan, ensure_ascii=False)
        task.worker_brief_json = json.dumps(worker_brief, ensure_ascii=False)
        task.normalized_task_text = _render_normalized_text(internal_plan)
        task.acceptance_criteria_json = json.dumps(worker_brief.get("acceptance_criteria") or [], ensure_ascii=False)
        task.validation_commands_json = json.dumps(worker_brief.get("validation_commands") or [], ensure_ascii=False)
        task.recommended_worker = _normalize_worker_slug(internal_plan.get("recommended_worker"))
        task.recommended_scope_class = _normalize_scope_class(internal_plan.get("recommended_scope_class"))
        _apply_worker_selection(task=task, settings=settings, issue_labels=issue_labels)
        planning_meta = plan_payload.get("planning_meta") if isinstance(plan_payload, dict) else {}
        plan_response_id = planning_meta.get("openai_last_response_id") if isinstance(planning_meta, dict) else None
        if isinstance(plan_response_id, str) and plan_response_id.strip():
            task.openai_last_response_id = plan_response_id.strip()
        ensure_program_for_task(
            session,
            settings=settings,
            task=task,
            internal_plan=internal_plan,
            worker_brief=worker_brief,
            program_plan=program_plan,
        )
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

    # Trusted kickoff: if the issue carries the trusted kickoff label and policy
    # allows, auto-confirm after planning so the operator does not need a second
    # manual approval step.
    has_kickoff_label = bool(settings.trusted_kickoff_label and settings.trusted_kickoff_label in labels)
    if (
        has_kickoff_label
        and settings.program_trusted_auto_confirm
        and task.status == TASK_STATUS_AWAITING_APPROVAL
        and task.approval_state == APPROVAL_PENDING
    ):
        process_approval(session, settings=settings, task=task, approved=True, source="trusted_kickoff_label")

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
                weak=True,
            )
    if task.id:
        latest_run = _latest_run_for_task(session, task.id)
        if latest_run is not None:
            reconcile_stale_weak_evidence_run(session, task=task, run=latest_run, trigger="issue_event")


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
        mark_slice_approved(session, task=task)
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
                    weak=True,
                )
        if task.id:
            latest_run = _latest_run_for_task(session, task.id)
            if latest_run is not None:
                reconcile_stale_weak_evidence_run(session, task=task, run=latest_run, trigger="issue_comment")
        return

    process_approval(session, settings=settings, task=task, approved=approved, source="comment")


def dispatch_task_if_ready(session: Session, *, settings: Settings, task: TaskPacket, force: bool = False) -> None:
    if task.id is None:
        return
    if task.approval_state != APPROVAL_APPROVED:
        return
    latest_run = _latest_run_for_task(session, task.id)
    if not force and latest_run and latest_run.status in {
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
        program_id=task.program_id,
        program_slice_id=task.program_slice_id,
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
    link_run_to_slice(session, run=run, task=task)

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
        link_run_to_slice(session, run=run, task=task)
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
        link_run_to_slice(session, run=run, task=task)
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
    link_run_to_slice(session, run=run, task=task)
    notify_discord(
        "Task failed to dispatch: "
        f"{task.github_repo}#{task.github_issue_number} -> {_worker_display_name(task)} "
        f"({dispatch_mode_summary})"
    )


def _task_for_pr_payload(session: Session, *, github_repo: str, pr_payload: dict[str, Any]) -> TaskPacket | None:
    pr_number = pr_payload.get("number")
    if isinstance(pr_number, int):
        run_query = (
            select(AgentRun)
            .where(AgentRun.github_repo == github_repo)
            .where(AgentRun.github_pr_number == pr_number)
            .order_by(AgentRun.updated_at.desc())
            .limit(1)
        )
        existing_run = session.exec(run_query).first()
        if existing_run is not None:
            linked_task = session.get(TaskPacket, existing_run.task_packet_id)
            if linked_task is not None:
                return linked_task

    body = str(pr_payload.get("body") or "")
    title = str(pr_payload.get("title") or "")
    refs = ISSUE_REF_RE.findall(f"{title}\n{body}")
    for issue_ref in refs:
        task = _get_task_by_repo_issue(session, github_repo=github_repo, github_issue_number=int(issue_ref))
        if task is not None:
            return task
    return None


def _summarize_and_store(
    session: Session,
    *,
    settings: Settings,
    task: TaskPacket,
    run: AgentRun,
    context: str,
    run_status: str,
    event_key: str,
    checks_passed: bool,
    pr_is_draft: bool = False,
) -> None:
    try:
        summary = summarize_work_update(
            settings=settings,
            update_context=context,
            previous_response_id=run.openai_last_response_id,
        )
        openai_meta = summary.get("openai_meta") if isinstance(summary, dict) else {}
        response_id = openai_meta.get("response_id") if isinstance(openai_meta, dict) else None
        if isinstance(response_id, str) and response_id.strip():
            run.openai_last_response_id = response_id.strip()
        artifact = summary.get("review_artifact") if isinstance(summary.get("review_artifact"), dict) else {}
        bullets = summary.get("summary_bullets") or artifact.get("summary") or []
        next_action = summary.get("next_action") or artifact.get("decision") or "revise"
        rendered = "\n".join(f"- {line}" for line in bullets)
        full_summary = f"{rendered}\nNext action: {next_action}".strip()
        run.review_artifact_json = json.dumps(artifact, ensure_ascii=False) if artifact else None
    except Exception as exc:
        full_summary = f"Summary unavailable: {exc}"
        run.review_artifact_json = json.dumps(
            {
                "decision": "revise",
                "status": "blocked",
                "confidence": 0.0,
                "scope_alignment": [],
                "acceptance_assessment": [],
                "risk_findings": [],
                "merge_recommendation": "review_required",
                "revision_instructions": [str(exc)],
                "audit_recommendation": "",
                "next_slice_hint": "",
                "summary": [str(exc)],
            },
            ensure_ascii=False,
        )

    run.status = run_status
    run.last_summary = full_summary
    run.updated_at = _utc_now()

    task.latest_summary = full_summary
    task.updated_at = _utc_now()
    _save(session, run, task)
    link_run_to_slice(session, run=run, task=task)

    def _dispatch_fn(new_task: TaskPacket) -> None:
        dispatch_task_if_ready(session, settings=settings, task=new_task)

    decision = apply_reviewer_decision(
        session,
        settings=settings,
        task=task,
        run=run,
        event_key=event_key,
        checks_passed=checks_passed,
        dispatch_fn=_dispatch_fn,
    )

    if decision == "revise":
        task.status = TASK_STATUS_WORKING
        if run.github_pr_number:
            task.latest_summary = "Revision requested by reviewer; waiting for Copilot updates on existing PR branch"
        else:
            task.latest_summary = "Revision requested by reviewer; redispatching"
        task.updated_at = _utc_now()
        _save(session, task)
        if not run.github_pr_number:
            dispatch_task_if_ready(session, settings=settings, task=task, force=True)
        return

    # If the reviewer says continue/complete but the PR is still a draft, attempt
    # to mark it ready for review so it can be merged.  Surface a blocker if it fails.
    if decision in {"continue", "complete"} and pr_is_draft and run.github_pr_number:
        success, msg = mark_pr_ready_for_review(
            settings=settings,
            repo=task.github_repo,
            pr_number=run.github_pr_number,
        )
        if success:
            notify_discord(
                f"Draft PR #{run.github_pr_number} marked ready for review: {task.github_repo}#{task.github_issue_number}"
            )
        else:
            # Un-draft failed; surface an explicit blocker so the operator can act.
            # Distinguish permission failures (403) from other errors so the operator
            # knows whether this is a token scope issue or a transient problem.
            is_permissions_error = "403" in msg or "forbidden" in msg.lower() or "permission" in msg.lower()
            blocker_reason = BLOCKER_WAITING_FOR_PERMISSIONS if is_permissions_error else BLOCKER_WAITING_FOR_PR_READY
            if task.program_id:
                from .models import Program as _Program
                prog = session.get(_Program, task.program_id)
                if prog is not None:
                    prog.blocker_state_json = json.dumps(
                        {
                            "reason": blocker_reason,
                            "pr_number": run.github_pr_number,
                            "detail": msg,
                        },
                        ensure_ascii=False,
                    )
                    prog.latest_summary = f"Waiting: PR draft could not be un-drafted automatically. {msg}"
                    prog.updated_at = _utc_now()
                    _save(session, prog)
            notify_discord(
                f"Draft PR stall detected for {task.github_repo}#{task.github_issue_number}: {msg}"
            )


def _review_summary_suffix(run: AgentRun) -> str:
    artifact = _parse_json_object(run.review_artifact_json)
    if not artifact:
        return ""
    concise = artifact.get("summary")
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
) -> bool:
    github_repo = _repo_name(payload)
    pr = payload.get("pull_request") or {}
    if not github_repo or not isinstance(pr, dict):
        return False

    task = _task_for_pr_payload(session, github_repo=github_repo, pr_payload=pr)
    if task is None or task.id is None:
        pr_number = pr.get("number")
        if isinstance(pr_number, int):
            candidate_query = (
                select(TaskPacket)
                .where(TaskPacket.github_repo == github_repo)
                .where(
                    TaskPacket.status.in_(
                        [
                            TASK_STATUS_AWAITING_WORKER_START,
                            TASK_STATUS_WORKING,
                            TASK_STATUS_MANUAL_DISPATCH_NEEDED,
                            TASK_STATUS_DISPATCH_REQUESTED,
                        ]
                    )
                )
                .order_by(TaskPacket.updated_at.desc())
                .limit(1)
            )
            candidate = session.exec(candidate_query).first()
            if candidate is not None:
                mark_reconciliation_incomplete(
                    session,
                    task=candidate,
                    summary=(
                        f"external PR activity seen but no internal linkage for PR #{pr_number} "
                        f"(action={action or 'unknown'})"
                    ),
                )
        return False

    run = _latest_run_for_task(session, task.id)
    if run is None:
        run = AgentRun(
            task_packet_id=task.id,
            program_id=task.program_id,
            program_slice_id=task.program_slice_id,
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
    pr_is_draft = bool(pr.get("draft"))
    changed_files_count = pr.get("changed_files") if isinstance(pr.get("changed_files"), int) else None
    commits_count = pr.get("commits") if isinstance(pr.get("commits"), int) else None
    if isinstance(pr_number, int) and changed_files_count is None and action in {"opened", "reopened", "ready_for_review"}:
        inspection = inspect_pull_request(settings=settings, repo=github_repo, pr_number=pr_number)
        if inspection.ok:
            changed_files_count = inspection.changed_files
            commits_count = inspection.commits
    if action in {"opened", "reopened", "ready_for_review"}:
        if changed_files_count is not None and changed_files_count <= 0:
            run.status = RUN_STATUS_BLOCKED
            run.last_summary = f"Rejected empty PR #{pr_number} as implementation progress: changed_files={changed_files_count}."
            run.updated_at = _utc_now()
            task.status = TASK_STATUS_BLOCKED
            task.latest_summary = run.last_summary
            task.updated_at = _utc_now()
            _save(session, run, task)
            link_run_to_slice(session, run=run, task=task)
            notify_discord(f"Empty PR rejected as progress: {github_repo} PR #{pr_number} -> {_worker_display_name(task)}")
            return True
        context = json.dumps(
            {
                "event": "pull_request",
                "action": action,
                "repo": github_repo,
                "issue_number": task.github_issue_number,
                "task_kind": task.task_kind,
                "program_id": task.program_id,
                "program_slice_id": task.program_slice_id,
                "pr": {
                    "number": pr.get("number"),
                    "title": pr.get("title"),
                    "body": pr.get("body"),
                    "url": html_url,
                    "draft": pr.get("draft"),
                    "mergeable": pr.get("mergeable"),
                    "mergeable_state": pr.get("mergeable_state"),
                    "changed_files_count": changed_files_count,
                    "commits_count": commits_count,
                },
                "slice_objective": task.title,
                "acceptance_criteria": json.loads(task.acceptance_criteria_json or "[]"),
                "non_goals": [],
                "worker_summary": run.last_summary,
            },
            ensure_ascii=False,
        )
        _summarize_and_store(
            session,
            settings=settings,
            task=task,
            run=run,
            context=context,
            run_status=RUN_STATUS_PR_OPENED,
            event_key=f"pull_request:{pr.get('id')}:{action}:{pr.get('updated_at')}",
            checks_passed=False,
            pr_is_draft=pr_is_draft,
        )
        task.status = TASK_STATUS_PR_OPENED
        task.updated_at = _utc_now()
        _save(session, task)
        link_run_to_slice(session, run=run, task=task)
        notify_discord(
            f"PR opened / ready for review: {github_repo} PR #{pr.get('number')} -> {_worker_display_name(task)}"
            f"{_review_summary_suffix(run)}"
        )
        _run_governor_loop(
            session,
            settings=settings,
            task=task,
            run=run,
            pr_payload=pr,
            event_key=f"governor:pull_request:{pr.get('id')}:{action}:{pr.get('updated_at')}",
            checks_passed=False,
        )
        return True

    if action == "closed":
        merged = bool(pr.get("merged"))
        if merged:
            if not run.review_artifact_json or not run.continuation_decision:
                mark_reconciliation_incomplete(
                    session,
                    task=task,
                    summary=(
                        f"merged PR #{pr_number} missing required review evidence "
                        f"(review_artifact_json={'present' if bool(run.review_artifact_json) else 'missing'}, "
                        f"continuation_decision={'present' if bool(run.continuation_decision) else 'missing'})"
                    ),
                )
                return True
            run.status = RUN_STATUS_COMPLETED
            run.last_summary = f"PR merged: {html_url}" if html_url else "PR merged"
            run.updated_at = _utc_now()
            task.status = TASK_STATUS_COMPLETED
            task.latest_summary = run.last_summary
            task.updated_at = _utc_now()
            _save(session, run, task)
            link_run_to_slice(session, run=run, task=task)
            notify_discord(f"Task completed: {github_repo}#{task.github_issue_number}")

            # Critical: advance the program after a successful merge so the next
            # slice is created and dispatched automatically.
            def _dispatch_fn(new_task: TaskPacket) -> None:
                dispatch_task_if_ready(session, settings=settings, task=new_task)

            advance_program_on_pr_merge(
                session,
                settings=settings,
                task=task,
                run=run,
                dispatch_fn=_dispatch_fn,
            )
            return True

        run.status = RUN_STATUS_BLOCKED
        run.last_summary = f"PR closed without merge: {html_url}" if html_url else "PR closed without merge"
        run.updated_at = _utc_now()
        task.status = TASK_STATUS_BLOCKED
        task.latest_summary = run.last_summary
        task.updated_at = _utc_now()
        _save(session, run, task)
        link_run_to_slice(session, run=run, task=task)
        notify_discord(f"Task blocked (PR closed): {github_repo}#{task.github_issue_number}")
        return True

    run.status = RUN_STATUS_WORKING
    run.last_summary = f"PR action observed: {action}"
    run.updated_at = _utc_now()
    task.status = TASK_STATUS_WORKING
    task.latest_summary = run.last_summary
    task.updated_at = _utc_now()
    _save(session, run, task)
    link_run_to_slice(session, run=run, task=task)
    _run_governor_loop(
        session,
        settings=settings,
        task=task,
        run=run,
        pr_payload=pr,
        event_key=f"governor:pull_request:{pr.get('id')}:{action}:{pr.get('updated_at')}",
        checks_passed=False,
    )
    return True


def process_workflow_run_event(
    session: Session,
    *,
    settings: Settings,
    payload: dict[str, Any],
    action: str | None,
) -> bool:
    github_repo = _repo_name(payload)
    workflow_run = payload.get("workflow_run") or {}
    if not github_repo or not isinstance(workflow_run, dict):
        return False

    pr_entries = workflow_run.get("pull_requests") or []
    pr_numbers = [pr.get("number") for pr in pr_entries if isinstance(pr, dict) and isinstance(pr.get("number"), int)]
    if not pr_numbers:
        return False

    query = (
        select(AgentRun)
        .where(AgentRun.github_repo == github_repo)
        .where(AgentRun.github_pr_number.in_(pr_numbers))
        .order_by(AgentRun.updated_at.desc())
        .limit(1)
    )
    run = session.exec(query).first()
    if run is None:
        candidate_query = (
            select(TaskPacket)
            .where(TaskPacket.github_repo == github_repo)
            .where(
                TaskPacket.status.in_(
                    [
                        TASK_STATUS_AWAITING_WORKER_START,
                        TASK_STATUS_WORKING,
                        TASK_STATUS_MANUAL_DISPATCH_NEEDED,
                        TASK_STATUS_DISPATCH_REQUESTED,
                    ]
                )
            )
            .order_by(TaskPacket.updated_at.desc())
            .limit(1)
        )
        candidate = session.exec(candidate_query).first()
        if candidate is not None:
            mark_reconciliation_incomplete(
                session,
                task=candidate,
                summary=(
                    "workflow activity seen but no linked internal run for PR(s) "
                    f"{pr_numbers}"
                ),
            )
        return False

    task = session.get(TaskPacket, run.task_packet_id)
    if task is None:
        return False

    conclusion = str(workflow_run.get("conclusion") or "")
    status = str(workflow_run.get("status") or "")
    name = str(workflow_run.get("name") or "workflow")
    html_url = str(workflow_run.get("html_url") or "")

    context = json.dumps(
        {
            "event": "workflow_run",
            "action": action,
            "repo": github_repo,
            "issue_number": task.github_issue_number,
            "program_id": task.program_id,
            "program_slice_id": task.program_slice_id,
            "workflow": {
                "id": workflow_run.get("id"),
                "name": name,
                "status": status,
                "conclusion": conclusion,
                "url": html_url,
            },
            "pull_requests": pr_entries,
            "acceptance_criteria": json.loads(task.acceptance_criteria_json or "[]"),
            "latest_worker_summary": run.last_summary,
            "previous_review_artifact": _parse_json_object(run.review_artifact_json),
        },
        ensure_ascii=False,
    )

    if status == "completed" and conclusion == "success":
        _summarize_and_store(
            session,
            settings=settings,
            task=task,
            run=run,
            context=context,
            run_status=RUN_STATUS_AWAITING_REVIEW,
            event_key=f"workflow_run:{workflow_run.get('id')}:{status}:{conclusion}",
            checks_passed=True,
        )
        task.status = TASK_STATUS_PR_OPENED
        task.updated_at = _utc_now()
        _save(session, task)
        link_run_to_slice(session, run=run, task=task)
        notify_discord(
            f"Checks complete and ready for review: {github_repo} PR #{run.github_pr_number} -> {_worker_display_name(task)}"
            f"{_review_summary_suffix(run)}"
        )
        previous_state = _load_governor_state(run)
        _run_governor_loop(
            session,
            settings=settings,
            task=task,
            run=run,
            pr_payload={
                "number": run.github_pr_number,
                "draft": bool(previous_state.get("pr_draft")),
                "state": "open",
                "requested_reviewers": [{"login": item} for item in previous_state.get("requested_reviewers", [])],
            },
            event_key=f"governor:workflow_run:{workflow_run.get('id')}:{status}:{conclusion}",
            checks_passed=True,
        )
        return True

    if status == "completed" and conclusion in {"failure", "cancelled", "timed_out", "startup_failure"}:
        _summarize_and_store(
            session,
            settings=settings,
            task=task,
            run=run,
            context=context,
            run_status=RUN_STATUS_BLOCKED,
            event_key=f"workflow_run:{workflow_run.get('id')}:{status}:{conclusion}",
            checks_passed=False,
        )
        task.status = TASK_STATUS_BLOCKED
        task.updated_at = _utc_now()
        _save(session, task)
        link_run_to_slice(session, run=run, task=task)
        notify_discord(
            f"Checks failed / task blocked: {github_repo} PR #{run.github_pr_number} -> {_worker_display_name(task)}"
            f"{_review_summary_suffix(run)}"
        )
        previous_state = _load_governor_state(run)
        _run_governor_loop(
            session,
            settings=settings,
            task=task,
            run=run,
            pr_payload={
                "number": run.github_pr_number,
                "draft": bool(previous_state.get("pr_draft")),
                "state": "open",
                "requested_reviewers": [{"login": item} for item in previous_state.get("requested_reviewers", [])],
            },
            event_key=f"governor:workflow_run:{workflow_run.get('id')}:{status}:{conclusion}",
            checks_passed=False,
        )
        return True

    # Workflow waiting for approval — surface an explicit blocker so the chain
    # does not appear as a silent "working" stall.
    if status == "waiting" or action == "waiting":
        run.status = RUN_STATUS_BLOCKED
        run.last_summary = (
            f"Workflow awaiting approval: {name} ({html_url or 'no url'}). "
            "A repository maintainer must approve this workflow run in GitHub Actions."
        )
        run.updated_at = _utc_now()
        task.status = TASK_STATUS_BLOCKED
        task.latest_summary = run.last_summary
        task.updated_at = _utc_now()
        _save(session, run, task)
        link_run_to_slice(session, run=run, task=task)
        if task.program_id:
            prog = session.get(Program, task.program_id)
            if prog is not None:
                prog.blocker_state_json = json.dumps(
                    {
                        "reason": BLOCKER_WAITING_FOR_WORKFLOW_APPROVAL,
                        "workflow_name": name,
                        "workflow_url": html_url,
                        "pr_numbers": pr_numbers,
                    },
                    ensure_ascii=False,
                )
                prog.latest_summary = f"Workflow approval required: {name}"
                prog.updated_at = _utc_now()
                _save(session, prog)
        notify_discord(
            f"Workflow approval required: {github_repo} PR #{pr_numbers} workflow={name!r}. "
            "Approve in GitHub Actions to continue."
        )
        previous_state = _load_governor_state(run)
        _run_governor_loop(
            session,
            settings=settings,
            task=task,
            run=run,
            pr_payload={
                "number": run.github_pr_number,
                "draft": bool(previous_state.get("pr_draft")),
                "state": "open",
                "requested_reviewers": [{"login": item} for item in previous_state.get("requested_reviewers", [])],
            },
            event_key=f"governor:workflow_run:{workflow_run.get('id')}:{status}:{conclusion}:{action}",
            checks_passed=False,
        )
        return True

    run.status = RUN_STATUS_WORKING
    run.last_summary = f"Workflow update observed: {name} ({status}/{conclusion or 'n/a'})"
    run.updated_at = _utc_now()
    task.status = TASK_STATUS_WORKING
    task.latest_summary = run.last_summary
    task.updated_at = _utc_now()
    _save(session, run, task)
    link_run_to_slice(session, run=run, task=task)
    return True


def process_pull_request_review_event(
    session: Session,
    *,
    settings: Settings,
    payload: dict[str, Any],
    action: str | None,
) -> bool:
    github_repo = _repo_name(payload)
    review = payload.get("review") or {}
    pr = payload.get("pull_request") or {}
    if not github_repo or not isinstance(pr, dict):
        return False
    pr_number = pr.get("number")
    if not isinstance(pr_number, int):
        return False

    query = (
        select(AgentRun)
        .where(AgentRun.github_repo == github_repo)
        .where(AgentRun.github_pr_number == pr_number)
        .order_by(AgentRun.updated_at.desc())
        .limit(1)
    )
    run = session.exec(query).first()
    if run is None:
        return False
    task = session.get(TaskPacket, run.task_packet_id)
    if task is None:
        return False

    actor = (review.get("user") or {}) if isinstance(review, dict) else {}
    actor_login = actor.get("login") if isinstance(actor, dict) else None
    if _is_copilot_actor(settings=settings, login=actor_login, display_name=None):
        _run_governor_loop(
            session,
            settings=settings,
            task=task,
            run=run,
            pr_payload=pr,
            event_key=f"governor:pull_request_review:{pr.get('id')}:{review.get('id')}:{action}:{review.get('submitted_at')}",
            checks_passed=False,
        )
    return True


def process_pull_request_review_comment_event(
    session: Session,
    *,
    settings: Settings,
    payload: dict[str, Any],
    action: str | None,
) -> bool:
    github_repo = _repo_name(payload)
    pr = payload.get("pull_request") or {}
    comment = payload.get("comment") or {}
    if not github_repo or not isinstance(pr, dict):
        return False
    pr_number = pr.get("number")
    if not isinstance(pr_number, int):
        return False
    query = (
        select(AgentRun)
        .where(AgentRun.github_repo == github_repo)
        .where(AgentRun.github_pr_number == pr_number)
        .order_by(AgentRun.updated_at.desc())
        .limit(1)
    )
    run = session.exec(query).first()
    if run is None:
        return False
    task = session.get(TaskPacket, run.task_packet_id)
    if task is None:
        return False
    actor = (comment.get("user") or {}) if isinstance(comment, dict) else {}
    actor_login = actor.get("login") if isinstance(actor, dict) else None
    if _is_copilot_actor(settings=settings, login=actor_login, display_name=None):
        _run_governor_loop(
            session,
            settings=settings,
            task=task,
            run=run,
            pr_payload=pr,
            event_key=f"governor:pull_request_review_comment:{pr.get('id')}:{comment.get('id')}:{action}:{comment.get('updated_at')}",
            checks_passed=False,
        )
    return True
