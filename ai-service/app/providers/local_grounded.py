import json
from collections.abc import Sequence
from datetime import date
from urllib.parse import urlsplit

import httpx

from app.grounding import build_grounded_messages, parse_and_validate_grounded_output
from app.providers.base import ProviderError, ProviderResponseError, ProviderTimeoutError
from app.providers.grounded_base import GroundedGenerationResult, GroundedProvider
from app.schemas import GroundedDataClassification, GroundingEvidenceFragment

DEFAULT_LOCAL_ALLOWED_HOSTS = frozenset(
    {"127.0.0.1", "::1", "host.docker.internal", "local-model", "localhost"}
)

# llama.cpp converts this top-level json_schema to a constrained-output grammar.
# Pydantic validation below remains mandatory because the runtime is untrusted.
GROUNDED_OUTPUT_JSON_SCHEMA: dict[str, object] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "answer",
        "status",
        "cited_fragment_ids",
        "missing_information",
    ],
    "properties": {
        "answer": {"type": "string", "minLength": 1, "maxLength": 8000},
        "status": {
            "type": "string",
            "enum": ["ANSWER", "NEED_CLARIFICATION", "INSUFFICIENT_DATA"],
        },
        "cited_fragment_ids": {
            "type": "array",
            "maxItems": 8,
            "items": {"type": "string"},
        },
        "missing_information": {
            "type": "array",
            "maxItems": 10,
            "items": {"type": "string"},
        },
    },
}


