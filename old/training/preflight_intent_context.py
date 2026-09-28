"""Validate intent/context TRAIN/DEV fixtures and local QLoRA readiness."""

# ruff: noqa: E402 -- repository-local modules are added to sys.path below.

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import torch
from transformers import AutoConfig, AutoTokenizer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from training.train_intent_context_qlora import IntentContextDataset, load_cases


def target_procedure_ids(rows: list[dict]) -> set[str]:
    values = set()
    for row in rows:
        patch = row["expected"]["patch"]["procedure_id"]
        if patch["op"] == "SET":
            values.add(patch["value"])
    return values


def catalog_ids(rows: list[dict]) -> set[str]:
    catalogs = {
        tuple(sorted(item["id"] for item in row["procedure_candidates"]))
        for row in rows
        if row.get("data_classification") == "D2_COMPANY_REAL"
    }
    if len(catalogs) != 1:
        raise ValueError("D2_CATALOG_NOT_STABLE")
    return set(next(iter(catalogs)))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train", type=Path, required=True)
    parser.add_argument("--dev", type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--max-length", type=int, default=2304)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    errors: list[str] = []
    try:
        train, train_manifest, train_sha = load_cases(args.train.resolve(), "TRAIN")
        dev, dev_manifest, dev_sha = load_cases(args.dev.resolve(), "DEV")
    except (OSError, ValueError, SystemExit, json.JSONDecodeError) as error:
        train, dev, train_manifest, dev_manifest = [], [], {}, {}
        train_sha = dev_sha = None
        errors.append(str(error) or type(error).__name__)

    train_catalog: set[str] = set()
    dev_catalog: set[str] = set()
    if train and dev:
        try:
            train_catalog = catalog_ids(train)
            dev_catalog = catalog_ids(dev)
            if train_catalog != dev_catalog or len(train_catalog) != 38:
                errors.append("FULL38_CATALOG_REQUIRED")
            if target_procedure_ids(train) & train_catalog != train_catalog:
                errors.append("TRAIN_PROCEDURE_COVERAGE_INCOMPLETE")
            if target_procedure_ids(dev) & dev_catalog != dev_catalog:
                errors.append("DEV_PROCEDURE_COVERAGE_INCOMPLETE")
            if train_manifest.get("source_corpus_sha256") != dev_manifest.get(
                "source_corpus_sha256"
            ):
                errors.append("TRAIN_DEV_CORPUS_MISMATCH")
            if train_manifest.get("catalog_sha256") != dev_manifest.get("catalog_sha256"):
                errors.append("TRAIN_DEV_CATALOG_MISMATCH")
            train_messages = {row["current_user_message"] for row in train}
            if train_messages & {row["current_user_message"] for row in dev}:
                errors.append("TRAIN_DEV_UTTERANCE_LEAKAGE")
        except ValueError as error:
            errors.append(str(error))

    forbidden = [
        str(path)
        for directory in (args.train.resolve(), args.dev.resolve())
        for path in directory.rglob("*")
        if path.is_file() and "test" in path.name.casefold()
    ]
    if forbidden:
        errors.append("TEST_FILE_PRESENT")

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

    encoded = {"train": 0, "dev": 0, "max_train_tokens": 0, "max_dev_tokens": 0}
    if tokenizer is not None and train and dev:
        try:
            train_dataset = IntentContextDataset(train, tokenizer, args.max_length)
            dev_dataset = IntentContextDataset(dev, tokenizer, args.max_length)
            encoded = {
                "train": len(train_dataset),
                "dev": len(dev_dataset),
                "max_train_tokens": max(len(item["input_ids"]) for item in train_dataset.items),
                "max_dev_tokens": max(len(item["input_ids"]) for item in dev_dataset.items),
            }
            if len(train_dataset) != len(train) or len(dev_dataset) != len(dev):
                errors.append("EXAMPLE_EXCEEDS_TOKEN_BUDGET")
        except SystemExit as error:
            errors.append(str(error) or type(error).__name__)

    if not torch.cuda.is_available():
        errors.append("CUDA_NOT_AVAILABLE")
    elif not torch.cuda.is_bf16_supported():
        errors.append("BF16_NOT_SUPPORTED")

    result = {
        "schema_version": "g7-intent-context-full38-preflight-v1",
        "status": "PASS" if not errors else "FAIL",
        "test_data_used": False,
        "model": args.model,
        "revision": args.revision,
        "architecture": architecture,
        "max_length": args.max_length,
        "train_sha256": train_sha,
        "dev_sha256": dev_sha,
        "train_cases": len(train),
        "dev_cases": len(dev),
        "procedure_count": len(train_catalog),
        "encoded": encoded,
        "cuda_available": torch.cuda.is_available(),
        "bf16_supported": torch.cuda.is_bf16_supported() if torch.cuda.is_available() else False,
        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "gpu_memory_bytes": (
            torch.cuda.get_device_properties(0).total_memory if torch.cuda.is_available() else None
        ),
        "errors": sorted(set(errors)),
    }
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        output = args.output.resolve()
        if not output.is_relative_to((ROOT / "training/output").resolve()):
            raise SystemExit("PRIVATE_PREFLIGHT_OUTPUT_REQUIRED")
        output.write_text(rendered, encoding="utf-8", newline="\n")
    print(json.dumps(result, ensure_ascii=False))
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
