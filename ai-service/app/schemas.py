from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

NonBlankContent = Annotated[str, StringConstraints(min_length=1, max_length=16_000)]
GroundedText = Annotated[str, StringConstraints(min_length=1, max_length=8_000)]
Identifier = Annotated[
    str,
    StringConstraints(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$"),
]
GroundedStatus = Literal["ANSWER", "NEED_CLARIFICATION", "INSUFFICIENT_DATA"]
GroundedDataClassification = Literal["D0_SYSTEM_SMOKE", "D1_PUBLIC_DEMO"]


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

    @field_validator("text", "provider", "model")
    @classmethod
    def reject_blank_output_fields(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("response text, provider, and model must not be blank")
        return value


class GroundingEvidenceFragment(BaseModel):
    """A reviewed retrieval fragment. Its text is untrusted prompt data."""

    model_config = ConfigDict(extra="forbid")

    fragment_id: Identifier
    source_id: Identifier
    procedure_id: Identifier
    section_type: Identifier
    title: Annotated[str, StringConstraints(min_length=1, max_length=500)]
    text: GroundedText
    jurisdiction: Annotated[str, StringConstraints(min_length=1, max_length=500)] | None = None
    effective_from: date | None = None
    effective_to: date | None = None
    validity_status: Literal["CURRENT", "EXPIRED", "FUTURE", "UNKNOWN"] = "UNKNOWN"

    @field_validator("title", "text", "jurisdiction")
    @classmethod
    def reject_blank_optional_text(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("text fields must not be blank")
        return value

    @model_validator(mode="after")
    def validate_effective_range(self) -> "GroundingEvidenceFragment":
        if (
            self.effective_from is not None
            and self.effective_to is not None
            and self.effective_to < self.effective_from
        ):
            raise ValueError("effective_to must not be before effective_from")
        return self


class GroundingContext(BaseModel):
    """Minimal evidence sent by Core Backend; URLs and retrieval scores stay there."""

    model_config = ConfigDict(extra="forbid")

    evidence_bundle_id: UUID
    corpus_version: Identifier
    data_classification: GroundedDataClassification
    query: Annotated[str, StringConstraints(min_length=1, max_length=4_000)]
    evidence: list[GroundingEvidenceFragment] = Field(default_factory=list, max_length=8)
    as_of: date | None = None

    @field_validator("query")
    @classmethod
    def reject_blank_query(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("query must not be blank")
        return value

    @model_validator(mode="after")
    def validate_evidence_budget_and_ids(self) -> "GroundingContext":
        fragment_ids = [fragment.fragment_id for fragment in self.evidence]
        if len(fragment_ids) != len(set(fragment_ids)):
            raise ValueError("evidence fragment_id values must be unique")
        if sum(len(fragment.text) for fragment in self.evidence) > 32_000:
            raise ValueError("total evidence text exceeds 32000 characters")
        return self


class GroundedGenerateRequest(GroundingContext):
    """G2 request. Core Backend, not the browser, supplies the evidence."""

    request_id: UUID
    max_output_tokens: int = Field(default=500, ge=32, le=2048, strict=True)


class GroundedModelOutput(BaseModel):
    """Strict JSON shape expected from a grounded provider before API metadata."""

    model_config = ConfigDict(extra="forbid")

    answer: GroundedText
    status: GroundedStatus
    cited_fragment_ids: list[Identifier] = Field(default_factory=list, max_length=8)
    missing_information: list[Annotated[str, StringConstraints(min_length=1, max_length=500)]] = (
        Field(default_factory=list, max_length=10)
    )

    @field_validator("answer")
    @classmethod
    def reject_blank_answer(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("answer must not be blank")
        return value

    @field_validator("cited_fragment_ids", "missing_information")
    @classmethod
    def reject_duplicate_list_values(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("list values must be unique")
        if any(not item.strip() for item in value):
            raise ValueError("list values must not be blank")
        return value

    @model_validator(mode="after")
    def validate_status_invariants(self) -> "GroundedModelOutput":
        if self.status == "ANSWER" and not self.cited_fragment_ids:
            raise ValueError("ANSWER requires at least one cited fragment")
        if self.status == "ANSWER" and self.missing_information:
            raise ValueError("ANSWER must not contain missing_information")
        if self.status == "NEED_CLARIFICATION" and not self.missing_information:
            raise ValueError("NEED_CLARIFICATION requires missing_information")
        if self.status == "INSUFFICIENT_DATA" and self.cited_fragment_ids:
            raise ValueError("INSUFFICIENT_DATA must not cite a fragment")
        return self


class GroundedGenerateResponse(GroundedModelOutput):
    request_id: UUID
    evidence_bundle_id: UUID
    corpus_version: Identifier
    data_classification: GroundedDataClassification
    prompt_version: Identifier
    provider: str
    model: str
    usage: Usage
    latency_ms: int = Field(ge=0)

    @field_validator("provider", "model")
    @classmethod
    def reject_blank_provider_fields(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("provider and model must not be blank")
        return value


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


class GroundedHealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: Literal["ai-service"] = "ai-service"
    endpoint: Literal["grounded-v2"] = "grounded-v2"
    provider: str
    prompt_version: Identifier
    external_calls_enabled: bool
