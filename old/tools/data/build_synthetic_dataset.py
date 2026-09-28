"""Build the deterministic D0 corpus used for RAG development and demos."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from uuid import UUID

ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "data/demo_synthetic"
VERSION = "synthetic-demo-v1"

SECTION_TYPES = {
    "applicant_scope": "APPLICANT_SCOPE",
    "receiving_authority": "RECEIVING_AUTHORITY",
    "submission_methods": "SUBMISSION_METHODS",
    "required_documents": "REQUIRED_DOCUMENTS",
    "steps": "STEPS",
    "fees": "FEES",
    "processing_time": "PROCESSING_TIME",
    "legal_bases": "LEGAL_BASES",
}

PROCEDURES = [
    {
        "slug": "birth_star",
        "procedure_id": "synthetic_birth_star",
        "source_id": "src_synthetic_birth_star",
        "code": "D0-BIRTH-001",
        "title": "Đăng ký khai sinh Sao Mai",
        "aliases": ["khai sinh sao mai", "làm giấy khai sinh sao mai"],
        "facts": {
            "applicant_scope": "D0 giả lập – Đăng ký khai sinh Sao Mai dành cho cha, mẹ hoặc người giám hộ tại Thành phố Demo.",
            "receiving_authority": "D0 giả lập – Hồ sơ khai sinh Sao Mai được tiếp nhận tại Bộ phận Một cửa Phường Mặt Trời, Thành phố Demo.",
            "submission_methods": "D0 giả lập – Có thể nộp hồ sơ khai sinh Sao Mai trực tiếp hoặc qua Cổng Dịch vụ Demo.",
            "required_documents": "D0 giả lập – Hồ sơ khai sinh Sao Mai gồm Phiếu D0-KS01, thẻ Sao Mai của người nộp và giấy chứng sinh mô phỏng.",
            "steps": "D0 giả lập – Các bước thực hiện quy trình khai sinh Sao Mai gồm gửi hồ sơ, nhận mã D0, kiểm tra mô phỏng và nhận kết quả thử nghiệm.",
            "fees": "D0 giả lập – Lệ phí khai sinh Sao Mai là 5 đơn vị thử nghiệm; đây không phải mức phí thật.",
            "processing_time": "D0 giả lập – Thời gian xử lý khai sinh Sao Mai là 2 ngày mô phỏng.",
            "legal_bases": "D0 giả lập – Căn cứ của khai sinh Sao Mai là Quy tắc D0-KS-2026, một văn bản hoàn toàn hư cấu.",
        },
    },
    {
        "slug": "identity_moon",
        "procedure_id": "synthetic_identity_moon",
        "source_id": "src_synthetic_identity_moon",
        "code": "D0-ID-002",
        "title": "Cấp thẻ căn cước Ánh Trăng",
        "aliases": ["căn cước ánh trăng", "làm thẻ ánh trăng"],
        "facts": {
            "applicant_scope": "D0 giả lập – Cấp thẻ căn cước Ánh Trăng dành cho cư dân từ 14 tuổi của Quận Ngân Hà, Thành phố Demo.",
            "receiving_authority": "D0 giả lập – Hồ sơ thẻ Ánh Trăng được tiếp nhận tại Trạm Dịch vụ Ngân Hà số 2.",
            "submission_methods": "D0 giả lập – Cách nộp hồ sơ thẻ Ánh Trăng là đặt lịch trên Cổng Dịch vụ Demo rồi đến trực tiếp Trạm Ngân Hà số 2.",
            "required_documents": "D0 giả lập – Hồ sơ thẻ Ánh Trăng gồm Phiếu D0-CC02, mã cư dân thử nghiệm và ảnh chân dung mô phỏng.",
            "steps": "D0 giả lập – Các bước thực hiện quy trình thẻ Ánh Trăng gồm đặt lịch, đối chiếu dữ liệu giả, chụp ảnh thử và nhận phiếu hẹn D0.",
            "fees": "D0 giả lập – Lệ phí cấp thẻ Ánh Trăng là 9 đơn vị thử nghiệm; đây không phải mức phí thật.",
            "processing_time": "D0 giả lập – Thời gian xử lý thẻ Ánh Trăng là 4 ngày mô phỏng.",
            "legal_bases": "D0 giả lập – Căn cứ của thẻ Ánh Trăng là Quy tắc D0-CC-2026, một văn bản hoàn toàn hư cấu.",
        },
    },
    {
        "slug": "death_cloud",
        "procedure_id": "synthetic_death_cloud",
        "source_id": "src_synthetic_death_cloud",
        "code": "D0-DEATH-003",
        "title": "Đăng ký khai tử Mây Trắng",
        "aliases": ["khai tử mây trắng", "làm giấy khai tử mây trắng"],
        "facts": {
            "applicant_scope": "D0 giả lập – Đăng ký khai tử Mây Trắng dành cho thân nhân hoặc người đại diện tại Huyện Gió, Thành phố Demo.",
            "receiving_authority": "D0 giả lập – Hồ sơ khai tử Mây Trắng được tiếp nhận tại Bộ phận Một cửa Xã Cầu Mây.",
            "submission_methods": "D0 giả lập – Có thể khai báo trước trên Cổng Dịch vụ Demo và nộp bản mô phỏng tại Xã Cầu Mây.",
            "required_documents": "D0 giả lập – Hồ sơ khai tử Mây Trắng gồm Phiếu D0-KT03, giấy báo tử mô phỏng và thẻ Mây của người khai.",
            "steps": "D0 giả lập – Các bước thực hiện quy trình khai tử Mây Trắng gồm khai báo, nộp hồ sơ giả, kiểm tra D0 và nhận trích lục thử nghiệm.",
            "fees": "D0 giả lập – Lệ phí khai tử Mây Trắng là 0 đơn vị thử nghiệm; đây không phải quy định thật.",
            "processing_time": "D0 giả lập – Thời gian xử lý khai tử Mây Trắng là 3 ngày mô phỏng.",
            "legal_bases": "D0 giả lập – Căn cứ của khai tử Mây Trắng là Quy tắc D0-KT-2026, một văn bản hoàn toàn hư cấu.",
        },
    },
]

QUESTION_TEMPLATES = [
    ("applicant_scope", "Ai được nộp hồ sơ cho {title}?"),
    ("receiving_authority", "Tôi nộp hồ sơ {title} ở đâu?"),
    ("submission_methods", "{title} có thể nộp bằng cách nào?"),
    ("required_documents", "Cần chuẩn bị giấy tờ gì để {title}?"),
    ("steps", "Các bước thực hiện {title} là gì?"),
    ("fees", "Lệ phí của {title} là bao nhiêu?"),
    ("processing_time", "{title} được xử lý trong bao lâu?"),
    ("legal_bases", "{title} dựa trên căn cứ giả lập nào?"),
    ("required_documents", "Ho so {alias} can nhung giay to gi?"),
    ("fees", "Cho tôi biết phí thử nghiệm khi {alias}."),
]


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def json_line(value: dict) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json_line(row) for row in rows) + "\n", encoding="utf-8", newline="\n"
    )


def build() -> None:
    sources: list[dict] = []
    procedures: list[dict] = []
    fragments: list[dict] = []
    questions: list[dict] = []
    fragment_lookup: dict[tuple[str, str], dict] = {}

    for item in PROCEDURES:
        raw_relative = f"data/demo_synthetic/raw/{item['slug']}/snapshot.txt"
        raw_path = ROOT / raw_relative
        raw_text = "\n".join(item["facts"].values()) + "\n"
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_text(raw_text, encoding="utf-8", newline="\n")
        sources.append(
            {
                "source_id": item["source_id"],
                "source_url": f"https://fixture.invalid/d0/{item['slug']}",
                "source_domain": "fixture.invalid",
                "title": f"[D0 GIẢ LẬP] {item['title']}",
                "issuing_authority": "SYNTHETIC_TEST_ONLY",
                "jurisdiction": "DEMO_CITY",
                "procedure_code": item["code"],
                "retrieved_at": "2026-09-09T00:00:00Z",
                "effective_from": None,
                "effective_to": None,
                "status": "UNKNOWN",
                "content_sha256": sha256(raw_text.encode("utf-8")),
                "raw_path": raw_relative,
                "parser_version": "synthetic-generator-v1",
                "review_status": "APPROVED",
                "usage": "D0_SYSTEM_SMOKE",
            }
        )
        field_evidence: dict[str, list[list[str]]] = {}
        for key, text in item["facts"].items():
            fragment_id = f"frag_{item['slug']}_{key}"
            fragment = {
                "fragment_id": fragment_id,
                "procedure_id": item["procedure_id"],
                "section_type": SECTION_TYPES[key],
                "text": text,
                "source_id": item["source_id"],
                "ordinal": 1,
                "content_sha256": sha256(text.encode("utf-8")),
            }
            fragments.append(fragment)
            fragment_lookup[(item["procedure_id"], key)] = fragment
            field_evidence[key] = [[fragment_id]]
        procedures.append(
            {
                "procedure_id": item["procedure_id"],
                "title": item["title"],
                "aliases": item["aliases"],
                "jurisdiction": "DEMO_CITY",
                **{key: [value] for key, value in item["facts"].items()},
                "source_ids": [item["source_id"]],
                "version": VERSION,
                "field_evidence": field_evidence,
            }
        )

    number = 1
    for item in PROCEDURES:
        for offset, (key, template) in enumerate(QUESTION_TEMPLATES):
            fragment = fragment_lookup[(item["procedure_id"], key)]
            questions.append(
                {
                    "question_id": f"q_d0_{number:03d}",
                    "question": template.format(
                        title=item["title"], alias=item["aliases"][0]
                    ),
                    "procedure_id": item["procedure_id"],
                    "facts": {},
                    "expected_status": "ANSWER",
                    "expected_points": [item["facts"][key]],
                    "forbidden_points": [
                        "Không được trình bày dữ liệu D0 như hướng dẫn hành chính thật."
                    ],
                    "gold_source_ids": [item["source_id"]],
                    "gold_fragment_ids": [fragment["fragment_id"]],
                    "contains_pii": False,
                    "split": "DEV" if offset < 7 else "TEST",
                    "author": "synthetic-dataset-generator",
                    "reviewer": "synthetic-fixture-checker",
                    "filters": {"procedure_id": item["procedure_id"]},
                }
            )
            number += 1

    questions.extend(
        [
            {
                "question_id": "q_d0_031",
                "question": "Lệ phí thủ tục là bao nhiêu?",
                "procedure_id": None,
                "facts": {},
                "expected_status": "NEED_CLARIFICATION",
                "expected_points": ["Cần xác định thủ tục giả lập cụ thể."],
                "forbidden_points": ["Không được tự chọn một thủ tục."],
                "gold_source_ids": [],
                "gold_fragment_ids": [],
                "contains_pii": False,
                "split": "DEV",
                "author": "synthetic-dataset-generator",
                "reviewer": "synthetic-fixture-checker",
                "filters": {},
            },
            {
                "question_id": "q_d0_032",
                "question": "Tôi cần chuẩn bị hồ sơ giấy tờ gì?",
                "procedure_id": None,
                "facts": {},
                "expected_status": "NEED_CLARIFICATION",
                "expected_points": ["Cần xác định thủ tục giả lập cụ thể."],
                "forbidden_points": ["Không được trộn hồ sơ của nhiều thủ tục."],
                "gold_source_ids": [],
                "gold_fragment_ids": [],
                "contains_pii": False,
                "split": "DEV",
                "author": "synthetic-dataset-generator",
                "reviewer": "synthetic-fixture-checker",
                "filters": {},
            },
            {
                "question_id": "q_d0_033",
                "question": "zeta quark nebula alpha",
                "procedure_id": None,
                "facts": {},
                "expected_status": "INSUFFICIENT_DATA",
                "expected_points": [],
                "forbidden_points": ["Không được bịa thủ tục không có trong corpus."],
                "gold_source_ids": [],
                "gold_fragment_ids": [],
                "contains_pii": False,
                "split": "TEST",
                "author": "synthetic-dataset-generator",
                "reviewer": "synthetic-fixture-checker",
                "filters": {},
            },
        ]
    )

    write_jsonl(DATASET / "source_manifest.jsonl", sources)
    write_jsonl(DATASET / "normalized/procedures.jsonl", procedures)
    write_jsonl(DATASET / "normalized/fragments.jsonl", fragments)
    write_jsonl(DATASET / "gold/questions.jsonl", questions)

    fee_fragment = fragment_lookup[("synthetic_birth_star", "fees")]
    request_id = UUID("00000000-0000-4000-8000-000000000101")
    bundle_id = UUID("10000000-0000-4000-8000-000000000101")
    common = {
        "request_id": str(request_id),
        "evidence_bundle_id": str(bundle_id),
        "corpus_version": VERSION,
        "data_classification": "D0_SYSTEM_SMOKE",
    }
    projected = {
        "fragment_id": fee_fragment["fragment_id"],
        "source_id": "src_synthetic_birth_star",
        "procedure_id": "synthetic_birth_star",
        "section_type": "FEES",
        "title": "[D0 GIẢ LẬP] Đăng ký khai sinh Sao Mai",
        "text": fee_fragment["text"],
        "jurisdiction": "DEMO_CITY",
        "effective_from": None,
        "effective_to": None,
        "validity_status": "UNKNOWN",
    }
    bundle = {
        **common,
        "query": "Lệ phí của Đăng ký khai sinh Sao Mai là bao nhiêu?",
        "evidence": [
            {
                **projected,
                "url": "https://fixture.invalid/d0/birth_star",
                "score": 1.0,
                "metadata": {"synthetic": True, "procedure_version": VERSION},
            }
        ],
        "as_of": None,
    }
    request = {
        **common,
        "query": bundle["query"],
        "evidence": [projected],
        "as_of": None,
        "max_output_tokens": 500,
    }
    answer = {
        **common,
        "prompt_version": "g2-grounded-v2",
        "answer": f"BẢN MÔ PHỎNG D0 - KHÔNG PHẢI HƯỚNG DẪN: {fee_fragment['text']}",
        "status": "ANSWER",
        "cited_fragment_ids": [fee_fragment["fragment_id"]],
        "missing_information": [],
        "provider": "template",
        "model": "template-grounded-v2",
        "usage": {"input_tokens": 0, "output_tokens": 0},
        "latency_ms": 0,
    }
    fixtures = DATASET / "fixtures"
    fixtures.mkdir(parents=True, exist_ok=True)
    for name, value in (
        ("evidence_bundle.json", bundle),
        ("grounding_request.json", request),
        ("grounded_answer.json", answer),
    ):
        (fixtures / name).write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )

    print(
        "Built data/demo_synthetic: 3 sources, 3 procedures, 24 fragments, 33 questions"
    )


if __name__ == "__main__":
    build()
