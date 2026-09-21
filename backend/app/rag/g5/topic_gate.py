"""Current-turn procedure evidence, independent of the conversation's active topic.

An old procedure is a prior, not a hard filter. This gate deliberately separates
new-procedure requests from mentions of documents inside the old procedure.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Literal

from app.rag.catalog_policy import is_serving_candidate, preferred_procedure_id
from app.rag.g3.retrieval import procedure_names
from app.rag.retrieval import normalize

NEW_PROCEDURE_REQUEST = re.compile(
    r"\b(?:muon|can|dinh|hoi|lam|xin)\s+(?:lam\s+)?(?:thu tuc|dang ky|xin cap|cap|"
    r"chuyen|doi|lam giay|xin giay)\b|\b(?:chuyen sang|doi sang|khong hoi .+ nua)\b"
)
CORRECTION_REQUEST = re.compile(
    r"\b(?:chua dung y|sua lai|dinh chinh|chuyen (?:han )?sang|doi sang|thay cho|"
    r"bi nham|thuc su can|khong (?:tra|hoi|lam).{0,80}|bo .{0,40} nhe)\b"
)
DOCUMENT_INVENTORY = re.compile(
    r"\b(?:da co|co san|da chuan bi|con thieu|can bo sung|giay to con lai)\b"
)
INVENTORY_FOLLOWUP = re.compile(r"\b(?:con thieu|can bo sung|con can|con gi nua|giay to con lai)\b")
GENERIC_TITLE_WORDS = frozenset({"thu", "tuc", "ho", "so", "co", "yeu", "to"})
HYBRID_SWITCH_MIN_SCORE = 0.70
HYBRID_SWITCH_MIN_LEXICAL = 0.35
# Dense similarity is corroborating evidence, not a veto when the lexical winner
# is exact and unambiguous. Real colloquial wording can sit just below 0.55.
HYBRID_SWITCH_MIN_DENSE = 0.50


@dataclass(frozen=True, slots=True)
class TopicDecision:
    action: Literal["KEEP", "SWITCH", "CLARIFY"]
    procedure_id: str | None = None
    reason: str = ""


def _phrase_in(text: str, phrase: str) -> bool:
    return f" {phrase} " in f" {text} "


def _surface_tokens(text: str) -> set[str]:
    return set(re.findall(r"\w+", unicodedata.normalize("NFC", text).lower()))


def _surface_phrase(text: str) -> str:
    return " ".join(re.findall(r"\w+", unicodedata.normalize("NFC", text).lower()))


def _has_diacritic(token: str) -> bool:
    return token != normalize(token.replace("đ", "d"))


def _accent_conflict(query: str, title: str) -> bool:
    """Reject a different accented word that only matches after accent stripping.

    An unaccented user query remains eligible for retrieval. Two *different*
    accented words, such as "sổ" and "số", are not interchangeable evidence.
    """

    query_tokens = _surface_tokens(query)
    title_tokens = _surface_tokens(title)
    for query_token in query_tokens:
        if not _has_diacritic(query_token) or query_token in title_tokens:
            continue
        folded = normalize(query_token.replace("đ", "d"))
        if any(
            _has_diacritic(title_token) and normalize(title_token.replace("đ", "d")) == folded
            for title_token in title_tokens
        ):
            return True
    return False


def _fold_tokens(text: str) -> list[str]:
    return normalize(text.replace("đ", "d").replace("Đ", "D")).split()


def _specific_variant(data, base_id: str, query: str) -> str | None:
    """Prefer a catalog variant when current-turn words name its qualifiers."""

    base = set(_fold_tokens(data.procedures[base_id]["title"])) - GENERIC_TITLE_WORDS
    query_sequence = _fold_tokens(query)
    query_tokens = set(query_sequence)
    ranked: list[tuple[int, str]] = []
    for procedure_id in data.accepted:
        if procedure_id == base_id or not is_serving_candidate(procedure_id):
            continue
        title_tokens = set(_fold_tokens(data.procedures[procedure_id]["title"]))
        if not base <= title_tokens:
            continue
        qualifiers = (title_tokens - base) - GENERIC_TITLE_WORDS
        matched = qualifiers & query_tokens
        negated = any(
            token in matched and "khong" in query_sequence[max(0, index - 5) : index]
            for index, token in enumerate(query_sequence)
        )
        if (
            len(matched) >= 2
            and not _accent_conflict(query, data.procedures[procedure_id]["title"])
            and not negated
        ):
            ranked.append((len(matched), procedure_id))
    if not ranked:
        return None
    best = max(score for score, _ in ranked)
    winners = {procedure_id for score, procedure_id in ranked if score == best}
    return next(iter(winners)) if len(winners) == 1 else None


def _explicit_match(data, query: str) -> str | None:
    text = normalize(query)
    surface_query = _surface_phrase(query)
    matches: list[tuple[int, int, str]] = []
    for procedure_id, procedure in data.procedures.items():
        surface_title = _surface_phrase(procedure["title"])
        if _phrase_in(surface_query, surface_title):
            matches.append(
                (len(surface_title.split()), 2, preferred_procedure_id(procedure_id))
            )
        for alias in procedure.get("aliases", []):
            surface_alias = _surface_phrase(alias)
            if _phrase_in(surface_query, surface_alias):
                matches.append(
                    (len(surface_alias.split()), 2, preferred_procedure_id(procedure_id))
                )
        for name in procedure_names(data, procedure):
            variants = {name}
            if name.startswith("ho so ") and len(name.split()) >= 4:
                variants.add(name.removeprefix("ho so "))
            for variant in variants:
                if _phrase_in(text, variant) and not _accent_conflict(query, procedure["title"]):
                    matches.append(
                        (
                            len(variant.split()),
                            int(variant == name),
                            preferred_procedure_id(procedure_id),
                        )
                    )
    if not matches:
        return None
    best = max((length, original) for length, original, _ in matches)
    winners = {
        procedure_id for length, original, procedure_id in matches if (length, original) == best
    }
    if len(winners) != 1:
        return None
    base_id = next(iter(winners))
    return _specific_variant(data, base_id, query) or base_id


def _positive_correction_clause(query: str) -> str:
    """Keep the positive target of a correction, not the rejected old topic."""

    text = normalize(query.replace("đ", "d").replace("Đ", "D"))
    markers = (
        r"\bthuc su can(?: hoi| lam)?(?: la)?\s+",
        r"\bchuyen (?:han )?sang\s+",
        r"\bdoi sang\s+",
    )
    for pattern in markers:
        matches = list(re.finditer(pattern, text))
        if matches:
            return query[matches[-1].end() :]

    if re.search(r"\bthay cho\b", text):
        prefix = re.split(r"\bthay cho\b", text, maxsplit=1)[0]
        positive = re.split(r"(?:\btoi\b|\bminh\b|\bem\b)\s+can\s+(?:hoi|lam)\s+", prefix)
        if len(positive) > 1:
            return positive[-1]
    return query


async def decide_topic(
    data, query: str, active_id: str | None, hybrid_router=None
) -> TopicDecision:
    """Select only strong current-turn evidence; otherwise preserve model judgment.

    Dense retrieval can suggest a switch but cannot override an exact title, a
    document-inventory follow-up, or a low-margin/low-lexical candidate.
    """

    active_id = preferred_procedure_id(active_id)
    text = normalize(query.replace("đ", "d").replace("Đ", "D"))
    correction = bool(CORRECTION_REQUEST.search(text))
    explicit_query = _positive_correction_clause(query) if correction else query
    explicit = _explicit_match(data, explicit_query)
    new_request = bool(NEW_PROCEDURE_REQUEST.search(text) or correction)
    inventory = (
        bool(DOCUMENT_INVENTORY.search(text))
        and bool(INVENTORY_FOLLOWUP.search(text))
        and not new_request
    )

    if inventory and active_id is not None:
        return TopicDecision("KEEP", reason="document_inventory")

    if explicit is not None and explicit == active_id:
        return TopicDecision("KEEP", reason="current_procedure_explicit")
    if explicit is not None:
        if explicit not in data.accepted:
            return TopicDecision("CLARIFY", reason="procedure_not_approved")
        if active_id is None or new_request or not inventory:
            return TopicDecision("SWITCH", explicit, "explicit_catalog_name")
        return TopicDecision("KEEP", reason="document_inventory")
    if not new_request and active_id is not None:
        return TopicDecision("KEEP", reason="no_new_procedure_signal")

    if hybrid_router is not None:
        candidate = await hybrid_router.route(data, query)
        candidate_id = (
            preferred_procedure_id(candidate.procedure_id) if candidate is not None else None
        )
        if candidate is not None and candidate_id == active_id:
            return TopicDecision("KEEP", reason="semantic_current_procedure")
        if (
            candidate is not None
            and candidate_id in data.accepted
            and not _accent_conflict(query, data.procedures[candidate_id]["title"])
            and candidate.score >= HYBRID_SWITCH_MIN_SCORE
            and candidate.lexical_score >= HYBRID_SWITCH_MIN_LEXICAL
            and candidate.dense_score >= HYBRID_SWITCH_MIN_DENSE
        ):
            return TopicDecision("SWITCH", candidate_id, "hybrid_high_confidence")

    # A first turn or a new/corrected procedure request that the approved catalog
    # cannot confidently map must not inherit or fabricate procedure evidence.
    return TopicDecision("CLARIFY", reason="new_procedure_unresolved")
