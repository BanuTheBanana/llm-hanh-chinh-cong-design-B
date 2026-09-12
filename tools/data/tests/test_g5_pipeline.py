import hashlib
import json

from g3_pipeline.common import write_jsonl
from g5_pipeline.scope import audit_scope
from g5_pipeline.sft import build_sft_bundle, validate_sft_bundle


def _record(record_type, dataset_version, **values):
    return {
        "record_type": record_type,
        "schema_version": "g3-data-v1",
        "dataset_version": dataset_version,
        "data_classification": "D2_COMPANY_REAL",
        **values,
    }


def _fixture(tmp_path):
    version = "private-fixture-v1"
    dataset = tmp_path / "dataset"
    sources, procedures, fragments, scenarios = [], [], [], []
    for index in range(3):
        source_id = f"source-{index}"
        procedure_id = f"procedure-{index}"
        fragment_id = f"fragment-{index}"
        text = f"Giấy tờ mẫu {index}."
        sources.append(
            _record(
                "source_manifest",
                version,
                source_id=source_id,
                jurisdiction={"country_code": "VN", "province": "Thành phố mẫu"},
                effective_from="2026-01-01",
                effective_to=None,
                validity_status="CURRENT",
                review={"status": "APPROVED_FOR_DEMO"},
            )
        )
        fragments.append(
            _record(
                "procedure_fragment",
                version,
                fragment_id=fragment_id,
                source_id=source_id,
                procedure_id=procedure_id,
                section_type="REQUIRED_DOCUMENTS",
                text=text,
            )
        )
        procedures.append(
            _record(
                "procedure",
                version,
                procedure_id=procedure_id,
                title=f"Thủ tục mẫu {index}",
                category_code="FIXTURE",
                source_ids=[source_id],
                required_documents=[text],
                applicant_scope=[],
                receiving_authority=[],
                submission_methods=[],
                steps=[],
                fees=[],
                processing_times=[],
                legal_bases=[],
                missing_fields=[
                    "applicant_scope",
                    "receiving_authority",
                    "submission_methods",
                    "steps",
                    "fees",
                    "processing_times",
                    "legal_bases",
                ],
                field_evidence={
                    "applicant_scope": [],
                    "receiving_authority": [],
                    "submission_methods": [],
                    "required_documents": [fragment_id],
                    "steps": [],
                    "fees": [],
                    "processing_times": [],
                    "legal_bases": [],
                },
                review={"status": "APPROVED_FOR_DEMO"},
            )
        )
        scenarios.append(
            {
                "scenario_id": f"scenario-{index}",
                "dataset_version": version,
                "split": "DEV",
                "procedure_id": procedure_id,
                "field_expected": "required_documents",
                "question": f"Thủ tục mẫu {index} cần giấy tờ gì?",
                "expected_status": "ANSWER",
                "gold_fragment_ids": [fragment_id],
                "contains_pii": False,
                "review": {"status": "APPROVED", "reviewer_role": "LEADER"},
            }
        )
    write_jsonl(dataset / "source_manifest.jsonl", sources, "source_id")
    write_jsonl(dataset / "normalized/procedures.jsonl", procedures, "procedure_id")
    write_jsonl(dataset / "normalized/fragments.jsonl", fragments, "fragment_id")
    write_jsonl(dataset / "quarantine/conflicts.jsonl", [], "conflict_id")
    dev = tmp_path / "scenario_dev.jsonl"
    write_jsonl(dev, scenarios, "scenario_id")
    return dataset, dev


def test_scope_and_sft_use_reviewed_dev_with_disjoint_procedures(tmp_path):
    dataset, dev = _fixture(tmp_path)
    scope = audit_scope(dataset)
    assert scope["counts"]["serving_eligible"] == 3
    assert scope["field_coverage"]["required_documents"] == 3

    output = tmp_path / "bundle"
    manifest = build_sft_bundle(dataset, dev, output, variants=2)
    assert manifest["test_data_used"] is False
    assert manifest["rendered_examples"] == {"TRAIN": 4, "VALIDATION": 2}
    assert validate_sft_bundle(output)["status"] == "PASS"


def test_sft_validator_detects_cross_split_leakage(tmp_path):
    dataset, dev = _fixture(tmp_path)
    output = tmp_path / "bundle"
    build_sft_bundle(dataset, dev, output, variants=1)
    training_row = json.loads((output / "train.jsonl").read_text(encoding="utf-8").splitlines()[0])
    validation_path = output / "validation.jsonl"
    with validation_path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps({**training_row, "split": "VALIDATION"}, ensure_ascii=False))
        stream.write("\n")
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    manifest["files"]["validation"]["sha256"] = hashlib.sha256(
        validation_path.read_bytes()
    ).hexdigest()
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
    )
    report = validate_sft_bundle(output)
    assert report["errors"]["PROCEDURE_SPLIT_LEAKAGE"] == 1
