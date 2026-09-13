"""Deterministic safety policy applied after intent/context model inference."""

from __future__ import annotations

import copy
import unicodedata

POLICY_VERSION = "g5-intent-context-policy-v1"
CONTEXT_SLOTS = ("procedure_id", "field_intents", "jurisdiction", "as_of")
_CORRECTION_MARKERS = (
    "doi sang",
    "chuyen sang",
    "khong hoi",
    "khong phai",
    "sua lai",
    "thay bang",
)
_ACKNOWLEDGEMENTS = {
    "dung",
    "dung roi",
    "ok",
    "oke",
    "uh",
    "u",
    "vang",
}


def _plain_text(value: str) -> str:
    value = unicodedata.normalize("NFD", value.casefold())
    value = "".join(char for char in value if unicodedata.category(char) != "Mn")
    value = value.replace("đ", "d")
    return " ".join("".join(char if char.isalnum() else " " for char in value).split())


def _keep_patch() -> dict:
    return {"op": "KEEP", "value": None, "evidence": []}


def apply_intent_context_policy(output: dict, payload: dict) -> tuple[dict, list[str]]:
    """Enforce context invariants without inventing procedure or slot values.

    The model remains responsible for extracting values.  This layer only resolves
    deterministic state-machine contradictions and records every applied action.
    """

    normalized = copy.deepcopy(output)
    actions: list[str] = []
    patch = normalized["patch"]
    state = payload["state_before"]
    message = _plain_text(payload["current_user_message"])
    dialogue_act = normalized["dialogue_act"]

    has_context = any(
        state.get(slot) not in (None, [], "")
        for slot in ("procedure_id", "field_intents", "jurisdiction", "as_of")
    )
    if message in _ACKNOWLEDGEMENTS and has_context:
        if dialogue_act != "ASK_INFORMATION" or normalized["topic_action"] != "KEEP":
            actions.append("ACKNOWLEDGEMENT_KEEPS_CONTEXT")
        normalized["dialogue_act"] = "ASK_INFORMATION"
        normalized["topic_action"] = "KEEP"
        for slot in CONTEXT_SLOTS:
            patch[slot] = _keep_patch()
        dialogue_act = normalized["dialogue_act"]

    if dialogue_act in {"GREET", "OUT_OF_SCOPE"}:
        if normalized["topic_action"] != "KEEP" or any(
            patch[slot]["op"] != "KEEP" for slot in CONTEXT_SLOTS
        ):
            actions.append("POLICY_INTENT_KEEPS_CONTEXT")
        normalized["topic_action"] = "KEEP"
        for slot in CONTEXT_SLOTS:
            patch[slot] = _keep_patch()
        return normalized, actions

    if dialogue_act == "RESET_CONTEXT":
        changed = normalized["topic_action"] != "RESET" or any(
            patch[slot]["op"] != "KEEP" for slot in CONTEXT_SLOTS
        )
        normalized["topic_action"] = "RESET"
        for slot in CONTEXT_SLOTS:
            patch[slot] = _keep_patch()
        if changed:
            actions.append("RESET_ACT_CLEARS_STATE_MACHINE")

    pending = state.get("pending_clarification")
    if (
        pending in CONTEXT_SLOTS
        and patch[pending]["op"] == "SET"
        and normalized["dialogue_act"] == "ASK_INFORMATION"
    ):
        normalized["dialogue_act"] = "PROVIDE_CLARIFICATION"
        actions.append("PENDING_SLOT_WAS_PROVIDED")

    if normalized["topic_action"] == "SWITCH" and any(
        marker in message for marker in _CORRECTION_MARKERS
    ):
        if normalized["dialogue_act"] != "CORRECT_CONTEXT":
            normalized["dialogue_act"] = "CORRECT_CONTEXT"
            actions.append("EXPLICIT_TOPIC_CORRECTION")

    if normalized["dialogue_act"] in {"ASK_INFORMATION", "PROVIDE_CLARIFICATION"}:
        for slot in ("jurisdiction", "as_of"):
            old_value = state.get(slot)
            operation = patch[slot]
            if (
                state.get("pending_clarification") is None
                and old_value not in (None, "")
                and operation["op"] == "SET"
                and str(operation["value"]) != str(old_value)
            ):
                normalized["dialogue_act"] = "CORRECT_CONTEXT"
                actions.append(f"REPLACED_EXISTING_{slot.upper()}")
                break

    return normalized, actions
