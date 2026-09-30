from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class RuntimeResponse:
    text: str
    elapsed_ms: float
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


class ChatRuntime(Protocol):
    def complete(self, messages: list[dict[str, str]]) -> RuntimeResponse: ...


class StaticRuntime:
    """Deterministic runtime for unit tests and offline contract work."""

    def __init__(self, text: str):
        self.text = text
        self.calls: list[list[dict[str, str]]] = []

    def complete(self, messages: list[dict[str, str]]) -> RuntimeResponse:
        self.calls.append(messages)
        return RuntimeResponse(self.text, elapsed_ms=0.0)


class LlamaCppHTTPRuntime:
    """Small OpenAI-compatible client for a local llama.cpp/llama-server style endpoint."""

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        api_key: str | None = None,
        timeout_seconds: float = 120.0,
        temperature: float = 0.0,
        seed: int = 42,
        max_tokens: int = 768,
        json_mode: bool = True,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.temperature = temperature
        self.seed = seed
        self.max_tokens = max_tokens
        self.json_mode = json_mode

    def complete(self, messages: list[dict[str, str]]) -> RuntimeResponse:
        payload: dict = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "seed": self.seed,
            "max_tokens": self.max_tokens,
        }
        if self.json_mode:
            payload["response_format"] = {"type": "json_object"}

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        request = urllib.request.Request(
            f"{self.base_url}/v1/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers=headers,
            method="POST",
        )

        started = time.perf_counter()
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"local model HTTP {exc.code}: {detail[:1000]}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"local model unavailable: {exc.reason}") from exc
        elapsed_ms = (time.perf_counter() - started) * 1000.0

        try:
            text = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("local model response did not contain choices[0].message.content") from exc

        usage = body.get("usage") or {}
        return RuntimeResponse(
            text=text,
            elapsed_ms=elapsed_ms,
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
        )
