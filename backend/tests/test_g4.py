"""G4 regressions use fictional fixtures only, never private evaluation data."""

import copy
import json
from pathlib import Path
from uuid import uuid4

import pytest
from test_g3 import VERSION, fixture_groups, write_dataset

from app.rag.corpus import CorpusError
from app.rag.g3.retrieval import retrieve
from app.rag.g3.runtime import load_active_dataset
from app.rag.g3.validator import digest, load_serving
from app.rag.g4.context import ConversationContext, prepare_turn
from app.rag.g4.evaluation import benchmark, read_dev
from app.rag.g4.intent import detect_fields
from app.rag.schemas import RetrievalInput


def expanded_groups():
    g = fixture_groups()
    for p in g[1]:
        for field, section, text in [
            ("receiving_authority", "RECEIVING_AUTHORITY", "Quầy mô phỏng Alpha."),
            ("required_documents", "REQUIRED_DOCUMENTS", "Giấy tờ hư cấu."),
            ("processing_times", "PROCESSING_TIME", "Hai ngày trong mô phỏng."),
        ]:
            f = copy.deepcopy(next(f for f in g[2] if f["procedure_id"] == p["procedure_id"]))
            f.update(
                fragment_id=p["procedure_id"] + ":" + field,
                section_type=section,
                text=text,
                content_sha256=digest(text.encode()),
            )
            g[2].append(f)
            p["field_evidence"][field] = [f["fragment_id"]]
            p["missing_fields"].remove(field)
            p[field] = (
                [dict(raw_text=text, min_business_days=2, max_business_days=2, condition=None)]
                if field == "processing_times"
                else [text]
            )
    return g


@pytest.fixture
def g4_data(tmp_path):
    return load_serving(write_dataset(tmp_path, expanded_groups()), VERSION, 2)


@pytest.mark.parametrize(
    "q",
    [
        "Đăng ký khai sinh nộp hồ sơ ở đâu?",
        "Mẫu Alpha đến đâu làm?",
        "Mẫu Alpha cần tới cơ quan nào?",
        "Nơi tiếp nhận Mẫu Alpha?",
        "Gửi hồ sơ Mẫu Alpha ở đâu?",
    ],
)
def test_location_not_documents(q):
    assert detect_fields(q) == {"receiving_authority"}


def test_multiple_fields():
    assert detect_fields("Cần giấy tờ gì, nộp ở đâu và lệ phí bao nhiêu?") == {
        "required_documents",
        "receiving_authority",
        "fees",
    }


def test_evidence_bound_to_location(g4_data):
    r = retrieve(g4_data, "Mẫu Alpha nộp hồ sơ ở đâu?")
    assert r["status"] == "ANSWER"
    assert {e["section_type"] for e in r["evidence"]} == {"RECEIVING_AUTHORITY"}


def test_multifield_reserves_evidence(g4_data):
    r = retrieve(g4_data, "Mẫu Alpha giấy tờ gì, nộp ở đâu, phí và bao lâu?")
    assert r["status"] == "ANSWER"
    assert len(r["evidence"]) <= 5
    assert {e["section_type"] for e in r["evidence"]} == {
        "REQUIRED_DOCUMENTS",
        "RECEIVING_AUTHORITY",
        "FEES",
        "PROCESSING_TIME",
    }
    assert retrieve(g4_data, "Mẫu Alpha giấy tờ gì và phí?", top_k=1)["status"] != "ANSWER"


def test_missing_field_never_fills_with_other_evidence(g4_data):
    r = retrieve(g4_data, "Mẫu Alpha lệ phí và các bước?")
    assert r["status"] == "INSUFFICIENT_DATA" and not r["evidence"]
    assert r["missing_fields"] == ["steps"]


def test_no_gold_opened(tmp_path, monkeypatch):
    root = write_dataset(tmp_path, expanded_groups())
    (root / "gold/questions.jsonl").write_text("POISON: MUST NOT OPEN", encoding="utf-8")
    original = Path.read_bytes

    def guarded(path):
        assert "/gold/" not in path.as_posix() and "/g4_eval/" not in path.as_posix()
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", guarded)
    d = load_serving(root, VERSION, 2)
    assert d.groups[4] == {}
    assert len(load_active_dataset(str(root), VERSION, 2, d.fingerprint).accepted) == 2


