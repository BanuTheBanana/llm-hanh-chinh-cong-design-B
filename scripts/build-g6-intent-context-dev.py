"""Build the reviewed fictional conversational DEV set for G6 intent/context."""

from __future__ import annotations

import hashlib
import json
import re
import sys
import unicodedata
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "evaluation/fixtures/g6-intent-context-dev-v1"
sys.path.insert(0, str(ROOT))

from training.intent_context import (  # noqa: E402
    CONTEXT_SLOTS,
    apply_output_to_state,
    build_target,
)


CANDIDATES = [
    {"id": "p_birth", "name": "Đăng ký khai sinh"},
    {"id": "p_marriage", "name": "Đăng ký kết hôn"},
    {"id": "p_death", "name": "Đăng ký khai tử"},
    {"id": "p_copy", "name": "Cấp bản sao trích lục hộ tịch"},
    {"id": "p_residence", "name": "Xác nhận thông tin về cư trú"},
    {"id": "p_change", "name": "Đăng ký thay đổi, cải chính hộ tịch"},
]


def turn(message, group, act, topic, updates=None, *, clears=(), pending=None):
    return {
        "message": message,
        "group": group,
        "act": act,
        "topic": topic,
        "updates": updates or {},
        "clears": clears,
        "pending": pending,
    }


