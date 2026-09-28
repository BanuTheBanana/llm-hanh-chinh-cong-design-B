"""Build the fictional, error-driven TRAIN v2 fixture for G5 intent/context."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / "evaluation/fixtures/intent-context-train-pilot-v1/cases.jsonl"
DEV = ROOT / "evaluation/fixtures/intent-context-pilot-v1/cases.jsonl"
OUTPUT = ROOT / "evaluation/fixtures/intent-context-train-hard-v2"
CANDIDATES = [
    {"id": "p_birth", "name": "Đăng ký khai sinh"},
    {"id": "p_marriage", "name": "Đăng ký kết hôn"},
    {"id": "p_death", "name": "Đăng ký khai tử"},
    {"id": "p_copy", "name": "Cấp bản sao trích lục hộ tịch"},
    {"id": "p_residence", "name": "Xác nhận thông tin về cư trú"},
    {"id": "p_change", "name": "Đăng ký thay đổi, cải chính hộ tịch"},
]
KEEP = {"op": "KEEP", "value": None}


def normalized(text: str) -> str:
    return " ".join(text.casefold().split())


def patch(op: str = "KEEP", value=None) -> dict:
    return {"op": op, "value": value}


def state(
    procedure_id: str | None = None,
    *,
    fields: list[str] | None = None,
    jurisdiction: str | None = None,
    as_of: str | None = None,
    pending: str | None = None,
) -> dict:
    return {
        "procedure_id": procedure_id,
        "field_intents": fields or [],
        "jurisdiction": jurisdiction,
        "as_of": as_of,
        "pending_clarification": pending,
    }


def expected(
    dialogue_act: str,
    topic_action: str,
    *,
    procedure: dict = KEEP,
    fields: dict = KEEP,
    jurisdiction: dict = KEEP,
    as_of: dict = KEEP,
) -> dict:
    return {
        "dialogue_act": dialogue_act,
        "topic_action": topic_action,
        "patch": {
            "procedure_id": procedure,
            "field_intents": fields,
            "jurisdiction": jurisdiction,
            "as_of": as_of,
        },
    }


def build_cases() -> list[dict]:
    rows: list[dict] = []
    seen: set[str] = set()
    dev_text = {
        normalized(json.loads(line)["current_user_message"])
        for line in DEV.read_text(encoding="utf-8").splitlines()
    }

    def add(group: str, message: str, before: dict, target: dict) -> None:
        key = normalized(message)
        if key in seen or key in dev_text:
            return
        seen.add(key)
        rows.append(
            {
                "case_id": f"ic2-{len(rows) + 1:04d}",
                "group": group,
                "current_user_message": message,
                "state_before": before,
                "procedure_candidates": CANDIDATES,
                "expected": target,
            }
        )

    # Keep reviewed pilot labels, deduplicate utterances and regenerate IDs.
    for line in BASE.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        add(row["group"], row["current_user_message"], row["state_before"], row["expected"])

    hard_fields = {
        "receiving_authority": (
            "Hồ sơ {name} được tiếp nhận bởi cơ quan nào?",
            "Tôi phải nộp hồ sơ {name} cho đơn vị nào?",
        ),
        "submission_methods": (
            "Tôi có thể gửi hồ sơ {name} qua những kênh nào?",
            "{name} cho phép nộp online, trực tiếp hay bưu điện?",
        ),
        "applicant_scope": (
            "Ai là người được thực hiện {name}?",
            "Đối tượng có quyền làm {name} gồm những ai?",
        ),
        "legal_bases": (
            "{name} được quy định trong văn bản pháp lý nào?",
            "Cho biết căn cứ pháp luật của {name}.",
        ),
    }
    for candidate in CANDIDATES:
        for field, templates in hard_fields.items():
            for template in templates:
                add(
                    "hard_field_direct",
                    template.format(name=candidate["name"]),
                    state(),
                    expected(
                        "ASK_INFORMATION",
                        "SWITCH",
                        procedure=patch("SET", candidate["id"]),
                        fields=patch("SET", [field]),
                    ),
                )

    followups = {
        "receiving_authority": (
            "Vậy chính xác cơ quan nào nhận bộ hồ sơ?",
            "Tôi phải đến đơn vị tiếp nhận nào?",
            "Nơi nộp hồ sơ là cơ quan nào vậy?",
        ),
        "submission_methods": (
            "Có thể gửi bằng các hình thức nào?",
            "Nộp online hay qua bưu điện được chứ?",
            "Còn những kênh nộp hồ sơ thì sao?",
        ),
        "required_documents": (
            "Bộ hồ sơ phải có những giấy tờ nào?",
            "Tôi cần mang theo tài liệu gì?",
            "Thành phần cần chuẩn bị gồm gì?",
        ),
        "applicant_scope": (
            "Những đối tượng nào được thực hiện?",
            "Ai có quyền đứng tên làm việc này?",
            "Người nào thuộc phạm vi áp dụng?",
        ),
        "legal_bases": (
            "Cơ sở pháp lý nằm ở văn bản nào?",
            "Việc này căn cứ theo quy định nào?",
            "Cho tôi tên văn bản làm căn cứ.",
        ),
        "steps": (
            "Quy trình lần lượt diễn ra thế nào?",
            "Các bước xử lý cụ thể gồm gì?",
            "Trình tự thực hiện ra sao vậy?",
        ),
        "fees": (
            "Khoản lệ phí thủ tục là bao nhiêu?",
            "Tổng phí phải đóng thế nào?",
            "Có phải nộp tiền cho thủ tục không?",
        ),
        "processing_times": (
            "Cơ quan xử lý trong thời hạn bao lâu?",
            "Mất khoảng mấy ngày để có kết quả?",
            "Thời gian giải quyết được tính thế nào?",
        ),
    }
    for field_index, (field, messages) in enumerate(followups.items()):
        for message_index, message in enumerate(messages):
            current = CANDIDATES[(field_index + message_index) % len(CANDIDATES)]
            add(
                "hard_field_followup",
                message,
                state(current["id"], fields=["required_documents"]),
                expected("ASK_INFORMATION", "KEEP", fields=patch("SET", [field])),
            )

    multi_cases = [
        ("Nơi tiếp nhận và cách gửi hồ sơ là gì?", ["receiving_authority", "submission_methods"]),
        ("Ai được làm và phải chuẩn bị giấy tờ nào?", ["applicant_scope", "required_documents"]),
        ("Cho tôi căn cứ pháp lý cùng các bước thực hiện.", ["legal_bases", "steps"]),
        ("Cần đóng phí bao nhiêu và đợi trong bao lâu?", ["fees", "processing_times"]),
        (
            "Nộp cho đơn vị nào và qua mạng được không?",
            ["receiving_authority", "submission_methods"],
        ),
        ("Đối tượng áp dụng và văn bản quy định là gì?", ["applicant_scope", "legal_bases"]),
        ("Hồ sơ gồm gì và trình tự xử lý thế nào?", ["required_documents", "steps"]),
        ("Mất mấy ngày, có thu lệ phí không?", ["processing_times", "fees"]),
        (
            "Tôi đến đâu, cần mang gì và trả bao nhiêu?",
            ["receiving_authority", "required_documents", "fees"],
        ),
        (
            "Ai được nộp, nộp bằng cách nào và gồm bước gì?",
            ["applicant_scope", "submission_methods", "steps"],
        ),
        (
            "Cơ quan nhận hồ sơ và thời gian xử lý là gì?",
            ["receiving_authority", "processing_times"],
        ),
        (
            "Cho biết cách nộp, lệ phí và căn cứ pháp lý.",
            ["submission_methods", "fees", "legal_bases"],
        ),
    ]
    for index, (message, fields) in enumerate(multi_cases):
        current = CANDIDATES[index % len(CANDIDATES)]
        add(
            "hard_multi_followup",
            message,
            state(current["id"], fields=["required_documents"]),
            expected("ASK_INFORMATION", "KEEP", fields=patch("SET", fields)),
        )

    locations = [
        "phường Linh Tây, TP.HCM",
        "quận Hải Châu, Đà Nẵng",
        "thành phố Biên Hòa, Đồng Nai",
        "tỉnh Bắc Ninh",
        "quận Ninh Kiều, Cần Thơ",
        "thành phố Vinh, Nghệ An",
    ]
    location_messages = (
        "Địa bàn tôi thực hiện là {value}.",
        "Tôi làm hồ sơ ở {value}.",
        "Nơi thực hiện: {value}.",
        "Chọn phạm vi tại {value}.",
        "Địa phương cần tra cứu là {value}.",
        "Tôi đang ở {value}.",
    )
    for index, value in enumerate(locations):
        add(
            "hard_scope_pending",
            location_messages[index].format(value=value),
            state(CANDIDATES[index]["id"], pending="jurisdiction"),
            expected(
                "PROVIDE_CLARIFICATION",
                "KEEP",
                jurisdiction=patch("SET", value),
            ),
        )

    dates = [
        ("Dùng quy định tại ngày 05/07/2026.", "2026-07-05"),
        ("Mốc tra cứu là 21/08/2026.", "2026-08-21"),
        ("Tính theo ngày 03/09/2026.", "2026-09-03"),
        ("Ngày cần đối chiếu: 17/06/2026.", "2026-06-17"),
        ("Tôi cần thông tin có hiệu lực ngày 28/07/2026.", "2026-07-28"),
        ("Tra cứu tại thời điểm 11/08/2026.", "2026-08-11"),
    ]
    for index, (message, value) in enumerate(dates):
        add(
            "hard_date_pending",
            message,
            state(CANDIDATES[index]["id"], fields=["fees"], pending="as_of"),
            expected("PROVIDE_CLARIFICATION", "KEEP", as_of=patch("SET", value)),
        )

    for index, value in enumerate(locations):
        old = "TP.HCM" if index % 2 == 0 else "Hà Nội"
        add(
            "hard_scope_correction",
            f"Sửa địa phương {old} thành {value}.",
            state(CANDIDATES[index]["id"], jurisdiction=old),
            expected("CORRECT_CONTEXT", "KEEP", jurisdiction=patch("SET", value)),
        )

    direct_locations = ["Hà Nội", "TP.HCM", "Đà Nẵng", "Huế", "Hải Phòng", "Cần Thơ"]
    for index, candidate in enumerate(CANDIDATES):
        value = direct_locations[index]
        add(
            "hard_scope_direct",
            f"Tại {value}, {candidate['name']} cần nộp những giấy tờ nào?",
            state(),
            expected(
                "ASK_INFORMATION",
                "SWITCH",
                procedure=patch("SET", candidate["id"]),
                fields=patch("SET", ["required_documents"]),
                jurisdiction=patch("SET", value),
            ),
        )

    field_cycle = [
        ("lệ phí thế nào", "fees"),
        ("mất bao lâu", "processing_times"),
        ("nộp ở cơ quan nào", "receiving_authority"),
        ("có nộp trực tuyến được không", "submission_methods"),
        ("cần giấy tờ gì", "required_documents"),
        ("dựa trên văn bản nào", "legal_bases"),
    ]
    for index, candidate in enumerate(CANDIDATES):
        old = CANDIDATES[(index + 1) % len(CANDIDATES)]
        phrase, field = field_cycle[index]
        add(
            "hard_correction_switch",
            f"Tôi nói nhầm, không phải {old['name']} mà là {candidate['name']}; {phrase}?",
            state(old["id"], fields=["steps"], jurisdiction="Địa phương cũ", as_of="2026-06-01"),
            expected(
                "CORRECT_CONTEXT",
                "SWITCH",
                procedure=patch("SET", candidate["id"]),
                fields=patch("SET", [field]),
                jurisdiction=patch("CLEAR"),
            ),
        )
        add(
            "hard_correction_switch",
            f"Ý cần sửa là chuyển sang {candidate['name']}, chưa hỏi mục chi tiết.",
            state(old["id"], fields=["fees"], jurisdiction="Phạm vi cũ"),
            expected(
                "CORRECT_CONTEXT",
                "SWITCH",
                procedure=patch("SET", candidate["id"]),
                fields=patch("CLEAR"),
                jurisdiction=patch("CLEAR"),
            ),
        )

    no_state_boundary = [
        ("Chào bạn, chúc một ngày tốt lành.", "GREET"),
        ("Cảm ơn nhé!", "GREET"),
        ("Hãy kể một câu chuyện ngắn.", "OUT_OF_SCOPE"),
        ("Chiếc máy tính này bán giá nào?", "OUT_OF_SCOPE"),
        ("Tôi muốn hỏi thêm một việc.", "ASK_INFORMATION"),
        ("Có giấy tờ cần xử lý.", "ASK_INFORMATION"),
    ]
    for message, act in no_state_boundary:
        add("hard_boundary", message, state(), expected(act, "UNRESOLVED"))

    with_state_boundary = [
        ("Xin chào lại nhé.", "GREET"),
        ("Cảm ơn, tôi đã hiểu.", "GREET"),
        ("Viết cho tôi lời bài hát.", "OUT_OF_SCOPE"),
        ("Một chiếc điện thoại có giá bao nhiêu?", "OUT_OF_SCOPE"),
        ("Được rồi, nói tiếp đi.", "ASK_INFORMATION"),
        ("Tôi muốn biết thêm.", "ASK_INFORMATION"),
    ]
    for index, (message, act) in enumerate(with_state_boundary):
        add(
            "hard_boundary",
            message,
            state(CANDIDATES[index]["id"], fields=["fees"]),
            expected(act, "KEEP"),
        )

    resets = [
        "Xóa phiên tra cứu này và làm lại.",
        "Bỏ toàn bộ chủ đề hiện tại.",
        "Khởi động lại phần hỏi thủ tục.",
        "Quên hết ngữ cảnh vừa trao đổi.",
        "Tạo cuộc tra cứu trống từ đầu.",
        "Reset toàn bộ thông tin đang nhớ.",
    ]
    for index, message in enumerate(resets):
        add(
            "hard_reset",
            message,
            state(
                CANDIDATES[index]["id"],
                fields=["fees"],
                jurisdiction="Phạm vi cũ",
                as_of="2026-06-01",
            ),
            expected(
                "RESET_CONTEXT",
                "RESET",
                procedure=patch("CLEAR"),
                fields=patch("CLEAR"),
                jurisdiction=patch("CLEAR"),
                as_of=patch("CLEAR"),
            ),
        )
    return rows


def main() -> int:
    cases = build_cases()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    payload = "".join(
        json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in cases
    )
    cases_path = OUTPUT / "cases.jsonl"
    cases_path.write_bytes(payload.encode("utf-8"))
    groups = dict(sorted(Counter(row["group"] for row in cases).items()))
    manifest = {
        "schema_version": "g5-intent-context-train-hard-manifest-v2",
        "source_file": "cases.jsonl",
        "split": "TRAIN",
        "final_test": False,
        "classification": "D0_SYSTEM_SMOKE",
        "contains_company_data": False,
        "case_count": len(cases),
        "groups": groups,
        "content_sha256": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
        "strategy": "deduplicated pilot plus manually reviewed error-class templates",
    }
    (OUTPUT / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
