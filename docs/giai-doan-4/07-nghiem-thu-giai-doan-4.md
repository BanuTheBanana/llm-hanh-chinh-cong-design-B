# Nghiệm thu Giai đoạn 4

Ngày nghiệm thu: **11/09/2026**. Các candidate đã mở release gate:
`00b2c0378e1ba2ea8f69856cf59e3b35049602bf` (TEST_V2) và
`824fd50e923f30c3103f833099e5cb68781c1205` (TEST_V3).

## Kết luận

**G4 chưa đạt gate phát hành.** Hệ thống đã tích hợp đầy đủ phần Hoan, Minh và Tú,
chạy ổn trên DEV, PostgreSQL, Docker Qwen local và Web. TEST_V2 đạt 85% chuỗi
hội thoại. TEST_V3 mới, sau khi sửa contract và khóa nhãn theo nguồn, chỉ đạt 5%; vì
vậy không được tuyên bố G4 hoàn thành.

Không chạy lại hoặc dùng nội dung lỗi của TEST_V2/TEST_V3 để tuning. Lỗi tổng quát
về câu nối tiếp dài đã được bổ sung bằng fixture hư cấu và DEV. Candidate hiện tại
`439e1d7f46f9f689cc6ee754cea163fdbc33d3f3` cần một TEST_V4 mới, được giữ kín và
khóa trước khi chấm đúng một lần.

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

## Kết quả TEST_V3 khóa

Gói Tú gửi ban đầu chưa đúng contract: thiếu metadata schema/review/PII, target
`question` chưa trỏ tới lượt user cuối và một số gold label không khớp corpus. Leader
đã sửa nhãn theo nguồn đã duyệt, kiểm schema/source/hash/leakage rồi khóa bản reviewed
trước khi chấm. TEST_V2 cũ gửi kèm không được sử dụng.

| Chỉ số | Kết quả | Gate |
|---|---:|---:|
| Số scenario | 40 | — |
| Có căn cứ / abstain an toàn | 35 / 5 | — |
| Field accuracy | 75% | ≥90% — không đạt |
| Routing accuracy | 7,5% | ≥90% — không đạt |
| Status accuracy | 22,5% | ≥90% — không đạt |
| Recall@5 | 2,86% | ≥90% — không đạt |
| MRR@5 | 0,0286 | — |
| AnswerPlan đúng | 5% | ≥90% — không đạt |
| Multi-turn chain | 5% | ≥90% — không đạt |
| Lỗi claim trọng yếu | 28 | 0 — không đạt |

Hash TEST_V3 reviewed:
`bab36260dc4a920d6f315b73a0414834d90fedd9ea6c2bf7986a3bc12566d1a1`.
Kết quả và marker một-lần chỉ lưu local trong `evaluation/reports/` bị Git-ignore.

## Xác minh kỹ thuật

- Backend: 219 passed, 1 skipped; Ruff sạch.
- AI service: 68 passed; Ruff sạch.
- Data tools: 14 passed; các file G4 mới qua Ruff.
- Web: 12 passed; build và ESLint sạch.
- Migration database dùng một lần: `upgrade head → downgrade 0002 → upgrade head`
  đều qua; Docker đang ở `0003_g4_context`.
- API Docker: 16/16 multi-turn DEV qua; 13 answer và 3 safe abstention.
- Chromium thật: đăng nhập, gửi câu, hiển thị citation và reload history qua.
- Repository hygiene: không phát hiện secret hoặc dữ liệu công ty trong candidate.

## Việc tiếp theo để đạt G4.1

1. Giữ TEST_V2/TEST_V3 đã dùng ở trạng thái lưu trữ; không chạy lại và không đổi
   threshold theo kết quả TEST.
2. Tú/reviewer tạo TEST_V4 mới, tách paraphrase/hội thoại với DEV và hai TEST cũ;
   không giao câu hỏi hoặc gold cho người sửa code.
3. Đóng băng commit/config mới, chạy regression/Docker, rồi chấm TEST_V4 đúng một lần.
4. Chỉ gắn tag phát hành G4 khi toàn bộ gate, gồm multi-turn ≥90%, đều đạt.
