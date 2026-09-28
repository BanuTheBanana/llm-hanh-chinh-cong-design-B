"""Create a reviewed, leakage-aware demo subset from private G3 normalized data."""

from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .builder import BuildError, choose_priority_procedures
from .common import canonical_json, file_sha256, sha256_text, write_json, write_jsonl
from .validator import FILES, validate_dataset

REVIEW_STATUS = "APPROVED_FOR_DEMO"


@dataclass(frozen=True)
class ReleaseResult:
    dataset_dir: Path
    dataset_version: str
    report: dict[str, Any]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    try:
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise BuildError("PRIVATE_DATASET_READ_FAILED") from exc


def ensure_private_path(path: Path) -> None:
    if "company_private" not in {part.casefold() for part in path.resolve().parts}:
        raise BuildError("PRIVATE_DATASET_PATH_REQUIRED")


def reviewed(status: str, role: str, reviewed_at: str, note: str) -> dict[str, Any]:
    return {
        "status": status,
        "reviewer_role": role,
        "reviewed_at": reviewed_at,
        "note": note,
    }


def validate_review_timestamp(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise BuildError("REVIEWED_AT_INVALID") from exc
    if parsed.tzinfo is None:
        raise BuildError("REVIEWED_AT_TIMEZONE_REQUIRED")
    return value


def release_demo_subset(
    source_dir: Path,
    output_root: Path,
    schema_path: Path,
    *,
    reviewer_role: str,
    reviewed_at: str,
    demo_size: int = 10,
) -> ReleaseResult:
    source_dir = source_dir.resolve()
    output_root = output_root.resolve()
    ensure_private_path(source_dir)
    ensure_private_path(output_root)
    if not reviewer_role.strip() or reviewer_role == "PENDING_SECOND_REVIEW":
        raise BuildError("REVIEWER_ROLE_INVALID")
    reviewed_at = validate_review_timestamp(reviewed_at)
    if not 2 <= demo_size <= 20:
        raise BuildError("DEMO_SIZE_OUT_OF_RANGE")

    preflight = validate_dataset(source_dir, schema_path.resolve(), mode="preflight")
    if preflight["status"] != "PASS":
        raise BuildError("SOURCE_PREFLIGHT_FAILED")

    groups = {label: read_jsonl(source_dir / relative) for label, (relative, _) in FILES.items()}
    original_version = next(
        (
            row["dataset_version"]
            for rows in groups.values()
            for row in rows
            if "dataset_version" in row
        ),
        None,
    )
    if not original_version:
        raise BuildError("SOURCE_DATASET_VERSION_MISSING")

    open_conflict_procedures = {
        row["candidate_procedure_id"] for row in groups["conflicts"] if row["status"] == "OPEN"
    }
    eligible = [
        row
        for row in groups["procedures"]
        if row["procedure_id"] not in open_conflict_procedures
        and row["review"]["status"] == "PENDING_REVIEW"
    ]
    selected = choose_priority_procedures(eligible, demo_size)
    if len(selected) != demo_size:
        raise BuildError("NOT_ENOUGH_ELIGIBLE_PROCEDURES")
    selected_ids = {row["procedure_id"] for row in selected}
    selected_sources = {source_id for row in selected for source_id in row["source_ids"]}
    release_version = f"{original_version}-demo{demo_size}-v1"
    release_dir = output_root / release_version
    note = "Approved for local G3 demo only; not approved for production."

    sources: list[dict[str, Any]] = []
    for original in groups["sources"]:
        if original["source_id"] not in selected_sources:
            continue
        row = deepcopy(original)
        row["dataset_version"] = release_version
        row["source_type"] = "COMPANY_APPROVED_INTERNAL"
        row["last_verified_at"] = reviewed_at
        row["review"] = reviewed(REVIEW_STATUS, reviewer_role, reviewed_at, note)
        sources.append(row)

    procedures: list[dict[str, Any]] = []
    for original in selected:
        row = deepcopy(original)
        row["dataset_version"] = release_version
        row["version"] = "demo-v1"
        row["review"] = reviewed(REVIEW_STATUS, reviewer_role, reviewed_at, note)
        procedures.append(row)

    fragments: list[dict[str, Any]] = []
    for original in groups["fragments"]:
        if original["procedure_id"] not in selected_ids:
            continue
        row = deepcopy(original)
        row["dataset_version"] = release_version
        fragments.append(row)

    ordered_ids = sorted(
        selected_ids,
        key=lambda procedure_id: sha256_text(f"{release_version}:{procedure_id}"),
    )
    test_size = max(1, round(demo_size * 0.2))
    test_ids = set(ordered_ids[-test_size:])
    split_by_id = {
        procedure_id: "TEST" if procedure_id in test_ids else "DEV" for procedure_id in ordered_ids
    }
    questions: list[dict[str, Any]] = []
    for original in groups["questions"]:
        procedure_id = original["procedure_id"]
        if procedure_id is not None and procedure_id not in selected_ids:
            continue
        row = deepcopy(original)
        row["dataset_version"] = release_version
        if procedure_id is not None:
            row["split"] = split_by_id[procedure_id]
        row["reviewer_role"] = reviewer_role
        questions.append(row)
    question_procedures = {
        row["procedure_id"] for row in questions if row["procedure_id"] is not None
    }
    if question_procedures != selected_ids:
        raise BuildError("SELECTED_PROCEDURE_MISSING_GOLD")

    output = {
        "sources": sources,
        "procedures": procedures,
        "fragments": fragments,
        "conflicts": [],
        "questions": questions,
    }
    for label, (relative, key) in FILES.items():
        write_jsonl(release_dir / relative, output[label], key)

    test_questions = sorted(
        (row for row in questions if row["split"] == "TEST"),
        key=lambda row: row["question_id"],
    )
    test_lock = {
        "dataset_version": release_version,
        "split": "TEST",
        "procedure_count": len(test_ids),
        "question_count": len(test_questions),
        "content_sha256": sha256_text(canonical_json(test_questions)),
        "policy": "Do not tune prompts, retrieval or model on TEST outcomes.",
    }
    write_json(release_dir / "reports/test-lock.json", test_lock)

    publish = validate_dataset(
        release_dir,
        schema_path.resolve(),
        mode="publish",
        expected_source_count=len(sources),
    )
    if publish["status"] != "PASS":
        raise BuildError("DEMO_PUBLISH_GATE_FAILED")
    file_hashes = {
        label: file_sha256(release_dir / relative) for label, (relative, _) in FILES.items()
    }
    report = {
        "schema_version": "g3-data-v1",
        "dataset_version": release_version,
        "source_dataset_version": original_version,
        "review_status": REVIEW_STATUS,
        "source_count": len(sources),
        "procedure_count": len(procedures),
        "fragment_count": len(fragments),
        "conflict_open_count": 0,
        "question_count_by_split": {
            split: sum(row["split"] == split for row in questions) for split in ("DEV", "TEST")
        },
        "procedure_count_by_split": {
            "DEV": demo_size - test_size,
            "TEST": test_size,
        },
        "test_lock_sha256": test_lock["content_sha256"],
        "publish_validation": "PASS",
        "file_sha256": file_hashes,
    }
    write_json(release_dir / "reports/demo-release.json", report)
    return ReleaseResult(release_dir, release_version, report)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--schema", type=Path, required=True)
    parser.add_argument("--reviewer-role", required=True)
    parser.add_argument("--reviewed-at", required=True)
    parser.add_argument("--demo-size", type=int, default=10)
    args = parser.parse_args()
    try:
        result = release_demo_subset(
            args.source,
            args.output_root,
            args.schema,
            reviewer_role=args.reviewer_role,
            reviewed_at=args.reviewed_at,
            demo_size=args.demo_size,
        )
    except (BuildError, OSError, ValueError):
        print('{"status":"FAIL","error":"DEMO_RELEASE_FAILED"}')
        return 1
    summary = {
        "status": "PASS",
        "dataset_version": result.dataset_version,
        "counts": {
            "sources": result.report["source_count"],
            "procedures": result.report["procedure_count"],
            "fragments": result.report["fragment_count"],
            "dev_questions": result.report["question_count_by_split"]["DEV"],
            "test_questions": result.report["question_count_by_split"]["TEST"],
        },
        "test_lock_sha256": result.report["test_lock_sha256"],
    }
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
