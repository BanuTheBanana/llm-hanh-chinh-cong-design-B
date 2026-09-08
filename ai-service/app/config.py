from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

MockMode = Literal["success", "error", "timeout"]


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables."""

    app_env: str = "development"
    log_level: str = "INFO"
    llm_provider: str = "mock"
    mock_mode: MockMode = "success"
    mock_latency_ms: int = Field(default=10, ge=0, le=60_000)
    mock_timeout_seconds: float = Field(default=5.0, gt=0, le=300)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
