import json

import httpx
import pytest
import pytest_asyncio
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.main import create_app
from app.providers.base import ProviderError, ProviderResponseError, ProviderTimeoutError
from app.providers.grounded_base import GroundedGenerationResult
from app.providers.local_grounded import (
    GROUNDED_OUTPUT_JSON_SCHEMA,
    LocalGroundedProvider,
)
from app.schemas import GroundingEvidenceFragment


def evidence_fragment(
    fragment_id: str = "frag_001", *, text: str = "Hồ sơ cần nộp Phiếu A."
) -> GroundingEvidenceFragment:
    return GroundingEvidenceFragment(
        fragment_id=fragment_id,
        source_id="src_001",
        procedure_id="proc_001",
        section_type="REQUIRED_DOCUMENTS",
        title="Nguồn thử nghiệm",
        text=text,
        jurisdiction="DEMO",
        validity_status="UNKNOWN",
    )


def make_openai_response(
    answer: str = "Theo nguồn, cần Phiếu A.",
    status: str = "ANSWER",
    cited_ids: list[str] | None = None,
    missing: list[str] | None = None,
    input_tokens: int = 100,
    output_tokens: int = 50,
) -> dict[str, object]:
    if cited_ids is None:
        cited_ids = ["frag_001"]
    if missing is None:
        missing = []
    content = json.dumps(
        {
            "answer": answer,
            "status": status,
            "cited_fragment_ids": cited_ids,
            "missing_information": missing,
        },
        ensure_ascii=False,
    )
    return {
        "choices": [{"message": {"role": "assistant", "content": content}}],
        "usage": {"prompt_tokens": input_tokens, "completion_tokens": output_tokens},
    }


@pytest_asyncio.fixture
async def provider_factory():
    providers: list[LocalGroundedProvider] = []

    def make(handler, **overrides: object) -> LocalGroundedProvider:
        config: dict[str, object] = {
            "base_url": "http://localhost:8080/v1",
            "model_name": "test-model",
            "timeout_seconds": 30.0,
            "context_tokens": 4096,
            "max_prompt_characters": 8000,
            "max_output_tokens": 500,
            "client": httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        }
        config.update(overrides)
        provider = LocalGroundedProvider(**config)  # type: ignore[arg-type]
        providers.append(provider)
        return provider

    yield make

    for provider in providers:
        await provider.aclose()


async def generate(provider: LocalGroundedProvider, **overrides: object):
    arguments: dict[str, object] = {
        "query": "Cần nộp phiếu nào?",
        "evidence": [evidence_fragment()],
        "as_of": None,
        "data_classification": "D0_SYSTEM_SMOKE",
        "max_output_tokens": 200,
    }
    arguments.update(overrides)
    return await provider.generate_grounded(**arguments)  # type: ignore[arg-type]


async def test_valid_response_sends_locked_llama_cpp_payload(provider_factory):
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "http://localhost:8080/v1/chat/completions"
        payload = json.loads(request.content)
        assert payload["model"] == "test-model"
        assert payload["stream"] is False
        assert payload["max_tokens"] == 200
        assert payload["temperature"] == 0.7
        assert payload["top_p"] == 0.8
        assert payload["top_k"] == 20
        assert payload["min_p"] == 0.0
        assert payload["presence_penalty"] == 1.5
        assert payload["seed"] == 42
        assert payload["response_format"] == {"type": "json_object"}
        assert payload["json_schema"] == GROUNDED_OUTPUT_JSON_SCHEMA
        return httpx.Response(200, json=make_openai_response())

    result = await generate(provider_factory(handler))

    assert isinstance(result, GroundedGenerationResult)
    assert result.status == "ANSWER"
    assert result.cited_fragment_ids == ("frag_001",)
    assert result.provider == "local"
    assert result.model == "test-model"
    assert result.input_tokens == 100
    assert result.output_tokens == 50


async def test_request_output_tokens_are_capped_by_provider(provider_factory):
    def handler(request: httpx.Request) -> httpx.Response:
        assert json.loads(request.content)["max_tokens"] == 300
        return httpx.Response(200, json=make_openai_response())

    provider = provider_factory(handler, max_output_tokens=300)
    await generate(provider, max_output_tokens=1000)


async def test_invalid_http_json_raises_provider_response_error(provider_factory):
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"not-json")

    with pytest.raises(ProviderResponseError):
        await generate(provider_factory(handler))


async def test_malformed_model_json_raises_provider_response_error(provider_factory):
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "not valid json"}}]},
        )

    with pytest.raises(ProviderResponseError):
        await generate(provider_factory(handler))


