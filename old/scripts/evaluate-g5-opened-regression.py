"""Score the already-opened G4 TEST_V3 as G5 regression, never as holdout."""

from __future__ import annotations

import argparse
import json
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--expected-rows", type=int, default=10)
    parser.add_argument("--test-v3", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to((ROOT / "evaluation" / "reports").resolve()):
        raise ValueError("G5_PRIVATE_OUTPUT_REQUIRED")
    if output.exists():
        raise ValueError("G5_OUTPUT_ALREADY_EXISTS")

    from app.rag.g3.validator import load_serving
    from app.rag.g4.evaluation import read_locked_test_v3

    release_module = runpy.run_path(str(ROOT / "scripts" / "evaluate-g4-release.py"))
    evaluate_rows = release_module["evaluate_rows"]
    data = load_serving(args.dataset, args.version, args.expected_rows)
    rows, scenario_hash = read_locked_test_v3(args.test_v3, acknowledged=True)
    metrics = evaluate_rows(data, rows, expected_split="TEST_V3")
    result = {
        "schema_version": "g5-opened-regression-v1",
        "status": "PASS" if metrics.pop("gate_passed") else "FAIL",
        "scenario_role": "OPENED_TEST_V3_REGRESSION_NOT_HOLDOUT",
        "test_data_used": True,
        "scenario_sha256": scenario_hash,
        "corpus_sha256": data.fingerprint,
        **metrics,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001 - do not expose private payloads.
        safe = {"G5_PRIVATE_OUTPUT_REQUIRED", "G5_OUTPUT_ALREADY_EXISTS"}
        code = str(exc) if str(exc) in safe else "G5_OPENED_REGRESSION_FAILED"
        print(json.dumps({"status": "ERROR", "error": code}))
        raise SystemExit(2) from None
