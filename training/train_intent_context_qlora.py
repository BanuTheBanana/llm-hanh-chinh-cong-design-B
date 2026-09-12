"""Pilot QLoRA training for the G5 structured intent/context task."""

# ruff: noqa: E402 -- repository-local training helpers are added to sys.path below.

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import torch
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from torch.utils.data import Dataset
from transformers import (
    AutoConfig,
    AutoModelForCausalLM,
    AutoModelForMultimodalLM,
    AutoProcessor,
    AutoTokenizer,
    BitsAndBytesConfig,
    Trainer,
    TrainingArguments,
    set_seed,
)

from training.intent_context import build_messages, build_target

PRIVATE_OUTPUT_ROOT = (ROOT / "training/output").resolve()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_cases(directory: Path, expected_split: str) -> tuple[list[dict], dict, str]:
    manifest_path = directory / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    cases_path = directory / manifest["source_file"]
    cases = [json.loads(line) for line in cases_path.read_text(encoding="utf-8").splitlines()]
    if len(cases) != manifest["case_count"]:
        raise SystemExit(f"{expected_split}_COUNT_MISMATCH")
    if manifest.get("contains_company_data") is not False:
        raise SystemExit(f"{expected_split}_PILOT_MUST_BE_D0")
    if expected_split == "TRAIN" and manifest.get("split") != "TRAIN":
        raise SystemExit("TRAIN_SPLIT_REQUIRED")
    if expected_split == "DEV" and manifest.get("final_test") is not False:
        raise SystemExit("DEV_MUST_NOT_BE_FINAL_TEST")
    return cases, manifest, sha256(cases_path)


def input_ids(value) -> list[int]:
    if hasattr(value, "input_ids"):
        value = value.input_ids
    elif isinstance(value, dict):
        value = value["input_ids"]
    if isinstance(value, torch.Tensor):
        value = value.tolist()
    if value and isinstance(value[0], list):
        value = value[0]
    return list(value)


