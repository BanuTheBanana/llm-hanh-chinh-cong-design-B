#!/usr/bin/env python3
"""Prepare and validate a private G4 hidden release test without printing its content."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from .g4_tu_validator import FIELD_SECTIONS

EMAIL_RE = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
PHONE_RE = re.compile(r"(?<!\d)(?:\+?84|0)(?:[ .-]?\d){9}(?!\d)")
EXPECTED_FIELDS = {
    "receiving_authority": 10,
    "required_documents": 10,
    "fees": 10,
    "processing_times": 10,
}


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    payload = path.read_bytes()
    text = payload.decode("utf-8")
    if text.startswith("\ufeff") or text != unicodedata.normalize("NFC", text):
        raise ValueError("PRIVATE_TEST_TEXT_ENCODING_INVALID")
    rows = [json.loads(line) for line in text.splitlines() if line.strip()]
    if not all(isinstance(row, dict) for row in rows):
        raise ValueError("PRIVATE_TEST_JSON_OBJECT_REQUIRED")
    return rows


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
        newline="\n",
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _values(procedure: dict[str, Any], field: str) -> list[Any]:
    value = procedure.get(field)
    return list(value) if isinstance(value, list) else []


def _expected_points(procedure: dict[str, Any], field: str) -> list[str]:
    points: list[str] = []
    for item in _values(procedure, field):
        if isinstance(item, str) and item.strip():
            points.append(item.strip())
        elif isinstance(item, dict):
            raw_text = item.get("raw_text")
            if isinstance(raw_text, str) and raw_text.strip():
                points.append(raw_text.strip())
    return list(dict.fromkeys(points))


def _expected_status(procedure: dict[str, Any], field: str, field_evidence: list[Any]) -> str:
    values = _values(procedure, field)
    raw_values = {
        str(item.get("raw_text", "")).strip().casefold()
        for item in values
        if isinstance(item, dict)
    }
    if not values or not field_evidence or raw_values & {"0.0", "05"}:
        return "INSUFFICIENT_DATA"
    return "ANSWER"


def _fingerprint(row: dict[str, Any]) -> str:
    text = " ".join(
        str(turn.get("text", "")) for turn in row.get("turns", []) if isinstance(turn, dict)
    )
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


def _question_fingerprint(row: dict[str, Any]) -> str:
    return " ".join(unicodedata.normalize("NFKC", str(row.get("question", ""))).casefold().split())


def _review_map(prior_paths: list[Path]) -> dict[tuple[str, str], dict[str, Any]]:
    mapped: dict[tuple[str, str], dict[str, Any]] = {}
    for path in prior_paths:
        for row in _load_jsonl(path):
            review = row.get("review", {})
            if review.get("status") != "APPROVED":
                raise ValueError("APPROVED_PRIOR_REVIEW_REQUIRED")
            key = (str(row.get("procedure_id")), str(row.get("field_expected")))
            value = {
                "flags": list(review.get("flags", [])),
                "decision": review.get("decision"),
            }
            if key in mapped and mapped[key] != value:
                raise ValueError("PRIOR_REVIEW_CONFLICT")
            mapped[key] = value
    return mapped


def _normalize_row(
    row: dict[str, Any],
    procedures: dict[str, dict[str, Any]],
    reviews: dict[tuple[str, str], dict[str, Any]],
    reviewer_role: str,
    reviewed_at: str,
) -> dict[str, Any]:
    procedure_id = str(row.get("procedure_id", ""))
    field = str(row.get("field_expected", ""))
    procedure = procedures.get(procedure_id)
    if procedure is None or field not in EXPECTED_FIELDS:
        raise ValueError("PRIVATE_TEST_SOURCE_REFERENCE_INVALID")
    turns = row.get("turns")
    if not isinstance(turns, list) or [turn.get("role") for turn in turns] != [
        "user",
        "assistant",
        "user",
    ]:
        raise ValueError("PRIVATE_TEST_MULTITURN_STRUCTURE_INVALID")
    if not all(isinstance(turn.get("text"), str) and turn["text"].strip() for turn in turns):
        raise ValueError("PRIVATE_TEST_TURN_TEXT_INVALID")
    if EMAIL_RE.search(json.dumps(turns, ensure_ascii=False)) or PHONE_RE.search(
        json.dumps(turns, ensure_ascii=False)
    ):
        raise ValueError("PRIVATE_TEST_PII_PATTERN")
    final_question = turns[2]["text"]
    if final_question == turns[0]["text"] or len(final_question.split()) < 3:
        raise ValueError("PRIVATE_TEST_FOLLOWUP_QUALITY_INVALID")

    field_evidence = procedure.get("field_evidence", {}).get(field, [])
    if not isinstance(field_evidence, list):
        field_evidence = []
    status = _expected_status(procedure, field, field_evidence)
    gold_fragment_ids = list(field_evidence) if status == "ANSWER" else []
    gold_answer = _values(procedure, field) if status == "ANSWER" else []
    expected_points = (
        _expected_points(procedure, field) if status == "ANSWER" else ["chưa đủ căn cứ"]
    )
    review = reviews.get((procedure_id, field))
    if review is None:
        raise ValueError("PRIVATE_TEST_PRIOR_REVIEW_REQUIRED")
    expected_decision = (
        (
            "APPROVED_AS_INSUFFICIENT_DATA"
            if status == "INSUFFICIENT_DATA"
            else "APPROVED_FOR_RAW_TEXT_ONLY"
        )
        if review["flags"]
        else "APPROVED_AGAINST_NORMALIZED_SOURCE"
    )
    if review["decision"] != expected_decision:
        raise ValueError("PRIVATE_TEST_REVIEW_DECISION_MISMATCH")

    must_exclude = row.get("must_exclude", [])
    if not isinstance(must_exclude, list) or not all(
        isinstance(item, str) for item in must_exclude
    ):
        raise ValueError("PRIVATE_TEST_MUST_EXCLUDE_INVALID")
    return {
        "scenario_version": "g4-eval-scenario-v1",
        "scenario_id": row.get("scenario_id"),
        "dataset_version": procedure.get("dataset_version"),
        "split": "TEST_V3",
        "scenario_group_id": row.get("scenario_group_id"),
        "procedure_id": procedure_id,
        "procedure_title": procedure.get("title"),
        "field_expected": field,
        "question": final_question,
        "expected_status": status,
        "gold_fragment_ids": gold_fragment_ids,
        "gold_label": {
            "status": status,
            "procedure_id": procedure_id,
            "field": field,
            "fragment_ids": gold_fragment_ids,
        },
        "gold_answer": gold_answer,
        "expected_points": expected_points,
        "must_include": expected_points,
        "must_exclude": must_exclude,
        "is_multiturn": True,
        "conversation_turns": 3,
        "turns": turns,
        "scored_turn_index": 2,
        "scored_turn_role": "user",
        "answer_visibility": "private_gold_only",
        "contains_pii": False,
        "review": {
            "author_role": "DATA_CURATOR",
            "status": "APPROVED",
            "reviewer_role": reviewer_role,
            "reviewed_at": reviewed_at,
            "decision": expected_decision,
            "flags": review["flags"],
        },
    }


def validate_release_test(
    test_dir: Path,
    dataset_dir: Path,
    prior_paths: list[Path],
    scenario_schema_path: Path,
    manifest_schema_path: Path,
) -> dict[str, Any]:
    errors: Counter[str] = Counter()
    test_path = test_dir / "scenario_test_v3.jsonl"
    manifest_path = test_dir / "scenario_test_v3_manifest.json"
    try:
        rows = _load_jsonl(test_path)
        procedures_list = _load_jsonl(dataset_dir / "normalized/procedures.jsonl")
        fragments_list = _load_jsonl(dataset_dir / "normalized/fragments.jsonl")
        priors = [row for path in prior_paths for row in _load_jsonl(path)]
        prior_reviews = _review_map(prior_paths)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        scenario_schema = json.loads(scenario_schema_path.read_text(encoding="utf-8"))
        manifest_schema = json.loads(manifest_schema_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
        return {"status": "FAIL", "errors": {"PRIVATE_TEST_REQUIRED_FILE_INVALID": 1}}

    scenario_validator = Draft202012Validator(scenario_schema, format_checker=FormatChecker())
    manifest_validator = Draft202012Validator(manifest_schema, format_checker=FormatChecker())
    for row in rows:
        if next(scenario_validator.iter_errors(row), None) is not None:
            errors["PRIVATE_TEST_SCENARIO_SCHEMA_INVALID"] += 1
    if next(manifest_validator.iter_errors(manifest), None) is not None:
        errors["PRIVATE_TEST_MANIFEST_SCHEMA_INVALID"] += 1

    if len(rows) != 40:
        errors["PRIVATE_TEST_COUNT_INVALID"] += 1
    for key in ("scenario_id", "scenario_group_id"):
        values = [row.get(key) for row in rows]
        if len(values) != len(set(values)):
            errors[f"PRIVATE_TEST_{key.upper()}_DUPLICATE"] += 1
    procedures = {row.get("procedure_id"): row for row in procedures_list}
    fragments = {row.get("fragment_id"): row for row in fragments_list}
    field_counts: Counter[str] = Counter()
    for row in rows:
        procedure = procedures.get(row.get("procedure_id"))
        field = row.get("field_expected")
        field_counts[str(field)] += 1
        turns = row.get("turns", [])
        roles = [turn.get("role") for turn in turns if isinstance(turn, dict)]
        final_turn_matches = (
            bool(turns)
            and isinstance(turns[-1], dict)
            and (row.get("question") == turns[-1].get("text"))
        )
        if (
            row.get("split") != "TEST_V3"
            or row.get("is_multiturn") is not True
            or row.get("conversation_turns") != 3
            or roles != ["user", "assistant", "user"]
            or not final_turn_matches
            or row.get("scored_turn_index") != 2
            or row.get("scored_turn_role") != "user"
        ):
            errors["PRIVATE_TEST_TARGET_TURN_INVALID"] += 1
        if procedure is None:
            errors["PRIVATE_TEST_PROCEDURE_REFERENCE_INVALID"] += 1
            continue
        evidence = procedure.get("field_evidence", {}).get(field, [])
        if not isinstance(evidence, list):
            evidence = []
        status = _expected_status(procedure, str(field), evidence)
        ids = list(evidence) if status == "ANSWER" else []
        answer = _values(procedure, str(field)) if status == "ANSWER" else []
        points = (
            _expected_points(procedure, str(field)) if status == "ANSWER" else ["chưa đủ căn cứ"]
        )
        if row.get("expected_status") != status:
            errors["PRIVATE_TEST_STATUS_SOURCE_MISMATCH"] += 1
        if row.get("gold_fragment_ids") != ids:
            errors["PRIVATE_TEST_FRAGMENT_SOURCE_MISMATCH"] += 1
        if row.get("gold_answer") != answer:
            errors["PRIVATE_TEST_ANSWER_SOURCE_MISMATCH"] += 1
        if row.get("expected_points") != points or row.get("must_include") != points:
            errors["PRIVATE_TEST_POINTS_SOURCE_MISMATCH"] += 1
        for fragment_id in ids:
            fragment = fragments.get(fragment_id)
            if (
                fragment is None
                or fragment.get("procedure_id") != row.get("procedure_id")
                or fragment.get("section_type") != FIELD_SECTIONS.get(str(field))
            ):
                errors["PRIVATE_TEST_FRAGMENT_BINDING_INVALID"] += 1
        review = row.get("review", {})
        if review.get("status") != "APPROVED" or not review.get("reviewer_role"):
            errors["PRIVATE_TEST_REVIEW_REQUIRED"] += 1
        prior_review = prior_reviews.get((str(row.get("procedure_id")), str(field)))
        if prior_review is None:
            errors["PRIVATE_TEST_PRIOR_REVIEW_REQUIRED"] += 1
        else:
            expected_decision = (
                (
                    "APPROVED_AS_INSUFFICIENT_DATA"
                    if status == "INSUFFICIENT_DATA"
                    else "APPROVED_FOR_RAW_TEXT_ONLY"
                )
                if prior_review["flags"]
                else "APPROVED_AGAINST_NORMALIZED_SOURCE"
            )
            if (
                review.get("flags") != prior_review["flags"]
                or review.get("decision") != expected_decision
            ):
                errors["PRIVATE_TEST_REVIEW_SOURCE_MISMATCH"] += 1
        visible = json.dumps({"question": row.get("question"), "turns": turns}, ensure_ascii=False)
        if (
            EMAIL_RE.search(visible)
            or PHONE_RE.search(visible)
            or row.get("contains_pii") is not False
        ):
            errors["PRIVATE_TEST_PII_INVALID"] += 1

    prior_question_fingerprints = {_question_fingerprint(row) for row in priors}
    question_fingerprints = {_question_fingerprint(row) for row in rows}
    if prior_question_fingerprints & question_fingerprints:
        errors["PRIVATE_TEST_EXACT_QUESTION_LEAKAGE"] += 1
    prior_conversations = {_fingerprint(row) for row in priors}
    conversations = {_fingerprint(row) for row in rows}
    if prior_conversations & conversations:
        errors["PRIVATE_TEST_EXACT_CONVERSATION_LEAKAGE"] += 1
    if any(
        SequenceMatcher(None, left, right).ratio() >= 0.97
        for left in conversations
        for right in prior_conversations
    ):
        errors["PRIVATE_TEST_NEAR_CONVERSATION_LEAKAGE"] += 1

    if dict(field_counts) != EXPECTED_FIELDS:
        errors["PRIVATE_TEST_FIELD_DISTRIBUTION_INVALID"] += 1
    if len({row.get("procedure_id") for row in rows}) != 10:
        errors["PRIVATE_TEST_PROCEDURE_COVERAGE_INVALID"] += 1
    if manifest.get("field_counts") != dict(field_counts):
        errors["PRIVATE_TEST_MANIFEST_FIELD_COUNTS_MISMATCH"] += 1
    if manifest.get("sha256", {}).get("test") != _sha256(test_path):
        errors["PRIVATE_TEST_HASH_MISMATCH"] += 1
    if manifest.get("scenario_count") != len(rows):
        errors["PRIVATE_TEST_MANIFEST_COUNT_MISMATCH"] += 1

    return {
        "status": "PASS" if not errors else "FAIL",
        "counts": {
            "scenarios": len(rows),
            "multiturn": sum(row.get("is_multiturn") is True for row in rows),
            "procedures": len({row.get("procedure_id") for row in rows}),
            "fields": dict(sorted(field_counts.items())),
        },
        "test_sha256": _sha256(test_path),
        "errors": dict(sorted(errors.items())),
    }


def prepare_and_lock(
    input_path: Path,
    output_dir: Path,
    dataset_dir: Path,
    prior_paths: list[Path],
    scenario_schema_path: Path,
    manifest_schema_path: Path,
    *,
    reviewer_role: str,
    reviewed_at: str,
    generated_at: str,
) -> dict[str, Any]:
    source_rows = _load_jsonl(input_path)
    if len(source_rows) != 40:
        raise ValueError("PRIVATE_TEST_COUNT_INVALID")
    if len({row.get("scenario_id") for row in source_rows}) != len(source_rows):
        raise ValueError("PRIVATE_TEST_SCENARIO_ID_DUPLICATE")
    procedures = {
        row.get("procedure_id"): row
        for row in _load_jsonl(dataset_dir / "normalized/procedures.jsonl")
    }
    reviews = _review_map(prior_paths)
    rows = [
        _normalize_row(row, procedures, reviews, reviewer_role, reviewed_at) for row in source_rows
    ]
    output_dir.mkdir(parents=True, exist_ok=True)
    test_path = output_dir / "scenario_test_v3.jsonl"
    manifest_path = output_dir / "scenario_test_v3_manifest.json"
    _write_jsonl(test_path, rows)
    field_counts = dict(sorted(Counter(row["field_expected"] for row in rows).items()))
    manifest = {
        "schema_version": "g4-release-test-manifest-v1",
        "dataset_version": rows[0]["dataset_version"],
        "scenario_set": "G4-01-test-v3-reviewed",
        "generated_at": generated_at,
        "author_role": "DATA_CURATOR",
        "reviewer_role": reviewer_role,
        "reviewed_at": reviewed_at,
        "review_status": "LOCKED",
        "split": "TEST_V3",
        "split_strategy": "HIDDEN_MULTITURN_PARAPHRASE",
        "schema_file": "docs/giai-doan-4/schema/g4-evaluation-scenario-v1.schema.json",
        "procedure_count": len({row["procedure_id"] for row in rows}),
        "scenario_count": len(rows),
        "multi_turn_count": sum(row["is_multiturn"] for row in rows),
        "field_counts": field_counts,
        "answer_visibility": "PRIVATE_GOLD_ONLY",
        "recipient": "Hoan only",
        "do_not_use_for": [
            "prompt_tuning",
            "retrieval_tuning",
            "model_tuning",
            "serving_index",
        ],
        "files": {"test": "scenario_test_v3.jsonl"},
        "sha256": {"test": _sha256(test_path)},
        "validation": {"status": "PASS", "errors": {}},
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return validate_release_test(
        output_dir,
        dataset_dir,
        prior_paths,
        scenario_schema_path,
        manifest_schema_path,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("prepare-lock", "validate"):
        sub = subparsers.add_parser(command)
        sub.add_argument("--test-dir", type=Path, required=True)
        sub.add_argument("--dataset", type=Path, required=True)
        sub.add_argument("--prior", action="append", type=Path, required=True)
        sub.add_argument("--scenario-schema", type=Path, required=True)
        sub.add_argument("--manifest-schema", type=Path, required=True)
        if command == "prepare-lock":
            sub.add_argument("--input", type=Path, required=True)
            sub.add_argument("--reviewer-role", required=True)
            sub.add_argument("--reviewed-at")
            sub.add_argument("--generated-at")
    args = parser.parse_args()
    if args.command == "prepare-lock":
        now = datetime.now(timezone.utc).isoformat()
        report = prepare_and_lock(
            args.input.resolve(),
            args.test_dir.resolve(),
            args.dataset.resolve(),
            [path.resolve() for path in args.prior],
            args.scenario_schema.resolve(),
            args.manifest_schema.resolve(),
            reviewer_role=args.reviewer_role,
            reviewed_at=args.reviewed_at or now,
            generated_at=args.generated_at or now,
        )
    else:
        report = validate_release_test(
            args.test_dir.resolve(),
            args.dataset.resolve(),
            [path.resolve() for path in args.prior],
            args.scenario_schema.resolve(),
            args.manifest_schema.resolve(),
        )
    print(json.dumps(report, ensure_ascii=True, sort_keys=True))
    return 0 if report["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
