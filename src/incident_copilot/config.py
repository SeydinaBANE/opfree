from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    llm_provider: Literal["anthropic", "bedrock", "vertex"] = "anthropic"
    llm_model: str = "claude-sonnet-4-6"

    anthropic_api_key: SecretStr = SecretStr("")

    aws_region: str = "us-east-1"
    aws_profile: str = "default"

    google_cloud_project: str = ""
    google_cloud_region: str = "us-central1"

    max_agent_iterations: int = 15
    max_total_tokens: int = 200_000
    agent_timeout_seconds: int = 300

    memory_db_path: str = "incidents.db"

    log_level: str = "INFO"
