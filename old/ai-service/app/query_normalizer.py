"""Lightweight Vietnamese query normalization for administrative-service routing.

The original user message is never mutated. This module produces a routing-only
representation and accepts typo repairs only when the best domain term is unique.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache

from rapidfuzz import fuzz, process
from rapidfuzz.distance import Levenshtein

_SAFE_WORDS = {
    "ai",
    "bao",
    "be",
    "bo",
    "buoc",
    "can",
    "cap",
    "chinh",
    "cho",
    "co",
    "con",
    "cu",
    "cuoc",
    "dang",
    "dau",
    "den",
    "dieu",
    "doi",
    "duoc",
    "gi",
    "giay",
    "gio",
    "gui",
    "hai",
    "han",
    "het",
    "hinh",
    "ho",
    "hoi",
    "hon",
    "khai",
    "khong",
    "ky",
    "lai",
    "lam",
    "lau",
    "le",
    "mang",
    "mat",
    "minh",
    "moi",
    "muon",
    "nao",
    "ngay",
    "nhan",
    "nhieu",
    "nop",
    "nuoc",
    "o",
    "phi",
    "phuong",
    "qua",
    "quay",
    "quy",
    "sinh",
    "so",
    "tai",
    "tat",
    "them",
    "thoi",
    "thu",
    "tiep",
    "to",
    "toi",
    "toan",
    "trinh",
    "truc",
    "tuc",
    "tuyen",
    "ve",
    "xin",
    "xu",
    "yeu",
}

# Valid conversational words must never be "repaired" merely because they are
# close to an administrative term. This guard keeps fuzzy matching focused on
# domain typos instead of rewriting the user's Vietnamese.
_PROTECTED_WORDS = {
    "anh", "bang", "biet", "bo", "canh", "cach", "chuyen", "dung", "em",
    "han", "hien", "ma", "nhung", "noi", "quan", "roi", "sang", "the",
    "thong", "tin", "tru", "van", "xoa", "xac",
}

# Only these distinctive administrative tokens (plus sufficiently long words
# from procedure names) are valid typo targets. Common Vietnamese words are
# deliberately excluded because edit-distance alone cannot resolve semantics.
_CORRECTION_TERMS = {
    "cccd",
    "chung",
    "khieu",
    "phuong",
    "quyen",
    "sinh",
    "tuyen",
}

_ABBREVIATIONS = {
    "c c c d": "cccd",
    "c m n d": "cmnd",
    "d k": "dang ky",
    "onl": "truc tuyen",
}

_SYNONYM_EXPANSIONS = {
    "qua mang": "truc tuyen",
    "nop web": "truc tuyen",
    "cho may ngay": "thoi gian",
    "cho bao lau": "thoi gian",
    "ton tien": "le phi",
    "mat tien": "le phi",
    "cho nao lam": "noi tiep nhan",
    "nop cho nao": "noi tiep nhan",
    "can mang theo": "giay to",
}


@dataclass(frozen=True)
class NormalizedQuery:
    text: str
    typo_repairs: tuple[tuple[str, str], ...]
    synonym_expansions: tuple[str, ...]


def plain_text(value: str) -> str:
    value = unicodedata.normalize("NFD", value.casefold())
    value = "".join(char for char in value if unicodedata.category(char) != "Mn")
    value = value.replace("đ", "d")
    return " ".join("".join(char if char.isalnum() else " " for char in value).split())


@lru_cache(maxsize=128)
def _domain_vocabulary(candidate_names: tuple[str, ...]) -> tuple[str, ...]:
    words = set(_CORRECTION_TERMS)
    for name in candidate_names:
        words.update(word for word in plain_text(name).split() if len(word) >= 6)
    return tuple(sorted(words))


def _repair_token(token: str, vocabulary: tuple[str, ...]) -> str | None:
    if (
        token in _SAFE_WORDS
        or token in _PROTECTED_WORDS
        or len(token) < 3
        or any(char.isdigit() for char in token)
    ):
        return None
    matches = process.extract(token, vocabulary, scorer=fuzz.ratio, limit=2, score_cutoff=80)
    if not matches:
        return None
    best, best_score, _ = matches[0]
    if token[0] != best[0]:
        return None
    second_score = matches[1][1] if len(matches) > 1 else 0
    max_distance = 1 if len(token) <= 6 else 2
    if Levenshtein.distance(token, best) > max_distance:
        return None
    if best_score - second_score < 8:
        return None
    return best


def normalize_query(value: str, *, candidate_names: tuple[str, ...] = ()) -> NormalizedQuery:
    normalized = plain_text(value)
    for source, target in _ABBREVIATIONS.items():
        normalized = re.sub(rf"\b{re.escape(source)}\b", target, normalized)

    vocabulary = _domain_vocabulary(tuple(sorted(candidate_names)))
    repairs: list[tuple[str, str]] = []
    tokens: list[str] = []
    for token in normalized.split():
        repaired = _repair_token(token, vocabulary)
        if repaired is not None:
            repairs.append((token, repaired))
            tokens.append(repaired)
        else:
            tokens.append(token)
    normalized = " ".join(tokens)

    expansions = [
        canonical
        for phrase, canonical in _SYNONYM_EXPANSIONS.items()
        if f" {phrase} " in f" {normalized} "
    ]
    if expansions:
        normalized = " ".join((normalized, *expansions))
    return NormalizedQuery(normalized, tuple(repairs), tuple(expansions))
