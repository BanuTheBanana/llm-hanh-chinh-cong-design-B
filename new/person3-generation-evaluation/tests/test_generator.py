import json

import pytest

from person3_generation_evaluation import (
    GenerationContractError,
    GroundedGenerator,
    StaticRuntime,
    validate_generated_output,
)


def bundle():
    return {
        "bundle_id": "B-1",
        "query_text_segmented": "thời_hạn thủ_tục",
        "resolved_procedure_id": "PROC-1",
        "top_score": 0.9,
        "second_score": 0.2,
        "margin": 0.7,
        "confidence_status": "resolved",
        "ambiguous_candidates": [],
        "evidence": [
            {
                "fragment_id": "FRAG-1",
                "procedure_id": "PROC-1",
                "text": "Thời hạn giải quyết là 7 ngày làm việc.",
                "score": 0.9,
                "method": "fused",
                "source_id": "SRC-1",
                "source_version": "v1",
                "effective_date": "2026-01-01",
                "source_locator": "mục 1",
                "section_type": "processing_time",
            }
        ],
        "fusion_method": "rrf",
        "created_at": "2026-09-30T00:00:00Z",
    }


def valid_output():
    claim = "Thời hạn giải quyết là 7 ngày làm việc."
    return {
        "answer_text": claim,
        "citations": [
            {
                "claim_text": claim,
                "fragment_id": "FRAG-1",
                "source_id": "SRC-1",
                "source_locator": "mục 1",
            }
        ],
    }


def test_generator_returns_person2_compatible_shape():
    runtime = StaticRuntime(json.dumps(valid_output(), ensure_ascii=False))
    generator = GroundedGenerator(runtime, max_repair_attempts=0)
    assert generator.generate(bundle()) == valid_output()
    assert len(runtime.calls) == 1


def test_rejects_citation_outside_current_bundle():
    output = valid_output()
    output["citations"][0]["fragment_id"] = "FRAG-OTHER"
    with pytest.raises(GenerationContractError, match="outside this bundle"):
        validate_generated_output(bundle(), output)


def test_rejects_claim_text_not_in_answer():
    output = valid_output()
    output["citations"][0]["claim_text"] = "không có trong answer"
    with pytest.raises(GenerationContractError, match="exact answer span"):
        validate_generated_output(bundle(), output)


def test_generator_repairs_invalid_json_once():
    class RepairRuntime:
        def __init__(self):
            self.calls = 0

        def complete(self, messages):
            from person3_generation_evaluation.runtime import RuntimeResponse

            self.calls += 1
            if self.calls == 1:
                return RuntimeResponse("not json", 1.0)
            return RuntimeResponse(json.dumps(valid_output(), ensure_ascii=False), 2.0)

    runtime = RepairRuntime()
    generator = GroundedGenerator(runtime, max_repair_attempts=1)
    output, metrics = generator.generate_with_metrics(bundle())
    assert output == valid_output()
    assert metrics.repair_attempts == 1
    assert metrics.elapsed_ms == 3.0


def test_does_not_generate_ambiguous_bundle():
    data = bundle()
    data["confidence_status"] = "ambiguous"
    data["resolved_procedure_id"] = None
    data["evidence"] = []
    with pytest.raises(GenerationContractError, match="resolved"):
        GroundedGenerator(StaticRuntime("{}")).generate(data)
