"""Deterministic filter carry-over and replacement for conversation state."""
from __future__ import annotations

import re

from .interpretation import NULL_FILTERS, extract_explicit_filters, requested_section_types

FOLLOW_UP_PREFIX = re.compile(r"^(còn\b|vậy\b|thế\b|thủ tục đó\b|cái đó\b)", re.IGNORECASE)


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