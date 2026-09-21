import json
from uuid import uuid4

import httpx
import pytest
from test_g3 import VERSION, fixture_groups, write_dataset

from app.ai import AIClient
from app.config import get_settings
from app.errors import APIError
from app.rag.g3.validator import load_serving
from app.rag.g4.context import ConversationContext
from app.rag.g5.intent_context import (
    IntentContextOutput,
    IntentContextState,
    _same_procedure_family,
    load_context,
    merge_legacy_context,
    model_state,
    prepare_model_turn,
    procedure_candidates,
    record_grounded_turn,
    reduce_context,
    to_legacy_context,
    validate_model_output,
)
from app.rag.g5.topic_gate import TopicDecision
from app.rag.schemas import Filters, RetrievalInput


def test_procedure_family_match_requires_shared_distinguishing_tokens():
    data = type(
        "Catalog",
        (),
        {
            "procedures": {
                "domestic": {"title": "Thủ tục đăng ký kết hôn"},
                "foreign": {"title": "Đăng ký kết hôn có yếu tố nước ngoài"},
                "birth": {"title": "Thủ tục đăng ký khai sinh"},
            }
        },
    )()

    assert _same_procedure_family(data, "domestic", "foreign") is True
    assert _same_procedure_family(data, "birth", "foreign") is False


