from uuid import uuid4

from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.dependencies import get_provider
from app.providers.mock import MockProvider


def request_body() -> dict[str, object]:
    return {
        "request_id": str(uuid4()),
        "messages": [
            {"role": "user", "content": "Xin chào, đây là tin nhắn kiểm thử."}
        ],
        "max_output_tokens": 300,
    }


def test_health_returns_service_and_configured_provider(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "ai-service",
        "provider": "mock",
    }


def test_health_does_not_report_ok_for_unsupported_provider(
    client: TestClient,
) -> None:
    client.app.dependency_overrides[get_settings] = lambda: Settings(
        llm_provider="not-implemented"
    )

    response = client.get("/health")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "AI_PROVIDER_UNAVAILABLE"


def test_generate_success_matches_frozen_contract(client: TestClient) -> None:
    body = request_body()

    response = client.post("/internal/v1/generate", json=body)

    assert response.status_code == 200
    payload = response.json()
    assert payload["request_id"] == body["request_id"]
    assert payload["provider"] == "mock"
    assert payload["model"] == "mock-v1"
    assert payload["usage"] == {"input_tokens": 0, "output_tokens": 0}
    assert payload["latency_ms"] >= 0
    assert "phản hồi mô phỏng" in payload["text"]
    assert "không phải tư vấn hành chính" in payload["text"]


def test_generate_error_mode_is_predictable(client: TestClient) -> None:
    body = request_body()
    client.app.dependency_overrides[get_provider] = lambda: MockProvider(
        mode="error", latency_ms=0
    )

    response = client.post("/internal/v1/generate", json=body)

    assert response.status_code == 503
    assert response.json() == {
        "error": {
            "code": "AI_PROVIDER_ERROR",
            "message": "AI Service is temporarily unavailable.",
            "request_id": body["request_id"],
        }
    }


def test_generate_timeout_mode_is_predictable_and_fast_in_test(
    client: TestClient,
) -> None:
    body = request_body()
    client.app.dependency_overrides[get_provider] = lambda: MockProvider(
        mode="timeout", latency_ms=0, timeout_seconds=0.001
    )

    response = client.post("/internal/v1/generate", json=body)

    assert response.status_code == 504
    assert response.json() == {
        "error": {
            "code": "AI_SERVICE_TIMEOUT",
            "message": "AI Service timed out. Please try again.",
            "request_id": body["request_id"],
        }
    }


def test_unsupported_provider_dependency_returns_contract_error(
    client: TestClient,
) -> None:
    body = request_body()
    client.app.dependency_overrides[get_settings] = lambda: Settings(
        llm_provider="not-implemented"
    )

    response = client.post("/internal/v1/generate", json=body)

    assert response.status_code == 503
    assert response.json() == {
        "error": {
            "code": "AI_PROVIDER_UNAVAILABLE",
            "message": "The configured AI provider is unavailable.",
            "request_id": body["request_id"],
        }
    }


def test_validation_rejects_blank_content_with_contract_error_shape(
    client: TestClient,
) -> None:
    body = request_body()
    body["messages"] = [{"role": "user", "content": "   "}]

    response = client.post("/internal/v1/generate", json=body)

    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "VALIDATION_ERROR",
            "message": "Request payload is invalid.",
            "request_id": body["request_id"],
        }
    }


def test_validation_rejects_unknown_role(client: TestClient) -> None:
    body = request_body()
    body["messages"] = [{"role": "tool", "content": "invalid role"}]

    response = client.post("/internal/v1/generate", json=body)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert response.json()["error"]["request_id"] == body["request_id"]


def test_validation_rejects_invalid_max_output_tokens(client: TestClient) -> None:
    body = request_body()
    body["max_output_tokens"] = 0

    response = client.post("/internal/v1/generate", json=body)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert response.json()["error"]["request_id"] == body["request_id"]
