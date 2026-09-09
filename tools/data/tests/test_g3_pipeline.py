from __future__ import annotations

import json
from pathlib import Path

from openpyxl import Workbook

from g3_pipeline.builder import build_dataset, verify_deterministic
from g3_pipeline.validator import validate_dataset

HEADERS = [
    "Dấu thời gian",
    "Địa chỉ email",
    "Tên thủ tục hành chính",
    "Lĩnh vực",
    "Hình thức nộp",
    "Thành phần hồ sơ",
    "Thời gian giải quyết",
    "Lệ phí",
    "Địa điểm tiếp nhận hồ sơ trực tiếp (nếu có)",
    "Ghi chú",
    "File biểu mẫu",
    "Trạng thái",
]


def create_workbook(path: Path) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Dữ liệu mẫu"
    sheet.append(HEADERS)
    sheet.append(
        [
            "07/10/2025 08:00",
            "owner@example.test",
            "Thủ tục Mặt Trăng",
            "Hộ tịch",
            "Cả hai",
            "- Giấy tờ Alpha\n- Giấy tờ Beta",
            "3 ngày làm việc",
            "Không thu phí",
            "Bộ phận Một cửa",
            None,
            None,
            "Xong",
        ]
    )
    sheet.append(
        [
            None,
            "second@example.test",
            "Thủ tục Sao Mai",
            "Giáo dục và đào tạo",
            "Trực tuyến",
            "Giấy tờ Gamma",
            "5 ngày làm việc",
            "10.000 đồng",
            None,
            None,
            None,
            "Xong",
        ]
    )
    sheet.append(
        [
            None,
            "third@example.test",
            "Thủ tục Trùng",
            "Văn hóa - Xã hội",
            "Trực tiếp",
            "Giấy tờ Một",
            "2 ngày làm việc",
            "Không",
            "Điểm tiếp nhận A",
            None,
            None,
            "Xong",
        ]
    )
    sheet.append(
        [
            None,
            "fourth@example.test",
            "Thủ tục Trùng",
            "Văn hóa - Xã hội",
            "Trực tiếp",
            "Giấy tờ Hai",
            "4 ngày làm việc",
            "Không",
            "Điểm tiếp nhận B",
            None,
            None,
            "Xong",
        ]
    )
    sheet.append([None] * len(HEADERS))
    workbook.save(path)


def schema_path() -> Path:
    return Path(__file__).parents[3] / "docs/giai-doan-3/schema/data-contract-v1.schema.json"


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_build_is_schema_valid_private_and_deterministic(tmp_path: Path) -> None:
    workbook = tmp_path / "synthetic.xlsx"
    create_workbook(workbook)
    result = build_dataset(workbook, tmp_path / "private")

    report = validate_dataset(
        result.dataset_dir,
        schema_path(),
        mode="preflight",
        expected_source_count=4,
        workbook_path=workbook,
    )

    assert report["status"] == "PASS", report
    assert report["counts"] == {
        "sources": 4,
        "procedures": 3,
        "fragments": 19,
        "conflicts": 1,
        "questions": 9,
    }
    assert report["warnings"]["PROCEDURE_REVIEW_PENDING"] == 3
    assert report["warnings"]["GOLD_REVIEW_PENDING"] == 9
    assert "example.test" not in "".join(
        path.read_text(encoding="utf-8") for path in result.dataset_dir.rglob("*") if path.is_file()
    )
    assert verify_deterministic(workbook)


def test_review_is_never_approved_automatically(tmp_path: Path) -> None:
    workbook = tmp_path / "synthetic.xlsx"
    create_workbook(workbook)
    result = build_dataset(workbook, tmp_path / "private")
    procedures = load_jsonl(result.dataset_dir / "normalized/procedures.jsonl")
    statuses = {row["review"]["status"] for row in procedures}
    assert statuses == {"PENDING_REVIEW", "QUARANTINED"}


def test_validator_rejects_pii_in_gold(tmp_path: Path) -> None:
    workbook = tmp_path / "synthetic.xlsx"
    create_workbook(workbook)
    result = build_dataset(workbook, tmp_path / "private")
    questions_path = result.dataset_dir / "gold/questions.jsonl"
    questions = load_jsonl(questions_path)
    questions[0]["question"] += " owner@example.test"
    questions_path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in questions),
        encoding="utf-8",
        newline="\n",
    )

    report = validate_dataset(result.dataset_dir, schema_path())

    assert report["status"] == "FAIL"
    assert report["errors"]["SENSITIVE_PATTERN_EMAIL"] == 1


def test_publish_requires_human_review(tmp_path: Path) -> None:
    workbook = tmp_path / "synthetic.xlsx"
    create_workbook(workbook)
    result = build_dataset(workbook, tmp_path / "private")

    report = validate_dataset(result.dataset_dir, schema_path(), mode="publish")

    assert report["status"] == "FAIL"
    assert report["errors"]["PROCEDURE_REVIEW_PENDING"] == 3
    assert report["errors"]["GOLD_REVIEW_PENDING"] == 9
