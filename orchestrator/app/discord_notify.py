from __future__ import annotations

import logging

import httpx

from .config import get_settings

logger = logging.getLogger(__name__)


def notify_discord(message: str) -> None:
    settings = get_settings()
    webhook_url = settings.discord_webhook_url
    if not webhook_url:
        return
    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.post(webhook_url, json={"content": message})
            response.raise_for_status()
    except Exception as exc:
        logger.warning("discord notification failed: %s", exc)
