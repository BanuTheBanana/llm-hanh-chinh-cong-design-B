"""Frozen-schema consumer. Never read raw files or echo input values in diagnostics."""

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlsplit

from jsonschema import Draft202012Validator, FormatChecker

from app.rag.corpus import CorpusError

FILES = (
    ("source_manifest.jsonl", "SOURCE_MANIFEST", "source_id"),
    ("normalized/procedures.jsonl", "PROCEDURE_RECORD", "procedure_id"),
    ("normalized/fragments.jsonl", "PROCEDURE_FRAGMENT", "fragment_id"),
    ("quarantine/conflicts.jsonl", "CONFLICT_RECORD", "conflict_id"),
    ("gold/questions.jsonl", "GOLD_QUESTION", "question_id"),
)
SECTIONS = {
    "applicant_scope": "APPLICANT_SCOPE",
    "receiving_authority": "RECEIVING_AUTHORITY",
    "submission_methods": "SUBMISSION_METHODS",
    "required_documents": "REQUIRED_DOCUMENTS",
    "steps": "STEPS",
    "fees": "FEES",
    "processing_times": "PROCESSING_TIME",
    "legal_bases": "LEGAL_BASES",
}
APPROVED = {"APPROVED_FOR_DEMO", "APPROVED_FOR_PRODUCTION"}
EMAIL = re.compile(r"[^\s@]+@[^\s@]+", re.UNICODE)
PHONE = re.compile(r"(?<!\w)(?:\+?84|0)[\s.()-]*(?:\d[\s.()-]*){8,10}(?!\w)")
CCCD = re.compile(r"(?<!\w)(?:\d[ -]?){12}(?!\w)")
SCHEMA = json.loads(Path(__file__).with_name("data-contract-v1.schema.json").read_text())
VALIDATOR = Draft202012Validator(SCHEMA, format_checker=FormatChecker())


def require(ok, code):
    if not ok:
        raise CorpusError(code)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def scan(value):
    """Heuristic tripwire, not a claim to detect all forms of personal data."""
    if isinstance(value, dict):
        for k, v in value.items():
            scan(k)
            # Hashes are validated by the schema and aren't phone numbers.
            if not (
                k in {"content_sha256", "workbook_sha256", "raw_cell_sha256"}
                and isinstance(v, str)
                and re.fullmatch(r"[0-9a-f]{64}", v)
            ):
                scan(v)
    elif isinstance(value, list):
        for item in value:
            scan(item)
    elif isinstance(value, str):
        require(
            value == unicodedata.normalize("NFC", value) and value == value.strip(),
            "TEXT_NORMALIZATION_ERROR",
        )
        text = unquote(value)
        require(
            not (EMAIL.search(text) or PHONE.search(text) or CCCD.search(text)),
            "PII_PATTERN_DETECTED",
        )


def pairs(items):
    out = {}
    for k, v in items:
        require(k not in out, "DUPLICATE_JSON_KEY")
        out[k] = v
    return out


@dataclass
class Dataset:
    version: str
    groups: list[dict]
    fingerprint: str
    accepted: list[str]
    rejected: dict[str, str]
    row_count: int

    @property
    def sources(self):
        return self.groups[0]

    @property
    def procedures(self):
        return self.groups[1]

    @property
    def fragments(self):
        return self.groups[2]

    def report(self):
        # IDs are schema validated and PII scanned; no titles/text/locators.
        return {
            "dataset_version": self.version,
            "schema_version": "g3-data-v1",
            "corpus_sha256": self.fingerprint,
            "accepted_procedure_ids": self.accepted,
            "rejected_procedure_ids": self.rejected,
            "source_count": len(self.sources),
            "fragment_count": len(self.fragments),
            "accounted_rows": self.row_count,
            "validation": "PASS",
            "readiness": "BLOCKED",
            "blockers": [
                "SOURCE_HASH_CONVENTION_UNRESOLVED",
                "RAW_HASH_VERIFICATION_NOT_PERFORMED",
                "D2_GENERATION_CONTRACT_NOT_APPROVED",
            ],
        }


