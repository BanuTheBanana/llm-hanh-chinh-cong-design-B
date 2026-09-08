import asyncio
import logging
import time

import httpx
from pydantic import ValidationError

from app.config import get_settings
from app.errors import APIError
from app.rag.corpus import CorpusError
from app.rag.retrieval import retrieve
from app.rag.schemas import (
    Citation,
    EvidenceBundle,
    GenerateGroundedRequest,
    GroundedAnswer,
    Grounding,
    RetrievalInput,
)
from app.rag.store import load_corpus

logger = logging.getLogger("g1.requests")


def validate_answer(answer: GroundedAnswer, bundle: EvidenceBundle) -> Grounding:
    available = {item.fragment_id: item for item in bundle.evidence}
    cited = answer.cited_fragment_ids
    if (
        answer.request_id != bundle.request_id
        or len(cited) != len(set(cited))
        or not set(cited) <= available.keys()
        or (answer.status == "ANSWER" and (not available or not cited))
    ):
        raise APIError(502, "AI_CITATION_INVALID", "Phản hồi AI có nguồn không hợp lệ.")
    if answer.status == "NEED_CLARIFICATION" and not answer.missing_information:
        raise APIError(502, "AI_SERVICE_ERROR", "AI chưa nêu thông tin cần làm rõ.")
    return Grounding(
        status=answer.status,
        corpus_version=bundle.corpus_version,
        sources=[
            Citation(
                fragment_id=i,
                source_id=available[i].source_id,
                title=available[i].title,
                url=available[i].url,
                metadata=available[i].metadata,
            )
            for i in cited
        ],
        missing_information=answer.missing_information,
    )


async def generate_grounded(
    client: httpx.AsyncClient, bundle: EvidenceBundle, history: list[dict]
) -> GroundedAnswer:
    settings = get_settings()
    try:
        async with asyncio.timeout(settings.ai_request_timeout_seconds):
            response = await client.post(
                settings.ai_service_url.rstrip("/") + "/internal/v1/generate-grounded",
                json=GenerateGroundedRequest(
                    evidence_bundle=bundle,
                    history=history[-10:],
                    max_output_tokens=settings.llm_max_output_tokens,
                ).model_dump(mode="json"),
                timeout=settings.ai_request_timeout_seconds,
            )
            if response.status_code == 504:
                raise TimeoutError()
            response.raise_for_status()
            return GroundedAnswer.model_validate(response.json())
    except (TimeoutError, httpx.TimeoutException) as exc:
        raise APIError(
            504, "AI_SERVICE_TIMEOUT", "AI đang phản hồi chậm. Vui lòng thử lại."
        ) from exc
    except (httpx.HTTPError, ValidationError, ValueError) as exc:
        raise APIError(502, "AI_SERVICE_ERROR", "Phản hồi grounded AI không hợp lệ.") from exc


async def _answer_with_rag(db, query: RetrievalInput, request_id, ai, history):
    settings = get_settings()
    started = time.perf_counter()
    try:
        if not settings.rag_corpus_version:
            raise CorpusError("CORPUS_VERSION_REQUIRED")
        corpus = await load_corpus(db, settings.rag_corpus_version, settings.rag_allow_fixtures)
    except (CorpusError, ValidationError) as exc:
        raise APIError(503, "RAG_CORPUS_UNAVAILABLE", "Corpus RAG chưa sẵn sàng.") from exc
    result = retrieve(corpus, query, request_id)
    await db.commit()  # Release transaction before external generation.
    logger.info(
        "request_id=%s stage=retrieval latency_ms=%.3f hits=%s",
        request_id,
        (time.perf_counter() - started) * 1000,
        len(result.bundle.evidence),
    )
    if not result.bundle.evidence:
        status = "NEED_CLARIFICATION" if result.needs_clarification else "INSUFFICIENT_DATA"
        text = (
            "Vui lòng cho biết thủ tục hoặc phạm vi địa phương cần tra cứu."
            if result.needs_clarification
            else "Chưa có đủ dữ liệu đã duyệt để trả lời câu hỏi này."
        )
        grounding = Grounding(
            status=status,
            corpus_version=corpus.version,
            sources=[],
            missing_information=["procedure_id hoặc jurisdiction"]
            if result.needs_clarification
            else [],
        )
        return text, grounding.model_dump(mode="json")
    # Never call legacy G1 generation as a fallback for a missing grounded endpoint.
    answer = await generate_grounded(ai.client, result.bundle, history)
    grounding = validate_answer(answer, result.bundle)
    return answer.answer, grounding.model_dump(mode="json")


async def answer_with_rag(db, query: RetrievalInput, request_id, ai, history):
    started = time.perf_counter()
    try:
        return await _answer_with_rag(db, query, request_id, ai, history)
    finally:
        logger.info(
            "request_id=%s stage=rag_orchestration latency_ms=%.3f",
            request_id,
            (time.perf_counter() - started) * 1000,
        )
