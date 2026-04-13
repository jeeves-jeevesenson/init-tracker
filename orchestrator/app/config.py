import os

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


ENV_FILE = os.getenv(
    "ORCHESTRATOR_ENV_FILE",
    "/opt/init-orchestrator/secrets/orchestrator.env",
)


class Settings(BaseSettings):
    openai_api_key: str
    discord_webhook_url: str
    github_webhook_secret: str = Field(validation_alias="GH_WEBHOOK_SECRET")
    openai_webhook_secret: str
    orchestrator_secret_key: str

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
