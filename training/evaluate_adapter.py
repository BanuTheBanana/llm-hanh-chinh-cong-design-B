"""Compare base and optional G5 adapter on the private validation split."""

# ruff: noqa: E402 -- the private ai-service package is added to sys.path below.

from __future__ import annotations

import argparse
import hashlib
import json
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
        torch_dtype=torch.bfloat16,
        device_map={"": 0},
        trust_remote_code=False,
    )
    if args.adapter:
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
        citation_recall = 0.0
        claim_coverage = 0.0
        try:
            parsed = parse_and_validate_grounded_output(raw_text=raw, allowed_fragment_ids=allowed)
            valid = True
            gold_ids = set(row["target"]["cited_fragment_ids"])
            citation_recall = len(set(parsed.cited_fragment_ids) & gold_ids) / len(gold_ids)
            gold_texts = [item.text for item in evidence if item.fragment_id in gold_ids]
            claim_coverage = sum(
                normalized(text) in normalized(parsed.answer) for text in gold_texts
            ) / len(gold_texts)
        except ProviderResponseError:
            pass
        results.append(
            {
                "example_id": row["example_id"],
                "contract_valid": valid,
                "citation_recall": citation_recall,
                "claim_coverage": claim_coverage,
                "latency_ms": round((time.perf_counter() - started) * 1000, 2),
            }
        )
        if len(results) % 5 == 0 or len(results) == len(rows):
            print(f"evaluated={len(results)}/{len(rows)}", flush=True)
    denominator = len(results)
    summary = {
        "schema_version": "g5-model-evaluation-v1",
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
        "citation_recall": sum(item["citation_recall"] for item in results) / denominator,
        "verbatim_claim_coverage": sum(item["claim_coverage"] for item in results) / denominator,
        "mean_latency_ms": sum(item["latency_ms"] for item in results) / denominator,
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
