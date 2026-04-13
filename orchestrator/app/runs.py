from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlmodel import Session, select

from .models import RunEvent


def record_run_event(
    session: Session,
    *,
    source: str,
    external_id: str | None,
    event_type: str,
    action: str | None,
    status: str,
    summary: str,
    payload_json: str,
) -> RunEvent:
    event = RunEvent(
        source=source,
        external_id=external_id,
        event_type=event_type,
        action=action,
        status=status,
        summary=summary,
        payload_json=payload_json,
        updated_at=datetime.now(timezone.utc),
    )
    session.add(event)
    session.commit()
    session.refresh(event)
    return event


def list_recent_runs(session: Session, *, limit: int = 50) -> list[RunEvent]:
    query = select(RunEvent).order_by(RunEvent.created_at.desc()).limit(limit)
    return list(session.exec(query).all())


def run_to_dict(run: RunEvent) -> dict[str, Any]:
    return {
        "id": run.id,
        "source": run.source,
        "external_id": run.external_id,
        "event_type": run.event_type,
        "action": run.action,
        "status": run.status,
        "summary": run.summary,
        "payload_json": run.payload_json,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "updated_at": run.updated_at.isoformat() if run.updated_at else None,
    }
