from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from .copilot_identity import DOCUMENTED_COPILOT_ASSIGNEE_LOGIN

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

    github_api_token: str | None = Field(default=None, alias="GITHUB_API_TOKEN")
    github_api_url: str = Field(default="https://api.github.com", alias="GITHUB_API_URL")

    default_repo_owner: str | None = Field(default=None, alias="DEFAULT_REPO_OWNER")
    default_repo_name: str | None = Field(default=None, alias="DEFAULT_REPO_NAME")

    task_label: str = Field(default="agent:task", alias="TASK_LABEL")
    task_approved_label: str = Field(default="agent:approved", alias="TASK_APPROVED_LABEL")

    copilot_dispatch_assignee: str = Field(
        default=DOCUMENTED_COPILOT_ASSIGNEE_LOGIN,
        alias="COPILOT_DISPATCH_ASSIGNEE",
    )
    copilot_target_branch: str = Field(default="main", alias="COPILOT_TARGET_BRANCH")
    copilot_target_repo: str | None = Field(default=None, alias="COPILOT_TARGET_REPO")
    copilot_custom_instructions: str | None = Field(default=None, alias="COPILOT_CUSTOM_INSTRUCTIONS")
    copilot_custom_agent: str | None = Field(default=None, alias="COPILOT_CUSTOM_AGENT")
    copilot_model: str | None = Field(default=None, alias="COPILOT_MODEL")

    openai_planning_model: str = Field(default="gpt-4.1-mini", alias="OPENAI_PLANNING_MODEL")
    openai_review_model: str = Field(default="gpt-4.1-mini", alias="OPENAI_REVIEW_MODEL")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
