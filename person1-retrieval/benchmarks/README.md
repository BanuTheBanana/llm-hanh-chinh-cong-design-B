# Benchmark contract và quy trình bàn giao

`synthetic_smoke.json`: bộ dữ liệu TỰ TẠO từ fixture demo, không lấy từ TEST_V2.
Nhóm cần cung cấp corpus đã duyệt và DEV gold trước khi đo chất lượng/tune thật.

Một case JSON:

```json
{
  "case_id": "dev-unique-id",
  "split": "dev",
  "query": "câu hỏi do người gán nhãn cung cấp",
  "status": "resolved",
  "procedure_id": "ID-trong-corpus",
  "section_types": ["fee", "required_documents"],
  "filters": {},
  "top_k": 5
}
```

- `status`: resolved / ambiguous / low_confidence. Khi không resolved: procedure_id=null.
- `candidate_ids`: danh sách ID kỳ vọng khi ambiguous; dùng để đo candidate recall.
- `state`: tùy chọn, snapshot state trước câu hỏi để kiểm tra hội thoại.
- `section_types`: nhãn trường thông tin cần tìm. Đếm đúng field chỉ khi đúng cả procedure ID.
- `split`: dev hoặc test. Tuning chỉ chấp nhận toàn bộ input là DEV.
- Chia theo nhóm tình huống/paraphrase để tránh cùng một câu đổi vài chữ ở cả hai split.
- Có direct name/code, paraphrase không exact alias, colloquial intent, nhiều field, ngoài corpus,
  ambiguity, follow-up, correction, topic switch, jurisdiction/date/supersession và thiếu field.
- Chốt snapshot + segmenter config + model hash + prefix trước so sánh.
- So lexical, dense, hybrid trên cùng corpus/case/filter/top_k; xây index một lần mỗi config.
- Chọn threshold trên DEV theo yêu cầu precision/coverage mà nhóm phê duyệt; evaluator mặc định
  xếp grid bằng procedure+status accuracy, sau đó resolved precision. Không mặc định đó là mục tiêu production.
- TEST do chủ sở hữu nhãn kín chạy, chỉ chia sẻ chỉ số tổng hợp cho Person 1.
- Không có target accuracy/latency được nhóm chốt trong handoff: để pending, không tự gán mức đạt.

Báo cáo gồm procedure+status accuracy, status accuracy, resolved precision/coverage,
field precision/recall, tỷ lệ đủ mọi field, recall ứng viên ambiguity và p50/p95 latency.
`cases` trong report chỉ chứa ID, outcome và scores; không chứa raw query hay source text.
Các metric này chưa thay thế đánh giá semantic groundedness/citation/generation của Person 3.
