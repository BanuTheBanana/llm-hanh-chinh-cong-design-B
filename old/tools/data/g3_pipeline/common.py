"""Shared deterministic and privacy-safe helpers for the G3 data pipeline."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")

PII_PATTERNS = {
    "EMAIL": re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b"),
    "PHONE": re.compile(r"(?<!\d)(?:\+?84|0)(?:\d[ .-]?){8,10}(?!\d)"),
    "CCCD": re.compile(r"(?<!\d)\d{12}(?!\d)"),
}

SECRET_PATTERNS = {
    "GROQ_KEY": re.compile(r"\bgsk_[A-Za-z0-9_-]{12,}"),
    "GOOGLE_KEY": re.compile(r"\bAQ\.[A-Za-z0-9_-]{12,}"),
    "OPENAI_KEY": re.compile(r"\bsk-[A-Za-z0-9_-]{16,}"),
}

VIETNAM_TZ = timezone(timedelta(hours=7))


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def nfc_text(value: Any) -> str:
    """Normalize cell text while preserving meaningful line boundaries."""
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = unicodedata.normalize("NFC", str(value)).replace("\r\n", "\n").replace("\r", "\n")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
    return "\n".join(line for line in lines if line)


def comparison_text(value: Any) -> str:
    return re.sub(r"\s+", " ", nfc_text(value)).strip().casefold()


def header_key(value: Any) -> str:
    text = comparison_text(value)
    text = text.replace("đ", "d")
    text = "".join(
        char for char in unicodedata.normalize("NFD", text) if unicodedata.category(char) != "Mn"
    )
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def title_fingerprint(value: str) -> str:
    normalized = comparison_text(value)
    normalized = re.sub(r"[\s\.,;:!?]+$", "", normalized)
    return sha256_text(normalized)[:12]


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def stable_unique(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def parse_collected_at(value: Any) -> str | None:
    """Parse known timestamp forms without inventing a missing timestamp."""
    parsed: datetime | None = None
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, date):
        parsed = datetime.combine(value, time.min)
    elif value is not None:
        raw = str(value).strip()
        if not raw:
            return None
        candidates = (
            "%d/%m/%Y %H:%M:%S",
            "%d/%m/%Y %H:%M",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
        )
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            for candidate in candidates:
                try:
                    parsed = datetime.strptime(raw, candidate)
                    break
                except ValueError:
                    continue
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=VIETNAM_TZ)
    return parsed.isoformat()


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]], id_key: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(rows, key=lambda row: str(row[id_key]))
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in ordered:
            handle.write(canonical_json(row))
            handle.write("\n")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, sort_keys=True, indent=2)
        handle.write("\n")


def file_sha256(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def scan_sensitive_text(text: str) -> set[str]:
    findings = {
        name
        for name, pattern in {**PII_PATTERNS, **SECRET_PATTERNS}.items()
        if pattern.search(text)
    }
    return findings


NON_SEMANTIC_KEYS = {
    "record_type",
    "schema_version",
    "dataset_version",
    "data_classification",
    "source_type",
    "source_uri",
    "parser_version",
    "validity_status",
    "status",
    "reviewer_role",
    "author_role",
    "split",
    "section_type",
    "category_code",
    "submission_methods",
    "version",
    "country_code",
    "procedure_code",
}


def scan_sensitive_record(value: Any, parent_key: str = "") -> set[str]:
    """Scan semantic values while excluding hashes, IDs and other machine metadata."""
    if isinstance(value, dict):
        findings: set[str] = set()
        for key, item in value.items():
            if (
                key in NON_SEMANTIC_KEYS
                or key.endswith("_id")
                or key.endswith("_ids")
                or key.endswith("_sha256")
            ):
                continue
            findings.update(scan_sensitive_record(item, key))
        return findings
    if isinstance(value, list):
        findings = set()
        for item in value:
            findings.update(scan_sensitive_record(item, parent_key))
        return findings
    if isinstance(value, str):
        return scan_sensitive_text(value)
    return set()
