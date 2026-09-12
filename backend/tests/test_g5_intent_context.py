import json

import pytest

from app.rag.g5.intent_context import (
    IntentContextState,
    reduce_context,
    validate_model_output,
)


def output(
    *,
    topic="SWITCH",
    procedure=("SET", "p_birth"),
    fields=("SET", ["fees"]),
    jurisdiction=("KEEP", None),
    as_of=("KEEP", None),
):
    message = "Đổi sang đăng ký khai sinh, hỏi lệ phí"

    def patch(item):
        op, value = item
        return {
            "op": op,
            "value": value,
            "evidence": [] if op == "KEEP" else [{"message_id": "user-2", "quote": message}],
        }

    return message, json.dumps(
        {
            "schema_version": "g5-intent-context-v2",
            "dialogue_act": "CORRECT_CONTEXT",
            "topic_action": topic,
            "patch": {
                "procedure_id": patch(procedure),
                "field_intents": patch(fields),
                "jurisdiction": patch(jurisdiction),
                "as_of": patch(as_of),
            },
        },
        ensure_ascii=False,
    )


def validate(message, raw):
    return validate_model_output(
        raw,
        current_message_id="user-2",
        current_user_message=message,
        candidate_ids={"p_birth", "p_marriage"},
    )


def test_switch_clears_dependent_context_before_keep_operations():
    previous = IntentContextState(
        procedure_id="p_marriage",
        field_intents=["required_documents"],
        jurisdiction="Phường Mô Phỏng",
        as_of="2026-09-01",
        source_message_ids={
            "procedure_id": "user-1",
            "field_intents": "user-1",
            "jurisdiction": "user-1",
            "as_of": "user-1",
        },
    )
    message, raw = output(fields=("KEEP", None))
    state = reduce_context(previous, validate(message, raw), message_id="user-2")
    assert state.procedure_id == "p_birth"
    assert state.field_intents == []
    assert state.jurisdiction is None
    assert state.as_of is None
    assert state.source_message_ids == {"procedure_id": "user-2"}


def test_reducer_is_idempotent_for_same_message():
    message, raw = output()
    parsed = validate(message, raw)
    once = reduce_context(None, parsed, message_id="user-2")
    twice = reduce_context(once, parsed, message_id="user-2")
    assert twice == once
    assert twice.revision == 1


def test_reset_is_backend_owned_even_when_model_patches_keep():
    previous = IntentContextState(procedure_id="p_marriage", field_intents=["fees"])
    message, raw = output(
        topic="RESET",
        procedure=("KEEP", None),
        fields=("KEEP", None),
    )
    state = reduce_context(previous, validate(message, raw), message_id="user-2")
    assert state.procedure_id is None
    assert state.field_intents == []


@pytest.mark.parametrize(
    ("candidate_ids", "message", "error"),
    [
        ({"p_marriage"}, "Đổi sang đăng ký khai sinh, hỏi lệ phí", "PROCEDURE_NOT_IN_CATALOG"),
        ({"p_birth"}, "Nội dung khác", "EVIDENCE_QUOTE_NOT_IN_MESSAGE"),
    ],
)
def test_runtime_rejects_unverified_model_facts(candidate_ids, message, error):
    _, raw = output()
    with pytest.raises(ValueError, match=error):
        validate_model_output(
            raw,
            current_message_id="user-2",
            current_user_message=message,
            candidate_ids=candidate_ids,
        )


def test_runtime_rejects_wrong_evidence_message_id():
    message, raw = output()
    raw = raw.replace("user-2", "assistant-1")
    with pytest.raises(ValueError, match="EVIDENCE_MESSAGE_ID"):
        validate_model_output(
            raw,
            current_message_id="user-2",
            current_user_message=message,
            candidate_ids={"p_birth"},
        )
