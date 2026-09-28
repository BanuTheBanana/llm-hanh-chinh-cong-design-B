from types import SimpleNamespace

import pytest

from app.rag.g4.intent import detect_fields
from app.rag.g5.hybrid import RouteCandidate
from app.rag.g5.intent_context import procedure_candidates
from app.rag.g5.topic_gate import decide_topic


def catalog():
    return SimpleNamespace(
        accepted={"birth", "marriage", "foreign_marriage"},
        sources={"s1": {"procedure_code": ""}, "s2": {"procedure_code": ""}},
        procedures={
            "birth": {
                "title": "Đăng ký khai sinh",
                "aliases": ["làm giấy khai sinh"],
                "source_ids": ["s1"],
            },
            "marriage": {
                "title": "Thủ tục đăng ký kết hôn",
                "aliases": [],
                "source_ids": ["s2"],
            },
            "foreign_marriage": {
                "title": "Đăng ký kết hôn có yếu tố nước ngoài",
                "aliases": [],
                "source_ids": ["s2"],
            },
            "house_number": {
                "title": "Hồ sơ cấp số nhà",
                "aliases": [],
                "source_ids": ["s2"],
            },
        },
    )


class Router:
    def __init__(self, result):
        self.result = result
        self.calls = 0

    async def route(self, _data, _query):
        self.calls += 1
        return self.result


def adjudicated_catalog():
    construction_shadow = "d2_title_70d8a7c53c19"
    construction = "d2_title_c98b4aa39036"
    cremation_shadow = "d2_title_1df9a1a807f0"
    cremation = "d2_title_10ed2a9ea4a7"
    procedures = {
        construction_shadow: {
            "title": "HO SO CAP GIAY PHEP XAY DUNG",
            "aliases": [],
            "source_ids": ["s26"],
        },
        construction: {
            "title": "CAP GIAY PHEP XAY DUNG",
            "aliases": [],
            "source_ids": ["s28"],
        },
        cremation_shadow: {
            "title": "THU TUC HO TRO CHI PHI KHUYEN KHICH HOA TANG DOI VOI NGUOI DAN",
            "aliases": [],
            "source_ids": ["s11"],
        },
        cremation: {
            "title": "HO TRO CHI PHI KHUYEN KHICH HOA TANG",
            "aliases": [],
            "source_ids": ["s17"],
        },
    }
    return SimpleNamespace(
        accepted=set(procedures),
        procedures=procedures,
        sources={key: {"procedure_code": ""} for key in ["s26", "s28", "s11", "s17"]},
    )


@pytest.mark.asyncio
async def test_adjudicated_duplicate_names_route_to_preferred_rows():
    data = adjudicated_catalog()
    construction = await decide_topic(
        data, "HO SO CAP GIAY PHEP XAY DUNG gom gi?", None, Router(None)
    )
    cremation = await decide_topic(
        data,
        "THU TUC HO TRO CHI PHI KHUYEN KHICH HOA TANG DOI VOI NGUOI DAN gom gi?",
        None,
        Router(None),
    )
    assert construction.procedure_id == "d2_title_c98b4aa39036"
    assert cremation.procedure_id == "d2_title_10ed2a9ea4a7"


def test_adjudicated_shadow_rows_remain_in_corpus_but_not_model_candidates():
    data = adjudicated_catalog()
    assert len(data.procedures) == 4
    assert {item["id"] for item in procedure_candidates(data)} == {
        "d2_title_c98b4aa39036",
        "d2_title_10ed2a9ea4a7",
    }


def test_cremation_alias_prevents_procedure_words_from_becoming_fee_intent():
    query = (
        "Gia đình tôi vừa hỏa táng người thân. Hồ sơ xin hỗ trợ chi phí hỏa táng "
        "gồm những giấy tờ gì?"
    )
    assert detect_fields(query, ["hỗ trợ chi phí hỏa táng"]) == {"required_documents"}


@pytest.mark.asyncio
async def test_exact_accented_alias_is_not_rejected_by_unrelated_ho_so_word():
    data = adjudicated_catalog()
    data.procedures["d2_title_10ed2a9ea4a7"]["title"] = (
        "Hỗ trợ chi phí khuyến khích hỏa táng"
    )
    data.procedures["d2_title_10ed2a9ea4a7"]["aliases"] = ["Hỗ trợ chi phí hỏa táng"]
    decision = await decide_topic(
        data,
        "Gia đình tôi vừa hỏa táng người thân. Hồ sơ xin hỗ trợ chi phí hỏa táng "
        "gồm những giấy tờ gì?",
        None,
        Router(None),
    )
    assert decision.procedure_id == "d2_title_10ed2a9ea4a7"