def test_serving_hash_does_not_depend_on_gold(tmp_path):
    root = write_dataset(tmp_path, expanded_groups())
    a = load_serving(root, VERSION, 2).fingerprint
    (root / "gold/questions.jsonl").unlink()
    assert load_serving(root, VERSION, 2).fingerprint == a


def test_context_refresh_provenance_switch_and_isolation(g4_data):
    first = uuid4()
    q, state, _ = prepare_turn(
        g4_data, RetrievalInput(query="Mẫu Alpha cần giấy tờ gì?"), None, first
    )
    assert q.filters.procedure_id == "fictional-alpha"
    for text in ["Nộp hồ sơ ở đâu?", "Còn lệ phí?", "Bao lâu?"]:
        # A fresh object from serialized DB state, not an in-process singleton.
        state = ConversationContext.model_validate_json(state.model_dump_json())
        q, state, ctx = prepare_turn(g4_data, RetrievalInput(query=text), state, uuid4())
        assert q.filters.procedure_id == "fictional-alpha"
        assert ctx.source_message_ids["active_procedure_id"] == first
    second = uuid4()
    q, state, _ = prepare_turn(g4_data, RetrievalInput(query="Mẫu Beta lệ phí?"), state, second)
    assert q.filters.procedure_id == "fictional-beta"
    assert state.source_message_ids["active_procedure_id"] == second
    q2, other, _ = prepare_turn(g4_data, RetrievalInput(query="Còn lệ phí?"), None, uuid4())
    assert other.active_procedure_id is None and q2.filters.procedure_id is None
    assert other.pending_clarification == "procedure_id"


def test_explicit_unknown_does_not_inherit(g4_data):
    _, state, _ = prepare_turn(g4_data, RetrievalInput(query="Mẫu Alpha lệ phí?"), None, uuid4())
    _, state, _ = prepare_turn(g4_data, RetrievalInput(query="Zzzzzzz giấy tờ gì?"), state, uuid4())
    assert state.active_procedure_id is None


def test_pending_field_survives_procedure_clarification(g4_data):
    _, state, _ = prepare_turn(g4_data, RetrievalInput(query="Lệ phí bao nhiêu?"), None, uuid4())
    q, state, _ = prepare_turn(g4_data, RetrievalInput(query="Mẫu Alpha"), state, uuid4())
    assert q.field_intents == ["fees"] and q.filters.procedure_id == "fictional-alpha"
    assert state.pending_clarification is None


def test_corpus_change_resets_context(g4_data):
    _, state, _ = prepare_turn(g4_data, RetrievalInput(query="Mẫu Alpha lệ phí?"), None, uuid4())
    state.corpus_version = "old-version"
    _, state, _ = prepare_turn(g4_data, RetrievalInput(query="Còn lệ phí?"), state, uuid4())
    assert state.active_procedure_id is None


def test_unknown_jurisdiction_abstains_and_is_retained(g4_data):
    mid = uuid4()
    q, state, _ = prepare_turn(
        g4_data,
        RetrievalInput(query="Mẫu Alpha lệ phí tại tỉnh Hư Cấu?"),
        None,
        mid,
    )
    assert state.confirmed_jurisdiction == "tỉnh Hư Cấu"
    assert state.source_message_ids["confirmed_jurisdiction"] == mid
    assert state.pending_clarification == "jurisdiction"
    r = retrieve(
        g4_data, q.query, procedure_id=q.filters.procedure_id, jurisdiction=q.filters.jurisdiction
    )
    assert r["status"] == "INSUFFICIENT_DATA" and not r["evidence"]


def test_dev_reader_rejects_wrong_filename_before_open(tmp_path, monkeypatch):
    def forbidden(*a, **k):
        pytest.fail("File must not be opened")

    monkeypatch.setattr(Path, "read_bytes", forbidden)
    with pytest.raises(CorpusError, match="DEV_FILENAME_REQUIRED"):
        read_dev(tmp_path / "scenario_test_v2.jsonl")


