from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL, make_url

BACKEND_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_ROOT / ".env",
        env_file_encoding="utf-8-sig",
        extra="ignore",
        hide_input_in_errors=True,
    )
    # Optional legacy/full DSN takes priority. Never print this raw value.
    app_env: str = "development"
    database_url: SecretStr | None = None
    db_host: str = "127.0.0.1"
    db_port: int = Field(default=15432, ge=1, le=65535)
    db_name: str = "g1"
    db_user: str = "postgres"
    db_password: SecretStr = SecretStr("postgres")
    rag_enabled: bool = False
    rag_corpus_version: str = ""
    rag_top_k: int = Field(default=5, ge=1, le=8)
    rag_allow_fixtures: bool = False
    g3_d2_enabled: bool = False
    g3_private_dataset_path: Path | None = None
    g3_expected_rows: int = Field(default=10, ge=1)
    g3_corpus_sha256: str = ""
    g3_allow_production: bool = False
    # Root Compose provides the origin; AIClient owns the internal route path.
    ai_service_url: str = "http://localhost:8001"
    ai_request_timeout_seconds: float = Field(default=10, gt=0, le=120)
    llm_max_output_tokens: int = Field(default=300, ge=1, le=4096)
    grounded_max_output_tokens: int = Field(default=500, ge=32, le=2048)
    session_cookie_name: str = "g1_session"
    session_cookie_secure: bool = False
    session_ttl_seconds: int = Field(default=86400, gt=0)
    web_origin: str = "http://localhost:3000"
    web_origins: str = ""

    @property
    def allowed_web_origins(self) -> tuple[str, ...]:
        """Return the primary Web origin plus explicitly configured local aliases."""
        candidates = [self.web_origin, *self.web_origins.split(",")]
        normalized = (origin.strip().rstrip("/") for origin in candidates if origin.strip())
        return tuple(dict.fromkeys(normalized))

    @model_validator(mode="after")
    def validate_rag_safety(self):
        if not self.allowed_web_origins:
            raise ValueError("At least one Web origin is required.")
        if self.rag_enabled and not self.rag_corpus_version.strip():
            raise ValueError("RAG_CORPUS_VERSION is required when RAG_ENABLED=true.")
        if self.rag_allow_fixtures and self.app_env.lower() in {"production", "prod"}:
            raise ValueError("RAG fixtures are forbidden in production.")
        if self.g3_d2_enabled:
            if not self.rag_enabled:
                raise ValueError("RAG_ENABLED=true is required when G3_D2_ENABLED=true.")
            if self.g3_private_dataset_path is None:
                raise ValueError("G3_PRIVATE_DATASET_PATH is required when G3_D2_ENABLED=true.")
            if len(self.g3_corpus_sha256) != 64 or any(
                character not in "0123456789abcdef" for character in self.g3_corpus_sha256
            ):
                raise ValueError("G3_CORPUS_SHA256 must pin the approved private corpus.")
            if self.app_env.lower() in {"production", "prod"} and not self.g3_allow_production:
                raise ValueError("G3 D2 demo data is forbidden in production by default.")
        return self

    @property
    def connection_url(self) -> URL:
        raw = self.database_url.get_secret_value().strip() if self.database_url else ""
        if raw:
            try:
                url = make_url(raw)
                if url.drivername != "postgresql+asyncpg" or not url.host or not url.database:
                    raise ValueError()
                if url.port is not None and not 1 <= url.port <= 65535:
                    raise ValueError()
                return url
            except Exception:
                raise ValueError(
                    "DATABASE_URL khong hop le. Dung postgresql+asyncpg://... "
                    "hoac bo DATABASE_URL va dung cac bien DB_*."
                ) from None
        if not all(value.strip() for value in (self.db_host, self.db_name, self.db_user)):
            raise ValueError("DB_HOST, DB_NAME va DB_USER khong duoc rong.")
        # URL object accepts a raw password, including @, :, /, # and %.
        return URL.create(
            "postgresql+asyncpg",
            username=self.db_user,
            password=self.db_password.get_secret_value(),
            host=self.db_host,
            port=self.db_port,
            database=self.db_name,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
