"""Integrity tests for the public, fictional G5 train/DEV pilot fixtures."""

import hashlib
import json
from collections import Counter
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[3]
FIXTURE_ROOT = ROOT / "evaluation/fixtures"
SCHEMA = json.loads(
    (ROOT / "docs/giai-doan-5/schema/intent-context-v2.schema.json").read_text(encoding="utf-8")
)
VALIDATOR = Draft202012Validator(SCHEMA, format_checker=FormatChecker())


def load_fixture(name):
    directory = FIXTURE_ROOT / name
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    source = directory / manifest["source_file"]
    rows = [json.loads(line) for line in source.read_text(encoding="utf-8").splitlines()]
    return manifest, source, rows


def expanded_target(row):
    target = json.loads(json.dumps(row["expected"]))
    target["schema_version"] = "g5-intent-context-v2"
    for patch in target["patch"].values():
        patch["evidence"] = (
            []
            if patch["op"] == "KEEP"
            else [{"message_id": "current-user", "quote": row["current_user_message"]}]
        )
    return target


def test_manifests_counts_hashes_and_classification():
    for name in (
        "intent-context-train-pilot-v1",
        "intent-context-train-hard-v2",
        "intent-context-pilot-v1",
    ):
        manifest, source, rows = load_fixture(name)
        assert manifest["classification"] == "D0_SYSTEM_SMOKE"
        assert manifest["contains_company_data"] is False
        assert len(rows) == manifest["case_count"]
        assert Counter(row["group"] for row in rows) == manifest["groups"]
        assert hashlib.sha256(source.read_bytes()).hexdigest() == manifest["content_sha256"]


def test_train_and_dev_have_no_id_or_exact_utterance_overlap():
    _, _, train = load_fixture("intent-context-train-pilot-v1")
    _, _, dev = load_fixture("intent-context-pilot-v1")
    assert {row["case_id"] for row in train}.isdisjoint(row["case_id"] for row in dev)
    train_text = {" ".join(row["current_user_message"].casefold().split()) for row in train}
    dev_text = {" ".join(row["current_user_message"].casefold().split()) for row in dev}
    assert train_text.isdisjoint(dev_text)

    _, _, hard_train = load_fixture("intent-context-train-hard-v2")
    hard_ids = {row["case_id"] for row in hard_train}
    hard_text = {" ".join(row["current_user_message"].casefold().split()) for row in hard_train}
    assert len(hard_ids) == len(hard_train)
    assert len(hard_text) == len(hard_train)
    assert hard_ids.isdisjoint(row["case_id"] for row in dev)
    assert hard_text.isdisjoint(dev_text)


def test_all_reviewed_labels_expand_to_contract_and_known_candidates():
    for name in (
        "intent-context-train-pilot-v1",
        "intent-context-train-hard-v2",
        "intent-context-pilot-v1",
    ):
        _, _, rows = load_fixture(name)
        assert len({row["case_id"] for row in rows}) == len(rows)
        for row in rows:
            target = expanded_target(row)
            VALIDATOR.validate(target)
            candidate_ids = {candidate["id"] for candidate in row["procedure_candidates"]}
            procedure = target["patch"]["procedure_id"]
            if procedure["op"] == "SET":
                assert procedure["value"] in candidate_ids
