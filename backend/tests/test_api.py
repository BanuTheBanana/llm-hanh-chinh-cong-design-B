import asyncio
from datetime import timedelta
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import select, update

from app.ai import AIClient, get_ai
from app.auth import token_hash
from app.chat import AI_CONTEXT_MAX_MESSAGES
from app.config import get_settings
from app.main import app
from app.models import Message, SessionRecord, utcnow

P = "/api/v1"


async def login(client, name="Minh"):
    response = await client.post(P + "/auth/login", json={"display_name": name})
    assert response.status_code == 200, response.text
    return response


async def conversation(client):
    await login(client)
    response = await client.post(P + "/conversations", json={})
    assert response.status_code == 201, response.text
    return P + "/conversations/" + response.json()["id"] + "/messages"


def body(content="D0_SYSTEM_SMOKE"):
    return {"client_message_id": str(uuid4()), "content": content}


def assert_error(response, status, code):
    assert response.status_code == status, response.text
    assert set(response.json()) == {"error"}
    error = response.json()["error"]
    assert error["code"] == code
    assert str(UUID(error["request_id"])) == response.headers["x-request-id"]


async def test_auth_cookie_hash_rotation_expiry_logout(client, database):
    assert_error(await client.get(P + "/auth/me"), 401, "UNAUTHORIZED")
    response = await login(client)
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "SameSite=lax" in response.headers["set-cookie"]
    token = client.cookies.get("g1_session")
    async with database() as db:
        record = await db.scalar(select(SessionRecord))
        assert record.token_hash == token_hash(token)
        assert record.token_hash != token
    assert (await client.get(P + "/auth/me")).json() == response.json()
    assert (await login(client)).json() == response.json()
    async with database() as db:
        assert (
            await db.scalar(
                select(SessionRecord).where(SessionRecord.token_hash == token_hash(token))
            )
            is None
        )
        await db.execute(update(SessionRecord).values(expires_at=utcnow() - timedelta(seconds=1)))
        await db.commit()
    assert_error(await client.get(P + "/auth/me"), 401, "UNAUTHORIZED")
    await login(client)
    current = client.cookies.get("g1_session")
    assert (await client.post(P + "/auth/logout")).status_code == 204
    client.cookies.set("g1_session", current)
    assert_error(await client.get(P + "/auth/me"), 401, "UNAUTHORIZED")
    assert (await client.post(P + "/auth/logout")).status_code == 204


@pytest.mark.parametrize(
    "method,path,payload",
    [
        ("GET", "/conversations", None),
        ("POST", "/conversations", {}),
        ("GET", f"/conversations/{uuid4()}/messages", None),
        ("POST", f"/conversations/{uuid4()}/messages", body()),
    ],
)
async def test_unauthenticated(client, method, path, payload):
    assert_error(await client.request(method, P + path, json=payload), 401, "UNAUTHORIZED")


async def test_success_history_relogin_and_idempotency(client, ai_mock):
    path = await conversation(client)
    payload = body()
    first = await client.post(path, json=payload)
    assert first.status_code == 200, first.text
    pair = first.json()
    assert pair["user_message"]["status"] == "completed"
    assert pair["assistant_message"]["role"] == "assistant"
    second = await client.post(path, json=payload)
    assert second.json() == pair
    assert len(ai_mock) == 1
    assert ai_mock[0]["messages"] == [{"role": "user", "content": payload["content"]}]
    assert ai_mock[0]["max_output_tokens"] == 300
    assert_error(
        await client.post(path, json={**payload, "content": "different"}),
        409,
        "IDEMPOTENCY_CONFLICT",
    )
    await client.post(P + "/auth/logout")
    await login(client)
    assert (await client.get(path)).json() == [pair["user_message"], pair["assistant_message"]]
    await client.post(path, json=body("second turn"))
    assert len(ai_mock[1]["messages"]) == 3
    assert len((await client.get(P + "/conversations")).json()) == 1


async def test_ai_context_is_capped_to_internal_contract(client, database, ai_mock):
    path = await conversation(client)
    conversation_id = UUID(path.split("/")[-2])
    async with database() as db:
        for index in range(55):
            request_id = uuid4()
            db.add_all(
                [
                    Message(
                        conversation_id=conversation_id,
                        client_message_id=uuid4(),
                        role="user",
                        content=f"seed-user-{index}",
                        status="completed",
                        request_id=request_id,
                    ),
                    Message(
                        conversation_id=conversation_id,
                        role="assistant",
                        content=f"seed-assistant-{index}",
                        status="completed",
                        request_id=request_id,
                    ),
                ]
            )
        await db.commit()

    response = await client.post(path, json=body("latest-turn"))

    assert response.status_code == 200, response.text
    sent_messages = ai_mock[0]["messages"]
    assert len(sent_messages) == AI_CONTEXT_MAX_MESSAGES
    assert sent_messages[-1] == {"role": "user", "content": "latest-turn"}