CONVERSATIONS = [
    [
        turn("Gia đình cần làm khai sinh, xin cho danh sách giấy tờ phải chuẩn bị.", "direct", "ASK_INFORMATION", "SWITCH", {"procedure_id": "p_birth", "field_intents": ["required_documents"]}),
        turn("Nơi nào nhận bộ hồ sơ này?", "followup", "ASK_INFORMATION", "KEEP", {"field_intents": ["receiving_authority"]}),
        turn("Tôi không cần nơi nộp nữa, chuyển sang mức lệ phí.", "correction_switch", "CORRECT_CONTEXT", "KEEP", {"field_intents": ["fees"]}),
    ],
    [
        turn("Có những kênh nào để gửi hồ sơ đăng ký kết hôn?", "direct", "ASK_INFORMATION", "SWITCH", {"procedure_id": "p_marriage", "field_intents": ["submission_methods"]}),
        turn("Trường hợp này thực hiện tại thành phố Bến Tre.", "scope_date", "ASK_INFORMATION", "KEEP", {"jurisdiction": "thành phố Bến Tre"}),
        turn("Ngày cần kiểm tra là 01/08/2026.", "clarification", "PROVIDE_CLARIFICATION", "KEEP", {"as_of": "2026-08-01"}, pending="as_of"),
    ],
    [
        turn("Cơ sở pháp lý của việc đăng ký khai tử nằm trong các văn bản nào?", "direct", "ASK_INFORMATION", "SWITCH", {"procedure_id": "p_death", "field_intents": ["legal_bases"]}),
        turn("Đổi qua cấp bản sao trích lục hộ tịch và xem khoản phí.", "correction_switch", "CORRECT_CONTEXT", "SWITCH", {"procedure_id": "p_copy", "field_intents": ["fees"]}),
        turn("Quy trình cấp bản sao đó gồm các bước nào?", "followup", "ASK_INFORMATION", "KEEP", {"field_intents": ["steps"]}),
    ],
    [
        turn("Tôi chưa biết tên thủ tục hành chính đang cần.", "boundary", "ASK_INFORMATION", "UNRESOLVED"),
        turn("Nhu cầu cụ thể là đăng ký thay đổi, cải chính hộ tịch.", "clarification", "PROVIDE_CLARIFICATION", "SWITCH", {"procedure_id": "p_change"}, pending="procedure_id"),
        turn("Tôi cần hỏi về thành phần hồ sơ.", "clarification", "PROVIDE_CLARIFICATION", "KEEP", {"field_intents": ["required_documents"]}, pending="field_intents"),
    ],
    [
        turn("Xác nhận thông tin cư trú thường được xử lý trong bao lâu?", "direct", "ASK_INFORMATION", "SWITCH", {"procedure_id": "p_residence", "field_intents": ["processing_times"]}),
        turn("Tôi nộp ở quận Gò Vấp, Thành phố Hồ Chí Minh.", "clarification", "PROVIDE_CLARIFICATION", "KEEP", {"jurisdiction": "quận Gò Vấp, Thành phố Hồ Chí Minh"}, pending="jurisdiction"),
        turn("Sửa địa bàn vừa nói thành quận Tân Bình, Thành phố Hồ Chí Minh.", "correction_switch", "CORRECT_CONTEXT", "KEEP", {"jurisdiction": "quận Tân Bình, Thành phố Hồ Chí Minh"}),
    ],
    [
        turn("Muốn cấp bản sao trích lục hộ tịch thì phải có tài liệu gì?", "direct", "ASK_INFORMATION", "SWITCH", {"procedure_id": "p_copy", "field_intents": ["required_documents"]}),
        turn("Xóa bối cảnh và cho tôi bắt đầu một lượt tra cứu khác.", "reset", "RESET_CONTEXT", "RESET"),
        turn("Yêu cầu mới là các cách nộp hồ sơ đăng ký khai sinh.", "direct", "ASK_INFORMATION", "SWITCH", {"procedure_id": "p_birth", "field_intents": ["submission_methods"]}),
    ],
    [
        turn("Đăng ký kết hôn dành cho những đối tượng nào?", "direct", "ASK_INFORMATION", "SWITCH", {"procedure_id": "p_marriage", "field_intents": ["applicant_scope"]}),
        turn("Cảm ơn bạn, tôi hiểu rồi.", "boundary", "GREET", "KEEP"),
        turn("Thời hạn trả kết quả của thủ tục đó là bao lâu?", "followup", "ASK_INFORMATION", "KEEP", {"field_intents": ["processing_times"]}),
    ],
    [
        turn("Cơ quan nào chịu trách nhiệm nhận đăng ký khai tử?", "direct", "ASK_INFORMATION", "SWITCH", {"procedure_id": "p_death", "field_intents": ["receiving_authority"]}),
        turn("Bạn dự đoán giá vàng ngày mai giúp tôi.", "boundary", "OUT_OF_SCOPE", "KEEP"),
        turn("Trở lại khai tử, bộ hồ sơ phải kèm giấy tờ nào?", "followup", "ASK_INFORMATION", "KEEP", {"field_intents": ["required_documents"]}),
    ],
    [
        turn("Tra cứu tại ngày 11 tháng 2 năm 2026: đăng ký khai sinh thực hiện theo trình tự nào?", "scope_date", "ASK_INFORMATION", "SWITCH", {"procedure_id": "p_birth", "field_intents": ["steps"], "as_of": "2026-02-11"}),
        turn("Ngoài trình tự, thủ tục này có thu lệ phí không?", "followup", "ASK_INFORMATION", "KEEP", {"field_intents": ["fees"]}),
        turn("Bỏ mốc ngày đã chọn nhưng giữ thủ tục và nội dung đang hỏi.", "correction_switch", "CORRECT_CONTEXT", "KEEP", clears=("as_of",)),
    ],
    [
        turn("Ở huyện Châu Thành, Đồng Tháp, cải chính hộ tịch có mất lệ phí không?", "scope_date", "ASK_INFORMATION", "SWITCH", {"procedure_id": "p_change", "field_intents": ["fees"], "jurisdiction": "huyện Châu Thành, Đồng Tháp"}),
        turn("Tôi muốn đối chiếu vào ngày 06 tháng 5 năm 2026.", "scope_date", "ASK_INFORMATION", "KEEP", {"as_of": "2026-05-06"}),
        turn("Ngoài khoản phí, hồ sơ cần mang theo tài liệu gì?", "followup", "ASK_INFORMATION", "KEEP", {"field_intents": ["required_documents"]}),
    ],
    [
        turn("Chào bạn, hệ thống này hỗ trợ nội dung nào?", "boundary", "GREET", "UNRESOLVED"),
        turn("Tôi cần nơi tiếp nhận yêu cầu cấp bản sao trích lục hộ tịch.", "direct", "ASK_INFORMATION", "SWITCH", {"procedure_id": "p_copy", "field_intents": ["receiving_authority"]}),
        turn("Vâng.", "boundary", "ASK_INFORMATION", "KEEP"),
    ],
    [
        turn("Tôi không rõ dịch vụ mình cần gọi là gì.", "boundary", "ASK_INFORMATION", "UNRESOLVED"),
        turn("Tên đúng của dịch vụ là đăng ký kết hôn.", "clarification", "PROVIDE_CLARIFICATION", "SWITCH", {"procedure_id": "p_marriage"}, pending="procedure_id"),
        turn("Với kết hôn, người dân phải đóng khoản tiền nào?", "followup", "ASK_INFORMATION", "KEEP", {"field_intents": ["fees"]}),
    ],
    [
        turn("Tôi muốn xác nhận cư trú và cần biết hình thức nộp yêu cầu.", "direct", "ASK_INFORMATION", "SWITCH", {"procedure_id": "p_residence", "field_intents": ["submission_methods"]}),
        turn("Không hỏi cư trú nữa, đổi sang khai tử và cho biết ai được thực hiện.", "correction_switch", "CORRECT_CONTEXT", "SWITCH", {"procedure_id": "p_death", "field_intents": ["applicant_scope"]}),
        turn("Sau đó quy trình khai tử đi qua những bước nào?", "followup", "ASK_INFORMATION", "KEEP", {"field_intents": ["steps"]}),
    ],
    [
        turn("Làm khai sinh cần chuẩn bị những tài liệu gì?", "direct", "ASK_INFORMATION", "SWITCH", {"procedure_id": "p_birth", "field_intents": ["required_documents"]}),
        turn("Tôi thực hiện tại thị xã Cai Lậy, Tiền Giang.", "scope_date", "ASK_INFORMATION", "KEEP", {"jurisdiction": "thị xã Cai Lậy, Tiền Giang"}),
        turn("Ở địa bàn vừa nêu, lệ phí của khai sinh thế nào?", "followup", "ASK_INFORMATION", "KEEP", {"field_intents": ["fees"]}),
    ],
    [
        turn("Thay đổi, cải chính hộ tịch có thời gian giải quyết mấy ngày?", "direct", "ASK_INFORMATION", "SWITCH", {"procedure_id": "p_change", "field_intents": ["processing_times"]}),
        turn("Không hỏi thời gian nữa mà cần biết đơn vị có thẩm quyền tiếp nhận.", "correction_switch", "CORRECT_CONTEXT", "KEEP", {"field_intents": ["receiving_authority"]}),
        turn("Có thể gửi hồ sơ đến đơn vị đó bằng các kênh nào?", "followup", "ASK_INFORMATION", "KEEP", {"field_intents": ["submission_methods"]}),
    ],
    [
        turn("Những quy định nào là căn cứ cấp bản sao trích lục hộ tịch?", "direct", "ASK_INFORMATION", "SWITCH", {"procedure_id": "p_copy", "field_intents": ["legal_bases"]}),
        turn("Phạm vi thực hiện của tôi là phường Trần Phú, thành phố Quy Nhơn.", "scope_date", "ASK_INFORMATION", "KEEP", {"jurisdiction": "phường Trần Phú, thành phố Quy Nhơn"}),
        turn("Chuyển địa bàn sang phường Ghềnh Ráng, thành phố Quy Nhơn.", "correction_switch", "CORRECT_CONTEXT", "KEEP", {"jurisdiction": "phường Ghềnh Ráng, thành phố Quy Nhơn"}),
    ],
    [
        turn("Đăng ký khai tử có thu khoản phí nào từ người làm hồ sơ?", "direct", "ASK_INFORMATION", "SWITCH", {"procedure_id": "p_death", "field_intents": ["fees"]}),
        turn("Bắt đầu lại và xóa toàn bộ nội dung cũ.", "reset", "RESET_CONTEXT", "RESET"),
        turn("Cho tôi các văn bản làm căn cứ xác nhận thông tin cư trú.", "direct", "ASK_INFORMATION", "SWITCH", {"procedure_id": "p_residence", "field_intents": ["legal_bases"]}),
    ],
    [
        turn("Trình tự đăng ký kết hôn từ đầu đến cuối ra sao?", "direct", "ASK_INFORMATION", "SWITCH", {"procedure_id": "p_marriage", "field_intents": ["steps"]}),
        turn("Trong bộ hồ sơ kết hôn cần có giấy tờ nào?", "followup", "ASK_INFORMATION", "KEEP", {"field_intents": ["required_documents"]}),
        turn("Không tiếp tục hỏi kết hôn; chuyển sang khai sinh và cho biết nơi tiếp nhận.", "correction_switch", "CORRECT_CONTEXT", "SWITCH", {"procedure_id": "p_birth", "field_intents": ["receiving_authority"]}),
    ],
    [
        turn("Người nào đủ điều kiện yêu cầu cải chính hộ tịch?", "direct", "ASK_INFORMATION", "SWITCH", {"procedure_id": "p_change", "field_intents": ["applicant_scope"]}),
        turn("Thời điểm cần tra cứu là ngày 19-07-2026.", "clarification", "PROVIDE_CLARIFICATION", "KEEP", {"as_of": "2026-07-19"}, pending="as_of"),
        turn("Hãy viết cho tôi mã trò chơi đơn giản.", "boundary", "OUT_OF_SCOPE", "KEEP"),
    ],
    [
        turn("Cấp bản sao trích lục có thể thực hiện bằng những hình thức nào?", "direct", "ASK_INFORMATION", "SWITCH", {"procedure_id": "p_copy", "field_intents": ["submission_methods"]}),
        turn("Không cần hình thức nộp nữa, tôi hỏi thời gian trả kết quả.", "correction_switch", "CORRECT_CONTEXT", "KEEP", {"field_intents": ["processing_times"]}),
        turn("Kết thúc ngữ cảnh cấp bản sao hiện tại.", "reset", "RESET_CONTEXT", "RESET"),
    ],
]


