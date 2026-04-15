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
    fetch_pull_request_patch,
    inspect_pull_request,
    list_recent_pull_requests,
    lookup_pr_linked_issue_numbers,
    list_issue_comments,
    list_issue_timeline_events,
    list_pull_request_file_details,
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
from .github_auth import has_dispatch_auth, has_governor_auth
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
    RunEvent,
    TaskPacket,
)
from .openai_planning import plan_task_packet
from .openai_review import summarize_work_update
from .openai_review import summarize_governor_update
from .openai_review import summarize_copilot_review_batch
from .openai_review import summarize_merge_audit
from .runs import record_run_event
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
LINKAGE_TAG_PREFIX = "ORCH-LINK:"
ORCH_LINKAGE_TAG_RE = re.compile(
    r"(?m)^\s*ORCH-LINK:\s*task=(?P<task_id>\d+)\s+issue=(?P<issue_number>\d+)\s+run=(?P<run_id>\d+)\s*$"
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
EXECUTION_MODE_STANDARD = "standard"
EXECUTION_MODE_HIGH_AUTONOMY_PROGRAM = "high_autonomy_program"
_NOISY_PR_ACTIONS = {"review_requested", "review_request_removed", "assigned", "edited"}
SKIP_REASON_SUPPRESSED_NOISY_EVENT = "suppressed_noisy_event_without_material_change"
SKIP_REASON_SUPPRESSED_UNCHANGED_STATE = "suppressed_unchanged_material_state"
SKIP_REASON_HEAVY_REVIEW_GATED = "heavy_review_gated_no_meaningful_transition"
DIFF_EVIDENCE_REASON = "diff_evidence_changed"
_NON_ACTIONABLE_COPILOT_REVIEW_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"copilot\s+wasn['’]?t\s+able\s+to\s+review\s+any\s+files", re.IGNORECASE),
    re.compile(r"unable\s+to\s+review\s+(any\s+)?files", re.IGNORECASE),
    re.compile(r"no\s+files?\s+(were\s+)?changed", re.IGNORECASE),
    re.compile(r"empty\s+diff", re.IGNORECASE),
    re.compile(r"nothing\s+to\s+review", re.IGNORECASE),
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


