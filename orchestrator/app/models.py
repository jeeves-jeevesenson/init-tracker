from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


TASK_STATUS_RECEIVED = "received"
TASK_STATUS_PLANNING = "planning"
TASK_STATUS_AWAITING_APPROVAL = "awaiting_approval"
TASK_STATUS_APPROVED = "approved"
TASK_STATUS_DISPATCH_REQUESTED = "dispatch_requested"
TASK_STATUS_AWAITING_WORKER_START = "awaiting_worker_start"
TASK_STATUS_DISPATCHED = "dispatched"
TASK_STATUS_WORKING = "working"
TASK_STATUS_WORKER_FAILED = "worker_failed"
TASK_STATUS_PR_OPENED = "pr_opened"
TASK_STATUS_MANUAL_DISPATCH_NEEDED = "manual_dispatch_needed"
TASK_STATUS_BLOCKED = "blocked"
TASK_STATUS_COMPLETED = "completed"
TASK_STATUS_FAILED = "failed"

APPROVAL_PENDING = "pending"
APPROVAL_APPROVED = "approved"
APPROVAL_REJECTED = "rejected"

RUN_STATUS_QUEUED = "queued"
RUN_STATUS_DISPATCH_REQUESTED = "dispatch_requested"
RUN_STATUS_AWAITING_WORKER_START = "awaiting_worker_start"
RUN_STATUS_DISPATCHED = "dispatched"
RUN_STATUS_WORKING = "working"
RUN_STATUS_WORKER_FAILED = "worker_failed"
RUN_STATUS_PR_OPENED = "pr_opened"
RUN_STATUS_AWAITING_REVIEW = "awaiting_review"
RUN_STATUS_MANUAL_DISPATCH_NEEDED = "manual_dispatch_needed"
RUN_STATUS_BLOCKED = "blocked"
RUN_STATUS_COMPLETED = "completed"
RUN_STATUS_FAILED = "failed"

PROGRAM_STATUS_PLANNING = "planning"
PROGRAM_STATUS_ACTIVE = "active"
PROGRAM_STATUS_BLOCKED = "blocked"
PROGRAM_STATUS_ESCALATED = "escalated"
PROGRAM_STATUS_COMPLETED = "completed"
PROGRAM_STATUS_FAILED = "failed"

SLICE_STATUS_PLANNED = "planned"
SLICE_STATUS_APPROVED = "approved"
SLICE_STATUS_IN_PROGRESS = "in_progress"
SLICE_STATUS_AWAITING_REVIEW = "awaiting_review"
SLICE_STATUS_REVISION_REQUESTED = "revision_requested"
SLICE_STATUS_AUDIT_REQUESTED = "audit_requested"
SLICE_STATUS_WAITING_FOR_MERGE = "waiting_for_merge"
SLICE_STATUS_COMPLETED = "completed"
SLICE_STATUS_ESCALATED = "escalated"
SLICE_STATUS_BLOCKED = "blocked"

BLOCKER_WAITING_FOR_TRUSTED_CONFIRM = "waiting_for_trusted_confirm"
BLOCKER_WAITING_FOR_PR_READY = "waiting_for_pr_ready"
BLOCKER_WAITING_FOR_WORKFLOW_APPROVAL = "waiting_for_workflow_approval"
BLOCKER_WAITING_FOR_CHECKS = "waiting_for_checks"
BLOCKER_WAITING_FOR_MERGE = "waiting_for_merge"
BLOCKER_REVIEW_EVIDENCE_MISSING = "review_evidence_missing"
BLOCKER_WAITING_FOR_ISSUE_CREATION = "waiting_for_issue_creation_capability"
BLOCKER_ESCALATED_TO_HUMAN = "escalated_to_human"
BLOCKER_WAITING_FOR_PERMISSIONS = "waiting_for_permissions"
BLOCKER_WAITING_FOR_REPO_SETTING = "waiting_for_repo_setting"
BLOCKER_AUTO_MERGE_DISABLED = "auto_merge_disabled"


class Program(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    github_repo: str = Field(index=True)
    root_issue_number: int = Field(index=True)
    title: str = Field(default="")
    normalized_goal: str = Field(default="")
    definition_of_done_json: str = Field(default="[]")
    non_goals_json: str = Field(default="[]")
    milestones_json: str = Field(default="[]")
    status: str = Field(default=PROGRAM_STATUS_PLANNING, index=True)
    current_slice_number: int = Field(default=1, index=True)
    auto_plan: bool = Field(default=True)
    auto_approve: bool = Field(default=True)
    auto_dispatch: bool = Field(default=True)
    auto_continue: bool = Field(default=True)
    auto_merge: bool = Field(default=False)
    max_revision_attempts: int = Field(default=2)
    merge_review_policy_json: str = Field(default="{}")
    blocker_state_json: str = Field(default="{}")
    audit_state_json: str = Field(default="{}")
    latest_decision: str | None = Field(default=None, index=True)
    latest_summary: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=utc_now, index=True)
    updated_at: datetime = Field(default_factory=utc_now, index=True)


