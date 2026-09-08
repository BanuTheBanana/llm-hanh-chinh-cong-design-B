import re
import unicodedata
from collections.abc import Iterable
from statistics import median
from time import perf_counter

from app.evaluation.loader import LoadedSuite
from app.evaluation.models import (
    CaseEvaluation,
    EvalCase,
    EvaluationReport,
    EvaluationSummary,
    MatchRule,
    Split,
)
from app.grounded_service import run_grounded_generation
from app.providers.grounded_base import GroundedProvider


def _normalize(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return re.sub(r"\s+", " ", normalized).strip()


def _mean(values: Iterable[float]) -> float | None:
    items = list(values)
    return sum(items) / len(items) if items else None


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int((len(ordered) - 1) * percentile + 0.5)))
    return float(ordered[index])


def _rule_rate(answer: str, rules: list[MatchRule]) -> float | None:
    if not rules:
        return None
    normalized_answer = _normalize(answer)
    matched = sum(
        any(_normalize(phrase) in normalized_answer for phrase in rule.match_any) for rule in rules
    )
    return matched / len(rules)


def _retrieval_metrics(
    case: EvalCase,
) -> tuple[float | None, float | None, bool | None, float | None]:
    gold_ids = set(case.gold_question.gold_fragment_ids)
    if not gold_ids:
        return None, None, None, None
    retrieved = [fragment.fragment_id for fragment in case.grounding_request.evidence]
    recall_at_1 = len(set(retrieved[:1]) & gold_ids) / len(gold_ids)
    recall_in_bundle = len(set(retrieved) & gold_ids) / len(gold_ids)
    query_failed = recall_in_bundle == 0
    reciprocal_rank = next(
        (
            1 / rank
            for rank, fragment_id in enumerate(retrieved, start=1)
            if fragment_id in gold_ids
        ),
        0.0,
    )
    return recall_at_1, recall_in_bundle, query_failed, reciprocal_rank


async def _evaluate_case(case: EvalCase, provider: GroundedProvider) -> CaseEvaluation:
    recall_at_1, recall_in_bundle, query_failed, reciprocal_rank = _retrieval_metrics(case)
    retrieved_ids = [fragment.fragment_id for fragment in case.grounding_request.evidence]
    started_at = perf_counter()
    try:
        result = await run_grounded_generation(
            payload=case.grounding_request,
            provider=provider,
        )
    except Exception as exc:  # noqa: BLE001 - a report must retain per-case failures
        return CaseEvaluation(
            question_id=case.gold_question.question_id,
            request_id=case.grounding_request.request_id,
            evidence_bundle_id=case.grounding_request.evidence_bundle_id,
            split=case.gold_question.split,
            expected_status=case.gold_question.expected_status,
            actual_status=None,
            status_correct=False,
            retrieval_recall_at_1=recall_at_1,
            retrieval_recall_in_bundle=recall_in_bundle,
            retrieval_query_failed=query_failed,
            reciprocal_rank=reciprocal_rank,
            citation_ids_valid=False,
            gold_citation_recall=(0.0 if case.gold_question.gold_fragment_ids else None),
            lexical_expected_point_coverage=(0.0 if case.checks.expected_points else None),
            lexical_forbidden_claim_rate=None,
            retrieved_fragment_ids=retrieved_ids,
            cited_fragment_ids=[],
            answer=None,
            missing_information=[],
            latency_ms=round((perf_counter() - started_at) * 1000, 3),
            input_tokens=None,
            output_tokens=None,
            provider=None,
            model=None,
            abstention_correct=None,
            unsafe_answer=None,
            over_abstention=None,
            strict_safety_pass=False,
            error_code=type(exc).__name__,
        )

    evidence_ids = {fragment.fragment_id for fragment in case.grounding_request.evidence}
    cited_ids = set(result.cited_fragment_ids)
    citation_ids_valid = cited_ids <= evidence_ids
    gold_ids = set(case.gold_question.gold_fragment_ids)
    gold_citation_recall = len(cited_ids & gold_ids) / len(gold_ids) if gold_ids else None
    expected_coverage = _rule_rate(result.answer, case.checks.expected_points)
    forbidden_rate = _rule_rate(result.answer, case.checks.forbidden_points)
    expected_abstention = case.gold_question.expected_status != "ANSWER"
    abstention_correct = result.status != "ANSWER" if expected_abstention else None
    unsafe_answer = result.status == "ANSWER" if expected_abstention else None
    over_abstention = result.status != "ANSWER" if not expected_abstention else None
    unsafe_empty_evidence_answer = not evidence_ids and result.status == "ANSWER"
    answer_without_citation = result.status == "ANSWER" and not cited_ids
    strict_safety_pass = (
        citation_ids_valid
        and not unsafe_empty_evidence_answer
        and not answer_without_citation
        and unsafe_answer is not True
    )
    latency_ms = round((perf_counter() - started_at) * 1000, 3)

    return CaseEvaluation(
        question_id=case.gold_question.question_id,
        request_id=case.grounding_request.request_id,
        evidence_bundle_id=case.grounding_request.evidence_bundle_id,
        split=case.gold_question.split,
        expected_status=case.gold_question.expected_status,
        actual_status=result.status,
        status_correct=result.status == case.gold_question.expected_status,
        retrieval_recall_at_1=recall_at_1,
        retrieval_recall_in_bundle=recall_in_bundle,
        retrieval_query_failed=query_failed,
        reciprocal_rank=reciprocal_rank,
        citation_ids_valid=citation_ids_valid,
        gold_citation_recall=gold_citation_recall,
        lexical_expected_point_coverage=expected_coverage,
        lexical_forbidden_claim_rate=forbidden_rate,
        retrieved_fragment_ids=retrieved_ids,
        cited_fragment_ids=list(result.cited_fragment_ids),
        answer=result.answer,
        missing_information=list(result.missing_information),
        latency_ms=latency_ms,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        provider=result.provider,
        model=result.model,
        abstention_correct=abstention_correct,
        unsafe_answer=unsafe_answer,
        over_abstention=over_abstention,
        strict_safety_pass=strict_safety_pass,
    )


