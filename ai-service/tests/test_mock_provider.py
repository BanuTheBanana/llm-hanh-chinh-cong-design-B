import pytest

from app.providers.base import ProviderError, ProviderTimeoutError
from app.providers.mock import MockProvider
from app.schemas import ChatMessage

MESSAGES = [ChatMessage(role="user", content="Smoke test")]


@pytest.mark.anyio
async def test_mock_provider_success_is_deterministic() -> None:
    provider = MockProvider(mode="success", latency_ms=0)

    first = await provider.generate(MESSAGES, 300)
    second = await provider.generate(MESSAGES, 300)

    assert first == second
    assert first.provider == "mock"
    assert first.model == "mock-v1"


@pytest.mark.anyio
async def test_mock_provider_error_mode() -> None:
    provider = MockProvider(mode="error", latency_ms=0)

    with pytest.raises(ProviderError):
        await provider.generate(MESSAGES, 300)


@pytest.mark.anyio
async def test_mock_provider_timeout_mode() -> None:
    provider = MockProvider(mode="timeout", latency_ms=0, timeout_seconds=0.001)

    with pytest.raises(ProviderTimeoutError):
        await provider.generate(MESSAGES, 300)