def load(dataset: Path, version: str, expected_rows: int = 42, production=False):
    require(bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", version)), "INVALID_VERSION")
    require(expected_rows > 0, "INVALID_EXPECTED_ROWS")
    root = dataset.resolve()
    groups, seen = [], set()
    for filename, kind, key in FILES:
        path = root / filename
        require(path.resolve().is_relative_to(root), "FILE_OUTSIDE_DATASET")
        try:
            data = path.read_bytes()
            require(
                not data.startswith(b"\xef\xbb\xbf") and b"\r" not in data, "JSONL_ENCODING_ERROR"
            )
            require(not data or data.endswith(b"\n"), "JSONL_FINAL_NEWLINE_REQUIRED")
            rows = []
            for line in data.decode("utf-8").splitlines():
                require(bool(line.strip()), "JSONL_BLANK_LINE")
                row = json.loads(
                    line,
                    object_pairs_hook=pairs,
                    parse_constant=lambda _: require(False, "INVALID_JSON_NUMBER"),
                )
                require(VALIDATOR.is_valid(row), "SCHEMA_ERROR")
                scan(row)
                require(row["record_type"] == kind, "RECORD_TYPE_MISMATCH")
                require(row["dataset_version"] == version, "DATASET_VERSION_MISMATCH")
                require(row[key] not in seen, "DUPLICATE_PRIMARY_ID")
                seen.add(row[key])
                rows.append(row)
            require([r[key] for r in rows] == sorted(r[key] for r in rows), "UNSORTED_PRIMARY_IDS")
            groups.append({r[key]: r for r in rows})
        except (OSError, UnicodeError, json.JSONDecodeError):
            raise CorpusError("JSONL_READ_OR_PARSE_ERROR") from None
    sources, procedures, fragments, conflicts, gold = groups
    require(bool(sources and procedures), "EMPTY_CORPUS")
    row_refs, workbook_hashes = set(), set()
    for s in sources.values():
        start, end = s["effective_from"], s["effective_to"]
        require(not (start and end) or start <= end, "INVALID_EFFECTIVE_INTERVAL")
        uri = urlsplit(s["source_uri"])
        require(
            uri.scheme == "company-internal"
            and bool(uri.netloc)
            and not uri.username
            and not uri.password
            and not uri.query
            and not uri.fragment
            and ".." not in uri.path.split("/"),
            "UNSAFE_SOURCE_URI",
        )
        if s["public_url"]:
            url = urlsplit(s["public_url"])
            require(
                bool(url.hostname)
                and not url.username
                and not url.password
                and not url.query
                and not url.fragment,
                "UNSAFE_PUBLIC_URL",
            )
        loc = s["raw_locator"]
        workbook_hashes.add(loc["workbook_sha256"])
        for n in loc["row_numbers"]:
            ref = (loc["workbook_sha256"], loc["sheet"], n)
            require(ref not in row_refs, "DUPLICATE_RAW_ROW")
            row_refs.add(ref)
    require(len(workbook_hashes) == 1, "MIXED_WORKBOOKS")
    require(len(row_refs) == expected_rows, "ROW_ACCOUNTING_MISMATCH")
    ordinals = set()
    for f in fragments.values():
        require(
            f["procedure_id"] in procedures and f["source_id"] in sources,
            "BROKEN_FRAGMENT_REFERENCE",
        )
        p, s = procedures[f["procedure_id"]], sources[f["source_id"]]
        require(f["source_id"] in p["source_ids"], "FRAGMENT_SOURCE_MISMATCH")
        require(digest(f["text"].encode("utf-8")) == f["content_sha256"], "FRAGMENT_HASH_MISMATCH")
        loc, raw = f["source_locator"], s["raw_locator"]
        require(
            loc["sheet"] == raw["sheet"] and loc["row_number"] in raw["row_numbers"],
            "LOCATOR_SOURCE_MISMATCH",
        )
        ordinal = (f["procedure_id"], f["section_type"], f["ordinal"])
        require(ordinal not in ordinals, "DUPLICATE_ORDINAL")
        ordinals.add(ordinal)
    used_sources = set()
    for p in procedures.values():
        require(set(p["source_ids"]) <= sources.keys(), "BROKEN_SOURCE_REFERENCE")
        used_sources.update(p["source_ids"])
        for field, section in SECTIONS.items():
            refs = p["field_evidence"][field]
            require(bool(p[field]) or field in p["missing_fields"], "MISSING_FIELD_UNDECLARED")
            require(
                not (field in p["missing_fields"] and (refs or p[field])), "MISSING_FIELD_HAS_CLAIM"
            )
            require(not p[field] or bool(refs), "FIELD_WITHOUT_EVIDENCE")
            for fid in refs:
                require(fid in fragments, "BROKEN_FIELD_REFERENCE")
                f = fragments[fid]
                require(
                    f["procedure_id"] == p["procedure_id"] and f["section_type"] == section,
                    "FIELD_EVIDENCE_MISMATCH",
                )
        for t in p["processing_times"]:
            lo, hi = t["min_business_days"], t["max_business_days"]
            require(lo is None or hi is None or lo <= hi, "INVALID_TIME_INTERVAL")
    open_procs, open_sources = set(), set()
    for c in conflicts.values():
        require(set(c["source_ids"]) <= sources.keys(), "BROKEN_CONFLICT_SOURCE")
        used_sources.update(c["source_ids"])
        rows = {n for sid in c["source_ids"] for n in sources[sid]["raw_locator"]["row_numbers"]}
        require(set(c["row_numbers"]) <= rows, "CONFLICT_ROW_MISMATCH")
        if c["status"] == "OPEN":
            pid = c["candidate_procedure_id"]
            require(
                pid in procedures and procedures[pid]["review"]["status"] == "QUARANTINED",
                "OPEN_CONFLICT_NOT_QUARANTINED",
            )
            open_procs.add(pid)
            open_sources.update(c["source_ids"])
    require(used_sources == sources.keys(), "UNACCOUNTED_SOURCE")
    splits = {}
    for q in gold.values():
        pid = q["procedure_id"]
        require(pid is None or pid in procedures, "GOLD_PROCEDURE_REFERENCE")
        require(q["author_role"] != q["reviewer_role"], "GOLD_SELF_REVIEW")
        require(
            set(q["gold_source_ids"]) <= sources.keys()
            and set(q["gold_fragment_ids"]) <= fragments.keys(),
            "GOLD_REFERENCE_ERROR",
        )
        if pid:
            require(
                set(q["gold_source_ids"]) <= set(procedures[pid]["source_ids"]),
                "GOLD_SOURCE_PROCEDURE_MISMATCH",
            )
            require(pid not in splits or splits[pid] == q["split"], "GOLD_SPLIT_LEAKAGE")
            splits[pid] = q["split"]
        require(
            q["expected_status"] != "ANSWER" or (pid and q["gold_fragment_ids"]),
            "GOLD_ANSWER_WITHOUT_EVIDENCE",
        )
        for fid in q["gold_fragment_ids"]:
            f = fragments[fid]
            require(
                f["procedure_id"] == pid and f["source_id"] in q["gold_source_ids"],
                "GOLD_BINDING_MISMATCH",
            )
    allowed = {"APPROVED_FOR_PRODUCTION"} if production else APPROVED
    accepted, rejected = [], {}
    for pid, p in procedures.items():
        reason = None
        if pid in open_procs or set(p["source_ids"]) & open_sources:
            reason = "OPEN_CONFLICT"
        elif p["review"]["status"] not in allowed:
            reason = "PROCEDURE_NOT_APPROVED"
        elif any(sources[s]["review"]["status"] not in allowed for s in p["source_ids"]):
            reason = "SOURCE_NOT_APPROVED"
        if reason:
            rejected[pid] = reason
        else:
            accepted.append(pid)
    fp = digest(canonical([list(g.values()) for g in groups]).encode("utf-8"))
    return Dataset(version, groups, fp, accepted, rejected, len(row_refs))
