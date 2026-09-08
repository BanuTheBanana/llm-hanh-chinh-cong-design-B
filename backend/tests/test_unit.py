"""Database-independent checks; full API integration tests require PostgreSQL."""

import asyncio
import json
from uuid import uuid4

import httpx
import pytest
from pydantic import ValidationError

from app.ai import AIClient
from app.config import get_settings
from app.errors import APIError
from app.main import app
from app.schemas import ConversationInput, LoginInput, MessageInput


def reply(request_id, **changes):
    return {
        "request_id": str(request_id),
        "text": "D0_SYSTEM_SMOKE",
        "provider": "mock",
        "model": "mock-v1",
        "usage": {"input_tokens": 0, "output_tokens": 0},
        "latency_ms": 10,
        **changes,
    }


async def test_ai_contract_success(monkeypatch):
    request_id = uuid4()
    monkeypatch.setattr(get_settings(), "ai_service_url", "http://ai-service:8001/internal/v1/")

    def handler(request):
        assert str(request.url) == "http://ai-service:8001/internal/v1/generate"
        assert json.loads(request.content) == {
            "request_id": str(request_id),
            "messages": [{"role": "user", "content": "hello"}],
            "max_output_tokens": 300,
        }
        return httpx.Response(200, json=reply(request_id))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        assert (
            await AIClient(http).generate(request_id, [{"role": "user", "content": "hello"}])
            == "D0_SYSTEM_SMOKE"
        )


@pytest.mark.parametrize(
    "mode,status,code",
    [
        ("timeout", 504, "AI_SERVICE_TIMEOUT"),
        ("deadline", 504, "AI_SERVICE_TIMEOUT"),
        ("network", 502, "AI_SERVICE_ERROR"),
        ("http", 502, "AI_SERVICE_ERROR"),
        ("json", 502, "AI_SERVICE_ERROR"),
        ("request_id", 502, "AI_SERVICE_ERROR"),
        ("blank", 502, "AI_SERVICE_ERROR"),
        ("schema", 502, "AI_SERVICE_ERROR"),
    ],
)
async def test_ai_errors(monkeypatch, mode, status, code):
    request_id = uuid4()
    monkeypatch.setattr(get_settings(), "ai_timeout_seconds", 0.01)

    async def handler(request):
        if mode == "timeout":
            raise httpx.ReadTimeout("test timeout")
        if mode == "deadline":
            await asyncio.sleep(0.1)
        if mode == "network":
            raise httpx.ConnectError("test network")
        if mode == "http":
            return httpx.Response(503)
        if mode == "json":
            return httpx.Response(200, content=b"not JSON")
        payload = reply(request_id)
        if mode == "request_id":
            payload["request_id"] = str(uuid4())
        if mode == "blank":
            payload["text"] = "  "
        if mode == "schema":
            del payload["usage"]
        return httpx.Response(200, json=payload)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        with pytest.raises(APIError) as caught:
            await AIClient(http).generate(request_id, [])
    assert caught.value.status == status
    assert caught.value.code == code


@pytest.mark.parametrize(
    "schema,payload",
    [
        (LoginInput, {"display_name": " "}),
        (LoginInput, {"display_name": "x" * 101}),
        (ConversationInput, {"user_id": str(uuid4())}),
        (ConversationInput, {"title": " "}),
        (MessageInput, {"client_message_id": str(uuid4()), "content": " "}),
        (MessageInput, {"client_message_id": str(uuid4()), "content": "x" * 10001}),
        (MessageInput, {"client_message_id": "bad", "content": "x"}),
    ],
)
def test_invalid_input(schema, payload):
    with pytest.raises(ValidationError):
        schema.model_validate(payload)


async def test_error_envelope_and_cors_without_database():
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/auth/me", headers={"origin": "http://localhost:3000"})
        assert response.status_code == 401
        assert response.json()["error"]["request_id"] == response.headers["x-request-id"]
        assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
        assert response.headers["cache-control"] == "no-store"
        response = await client.post(
            "/api/v1/auth/login",
            json={"display_name": "Minh"},
            headers={"origin": "https://evil.example"},
        )
        assert response.status_code == 403


def test_openapi_contract():
    schema = app.openapi()
    expected = {
        "/health": {"get"},
        "/api/v1/auth/login": {"post"},
        "/api/v1/auth/logout": {"post"},
        "/api/v1/auth/me": {"get"},
        "/api/v1/conversations": {"get", "post"},
        "/api/v1/conversations/{conversation_id}/messages": {"get", "post"},
    }
    assert {path: set(methods) for path, methods in schema["paths"].items()} == expected
    message = schema["components"]["schemas"]["MessageOutput"]["properties"]
    assert set(message) == {"id", "conversation_id", "role", "content", "status", "created_at"}
    assert set(schema["components"]["schemas"]["MessagePair"]["properties"]) == {
        "user_message",
        "assistant_message",
    }
    errors = schema["paths"]["/api/v1/conversations"]["post"]["responses"]
    assert errors["422"]["content"]["application/json"]["schema"]["$ref"].endswith("ErrorOutput")
