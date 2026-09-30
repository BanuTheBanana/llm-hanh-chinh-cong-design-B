import pytest

from app.contracts import validate
from app.legacy.conversation_state import (
    build_conversation_state,
    is_follow_up,
    resolve_filters,
)
from app.legacy.grounding import check_sufficiency, verify_citations
from app.service import ground_and_answer


def evidence(fragment_id="FEE-1", section_type="fee"):
    return {
        "fragment_id": fragment_id,
        "procedure_id": "PROC-1",
        "section_type": section_type,
        "text": f"Evidence text for {section_type}.",
        "score": 1.2,
        "method": "lexical",
        "source_id": "SOURCE-1",
        "source_version": "v1",
        "effective_date": "2024-01-01",
        "source_locator": f"section/{fragment_id}",
    }


def bundle(evidence_items=None):
    return {
        "bundle_id": "BUNDLE-1",
        "query_text_segmented": "query",
        "resolved_procedure_id": "PROC-1",
        "top_score": 1.2,
        "second_score": 0.2,
        "margin": 1.0,
        "confidence_status": "resolved",
        "ambiguous_candidates": [],
        "evidence": evidence_items if evidence_items is not None else [evidence()],
        "fusion_method": "lexical_bm25_procedure_max",
        "created_at": "2026-09-30T00:00:00Z",
    }


def test_multi_field_answer_cites_each_evidence_fragment():
    result = ground_and_answer(
        bundle([evidence(), evidence("TIME-1", "processing_time")]),
        "Nêu lệ phí và thời gian giải quyết",
    )

    assert result["status"] == "answered"
    assert {citation["fragment_id"] for citation in result["citations"]} == {
        "FEE-1",
        "TIME-1",
    }


def test_missing_requested_field_abstains_without_citations():
    result = ground_and_answer(bundle(), "Nêu lệ phí và thời gian giải quyết")

    assert result["status"] == "insufficient_data"
    assert result["answer_text"] == ""
    assert result["citations"] == []
    assert result["clarification_prompt"]


@pytest.mark.parametrize(
    "mutation",
    [
        lambda item: item.update(procedure_id="PROC-2"),
        lambda item: item.update(source_version="v2"),
        lambda item: item.update(effective_date="2025-01-01"),
    ],
)
def test_inconsistent_procedure_or_source_version_abstains(mutation):
    first = evidence()
    second = evidence("OTHER-1", "processing_time")
    mutation(second)
    result = ground_and_answer(bundle([first, second]), "Nêu lệ phí và thời gian giải quyết")

    assert result["status"] == "insufficient_data"
    assert result["citations"] == []


def test_sufficiency_uses_declared_section_type_not_text_guessing():
    item = evidence(section_type="fee")
    item["text"] = "A fragment that mentions thời gian but is labeled fee."

    result = check_sufficiency(bundle([item]), ["processing_time"])

    assert not result.ok
    assert any("missing requested section processing_time" in problem for problem in result.problems)


def test_citation_must_point_into_current_bundle_and_match_answer_span():
    current = bundle()
    citation = {
        "claim_text": "unsupported claim",
        "fragment_id": "NOT-IN-BUNDLE",
        "source_id": "SOURCE-1",
        "source_locator": "section/FEE-1",
    }

    result = verify_citations(current, "An answer", [citation])

    assert not result.ok
    assert any("not in evidence bundle" in problem for problem in result.problems)


def test_citation_rejects_wrong_source_locator_and_unbound_claim():
    item = evidence()
    current = bundle([item])
    citation = {
        "claim_text": "not an answer span",
        "fragment_id": item["fragment_id"],
        "source_id": item["source_id"],
        "source_locator": "wrong/locator",
    }

    result = verify_citations(current, "A different answer", [citation])

    assert not result.ok
    assert any("source_locator" in problem for problem in result.problems)
    assert any("verbatim span" in problem for problem in result.problems)


