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
    grounded_provider: str = "template"
    mock_mode: MockMode = "success"
    mock_latency_ms: int = Field(default=10, ge=0, le=60_000)
    mock_timeout_seconds: float = Field(default=5.0, gt=0, le=300)
    local_llm_base_url: str = "http://localhost:8080/v1"
    local_llm_model: str = "Qwen3-1.7B"
    local_llm_timeout_seconds: float = Field(default=30.0, gt=0, le=300)
    local_llm_context: int = Field(default=4096, ge=512, le=32768)
    local_llm_max_prompt_characters: int = Field(default=8000, ge=1000, le=64000)
    local_llm_max_output_tokens: int = Field(default=500, ge=32, le=2048)
    local_llm_temperature: float = Field(default=0.2, gt=0, le=2)
    local_llm_top_p: float = Field(default=0.8, gt=0, le=1)
    local_llm_top_k: int = Field(default=20, ge=1, le=100)
    local_llm_min_p: float = Field(default=0.0, ge=0, le=1)
    local_llm_presence_penalty: float = Field(default=1.5, ge=-2, le=2)
    local_llm_seed: int = 42
    local_llm_allowed_hosts: str = "localhost,127.0.0.1,::1,local-model,host.docker.internal"
    local_llm_allow_d2_company_data: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
