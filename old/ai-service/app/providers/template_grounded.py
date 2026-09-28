import re
import unicodedata
from collections.abc import Sequence
from datetime import date

from app.providers.grounded_base import GroundedGenerationResult, GroundedProvider
from app.schemas import GroundedDataClassification, GroundingEvidenceFragment

_STOP_WORDS = {
    "các",
    "cho",
    "có",
    "của",
    "gì",
    "giả",
    "hồ",
    "không",
    "là",
    "lập",
    "một",
    "nào",
    "những",
    "nguồn",
    "sơ",
    "theo",
    "thì",
    "thủ",
    "tôi",
    "và",
    "về",
    "tục",
}
_INSTRUCTION_MARKERS = (
    "bỏ qua chỉ dẫn",
    "bỏ qua system",
    "ignore previous",
    "system prompt",
    "assistant:",
    "<script",
)


def _normalize(value: str) -> str:
    return unicodedata.normalize("NFKC", value).casefold()


def _tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"\w+", _normalize(value), flags=re.UNICODE)
        if len(token) >= 3 and token not in _STOP_WORDS
    }


def _contains_instruction_marker(value: str) -> bool:
    normalized = _normalize(value)
    return any(marker in normalized for marker in _INSTRUCTION_MARKERS)


def _is_eligible(fragment: GroundingEvidenceFragment, as_of: date | None) -> bool:
    if fragment.validity_status in {"EXPIRED", "FUTURE"}:
        return False
    if as_of is None:
        return True
    if fragment.effective_from is not None and fragment.effective_from > as_of:
        return False
    return fragment.effective_to is None or fragment.effective_to >= as_of


class TemplateGroundedProvider(GroundedProvider):
    """Deterministic D0 plumbing baseline. It must never serve real guidance."""

    name = "template"
    model_name = "template-grounded-v2"
    external_calls_enabled = False
    allowed_data_classifications: frozenset[GroundedDataClassification] = frozenset(
        {"D0_SYSTEM_SMOKE"}
    )

    async def generate_grounded(
        self,
        *,
        query: str,
        evidence: Sequence[GroundingEvidenceFragment],
        as_of: date | None,
        data_classification: GroundedDataClassification,
        max_output_tokens: int,
    ) -> GroundedGenerationResult:
        if data_classification not in self.allowed_data_classifications:
            raise AssertionError("service boundary must reject unsupported classifications")

        query_tokens = _tokens(query)
        candidates: list[tuple[int, int, GroundingEvidenceFragment]] = []
        for index, fragment in enumerate(evidence):
            searchable_text = f"{fragment.title} {fragment.text}"
            if not _is_eligible(fragment, as_of):
                continue
            if _contains_instruction_marker(searchable_text):
                continue
            score = len(query_tokens & _tokens(searchable_text))
            if score >= 2:
                candidates.append((score, -index, fragment))

        if not candidates or _contains_instruction_marker(query):
            return GroundedGenerationResult(
                answer="Bản mô phỏng D0 không tìm thấy evidence phù hợp và còn hiệu lực.",
                status="INSUFFICIENT_DATA",
                cited_fragment_ids=(),
                missing_information=(),
                provider="ignored-provider-output",
                model="ignored-model-output",
            )

        selected = max(candidates, key=lambda candidate: (candidate[0], candidate[1]))[2]
        if selected.section_type == "REQUIRED_FACTS":
            return GroundedGenerationResult(
                answer="Bản mô phỏng D0 cần người dùng bổ sung dữ kiện trước khi trả lời.",
                status="NEED_CLARIFICATION",
                cited_fragment_ids=(selected.fragment_id,),
                missing_information=("Thông tin trường hợp được evidence yêu cầu",),
                provider="ignored-provider-output",
                model="ignored-model-output",
            )

        prefix = "BẢN MÔ PHỎNG D0 - KHÔNG PHẢI HƯỚNG DẪN: "
        character_budget = min(8_000, max_output_tokens * 4)
        available_for_evidence = character_budget - len(prefix)
        if available_for_evidence < 20:
            return GroundedGenerationResult(
                answer="D0: không đủ ngân sách đầu ra.",
                status="INSUFFICIENT_DATA",
                cited_fragment_ids=(),
                missing_information=(),
                provider="ignored-provider-output",
                model="ignored-model-output",
            )
        answer = prefix + selected.text[:available_for_evidence]
        return GroundedGenerationResult(
            answer=answer,
            status="ANSWER",
            cited_fragment_ids=(selected.fragment_id,),
            missing_information=(),
            provider="ignored-provider-output",
            model="ignored-model-output",
        )
