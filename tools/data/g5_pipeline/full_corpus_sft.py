"""Build and validate a procedure-disjoint SFT bundle from a controlled corpus release."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from g3_pipeline.common import file_sha256, write_json, write_jsonl

from . import SFT_MANIFEST_VERSION, SFT_SCHEMA_VERSION
from .sft import _evidence, _target, validate_sft_bundle

ROOT = Path(__file__).resolve().parents[3]
FIELDS = (
    "receiving_authority",
    "submission_methods",
    "required_documents",
    "fees",
    "processing_times",
    "steps",
    "legal_bases",
    "applicant_scope",
)
FIELD_TEMPLATES = {
    "receiving_authority": (
        "{title} được nộp tại cơ quan nào?",
        "Cho tôi biết nơi tiếp nhận hồ sơ của {title}.",
    ),
    "submission_methods": (
        "Có thể nộp {title} bằng những cách nào?",
        "Hình thức nộp hồ sơ cho {title} gồm những gì?",
    ),
    "required_documents": (
        "{title} cần chuẩn bị những giấy tờ nào?",
        "Thành phần hồ sơ của {title} gồm những gì?",
    ),
    "fees": (
        "Thực hiện {title} có mất lệ phí không?",
        "Lệ phí của {title} được quy định thế nào?",
    ),
    "processing_times": (
        "{title} mất bao lâu để giải quyết?",
        "Thời gian xử lý {title} là bao nhiêu?",
    ),
    "steps": (
        "Trình tự thực hiện {title} gồm những bước nào?",
        "Tôi cần làm lần lượt những gì để thực hiện {title}?",
    ),
    "legal_bases": (
        "{title} dựa trên những căn cứ pháp lý nào?",
        "Văn bản nào là căn cứ của {title}?",
    ),
    "applicant_scope": (
        "Ai thuộc đối tượng được thực hiện {title}?",
        "Phạm vi người được làm {title} được quy định thế nào?",
    ),
}


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("JSON_OBJECT_REQUIRED")
    return value


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    if any(not isinstance(row, dict) for row in rows):
        raise ValueError("JSONL_OBJECT_REQUIRED")
    return rows


def _stable_rank(seed: int, phase: str, value: str) -> str:
    return hashlib.sha256(f"{seed}:{phase}:{value}".encode()).hexdigest()


def _features(procedure_id: str, decisions: dict[tuple[str, str], dict[str, Any]]) -> set[str]:
    return {f"{field}:{decisions[(procedure_id, field)]['decision_status']}" for field in FIELDS}


def _select_holdout(
    candidates: set[str],
    decisions: dict[tuple[str, str], dict[str, Any]],
    size: int,
    *,
    seed: int,
    phase: str,
) -> set[str]:
    selected: set[str] = set()
    covered: set[str] = set()
    feature_frequency = Counter(
        feature for procedure_id in candidates for feature in _features(procedure_id, decisions)
    )
    while len(selected) < size:
        remaining = candidates - selected
        if not remaining:
            raise ValueError("FULL_SFT_SPLIT_TOO_SMALL")

        def score(procedure_id: str) -> tuple[float, str]:
            features = _features(procedure_id, decisions)
            new_features = features - covered
            rarity = sum(1 / feature_frequency[item] for item in new_features)
            return (len(new_features) * 100 + rarity, _stable_rank(seed, phase, procedure_id))

        chosen = max(remaining, key=score)
        selected.add(chosen)
        covered.update(_features(chosen, decisions))
    return selected


def _normalized_question(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", value.casefold())).strip()


def _validate_release(
    release: Path,
) -> tuple[
    dict[str, Any],
    dict[str, dict[str, Any]],
    dict[str, dict[str, Any]],
    dict[str, dict[str, Any]],
    dict[tuple[str, str], dict[str, Any]],
]:
    manifest = _load_json(release / "release-manifest.json")
    if (
        manifest.get("status") != "READY_FOR_CONTROLLED_RAG"
        or manifest.get("usage_policy") != "ALLOWLISTED_FIELDS_ONLY"
    ):
        raise ValueError("FULL_SFT_RELEASE_NOT_READY")
    for artifact in manifest.get("artifacts", []):
        path = (release / artifact["path"]).resolve()
        if not path.is_relative_to(release.resolve()) or file_sha256(path) != artifact["sha256"]:
            raise ValueError("FULL_SFT_RELEASE_HASH_MISMATCH")
    sources = {row["source_id"]: row for row in _load_jsonl(release / "source_manifest.jsonl")}
    procedures = {
        row["procedure_id"]: row for row in _load_jsonl(release / "normalized/procedures.jsonl")
    }
    fragments = {
        row["fragment_id"]: row for row in _load_jsonl(release / "normalized/fragments.jsonl")
    }
    decisions_list = _load_jsonl(release / "field-decisions.jsonl")
    decisions = {
        (row["procedure_id"], row["field"]): row
        for row in decisions_list
        if row["procedure_id"] in procedures
    }
    expected_keys = {(procedure_id, field) for procedure_id in procedures for field in FIELDS}
    if set(decisions) != expected_keys or len(decisions) != len(expected_keys):
        raise ValueError("FULL_SFT_FIELD_DECISION_MATRIX_INVALID")
    version = manifest.get("dataset_version")
    if any(
        row.get("dataset_version") != version
        for row in [*sources.values(), *procedures.values(), *fragments.values()]
    ):
        raise ValueError("FULL_SFT_RELEASE_VERSION_MISMATCH")
    for (procedure_id, _), decision in decisions.items():
        approved = decision.get("decision_status") == "APPROVED"
        fragment_ids = decision.get("fragment_ids", [])
        if approved == (not fragment_ids):
            raise ValueError("FULL_SFT_DECISION_EVIDENCE_INVALID")
        if any(
            fragment_id not in fragments
            or fragments[fragment_id].get("procedure_id") != procedure_id
            for fragment_id in fragment_ids
        ):
            raise ValueError("FULL_SFT_DECISION_REFERENCE_INVALID")
    return manifest, sources, procedures, fragments, decisions


def _render_row(
    *,
    dataset_version: str,
    procedure: dict[str, Any],
    field: str,
    decision: dict[str, Any],
    sources: dict[str, dict[str, Any]],
    fragments: dict[str, dict[str, Any]],
    split: str,
    variant: int,
) -> dict[str, Any]:
    procedure_id = procedure["procedure_id"]
    gold_ids = decision.get("fragment_ids", [])
    approved = decision["decision_status"] == "APPROVED"
    same_procedure = [row for row in fragments.values() if row["procedure_id"] == procedure_id]
    gold = [fragments[fragment_id] for fragment_id in gold_ids]
    distractors = [row for row in same_procedure if row["fragment_id"] not in set(gold_ids)]
    if distractors:
        offset = variant % len(distractors)
        distractors = distractors[offset:] + distractors[:offset]
    selected = [*gold, *distractors[: max(0, 5 - len(gold))]]
    evidence = [_evidence(row, sources[row["source_id"]], procedure["title"]) for row in selected]
    if approved:
        target = _target([row for row in evidence if row["fragment_id"] in set(gold_ids)])
        expected_status = "ANSWER"
    else:
        target = {
            "answer": "Nguồn nội bộ đã duyệt chưa cung cấp đủ thông tin này.",
            "cited_fragment_ids": [],
            "missing_information": [field],
            "status": "INSUFFICIENT_DATA",
        }
        expected_status = "INSUFFICIENT_DATA"
    template = FIELD_TEMPLATES[field][variant % len(FIELD_TEMPLATES[field])]
    base_id = f"full:{procedure_id}:{field}"
    return {
        "base_scenario_id": base_id,
        "dataset_version": dataset_version,
        "decision_status": decision["decision_status"],
        "evidence": evidence,
        "example_id": f"{base_id}:v{variant + 1}",
        "expected_status": expected_status,
        "field": field,
        "procedure_id": procedure_id,
        "query": template.format(title=procedure["title"]),
        "review": {
            "reviewer_role": "PROJECT_OWNER_DELEGATED_REVIEW",
            "source": "CONTROLLED_FULL_CORPUS_FIELD_DECISION",
            "status": "APPROVED",
        },
        "schema_version": SFT_SCHEMA_VERSION,
        "split": split,
        "target": target,
    }


def build_full_sft(
    release: Path,
    training_output: Path,
    test_output: Path,
    *,
    train_variants: int = 2,
    validation_procedures: int = 5,
    test_procedures: int = 5,
    seed: int = 42,
) -> dict[str, Any]:
    if not 1 <= train_variants <= len(next(iter(FIELD_TEMPLATES.values()))):
        raise ValueError("FULL_SFT_TRAIN_VARIANTS_INVALID")
    allowed_training_root = (ROOT / "training/output").resolve()
    training_output = training_output.resolve()
    test_output = test_output.resolve()
    if not training_output.is_relative_to(allowed_training_root):
        raise ValueError("FULL_SFT_PRIVATE_TRAINING_OUTPUT_REQUIRED")
    if training_output.exists() or test_output.exists():
        raise FileExistsError("FULL_SFT_REFUSES_TO_OVERWRITE")
    if test_output.is_relative_to(allowed_training_root) or not any(
        "private" in part.casefold() for part in test_output.parts
    ):
        raise ValueError("FULL_SFT_SEPARATE_PRIVATE_TEST_OUTPUT_REQUIRED")

    release_manifest, sources, procedures, fragments, decisions = _validate_release(release)
    procedure_ids = set(procedures)
    if len(procedure_ids) <= validation_procedures + test_procedures:
        raise ValueError("FULL_SFT_SPLIT_TOO_SMALL")
    test_ids = _select_holdout(procedure_ids, decisions, test_procedures, seed=seed, phase="TEST")
    validation_ids = _select_holdout(
        procedure_ids - test_ids,
        decisions,
        validation_procedures,
        seed=seed,
        phase="VALIDATION",
    )
    train_ids = procedure_ids - test_ids - validation_ids
    split_ids = {"TRAIN": train_ids, "VALIDATION": validation_ids, "TEST": test_ids}
    dataset_version = release_manifest["dataset_version"]

    rows: dict[str, list[dict[str, Any]]] = {name: [] for name in split_ids}
    for split, ids in split_ids.items():
        variants = train_variants if split == "TRAIN" else 1
        for procedure_id in sorted(ids):
            for field in FIELDS:
                for variant in range(variants):
                    rows[split].append(
                        _render_row(
                            dataset_version=dataset_version,
                            procedure=procedures[procedure_id],
                            field=field,
                            decision=decisions[(procedure_id, field)],
                            sources=sources,
                            fragments=fragments,
                            split=split,
                            variant=variant,
                        )
                    )

    training_output.mkdir(parents=True)
    train_path = training_output / "train.jsonl"
    validation_path = training_output / "validation.jsonl"
    write_jsonl(train_path, rows["TRAIN"], "example_id")
    write_jsonl(validation_path, rows["VALIDATION"], "example_id")
    corpus_fingerprint = file_sha256(release / "release-manifest.json")
    training_manifest = {
        "base_scenarios": {
            "TRAIN": len(train_ids) * len(FIELDS),
            "VALIDATION": len(validation_ids) * len(FIELDS),
        },
        "dataset_version": dataset_version,
        "files": {
            "train": {"path": "train.jsonl", "sha256": file_sha256(train_path)},
            "validation": {
                "path": "validation.jsonl",
                "sha256": file_sha256(validation_path),
            },
        },
        "field_decisions_sha256": file_sha256(release / "field-decisions.jsonl"),
        "independence_note": (
            "Procedure-disjoint; TEST is stored separately and never opened by trainer."
        ),
        "procedure_count": {
            "TRAIN": len(train_ids),
            "VALIDATION": len(validation_ids),
        },
        "release_status": "READY_FOR_QLORA",
        "rendered_examples": {
            "TRAIN": len(rows["TRAIN"]),
            "VALIDATION": len(rows["VALIDATION"]),
        },
        "rendered_variants_per_base_scenario": train_variants,
        "recommended_max_length": 2304,
        "schema_version": SFT_MANIFEST_VERSION,
        "seed": seed,
        "source_corpus_sha256": corpus_fingerprint,
        "split_strategy": (
            "PROCEDURE_DISJOINT_FEATURE_BALANCED_"
            f"{len(train_ids)}_{len(validation_ids)}_{len(test_ids)}"
        ),
        "test_data_used": False,
    }
    write_json(training_output / "manifest.json", training_manifest)

    test_output.mkdir(parents=True)
    test_path = test_output / "test.jsonl"
    write_jsonl(test_path, rows["TEST"], "example_id")
    train_questions = {
        _normalized_question(row["query"]) for row in [*rows["TRAIN"], *rows["VALIDATION"]]
    }
    test_overlap = sum(
        _normalized_question(row["query"]) in train_questions for row in rows["TEST"]
    )
    test_manifest = {
        "answer_visibility": "PRIVATE_GOLD_ONLY",
        "case_count": len(rows["TEST"]),
        "contains_company_data": True,
        "content_sha256": file_sha256(test_path),
        "dataset_version": dataset_version,
        "exact_question_overlap_with_train_dev": test_overlap,
        "field_decisions_sha256": file_sha256(release / "field-decisions.jsonl"),
        "final_test": True,
        "procedure_count": len(test_ids),
        "release_manifest_sha256": corpus_fingerprint,
        "review_status": "LOCKED",
        "schema_version": "full-corpus-sft-test-manifest-v1",
        "seed": seed,
        "split": "TEST",
    }
    write_json(test_output / "manifest.json", test_manifest)
    validate_result = validate_full_sft(training_output, test_output, release)
    if validate_result["status"] != "PASS":
        raise ValueError("FULL_SFT_POST_BUILD_VALIDATION_FAILED")
    return {
        "dataset_version": dataset_version,
        "decision_counts": {
            split: dict(Counter(row["decision_status"] for row in split_rows))
            for split, split_rows in rows.items()
        },
        "procedure_counts": {split: len(ids) for split, ids in split_ids.items()},
        "row_counts": {split: len(items) for split, items in rows.items()},
        "status": "PASS",
    }


def validate_full_sft(training: Path, test: Path, release: Path) -> dict[str, Any]:
    errors: Counter[str] = Counter()
    release_manifest, _, procedures, fragments, decisions = _validate_release(release)
    training_result = validate_sft_bundle(training)
    errors.update(training_result.get("errors", {}))
    training_manifest = _load_json(training / "manifest.json")
    test_manifest = _load_json(test / "manifest.json")
    train = _load_jsonl(training / "train.jsonl")
    validation = _load_jsonl(training / "validation.jsonl")
    test_rows = _load_jsonl(test / "test.jsonl")
    version = release_manifest["dataset_version"]
    release_manifest_sha256 = file_sha256(release / "release-manifest.json")
    field_decisions_sha256 = file_sha256(release / "field-decisions.jsonl")
    if (
        training_manifest.get("dataset_version") != version
        or test_manifest.get("dataset_version") != version
        or any(row.get("dataset_version") != version for row in [*train, *validation, *test_rows])
    ):
        errors["DATASET_VERSION_MISMATCH"] += 1
    if test_manifest.get("content_sha256") != file_sha256(test / "test.jsonl"):
        errors["TEST_HASH_MISMATCH"] += 1
    if (
        training_manifest.get("source_corpus_sha256") != release_manifest_sha256
        or test_manifest.get("release_manifest_sha256") != release_manifest_sha256
        or training_manifest.get("field_decisions_sha256") != field_decisions_sha256
        or test_manifest.get("field_decisions_sha256") != field_decisions_sha256
    ):
        errors["SOURCE_RELEASE_BINDING_INVALID"] += 1
    if (
        test_manifest.get("review_status") != "LOCKED"
        or test_manifest.get("final_test") is not True
        or any(row.get("split") != "TEST" for row in test_rows)
    ):
        errors["TEST_LOCK_INVALID"] += 1

    split_rows = {"TRAIN": train, "VALIDATION": validation, "TEST": test_rows}
    split_procedures = {
        split: {row.get("procedure_id") for row in rows} for split, rows in split_rows.items()
    }
    if (
        split_procedures["TRAIN"] & split_procedures["VALIDATION"]
        or split_procedures["TRAIN"] & split_procedures["TEST"]
        or split_procedures["VALIDATION"] & split_procedures["TEST"]
    ):
        errors["PROCEDURE_SPLIT_LEAKAGE"] += 1
    if set().union(*split_procedures.values()) != set(procedures):
        errors["PROCEDURE_COVERAGE_INCOMPLETE"] += 1
    if training_manifest.get("procedure_count") != {
        "TRAIN": len(split_procedures["TRAIN"]),
        "VALIDATION": len(split_procedures["VALIDATION"]),
    } or training_manifest.get("rendered_examples") != {
        "TRAIN": len(train),
        "VALIDATION": len(validation),
    }:
        errors["TRAINING_MANIFEST_COUNT_INVALID"] += 1
    expected_split_strategy = (
        "PROCEDURE_DISJOINT_FEATURE_BALANCED_"
        f"{len(split_procedures['TRAIN'])}_"
        f"{len(split_procedures['VALIDATION'])}_"
        f"{len(split_procedures['TEST'])}"
    )
    if training_manifest.get("split_strategy") != expected_split_strategy:
        errors["SPLIT_STRATEGY_INVALID"] += 1
    ids = [row.get("example_id") for rows in split_rows.values() for row in rows]
    if len(ids) != len(set(ids)):
        errors["EXAMPLE_ID_DUPLICATE"] += 1

    train_dev_questions = {_normalized_question(row["query"]) for row in [*train, *validation]}
    test_overlap = sum(
        _normalized_question(row["query"]) in train_dev_questions for row in test_rows
    )
    if test_overlap:
        errors["TEST_QUESTION_EXACT_OVERLAP"] += 1
    if (
        test_manifest.get("case_count") != len(test_rows)
        or test_manifest.get("procedure_count") != len(split_procedures["TEST"])
        or test_manifest.get("exact_question_overlap_with_train_dev") != test_overlap
    ):
        errors["TEST_MANIFEST_COUNT_INVALID"] += 1
    for row in [*train, *validation, *test_rows]:
        decision = decisions.get((row.get("procedure_id"), row.get("field")))
        if not decision or row.get("decision_status") != decision.get("decision_status"):
            errors["ROW_DECISION_BINDING_INVALID"] += 1
            continue
        evidence_ids = {item.get("fragment_id") for item in row.get("evidence", [])}
        cited = row.get("target", {}).get("cited_fragment_ids", [])
        if not evidence_ids <= fragments.keys():
            errors["ROW_EVIDENCE_REFERENCE_INVALID"] += 1
        if decision["decision_status"] == "APPROVED":
            if (
                row.get("expected_status") != "ANSWER"
                or not cited
                or not set(cited) <= evidence_ids
            ):
                errors["ROW_ANSWER_TARGET_INVALID"] += 1
        elif (
            row.get("expected_status") != "INSUFFICIENT_DATA"
            or cited
            or not row.get("target", {}).get("missing_information")
        ):
            errors["ROW_ABSTENTION_TARGET_INVALID"] += 1
    return {
        "counts": {split: len(rows) for split, rows in split_rows.items()},
        "errors": dict(sorted(errors.items())),
        "procedure_counts": {split: len(ids) for split, ids in split_procedures.items()},
        "status": "PASS" if not errors else "FAIL",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build")
    build.add_argument("--release", type=Path, required=True)
    build.add_argument("--training-output", type=Path, required=True)
    build.add_argument("--test-output", type=Path, required=True)
    build.add_argument("--train-variants", type=int, default=2)
    build.add_argument("--validation-procedures", type=int, default=5)
    build.add_argument("--test-procedures", type=int, default=5)
    build.add_argument("--seed", type=int, default=42)
    validate = sub.add_parser("validate")
    validate.add_argument("--release", type=Path, required=True)
    validate.add_argument("--training", type=Path, required=True)
    validate.add_argument("--test", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "build":
            result = build_full_sft(
                args.release.resolve(),
                args.training_output,
                args.test_output,
                train_variants=args.train_variants,
                validation_procedures=args.validation_procedures,
                test_procedures=args.test_procedures,
                seed=args.seed,
            )
        else:
            result = validate_full_sft(
                args.training.resolve(), args.test.resolve(), args.release.resolve()
            )
        print(json.dumps(result, ensure_ascii=True, sort_keys=True))
        return 0 if result["status"] == "PASS" else 2
    except Exception as error:
        print(
            json.dumps(
                {"status": "FAIL", "error": str(error) or type(error).__name__},
                ensure_ascii=True,
                sort_keys=True,
            )
        )
        return 2


if __name__ == "__main__":
    sys.exit(main())
