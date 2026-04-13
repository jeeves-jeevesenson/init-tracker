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
RUN_STATUS_PR_OPENED = "pr_opened"
RUN_STATUS_AWAITING_REVIEW = "awaiting_review"
RUN_STATUS_MANUAL_DISPATCH_NEEDED = "manual_dispatch_needed"
RUN_STATUS_BLOCKED = "blocked"
RUN_STATUS_COMPLETED = "completed"
RUN_STATUS_FAILED = "failed"


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
    github_issue_node_id: str | None = Field(default=None)
    title: str = Field(default="")
    raw_body: str = Field(default="")
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
    provider: str = Field(default="github_copilot", index=True)
    github_repo: str = Field(index=True)
    github_issue_number: int = Field(index=True)
    github_pr_number: int | None = Field(default=None, index=True)
    github_dispatch_id: str | None = Field(default=None, index=True)
    github_dispatch_url: str | None = Field(default=None)
    selected_custom_agent: str | None = Field(default=None, index=True)
    worker_selection_mode: str | None = Field(default=None, index=True)
    dispatch_payload_json: str | None = Field(default=None)
    status: str = Field(default=RUN_STATUS_QUEUED, index=True)
    last_summary: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=utc_now, index=True)
    updated_at: datetime = Field(default_factory=utc_now, index=True)
