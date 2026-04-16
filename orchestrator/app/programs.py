from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Callable

import httpx
from sqlmodel import Session, select

from .config import Settings
from .github_auth import build_dispatch_auth_headers, has_dispatch_auth
from .github_dispatch import merge_pr
from .models import (
    APPROVAL_APPROVED,
    BLOCKER_AUTO_MERGE_DISABLED,
    BLOCKER_ESCALATED_TO_HUMAN,
    BLOCKER_REVIEW_EVIDENCE_MISSING,
    BLOCKER_WAITING_FOR_CHECKS,
    BLOCKER_WAITING_FOR_ISSUE_CREATION,
    BLOCKER_WAITING_FOR_MERGE,
    BLOCKER_WAITING_FOR_PERMISSIONS,
    BLOCKER_WAITING_FOR_PR_READY,
    BLOCKER_WAITING_FOR_REPO_SETTING,
    PROGRAM_STATUS_ACTIVE,
    PROGRAM_STATUS_BLOCKED,
    PROGRAM_STATUS_COMPLETED,
    PROGRAM_STATUS_ESCALATED,
    RUN_STATUS_BLOCKED,
    RUN_STATUS_COMPLETED,
    RUN_STATUS_FAILED,
    RUN_STATUS_WORKER_FAILED,
    AgentRun,
    Program,
    ProgramSlice,
    SLICE_STATUS_APPROVED,
    SLICE_STATUS_AUDIT_REQUESTED,
    SLICE_STATUS_BLOCKED,
    SLICE_STATUS_COMPLETED,
    SLICE_STATUS_ESCALATED,
    SLICE_STATUS_IN_PROGRESS,
    SLICE_STATUS_PLANNED,
    SLICE_STATUS_REVISION_REQUESTED,
    SLICE_STATUS_WAITING_FOR_MERGE,
    TaskPacket,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _json_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    return []


def _json_obj(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def _parse_json(value: str | None) -> Any:
    if not value:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return None


def _parse_list_json(value: str | None) -> list[Any]:
    parsed = _parse_json(value)
    return parsed if isinstance(parsed, list) else []


def _parse_dict_json(value: str | None) -> dict[str, Any]:
    parsed = _parse_json(value)
    return parsed if isinstance(parsed, dict) else {}


def _save(session: Session, *objects: Any) -> None:
    for obj in objects:
        session.add(obj)
    session.commit()
    for obj in objects:
        session.refresh(obj)


def _default_slice_from_internal_plan(internal_plan: dict[str, Any], worker_brief: dict[str, Any]) -> dict[str, Any]:
    return {
        "slice_number": 1,
        "milestone_key": "M1",
        "slice_type": "implementation",
        "title": "Initial implementation slice",
        "objective": worker_brief.get("objective") or internal_plan.get("objective") or "",
        "acceptance_criteria": worker_brief.get("acceptance_criteria") or internal_plan.get("acceptance_criteria") or [],
        "non_goals": worker_brief.get("non_goals") or internal_plan.get("non_goals") or [],
        "expected_file_zones": internal_plan.get("repo_areas") or [],
        "continuation_hint": "",
    }


def _normalized_program_slices(
    *,
    internal_plan: dict[str, Any],
    worker_brief: dict[str, Any],
    program_plan: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    plan = _json_obj(program_plan or {})
    slices = _json_list(plan.get("slices"))
    normalized: list[dict[str, Any]] = []
    for index, raw in enumerate(slices, start=1):
        if not isinstance(raw, dict):
            continue
        objective = str(raw.get("objective") or "").strip()
        if not objective:
            continue
        normalized.append(
            {
                "slice_number": int(raw.get("slice_number") or index),
                "milestone_key": str(raw.get("milestone_key") or f"M{index}"),
                "slice_type": str(raw.get("slice_type") or "implementation"),
                "title": str(raw.get("title") or f"Slice {index}"),
                "objective": objective,
                "acceptance_criteria": _json_list(raw.get("acceptance_criteria")),
                "non_goals": _json_list(raw.get("non_goals")),
                "expected_file_zones": _json_list(raw.get("expected_file_zones")),
                "continuation_hint": str(raw.get("continuation_hint") or ""),
            }
        )
    if normalized:
        return sorted(normalized, key=lambda item: item["slice_number"])
    return [_default_slice_from_internal_plan(internal_plan, worker_brief)]


def ensure_program_for_task(
    session: Session,
    *,
    settings: Settings,
    task: TaskPacket,
    internal_plan: dict[str, Any],
    worker_brief: dict[str, Any],
    program_plan: dict[str, Any] | None,
) -> tuple[Program, ProgramSlice]:
    if task.program_id:
        program = session.get(Program, task.program_id)
        if program is None:
            task.program_id = None
        else:
            slice_record = session.get(ProgramSlice, task.program_slice_id or 0) if task.program_slice_id else None
            if slice_record is not None:
                return program, slice_record

    program = Program(
        github_repo=task.github_repo,
        root_issue_number=task.github_issue_number,
        title=task.title,
        normalized_goal=str((program_plan or {}).get("normalized_program_objective") or internal_plan.get("objective") or ""),
        definition_of_done_json=json.dumps(
            _json_list((program_plan or {}).get("definition_of_done")) or _json_list(worker_brief.get("acceptance_criteria")),
            ensure_ascii=False,
        ),
        non_goals_json=json.dumps(
            _json_list((program_plan or {}).get("non_goals")) or _json_list(internal_plan.get("non_goals")),
            ensure_ascii=False,
        ),
        milestones_json=json.dumps(_json_list((program_plan or {}).get("milestones")), ensure_ascii=False),
        status=PROGRAM_STATUS_ACTIVE,
        latest_summary="Program created from approved objective",
        auto_plan=settings.program_auto_plan,
        auto_approve=settings.program_auto_approve,
        auto_dispatch=settings.program_auto_dispatch,
        auto_continue=settings.program_auto_continue,
        auto_merge=settings.program_auto_merge,
        max_revision_attempts=max(1, settings.program_max_revision_attempts),
    )
    _save(session, program)

    slices = _normalized_program_slices(internal_plan=internal_plan, worker_brief=worker_brief, program_plan=program_plan)
    first_slice: ProgramSlice | None = None
    for item in slices:
        slice_record = ProgramSlice(
            program_id=program.id or 0,
            slice_number=item["slice_number"],
            milestone_key=item["milestone_key"],
            slice_type=item["slice_type"],
            title=item["title"],
            objective=item["objective"],
            acceptance_criteria_json=json.dumps(item["acceptance_criteria"], ensure_ascii=False),
            non_goals_json=json.dumps(item["non_goals"], ensure_ascii=False),
            expected_file_zones_json=json.dumps(item["expected_file_zones"], ensure_ascii=False),
            continuation_hint=item["continuation_hint"] or None,
            status=SLICE_STATUS_PLANNED,
        )
        _save(session, slice_record)
        if first_slice is None:
            first_slice = slice_record

    if first_slice is None:
        first_slice = ProgramSlice(
            program_id=program.id or 0,
            slice_number=1,
            milestone_key="M1",
            title="Initial implementation slice",
            objective=worker_brief.get("objective") or internal_plan.get("objective") or "",
            acceptance_criteria_json=json.dumps(_json_list(worker_brief.get("acceptance_criteria")), ensure_ascii=False),
            non_goals_json=json.dumps(_json_list(worker_brief.get("non_goals")), ensure_ascii=False),
            expected_file_zones_json=json.dumps(_json_list(internal_plan.get("repo_areas")), ensure_ascii=False),
            status=SLICE_STATUS_PLANNED,
        )
        _save(session, first_slice)

    task.program_id = program.id
    task.program_slice_id = first_slice.id
    task.task_kind = "program_slice"
    task.updated_at = _utc_now()
    first_slice.task_packet_id = task.id
    first_slice.status = SLICE_STATUS_APPROVED if task.approval_state == APPROVAL_APPROVED else SLICE_STATUS_PLANNED
    first_slice.updated_at = _utc_now()
    _save(session, task, first_slice)
    return program, first_slice


def link_run_to_slice(session: Session, *, run: AgentRun, task: TaskPacket) -> None:
    if not task.program_slice_id:
        return
    run.program_id = task.program_id
    run.program_slice_id = task.program_slice_id
    run.updated_at = _utc_now()
    slice_record = session.get(ProgramSlice, task.program_slice_id)
    if slice_record is not None:
        slice_record.latest_run_id = run.id
        if run.github_pr_number:
            slice_record.linked_pr_number = run.github_pr_number
        if slice_record.status in {SLICE_STATUS_PLANNED, SLICE_STATUS_APPROVED, SLICE_STATUS_REVISION_REQUESTED}:
            slice_record.status = SLICE_STATUS_IN_PROGRESS
        slice_record.updated_at = _utc_now()
        _save(session, run, slice_record)
        return
    _save(session, run)


def mark_slice_approved(session: Session, *, task: TaskPacket) -> None:
    if not task.program_slice_id:
        return
    slice_record = session.get(ProgramSlice, task.program_slice_id)
    if slice_record is None:
        return
    if slice_record.status in {SLICE_STATUS_COMPLETED, SLICE_STATUS_ESCALATED}:
        return
    slice_record.status = SLICE_STATUS_APPROVED
    slice_record.updated_at = _utc_now()
    _save(session, slice_record)


def list_programs(session: Session, *, limit: int = 50) -> list[Program]:
    query = select(Program).order_by(Program.updated_at.desc()).limit(limit)
    return list(session.exec(query).all())


def get_program_with_slices(session: Session, program_id: int) -> tuple[Program | None, list[ProgramSlice]]:
    program = session.get(Program, program_id)
    if program is None:
        return None, []
    query = (
        select(ProgramSlice)
        .where(ProgramSlice.program_id == program_id)
        .order_by(ProgramSlice.slice_number.asc(), ProgramSlice.created_at.asc())
    )
    return program, list(session.exec(query).all())


def program_to_dict(program: Program, slices: list[ProgramSlice]) -> dict[str, Any]:
    current_slice = next((item for item in slices if item.slice_number == program.current_slice_number), None)
    return {
        "id": program.id,
        "github_repo": program.github_repo,
        "root_issue_number": program.root_issue_number,
        "title": program.title,
        "normalized_goal": program.normalized_goal,
        "definition_of_done": _parse_list_json(program.definition_of_done_json),
        "non_goals": _parse_list_json(program.non_goals_json),
        "milestones": _parse_list_json(program.milestones_json),
        "status": program.status,
        "current_slice_number": program.current_slice_number,
        "latest_decision": program.latest_decision,
        "latest_summary": program.latest_summary,
        "wait_reason": _derive_wait_reason(program),
        "auto_policy": {
            "auto_plan": program.auto_plan,
            "auto_approve": program.auto_approve,
            "auto_dispatch": program.auto_dispatch,
            "auto_continue": program.auto_continue,
            "auto_merge": program.auto_merge,
            "max_revision_attempts": program.max_revision_attempts,
        },
        "blocker_state": _parse_dict_json(program.blocker_state_json),
        "audit_state": _parse_dict_json(program.audit_state_json),
        "current_slice": slice_to_dict(current_slice) if current_slice else None,
        "slices": [slice_to_dict(item) for item in slices],
        "created_at": program.created_at.isoformat() if program.created_at else None,
        "updated_at": program.updated_at.isoformat() if program.updated_at else None,
    }


def slice_to_dict(slice_record: ProgramSlice | None) -> dict[str, Any] | None:
    if slice_record is None:
        return None
    return {
        "id": slice_record.id,
        "program_id": slice_record.program_id,
        "slice_number": slice_record.slice_number,
        "milestone_key": slice_record.milestone_key,
        "slice_type": slice_record.slice_type,
        "title": slice_record.title,
        "objective": slice_record.objective,
        "acceptance_criteria": _parse_list_json(slice_record.acceptance_criteria_json),
        "non_goals": _parse_list_json(slice_record.non_goals_json),
        "expected_file_zones": _parse_list_json(slice_record.expected_file_zones_json),
        "continuation_hint": slice_record.continuation_hint,
        "status": slice_record.status,
        "task_packet_id": slice_record.task_packet_id,
        "latest_run_id": slice_record.latest_run_id,
        "linked_pr_number": slice_record.linked_pr_number,
        "revision_count": slice_record.revision_count,
        "last_decision": slice_record.last_decision,
        "last_decision_summary": slice_record.last_decision_summary,
        "decision_artifact": _parse_dict_json(slice_record.decision_artifact_json),
        "created_at": slice_record.created_at.isoformat() if slice_record.created_at else None,
        "updated_at": slice_record.updated_at.isoformat() if slice_record.updated_at else None,
    }


def _next_slice(session: Session, *, program_id: int, current_slice_number: int) -> ProgramSlice | None:
    query = (
        select(ProgramSlice)
        .where(ProgramSlice.program_id == program_id)
        .where(ProgramSlice.slice_number > current_slice_number)
        .order_by(ProgramSlice.slice_number.asc())
        .limit(1)
    )
    return session.exec(query).first()


def _get_slice_by_number(session: Session, *, program_id: int, slice_number: int) -> ProgramSlice | None:
    query = (
        select(ProgramSlice)
        .where(ProgramSlice.program_id == program_id)
        .where(ProgramSlice.slice_number == slice_number)
        .order_by(ProgramSlice.created_at.asc())
        .limit(1)
    )
    return session.exec(query).first()


def _merge_policy_allows_auto_merge(artifact: dict[str, Any], *, checks_passed: bool) -> bool:
    if artifact.get("merge_recommendation") != "merge_ready":
        return False
    if not checks_passed:
        return False
    if artifact.get("status") in {"drifted", "blocked"}:
        return False
    risk_findings = _json_list(artifact.get("risk_findings"))
    return not any("high" in str(item).lower() for item in risk_findings)


def _continuation_guard_failures(*, run: AgentRun, artifact: dict[str, Any], checks_passed: bool) -> list[str]:
    failures: list[str] = []
    if not run.github_pr_number:
        failures.append("missing github_pr_number")
    if run.status in {RUN_STATUS_BLOCKED, RUN_STATUS_WORKER_FAILED, RUN_STATUS_FAILED}:
        failures.append(f"run status is non-successful ({run.status})")
    if artifact.get("merge_recommendation") != "merge_ready":
        failures.append("merge_recommendation is not merge_ready")
    if artifact.get("status") in {"drifted", "blocked"}:
        failures.append(f"artifact status is {artifact.get('status')}")
    risk_findings = _json_list(artifact.get("risk_findings"))
    if any("empty pr" in str(item).lower() or "zero" in str(item).lower() for item in risk_findings):
        failures.append("artifact indicates empty/zero-diff PR")
    return failures


def _attempt_pr_merge(
    session: Session,
    *,
    settings: Settings,
    program: Program,
    pr_number: int,
) -> None:
    """Best-effort attempt to merge a PR on GitHub when auto_merge is enabled.

    Surfaces a structured blocker on the program record when the merge fails due to
    missing token permissions or a repository setting that disallows direct merge.
    A failure here does NOT block the orchestrator state machine — the program still
    advances internally; the human or GitHub auto-merge can complete the actual merge.
    """
    success, message = merge_pr(settings=settings, repo=program.github_repo, pr_number=pr_number)
    if success:
        program.blocker_state_json = json.dumps({}, ensure_ascii=False)
        program.updated_at = _utc_now()
        _save(session, program)
        return

    # Classify the failure for the operator.
    lower = message.lower()
    if "403" in message or "forbidden" in lower or "permission" in lower:
        reason = BLOCKER_WAITING_FOR_PERMISSIONS
        summary = (
            f"Auto-merge attempted but governor auth lacks required permissions to merge PR #{pr_number}. "
            "Grant contents:write to the configured governor identity and ensure 'Allow auto-merge' is enabled "
            "in repository Settings > General."
        )
    elif "405" in message or "not allowed" in lower or "protected" in lower:
        reason = BLOCKER_WAITING_FOR_REPO_SETTING
        summary = (
            f"Auto-merge attempted but the repository does not allow direct merge for PR #{pr_number}. "
            "Enable 'Allow auto-merge' in repository Settings > General, or check branch protection rules."
        )
    elif "422" in message and ("auto-merge" in lower or "automerge" in lower):
        reason = BLOCKER_AUTO_MERGE_DISABLED
        summary = (
            f"Auto-merge is not enabled on PR #{pr_number}. "
            "Enable 'Allow auto-merge' in repository Settings > General."
        )
    else:
        reason = BLOCKER_WAITING_FOR_MERGE
        summary = f"Auto-merge attempted but failed for PR #{pr_number}: {message}"

    program.blocker_state_json = json.dumps(
        {
            "reason": reason,
            "pr_number": pr_number,
            "detail": message,
        },
        ensure_ascii=False,
    )
    program.latest_summary = summary
    program.updated_at = _utc_now()
    _save(session, program)


def _create_github_issue_for_slice(
    *,
    settings: Settings,
    repo: str,
    title: str,
    body: str,
) -> int | None:
    if not has_dispatch_auth(settings):
        return None
    api_base = settings.github_api_url.rstrip("/")
    headers = build_dispatch_auth_headers(settings)
    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.post(
                f"{api_base}/repos/{repo}/issues",
                headers=headers,
                json={"title": title, "body": body},
            )
            if response.status_code >= 400:
                return None
            payload = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
            number = payload.get("number")
            return int(number) if isinstance(number, int) else None
    except Exception:
        return None


def _create_followup_task_for_slice(
    session: Session,
    *,
    settings: Settings,
    program: Program,
    slice_record: ProgramSlice,
    prior_task: TaskPacket,
) -> TaskPacket | None:
    title = f"[Program #{program.id}] Slice {slice_record.slice_number}: {slice_record.title}"
    body = (
        f"Program objective:\n{program.normalized_goal}\n\n"
        f"Slice objective:\n{slice_record.objective}\n\n"
        "Acceptance criteria:\n"
        + "\n".join(f"- {item}" for item in _parse_list_json(slice_record.acceptance_criteria_json))
    )
    issue_number = _create_github_issue_for_slice(settings=settings, repo=program.github_repo, title=title, body=body)
    if issue_number is None:
        return None
    task = TaskPacket(
        github_repo=prior_task.github_repo,
        github_issue_number=issue_number,
        github_issue_node_id=None,
        title=title,
        raw_body=body,
        internal_plan_json=prior_task.internal_plan_json,
        worker_brief_json=prior_task.worker_brief_json,
        normalized_task_text=prior_task.normalized_task_text,
        acceptance_criteria_json=slice_record.acceptance_criteria_json,
        validation_commands_json=prior_task.validation_commands_json,
        selected_custom_agent=prior_task.selected_custom_agent,
        worker_selection_mode=prior_task.worker_selection_mode,
        worker_selection_reason=prior_task.worker_selection_reason,
        worker_override_label=prior_task.worker_override_label,
        recommended_worker=prior_task.recommended_worker,
        recommended_scope_class=prior_task.recommended_scope_class,
        status="approved" if program.auto_approve else "awaiting_approval",
        approval_state="approved" if program.auto_approve else "pending",
        latest_summary=f"Auto-created for program slice {slice_record.slice_number}",
        program_id=program.id,
        program_slice_id=slice_record.id,
        task_kind="program_slice",
    )
    _save(session, task)
    slice_record.task_packet_id = task.id
    slice_record.status = SLICE_STATUS_APPROVED if program.auto_approve else SLICE_STATUS_PLANNED
    slice_record.updated_at = _utc_now()
    _save(session, slice_record)
    return task


def apply_reviewer_decision(
    session: Session,
    *,
    settings: Settings,
    task: TaskPacket,
    run: AgentRun,
    event_key: str,
    checks_passed: bool,
    dispatch_fn: Callable[[TaskPacket], None] | None = None,
) -> str | None:
    if not task.program_id or not task.program_slice_id:
        return None
    program = session.get(Program, task.program_id)
    slice_record = session.get(ProgramSlice, task.program_slice_id)
    if program is None or slice_record is None:
        return None
    artifact = _parse_dict_json(run.review_artifact_json)
    decision = str(artifact.get("decision") or "").strip().lower()
    if not decision:
        return None
    if slice_record.last_decision_event_key == event_key and slice_record.last_decision == decision:
        return decision

    run.continuation_decision = decision
    run.updated_at = _utc_now()
    slice_record.last_decision = decision
    slice_record.last_decision_summary = str(artifact.get("summary") or "")
    slice_record.last_decision_event_key = event_key
    slice_record.decision_artifact_json = json.dumps(artifact, ensure_ascii=False)
    if run.github_pr_number:
        slice_record.linked_pr_number = run.github_pr_number
    slice_record.updated_at = _utc_now()
    program.latest_decision = decision
    program.updated_at = _utc_now()

    if decision == "escalate":
        slice_record.status = SLICE_STATUS_ESCALATED
        program.status = PROGRAM_STATUS_ESCALATED
        program.blocker_state_json = json.dumps(
            {"reason": BLOCKER_ESCALATED_TO_HUMAN, "slice_id": slice_record.id, "run_id": run.id},
            ensure_ascii=False,
        )
        program.latest_summary = "Reviewer requested escalation"
        _save(session, run, slice_record, program)
        return decision

    if decision == "audit":
        slice_record.status = SLICE_STATUS_AUDIT_REQUESTED
        next_slice_number = slice_record.slice_number + 1
        audit_slice = _get_slice_by_number(
            session,
            program_id=program.id or 0,
            slice_number=next_slice_number,
        )
        if audit_slice is None:
            audit_slice = ProgramSlice(
                program_id=program.id or 0,
                slice_number=next_slice_number,
                milestone_key=slice_record.milestone_key,
                slice_type="audit",
                title=f"Audit: {slice_record.title}",
                objective=str(artifact.get("audit_recommendation") or "Run targeted audit and stabilization checks."),
                acceptance_criteria_json=json.dumps(_json_list(artifact.get("acceptance_assessment")), ensure_ascii=False),
                non_goals_json=json.dumps([], ensure_ascii=False),
                expected_file_zones_json=json.dumps(_json_list(artifact.get("scope_alignment")), ensure_ascii=False),
                continuation_hint=str(artifact.get("next_slice_hint") or ""),
                status=SLICE_STATUS_PLANNED,
            )
            _save(session, run, slice_record, audit_slice)
        else:
            if audit_slice.slice_type == "audit":
                audit_slice.milestone_key = slice_record.milestone_key
                audit_slice.title = f"Audit: {slice_record.title}"
                audit_slice.objective = str(artifact.get("audit_recommendation") or "Run targeted audit and stabilization checks.")
                audit_slice.acceptance_criteria_json = json.dumps(
                    _json_list(artifact.get("acceptance_assessment")),
                    ensure_ascii=False,
                )
                audit_slice.expected_file_zones_json = json.dumps(
                    _json_list(artifact.get("scope_alignment")),
                    ensure_ascii=False,
                )
                audit_slice.continuation_hint = str(artifact.get("next_slice_hint") or "")
                audit_slice.updated_at = _utc_now()
            _save(session, run, slice_record, audit_slice)
        program.audit_state_json = json.dumps({"last_audit_slice_id": audit_slice.id}, ensure_ascii=False)
        program.latest_summary = "Audit slice created from reviewer decision"
        _save(session, program)
        return decision

    if decision == "revise":
        slice_record.revision_count += 1
        if slice_record.revision_count > max(1, program.max_revision_attempts):
            slice_record.status = SLICE_STATUS_ESCALATED
            program.status = PROGRAM_STATUS_ESCALATED
            program.blocker_state_json = json.dumps(
                {"reason": "max_revisions_exceeded", "slice_id": slice_record.id, "run_id": run.id},
                ensure_ascii=False,
            )
            program.latest_summary = "Escalated after repeated revision cycles"
            _save(session, run, slice_record, program)
            return "escalate"
        slice_record.status = SLICE_STATUS_REVISION_REQUESTED
        program.latest_summary = f"Revision requested for slice {slice_record.slice_number}"
        _save(session, run, slice_record, program)
        return decision

    if decision in {"continue", "complete"}:
        if not checks_passed and run.status != RUN_STATUS_COMPLETED:
            program.blocker_state_json = json.dumps(
                {
                    "reason": BLOCKER_WAITING_FOR_CHECKS,
                    "slice_id": slice_record.id,
                    "run_id": run.id,
                    "linked_pr_number": run.github_pr_number,
                },
                ensure_ascii=False,
            )
            program.latest_summary = "Continuation deferred: waiting for successful checks"
            _save(session, run, slice_record, program)
            return decision

        guard_failures = _continuation_guard_failures(run=run, artifact=artifact, checks_passed=checks_passed)
        if guard_failures:
            slice_record.status = SLICE_STATUS_BLOCKED
            program.status = PROGRAM_STATUS_BLOCKED
            program.blocker_state_json = json.dumps(
                {
                    "reason": BLOCKER_REVIEW_EVIDENCE_MISSING,
                    "slice_id": slice_record.id,
                    "run_id": run.id,
                    "missing_evidence": guard_failures,
                    "linked_pr_number": run.github_pr_number,
                },
                ensure_ascii=False,
            )
            run.last_summary = (
                "Continuation rejected: "
                f"{'; '.join(guard_failures)}"
            )
            run.updated_at = _utc_now()
            program.latest_summary = "Continuation blocked: required merge/review evidence is missing or contradictory"
            _save(session, run, slice_record, program)
            return "blocked"

        if run.status == RUN_STATUS_COMPLETED:
            slice_record.status = SLICE_STATUS_COMPLETED
        elif program.auto_merge and _merge_policy_allows_auto_merge(artifact, checks_passed=checks_passed):
            slice_record.status = SLICE_STATUS_COMPLETED
        else:
            slice_record.status = SLICE_STATUS_WAITING_FOR_MERGE
            program.blocker_state_json = json.dumps(
                {
                    "reason": BLOCKER_WAITING_FOR_MERGE,
                    "slice_id": slice_record.id,
                    "linked_pr_number": slice_record.linked_pr_number,
                },
                ensure_ascii=False,
            )
            program.latest_summary = "Waiting for merge before continuing program slices"
            _save(session, run, slice_record, program)
            return decision

        continuation = _complete_slice_and_advance(
            session,
            settings=settings,
            program=program,
            slice_record=slice_record,
            task=task,
            run=run,
            dispatch_fn=dispatch_fn,
        )

        # After advancing internally, attempt to actually merge the PR on GitHub.
        # This is done after _complete_slice_and_advance so that any merge failure
        # blocker is set last and is visible in program state.  A failure does NOT
        # roll back the internal advancement; the human or GitHub can complete the
        # actual merge and the webhook handler will be a no-op on an already-completed slice.
        if (
            program.auto_merge
            and _merge_policy_allows_auto_merge(artifact, checks_passed=checks_passed)
            and run.github_pr_number
            and run.status != RUN_STATUS_COMPLETED
        ):
            # Refresh program from session after _complete_slice_and_advance saved it
            session.refresh(program)
            _attempt_pr_merge(
                session,
                settings=settings,
                program=program,
                pr_number=run.github_pr_number,
            )

        return continuation

    program.latest_summary = f"Unhandled reviewer decision: {decision}"
    _save(session, run, slice_record, program)
    return decision


def _complete_slice_and_advance(
    session: Session,
    *,
    settings: Settings,
    program: Program,
    slice_record: ProgramSlice,
    task: TaskPacket,
    run: AgentRun,
    dispatch_fn: Callable[[TaskPacket], None] | None = None,
) -> str:
    """Mark the current slice complete and advance the program to the next slice.

    Returns the effective continuation decision string ("continue" or "complete").
    """
    slice_record.status = SLICE_STATUS_COMPLETED
    next_slice = _next_slice(session, program_id=program.id or 0, current_slice_number=slice_record.slice_number)
    if next_slice is None:
        program.status = PROGRAM_STATUS_COMPLETED
        program.current_slice_number = slice_record.slice_number
        program.blocker_state_json = json.dumps({}, ensure_ascii=False)
        program.latest_summary = "Program completed"
        _save(session, run, slice_record, program)
        return "complete"

    program.current_slice_number = next_slice.slice_number
    program.status = PROGRAM_STATUS_ACTIVE
    program.blocker_state_json = json.dumps({}, ensure_ascii=False)
    program.latest_summary = f"Advancing to slice {next_slice.slice_number}"
    next_slice.status = SLICE_STATUS_PLANNED if next_slice.task_packet_id is None else next_slice.status
    _save(session, run, slice_record, next_slice, program)

    if program.auto_continue and next_slice.task_packet_id is None:
        task_record = _create_followup_task_for_slice(
            session,
            settings=settings,
            program=program,
            slice_record=next_slice,
            prior_task=task,
        )
        if task_record is None:
            next_slice.status = SLICE_STATUS_BLOCKED
            program.status = PROGRAM_STATUS_BLOCKED
            program.blocker_state_json = json.dumps(
                {"reason": BLOCKER_WAITING_FOR_ISSUE_CREATION, "slice_id": next_slice.id},
                ensure_ascii=False,
            )
            program.latest_summary = "Failed to auto-create issue for next slice"
            _save(session, next_slice, program)
        elif dispatch_fn is not None and program.auto_dispatch:
            dispatch_fn(task_record)
    return "continue"


def advance_program_on_pr_merge(
    session: Session,
    *,
    settings: Settings,
    task: TaskPacket,
    run: AgentRun,
    dispatch_fn: Callable[[TaskPacket], None] | None = None,
) -> None:
    """Called after a PR is merged.  Advances the program if the slice was waiting for merge.

    This is the critical link that makes merge-and-continue actually fire.  It is idempotent:
    if the slice is already completed (e.g., auto-merge path), it is a no-op.
    """
    if not task.program_id or not task.program_slice_id:
        return
    program = session.get(Program, task.program_id)
    slice_record = session.get(ProgramSlice, task.program_slice_id)
    if program is None or slice_record is None:
        return

    # If the slice was explicitly waiting for the merge, advance now.
    if slice_record.status == SLICE_STATUS_WAITING_FOR_MERGE:
        _complete_slice_and_advance(
            session,
            settings=settings,
            program=program,
            slice_record=slice_record,
            task=task,
            run=run,
            dispatch_fn=dispatch_fn,
        )
        return

    # If the slice was still in-progress (reviewer hadn't run yet) but the PR was merged,
    # mark the slice complete and advance so the program doesn't stall.
    if slice_record.status in {SLICE_STATUS_IN_PROGRESS, SLICE_STATUS_APPROVED, SLICE_STATUS_PLANNED}:
        _complete_slice_and_advance(
            session,
            settings=settings,
            program=program,
            slice_record=slice_record,
            task=task,
            run=run,
            dispatch_fn=dispatch_fn,
        )


def _derive_wait_reason(program: Program) -> str | None:
    """Return a human-readable wait reason derived from program/blocker state."""
    blocker = _parse_dict_json(program.blocker_state_json)
    if blocker:
        return str(blocker.get("reason") or "")
    if program.status == PROGRAM_STATUS_BLOCKED:
        return "blocked"
    if program.status == PROGRAM_STATUS_ESCALATED:
        return BLOCKER_ESCALATED_TO_HUMAN
    return None