def output(
    *,
    dialogue_act="CORRECT_CONTEXT",
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
            "dialogue_act": dialogue_act,
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


def test_current_turn_candidate_recovers_model_missed_switch(tmp_path):
    data = load_serving(write_dataset(tmp_path, fixture_groups()), VERSION, 2)
    _, raw = output(
        dialogue_act="ASK_INFORMATION",
        topic="KEEP",
        procedure=("KEEP", None),
        fields=("KEEP", None),
    )
    previous = IntentContextState(
        corpus_version=VERSION,
        procedure_id="fictional-alpha",
        field_intents=["fees"],
        last_answered_fields=["fees"],
        known_documents=["identity_document"],
    )
    prepared, state, policy = prepare_model_turn(
        data,
        RetrievalInput(query="Tôi muốn làm thủ tục hư cấu Beta, lệ phí thế nào?"),
        previous,
        IntentContextOutput.model_validate_json(raw),
        message_id="user-2",
        topic_decision=TopicDecision("SWITCH", "fictional-beta", "explicit_catalog_name"),
    )
    assert policy is None
    assert prepared.filters.procedure_id == "fictional-beta"
    assert state.procedure_id == "fictional-beta"
    assert state.known_documents == []
    assert state.last_answered_fields == []


def test_unknown_new_topic_clears_stale_context_and_asks_for_procedure(tmp_path):
    data = load_serving(write_dataset(tmp_path, fixture_groups()), VERSION, 2)
    _, raw = output(
        dialogue_act="ASK_INFORMATION",
        topic="KEEP",
        procedure=("KEEP", None),
        fields=("KEEP", None),
    )
    previous = IntentContextState(
        corpus_version=VERSION,
        procedure_id="fictional-alpha",
        field_intents=["fees"],
        known_documents=["identity_document"],
    )
    prepared, state, policy = prepare_model_turn(
        data,
        RetrievalInput(query="Tôi muốn xin cấp sổ nhà, cần hồ sơ gì?"),
        previous,
        IntentContextOutput.model_validate_json(raw),
        message_id="user-2",
        topic_decision=TopicDecision("CLARIFY", reason="new_procedure_unresolved"),
    )
    assert prepared is None
    assert policy is not None and "chưa xác định" in policy
    assert state.procedure_id is None
    assert state.field_intents == []
    assert state.known_documents == []
    assert state.pending_clarification == "procedure_id"


def test_reducer_is_idempotent_for_same_message():
    message, raw = output()
    parsed = validate(message, raw)
    once = reduce_context(None, parsed, message_id="user-2")
    twice = reduce_context(once, parsed, message_id="user-2")
    assert twice == once
    assert twice.revision == 1


def test_grounded_turn_records_only_user_facts_and_verified_answer_memory():
    state = IntentContextState(
        corpus_version="corpus-v1",
        procedure_id="p_birth",
        field_intents=["required_documents"],
    )
    grounding = {
        "status": "ANSWER",
        "checklist": [{"field": "required_documents"}],
        "sources": [{"fragment_id": "fragment-1"}],
    }
    updated = record_grounded_turn(
        state,
        user_query="Tôi đã có CCCD rồi, cần bổ sung gì nữa?",
        message_id="user-2",
        grounding=grounding,
    )

    assert updated.known_documents == ["identity_document"]
    assert updated.last_answered_fields == ["required_documents"]
    assert updated.last_answered_fragment_ids == ["fragment-1"]
    assert updated.last_turn_mode == "DOCUMENT_INVENTORY"
    assert updated.source_message_ids["known_document:identity_document"] == "user-2"

    question_only = record_grounded_turn(
        state,
        user_query="Có cần CCCD không?",
        message_id="user-3",
        grounding=None,
    )
    assert question_only.known_documents == []


def test_confirmation_recovers_fields_from_last_grounded_answer(tmp_path):
    data = load_serving(write_dataset(tmp_path, fixture_groups()), VERSION, 2)
    _, raw = output(
        dialogue_act="ASK_INFORMATION",
        topic="KEEP",
        procedure=("KEEP", None),
        fields=("KEEP", None),
    )
    parsed = validate_model_output(
        raw,
        current_message_id="user-2",
        current_user_message="Đổi sang đăng ký khai sinh, hỏi lệ phí",
        candidate_ids={item["id"] for item in procedure_candidates(data)},
    )
    previous = IntentContextState(
        corpus_version=VERSION,
        procedure_id="fictional-alpha",
        field_intents=[],
        last_answered_fields=["fees"],
    )

    query, state, policy = prepare_model_turn(
        data,
        RetrievalInput(query="Vậy là mức phí này đúng không?"),
        previous,
        parsed,
        message_id="user-2",
    )

    assert policy is None
    assert query.field_intents == ["fees"]
    assert state.field_intents == ["fees"]


def test_reset_is_backend_owned_even_when_model_patches_keep():
    previous = IntentContextState(
        procedure_id="p_marriage",
        field_intents=["fees"],
        last_answered_fields=["fees"],
        known_documents=["identity_document"],
    )
    message, raw = output(
        dialogue_act="RESET_CONTEXT",
        topic="RESET",
        procedure=("KEEP", None),
        fields=("KEEP", None),
    )
    state = reduce_context(previous, validate(message, raw), message_id="user-2")
    assert state.procedure_id is None
    assert state.field_intents == []
    assert state.last_answered_fields == []
    assert state.known_documents == []


def test_runtime_rejects_reset_that_does_not_reset_topic():
    message, raw = output(dialogue_act="RESET_CONTEXT", topic="KEEP")
    with pytest.raises(ValueError, match="RESET_SEMANTICS"):
        validate(message, raw)


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


def test_load_context_migrates_g4_and_resets_on_corpus_change():
    message_id = uuid4()
    legacy = ConversationContext(
        corpus_version="corpus-v1",
        active_procedure_id="p_birth",
        field_intents=["fees"],
        source_message_ids={"active_procedure_id": message_id},
    )
    migrated = load_context(legacy.model_dump(mode="json"), corpus_version="corpus-v1")
    assert migrated.procedure_id == "p_birth"
    assert migrated.field_intents == ["fees"]
    assert migrated.source_message_ids["procedure_id"] == str(message_id)
    assert to_legacy_context(migrated).source_message_ids["active_procedure_id"] == message_id
    reset = load_context(migrated.model_dump(mode="json"), corpus_version="corpus-v2")
    assert model_state(reset)["procedure_id"] is None


def test_fallback_merge_keeps_g5_revision_and_date():
    previous = IntentContextState(
        corpus_version="corpus-v1",
        procedure_id="p_birth",
        field_intents=["fees"],
        as_of="2026-09-01",
        source_message_ids={"as_of": "00000000-0000-4000-8000-000000000001"},
        applied_message_ids=["00000000-0000-4000-8000-000000000001"],
        revision=3,
    )
    legacy = to_legacy_context(previous)
    merged = merge_legacy_context(
        previous,
        legacy,
        message_id="00000000-0000-4000-8000-000000000002",
    )
    assert merged.schema_version == "g5-context-state-v1"
    assert merged.as_of.isoformat() == "2026-09-01"
    assert merged.revision == 4
    assert len(merged.applied_message_ids) == 2


def test_prepare_model_turn_drives_retrieval_and_backend_policy(tmp_path):
    data = load_serving(write_dataset(tmp_path, fixture_groups()), VERSION, 2)
    message_id = "00000000-0000-4000-8000-000000000002"
    message = "Đổi sang Mẫu Alpha, hỏi lệ phí"
    evidence = [{"message_id": message_id, "quote": message}]
    parsed = validate_model_output(
        json.dumps(
            {
                "schema_version": "g5-intent-context-v2",
                "dialogue_act": "CORRECT_CONTEXT",
                "topic_action": "SWITCH",
                "patch": {
                    "procedure_id": {
                        "op": "SET",
                        "value": "fictional-alpha",
                        "evidence": evidence,
                    },
                    "field_intents": {"op": "SET", "value": ["fees"], "evidence": evidence},
                    "jurisdiction": {"op": "KEEP", "value": None, "evidence": []},
                    "as_of": {"op": "KEEP", "value": None, "evidence": []},
                },
            },
            ensure_ascii=False,
        ),
        current_message_id=message_id,
        current_user_message=message,
        candidate_ids={item["id"] for item in procedure_candidates(data)},
    )
    previous = IntentContextState(
        corpus_version=VERSION,
        procedure_id="fictional-beta",
        field_intents=["required_documents"],
        jurisdiction="Tỉnh cũ",
    )
    query, state, policy = prepare_model_turn(
        data,
        RetrievalInput(query=message),
        previous,
        parsed,
        message_id=message_id,
    )
    assert policy is None
    assert query.filters.procedure_id == "fictional-alpha"
    assert query.field_intents == ["fees"]
    assert state.jurisdiction is None
    assert state.pending_clarification is None


def test_guarded_direct_reads_catalog_only_after_trusted_resolution(tmp_path):
    data = load_serving(write_dataset(tmp_path, fixture_groups()), VERSION, 2)
    message = "Lệ phí bao nhiêu?"
    evidence = [{"message_id": "user-2", "quote": message}]
    parsed = IntentContextOutput.model_validate(
        {
            "schema_version": "g5-intent-context-v2",
            "dialogue_act": "ASK_INFORMATION",
            "topic_action": "KEEP",
            "patch": {
                "procedure_id": {"op": "KEEP", "value": None, "evidence": []},
                "field_intents": {
                    "op": "SET",
                    "value": ["fees", "required_documents"],
                    "evidence": evidence,
                },
                "jurisdiction": {"op": "KEEP", "value": None, "evidence": []},
                "as_of": {"op": "KEEP", "value": None, "evidence": []},
            },
        }
    )
    prepared, state, policy = prepare_model_turn(
        data,
        RetrievalInput(query=message),
        IntentContextState(corpus_version=VERSION, procedure_id="fictional-alpha"),
        parsed,
        message_id="user-2",
        topic_decision=TopicDecision("KEEP", reason="no_new_procedure_signal"),
        evidence_mode="guarded_direct",
    )

    assert policy is None
    assert prepared.acquisition_mode == "direct_catalog"
    assert prepared.filters.procedure_id == "fictional-alpha"
    assert prepared.field_intents == ["fees"]
    assert state.field_intents == ["fees"]


def test_guarded_direct_current_turn_submission_cue_overrides_document_guess(tmp_path):
    data = load_serving(write_dataset(tmp_path, fixture_groups()), VERSION, 2)
    message = "Có gửi hồ sơ qua mạng được không?"
    evidence = [{"message_id": "user-2", "quote": message}]
    parsed = IntentContextOutput.model_validate(
        {
            "schema_version": "g5-intent-context-v2",
            "dialogue_act": "ASK_INFORMATION",
            "topic_action": "KEEP",
            "patch": {
                "procedure_id": {"op": "KEEP", "value": None, "evidence": []},
                "field_intents": {
                    "op": "SET",
                    "value": ["required_documents"],
                    "evidence": evidence,
                },
                "jurisdiction": {"op": "KEEP", "value": None, "evidence": []},
                "as_of": {"op": "KEEP", "value": None, "evidence": []},
            },
        }
    )
    prepared, state, policy = prepare_model_turn(
        data,
        RetrievalInput(query=message),
        IntentContextState(corpus_version=VERSION, procedure_id="fictional-alpha"),
        parsed,
        message_id="user-2",
        topic_decision=TopicDecision("KEEP", reason="no_new_procedure_signal"),
        evidence_mode="guarded_direct",
    )

    assert policy is None
    assert prepared.acquisition_mode == "direct_catalog"
    assert prepared.field_intents == ["submission_methods"]
    assert state.field_intents == ["submission_methods"]


def test_guarded_direct_keeps_hybrid_for_unverified_model_resolution(tmp_path):
    data = load_serving(write_dataset(tmp_path, fixture_groups()), VERSION, 2)
    message, raw = output(
        dialogue_act="ASK_INFORMATION",
        topic="SWITCH",
        procedure=("SET", "fictional-alpha"),
        fields=("SET", ["fees"]),
    )
    parsed = IntentContextOutput.model_validate_json(raw)
    prepared, _, policy = prepare_model_turn(
        data,
        RetrievalInput(query=message),
        IntentContextState(corpus_version=VERSION),
        parsed,
        message_id="user-2",
        evidence_mode="guarded_direct",
    )

    assert policy is None
    assert prepared.acquisition_mode == "hybrid_retrieval"


def test_all_information_request_uses_only_fields_available_for_procedure(tmp_path):
    data = load_serving(write_dataset(tmp_path, fixture_groups()), VERSION, 2)
    message_id = "00000000-0000-4000-8000-000000000002"
    message, raw = output(
        procedure=("SET", "fictional-alpha"),
        fields=(
            "SET",
            [
                "receiving_authority",
                "required_documents",
                "fees",
                "processing_times",
                "submission_methods",
                "steps",
                "legal_bases",
                "applicant_scope",
            ],
        ),
    )
    parsed = validate_model_output(
        raw,
        current_message_id="user-2",
        current_user_message=message,
        candidate_ids={item["id"] for item in procedure_candidates(data)},
    )

    query, state, policy = prepare_model_turn(
        data,
        RetrievalInput(query="Tất cả mọi thứ"),
        IntentContextState(corpus_version=VERSION),
        parsed,
        message_id=message_id,
    )

    available = data.procedures["fictional-alpha"]["field_evidence"]
    assert policy is None
    assert query.field_intents == [
        field
        for field in (
            "receiving_authority",
            "required_documents",
            "fees",
            "processing_times",
            "submission_methods",
            "steps",
            "legal_bases",
            "applicant_scope",
        )
        if available.get(field)
    ]
    assert state.field_intents == query.field_intents


def test_reset_policy_ignores_stale_explicit_filters(tmp_path):
    data = load_serving(write_dataset(tmp_path, fixture_groups()), VERSION, 2)
    message_id = "00000000-0000-4000-8000-000000000002"
    message, raw = output(
        dialogue_act="RESET_CONTEXT",
        topic="RESET",
        procedure=("CLEAR", None),
        fields=("CLEAR", None),
    )
    parsed = validate(message, raw)
    query, state, policy = prepare_model_turn(
        data,
        RetrievalInput(
            query=message,
            filters=Filters(procedure_id="fictional-alpha"),
        ),
        IntentContextState(procedure_id="fictional-beta", field_intents=["fees"]),
        parsed,
        message_id=message_id,
    )
    assert query is None
    assert state.procedure_id is None
    assert policy.startswith("Đã xóa")


async def test_ai_client_calls_internal_intent_endpoint_and_revalidates(monkeypatch):
    request_id = uuid4()
    message_id = uuid4()
    message = "Đăng ký khai sinh có mất phí không?"
    evidence = [{"message_id": str(message_id), "quote": message}]

    def handler(request):
        assert request.url.path == "/internal/v3/intent-context"
        payload = json.loads(request.content)
        assert payload["state_before"]["procedure_id"] is None
        return httpx.Response(
            200,
            json={
                "request_id": str(request_id),
                "output": {
                    "schema_version": "g5-intent-context-v2",
                    "dialogue_act": "ASK_INFORMATION",
                    "topic_action": "SWITCH",
                    "patch": {
                        "procedure_id": {
                            "op": "SET",
                            "value": "p_birth",
                            "evidence": evidence,
                        },
                        "field_intents": {
                            "op": "SET",
                            "value": ["fees"],
                            "evidence": evidence,
                        },
                        "jurisdiction": {"op": "KEEP", "value": None, "evidence": []},
                        "as_of": {"op": "KEEP", "value": None, "evidence": []},
                    },
                },
                "provider": "local-intent-context",
                "model": "intent-test",
                "usage": {"input_tokens": 10, "output_tokens": 5},
                "latency_ms": 1,
            },
        )

    monkeypatch.setattr(get_settings(), "ai_service_url", "http://ai-service:8001")
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await AIClient(client).analyze_intent_context(
            request_id=request_id,
            current_message_id=message_id,
            current_user_message=message,
            state_before={
                "procedure_id": None,
                "field_intents": [],
                "jurisdiction": None,
                "as_of": None,
                "pending_clarification": None,
            },
            procedure_candidates=[{"id": "p_birth", "name": "Đăng ký khai sinh"}],
            data_classification="D0_SYSTEM_SMOKE",
        )
    assert result.patch.field_intents.value == ["fees"]


async def test_ai_client_rejects_forged_intent_evidence(monkeypatch):
    request_id = uuid4()
    message_id = uuid4()

    def handler(_request):
        body = {
            "request_id": str(request_id),
            "output": json.loads(output()[1]),
            "provider": "local-intent-context",
            "model": "intent-test",
            "usage": {"input_tokens": 0, "output_tokens": 0},
            "latency_ms": 1,
        }
        return httpx.Response(200, json=body)

    monkeypatch.setattr(get_settings(), "ai_service_url", "http://ai-service:8001")
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(APIError, match="Không thể kiểm chứng"):
            await AIClient(client).analyze_intent_context(
                request_id=request_id,
                current_message_id=message_id,
                current_user_message="Nội dung khác",
                state_before={
                    "procedure_id": None,
                    "field_intents": [],
                    "jurisdiction": None,
                    "as_of": None,
                    "pending_clarification": None,
                },
                procedure_candidates=[{"id": "p_birth", "name": "Đăng ký khai sinh"}],
                data_classification="D0_SYSTEM_SMOKE",
            )