async def evaluate_suite(
    *, suite: LoadedSuite, provider: GroundedProvider, candidate: str, split: Split
) -> EvaluationReport:
    selected = [case for case in suite.cases if case.gold_question.split == split]
    if not selected:
        raise ValueError(f"suite contains no cases for split {split}")

    results = [await _evaluate_case(case, provider) for case in selected]
    completed = [result for result in results if result.error_code is None]
    latencies = [result.latency_ms for result in results if result.latency_ms is not None]
    summary = EvaluationSummary(
        case_count=len(results),
        completed_count=len(completed),
        error_rate=_mean(float(result.error_code is not None) for result in results),
        status_accuracy=_mean(float(result.status_correct) for result in results),
        retrieval_recall_at_1=_mean(
            result.retrieval_recall_at_1
            for result in results
            if result.retrieval_recall_at_1 is not None
        ),
        retrieval_recall_in_bundle=_mean(
            result.retrieval_recall_in_bundle
            for result in results
            if result.retrieval_recall_in_bundle is not None
        ),
        retrieval_query_fail_rate=_mean(
            float(result.retrieval_query_failed)
            for result in results
            if result.retrieval_query_failed is not None
        ),
        mean_reciprocal_rank=_mean(
            result.reciprocal_rank for result in results if result.reciprocal_rank is not None
        ),
        citation_id_validity=_mean(float(result.citation_ids_valid) for result in results),
        gold_citation_recall=_mean(
            result.gold_citation_recall
            for result in results
            if result.gold_citation_recall is not None
        ),
        lexical_expected_point_coverage=_mean(
            result.lexical_expected_point_coverage
            for result in results
            if result.lexical_expected_point_coverage is not None
        ),
        lexical_forbidden_claim_rate=_mean(
            result.lexical_forbidden_claim_rate
            for result in results
            if result.lexical_forbidden_claim_rate is not None
        ),
        abstention_accuracy=_mean(
            float(result.abstention_correct)
            for result in results
            if result.abstention_correct is not None
        ),
        unsafe_answer_rate=_mean(
            float(result.unsafe_answer) for result in results if result.unsafe_answer is not None
        ),
        over_abstention_rate=_mean(
            float(result.over_abstention)
            for result in results
            if result.over_abstention is not None
        ),
        strict_safety_pass_rate=_mean(float(result.strict_safety_pass) for result in results),
        latency_p50_ms=float(median(latencies)) if latencies else None,
        latency_p95_ms=_percentile(latencies, 0.95),
        mean_input_tokens=_mean(
            float(result.input_tokens) for result in completed if result.input_tokens is not None
        ),
        mean_output_tokens=_mean(
            float(result.output_tokens) for result in completed if result.output_tokens is not None
        ),
    )
    return EvaluationReport(
        suite_id=suite.manifest.suite_id,
        usage=suite.manifest.usage,
        corpus_version=suite.manifest.corpus_version,
        prompt_version=suite.manifest.prompt_version,
        cases_sha256=suite.manifest.cases_sha256,
        candidate=candidate,
        split=split,
        summary=summary,
        cases=results,
    )
