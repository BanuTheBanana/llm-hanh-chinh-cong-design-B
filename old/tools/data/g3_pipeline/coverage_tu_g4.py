#!/usr/bin/env python3
"""Produce a sanitized G4 coverage summary for a private demo10 corpus."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from g3_pipeline.g4_tu_scenarios import FIELD_ORDER, _ambiguity_flags


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def coverage(procedures_path: Path) -> dict[str, Any]:
    procedures = _load_jsonl(procedures_path)
    present = Counter()
    missing = Counter()
    ambiguous: set[tuple[str, str]] = set()
    for proc in procedures:
        for field in FIELD_ORDER:
            values = proc.get(field)
            if isinstance(values, list) and values:
                present[field] += 1
            else:
                missing[field] += 1
            if _ambiguity_flags(proc, field):
                ambiguous.add((str(proc.get("procedure_id")), field))
    return {
        "procedure_count": len(procedures),
        "present": {field: present[field] for field in FIELD_ORDER},
        "missing": {field: missing[field] for field in FIELD_ORDER},
        "ambiguous_source_field_count": len(ambiguous),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--procedures", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = coverage(args.procedures.resolve())
    except Exception:
        print('{"status":"FAIL","error":"G4_COVERAGE_FAILED"}')
        return 2
    print(json.dumps(report, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
