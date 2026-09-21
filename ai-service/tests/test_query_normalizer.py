"""Regression tests for routing-only Vietnamese query normalization."""

from app.query_normalizer import normalize_query

CANDIDATES = (
    "Thủ tục đăng ký khai sinh",
    "Thủ tục đăng ký kết hôn",
    "Hồ sơ cấp số nhà",
)


def test_repairs_unique_domain_typos_without_changing_original():
    original = "Tôi muốn làm giấy khai sih cho em bé"
    result = normalize_query(original, candidate_names=CANDIDATES)

    assert "khai sinh" in result.text
    assert ("sih", "sinh") in result.typo_repairs
    assert original == "Tôi muốn làm giấy khai sih cho em bé"


def test_expands_reviewed_synonyms_for_intent_detection():
    result = normalize_query("Nộp qua mạng và chờ bao lâu?", candidate_names=CANDIDATES)

    assert "truc tuyen" in result.text
    assert "thoi gian" in result.text


def test_normalizes_common_online_abbreviation():
    result = normalize_query("Nếu nộp onl thì sao?", candidate_names=CANDIDATES)

    assert "truc tuyen" in result.text
    assert "onl" not in result.text.split()


def test_does_not_repair_numbers_or_ambiguous_short_words():
    result = normalize_query("Phường 12, bản sao 8000 đồng", candidate_names=CANDIDATES)

    assert "12" in result.text
    assert "8000" in result.text
    assert not any(source in {"12", "8000"} for source, _ in result.typo_repairs)
