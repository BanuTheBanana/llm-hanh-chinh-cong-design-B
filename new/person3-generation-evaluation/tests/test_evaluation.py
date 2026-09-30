import json

from person3_generation_evaluation import (
    GroundedGenerator,
    StaticRuntime,
    run_generation_benchmark,
    score_retrieval_records,
    tune_thresholds,
)


def sample_bundle():
    return {
        "bundle_id": "B-1",
        "query_text_segmented": "lệ_phí",
        "resolved_procedure_id": "PROC-1",
        "top_score": 0.9,
        "second_score": 0.4,
        "margin": 0.5,
        "confidence_status": "resolved",
        "ambiguous_candidates": [],
        "evidence": [
            {
                "fragment_id": "FRAG-FEE",
                "procedure_id": "PROC-1",
                "text": "Lệ phí là 10.000 đồng.",
                "score": 0.9,
                "method": "lexical",
                "source_id": "SRC-1",
                "source_version": "v1",
                "effective_date": None,
                "source_locator": "mục phí",
                "section_type": "fee",
            }
        ],
        "fusion_method": "bm25",
        "created_at": "2026-09-30T00:00:00Z",
    }


def test_generation_benchmark_reports_structural_and_latency_metrics():
    output = {
        "answer_text": "Lệ phí là 10.000 đồng.",
        "citations": [
            {
                "claim_text": "Lệ phí là 10.000 đồng.",
                "fragment_id": "FRAG-FEE",
                "source_id": "SRC-1",
                "source_locator": "mục phí",
            }
        ],
    }
    generator = GroundedGenerator(
        StaticRuntime(json.dumps(output, ensure_ascii=False)),
        max_repair_attempts=0,
    )
    report = run_generation_benchmark(
        [
            {
                "case_id": "fee",
                "evidence_bundle": sample_bundle(),
                "required_fragment_ids": ["FRAG-FEE"],
                "expected_answer_contains": ["10.000 đồng"],
            }
        ],
        generator,
        latency_budget_ms=100,
    )
    assert report["summary"]["structural_pass_rate"] == 1.0
    assert report["cases"][0]["required_fragment_coverage"] == 1.0
    assert report["summary"]["semantic_groundedness_scored"] is False


def test_scores_procedure_and_field_separately():
    record = {
        "expected_procedure_id": "PROC-1",
        "expected_section_type": "fee",
        "expected_confidence_status": "resolved",
        "evidence_bundle": sample_bundle(),
    }
    metrics = score_retrieval_records([record])
    assert metrics["procedure_level"]["accuracy"] == 1.0
    assert metrics["field_level"]["accuracy"] == 1.0
    assert metrics["confidence_status"]["accuracy"] == 1.0


def test_threshold_tuning_uses_expected_status_labels():
    rows = [
        {"top_score": 0.9, "second_score": 0.2, "expected_confidence_status": "resolved"},
        {"top_score": 0.8, "second_score": 0.78, "expected_confidence_status": "ambiguous"},
        {"top_score": 0.2, "second_score": 0.1, "expected_confidence_status": "low_confidence"},
    ]
    report = tune_thresholds(rows, score_floors=[0.3, 0.5], margin_floors=[0.05, 0.2])
    assert report["best"]["accuracy"] == 1.0