@pytest.mark.parametrize(
    "body",
    [
        [],
        {"choices": [None]},
        {"choices": [{"message": None}]},
        {
            "choices": [{"message": {"content": "{}"}}],
            "usage": None,
        },
        {
            "choices": [{"message": {"content": "{}"}}],
            "usage": {"prompt_tokens": True, "completion_tokens": 1},
        },
    ],
)
async def test_malformed_openai_envelope_raises_provider_response_error(
    provider_factory, body: object
):
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=body)

    with pytest.raises(ProviderResponseError):
        await generate(provider_factory(handler))


async def test_forged_citation_raises_provider_response_error(provider_factory):
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=make_openai_response(cited_ids=["frag_not_in_evidence"]),
        )

    with pytest.raises(ProviderResponseError):
        await generate(provider_factory(handler))


@pytest.mark.parametrize(
    "message_patch",
    [
        {"reasoning_content": "hidden reasoning"},
        {"content": "<think>hidden reasoning</think>{}"},
    ],
)
async def test_thinking_output_is_rejected(provider_factory, message_patch: dict):
    response_body = make_openai_response()
    response_body["choices"][0]["message"].update(message_patch)  # type: ignore[index,union-attr]

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=response_body)

    with pytest.raises(ProviderResponseError):
        await generate(provider_factory(handler))


async def test_timeout_raises_provider_timeout_error(provider_factory):
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timeout")

    with pytest.raises(ProviderTimeoutError):
        await generate(provider_factory(handler))


async def test_http_error_raises_provider_response_error(provider_factory):
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "unavailable"})

    with pytest.raises(ProviderResponseError):
        await generate(provider_factory(handler))


async def test_connection_error_raises_provider_error(provider_factory):
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.RequestError("connection failed")

    with pytest.raises(ProviderError):
        await generate(provider_factory(handler))


async def test_missing_usage_defaults_to_zero(provider_factory):
    response_body = make_openai_response()
    del response_body["usage"]

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=response_body)

    result = await generate(provider_factory(handler))

    assert result.input_tokens == 0
    assert result.output_tokens == 0


async def test_prompt_over_character_budget_is_rejected_before_http_call(provider_factory):
    def handler(_request: httpx.Request) -> httpx.Response:
        raise AssertionError("HTTP client must not be called")

    provider = provider_factory(handler, max_prompt_characters=2000)
    with pytest.raises(ProviderResponseError):
        await generate(provider, evidence=[evidence_fragment(text="A" * 3000)])


def test_external_or_credentialed_base_urls_are_rejected():
    base_config = {
        "model_name": "test-model",
        "timeout_seconds": 30.0,
        "context_tokens": 4096,
        "max_prompt_characters": 8000,
        "max_output_tokens": 500,
    }

    with pytest.raises(ValueError):
        LocalGroundedProvider(base_url="https://api.example.com/v1", **base_config)
    with pytest.raises(ValueError):
        LocalGroundedProvider(base_url="http://user:pass@localhost:8080/v1", **base_config)


def test_greedy_sampling_configuration_is_rejected():
    with pytest.raises(ValueError):
        LocalGroundedProvider(
            base_url="http://localhost:8080/v1",
            model_name="test-model",
            timeout_seconds=30.0,
            context_tokens=4096,
            max_prompt_characters=8000,
            max_output_tokens=500,
            temperature=0.0,
        )


async def test_provider_only_allows_synthetic_d0():
    provider = LocalGroundedProvider(
        base_url="http://localhost:8080/v1",
        model_name="test-model",
        timeout_seconds=30.0,
        context_tokens=4096,
        max_prompt_characters=8000,
        max_output_tokens=500,
    )

    assert provider.allowed_data_classifications == frozenset({"D0_SYSTEM_SMOKE"})
    assert provider.external_calls_enabled is False
    assert provider.name == "local"
    await provider.aclose()


def test_application_reuses_and_closes_local_provider():
    application = create_app()
    application.dependency_overrides[get_settings] = lambda: Settings(
        grounded_provider="local",
        local_llm_base_url="http://localhost:8080/v1",
        local_llm_model="test-model",
    )

    with TestClient(application) as client:
        assert client.get("/internal/v2/health").status_code == 200
        assert client.get("/internal/v2/health").status_code == 200
        providers = list(application.state.local_grounded_providers.values())
        assert len(providers) == 1
        provider = providers[0]
        assert provider._client.is_closed is False

    assert provider._client.is_closed is True
