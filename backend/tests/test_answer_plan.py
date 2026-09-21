"""Fictional guard regressions; no company text or gold questions in Git."""

from datetime import date
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest

from app.config import Settings
from app.rag.answer_plan import (
    AnswerPlan,
    build_answer_plan,
    plan_citations,
    render_plan,
    requested_fields,
    verify_candidate,
)
from app.rag.planned_grounding import answer_with_plan
from app.rag.schemas import Evidence, EvidenceBundle, GroundedAnswer, Grounding


def bundle(text="Bản chính miễn phí; bản sao 2.000 đồng/bản.", section="FEES"):
    return EvidenceBundle(
        request_id=uuid4(),
        evidence_bundle_id=uuid4(),
        corpus_version="fictional-v1",
        data_classification="D0_SYSTEM_SMOKE",
        query="Thủ tục giả lập có lệ phí gì?",
        evidence=[
            Evidence(
                fragment_id="f1",
                source_id="s1",
                procedure_id="p1",
                section_type=section,
                title="Fixture",
                url=None,
                text=text,
                score=1,
                metadata={},
            )
        ],
    )


def candidate(b, **patch):
    return GroundedAnswer.model_validate(
        {
            "request_id": b.request_id,
            "evidence_bundle_id": b.evidence_bundle_id,
            "corpus_version": b.corpus_version,
            "data_classification": b.data_classification,
            "prompt_version": "g2-grounded-v2",
            "answer": b.evidence[0].text,
            "status": "ANSWER",
            "cited_fragment_ids": ["f1"],
            "missing_information": [],
            "provider": "local",
            "model": "fixture",
            "latency_ms": 1,
            "usage": {"input_tokens": 1, "output_tokens": 1},
            **patch,
        }
    )


def plan_for(b, **kwargs):
    return build_answer_plan(b, field_evidence={"fees": ["f1"]}, **kwargs)


@pytest.mark.parametrize(
    "question,expected",
    [
        ("Đăng ký khai sinh nộp hồ sơ ở đâu?", ["receiving_authority"]),
        ("Hồ sơ cần giấy tờ gì và nộp ở đâu?", ["required_documents", "receiving_authority"]),
        ("Lệ phí và thời gian giải quyết?", ["fees", "processing_times"]),
        ("Còn bao lâu?", ["processing_times"]),
        ("Xin chào", []),
    ],
)
def test_guard_field_adapter(question, expected):
    assert requested_fields(question) == expected


@pytest.mark.parametrize(
    "title,question,expected",
    [
        (
            "Thủ tục hỗ trợ chi phí Sao Băng",
            "Hỗ trợ chi phí Sao Băng cần giấy tờ gì?",
            ["required_documents"],
        ),
        (
            "Gia hạn thời gian Sao Băng",
            "Gia hạn thời gian Sao Băng nộp ở đâu?",
            ["receiving_authority"],
        ),
        ("Hỗ trợ chi phí Sao Băng", "Lệ phí của hỗ trợ chi phí Sao Băng là gì?", ["fees"]),
    ],
)
def test_procedure_name_keywords_are_not_field_intents(title, question, expected):
    assert requested_fields(question, procedure_titles=[title]) == expected


@pytest.mark.parametrize(
    "wrong",
    [
        "Không mất lệ phí.",
        "Bản chính miễn phí.",
        "2.000 đồng.",
        "Bản chính miễn phí; bản sao 3.000 đồng/bản.",
        "Bản chính miễn phí; bản sao 2.000 đồng/bản. Nộp tại cơ quan xã.",
    ],
)
def test_blocks_omitted_conditions_changed_amount_and_extra_claim(wrong):
    b = bundle()
    assert "FULL_CLAIM_TEXT_NOT_VERIFIED" in verify_candidate(
        plan_for(b), candidate(b, answer=wrong)
    )


def test_verbatim_passes_and_preserves_conditions():
    b = bundle()
    plan = plan_for(b)
    assert verify_candidate(plan, candidate(b)) == []
    assert b.evidence[0].text in render_plan(plan)
    assert plan.claims[0].conditions is None
    assert plan_citations(plan) == ["f1"]


