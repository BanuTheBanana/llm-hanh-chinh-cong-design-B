from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient

from app.auth import digest_session_token, hash_password, new_session_token, verify_password
from app.config import Settings
from app.models import Account, LoginSession
import app.main as main


def test_password_hash_is_salted_and_rejects_wrong_password():
    first = hash_password("correct-horse-battery")
    second = hash_password("correct-horse-battery")

    assert first != second
    assert verify_password("correct-horse-battery", first)
    assert not verify_password("wrong-password", first)
    assert not verify_password("correct-horse-battery", "malformed")


def test_session_cookie_token_is_opaque_and_stored_as_digest():
    token = new_session_token()
    digest = digest_session_token(token)

    assert len(token) >= 40
    assert len(digest) == 64
    assert digest != token
    assert digest_session_token(token) == digest


class FakeConnection:
    async def run_sync(self, operation):
        assert callable(operation)
        return None


class FakeEngine:
    @asynccontextmanager
    async def begin(self):
        yield FakeConnection()

    async def dispose(self):
        return None


class FakeAuthDatabase:
    def __init__(self, sessions, account):
        self.sessions = sessions
        self.account = account

    async def get(self, model, key):
        if model is LoginSession:
            return self.sessions.get(key)
        if model is Account and self.account.account_id == key:
            return self.account
        return None

    async def execute(self, statement, params=None):
        assert statement is not None
        assert params is None or isinstance(params, dict)
        return None


class FakeAuthSessions:
    def __init__(self, database):
        self.database = database

    @asynccontextmanager
    async def begin(self):
        yield self.database

    @asynccontextmanager
    async def __call__(self):
        yield self.database


def test_authenticated_account_is_resolved_only_from_session_cookie(monkeypatch):
    token = new_session_token()
    account = Account(account_id='account-a', username='alice', password_hash='unused')
    login = LoginSession(
        token_hash=digest_session_token(token),
        account_id=account.account_id,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    database = FakeAuthDatabase({login.token_hash: login}, account)
    def fake_make_database(settings):
        assert settings is not None
        return FakeEngine(), FakeAuthSessions(database)

    monkeypatch.setattr(main, 'make_database', fake_make_database)
    async def no_active_corpus(db):
        assert db is not None
        return None

    monkeypatch.setattr(main, 'load_active', no_active_corpus)

    with TestClient(main.create_app(Settings(bootstrap_demo=False, auth_cookie_secure=False))) as client:
        client.cookies.set('hcc_session', token)
        response = client.get('/api/v1/auth/me')
        assert response.status_code == 200
        assert response.json() == {'account_id': 'account-a', 'username': 'alice'}
        client.cookies.set('hcc_session', 'not-a-valid-token')
        assert client.get('/api/v1/auth/me').status_code == 401
