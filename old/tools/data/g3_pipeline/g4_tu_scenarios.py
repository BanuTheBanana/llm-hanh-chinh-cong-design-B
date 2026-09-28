#!/usr/bin/env python3
"""Build a deterministic, private G4 DEV/TEST_V2 evaluation bundle.

The source procedures and generated scenarios are D2 private data. This module
must only be run locally and never prints questions, answers or source text.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

FIELD_ORDER = (
    "receiving_authority",
    "required_documents",
    "fees",
    "processing_times",
    "submission_methods",
    "steps",
)

FIELD_LABELS = {
    "receiving_authority": "nơi tiếp nhận hồ sơ",
    "required_documents": "thành phần hồ sơ",
    "fees": "lệ phí",
    "processing_times": "thời gian giải quyết",
    "submission_methods": "hình thức nộp",
    "steps": "các bước thực hiện",
}

FIELD_CODES = {
    "receiving_authority": "RA",
    "required_documents": "DOC",
    "fees": "FEE",
    "processing_times": "TIME",
    "submission_methods": "METHOD",
    "steps": "STEPS",
}

FIELD_SECTIONS = {
    "receiving_authority": "RECEIVING_AUTHORITY",
    "required_documents": "REQUIRED_DOCUMENTS",
    "fees": "FEES",
    "processing_times": "PROCESSING_TIME",
    "submission_methods": "SUBMISSION_METHODS",
    "steps": "STEPS",
}

SINGLE_QUESTIONS = {
    "receiving_authority": (
        "Thủ tục {title} tiếp nhận hồ sơ tại đâu?",
        "Tôi phải đến cơ quan nào để nộp hồ sơ cho thủ tục {title}?",
        "Nguồn ghi nơi tiếp nhận của thủ tục {title} là đâu?",
    ),
    "required_documents": (
        "Thủ tục {title} cần chuẩn bị những giấy tờ nào?",
        "Hồ sơ của thủ tục {title} gồm những thành phần gì?",
        "Theo nguồn, tôi cần mang gì khi làm thủ tục {title}?",
    ),
    "fees": (
        "Thủ tục {title} có lệ phí như thế nào?",
        "Theo nguồn, mức phí của thủ tục {title} là bao nhiêu?",
        "Làm thủ tục {title} có thu phí không và điều kiện là gì?",
    ),
    "processing_times": (
        "Thủ tục {title} được giải quyết trong bao lâu?",
        "Thời gian xử lý thủ tục {title} theo nguồn là bao nhiêu?",
        "Tôi cần chờ mấy ngày khi làm thủ tục {title}?",
    ),
    "submission_methods": (
        "Thủ tục {title} có thể nộp bằng những hình thức nào?",
        "Tôi có thể nộp trực tuyến hay phải đến trực tiếp để làm thủ tục {title}?",
        "Nguồn quy định cách nộp thủ tục {title} như thế nào?",
    ),
    "steps": (
        "Các bước thực hiện thủ tục {title} là gì?",
        "Nguồn có nêu trình tự xử lý thủ tục {title} không?",
        "Tôi cần làm lần lượt những bước nào cho thủ tục {title}?",
    ),
}

FOLLOW_UP_QUESTIONS = {
    "receiving_authority": (
        "Vậy hồ sơ này được tiếp nhận ở đâu?",
        "Còn cơ quan tiếp nhận của thủ tục vừa nói là cơ quan nào?",
        "Trong trường hợp này tôi phải đến đâu nộp hồ sơ?",
    ),
    "required_documents": (
        "Vậy tôi cần chuẩn bị những giấy tờ nào?",
        "Còn thành phần hồ sơ của thủ tục vừa nói gồm những gì?",
        "Đối với trường hợp này, tôi phải mang theo giấy tờ gì?",
    ),
    "fees": (
        "Vậy thủ tục này có mất lệ phí không?",
        "Còn mức phí của trường hợp vừa nói là bao nhiêu?",
        "Nguồn có quy định khoản phí nào cho thủ tục này không?",
    ),
    "processing_times": (
        "Vậy thủ tục này được giải quyết trong bao lâu?",
        "Còn thời gian xử lý của trường hợp vừa nói là mấy ngày?",
        "Theo nguồn thì tôi cần chờ bao lâu?",
    ),
    "submission_methods": (
        "Vậy tôi có thể nộp hồ sơ bằng hình thức nào?",
        "Còn cách nộp của thủ tục vừa nói thì sao?",
        "Trường hợp này cho phép nộp trực tuyến hay trực tiếp?",
    ),
    "steps": (
        "Vậy các bước tiếp theo của thủ tục này là gì?",
        "Còn trình tự thực hiện của trường hợp vừa nói thì sao?",
        "Nguồn có nêu các bước phải làm không?",
    ),
}

UNSUPPORTED_CLAIMS = (
    "thông tin không có trong fragment được phép",
    "điều kiện do hệ thống tự suy diễn",
)


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
        newline="\n",
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _values(proc: dict[str, Any], field: str) -> list[Any]:
    value = proc.get(field)
    return list(value) if isinstance(value, list) else []


def _expected_points(proc: dict[str, Any], field: str) -> list[str]:
    points: list[str] = []
    for item in _values(proc, field):
        if isinstance(item, str) and item.strip():
            points.append(item.strip())
        elif isinstance(item, dict):
            raw_text = item.get("raw_text")
            if isinstance(raw_text, str) and raw_text.strip():
                points.append(raw_text.strip())
    return list(dict.fromkeys(points))


def _evidence_ids(proc: dict[str, Any], field: str) -> list[str]:
    ids = proc.get("field_evidence", {}).get(field, [])
    if not isinstance(ids, list):
        return []
    return list(dict.fromkeys(item for item in ids if isinstance(item, str) and item))


def _ambiguity_flags(proc: dict[str, Any], field: str) -> list[str]:
    if field not in {"fees", "processing_times"}:
        return []
    raw = " ".join(
        str(item.get("raw_text", "")) for item in _values(proc, field) if isinstance(item, dict)
    ).casefold()
    markers = ("không quy định", "0.0", "05", "3–5", "điều kiện")
    if any(marker in raw for marker in markers):
        return ["AMBIGUOUS_FEE_SOURCE" if field == "fees" else "AMBIGUOUS_PROCESSING_TIME_SOURCE"]
    return []


def _requires_abstention(proc: dict[str, Any], field: str) -> bool:
    raw_values = {
        str(item.get("raw_text", "")).strip().casefold()
        for item in _values(proc, field)
        if isinstance(item, dict)
    }
    return bool(raw_values & {"0.0", "05"})


def expected_status(proc: dict[str, Any], field: str) -> str:
    values = _values(proc, field)
    evidence = _evidence_ids(proc, field)
    if not values or not evidence or _requires_abstention(proc, field):
        return "INSUFFICIENT_DATA"
    return "ANSWER"


def _prior_assistant_text(proc: dict[str, Any], field: str) -> str:
    points = _expected_points(proc, field)
    if not points:
        return f"Nguồn hiện chưa có đủ căn cứ về {FIELD_LABELS[field]}."
    return f"Theo dữ liệu đã duyệt về {FIELD_LABELS[field]}: " + "; ".join(points)


def _scenario(
    proc: dict[str, Any],
    *,
    split: str,
    scenario_number: int,
    field: str,
    variant: int,
    prior_field: str | None = None,
) -> dict[str, Any]:
    procedure_id = str(proc["procedure_id"])
    title = str(proc["title"])
    values = _values(proc, field)
    fragment_ids = _evidence_ids(proc, field)
    status = expected_status(proc, field)
    points = _expected_points(proc, field) if status == "ANSWER" else ["chưa đủ căn cứ"]
    flags = _ambiguity_flags(proc, field)

    if prior_field is None:
        question = SINGLE_QUESTIONS[field][variant % len(SINGLE_QUESTIONS[field])].format(
            title=title
        )
        turns = [{"role": "user", "text": question}]
        context_kind = "SINGLE"
    else:
        first_question = SINGLE_QUESTIONS[prior_field][
            (variant + 1) % len(SINGLE_QUESTIONS[prior_field])
        ].format(title=title)
        question = FOLLOW_UP_QUESTIONS[field][variant % len(FOLLOW_UP_QUESTIONS[field])]
        turns = [
            {"role": "user", "text": first_question},
            {"role": "assistant", "text": _prior_assistant_text(proc, prior_field)},
            {"role": "user", "text": question},
        ]
        context_kind = "FOLLOW_UP"

    scenario_id = f"g4-{split.lower()}-{scenario_number:03d}"
    return {
        "scenario_version": "g4-eval-scenario-v1",
        "scenario_id": scenario_id,
        "dataset_version": str(proc["dataset_version"]),
        "split": split,
        "scenario_group_id": (f"G4-{FIELD_CODES[field]}-{procedure_id}-{context_kind}"),
        "procedure_id": procedure_id,
        "procedure_title": title,
        "field_expected": field,
        "question": question,
        "expected_status": status,
        "gold_fragment_ids": fragment_ids if status == "ANSWER" else [],
        "gold_label": {
            "status": status,
            "procedure_id": procedure_id,
            "field": field,
            "fragment_ids": fragment_ids if status == "ANSWER" else [],
        },
        "gold_answer": values if status == "ANSWER" else [],
        "expected_points": points,
        "must_include": points,
        "must_exclude": list(UNSUPPORTED_CLAIMS),
        "is_multiturn": prior_field is not None,
        "conversation_turns": len(turns),
        "turns": turns,
        "contains_pii": False,
        "review": {
            "author_role": "DATA_OWNER_TU",
            "status": "PENDING_REVIEW",
            "reviewer_role": None,
            "reviewed_at": None,
            "decision": None,
            "flags": flags,
        },
    }


def _build_dev(procedures: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    number = 1
    for proc_index, proc in enumerate(procedures):
        for field_index, field in enumerate(FIELD_ORDER):
            rows.append(
                _scenario(
                    proc,
                    split="DEV",
                    scenario_number=number,
                    field=field,
                    variant=proc_index + field_index,
                )
            )
            number += 1
        for field, prior_field in (
            ("fees", "required_documents"),
            ("processing_times", "receiving_authority"),
        ):
            rows.append(
                _scenario(
                    proc,
                    split="DEV",
                    scenario_number=number,
                    field=field,
                    variant=proc_index,
                    prior_field=prior_field,
                )
            )
            number += 1
        for field in ("receiving_authority", "required_documents"):
            rows.append(
                _scenario(
                    proc,
                    split="DEV",
                    scenario_number=number,
                    field=field,
                    variant=proc_index + 1,
                )
            )
            number += 1
    return rows


def _build_test(procedures: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    number = 1
    targets = (
        *FIELD_ORDER,
        "receiving_authority",
        "required_documents",
        "fees",
        "processing_times",
    )
    priors = (
        "required_documents",
        "receiving_authority",
        "required_documents",
        "fees",
        "receiving_authority",
        "submission_methods",
        "fees",
        "processing_times",
        "steps",
        "submission_methods",
    )
    for proc_index, proc in enumerate(procedures):
        for variant, field in enumerate(targets):
            rows.append(
                _scenario(
                    proc,
                    split="TEST_V2",
                    scenario_number=number,
                    field=field,
                    variant=variant + proc_index,
                )
            )
            number += 1
        for variant, (field, prior_field) in enumerate(zip(targets, priors, strict=True)):
            rows.append(
                _scenario(
                    proc,
                    split="TEST_V2",
                    scenario_number=number,
                    field=field,
                    variant=variant + proc_index,
                    prior_field=prior_field,
                )
            )
            number += 1
    return rows


def generate_bundle(
    procedures_path: Path,
    output_dir: Path,
    *,
    generated_at: str,
) -> dict[str, Any]:
    procedures = _load_jsonl(procedures_path)
    if len(procedures) != 10:
        raise ValueError("DEMO10_PROCEDURES_REQUIRED")
    versions = {row.get("dataset_version") for row in procedures}
    if len(versions) != 1 or not next(iter(versions)):
        raise ValueError("ONE_DATASET_VERSION_REQUIRED")
    procedure_ids = [row.get("procedure_id") for row in procedures]
    if len(procedure_ids) != len(set(procedure_ids)) or any(not item for item in procedure_ids):
        raise ValueError("UNIQUE_PROCEDURE_IDS_REQUIRED")

    dev_procedures = procedures[:8]
    test_procedures = procedures[8:]
    dev = _build_dev(dev_procedures)
    test_v2 = _build_test(test_procedures)
    if len(dev) != 80 or len(test_v2) != 40:
        raise AssertionError("G4_SCENARIO_COUNTS")

    output_dir.mkdir(parents=True, exist_ok=True)
    dev_path = output_dir / "scenario_dev.jsonl"
    test_path = output_dir / "scenario_test_v2.jsonl"
    _write_jsonl(dev_path, dev)
    _write_jsonl(test_path, test_v2)

    ambiguous_pairs = {
        (row["procedure_id"], row["field_expected"])
        for row in dev + test_v2
        if row["review"]["flags"]
    }
    categories_dev = {row.get("category_code") for row in dev_procedures}
    categories_test = {row.get("category_code") for row in test_procedures}
    manifest = {
        "schema_version": "g4-eval-manifest-v1",
        "dataset_version": next(iter(versions)),
        "scenario_set": "G4-01-evaluation-v4",
        "generated_at": generated_at,
        "author_role": "DATA_OWNER_TU",
        "reviewer_role": None,
        "reviewed_at": None,
        "review_status": "PENDING_REVIEW",
        "split_strategy": "PROCEDURE_ID_HOLDOUT",
        "schema_file": "docs/giai-doan-4/schema/g4-evaluation-scenario-v1.schema.json",
        "procedure_count": 10,
        "dev_count": len(dev),
        "test_v2_count": len(test_v2),
        "multi_turn_count": sum(row["is_multiturn"] for row in dev + test_v2),
        "ambiguous_source_field_count": len(ambiguous_pairs),
        "category_overlap_count": len(categories_dev & categories_test),
        "dev_procedure_ids": [str(row["procedure_id"]) for row in dev_procedures],
        "test_v2_procedure_ids": [str(row["procedure_id"]) for row in test_procedures],
        "files": {
            "dev": "g4_eval/scenario_dev.jsonl",
            "test_v2": "g4_eval/scenario_test_v2.jsonl",
        },
        "sha256": {"dev": _sha256(dev_path), "test_v2": _sha256(test_path)},
        "test_v2_lock": {
            "status": "PENDING_REVIEW",
            "recipient": "Hoan only",
            "do_not_use_for": [
                "prompt_tuning",
                "retrieval_tuning",
                "model_tuning",
                "serving_index",
            ],
        },
    }
    (output_dir / "scenario_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--procedures", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--generated-at", default="2026-09-11T00:00:00+07:00")
    args = parser.parse_args()
    try:
        manifest = generate_bundle(
            args.procedures.resolve(),
            args.output_dir.resolve(),
            generated_at=args.generated_at,
        )
    except Exception:
        print('{"status":"FAIL","error":"G4_BUNDLE_GENERATION_FAILED"}')
        return 2
    print(
        json.dumps(
            {
                "status": "GENERATED_PENDING_REVIEW",
                "dev_count": manifest["dev_count"],
                "test_v2_count": manifest["test_v2_count"],
                "multi_turn_count": manifest["multi_turn_count"],
                "ambiguous_source_field_count": manifest["ambiguous_source_field_count"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
