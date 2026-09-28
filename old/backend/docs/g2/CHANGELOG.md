# Changelog tích hợp G2

## 09/09/2026 – D0 technical vertical slice

Baseline: `main` / tag `g1-v1.0.0`.

Nguồn ghép:

- Hoan: `g2/ai-eval-hoan`;
- Tú: `data/frontend-tu`;
- Minh: `Minh-RAG_test`;
- tích hợp và sửa lỗi: `g2/integration`.

### Contract và Backend/RAG

- Đồng bộ Core Backend với `POST /internal/v2/generate`; bỏ request wrapper và
  history khỏi grounded projection.
- Bind/kiểm tra `request_id`, `evidence_bundle_id`, corpus version, data
  classification, prompt version và citation allowlist trước khi lưu.
- Giới hạn query/evidence/output theo contract, kiểm tra invariant của
  `ANSWER`, `NEED_CLARIFICATION` và `INSUFFICIENT_DATA`.
- Không trộn nhiều procedure trong một bundle; phát hiện ambiguity trước khi
  cắt `top_k`.
- Thêm readiness `/health/rag`, config guard cấm fixture ở production và lỗi
  upstream an toàn.
- Sửa Alembic path để chạy độc lập current working directory.

### Data

- Chuyển cây dữ liệu về canonical path `data/demo_public`.
- Sửa raw hash theo byte snapshot, nguồn/fragment reference và provenance tới
  file PDF nằm trong archive.
- Sửa submission method, fee, exemption và legal bases theo snapshot; không tự
  điền documents/steps khi nguồn không có.
- Thêm data validator hai mode: technical `preflight` và human/business
  `publish`.
- Giữ source/gold ở trạng thái pending; không tự gắn APPROVED.

### AI, Web, Compose và CI

- Giữ template provider offline chỉ nhận D0; D1/hosted vẫn khóa bằng policy.
- Thêm Compose overlay ingest fixture và bật grounded flow mà không phá G1.
- Web hiển thị status, cảnh báo D0, missing information và nguồn HTTPS đã hydrate
  từ Backend.
- Thêm API smoke và Chromium E2E cho answer + source + reload history.
- CI chạy data preflight, G1 regression rồi G2 Compose/API/browser smoke.

### Trạng thái

`G2-I01` bằng D0 đã pass kỹ thuật. `G2-D04`, `G2-R03`, `G2-A03` và `G2-I02`
chưa hoàn tất vì D1 thiếu review/phạm vi và hosted provider chưa được phê duyệt.
Chi tiết lệnh/kết quả ở [TEST_REPORT.md](TEST_REPORT.md).
