"""Build and validate a private, procedure-disjoint G5 SFT bundle.

Only the reviewed G4 DEV file is accepted. Locked TEST files are rejected by
filename and are never opened. Rendered variants change distractor ordering;
they are not reported as independent business facts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from g3_pipeline.common import canonical_json, file_sha256, write_json, write_jsonl
from g3_pipeline.g4_tu_validator import FIELD_SECTIONS
from g3_pipeline.validator import load_jsonl

from . import SFT_MANIFEST_VERSION, SFT_SCHEMA_VERSION

ROOT = Path(__file__).resolve().parents[3]


def _private_output(path: Path) -> Path:
    resolved = path.resolve()
    allowed = (
        (ROOT / "training" / "output").resolve(),
        (ROOT / "evaluation" / "reports").resolve(),
    )
    if not any(resolved.is_relative_to(root) for root in allowed):
        raise ValueError("G5_PRIVATE_OUTPUT_REQUIRED")
    return resolved


def _evidence(fragment: dict[str, Any], source: dict[str, Any], title: str) -> dict[str, Any]:
    jurisdiction = source.get("jurisdiction")
    if isinstance(jurisdiction, dict):
        jurisdiction = (
            ", ".join(
                str(value) for key, value in jurisdiction.items() if key != "country_code" and value
            )
            or None
        )
    return {
        "fragment_id": fragment["fragment_id"],
        "source_id": fragment["source_id"],
        "procedure_id": fragment["procedure_id"],
        "section_type": fragment["section_type"],
        "title": title,
        "text": fragment["text"],
        "jurisdiction": jurisdiction,
        "effective_from": source.get("effective_from"),
        "effective_to": source.get("effective_to"),
        "validity_status": source.get("validity_status", "UNKNOWN"),
    }


def _target(evidence: list[dict[str, Any]]) -> dict[str, Any]:
    answer = "Theo nguồn đã duyệt:\n" + "\n".join(
        f"- {' '.join(item['text'].split())}" for item in evidence
    )
    if len(answer) > 8_000:
        raise ValueError("SFT_TARGET_TOO_LONG")
    return {
        "answer": answer,
        "status": "ANSWER",
        "cited_fragment_ids": [item["fragment_id"] for item in evidence],
        "missing_information": [],
    }


def build_sft_bundle(dataset_dir: Path, dev_path: Path, output_dir: Path, *, variants: int = 4):
    if dev_path.name != "scenario_dev.jsonl" or "test" in dev_path.name.casefold():
        raise ValueError("G5_SFT_DEV_ONLY")
    if not 1 <= variants <= 8:
        raise ValueError("G5_SFT_VARIANTS_INVALID")
    errors: list[str] = []
    scenarios = load_jsonl(dev_path, errors)
    sources = load_jsonl(dataset_dir / "source_manifest.jsonl", errors)
    procedures = load_jsonl(dataset_dir / "normalized/procedures.jsonl", errors)
    fragments = load_jsonl(dataset_dir / "normalized/fragments.jsonl", errors)
    if errors or not scenarios:
        raise ValueError("G5_SFT_INPUT_INVALID")
    if any(
        row.get("split") != "DEV"
        or row.get("contains_pii") is not False
        or row.get("review", {}).get("status") != "APPROVED"
        for row in scenarios
    ):
        raise ValueError("G5_SFT_REVIEWED_DEV_REQUIRED")

    source_by_id = {row["source_id"]: row for row in sources}
    procedure_by_id = {row["procedure_id"]: row for row in procedures}
    fragment_by_id = {row["fragment_id"]: row for row in fragments}
    corpus_versions = {row.get("dataset_version") for row in [*sources, *procedures, *fragments]}
    scenario_versions = {row.get("dataset_version") for row in scenarios}
    if len(corpus_versions) != 1 or scenario_versions != corpus_versions:
        raise ValueError("G5_SFT_DATASET_VERSION_MISMATCH")
    procedure_ids = sorted({row["procedure_id"] for row in scenarios})
    if len(procedure_ids) < 3:
        raise ValueError("G5_SFT_PROCEDURE_SPLIT_TOO_SMALL")
    validation_count = max(1, round(len(procedure_ids) * 0.25))
    validation_ids = set(procedure_ids[-validation_count:])

    rows: list[dict[str, Any]] = []
    base_counts: Counter[str] = Counter()
    for scenario in sorted(scenarios, key=lambda item: item["scenario_id"]):
        if scenario["expected_status"] != "ANSWER" or not scenario["gold_fragment_ids"]:
            continue
        procedure_id = scenario["procedure_id"]
        procedure = procedure_by_id.get(procedure_id)
        if not procedure:
            raise ValueError("G5_SFT_PROCEDURE_REFERENCE")
        gold_ids = scenario["gold_fragment_ids"]
        gold = [fragment_by_id.get(fragment_id) for fragment_id in gold_ids]
        if any(item is None for item in gold):
            raise ValueError("G5_SFT_FRAGMENT_REFERENCE")
        if any(
            item["procedure_id"] != procedure_id
            or item["section_type"] != FIELD_SECTIONS[scenario["field_expected"]]
            for item in gold
        ):
            raise ValueError("G5_SFT_GOLD_BINDING")
        distractors = [
            fragment
            for fragment in fragments
            if fragment["procedure_id"] == procedure_id
            and fragment["fragment_id"] not in set(gold_ids)
        ]
        split = "VALIDATION" if procedure_id in validation_ids else "TRAIN"
        base_counts[split] += 1
        for variant in range(variants):
            if distractors:
                distractor_offset = variant % len(distractors)
                rotated = distractors[distractor_offset:] + distractors[:distractor_offset]
            else:
                rotated = []
            selected = [*gold, *rotated[: max(0, 5 - len(gold))]]
            # Rotate the complete evidence list while preserving every gold fragment.
            offset = variant % len(selected)
            selected = selected[offset:] + selected[:offset]
            evidence = [
                _evidence(item, source_by_id[item["source_id"]], procedure["title"])
                for item in selected
            ]
            gold_evidence = [item for item in evidence if item["fragment_id"] in set(gold_ids)]
            rows.append(
                {
                    "schema_version": SFT_SCHEMA_VERSION,
                    "example_id": f"{scenario['scenario_id']}:v{variant + 1}",
                    "base_scenario_id": scenario["scenario_id"],
                    "dataset_version": scenario["dataset_version"],
                    "split": split,
                    "procedure_id": procedure_id,
                    "field": scenario["field_expected"],
                    "query": scenario["question"],
                    "evidence": evidence,
                    "target": _target(gold_evidence),
                    "review": {
                        "source": "G4_REVIEWED_DEV",
                        "status": "APPROVED",
                        "reviewer_role": scenario["review"]["reviewer_role"],
                    },
                }
            )

    train = [row for row in rows if row["split"] == "TRAIN"]
    validation = [row for row in rows if row["split"] == "VALIDATION"]
    if not train or not validation:
        raise ValueError("G5_SFT_EMPTY_SPLIT")
    output_dir.mkdir(parents=True, exist_ok=True)
    train_path = output_dir / "train.jsonl"
    validation_path = output_dir / "validation.jsonl"
    write_jsonl(train_path, train, "example_id")
    write_jsonl(validation_path, validation, "example_id")
    manifest = {
        "schema_version": SFT_MANIFEST_VERSION,
        "dataset_version": scenarios[0]["dataset_version"],
        "split_strategy": "PROCEDURE_ID_DISJOINT_WITHIN_REVIEWED_DEV",
        "source_dev_sha256": file_sha256(dev_path),
        "source_corpus_sha256": hashlib.sha256(
            canonical_json(
                {
                    "sources": file_sha256(dataset_dir / "source_manifest.jsonl"),
                    "procedures": file_sha256(dataset_dir / "normalized/procedures.jsonl"),
                    "fragments": file_sha256(dataset_dir / "normalized/fragments.jsonl"),
                }
            ).encode("utf-8")
        ).hexdigest(),
        "base_scenarios": dict(sorted(base_counts.items())),
        "rendered_examples": {"TRAIN": len(train), "VALIDATION": len(validation)},
        "procedure_count": {
            "TRAIN": len({row["procedure_id"] for row in train}),
            "VALIDATION": len({row["procedure_id"] for row in validation}),
        },
        "rendered_variants_per_base_scenario": variants,
        "independence_note": "Rendered variants are not independent business facts.",
        "test_data_used": False,
        "files": {
            "train": {"path": "train.jsonl", "sha256": file_sha256(train_path)},
            "validation": {
                "path": "validation.jsonl",
                "sha256": file_sha256(validation_path),
            },
        },
        "release_status": "TRAINING_CANDIDATE_REVIEWED_SOURCE",
    }
    write_json(output_dir / "manifest.json", manifest)
    return manifest


def validate_sft_bundle(bundle_dir: Path) -> dict[str, Any]:
    errors: Counter[str] = Counter()
    try:
        manifest = json.loads((bundle_dir / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {"status": "FAIL", "errors": {"MANIFEST_INVALID": 1}}
    rows: dict[str, list[dict[str, Any]]] = {}
    for split, filename in (("TRAIN", "train.jsonl"), ("VALIDATION", "validation.jsonl")):
        load_errors: list[str] = []
        rows[split] = load_jsonl(bundle_dir / filename, load_errors)
        errors.update(load_errors)
        if file_sha256(bundle_dir / filename) != manifest.get("files", {}).get(
            split.casefold(), {}
        ).get("sha256"):
            errors["FILE_HASH_MISMATCH"] += 1
        for row in rows[split]:
            if row.get("schema_version") != SFT_SCHEMA_VERSION or row.get("split") != split:
                errors["ROW_CONTRACT_INVALID"] += 1
            evidence = row.get("evidence", [])
            target = row.get("target", {})
            evidence_ids = {item.get("fragment_id") for item in evidence}
            cited = target.get("cited_fragment_ids", [])
            status = target.get("status")
            if status == "ANSWER" and (not cited or not set(cited) <= evidence_ids):
                errors["TARGET_CITATION_INVALID"] += 1
            elif status == "INSUFFICIENT_DATA" and (cited or not target.get("missing_information")):
                errors["TARGET_ABSTENTION_INVALID"] += 1
            elif status not in {"ANSWER", "INSUFFICIENT_DATA"}:
                errors["TARGET_STATUS_INVALID"] += 1
            if row.get("review", {}).get("status") != "APPROVED":
                errors["ROW_NOT_REVIEWED"] += 1
    ids = [row.get("example_id") for values in rows.values() for row in values]
    if len(ids) != len(set(ids)):
        errors["EXAMPLE_ID_DUPLICATE"] += 1
    train_procedures = {row.get("procedure_id") for row in rows["TRAIN"]}
    validation_procedures = {row.get("procedure_id") for row in rows["VALIDATION"]}
    if train_procedures & validation_procedures:
        errors["PROCEDURE_SPLIT_LEAKAGE"] += 1
    row_versions = {row.get("dataset_version") for values in rows.values() for row in values}
    if row_versions != {manifest.get("dataset_version")}:
        errors["DATASET_VERSION_MISMATCH"] += 1
    if manifest.get("test_data_used") is not False:
        errors["TEST_DATA_PROHIBITED"] += 1
    return {
        "status": "PASS" if not errors else "FAIL",
        "counts": {split: len(values) for split, values in rows.items()},
        "procedure_counts": {
            "TRAIN": len(train_procedures),
            "VALIDATION": len(validation_procedures),
        },
        "errors": dict(sorted(errors.items())),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build")
    build.add_argument("--dataset", type=Path, required=True)
    build.add_argument("--dev", type=Path, required=True)
    build.add_argument("--output", type=Path, required=True)
    build.add_argument("--variants", type=int, default=4)
    validate = sub.add_parser("validate")
    validate.add_argument("--bundle", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "build":
            result = build_sft_bundle(
                args.dataset.resolve(),
                args.dev.resolve(),
                _private_output(args.output),
                variants=args.variants,
            )
            public = {
                "status": "PASS",
                "schema_version": result["schema_version"],
                "base_scenarios": result["base_scenarios"],
                "rendered_examples": result["rendered_examples"],
                "procedure_count": result["procedure_count"],
                "test_data_used": result["test_data_used"],
            }
        else:
            public = validate_sft_bundle(args.bundle.resolve())
        print(json.dumps(public, ensure_ascii=True, sort_keys=True))
        return 0 if public["status"] == "PASS" else 2
    except Exception:
        print('{"status":"FAIL","error":"G5_SFT_PIPELINE_FAILED"}')
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