def test_reviewed_full_corpus_sft_format_passes_without_weakening_claim_check():
    b = bundle()
    answer = "Theo ngu\u1ed3n \u0111\u00e3 duy\u1ec7t:\n- " + b.evidence[0].text
    assert verify_candidate(plan_for(b), candidate(b, answer=answer)) == []


def test_single_field_render_is_direct_and_conversational():
    text = render_plan(plan_for(bundle()))
    assert text.startswith("Lệ phí theo nguồn đã duyệt là:")
    assert bundle().evidence[0].text in text


def test_document_followup_acknowledges_existing_identity_document_safely():
    b = bundle(section="REQUIRED_DOCUMENTS")
    b.evidence[0].text = (
        "CCCD của cả hai vợ chồng (01 bản photo); Giấy chứng sinh (bản chính)."
    )
    plan = build_answer_plan(
        b,
        fields=["required_documents"],
        field_evidence={"required_documents": ["f1"]},
    )

    text = render_plan(plan, query="Tôi có CCCD rồi, cần bổ sung gì nữa?")

    assert text.startswith("Giấy tờ tùy thân bạn nêu có trong thành phần hồ sơ")
    assert b.evidence[0].text in text


def test_document_followup_acknowledges_marriage_certificate_from_source():
    b = bundle(section="REQUIRED_DOCUMENTS")
    b.evidence[0].text = "Giấy chứng nhận kết hôn (01 bản photo)."
    plan = build_answer_plan(
        b,
        fields=["required_documents"],
        field_evidence={"required_documents": ["f1"]},
    )

    text = render_plan(plan, query="Tôi có giấy chứng nhận kết hôn, có được tính không?")

    assert text.startswith("Giấy chứng nhận kết hôn bạn nêu có trong thành phần hồ sơ")
    assert b.evidence[0].text in text


def test_online_original_followup_combines_both_sources_without_inventing_timing():
    b = bundle(
        text="Giấy chứng sinh (bản chính, xuất trình để đối chiếu).",
        section="REQUIRED_DOCUMENTS",
    )
    b.query = "Nếu tôi nộp onl thì vẫn phải mang bản chính tới đối chiếu à?"
    b.evidence.append(
        Evidence(
            fragment_id="f2",
            source_id="s2",
            procedure_id="p1",
            section_type="SUBMISSION_METHODS",
            title="Fixture",
            url=None,
            text="Cả trực tiếp và trực tuyến.",
            score=1,
            metadata={},
        )
    )
    plan = build_answer_plan(
        b,
        fields=["required_documents", "submission_methods"],
        field_evidence={"required_documents": ["f1"], "submission_methods": ["f2"]},
    )

    text = render_plan(plan, query=b.query)

    assert "Cả trực tiếp và trực tuyến." in text
    assert "Giấy chứng sinh (bản chính, xuất trình để đối chiếu)." in text
    assert "chưa nêu rõ thời điểm hoặc cách đối chiếu bản chính" in text
    assert plan_citations(plan) == ["f1", "f2"]


def test_wrong_field_and_missing_manifest_abstain():
    b = bundle(section="REQUIRED_DOCUMENTS")
    assert plan_for(b).status == "INSUFFICIENT_DATA"
    assert build_answer_plan(bundle()).status == "INSUFFICIENT_DATA"


def test_top_k_must_not_drop_condition_fragment():
    assert (
        build_answer_plan(bundle(), field_evidence={"fees": ["f1", "f2"]}).status
        == "INSUFFICIENT_DATA"
    )


def test_multiple_fields_require_all_fields():
    plan = plan_for(bundle(), fields=["fees", "processing_times"])
    assert plan.status == "INSUFFICIENT_DATA"
    assert plan.claims == []
    assert plan.missing_fields == ["processing_times"]