@pytest.mark.asyncio
async def test_explicit_new_procedure_switches_without_needing_embedding():
    router = Router(None)
    decision = await decide_topic(
        catalog(), "Tôi muốn đăng ký khai sinh, cần giấy tờ gì?", "marriage", router
    )
    assert (decision.action, decision.procedure_id) == ("SWITCH", "birth")
    assert router.calls == 0


@pytest.mark.asyncio
async def test_specific_catalog_variant_beats_shorter_base_title():
    decision = await decide_topic(
        catalog(),
        "Tôi muốn đăng ký kết hôn với người nước ngoài. Hồ sơ cần gì?",
        "marriage",
        Router(None),
    )
    assert (decision.action, decision.procedure_id) == ("SWITCH", "foreign_marriage")

    negated = await decide_topic(
        catalog(),
        "Tôi muốn đăng ký kết hôn, không có yếu tố nước ngoài.",
        None,
        Router(None),
    )
    assert (negated.action, negated.procedure_id) == ("SWITCH", "marriage")


@pytest.mark.asyncio
async def test_document_inventory_does_not_switch_procedure():
    router = Router(RouteCandidate("birth", 0.9, 0.9, 0.9))
    decision = await decide_topic(
        catalog(), "Tôi đã có giấy khai sinh, còn cần bổ sung gì?", "marriage", router
    )
    assert decision.action == "KEEP"
    assert router.calls == 0


@pytest.mark.asyncio
async def test_unknown_new_procedure_clarifies_instead_of_reusing_old_context():
    decision = await decide_topic(
        catalog(), "Tôi muốn xin cấp sổ nhà, cần hồ sơ gì?", "marriage", Router(None)
    )
    assert decision.action == "CLARIFY"


@pytest.mark.asyncio
async def test_dense_only_candidate_is_not_enough_to_switch():
    weak = RouteCandidate("birth", 0.78, 0.05, 0.95)
    decision = await decide_topic(
        catalog(), "Tôi muốn xin cấp một giấy khác", "marriage", Router(weak)
    )
    assert decision.action == "CLARIFY"


@pytest.mark.asyncio
async def test_strong_hybrid_candidate_can_switch_implicit_new_topic():
    strong = RouteCandidate("birth", 0.82, 0.6, 0.9)
    decision = await decide_topic(
        catalog(), "Tôi muốn làm thủ tục cho em bé mới sinh", "marriage", Router(strong)
    )
    assert (decision.action, decision.procedure_id) == ("SWITCH", "birth")


@pytest.mark.asyncio
async def test_lexically_exact_colloquial_business_pause_is_not_vetoed_by_dense_score():
    candidate = RouteCandidate("marriage", 0.745, 1.0, 0.537)
    decision = await decide_topic(
        catalog(),
        "Năm nay làm ăn thua lỗ, tôi muốn tạm ngừng hộ kinh doanh thì cần chuẩn bị gì?",
        None,
        Router(candidate),
    )
    assert (decision.action, decision.procedure_id) == ("SWITCH", "marriage")


@pytest.mark.asyncio
async def test_different_accented_legal_word_cannot_be_collapsed():
    data = catalog()
    data.accepted.add("house_number")
    strong = RouteCandidate("house_number", 0.92, 0.9, 0.95)
    decision = await decide_topic(
        data, "Tôi muốn xin cấp sổ nhà, cần giấy tờ gì?", "marriage", Router(strong)
    )
    assert decision.action == "CLARIFY"
    first_turn = await decide_topic(
        data, "Tôi muốn xin cấp sổ nhà, cần giấy tờ gì?", None, Router(strong)
    )
    assert first_turn.action == "CLARIFY"

    exact = await decide_topic(
        data, "Tôi muốn xin cấp số nhà, cần giấy tờ gì?", "marriage", Router(None)
    )
    assert (exact.action, exact.procedure_id) == ("SWITCH", "house_number")


@pytest.mark.asyncio
async def test_correction_uses_positive_target_instead_of_rejected_old_title():
    decision = await decide_topic(
        catalog(),
        'Tôi vừa nói chưa đúng ý: bỏ "Thủ tục đăng ký kết hôn" nhé. '
        'Việc tôi thực sự cần là "Đăng ký khai sinh".',
        "marriage",
        Router(None),
    )
    assert (decision.action, decision.procedure_id) == ("SWITCH", "birth")


@pytest.mark.asyncio
async def test_first_turn_implicit_request_uses_hybrid_verifier():
    router = Router(RouteCandidate("birth", 0.82, 0.6, 0.9))
    decision = await decide_topic(
        catalog(), "Vợ tôi vừa sinh em bé, giờ làm giấy cho con thế nào?", None, router
    )
    assert (decision.action, decision.procedure_id) == ("SWITCH", "birth")
    assert router.calls == 1
