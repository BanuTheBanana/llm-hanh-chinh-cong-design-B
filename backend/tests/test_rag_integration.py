import copy
import json
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import func, select

from app.ai import AIClient, get_ai
from app.config import get_settings
from app.main import app
from app.rag.corpus import CorpusError, fingerprint, validate_corpus
from app.rag.models import Fragment, IngestionRun
from app.rag.store import ingest, load_corpus

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "backend/tests/fixtures/rag"
P = "/api/v1"


@pytest.fixture
def corpus():
    return validate_corpus(ROOT, DATA, "fixture-v1", {"fixture.invalid"}, True)


async def test_ingest_twice_conflict_and_pinning(database, corpus):
    async with database() as db:
        assert await ingest(db, corpus)
        await db.commit()
        assert not await ingest(db, corpus)
        await db.commit()
        assert await db.scalar(select(func.count()).select_from(Fragment)) == 3
        with pytest.raises(CorpusError, match="FIXTURE_DISABLED"):
            await load_corpus(db, corpus.version)
        loaded = await load_corpus(db, corpus.version, True)
        assert loaded.fingerprint == corpus.fingerprint
        changed = copy.deepcopy(corpus)
        changed.sources["src_synthetic"].title = "Changed"
        changed.fingerprint = fingerprint(changed.sources, changed.procedures, changed.fragments)
        with pytest.raises(CorpusError, match="VERSION_CONFLICT"):
            await ingest(db, changed)
        await db.rollback()
        assert await db.scalar(select(func.count()).select_from(IngestionRun)) == 1
        assert (await load_corpus(db, corpus.version, True)).sources[
            "src_synthetic"
        ].title != "Changed"


async def setup(client, database, corpus, monkeypatch):
    monkeypatch.setattr(get_settings(), "rag_enabled", True)
    monkeypatch.setattr(get_settings(), "rag_allow_fixtures", True)
    monkeypatch.setattr(get_settings(), "rag_corpus_version", corpus.version)
    async with database() as db:
        await ingest(db, corpus)
        await db.commit()
    assert (
        await client.post(P + "/auth/login", json={"display_name": "RagUser"})
    ).status_code == 200
    conv = await client.post(P + "/conversations", json={})
    assert conv.status_code == 201
    return P + "/conversations/" + conv.json()["id"] + "/messages"


