from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .evaluation import run_generation_benchmark
from .generator import GroundedGenerator, validate_generated_output
from .runtime import LlamaCppHTTPRuntime
from .thresholds import tune_thresholds


def _read_json(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _read_jsonl(path: str) -> list[dict]:
    rows = []
    for number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise SystemExit(f"{path}:{number}: invalid JSON: {exc}") from exc
    return rows


def _write_json(path: str | None, value: object) -> None:
    text = json.dumps(value, ensure_ascii=False, indent=2)
    if path:
        Path(path).write_text(text + "\n", encoding="utf-8")
    else:
        print(text)


def _runtime(args) -> LlamaCppHTTPRuntime:
    return LlamaCppHTTPRuntime(
        base_url=args.base_url or os.getenv("LLM_BASE_URL", "http://127.0.0.1:8080"),
        model=args.model or os.getenv("LLM_MODEL", "local-model"),
        api_key=os.getenv("LLM_API_KEY"),
        temperature=0.0,
        seed=args.seed,
        max_tokens=args.max_tokens,
        timeout_seconds=args.timeout,
        json_mode=not args.no_json_mode,
    )


def _add_runtime_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--base-url")
    parser.add_argument("--model")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-tokens", type=int, default=768)
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--no-json-mode", action="store_true")


def main() -> None:
    parser = argparse.ArgumentParser(prog="person3")
    sub = parser.add_subparsers(dest="command", required=True)

    generate = sub.add_parser("generate")
    generate.add_argument("--bundle", required=True)
    generate.add_argument("--output")
    _add_runtime_args(generate)

    benchmark = sub.add_parser("benchmark")
    benchmark.add_argument("--benchmark", required=True)
    benchmark.add_argument("--output")
    benchmark.add_argument("--latency-budget-ms", type=float)
    _add_runtime_args(benchmark)

    validate = sub.add_parser("validate-output")
    validate.add_argument("--bundle", required=True)
    validate.add_argument("--output-json", required=True)

    tune = sub.add_parser("tune-thresholds")
    tune.add_argument("--input", required=True)
    tune.add_argument("--scores", required=True)
    tune.add_argument("--margins", required=True)
    tune.add_argument("--output")

    args = parser.parse_args()

    if args.command == "generate":
        generator = GroundedGenerator(_runtime(args))
        result, metrics = generator.generate_with_metrics(_read_json(args.bundle))
        _write_json(
            args.output,
            {
                "generation": result,
                "metrics": {
                    "elapsed_ms": metrics.elapsed_ms,
                    "prompt_tokens": metrics.prompt_tokens,
                    "completion_tokens": metrics.completion_tokens,
                    "repair_attempts": metrics.repair_attempts,
                },
            },
        )
    elif args.command == "benchmark":
        generator = GroundedGenerator(_runtime(args))
        report = run_generation_benchmark(
            _read_jsonl(args.benchmark),
            generator,
            latency_budget_ms=args.latency_budget_ms,
        )
        _write_json(args.output, report)
    elif args.command == "validate-output":
        bundle = _read_json(args.bundle)
        output = _read_json(args.output_json)
        validate_generated_output(bundle, output)
        print("OK")
    elif args.command == "tune-thresholds":
        scores = [float(value) for value in args.scores.split(",")]
        margins = [float(value) for value in args.margins.split(",")]
        report = tune_thresholds(
            _read_jsonl(args.input),
            score_floors=scores,
            margin_floors=margins,
        )
        _write_json(args.output, report)


if __name__ == "__main__":
    main()
