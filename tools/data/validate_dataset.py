"""Reproducible technical and publish gates for the G2 public demo corpus."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from pathlib import Path
from urllib.parse import urlsplit

ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")
SECRET_PATTERNS = (
    re.compile(r"\bgsk_[A-Za-z0-9_-]{12,}"),
    re.compile(r"\bAQ\.[A-Za-z0-9_-]{12,}"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}"),
)
BUSINESS_FIELDS = (
    "applicant_scope",
    "receiving_authority",
    "submission_methods",
    "required_documents",
    "steps",
    "fees",
    "processing_time",
    "legal_bases",
)
ALLOWED_DOMAINS = {"vanban.chinhphu.vn", "vpub.hochiminhcity.gov.vn"}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_jsonl(path: Path, errors: list[str]) -> list[dict]:
    try:
        raw = path.read_bytes()
        text = raw.decode("utf-8")
    except (OSError, UnicodeDecodeError):
        errors.append(f"FILE_NOT_UTF8:{path.as_posix()}")
        return []
    if text.startswith("\ufeff"):
        errors.append(f"UTF8_BOM_NOT_ALLOWED:{path.as_posix()}")
    rows: list[dict] = []
    for number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            errors.append(f"INVALID_JSON:{path.as_posix()}:{number}")
            continue
        if not isinstance(value, dict):
            errors.append(f"JSON_OBJECT_REQUIRED:{path.as_posix()}:{number}")
            continue
        rows.append(value)
    return rows


def index(rows: list[dict], key: str, label: str, errors: list[str]) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for row in rows:
        value = row.get(key)
        if not isinstance(value, str) or not ID_PATTERN.fullmatch(value):
            errors.append(f"INVALID_ID:{label}")
            continue
        if value in result:
            errors.append(f"DUPLICATE_ID:{label}:{value}")
        result[value] = row
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--dataset", default="data/demo_public")
    parser.add_argument("--mode", choices=("preflight", "publish"), default="preflight")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    dataset = (root / args.dataset).resolve()
    errors: list[str] = []
    warnings: list[str] = []

    if not dataset.is_relative_to(root) or not dataset.is_dir():
        errors.append("DATASET_NOT_INSIDE_ROOT")
        print(json.dumps({"status": "FAIL", "errors": errors}, ensure_ascii=False))
        return 1

    def publish_gate(ok: bool, code: str) -> None:
        if ok:
            return
        (errors if args.mode == "publish" else warnings).append(code)

    source_rows = load_jsonl(dataset / "source_manifest.jsonl", errors)
    procedure_rows = load_jsonl(dataset / "normalized/procedures.jsonl", errors)
    fragment_rows = load_jsonl(dataset / "normalized/fragments.jsonl", errors)
    question_rows = load_jsonl(dataset / "gold/questions.jsonl", errors)
    sources = index(source_rows, "source_id", "source", errors)
    procedures = index(procedure_rows, "procedure_id", "procedure", errors)
    fragments = index(fragment_rows, "fragment_id", "fragment", errors)
    questions = index(question_rows, "question_id", "question", errors)

    for path in (
        dataset / "source_manifest.jsonl",
        dataset / "normalized/procedures.jsonl",
        dataset / "normalized/fragments.jsonl",
        dataset / "gold/questions.jsonl",
    ):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        if any(pattern.search(text) for pattern in SECRET_PATTERNS):
            errors.append(f"POSSIBLE_SECRET:{path.relative_to(root).as_posix()}")
        if path.parent.name in {"normalized", "gold"} and text != unicodedata.normalize(
            "NFC", text
        ):
            errors.append(f"TEXT_NOT_NFC:{path.relative_to(root).as_posix()}")

    raw_root = (dataset / "raw").resolve()
    for source_id, source in sources.items():
        url = urlsplit(str(source.get("source_url", "")))
        domain = str(source.get("source_domain", "")).lower()
        if (
            url.scheme != "https"
            or url.hostname != domain
            or domain not in ALLOWED_DOMAINS
            or url.username
            or url.password
        ):
            errors.append(f"SOURCE_URL_NOT_ALLOWED:{source_id}")
        raw_value = source.get("raw_path")
        raw_path = Path(raw_value) if isinstance(raw_value, str) else Path("INVALID")
        candidate = (root / raw_path).resolve()
        if raw_path.is_absolute() or not candidate.is_relative_to(raw_root):
            errors.append(f"RAW_PATH_OUTSIDE_DATASET:{source_id}")
        else:
            try:
                actual = digest(candidate.read_bytes())
            except OSError:
                errors.append(f"RAW_MISSING:{source_id}")
            else:
                expected = source.get("content_sha256")
                if not isinstance(expected, str) or not HASH_PATTERN.fullmatch(expected):
                    errors.append(f"RAW_HASH_INVALID:{source_id}")
                elif actual != expected:
                    errors.append(f"RAW_HASH_MISMATCH:{source_id}")
        publish_gate(source.get("review_status") == "APPROVED", f"SOURCE_PENDING:{source_id}")
        if source.get("usage") != "D1_PUBLIC_DEMO":
            errors.append(f"SOURCE_CLASSIFICATION_INVALID:{source_id}")

    for fragment_id, fragment in fragments.items():
        procedure_id = fragment.get("procedure_id")
        source_id = fragment.get("source_id")
        if procedure_id not in procedures or source_id not in sources:
            errors.append(f"BROKEN_FRAGMENT_REFERENCE:{fragment_id}")
        text = fragment.get("text")
        expected = fragment.get("content_sha256")
        if not isinstance(text, str) or not isinstance(expected, str) or digest(
            text.encode("utf-8")
        ) != expected:
            errors.append(f"FRAGMENT_HASH_MISMATCH:{fragment_id}")
        source = sources.get(str(source_id), {})
        if str(source.get("raw_path", "")).lower().endswith(".rar"):
            locator = fragment.get("source_locator")
            if not isinstance(locator, dict):
                errors.append(f"ARCHIVE_LOCATOR_REQUIRED:{fragment_id}")
            elif not HASH_PATTERN.fullmatch(str(locator.get("inner_content_sha256", ""))):
                errors.append(f"INNER_HASH_INVALID:{fragment_id}")

    for procedure_id, procedure in procedures.items():
        source_ids = procedure.get("source_ids")
        if not isinstance(source_ids, list) or not source_ids or not set(source_ids) <= sources.keys():
            errors.append(f"BROKEN_PROCEDURE_SOURCE:{procedure_id}")
        provenance = procedure.get("field_evidence")
        if not isinstance(provenance, dict):
            errors.append(f"FIELD_EVIDENCE_REQUIRED:{procedure_id}")
            continue
        for field in BUSINESS_FIELDS:
            values = procedure.get(field)
            refs = provenance.get(field)
            if not isinstance(values, list) or not isinstance(refs, list) or len(values) != len(refs):
                errors.append(f"PROVENANCE_LENGTH:{procedure_id}:{field}")
                continue
            for group in refs:
                if not isinstance(group, list) or not group or not set(group) <= fragments.keys():
                    errors.append(f"BROKEN_PROVENANCE:{procedure_id}:{field}")
        publish_gate(
            all(procedure.get(field) for field in ("applicant_scope", "required_documents", "steps")),
            f"PROCEDURE_INCOMPLETE:{procedure_id}",
        )

    for question_id, question in questions.items():
        procedure_id = question.get("procedure_id")
        source_ids = question.get("gold_source_ids")
        fragment_ids = question.get("gold_fragment_ids")
        if procedure_id is not None and procedure_id not in procedures:
            errors.append(f"BROKEN_GOLD_PROCEDURE:{question_id}")
        if not isinstance(source_ids, list) or not set(source_ids) <= sources.keys():
            errors.append(f"BROKEN_GOLD_SOURCE:{question_id}")
        if not isinstance(fragment_ids, list) or not set(fragment_ids) <= fragments.keys():
            errors.append(f"BROKEN_GOLD_FRAGMENT:{question_id}")
        if question.get("contains_pii") is not False:
            errors.append(f"PII_FLAG_NOT_FALSE:{question_id}")
        reviewer = question.get("reviewer")
        publish_gate(
            isinstance(reviewer, str)
            and reviewer not in {"PENDING_SECOND_REVIEW", "minh_or_hoan", question.get("author")},
            f"GOLD_REVIEW_PENDING:{question_id}",
        )
        if question.get("expected_status") == "INSUFFICIENT_DATA" and (
            procedure_id is not None or source_ids or fragment_ids
        ):
            errors.append(f"OUT_OF_CORPUS_GOLD_MUST_BE_EMPTY:{question_id}")

    fixture_dir = dataset / "fixtures"
    try:
        bundle = json.loads((fixture_dir / "evidence_bundle.json").read_text(encoding="utf-8"))
        request = json.loads((fixture_dir / "grounding_request.json").read_text(encoding="utf-8"))
        answer = json.loads((fixture_dir / "grounded_answer.json").read_text(encoding="utf-8"))
        binding = ("request_id", "evidence_bundle_id", "corpus_version", "data_classification")
        if any(bundle.get(key) != request.get(key) or request.get(key) != answer.get(key) for key in binding):
            errors.append("FIXTURE_BINDING_MISMATCH")
        if any(key in request for key in ("history", "url", "score", "metadata")) or any(
            any(key in item for key in ("url", "score", "metadata"))
            for item in request.get("evidence", [])
        ):
            errors.append("AI_REQUEST_CONTAINS_BACKEND_ONLY_FIELDS")
        available = {item.get("fragment_id") for item in bundle.get("evidence", [])}
        if not set(answer.get("cited_fragment_ids", [])) <= available:
            errors.append("FIXTURE_CITATION_INVALID")
    except (OSError, json.JSONDecodeError, TypeError):
        errors.append("FIXTURE_INVALID")

    referenced_sources = {
        source_id for procedure in procedures.values() for source_id in procedure.get("source_ids", [])
    }
    for source_id in sorted(sources.keys() - referenced_sources):
        warnings.append(f"SOURCE_NOT_USED_BY_PROCEDURE:{source_id}")

    publish_gate(2 <= len(procedures) <= 3, "PUBLISH_SCOPE_REQUIRES_2_TO_3_PROCEDURES")
    publish_gate(30 <= len(questions) <= 50, "PUBLISH_SCOPE_REQUIRES_30_TO_50_QUESTIONS")
    publish_gate(any(q.get("split") == "TEST" for q in questions.values()), "TEST_SPLIT_REQUIRED")

    report = {
        "status": "PASS" if not errors else "FAIL",
        "mode": args.mode,
        "records": {
            "sources": len(sources),
            "procedures": len(procedures),
            "fragments": len(fragments),
            "questions": len(questions),
        },
        "errors": sorted(set(errors)),
        "warnings": sorted(set(warnings)),
    }
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
