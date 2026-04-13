from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from .models import RunEvent


def _new_run_event(
    *,
    source: str,
    external_id: str | None,
    event_type: str,
    action: str | None,
    status: str,
    summary: str,
    payload_json: str,
) -> RunEvent:
    return RunEvent(
        source=source,
        external_id=external_id,
        event_type=event_type,
        action=action,
        status=status,
        summary=summary,
        payload_json=payload_json,
        updated_at=datetime.now(timezone.utc),
    )


def get_run_event_by_external_id(
    session: Session,
    *,
    source: str,
    external_id: str,
) -> RunEvent | None:
    query = (
        select(RunEvent)
        .where(RunEvent.source == source)
        .where(RunEvent.external_id == external_id)
        .limit(1)
    )
    return session.exec(query).first()


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
    event = _new_run_event(
        source=source,
        external_id=external_id,
        event_type=event_type,
        action=action,
        status=status,
        summary=summary,
        payload_json=payload_json,
    )
    session.add(event)
    session.commit()
    session.refresh(event)
    return event


def record_run_event_idempotent(
    session: Session,
    *,
    source: str,
    external_id: str | None,
    event_type: str,
    action: str | None,
    status: str,
    summary: str,
    payload_json: str,
) -> tuple[RunEvent, bool]:
    event = _new_run_event(
        source=source,
        external_id=external_id,
        event_type=event_type,
        action=action,
        status=status,
        summary=summary,
        payload_json=payload_json,
    )
    session.add(event)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        if not external_id:
            raise
        existing = get_run_event_by_external_id(
            session,
            source=source,
            external_id=external_id,
        )
        if existing is None:
            raise
        return existing, False
    session.refresh(event)
    return event, True


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
