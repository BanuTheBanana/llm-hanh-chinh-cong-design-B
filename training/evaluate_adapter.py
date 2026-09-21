"""Compare base and optional G5 adapter on the private validation split."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ai-service"))
DEFAULT_QWEN_REVISION = "70d244cc86ccca08cf5af4e1e306ecf908b1ad5e"

import torch
from app.grounding import (
    build_grounded_messages,
    parse_and_validate_grounded_output,
)
from app.providers.base import ProviderResponseError
from app.schemas import GroundingEvidenceFragment
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig


def normalized(text):
    return re.sub(r"\s+", " ", text).strip().casefold()


def mean_metric(rows: list[dict], key: str) -> float | None:
    return sum(row[key] for row in rows) / len(rows) if rows else None


def percentile(values: list[float], percentile_value: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, math.ceil(percentile_value * len(ordered)) - 1)
    return ordered[index]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _private_output(path: Path) -> Path:
    resolved = path.resolve()
    if not resolved.is_relative_to((ROOT / "evaluation" / "reports").resolve()):
        raise SystemExit("G5_EVAL_PRIVATE_OUTPUT_REQUIRED")
    return resolved


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", default="Qwen/Qwen3-1.7B")
    parser.add_argument("--revision", default=DEFAULT_QWEN_REVISION)
    parser.add_argument("--adapter", type=Path)
    parser.add_argument("--limit", type=int, default=40)
    parser.add_argument("--max-new-tokens", type=int, default=320)
    parser.add_argument(
        "--one-variant-per-base",
        action="store_true",
        help="Evaluate one distractor-order variant for each independent scenario.",
    )
    args = parser.parse_args()
    if not torch.cuda.is_available() or not torch.cuda.is_bf16_supported():
        raise SystemExit("G5_EVAL_REQUIRES_BF16_CUDA")
    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats()
    gpu_baseline_allocated = torch.cuda.memory_allocated()
    gpu_baseline_reserved = torch.cuda.memory_reserved()
    output_path = _private_output(args.output)
    if output_path.exists():
        raise SystemExit("G5_EVAL_OUTPUT_ALREADY_EXISTS")
    bundle = args.bundle.resolve()
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    validation_path = bundle / "validation.jsonl"
    if (
        manifest.get("schema_version") != "g5-sft-manifest-v1"
        or manifest.get("test_data_used") is not False
        or _sha256(validation_path) != manifest.get("files", {}).get("validation", {}).get("sha256")
    ):
        raise SystemExit("G5_EVAL_BUNDLE_INVALID")
    rows = [
        json.loads(line)
        for line in validation_path.read_text(encoding="utf-8").splitlines()
        if line
    ]
    if not rows or any(row.get("split") != "VALIDATION" for row in rows):
        raise SystemExit("G5_EVAL_VALIDATION_SPLIT_INVALID")
    for row in rows:
        target = row.get("target", {})
        cited = target.get("cited_fragment_ids", [])
        if target.get("status") not in {"ANSWER", "INSUFFICIENT_DATA"}:
            raise SystemExit("G5_EVAL_TARGET_STATUS_INVALID")
        if target.get("status") == "ANSWER" and not cited:
            raise SystemExit("G5_EVAL_ANSWER_TARGET_INVALID")
        if target.get("status") == "INSUFFICIENT_DATA" and cited:
            raise SystemExit("G5_EVAL_ABSTENTION_TARGET_INVALID")
    if args.one_variant_per_base:
        unique_rows: dict[str, dict] = {}
        for row in rows:
            unique_rows.setdefault(row["base_scenario_id"], row)
        rows = list(unique_rows.values())
    rows = rows[: args.limit]
    tokenizer = AutoTokenizer.from_pretrained(
        args.model, revision=args.revision, trust_remote_code=False
    )
    quantization = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype=torch.bfloat16,
    )
    model = AutoModelForCausalLM.from_pretrained(
        args.model,
        revision=args.revision,
        quantization_config=quantization,
        dtype=torch.bfloat16,
        device_map={"": 0},
        trust_remote_code=False,
    )
    if args.adapter:
        adapter_manifest_path = args.adapter.resolve() / "training_manifest.json"
        if not adapter_manifest_path.is_file():
            raise SystemExit("G5_EVAL_ADAPTER_MANIFEST_REQUIRED")
        adapter_manifest = json.loads(adapter_manifest_path.read_text(encoding="utf-8"))
        manifest_schema = adapter_manifest.get("schema_version")
        expected_source_sha = _sha256(bundle / "manifest.json")
        if manifest_schema == "g5-qlora-run-v1":
            source_bound = (
                adapter_manifest.get("source_manifest_sha256") == expected_source_sha
            )
        elif manifest_schema == "g6-single-qwen-multitask-qlora-v1":
            source_bound = (
                adapter_manifest.get("sources", {}).get("answer_manifest_sha256")
                == expected_source_sha
            )
        else:
            source_bound = False
        if (
            adapter_manifest.get("base_model") != args.model
            or adapter_manifest.get("base_revision") != args.revision
            or not source_bound
            or adapter_manifest.get("test_data_used") is not False
        ):
            raise SystemExit("G5_EVAL_ADAPTER_BINDING_INVALID")
        model = PeftModel.from_pretrained(model, args.adapter)
    model.eval()
    results = []
    for row in rows:
        evidence = [GroundingEvidenceFragment.model_validate(item) for item in row["evidence"]]
        messages = build_grounded_messages(query=row["query"], evidence=evidence)
        input_encoding = tokenizer.apply_chat_template(
            messages,
            tokenize=True,
            add_generation_prompt=True,
            enable_thinking=False,
            return_tensors="pt",
        )
        input_ids = (
            input_encoding.input_ids if hasattr(input_encoding, "input_ids") else input_encoding
        ).to(model.device)
        attention_mask = torch.ones_like(input_ids)
        started = time.perf_counter()
        with torch.inference_mode():
            output = model.generate(
                input_ids,
                attention_mask=attention_mask,
                max_new_tokens=args.max_new_tokens,
                do_sample=False,
                pad_token_id=tokenizer.eos_token_id,
            )
        raw = tokenizer.decode(output[0, input_ids.shape[1] :], skip_special_tokens=True)
        allowed = {item.fragment_id for item in evidence}
        valid = False
        status_correct = False
        expected_status = row["target"]["status"]
        is_answer = expected_status == "ANSWER"
        citation_recall = 0.0 if is_answer else None
        claim_coverage = 0.0 if is_answer else None
        abstention_correct = None if is_answer else False
        missing_information_recall = None if is_answer else 0.0
        try:
            parsed = parse_and_validate_grounded_output(raw_text=raw, allowed_fragment_ids=allowed)
            valid = True
            status_correct = parsed.status == expected_status
            gold_ids = set(row["target"]["cited_fragment_ids"])
            if is_answer:
                citation_recall = len(set(parsed.cited_fragment_ids) & gold_ids) / len(gold_ids)
                gold_texts = [item.text for item in evidence if item.fragment_id in gold_ids]
                claim_coverage = sum(
                    normalized(text) in normalized(parsed.answer) for text in gold_texts
                ) / len(gold_texts)
            else:
                expected_missing = set(row["target"].get("missing_information", []))
                predicted_missing = set(parsed.missing_information)
                abstention_correct = status_correct and not parsed.cited_fragment_ids
                missing_information_recall = (
                    len(predicted_missing & expected_missing) / len(expected_missing)
                    if expected_missing
                    else float(not predicted_missing)
                )
        except ProviderResponseError:
            pass
        results.append(
            {
                "example_id": row["example_id"],
                "contract_valid": valid,
                "expected_status": expected_status,
                "status_correct": status_correct,
                "citation_recall": citation_recall,
                "claim_coverage": claim_coverage,
                "abstention_correct": abstention_correct,
                "missing_information_recall": missing_information_recall,
                "latency_ms": round((time.perf_counter() - started) * 1000, 2),
            }
        )
        if len(results) % 5 == 0 or len(results) == len(rows):
            print(f"evaluated={len(results)}/{len(rows)}", flush=True)
    denominator = len(results)
    torch.cuda.synchronize()
    latencies = [item["latency_ms"] for item in results]
    answer_results = [item for item in results if item["expected_status"] == "ANSWER"]
    abstention_results = [
        item for item in results if item["expected_status"] == "INSUFFICIENT_DATA"
    ]
    summary = {
        "schema_version": "g5-model-evaluation-v2",
        "model": args.model,
        "model_revision": args.revision,
        "adapter_used": args.adapter is not None,
        "adapter_manifest_sha256": (
            _sha256(args.adapter.resolve() / "training_manifest.json")
            if args.adapter and (args.adapter.resolve() / "training_manifest.json").is_file()
            else None
        ),
        "test_data_used": False,
        "validation_sha256": _sha256(validation_path),
        "count": denominator,
        "max_new_tokens": args.max_new_tokens,
        "one_variant_per_base": args.one_variant_per_base,
        "contract_accuracy": sum(item["contract_valid"] for item in results) / denominator,
        "status_accuracy": sum(item["status_correct"] for item in results) / denominator,
        "answer_count": len(answer_results),
        "citation_recall": mean_metric(answer_results, "citation_recall"),
        "verbatim_claim_coverage": mean_metric(answer_results, "claim_coverage"),
        "abstention_count": len(abstention_results),
        "abstention_accuracy": mean_metric(abstention_results, "abstention_correct"),
        "missing_information_recall": mean_metric(
            abstention_results, "missing_information_recall"
        ),
        "mean_latency_ms": sum(latencies) / denominator,
        "p50_latency_ms": percentile(latencies, 0.50),
        "p95_latency_ms": percentile(latencies, 0.95),
        "resource_metrics": {
            "gpu_name": torch.cuda.get_device_name(0),
            "gpu_total_memory_bytes": torch.cuda.get_device_properties(0).total_memory,
            "process_baseline_allocated_bytes": gpu_baseline_allocated,
            "process_baseline_reserved_bytes": gpu_baseline_reserved,
            "process_peak_allocated_bytes": torch.cuda.max_memory_allocated(),
            "process_peak_reserved_bytes": torch.cuda.max_memory_reserved(),
        },
        "results": results,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps({key: value for key, value in summary.items() if key != "results"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
