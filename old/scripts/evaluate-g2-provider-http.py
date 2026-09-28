"""Compare a locally exposed grounded provider on the full synthetic G2 corpus.

The report is aggregate-only. The script never sends data to a non-loopback URL.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from uuid import uuid4

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.rag.corpus import read_jsonl, validate_corpus
from app.rag.grounding import validate_answer
from app.rag.retrieval import retrieve
from app.rag.schemas import (
    GenerateGroundedRequest,
    GoldQuestion,
    GroundedAnswer,
    GroundingEvidence,
    RetrievalInput,
)


def request_json(url: str, *, body: dict | None = None, timeout: float = 60) -> dict:
    parsed = urlsplit(url)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"}:
        raise ValueError("LOCAL_AI_ENDPOINT_REQUIRED")
    payload = None if body is None else json.dumps(body).encode("utf-8")
    request = Request(
        url,
        data=payload,
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        method="GET" if body is None else "POST",
    )
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read())


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return round(ordered[math.ceil(fraction * len(ordered)) - 1], 3)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--ai-base-url", default="http://127.0.0.1:8001")
    parser.add_argument("--json-out", type=Path, required=True)
    args = parser.parse_args()

    dataset = REPO_ROOT / "data" / "demo_synthetic"
    corpus = validate_corpus(
        REPO_ROOT,
        dataset,
        "synthetic-demo-v1",
        {"fixture.invalid"},
        allow_fixture=True,
    )
    questions = sorted(
        read_jsonl(dataset / "gold" / "questions.jsonl", GoldQuestion),
        key=lambda item: item.question_id,
    )
    health = request_json(args.ai_base_url.rstrip("/") + "/internal/v2/health")

    provider_calls = 0
    errors = 0
    valid_generations = 0
    citation_bindings = 0
    status_correct = 0
    unsafe_answers = 0
    over_abstentions = 0
    fallback_count = 0
    latencies: list[float] = []
    gold_recalls: list[float] = []
    input_tokens: list[int] = []
    output_tokens: list[int] = []

    for question in questions:
        request_id = uuid4()
        found = retrieve(
            corpus,
            RetrievalInput(query=question.question, top_k=5, filters=question.filters),
            request_id,
        )
        bundle = found.bundle
        if found.needs_clarification:
            actual_status = "NEED_CLARIFICATION"
        elif not bundle.evidence:
            actual_status = "INSUFFICIENT_DATA"
        else:
            provider_calls += 1
            payload = GenerateGroundedRequest(
                request_id=request_id,
                evidence_bundle_id=bundle.evidence_bundle_id,
                corpus_version=bundle.corpus_version,
                data_classification=bundle.data_classification,
                query=bundle.query,
                evidence=[
                    GroundingEvidence(
                        fragment_id=item.fragment_id,
                        source_id=item.source_id,
                        procedure_id=item.procedure_id,
                        section_type=item.section_type,
                        title=item.title,
                        text=item.text,
                        jurisdiction=item.jurisdiction,
                        effective_from=item.effective_from,
                        effective_to=item.effective_to,
                        validity_status=item.validity_status,
                    )
                    for item in bundle.evidence
                ],
                as_of=bundle.as_of,
                max_output_tokens=500,
            )
            started = time.perf_counter()
            try:
                raw = request_json(
                    args.ai_base_url.rstrip("/") + "/internal/v2/generate",
                    body=payload.model_dump(mode="json"),
                )
                answer = GroundedAnswer.model_validate(raw)
                valid_generations += 1
                validate_answer(answer, bundle)
                citation_bindings += 1
                actual_status = answer.status
                latencies.append((time.perf_counter() - started) * 1000)
                input_tokens.append(answer.usage.input_tokens)
                output_tokens.append(answer.usage.output_tokens)
                if "chế độ trích xuất an toàn" in answer.answer.casefold():
                    fallback_count += 1
                gold = set(question.gold_fragment_ids)
                if gold:
                    gold_recalls.append(len(set(answer.cited_fragment_ids) & gold) / len(gold))
            except Exception:  # noqa: BLE001 - aggregate report deliberately hides details.
                errors += 1
                actual_status = "ERROR"
                latencies.append((time.perf_counter() - started) * 1000)

        status_correct += int(actual_status == question.expected_status)
        if question.expected_status != "ANSWER" and actual_status == "ANSWER":
            unsafe_answers += 1
        if question.expected_status == "ANSWER" and actual_status != "ANSWER":
            over_abstentions += 1

    result = {
        "scope": "G2 synthetic full set; same retrieval and EvidenceBundle; aggregate only",
        "candidate": args.candidate,
        "provider": health.get("provider"),
        "model": health.get("model"),
        "external_calls_enabled": health.get("external_calls_enabled"),
        "case_count": len(questions),
        "provider_calls": provider_calls,
        "error_rate": errors / provider_calls if provider_calls else 0.0,
        "status_accuracy": status_correct / len(questions),
        "valid_generation_rate": valid_generations / provider_calls if provider_calls else 1.0,
        "citation_binding_rate": citation_bindings / provider_calls if provider_calls else 1.0,
        "gold_citation_recall": statistics.mean(gold_recalls) if gold_recalls else None,
        "unsafe_answer_rate": unsafe_answers / len(questions),
        "over_abstention_rate": over_abstentions / len(questions),
        "extractive_fallback_count": fallback_count,
        "latency_ms_p50": round(statistics.median(latencies), 3) if latencies else None,
        "latency_ms_p95": percentile(latencies, 0.95),
        "mean_input_tokens": round(statistics.mean(input_tokens), 3) if input_tokens else None,
        "mean_output_tokens": round(statistics.mean(output_tokens), 3) if output_tokens else None,
    }
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
