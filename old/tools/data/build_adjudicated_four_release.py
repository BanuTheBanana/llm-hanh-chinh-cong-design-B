"""Build a non-destructive, field-wise 38-procedure candidate from controlled-v1.

This is a controlled-demo candidate, not a legal approval. Unresolved fields are
withheld rather than answered from a conflicting source. Original workbook and
the 34-procedure release are never modified.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import shutil
from pathlib import Path

BASE_VERSION = "company-tthc-9c38dde8-v1-controlled-v1"
NEW_VERSION = "company-tthc-9c38dde8-v1-adjudicated-v1"
REVIEWED_AT = "2026-09-20T00:00:00+07:00"
CANONICAL_CONSTRUCTION_PROCEDURE_ID = "d2_title_c98b4aa39036"
PREFERRED_ALIASES = {
    "d2_title_10ed2a9ea4a7": [
        "Hỗ trợ chi phí hỏa táng",
        "Xin hỗ trợ chi phí hỏa táng",
    ],
}
FIELDS = (
    "applicant_scope",
    "receiving_authority",
    "submission_methods",
    "required_documents",
    "steps",
    "fees",
    "processing_times",
    "legal_bases",
)
SECTION = {
    "receiving_authority": "RECEIVING_AUTHORITY",
    "required_documents": "REQUIRED_DOCUMENTS",
    "submission_methods": "SUBMISSION_METHODS",
    "fees": "FEES",
    "processing_times": "PROCESSING_TIME",
}
# Row selection is per field. None means the evidence is still disputed or
# insufficient; it must not enter the serving fragment allowlist.
DECISIONS = {
    "d2_title_3cc26cfe53d5": {
        "receiving_authority": 24,
        "required_documents": 24,
        "submission_methods": 24,
        "fees": 24,
        "processing_times": 24,
    },
    "d2_title_7677bda9d6bd": {
        "receiving_authority": 12,
        "required_documents": 16,
        "submission_methods": 12,
        "fees": 12,
    },
    "d2_title_85fb93f4cc41": {
        "receiving_authority": 21,
        "required_documents": 21,
        "submission_methods": 21,
        "fees": 21,
        "processing_times": 21,
    },
    "d2_title_f29de859e25e": {
        "receiving_authority": 15,
        "required_documents": 20,
        "submission_methods": 15,
        "fees": 15,
    },
}
NOTES = {
    "d2_title_3cc26cfe53d5": (
        "Row 24 is the detailed canonical description; row 10 is retained only as provenance."
    ),
    "d2_title_7677bda9d6bd": (
        "Row 16 gives the common document list. Row 12's extra kinship statement "
        "and 17-working-day wording remain unverified; row 16's five days is not "
        "used as a whole-procedure duration."
    ),
    "d2_title_85fb93f4cc41": (
        "Row 21 is canonical. Row 9's separate CCCD requirement is not promoted "
        "to a required document."
    ),
    "d2_title_f29de859e25e": (
        "Row 20 preserves the distinct benefit-branch document lists. Rows 15/20 "
        "do not establish one unambiguous whole-procedure duration."
    ),
}


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def write_jsonl(path: Path, rows: list[dict], key: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows.sort(key=lambda row: row[key])
    path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
            for row in rows
        ),
        encoding="utf-8",
        newline="\n",
    )


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def selected_fragment(
    fragments: list[dict], procedure_id: str, field: str, row_number: int
) -> dict:
    hits = [
        f
        for f in fragments
        if f["procedure_id"] == procedure_id
        and f["section_type"] == SECTION[field]
        and f["source_locator"]["row_number"] == row_number
    ]
    if len(hits) != 1:
        raise ValueError(
            f"expected one {field} fragment for {procedure_id} row {row_number}; got {len(hits)}"
        )
    return hits[0]


def value_for(field: str, text: str) -> list:
    if field in {"receiving_authority", "required_documents"}:
        return [text]
    if field == "submission_methods":
        if text.strip().casefold() != "cả hai":
            raise ValueError("submission method cannot be normalized")
        return ["DIRECT", "ONLINE"]
    if field == "fees":
        if text.strip().casefold() not in {"không", "không đồng"}:
            raise ValueError("fee cannot be normalized to zero")
        return [{"amount_vnd": 0, "condition": None, "raw_text": text}]
    if field == "processing_times":
        match = re.match(
            r"(?i)^(?:mười\s*)?\(?([0-9]+)\)?\s+ngày làm việc"
            r"(?:, kể từ ngày nhận đủ hồ sơ và hợp lệ;?)?$",
            text.strip(),
        )
        if not match:
            raise ValueError("processing time cannot be parsed without an assumption")
        days = int(match.group(1))
        return [
            {
                "raw_text": text,
                "min_business_days": days,
                "max_business_days": days,
                "condition": None,
            }
        ]
    raise ValueError(field)


def approve_construction_processing_time(
    procedures: list[dict],
    fragments: list[dict],
    decisions: list[dict],
    source_fragments: list[dict],
) -> tuple[list[dict], list[dict], list[dict]]:
    """Approve row 28's recorded 15-day value without deleting either source row."""

    canonical = next(
        p for p in procedures if p["procedure_id"] == CANONICAL_CONSTRUCTION_PROCEDURE_ID
    )
    canonical["review"] = {
        "status": "APPROVED_FOR_DEMO",
        "reviewer_role": "PROJECT_OWNER_ADJUDICATION",
        "reviewed_at": REVIEWED_AT,
        "note": (
            "Workbook row 28 is the serving-time preferred construction-permit "
            "record. Row 26 remains unchanged and traceable in the corpus."
        ),
    }
    fragment = copy.deepcopy(
        next(
        f
        for f in source_fragments
            if f["procedure_id"] == CANONICAL_CONSTRUCTION_PROCEDURE_ID
            and f["section_type"] == "PROCESSING_TIME"
            and f["source_locator"]["row_number"] == 28
        )
    )
    fragment["dataset_version"] = NEW_VERSION
    days = int(float(fragment["text"]))
    normalized_time = f"{days} ngày làm việc"
    fragment["text"] = normalized_time
    fragment["content_sha256"] = hashlib.sha256(normalized_time.encode("utf-8")).hexdigest()
    canonical["processing_times"] = [
        {
            "raw_text": normalized_time,
            "min_business_days": days,
            "max_business_days": days,
            "condition": None,
        }
    ]
    canonical["field_evidence"]["processing_times"] = [fragment["fragment_id"]]
    canonical["missing_fields"] = [
        field for field in canonical["missing_fields"] if field != "processing_times"
    ]
    fragments = [
        f
        for f in fragments
        if not (
            f["procedure_id"] == CANONICAL_CONSTRUCTION_PROCEDURE_ID
            and f["section_type"] == "PROCESSING_TIME"
        )
    ]
    fragments.append(fragment)
    decisions = [
        d
        for d in decisions
        if not (
            d["procedure_id"] == CANONICAL_CONSTRUCTION_PROCEDURE_ID
            and d["field"] == "processing_times"
        )
    ]
    decisions.append(
        {
            "dataset_version": NEW_VERSION,
            "decision_status": "APPROVED",
            "field": "processing_times",
            "fragment_ids": [fragment["fragment_id"]],
            "procedure_id": CANONICAL_CONSTRUCTION_PROCEDURE_ID,
            "reason_code": "PROJECT_OWNER_PREFERRED_ROW_28",
            "source_ids": canonical["source_ids"],
        }
    )
    return procedures, fragments, decisions


