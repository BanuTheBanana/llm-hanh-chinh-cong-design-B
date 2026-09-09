import asyncio

from fastapi import Depends, FastAPI, Request

from app.config import Settings, get_settings
from app.providers.base import AIProvider, UnsupportedProviderError
from app.providers.grounded_base import GroundedProvider
from app.providers.local_grounded import LocalGroundedProvider
from app.providers.mock import MockProvider
from app.providers.template_grounded import TemplateGroundedProvider

LocalProviderKey = tuple[
    str, str, float, int, int, int, float, float, int, float, float, int, bool, str
]


def get_provider(settings: Settings = Depends(get_settings)) -> AIProvider:
    if settings.llm_provider != "mock":
        raise UnsupportedProviderError(settings.llm_provider)

    return MockProvider(
        mode=settings.mock_mode,
        latency_ms=settings.mock_latency_ms,
        timeout_seconds=settings.mock_timeout_seconds,
    )


def initialize_grounded_provider_cache(application: FastAPI) -> None:
    application.state.local_grounded_providers = {}
    application.state.local_grounded_provider_lock = asyncio.Lock()


async def close_grounded_provider_cache(application: FastAPI) -> None:
    providers: dict[LocalProviderKey, LocalGroundedProvider] = (
        application.state.local_grounded_providers
    )
    application.state.local_grounded_providers = {}
    for provider in providers.values():
        await provider.aclose()


def _local_provider_key(settings: Settings) -> LocalProviderKey:
    return (
        settings.local_llm_base_url,
        settings.local_llm_model,
        settings.local_llm_timeout_seconds,
        settings.local_llm_context,
        settings.local_llm_max_prompt_characters,
        settings.local_llm_max_output_tokens,
        settings.local_llm_temperature,
        settings.local_llm_top_p,
        settings.local_llm_top_k,
        settings.local_llm_min_p,
        settings.local_llm_presence_penalty,
        settings.local_llm_seed,
        settings.local_llm_allow_d2_company_data,
        settings.local_llm_allowed_hosts,
    )


def _create_local_grounded_provider(settings: Settings) -> LocalGroundedProvider:
    allowed_hosts = frozenset(
        host.strip().lower() for host in settings.local_llm_allowed_hosts.split(",") if host.strip()
    )
    try:
        return LocalGroundedProvider(
            base_url=settings.local_llm_base_url,
            model_name=settings.local_llm_model,
            timeout_seconds=settings.local_llm_timeout_seconds,
            context_tokens=settings.local_llm_context,
            max_prompt_characters=settings.local_llm_max_prompt_characters,
            max_output_tokens=settings.local_llm_max_output_tokens,
            temperature=settings.local_llm_temperature,
            top_p=settings.local_llm_top_p,
            top_k=settings.local_llm_top_k,
            min_p=settings.local_llm_min_p,
            presence_penalty=settings.local_llm_presence_penalty,
            seed=settings.local_llm_seed,
            allow_d2_company_data=settings.local_llm_allow_d2_company_data,
            allowed_hosts=allowed_hosts,
        )
    except ValueError as exc:
        raise UnsupportedProviderError("local") from exc


async def get_grounded_provider(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> GroundedProvider:
    if settings.grounded_provider == "template":
        return TemplateGroundedProvider()
    if settings.grounded_provider == "local":
        key = _local_provider_key(settings)
        providers: dict[LocalProviderKey, LocalGroundedProvider] = (
            request.app.state.local_grounded_providers
        )
        provider = providers.get(key)
        if provider is not None:
            return provider
        async with request.app.state.local_grounded_provider_lock:
            provider = providers.get(key)
            if provider is None:
                provider = _create_local_grounded_provider(settings)
                providers[key] = provider
            return provider
    raise UnsupportedProviderError(settings.grounded_provider)
