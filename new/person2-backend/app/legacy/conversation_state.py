"""Deterministic filter carry-over and replacement for conversation state."""
from __future__ import annotations

import re

from .interpretation import NULL_FILTERS, extract_explicit_filters, requested_section_types

FOLLOW_UP_PREFIX = re.compile(r"^(còn\b|vậy\b|thế\b|thủ tục đó\b|cái đó\b)", re.IGNORECASE)
STATE_SELECTION = re.compile(
    r"^(?:(?:không|nhầm|sửa lại)[, :;.!-]*\s*)?(?:tôi\s+)?(?:chọn\s+)?(?:cái|thủ tục|mục|số|phương án)\s+(?:thứ\s+)?(?:đầu tiên|đầu|nhất|một|hai|ba|bốn|năm|[0-9]+)(?:\s*(?:nhé|ạ|đi))?[.!?]*$",
    re.IGNORECASE,
)


def is_follow_up(query_text: str) -> bool:
    return bool(FOLLOW_UP_PREFIX.match(query_text.strip()))


def resolve_filters(query_text: str, supplied: dict, state: dict | None) -> dict:
    explicit = extract_explicit_filters(query_text)
    carried = (state or {}).get("active_filters", {}) if is_follow_up(query_text) else {}
    return {
        key: supplied[key]
        if key in supplied
        else explicit[key]
        if explicit[key] is not None
        else carried.get(key)
        for key in NULL_FILTERS
    }


def build_conversation_state(
    session_id: str, filters: dict, bundle: dict, query_text: str, updated_at: str
) -> dict:
    unresolved = []
    if bundle["confidence_status"] == "ambiguous":
        unresolved = list(
            dict.fromkeys(
                candidate["procedure_id"]
                for candidate in bundle["ambiguous_candidates"]
            )
        )
    return {
        "session_id": session_id,
        "active_filters": filters,
        "last_resolved_procedure_id": bundle["resolved_procedure_id"],
        "last_requested_section_types": requested_section_types(query_text),
        "unresolved_references": unresolved,
        "updated_at": updated_at,
    }


def explain_state_transition(
    query_text: str,
    previous_state: dict | None,
    current_state: dict,
    supplied_filters: dict,
    explicit_filters: dict,
) -> dict:
    previous = previous_state or {}
    before_procedure = previous.get("last_resolved_procedure_id")
    after_procedure = current_state.get("last_resolved_procedure_id")
    previous_unresolved = previous.get("unresolved_references", [])
    current_unresolved = current_state.get("unresolved_references", [])
    selection_response = bool(STATE_SELECTION.fullmatch(query_text.strip()))
    follow_up = is_follow_up(query_text) or selection_response
    carried_filters = {
        key: value
        for key, value in (previous.get("active_filters") or {}).items()
        if follow_up
        and value is not None
        and key not in supplied_filters
        and explicit_filters.get(key) is None
        and current_state.get("active_filters", {}).get(key) == value
    }

    if not previous:
        reason = "initial_state_created"
    elif not follow_up and re.match(r"^(không phải|nhầm|sửa lại)\b", query_text.strip(), re.IGNORECASE):
        reason = "explicit_correction_replaced_prior_context"
    elif not follow_up and previous_unresolved:
        reason = "new_topic_replaced_ambiguous_context"
    elif not follow_up and before_procedure and before_procedure != after_procedure:
        reason = "new_topic_replaced_prior_procedure"
    elif not follow_up:
        reason = "new_topic_reset_carried_filters"
    elif previous_unresolved and not current_unresolved and after_procedure and selection_response:
        reason = "ambiguity_selection_resolved"
    elif current_unresolved:
        reason = "ambiguity_replaced_resolved_procedure_context"
    elif before_procedure and after_procedure and before_procedure != after_procedure:
        reason = "follow_up_replaced_procedure_context"
    elif before_procedure and not after_procedure:
        reason = "unresolved_follow_up_cleared_prior_procedure"
    elif carried_filters:
        reason = "follow_up_carried_prior_filters"
    else:
        reason = "follow_up_retained_current_context"

    def summary(state):
        if not state:
            return None
        return {
            "active_filters": state.get("active_filters", {}),
            "last_resolved_procedure_id": state.get("last_resolved_procedure_id"),
            "last_requested_section_types": state.get("last_requested_section_types", []),
            "unresolved_references": state.get("unresolved_references", []),
        }

    return {
        "follow_up": follow_up,
        "previous_state": summary(previous),
        "current_state": summary(current_state),
        "carried_filters": carried_filters,
        "state_reset_or_replacement_reason": reason,
    }