def expected_output(item):
    patch = {slot: {"op": "KEEP", "value": None} for slot in CONTEXT_SLOTS}
    for slot, value in item["updates"].items():
        patch[slot] = {"op": "SET", "value": value}
    for slot in item["clears"]:
        patch[slot] = {"op": "CLEAR", "value": None}
    return {
        "dialogue_act": item["act"],
        "topic_action": item["topic"],
        "patch": patch,
    }


def normalize(value):
    return re.sub(
        r"[^\w]+", " ", unicodedata.normalize("NFC", value).casefold(), flags=re.UNICODE
    ).strip()


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    assert len(CONVERSATIONS) == 20
    rows = []
    for conversation_number, turns in enumerate(CONVERSATIONS, start=1):
        assert len(turns) == 3
        state = {"procedure_id": None, "field_intents": [], "jurisdiction": None, "as_of": None}
        for turn_number, item in enumerate(turns, start=1):
            before = {**state, "pending_clarification": item["pending"]}
            expected = expected_output(item)
            row = {
                "case_id": f"g6-dev-v1-{conversation_number:02d}-t{turn_number}",
                "conversation_id": f"g6-dev-v1-conversation-{conversation_number:02d}",
                "turn_index": turn_number,
                "group": item["group"],
                "split": "DEV",
                "current_user_message": item["message"],
                "assistant_message_before": None if turn_number == 1 else "Đã ghi nhận lượt trước.",
                "state_before": before,
                "procedure_candidates": CANDIDATES,
                "expected": expected,
                "review": {"reviewer": "Bui Xuan Hoan", "status": "APPROVED"},
            }
            rows.append(row)
            state = apply_output_to_state(before, expected)

    schema = json.loads(
        (ROOT / "docs/giai-doan-5/schema/intent-context-v2.schema.json").read_text(
            encoding="utf-8"
        )
    )
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    for row in rows:
        validator.validate(build_target(row))

    messages = [normalize(row["current_user_message"]) for row in rows]
    assert len(rows) == 60 and len(set(messages)) == 60
    reference_dirs = [
        ROOT / "evaluation/fixtures/intent-context-train-hard-v2",
        ROOT / "evaluation/fixtures/intent-context-pilot-v1",
        Path(r"D:\CODEFPT\OJT\G5_Hoan_Final_Test_V1_private"),
        Path(r"D:\CODEFPT\OJT\G5_Hoan_Final_Test_V2_private"),
        Path(r"D:\CODEFPT\OJT\G5_Hoan_Final_Test_V3_private"),
    ]
    references = []
    reference_hashes = {}
    for directory in reference_dirs:
        manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
        source = directory / manifest["source_file"]
        assert sha256(source) == manifest["content_sha256"]
        reference_hashes[directory.name] = sha256(source)
        references.extend(
            normalize(json.loads(line)["current_user_message"])
            for line in source.read_text(encoding="utf-8").splitlines()
        )
    closest = [
        max(SequenceMatcher(None, message, reference).ratio() for reference in references)
        for message in messages
    ]
    exact_overlap = sum(message in set(references) for message in messages)
    near_overlap = sum(ratio >= 0.9 for ratio in closest)
    assert exact_overlap == 0
    assert near_overlap == 0, sorted(closest, reverse=True)[:10]

    OUT.mkdir(parents=True, exist_ok=True)
    cases_path = OUT / "cases.jsonl"
    cases_path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
        newline="\n",
    )
    groups = dict(sorted(Counter(row["group"] for row in rows).items()))
    manifest = {
        "schema_version": "g6-intent-context-dev-manifest-v1",
        "classification": "D0_SYSTEM_DEVELOPMENT",
        "purpose": "Reviewed conversational development gate; never final acceptance.",
        "source_file": "cases.jsonl",
        "split": "DEV",
        "final_test": False,
        "contains_company_data": False,
        "review_status": "APPROVED_DEV",
        "case_count": len(rows),
        "conversation_count": len(CONVERSATIONS),
        "turns_per_conversation": 3,
        "groups": groups,
        "content_sha256": sha256(cases_path),
        "leakage_audit": {
            "reference_hashes": reference_hashes,
            "near_duplicate_threshold": 0.9,
            "exact_overlap_count": exact_overlap,
            "near_duplicate_count": near_overlap,
            "maximum_similarity": round(max(closest), 6),
        },
    }
    (OUT / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
