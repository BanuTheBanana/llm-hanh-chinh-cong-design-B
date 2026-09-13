"""Shared prompt and target rendering for the G5 intent/context task."""

from __future__ import annotations

import copy
import json
from pathlib import Path

CONTEXT_SLOTS = ("procedure_id", "field_intents", "jurisdiction", "as_of")
SYSTEM_PROMPT_VERSION = "g5-intent-context-prompt-v2"
SYSTEM_PROMPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "ai-service/app/prompts/intent-context-v2.txt"
)
SYSTEM_PROMPT = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8").strip()


def user_payload(row: dict) -> dict:
    return {
        "message_id": "current-user",
        "current_user_message": row["current_user_message"],
        "state_before": row["state_before"],
        "procedure_candidates": row["procedure_candidates"],
    }


def build_messages(row: dict) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": json.dumps(user_payload(row), ensure_ascii=False, separators=(",", ":")),
        },
    ]


def build_target(row: dict) -> dict:
    """Expand the compact reviewed label to the strict model-output contract."""

    target = copy.deepcopy(row["expected"])
    target["schema_version"] = "g5-intent-context-v2"
    message = row["current_user_message"]
    for patch in target["patch"].values():
        patch["evidence"] = (
            [] if patch["op"] == "KEEP" else [{"message_id": "current-user", "quote": message}]
        )
    return target


def apply_output_to_state(state_before: dict, output: dict) -> dict:
    """Apply a reviewed/model patch using the deterministic Backend ownership rules.

    A procedure switch invalidates procedure-dependent slots before explicit patch
    operations are applied.  This makes evaluation about the resulting context,
    while exact patch matching remains useful as a stricter diagnostic metric.
    """

    state = {
        "procedure_id": state_before.get("procedure_id"),
        "field_intents": list(state_before.get("field_intents") or []),
        "jurisdiction": state_before.get("jurisdiction"),
        "as_of": state_before.get("as_of"),
    }
    patch = output["patch"]
    procedure_patch = patch["procedure_id"]

    if output["topic_action"] == "RESET":
        state = {
            "procedure_id": None,
            "field_intents": [],
            "jurisdiction": None,
            "as_of": None,
        }
    elif (
        output["topic_action"] == "SWITCH"
        and procedure_patch["op"] == "SET"
        and procedure_patch["value"] != state["procedure_id"]
    ):
        state["field_intents"] = []
        state["jurisdiction"] = None
        state["as_of"] = None

    for slot in CONTEXT_SLOTS:
        operation = patch[slot]
        if operation["op"] == "KEEP":
            continue
        if operation["op"] == "CLEAR":
            state[slot] = [] if slot == "field_intents" else None
            continue
        value = operation["value"]
        state[slot] = list(value) if slot == "field_intents" else value

    state["field_intents"] = sorted(state["field_intents"])
    return state
