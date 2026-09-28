"""Structural checks for the planned NLU contract; not model-quality evaluation."""

import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

SCHEMA_DIR = Path(__file__).resolve().parents[3] / "docs/giai-doan-5/schema"
SCHEMA = json.loads((SCHEMA_DIR / "intent-context-v2.schema.json").read_text(encoding="utf-8"))
EXAMPLE = json.loads((SCHEMA_DIR / "intent-context-v2.example.json").read_text(encoding="utf-8"))
VALIDATOR = Draft202012Validator(SCHEMA, format_checker=FormatChecker())


def test_schema_and_fictional_followup_example():
    Draft202012Validator.check_schema(SCHEMA)
    VALIDATOR.validate(EXAMPLE)


@pytest.mark.parametrize(
    ("op", "value", "valid"),
    [("KEEP", None, True), ("SET", "fixture-procedure-alpha", True), ("CLEAR", None, True)],
)
def test_three_distinct_operations(op, value, valid):
    result = copy.deepcopy(EXAMPLE)
    result["patch"]["procedure_id"] = {
        "op": op,
        "value": value,
        "evidence": [] if op == "KEEP" else [{"message_id": "fixture-user-3", "quote": "Mẫu"}],
    }
    assert VALIDATOR.is_valid(result) is valid


@pytest.mark.parametrize(
    "invalid_patch",
    [
        {"op": "SET", "value": None, "evidence": [{"message_id": "u", "quote": "phí"}]},
        {"op": "SET", "value": ["fees"], "evidence": []},
        {"op": "KEEP", "value": ["fees"], "evidence": []},
        {"op": "CLEAR", "value": None, "evidence": []},
        {"op": "APPEND", "value": ["fees"], "evidence": []},
        {"op": "SET", "value": ["unknown"], "evidence": [{"message_id": "u", "quote": "x"}]},
        {"op": "SET", "value": ["fees", "fees"], "evidence": [{"message_id": "u", "quote": "x"}]},
    ],
)
def test_reject_invalid_field_patch(invalid_patch):
    result = copy.deepcopy(EXAMPLE)
    result["patch"]["field_intents"] = invalid_patch
    assert not VALIDATOR.is_valid(result)


def test_no_model_supplied_ownership_or_unknown_fields():
    result = copy.deepcopy(EXAMPLE)
    result["user_id"] = "not-model-owned"
    assert not VALIDATOR.is_valid(result)
    result = copy.deepcopy(EXAMPLE)
    result["patch"]["invented_slot"] = {"op": "KEEP", "value": None, "evidence": []}
    assert not VALIDATOR.is_valid(result)


def test_date_requires_valid_iso_date():
    result = copy.deepcopy(EXAMPLE)
    result["patch"]["as_of"] = {
        "op": "SET",
        "value": "2026-02-30",
        "evidence": [{"message_id": "fixture-user-4", "quote": "30/02/2026"}],
    }
    assert not VALIDATOR.is_valid(result)
    result["patch"]["as_of"]["value"] = "2026-02-28"
    VALIDATOR.validate(result)


def test_evidence_cannot_be_empty_or_whitespace():
    result = copy.deepcopy(EXAMPLE)
    result["patch"]["field_intents"]["evidence"][0]["quote"] = " "
    assert not VALIDATOR.is_valid(result)


def test_structural_validity_is_not_semantic_proof():
    # Future runtime MUST reject this if the quoted message/catalog item is absent.
    # Keep this explicit: schema success alone must never authorize a state change.
    result = copy.deepcopy(EXAMPLE)
    result["patch"]["procedure_id"] = {
        "op": "SET",
        "value": "fixture-unknown-procedure",
        "evidence": [{"message_id": "fixture-missing-message", "quote": "Không có trong input"}],
    }
    assert VALIDATOR.is_valid(result)
