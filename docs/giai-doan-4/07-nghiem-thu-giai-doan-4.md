# Nghiệm thu Giai đoạn 4

Ngày nghiệm thu: **11/09/2026**. Runtime release candidate:
`00b2c0378e1ba2ea8f69856cf59e3b35049602bf`.

## Kết luận

**G4 chưa đạt gate phát hành.** Hệ thống đã tích hợp đầy đủ phần Hoan, Minh và Tú,
chạy ổn trên DEV, PostgreSQL, Docker Qwen local và Web. Tuy nhiên TEST_V2 độc lập
cho kết quả chuỗi hội thoại nhiều lượt 85%, thấp hơn ngưỡng nội bộ 90%.

Không dùng lỗi TEST_V2 để sửa code và không chạy lại bộ này. Muốn nghiệm thu lần
tiếp theo phải phát triển bằng DEV/fixture hư cấu, sau đó tạo một TEST_V3 mới và
khóa trước khi chấm.

## Thành phần đã hoàn thành

| Hạng mục | Kết quả |
|---|---|
| G4-01 — dữ liệu đánh giá | 80 DEV, 40 TEST_V2, 36 multi-turn; split 8/2 thủ tục; schema, validator, review và hash khóa đầy đủ |
| G4-02 — intent/retrieval | Tách field khỏi tên thủ tục; evidence đúng field; Top-5; placeholder nguồn buộc abstain |
| G4-03 — AnswerPlan/verifier | Backend dựng claim từ nguồn, kiểm citation/contract và fallback trích xuất an toàn |
| G4-04 — conversation context | Lưu thủ tục, field, địa phương và provenance theo conversation trong PostgreSQL |
| G4-05 — tích hợp | Qwen3-1.7B local, Docker riêng, DEV evaluator, smoke API/Chromium và release gate một-lần |

## Kết quả DEV

DEV được dùng để phát triển, không phải số liệu nghiệm thu độc lập.

| Chỉ số | Kết quả |
|---|---:|
| Số scenario | 80 |
| Multi-turn | 16/16 |
| Field accuracy | 100% |
| Routing accuracy | 100% |
| Status accuracy | 100% |
| Recall@5 | 100% |
| MRR@5 | 1,0000 |
| AnswerPlan đúng status/citation/nội dung nguồn | 100% |
| Lỗi claim trọng yếu | 0 |

So với G3 trên cùng 64 câu một lượt, field accuracy tăng từ 48,44% lên 100%,
status accuracy từ 84,38% lên 100% và Recall@5 từ 73,47% lên 100%.

## Kết quả TEST_V2 khóa

TEST_V2 được chạy đúng một lần sau khi code/config đã commit và push. Artifact chi
tiết chỉ lưu local trong thư mục Git-ignore; báo cáo công khai chỉ chứa số tổng hợp.

| Chỉ số | Kết quả | Gate |
|---|---:|---:|
| Số scenario | 40 | — |
| Có căn cứ / abstain an toàn | 36 / 4 | — |
| Field accuracy | 100% | ≥90% |
| Routing accuracy | 90% | ≥90% |
| Status accuracy | 92,5% | ≥90% |
| Recall@5 | 91,67% | ≥90% |
| MRR@5 | 0,9167 | — |
| AnswerPlan đúng | 92,5% | ≥90% |
| Multi-turn chain | **85%** | **≥90% — không đạt** |
| Lỗi claim trọng yếu | 0 | 0 |

Hash TEST_V2:
`bdb91d1c1d661aa321f6cd9f6aab7db7881d3686082e13b85b75c87f0c88387d`.
Hash corpus phục vụ:
`3cf57b03c3c10d580e1dfe298b08728dd910198379c80bc30c338ed6d0e99181`.

## Xác minh kỹ thuật

- Backend: 214 passed, 1 skipped; Ruff sạch.
- AI service: 68 passed; Ruff sạch.
- Data tools: 12 passed; Ruff sạch.
- Web: 12 passed; build và ESLint sạch.
- Migration database dùng một lần: `upgrade head → downgrade 0002 → upgrade head`
  đều qua; Docker đang ở `0003_g4_context`.
- API Docker: 16/16 multi-turn DEV qua; 13 answer và 3 safe abstention.
- Chromium thật: đăng nhập, gửi câu, hiển thị citation và reload history qua.
- Repository hygiene: không phát hiện secret hoặc dữ liệu công ty trong candidate.

## Việc tiếp theo để đạt G4.1

1. Chỉ dùng DEV và fixture hư cấu để mở rộng robustness cho câu nối tiếp; không xem
   ba ca TEST_V2 lỗi và không đổi threshold theo số TEST.
2. Tú/reviewer tạo TEST_V3 mới, tách procedure/paraphrase với DEV và không giao đáp
   án cho người sửa code.
3. Đóng băng commit/config mới, chạy regression/Docker, rồi chấm TEST_V3 đúng một lần.
4. Chỉ gắn tag phát hành G4 khi toàn bộ gate, gồm multi-turn ≥90%, đều đạt.
