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
