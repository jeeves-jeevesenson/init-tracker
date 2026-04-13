from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


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
