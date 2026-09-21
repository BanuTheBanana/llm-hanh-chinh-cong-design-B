import pytest
from sqlalchemy.engine import make_url

from app.config import Settings
from app.doctor import diagnose_exception


@pytest.fixture(autouse=True)
def clean_config_environment(monkeypatch):
    for key in ("DATABASE_URL", "DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"):
        monkeypatch.delenv(key, raising=False)


def test_password_special_characters():
    password = "secret@:/#%$!"
    settings = Settings(_env_file=None, db_password=password)
    url = settings.connection_url
    assert url.password == password
    assert make_url(url.render_as_string(hide_password=False)).password == password
    assert password not in repr(settings)


def test_old_database_url_still_works():
    settings = Settings(
        _env_file=None,
        database_url="postgresql+asyncpg://user:pass@db:5433/legacy",
        db_host="ignored",
        db_port=15432,
    )
    assert settings.connection_url.host == "db"
    assert settings.connection_url.database == "legacy"
    assert settings.connection_url.port == 5433
    assert "user:pass" not in repr(settings)


@pytest.mark.parametrize("raw", ["", "   "])
def test_empty_url_uses_fields(raw):
    assert Settings(_env_file=None, database_url=raw).connection_url.port == 15432


def test_empty_url_uses_compose_database_fields(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.setenv("DB_HOST", "postgres")
    monkeypatch.setenv("DB_PORT", "5432")
    monkeypatch.setenv("DB_NAME", "custom_db")
    monkeypatch.setenv("DB_USER", "custom_user")
    monkeypatch.setenv("DB_PASSWORD", "custom_password")

    settings = Settings(_env_file=None)

    assert settings.connection_url.host == "postgres"
    assert settings.connection_url.port == 5432
    assert settings.connection_url.database == "custom_db"
    assert settings.connection_url.username == "custom_user"
    assert settings.connection_url.password == "custom_password"


@pytest.mark.parametrize("value", [0, 4097])
def test_llm_max_output_tokens_is_bounded(value):
    with pytest.raises(ValueError):
        Settings(_env_file=None, llm_max_output_tokens=value)


@pytest.mark.parametrize("value", [31, 2049])
def test_grounded_max_output_tokens_is_bounded(value):
    with pytest.raises(ValueError):
        Settings(_env_file=None, grounded_max_output_tokens=value)


def test_rag_requires_version_and_fixture_is_forbidden_in_production():
    with pytest.raises(ValueError, match="RAG_CORPUS_VERSION"):
        Settings(_env_file=None, rag_enabled=True)
    with pytest.raises(ValueError, match="forbidden in production"):
        Settings(
            _env_file=None,
            app_env="production",
            rag_allow_fixtures=True,
        )


def test_g3_d2_requires_rag_and_private_path_and_is_demo_only():
    with pytest.raises(ValueError, match="RAG_ENABLED"):
        Settings(
            _env_file=None,
            rag_corpus_version="private-v1",
            g3_d2_enabled=True,
            g3_private_dataset_path="private",
            g3_corpus_sha256="a" * 64,
        )
    with pytest.raises(ValueError, match="G3_PRIVATE_DATASET_PATH"):
        Settings(
            _env_file=None,
            rag_enabled=True,
            rag_corpus_version="private-v1",
            g3_d2_enabled=True,
        )
    with pytest.raises(ValueError, match="forbidden in production"):
        Settings(
            _env_file=None,
            app_env="production",
            rag_enabled=True,
            rag_corpus_version="private-v1",
            g3_d2_enabled=True,
            g3_private_dataset_path="private",
            g3_corpus_sha256="a" * 64,
        )


@pytest.mark.parametrize(
    "raw",
    [
        "secret",
        "mongodb://host/db",
        "postgresql://host/db",
        "postgresql+asyncpg://host:bad/db",
        "postgresql+asyncpg://host",
    ],
)
def test_invalid_url_without_leaking(raw):
    with pytest.raises(ValueError) as error:
        Settings(_env_file=None, database_url=raw).connection_url
    assert raw not in str(error.value)


def test_bom_env_and_environment_override(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("DB_HOST=from-file\nDB_PORT=15555\nDB_PASSWORD='p@ss'\n", encoding="utf-8-sig")
    monkeypatch.setenv("DB_HOST", "from-shell")
    settings = Settings(_env_file=env)
    assert settings.connection_url.host == "from-shell"
    assert settings.connection_url.port == 15555
    assert settings.connection_url.password == "p@ss"


@pytest.mark.parametrize(
    "state,code",
    [("28P01", "DB_AUTH_FAILED"), ("3D000", "DB_NOT_FOUND"), ("28000", "DB_AUTH_FAILED")],
)
def test_diagnostic_sqlstates(state, code):
    error = Exception("private secret must not be printed")
    error.sqlstate = state
    wrapped = Exception("wrapped")
    wrapped.__cause__ = error
    found, hint = diagnose_exception(wrapped)
    assert found == code
    assert "private secret" not in hint


def test_diagnostic_network():
    assert diagnose_exception(ConnectionRefusedError())[0] == "DB_NETWORK_ERROR"


def test_g5_intent_context_requires_answer_plan():
    with pytest.raises(ValueError, match="intent/context"):
        Settings(_env_file=None, g5_intent_context_enabled=True)

    settings = Settings(
        _env_file=None,
        rag_enabled=True,
        rag_corpus_version="fixture-v1",
        g3_d2_enabled=True,
        g3_private_dataset_path="private",
        g3_corpus_sha256="a" * 64,
        g4_answer_plan_enabled=True,
        g5_intent_context_enabled=True,
    )
    assert settings.g5_intent_context_enabled is True


def test_guarded_direct_requires_complete_grounded_stack():
    with pytest.raises(ValueError, match="direct evidence modes"):
        Settings(_env_file=None, g8_evidence_mode="guarded_direct")

    with pytest.raises(ValueError, match="global hybrid procedure verifier"):
        Settings(
            _env_file=None,
            rag_enabled=True,
            rag_corpus_version="fixture-v1",
            g3_d2_enabled=True,
            g3_private_dataset_path="private",
            g3_corpus_sha256="a" * 64,
            g4_answer_plan_enabled=True,
            g5_intent_context_enabled=True,
            g5_hybrid_enabled=False,
            g8_evidence_mode="guarded_direct",
        )

    settings = Settings(
        _env_file=None,
        rag_enabled=True,
        rag_corpus_version="fixture-v1",
        g3_d2_enabled=True,
        g3_private_dataset_path="private",
        g3_corpus_sha256="a" * 64,
        g4_answer_plan_enabled=True,
        g5_intent_context_enabled=True,
        g5_hybrid_enabled=True,
        g8_evidence_mode="guarded_direct",
    )
    assert settings.g8_evidence_mode == "guarded_direct"
