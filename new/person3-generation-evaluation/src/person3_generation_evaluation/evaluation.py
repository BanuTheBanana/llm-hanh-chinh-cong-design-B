from __future__ import annotations

import math
from statistics import median

from .generator import GenerationContractError, GroundedGenerator, validate_generated_output


def _percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    rank = max(0, min(len(ordered) - 1, math.ceil(p * len(ordered)) - 1))
    return ordered[rank]


def evaluate_output(
    bundle: dict,
    output: dict,
    *,
    required_fragment_ids: list[str] | None = None,
    expected_answer_contains: list[str] | None = None,
    latency_ms: float | None = None,
    latency_budget_ms: float | None = None,
) -> dict:
    failures: list[str] = []
    try:
        validate_generated_output(bundle, output)
        contract_valid = True
    except GenerationContractError as exc:
        contract_valid = False
        failures.append(f"generation_contract:{exc}")

    evidence_ids = {item["fragment_id"] for item in bundle.get("evidence", [])}
    cited_ids = {
        citation.get("fragment_id")
        for citation in output.get("citations", [])
        if citation.get("fragment_id") in evidence_ids
    }
    expected_ids = set(required_fragment_ids or [])
    coverage = None if not expected_ids else len(expected_ids & cited_ids) / len(expected_ids)

    missing_phrases = [
        phrase
        for phrase in (expected_answer_contains or [])
        if phrase not in output.get("answer_text", "")
    ]
    if missing_phrases:
        failures.append("missing_expected_text:" + "|".join(missing_phrases))

    latency_pass = None
    if latency_ms is not None and latency_budget_ms is not None:
        latency_pass = latency_ms <= latency_budget_ms
        if not latency_pass:
            failures.append("latency_budget_exceeded")

    return {
        "contract_valid": contract_valid,
        "citation_binding_pass": contract_valid,
        "cited_fragment_ids": sorted(cited_ids),
        "evidence_citation_coverage": (
            len(cited_ids) / len(evidence_ids) if evidence_ids else 0.0
        ),
        "required_fragment_coverage": coverage,
        "expected_text_pass": not missing_phrases,
        "latency_ms": latency_ms,
        "latency_pass": latency_pass,
        "semantic_groundedness": None,
        "semantic_groundedness_note": (
            "Requires benchmark/manual-or-agreed-judge evaluation; structural citation binding is not entailment."
        ),
        "failures": failures,
        "passed_structural_gate": not failures,
    }


def run_generation_benchmark(
    cases: list[dict],
    generator: GroundedGenerator,
    *,
    latency_budget_ms: float | None = None,
) -> dict:
    rows = []
    latencies: list[float] = []
    for case in cases:
        case_id = case.get("case_id", f"case-{len(rows)+1}")
        bundle = case["evidence_bundle"]
        try:
            output, metrics = generator.generate_with_metrics(bundle)
            latencies.append(metrics.elapsed_ms)
            result = evaluate_output(
                bundle,
                output,
                required_fragment_ids=case.get("required_fragment_ids"),
                expected_answer_contains=case.get("expected_answer_contains"),
                latency_ms=metrics.elapsed_ms,
                latency_budget_ms=latency_budget_ms,
            )
            result.update(
                {
                    "case_id": case_id,
                    "output": output,
                    "prompt_tokens": metrics.prompt_tokens,
                    "completion_tokens": metrics.completion_tokens,
                    "repair_attempts": metrics.repair_attempts,
                }
            )
        except Exception as exc:
            result = {
                "case_id": case_id,
                "contract_valid": False,
                "citation_binding_pass": False,
                "semantic_groundedness": None,
                "failures": [f"runtime_or_generation:{type(exc).__name__}:{exc}"],
                "passed_structural_gate": False,
            }
        rows.append(result)

    passed = sum(bool(row.get("passed_structural_gate")) for row in rows)
    return {
        "summary": {
            "cases": len(rows),
            "structural_pass_rate": passed / len(rows) if rows else 0.0,
            "latency_p50_ms": median(latencies) if latencies else None,
            "latency_p95_ms": _percentile(latencies, 0.95),
            "semantic_groundedness_scored": False,
        },
        "cases": rows,
    }


def score_retrieval_records(records: list[dict]) -> dict:
    procedure_total = procedure_correct = 0
    field_total = field_correct = 0
    status_total = status_correct = 0

    for row in records:
        bundle = row.get("evidence_bundle", row)
        expected_procedure = row.get("expected_procedure_id")
        if expected_procedure is not None:
            procedure_total += 1
            procedure_correct += int(bundle.get("resolved_procedure_id") == expected_procedure)

        expected_field = row.get("expected_section_type")
        if expected_field is not None:
            field_total += 1
            evidence = bundle.get("evidence") or []
            actual_field = evidence[0].get("section_type") if evidence else None
            field_correct += int(actual_field == expected_field)

        expected_status = row.get("expected_confidence_status")
        if expected_status is not None:
            status_total += 1
            status_correct += int(bundle.get("confidence_status") == expected_status)

    def metric(correct: int, total: int) -> dict:
        return {
            "correct": correct,
            "total": total,
            "accuracy": correct / total if total else None,
        }

    return {
        "procedure_level": metric(procedure_correct, procedure_total),
        "field_level": metric(field_correct, field_total),
        "confidence_status": metric(status_correct, status_total),
    }
