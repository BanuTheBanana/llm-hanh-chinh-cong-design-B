from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')
    database_url: str = ''
    db_host: str = '127.0.0.1'
    db_port: int = 5432
    db_name: str = 'hanh_chinh_mvp'
    db_user: str = 'app_user'
    db_password: str = 'change-me-local-only'
    segmenter_backend: str = 'underthesea'
    allow_draft: bool = True  # explicit DEMO configuration
    bootstrap_demo: bool = True
    bm25_score_floor: float = 0.5  # UNCALIBRATED demo values
    bm25_margin: float = 0.15
    retrieval_mode: str = 'lexical'
    dense_model_path: str = ''
    dense_device: str = 'cpu'
    dense_batch_size: int = 1
    dense_query_prefix: str = ''
    dense_document_prefix: str = ''
    dense_score_floor: float = 0.02
    dense_margin_floor: float = 0.001
    dense_min_similarity: float = 0.4
    dense_rrf_k: int = 60
    auth_cookie_name: str = 'hcc_session'
    auth_cookie_secure: bool = True
    auth_session_hours: int = 12
    allow_registration: bool = False
    enable_dev_trace: bool = False

    @property
    def connection_url(self):
        return self.database_url or URL.create('postgresql+asyncpg', username=self.db_user,
            password=self.db_password,host=self.db_host,port=self.db_port,database=self.db_name)

@lru_cache
def get_settings(): return Settings()
