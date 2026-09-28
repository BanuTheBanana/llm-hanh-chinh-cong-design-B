"""Compare G4 lexical routing with G5 hybrid routing on private DEV only."""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import sys
import time
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.rag.g3.retrieval import retrieve  # noqa: E402
from app.rag.g3.validator import load_serving  # noqa: E402
from app.rag.g4.context import prepare_turn  # noqa: E402
from app.rag.g4.evaluation import (  # noqa: E402
    prepare_scenario_target,
    read_dev,
    read_locked_test_v3,
)
from app.rag.g5.hybrid import HybridProcedureRouter  # noqa: E402
from app.rag.schemas import RetrievalInput  # noqa: E402


def _private_output(path: Path) -> Path:
    resolved = path.resolve()
    reports = (ROOT / "evaluation" / "reports").resolve()
    if not resolved.is_relative_to(reports):
        raise ValueError("G5_PRIVATE_OUTPUT_REQUIRED")
    if resolved.exists():
        raise ValueError("G5_OUTPUT_ALREADY_EXISTS")
    return resolved


def _score(rows: list[dict], results: list[dict]) -> dict:
    recalls = []
    for row, result in zip(rows, results):
        gold = set(row["gold_fragment_ids"])
        found = {item["fragment_id"] for item in result["evidence"]}
        if gold:
            recalls.append(len(gold & found) / len(gold))
    total = len(rows)
    return {
        "routing_accuracy": sum(
            result["procedure_id"] == row["procedure_id"] for row, result in zip(rows, results)
        )
        / total,
        "status_accuracy": sum(
            result["status"] == row["expected_status"] for row, result in zip(rows, results)
        )
        / total,
        "recall_at_5": sum(recalls) / len(recalls) if recalls else None,
    }


def _retrieve(data, query):
    return retrieve(
        data,
        query.query,
        top_k=query.top_k,
        procedure_id=query.filters.procedure_id,
        jurisdiction=query.filters.jurisdiction,
        field_intents=query.field_intents,
        as_of=query.filters.as_of.isoformat() if query.filters.as_of else None,
    )


async def _hybrid_result(router, data, row):
    state = None
    prepared = None
    used = 0
    for index, turn in enumerate(row["turns"]):
        if turn["role"] != "user":
            continue
        previous = state
        prepared, state, context = prepare_turn(
            data,
            RetrievalInput(query=turn["text"], top_k=5),
            previous,
            uuid5(NAMESPACE_URL, f"g5-hybrid/{row['scenario_id']}:{index}"),
        )
        if context.procedure_id is None:
            candidate = await router.route(data, turn["text"])
            used += candidate is not None
            if candidate is not None:
                prepared, state, _ = prepare_turn(
                    data,
                    RetrievalInput(query=turn["text"], top_k=5),
                    previous,
                    uuid5(NAMESPACE_URL, f"g5-hybrid/{row['scenario_id']}:{index}"),
                    procedure_hint=candidate.procedure_id,
                )
    if prepared is None:
        raise ValueError("G5_DEV_USER_TURN_REQUIRED")
    return _retrieve(data, prepared), used


async def run(args) -> int:
    output = _private_output(args.output)
    data = load_serving(args.dataset, args.version, args.expected_rows)
    if args.opened_test_v3_regression:
        rows, scenario_hash = read_locked_test_v3(args.dev, acknowledged=True)
        scenario_role = "OPENED_TEST_V3_REGRESSION_NOT_HOLDOUT"
    else:
        rows, scenario_hash = read_dev(args.dev)
        scenario_role = "DEV"
    baseline = [_retrieve(data, prepare_scenario_target(data, row, 5)) for row in rows]
    router = HybridProcedureRouter(
        base_url=args.embedding_url,
        model_name=args.embedding_model,
        timeout_seconds=args.timeout,
    )
    hybrid_pairs = []
    latencies = []
    try:
        for row in rows:
            started = time.perf_counter()
            hybrid_pairs.append(await _hybrid_result(router, data, row))
            latencies.append((time.perf_counter() - started) * 1000)
    finally:
        await router.aclose()
    hybrid = [item[0] for item in hybrid_pairs]
    sorted_latencies = sorted(latencies)
    result = {
        "schema_version": "g5-hybrid-evaluation-v1",
        "test_data_used": args.opened_test_v3_regression,
        "scenario_role": scenario_role,
        "dataset_version": data.version,
        "corpus_sha256": data.fingerprint,
        "scenario_sha256": scenario_hash,
        "scenario_count": len(rows),
        "hybrid_hint_count": sum(item[1] for item in hybrid_pairs),
        "baseline": _score(rows, baseline),
        "hybrid": {
            **_score(rows, hybrid),
            "mean_ms": sum(latencies) / len(latencies),
            "p95_ms": sorted_latencies[math.ceil(0.95 * len(sorted_latencies)) - 1],
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--expected-rows", type=int, default=10)
    parser.add_argument("--dev", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--embedding-url", default="http://127.0.0.1:8095/v1")
    parser.add_argument("--embedding-model", default="Qwen3-Embedding-0.6B")
    parser.add_argument("--timeout", type=float, default=8)
    parser.add_argument(
        "--opened-test-v3-regression",
        action="store_true",
        help="Use the already-opened TEST_V3 strictly as regression, never as a holdout.",
    )
    args = parser.parse_args()
    return asyncio.run(run(args))


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001 - never expose private exception text.
        safe = {
            "G5_PRIVATE_OUTPUT_REQUIRED",
            "G5_OUTPUT_ALREADY_EXISTS",
            "G5_DEV_USER_TURN_REQUIRED",
        }
        code = str(exc) if str(exc) in safe else "G5_HYBRID_EVALUATION_FAILED"
        print(json.dumps({"status": "ERROR", "error": code}))
        raise SystemExit(2) from None
