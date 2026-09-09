"""Validate private G3 JSONL without printing private record contents."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from . import DATA_CLASSIFICATION, SCHEMA_VERSION
from .common import file_sha256, scan_sensitive_record, sha256_text

FILES = {
    "sources": ("source_manifest.jsonl", "source_id"),
    "procedures": ("normalized/procedures.jsonl", "procedure_id"),
    "fragments": ("normalized/fragments.jsonl", "fragment_id"),
    "conflicts": ("quarantine/conflicts.jsonl", "conflict_id"),
    "questions": ("gold/questions.jsonl", "question_id"),
}

BUSINESS_FIELDS = (
    "applicant_scope",
    "receiving_authority",
    "submission_methods",
    "required_documents",
    "steps",
    "fees",
    "processing_times",
    "legal_bases",
)


def load_jsonl(path: Path, error_codes: list[str]) -> list[dict[str, Any]]:
    try:
        raw = path.read_bytes()
        text = raw.decode("utf-8")
    except OSError:
        error_codes.append("FILE_MISSING")
        return []
    except UnicodeDecodeError:
        error_codes.append("FILE_NOT_UTF8")
        return []
    if raw.startswith(b"\xef\xbb\xbf"):
        error_codes.append("UTF8_BOM_NOT_ALLOWED")
    if b"\r" in raw:
        error_codes.append("LF_REQUIRED")
    rows: list[dict[str, Any]] = []
    for line in text.splitlines():
        if not line.strip():
            error_codes.append("BLANK_JSONL_LINE")
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            error_codes.append("INVALID_JSON")
            continue
        if not isinstance(row, dict):
            error_codes.append("JSON_OBJECT_REQUIRED")
            continue
        rows.append(row)
    return rows


def index_rows(
    rows: list[dict[str, Any]], key: str, errors: list[str]
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        value = row.get(key)
        if not isinstance(value, str):
            errors.append("PRIMARY_ID_INVALID")
            continue
        if value in result:
            errors.append("PRIMARY_ID_DUPLICATE")
        result[value] = row
    return result


def gate(condition: bool, code: str, mode: str, errors: list[str], warnings: list[str]) -> None:
    if condition:
        return
    (errors if mode == "publish" else warnings).append(code)


def validate_dataset(
    dataset_dir: Path,
    schema_path: Path,
    *,
    mode: str = "preflight",
    expected_source_count: int | None = None,
    workbook_path: Path | None = None,
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"status": "FAIL", "errors": {"SCHEMA_FILE_INVALID": 1}, "warnings": {}}
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    loaded: dict[str, list[dict[str, Any]]] = {}
    for label, (relative, _) in FILES.items():
        path = dataset_dir / relative
        loaded[label] = load_jsonl(path, errors)
        for row in loaded[label]:
            findings = scan_sensitive_record(row)
            errors.extend(f"SENSITIVE_PATTERN_{finding}" for finding in findings)
            schema_errors = list(validator.iter_errors(row))
            errors.extend(f"SCHEMA_{item.validator.upper()}" for item in schema_errors)

    indexes = {label: index_rows(loaded[label], key, errors) for label, (_, key) in FILES.items()}
    all_ids: list[str] = []
    for values in indexes.values():
        all_ids.extend(values)
    if len(all_ids) != len(set(all_ids)):
        errors.append("CROSS_RECORD_ID_DUPLICATE")

    versions = {
        (
            row.get("schema_version"),
            row.get("dataset_version"),
            row.get("data_classification", DATA_CLASSIFICATION),
        )
        for rows in loaded.values()
        for row in rows
    }
    if any(version != SCHEMA_VERSION for version, _, _ in versions):
        errors.append("SCHEMA_VERSION_MISMATCH")
    if any(classification != DATA_CLASSIFICATION for _, _, classification in versions):
        errors.append("DATA_CLASSIFICATION_MISMATCH")
    dataset_versions = {version for _, version, _ in versions}
    if len(dataset_versions) != 1:
        errors.append("DATASET_VERSION_MISMATCH")

    sources = indexes["sources"]
    procedures = indexes["procedures"]
    fragments = indexes["fragments"]
    conflicts = indexes["conflicts"]
    questions = indexes["questions"]

    row_numbers: list[int] = []
    workbook_hashes: set[str] = set()
    for source in sources.values():
        locator = source.get("raw_locator", {})
        if isinstance(locator, dict):
            row_numbers.extend(locator.get("row_numbers", []))
            workbook_hashes.add(str(locator.get("workbook_sha256", "")))
    if len(row_numbers) != len(set(row_numbers)):
        errors.append("SOURCE_ROW_ACCOUNTING_DUPLICATE")
    if expected_source_count is not None and len(set(row_numbers)) != expected_source_count:
        errors.append("SOURCE_ROW_ACCOUNTING_COUNT")
    if workbook_path is not None:
        if not workbook_path.is_file() or workbook_hashes != {file_sha256(workbook_path)}:
            errors.append("WORKBOOK_SHA256_MISMATCH")

    for fragment in fragments.values():
        if fragment.get("procedure_id") not in procedures:
            errors.append("FRAGMENT_PROCEDURE_REFERENCE")
        if fragment.get("source_id") not in sources:
            errors.append("FRAGMENT_SOURCE_REFERENCE")
        if sha256_text(str(fragment.get("text", ""))) != fragment.get("content_sha256"):
            errors.append("FRAGMENT_CONTENT_HASH")

    open_conflict_procedures: set[str] = set()
    for conflict in conflicts.values():
        source_ids = conflict.get("source_ids", [])
        if not isinstance(source_ids, list) or not set(source_ids) <= sources.keys():
            errors.append("CONFLICT_SOURCE_REFERENCE")
        candidate = conflict.get("candidate_procedure_id")
        if candidate not in procedures:
            errors.append("CONFLICT_PROCEDURE_REFERENCE")
        if conflict.get("status") == "OPEN" and isinstance(candidate, str):
            open_conflict_procedures.add(candidate)

    for procedure_id, procedure in procedures.items():
        source_ids = procedure.get("source_ids", [])
        if (
            not isinstance(source_ids, list)
            or not source_ids
            or not set(source_ids) <= sources.keys()
        ):
            errors.append("PROCEDURE_SOURCE_REFERENCE")
        field_evidence = procedure.get("field_evidence")
        if not isinstance(field_evidence, dict):
            errors.append("FIELD_EVIDENCE_INVALID")
            continue
        for field in BUSINESS_FIELDS:
            evidence_ids = field_evidence.get(field)
            if not isinstance(evidence_ids, list) or not set(evidence_ids) <= fragments.keys():
                errors.append("FIELD_EVIDENCE_REFERENCE")
                continue
            if any(fragments[item].get("procedure_id") != procedure_id for item in evidence_ids):
                errors.append("FIELD_EVIDENCE_WRONG_PROCEDURE")
            values = procedure.get(field)
            missing = field in procedure.get("missing_fields", [])
            if (not isinstance(values, list)) or (bool(values) == missing):
                errors.append("MISSING_FIELDS_INCONSISTENT")
            if values and not evidence_ids:
                errors.append("FIELD_WITHOUT_EVIDENCE")
        if (
            procedure_id in open_conflict_procedures
            and procedure.get("review", {}).get("status") != "QUARANTINED"
        ):
            errors.append("OPEN_CONFLICT_NOT_QUARANTINED")
        review_status = procedure.get("review", {}).get("status")
        gate(
            review_status in {"APPROVED_FOR_DEMO", "APPROVED_FOR_PRODUCTION"},
            "PROCEDURE_REVIEW_PENDING",
            mode,
            errors,
            warnings,
        )
        if review_status in {"APPROVED_FOR_DEMO", "APPROVED_FOR_PRODUCTION"}:
            source_statuses = {sources[item].get("review", {}).get("status") for item in source_ids}
            if not source_statuses <= {"APPROVED_FOR_DEMO", "APPROVED_FOR_PRODUCTION"}:
                errors.append("APPROVED_PROCEDURE_SOURCE_NOT_APPROVED")

    split_procedures: dict[str, set[str]] = {"TRAIN": set(), "DEV": set(), "TEST": set()}
    for question in questions.values():
        procedure_id = question.get("procedure_id")
        source_ids = question.get("gold_source_ids", [])
        fragment_ids = question.get("gold_fragment_ids", [])
        if procedure_id is not None and procedure_id not in procedures:
            errors.append("GOLD_PROCEDURE_REFERENCE")
        if not isinstance(source_ids, list) or not set(source_ids) <= sources.keys():
            errors.append("GOLD_SOURCE_REFERENCE")
        if not isinstance(fragment_ids, list) or not set(fragment_ids) <= fragments.keys():
            errors.append("GOLD_FRAGMENT_REFERENCE")
        if isinstance(procedure_id, str) and any(
            fragments[item].get("procedure_id") != procedure_id for item in fragment_ids
        ):
            errors.append("GOLD_FRAGMENT_WRONG_PROCEDURE")
        if question.get("expected_status") == "ANSWER" and (
            not source_ids or not fragment_ids or not question.get("expected_points")
        ):
            errors.append("GOLD_ANSWER_EVIDENCE_REQUIRED")
        if question.get("expected_status") == "INSUFFICIENT_DATA" and (
            procedure_id is not None or source_ids or fragment_ids
        ):
            errors.append("GOLD_INSUFFICIENT_MUST_BE_UNBOUND")
        split = question.get("split")
        if isinstance(procedure_id, str) and split in split_procedures:
            split_procedures[split].add(procedure_id)
        gate(
            question.get("reviewer_role") not in {None, "PENDING_SECOND_REVIEW"}
            and question.get("reviewer_role") != question.get("author_role"),
            "GOLD_REVIEW_PENDING",
            mode,
            errors,
            warnings,
        )
    if (
        split_procedures["TRAIN"] & split_procedures["DEV"]
        or split_procedures["TRAIN"] & split_procedures["TEST"]
        or split_procedures["DEV"] & split_procedures["TEST"]
    ):
        errors.append("GOLD_SPLIT_PROCEDURE_LEAKAGE")

    report = {
        "status": "PASS" if not errors else "FAIL",
        "mode": mode,
        "schema_version": SCHEMA_VERSION,
        "dataset_version_count": len(dataset_versions),
        "counts": {label: len(rows) for label, rows in loaded.items()},
        "errors": dict(sorted(Counter(errors).items())),
        "warnings": dict(sorted(Counter(warnings).items())),
        "pii_scan": "PASS"
        if not any(code.startswith("SENSITIVE_PATTERN") for code in errors)
        else "FAIL",
        "schema_validation": "PASS"
        if not any(code.startswith("SCHEMA_") for code in errors)
        else "FAIL",
        "reference_validation": "PASS"
        if not any("REFERENCE" in code for code in errors)
        else "FAIL",
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--schema", type=Path, required=True)
    parser.add_argument("--mode", choices=("preflight", "publish"), default="preflight")
    parser.add_argument("--expected-source-count", type=int)
    parser.add_argument("--workbook", type=Path)
    args = parser.parse_args()
    report = validate_dataset(
        args.dataset.resolve(),
        args.schema.resolve(),
        mode=args.mode,
        expected_source_count=args.expected_source_count,
        workbook_path=args.workbook.resolve() if args.workbook else None,
    )
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