def add_reviewed_aliases(procedures: list[dict]) -> None:
    """Add project-owner synonyms without modifying or deleting workbook rows."""

    procedure_map = {procedure["procedure_id"]: procedure for procedure in procedures}
    for procedure_id, aliases in PREFERRED_ALIASES.items():
        procedure = procedure_map[procedure_id]
        procedure["aliases"] = sorted(set([*procedure["aliases"], *aliases]))


def build(baseline: Path, reviewed: Path, output: Path) -> None:
    if output.exists():
        current_manifest_path = output / "release-manifest.json"
        if not current_manifest_path.is_file():
            raise FileExistsError(f"refuse to overwrite non-release directory {output}")
        current_manifest = json.loads(current_manifest_path.read_text(encoding="utf-8"))
        if current_manifest.get("dataset_version") != NEW_VERSION:
            raise ValueError("refuse to overwrite a different dataset version")
    baseline_manifest = json.loads((baseline / "release-manifest.json").read_text(encoding="utf-8"))
    if baseline_manifest["dataset_version"] != BASE_VERSION:
        raise ValueError("unexpected baseline release")
    old_sources = read_jsonl(baseline / "source_manifest.jsonl")
    old_procedures = read_jsonl(baseline / "normalized/procedures.jsonl")
    old_fragments = read_jsonl(baseline / "normalized/fragments.jsonl")
    old_decisions = read_jsonl(baseline / "field-decisions.jsonl")
    source_map = {s["source_id"]: s for s in read_jsonl(reviewed / "source_manifest.jsonl")}
    procedure_map = {
        p["procedure_id"]: p for p in read_jsonl(reviewed / "normalized/procedures.jsonl")
    }
    fragments = read_jsonl(reviewed / "normalized/fragments.jsonl")
    conflicts = read_jsonl(reviewed / "quarantine/conflicts.jsonl")
    if {c["candidate_procedure_id"] for c in conflicts if c["status"] == "OPEN"} != set(DECISIONS):
        raise ValueError("the reviewed conflict set has changed")

    sources = copy.deepcopy(old_sources)
    procedures = copy.deepcopy(old_procedures)
    serving_fragments = copy.deepcopy(old_fragments)
    decisions = [
        copy.deepcopy(row) for row in old_decisions if row["procedure_id"] not in DECISIONS
    ]
    included_sources = {row["source_id"] for row in sources}
    for group in (sources, procedures, serving_fragments, decisions):
        for row in group:
            row["dataset_version"] = NEW_VERSION

    for procedure_id, chosen_fields in DECISIONS.items():
        procedure = copy.deepcopy(procedure_map[procedure_id])
        for source_id in procedure["source_ids"]:
            if source_id not in included_sources:
                source = copy.deepcopy(source_map[source_id])
                source["dataset_version"] = NEW_VERSION
                source["review"] = {
                    "status": "APPROVED_FOR_DEMO",
                    "reviewer_role": "PROJECT_OWNER_ADJUDICATION",
                    "reviewed_at": REVIEWED_AT,
                    "note": (
                        "Accepted for traceable field-wise controlled candidate; "
                        "not blanket approval of every source cell."
                    ),
                }
                sources.append(source)
                included_sources.add(source_id)
        procedure["dataset_version"] = NEW_VERSION
        procedure["review"] = {
            "status": "APPROVED_FOR_DEMO",
            "reviewer_role": "PROJECT_OWNER_ADJUDICATION",
            "reviewed_at": REVIEWED_AT,
            "note": NOTES[procedure_id],
        }
        for field in FIELDS:
            procedure[field] = []
            procedure["field_evidence"][field] = []
            if field not in procedure["missing_fields"]:
                procedure["missing_fields"].append(field)
            status, reason, fragment_ids = "INSUFFICIENT_DATA", "UNRESOLVED_OR_NOT_IN_SOURCE", []
            if field in chosen_fields:
                fragment = copy.deepcopy(
                    selected_fragment(fragments, procedure_id, field, chosen_fields[field])
                )
                fragment["dataset_version"] = NEW_VERSION
                procedure[field] = value_for(field, fragment["text"])
                procedure["field_evidence"][field] = [fragment["fragment_id"]]
                procedure["missing_fields"].remove(field)
                serving_fragments.append(fragment)
                status, reason, fragment_ids = (
                    "APPROVED",
                    "FIELDWISE_SOURCE_ADJUDICATION",
                    [fragment["fragment_id"]],
                )
            decisions.append(
                {
                    "dataset_version": NEW_VERSION,
                    "decision_status": status,
                    "field": field,
                    "fragment_ids": fragment_ids,
                    "procedure_id": procedure_id,
                    "reason_code": reason,
                    "source_ids": sorted(procedure["source_ids"]),
                }
            )
        procedure["missing_fields"] = sorted(set(procedure["missing_fields"]))
        procedures.append(procedure)

    add_reviewed_aliases(procedures)
    procedures, serving_fragments, decisions = approve_construction_processing_time(
        procedures, serving_fragments, decisions, fragments
    )

    output.mkdir(parents=True, exist_ok=True)
    write_jsonl(output / "source_manifest.jsonl", sources, "source_id")
    write_jsonl(output / "normalized/procedures.jsonl", procedures, "procedure_id")
    write_jsonl(output / "normalized/fragments.jsonl", serving_fragments, "fragment_id")
    write_jsonl(output / "field-decisions.jsonl", decisions, "procedure_id")
    write_jsonl(output / "quarantine/conflicts.jsonl", [], "conflict_id")
    write_jsonl(output / "gold/questions.jsonl", [], "question_id")
    closure = read_jsonl(baseline / "review-closure.jsonl")
    for row in closure:
        procedure_id = row["procedure_id"]
        if (
            procedure_id in DECISIONS
            and row.get("original_issue_code") == "OPEN_SOURCE_CONFLICT"
        ):
            row["resolution"] = "RESOLVED_FIELDWISE_PARTIAL"
            row["reviewer_role"] = "PROJECT_OWNER_ADJUDICATION"
            row["reviewed_at"] = REVIEWED_AT
        elif (
            procedure_id in DECISIONS
            and row.get("field") in DECISIONS[procedure_id]
        ):
            row["resolution"] = "APPROVED_FIELDWISE"
            row["reviewer_role"] = "PROJECT_OWNER_ADJUDICATION"
            row["reviewed_at"] = REVIEWED_AT
    write_jsonl(output / "review-closure.jsonl", closure, "procedure_id")
    (output / "schema").mkdir(exist_ok=True)
    shutil.copyfile(
        baseline / "schema/data-contract-v1.schema.json",
        output / "schema/data-contract-v1.schema.json",
    )
    card = (
        "# Field-wise adjudicated controlled candidate\n\n"
        "The original workbook and controlled-v1 remain unchanged. Four formerly "
        "quarantined procedures are present, but only individually selected fields "
        "are answerable. Rows 26 and 28 remain traceable; runtime catalog policy "
        "prefers row 28 for construction-permit questions.\n"
        "For the worship allowance and bereavement allowance procedures, "
        "whole-procedure processing time is withheld.\n"
        "The source rows remain traceable. This release is not evidence of "
        "independent legal review or live government updates.\n"
    )
    (output / "DATA_CARD.md").write_text(card, encoding="utf-8", newline="\n")
    names = [
        "source_manifest.jsonl",
        "normalized/procedures.jsonl",
        "normalized/fragments.jsonl",
        "quarantine/conflicts.jsonl",
        "gold/questions.jsonl",
        "field-decisions.jsonl",
        "review-closure.jsonl",
        "schema/data-contract-v1.schema.json",
        "DATA_CARD.md",
    ]
    artifacts = []
    for name in names:
        path = output / name
        item = {"path": name, "sha256": digest(path), "size_bytes": path.stat().st_size}
        if path.suffix == ".jsonl":
            item["record_count"] = len(read_jsonl(path))
        artifacts.append(item)
    counts = {
        "approved_procedures": len(procedures),
        "approved_sources": len(sources),
        "approved_fragments": len(serving_fragments),
        "field_decisions": len(decisions),
        "review_items_closed": len(closure),
    }
    manifest = {
        "manifest_version": "controlled-corpus-release-v1",
        "dataset_version": NEW_VERSION,
        "status": "READY_FOR_CONTROLLED_RAG",
        "source_scope": "COMPANY_SOURCE_EXHAUSTED",
        "usage_policy": "ALLOWLISTED_FIELDS_ONLY",
        "counts": counts,
        "artifacts": artifacts,
    }
    (output / "release-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps({"output": str(output), **counts}, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--reviewed", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    build(args.baseline.resolve(), args.reviewed.resolve(), args.output.resolve())


if __name__ == "__main__":
    main()