def test_dev_reader_rejects_non_dev_record(tmp_path):
    path = tmp_path / "scenario_dev.jsonl"
    path.write_text(json.dumps({"split": "TEST_V2"}), encoding="utf-8")
    with pytest.raises(CorpusError, match="DEV_ONLY"):
        read_dev(path)


def test_multiturn_benchmark_replays_user_context(g4_data):
    fee_ids = g4_data.procedures["fictional-alpha"]["field_evidence"]["fees"]
    row = {
        "scenario_version": "g4-eval-scenario-v1",
        "scenario_id": "fictional-dev-multiturn",
        "dataset_version": VERSION,
        "split": "DEV",
        "procedure_id": "fictional-alpha",
        "field_expected": "fees",
        "question": "Còn lệ phí?",
        "expected_status": "ANSWER",
        "gold_fragment_ids": fee_ids,
        "gold_label": {
            "status": "ANSWER",
            "procedure_id": "fictional-alpha",
            "field": "fees",
            "fragment_ids": fee_ids,
        },
        "is_multiturn": True,
        "conversation_turns": 3,
        "turns": [
            {"role": "user", "text": "Mẫu Alpha cần giấy tờ gì?"},
            {"role": "assistant", "text": "Phản hồi mô phỏng."},
            {"role": "user", "text": "Còn lệ phí?"},
        ],
        "review": {"status": "APPROVED"},
    }
    result = benchmark(g4_data, [row])
    assert result["scored_scenarios"] == 1
    assert result["scored_multiturn"] == 1
    assert result["routing_accuracy"] == 1
    assert result["field_accuracy"] == 1
    assert result["status_accuracy"] == 1
    assert result["recall_at_5"] == 1


def test_title_keywords_are_not_question_intents(g4_data):
    from app.rag.g3.retrieval import fields_for_query

    g4_data.procedures["fictional-alpha"]["title"] = "Miễn lệ phí hư cấu Alpha"
    assert fields_for_query(g4_data, "Miễn lệ phí hư cấu Alpha cần giấy tờ gì?") == {
        "required_documents"
    }
    assert fields_for_query(g4_data, "Miễn lệ phí hư cấu Alpha mất bao lâu?") == {
        "processing_times"
    }


def test_documents_context_versus_documents_question():
    assert detect_fields("Chuẩn bị hồ sơ Mẫu Alpha để nộp ở đâu?") == {"receiving_authority"}
    assert detect_fields("Mẫu Alpha cần chuẩn bị hồ sơ gì?") == {"required_documents"}
    assert detect_fields("Mẫu Alpha hồ sơ và lệ phí?") == {"required_documents", "fees"}


def test_pending_scope_answer_keeps_procedure(g4_data):
    _, state, _ = prepare_turn(
        g4_data, RetrievalInput(query="Mẫu Alpha lệ phí tại tỉnh Hư Cấu?"), None, uuid4()
    )
    q, state, _ = prepare_turn(g4_data, RetrievalInput(query="Tỉnh Mô Phỏng"), state, uuid4())
    assert q.filters.procedure_id == "fictional-alpha"
    assert q.field_intents == ["fees"]
    assert state.confirmed_jurisdiction == "Tỉnh Mô Phỏng"


def test_field_clarification_required_for_bare_procedure(g4_data):
    q, state, _ = prepare_turn(g4_data, RetrievalInput(query="Mẫu Alpha"), None, uuid4())
    result = retrieve(
        g4_data, q.query, procedure_id=q.filters.procedure_id, field_intents=q.field_intents
    )
    assert result["status"] == "NEED_CLARIFICATION" and not result["evidence"]
    assert state.pending_clarification == "field_intents"


def test_known_jurisdiction_filter(g4_data):
    g4_data.procedures["fictional-alpha"]["jurisdiction"]["province"] = "Tỉnh Mô Phỏng"
    assert (
        retrieve(g4_data, "Mẫu Alpha lệ phí?", jurisdiction="Tỉnh Mô Phỏng")["status"] == "ANSWER"
    )
    assert (
        retrieve(g4_data, "Mẫu Alpha lệ phí?", jurisdiction="Tỉnh Khác")["status"]
        == "INSUFFICIENT_DATA"
    )
