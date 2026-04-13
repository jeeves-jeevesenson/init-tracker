from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_ENV_FILE = Path("/opt/init-orchestrator/secrets/orchestrator.env")
DEFAULT_DATABASE_URL = "sqlite:////opt/init-orchestrator/state/orchestrator.db"


def _load_env_file() -> None:
    env_file = Path(os.getenv("ORCHESTRATOR_ENV_FILE", str(DEFAULT_ENV_FILE)))
    if env_file.is_file():
        load_dotenv(env_file, override=False)


_load_env_file()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    discord_webhook_url: str | None = Field(default=None, alias="DISCORD_WEBHOOK_URL")
    gh_webhook_secret: str | None = Field(default=None, alias="GH_WEBHOOK_SECRET")
    openai_webhook_secret: str | None = Field(default=None, alias="OPENAI_WEBHOOK_SECRET")
    orchestrator_secret_key: str | None = Field(default=None, alias="ORCHESTRATOR_SECRET_KEY")
    database_url: str = Field(default=DEFAULT_DATABASE_URL, alias="DATABASE_URL")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
