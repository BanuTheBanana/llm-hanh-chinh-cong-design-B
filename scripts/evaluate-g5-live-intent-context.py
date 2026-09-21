"""Score the running G5 intent service on the opened D0 conversation DEV set.

This is a development regression, never a new independent acceptance test.
Only aggregate metrics and case IDs are written; user text is not copied to output.
"""

from __future__ import annotations

import hashlib
import json
import runpy
import statistics
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ai-service"))
sys.path.insert(0, str(ROOT))

from app.intent_context_policy import POLICY_VERSION

helpers = runpy.run_path(str(ROOT / "scripts/evaluate-g5-intent-context-models.py"))
from training.intent_context import apply_output_to_state

FIXTURE = ROOT / "evaluation/fixtures/g6-intent-context-dev-v1/cases.jsonl"
OUTPUT_ROOT = ROOT / "evaluation/reports/g5"
URL = "http://127.0.0.1:8105/internal/v3/intent-context"


def request_intent(case: dict, state: dict) -> tuple[dict, dict]:
    body = {
        "request_id": str(uuid4()),
        "current_message_id": str(uuid4()),
        "current_user_message": case["current_user_message"],
        "state_before": state,
        "procedure_candidates": case["procedure_candidates"],
        "data_classification": "D0_SYSTEM_SMOKE",
    }
    request = Request(
        URL,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=45) as response:
        result = json.load(response)
    return result["output"], result


def main() -> int:
    manifest = json.loads(FIXTURE.with_name("manifest.json").read_text(encoding="utf-8"))
    fixture_bytes = FIXTURE.read_bytes()
    fixture_hash = hashlib.sha256(fixture_bytes).hexdigest()
    if fixture_hash != manifest["content_sha256"] or manifest["final_test"] is not False:
        raise RuntimeError("DEV_FIXTURE_MANIFEST_MISMATCH")
    cases = [json.loads(line) for line in fixture_bytes.decode("utf-8").splitlines() if line]
    if len(cases) != manifest["case_count"]:
        raise RuntimeError("DEV_FIXTURE_CASE_COUNT_MISMATCH")

    counts = Counter()
    groups = {name: Counter() for name in manifest["groups"]}
    field_counts = {name: Counter() for name in helpers["FIELD_INTENTS"]}
    replay: dict[str, dict] = {}
    conversations: dict[str, bool] = {}
    latencies: list[float] = []
    failed_ids: list[str] = []
    errors: list[str] = []
    model_name = None

    for case in cases:
        conversation_id = case["conversation_id"]
        if case["turn_index"] == 1:
            replay[conversation_id] = helpers["empty_runtime_state"](case["state_before"])
            conversations[conversation_id] = True
        state = {
            **replay[conversation_id],
            "pending_clarification": case["state_before"].get("pending_clarification"),
        }
        started = time.perf_counter()
        try:
            predicted, response = request_intent(case, state)
            model_name = response.get("model") or model_name
            counts["schema_valid"] += 1
            counts["semantic_valid"] += 1
            if response.get("usage", {}).get("input_tokens", 0) == 0:
                counts["fast_path"] += 1
            else:
                counts["model_path"] += 1
        except Exception as exc:  # noqa: BLE001 - aggregate failure without user text
            predicted = None
            errors.append(f"{case['case_id']}:{type(exc).__name__}")
        latencies.append((time.perf_counter() - started) * 1000)

        expected = case["expected"]
        gold_state = apply_output_to_state(case["state_before"], expected)
        if predicted is not None:
            predicted_state = apply_output_to_state(state, predicted)
            act_ok = predicted["dialogue_act"] == expected["dialogue_act"]
            topic_ok = predicted["topic_action"] == expected["topic_action"]
            state_ok = helpers["state_equal"](predicted_state, gold_state)
            counts["dialogue_act"] += int(act_ok)
            counts["topic_action"] += int(topic_ok)
            counts["joint_state"] += int(state_ok)
            counts["field_state_exact"] += int(
                helpers["update_field_scores"](field_counts, gold_state, predicted_state)
            )
            full_ok = act_ok and topic_ok and state_ok
        else:
            predicted_state = helpers["empty_runtime_state"](state)
            helpers["update_field_scores"](field_counts, gold_state, predicted_state)
            full_ok = False

        counts["full_state_case"] += int(full_ok)
        groups[case["group"]]["total"] += 1
        groups[case["group"]]["correct"] += int(full_ok)
        conversations[conversation_id] &= full_ok
        replay[conversation_id] = predicted_state
        if not full_ok:
            failed_ids.append(case["case_id"])

    total = len(cases)
    result = {
        "schema_version": "g5-current-dev-regression-v1",
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "scope": "Opened D0 DEV conversation regression; not independent holdout or legal-answer evaluation",
        "fixture_sha256": fixture_hash,
        "policy_version": POLICY_VERSION,
        "runtime_model": model_name,
        "case_count": total,
        "conversation_count": len(conversations),
        "metrics": {
            name: round(counts[name] / total, 6)
            for name in (
                "schema_valid", "semantic_valid", "dialogue_act", "topic_action",
                "joint_state", "field_state_exact", "full_state_case",
            )
        },
        "field_macro_f1": helpers["macro_f1"](field_counts),
        "conversation_success": round(sum(conversations.values()) / len(conversations), 6),
        "routes": {"fast_path": counts["fast_path"], "model_path": counts["model_path"]},
        "latency_ms": {
            "p50": helpers["percentile"](latencies, 0.5),
            "p95": helpers["percentile"](latencies, 0.95),
            "mean": round(statistics.fmean(latencies), 3),
        },
        "per_group_full_state_case": {
            group: {
                "correct": item["correct"],
                "count": item["total"],
                "accuracy": round(item["correct"] / item["total"], 6),
            }
            for group, item in sorted(groups.items())
        },
        "failed_case_ids": failed_ids,
        "errors": errors,
    }
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    output = OUTPUT_ROOT / f"current-dev-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key not in ("failed_case_ids", "errors")}, ensure_ascii=False))
    print(f"report={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
