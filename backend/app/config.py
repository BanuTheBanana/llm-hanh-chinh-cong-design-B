from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/g1"
    ai_service_url: str = "http://ai-service:8001/internal/v1"
    ai_timeout_seconds: float = Field(default=10, gt=0, le=120)
    session_cookie_name: str = "g1_session"
    session_secure: bool = False
    session_ttl_seconds: int = Field(default=86400, gt=0)
    cors_origins: list[str] = ["http://localhost:3000"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