@pytest.mark.parametrize("validity", ["EXPIRED", "FUTURE"])
def test_unusable_dates_are_rejected(validity):
    b = bundle()
    b.evidence[0].validity_status = validity
    assert plan_for(b).status == "INSUFFICIENT_DATA"


def test_unknown_effective_date_rejected_for_as_of():
    b = bundle()
    b.as_of = date(2026, 1, 1)
    assert plan_for(b).status == "INSUFFICIENT_DATA"


def test_mixed_procedures_rejected():
    b = bundle()
    b.evidence.append(b.evidence[0].model_copy(update={"fragment_id": "f2", "procedure_id": "p2"}))
    assert plan_for(b).status == "INSUFFICIENT_DATA"


def test_oversized_claim_not_truncated():
    plan = plan_for(bundle("x" * 8000))
    assert plan.status == "INSUFFICIENT_DATA"
    assert plan.reason == "ANSWER_BUDGET_EXCEEDED"
    assert plan.claims == []


def test_forged_citation_not_accepted():
    b = bundle()
    assert "CLAIM_CITATIONS_INCOMPLETE" in verify_candidate(
        plan_for(b), candidate(b, cited_fragment_ids=["forged"])
    )


@pytest.mark.parametrize("mode", ["good", "wrong", "binding", "timeout", "forged"])
async def test_orchestration_verifies_renders_and_records_reason(mode):
    b = bundle()
    data = SimpleNamespace(procedures={"p1": {"field_evidence": {"fees": ["f1"]}}})

    def handler(request):
        if mode == "timeout":
            return httpx.Response(504)
        value = candidate(b).model_dump(mode="json")
        if mode == "wrong":
            value["answer"] = "Miễn phí."
        if mode == "binding":
            value["request_id"] = str(uuid4())
        if mode == "forged":
            value["cited_fragment_ids"] = ["forged"]
        return httpx.Response(200, json=value)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        text, metadata = await answer_with_plan(client, b, data)
    grounding = Grounding.model_validate(metadata)
    assert text == render_plan(plan_for(b))
    assert grounding.status == "ANSWER"
    assert grounding.sources[0].fragment_id == "f1"
    assert grounding.knowledge_version == b.corpus_version
    assert grounding.verification.fallback_used == (mode != "good")
    assert grounding.verification.candidate_passed == (mode == "good")


async def test_unanswerable_plan_skips_model():
    b = bundle(section="REQUIRED_DOCUMENTS")
    data = SimpleNamespace(procedures={"p1": {"field_evidence": {"fees": ["f1"]}}})
    text, metadata = await answer_with_plan(None, b, data)
    assert metadata["status"] == "INSUFFICIENT_DATA"
    assert metadata["sources"] == []
    assert not metadata["verification"]["candidate_checked"]


def test_feature_disabled_by_default_and_requires_d2():
    assert not Settings(_env_file=None).g4_answer_plan_enabled
    with pytest.raises(ValueError):
        Settings(_env_file=None, g4_answer_plan_enabled=True)


def test_plan_contract_rejects_empty_answer_and_duplicate_fields():
    with pytest.raises(ValueError, match="INCOMPLETE_ANSWER_PLAN"):
        AnswerPlan(requested_fields=["fees"], claims=[], status="ANSWER", missing_fields=[])
    with pytest.raises(ValueError, match="DUPLICATE_PLAN_FIELD"):
        AnswerPlan(
            requested_fields=["fees", "fees"],
            claims=[],
            status="INSUFFICIENT_DATA",
            missing_fields=["fees"],
            reason="FIELD_EVIDENCE_INCOMPLETE",
        )


def test_full_claims_follow_reviewed_manifest_order_not_rank():
    b = bundle()
    b.evidence.append(
        b.evidence[0].model_copy(
            update={"fragment_id": "f2", "text": "Trường hợp ngoại lệ: cần đối chiếu bản chính."}
        )
    )
    plan = build_answer_plan(b, field_evidence={"fees": ["f2", "f1"]})
    assert plan_citations(plan) == ["f2", "f1"]
