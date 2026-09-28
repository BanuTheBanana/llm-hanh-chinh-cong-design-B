from __future__ import annotations

import json
from pathlib import Path

from g3_pipeline.g4_tu_review import review_and_lock
from g3_pipeline.g4_tu_scenarios import FIELD_SECTIONS, generate_bundle
from g3_pipeline.g4_tu_validator import validate_bundle


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
        newline="\n",
    )


def _schema_paths() -> tuple[Path, Path]:
    root = Path(__file__).parents[3]
    return (
        root / "docs/giai-doan-4/schema/g4-evaluation-scenario-v1.schema.json",
        root / "docs/giai-doan-4/schema/g4-evaluation-manifest-v1.schema.json",
    )


def _dataset(tmp_path: Path) -> Path:
    dataset = tmp_path / "fictional-demo10"
    procedures = []
    fragments = []
    for index in range(10):
        procedure_id = f"fictional_proc_{index:02d}"
        field_evidence = {}
        proc = {
            "procedure_id": procedure_id,
            "title": f"Thủ tục giả lập {index}",
            "dataset_version": "fictional-demo10-v1",
            "category_code": f"CATEGORY_{index % 4}",
        }
        values = {
            "receiving_authority": [f"Điểm tiếp nhận {index}"],
            "required_documents": [f"Giấy tờ {index}"],
            "fees": [
                {
                    "amount_vnd": index * 1000,
                    "condition": None,
                    "raw_text": f"phí giả lập mức {index}",
                }
            ],
            "processing_times": [
                {
                    "min_business_days": index + 1,
                    "max_business_days": index + 1,
                    "condition": None,
                    "raw_text": f"{index + 1} ngày làm việc",
                }
            ],
            "submission_methods": ["ONLINE"],
            "steps": [f"Bước giả lập {index}"],
        }
        for field, field_values in values.items():
            fragment_id = f"{procedure_id}:{field}:001"
            field_evidence[field] = [fragment_id]
            fragments.append(
                {
                    "fragment_id": fragment_id,
                    "procedure_id": procedure_id,
                    "section_type": FIELD_SECTIONS[field],
                }
            )
            proc[field] = field_values
        proc["field_evidence"] = field_evidence
        procedures.append(proc)
    _write_jsonl(dataset / "normalized/procedures.jsonl", procedures)
    _write_jsonl(dataset / "normalized/fragments.jsonl", fragments)
    generate_bundle(
        dataset / "normalized/procedures.jsonl",
        dataset / "g4_eval",
        generated_at="2026-09-11T00:00:00+07:00",
    )
    return dataset


def _validate(dataset: Path, mode: str = "preflight") -> dict:
    scenario_schema, manifest_schema = _schema_paths()
    return validate_bundle(
        dataset,
        scenario_schema,
        manifest_schema,
        mode=mode,
    )


def test_bundle_is_split_by_procedure_and_multiturn_ends_with_user(tmp_path: Path) -> None:
    dataset = _dataset(tmp_path)
    report = _validate(dataset)
    dev = [
        json.loads(line)
        for line in (dataset / "g4_eval/scenario_dev.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    test = [
        json.loads(line)
        for line in (dataset / "g4_eval/scenario_test_v2.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]

    assert report["status"] == "PASS", report
    assert report["counts"] == {
        "dev": 80,
        "test_v2": 40,
        "multi_turn": 36,
        "dev_procedures": 8,
        "test_v2_procedures": 2,
        "ambiguous_source_fields": 0,
    }
    assert {row["procedure_id"] for row in dev}.isdisjoint({row["procedure_id"] for row in test})
    assert all(row["turns"][-1]["role"] == "user" for row in dev + test)
    assert all(row["question"] == row["turns"][-1]["text"] for row in dev + test)


def test_validator_rejects_procedure_split_leakage(tmp_path: Path) -> None:
    dataset = _dataset(tmp_path)
    path = dataset / "g4_eval/scenario_test_v2.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    rows[0]["procedure_id"] = "fictional_proc_00"
    _write_jsonl(path, rows)

    report = _validate(dataset)

    assert report["status"] == "FAIL"
    assert report["errors"]["PROCEDURE_SPLIT_LEAKAGE"] == 1


def test_validator_rejects_multiturn_ending_with_assistant(tmp_path: Path) -> None:
    dataset = _dataset(tmp_path)
    path = dataset / "g4_eval/scenario_dev.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    row = next(item for item in rows if item["is_multiturn"])
    row["turns"].append({"role": "assistant", "text": "Tôi sẽ đối chiếu sau."})
    row["conversation_turns"] += 1
    _write_jsonl(path, rows)

    report = _validate(dataset)

    assert report["status"] == "FAIL"
    assert report["errors"]["CONVERSATION_MUST_START_END_USER"] == 1


def test_validator_rejects_pii_and_broken_fragment(tmp_path: Path) -> None:
    dataset = _dataset(tmp_path)
    path = dataset / "g4_eval/scenario_test_v2.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    rows[0]["question"] += " user@example.test"
    rows[0]["turns"][-1]["text"] = rows[0]["question"]
    rows[1]["gold_fragment_ids"] = ["missing:fragment:001"]
    rows[1]["gold_label"]["fragment_ids"] = ["missing:fragment:001"]
    _write_jsonl(path, rows)

    report = _validate(dataset)

    assert report["status"] == "FAIL"
    assert report["errors"]["SCENARIO_PII_PATTERN"] == 1
    assert report["errors"]["GOLD_FRAGMENT_REFERENCE_INVALID"] == 1


def test_final_review_locks_hashes_and_passes_publish(tmp_path: Path) -> None:
    dataset = _dataset(tmp_path)
    scenario_schema, manifest_schema = _schema_paths()

    report = review_and_lock(
        dataset,
        scenario_schema,
        manifest_schema,
        reviewer_role="PROJECT_LEADER_DELEGATED_REVIEW",
        reviewed_at="2026-09-11T12:00:00+07:00",
    )
    manifest = json.loads((dataset / "g4_eval/scenario_manifest.json").read_text(encoding="utf-8"))

    assert report["status"] == "PASS", report
    assert manifest["review_status"] == "LOCKED"
    assert manifest["test_v2_lock"]["status"] == "LOCKED"
    assert _validate(dataset, mode="publish")["status"] == "PASS"