class ProgramSlice(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    program_id: int = Field(foreign_key="program.id", index=True)
    slice_number: int = Field(index=True)
    milestone_key: str | None = Field(default=None, index=True)
    slice_type: str = Field(default="implementation", index=True)
    title: str = Field(default="")
    objective: str = Field(default="")
    acceptance_criteria_json: str = Field(default="[]")
    non_goals_json: str = Field(default="[]")
    expected_file_zones_json: str = Field(default="[]")
    continuation_hint: str | None = Field(default=None)
    status: str = Field(default=SLICE_STATUS_PLANNED, index=True)
    task_packet_id: int | None = Field(default=None, foreign_key="taskpacket.id", index=True)
    latest_run_id: int | None = Field(default=None, foreign_key="agentrun.id", index=True)
    linked_pr_number: int | None = Field(default=None, index=True)
    revision_count: int = Field(default=0)
    decision_artifact_json: str | None = Field(default=None)
    last_decision: str | None = Field(default=None, index=True)
    last_decision_summary: str | None = Field(default=None)
    last_decision_event_key: str | None = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=utc_now, index=True)
    updated_at: datetime = Field(default_factory=utc_now, index=True)


class RunEvent(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    source: str = Field(index=True)
    external_id: str | None = Field(default=None, index=True)
    event_type: str = Field(index=True)
    action: str | None = Field(default=None)
    status: str = Field(default="received", index=True)
    summary: str | None = Field(default=None)
    payload_json: str = Field(default="{}")
    created_at: datetime = Field(default_factory=utc_now, index=True)
    updated_at: datetime = Field(default_factory=utc_now, index=True)


class TaskPacket(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    github_repo: str = Field(index=True)
    github_issue_number: int = Field(index=True)
    program_id: int | None = Field(default=None, foreign_key="program.id", index=True)
    program_slice_id: int | None = Field(default=None, foreign_key="programslice.id", index=True)
    task_kind: str = Field(default="single_task", index=True)
    github_issue_node_id: str | None = Field(default=None)
    title: str = Field(default="")
    raw_body: str = Field(default="")
    internal_plan_json: str | None = Field(default=None)
    worker_brief_json: str | None = Field(default=None)
    normalized_task_text: str | None = Field(default=None)
    acceptance_criteria_json: str | None = Field(default=None)
    validation_commands_json: str | None = Field(default=None)
    selected_custom_agent: str | None = Field(default=None, index=True)
    worker_selection_mode: str | None = Field(default=None, index=True)
    worker_selection_reason: str | None = Field(default=None)
    worker_override_label: str | None = Field(default=None)
    recommended_worker: str | None = Field(default=None)
    recommended_scope_class: str | None = Field(default=None)
    status: str = Field(default=TASK_STATUS_RECEIVED, index=True)
    approval_state: str = Field(default=APPROVAL_PENDING, index=True)
    priority: int | None = Field(default=None, index=True)
    latest_summary: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=utc_now, index=True)
    updated_at: datetime = Field(default_factory=utc_now, index=True)


class AgentRun(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    task_packet_id: int = Field(foreign_key="taskpacket.id", index=True)
    program_id: int | None = Field(default=None, foreign_key="program.id", index=True)
    program_slice_id: int | None = Field(default=None, foreign_key="programslice.id", index=True)
    provider: str = Field(default="github_copilot", index=True)
    github_repo: str = Field(index=True)
    github_issue_number: int = Field(index=True)
    github_pr_number: int | None = Field(default=None, index=True)
    github_dispatch_id: str | None = Field(default=None, index=True)
    github_dispatch_url: str | None = Field(default=None)
    selected_custom_agent: str | None = Field(default=None, index=True)
    worker_selection_mode: str | None = Field(default=None, index=True)
    dispatch_payload_json: str | None = Field(default=None)
    review_artifact_json: str | None = Field(default=None)
    continuation_decision: str | None = Field(default=None, index=True)
    status: str = Field(default=RUN_STATUS_QUEUED, index=True)
    last_summary: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=utc_now, index=True)
    updated_at: datetime = Field(default_factory=utc_now, index=True)
