"""Each test gets an isolated PostgreSQL schema; no user tables are truncated."""

import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app import chat
from app.ai import AIClient, get_ai
from app.db import get_db
from app.main import app


@pytest_asyncio.fixture
async def database(monkeypatch):
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.fail("Set TEST_DATABASE_URL to a dedicated PostgreSQL database; see README.")
    schema = "g1_test_" + uuid4().hex
    admin = create_async_engine(url, poolclass=NullPool)
    async with admin.begin() as conn:
        await conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    # Run the actual Alembic migration, never metadata.create_all().
    env = dict(os.environ, DATABASE_URL=url, PGOPTIONS=f"-c search_path={schema}")
    # asyncpg doesn't use PGOPTIONS. A schema-aware connection is supplied to Alembic below.
    env["G1_TEST_SCHEMA"] = schema
    script = """
import asyncio, os
from alembic.config import Config
from alembic import command
from sqlalchemy.ext.asyncio import create_async_engine
async def main():
    engine = create_async_engine(os.environ["DATABASE_URL"],
        connect_args={"server_settings": {"search_path": os.environ["G1_TEST_SCHEMA"]}})
    async with engine.begin() as connection:
        def migrate(sync_conn):
            cfg = Config("alembic.ini")
            cfg.attributes["connection"] = sync_conn
            command.upgrade(cfg, "head")
        await connection.run_sync(migrate)
    await engine.dispose()
asyncio.run(main())
"""
    try:
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=Path(__file__).parents[1],
            env=env,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
        engine = create_async_engine(
            url, poolclass=NullPool, connect_args={"server_settings": {"search_path": schema}}
        )
        sessions = async_sessionmaker(engine, expire_on_commit=False)

        async def override_db():
            async with sessions() as db:
                yield db

        app.dependency_overrides[get_db] = override_db
        monkeypatch.setattr(chat, "engine", engine)
        yield sessions
        await engine.dispose()
    finally:
        app.dependency_overrides.clear()
        async with admin.begin() as conn:
            await conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        await admin.dispose()


@pytest_asyncio.fixture
async def client(database):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client


@pytest_asyncio.fixture
async def ai_mock(database):
    import json

    calls = []

    def success(request):
        payload = json.loads(request.content)
        calls.append(payload)
        return httpx.Response(
            200,
            json={
                "request_id": payload["request_id"],
                "text": "D0_SYSTEM_SMOKE: phản hồi mô phỏng.",
                "provider": "mock",
                "model": "mock-v1",
                "usage": {"input_tokens": 0, "output_tokens": 0},
                "latency_ms": 10,
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(success)) as http:
        app.dependency_overrides[get_ai] = lambda: AIClient(http)
        yield calls
