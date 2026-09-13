"""Deterministic safety policy applied after intent/context model inference."""

from __future__ import annotations

import copy
import re
import unicodedata

POLICY_VERSION = "g6-intent-context-policy-v4"
CONTEXT_SLOTS = ("procedure_id", "field_intents", "jurisdiction", "as_of")
_CORRECTION_PATTERNS = (
    r"\bdoi (?:qua|sang)\b",
    r"\b(?<!vua )chuyen (?:han )?(?:chu de )?sang\b",
    r"\bkhong (?:con |tiep tuc )?hoi\b",
    r"\bkhong (?:lam|phai)\b.*\bnua\b",
    r"\bsua (?:lai |dia ban )?(?:tu|thanh|sang)\b",
    r"\bthay chu de\b",
    r"\bthay bang\b",
    r"\bsua\b[^,.!?;]{0,40}\bdia ban\b",
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
        "ben nao co tham quyen",
        "bo phan nao",
        "tham quyen tiep nhan",
        "cho biet co quan nhan",
        "den dau nop",
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
        "kem theo",
        "mang theo",
        "mang gi",
    ),
    "fees": (
        "le phi",
        "muc phi",
        "chi phi",
        "dong phi",
        "thu phi",
        "khoan tien",
        "bao nhieu tien",
    ),
    "processing_times": (
        "thoi han",
        "thoi gian",
        "bao lau",
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


def _plain_text(value: str) -> str:
    value = unicodedata.normalize("NFD", value.casefold())
    value = "".join(char for char in value if unicodedata.category(char) != "Mn")
    value = value.replace("đ", "d")
    return " ".join("".join(char if char.isalnum() else " " for char in value).split())


def _keep_patch() -> dict:
    return {"op": "KEEP", "value": None, "evidence": []}


def _set_patch(value: object, payload: dict) -> dict:
    return {
        "op": "SET",
        "value": value,
        "evidence": [
            {
                "message_id": payload.get("message_id")
                or payload.get("current_message_id")
                or "current-user",
                "quote": payload["current_user_message"],
            }
        ],
    }


def _matches_any(message: str, patterns: tuple[str, ...]) -> bool:
    return any(re.search(pattern, message) for pattern in patterns)


def _positive_clause(message: str) -> str:
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
    positive_message = _positive_clause(message)
    detected = [
        field
        for field, cues in _FIELD_CUES.items()
        if any(cue in positive_message for cue in cues)
    ]
    if "steps" in detected and "required_documents" in detected:
        strong_document_cues = (
            "giay to",
            "tai lieu",
            "thanh phan",
            "kem theo",
            "mang theo",
            "mang gi",
        )
        if not any(cue in positive_message for cue in strong_document_cues):
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


def _detect_procedure(payload: dict, message: str) -> str | None:
    """Return only a unique, high-confidence catalog match from the current text."""

    candidates = payload.get("procedure_candidates") or []
    message = _positive_clause(message)
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
        distinctive = [
            token for token in title.split() if token not in _PROCEDURE_GENERIC_TOKENS
        ]
        matched = sum(token in message_tokens for token in distinctive)
        if len(distinctive) >= 2 and matched >= 2 and matched / len(distinctive) >= 0.5:
            scored.append((matched / len(distinctive), matched, candidate_id))
    if not scored:
        return None
    scored.sort(reverse=True)
    if len(scored) > 1 and scored[0][:2] == scored[1][:2]:
        return None
    return scored[0][2]


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
    explicit_correction = _matches_any(message, _CORRECTION_PATTERNS)
    explicit_reset = _matches_any(message, _RESET_PATTERNS)
    unresolved_request = _matches_any(message, _UNRESOLVED_PATTERNS)
    detected_procedure = _detect_procedure(payload, message)
    detected_fields = _detect_fields(message)

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
        else:
            if (
                patch["procedure_id"].get("op") != "SET"
                or patch["procedure_id"].get("value") != detected_procedure
                or normalized["topic_action"] != "SWITCH"
            ):
                actions.append("CATALOG_PROCEDURE_RECOVERED")
            patch["procedure_id"] = _set_patch(detected_procedure, payload)
            normalized["topic_action"] = "SWITCH"

    if detected_fields:
        expected_fields = sorted(set(detected_fields))
        model_fields = patch["field_intents"].get("value") or []
        if patch["field_intents"].get("op") != "SET" or sorted(model_fields) != expected_fields:
            actions.append("HIGH_CONFIDENCE_FIELDS_NORMALIZED")
        patch["field_intents"] = _set_patch(expected_fields, payload)
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