def _record_openai_telemetry(
    session: Session,
    *,
    task: TaskPacket | None,
    run: AgentRun | None,
    stage: str,
    action: str,
    outcome: str,
    execution_mode: str | None = None,
    model: str | None = None,
    reasoning_effort: str | None = None,
    event_key: str | None = None,
    head_sha: str | None = None,
    slice_contract_hash: str | None = None,
    prompt_fingerprint: str | None = None,
    usage: dict[str, Any] | None = None,
    skip_reason: str | None = None,
    budget_counters: dict[str, Any] | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    payload: dict[str, Any] = {
        "stage": stage,
        "action": action,
        "outcome": outcome,
        "model": model,
        "reasoning_effort": reasoning_effort,
        "task_id": task.id if task else None,
        "run_id": run.id if run else None,
        "issue_number": task.github_issue_number if task else (run.github_issue_number if run else None),
        "pr_number": run.github_pr_number if run else None,
        "execution_mode": execution_mode,
        "event_key": event_key,
        "head_sha": head_sha,
        "slice_contract_hash": slice_contract_hash,
        "prompt_fingerprint": prompt_fingerprint,
        "usage": usage or {},
        "skip_reason": skip_reason,
        "budget_counters": budget_counters or {},
    }
    if extra:
        payload.update(extra)
    record_run_event(
        session,
        source="openai_control_plane",
        external_id=None,
        event_type="openai_decision",
        action=action,
        status=outcome,
        summary=f"OpenAI {stage} {outcome}",
        payload_json=json.dumps(payload, ensure_ascii=False, sort_keys=True),
    )


def summarize_openai_telemetry(
    session: Session,
    *,
    task_id: int | None = None,
    run_id: int | None = None,
    limit: int = 500,
) -> dict[str, Any]:
    query = (
        select(RunEvent)
        .where(RunEvent.source == "openai_control_plane")
        .order_by(RunEvent.created_at.desc())
        .limit(limit)
    )
    events = list(session.exec(query).all())
    filtered: list[dict[str, Any]] = []
    for event in events:
        payload = _parse_json_object(event.payload_json) or {}
        if task_id is not None and int(payload.get("task_id") or 0) != task_id:
            continue
        if run_id is not None and int(payload.get("run_id") or 0) != run_id:
            continue
        filtered.append(payload)

    by_stage: dict[str, int] = {}
    by_outcome: dict[str, int] = {}
    by_model: dict[str, int] = {}
    top_token_consumers: list[dict[str, Any]] = []
    for payload in filtered:
        stage = str(payload.get("stage") or "unknown")
        outcome = str(payload.get("outcome") or "unknown")
        model = str(payload.get("model") or "unknown")
        by_stage[stage] = by_stage.get(stage, 0) + 1
        by_outcome[outcome] = by_outcome.get(outcome, 0) + 1
        by_model[model] = by_model.get(model, 0) + 1
        usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
        top_token_consumers.append(
            {
                "stage": stage,
                "model": model,
                "task_id": payload.get("task_id"),
                "run_id": payload.get("run_id"),
                "total_tokens": int(usage.get("total_tokens") or 0),
                "input_tokens": int(usage.get("input_tokens") or 0),
                "output_tokens": int(usage.get("output_tokens") or 0),
            }
        )
    top_token_consumers.sort(key=lambda item: item["total_tokens"], reverse=True)
    return {
        "count": len(filtered),
        "by_stage": by_stage,
        "by_outcome": by_outcome,
        "by_model": by_model,
        "suppressed_count": by_outcome.get("suppressed", 0),
        "budget_blocked_count": by_outcome.get("budget_blocked", 0),
        "dominant_token_consumers": top_token_consumers[:10],
    }


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


def mark_pr_association_pending(
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
    if run.status in {RUN_STATUS_COMPLETED, RUN_STATUS_FAILED, RUN_STATUS_BLOCKED}:
        return
    pending_summary = f"PR association pending (retryable): {summary}"
    run.last_summary = pending_summary
    run.updated_at = _utc_now()
    task.latest_summary = pending_summary
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


def _parse_github_datetime(raw: Any) -> datetime | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    candidate = raw.strip()
    if candidate.endswith("Z"):
        candidate = candidate[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return None
    return _as_utc(parsed)


def _parse_json_list(raw_json: str | None) -> list[Any]:
    if not raw_json:
        return []
    try:
        parsed = json.loads(raw_json)
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []


def _build_run_linkage_tag(*, task: TaskPacket, run: AgentRun) -> str:
    task_id = task.id if task.id is not None else 0
    run_id = run.id if run.id is not None else 0
    return (
        f"{LINKAGE_TAG_PREFIX} "
        f"task={task_id} issue={task.github_issue_number} run={run_id}"
    )


def parse_orch_linkage_tag(text: str | None) -> dict[str, int] | None:
    if not isinstance(text, str) or not text.strip():
        return None
    match = ORCH_LINKAGE_TAG_RE.search(text)
    if match is None:
        return None
    try:
        return {
            "task_id": int(match.group("task_id")),
            "issue_number": int(match.group("issue_number")),
            "run_id": int(match.group("run_id")),
        }
    except (TypeError, ValueError):
        return None


def _discover_post_dispatch_pr_candidate(
    *,
    settings: Settings,
    task: TaskPacket,
    run: AgentRun,
    dispatch_observed_at: datetime,
) -> tuple[dict[str, Any] | None, str, list[dict[str, Any]]]:
    candidates, msg = list_recent_pull_requests(settings=settings, repo=task.github_repo, limit=40)
    if not candidates:
        return None, "no_recent_pr_candidates", []
    linkage_tag = str(run.linkage_tag or "").strip()
    issue_pattern = re.compile(rf"(?<!\d)#?{task.github_issue_number}(?!\d)")
    branch_issue_pattern = re.compile(rf"(?<!\d){task.github_issue_number}(?!\d)")
    scored: list[dict[str, Any]] = []
    for pr in candidates:
        number = pr.get("number")
        if not isinstance(number, int):
            continue
        title = str(pr.get("title") or "")
        body = str(pr.get("body") or "")
        combined = f"{title}\n{body}"
        user = pr.get("user") if isinstance(pr.get("user"), dict) else {}
        login = user.get("login") if isinstance(user, dict) else None
        created_at = _parse_github_datetime(pr.get("created_at"))
        head_ref = ""
        head = pr.get("head")
        if isinstance(head, dict):
            head_ref = str(head.get("ref") or "")
        score = 0
        reasons: list[str] = []
        exact_linkage_tag_present = bool(linkage_tag and linkage_tag in combined)
        issue_link_present = bool(issue_pattern.search(combined))
        branch_issue_link_present = bool(head_ref and branch_issue_pattern.search(head_ref))
        copilot_actor = _is_copilot_actor(
            settings=settings,
            login=login if isinstance(login, str) else None,
            display_name=None,
        )
        created_after_dispatch = bool(
            created_at is not None and created_at >= dispatch_observed_at - timedelta(minutes=1)
        )
        heuristic_authoritative = copilot_actor and created_after_dispatch and (
            issue_link_present or branch_issue_link_present
        )
        authoritative = exact_linkage_tag_present or heuristic_authoritative

        if exact_linkage_tag_present:
            score += 100
            reasons.append("exact_linkage_tag_match")

        if issue_link_present:
            score += 6
            reasons.append("issue_link_present")
        if branch_issue_link_present:
            score += 2
            reasons.append("branch_issue_link_present")
        if copilot_actor:
            score += 3
            reasons.append("copilot_actor")
        if created_after_dispatch:
            score += 2
            reasons.append("created_after_dispatch")
        if head_ref and "copilot" in head_ref.lower():
            score += 1
            reasons.append("branch_pattern_matched")
        scored.append(
            {
                "pr": pr,
                "score": score,
                "reasons": reasons,
                "created_at": created_at.isoformat() if created_at else None,
                "authoritative": authoritative,
                "heuristic_authoritative": heuristic_authoritative,
                "exact_linkage_tag_present": exact_linkage_tag_present,
            }
        )
    if not scored:
        return None, "no_recent_pr_candidates", []
    if linkage_tag:
        exact_tag_candidates = [entry for entry in scored if bool(entry.get("exact_linkage_tag_present"))]
        if len(exact_tag_candidates) == 1:
            return exact_tag_candidates[0], "linked_exact_linkage_tag", scored[:8]
        if len(exact_tag_candidates) > 1:
            return None, "candidate_prs_ambiguous_exact_linkage_tag", scored[:8]
    scored.sort(
        key=lambda entry: (
            int(entry["score"]),
            int(entry["pr"].get("number") or 0),
        ),
        reverse=True,
    )
    authoritative_candidates = [entry for entry in scored if bool(entry.get("heuristic_authoritative"))]
    if not authoritative_candidates:
        if linkage_tag:
            return None, "linkage_tag_missing_in_candidate_prs", scored[:8]
        return None, "authoritative_linkage_not_found", scored[:8]
    top_score = int(authoritative_candidates[0]["score"])
    top = [entry for entry in authoritative_candidates if int(entry["score"]) == top_score]
    if len(top) > 1:
        return None, "candidate_prs_ambiguous", scored[:8]
    return top[0], "linked_heuristic", scored[:8]


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


def _looks_docs_only_path(path: str) -> bool:
    normalized = str(path or "").strip().lower().lstrip("/")
    if not normalized:
        return False
    docs_prefixes = ("docs/", ".github/", "mkdocs/", "changelog/", "guides/")
    docs_suffixes = (
        ".md",
        ".mdx",
        ".rst",
        ".txt",
        ".adoc",
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".svg",
        ".webp",
    )
    if normalized in {"readme", "readme.md", "license", "license.md", "contributing.md"}:
        return True
    return normalized.startswith(docs_prefixes) or normalized.endswith(docs_suffixes)


def _is_docs_only_change(changed_files: list[str]) -> bool:
    if not changed_files:
        return False
    return all(_looks_docs_only_path(path) for path in changed_files)


def _truncate_patch(patch: str, *, max_chars: int = 2000) -> tuple[str, bool]:
    if len(patch) <= max_chars:
        return patch, False
    return patch[:max_chars], True


def _derive_file_details_from_patch(patch_text: str, *, max_files: int = 80) -> list[dict[str, Any]]:
    details: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for raw_line in patch_text.splitlines():
        if raw_line.startswith("diff --git "):
            if current and str(current.get("filename") or "").strip():
                details.append(current)
                if len(details) >= max_files:
                    break
            current = {
                "filename": "",
                "status": "modified",
                "additions": 0,
                "deletions": 0,
                "patch": "",
            }
            continue
        if current is None:
            continue
        if raw_line.startswith("new file mode "):
            current["status"] = "added"
            continue
        if raw_line.startswith("deleted file mode "):
            current["status"] = "removed"
            continue
        if raw_line.startswith("rename from "):
            current["status"] = "renamed"
            continue
        if raw_line.startswith("+++ b/"):
            current["filename"] = raw_line[6:].strip()
            continue
        if raw_line.startswith("@@") or raw_line.startswith("+") or raw_line.startswith("-") or raw_line.startswith(" "):
            current["patch"] = f"{current['patch']}{raw_line}\n"
            if raw_line.startswith("+") and not raw_line.startswith("+++"):
                current["additions"] = int(current.get("additions") or 0) + 1
            elif raw_line.startswith("-") and not raw_line.startswith("---"):
                current["deletions"] = int(current.get("deletions") or 0) + 1
    if current and str(current.get("filename") or "").strip() and len(details) < max_files:
        details.append(current)
    return details


def _workflow_run_linked_head_sha(
    workflow_run: dict[str, Any],
    *,
    preferred_pr_number: int | None = None,
) -> str:
    pr_entries = workflow_run.get("pull_requests") or []
    if isinstance(pr_entries, list):
        if preferred_pr_number is not None:
            for pr_entry in pr_entries:
                if not isinstance(pr_entry, dict):
                    continue
                if pr_entry.get("number") != preferred_pr_number:
                    continue
                head = pr_entry.get("head") if isinstance(pr_entry.get("head"), dict) else {}
                head_sha = str(head.get("sha") or "").strip()
                if head_sha:
                    return head_sha
        for pr_entry in pr_entries:
            if not isinstance(pr_entry, dict):
                continue
            head = pr_entry.get("head") if isinstance(pr_entry.get("head"), dict) else {}
            head_sha = str(head.get("sha") or "").strip()
            if head_sha:
                return head_sha
    return str(workflow_run.get("head_sha") or "").strip()


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
    state.setdefault("final_audit_artifact", {})
    state.setdefault("final_audit_decision", "")
    state.setdefault("final_audit_confidence", 0.0)
    state.setdefault("final_audit_last_error", "")
    state.setdefault("final_audit_summary", [])
    state.setdefault("last_checks_passed", False)
    state.setdefault("last_check_conclusion", "")
    state.setdefault("last_successful_checks_head_sha", "")
    state.setdefault("last_successful_checks_at", "")
    state.setdefault("last_observed_pr_head_sha", "")
    state.setdefault("effective_checks_passed", False)
    state.setdefault("execution_mode", EXECUTION_MODE_STANDARD)
    state.setdefault("active_slice_acceptance_criteria", [])
    state.setdefault("active_slice_scope", [])
    state.setdefault("active_slice_non_goals", [])
    state.setdefault("active_slice_validation_guidance", [])
    state.setdefault("active_slice_contract_hash", "")
    state.setdefault("active_slice_contract_version", 0)
    state.setdefault("material_state_hash", "")
    state.setdefault("material_state_pr_head_sha", "")
    state.setdefault("last_model_reuse_reason", "")
    state.setdefault("last_reused_governor_decision", "")
    state.setdefault("last_deterministic_skip_reason", "")
    state.setdefault("last_heavy_block_reason", "")
    state.setdefault("heavy_model_calls_total", 0)
    state.setdefault("heavy_model_calls_by_head_sha", {})
    state.setdefault("heavy_model_calls_by_slice", {})
    state.setdefault("blocked_state_repeat_count", 0)
    state.setdefault("last_blocked_state_hash", "")
    state.setdefault("budget_blocked_repeat_count", 0)
    state.setdefault("last_budget_blocked_state_hash", "")
    state.setdefault("final_audit_head_sha", "")
    state.setdefault("effective_checks_passed_at_final_audit", False)
    state.setdefault("final_audit_cache_key", "")
    state.setdefault("ready_for_review_attempted", False)
    state.setdefault("ready_for_review_attempt_count", 0)
    state.setdefault("ready_for_review_retry_count", 0)
    state.setdefault("ready_for_review_max_retries", 2)
    state.setdefault("ready_for_review_outcome", "")
    state.setdefault("ready_for_review_last_error", "")
    state.setdefault("ready_for_review_retry_scheduled", False)
    state.setdefault("ready_for_review_escalated", False)
    state.setdefault("checkpoints", {})
    return state


def _current_execution_mode(*, task: TaskPacket, run: AgentRun, state: dict[str, Any]) -> str:
    if state.get("execution_mode") == EXECUTION_MODE_HIGH_AUTONOMY_PROGRAM:
        return EXECUTION_MODE_HIGH_AUTONOMY_PROGRAM
    dispatch_payload = _parse_json_object(run.dispatch_payload_json) or {}
    mode = str(dispatch_payload.get("execution_mode") or "").strip()
    if mode:
        return mode
    if task.program_id and str(task.recommended_scope_class or "").strip().lower() == "broad":
        return EXECUTION_MODE_HIGH_AUTONOMY_PROGRAM
    return EXECUTION_MODE_STANDARD


def _active_slice_contract(task: TaskPacket, state: dict[str, Any]) -> dict[str, Any]:
    worker_brief = _parse_json_object(task.worker_brief_json) or {}
    acceptance = state.get("active_slice_acceptance_criteria")
    if not isinstance(acceptance, list) or not acceptance:
        acceptance = worker_brief.get("acceptance_criteria")
    if not isinstance(acceptance, list) or not acceptance:
        acceptance = json.loads(task.acceptance_criteria_json or "[]")
    scope = state.get("active_slice_scope")
    if not isinstance(scope, list) or not scope:
        scope = worker_brief.get("concise_scope") if isinstance(worker_brief.get("concise_scope"), list) else []
    non_goals = state.get("active_slice_non_goals")
    if not isinstance(non_goals, list) or not non_goals:
        non_goals = worker_brief.get("non_goals") if isinstance(worker_brief.get("non_goals"), list) else []
    validation = state.get("active_slice_validation_guidance")
    if not isinstance(validation, list) or not validation:
        validation = worker_brief.get("validation_commands") if isinstance(worker_brief.get("validation_commands"), list) else []
    payload = {
        "acceptance_criteria": [str(item).strip() for item in acceptance if str(item).strip()],
        "scope": [str(item).strip() for item in scope if str(item).strip()],
        "non_goals": [str(item).strip() for item in non_goals if str(item).strip()],
        "validation_guidance": [str(item).strip() for item in validation if str(item).strip()],
    }
    payload["contract_hash"] = hashlib.sha1(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    return payload


def _material_state_hash(*, payload: dict[str, Any]) -> str:
    return hashlib.sha1(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def _ordered_unique_reasons(reasons: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for reason in reasons:
        if reason in seen:
            continue
        seen.add(reason)
        deduped.append(reason)
    return deduped


def _material_transition_reasons(
    *,
    state: dict[str, Any],
    pr_head_sha: str,
    effective_checks_passed: bool,
    active_contract_hash: str,
    changed_files_hash: str,
    unresolved_findings_hash: str,
    mergeable_state: str,
    file_details_count: int,
    patch_fallback_used: bool,
) -> list[str]:
    reasons: list[str] = []
    if (pr_head_sha or "") != str(state.get("material_state_pr_head_sha") or ""):
        reasons.append("head_sha_changed")
    if bool(effective_checks_passed) != bool(state.get("effective_checks_passed_at_final_audit")):
        reasons.append("effective_checks_changed")
    if active_contract_hash != str(state.get("active_slice_contract_hash") or ""):
        reasons.append("slice_contract_changed")
    diff_evidence_changed = False
    if changed_files_hash and changed_files_hash != str(state.get("final_audit_changed_files_hash") or ""):
        diff_evidence_changed = True
    prior_findings_hash = str(state.get("final_audit_unresolved_findings_hash") or "")
    if unresolved_findings_hash and unresolved_findings_hash != prior_findings_hash:
        reasons.append("review_evidence_changed")
    if mergeable_state and mergeable_state != str(state.get("pr_mergeable_state") or ""):
        reasons.append("mergeability_changed")
    prior_file_details_count = int(state.get("final_audit_file_details_count") or 0)
    if int(file_details_count or 0) != prior_file_details_count:
        diff_evidence_changed = True
    if bool(state.get("final_audit_patch_fallback_used")) != bool(patch_fallback_used):
        diff_evidence_changed = True
    if bool(state.get("final_audit_evidence_missing")) and int(file_details_count or 0) > 0:
        diff_evidence_changed = True
    if diff_evidence_changed:
        reasons.append(DIFF_EVIDENCE_REASON)
    if int(state.get("blocked_state_repeat_count") or 0) > 0:
        reasons.append("blocked_state_repeat_active")
    return _ordered_unique_reasons(reasons)


def _is_noisy_pr_event(event_key: str) -> bool:
    if "governor:pull_request:" not in event_key:
        return False
    parts = event_key.split(":")
    if len(parts) < 4:
        return False
    return parts[3] in _NOISY_PR_ACTIONS


def _high_autonomy_noisy_skip_candidate(
    *,
    execution_mode: str,
    event_key: str,
    material_unchanged: bool,
    coarse_state_unchanged: bool,
    has_prior_decision: bool,
) -> bool:
    return bool(
        execution_mode == EXECUTION_MODE_HIGH_AUTONOMY_PROGRAM
        and _is_noisy_pr_event(event_key)
        and (material_unchanged or coarse_state_unchanged)
        and has_prior_decision
    )


def _legacy_unchanged_material_skip_candidate(
    *,
    execution_mode: str,
    event_key: str,
    material_unchanged: bool,
    has_prior_decision: bool,
) -> bool:
    return bool(
        execution_mode == EXECUTION_MODE_HIGH_AUTONOMY_PROGRAM
        and _is_noisy_pr_event(event_key)
        and material_unchanged
        and has_prior_decision
    )


def _revision_cycle_limit(*, settings: Settings, execution_mode: str) -> int:
    if execution_mode == EXECUTION_MODE_HIGH_AUTONOMY_PROGRAM:
        return max(1, int(getattr(settings, "governor_high_autonomy_max_revision_cycles", 1) or 1))
    return max(1, int(getattr(settings, "governor_max_revision_cycles", 2) or 2))


def _heavy_budget_counters(
    *,
    state: dict[str, Any],
    pr_head_sha: str | None = None,
    slice_contract_hash: str | None = None,
    include_repeat_counters: bool = False,
) -> dict[str, int]:
    head_key = pr_head_sha or "<none>"
    slice_key = slice_contract_hash or "<none>"
    counters = {
        "heavy_model_calls_total": int(state.get("heavy_model_calls_total") or 0),
        "heavy_model_calls_for_head_sha": int((state.get("heavy_model_calls_by_head_sha") or {}).get(head_key, 0)),
        "heavy_model_calls_for_slice": int((state.get("heavy_model_calls_by_slice") or {}).get(slice_key, 0)),
    }
    if include_repeat_counters:
        counters["blocked_state_repeat_count"] = int(state.get("blocked_state_repeat_count") or 0)
        counters["budget_blocked_repeat_count"] = int(state.get("budget_blocked_repeat_count") or 0)
    return counters


def _heavy_budget_available(*, settings: Settings, state: dict[str, Any], pr_head_sha: str, slice_contract_hash: str) -> tuple[bool, str]:
    total_limit = max(1, int(getattr(settings, "governor_heavy_max_calls_per_pr_total", 6) or 6))
    head_limit = max(1, int(getattr(settings, "governor_heavy_max_calls_per_head_sha", 2) or 2))
    slice_limit = max(1, int(getattr(settings, "governor_heavy_max_calls_per_slice", 4) or 4))
    total = int(state.get("heavy_model_calls_total") or 0)
    if total >= total_limit:
        return False, "heavy_model_budget_exhausted:pr_total"
    by_head = state.get("heavy_model_calls_by_head_sha")
    if not isinstance(by_head, dict):
        by_head = {}
    if int(by_head.get(pr_head_sha or "<none>") or 0) >= head_limit:
        return False, "heavy_model_budget_exhausted:head_sha"
    by_slice = state.get("heavy_model_calls_by_slice")
    if not isinstance(by_slice, dict):
        by_slice = {}
    if int(by_slice.get(slice_contract_hash or "<none>") or 0) >= slice_limit:
        return False, "heavy_model_budget_exhausted:slice"
    return True, ""


def _record_heavy_model_call(*, state: dict[str, Any], pr_head_sha: str, slice_contract_hash: str) -> None:
    state["heavy_model_calls_total"] = int(state.get("heavy_model_calls_total") or 0) + 1
    by_head = state.get("heavy_model_calls_by_head_sha")
    if not isinstance(by_head, dict):
        by_head = {}
    head_key = pr_head_sha or "<none>"
    by_head[head_key] = int(by_head.get(head_key) or 0) + 1
    state["heavy_model_calls_by_head_sha"] = by_head
    by_slice = state.get("heavy_model_calls_by_slice")
    if not isinstance(by_slice, dict):
        by_slice = {}
    slice_key = slice_contract_hash or "<none>"
    by_slice[slice_key] = int(by_slice.get(slice_key) or 0) + 1
    state["heavy_model_calls_by_slice"] = by_slice


def _save_governor_state(run: AgentRun, state: dict[str, Any]) -> None:
    run.governor_state_json = json.dumps(state, ensure_ascii=False)


_governor_logger = logging.getLogger("orchestrator.governor")


def _workflow_debug_enabled(settings: Settings) -> bool:
    return bool(getattr(settings, "orchestrator_debug_workflow", False))


def _governor_fingerprint(state: dict[str, Any] | None) -> str:
    payload = state or {}
    compact = {
        "revision_cycle_count": payload.get("revision_cycle_count"),
        "waiting_for_revision_push": payload.get("waiting_for_revision_push"),
        "guarded_paths_touched": payload.get("guarded_paths_touched"),
        "last_event_key": payload.get("last_event_key"),
        "checkpoints": payload.get("checkpoints"),
    }
    return hashlib.sha1(json.dumps(compact, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:12]


def _log_workflow_checkpoint(
    settings: Settings,
    *,
    event: str,
    task: TaskPacket | None,
    run: AgentRun | None = None,
    success: bool,
    summary: str,
    auth_lane: str = "n/a",
    api_type: str = "n/a",
    postcondition: str | None = None,
    skip_reason: str | None = None,
    state: dict[str, Any] | None = None,
    pr_node_id: str | None = None,
    retry_count: int | None = None,
    result_class: str | None = None,
) -> None:
    if not _workflow_debug_enabled(settings):
        return
    _governor_logger.info(
        "workflow_event=%s task_id=%s issue_number=%s pr_number=%s pr_node_id=%s repo=%s auth_lane=%s api_type=%s success=%s result_class=%s retry_count=%s checkpoint=%s governor_fingerprint=%s skip_reason=%s postcondition=%s summary=%s",
        event,
        (task.id if task and task.id is not None else (run.task_packet_id if run else "n/a")),
        (task.github_issue_number if task else (run.github_issue_number if run else "n/a")),
        (run.github_pr_number if run else "n/a"),
        pr_node_id or "n/a",
        (task.github_repo if task else (run.github_repo if run else "n/a")),
        auth_lane,
        api_type,
        success,
        result_class or "n/a",
        retry_count if retry_count is not None else "n/a",
        event,
        _governor_fingerprint(state),
        skip_reason or "n/a",
        postcondition or "n/a",
        summary,
    )


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


def _ready_for_review_failure_outcome(message: str) -> tuple[str, bool]:
    text = str(message or "").lower()
    if "dispatch user-token auth not configured" in text or "auth failure" in text:
        return "ready_for_review_failed_auth", False
    if "postcondition failed" in text:
        return "ready_for_review_failed_postcondition", True
    if " 403 " in f" {text} " or "forbidden" in text or "permission" in text:
        return "ready_for_review_failed_http", False
    return "ready_for_review_failed_http", True


def _has_substantive_file_evidence(*, file_details: list[dict[str, Any]], changed_files: list[str]) -> bool:
    if any(str(path or "").strip() for path in changed_files):
        for item in file_details:
            if not isinstance(item, dict):
                continue
            patch = str(item.get("patch") or "").strip()
            additions = int(item.get("additions") or 0)
            deletions = int(item.get("deletions") or 0)
            if patch or additions > 0 or deletions > 0:
                return True
    return False


def safe_draft_can_be_promoted(
    *,
    pr_draft: bool,
    checks_passed: bool,
    effective_checks_passed: bool,
    guarded_paths_touched: bool,
    unresolved_findings: list[str],
    waiting_for_revision_push: bool,
    changed_files: list[str],
    file_details: list[dict[str, Any]],
    event_has_push_signal: bool,
    commits: int | None,
    prior_head_sha: str,
    current_head_sha: str,
) -> tuple[bool, list[str]]:
    """Deterministic predicate for safe draft->ready transitions."""
    reasons: list[str] = []
    if not pr_draft:
        reasons.append("already_non_draft")
        return False, reasons
    if guarded_paths_touched:
        reasons.append("guarded_paths_touched")
    if unresolved_findings:
        reasons.append("unresolved_findings_present")
    if waiting_for_revision_push:
        reasons.append("waiting_for_revision_push")

    substantive_evidence = _has_substantive_file_evidence(file_details=file_details, changed_files=changed_files)
    if not substantive_evidence:
        reasons.append("no_substantive_diff_evidence")

    worker_update_signal = bool(
        event_has_push_signal
        or (isinstance(commits, int) and commits > 1)
        or (prior_head_sha and current_head_sha and prior_head_sha != current_head_sha)
    )
    validation_signal = bool(checks_passed or effective_checks_passed)
    if not (worker_update_signal or validation_signal):
        reasons.append("no_worker_update_or_validation_signal")

    return (len(reasons) == 0), reasons


def _is_non_actionable_copilot_review_body(body: str) -> bool:
    compact = " ".join(str(body or "").split())
    if not compact:
        return True
    return any(pattern.search(compact) for pattern in _NON_ACTIONABLE_COPILOT_REVIEW_PATTERNS)


def _copilot_findings_from_reviews(
    *,
    settings: Settings,
    reviews: list[dict[str, Any]],
    comments: list[dict[str, Any]],
) -> tuple[bool, list[str], int]:
    findings: list[str] = []
    observed = False
    ignored_non_actionable = 0
    for review in reviews:
        user = review.get("user") if isinstance(review, dict) else None
        login = user.get("login") if isinstance(user, dict) else None
        if not _is_copilot_actor(settings=settings, login=login, display_name=None):
            continue
        observed = True
        body = str(review.get("body") or "").strip()
        state = str(review.get("state") or "").strip().upper()
        if body and state in {"COMMENTED", "CHANGES_REQUESTED"}:
            if _is_non_actionable_copilot_review_body(body):
                ignored_non_actionable += 1
                _governor_logger.info(
                    "Ignoring non-actionable Copilot review body for unresolved findings: %s",
                    " ".join(body.split())[:160],
                )
                continue
            findings.append(body)
    for comment in comments:
        user = comment.get("user") if isinstance(comment, dict) else None
        login = user.get("login") if isinstance(user, dict) else None
        if not _is_copilot_actor(settings=settings, login=login, display_name=None):
            continue
        observed = True
        body = str(comment.get("body") or "").strip()
        if body:
            if _is_non_actionable_copilot_review_body(body):
                ignored_non_actionable += 1
                _governor_logger.info(
                    "Ignoring non-actionable Copilot review comment for unresolved findings: %s",
                    " ".join(body.split())[:160],
                )
                continue
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
    return observed, deduped[:20], ignored_non_actionable


def _handle_linked_draft_ready_for_review(
    session: Session,
    *,
    settings: Settings,
    task: TaskPacket,
    run: AgentRun,
    state: dict[str, Any],
    pr_payload: dict[str, Any],
    event_key: str,
    checks_passed: bool,
    effective_checks_passed: bool,
    guarded_paths_touched: bool,
    unresolved_findings: list[str],
    waiting_for_revision_push: bool,
    changed_files: list[str],
    file_details: list[dict[str, Any]],
    event_has_push_signal: bool,
    pr_head_sha: str,
) -> tuple[bool, bool]:
    """Force ready-for-review handoff for linked draft PRs.

    Returns (handled_terminal, promoted_to_non_draft).
    """
    pr_number = run.github_pr_number
    if not isinstance(pr_number, int):
        state["ready_for_review_outcome"] = "ready_for_review_skipped_missing_pr_linkage"
        state["ready_for_review_retry_scheduled"] = False
        state["ready_for_review_escalated"] = False
        _log_workflow_checkpoint(
            settings,
            event="ready_for_review_skipped_missing_pr_linkage",
            task=task,
            run=run,
            success=False,
            summary="Linked draft handoff skipped because PR linkage is missing.",
            result_class="skipped_missing_pr_linkage",
            state=state,
        )
        return True, False

    pr_draft = bool(pr_payload.get("draft"))
    pr_node_id = pr_payload.get("node_id") if isinstance(pr_payload.get("node_id"), str) else None
    if not pr_draft:
        state["ready_for_review_outcome"] = "ready_for_review_skipped_non_draft"
        state["ready_for_review_retry_scheduled"] = False
        state["ready_for_review_escalated"] = False
        _log_workflow_checkpoint(
            settings,
            event="ready_for_review_skipped_non_draft",
            task=task,
            run=run,
            success=True,
            summary="Ready-for-review handoff skipped because PR is already non-draft.",
            postcondition="isDraft=False",
            result_class="skipped_non_draft",
            pr_node_id=pr_node_id,
            state=state,
        )
        return False, True

    initial_head_sha = str(state.get("initial_pr_head_sha") or "")
    commits_value = pr_payload.get("commits") if isinstance(pr_payload.get("commits"), int) else None
    reviewable, readiness_reasons = safe_draft_can_be_promoted(
        pr_draft=pr_draft,
        checks_passed=checks_passed,
        effective_checks_passed=effective_checks_passed,
        guarded_paths_touched=guarded_paths_touched,
        unresolved_findings=unresolved_findings,
        waiting_for_revision_push=waiting_for_revision_push,
        changed_files=changed_files,
        file_details=file_details,
        event_has_push_signal=event_has_push_signal,
        commits=commits_value,
        prior_head_sha=initial_head_sha,
        current_head_sha=pr_head_sha,
    )
    if not reviewable:
        state["ready_for_review_outcome"] = "pr_not_ready_for_review_yet"
        state["ready_for_review_retry_scheduled"] = False
        state["ready_for_review_escalated"] = False
        state["ready_for_review_skip_reason"] = ",".join(readiness_reasons)
        _set_checkpoint(
            state,
            name="pr_ready_verified",
            success=False,
            summary="Draft PR remains pre-review until substantive evidence exists.",
        )
        _log_workflow_checkpoint(
            settings,
            event="ready_for_review_deferred",
            task=task,
            run=run,
            success=True,
            summary=(
                "Draft PR kept in pre-review hold; readiness predicate not yet satisfied "
                f"(reasons={readiness_reasons})."
            ),
            skip_reason="pr_not_ready_for_review_yet",
            result_class="pr_not_ready_for_review_yet",
            pr_node_id=pr_node_id,
            state=state,
        )
        return False, False

    state["ready_for_review_attempted"] = True
    state["ready_for_review_attempt_count"] = int(state.get("ready_for_review_attempt_count") or 0) + 1
    _log_workflow_checkpoint(
        settings,
        event="linked_draft_pr_detected",
        task=task,
        run=run,
        success=True,
        summary="Linked draft PR detected; forcing ready-for-review handoff.",
        auth_lane="dispatch_user_token",
        api_type="GraphQL",
        postcondition="isDraft=True",
        result_class="linked_draft",
        pr_node_id=pr_node_id,
        retry_count=int(state.get("ready_for_review_retry_count") or 0),
        state=state,
    )
    _log_workflow_checkpoint(
        settings,
        event="ready_for_review_attempted",
        task=task,
        run=run,
        success=True,
        summary="Attempting ready-for-review mutation for linked draft PR.",
        auth_lane="dispatch_user_token",
        api_type="GraphQL",
        pr_node_id=pr_node_id,
        retry_count=int(state.get("ready_for_review_retry_count") or 0),
        state=state,
    )
    success, msg = mark_pr_ready_for_review(settings=settings, repo=task.github_repo, pr_number=pr_number)
    state["last_event_key"] = event_key
    state["ready_for_review_last_error"] = "" if success else str(msg)

    if success:
        state["ready_for_review_outcome"] = "ready_for_review_succeeded"
        state["ready_for_review_retry_scheduled"] = False
        state["ready_for_review_escalated"] = False
        _set_checkpoint(
            state,
            name="pr_ready_verified",
            success=True,
            summary="Draft->ready transition completed and verified (isDraft=False).",
        )
        _log_workflow_checkpoint(
            settings,
            event="ready_for_review_postcondition_observed",
            task=task,
            run=run,
            success=True,
            summary="Ready-for-review postcondition observed after mutation.",
            postcondition="isDraft=False",
            auth_lane="dispatch_user_token",
            api_type="GraphQL",
            pr_node_id=pr_node_id,
            result_class="postcondition_verified",
            state=state,
        )
        _log_workflow_checkpoint(
            settings,
            event="ready_for_review_verified",
            task=task,
            run=run,
            success=True,
            summary=msg,
            auth_lane="dispatch_user_token",
            api_type="GraphQL",
            postcondition="isDraft=False",
            pr_node_id=pr_node_id,
            result_class="ready_for_review_succeeded",
            state=state,
        )
        return False, True

    outcome, transient = _ready_for_review_failure_outcome(msg)
    state["ready_for_review_outcome"] = outcome
    _set_checkpoint(
        state,
        name="pr_ready_verified",
        success=False,
        summary=str(msg),
    )
    _log_workflow_checkpoint(
        settings,
        event="ready_for_review_attempt_failed",
        task=task,
        run=run,
        success=False,
        summary=str(msg),
        auth_lane="dispatch_user_token",
        api_type="GraphQL",
        pr_node_id=pr_node_id,
        result_class=outcome,
        retry_count=int(state.get("ready_for_review_retry_count") or 0),
        state=state,
    )

    max_retries = max(1, int(state.get("ready_for_review_max_retries") or 2))
    retry_count = int(state.get("ready_for_review_retry_count") or 0)
    if transient and retry_count < max_retries:
        retry_count += 1
        state["ready_for_review_retry_count"] = retry_count
        state["ready_for_review_retry_scheduled"] = True
        state["ready_for_review_escalated"] = False
        state["ready_for_review_outcome"] = "ready_for_review_retry_scheduled"
        _log_workflow_checkpoint(
            settings,
            event="ready_for_review_retry",
            task=task,
            run=run,
            success=False,
            summary=f"Ready-for-review failed; scheduled bounded retry {retry_count}/{max_retries}: {msg}",
            auth_lane="dispatch_user_token",
            api_type="GraphQL",
            pr_node_id=pr_node_id,
            result_class=outcome,
            retry_count=retry_count,
            state=state,
        )
        return True, False

    state["ready_for_review_retry_scheduled"] = False
    state["ready_for_review_escalated"] = True
    state["ready_for_review_outcome"] = "ready_for_review_escalated"
    _log_workflow_checkpoint(
        settings,
        event="ready_for_review_escalated",
        task=task,
        run=run,
        success=False,
        summary=f"Ready-for-review escalation after bounded retries exhausted or non-transient failure: {msg}",
        auth_lane="dispatch_user_token",
        api_type="GraphQL",
        pr_node_id=pr_node_id,
        result_class=outcome,
        retry_count=int(state.get("ready_for_review_retry_count") or 0),
        state=state,
    )
    if task.program_id:
        program = session.get(Program, task.program_id)
        if program is not None:
            permission_failure = "403" in str(msg) or "forbidden" in str(msg).lower() or "permission" in str(msg).lower()
            program.status = "blocked"
            program.blocker_state_json = json.dumps(
                {
                    "reason": BLOCKER_WAITING_FOR_PERMISSIONS if permission_failure else BLOCKER_WAITING_FOR_PR_READY,
                    "slice_id": task.program_slice_id,
                    "run_id": run.id,
                    "pr_number": pr_number,
                    "detail": msg,
                    "ready_for_review_outcome": state.get("ready_for_review_outcome"),
                    "retry_count": int(state.get("ready_for_review_retry_count") or 0),
                },
                ensure_ascii=False,
            )
            program.latest_summary = (
                "Ready-for-review escalation for linked draft PR "
                f"#{pr_number}: {msg}"
            )
            program.updated_at = _utc_now()
            _save(session, program)
    run.last_summary = (
        f"{run.last_summary or ''}\nGovernor: ready_for_review_escalated ({msg})"
    ).strip()
    run.updated_at = _utc_now()
    _save_governor_state(run, state)
    _save(session, run)
    return True, False


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
        "initial_slice_contract": {
            "slice_title": task.title or "Initial slice",
            "slice_goal": internal_plan.get("objective") or task.title or "",
            "in_scope": internal_plan.get("scope") or [],
            "out_of_scope": internal_plan.get("non_goals") or [],
            "must_preserve": ["Preserve behavior outside the active slice boundary."],
            "focused_validation": internal_plan.get("validation_guidance") or [],
            "completion_conditions": internal_plan.get("acceptance_criteria") or [],
            "next_slice_hint": "",
        },
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
        state = _load_governor_state(run)
        state["ready_for_review_outcome"] = "ready_for_review_skipped_missing_pr_linkage"
        _set_checkpoint(
            state,
            name="pr_ready_verified",
            success=False,
            summary="Ready-for-review skipped: missing authoritative PR linkage.",
        )
        _save_governor_state(run, state)
        _save(session, run)
        _log_workflow_checkpoint(
            settings,
            event="ready_for_review_skipped_missing_pr_linkage",
            task=task,
            run=run,
            success=False,
            summary="Governor loop skipped because no PR number is linked to run.",
            skip_reason="no_pr_discovered",
            result_class="ready_for_review_skipped_missing_pr_linkage",
            state=state,
        )
        return
    state = _load_governor_state(run)
    if state.get("last_event_key") == event_key:
        return
    execution_mode = _current_execution_mode(task=task, run=run, state=state)
    state["execution_mode"] = execution_mode
    active_contract = _active_slice_contract(task, state)
    state["active_slice_acceptance_criteria"] = active_contract["acceptance_criteria"]
    state["active_slice_scope"] = active_contract["scope"]
    state["active_slice_non_goals"] = active_contract["non_goals"]
    state["active_slice_validation_guidance"] = active_contract["validation_guidance"]
    prior_contract_hash = str(state.get("active_slice_contract_hash") or "")
    state["active_slice_contract_hash"] = active_contract["contract_hash"]
    if prior_contract_hash != active_contract["contract_hash"]:
        state["active_slice_contract_version"] = int(state.get("active_slice_contract_version") or 0) + 1
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
    _log_workflow_checkpoint(
        settings,
        event="pr_discovered",
        task=task,
        run=run,
        success=True,
        summary=f"PR linkage discovered: #{pr_number}.",
        state=state,
    )
    event_has_push_signal = ":synchronize:" in event_key
    event_has_review_signal = ("pull_request_review:" in event_key) or ("pull_request_review_comment:" in event_key)

    pr_draft = bool(pr_payload.get("draft"))
    pr_node_id = pr_payload.get("node_id") if isinstance(pr_payload.get("node_id"), str) else None
    pr_state = str(pr_payload.get("state") or "open")
    _set_checkpoint(
        state,
        name="pr_ready_verified",
        success=not pr_draft,
        summary="PR is non-draft (ready for review)." if not pr_draft else "PR remains draft.",
    )
    _log_workflow_checkpoint(
        settings,
        event="pr_state_observed",
        task=task,
        run=run,
        success=True,
        summary=f"Observed PR state={pr_state}, draft={pr_draft}.",
        postcondition=f"isDraft={pr_draft}",
        pr_node_id=pr_node_id,
        state=state,
    )
    requested_reviewers = []
    for item in pr_payload.get("requested_reviewers") or []:
        if isinstance(item, dict) and isinstance(item.get("login"), str):
            requested_reviewers.append(item["login"])

    pr_title = str(pr_payload.get("title") or "")
    pr_body = str(pr_payload.get("body") or "")
    pr_head = pr_payload.get("head") if isinstance(pr_payload.get("head"), dict) else {}
    pr_head_sha = str(pr_head.get("sha") or pr_payload.get("head_sha") or "").strip()
    if pr_head_sha:
        state["last_observed_pr_head_sha"] = pr_head_sha
        state.setdefault("initial_pr_head_sha", pr_head_sha)
    pr_mergeable_raw = pr_payload.get("mergeable")
    pr_mergeable = pr_mergeable_raw if isinstance(pr_mergeable_raw, bool) or pr_mergeable_raw is None else None
    pr_mergeable_state = str(pr_payload.get("mergeable_state") or "")

    last_successful_checks_head_sha = str(state.get("last_successful_checks_head_sha") or "").strip()
    if checks_passed:
        state["last_checks_passed"] = True
        state["last_check_conclusion"] = "success"
        if pr_head_sha:
            state["last_successful_checks_head_sha"] = pr_head_sha
            last_successful_checks_head_sha = pr_head_sha
            state["last_successful_checks_at"] = _utc_now().isoformat()
    elif pr_head_sha and last_successful_checks_head_sha and pr_head_sha != last_successful_checks_head_sha:
        state["last_checks_passed"] = False
        state["last_check_conclusion"] = "head_sha_mismatch"

    effective_checks_passed = bool(
        checks_passed
        or (
            bool(state.get("last_checks_passed"))
            and pr_head_sha
            and last_successful_checks_head_sha
            and pr_head_sha == last_successful_checks_head_sha
        )
    )
    if not pr_head_sha and bool(state.get("last_checks_passed")):
        observed_head = str(state.get("last_observed_pr_head_sha") or "").strip()
        effective_checks_passed = effective_checks_passed or bool(
            observed_head
            and last_successful_checks_head_sha
            and observed_head == last_successful_checks_head_sha
        )
    state["effective_checks_passed"] = effective_checks_passed

    changed_files = [path for path in _parse_json_list(json.dumps(state.get("changed_files", []))) if isinstance(path, str)]
    file_details, file_details_msg = list_pull_request_file_details(settings=settings, repo=task.github_repo, pr_number=pr_number)
    patch_fallback_used = False
    patch_fallback_msg = ""
    patch_fallback_text = ""
    patch_fallback_truncated = False
    patch_fetch_error = ""
    if file_details:
        changed_files = [str(item.get("filename") or "") for item in file_details if str(item.get("filename") or "").strip()]
    elif not changed_files:
        files, _ = list_pull_request_files(settings=settings, repo=task.github_repo, pr_number=pr_number)
        if files:
            changed_files = files
    if not file_details:
        patch_fallback_text, patch_fallback_msg = fetch_pull_request_patch(
            settings=settings,
            repo=task.github_repo,
            pr_number=pr_number,
        )
        patch_fetch_error = patch_fallback_msg if not patch_fallback_text else ""
        if patch_fallback_text:
            derived_file_details = _derive_file_details_from_patch(patch_fallback_text, max_files=80)
            if derived_file_details:
                file_details = derived_file_details
                patch_fallback_used = True
                changed_files = [
                    str(item.get("filename") or "")
                    for item in file_details
                    if str(item.get("filename") or "").strip()
                ]
            if len(patch_fallback_text) > 12000:
                patch_fallback_text = patch_fallback_text[:12000]
                patch_fallback_truncated = True
    guarded_patterns = _governor_guarded_patterns(settings)
    guarded_files = [path for path in changed_files if _matches_guarded_path(path, guarded_patterns)]
    guarded_paths_touched = bool(guarded_files)
    docs_only = _is_docs_only_change(changed_files)

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

    _log_workflow_checkpoint(
        settings,
        event="review_harvest_attempted",
        task=task,
        run=run,
        success=True,
        summary="Attempting to harvest PR reviews and review comments.",
        auth_lane="governor",
        api_type="REST",
        state=state,
    )
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
    _log_workflow_checkpoint(
        settings,
        event="review_harvest_result",
        task=task,
        run=run,
        success=review_harvested,
        summary=(
            f"{state['review_harvest_summary']}; reviews_count={len(reviews)}; "
            f"review_comments_count={len(review_comments)}"
        ),
        auth_lane="governor",
        api_type="REST",
        state=state,
    )
    copilot_review_observed, unresolved_findings, ignored_non_actionable_reviews = _copilot_findings_from_reviews(
        settings=settings,
        reviews=reviews,
        comments=review_comments,
    )

    if ignored_non_actionable_reviews:
        _log_workflow_checkpoint(
            settings,
            event="ignored_non_actionable_copilot_review",
            task=task,
            run=run,
            success=True,
            summary=(
                f"Ignored {ignored_non_actionable_reviews} non-actionable Copilot review/review-comment body entries."
            ),
            skip_reason="ignored_non_actionable_copilot_review",
            result_class="ignored_non_actionable_copilot_review",
            state=state,
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
        _log_workflow_checkpoint(
            settings,
            event="copilot_push_detected",
            task=task,
            run=run,
            success=True,
            summary="Revision findings cleared after Copilot push/re-review.",
            state=state,
        )
    elif waiting_for_revision_push and (event_has_push_signal or event_has_review_signal):
        _set_checkpoint(
            state,
            name="copilot_push_rereview_observed",
            success=True,
            summary="Copilot push/re-review signal observed while waiting for revision.",
        )
        _log_workflow_checkpoint(
            settings,
            event="copilot_push_detected",
            task=task,
            run=run,
            success=True,
            summary="Copilot push/re-review signal observed while waiting for revision.",
            state=state,
        )
    if not unresolved_findings:
        _set_checkpoint(
            state,
            name="continuation_comment_posted",
            success=True,
            summary="No actionable unresolved review findings; no continuation comment needed.",
        )

    ready_handled, promoted_now = _handle_linked_draft_ready_for_review(
        session,
        settings=settings,
        task=task,
        run=run,
        state=state,
        pr_payload=pr_payload,
        event_key=event_key,
        checks_passed=checks_passed,
        effective_checks_passed=effective_checks_passed,
        guarded_paths_touched=guarded_paths_touched,
        unresolved_findings=unresolved_findings,
        waiting_for_revision_push=waiting_for_revision_push,
        changed_files=changed_files,
        file_details=file_details,
        event_has_push_signal=event_has_push_signal,
        pr_head_sha=pr_head_sha,
    )
    if promoted_now:
        pr_draft = False
        state["pr_draft"] = False
        state["safe_draft_promoted"] = True
        state["safe_draft_promotion_failed"] = False
    if ready_handled:
        _save_governor_state(run, state)
        _save(session, run)
        return

    if pr_mergeable is None and isinstance(pr_number, int):
        inspection = inspect_pull_request(settings=settings, repo=task.github_repo, pr_number=pr_number)
        if inspection.ok:
            inspection_mergeable = inspection.mergeable
            pr_mergeable = (
                inspection_mergeable
                if isinstance(inspection_mergeable, bool) or inspection_mergeable is None
                else pr_mergeable
            )
            inspection_mergeable_state = inspection.mergeable_state
            if isinstance(inspection_mergeable_state, str):
                pr_mergeable_state = inspection_mergeable_state or pr_mergeable_state

    pre_review_hold = bool(
        pr_draft
        and str(state.get("ready_for_review_outcome") or "") == "pr_not_ready_for_review_yet"
    )
    if pre_review_hold:
        state["last_governor_decision"] = "wait"
        state["last_governor_summary"] = [
            "Pre-review hold: waiting for substantive implementation evidence before revision/governor actions."
        ]
        _log_workflow_checkpoint(
            settings,
            event="pre_review_state_wait",
            task=task,
            run=run,
            success=True,
            summary=(
                "Pre-review hold active; skipping revision synthesis until reviewable evidence is present "
                f"(reason={state.get('ready_for_review_skip_reason') or 'pr_not_ready_for_review_yet'})."
            ),
            skip_reason="pre_review_state_wait",
            result_class="pre_review_state_wait",
            state=state,
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
            _log_workflow_checkpoint(
                settings,
                event="continuation_comment_posted",
                task=task,
                run=run,
                success=True,
                summary=(
                    "Top-level @copilot continuation comment posted; "
                    f"comment_fingerprint={trigger_fp[:12]}; dedupe_remote={exists_remote}"
                ),
                auth_lane="dispatch_user_token",
                api_type="REST",
                state=state,
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
            _log_workflow_checkpoint(
                settings,
                event="continuation_comment_skipped",
                task=task,
                run=run,
                success=True,
                summary=f"Continuation comment deduplicated by fingerprint={trigger_fp[:12]}.",
                skip_reason="no_actionable_review_findings",
                state=state,
            )
        else:
            _set_checkpoint(
                state,
                name="continuation_comment_posted",
                success=True,
                summary="No actionable/deduplicated continuation comment required this cycle.",
            )
            _log_workflow_checkpoint(
                settings,
                event="continuation_comment_skipped",
                task=task,
                run=run,
                success=True,
                summary=(
                    f"should_trigger_copilot={should_trigger_copilot}; unresolved_findings={len(unresolved_findings)}"
                ),
                skip_reason="no_actionable_review_findings",
                state=state,
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
        max_cycles = _revision_cycle_limit(settings=settings, execution_mode=execution_mode)
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

    review_artifact = _parse_json_object(run.review_artifact_json) or {}
    mergeable_for_audit = bool(pr_mergeable is True or pr_mergeable_state.lower() == "clean")
    merge_eligible_for_audit = (
        (not pr_draft)
        and effective_checks_passed
        and (not unresolved_findings)
        and (not waiting_for_revision_push)
        and (not guarded_paths_touched)
        and mergeable_for_audit
    )
    decision_payload: dict[str, Any]
    decision = "wait"
    summary_bullets: list[str] = []
    revision_requests: list[str] = []
    escalation_reason = ""
    program_acceptance_criteria = json.loads(task.acceptance_criteria_json or "[]")
    prior_decision_exists = bool(state.get("last_governor_decision"))
    contract_changed = str(state.get("active_slice_contract_hash") or "") != active_contract["contract_hash"]
    include_full_program_acceptance = bool((not prior_decision_exists) or contract_changed)
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
        "effective_checks_passed": effective_checks_passed,
        "pr_head_sha": pr_head_sha,
        "last_successful_checks_head_sha": state.get("last_successful_checks_head_sha"),
        "review_artifact": review_artifact,
        "copilot_review_observed": copilot_review_observed,
        "unresolved_copilot_findings": unresolved_findings,
        "changed_files": changed_files,
        "docs_only": docs_only,
        "mergeable": pr_mergeable,
        "mergeable_state": pr_mergeable_state,
        "guarded_paths_touched": guarded_paths_touched,
        "guarded_files": guarded_files,
        "revision_cycle_count": int(state.get("revision_cycle_count") or 0),
        "execution_mode": execution_mode,
        "active_slice_contract": active_contract,
        "prior_decision_summary": {
            "decision": str(state.get("last_governor_decision") or ""),
            "summary": [str(item).strip() for item in (state.get("last_governor_summary") or []) if str(item).strip()][:4],
            "reuse_reason": str(state.get("last_model_reuse_reason") or ""),
        },
        "budget_counters": _heavy_budget_counters(
            state=state,
            pr_head_sha=pr_head_sha,
            slice_contract_hash=active_contract["contract_hash"],
            include_repeat_counters=True,
        ),
    }
    if include_full_program_acceptance:
        governor_context["program_acceptance_criteria"] = program_acceptance_criteria
    else:
        governor_context["program_acceptance_summary"] = {
            "total_items": len(program_acceptance_criteria),
            "contract_hash": active_contract["contract_hash"],
        }
        governor_context["umbrella_context_trimmed"] = True
    material_state_payload = {
        "repo": task.github_repo,
        "pr_number": pr_number,
        "pr_head_sha": pr_head_sha,
        "effective_checks_passed": effective_checks_passed,
        "unresolved_findings_hash": hashlib.sha1(
            json.dumps(unresolved_findings, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest(),
        "requested_reviewers_hash": hashlib.sha1(
            json.dumps(sorted(requested_reviewers), ensure_ascii=False).encode("utf-8")
        ).hexdigest(),
        "review_decision": str(review_artifact.get("decision") or ""),
        "review_status": str(review_artifact.get("status") or ""),
        "guarded_paths_touched": guarded_paths_touched,
        "guarded_files_hash": hashlib.sha1(
            json.dumps(sorted(guarded_files), ensure_ascii=False).encode("utf-8")
        ).hexdigest(),
        "changed_files_hash": hashlib.sha1(
            json.dumps(sorted(changed_files), ensure_ascii=False).encode("utf-8")
        ).hexdigest(),
        "mergeable": pr_mergeable,
        "mergeable_state": pr_mergeable_state,
        "slice_contract_hash": active_contract["contract_hash"],
    }
    unresolved_findings_hash = hashlib.sha1(
        json.dumps(unresolved_findings, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    changed_files_hash = hashlib.sha1(
        json.dumps(sorted(changed_files), ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    material_hash = _material_state_hash(payload=material_state_payload)
    prior_material_hash = str(state.get("material_state_hash") or "")
    prior_material_head = str(state.get("material_state_pr_head_sha") or "")
    material_unchanged = bool(
        prior_material_hash
        and prior_material_hash == material_hash
        and prior_material_head == (pr_head_sha or "")
    )
    coarse_state_unchanged = bool(
        prior_material_head
        and prior_material_head == (pr_head_sha or "")
        and str(state.get("active_slice_contract_hash") or "") == active_contract["contract_hash"]
    )
    has_prior_decision = bool(state.get("last_governor_decision"))
    deterministic_noisy_skip = _high_autonomy_noisy_skip_candidate(
        execution_mode=execution_mode,
        event_key=event_key,
        material_unchanged=material_unchanged,
        coarse_state_unchanged=coarse_state_unchanged,
        has_prior_decision=has_prior_decision,
    )
    merge_candidate = bool(
        (not pr_draft)
        and effective_checks_passed
        and (not unresolved_findings)
        and (not waiting_for_revision_push)
    )
    serious_review_pass_ready = bool(merge_candidate and (not requested_reviewers) and (not guarded_paths_touched))
    if deterministic_noisy_skip:
        decision = str(state.get("last_governor_decision") or "wait")
        summary_bullets = [str(item).strip() for item in (state.get("last_governor_summary") or []) if str(item).strip()]
        state["last_model_reuse_reason"] = SKIP_REASON_SUPPRESSED_NOISY_EVENT
        state["last_reused_governor_decision"] = decision
        state["last_deterministic_skip_reason"] = SKIP_REASON_SUPPRESSED_NOISY_EVENT
        _record_openai_telemetry(
            session,
            task=task,
            run=run,
            stage="governor_fast_path",
            action="summarize_governor_update",
            outcome="suppressed",
            execution_mode=execution_mode,
            event_key=event_key,
            head_sha=pr_head_sha,
            slice_contract_hash=active_contract["contract_hash"],
            skip_reason=SKIP_REASON_SUPPRESSED_NOISY_EVENT,
            extra={"reused_decision": decision, "material_hash": material_hash},
        )
    elif merge_eligible_for_audit:
        heavy_reasons = _material_transition_reasons(
            state=state,
            pr_head_sha=pr_head_sha,
            effective_checks_passed=effective_checks_passed,
            active_contract_hash=active_contract["contract_hash"],
            changed_files_hash=changed_files_hash,
            unresolved_findings_hash=unresolved_findings_hash,
            mergeable_state=pr_mergeable_state,
            file_details_count=len(file_details),
            patch_fallback_used=patch_fallback_used,
        )
        if not heavy_reasons:
            decision = "wait"
            summary_bullets = [
                "Heavy merge audit deferred: no meaningful transition since prior serious review state."
            ]
            decision_payload = {
                "merge_audit_artifact": {
                    "decision": "wait",
                    "confidence": 0.0,
                    "doc_only": docs_only,
                    "safe_to_merge": False,
                    "requires_followup": True,
                    "summary": summary_bullets,
                    "findings": [],
                    "merge_rationale": "",
                    "escalation_reason": "",
                    "review_scope": ["material_transition_gate"],
                },
                "openai_meta": {"cache_hit": True, "reason": SKIP_REASON_HEAVY_REVIEW_GATED},
            }
            state["last_heavy_block_reason"] = SKIP_REASON_HEAVY_REVIEW_GATED
            _record_openai_telemetry(
                session,
                task=task,
                run=run,
                stage="merge_audit",
                action="summarize_merge_audit",
                outcome="suppressed",
                execution_mode=execution_mode,
                event_key=event_key,
                head_sha=pr_head_sha,
                slice_contract_hash=active_contract["contract_hash"],
                skip_reason=SKIP_REASON_HEAVY_REVIEW_GATED,
            )
        else:
            state["last_heavy_block_reason"] = ""
            governor_context["heavy_review_reasons"] = heavy_reasons
            material_state_payload["heavy_review_reasons"] = heavy_reasons
        prior_final_audit_artifact = state.get("final_audit_artifact") if isinstance(state.get("final_audit_artifact"), dict) else {}
        prior_final_audit_decision = str(state.get("final_audit_decision") or "")
        prior_final_audit_head_sha = str(state.get("final_audit_head_sha") or "").strip()
        prior_partial_or_stale = bool(
            prior_final_audit_artifact.get("requires_followup")
            or prior_final_audit_decision in {"wait", "escalate_human", "request_revision"}
            or (pr_head_sha and prior_final_audit_head_sha and prior_final_audit_head_sha != pr_head_sha)
            or (not state.get("effective_checks_passed_at_final_audit"))
        )
        bounded_files: list[dict[str, Any]] = []
        truncated_patch_count = 0
        for file_item in file_details[:20]:
            filename = str(file_item.get("filename") or "")
            patch_value = str(file_item.get("patch") or "")
            truncated_patch, was_truncated = _truncate_patch(patch_value, max_chars=2000)
            if was_truncated:
                truncated_patch_count += 1
            bounded_files.append(
                {
                    "filename": filename,
                    "status": str(file_item.get("status") or "modified"),
                    "additions": int(file_item.get("additions") or 0),
                    "deletions": int(file_item.get("deletions") or 0),
                    "patch": truncated_patch,
                    "patch_truncated": was_truncated,
                }
            )
        patch_fallback_text_bounded = ""
        patch_fallback_text_truncated = False
        if patch_fallback_text:
            patch_fallback_text_bounded, patch_fallback_text_truncated = _truncate_patch(
                patch_fallback_text,
                max_chars=4000,
            )
            if patch_fallback_truncated and not patch_fallback_text_truncated:
                patch_fallback_text_truncated = True
        evidence_missing = not bounded_files and not patch_fallback_text_bounded.strip()
        no_evidence_state_hash = hashlib.sha1(
            json.dumps(
                {
                    "pr_number": pr_number,
                    "pr_head_sha": pr_head_sha,
                    "effective_checks_passed": effective_checks_passed,
                    "mergeable_for_audit": mergeable_for_audit,
                    "docs_only": docs_only,
                    "changed_files_hash": changed_files_hash,
                    "file_details_count": len(file_details),
                    "patch_fallback_used": patch_fallback_used,
                    "patch_fetch_error": patch_fetch_error,
                },
                sort_keys=True,
                ensure_ascii=False,
            ).encode("utf-8")
        ).hexdigest()
        prior_no_evidence_hash = str(state.get("final_audit_no_evidence_state_hash") or "")
        reuse_no_evidence_wait = bool(
            evidence_missing and prior_no_evidence_hash and prior_no_evidence_hash == no_evidence_state_hash
        )
        audit_context = {
            "event_key": event_key,
            "repo": task.github_repo,
            "issue_number": task.github_issue_number,
            "pr_number": pr_number,
            "pr_title": pr_title,
            "pr_body": pr_body,
            "pr": {
                "draft": pr_draft,
                "state": pr_state,
                "mergeable": pr_mergeable,
                "mergeable_state": pr_mergeable_state,
            },
            "checks_passed": checks_passed,
            "effective_checks_passed": effective_checks_passed,
            "check_status_summary": {
                "checks_passed": checks_passed,
                "effective_checks_passed": effective_checks_passed,
                "head_sha": pr_head_sha,
                "last_successful_checks_head_sha": state.get("last_successful_checks_head_sha"),
            },
            "mergeability_summary": {
                "mergeable": pr_mergeable,
                "mergeable_state": pr_mergeable_state,
                "mergeable_for_audit": mergeable_for_audit,
            },
            "review_artifact": review_artifact,
            "copilot_review_observed": copilot_review_observed,
            "unresolved_copilot_findings": unresolved_findings,
            "changed_files": changed_files[:80],
            "file_details": bounded_files,
            "file_detail_summary": {
                "files_returned": len(file_details),
                "files_included": len(bounded_files),
                "file_details_message": file_details_msg,
                "truncated_patch_count": truncated_patch_count,
                "all_patches_present": all(bool(str(item.get("patch") or "").strip()) for item in bounded_files) if bounded_files else False,
                "patch_fallback_used": patch_fallback_used,
                "patch_fallback_message": patch_fallback_msg,
                "patch_fallback_truncated": patch_fallback_text_truncated,
                "fetch_error": patch_fetch_error or file_details_msg if not file_details else "",
                "evidence_missing": evidence_missing,
            },
            "patch_fallback_evidence": patch_fallback_text_bounded,
            "guarded_paths_touched": guarded_paths_touched,
            "guarded_files": guarded_files,
            "doc_only": docs_only,
            "acceptance_criteria": active_contract["acceptance_criteria"],
            "slice_scope": active_contract["scope"],
            "slice_non_goals": active_contract["non_goals"],
            "slice_validation_guidance": active_contract["validation_guidance"],
            "program_acceptance_criteria": json.loads(task.acceptance_criteria_json or "[]"),
            "prior_final_audit_artifact": prior_final_audit_artifact,
            "prior_final_audit_decision": prior_final_audit_decision,
            "prior_final_audit_partial_or_stale": prior_partial_or_stale,
            "waiting_for_revision_push": waiting_for_revision_push,
            "approval_submitted": bool(state.get("approval_submitted")),
            "reviews_summary": state.get("review_harvest_summary"),
            "requested_reviewers": requested_reviewers,
            "heavy_review_reasons": heavy_reasons,
        }
        merge_audit_cache_payload = {
            "pr_number": pr_number,
            "pr_head_sha": pr_head_sha,
            "effective_checks_passed": effective_checks_passed,
            "pr_draft": pr_draft,
            "changed_files_hash": changed_files_hash,
            "unresolved_findings_hash": unresolved_findings_hash,
            "guarded_paths_touched": guarded_paths_touched,
            "guarded_files_hash": hashlib.sha1(
                json.dumps(sorted(guarded_files), ensure_ascii=False).encode("utf-8")
            ).hexdigest(),
            "mergeable_for_audit": mergeable_for_audit,
            "docs_only": docs_only,
            "file_details_count": len(file_details),
            "patch_fallback_used": patch_fallback_used,
            "evidence_missing": evidence_missing,
        }
        merge_audit_cache_key = hashlib.sha1(
            json.dumps(merge_audit_cache_payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()
        prior_cache_key = str(state.get("final_audit_cache_key") or "").strip()
        prior_evidence_missing = bool(prior_final_audit_artifact.get("evidence_missing"))
        if not heavy_reasons:
            pass
        elif reuse_no_evidence_wait:
            artifact = prior_final_audit_artifact if prior_final_audit_artifact else {}
            if not artifact:
                artifact = {
                    "decision": "wait",
                    "confidence": 0.0,
                    "doc_only": docs_only,
                    "safe_to_merge": False,
                    "requires_followup": True,
                    "summary": [
                        "Final merge audit deferred: PR evidence is still unavailable.",
                        "Waiting for file details or patch evidence before calling merge audit model again.",
                    ],
                    "findings": [],
                    "merge_rationale": "",
                    "escalation_reason": "merge_audit_evidence_missing",
                    "review_scope": ["evidence_missing"],
                }
            decision_payload = {
                "merge_audit_artifact": artifact,
                "openai_meta": {"cache_hit": True, "reason": "evidence_missing_no_state_change"},
            }
            _record_openai_telemetry(
                session,
                task=task,
                run=run,
                stage="merge_audit",
                action="summarize_merge_audit",
                outcome="suppressed",
                execution_mode=execution_mode,
                event_key=event_key,
                head_sha=pr_head_sha,
                slice_contract_hash=active_contract["contract_hash"],
                skip_reason="evidence_missing_no_state_change",
                budget_counters=_heavy_budget_counters(state=state),
            )
        elif prior_cache_key and prior_cache_key == merge_audit_cache_key and prior_final_audit_artifact and prior_final_audit_decision and not (prior_evidence_missing and not evidence_missing):
            decision_payload = {
                "merge_audit_artifact": prior_final_audit_artifact,
                "openai_meta": {"cache_hit": True},
            }
            _record_openai_telemetry(
                session,
                task=task,
                run=run,
                stage="merge_audit",
                action="summarize_merge_audit",
                outcome="suppressed",
                execution_mode=execution_mode,
                event_key=event_key,
                head_sha=pr_head_sha,
                slice_contract_hash=active_contract["contract_hash"],
                skip_reason="cached_result_reuse",
                budget_counters=_heavy_budget_counters(state=state),
            )
            _governor_logger.info(
                "Reusing cached final merge audit for PR #%s head=%s cache_key=%s",
                pr_number,
                pr_head_sha or "<unknown>",
                merge_audit_cache_key[:12],
            )
        else:
            budget_ok, budget_reason = _heavy_budget_available(
                settings=settings,
                state=state,
                pr_head_sha=pr_head_sha,
                slice_contract_hash=active_contract["contract_hash"],
            )
            if not budget_ok:
                decision_payload = {
                    "merge_audit_artifact": {
                        "decision": "wait",
                        "confidence": 0.0,
                        "doc_only": docs_only,
                        "safe_to_merge": False,
                        "requires_followup": True,
                        "summary": [f"Merge audit paused: {budget_reason}."],
                        "findings": [],
                        "merge_rationale": "",
                        "escalation_reason": budget_reason,
                        "review_scope": ["budget_guardrail"],
                    },
                    "openai_meta": {"cache_hit": True, "reason": budget_reason},
                }
                _record_openai_telemetry(
                    session,
                    task=task,
                    run=run,
                    stage="merge_audit",
                    action="summarize_merge_audit",
                    outcome="budget_blocked",
                    execution_mode=execution_mode,
                    event_key=event_key,
                    head_sha=pr_head_sha,
                    slice_contract_hash=active_contract["contract_hash"],
                    skip_reason=budget_reason,
                    budget_counters=_heavy_budget_counters(
                        state=state,
                        pr_head_sha=pr_head_sha,
                        slice_contract_hash=active_contract["contract_hash"],
                    ),
                )
                state["last_heavy_block_reason"] = budget_reason
                budget_blocked_state_hash = hashlib.sha1(
                    json.dumps(
                        {
                            "reason": budget_reason,
                            "head_sha": pr_head_sha,
                            "slice_contract_hash": active_contract["contract_hash"],
                        },
                        sort_keys=True,
                        ensure_ascii=False,
                    ).encode("utf-8")
                ).hexdigest()
                if str(state.get("last_budget_blocked_state_hash") or "") == budget_blocked_state_hash:
                    state["budget_blocked_repeat_count"] = int(state.get("budget_blocked_repeat_count") or 0) + 1
                else:
                    state["budget_blocked_repeat_count"] = 1
                    state["last_budget_blocked_state_hash"] = budget_blocked_state_hash
                max_repeats = max(1, int(getattr(settings, "governor_max_repeated_blocked_reviews", 2) or 2))
                if int(state.get("budget_blocked_repeat_count") or 0) > max_repeats:
                    decision = "escalate_human"
                    escalation_reason = "Repeated heavy-review budget blocks detected; summarize-and-stop enforced."
                    summary_bullets = [escalation_reason]
                    state["last_heavy_block_reason"] = escalation_reason
            else:
                decision_payload = summarize_merge_audit(
                    settings=settings,
                    update_context=json.dumps(audit_context, ensure_ascii=False),
                    previous_response_id=run.openai_last_response_id,
                )
                _record_heavy_model_call(
                    state=state,
                    pr_head_sha=pr_head_sha,
                    slice_contract_hash=active_contract["contract_hash"],
                )
                state["budget_blocked_repeat_count"] = 0
                state["last_budget_blocked_state_hash"] = ""
        openai_meta = decision_payload.get("openai_meta") if isinstance(decision_payload, dict) else {}
        if not isinstance(openai_meta, dict):
            openai_meta = {}
        if (openai_meta or {}).get("response_id"):
            _record_openai_telemetry(
                session,
                task=task,
                run=run,
                stage=str(openai_meta.get("stage") or "final_merge_audit"),
                action="summarize_merge_audit",
                outcome=str(openai_meta.get("outcome") or "success"),
                execution_mode=execution_mode,
                event_key=event_key,
                head_sha=pr_head_sha,
                slice_contract_hash=active_contract["contract_hash"],
                model=openai_meta.get("model"),
                reasoning_effort=openai_meta.get("reasoning_effort"),
                prompt_fingerprint=openai_meta.get("prompt_fingerprint"),
                usage=openai_meta.get("usage") if isinstance(openai_meta.get("usage"), dict) else {},
                skip_reason=openai_meta.get("skip_reason"),
                budget_counters=_heavy_budget_counters(state=state),
                extra={"response_id": openai_meta.get("response_id"), "model_tier": openai_meta.get("model_tier")},
            )
        response_id = openai_meta.get("response_id") if isinstance(openai_meta, dict) else None
        if isinstance(response_id, str) and response_id.strip():
            run.openai_last_response_id = response_id.strip()
        artifact = decision_payload.get("merge_audit_artifact") if isinstance(decision_payload, dict) else {}
        if isinstance(artifact, dict):
            artifact.setdefault("evidence_missing", evidence_missing)
            artifact.setdefault("file_details_count", len(file_details))
            artifact.setdefault("patch_fallback_used", patch_fallback_used)
            artifact.setdefault("fetch_error", patch_fetch_error or file_details_msg if evidence_missing else "")
            artifact.setdefault("changed_files_hash", changed_files_hash)
        decision = str((artifact or {}).get("decision") or "wait")
        summary_bullets = artifact.get("summary") if isinstance(artifact.get("summary"), list) else []
        revision_requests = [str(item.get("summary") or "").strip() for item in artifact.get("findings") or [] if isinstance(item, dict)]
        escalation_reason = str(artifact.get("escalation_reason") or "")
        state["final_audit_artifact"] = artifact if isinstance(artifact, dict) else {}
        state["final_audit_decision"] = decision
        state["final_audit_confidence"] = float(artifact.get("confidence") or 0.0) if isinstance(artifact, dict) else 0.0
        state["final_audit_summary"] = summary_bullets
        state["final_audit_last_error"] = str((openai_meta or {}).get("validation_error") or "")
        state["final_audit_head_sha"] = pr_head_sha
        state["effective_checks_passed_at_final_audit"] = effective_checks_passed
        state["final_audit_cache_key"] = merge_audit_cache_key
        state["final_audit_file_details_count"] = len(file_details)
        state["final_audit_patch_fallback_used"] = patch_fallback_used
        state["final_audit_evidence_missing"] = evidence_missing
        state["final_audit_fetch_error"] = patch_fetch_error or file_details_msg if evidence_missing else ""
        state["final_audit_changed_files_hash"] = changed_files_hash
        state["final_audit_no_evidence_state_hash"] = no_evidence_state_hash if evidence_missing else ""
    else:
        if pre_review_hold:
            decision = "wait"
            summary_bullets = [
                "Pre-review hold: waiting for substantive implementation evidence before requesting revisions."
            ]
            state["last_model_reuse_reason"] = "pre_review_state_wait"
            state["last_reused_governor_decision"] = decision
            _record_openai_telemetry(
                session,
                task=task,
                run=run,
                stage="governor_fast_path" if execution_mode == EXECUTION_MODE_HIGH_AUTONOMY_PROGRAM else "continuation_audit",
                action="summarize_governor_update",
                outcome="skipped",
                execution_mode=execution_mode,
                event_key=event_key,
                head_sha=pr_head_sha,
                slice_contract_hash=active_contract["contract_hash"],
                skip_reason="pre_review_state_wait",
            )
        else:
            reuse_previous = _legacy_unchanged_material_skip_candidate(
                execution_mode=execution_mode,
                event_key=event_key,
                material_unchanged=material_unchanged,
                has_prior_decision=has_prior_decision,
            )
            if reuse_previous:
                decision = str(state.get("last_governor_decision") or "wait")
                summary_bullets = [str(item) for item in (state.get("last_governor_summary") or []) if str(item).strip()]
                state["last_model_reuse_reason"] = SKIP_REASON_SUPPRESSED_UNCHANGED_STATE
                state["last_reused_governor_decision"] = decision
                _governor_logger.info(
                    "Suppressed governor model call for PR #%s due to unchanged material state (head=%s hash=%s).",
                    pr_number,
                    pr_head_sha or "<unknown>",
                    material_hash[:12],
                )
                _record_openai_telemetry(
                    session,
                    task=task,
                    run=run,
                    stage="governor_fast_path" if execution_mode == EXECUTION_MODE_HIGH_AUTONOMY_PROGRAM else "continuation_audit",
                    action="summarize_governor_update",
                    outcome="suppressed",
                    execution_mode=execution_mode,
                    event_key=event_key,
                    head_sha=pr_head_sha,
                    slice_contract_hash=active_contract["contract_hash"],
                    skip_reason=SKIP_REASON_SUPPRESSED_UNCHANGED_STATE,
                )
            elif execution_mode == EXECUTION_MODE_HIGH_AUTONOMY_PROGRAM and not serious_review_pass_ready:
                decision = "wait"
                summary_bullets = [
                    "High-autonomy mode holding: serious review pass deferred until merge-candidate gates are met."
                ]
                state["last_model_reuse_reason"] = "high_autonomy_wait_for_serious_pass"
                state["last_reused_governor_decision"] = decision
                _record_openai_telemetry(
                    session,
                    task=task,
                    run=run,
                    stage="governor_fast_path",
                    action="summarize_governor_update",
                    outcome="skipped",
                    execution_mode=execution_mode,
                    event_key=event_key,
                    head_sha=pr_head_sha,
                    slice_contract_hash=active_contract["contract_hash"],
                    skip_reason="high_autonomy_wait_for_serious_pass",
                )
            else:
                governor_model = (
                    settings.openai_governor_model_fast
                    if execution_mode == EXECUTION_MODE_HIGH_AUTONOMY_PROGRAM
                    else settings.openai_governor_model_heavy
                )
                decision_payload = summarize_governor_update(
                    settings=settings,
                    update_context=json.dumps(governor_context, ensure_ascii=False),
                    previous_response_id=run.openai_last_response_id,
                    model=governor_model,
                    stage="governor_fast_path" if execution_mode == EXECUTION_MODE_HIGH_AUTONOMY_PROGRAM else "continuation_audit",
                )
                openai_meta = decision_payload.get("openai_meta") if isinstance(decision_payload, dict) else {}
                if not isinstance(openai_meta, dict):
                    openai_meta = {}
                _record_openai_telemetry(
                    session,
                    task=task,
                    run=run,
                    stage=str(openai_meta.get("stage") or ("governor_fast_path" if execution_mode == EXECUTION_MODE_HIGH_AUTONOMY_PROGRAM else "continuation_audit")),
                    action="summarize_governor_update",
                    outcome=str(openai_meta.get("outcome") or "success"),
                    execution_mode=execution_mode,
                    event_key=event_key,
                    head_sha=pr_head_sha,
                    slice_contract_hash=active_contract["contract_hash"],
                    model=openai_meta.get("model") or governor_model,
                    reasoning_effort=openai_meta.get("reasoning_effort"),
                    prompt_fingerprint=openai_meta.get("prompt_fingerprint"),
                    usage=openai_meta.get("usage") if isinstance(openai_meta.get("usage"), dict) else {},
                    skip_reason=openai_meta.get("skip_reason"),
                    budget_counters=_heavy_budget_counters(state=state),
                    extra={"response_id": openai_meta.get("response_id"), "model_tier": openai_meta.get("model_tier")},
                )
                response_id = openai_meta.get("response_id") if isinstance(openai_meta, dict) else None
                if isinstance(response_id, str) and response_id.strip():
                    run.openai_last_response_id = response_id.strip()
                artifact = decision_payload.get("governor_artifact") if isinstance(decision_payload, dict) else {}
                decision = str((artifact or {}).get("decision") or "wait")
                summary_bullets = artifact.get("summary") if isinstance(artifact.get("summary"), list) else []
                revision_requests = artifact.get("revision_requests") if isinstance(artifact.get("revision_requests"), list) else []
                escalation_reason = str(artifact.get("escalation_reason") or "")
                state["last_model_reuse_reason"] = ""

    if not deterministic_noisy_skip:
        state["last_deterministic_skip_reason"] = ""
    if decision != "wait" or not str(state.get("last_heavy_block_reason") or "").startswith("heavy_model_budget_exhausted"):
        if str(state.get("last_heavy_block_reason") or "").startswith("heavy_model_budget_exhausted"):
            state["last_heavy_block_reason"] = ""
    state["pr_draft"] = pr_draft
    state["pr_state"] = pr_state
    state["requested_reviewers"] = requested_reviewers
    state["changed_files"] = changed_files
    state["docs_only"] = docs_only
    state["pr_mergeable"] = pr_mergeable
    state["pr_mergeable_state"] = pr_mergeable_state
    state["copilot_review_observed"] = copilot_review_observed
    state["unresolved_copilot_findings"] = unresolved_findings
    state["guarded_paths_touched"] = guarded_paths_touched
    state["guarded_files"] = guarded_files
    state["material_state_hash"] = material_hash
    state["material_state_pr_head_sha"] = pr_head_sha or ""
    state["last_event_key"] = event_key
    state["last_governor_decision"] = decision
    state["last_governor_summary"] = summary_bullets
    state["final_audit_unresolved_findings_hash"] = unresolved_findings_hash
    final_audit_safe_to_merge = bool(
        merge_eligible_for_audit and isinstance(state.get("final_audit_artifact"), dict) and state["final_audit_artifact"].get("safe_to_merge")
    )
    if merge_eligible_for_audit and decision == "approve_and_merge" and not final_audit_safe_to_merge:
        decision = "wait"
        summary_bullets = summary_bullets or ["Final audit did not confirm safe_to_merge=true."]
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
        _log_workflow_checkpoint(
            settings,
            event="continuation_comment_synthesized",
            task=task,
            run=run,
            success=True,
            summary=(
                f"Synthesized continuation comment; unresolved_findings={len(rendered_findings)}; "
                f"governor_requests={len(rendered_requests)}; fingerprint={fingerprint[:12]}"
            ),
            state=state,
        )
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
        max_cycles = _revision_cycle_limit(settings=settings, execution_mode=execution_mode)
        if int(state.get("revision_cycle_count") or 0) > max_cycles:
            decision = "escalate_human"
            escalation_reason = "Max governor revision cycles exceeded."

    if decision in {"request_revision", "escalate_human"}:
        blocked_state_hash = hashlib.sha1(
            json.dumps(
                {
                    "decision": decision,
                    "revision_requests": [str(item).strip() for item in revision_requests if str(item).strip()],
                    "escalation_reason": escalation_reason,
                    "slice_contract_hash": active_contract["contract_hash"],
                },
                sort_keys=True,
                ensure_ascii=False,
            ).encode("utf-8")
        ).hexdigest()
        if str(state.get("last_blocked_state_hash") or "") == blocked_state_hash:
            state["blocked_state_repeat_count"] = int(state.get("blocked_state_repeat_count") or 0) + 1
        else:
            state["blocked_state_repeat_count"] = 1
            state["last_blocked_state_hash"] = blocked_state_hash
        max_repeats = max(1, int(getattr(settings, "governor_max_repeated_blocked_reviews", 2) or 2))
        if int(state.get("blocked_state_repeat_count") or 0) > max_repeats:
            decision = "escalate_human"
            escalation_reason = "Repeated blocked governor state detected; summarize-and-stop enforced."
            summary_bullets = [escalation_reason]
    else:
        state["blocked_state_repeat_count"] = 0
        state["last_blocked_state_hash"] = ""

    if decision == "ready_for_review" and pr_draft:
        _log_workflow_checkpoint(
            settings,
            event="ready_for_review_skipped_non_draft",
            task=task,
            run=run,
            success=True,
            summary="OpenAI requested ready_for_review but draft handoff already executed in this cycle.",
            auth_lane="dispatch_user_token",
            api_type="GraphQL",
            skip_reason="already_handled_earlier",
            state=state,
        )
    if decision == "approve_and_merge":
        ready_gate = bool((state.get("checkpoints") or {}).get("pr_ready_verified", {}).get("success"))
        harvest_gate = bool((state.get("checkpoints") or {}).get("review_harvested", {}).get("success"))
        pr_gate = bool((state.get("checkpoints") or {}).get("pr_discovered", {}).get("success"))
        dispatch_gate = bool((state.get("checkpoints") or {}).get("issue_dispatched", {}).get("success"))
        governor_auth_ready = has_governor_auth(settings)
        dispatch_auth_ready = has_dispatch_auth(settings)
        if (
            guarded_paths_touched
            or unresolved_findings
            or pr_draft
            or not effective_checks_passed
            or waiting_for_revision_push
            or not governor_auth_ready
            or not dispatch_auth_ready
            or not ready_gate
            or not harvest_gate
            or not pr_gate
            or not dispatch_gate
        ):
            _log_workflow_checkpoint(
                settings,
                event="merge_failed",
                task=task,
                run=run,
                success=False,
                summary=(
                    "Merge path skipped due to unmet prerequisites: "
                    f"ready_gate={ready_gate}, harvest_gate={harvest_gate}, pr_gate={pr_gate}, dispatch_gate={dispatch_gate}, "
                    f"governor_auth_ready={governor_auth_ready}, dispatch_auth_ready={dispatch_auth_ready}, "
                    f"guarded_paths_touched={guarded_paths_touched}, unresolved_findings={len(unresolved_findings)}, "
                    f"pr_draft={pr_draft}, checks_passed={checks_passed}, "
                    f"effective_checks_passed={effective_checks_passed}, waiting_for_revision_push={waiting_for_revision_push}"
                ),
                skip_reason="missing_checkpoint_prerequisite",
                state=state,
            )
            decision = "escalate_human" if (not governor_auth_ready or not dispatch_auth_ready) else "wait"
            if decision == "escalate_human":
                escalation_reason = "Merge audit approved but GitHub auth for approval/merge is unavailable."
        else:
            if not bool(state.get("approval_submitted")):
                approval_ok, approval_msg = submit_approving_review(settings=settings, repo=task.github_repo, pr_number=pr_number)
                if not approval_ok:
                    decision = "escalate_human"
                    escalation_reason = approval_msg
                    _set_checkpoint(
                        state,
                        name="approval_submitted",
                        success=False,
                        summary=approval_msg,
                    )
                else:
                    _set_checkpoint(
                        state,
                        name="approval_submitted",
                        success=True,
                        summary=approval_msg,
                    )
                    state["approval_submitted"] = True
            if decision == "escalate_human":
                state["last_governor_decision"] = decision
                state["last_governor_summary"] = [escalation_reason or "Approval submission failed."]
            else:
                state["approval_submitted"] = True
                _log_workflow_checkpoint(
                    settings,
                    event="merge_attempted",
                    task=task,
                    run=run,
                    success=True,
                    summary="Attempting merge with latest head SHA.",
                    auth_lane="dispatch_user_token",
                    api_type="REST",
                    state=state,
                )
                merged, merge_msg = merge_pr(settings=settings, repo=task.github_repo, pr_number=pr_number)
                if "retry_used=True" in str(merge_msg):
                    _log_workflow_checkpoint(
                        settings,
                        event="merge_retry_409",
                        task=task,
                        run=run,
                        success=True,
                        summary=merge_msg,
                        auth_lane="dispatch_user_token",
                        api_type="REST",
                        state=state,
                    )
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
                    _log_workflow_checkpoint(
                        settings,
                        event="merge_verified",
                        task=task,
                        run=run,
                        success=True,
                        summary=merge_msg,
                        postcondition="merged=true",
                        auth_lane="dispatch_user_token",
                        api_type="REST",
                        state=state,
                    )
                else:
                    _set_checkpoint(
                        state,
                        name="merge_verified",
                        success=False,
                        summary=merge_msg,
                    )
                    _log_workflow_checkpoint(
                        settings,
                        event="merge_failed",
                        task=task,
                        run=run,
                        success=False,
                        summary=merge_msg,
                        postcondition="merged!=true",
                        auth_lane="dispatch_user_token",
                        api_type="REST",
                        state=state,
                    )
                    decision = "wait"
                    summary_bullets = [merge_msg]
                    state["last_governor_decision"] = decision
                    state["last_governor_summary"] = summary_bullets
    state["last_governor_decision"] = decision
    state["last_governor_summary"] = summary_bullets if summary_bullets else [decision]

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
            {
                "github_pr_number": latest_run.github_pr_number,
                "github_pr_url": latest_run.github_pr_url,
                "github_pr_node_id": latest_run.github_pr_node_id,
                "github_dispatch_url": latest_run.github_dispatch_url,
                "linkage_tag": latest_run.linkage_tag,
            }
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
        "github_pr_url": run.github_pr_url,
        "github_pr_node_id": run.github_pr_node_id,
        "linkage_tag": run.linkage_tag,
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
        call_metas = planning_meta.get("calls") if isinstance(planning_meta, dict) else []
        if isinstance(call_metas, list):
            for call_meta in call_metas:
                if not isinstance(call_meta, dict):
                    continue
                _record_openai_telemetry(
                    session,
                    task=task,
                    run=None,
                    stage=str(call_meta.get("stage") or "planner"),
                    action="plan_task_packet",
                    outcome=str(call_meta.get("outcome") or "success"),
                    execution_mode=EXECUTION_MODE_STANDARD,
                    model=call_meta.get("model"),
                    reasoning_effort=call_meta.get("reasoning_effort"),
                    prompt_fingerprint=call_meta.get("prompt_fingerprint"),
                    usage=call_meta.get("usage") if isinstance(call_meta.get("usage"), dict) else {},
                    skip_reason=call_meta.get("skip_reason"),
                    extra={
                        "model_tier": call_meta.get("model_tier"),
                        "response_id": call_meta.get("response_id"),
                    },
                )
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
        _log_workflow_checkpoint(
            settings,
            event="task_planned",
            task=task,
            success=True,
            summary=task.latest_summary or "Task planned and awaiting approval.",
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
        _log_workflow_checkpoint(
            settings,
            event="task_planned",
            task=task,
            success=False,
            summary=f"Planning failed: {exc}",
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
        _log_workflow_checkpoint(
            settings,
            event="task_packet_created",
            task=task,
            success=True,
            summary="Task packet created from task-labeled issue.",
        )

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
            _log_workflow_checkpoint(
                settings,
                event="task_approved",
                task=task,
                success=False,
                summary=task.latest_summary or "Task approval blocked by worker selection.",
                skip_reason="guarded_path_block",
            )
            return
        task.approval_state = APPROVAL_APPROVED
        task.status = TASK_STATUS_APPROVED
        task.latest_summary = f"Approved via {source}; worker={_worker_display_name(task)}"
        task.updated_at = _utc_now()
        _save(session, task)
        mark_slice_approved(session, task=task)
        notify_discord(f"Task approved: {task.github_repo}#{task.github_issue_number} -> {_worker_display_name(task)}")
        _log_workflow_checkpoint(
            settings,
            event="task_approved",
            task=task,
            success=True,
            summary=task.latest_summary or "Task approved.",
        )
        dispatch_task_if_ready(session, settings=settings, task=task)
        return

    task.approval_state = APPROVAL_REJECTED
    task.status = TASK_STATUS_BLOCKED
    task.latest_summary = f"Rejected via {source}"
    task.updated_at = _utc_now()
    _save(session, task)
    notify_discord(f"Task rejected: {task.github_repo}#{task.github_issue_number}")
    _log_workflow_checkpoint(
        settings,
        event="task_approved",
        task=task,
        success=False,
        summary=task.latest_summary or "Task rejected.",
        skip_reason="task_not_approved",
    )


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
        _log_workflow_checkpoint(
            settings,
            event="issue_dispatch_attempted",
            task=task,
            success=False,
            summary="Dispatch skipped because task is not approved.",
            skip_reason="task_not_approved",
        )
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
    run.linkage_tag = _build_run_linkage_tag(task=task, run=run)
    run.dispatch_payload_json = json.dumps(
        build_dispatch_payload_summary(settings, task, linkage_tag=run.linkage_tag),
        ensure_ascii=False,
    )
    run.updated_at = _utc_now()
    _save(session, run)
    _log_workflow_checkpoint(
        settings,
        event="pr_linkage_tag_generated",
        task=task,
        run=run,
        success=True,
        summary=f"Generated deterministic PR linkage tag: {run.linkage_tag}",
    )
    _log_workflow_checkpoint(
        settings,
        event="pr_linkage_tag_injected_dispatch_payload",
        task=task,
        run=run,
        success=True,
        summary=(
            f"Injected linkage tag into Copilot dispatch payload: {run.linkage_tag}"
            if run.linkage_tag
            else "Linkage tag missing; dispatch payload injection skipped."
        ),
        skip_reason=None if run.linkage_tag else "missing_linkage_tag",
    )

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

    result = dispatch_task_to_github_copilot(settings=settings, task=task, linkage_tag=run.linkage_tag)
    _log_workflow_checkpoint(
        settings,
        event="issue_dispatch_attempted",
        task=task,
        run=run,
        success=True,
        summary="Dispatch requested via GitHub Copilot assignment APIs.",
        auth_lane="dispatch_user_token",
        api_type="GraphQL+REST",
    )
    result_summary = (
        f"{result.summary} "
        f"(dispatch_state={result.state}, api_status={result.api_status_code if result.api_status_code is not None else 'n/a'})"
    )
    if result.accepted:
        dispatch_observed_at = _utc_now()
        run.status = RUN_STATUS_AWAITING_WORKER_START
        run.last_summary = result_summary
        run.github_dispatch_id = result.dispatch_id
        run.github_dispatch_url = result.dispatch_url
        run.updated_at = dispatch_observed_at

        task.status = TASK_STATUS_AWAITING_WORKER_START
        task.latest_summary = f"{result_summary} Awaiting worker-start signal."
        task.updated_at = dispatch_observed_at
        _save(session, run, task)
        link_run_to_slice(session, run=run, task=task)
        notify_discord(
            "Task dispatched: "
            f"{task.github_repo}#{task.github_issue_number} -> {_worker_display_name(task)} "
            f"({dispatch_mode_summary})"
        )
        _log_workflow_checkpoint(
            settings,
            event="issue_dispatch_succeeded",
            task=task,
            run=run,
            success=True,
            summary=result_summary,
            auth_lane="dispatch_user_token",
            api_type="GraphQL+REST",
        )
        _log_workflow_checkpoint(
            settings,
            event="pr_discovery_search_attempted",
            task=task,
            run=run,
            success=True,
            summary=(
                f"Attempting post-dispatch PR discovery with primary exact linkage tag check: {run.linkage_tag}"
            ),
            auth_lane="dispatch_user_token",
            api_type="REST",
        )
        selected, reason, scored_candidates = _discover_post_dispatch_pr_candidate(
            settings=settings,
            task=task,
            run=run,
            dispatch_observed_at=dispatch_observed_at,
        )
        _log_workflow_checkpoint(
            settings,
            event="pr_discovery_candidates_observed",
            task=task,
            run=run,
            success=bool(scored_candidates),
            summary=(
                "PR discovery candidates: "
                + json.dumps(
                    [
                        {
                            "pr_number": entry["pr"].get("number"),
                            "score": entry["score"],
                            "reasons": entry["reasons"],
                            "created_at": entry["created_at"],
                            "authoritative": bool(entry.get("authoritative")),
                            "heuristic_authoritative": bool(entry.get("heuristic_authoritative")),
                            "exact_linkage_tag_present": bool(entry.get("exact_linkage_tag_present")),
                        }
                        for entry in scored_candidates
                    ],
                    ensure_ascii=False,
                )
            ),
            skip_reason=None if scored_candidates else reason,
        )
        if run.linkage_tag and reason == "linked_heuristic":
            _log_workflow_checkpoint(
                settings,
                event="pr_discovery_fallback_to_heuristic",
                task=task,
                run=run,
                success=True,
                summary=(
                    f"No exact linkage-tag match found for {run.linkage_tag}; "
                    "falling back to heuristic PR discovery."
                ),
                skip_reason="linkage_tag_missing_in_candidate_prs",
            )
        if reason == "linked_exact_linkage_tag":
            _log_workflow_checkpoint(
                settings,
                event="pr_discovery_exact_linkage_tag_matched",
                task=task,
                run=run,
                success=True,
                summary=f"Exact linkage-tag match found for {run.linkage_tag}.",
            )
        if selected is None:
            if run.linkage_tag and reason in {
                "linkage_tag_missing_in_candidate_prs",
                "candidate_prs_ambiguous",
                "authoritative_linkage_not_found",
            }:
                _log_workflow_checkpoint(
                    settings,
                    event="pr_discovery_fallback_to_heuristic",
                    task=task,
                    run=run,
                    success=False,
                    summary=(
                        f"Exact linkage tag {run.linkage_tag} not matched; "
                        "heuristic PR discovery did not find a safe single candidate."
                    ),
                    skip_reason=reason,
                )
            _log_workflow_checkpoint(
                settings,
                event="pr_discovery_linkage_skipped",
                task=task,
                run=run,
                success=False,
                summary=f"Post-dispatch PR discovery did not produce PR linkage: {reason}.",
                skip_reason=reason,
            )
            return

        selected_pr = selected["pr"]
        pr_number = selected_pr.get("number")
        if not isinstance(pr_number, int):
            _log_workflow_checkpoint(
                settings,
                event="pr_discovery_linkage_skipped",
                task=task,
                run=run,
                success=False,
                summary="Selected PR candidate lacked integer PR number.",
                skip_reason="candidate_missing_pr_number",
            )
            return
        run.github_pr_number = pr_number
        run.github_pr_url = str(selected_pr.get("html_url") or "") or None
        run.github_pr_node_id = str(selected_pr.get("node_id") or "") or None
        run.status = RUN_STATUS_PR_OPENED
        discovery_path = "exact_linkage_tag" if reason == "linked_exact_linkage_tag" else "heuristic"
        run.last_summary = (
            f"Worker-start evidence linked from post-dispatch PR discovery via {discovery_path}: "
            f"PR #{pr_number} ({', '.join(selected['reasons']) or 'scored'})"
        )
        run.updated_at = _utc_now()
        task.status = TASK_STATUS_PR_OPENED
        task.latest_summary = run.last_summary
        task.updated_at = _utc_now()
        _save(session, run, task)
        link_run_to_slice(session, run=run, task=task)
        _log_workflow_checkpoint(
            settings,
            event="pr_discovery_linked",
            task=task,
            run=run,
            success=True,
            summary=(
                f"Linked post-dispatch PR #{pr_number} using path={discovery_path} "
                f"reasons={selected['reasons']}."
            ),
        )
        _log_workflow_checkpoint(
            settings,
            event="worker_start_evidence_upgraded",
            task=task,
            run=run,
            success=True,
            summary="Worker-start evidence upgraded from weak/awaiting to authoritative PR linkage.",
        )
        pr_is_draft = bool(selected_pr.get("draft"))
        _log_workflow_checkpoint(
            settings,
            event="ready_for_review_scheduling_decision",
            task=task,
            run=run,
            success=True,
            summary=(
                "PR is draft; deferring ready-for-review until substantive evidence satisfies readiness predicate."
                if pr_is_draft
                else "PR already non-draft; ready-for-review mutation skipped."
            ),
            skip_reason="pr_not_ready_for_review_yet" if pr_is_draft else "already_ready_for_review",
        )
        _run_governor_loop(
            session,
            settings=settings,
            task=task,
            run=run,
            pr_payload={
                "number": pr_number,
                "draft": pr_is_draft,
                "state": str(selected_pr.get("state") or "open"),
                "requested_reviewers": selected_pr.get("requested_reviewers") or [],
            },
            event_key=f"governor:dispatch_pr_discovery:{run.id}:{pr_number}:{_utc_now().isoformat()}",
            checks_passed=False,
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
        _log_workflow_checkpoint(
            settings,
            event="issue_dispatch_failed",
            task=task,
            run=run,
            success=False,
            summary=result_summary,
            skip_reason="auth_lane_unavailable",
            auth_lane="dispatch_user_token",
            api_type="GraphQL+REST",
        )
        return

    run.status = RUN_STATUS_FAILED
    run.last_summary = result_summary
    run.updated_at = _utc_now()

    task.status = TASK_STATUS_FAILED
    task.latest_summary = result_summary
    task.updated_at = _utc_now()
    _save(session, run, task)
    _log_workflow_checkpoint(
        settings,
        event="issue_dispatch_failed",
        task=task,
        run=run,
        success=False,
        summary=result_summary,
        auth_lane="dispatch_user_token",
        api_type="GraphQL+REST",
    )
    link_run_to_slice(session, run=run, task=task)
    notify_discord(
        "Task failed to dispatch: "
        f"{task.github_repo}#{task.github_issue_number} -> {_worker_display_name(task)} "
        f"({dispatch_mode_summary})"
    )


def _timeline_event_matches_pr(
    event: dict[str, Any],
    *,
    github_repo: str,
    pr_number: int | None,
    pr_head_sha: str | None,
) -> bool:
    if pr_number is None and not pr_head_sha:
        return False
    normalized_repo = github_repo.strip().lower()
    event_pr = event.get("pull_request") if isinstance(event.get("pull_request"), dict) else {}
    event_pr_number = event_pr.get("number") if isinstance(event_pr.get("number"), int) else None
    event_pr_base = event_pr.get("base") if isinstance(event_pr.get("base"), dict) else {}
    event_pr_repo_obj = event_pr_base.get("repo") if isinstance(event_pr_base.get("repo"), dict) else {}
    event_pr_repo = str(event_pr_repo_obj.get("full_name") or "").strip().lower()
    if pr_number is not None and event_pr_number == pr_number and (not event_pr_repo or event_pr_repo == normalized_repo):
        return True

    source = event.get("source") if isinstance(event.get("source"), dict) else {}
    source_issue = source.get("issue") if isinstance(source.get("issue"), dict) else {}
    source_pr = source_issue.get("pull_request") if isinstance(source_issue.get("pull_request"), dict) else {}
    source_pr_number = source_issue.get("number") if isinstance(source_issue.get("number"), int) else None
    source_linked_pr_number = source_pr.get("number") if isinstance(source_pr.get("number"), int) else None
    source_repo = str(source_issue.get("repository_url") or "").strip().lower()
    if source_repo and source_repo.endswith(f"/repos/{normalized_repo}"):
        source_repo = normalized_repo
    source_repo_matches = not source_repo or source_repo == normalized_repo
    if pr_number is not None and pr_number in {source_pr_number, source_linked_pr_number} and source_repo_matches:
        return True

    if pr_head_sha:
        commit_id = str(event.get("commit_id") or "").strip()
        if commit_id and commit_id.lower() == pr_head_sha.lower():
            return True
    return False


def _task_for_authoritative_pr_association(
    session: Session,
    *,
    settings: Settings,
    github_repo: str,
    pr_payload: dict[str, Any],
) -> tuple[TaskPacket | None, str]:
    pr_number = pr_payload.get("number") if isinstance(pr_payload.get("number"), int) else None
    head = pr_payload.get("head") if isinstance(pr_payload.get("head"), dict) else {}
    pr_head_sha = str(head.get("sha") or "").strip() or None

    candidate_query = (
        select(TaskPacket)
        .where(TaskPacket.github_repo == github_repo)
        .where(
            TaskPacket.status.in_(
                [
                    TASK_STATUS_AWAITING_WORKER_START,
                    TASK_STATUS_DISPATCH_REQUESTED,
                    TASK_STATUS_MANUAL_DISPATCH_NEEDED,
                    TASK_STATUS_WORKING,
                ]
            )
        )
        .order_by(TaskPacket.updated_at.desc())
        .limit(8)
    )
    candidates = list(session.exec(candidate_query).all())
    if not candidates:
        return None, "candidate_pool_empty"

    candidate_by_issue_number = {
        candidate.github_issue_number: candidate
        for candidate in candidates
        if isinstance(candidate.github_issue_number, int)
    }
    candidate_issue_numbers = sorted(candidate_by_issue_number.keys())
    graphql_reason: str | None = None
    _log_workflow_checkpoint(
        settings,
        event="pr_authoritative_candidates",
        task=candidates[0] if candidates else None,
        success=bool(candidate_issue_numbers),
        auth_lane="dispatch_user_token" if has_dispatch_auth(settings) else "missing",
        api_type="graphql",
        skip_reason=None if candidate_issue_numbers else "candidate_pool_empty",
        summary=f"authoritative candidate issue numbers={candidate_issue_numbers or []}",
    )
    if pr_number is not None and candidate_by_issue_number:
        linked_issue_numbers, lookup_summary = lookup_pr_linked_issue_numbers(
            settings=settings,
            repo=github_repo,
            pr_number=pr_number,
        )
        if not linked_issue_numbers:
            if lookup_summary.startswith("Dispatch auth failure:"):
                return None, "dispatch_auth_missing"
            if lookup_summary.startswith("PR association failure:"):
                graphql_reason = "graphql_link_lookup_error"
            else:
                graphql_reason = "graphql_link_lookup_empty"
        matched_by_graph = [
            candidate_by_issue_number[issue_number]
            for issue_number in sorted(linked_issue_numbers)
            if issue_number in candidate_by_issue_number
        ]
        _log_workflow_checkpoint(
            settings,
            event="pr_authoritative_graphql_intersection",
            task=matched_by_graph[0] if matched_by_graph else (candidates[0] if candidates else None),
            success=bool(matched_by_graph),
            auth_lane="dispatch_user_token",
            api_type="graphql",
            skip_reason=None if matched_by_graph else "candidate_intersection_empty",
            summary=(
                f"{lookup_summary}; candidates={candidate_issue_numbers}; "
                f"intersection={[task.github_issue_number for task in matched_by_graph]}"
            ),
        )
        if len(matched_by_graph) == 1:
            return matched_by_graph[0], "authoritative_match"
        if len(matched_by_graph) > 1:
            return None, "candidate_match_ambiguous"
        if linked_issue_numbers:
            graphql_reason = "candidate_intersection_empty"

    matched_tasks: list[TaskPacket] = []
    for candidate in candidates:
        issue_number = candidate.github_issue_number
        if issue_number is None:
            continue
        events, _ = list_issue_timeline_events(
            settings=settings,
            repo=github_repo,
            issue_number=issue_number,
            limit=30,
        )
        if not events:
            continue
        if any(
            _timeline_event_matches_pr(
                event,
                github_repo=github_repo,
                pr_number=pr_number,
                pr_head_sha=pr_head_sha,
            )
            for event in events
        ):
            matched_tasks.append(candidate)

    if len(matched_tasks) != 1:
        if graphql_reason:
            return None, graphql_reason
        return None, "timeline_match_missing_or_ambiguous"
    return matched_tasks[0], "timeline_match"


def _task_for_pr_payload(
    session: Session,
    *,
    settings: Settings,
    github_repo: str,
    pr_payload: dict[str, Any],
) -> tuple[TaskPacket | None, str]:
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
                return linked_task, "existing_run_match"

    body = str(pr_payload.get("body") or "")
    title = str(pr_payload.get("title") or "")
    refs = ISSUE_REF_RE.findall(f"{title}\n{body}")
    for issue_ref in refs:
        task = _get_task_by_repo_issue(session, github_repo=github_repo, github_issue_number=int(issue_ref))
        if task is not None:
            return task, "explicit_ref_match"
    task, authoritative_reason = _task_for_authoritative_pr_association(
        session,
        settings=settings,
        github_repo=github_repo,
        pr_payload=pr_payload,
    )
    if task is not None:
        return task, authoritative_reason
    if refs:
        return None, f"explicit_ref_miss;{authoritative_reason}"
    return None, authoritative_reason


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
        _record_openai_telemetry(
            session,
            task=task,
            run=run,
            stage=str(openai_meta.get("stage") or "reviewer"),
            action="summarize_work_update",
            outcome=str(openai_meta.get("outcome") or "success"),
            execution_mode=EXECUTION_MODE_STANDARD,
            model=openai_meta.get("model"),
            reasoning_effort=openai_meta.get("reasoning_effort"),
            event_key=event_key,
            prompt_fingerprint=openai_meta.get("prompt_fingerprint"),
            usage=openai_meta.get("usage") if isinstance(openai_meta.get("usage"), dict) else {},
            skip_reason=openai_meta.get("skip_reason"),
            extra={"model_tier": openai_meta.get("model_tier"), "response_id": openai_meta.get("response_id")},
        )
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
        return True

    task, association_reason = _task_for_pr_payload(
        session,
        settings=settings,
        github_repo=github_repo,
        pr_payload=pr,
    )
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
                mark_pr_association_pending(
                    session,
                    task=candidate,
                    summary=(
                        f"external PR activity seen but no internal linkage for PR #{pr_number} "
                        f"(action={action or 'unknown'}, reason={association_reason})"
                    ),
                )
                _log_workflow_checkpoint(
                    settings,
                    event="pr_webhook_association_pending",
                    task=candidate,
                    success=False,
                    auth_lane="dispatch_user_token" if has_dispatch_auth(settings) else "missing",
                    api_type="graphql+timeline",
                    skip_reason=association_reason,
                    summary=f"PR webhook could not link task for PR #{pr_number}; marked retryable pending",
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
    run.github_pr_url = str(pr.get("html_url") or "") or None
    run.github_pr_node_id = str(pr.get("node_id") or "") or None

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
    fallback_reason: str | None = None
    inspected_pr_number: int | None = None
    inspected_pr_url: str | None = None
    inspected_pr_node_id: str | None = None
    if run is None:
        for pr_number in pr_numbers:
            inspection = inspect_pull_request(settings=settings, repo=github_repo, pr_number=pr_number)
            if not inspection.ok:
                fallback_reason = (
                    f"workflow activity seen but no linked run for PR(s) {pr_numbers}; "
                    f"PR #{pr_number} inspection failed: {inspection.summary}"
                )
                continue
            parsed_tag = parse_orch_linkage_tag(inspection.body)
            if parsed_tag is None:
                fallback_reason = (
                    f"workflow activity seen but no linked run for PR(s) {pr_numbers}; "
                    f"PR #{pr_number} missing or invalid ORCH-LINK stamp"
                )
                continue
            recovered_run = session.get(AgentRun, parsed_tag["run_id"])
            recovered_task = session.get(TaskPacket, parsed_tag["task_id"])
            if recovered_run is None or recovered_task is None:
                fallback_reason = (
                    f"workflow activity seen but no linked run for PR(s) {pr_numbers}; "
                    f"PR #{pr_number} ORCH-LINK points to missing run/task (run={parsed_tag['run_id']}, task={parsed_tag['task_id']})"
                )
                continue
            validation_errors: list[str] = []
            if recovered_run.id != parsed_tag["run_id"]:
                validation_errors.append("run_id_mismatch")
            if recovered_task.id != parsed_tag["task_id"]:
                validation_errors.append("task_id_mismatch")
            if recovered_run.task_packet_id != recovered_task.id:
                validation_errors.append("run_task_relation_mismatch")
            if recovered_task.github_issue_number != parsed_tag["issue_number"]:
                validation_errors.append("issue_number_mismatch")
            if recovered_run.github_repo != github_repo or recovered_task.github_repo != github_repo:
                validation_errors.append("repo_mismatch")
            if validation_errors:
                fallback_reason = (
                    f"workflow activity seen but no linked run for PR(s) {pr_numbers}; "
                    f"PR #{pr_number} ORCH-LINK rejected ({', '.join(validation_errors)})"
                )
                continue
            run = recovered_run
            inspected_pr_number = pr_number
            inspected_pr_url = inspection.html_url
            inspected_pr_node_id = inspection.node_id
            break

    if run is None:
        candidate_runs = list(
            session.exec(
                select(AgentRun)
                .where(AgentRun.github_repo == github_repo)
                .where(
                    AgentRun.status.in_(
                        [
                            RUN_STATUS_AWAITING_WORKER_START,
                            RUN_STATUS_DISPATCH_REQUESTED,
                            RUN_STATUS_DISPATCHED,
                            RUN_STATUS_MANUAL_DISPATCH_NEEDED,
                            RUN_STATUS_QUEUED,
                            RUN_STATUS_WORKING,
                            RUN_STATUS_PR_OPENED,
                            RUN_STATUS_AWAITING_REVIEW,
                        ]
                    )
                )
                .order_by(AgentRun.updated_at.desc())
                .limit(5)
            ).all()
        )
        summary = fallback_reason or f"workflow activity seen but no linked run for PR(s) {pr_numbers}"
        for candidate_run in candidate_runs:
            candidate_task = session.get(TaskPacket, candidate_run.task_packet_id)
            if candidate_task is None:
                continue
            mark_pr_association_pending(session, task=candidate_task, summary=summary)
        return False

    task = session.get(TaskPacket, run.task_packet_id)
    if task is None:
        return False
    if run.github_repo != github_repo or task.github_repo != github_repo:
        mark_reconciliation_incomplete(
            session,
            task=task,
            summary=(
                f"workflow repo mismatch for run/task recovery: event_repo={github_repo}, "
                f"run_repo={run.github_repo}, task_repo={task.github_repo}"
            ),
        )
        return False

    if not run.github_pr_number and inspected_pr_number is not None:
        run.github_pr_number = inspected_pr_number
    if not run.github_pr_url and inspected_pr_url:
        run.github_pr_url = inspected_pr_url
    if not run.github_pr_node_id and inspected_pr_node_id:
        run.github_pr_node_id = inspected_pr_node_id

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
    linked_pr_number = run.github_pr_number if isinstance(run.github_pr_number, int) else (pr_numbers[0] if pr_numbers else None)
    successful_head_sha = _workflow_run_linked_head_sha(workflow_run, preferred_pr_number=linked_pr_number)

    if status == "completed" and conclusion == "success":
        previous_state = _load_governor_state(run)
        if successful_head_sha:
            previous_state["last_observed_pr_head_sha"] = successful_head_sha
            previous_state["last_successful_checks_head_sha"] = successful_head_sha
            previous_state["last_successful_checks_at"] = _utc_now().isoformat()
            previous_state["last_checks_passed"] = True
            previous_state["last_check_conclusion"] = "success"
            _save_governor_state(run, previous_state)
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
                "head_sha": successful_head_sha,
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
