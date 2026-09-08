from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

NonBlankContent = Annotated[str, StringConstraints(min_length=1, max_length=16_000)]


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["system", "user", "assistant"]
    content: NonBlankContent

    @field_validator("content")
    @classmethod
    def reject_blank_content(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("message content must not be blank")
        return value


class GenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: UUID
    messages: list[ChatMessage] = Field(min_length=1, max_length=100)
    max_output_tokens: int = Field(ge=1, le=4096, strict=True)


class Usage(BaseModel):
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)


class GenerateResponse(BaseModel):
    request_id: UUID
    text: str
    provider: str
    model: str
    usage: Usage
    latency_ms: int = Field(ge=0)


class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: UUID


class ErrorResponse(BaseModel):
    error: ErrorDetail


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: Literal["ai-service"] = "ai-service"
    provider: str
