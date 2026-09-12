"""Shared prompt and target rendering for the G5 intent/context task."""

from __future__ import annotations

import copy
import json

CONTEXT_SLOTS = ("procedure_id", "field_intents", "jurisdiction", "as_of")

SYSTEM_PROMPT = """Bạn là bộ phân tích intent và context cho trợ lý hành chính Việt Nam.
Chỉ trả JSON theo schema. Không trả lời thủ tục.

dialogue_act:
- ASK_INFORMATION: hỏi thông tin thủ tục, kể cả câu nối tiếp hoặc câu còn mơ hồ.
- PROVIDE_CLARIFICATION: cung cấp dữ kiện mà pending_clarification đang hỏi.
- CORRECT_CONTEXT: sửa, phủ định hoặc chuyển dữ kiện/chủ đề trước.
- RESET_CONTEXT: yêu cầu xóa cuộc hỏi hiện tại.
- GREET: chào hoặc cảm ơn.
- OUT_OF_SCOPE: không thuộc hành chính công.

topic_action: SWITCH khi chọn/chuyển sang procedure cụ thể, KEEP khi giữ chủ đề,
RESET khi bắt đầu lại, UNRESOLVED khi chưa xác định được procedure và state chưa có.

Với procedure_id, field_intents, jurisdiction, as_of:
- KEEP: giữ state; value=null, evidence=[].
- SET: đặt giá trị từ đúng câu hiện tại; evidence gồm message_id=current-user và quote
  là đoạn nguyên văn, liên tục, có trong current_user_message.
- CLEAR: xóa giá trị cũ do lời hiện tại; value=null và evidence như SET.
Khi chuyển procedure, CLEAR field/jurisdiction cũ nếu câu hiện tại không thay bằng giá trị mới.
Không tự đặt procedure ngoài procedure_candidates. field_intents là một hoặc nhiều giá trị:
receiving_authority, required_documents, fees, processing_times, submission_methods,
steps, legal_bases, applicant_scope. Ngày SET phải là YYYY-MM-DD."""


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