async def test_rag_readiness_checks_corpus_and_grounded_ai(client, database, corpus, monkeypatch):
    monkeypatch.setattr(get_settings(), "rag_enabled", True)
    monkeypatch.setattr(get_settings(), "rag_allow_fixtures", True)
    monkeypatch.setattr(get_settings(), "rag_corpus_version", corpus.version)
    async with database() as db:
        await ingest(db, corpus)
        await db.commit()

    def handler(request):
        assert request.method == "GET"
        assert request.url.path == "/internal/v2/health"
        return httpx.Response(
            200,
            json={
                "status": "ok",
                "service": "ai-service",
                "endpoint": "grounded-v2",
                "provider": "template",
                "prompt_version": "g2-grounded-v2",
                "external_calls_enabled": False,
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        app.dependency_overrides[get_ai] = lambda: AIClient(http)
        result = await client.get("/health/rag")
    assert result.status_code == 200
    assert result.json() == {
        "status": "ok",
        "corpus_version": corpus.version,
        "data_classification": "D0_SYSTEM_SMOKE",
        "sources": 1,
        "procedures": 1,
        "fragments": 3,
        "grounded_provider": "template",
        "prompt_version": "g2-grounded-v2",
        "external_calls_enabled": False,
    }


async def test_g5_rag_readiness_checks_intent_context(client, database, corpus, monkeypatch):
    monkeypatch.setattr(get_settings(), "rag_enabled", True)
    monkeypatch.setattr(get_settings(), "rag_allow_fixtures", True)
    monkeypatch.setattr(get_settings(), "rag_corpus_version", corpus.version)
    monkeypatch.setattr(get_settings(), "g5_intent_context_enabled", True)
    async with database() as db:
        await ingest(db, corpus)
        await db.commit()

    def handler(request):
        assert request.method == "GET"
        if request.url.path == "/internal/v2/health":
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "service": "ai-service",
                    "endpoint": "grounded-v2",
                    "provider": "local",
                    "prompt_version": "g2-grounded-v2",
                    "external_calls_enabled": False,
                },
            )
        assert request.url.path == "/internal/v3/intent-context/health"
        return httpx.Response(
            200,
            json={
                "status": "ok",
                "service": "ai-service",
                "endpoint": "intent-context-v2",
                "provider": "local-intent-context",
                "model": "Qwen3-4B-Intent-r16",
                "external_calls_enabled": False,
                "allowed_data_classifications": ["D0_SYSTEM_SMOKE", "D2_COMPANY_REAL"],
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        app.dependency_overrides[get_ai] = lambda: AIClient(http)
        result = await client.get("/health/rag")
    assert result.status_code == 200
    assert result.json()["intent_context_enabled"] is True
    assert result.json()["intent_context_model"] == "Qwen3-4B-Intent-r16"


async def test_rag_rejects_query_over_grounded_contract_limit(
    client, database, corpus, monkeypatch
):
    path = await setup(client, database, corpus, monkeypatch)
    app.dependency_overrides[get_ai] = lambda: object()
    response = await client.post(
        path,
        json={"client_message_id": str(uuid4()), "content": "x" * 4_001},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert (await client.get(path)).json() == []


async def test_rag_success_contract_retry_and_isolation(client, database, corpus, monkeypatch):
    path = await setup(client, database, corpus, monkeypatch)
    calls = []

    def handler(request):
        payload = json.loads(request.content)
        calls.append(payload)
        assert request.url.path == "/internal/v2/generate"
        assert "history" not in payload
        assert "url" not in payload["evidence"][0]
        assert "score" not in payload["evidence"][0]
        assert "metadata" not in payload["evidence"][0]
        return httpx.Response(
            200,
            json={
                "request_id": payload["request_id"],
                "evidence_bundle_id": payload["evidence_bundle_id"],
                "corpus_version": payload["corpus_version"],
                "data_classification": payload["data_classification"],
                "prompt_version": "g2-grounded-v2",
                "answer": "Fixture only",
                "status": "ANSWER",
                "cited_fragment_ids": [payload["evidence"][0]["fragment_id"]],
                "missing_information": [],
                "provider": "mock",
                "model": "mock-g2",
                "usage": {"input_tokens": 0, "output_tokens": 0},
                "latency_ms": 1,
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        app.dependency_overrides[get_ai] = lambda: AIClient(http)
        body = {"client_message_id": str(uuid4()), "content": "lệ phí"}
        first = await client.post(path, json=body)
        assert first.status_code == 200, first.text
        pair = first.json()
        assert pair["assistant_message"]["grounding"]["sources"][0]["fragment_id"] == "frag_fees"
        monkeypatch.setattr(get_settings(), "rag_corpus_version", "not-active-anymore")
        assert (await client.post(path, json=body)).json() == pair
        assert len(calls) == 1
        assert (await client.get(path)).json()[1] == pair["assistant_message"]
        conflict = await client.post(
            path, json={**body, "retrieval_filters": {"jurisdiction": "OTHER"}}
        )
        assert conflict.status_code == 409
        await client.post(P + "/auth/login", json={"display_name": "Other"})
        assert (await client.get(path)).status_code == 404
        assert (await client.post(path, json=body)).status_code == 404


@pytest.mark.parametrize("mode,expected", [("nohit", 200), ("citation", 502), ("timeout", 504)])
async def test_abstain_and_failure(client, database, corpus, monkeypatch, mode, expected):
    path = await setup(client, database, corpus, monkeypatch)
    calls = []

    def handler(request):
        calls.append(1)
        if mode == "timeout":
            raise httpx.ReadTimeout("fixture")
        payload = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "request_id": payload["request_id"],
                "evidence_bundle_id": payload["evidence_bundle_id"],
                "corpus_version": payload["corpus_version"],
                "data_classification": payload["data_classification"],
                "prompt_version": "g2-grounded-v2",
                "answer": "Bad source",
                "status": "ANSWER",
                "cited_fragment_ids": ["fabricated"],
                "missing_information": [],
                "provider": "mock",
                "model": "mock-g2",
                "usage": {"input_tokens": 0, "output_tokens": 0},
                "latency_ms": 1,
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        app.dependency_overrides[get_ai] = lambda: AIClient(http)
        body = {
            "client_message_id": str(uuid4()),
            "content": "quantumxyz" if mode == "nohit" else "lệ phí",
        }
        response = await client.post(path, json=body)
        assert response.status_code == expected, response.text
        history = (await client.get(path)).json()
        if mode == "nohit":
            assert not calls and len(history) == 2
            assert history[1]["grounding"]["status"] == "INSUFFICIENT_DATA"
        else:
            assert len(history) == 1 and history[0]["status"] == "failed"


async def test_upgrade_from_g1_retains_history(database):
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import text

    async with database() as db:
        conn = await db.connection()

        def downgrade(sync_conn):
            cfg = Config(str(Path(__file__).parents[1] / "alembic.ini"))
            cfg.attributes["connection"] = sync_conn
            command.downgrade(cfg, "0001_g1")

        await conn.run_sync(downgrade)
        user, conversation, message, key, request = [uuid4() for _ in range(5)]
        await db.execute(
            text(
                "INSERT INTO users (id,display_name,created_at) VALUES (:id,'UpgradeFixture',now())"
            ),
            {"id": user},
        )
        await db.execute(
            text(
                "INSERT INTO conversations (id,user_id,title,created_at,updated_at) "
                "VALUES (:id,:user,'G1 preserved',now(),now())"
            ),
            {"id": conversation, "user": user},
        )
        await db.execute(
            text(
                "INSERT INTO messages "
                "(id,conversation_id,client_message_id,role,content,status,request_id,created_at) "
                "VALUES (:id,:cid,:key,'user','G1 text','completed',:rid,now())"
            ),
            {"id": message, "cid": conversation, "key": key, "rid": request},
        )
        await db.commit()
        conn = await db.connection()

        def upgrade(sync_conn):
            cfg = Config(str(Path(__file__).parents[1] / "alembic.ini"))
            cfg.attributes["connection"] = sync_conn
            command.upgrade(cfg, "head")
            command.check(cfg)

        await conn.run_sync(upgrade)
        saved = (
            await db.execute(
                text("SELECT content,grounding,retrieval_filters FROM messages WHERE id=:id"),
                {"id": message},
            )
        ).one()
        assert tuple(saved) == ("G1 text", None, None)
        await db.commit()


async def test_concurrent_ingest_is_idempotent(database, corpus):
    import asyncio

    async def one():
        async with database() as db:
            async with db.begin():
                return await ingest(db, corpus)

    assert sorted(await asyncio.gather(one(), one())) == [False, True]


async def test_failed_citation_retry_reuses_user(client, database, corpus, monkeypatch):
    path = await setup(client, database, corpus, monkeypatch)
    repair = False

    def handler(request):
        payload = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "request_id": payload["request_id"],
                "evidence_bundle_id": payload["evidence_bundle_id"],
                "corpus_version": payload["corpus_version"],
                "data_classification": payload["data_classification"],
                "prompt_version": "g2-grounded-v2",
                "answer": "Fixture answer",
                "status": "ANSWER",
                "cited_fragment_ids": ["frag_fees" if repair else "bad_id"],
                "missing_information": [],
                "provider": "mock",
                "model": "mock-g2",
                "usage": {"input_tokens": 0, "output_tokens": 0},
                "latency_ms": 1,
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        app.dependency_overrides[get_ai] = lambda: AIClient(http)
        payload = {"client_message_id": str(uuid4()), "content": "lệ phí"}
        bad = await client.post(path, json=payload)
        assert bad.status_code == 502
        before = (await client.get(path)).json()
        assert len(before) == 1
        repair = True
        good = await client.post(path, json=payload)
        assert good.status_code == 200, good.text
        assert good.json()["user_message"]["id"] == before[0]["id"]
        assert len((await client.get(path)).json()) == 2
