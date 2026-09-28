"""Deterministic safety policy applied after intent/context model inference."""

from __future__ import annotations

import copy
import re

from app.query_normalizer import normalize_query, plain_text

POLICY_VERSION = "g6-intent-context-policy-v11"
CONTEXT_SLOTS = ("procedure_id", "field_intents", "jurisdiction", "as_of")
ALL_FIELD_INTENTS = (
    "receiving_authority",
    "required_documents",
    "fees",
    "processing_times",
    "submission_methods",
    "steps",
    "legal_bases",
    "applicant_scope",
)
_CORRECTION_PATTERNS = (
    r"\ba khong\b",
    r"\bkhong phai\b[^,.!?;]{0,80}\bchu\b",
    r"\bdoi (?:qua|sang)\b",
    r"\b(?<!vua )chuyen (?:han )?(?:chu de )?sang\b",
    r"\bkhong (?:con |tiep tuc )?hoi\b",
    r"\bkhong (?:lam|phai)\b.*\bnua\b",
    r"\bsua (?:lai |dia ban )?(?:tu|thanh|sang)\b",
    r"\bthay chu de\b",
    r"\bthay bang\b",
    r"\bquay (?:lai|ve)\b",
    r"\bsua\b[^,.!?;]{0,40}\bdia ban\b",
    r"\bkhong can\b.*\bnua\b",
)
_RESET_PATTERNS = (
    r"\bbat dau lai\b",
    r"\bbo noi dung cu\b",
    r"\bcho toi lam lai tu dau\b",
    r"\breset (?:cuoc|ngu canh|boi canh)\b",
    r"\bxoa het (?:thong tin|noi dung)\b",
    r"\bxoa toan bo chu de\b",
    r"\bbo het thong tin\b",
    r"\bxoa (?:boi canh|ca chu de|ngu canh)\b",
    r"\bkhoi tao lai\b",
    r"\blam moi (?:hoan toan )?(?:cuoc|ngu canh)\b",
    r"\bdua ngu canh ve trang thai ban dau\b",
    r"\bdung chu de dang trao doi\b",
    r"\bket thuc ngu canh\b",
)
_UNRESOLVED_PATTERNS = (
    r"\bchua biet ten (?:thu tuc|dich vu)\b",
    r"\bchua xac dinh (?:duoc )?ten\b",
    r"\bkhong biet ten (?:thu tuc|dich vu)\b",
    r"\bkhong ro (?:ten )?(?:thu tuc|dich vu)\b",
    r"\bchua ro (?:minh )?(?:thuoc|can) (?:thu tuc|dich vu) nao\b",
    r"\bchua biet (?:minh )?(?:thuoc|chon) (?:thu tuc|dich vu) nao\b",
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
_DATE_SIGNAL = re.compile(
    r"\b(?:ngay\s+\d{1,2}(?:\s+thang\s+\d{1,2}(?:\s+nam\s+\d{4})?)?"
    r"|\d{1,2}[/-]\d{1,2}[/-]\d{4}|\d{4}-\d{2}-\d{2})\b"
)
_JURISDICTION_SIGNAL = re.compile(
    r"\b(?:tinh|thanh pho|quan|huyen|phuong|thi xa)\s+[a-z0-9]"
)
_INCIDENTAL_LOCATION_SIGNAL = re.compile(
    r"\b(?:toi|chung toi|gia dinh toi|hien tai toi|hien toi)\b(?:"
    r"\s+(?:(?:dang|hien)\s+)?(?:o|song|cu tru)"
    r"|.{1,96}\b(?:dang\s+o|hien(?:\s+tai)?\s+o|song(?:\s+(?:o|tai))?"
    r"|cu\s+tru(?:\s+(?:o|tai))?)"
    r")\s+(?:tai\s+)?(?:tinh|thanh pho|quan|huyen|phuong|thi xa)\s+[a-z0-9]"
)
_OUT_OF_SCOPE_SIGNAL = re.compile(
    r"\b(?:bai tho|quang cao|dien thoai|may tinh|lap trinh|du bao thoi tiet)\b"
)
_PROCEDURE_GENERIC_TOKENS = {
    "cap",
    "dang",
    "ho",
    "ky",
    "nhan",
    "thong",
    "tin",
    "tich",
    "thu",
    "tuc",
    "ve",
    "xac",
}
_FIELD_ONLY_REPLIES = {
    "ho so": "required_documents",
    "ve ho so": "required_documents",
    "giay to": "required_documents",
    "le phi": "fees",
    "phi": "fees",
    "thoi gian": "processing_times",
    "bao lau": "processing_times",
    "noi nop": "receiving_authority",
    "noi tiep nhan": "receiving_authority",
    "cach thuc hien": "steps",
    "quy trinh": "steps",
    "cac buoc": "steps",
}
_FIELD_CUES = {
    "receiving_authority": (
        "co quan nao",
        "co quan tiep nhan",
        "cho biet co quan xu ly",
        "co quan chiu trach nhiem",
        "don vi nha nuoc",
        "don vi nao",
        "noi tiep nhan",
        "noi nao tiep nhan",
        "noi nao nhan",
        "ben nao co tham quyen",
        "bo phan nao",
        "tham quyen tiep nhan",
        "cho biet co quan nhan",
        "den dau nop",
        "nop tai dau",
        "nop cho ai",
        "gui o dau",
        "o dau",
    ),
    "required_documents": (
        "thanh phan",
        "giay to",
        "tai lieu",
        "bo ho so",
        "can ho so",
        "ho so gi",
        "ho so va",
        "ho so gom",
        "ho so can chuan bi",
        "ho so phai chuan bi",
        "chuan bi ho so",
        "chuan bi giay to",
        "can chuan bi gi",
        "kem theo",
        "mang theo",
        "mang gi",
        "bo sung gi",
        "can gi nua",
        "con can gi",
        "them gi nua",
    ),
    "fees": (
        "le phi",
        "muc phi",
        "chi phi",
        "dong phi",
        "dong le phi",
        "phai dong",
        "ton khoan",
        "thu phi",
        "khoan tien",
        "bao nhieu tien",
    ),
    "processing_times": (
        "thoi han",
        "thoi gian",
        "bao lau",
        "mat bao lau",
        "xu ly trong bao lau",
        "bao nhieu ngay",
        "may ngay",
        "tra ket qua",
        "khi nao nhan ket qua",
    ),
    "submission_methods": (
        "hinh thuc nop",
        "hinh thuc",
        "phuong an nop",
        "cach nop",
        "kenh",
        "truc tuyen",
        "qua mang",
        "nop mang",
        "online",
        "buu chinh",
        "buu dien",
        "gui yeu cau bang",
        "gui den co quan bang",
    ),
    "steps": ("quy trinh", "trinh tu", "cac buoc", "thu tu cac buoc"),
    "legal_bases": (
        "can cu",
        "co so phap ly",
        "van ban",
        "theo van ban nao",
        "luat nao",
        "dua tren quy dinh",
        "quy dinh nao",
        "nhung quy dinh",
    ),
    "applicant_scope": (
        "doi tuong",
        "danh cho ai",
        "nhung nguoi",
        "nguoi nao",
        "ai co quyen",
        "ai duoc",
        "quyen yeu cau",
        "du dieu kien",
    ),
}

_PROCEDURE_SEMANTIC_ALIASES = {
    "khai sinh": ("sinh con", "lam khai sinh", "giay khai sinh"),
    "ket hon": ("cuoi nguoi", "lam dam cuoi", "dang ky cuoi"),
}
_PROCEDURE_QUALIFIER_STOPWORDS = _PROCEDURE_GENERIC_TOKENS | {
    "co",
    "doi",
    "nguoi",
    "thu",
    "tuc",
    "voi",
    "yeu",
    "to",
}
_ALL_FIELDS_PATTERNS = (
    r"\btat ca moi thu\b",
    r"\btat ca cac muc\b",
    r"\btoan bo thong tin\b",
    r"\bcho (?:toi|minh) xem het\b",
    r"\bhoi het\b",
)
_CONFIRMATION_PATTERNS = (
    "vay la",
    "co dung khong",
    "co dung ko",
    "dung khong",
    "dung ko",
    "phai khong",
    "phai ko",
    "thoi ha",
    "thoi a",
)
_REMAINING_PATTERNS = (
    "con gi nua",
    "con thieu gi",
    "con bo sung gi",
    "can bo sung gi",
    "nhung gi con lai",
    "muc con lai",
)
_DOCUMENT_CONCEPT_SIGNAL = re.compile(
    r"\b(?:ho so|giay to|tai lieu)\b(?:\s+[a-z0-9]+){0,5}\s+"
    r"(?:can|yeu cau|chuan bi|bo sung|kem|mang)\b"
    r"|\b(?:ho so|giay to|tai lieu)\b(?:\s+[a-z0-9]+){0,5}\s+"
    r"gom(?:\s+[a-z0-9]+){0,3}\s+(?:nhung\s+)?gi\b"
    r"|\b(?:can|chuan bi|bo sung|kem|mang)\b(?:\s+[a-z0-9]+){0,5}\s+"
    r"(?:ho so|giay to|tai lieu)\b"
)
_DOCUMENT_ARTIFACT_SIGNAL = re.compile(
    r"\b(?:mang|xuat trinh|doi chieu|can|nop)\b(?:\s+[a-z0-9]+){0,6}\s+"
    r"(?:ban chinh|ban sao|ban photo)\b"
    r"|\b(?:ban chinh|ban sao|ban photo)\b(?:\s+[a-z0-9]+){0,6}\s+"
    r"(?:xuat trinh|doi chieu|mang theo)\b"
)
_FEE_CLAIM_SIGNAL = re.compile(
    r"\b(?:phi|mien phi|mat phi|thu phi)\b"
    r"|\b\d+(?:[.,]\d+)?\s*(?:k|nghin|ngan|dong)\b"
)
_PROCESSING_TIME_CLAIM_SIGNAL = re.compile(
    r"\b\d+\s+(?:ngay|tuan|thang|gio)(?:\s+lam\s+viec)?\b"
)
_COMMON_TYPO_PHRASES = {
    "kha sin": "khai sinh",
    "khai sih": "khai sinh",
    "khai snh": "khai sinh",
    "ket hoon": "ket hon",
    "truc tuen": "truc tuyen",
}


def _plain_text(value: str) -> str:
    return plain_text(value)


def _detection_text(value: str, candidates: list[dict] | None = None) -> str:
    """Apply only reviewed, unambiguous typo repairs used for routing."""

    candidate_names = tuple(
        str(candidate.get("name") or "") for candidate in candidates or []
    )
    normalized = plain_text(value)
    for typo, replacement in _COMMON_TYPO_PHRASES.items():
        normalized = re.sub(rf"\b{re.escape(typo)}\b", replacement, normalized)
    return normalize_query(normalized, candidate_names=candidate_names).text


def _keep_patch() -> dict:
    return {"op": "KEEP", "value": None, "evidence": []}


def _field_only_reply(payload: dict, message: str) -> tuple[dict, list[str]] | None:
    """A short answer naming an information field cannot name a procedure."""

    field = _FIELD_ONLY_REPLIES.get(message)
    if field is None:
        return None
    current_procedure = payload["state_before"].get("procedure_id")
    if current_procedure is None:
        return (
            _base_output(dialogue_act="ASK_INFORMATION", topic_action="UNRESOLVED"),
            ["FIELD_REPLY_REQUIRES_PROCEDURE"],
        )
    output = _base_output(
        dialogue_act=(
            "PROVIDE_CLARIFICATION"
            if payload["state_before"].get("pending_clarification") == "field_intents"
            else "ASK_INFORMATION"
        ),
        topic_action="KEEP",
    )
    output["patch"]["field_intents"] = _set_patch([field], payload)
    return output, ["FIELD_ONLY_REPLY_KEEPS_PROCEDURE"]


def bounded_evidence_quote(payload: dict, value: object) -> str:
    """Select a literal, relevant user span that fits the audit contract."""

    message = payload["current_user_message"]
    if len(message) <= 300:
        return message

    windows = [message[index : index + 300] for index in range(0, len(message), 150)]
    plain_targets: list[str] = []
    if isinstance(value, list):
        for field in value:
            plain_targets.extend(_FIELD_CUES.get(str(field), ()))
    elif isinstance(value, str):
        for candidate in payload.get("procedure_candidates") or []:
            if candidate.get("id") == value:
                plain_targets.extend(
                    token
                    for token in _plain_text(str(candidate.get("name") or "")).split()
                    if token not in _PROCEDURE_GENERIC_TOKENS
                )
                break
        if not plain_targets:
            plain_targets.extend(_plain_text(value).split())

    def score(window: str) -> tuple[int, int]:
        plain = _plain_text(window)
        return sum(target in plain for target in plain_targets), -len(window)

    return max(windows, key=score)


def _set_patch(value: object, payload: dict) -> dict:
    return {
        "op": "SET",
        "value": value,
        "evidence": [
            {
                "message_id": payload.get("message_id")
                or payload.get("current_message_id")
                or "current-user",
                "quote": bounded_evidence_quote(payload, value),
            }
        ],
    }


def _matches_any(message: str, patterns: tuple[str, ...]) -> bool:
    return any(re.search(pattern, message) for pattern in patterns)


def _contains_phrase(message: str, phrase: str) -> bool:
    """Match normalized tokens, not arbitrary substrings such as can cu in can cuoc."""

    return f" {phrase} " in f" {message} "


def _has_field_cue(message: str, field: str) -> bool:
    if any(_contains_phrase(message, cue) for cue in _FIELD_CUES[field]):
        return True
    if field == "required_documents":
        return bool(
            _DOCUMENT_CONCEPT_SIGNAL.search(message)
            or _DOCUMENT_ARTIFACT_SIGNAL.search(message)
        )
    if field == "fees":
        return bool(_FEE_CLAIM_SIGNAL.search(message))
    if field == "processing_times":
        return bool(
            _PROCESSING_TIME_CLAIM_SIGNAL.search(message)
            and not _DATE_SIGNAL.search(message)
        )
    return False


def _positive_clause(message: str) -> str:
    transition = re.search(
        r"\b(?:doi (?:qua|sang)|chuyen (?:han )?(?:chu de )?sang|thay chu de|quay (?:lai|ve))\b",
        message,
    )
    if transition is not None:
        message = message[transition.start() :]
    positive_message = re.sub(
        r"\bkhong (?:con |tiep tuc )?hoi\b.*?\bnua\b(?:\s+ma)?",
        " ",
        message,
    )
    positive_message = re.sub(
        r"\bkhong (?:con |tiep tuc )?hoi\b[^,.!?;]*",
        " ",
        positive_message,
    )
    positive_message = re.sub(
        r"\bkhong (?:lam|phai)\b.*?\bnua\b(?:\s+ma)?",
        " ",
        positive_message,
    )
    positive_message = re.sub(
        r"\bkhong can\b.*?\bnua\b(?:\s+ma)?",
        " ",
        positive_message,
    )
    positive_message = re.sub(
        r"\bngoai (?:can cu phap ly|co so phap ly|van ban|quy dinh)\b",
        " ",
        positive_message,
    )
    positive_message = re.sub(
        r"\bngoai (?:quy trinh|trinh tu|cac buoc)\b",
        " ",
        positive_message,
    )
    positive_message = re.sub(
        r"\bsau khi (?:da )?(?:du|nop du) (?:giay to|ho so)\b",
        " ",
        positive_message,
    )
    positive_message = re.sub(
        r"\b(?:tra cuu theo|doi chieu)(?: noi dung nay| thong tin)?"
        r"(?: quy dinh)?(?: co hieu luc)?(?: vao| tai)? ngay\b",
        " ",
        positive_message,
    )
    positive_message = re.sub(r"\bquy dinh ngay\b", " ", positive_message)
    return positive_message


def _detect_fields(message: str) -> list[str]:
    has_calendar_date = bool(_DATE_SIGNAL.search(message))
    positive_message = _positive_clause(message)
    if _matches_any(positive_message, _ALL_FIELDS_PATTERNS):
        return list(ALL_FIELD_INTENTS)
    detected = [
        field
        for field in _FIELD_CUES
        if _has_field_cue(positive_message, field)
    ]
    if (
        has_calendar_date
        and "processing_times" in detected
        and not any(
            _contains_phrase(positive_message, cue)
            for cue in _FIELD_CUES["processing_times"]
        )
    ):
        detected.remove("processing_times")
    if "steps" in detected and "required_documents" in detected:
        strong_document_cues = (
            "giay to",
            "tai lieu",
            "thanh phan",
            "kem theo",
            "mang theo",
            "mang gi",
            "ho so gi",
            "ho so can chuan bi",
            "ho so phai chuan bi",
            "chuan bi ho so",
            "bo sung gi",
            "can gi nua",
            "con can gi",
            "them gi nua",
        )
        if not (
            any(_contains_phrase(positive_message, cue) for cue in strong_document_cues)
            or _DOCUMENT_CONCEPT_SIGNAL.search(positive_message)
            or _DOCUMENT_ARTIFACT_SIGNAL.search(positive_message)
        ):
            detected.remove("required_documents")
    if "receiving_authority" in detected and "required_documents" in detected:
        strong_document_cues = (
            "giay to",
            "tai lieu",
            "thanh phan",
            "kem theo",
            "mang theo",
            "mang gi",
            "ho so gi",
            "ho so can chuan bi",
            "ho so phai chuan bi",
            "chuan bi ho so",
            "bo sung gi",
            "can gi nua",
            "con can gi",
            "them gi nua",
        )
        if not (
            any(_contains_phrase(positive_message, cue) for cue in strong_document_cues)
            or _DOCUMENT_CONCEPT_SIGNAL.search(positive_message)
            or _DOCUMENT_ARTIFACT_SIGNAL.search(positive_message)
        ):
            detected.remove("required_documents")
    return detected


_CLEAR_CUES = {
    "procedure_id": ("bo thu tuc", "xoa thu tuc", "khong giu thu tuc"),
    "field_intents": ("bo noi dung dang hoi", "xoa noi dung dang hoi"),
    "jurisdiction": (
        "bo dia ban",
        "xoa dia ban",
        "bo dia phuong",
        "xoa dia phuong",
        "khong gioi han dia ban",
    ),
    "as_of": ("bo moc ngay", "xoa moc ngay", "bo thoi diem", "xoa thoi diem"),
}


def _clear_is_supported(slot: str, message: str) -> bool:
    return any(cue in message for cue in _CLEAR_CUES[slot])


def _base_output(*, dialogue_act: str, topic_action: str) -> dict:
    return {
        "schema_version": "g5-intent-context-v2",
        "dialogue_act": dialogue_act,
        "topic_action": topic_action,
        "patch": {slot: _keep_patch() for slot in CONTEXT_SLOTS},
    }


def resolve_high_confidence_without_model(payload: dict) -> tuple[dict, list[str]] | None:
    """Resolve only deterministic turns and leave every ambiguous turn to Qwen.

    The route deliberately excludes pending clarification, dates, jurisdictional
    applicability questions and possible out-of-scope requests. A residence/location
    supplied only as narrative context is not promoted to a legal jurisdiction filter.
    """

    message = _detection_text(
        payload["current_user_message"], payload.get("procedure_candidates")
    )
    state = payload["state_before"]
    has_context = any(
        state.get(slot) not in (None, [], "")
        for slot in ("procedure_id", "field_intents", "jurisdiction", "as_of")
    )
    if _matches_any(message, _RESET_PATTERNS):
        return (
            _base_output(dialogue_act="RESET_CONTEXT", topic_action="RESET"),
            ["DETERMINISTIC_EXPLICIT_RESET"],
        )
    field_only = _field_only_reply(payload, message)
    if field_only is not None:
        return field_only
    if _matches_any(message, _UNRESOLVED_PATTERNS) and not state.get("procedure_id"):
        return (
            _base_output(dialogue_act="ASK_INFORMATION", topic_action="UNRESOLVED"),
            ["DETERMINISTIC_EXPLICIT_UNRESOLVED"],
        )
    if message in _ACKNOWLEDGEMENTS and has_context:
        return (
            _base_output(dialogue_act="ASK_INFORMATION", topic_action="KEEP"),
            ["DETERMINISTIC_ACKNOWLEDGEMENT"],
        )
    jurisdiction_signal = _JURISDICTION_SIGNAL.search(message)
    incidental_location = jurisdiction_signal and _INCIDENTAL_LOCATION_SIGNAL.search(message)
    all_fields_signal = _matches_any(message, _ALL_FIELDS_PATTERNS)
    if (
        (
            state.get("pending_clarification") is not None
            and not (
                state.get("pending_clarification") == "field_intents"
                and all_fields_signal
            )
        )
        or _DATE_SIGNAL.search(message)
        or (jurisdiction_signal and not incidental_location)
        or _OUT_OF_SCOPE_SIGNAL.search(message)
    ):
        return None

    procedure = _detect_procedure(payload, message)
    fields = sorted(set(_detect_fields(message)))
    current_procedure = state.get("procedure_id")
    contextual_followup = _matches_any(
        message, (*_CONFIRMATION_PATTERNS, *_REMAINING_PATTERNS)
    )
    explicit_new_procedure = bool(
        procedure
        and procedure != current_procedure
        and _has_explicit_procedure_reference(payload, message, procedure)
    )
    if (
        contextual_followup
        and current_procedure
        and not _matches_any(message, _CORRECTION_PATTERNS)
        and not explicit_new_procedure
    ):
        output = _base_output(dialogue_act="ASK_INFORMATION", topic_action="KEEP")
        if fields:
            output["patch"]["field_intents"] = _set_patch(fields, payload)
        return output, [
            "DETERMINISTIC_CONTEXTUAL_FOLLOWUP",
            "DOCUMENT_MENTION_CANNOT_SWITCH_ACTIVE_PROCEDURE",
        ]
    if (
        not fields
        and procedure
        and procedure != current_procedure
        and (current_procedure or _matches_any(message, _CORRECTION_PATTERNS))
    ):
        output = _base_output(dialogue_act="CORRECT_CONTEXT", topic_action="SWITCH")
        output["patch"]["procedure_id"] = _set_patch(procedure, payload)
        return output, ["DETERMINISTIC_EXPLICIT_TOPIC_SWITCH"]
    if not fields and procedure and procedure == current_procedure:
        output = _base_output(dialogue_act="ASK_INFORMATION", topic_action="KEEP")
        output["patch"]["field_intents"] = {
            "op": "CLEAR",
            "value": None,
            "evidence": [
                {
                    "message_id": payload.get("message_id")
                    or payload.get("current_message_id")
                    or "current-user",
                    "quote": bounded_evidence_quote(payload, procedure),
                }
            ],
        }
        return output, ["DETERMINISTIC_TOPIC_ONLY_REQUEST"]
    if not fields or (procedure is None and not current_procedure):
        return None

    topic_action = "SWITCH" if procedure and procedure != current_procedure else "KEEP"
    dialogue_act = (
        "CORRECT_CONTEXT"
        if current_procedure and _matches_any(message, _CORRECTION_PATTERNS)
        else "ASK_INFORMATION"
    )
    output = _base_output(dialogue_act=dialogue_act, topic_action=topic_action)
    if topic_action == "SWITCH":
        output["patch"]["procedure_id"] = _set_patch(procedure, payload)
    output["patch"]["field_intents"] = _set_patch(fields, payload)
    actions = ["DETERMINISTIC_HIGH_CONFIDENCE_ROUTE"]
    if incidental_location:
        actions.append("INCIDENTAL_LOCATION_NOT_USED_AS_LEGAL_FILTER")
    return output, actions


def _has_explicit_procedure_reference(
    payload: dict, message: str, candidate_id: str
) -> bool:
    """Require a title/domain phrase, not coincidental words from document names."""

    for candidate in payload.get("procedure_candidates") or []:
        if candidate.get("id") != candidate_id:
            continue
        title = _plain_text(str(candidate.get("name") or ""))
        if title and _contains_phrase(message, title):
            return True
        return any(
            _contains_phrase(title, title_key)
            and any(
                _contains_phrase(message, reference)
                for reference in (title_key, *aliases)
            )
            for title_key, aliases in _PROCEDURE_SEMANTIC_ALIASES.items()
        )
    return False


def _detect_procedure(payload: dict, message: str) -> str | None:
    """Return only a unique, high-confidence catalog match from the current text."""

    candidates = payload.get("procedure_candidates") or []
    original_message = message
    # "chuyển sang" is ordinary wording inside first-turn procedures such as
    # school transfer. Treat it as a correction boundary only with an old topic.
    if payload.get("state_before", {}).get("procedure_id"):
        message = _positive_clause(message)
    has_active_procedure = bool(payload.get("state_before", {}).get("procedure_id"))
    allow_loose_match = not has_active_procedure or _matches_any(
        original_message, _CORRECTION_PATTERNS
    )
    message_tokens = set(message.split())
    scored: list[tuple[float, int, str]] = []
    for candidate in candidates:
        candidate_id = candidate.get("id")
        title = _plain_text(str(candidate.get("name") or ""))
        if not candidate_id or not title:
            continue
        if title in message:
            scored.append((2.0, len(title.split()), candidate_id))
            continue
        semantic_alias_matches = [
            reference
            for title_key, aliases in _PROCEDURE_SEMANTIC_ALIASES.items()
            if _contains_phrase(title, title_key)
            for reference in (title_key, *aliases)
            if _contains_phrase(message, reference)
        ]
        if semantic_alias_matches:
            alias_length = max(len(alias.split()) for alias in semantic_alias_matches)
            # Prefer a catalog variant whose distinguishing title modifiers are
            # present in the correction. Example: both marriage procedures match
            # "ket hon", while only the foreign-element variant also matches
            # "nuoc ngoai". This stays catalog-bound and generalizes to other
            # procedure families with explicit title qualifiers.
            qualifier_matches = sum(
                token in message_tokens
                for token in set(title.split()) - _PROCEDURE_QUALIFIER_STOPWORDS
            )
            scored.append((1.5 + min(qualifier_matches, 3) / 10, alias_length, candidate_id))
            continue
        # Once a conversation has an active procedure, loose token overlap is too
        # weak to switch it: document names often share words with unrelated titles.
        if not allow_loose_match:
            continue
        distinctive_tokens = [
            token for token in title.split() if token not in _PROCEDURE_GENERIC_TOKENS
        ]
        distinctive = set(distinctive_tokens)
        matched = sum(token in message_tokens for token in distinctive)
        message_distinctive_tokens = [
            token
            for token in message.split()
            if token not in _PROCEDURE_GENERIC_TOKENS
        ]
        longest_phrase = _longest_contiguous_overlap(
            distinctive_tokens, message_distinctive_tokens
        )
        # A user often names only the stable noun phrase of a long official title.
        # Accept that shorthand only when at least four consecutive distinctive
        # tokens match. Coverage still favors the shortest compatible title, while
        # explicit modifiers such as "mai tang" make the longer variant win.
        coverage = matched / len(distinctive) if distinctive else 0.0
        standard_match = matched >= 2 and coverage >= 0.5
        long_shorthand_match = (
            matched >= 4 and longest_phrase >= 4 and coverage >= 0.4
        )
        if len(distinctive) >= 2 and (standard_match or long_shorthand_match):
            scored.append((matched / len(distinctive), matched, candidate_id))
    if not scored:
        return None
    scored.sort(reverse=True)
    if len(scored) > 1 and scored[0][:2] == scored[1][:2]:
        return None
    return scored[0][2]


def _longest_contiguous_overlap(left: list[str], right: list[str]) -> int:
    """Length of the longest shared contiguous token phrase."""

    previous = [0] * (len(right) + 1)
    longest = 0
    for left_token in left:
        current = [0] * (len(right) + 1)
        for index, right_token in enumerate(right, start=1):
            if left_token == right_token:
                current[index] = previous[index - 1] + 1
                longest = max(longest, current[index])
        previous = current
    return longest


def apply_intent_context_policy(output: dict, payload: dict) -> tuple[dict, list[str]]:
    """Enforce context invariants without inventing procedure or slot values.

    The model remains responsible for extracting values.  This layer only resolves
    deterministic state-machine contradictions and records every applied action.
    """

    normalized = copy.deepcopy(output)
    actions: list[str] = []
    patch = normalized["patch"]
    state = payload["state_before"]
    message = _detection_text(
        payload["current_user_message"], payload.get("procedure_candidates")
    )
    if not _matches_any(message, _RESET_PATTERNS):
        field_only = _field_only_reply(payload, message)
        if field_only is not None:
            return field_only
    dialogue_act = normalized["dialogue_act"]
    explicit_correction = _matches_any(message, _CORRECTION_PATTERNS)
    explicit_reset = _matches_any(message, _RESET_PATTERNS)
    unresolved_request = _matches_any(message, _UNRESOLVED_PATTERNS)
    detected_procedure = _detect_procedure(payload, message)
    detected_fields = _detect_fields(message)
    current_procedure = state.get("procedure_id")
    contextual_followup = _matches_any(
        message, (*_CONFIRMATION_PATTERNS, *_REMAINING_PATTERNS)
    )

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
        return normalized, actions

    if explicit_reset:
        changed = dialogue_act != "RESET_CONTEXT" or normalized["topic_action"] != "RESET"
        normalized["dialogue_act"] = "RESET_CONTEXT"
        normalized["topic_action"] = "RESET"
        for slot in CONTEXT_SLOTS:
            patch[slot] = _keep_patch()
        if changed:
            actions.append("EXPLICIT_RESET_WINS")
        return normalized, actions

    if unresolved_request and not state.get("procedure_id") and detected_procedure is None:
        normalized["dialogue_act"] = "ASK_INFORMATION"
        normalized["topic_action"] = "UNRESOLVED"
        for slot in CONTEXT_SLOTS:
            patch[slot] = _keep_patch()
        actions.append("EXPLICIT_UNRESOLVED_REQUEST")
        return normalized, actions

    if contextual_followup and current_procedure and not explicit_correction:
        proposed_procedure = (
            patch["procedure_id"].get("value")
            if patch["procedure_id"].get("op") == "SET"
            else detected_procedure
        )
        explicit_new_procedure = bool(
            proposed_procedure
            and proposed_procedure != current_procedure
            and _has_explicit_procedure_reference(payload, message, proposed_procedure)
        )
        if not explicit_new_procedure:
            normalized["dialogue_act"] = "ASK_INFORMATION"
            normalized["topic_action"] = "KEEP"
            patch["procedure_id"] = _keep_patch()
            if detected_fields:
                patch["field_intents"] = _set_patch(
                    sorted(set(detected_fields)), payload
                )
            actions.append("DOCUMENT_MENTION_CANNOT_SWITCH_ACTIVE_PROCEDURE")
            return normalized, actions

    if dialogue_act == "RESET_CONTEXT":
        normalized["dialogue_act"] = (
            "CORRECT_CONTEXT" if explicit_correction else "ASK_INFORMATION"
        )
        normalized["topic_action"] = "KEEP" if state.get("procedure_id") else "UNRESOLVED"
        dialogue_act = normalized["dialogue_act"]
        actions.append("UNSUPPORTED_RESET_DOWNGRADED")

    for slot in CONTEXT_SLOTS:
        if patch[slot].get("op") == "CLEAR" and not _clear_is_supported(slot, message):
            patch[slot] = _keep_patch()
            actions.append(f"UNSUPPORTED_CLEAR_{slot.upper()}_REMOVED")
        if (
            state.get(slot) not in (None, [], "")
            and _clear_is_supported(slot, message)
            and patch[slot].get("op") != "CLEAR"
        ):
            patch[slot] = {
                "op": "CLEAR",
                "value": None,
                "evidence": [
                    {
                        "message_id": payload.get("message_id")
                        or payload.get("current_message_id")
                        or "current-user",
                        "quote": payload["current_user_message"],
                    }
                ],
            }
            normalized["dialogue_act"] = "CORRECT_CONTEXT"
            normalized["topic_action"] = "KEEP"
            dialogue_act = "CORRECT_CONTEXT"
            actions.append(f"EXPLICIT_CLEAR_{slot.upper()}_APPLIED")

    if detected_procedure is not None:
        candidate_ids = {
            item.get("id") for item in payload.get("procedure_candidates") or []
        }
        model_procedure_is_unknown = (
            patch["procedure_id"].get("op") == "SET"
            and patch["procedure_id"].get("value") not in candidate_ids
        )
        if model_procedure_is_unknown:
            pass
        elif detected_procedure == state.get("procedure_id"):
            if patch["procedure_id"]["op"] != "KEEP" or normalized["topic_action"] == "SWITCH":
                actions.append("REPEATED_PROCEDURE_KEEPS_TOPIC")
            patch["procedure_id"] = _keep_patch()
            normalized["topic_action"] = "KEEP"
        elif (
            current_procedure is None
            or explicit_correction
            or _has_explicit_procedure_reference(
                payload, message, detected_procedure
            )
        ):
            if (
                patch["procedure_id"].get("op") != "SET"
                or patch["procedure_id"].get("value") != detected_procedure
                or normalized["topic_action"] != "SWITCH"
            ):
                actions.append("CATALOG_PROCEDURE_RECOVERED")
            patch["procedure_id"] = _set_patch(detected_procedure, payload)
            normalized["topic_action"] = "SWITCH"
        elif patch["procedure_id"].get("op") == "SET":
            patch["procedure_id"] = _keep_patch()
            normalized["topic_action"] = "KEEP"
            actions.append("UNSUPPORTED_IMPLICIT_PROCEDURE_SWITCH_REMOVED")

    if detected_fields:
        expected_fields = sorted(set(detected_fields))
        model_fields = patch["field_intents"].get("value") or []
        if patch["field_intents"].get("op") != "SET" or sorted(model_fields) != expected_fields:
            actions.append("HIGH_CONFIDENCE_FIELDS_NORMALIZED")
        patch["field_intents"] = _set_patch(expected_fields, payload)
    elif (
        patch["field_intents"].get("op") == "SET"
        and "legal_bases" in (patch["field_intents"].get("value") or [])
        and not _has_field_cue(_positive_clause(message), "legal_bases")
    ):
        original_fields = patch["field_intents"].get("value") or []
        remaining = [
            field
            for field in original_fields
            if field != "legal_bases"
        ]
        patch["field_intents"] = (
            _set_patch(remaining, payload)
            if remaining and len(original_fields) <= 2
            else _keep_patch()
        )
        actions.append("UNSUPPORTED_LEGAL_BASIS_GUESS_REMOVED")
    elif (
        patch["field_intents"].get("op") == "SET"
        and (
            len(patch["field_intents"].get("value") or []) > 2
            or state.get("pending_clarification") == "procedure_id"
            or (patch["jurisdiction"].get("op") == "SET" and "ap dung" in message)
            or patch["as_of"].get("op") == "SET"
        )
    ):
        patch["field_intents"] = _keep_patch()
        actions.append("UNSUPPORTED_FIELD_GUESS_REMOVED")

    semantic_signal = detected_procedure is not None or bool(detected_fields)
    if dialogue_act in {"GREET", "OUT_OF_SCOPE"} and semantic_signal:
        normalized["dialogue_act"] = (
            "CORRECT_CONTEXT" if explicit_correction else "ASK_INFORMATION"
        )
        dialogue_act = normalized["dialogue_act"]
        actions.append("SEMANTIC_SIGNAL_OVERRIDES_POLICY_INTENT")

    if (
        not state.get("procedure_id")
        and detected_procedure is None
        and normalized["topic_action"] == "UNRESOLVED"
        and "chuan bi" not in message
    ):
        if patch["procedure_id"]["op"] != "KEEP" or patch["field_intents"]["op"] != "KEEP":
            actions.append("UNRESOLVED_TOPIC_DROPS_UNGROUNDED_ROUTING")
        patch["procedure_id"] = _keep_patch()
        patch["field_intents"] = _keep_patch()

    dialogue_act = normalized["dialogue_act"]

    procedure = patch["procedure_id"]
    if (
        normalized["topic_action"] == "SWITCH"
        and procedure["op"] == "SET"
        and procedure["value"] == state.get("procedure_id")
    ):
        normalized["topic_action"] = "KEEP"
        patch["procedure_id"] = _keep_patch()
        actions.append("REPEATED_PROCEDURE_KEEPS_TOPIC")

    if (
        explicit_correction
        and normalized["topic_action"] in {"KEEP", "SWITCH"}
        and any(patch[slot]["op"] != "KEEP" for slot in CONTEXT_SLOTS)
    ):
        if normalized["dialogue_act"] != "CORRECT_CONTEXT":
            actions.append("EXPLICIT_TOPIC_CORRECTION")
        normalized["dialogue_act"] = "CORRECT_CONTEXT"
        dialogue_act = normalized["dialogue_act"]

    if dialogue_act in {"GREET", "OUT_OF_SCOPE"}:
        safe_topic = "KEEP" if has_context else "UNRESOLVED"
        if normalized["topic_action"] != safe_topic or any(
            patch[slot]["op"] != "KEEP" for slot in CONTEXT_SLOTS
        ):
            actions.append("POLICY_INTENT_KEEPS_CONTEXT")
        normalized["topic_action"] = safe_topic
        for slot in CONTEXT_SLOTS:
            patch[slot] = _keep_patch()
        return normalized, actions

    pending = state.get("pending_clarification")
    if (
        pending in CONTEXT_SLOTS
        and patch[pending]["op"] == "SET"
        and not explicit_correction
        and normalized["dialogue_act"] != "PROVIDE_CLARIFICATION"
    ):
        normalized["dialogue_act"] = "PROVIDE_CLARIFICATION"
        actions.append("PENDING_SLOT_WAS_PROVIDED")

    if normalized["dialogue_act"] == "PROVIDE_CLARIFICATION" and pending is None:
        normalized["dialogue_act"] = (
            "CORRECT_CONTEXT" if explicit_correction else "ASK_INFORMATION"
        )
        actions.append("UNSOLICITED_CLARIFICATION_DOWNGRADED")

    if (
        normalized["dialogue_act"] == "CORRECT_CONTEXT"
        and not explicit_correction
        and normalized["topic_action"] == "KEEP"
    ):
        changed_slots = [
            slot for slot in CONTEXT_SLOTS if patch[slot]["op"] in {"SET", "CLEAR"}
        ]
        if changed_slots and all(
            state.get(slot) in (None, [], "") for slot in changed_slots
        ):
            normalized["dialogue_act"] = "ASK_INFORMATION"
            actions.append("NEW_VALUE_IS_NOT_A_CORRECTION")

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
