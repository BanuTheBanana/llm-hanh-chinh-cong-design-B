from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints, model_validator

ID = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_.-]{1,160}$")]
Hash = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
Text = Annotated[str, StringConstraints(min_length=1, pattern=r"\S")]
Status = Literal["ANSWER", "NEED_CLARIFICATION", "INSUFFICIENT_DATA"]
BUSINESS_FIELDS = (
    "applicant_scope",
    "receiving_authority",
    "submission_methods",
    "required_documents",
    "steps",
    "fees",
    "processing_time",
    "legal_bases",
)


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)


class SourceManifest(Strict):
    source_id: ID
    source_url: Text
    source_domain: Text
    title: Text
    issuing_authority: str | None
    jurisdiction: str | None
    procedure_code: str | None
    retrieved_at: AwareDatetime
    effective_from: date | None
    effective_to: date | None
    status: Literal["UNKNOWN", "CONFIRMED_FROM_SOURCE"]
    content_sha256: Hash
    raw_path: Text
    parser_version: Text
    review_status: Literal["PENDING", "APPROVED"]
    usage: Literal["D1_PUBLIC_DEMO", "D0_SYSTEM_SMOKE"]

    @model_validator(mode="after")
    def valid_interval(self):
        if self.effective_from and self.effective_to and self.effective_from > self.effective_to:
            raise ValueError("Invalid effective interval")
        return self


class ProcedureRecord(Strict):
    procedure_id: ID
    title: Text
    aliases: list[Text]
    jurisdiction: str | None
    applicant_scope: list[Text]
    receiving_authority: list[Text]
    submission_methods: list[Text]
    required_documents: list[Text]
    steps: list[Text]
    fees: list[Text]
    processing_time: list[Text]
    legal_bases: list[Text]
    source_ids: list[ID] = Field(min_length=1)
    version: Text
    field_evidence: dict[str, list[list[ID]]]


class ProcedureFragment(Strict):
    fragment_id: ID
    procedure_id: ID
    section_type: Literal[
        "OVERVIEW",
        "APPLICANT_SCOPE",
        "RECEIVING_AUTHORITY",
        "SUBMISSION_METHODS",
        "REQUIRED_DOCUMENTS",
        "STEPS",
        "FEES",
        "PROCESSING_TIME",
        "LEGAL_BASES",
        "OTHER",
    ]
    text: Text = Field(max_length=16000)
    source_id: ID
    ordinal: int = Field(ge=0, strict=True)
    content_sha256: Hash


class Filters(Strict):
    procedure_id: ID | None = None
    jurisdiction: str | None = None
    as_of: date | None = None


class RetrievalInput(Strict):
    query: Text = Field(max_length=10000)
    top_k: int = Field(default=5, ge=1, le=20, strict=True)
    filters: Filters = Field(default_factory=Filters)


class Evidence(Strict):
    fragment_id: ID
    source_id: ID
    title: Text
    url: Text
    text: Text
    score: float = Field(ge=0, allow_inf_nan=False)
    metadata: dict


class EvidenceBundle(Strict):
    request_id: UUID
    corpus_version: ID
    query: Text
    evidence: list[Evidence] = Field(max_length=20)


class Usage(Strict):
    input_tokens: int = Field(ge=0, strict=True)
    output_tokens: int = Field(ge=0, strict=True)


class GroundedAnswer(Strict):
    request_id: UUID
    answer: Text = Field(max_length=16000)
    status: Status
    cited_fragment_ids: list[ID]
    missing_information: list[Text]
    provider: Text
    model: Text
    usage: Usage
    latency_ms: float = Field(ge=0, allow_inf_nan=False)


class Citation(Strict):
    fragment_id: ID
    source_id: ID
    title: Text
    url: Text
    metadata: dict


class Grounding(Strict):
    status: Status
    corpus_version: ID
    sources: list[Citation]
    missing_information: list[str]


class GoldQuestion(Strict):
    question_id: ID
    question: Text
    procedure_id: ID | None
    facts: dict
    expected_status: Status
    expected_points: list[Text]
    forbidden_points: list[Text]
    gold_source_ids: list[ID]
    gold_fragment_ids: list[ID]
    contains_pii: Literal[False]
    split: Literal["TRAIN", "DEV", "TEST"]
    author: Text
    reviewer: Text
    filters: Filters = Field(default_factory=Filters)


class HistoryMessage(Strict):
    role: Literal["user", "assistant"]
    content: Text = Field(max_length=16000)


class GenerateGroundedRequest(Strict):
    evidence_bundle: EvidenceBundle
    history: list[HistoryMessage] = Field(default_factory=list, max_length=10)
    max_output_tokens: int = Field(ge=1, le=4096, strict=True)
