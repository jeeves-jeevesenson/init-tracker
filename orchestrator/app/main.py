from fastapi import FastAPI
from .config import settings

app = FastAPI(title="Init Tracker Orchestrator")


@app.get("/healthz")
async def healthz() -> dict:
    return {
        "ok": True,
        "openai_key_loaded": bool(settings.openai_api_key),
        "discord_webhook_loaded": bool(settings.discord_webhook_url),
        "github_webhook_secret_loaded": bool(settings.github_webhook_secret),
        "openai_webhook_secret_loaded": bool(settings.openai_webhook_secret),
    }
