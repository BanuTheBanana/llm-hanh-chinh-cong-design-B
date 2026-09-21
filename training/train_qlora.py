"""Run the bounded G5 QLoRA experiment on a private SFT bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ai-service"))
DEFAULT_QWEN_REVISION = "70d244cc86ccca08cf5af4e1e306ecf908b1ad5e"

import torch
from app.grounding import build_grounded_messages
from app.schemas import GroundingEvidenceFragment
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from torch.utils.data import Dataset
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    Trainer,
    TrainingArguments,
    set_seed,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]


def _private_output(path: Path) -> Path:
    resolved = path.resolve()
    allowed = (
        (ROOT / "training" / "output").resolve(),
        (ROOT / "evaluation" / "reports").resolve(),
    )
    if not any(resolved.is_relative_to(root) for root in allowed):
        raise SystemExit("G5_QLORA_PRIVATE_OUTPUT_REQUIRED")
    return resolved


def _validate_bundle(
    bundle: Path,
    manifest: dict,
    train_rows: list[dict],
    validation_rows: list[dict],
):
    if manifest.get("schema_version") != "g5-sft-manifest-v1":
        raise SystemExit("G5_QLORA_MANIFEST_VERSION_INVALID")
    if manifest.get("test_data_used") is not False:
        raise SystemExit("G5_QLORA_TEST_DATA_PROHIBITED")
    for key, filename in (("train", "train.jsonl"), ("validation", "validation.jsonl")):
        expected = manifest.get("files", {}).get(key, {}).get("sha256")
        if not expected or _sha256(bundle / filename) != expected:
            raise SystemExit("G5_QLORA_BUNDLE_HASH_MISMATCH")
    if not train_rows or not validation_rows:
        raise SystemExit("G5_QLORA_EMPTY_SPLIT")
    if any(row.get("split") != "TRAIN" for row in train_rows) or any(
        row.get("split") != "VALIDATION" for row in validation_rows
    ):
        raise SystemExit("G5_QLORA_SPLIT_INVALID")
    row_versions = {
        row.get("dataset_version") for row in [*train_rows, *validation_rows]
    }
    if row_versions != {manifest.get("dataset_version")}:
        raise SystemExit("G5_QLORA_DATASET_VERSION_MISMATCH")
    for row in [*train_rows, *validation_rows]:
        target = row.get("target", {})
        cited = target.get("cited_fragment_ids", [])
        evidence_ids = {item.get("fragment_id") for item in row.get("evidence", [])}
        if target.get("status") == "ANSWER" and (
            not cited or not set(cited) <= evidence_ids
        ):
            raise SystemExit("G5_QLORA_ANSWER_TARGET_INVALID")
        if target.get("status") == "INSUFFICIENT_DATA" and (
            cited or not target.get("missing_information")
        ):
            raise SystemExit("G5_QLORA_ABSTENTION_TARGET_INVALID")
    train_procedures = {row.get("procedure_id") for row in train_rows}
    validation_procedures = {row.get("procedure_id") for row in validation_rows}
    if train_procedures & validation_procedures:
        raise SystemExit("G5_QLORA_PROCEDURE_SPLIT_LEAKAGE")


class SFTDataset(Dataset):
    def __init__(self, rows, tokenizer, max_length):
        self.items = []
        self.source_count = len(rows)
        self.dropped = 0
        for row in rows:
            evidence = [
                GroundingEvidenceFragment.model_validate(item)
                for item in row["evidence"]
            ]
            messages = build_grounded_messages(query=row["query"], evidence=evidence)
            target = json.dumps(
                row["target"], ensure_ascii=False, separators=(",", ":")
            )
            prompt_encoding = tokenizer.apply_chat_template(
                messages,
                tokenize=True,
                add_generation_prompt=True,
                enable_thinking=False,
            )
            full_encoding = tokenizer.apply_chat_template(
                [*messages, {"role": "assistant", "content": target}],
                tokenize=True,
                add_generation_prompt=False,
                enable_thinking=False,
            )
            prompt_ids = _input_ids(prompt_encoding)
            full_ids = _input_ids(full_encoding)
            if len(prompt_ids) >= max_length or len(full_ids) > max_length:
                self.dropped += 1
                continue
            labels = [-100] * len(prompt_ids) + full_ids[len(prompt_ids) :]
            self.items.append(
                {
                    "input_ids": full_ids,
                    "attention_mask": [1] * len(full_ids),
                    "labels": labels,
                }
            )
        if not self.items:
            raise ValueError("G5_SFT_NO_EXAMPLE_FITS_CONTEXT")

    def __len__(self):
        return len(self.items)

    def __getitem__(self, index):
        return self.items[index]


def _input_ids(encoding) -> list[int]:
    """Normalize chat-template output across Transformers releases."""
    if hasattr(encoding, "input_ids"):
        encoding = encoding.input_ids
    elif isinstance(encoding, dict):
        encoding = encoding["input_ids"]
    if isinstance(encoding, torch.Tensor):
        encoding = encoding.tolist()
    if encoding and isinstance(encoding[0], list):
        encoding = encoding[0]
    return list(encoding)


@dataclass
class Collator:
    pad_token_id: int

    def __call__(self, features):
        width = max(len(item["input_ids"]) for item in features)
        batch = {"input_ids": [], "attention_mask": [], "labels": []}
        for item in features:
            padding = width - len(item["input_ids"])
            batch["input_ids"].append(item["input_ids"] + [self.pad_token_id] * padding)
            batch["attention_mask"].append(item["attention_mask"] + [0] * padding)
            batch["labels"].append(item["labels"] + [-100] * padding)
        return {
            key: torch.tensor(value, dtype=torch.long) for key, value in batch.items()
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", default="Qwen/Qwen3-1.7B")
    parser.add_argument("--revision", default=DEFAULT_QWEN_REVISION)
    parser.add_argument("--max-length", type=int, default=2304)
    parser.add_argument("--epochs", type=float, default=1.0)
    parser.add_argument("--learning-rate", type=float, default=0.0002)
    parser.add_argument("--lora-rank", type=int, choices=(8, 16), default=16)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    if not torch.cuda.is_available() or not torch.cuda.is_bf16_supported():
        raise SystemExit("G5_QLORA_REQUIRES_BF16_CUDA")
    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats()
    gpu_baseline_allocated = torch.cuda.memory_allocated()
    gpu_baseline_reserved = torch.cuda.memory_reserved()
    output = _private_output(args.output)
    output.mkdir(parents=True, exist_ok=True)
    if (output / "adapter_config.json").exists():
        raise SystemExit("G5_QLORA_OUTPUT_ALREADY_EXISTS")
    bundle = args.bundle.resolve()
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    train_rows = _load_jsonl(bundle / "train.jsonl")
    validation_rows = _load_jsonl(bundle / "validation.jsonl")
    _validate_bundle(bundle, manifest, train_rows, validation_rows)
    if args.smoke:
        random.Random(args.seed).shuffle(train_rows)
        train_rows = train_rows[:8]
        validation_rows = validation_rows[:4]
    set_seed(args.seed)
    tokenizer = AutoTokenizer.from_pretrained(
        args.model, revision=args.revision, trust_remote_code=False
    )
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
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
    model.config.use_cache = False
    model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)
    model = get_peft_model(
        model,
        LoraConfig(
            r=args.lora_rank,
            lora_alpha=args.lora_rank * 2,
            lora_dropout=0.05,
            bias="none",
            task_type="CAUSAL_LM",
            target_modules=[
                "q_proj",
                "k_proj",
                "v_proj",
                "o_proj",
                "gate_proj",
                "up_proj",
                "down_proj",
            ],
        ),
    )
    train_dataset = SFTDataset(train_rows, tokenizer, args.max_length)
    validation_dataset = SFTDataset(validation_rows, tokenizer, args.max_length)
    if train_dataset.dropped or validation_dataset.dropped:
        raise SystemExit("G5_SFT_EXAMPLE_EXCEEDS_CONTEXT")
    training_args = TrainingArguments(
        output_dir=str(output / "checkpoints"),
        num_train_epochs=args.epochs,
        max_steps=2 if args.smoke else -1,
        per_device_train_batch_size=1,
        per_device_eval_batch_size=1,
        gradient_accumulation_steps=8,
        learning_rate=args.learning_rate,
        lr_scheduler_type="cosine",
        warmup_steps=1,
        bf16=True,
        tf32=True,
        gradient_checkpointing=True,
        eval_strategy="steps",
        eval_steps=2 if args.smoke else 10,
        save_strategy="no",
        logging_steps=1,
        report_to="none",
        remove_unused_columns=False,
        seed=args.seed,
        data_seed=args.seed,
    )
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=validation_dataset,
        data_collator=Collator(tokenizer.pad_token_id),
    )
    train_result = trainer.train()
    eval_result = trainer.evaluate()
    torch.cuda.synchronize()
    model.save_pretrained(output, safe_serialization=True)
    tokenizer.save_pretrained(output)
    adapter_files = {
        path.name: _sha256(path)
        for path in output.iterdir()
        if path.is_file() and path.name != "training_manifest.json"
    }
    result = {
        "schema_version": "g5-qlora-run-v1",
        "base_model": args.model,
        "base_revision": args.revision,
        "source_manifest_sha256": _sha256(bundle / "manifest.json"),
        "test_data_used": False,
        "smoke": args.smoke,
        "seed": args.seed,
        "config": {
            "max_length": args.max_length,
            "epochs": args.epochs,
            "learning_rate": args.learning_rate,
            "lora_rank": args.lora_rank,
            "quantization": "NF4_DOUBLE_QUANT_BF16",
        },
        "examples": {
            "train": len(train_dataset),
            "validation": len(validation_dataset),
        },
        "train_metrics": train_result.metrics,
        "eval_metrics": eval_result,
        "resource_metrics": {
            "gpu_name": torch.cuda.get_device_name(0),
            "gpu_total_memory_bytes": torch.cuda.get_device_properties(0).total_memory,
            "process_baseline_allocated_bytes": gpu_baseline_allocated,
            "process_baseline_reserved_bytes": gpu_baseline_reserved,
            "process_peak_allocated_bytes": torch.cuda.max_memory_allocated(),
            "process_peak_reserved_bytes": torch.cuda.max_memory_reserved(),
        },
        "artifacts": adapter_files,
    }
    (output / "training_manifest.json").write_text(
        json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "status": "PASS",
                "smoke": args.smoke,
                "examples": result["examples"],
                "train_loss": result["train_metrics"].get("train_loss"),
                "eval_loss": result["eval_metrics"].get("eval_loss"),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