def test_ambiguous_result_names_both_candidates():
    current = bundle([])
    current.update(
        confidence_status="ambiguous",
        resolved_procedure_id=None,
        ambiguous_candidates=[
            {"procedure_id": "PROC-1", "canonical_name": "Procedure One", "score": 0.82},
            {"procedure_id": "PROC-2", "canonical_name": "Procedure Two", "score": 0.80},
        ],
    )

    result = ground_and_answer(current, "procedure question")

    assert result["status"] == "clarification_needed"
    assert "Procedure One" in result["clarification_prompt"]
    assert "Procedure Two" in result["clarification_prompt"]


def test_malformed_ambiguity_fails_closed_instead_of_guessing():
    current = bundle([])
    current.update(
        confidence_status="ambiguous",
        resolved_procedure_id=None,
        ambiguous_candidates=[
            {"procedure_id": "PROC-1", "canonical_name": "Procedure One", "score": 0.82}
        ],
    )

    result = ground_and_answer(current, "procedure question")

    assert result["status"] == "insufficient_data"
    assert result["answer_text"] == ""
    assert result["citations"] == []


def test_low_confidence_abstains():
    current = bundle([])
    current.update(confidence_status="low_confidence", resolved_procedure_id=None)

    result = ground_and_answer(current, "unknown question")

    assert result["status"] == "insufficient_data"
    assert result["citations"] == []


def test_follow_up_carries_filters_but_new_topic_does_not():
    state = {
        "active_filters": {
            "jurisdiction": "Tỉnh A",
            "effective_date": "2024-01-01",
            "scope": "cá nhân",
        }
    }

    assert is_follow_up("  Còn lệ phí thế nào?")
    assert resolve_filters("còn lệ phí", {}, state) == state["active_filters"]
    assert resolve_filters("Tôi hỏi một thủ tục khác", {}, state) == {
        "jurisdiction": None,
        "effective_date": None,
        "scope": None,
    }


def test_explicit_and_supplied_filters_override_carried_values():
    state = {"active_filters": {"jurisdiction": "Tỉnh A", "effective_date": "2024-01-01", "scope": None}}

    assert resolve_filters("còn lệ phí ngày 02/03/2025", {}, state)["effective_date"] == "2025-03-02"
    assert resolve_filters("còn lệ phí", {"effective_date": None}, state)["effective_date"] is None
    assert resolve_filters("còn lệ phí", {"jurisdiction": "Tỉnh B"}, state)["jurisdiction"] == "Tỉnh B"


def test_state_replaces_old_procedure_and_requested_fields():
    current = bundle()
    current["resolved_procedure_id"] = "PROC-2"
    state = build_conversation_state(
        "SESSION-1",
        {"jurisdiction": None, "effective_date": None, "scope": None},
        current,
        "thủ tục mới lệ phí",
        "2026-09-30T00:00:00Z",
    )

    assert state["last_resolved_procedure_id"] == "PROC-2"
    assert state["last_requested_section_types"] == ["fee"]
    assert state["unresolved_references"] == []

    current["resolved_procedure_id"] = None
    cleared = build_conversation_state("SESSION-1", state["active_filters"], current, "không rõ", "2026-09-30T00:00:01Z")
    assert cleared["last_resolved_procedure_id"] is None


def test_ambiguous_state_preserves_candidate_ids_until_resolved():
    current = bundle([])
    current.update(
        confidence_status="ambiguous",
        resolved_procedure_id=None,
        ambiguous_candidates=[
            {"procedure_id": "PROC-1", "canonical_name": "Procedure One", "score": 0.82},
            {"procedure_id": "PROC-2", "canonical_name": "Procedure Two", "score": 0.80},
            {"procedure_id": "PROC-1", "canonical_name": "Procedure One", "score": 0.79},
        ],
    )

    state = build_conversation_state("SESSION-1", {}, current, "question", "2026-09-30T00:00:00Z")

    assert state["unresolved_references"] == ["PROC-1", "PROC-2"]
    validate("conversation_state", state)