class LocalGroundedProvider(GroundedProvider):
    """Grounded generation through an allowlisted local llama.cpp endpoint."""

    name = "local"
    external_calls_enabled = False
    allowed_data_classifications: frozenset[GroundedDataClassification] = frozenset(
        {"D0_SYSTEM_SMOKE"}
    )

    def __init__(
        self,
        *,
        base_url: str,
        model_name: str,
        timeout_seconds: float,
        context_tokens: int,
        max_prompt_characters: int,
        max_output_tokens: int,
        temperature: float = 0.7,
        top_p: float = 0.8,
        top_k: int = 20,
        min_p: float = 0.0,
        presence_penalty: float = 1.5,
        seed: int = 42,
        allowed_hosts: frozenset[str] = DEFAULT_LOCAL_ALLOWED_HOSTS,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.model_name = model_name
        self._base_url = self._validate_base_url(base_url, allowed_hosts)
        self._context_tokens = context_tokens
        self._max_prompt_characters = max_prompt_characters
        self._max_output_tokens = max_output_tokens
        self._temperature = temperature
        self._top_p = top_p
        self._top_k = top_k
        self._min_p = min_p
        self._presence_penalty = presence_penalty
        self._seed = seed
        self._validate_generation_config()
        self._client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(timeout_seconds),
            limits=httpx.Limits(
                max_connections=20,
                max_keepalive_connections=10,
                keepalive_expiry=30.0,
            ),
            follow_redirects=False,
            trust_env=False,
        )

    @staticmethod
    def _validate_base_url(base_url: str, allowed_hosts: frozenset[str]) -> str:
        parsed = urlsplit(base_url)
        allowed = {host.strip().lower() for host in allowed_hosts if host.strip()}
        hostname = parsed.hostname.lower() if parsed.hostname else None
        if (
            parsed.scheme != "http"
            or hostname not in allowed
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("local LLM base URL must be an allowlisted HTTP origin/path")
        return base_url.rstrip("/")

    def _validate_generation_config(self) -> None:
        if not self.model_name.strip():
            raise ValueError("local LLM model name must not be blank")
        if self._context_tokens < 512:
            raise ValueError("local LLM context must be at least 512 tokens")
        if self._max_prompt_characters < 1000:
            raise ValueError("local LLM prompt character cap must be at least 1000")
        if not 32 <= self._max_output_tokens < self._context_tokens:
            raise ValueError("local LLM output cap must fit inside its context")
        if not 0.0 < self._temperature <= 2.0:
            raise ValueError("local LLM temperature must be non-greedy and at most 2")
        if not 0.0 < self._top_p <= 1.0:
            raise ValueError("local LLM top_p must be in (0, 1]")
        if self._top_k < 1:
            raise ValueError("local LLM top_k must be positive")
        if not 0.0 <= self._min_p <= 1.0:
            raise ValueError("local LLM min_p must be in [0, 1]")
        if not -2.0 <= self._presence_penalty <= 2.0:
            raise ValueError("local LLM presence penalty must be in [-2, 2]")

    async def aclose(self) -> None:
        """Release the shared HTTP connection pool during application shutdown."""

        await self._client.aclose()

    async def generate_grounded(
        self,
        *,
        query: str,
        evidence: Sequence[GroundingEvidenceFragment],
        as_of: date | None,
        data_classification: GroundedDataClassification,
        max_output_tokens: int,
    ) -> GroundedGenerationResult:
        if data_classification not in self.allowed_data_classifications:
            raise AssertionError("service boundary must reject unsupported classifications")

        messages = build_grounded_messages(query=query, evidence=evidence, as_of=as_of)
        prompt_characters = sum(len(message["content"]) for message in messages)
        if prompt_characters > self._max_prompt_characters:
            raise ProviderResponseError("local model prompt exceeds configured safe budget")

        payload = {
            "model": self.model_name,
            "messages": messages,
            "stream": False,
            "max_tokens": min(max_output_tokens, self._max_output_tokens),
            "temperature": self._temperature,
            "top_p": self._top_p,
            "top_k": self._top_k,
            "min_p": self._min_p,
            "presence_penalty": self._presence_penalty,
            "seed": self._seed,
            "response_format": {"type": "json_object"},
            "json_schema": GROUNDED_OUTPUT_JSON_SCHEMA,
        }

        try:
            response = await self._client.post(f"{self._base_url}/chat/completions", json=payload)
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError() from exc
        except httpx.HTTPStatusError as exc:
            raise ProviderResponseError("local model returned HTTP error") from exc
        except httpx.RequestError as exc:
            raise ProviderError("local model request failed") from exc
        except RuntimeError as exc:
            raise ProviderError("local model client is not available") from exc

        try:
            data = response.json()
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ProviderResponseError("local model returned invalid JSON") from exc
        if not isinstance(data, dict):
            raise ProviderResponseError("local model response must be an object")

        choices = data.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ProviderResponseError("local model response missing choices")
        choice = choices[0]
        if not isinstance(choice, dict):
            raise ProviderResponseError("local model response has invalid choice")
        message = choice.get("message")
        if not isinstance(message, dict):
            raise ProviderResponseError("local model response has invalid message")

        reasoning_content = message.get("reasoning_content")
        if reasoning_content not in (None, ""):
            raise ProviderResponseError("local model violated non-thinking mode")
        raw_content = message.get("content")
        if not isinstance(raw_content, str) or not raw_content.strip():
            raise ProviderResponseError("local model response missing content")
        if "<think>" in raw_content or "</think>" in raw_content:
            raise ProviderResponseError("local model leaked thinking content")

        if "usage" not in data:
            usage_data: dict[str, object] = {}
        else:
            raw_usage = data["usage"]
            if not isinstance(raw_usage, dict):
                raise ProviderResponseError("local model response has invalid usage")
            usage_data = raw_usage
        input_tokens = usage_data.get("prompt_tokens", 0)
        output_tokens = usage_data.get("completion_tokens", 0)
        if type(input_tokens) is not int or input_tokens < 0:
            raise ProviderResponseError("local model returned invalid prompt token usage")
        if type(output_tokens) is not int or output_tokens < 0:
            raise ProviderResponseError("local model returned invalid completion token usage")

        validated = parse_and_validate_grounded_output(
            raw_text=raw_content,
            allowed_fragment_ids={fragment.fragment_id for fragment in evidence},
        )
        return GroundedGenerationResult(
            answer=validated.answer,
            status=validated.status,
            cited_fragment_ids=tuple(validated.cited_fragment_ids),
            missing_information=tuple(validated.missing_information),
            provider=self.name,
            model=self.model_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
