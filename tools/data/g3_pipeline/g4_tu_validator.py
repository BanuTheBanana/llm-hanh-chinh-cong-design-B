#!/usr/bin/env python3
"""Validate a private G4 evaluation bundle without printing private content."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

FIELD_SECTIONS = {
    "receiving_authority": "RECEIVING_AUTHORITY",
    "required_documents": "REQUIRED_DOCUMENTS",
    "fees": "FEES",
    "processing_times": "PROCESSING_TIME",
    "submission_methods": "SUBMISSION_METHODS",
    "steps": "STEPS",
}
EMAIL_RE = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
PHONE_RE = re.compile(r"(?<!\d)(?:\+?84|0)(?:[ .-]?\d){9}(?!\d)")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_jsonl(path: Path, errors: Counter[str]) -> list[dict[str, Any]]:
    try:
        payload = path.read_bytes()
        text = payload.decode("utf-8")
    except (OSError, UnicodeDecodeError):
        errors["FILE_NOT_UTF8"] += 1
        return []
    if text.startswith("\ufeff"):
        errors["UTF8_BOM_NOT_ALLOWED"] += 1
    if text != unicodedata.normalize("NFC", text):
        errors["TEXT_NOT_NFC"] += 1
    rows: list[dict[str, Any]] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            errors["INVALID_JSONL"] += 1
            continue
        if not isinstance(value, dict):
            errors["JSON_OBJECT_REQUIRED"] += 1
            continue
        rows.append(value)
    return rows


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


def _expected_status(proc: dict[str, Any], field: str, field_evidence: list[Any]) -> str:
    values = _values(proc, field)
    raw_values = {
        str(item.get("raw_text", "")).strip().casefold()
        for item in values
        if isinstance(item, dict)
    }
    if not values or not field_evidence or raw_values & {"0.0", "05"}:
        return "INSUFFICIENT_DATA"
    return "ANSWER"


def _conversation_fingerprint(row: dict[str, Any]) -> str:
    turns = row.get("turns", [])
    text = " ".join(str(turn.get("text", "")) for turn in turns if isinstance(turn, dict))
    return " ".join(text.casefold().split())


def _schema_errors(
    rows: list[dict[str, Any]], schema: dict[str, Any], errors: Counter[str]
) -> None:
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    for row in rows:
        if next(validator.iter_errors(row), None) is not None:
            errors["SCENARIO_SCHEMA_INVALID"] += 1


def validate_bundle(
    dataset_dir: Path,
    scenario_schema_path: Path,
    manifest_schema_path: Path,
    *,
    mode: str = "preflight",
) -> dict[str, Any]:
    errors: Counter[str] = Counter()
    warnings: Counter[str] = Counter()
    bundle_dir = dataset_dir / "g4_eval"
    dev_path = bundle_dir / "scenario_dev.jsonl"
    test_path = bundle_dir / "scenario_test_v2.jsonl"
    manifest_path = bundle_dir / "scenario_manifest.json"

    dev = _load_jsonl(dev_path, errors)
    test_v2 = _load_jsonl(test_path, errors)
    procedures = _load_jsonl(dataset_dir / "normalized/procedures.jsonl", errors)
    fragments = _load_jsonl(dataset_dir / "normalized/fragments.jsonl", errors)
    try:
        manifest = _load_json(manifest_path)
        scenario_schema = _load_json(scenario_schema_path)
        manifest_schema = _load_json(manifest_schema_path)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        errors["REQUIRED_JSON_INVALID"] += 1
        manifest = {}
        scenario_schema = {}
        manifest_schema = {}

    if scenario_schema:
        _schema_errors(dev + test_v2, scenario_schema, errors)
    if manifest_schema:
        manifest_validator = Draft202012Validator(manifest_schema, format_checker=FormatChecker())
        if next(manifest_validator.iter_errors(manifest), None) is not None:
            errors["MANIFEST_SCHEMA_INVALID"] += 1

    rows = dev + test_v2
    if len(dev) != 80:
        errors["DEV_COUNT"] += 1
    if len(test_v2) != 40:
        errors["TEST_V2_COUNT"] += 1
    ids = [row.get("scenario_id") for row in rows]
    if len(ids) != len(set(ids)):
        errors["SCENARIO_ID_DUPLICATE"] += 1
    if any(row.get("split") != "DEV" for row in dev):
        errors["DEV_SPLIT_INVALID"] += 1
    if any(row.get("split") != "TEST_V2" for row in test_v2):
        errors["TEST_V2_SPLIT_INVALID"] += 1

    dev_procedure_ids = {row.get("procedure_id") for row in dev}
    test_procedure_ids = {row.get("procedure_id") for row in test_v2}
    if dev_procedure_ids & test_procedure_ids:
        errors["PROCEDURE_SPLIT_LEAKAGE"] += 1
    dev_pairs = {(row.get("procedure_id"), row.get("field_expected")) for row in dev}
    test_pairs = {(row.get("procedure_id"), row.get("field_expected")) for row in test_v2}
    if dev_pairs & test_pairs:
        errors["PROCEDURE_FIELD_SPLIT_LEAKAGE"] += 1
    dev_groups = {row.get("scenario_group_id") for row in dev}
    test_groups = {row.get("scenario_group_id") for row in test_v2}
    if dev_groups & test_groups:
        errors["SCENARIO_GROUP_SPLIT_LEAKAGE"] += 1

    proc_by_id = {row.get("procedure_id"): row for row in procedures}
    fragment_by_id = {row.get("fragment_id"): row for row in fragments}
    if len(proc_by_id) != len(procedures):
        errors["PROCEDURE_ID_DUPLICATE"] += 1
    if len(fragment_by_id) != len(fragments):
        errors["FRAGMENT_ID_DUPLICATE"] += 1

    ambiguous_pairs: set[tuple[Any, Any]] = set()
    pending_count = 0
    multi_turn_count = 0
    for row in rows:
        procedure_id = row.get("procedure_id")
        field = row.get("field_expected")
        proc = proc_by_id.get(procedure_id)
        if proc is None:
            errors["PROCEDURE_REFERENCE_INVALID"] += 1
            continue
        if row.get("dataset_version") != proc.get("dataset_version"):
            errors["DATASET_VERSION_MISMATCH"] += 1
        if row.get("procedure_title") != proc.get("title"):
            errors["PROCEDURE_TITLE_MISMATCH"] += 1

        values = _values(proc, str(field))
        field_evidence = proc.get("field_evidence", {}).get(field, [])
        if not isinstance(field_evidence, list):
            field_evidence = []
        expected_status = _expected_status(proc, str(field), field_evidence)
        gold_ids = row.get("gold_fragment_ids", [])
        if row.get("expected_status") != expected_status:
            errors["EXPECTED_STATUS_MISMATCH"] += 1
        if expected_status == "ANSWER":
            if row.get("gold_answer") != values:
                errors["GOLD_ANSWER_SOURCE_MISMATCH"] += 1
            if set(gold_ids) != set(field_evidence):
                errors["GOLD_FIELD_EVIDENCE_MISMATCH"] += 1
            points = _expected_points(proc, str(field))
            if row.get("expected_points") != points or row.get("must_include") != points:
                errors["GOLD_EXPECTED_POINTS_MISMATCH"] += 1
        else:
            if gold_ids or row.get("gold_answer"):
                errors["INSUFFICIENT_GOLD_MUST_BE_EMPTY"] += 1
            if row.get("expected_points") != ["chưa đủ căn cứ"]:
                errors["INSUFFICIENT_POINT_REQUIRED"] += 1

        label = row.get("gold_label", {})
        if label != {
            "status": row.get("expected_status"),
            "procedure_id": procedure_id,
            "field": field,
            "fragment_ids": gold_ids,
        }:
            errors["GOLD_LABEL_MISMATCH"] += 1

        for fragment_id in gold_ids:
            fragment = fragment_by_id.get(fragment_id)
            if fragment is None:
                errors["GOLD_FRAGMENT_REFERENCE_INVALID"] += 1
                continue
            if fragment.get("procedure_id") != procedure_id:
                errors["GOLD_FRAGMENT_PROCEDURE_MISMATCH"] += 1
            if fragment.get("section_type") != FIELD_SECTIONS.get(str(field)):
                errors["GOLD_FRAGMENT_FIELD_MISMATCH"] += 1

        turns = row.get("turns", [])
        if row.get("conversation_turns") != len(turns):
            errors["CONVERSATION_TURN_COUNT_MISMATCH"] += 1
        if not turns or turns[0].get("role") != "user" or turns[-1].get("role") != "user":
            errors["CONVERSATION_MUST_START_END_USER"] += 1
        if any(
            turns[index].get("role") == turns[index - 1].get("role")
            for index in range(1, len(turns))
        ):
            errors["CONVERSATION_ROLE_ORDER_INVALID"] += 1
        if turns and row.get("question") != turns[-1].get("text"):
            errors["QUESTION_FINAL_TURN_MISMATCH"] += 1
        if row.get("is_multiturn"):
            multi_turn_count += 1
            if len(turns) < 3 or not any(turn.get("role") == "assistant" for turn in turns):
                errors["MULTI_TURN_STRUCTURE_INVALID"] += 1
            if proc.get("title") in str(row.get("question", "")):
                errors["MULTI_TURN_DOES_NOT_REQUIRE_CONTEXT"] += 1
            if any("sẽ đối chiếu" in str(turn.get("text", "")).casefold() for turn in turns):
                errors["MULTI_TURN_PLACEHOLDER_ASSISTANT"] += 1
        elif len(turns) != 1:
            errors["SINGLE_TURN_STRUCTURE_INVALID"] += 1

        visible_input = " ".join(
            [str(row.get("question", ""))]
            + [str(turn.get("text", "")) for turn in turns if isinstance(turn, dict)]
        )
        if EMAIL_RE.search(visible_input) or PHONE_RE.search(visible_input):
            errors["SCENARIO_PII_PATTERN"] += 1
        if row.get("contains_pii") is not False:
            errors["CONTAINS_PII_MUST_BE_FALSE"] += 1

        review = row.get("review", {})
        flags = review.get("flags", []) if isinstance(review, dict) else []
        if flags:
            ambiguous_pairs.add((procedure_id, field))
        if review.get("status") != "APPROVED":
            pending_count += 1
        elif (
            not review.get("reviewer_role")
            or not review.get("reviewed_at")
            or review.get("reviewer_role") == review.get("author_role")
        ):
            errors["APPROVED_REVIEW_METADATA_INVALID"] += 1
        elif flags and review.get("decision") != "APPROVED_FOR_RAW_TEXT_ONLY":
            errors["AMBIGUOUS_REVIEW_DECISION_INVALID"] += 1
        elif not flags and review.get("decision") != "APPROVED_AGAINST_NORMALIZED_SOURCE":
            errors["REVIEW_DECISION_INVALID"] += 1

    fingerprints_dev = {_conversation_fingerprint(row) for row in dev}
    fingerprints_test = {_conversation_fingerprint(row) for row in test_v2}
    if fingerprints_dev & fingerprints_test:
        errors["EXACT_CONVERSATION_SPLIT_LEAKAGE"] += 1
    near_duplicates = 0
    for left in fingerprints_dev:
        for right in fingerprints_test:
            if SequenceMatcher(None, left, right).ratio() >= 0.97:
                near_duplicates += 1
    if near_duplicates:
        warnings["NEAR_DUPLICATE_CROSS_SPLIT"] = near_duplicates

    if multi_turn_count < 20:
        errors["MULTI_TURN_COUNT"] += 1
    if manifest.get("dev_count") != len(dev) or manifest.get("test_v2_count") != len(test_v2):
        errors["MANIFEST_COUNT_MISMATCH"] += 1
    if manifest.get("multi_turn_count") != multi_turn_count:
        errors["MANIFEST_MULTI_TURN_MISMATCH"] += 1
    if set(manifest.get("dev_procedure_ids", [])) != dev_procedure_ids:
        errors["MANIFEST_DEV_PROCEDURES_MISMATCH"] += 1
    if set(manifest.get("test_v2_procedure_ids", [])) != test_procedure_ids:
        errors["MANIFEST_TEST_PROCEDURES_MISMATCH"] += 1
    if manifest.get("ambiguous_source_field_count") != len(ambiguous_pairs):
        errors["MANIFEST_AMBIGUITY_COUNT_MISMATCH"] += 1
    try:
        if manifest.get("sha256", {}).get("dev") != _sha256(dev_path):
            errors["DEV_HASH_MISMATCH"] += 1
        if manifest.get("sha256", {}).get("test_v2") != _sha256(test_path):
            errors["TEST_V2_HASH_MISMATCH"] += 1
    except OSError:
        errors["SCENARIO_FILE_MISSING"] += 1

    manifest_state = manifest.get("review_status")
    lock_state = manifest.get("test_v2_lock", {}).get("status")
    if manifest_state != lock_state:
        errors["REVIEW_LOCK_STATE_MISMATCH"] += 1
    if manifest_state == "LOCKED" and (
        not manifest.get("reviewer_role") or not manifest.get("reviewed_at")
    ):
        errors["MANIFEST_REVIEW_METADATA_INVALID"] += 1
    if mode == "publish":
        if pending_count:
            errors["SCENARIO_REVIEW_PENDING"] = pending_count
        if manifest_state != "LOCKED":
            errors["MANIFEST_NOT_LOCKED"] += 1
    else:
        if pending_count:
            warnings["SCENARIO_REVIEW_PENDING"] = pending_count
        if ambiguous_pairs:
            warnings["AMBIGUOUS_SOURCE_FIELD_REVIEW"] = len(ambiguous_pairs)

    return {
        "status": "PASS" if not errors else "FAIL",
        "mode": mode,
        "counts": {
            "dev": len(dev),
            "test_v2": len(test_v2),
            "multi_turn": multi_turn_count,
            "dev_procedures": len(dev_procedure_ids),
            "test_v2_procedures": len(test_procedure_ids),
            "ambiguous_source_fields": len(ambiguous_pairs),
        },
        "errors": dict(sorted(errors.items())),
        "warnings": dict(sorted(warnings.items())),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--scenario-schema", type=Path, required=True)
    parser.add_argument("--manifest-schema", type=Path, required=True)
    parser.add_argument("--mode", choices=("preflight", "publish"), default="preflight")
    args = parser.parse_args()
    report = validate_bundle(
        args.dataset.resolve(),
        args.scenario_schema.resolve(),
        args.manifest_schema.resolve(),
        mode=args.mode,
    )
    print(json.dumps(report, ensure_ascii=True, sort_keys=True))
    return 0 if report["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
