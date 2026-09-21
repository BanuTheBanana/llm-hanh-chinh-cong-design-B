import json
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.dependencies import get_intent_context_provider
from app.main import create_app
from app.providers.base import ProviderPolicyError, ProviderResponseError
from app.providers.intent_context_base import (
    IntentContextGenerationResult,
    IntentContextProvider,
)
from app.providers.local_intent_context import (
    INTENT_OUTPUT_JSON_SCHEMA,
    LocalIntentContextProvider,
)
from app.schemas import IntentContextModelOutput, IntentContextRequest


def request_body(*, classification="D0_SYSTEM_SMOKE"):
    # Keep this transport fixture outside deterministic field fast paths so tests
    # below exercise model request/response validation rather than routing policy.
    message = "Tôi muốn hỏi thông tin về đăng ký khai sinh."
    return {
        "request_id": str(uuid4()),
        "current_message_id": str(uuid4()),
        "current_user_message": message,
        "state_before": {
            "procedure_id": None,
            "field_intents": [],
            "jurisdiction": None,
            "as_of": None,
            "pending_clarification": None,
        },
        "procedure_candidates": [{"id": "p_birth", "name": "Đăng ký khai sinh"}],
        "data_classification": classification,
        "max_output_tokens": 384,
    }


def model_output(body, *, procedure="p_birth"):
    return {
        "schema_version": "g5-intent-context-compact-v1",
        "dialogue_act": "ASK_INFORMATION",
        "topic_action": "SWITCH",
        "patch": {
            "procedure_id": {"op": "SET", "value": procedure},
            "field_intents": {"op": "SET", "value": ["fees"]},
            "jurisdiction": {"op": "KEEP", "value": None},
            "as_of": {"op": "KEEP", "value": None},
        },
    }


def completion(output):
    return {
        "choices": [{"message": {"content": json.dumps(output, ensure_ascii=False)}}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 50},
    }


@pytest_asyncio.fixture
async def provider_factory():
    providers = []

    def make(handler, *, allow_d2=False):
        provider = LocalIntentContextProvider(
            base_url="http://localhost:8087/v1",
            model_name="intent-test",
            timeout_seconds=30,
            context_tokens=4096,
            max_prompt_characters=12000,
            max_output_tokens=384,
            seed=42,
            allow_d2_company_data=allow_d2,
            allowed_hosts=frozenset({"localhost"}),
            client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        )
        providers.append(provider)
        return provider

    yield make
    for provider in providers:
        await provider.aclose()


async def test_local_provider_sends_deterministic_constrained_request(provider_factory):
    body = request_body()

    def handler(request):
        payload = json.loads(request.content)
        assert payload["temperature"] == 0
        assert payload["top_k"] == 1
        assert payload["seed"] == 42
        assert payload["chat_template_kwargs"] == {"enable_thinking": False}
        assert payload["response_format"] == {
            "type": "json_object",
            "schema": INTENT_OUTPUT_JSON_SCHEMA,
        }
        assert "json_schema" not in payload
        return httpx.Response(200, json=completion(model_output(body)))

    result = await provider_factory(handler).analyze(IntentContextRequest.model_validate(body))

    assert result.output.patch.procedure_id.value == "p_birth"
    assert result.input_tokens == 100
    assert result.output_tokens == 50


async def test_high_confidence_route_skips_the_model(provider_factory):
    body = request_body()
    body["current_user_message"] = "Đăng ký khai sinh cần chuẩn bị giấy tờ nào?"
    calls = 0

    def handler(_request):
        nonlocal calls
        calls += 1
        return httpx.Response(500)

    result = await provider_factory(handler).analyze(IntentContextRequest.model_validate(body))
    assert result.output.patch.procedure_id.value == "p_birth"
    assert result.output.patch.field_intents.value == ["required_documents"]
    assert result.input_tokens == 0
    assert result.output_tokens == 0
    assert result.policy_actions == ("DETERMINISTIC_HIGH_CONFIDENCE_ROUTE",)
    assert calls == 0


async def test_realistic_multifield_story_skips_model_and_returns_all_fields(provider_factory):
    body = request_body()
    body["current_user_message"] = (
        "Tôi đang ở phường Tăng Nhơn Phú, vừa có con và muốn đăng ký khai sinh. "
        "Tôi muốn biết cần chuẩn bị giấy tờ gì, có nộp trực tuyến được không, "
        "nộp ở đâu, mất bao lâu và có phải đóng lệ phí không?"
    )
    calls = 0

    def handler(_request):
        nonlocal calls
        calls += 1
        return httpx.Response(500)

    result = await provider_factory(handler).analyze(IntentContextRequest.model_validate(body))

    assert result.output.patch.procedure_id.value == "p_birth"
    assert result.output.patch.field_intents.value == [
        "fees",
        "processing_times",
        "receiving_authority",
        "required_documents",
        "submission_methods",
    ]
    assert result.output.patch.jurisdiction.op == "KEEP"
    assert result.input_tokens == 0
    assert result.output_tokens == 0
    assert result.policy_actions == (
        "DETERMINISTIC_HIGH_CONFIDENCE_ROUTE",
        "INCIDENTAL_LOCATION_NOT_USED_AS_LEGAL_FILTER",
    )
    assert calls == 0


