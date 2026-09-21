"""Verify a private SFT bundle and local GPU/model assets before QLoRA training."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bitsandbytes
import peft
import torch
import transformers
from train_qlora import SFTDataset, _load_jsonl, _validate_bundle
from transformers import AutoConfig, AutoTokenizer


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--max-length", type=int, default=2304)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    errors: list[str] = []
    bundle = args.bundle.resolve()
    try:
        manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
        train_rows = _load_jsonl(bundle / "train.jsonl")
        validation_rows = _load_jsonl(bundle / "validation.jsonl")
        _validate_bundle(bundle, manifest, train_rows, validation_rows)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, SystemExit, ValueError) as error:
        errors.append(str(error) or type(error).__name__)
        manifest = {}
        train_rows = []
        validation_rows = []

    if manifest.get("release_status") != "READY_FOR_QLORA":
        errors.append("QLORA_BUNDLE_NOT_RELEASED")
    unexpected_test_files = [
        path for path in bundle.rglob("*") if path.is_file() and "test" in path.name.casefold()
    ]
    if unexpected_test_files:
        errors.append("TEST_FILE_PRESENT_IN_TRAINING_BUNDLE")
    if not torch.cuda.is_available():
        errors.append("CUDA_NOT_AVAILABLE")
    elif not torch.cuda.is_bf16_supported():
        errors.append("BF16_NOT_SUPPORTED")

    tokenizer = None
    architecture = None
    try:
        config = AutoConfig.from_pretrained(
            args.model,
            revision=args.revision,
            trust_remote_code=False,
            local_files_only=True,
        )
        architecture = list(config.architectures or [])
        tokenizer = AutoTokenizer.from_pretrained(
            args.model,
            revision=args.revision,
            trust_remote_code=False,
            local_files_only=True,
        )
        if tokenizer.pad_token_id is None:
            tokenizer.pad_token = tokenizer.eos_token
    except (OSError, ValueError) as error:
        errors.append(f"LOCKED_MODEL_NOT_AVAILABLE:{type(error).__name__}")

    encoded_counts = {"train": 0, "validation": 0}
    if tokenizer is not None and train_rows and validation_rows:
        try:
            train_dataset = SFTDataset(train_rows, tokenizer, args.max_length)
            validation_dataset = SFTDataset(validation_rows, tokenizer, args.max_length)
            encoded_counts = {
                "train": len(train_dataset),
                "validation": len(validation_dataset),
            }
            if len(train_dataset) != len(train_rows) or len(validation_dataset) != len(
                validation_rows
            ):
                errors.append("EXAMPLE_EXCEEDS_TOKEN_BUDGET")
        except ValueError as error:
            errors.append(str(error) or type(error).__name__)

    result = {
        "architecture": architecture,
        "bundle_dataset_version": manifest.get("dataset_version"),
        "cuda": torch.version.cuda,
        "cuda_available": torch.cuda.is_available(),
        "encoded_examples": encoded_counts,
        "errors": sorted(set(errors)),
        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "libraries": {
            "bitsandbytes": bitsandbytes.__version__,
            "peft": peft.__version__,
            "torch": torch.__version__,
            "transformers": transformers.__version__,
        },
        "max_length": args.max_length,
        "model": args.model,
        "revision": args.revision,
        "status": "PASS" if not errors else "FAIL",
    }
    output = json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(output, encoding="utf-8", newline="\n")
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    return 0 if not errors else 2


if __name__ == "__main__":
    sys.exit(main())
