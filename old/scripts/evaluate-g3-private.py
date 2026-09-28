"""One-shot, aggregate-only TEST evaluation for a private G3 corpus."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import sys
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.rag.g3.retrieval import retrieve
from app.rag.g3.runtime import retrieve_active_dataset
from app.rag.g3.validator import load
from app.rag.grounding import validate_answer
from app.rag.schemas import (
    GenerateGroundedRequest,
    GroundedAnswer,
    GroundingEvidence,
    RetrievalInput,
)


def request_json(url: str, *, body: dict | None = None, timeout: float = 60) -> dict:
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


def canonical_sha256(rows: list[dict]) -> str:
    raw = json.dumps(
        rows,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--corpus-sha256", required=True)
    parser.add_argument("--expected-rows", type=int, default=10)
    parser.add_argument("--ai-base-url", default="http://127.0.0.1:8001")
    parser.add_argument("--split", choices=("DEV", "TEST"), default="TEST")
    args = parser.parse_args()

    # This evaluator is deliberately local-only and never prints records, IDs, or model text.
    if args.ai_base_url.rstrip("/") not in {
        "http://127.0.0.1:8001",
        "http://localhost:8001",
    }:
        print('{"status":"FAIL","error":"LOCAL_AI_ENDPOINT_REQUIRED"}')
        return 2
    if "company_private" not in {
        part.casefold() for part in args.dataset.resolve().parts
    }:
        print('{"status":"FAIL","error":"PRIVATE_DATASET_PATH_REQUIRED"}')
        return 2

    try:
        data = load(args.dataset, args.version, args.expected_rows)
        if data.fingerprint != args.corpus_sha256:
            raise ValueError("G3_CORPUS_HASH_MISMATCH")
        if data.report()["readiness"] != "READY_FOR_DEMO":
            raise ValueError("G3_DATASET_NOT_READY")
        evaluation_rows = sorted(
            (row for row in data.groups[4].values() if row["split"] == args.split),
            key=lambda row: row["question_id"],
        )
        if args.split == "TEST":
            lock = json.loads(
                (args.dataset / "reports/test-lock.json").read_text(encoding="utf-8")
            )
            lock_valid = (
                lock.get("dataset_version") == args.version
                and lock.get("question_count") == len(evaluation_rows)
                and lock.get("content_sha256") == canonical_sha256(evaluation_rows)
            )
        else:
            lock_valid = None
        health = request_json(args.ai_base_url.rstrip("/") + "/internal/v2/health")
        local_boundary = (
            health.get("provider") == "local"
            and health.get("external_calls_enabled") is False
            and "D2_COMPANY_REAL" in health.get("allowed_data_classifications", [])
        )

        routing_checks: list[bool] = []
        retrieval_recalls: list[float] = []
        status_checks: list[bool] = []
        generation_latencies: list[float] = []
        generation_calls = 0
        valid_generations = 0
        citation_bindings = 0
        generation_http_errors = 0

        for question in evaluation_rows:
            low_level = retrieve(data, question["question"], top_k=5)
            if question["procedure_id"] is not None:
                routing_checks.append(
                    low_level["procedure_id"] == question["procedure_id"]
                )
            expected_fragments = set(question["gold_fragment_ids"])
            retrieved_fragments = {
                item["fragment_id"] for item in low_level["evidence"]
            }
            if expected_fragments:
                retrieval_recalls.append(
                    len(retrieved_fragments & expected_fragments)
                    / len(expected_fragments)
                )

            request_id = uuid4()
            bundle, status, _ = retrieve_active_dataset(
                data,
                RetrievalInput(query=question["question"], top_k=5),
                request_id,
            )
            if not bundle.evidence:
                status_checks.append(status == question["expected_status"])
                continue

            generation_calls += 1
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
                response = request_json(
                    args.ai_base_url.rstrip("/") + "/internal/v2/generate",
                    body=payload.model_dump(mode="json"),
                )
            except HTTPError:
                generation_http_errors += 1
                generation_latencies.append((time.perf_counter() - started) * 1000)
                status_checks.append(False)
                continue
            generation_latencies.append((time.perf_counter() - started) * 1000)
            answer = GroundedAnswer.model_validate(response)
            valid_generations += 1
            validate_answer(answer, bundle)
            citation_bindings += 1
            status_checks.append(answer.status == question["expected_status"])

        result = {
            "status": "PASS"
            if lock_valid is not False
            and local_boundary
            and valid_generations == generation_calls
            and citation_bindings == generation_calls
            else "FAIL",
            "scope": (
                "one-shot frozen TEST" if args.split == "TEST" else "development split"
            )
            + "; aggregate metrics only; no semantic legal-quality claim",
            "split": args.split,
            "dataset_version": args.version,
            "test_lock_valid": lock_valid,
            "local_only_boundary": local_boundary,
            "query_count": len(evaluation_rows),
            "generation_calls": generation_calls,
            "generation_http_errors": generation_http_errors,
            "routing_accuracy": (
                sum(routing_checks) / len(routing_checks) if routing_checks else None
            ),
            "retrieval_recall_at_5": (
                sum(retrieval_recalls) / len(retrieval_recalls)
                if retrieval_recalls
                else None
            ),
            "status_accuracy": sum(status_checks) / len(status_checks),
            "valid_generation_rate": (
                valid_generations / generation_calls if generation_calls else 1.0
            ),
            "citation_binding_rate": (
                citation_bindings / generation_calls if generation_calls else 1.0
            ),
            "generation_latency_ms_p50": (
                round(statistics.median(generation_latencies), 3)
                if generation_latencies
                else None
            ),
            "generation_latency_ms_p95": percentile(generation_latencies, 0.95),
        }
        print(json.dumps(result, ensure_ascii=True, sort_keys=True))
        return 0 if result["status"] == "PASS" else 1
    except Exception as error:  # noqa: BLE001 - never expose private content through details.
        print(
            json.dumps(
                {
                    "status": "FAIL",
                    "error": "PRIVATE_EVALUATION_FAILED",
                    "error_type": type(error).__name__,
                },
                sort_keys=True,
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
