"""Audit a G3/G4 corpus for the deliberately narrow G5 serving scope.

The command prints counts and hashes only. A detailed report may be written to an
ignored local directory, because procedure identifiers can still reveal company data.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from g3_pipeline.common import file_sha256, write_json
from g3_pipeline.validator import BUSINESS_FIELDS, load_jsonl

ROOT = Path(__file__).resolve().parents[3]


def _private_output(path: Path) -> Path:
    resolved = path.resolve()
    if not resolved.is_relative_to((ROOT / "evaluation" / "reports").resolve()):
        raise ValueError("G5_PRIVATE_OUTPUT_REQUIRED")
    return resolved


def _raw_values(record: dict[str, Any], field: str) -> list[str]:
    values = record.get(field, [])
    if not isinstance(values, list):
        return []
    result: list[str] = []
    for value in values:
        if isinstance(value, str) and value.strip():
            result.append(value.strip())
        elif isinstance(value, dict):
            text = value.get("raw_text")
            if isinstance(text, str) and text.strip():
                result.append(text.strip())
    return result


def audit_scope(dataset_dir: Path) -> dict[str, Any]:
    errors: list[str] = []
    sources = load_jsonl(dataset_dir / "source_manifest.jsonl", errors)
    procedures = load_jsonl(dataset_dir / "normalized/procedures.jsonl", errors)
    fragments = load_jsonl(dataset_dir / "normalized/fragments.jsonl", errors)
    conflicts = load_jsonl(dataset_dir / "quarantine/conflicts.jsonl", errors)
    if errors:
        raise ValueError("G5_SCOPE_INPUT_INVALID")

    source_by_id = {row.get("source_id"): row for row in sources}
    fragment_by_id = {row.get("fragment_id"): row for row in fragments}
    open_conflicts = {
        row.get("candidate_procedure_id") for row in conflicts if row.get("status") == "OPEN"
    }
    details: list[dict[str, Any]] = []
    field_coverage: Counter[str] = Counter()
    categories: Counter[str] = Counter()
    eligible = 0
    for procedure in procedures:
        procedure_id = procedure.get("procedure_id")
        review_status = procedure.get("review", {}).get("status")
        field_evidence = procedure.get("field_evidence", {})
        source_ids = procedure.get("source_ids", [])
        source_approved = bool(source_ids) and all(
            source_by_id.get(source_id, {}).get("review", {}).get("status")
            in {"APPROVED_FOR_DEMO", "APPROVED_FOR_PRODUCTION"}
            for source_id in source_ids
        )
        supported_fields: list[str] = []
        missing_fields: list[str] = []
        for field in BUSINESS_FIELDS:
            ids = field_evidence.get(field, []) if isinstance(field_evidence, dict) else []
            bound = bool(ids) and all(
                fragment_by_id.get(fragment_id, {}).get("procedure_id") == procedure_id
                for fragment_id in ids
            )
            if _raw_values(procedure, field) and bound:
                supported_fields.append(field)
                field_coverage[field] += 1
            else:
                missing_fields.append(field)
        approved = review_status in {"APPROVED_FOR_DEMO", "APPROVED_FOR_PRODUCTION"}
        can_serve = approved and source_approved and procedure_id not in open_conflicts
        eligible += int(can_serve)
        categories[str(procedure.get("category_code", "UNKNOWN"))] += 1
        details.append(
            {
                "procedure_id": procedure_id,
                "category_code": procedure.get("category_code"),
                "review_status": review_status,
                "source_approved": source_approved,
                "open_conflict": procedure_id in open_conflicts,
                "serving_eligible": can_serve,
                "supported_fields": supported_fields,
                "missing_fields": missing_fields,
            }
        )

    versions = {row.get("dataset_version") for row in sources + procedures + fragments}
    return {
        "schema_version": "g5-scope-audit-v1",
        "dataset_version": next(iter(versions)) if len(versions) == 1 else None,
        "corpus_files": {
            "sources_sha256": file_sha256(dataset_dir / "source_manifest.jsonl"),
            "procedures_sha256": file_sha256(dataset_dir / "normalized/procedures.jsonl"),
            "fragments_sha256": file_sha256(dataset_dir / "normalized/fragments.jsonl"),
        },
        "counts": {
            "sources": len(sources),
            "procedures": len(procedures),
            "fragments": len(fragments),
            "open_conflicts": len(open_conflicts),
            "serving_eligible": eligible,
        },
        "categories": dict(sorted(categories.items())),
        "field_coverage": {field: field_coverage[field] for field in BUSINESS_FIELDS},
        "release_decision": "READY_FOR_G5_LIMITED_SCOPE" if eligible else "BLOCKED",
        "procedures": sorted(details, key=lambda item: str(item["procedure_id"])),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        report = audit_scope(args.dataset.resolve())
        if args.output:
            write_json(_private_output(args.output), report)
        public = {key: value for key, value in report.items() if key != "procedures"}
        print(json.dumps(public, ensure_ascii=True, sort_keys=True))
        return 0 if report["release_decision"] != "BLOCKED" else 2
    except Exception:
        print('{"status":"FAIL","error":"G5_SCOPE_AUDIT_FAILED"}')
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
