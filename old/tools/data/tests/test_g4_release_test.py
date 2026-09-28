from __future__ import annotations

import json
from pathlib import Path

from g3_pipeline.g4_release_test import prepare_and_lock, validate_release_test
from g3_pipeline.g4_tu_validator import FIELD_SECTIONS


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
        newline="\n",
    )


def _schemas() -> tuple[Path, Path]:
    root = Path(__file__).parents[3]
    return (
        root / "docs/giai-doan-4/schema/g4-evaluation-scenario-v1.schema.json",
        root / "docs/giai-doan-4/schema/g4-release-test-manifest-v1.schema.json",
    )


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    dataset = tmp_path / "fictional-demo10"
    input_path = tmp_path / "incoming.jsonl"
    prior_path = tmp_path / "prior.jsonl"
    procedures, fragments, incoming, prior = [], [], [], []
    fields = list(FIELD_SECTIONS)[:4]
    for index in range(10):
        procedure_id = f"fictional-procedure-{index}"
        procedure = {
            "procedure_id": procedure_id,
            "title": f"Thủ tục giả lập {index}",
            "dataset_version": "fictional-demo10-v1",
            "field_evidence": {},
        }
        for field in fields:
            fragment_id = f"{procedure_id}:{field}:001"
            value = f"Giá trị giả lập {field} {index}"
            procedure[field] = [value]
            procedure["field_evidence"][field] = [fragment_id]
            fragments.append(
                {
                    "fragment_id": fragment_id,
                    "procedure_id": procedure_id,
                    "section_type": FIELD_SECTIONS[field],
                }
            )
            incoming.append(
                {
                    "scenario_id": f"v3-{index}-{field}",
                    "scenario_group_id": f"v3-group-{index}-{field}",
                    "procedure_id": procedure_id,
                    "field_expected": field,
                    "question": f"Câu đầu chưa phải đích {index} {field}",
                    "expected_status": "INSUFFICIENT_DATA",
                    "gold_fragment_ids": [],
                    "gold_label": {},
                    "gold_answer": [],
                    "must_include": [],
                    "must_exclude": [],
                    "turns": [
                        {"role": "user", "text": f"Tôi hỏi thủ tục giả lập số {index}."},
                        {"role": "assistant", "text": "Bạn muốn hỏi thông tin nào?"},
                        {
                            "role": "user",
                            "text": f"Cho tôi thông tin mục {field} của hồ sơ số {index}.",
                        },
                    ],
                }
            )
            prior.append(
                {
                    "procedure_id": procedure_id,
                    "field_expected": field,
                    "question": f"Câu DEV khác {index} {field}",
                    "turns": [{"role": "user", "text": f"Câu DEV khác {index} {field}"}],
                    "review": {
                        "status": "APPROVED",
                        "decision": "APPROVED_AGAINST_NORMALIZED_SOURCE",
                        "flags": [],
                    },
                }
            )
        procedures.append(procedure)
    _write_jsonl(dataset / "normalized/procedures.jsonl", procedures)
    _write_jsonl(dataset / "normalized/fragments.jsonl", fragments)
    _write_jsonl(input_path, incoming)
    _write_jsonl(prior_path, prior)
    return dataset, input_path, prior_path


def test_prepare_lock_repairs_labels_and_target_turn(tmp_path: Path) -> None:
    dataset, input_path, prior_path = _fixture(tmp_path)
    scenario_schema, manifest_schema = _schemas()
    output = tmp_path / "reviewed"

    report = prepare_and_lock(
        input_path,
        output,
        dataset,
        [prior_path],
        scenario_schema,
        manifest_schema,
        reviewer_role="PROJECT_LEADER_DELEGATED_REVIEW",
        reviewed_at="2026-09-11T10:00:00+00:00",
        generated_at="2026-09-11T09:00:00+00:00",
    )
    rows = [
        json.loads(line)
        for line in (output / "scenario_test_v3.jsonl").read_text(encoding="utf-8").splitlines()
    ]

    assert report["status"] == "PASS", report
    assert report["counts"]["scenarios"] == 40
    assert all(row["question"] == row["turns"][2]["text"] for row in rows)
    assert all(row["expected_status"] == "ANSWER" for row in rows)
    assert all(row["gold_fragment_ids"] for row in rows)
    assert all(row["review"]["status"] == "APPROVED" for row in rows)


def test_validator_rejects_question_reused_from_prior(tmp_path: Path) -> None:
    dataset, input_path, prior_path = _fixture(tmp_path)
    scenario_schema, manifest_schema = _schemas()
    output = tmp_path / "reviewed"
    prepare_and_lock(
        input_path,
        output,
        dataset,
        [prior_path],
        scenario_schema,
        manifest_schema,
        reviewer_role="PROJECT_LEADER_DELEGATED_REVIEW",
        reviewed_at="2026-09-11T10:00:00+00:00",
        generated_at="2026-09-11T09:00:00+00:00",
    )
    rows = [
        json.loads(line)
        for line in (output / "scenario_test_v3.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    prior = json.loads(prior_path.read_text(encoding="utf-8").splitlines()[0])
    rows[0]["question"] = prior["question"]
    rows[0]["turns"][-1]["text"] = prior["question"]
    _write_jsonl(output / "scenario_test_v3.jsonl", rows)

    report = validate_release_test(output, dataset, [prior_path], scenario_schema, manifest_schema)

    assert report["status"] == "FAIL"
    assert report["errors"]["PRIVATE_TEST_EXACT_QUESTION_LEAKAGE"] == 1
