"""Fail CI when tracked files contain common secret material or local env files."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

SECRET_PATTERNS = {
    "private key": re.compile(rb"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----"),
    "GitHub token": re.compile(rb"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})\b"),
    "OpenAI API key": re.compile(rb"\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{20,}\b"),
    "Groq API key": re.compile(rb"\bgsk_[A-Za-z0-9_-]{20,}\b"),
    "AWS access key": re.compile(rb"\bAKIA[0-9A-Z]{16}\b"),
    "Google API key": re.compile(rb"\bAIza[0-9A-Za-z_-]{35}\b"),
    "Google/Gemini credential": re.compile(rb"\bAQ\.[0-9A-Za-z_-]{20,}\b"),
    "Slack token": re.compile(rb"\bxox[baprs]-[0-9A-Za-z-]{20,}\b"),
}

FORBIDDEN_DATA_SUFFIXES = {".xls", ".xlsx", ".xlsm"}
FORBIDDEN_DATA_ROOTS = {
    Path("dataset"),
    Path("data/company_private"),
    Path("data/gold"),
}


def is_below(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


def repository_paths() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        check=True,
        capture_output=True,
    )
    return sorted({Path(item.decode("utf-8")) for item in result.stdout.split(b"\0") if item})


def main() -> int:
    findings: list[str] = []
    paths = repository_paths()

    for path in paths:
        if (
            path.suffix.lower() in {".xlsx", ".xls", ".xlsm"}
            or "company_private" in path.parts
            or "dataset" in path.parts
        ):
            findings.append("COMPANY_PRIVATE_FILE_FORBIDDEN (path withheld)")
            continue  # Do not read company content, even when force-added to Git.
        if path.name.startswith(".env") and path.name != ".env.example":
            findings.append(f"{path}: local environment file is tracked")
        if path.suffix.lower() in {".key", ".p12", ".pfx"}:
            findings.append(f"{path}: private credential file type is tracked")
        if path.suffix.lower() in FORBIDDEN_DATA_SUFFIXES:
            findings.append(f"{path}: spreadsheet source data must not be tracked")
        if any(is_below(path, root) for root in FORBIDDEN_DATA_ROOTS):
            findings.append(f"{path}: private or derived company data path is tracked")

        try:
            data = path.read_bytes()
        except FileNotFoundError:
            # A tracked file staged for deletion is not present in the candidate tree.
            continue
        except OSError as error:
            findings.append(f"{path}: cannot inspect tracked file ({type(error).__name__})")
            continue
        if b"\0" in data or len(data) > 5_000_000:
            continue
        for label, pattern in SECRET_PATTERNS.items():
            if pattern.search(data):
                findings.append(f"{path}: possible {label}")

    if findings:
        print("Repository hygiene check failed:", file=sys.stderr)
        for finding in findings:
            print(f"- {finding}", file=sys.stderr)
        return 1

    print(f"PASS - inspected {len(paths)} repository files; no common secret material found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
