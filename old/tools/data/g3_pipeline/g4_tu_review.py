#!/usr/bin/env python3
"""Record the final human-delegated review and lock a private TEST_V2 bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from g3_pipeline.g4_tu_validator import validate_bundle


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def _encode_jsonl(rows: list[dict[str, Any]]) -> bytes:
    return "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows
    ).encode("utf-8")


def _encode_json(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def review_and_lock(
    dataset_dir: Path,
    scenario_schema_path: Path,
    manifest_schema_path: Path,
    *,
    reviewer_role: str,
    reviewed_at: str,
) -> dict[str, Any]:
    if not reviewer_role.strip() or reviewer_role == "DATA_OWNER_TU":
        raise ValueError("INDEPENDENT_REVIEWER_REQUIRED")
    preflight = validate_bundle(
        dataset_dir,
        scenario_schema_path,
        manifest_schema_path,
        mode="preflight",
    )
    if preflight["status"] != "PASS":
        raise ValueError("PREFLIGHT_REQUIRED")

    bundle_dir = dataset_dir / "g4_eval"
    dev_path = bundle_dir / "scenario_dev.jsonl"
    test_path = bundle_dir / "scenario_test_v2.jsonl"
    manifest_path = bundle_dir / "scenario_manifest.json"
    original = {
        dev_path: dev_path.read_bytes(),
        test_path: test_path.read_bytes(),
        manifest_path: manifest_path.read_bytes(),
    }

    dev = _load_jsonl(dev_path)
    test_v2 = _load_jsonl(test_path)
    for row in dev + test_v2:
        review = row["review"]
        review["status"] = "APPROVED"
        review["reviewer_role"] = reviewer_role
        review["reviewed_at"] = reviewed_at
        if review["flags"] and row["expected_status"] == "INSUFFICIENT_DATA":
            review["decision"] = "APPROVED_AS_INSUFFICIENT_DATA"
        elif review["flags"]:
            review["decision"] = "APPROVED_FOR_RAW_TEXT_ONLY"
        else:
            review["decision"] = "APPROVED_AGAINST_NORMALIZED_SOURCE"

    dev_bytes = _encode_jsonl(dev)
    test_bytes = _encode_jsonl(test_v2)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["review_status"] = "LOCKED"
    manifest["reviewer_role"] = reviewer_role
    manifest["reviewed_at"] = reviewed_at
    manifest["test_v2_lock"]["status"] = "LOCKED"
    manifest["sha256"] = {"dev": _sha256(dev_bytes), "test_v2": _sha256(test_bytes)}
    manifest_bytes = _encode_json(manifest)

    try:
        dev_path.write_bytes(dev_bytes)
        test_path.write_bytes(test_bytes)
        manifest_path.write_bytes(manifest_bytes)
        published = validate_bundle(
            dataset_dir,
            scenario_schema_path,
            manifest_schema_path,
            mode="publish",
        )
        if published["status"] != "PASS":
            raise ValueError("PUBLISH_VALIDATION_FAILED")
    except Exception:
        for path, payload in original.items():
            path.write_bytes(payload)
        raise
    return published


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--scenario-schema", type=Path, required=True)
    parser.add_argument("--manifest-schema", type=Path, required=True)
    parser.add_argument("--reviewer-role", required=True)
    parser.add_argument("--reviewed-at", required=True)
    parser.add_argument("--acknowledge-test-lock", action="store_true")
    args = parser.parse_args()
    if not args.acknowledge_test_lock:
        print('{"status":"FAIL","error":"TEST_LOCK_ACKNOWLEDGEMENT_REQUIRED"}')
        return 2
    try:
        report = review_and_lock(
            args.dataset.resolve(),
            args.scenario_schema.resolve(),
            args.manifest_schema.resolve(),
            reviewer_role=args.reviewer_role,
            reviewed_at=args.reviewed_at,
        )
    except Exception:
        print('{"status":"FAIL","error":"G4_REVIEW_LOCK_FAILED"}')
        return 2
    print(json.dumps(report, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
