import asyncio
from uuid import UUID

import httpx
from fastapi import Request
from pydantic import ValidationError

from app.config import get_settings
from app.errors import APIError
from app.schemas import AIOutput


class AIClient:
    def __init__(self, client: httpx.AsyncClient):
        self.client = client

    async def generate(self, request_id: UUID, messages: list[dict]) -> str:
        settings = get_settings()
        try:
            # A wall-clock deadline also bounds a response that keeps streaming bytes.
            async with asyncio.timeout(settings.ai_timeout_seconds):
                response = await self.client.post(
                    settings.ai_service_url.rstrip("/") + "/generate",
                    json={
                        "request_id": str(request_id),
                        "messages": messages,
                        "max_output_tokens": 300,
                    },
                    timeout=settings.ai_timeout_seconds,
                )
                response.raise_for_status()
                result = AIOutput.model_validate(response.json())
                if result.request_id != request_id or not result.text.strip():
                    raise ValueError("Invalid AI response")
                return result.text
        except (httpx.TimeoutException, TimeoutError) as exc:
            raise APIError(
                504, "AI_SERVICE_TIMEOUT", "AI đang phản hồi chậm. Vui lòng thử lại."
            ) from exc
        except (httpx.HTTPError, ValidationError, ValueError) as exc:
            raise APIError(
                502, "AI_SERVICE_ERROR", "Không thể nhận phản hồi từ AI. Vui lòng thử lại."
            ) from exc


def get_ai(request: Request) -> AIClient:
    return request.app.state.ai