async def test_model_path_hydrates_bounded_literal_evidence_for_long_message(provider_factory):
    body = request_body()
    body["current_user_message"] = (
        "Tôi xin trình bày thêm hoàn cảnh để cơ quan có thể hiểu đúng yêu cầu. " * 7
        + "Liệu việc này có phát sinh khoản nào không?"
    )

    def handler(_request):
        return httpx.Response(200, json=completion(model_output(body)))

    result = await provider_factory(handler).analyze(IntentContextRequest.model_validate(body))

    for slot in (result.output.patch.procedure_id, result.output.patch.field_intents):
        assert len(slot.evidence[0].quote) <= 300
        assert slot.evidence[0].quote in body["current_user_message"]


async def test_unknown_procedure_is_retried_once_then_rejected(provider_factory):
    body = request_body()
    calls = 0

    def handler(_request):
        nonlocal calls
        calls += 1
        return httpx.Response(200, json=completion(model_output(body, procedure="forged")))

    with pytest.raises(ProviderResponseError):
        await provider_factory(handler).analyze(IntentContextRequest.model_validate(body))
    assert calls == 2


async def test_false_reset_label_is_recovered_from_current_message(provider_factory):
    body = request_body()
    invalid = model_output(body)
    invalid["dialogue_act"] = "RESET_CONTEXT"
    calls = 0

    def handler(_request):
        nonlocal calls
        calls += 1
        return httpx.Response(200, json=completion(invalid))

    result = await provider_factory(handler).analyze(IntentContextRequest.model_validate(body))
    assert result.output.dialogue_act == "ASK_INFORMATION"
    assert result.output.topic_action == "SWITCH"
    assert result.policy_actions == (
        "UNSUPPORTED_RESET_DOWNGRADED",
        "CATALOG_PROCEDURE_RECOVERED",
    )
    assert calls == 1


async def test_policy_intent_cannot_mutate_existing_context(provider_factory):
    body = request_body()
    body["state_before"]["procedure_id"] = "p_birth"
    body["current_user_message"] = "Viết giúp tôi một bài thơ."
    invalid = model_output(body)
    invalid["dialogue_act"] = "OUT_OF_SCOPE"
    invalid["topic_action"] = "UNRESOLVED"

    def handler(_request):
        return httpx.Response(200, json=completion(invalid))

    result = await provider_factory(handler).analyze(IntentContextRequest.model_validate(body))
    assert result.output.topic_action == "KEEP"
    assert all(
        getattr(result.output.patch, slot).op == "KEEP"
        for slot in ("procedure_id", "field_intents", "jurisdiction", "as_of")
    )


def test_state_contract_accepts_as_of_clarification():
    body = request_body()
    body["state_before"]["pending_clarification"] = "as_of"
    assert IntentContextRequest.model_validate(body).state_before.pending_clarification == "as_of"


async def test_d2_requires_explicit_local_permission(provider_factory):
    body = request_body(classification="D2_COMPANY_REAL")

    def handler(_request):
        return httpx.Response(200, json=completion(model_output(body)))

    with pytest.raises(ProviderPolicyError):
        await provider_factory(handler).analyze(IntentContextRequest.model_validate(body))
    result = await provider_factory(handler, allow_d2=True).analyze(
        IntentContextRequest.model_validate(body)
    )
    assert result.output.patch.field_intents.value == ["fees"]


class StubIntentProvider(IntentContextProvider):
    name = "stub-intent"
    model_name = "stub-intent-v1"
    external_calls_enabled = False
    allowed_data_classifications = frozenset({"D0_SYSTEM_SMOKE"})

    async def analyze(self, payload):
        raw = model_output(payload.model_dump(mode="json"))
        raw["schema_version"] = "g5-intent-context-v2"
        for operation in raw["patch"].values():
            operation["evidence"] = (
                []
                if operation["op"] == "KEEP"
                else [
                    {
                        "message_id": payload.current_message_id,
                        "quote": payload.current_user_message,
                    }
                ]
            )
        output = IntentContextModelOutput.model_validate(raw)
        return IntentContextGenerationResult(output, self.name, self.model_name, 10, 5)


def test_internal_intent_endpoint_and_health_contract():
    application = create_app()
    application.dependency_overrides[get_intent_context_provider] = lambda: StubIntentProvider()
    with TestClient(application) as client:
        body = request_body()
        response = client.post("/internal/v3/intent-context", json=body)
        assert response.status_code == 200
        assert response.json()["output"]["patch"]["procedure_id"]["value"] == "p_birth"
        health = client.get("/internal/v3/intent-context/health")
        assert health.status_code == 200
        assert health.json()["endpoint"] == "intent-context-v2"


def test_dependency_reuses_and_closes_local_intent_provider():
    application = create_app()
    application.dependency_overrides[get_settings] = lambda: Settings(
        intent_context_provider="local",
        intent_llm_base_url="http://localhost:8087/v1",
        intent_llm_allowed_hosts="localhost",
    )
    with TestClient(application) as client:
        assert client.get("/internal/v3/intent-context/health").status_code == 200
        assert client.get("/internal/v3/intent-context/health").status_code == 200
        providers = list(application.state.local_intent_context_providers.values())
        assert len(providers) == 1
        provider = providers[0]
        assert provider._client.is_closed is False
    assert provider._client.is_closed is True
