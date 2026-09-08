from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Sequence

from app.schemas import ChatMessage


@dataclass(frozen=True, slots=True)
class GenerationResult:
    text: str
    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0


class ProviderError(Exception):
    """A predictable provider failure safe to map to the internal API."""

    code = "AI_PROVIDER_ERROR"
    public_message = "AI Service is temporarily unavailable."


class ProviderTimeoutError(ProviderError):
    code = "AI_SERVICE_TIMEOUT"
    public_message = "AI Service timed out. Please try again."


class UnsupportedProviderError(ProviderError):
    code = "AI_PROVIDER_UNAVAILABLE"
    public_message = "The configured AI provider is unavailable."


class AIProvider(ABC):
    """Provider boundary kept stable when hosted/local providers are added later."""

    name: str
    model_name: str

    @abstractmethod
    async def generate(
        self,
        messages: Sequence[ChatMessage],
        max_output_tokens: int,
    ) -> GenerationResult:
        raise NotImplementedError
