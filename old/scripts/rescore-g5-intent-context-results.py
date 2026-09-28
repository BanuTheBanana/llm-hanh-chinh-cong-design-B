"""Recompute state-based G5 metrics from saved local benchmark predictions."""

from __future__ import annotations

import argparse
import json
import sys
import unicodedata
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from training.intent_context import (
    CONTEXT_SLOTS,
    apply_output_to_state,
)


def load_cases(fixture: Path) -> list[dict]:
    manifest = json.loads((fixture / "manifest.json").read_text(encoding="utf-8"))
    source = fixture / manifest["source_file"]
    return [json.loads(line) for line in source.read_text(encoding="utf-8").splitlines()]


def patch_equal(slot: str, predicted: dict, expected: dict) -> bool:
    predicted_value = predicted.get("value")
    expected_value = expected.get("value")
    if slot == "field_intents":
        predicted_value = sorted(predicted_value) if isinstance(predicted_value, list) else None
        expected_value = sorted(expected_value) if isinstance(expected_value, list) else None
    return (predicted.get("op"), predicted_value) == (
        expected.get("op"),
        expected_value,
    )


def canonical_jurisdiction(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    plain = unicodedata.normalize("NFD", value.casefold())
    plain = "".join(char for char in plain if unicodedata.category(char) != "Mn")
    plain = plain.replace("đ", "d")
    tokens = "".join(char if char.isalnum() else " " for char in plain).split()
    administrative = {"tinh", "thanh", "pho", "quan", "huyen", "thi", "xa", "phuong"}
    return " ".join(token for token in tokens if token not in administrative)


def state_equal(predicted: dict, expected: dict) -> bool:
    return (
        predicted.get("procedure_id") == expected.get("procedure_id")
        and sorted(predicted.get("field_intents") or [])
        == sorted(expected.get("field_intents") or [])
        and canonical_jurisdiction(predicted.get("jurisdiction"))
        == canonical_jurisdiction(expected.get("jurisdiction"))
        and predicted.get("as_of") == expected.get("as_of")
    )


def rescore(result: dict, cases: list[dict]) -> dict:
    case_by_id = {case["case_id"]: case for case in cases}
    counts = Counter()
    groups = Counter()
    group_passes = Counter()
    for row in result["raw_rows"]:
        case = case_by_id[row["case_id"]]
        groups[case["group"]] += 1
        predicted = row.get("predicted")
        if predicted is None or row.get("errors"):
            row["state_passed"] = False
            continue
        expected = case["expected"]
        act_ok = predicted["dialogue_act"] == expected["dialogue_act"]
        topic_ok = predicted["topic_action"] == expected["topic_action"]
        patch_ok = all(
            patch_equal(slot, predicted["patch"][slot], expected["patch"][slot])
            for slot in CONTEXT_SLOTS
        )
        state_ok = state_equal(
            apply_output_to_state(case["state_before"], predicted),
            apply_output_to_state(case["state_before"], expected),
        )
        full_state_ok = act_ok and topic_ok and state_ok
        counts["joint_patch"] += patch_ok
        counts["joint_state"] += state_ok
        counts["full_exact_patch_case"] += act_ok and topic_ok and patch_ok
        counts["full_state_case"] += full_state_ok
        row["state_passed"] = full_state_ok
        if full_state_ok:
            group_passes[case["group"]] += 1

    total = len(cases)
    for metric in (
        "joint_patch",
        "joint_state",
        "full_exact_patch_case",
        "full_state_case",
    ):
        result["metrics"][metric] = round(counts[metric] / total, 6)
    result["metrics"].pop("full_case", None)
    result["per_group_full_state_case"] = {
        group: {
            "correct": group_passes[group],
            "count": groups[group],
            "accuracy": round(group_passes[group] / groups[group], 6),
        }
        for group in sorted(groups)
    }
    result.pop("per_group_full_case", None)
    result["metric_note"] = (
        "joint_patch is an exact diagnostic; joint_state/full_state_case score the "
        "deterministic context after Backend switch/reset rules."
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("result", nargs="+", type=Path)
    parser.add_argument(
        "--fixture",
        type=Path,
        default=ROOT / "evaluation/fixtures/intent-context-pilot-v1",
    )
    args = parser.parse_args()
    cases = load_cases(args.fixture)
    for path in args.result:
        result = json.loads(path.read_text(encoding="utf-8"))
        result = rescore(result, cases)
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        metrics = result["metrics"]
        print(
            f"{result['candidate']}: joint_state={metrics['joint_state']:.4f}, "
            f"full_state={metrics['full_state_case']:.4f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
