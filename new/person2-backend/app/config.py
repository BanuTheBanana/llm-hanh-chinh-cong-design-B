from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = ""
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "hanh_chinh_new"
    db_user: str = "app_user"
    db_password: str = "change-me-local-only"

    @property
    def connection_url(self) -> str:
        if self.database_url:
            return self.database_url
        return f"postgresql+asyncpg://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

@lru_cache
def get_settings() -> Settings:
    return Settings()
