from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from openai import OpenAI
from sqlmodel import Session

from .config import get_settings
from .db import get_session
from .discord_notify import notify_discord
from .runs import record_run_event

router = APIRouter(prefix="/openai", tags=["openai"])


def _extract_value(obj: Any, key: str) -> Any:
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _verify_openai_webhook(raw_body_text: str, headers: dict[str, str], secret: str):
    settings = get_settings()
    client = OpenAI(api_key=settings.openai_api_key or "not-required-for-webhook-verification")
    webhook_api = getattr(client, "webhooks", None)
    if webhook_api is None:
        raise RuntimeError("OpenAI SDK webhook verification is unavailable")

    if hasattr(webhook_api, "unwrap"):
        return webhook_api.unwrap(raw_body_text, headers, secret=secret)

    if hasattr(webhook_api, "verify_signature"):
        webhook_api.verify_signature(raw_body_text, headers, secret=secret)
        return json.loads(raw_body_text)

    raise RuntimeError("OpenAI SDK webhook verification methods are unavailable")


@router.post("/webhook")
async def openai_webhook(request: Request, session: Session = Depends(get_session)):
    settings = get_settings()
    if not settings.openai_webhook_secret:
        raise HTTPException(status_code=503, detail="openai webhook secret is not configured")

    body = await request.body()
    raw_body_text = body.decode("utf-8")
    headers = dict(request.headers)
    try:
        event = _verify_openai_webhook(raw_body_text, headers, settings.openai_webhook_secret)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=403, detail="invalid openai webhook signature") from exc

    event_type = _extract_value(event, "type") or "unknown"
    external_id = _extract_value(event, "id")
    action = _extract_value(event, "status")

    record_run_event(
        session,
        source="openai",
        external_id=external_id,
        event_type=event_type,
        action=action,
        status="recorded",
        summary=f"OpenAI event recorded: {event_type}",
        payload_json=raw_body_text,
    )
    notify_discord(f"Orchestrator: OpenAI event recorded ({event_type}).")
    return {"ok": True, "source": "openai", "event_type": event_type}
