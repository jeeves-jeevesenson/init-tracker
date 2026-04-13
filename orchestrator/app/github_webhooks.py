from __future__ import annotations

import hashlib
import hmac
import json

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session

from .config import get_settings
from .db import get_session
from .discord_notify import notify_discord
from .runs import record_run_event_idempotent
from .tasks import (
    process_issue_comment_event,
    process_issue_event,
    process_pull_request_event,
    process_workflow_run_event,
)

router = APIRouter(prefix="/github", tags=["github"])


def _verify_github_signature(body: bytes, signature_header: str | None, secret: str | None) -> bool:
    if not signature_header or not secret:
        return False
    expected = "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header)


@router.post("/webhook")
async def github_webhook(request: Request, session: Session = Depends(get_session)):
    settings = get_settings()
    body = await request.body()
    signature_header = request.headers.get("X-Hub-Signature-256")
    if not _verify_github_signature(body, signature_header, settings.gh_webhook_secret):
        raise HTTPException(status_code=403, detail="invalid github webhook signature")

    try:
        payload = json.loads(body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="invalid JSON payload") from exc

    event_type = request.headers.get("X-GitHub-Event", "unknown")
    external_id = request.headers.get("X-GitHub-Delivery")
    action = payload.get("action") if isinstance(payload, dict) else None

    if event_type == "ping":
        _, is_new = record_run_event_idempotent(
            session,
            source="github",
            external_id=external_id,
            event_type=event_type,
            action=action,
            status="pong",
            summary="GitHub webhook ping accepted",
            payload_json=body.decode("utf-8"),
        )
        if is_new:
            notify_discord("Orchestrator: GitHub ping accepted.")
        return {"ok": True, "message": "pong", "duplicate": not is_new}

    _, is_new = record_run_event_idempotent(
        session,
        source="github",
        external_id=external_id,
        event_type=event_type,
        action=action,
        status="recorded",
        summary=f"GitHub event recorded: {event_type}",
        payload_json=body.decode("utf-8"),
    )
    if not is_new:
        return {"ok": True, "source": "github", "event_type": event_type, "duplicate": True}

    if isinstance(payload, dict):
        if event_type == "issues":
            process_issue_event(session, settings=settings, payload=payload, action=action)
        elif event_type == "issue_comment":
            process_issue_comment_event(session, settings=settings, payload=payload, action=action)
        elif event_type == "pull_request":
            process_pull_request_event(session, settings=settings, payload=payload, action=action)
        elif event_type == "workflow_run":
            process_workflow_run_event(session, settings=settings, payload=payload, action=action)

    return {"ok": True, "source": "github", "event_type": event_type, "duplicate": False}
