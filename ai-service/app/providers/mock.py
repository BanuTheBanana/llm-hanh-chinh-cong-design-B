import asyncio
from collections.abc import Sequence

from app.config import MockMode
from app.providers.base import (
    AIProvider,
    GenerationResult,
    ProviderError,
    ProviderTimeoutError,
)
from app.schemas import ChatMessage


class MockProvider(AIProvider):
    """Deterministic provider for G1 plumbing and failure-path tests."""

    name = "mock"
    model_name = "mock-v1"
    response_text = (
        "Đây là phản hồi mô phỏng cho câu hỏi của bạn. "
        "Nội dung này chỉ dùng để kiểm thử kỹ thuật G1, không phải tư vấn hành chính."
    )

    def __init__(
        self,
        *,
        mode: MockMode = "success",
        latency_ms: int = 10,
        timeout_seconds: float = 5.0,
    ) -> None:
        if mode not in {"success", "error", "timeout"}:
            raise ValueError(f"unsupported mock mode: {mode}")
        if latency_ms < 0:
            raise ValueError("latency_ms must be non-negative")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self.mode = mode
        self.latency_ms = latency_ms
        self.timeout_seconds = timeout_seconds

    async def generate(
        self,
        messages: Sequence[ChatMessage],
        max_output_tokens: int,
    ) -> GenerationResult:
        # Touch the arguments so the mock has the same callable contract as real providers.
        _ = messages, max_output_tokens

        if self.latency_ms:
            await asyncio.sleep(self.latency_ms / 1000)

        if self.mode == "error":
            raise ProviderError("configured mock error")

        if self.mode == "timeout":
            # Keeping the request open lets Core Backend exercise its own HTTP timeout.
            await asyncio.sleep(self.timeout_seconds)
            raise ProviderTimeoutError("configured mock timeout")

        return GenerationResult(
            text=self.response_text,
            provider=self.name,
            model=self.model_name,
        )