async def test_ownership(client, ai_mock):
    path = await conversation(client)
    await client.post(path, json=body())
    await login(client, "Hoan")
    assert (await client.get(P + "/conversations")).json() == []
    assert_error(await client.get(path), 404, "NOT_FOUND")
    assert_error(await client.post(path, json=body()), 404, "NOT_FOUND")
    assert len(ai_mock) == 1


@pytest.mark.parametrize(
    "mode,code,status",
    [
        ("error", "AI_SERVICE_ERROR", 502),
        ("timeout", "AI_SERVICE_TIMEOUT", 504),
        ("malformed", "AI_SERVICE_ERROR", 502),
        ("mismatch", "AI_SERVICE_ERROR", 502),
        ("slow", "AI_SERVICE_TIMEOUT", 504),
    ],
)
async def test_ai_failure_keeps_message_then_retry(
    client, database, ai_mock, monkeypatch, mode, code, status
):
    path = await conversation(client)
    payload = body()
    success_override = app.dependency_overrides[get_ai]

    async def fail(request):
        # Check durability from another connection before returning any AI response.
        async with database() as db:
            saved = (await db.scalars(select(Message))).all()
            assert len(saved) == 1 and saved[0].status == "pending"
        if mode == "timeout":
            raise httpx.ReadTimeout("simulated")
        if mode == "slow":
            await asyncio.sleep(0.1)
        if mode == "malformed":
            return httpx.Response(200, content=b"not json")
        if mode == "mismatch":
            return httpx.Response(
                200,
                json={
                    "request_id": str(uuid4()),
                    "text": "bad",
                    "provider": "mock",
                    "model": "mock-v1",
                    "latency_ms": 1,
                    "usage": {"input_tokens": 0, "output_tokens": 0},
                },
            )
        return httpx.Response(500)

    if mode == "slow":
        monkeypatch.setattr(get_settings(), "ai_request_timeout_seconds", 0.05)
    async with httpx.AsyncClient(transport=httpx.MockTransport(fail)) as http:
        app.dependency_overrides[get_ai] = lambda: AIClient(http)
        response = await client.post(path, json=payload)
    assert_error(response, status, code)
    history = (await client.get(path)).json()
    assert len(history) == 1 and history[0]["status"] == "failed"
    app.dependency_overrides[get_ai] = success_override
    retried = await client.post(path, json=payload)
    assert retried.status_code == 200, retried.text
    assert retried.json()["user_message"]["id"] == history[0]["id"]
    assert len((await client.get(path)).json()) == 2


@pytest.mark.parametrize(
    "payload",
    [
        {"client_message_id": str(uuid4()), "content": "   "},
        {"client_message_id": str(uuid4()), "content": "x" * 10001},
        {"client_message_id": "bad", "content": "x"},
        {**body(), "user_id": str(uuid4())},
    ],
)
async def test_validation(client, payload):
    path = await conversation(client)
    assert_error(await client.post(path, json=payload), 422, "VALIDATION_ERROR")
    assert (await client.get(path)).json() == []


async def test_cors_and_client_identity_rejected(client):
    await login(client)
    assert_error(
        await client.post(P + "/conversations", json={"user_id": str(uuid4())}),
        422,
        "VALIDATION_ERROR",
    )
    assert_error(
        await client.post(P + "/auth/login", json={"display_name": " "}), 422, "VALIDATION_ERROR"
    )
    assert_error(
        await client.post(
            P + "/auth/login",
            json={"display_name": "Minh"},
            headers={"origin": "https://evil.example"},
        ),
        403,
        "FORBIDDEN_ORIGIN",
    )
    response = await client.get(P + "/auth/me", headers={"origin": "http://localhost:3000"})
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert response.headers["access-control-allow-credentials"] == "true"
    assert (await client.get("/health")).json() == {"status": "ok"}


async def test_concurrent_messages(client, ai_mock):
    path = await conversation(client)
    payload = body()
    entered, release = asyncio.Event(), asyncio.Event()
    success_override = app.dependency_overrides[get_ai]
    real_ai = success_override()

    class WaitingAI:
        async def generate(self, request_id, messages):
            entered.set()
            await release.wait()
            return await real_ai.generate(request_id, messages)

    app.dependency_overrides[get_ai] = lambda: WaitingAI()
    first = asyncio.create_task(client.post(path, json=payload))
    try:
        await asyncio.wait_for(entered.wait(), timeout=5)
        assert_error(await client.post(path, json=payload), 409, "MESSAGE_IN_PROGRESS")
        assert_error(await client.post(path, json=body("another")), 409, "MESSAGE_IN_PROGRESS")
    finally:
        release.set()
        result = await first
    assert result.status_code == 200, result.text
    app.dependency_overrides[get_ai] = success_override
    assert (await client.post(path, json=payload)).json() == result.json()
    assert len((await client.get(path)).json()) == 2
    assert len(ai_mock) == 1
