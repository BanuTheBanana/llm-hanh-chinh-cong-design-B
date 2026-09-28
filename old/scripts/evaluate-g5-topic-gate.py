"""Evaluate the current-turn topic gate on a labeled JSONL regression set.

This is an opened regression runner, not a substitute for a reviewer-held holdout.
It emits IDs and aggregate counts only, never query text or corpus contents.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import Counter
from pathlib import Path
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.rag.g3.validator import load_serving
from app.rag.g5.hybrid import HybridProcedureRouter
from app.rag.g5.topic_gate import decide_topic


def procedure_id_for_title(data, title: str | None) -> str | None:
    if title is None:
        return None
    matches = [pid for pid in data.accepted if data.procedures[pid]["title"] == title]
    if len(matches) != 1:
        raise ValueError(f"Expected one approved procedure for title: {title}")
    return matches[0]


async def evaluate(args: argparse.Namespace) -> dict:
    data = load_serving(args.dataset, args.version, args.expected_rows)
    router = (
        HybridProcedureRouter(base_url=args.embedding_url, model_name=args.embedding_model)
        if args.embedding_url
        else None
    )
    counts: Counter[str] = Counter()
    confusion: Counter[str] = Counter()
    failures = []
    durations = []
    try:
        for line in args.cases.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            item = json.loads(line)
            active_id = procedure_id_for_title(data, item.get("active_title"))
            expected_id = procedure_id_for_title(data, item.get("expected_title"))
            started = perf_counter()
            result = await decide_topic(data, item["query"], active_id, router)
            durations.append(round((perf_counter() - started) * 1000, 2))
            expected_action = item["expected_action"]
            passed = result.action == expected_action and result.procedure_id == expected_id
            counts["total"] += 1
            counts["passed" if passed else "failed"] += 1
            confusion[f"{expected_action}->{result.action}"] += 1
            if not passed:
                failures.append(
                    {
                        "case_id": item["case_id"],
                        "expected_action": expected_action,
                        "actual_action": result.action,
                        "actual_reason": result.reason,
                        "expected_procedure_id": expected_id,
                        "actual_procedure_id": result.procedure_id,
                    }
                )
    finally:
        if router is not None:
            await router.aclose()
    ordered = sorted(durations)
    p95_index = max(0, (95 * len(ordered) + 99) // 100 - 1)
    return {
        "corpus_version": data.version,
        "cases": str(args.cases),
        "total": counts["total"],
        "passed": counts["passed"],
        "failed": counts["failed"],
        "confusion": dict(sorted(confusion.items())),
        "latency_ms_p50": ordered[len(ordered) // 2] if ordered else None,
        "latency_ms_p95": ordered[p95_index] if ordered else None,
        "failures": failures,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--expected-rows", type=int, default=34)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--embedding-url", default="")
    parser.add_argument("--embedding-model", default="Qwen3-Embedding-0.6B")
    args = parser.parse_args()
    report = asyncio.run(evaluate(args))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
