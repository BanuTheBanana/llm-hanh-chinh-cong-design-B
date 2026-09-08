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

from app.schemas import GroundedGenerateRequest, GroundedStatus, Identifier

NonBlank = Annotated[str, StringConstraints(min_length=1, max_length=1_000)]
Split = Literal["TRAIN", "DEV", "TEST"]


class MatchRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    point: NonBlank
    match_any: list[NonBlank] = Field(min_length=1, max_length=20)

    @field_validator("point")
    @classmethod
    def reject_blank_point(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("match point must not be blank")
        return value

    @field_validator("match_any")
    @classmethod
    def reject_blank_or_duplicate_phrases(cls, value: list[str]) -> list[str]:
        if any(not item.strip() for item in value):
            raise ValueError("match phrases must not be blank")
        if len(value) != len(set(value)):
            raise ValueError("match phrases must be unique")
        return value


class EvalGoldReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_id: Identifier
    question: Annotated[str, StringConstraints(min_length=1, max_length=4_000)]
    procedure_id: Identifier | None = None
    facts: dict[str, object] = Field(default_factory=dict)
    expected_status: GroundedStatus
    expected_points: list[NonBlank] = Field(default_factory=list, max_length=20)
    forbidden_points: list[NonBlank] = Field(default_factory=list, max_length=20)
    gold_source_ids: list[Identifier] = Field(default_factory=list, max_length=8)
    gold_fragment_ids: list[Identifier] = Field(default_factory=list, max_length=8)
    contains_pii: Literal[False]
    split: Split
    author: Identifier
    reviewer: Identifier

    @field_validator("question")
    @classmethod
    def reject_blank_question(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("gold question must not be blank")
        return value

    @field_validator("expected_points", "forbidden_points")
    @classmethod
    def reject_blank_or_duplicate_points(cls, value: list[str]) -> list[str]:
        if any(not item.strip() for item in value):
            raise ValueError("gold points must not be blank")
        if len(value) != len(set(value)):
            raise ValueError("gold points must be unique")
        return value

    @field_validator("gold_source_ids", "gold_fragment_ids")
    @classmethod
    def reject_duplicate_gold_ids(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("gold IDs must be unique")
        return value

    @model_validator(mode="after")
    def require_independent_reviewer(self) -> "EvalGoldReference":
        if self.author == self.reviewer:
            raise ValueError("gold author and reviewer must be different")
        return self


class EvalChecks(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_points: list[MatchRule] = Field(default_factory=list, max_length=20)
    forbidden_points: list[MatchRule] = Field(default_factory=list, max_length=20)

    @field_validator("expected_points", "forbidden_points")
    @classmethod
    def reject_duplicate_rule_points(cls, value: list[MatchRule]) -> list[MatchRule]:
        points = [rule.point for rule in value]
        if len(points) != len(set(points)):
            raise ValueError("check rule points must be unique")
        return value


class EvalCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["g2.eval-case.v1"]
    gold_question: EvalGoldReference
    grounding_request: GroundedGenerateRequest
    checks: EvalChecks

    @model_validator(mode="after")
    def validate_gold_alignment(self) -> "EvalCase":
        if self.gold_question.question.strip() != self.grounding_request.query.strip():
            raise ValueError("gold question must match grounding request query")

        expected_names = {rule.point for rule in self.checks.expected_points}
        if expected_names != set(self.gold_question.expected_points):
            raise ValueError("expected point checks must match gold expected_points")

        forbidden_names = {rule.point for rule in self.checks.forbidden_points}
        if forbidden_names != set(self.gold_question.forbidden_points):
            raise ValueError("forbidden point checks must match gold forbidden_points")
        return self


class EvalSuiteManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["g2.eval-suite.v1"]
    suite_id: Identifier
    usage: Literal["D0_SYSTEM_SMOKE", "D1_PUBLIC_DEMO"]
    corpus_version: Identifier
    prompt_version: Identifier
    cases_file: Annotated[str, StringConstraints(min_length=1, max_length=255)]
    cases_sha256: Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]
    allowed_splits: list[Split] = Field(min_length=1, max_length=3)

    @field_validator("allowed_splits")
    @classmethod
    def reject_duplicate_splits(cls, value: list[Split]) -> list[Split]:
        if len(value) != len(set(value)):
            raise ValueError("allowed_splits must be unique")
        return value


class CaseEvaluation(BaseModel):
    question_id: Identifier
    request_id: UUID
    evidence_bundle_id: UUID
    split: Split
    expected_status: GroundedStatus
    actual_status: GroundedStatus | None
    status_correct: bool
    retrieval_recall_at_1: float | None
    retrieval_recall_in_bundle: float | None
    retrieval_query_failed: bool | None
    reciprocal_rank: float | None
    citation_ids_valid: bool
    gold_citation_recall: float | None
    lexical_expected_point_coverage: float | None
    lexical_forbidden_claim_rate: float | None
    retrieved_fragment_ids: list[Identifier]
    cited_fragment_ids: list[Identifier]
    answer: str | None
    missing_information: list[str]
    latency_ms: float | None
    input_tokens: int | None
    output_tokens: int | None
    provider: str | None
    model: str | None
    abstention_correct: bool | None
    unsafe_answer: bool | None
    over_abstention: bool | None
    strict_safety_pass: bool
    error_code: Identifier | None = None


class EvaluationSummary(BaseModel):
    case_count: int = Field(ge=0)
    completed_count: int = Field(ge=0)
    error_rate: float | None
    status_accuracy: float | None
    retrieval_recall_at_1: float | None
    retrieval_recall_in_bundle: float | None
    retrieval_query_fail_rate: float | None
    mean_reciprocal_rank: float | None
    citation_id_validity: float | None
    gold_citation_recall: float | None
    lexical_expected_point_coverage: float | None
    lexical_forbidden_claim_rate: float | None
    abstention_accuracy: float | None
    unsafe_answer_rate: float | None
    over_abstention_rate: float | None
    strict_safety_pass_rate: float | None
    latency_p50_ms: float | None
    latency_p95_ms: float | None
    mean_input_tokens: float | None
    mean_output_tokens: float | None


class EvaluationReport(BaseModel):
    schema_version: Literal["g2.eval-report.v1"] = "g2.eval-report.v1"
    suite_id: Identifier
    usage: Literal["D0_SYSTEM_SMOKE", "D1_PUBLIC_DEMO"]
    corpus_version: Identifier
    prompt_version: Identifier
    cases_sha256: Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]
    candidate: Identifier
    split: Split
    summary: EvaluationSummary
    cases: list[CaseEvaluation]
    citation_support_review: Literal["PENDING_HUMAN_REVIEW"] = "PENDING_HUMAN_REVIEW"
