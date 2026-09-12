"""Validate model-owned intent patches and reduce Backend-owned conversation state."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import Field, model_validator

from app.rag.schemas import ID, Scope, Strict, Text

FieldIntent = Literal[
    "receiving_authority",
    "required_documents",
    "fees",
    "processing_times",
    "submission_methods",
    "steps",
    "legal_bases",
    "applicant_scope",
]
DialogueAct = Literal[
    "ASK_INFORMATION",
    "PROVIDE_CLARIFICATION",
    "CORRECT_CONTEXT",
    "RESET_CONTEXT",
    "GREET",
    "OUT_OF_SCOPE",
]
TopicAction = Literal["KEEP", "SWITCH", "RESET", "UNRESOLVED"]
PatchOperation = Literal["KEEP", "SET", "CLEAR"]
CONTEXT_SLOTS = ("procedure_id", "field_intents", "jurisdiction", "as_of")


class PatchEvidence(Strict):
    message_id: ID
    quote: Text = Field(max_length=300)


class StringPatch(Strict):
    op: PatchOperation
    value: str | None = Field(default=None, max_length=200)
    evidence: list[PatchEvidence] = Field(default_factory=list, max_length=4)

    @model_validator(mode="after")
    def valid_operation(self):
        if self.op == "SET" and (not self.value or not self.value.strip() or not self.evidence):
            raise ValueError("SET requires a non-empty value and evidence")
        if self.op == "CLEAR" and (self.value is not None or not self.evidence):
            raise ValueError("CLEAR requires a null value and evidence")
        if self.op == "KEEP" and (self.value is not None or self.evidence):
            raise ValueError("KEEP requires a null value and no evidence")
        return self


class FieldPatch(Strict):
    op: PatchOperation
    value: list[FieldIntent] | None = Field(default=None, min_length=1, max_length=8)
    evidence: list[PatchEvidence] = Field(default_factory=list, max_length=4)

    @model_validator(mode="after")
    def valid_operation(self):
        if self.op == "SET" and (not self.value or not self.evidence):
            raise ValueError("SET requires a non-empty value and evidence")
        if self.value and len(self.value) != len(set(self.value)):
            raise ValueError("Duplicate field intent")
        if self.op == "CLEAR" and (self.value is not None or not self.evidence):
            raise ValueError("CLEAR requires a null value and evidence")
        if self.op == "KEEP" and (self.value is not None or self.evidence):
            raise ValueError("KEEP requires a null value and no evidence")
        return self


class IntentContextPatch(Strict):
    procedure_id: StringPatch
    field_intents: FieldPatch
    jurisdiction: StringPatch
    as_of: StringPatch


class IntentContextOutput(Strict):
    schema_version: Literal["g5-intent-context-v2"]
    dialogue_act: DialogueAct
    topic_action: TopicAction
    patch: IntentContextPatch

    @model_validator(mode="after")
    def valid_date(self):
        item = self.patch.as_of
        if item.op == "SET":
            try:
                date.fromisoformat(item.value or "")
            except ValueError as exc:
                raise ValueError("as_of SET value must be an ISO date") from exc
        return self


class IntentContextState(Strict):
    schema_version: Literal["g5-context-state-v1"] = "g5-context-state-v1"
    procedure_id: ID | None = None
    field_intents: list[FieldIntent] = Field(default_factory=list)
    jurisdiction: Scope | None = None
    as_of: date | None = None
    pending_clarification: Literal["procedure_id", "field_intents", "jurisdiction"] | None = None
    source_message_ids: dict[str, ID] = Field(default_factory=dict)
    applied_message_ids: list[ID] = Field(default_factory=list, max_length=64)
    revision: int = Field(default=0, ge=0, strict=True)


def validate_model_output(
    raw: str | bytes,
    *,
    current_message_id: str,
    current_user_message: str,
    candidate_ids: set[str],
) -> IntentContextOutput:
    """Parse the model JSON and enforce runtime facts not expressible by JSON Schema."""

    result = IntentContextOutput.model_validate_json(raw)
    procedure = result.patch.procedure_id
    if procedure.op == "SET" and procedure.value not in candidate_ids:
        raise ValueError("PROCEDURE_NOT_IN_CATALOG")
    for slot in CONTEXT_SLOTS:
        operation = getattr(result.patch, slot)
        for evidence in operation.evidence:
            if evidence.message_id != current_message_id:
                raise ValueError("EVIDENCE_MESSAGE_ID")
            if evidence.quote not in current_user_message:
                raise ValueError("EVIDENCE_QUOTE_NOT_IN_MESSAGE")
    return result


def reduce_context(
    previous: IntentContextState | None,
    output: IntentContextOutput,
    *,
    message_id: str,
) -> IntentContextState:
    """Idempotently apply a verified patch; the Backend remains state owner."""

    state = previous.model_copy(deep=True) if previous else IntentContextState()
    if message_id in state.applied_message_ids:
        return state

    procedure = output.patch.procedure_id
    if output.topic_action == "RESET":
        state.procedure_id = None
        state.field_intents = []
        state.jurisdiction = None
        state.as_of = None
        state.pending_clarification = None
        state.source_message_ids.clear()
    elif (
        output.topic_action == "SWITCH"
        and procedure.op == "SET"
        and procedure.value != state.procedure_id
    ):
        state.field_intents = []
        state.jurisdiction = None
        state.as_of = None
        state.pending_clarification = None
        for slot in ("field_intents", "jurisdiction", "as_of", "pending_clarification"):
            state.source_message_ids.pop(slot, None)

    for slot in CONTEXT_SLOTS:
        operation = getattr(output.patch, slot)
        if operation.op == "KEEP":
            continue
        if operation.op == "CLEAR":
            setattr(state, slot, [] if slot == "field_intents" else None)
            state.source_message_ids.pop(slot, None)
            continue
        value = operation.value
        if slot == "field_intents":
            value = sorted(value or [])
        elif slot == "as_of":
            value = date.fromisoformat(value or "")
        setattr(state, slot, value)
        state.source_message_ids[slot] = message_id

    state.applied_message_ids = [*state.applied_message_ids, message_id][-64:]
    state.revision += 1
    return state