class IntentContextDataset(Dataset):
    def __init__(self, cases: list[dict], processor, max_length: int):
        self.items = []
        self.dropped = 0
        for row in cases:
            messages = build_messages(row)
            target = json.dumps(build_target(row), ensure_ascii=False, separators=(",", ":"))
            prompt = input_ids(
                processor.apply_chat_template(
                    messages,
                    tokenize=True,
                    add_generation_prompt=True,
                    enable_thinking=False,
                )
            )
            complete = input_ids(
                processor.apply_chat_template(
                    [*messages, {"role": "assistant", "content": target}],
                    tokenize=True,
                    add_generation_prompt=False,
                    enable_thinking=False,
                )
            )
            if len(prompt) >= max_length or len(complete) > max_length:
                self.dropped += 1
                continue
            self.items.append(
                {
                    "input_ids": complete,
                    "attention_mask": [1] * len(complete),
                    "labels": [-100] * len(prompt) + complete[len(prompt) :],
                }
            )
        if not self.items:
            raise SystemExit("NO_INTENT_CONTEXT_CASE_FITS")

    def __len__(self):
        return len(self.items)

    def __getitem__(self, index):
        return self.items[index]


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
        return {key: torch.tensor(value, dtype=torch.long) for key, value in batch.items()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--train", type=Path, required=True)
    parser.add_argument("--dev", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-length", type=int, default=1024)
    parser.add_argument("--epochs", type=float, default=1.0)
    parser.add_argument("--learning-rate", type=float, default=0.0002)
    parser.add_argument("--lora-rank", type=int, choices=(8, 16), default=16)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    if not torch.cuda.is_available() or not torch.cuda.is_bf16_supported():
        raise SystemExit("BF16_CUDA_REQUIRED")
    output = args.output.resolve()
    if not output.is_relative_to(PRIVATE_OUTPUT_ROOT):
        raise SystemExit("PRIVATE_TRAINING_OUTPUT_REQUIRED")
    output.mkdir(parents=True, exist_ok=False)

    train_cases, train_manifest, train_sha = load_cases(args.train.resolve(), "TRAIN")
    dev_cases, dev_manifest, dev_sha = load_cases(args.dev.resolve(), "DEV")
    train_messages = {row["current_user_message"] for row in train_cases}
    if train_messages & {row["current_user_message"] for row in dev_cases}:
        raise SystemExit("TRAIN_DEV_UTTERANCE_LEAKAGE")
    if args.smoke:
        random.Random(args.seed).shuffle(train_cases)
        train_cases = train_cases[:8]
        dev_cases = dev_cases[:4]
    set_seed(args.seed)

    config = AutoConfig.from_pretrained(args.model, revision=args.revision, trust_remote_code=False)
    architectures = set(config.architectures or [])
    multimodal = any("ConditionalGeneration" in name for name in architectures)
    if multimodal:
        processor = AutoProcessor.from_pretrained(
            args.model, revision=args.revision, trust_remote_code=False
        )
        tokenizer = processor.tokenizer
        model_class = AutoModelForMultimodalLM
        target_modules = [
            "q_proj",
            "k_proj",
            "v_proj",
            "o_proj",
            "in_proj_qkv",
            "in_proj_z",
            "in_proj_a",
            "in_proj_b",
            "out_proj",
            "gate_proj",
            "up_proj",
            "down_proj",
        ]
    else:
        processor = AutoTokenizer.from_pretrained(
            args.model, revision=args.revision, trust_remote_code=False
        )
        tokenizer = processor
        model_class = AutoModelForCausalLM
        target_modules = [
            "q_proj",
            "k_proj",
            "v_proj",
            "o_proj",
            "gate_proj",
            "up_proj",
            "down_proj",
        ]
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    train_dataset = IntentContextDataset(train_cases, processor, args.max_length)
    dev_dataset = IntentContextDataset(dev_cases, processor, args.max_length)
    quantization = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype=torch.bfloat16,
    )
    model = model_class.from_pretrained(
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
            target_modules=target_modules,
        ),
    )
    trainable = sum(
        parameter.numel() for parameter in model.parameters() if parameter.requires_grad
    )
    if trainable <= 0:
        raise SystemExit("NO_TRAINABLE_PARAMETER")
    trainer = Trainer(
        model=model,
        args=TrainingArguments(
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
            eval_strategy="steps" if args.smoke else "epoch",
            eval_steps=2 if args.smoke else None,
            save_strategy="no",
            logging_steps=1,
            report_to="none",
            remove_unused_columns=False,
            seed=args.seed,
            data_seed=args.seed,
        ),
        train_dataset=train_dataset,
        eval_dataset=dev_dataset,
        data_collator=Collator(tokenizer.pad_token_id),
    )
    train_result = trainer.train()
    eval_result = trainer.evaluate()
    model.save_pretrained(output, safe_serialization=True)
    processor.save_pretrained(output)
    artifact_hashes = {
        path.name: sha256(path)
        for path in output.iterdir()
        if path.is_file() and path.name != "training_manifest.json"
    }
    run_manifest = {
        "schema_version": "g5-intent-context-qlora-pilot-v1",
        "purpose": "Candidate pilot; not final TEST",
        "model": args.model,
        "revision": args.revision,
        "architectures": sorted(architectures),
        "multimodal_loader": multimodal,
        "target_modules": target_modules,
        "lora_rank": args.lora_rank,
        "seed": args.seed,
        "epochs": args.epochs,
        "learning_rate": args.learning_rate,
        "train_fixture_version": train_manifest["schema_version"],
        "train_fixture_sha256": train_sha,
        "dev_fixture_version": dev_manifest["schema_version"],
        "dev_fixture_sha256": dev_sha,
        "train_examples": len(train_dataset),
        "dev_examples": len(dev_dataset),
        "dropped_train": train_dataset.dropped,
        "dropped_dev": dev_dataset.dropped,
        "trainable_parameters": trainable,
        "train_metrics": train_result.metrics,
        "eval_metrics": eval_result,
        "artifacts": artifact_hashes,
    }
    (output / "training_manifest.json").write_text(
        json.dumps(run_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(run_manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
