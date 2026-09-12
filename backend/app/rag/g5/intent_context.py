"""Validate model-owned intent patches and reduce Backend-owned conversation state."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import Field, model_validator

from app.rag.g3.retrieval import retrieve
from app.rag.g4.context import ConversationContext
from app.rag.schemas import ID, Filters, RetrievalInput, Scope, Strict, Text

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
    corpus_version: ID | None = None
    procedure_id: ID | None = None
    field_intents: list[FieldIntent] = Field(default_factory=list)
    jurisdiction: Scope | None = None
    as_of: date | None = None
    pending_clarification: (
        Literal["procedure_id", "field_intents", "jurisdiction", "as_of"] | None
    ) = None
    source_message_ids: dict[str, ID] = Field(default_factory=dict)
    applied_message_ids: list[ID] = Field(default_factory=list, max_length=64)
    revision: int = Field(default=0, ge=0, strict=True)


def load_context(raw: dict | None, *, corpus_version: str) -> IntentContextState:
    """Load G5 state, migrate G4 state, or reset state after a corpus change."""

    if not raw:
        return IntentContextState(corpus_version=corpus_version)
    if raw.get("schema_version") == "g5-context-state-v1":
        state = IntentContextState.model_validate(raw)
        return (
            state
            if state.corpus_version == corpus_version
            else IntentContextState(corpus_version=corpus_version)
        )
    legacy = ConversationContext.model_validate(raw)
    if legacy.corpus_version != corpus_version:
        return IntentContextState(corpus_version=corpus_version)
    legacy_keys = {
        "active_procedure_id": "procedure_id",
        "confirmed_jurisdiction": "jurisdiction",
    }
    return IntentContextState(
        corpus_version=corpus_version,
        procedure_id=legacy.active_procedure_id,
        field_intents=legacy.field_intents,
        jurisdiction=legacy.confirmed_jurisdiction,
        pending_clarification=legacy.pending_clarification,
        source_message_ids={
            legacy_keys.get(key, key): str(value)
            for key, value in legacy.source_message_ids.items()
        },
    )


def to_legacy_context(state: IntentContextState) -> ConversationContext:
    """Convert verified G5 state for the deterministic fallback route."""

    from uuid import UUID

    source_ids = {}
    g4_keys = {
        "procedure_id": "active_procedure_id",
        "jurisdiction": "confirmed_jurisdiction",
    }
    for key, value in state.source_message_ids.items():
        try:
            source_ids[g4_keys.get(key, key)] = UUID(value)
        except ValueError:
            continue
    return ConversationContext(
        corpus_version=state.corpus_version or "unknown-corpus",
        active_procedure_id=state.procedure_id,
        confirmed_jurisdiction=state.jurisdiction,
        field_intents=state.field_intents,
        pending_clarification=state.pending_clarification,
        source_message_ids=source_ids,
    )


def model_state(state: IntentContextState) -> dict:
    """Expose only the bounded state fields learned by the intent model."""

    return {
        "procedure_id": state.procedure_id,
        "field_intents": list(state.field_intents),
        "jurisdiction": state.jurisdiction,
        "as_of": state.as_of.isoformat() if state.as_of else None,
        "pending_clarification": state.pending_clarification,
    }


def procedure_candidates(data) -> list[dict[str, str]]:
    return [
        {"id": procedure_id, "name": data.procedures[procedure_id]["title"]}
        for procedure_id in sorted(data.accepted)
    ]


def validate_model_output(
    raw: str | bytes,
    *,
    current_message_id: str,
    current_user_message: str,
    candidate_ids: set[str],
    state_before: dict | None = None,
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
    is_reset_act = result.dialogue_act == "RESET_CONTEXT"
    is_reset_topic = result.topic_action == "RESET"
    if is_reset_act != is_reset_topic:
        raise ValueError("RESET_SEMANTICS")
    if result.topic_action == "SWITCH" and procedure.op != "SET":
        raise ValueError("SWITCH_WITHOUT_PROCEDURE")
    if procedure.op == "SET" and result.topic_action != "SWITCH":
        raise ValueError("PROCEDURE_SET_WITHOUT_SWITCH")
    if result.topic_action in {"RESET", "UNRESOLVED"} and procedure.op == "SET":
        raise ValueError("TOPIC_PROCEDURE_CONFLICT")
    if result.dialogue_act in {"GREET", "OUT_OF_SCOPE"}:
        if result.topic_action not in {"KEEP", "UNRESOLVED"} or any(
            getattr(result.patch, slot).op != "KEEP" for slot in CONTEXT_SLOTS
        ):
            raise ValueError("POLICY_CONTEXT_MUTATION")
    if state_before and result.dialogue_act == "PROVIDE_CLARIFICATION":
        pending = state_before.get("pending_clarification")
        if pending in CONTEXT_SLOTS and getattr(result.patch, pending).op != "SET":
            raise ValueError("PENDING_SLOT_NOT_SET")
    return result


def merge_legacy_context(
    previous: IntentContextState,
    legacy: ConversationContext,
    *,
    message_id: str,
    explicit_as_of: date | None = None,
) -> IntentContextState:
    """Keep G5 ownership metadata when the deterministic G4 fallback handles one turn."""

    state = load_context(legacy.model_dump(mode="json"), corpus_version=legacy.corpus_version)
    procedure_changed = state.procedure_id != previous.procedure_id
    state.as_of = None if procedure_changed else previous.as_of
    if procedure_changed:
        state.source_message_ids.pop("as_of", None)
    elif previous.as_of is not None and "as_of" in previous.source_message_ids:
        state.source_message_ids["as_of"] = previous.source_message_ids["as_of"]
    if explicit_as_of is not None:
        state.as_of = explicit_as_of
        state.source_message_ids["as_of"] = message_id
    state.applied_message_ids = [
        *[item for item in previous.applied_message_ids if item != message_id],
        message_id,
    ][-64:]
    state.revision = previous.revision + 1
    return state


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


def prepare_model_turn(
    data,
    query: RetrievalInput,
    previous: IntentContextState,
    output: IntentContextOutput,
    *,
    message_id: str,
) -> tuple[RetrievalInput | None, IntentContextState, str | None]:
    """Apply model intent, derive retrieval input and select Backend-owned policy replies."""

    state = reduce_context(previous, output, message_id=message_id)
    state.corpus_version = data.version

    if output.dialogue_act == "RESET_CONTEXT" or output.topic_action == "RESET":
        return None, state, "Đã xóa ngữ cảnh cũ. Bạn muốn tra cứu thủ tục nào?"
    if output.dialogue_act == "GREET":
        return None, state, "Xin chào! Tôi có thể hỗ trợ bạn tra cứu thủ tục hành chính công."
    if output.dialogue_act == "OUT_OF_SCOPE":
        return None, state, "Tôi chỉ hỗ trợ tra cứu dịch vụ hành chính công."

    explicit = query.filters
    if explicit.procedure_id is not None:
        if explicit.procedure_id not in data.accepted:
            raise ValueError("UNKNOWN_EXPLICIT_PROCEDURE")
        if explicit.procedure_id != state.procedure_id:
            state.field_intents = []
            state.jurisdiction = None
            state.as_of = None
        state.procedure_id = explicit.procedure_id
        state.source_message_ids["procedure_id"] = message_id
    if explicit.jurisdiction is not None:
        state.jurisdiction = explicit.jurisdiction
        state.source_message_ids["jurisdiction"] = message_id
    if explicit.as_of is not None:
        state.as_of = explicit.as_of
        state.source_message_ids["as_of"] = message_id

    prepared = RetrievalInput(
        query=query.query,
        top_k=query.top_k,
        field_intents=list(state.field_intents),
        filters=Filters(
            procedure_id=state.procedure_id,
            jurisdiction=state.jurisdiction,
            as_of=state.as_of,
        ),
    )
    found = retrieve(
        data,
        prepared.query,
        prepared.top_k,
        procedure_id=prepared.filters.procedure_id,
        jurisdiction=prepared.filters.jurisdiction,
        field_intents=prepared.field_intents,
        as_of=prepared.filters.as_of.isoformat() if prepared.filters.as_of else None,
    )
    resolved = found["procedure_id"]
    if state.procedure_id is None and resolved is not None:
        state.procedure_id = resolved
        state.source_message_ids["procedure_id"] = message_id
        prepared.filters.procedure_id = resolved
    if resolved is None:
        state.pending_clarification = "procedure_id"
    elif not state.field_intents:
        state.pending_clarification = "field_intents"
    elif found["reason"] == "JURISDICTION_UNVERIFIED":
        state.pending_clarification = "jurisdiction"
    else:
        state.pending_clarification = None
    if state.pending_clarification:
        state.source_message_ids["pending_clarification"] = message_id
    else:
        state.source_message_ids.pop("pending_clarification", None)
    return prepared, state, None
