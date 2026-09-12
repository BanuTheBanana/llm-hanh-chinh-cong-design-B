"""Run a deterministic, local-only intent/context pilot against GGUF candidates.

The fixture is fictional D0 data. Generated reports/logs stay under ignored local paths.
This is a candidate-selection pilot, not the final held-out legal-quality evaluation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import statistics
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from training.intent_context import (  # noqa: E402
    CONTEXT_SLOTS,
    apply_output_to_state,
    build_messages,
)

DEFAULT_FIXTURE = ROOT / "evaluation/fixtures/intent-context-pilot-v1"
DEFAULT_SCHEMA = ROOT / "docs/giai-doan-5/schema/intent-context-v2.schema.json"
ALLOWED_OUTPUT_ROOT = (ROOT / "evaluation/reports").resolve()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return round(ordered[math.ceil(len(ordered) * fraction) - 1], 3)


def request_json(url: str, *, body: dict | None = None, timeout: float = 90) -> dict:
    payload = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    request = Request(
        url,
        data=payload,
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        method="GET" if payload is None else "POST",
    )
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def wait_ready(base_url: str, process: subprocess.Popen, timeout: float) -> float:
    started = time.perf_counter()
    while time.perf_counter() - started < timeout:
        if process.poll() is not None:
            raise RuntimeError(f"LLAMA_SERVER_EXITED_{process.returncode}")
        try:
            status = request_json(base_url + "/health", timeout=2)
            if status.get("status") == "ok":
                return time.perf_counter() - started
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError):
            pass
        time.sleep(0.25)
    raise TimeoutError("LLAMA_SERVER_START_TIMEOUT")


def gpu_memory_mib() -> int | None:
    command = [
        "nvidia-smi",
        "--query-gpu=memory.used",
        "--format=csv,noheader,nounits",
    ]
    try:
        value = subprocess.check_output(command, text=True, timeout=10).splitlines()[0]
        return int(value.strip())
    except (FileNotFoundError, subprocess.SubprocessError, ValueError, IndexError):
        return None


def normalize_patch(slot: str, patch: dict) -> tuple[str | None, object]:
    op = patch.get("op")
    value = patch.get("value")
    if slot == "field_intents" and isinstance(value, list):
        value = tuple(sorted(value))
    return op, value


def patch_equal(slot: str, predicted: dict, expected: dict) -> bool:
    return normalize_patch(slot, predicted) == normalize_patch(slot, expected)


def semantic_errors(case: dict, predicted: dict) -> list[str]:
    errors = []
    allowed_ids = {item["id"] for item in case["procedure_candidates"]}
    procedure = predicted["patch"]["procedure_id"]
    if procedure["op"] == "SET" and procedure["value"] not in allowed_ids:
        errors.append("PROCEDURE_NOT_IN_CATALOG")
    message = case["current_user_message"]
    for slot in ("procedure_id", "field_intents", "jurisdiction", "as_of"):
        for item in predicted["patch"][slot]["evidence"]:
            if item["message_id"] != "current-user":
                errors.append("EVIDENCE_MESSAGE_ID")
            if item["quote"] not in message:
                errors.append("EVIDENCE_QUOTE_NOT_IN_MESSAGE")
    return errors


def evaluate_candidate(base_url: str, model_name: str, cases: list[dict], schema: dict) -> dict:
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    latencies = []
    failures = Counter()
    group_counts = Counter()
    group_passes = Counter()
    score_counts = Counter()
    raw_rows = []
    input_tokens = []
    output_tokens = []
    slots = CONTEXT_SLOTS

    for case in cases:
        group_counts[case["group"]] += 1
        request_body = {
            "model": model_name,
            "messages": build_messages(case),
            "temperature": 0,
            "top_k": 1,
            "seed": 42,
            "max_tokens": 384,
            "chat_template_kwargs": {"enable_thinking": False},
            "response_format": {"type": "json_object"},
            "json_schema": schema,
        }
        started = time.perf_counter()
        content = ""
        predicted = None
        error_codes = []
        try:
            response = request_json(base_url + "/v1/chat/completions", body=request_body)
            latencies.append((time.perf_counter() - started) * 1000)
            choice = response["choices"][0]
            content = choice["message"].get("content") or ""
            usage = response.get("usage", {})
            input_tokens.append(int(usage.get("prompt_tokens", 0)))
            output_tokens.append(int(usage.get("completion_tokens", 0)))
            predicted = json.loads(content)
            schema_errors = list(validator.iter_errors(predicted))
            if schema_errors:
                error_codes.append("SCHEMA_INVALID")
            else:
                score_counts["schema_valid"] += 1
                error_codes.extend(semantic_errors(case, predicted))
        except (
            HTTPError,
            URLError,
            TimeoutError,
            KeyError,
            IndexError,
            json.JSONDecodeError,
        ) as exc:
            latencies.append((time.perf_counter() - started) * 1000)
            error_codes.append(type(exc).__name__.upper())

        expected = case["expected"]
        semantic_ok = predicted is not None and not error_codes
        if semantic_ok:
            score_counts["semantic_valid"] += 1
            act_ok = predicted["dialogue_act"] == expected["dialogue_act"]
            topic_ok = predicted["topic_action"] == expected["topic_action"]
            patch_results = {
                slot: patch_equal(slot, predicted["patch"][slot], expected["patch"][slot])
                for slot in slots
            }
            exact_patch_ok = all(patch_results.values())
            expected_state = apply_output_to_state(case["state_before"], expected)
            predicted_state = apply_output_to_state(case["state_before"], predicted)
            state_ok = predicted_state == expected_state
            exact_full_ok = act_ok and topic_ok and exact_patch_ok
            full_ok = act_ok and topic_ok and state_ok
            score_counts["dialogue_act"] += int(act_ok)
            score_counts["topic_action"] += int(topic_ok)
            score_counts["joint_patch"] += int(exact_patch_ok)
            score_counts["joint_state"] += int(state_ok)
            score_counts["full_exact_patch_case"] += int(exact_full_ok)
            score_counts["full_state_case"] += int(full_ok)
            for slot, ok in patch_results.items():
                score_counts[f"slot_{slot}"] += int(ok)
            if full_ok:
                group_passes[case["group"]] += 1
        else:
            full_ok = False
        failures.update(error_codes)
        raw_rows.append(
            {
                "case_id": case["case_id"],
                "group": case["group"],
                "passed": full_ok,
                "exact_patch_passed": exact_full_ok if semantic_ok else False,
                "errors": sorted(set(error_codes)),
                "predicted": predicted,
                "raw_content": content if predicted is None else None,
            }
        )

    count = len(cases)
    metrics = {
        key: round(score_counts[key] / count, 6)
        for key in (
            "schema_valid",
            "semantic_valid",
            "dialogue_act",
            "topic_action",
            "joint_patch",
            "joint_state",
            "full_exact_patch_case",
            "full_state_case",
            "slot_procedure_id",
            "slot_field_intents",
            "slot_jurisdiction",
            "slot_as_of",
        )
    }
    return {
        "candidate": model_name,
        "case_count": count,
        "metrics": metrics,
        "per_group_full_state_case": {
            group: {
                "correct": group_passes[group],
                "count": group_counts[group],
                "accuracy": round(group_passes[group] / group_counts[group], 6),
            }
            for group in sorted(group_counts)
        },
        "errors": dict(sorted(failures.items())),
        "latency_ms": {
            "p50": percentile(latencies, 0.5),
            "p95": percentile(latencies, 0.95),
            "mean": round(statistics.fmean(latencies), 3),
        },
        "tokens": {
            "prompt_mean": round(statistics.fmean(input_tokens), 3) if input_tokens else None,
            "completion_mean": round(statistics.fmean(output_tokens), 3) if output_tokens else None,
        },
        "raw_rows": raw_rows,
    }


def safe_name(value: str) -> str:
    return "".join(char.lower() if char.isalnum() else "-" for char in value).strip("-")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--candidate",
        action="append",
        required=True,
        help="NAME=GGUF_PATH or NAME=GGUF_PATH::LORA_GGUF_PATH",
    )
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "evaluation/reports/g5/intent-context-baseline-v1",
    )
    parser.add_argument("--llama-server", default=shutil.which("llama-server"))
    parser.add_argument("--port", type=int, default=18085)
    parser.add_argument("--startup-timeout", type=float, default=120)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    output_dir = args.output_dir.resolve()
    if not output_dir.is_relative_to(ALLOWED_OUTPUT_ROOT):
        raise SystemExit("PRIVATE_EVALUATION_OUTPUT_REQUIRED")
    if not args.llama_server:
        raise SystemExit("LLAMA_SERVER_NOT_FOUND")
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest = read_json(args.fixture / "manifest.json")
    cases_path = args.fixture / manifest["source_file"]
    cases = [json.loads(line) for line in cases_path.read_text(encoding="utf-8").splitlines()]
    if len(cases) != manifest["case_count"] or manifest.get("final_test") is not False:
        raise SystemExit("PILOT_FIXTURE_MANIFEST_INVALID")
    if args.limit:
        cases = cases[: args.limit]
    schema = read_json(args.schema)
    Draft202012Validator.check_schema(schema)
    base_url = f"http://127.0.0.1:{args.port}"
    baseline_gpu = gpu_memory_mib()
    summaries = []

    for candidate_arg in args.candidate:
        if "=" not in candidate_arg:
            raise SystemExit("CANDIDATE_FORMAT_NAME_EQUALS_PATH")
        name, raw_path = candidate_arg.split("=", 1)
        model_part, separator, lora_part = raw_path.partition("::")
        model_path = Path(model_part).resolve()
        lora_path = Path(lora_part).resolve() if separator else None
        if not model_path.is_file():
            raise SystemExit(f"MODEL_NOT_FOUND:{name}")
        if lora_path is not None and not lora_path.is_file():
            raise SystemExit(f"LORA_NOT_FOUND:{name}")
        log_path = output_dir / f"{safe_name(name)}-server.log"
        command = [
            args.llama_server,
            "--model",
            str(model_path),
            "--host",
            "127.0.0.1",
            "--port",
            str(args.port),
            "--ctx-size",
            "4096",
            "--parallel",
            "1",
            "--n-gpu-layers",
            "99",
            "--flash-attn",
            "on",
            "--jinja",
            "--reasoning",
            "off",
            "--chat-template-kwargs",
            '{"enable_thinking":false}',
            "--temperature",
            "0",
            "--top-k",
            "1",
            "--seed",
            "42",
            "--no-context-shift",
        ]
        if lora_path is not None:
            command.extend(["--lora", str(lora_path)])
        loaded_gpu = None
        with log_path.open("w", encoding="utf-8") as log_handle:
            process = subprocess.Popen(command, stdout=log_handle, stderr=subprocess.STDOUT)
            try:
                load_seconds = wait_ready(base_url, process, args.startup_timeout)
                loaded_gpu = gpu_memory_mib()
                result = evaluate_candidate(base_url, name, cases, schema)
            finally:
                process.terminate()
                try:
                    process.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)
        result.update(
            {
                "model_file": model_path.name,
                "model_sha256": sha256(model_path),
                "model_bytes": model_path.stat().st_size,
                "adapter_file": lora_path.name if lora_path else None,
                "adapter_sha256": sha256(lora_path) if lora_path else None,
                "adapter_bytes": lora_path.stat().st_size if lora_path else None,
                "load_seconds": round(load_seconds, 3),
                "gpu_memory_loaded_mib": loaded_gpu,
                "gpu_memory_baseline_mib": baseline_gpu,
                "gpu_memory_delta_mib": (
                    loaded_gpu - baseline_gpu
                    if loaded_gpu is not None and baseline_gpu is not None
                    else None
                ),
            }
        )
        (output_dir / f"{safe_name(name)}.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        summaries.append({key: value for key, value in result.items() if key != "raw_rows"})

    summary = {
        "schema_version": "g5-intent-context-benchmark-v2",
        "scope": "D0 fictional pilot; not final TEST and not legal-answer evaluation",
        "fixture_sha256": sha256(cases_path),
        "schema_sha256": sha256(args.schema),
        "llama_server": str(args.llama_server),
        "llama_server_version": subprocess.check_output(
            [args.llama_server, "--version"], text=True, stderr=subprocess.STDOUT
        ).splitlines()[0],
        "candidate_count": len(summaries),
        "candidates": summaries,
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
