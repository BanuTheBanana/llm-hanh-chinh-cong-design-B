from fastapi import Depends

from app.config import Settings, get_settings
from app.providers.base import AIProvider, UnsupportedProviderError
from app.providers.mock import MockProvider


def get_provider(settings: Settings = Depends(get_settings)) -> AIProvider:
    if settings.llm_provider != "mock":
        raise UnsupportedProviderError(settings.llm_provider)

    return MockProvider(
        mode=settings.mock_mode,
        latency_ms=settings.mock_latency_ms,
        timeout_seconds=settings.mock_timeout_seconds,
    )
