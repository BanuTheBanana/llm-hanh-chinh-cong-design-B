# Test report — 2026-09-09

## Đã chạy

- Backend: `pytest tests/test_g3.py tests/test_rag_unit.py tests/test_unit.py tests/test_config.py -q`: **109 passed**.
- Trong đó G3: **29 passed** (fixture hư cấu, không dùng workbook).
- AI Service: `uv sync --frozen --extra test --offline`, `uv run --frozen --extra test pytest`: **42 passed**, 2 deprecation warnings của thư viện.
- Ruff trên module/test G3: PASS; backend lockfile check: PASS.
- Repository hygiene: PASS (198 file ở thời điểm kiểm); git check-ignore chặn dataset/, company_private/ và workbook nằm nơi khác.
- Schema G3 trong code giữ nguyên file schema đính kèm.
- Offline retrieval fixture: hai thủ tục; DEV 2 câu, TEST 2 câu; routing accuracy 1.0, Recall@5 1.0 ở cả hai split. Chỉ là smoke test; không phải kết quả công ty hay nghiệm thu 95%.

## Chưa đạt / bị chặn

- Đã gọi full Backend suite: các fixture DB lỗi setup; lượt chạy không có summary đầy đủ. Test tích hợp chạy riêng xác nhận lỗi `Set TEST_DATABASE_URL to a dedicated PostgreSQL database`. Môi trường không có PostgreSQL/Docker. Không tuyên bố full suite xanh.
- Web: bước npm ci bị môi trường chặn trước khi hoàn tất; chưa chạy Web tests/build/E2E.
- Chưa có DB ingest/idempotency/pin/rollback D2. Lệnh ingest cố ý chặn theo REVIEW_REGISTER.
- Chưa chạy 42-row accounting, raw hash verification hoặc PII scan trên workbook thật.
- Chưa có company normalized/gold đã duyệt; không có retrieval quality report thật.
- Không chạy Qwen/local provider, không đánh giá generation, không mở hosted API.

## Bảo mật và phạm vi

Không mở/parse Raw Excel, không gửi raw hoặc derived company content vào API,
không commit/push mã hoặc dữ liệu. Các test PII dùng chuỗi giả và kiểm lỗi không echo input.
PII regex không bảo đảm nhận biết mọi PII hay biến thể cố tình làm rối. Reviewer vẫn
phải kiểm nghĩa dữ liệu, quyền hiển thị public_url và semantic support của evidence.

Branch local `g3/rag-minh` được tạo từ ZIP không có Git history. Tag baseline và remote
branch chưa thể xác minh. Gói bàn giao chỉ chứa file mới/thay đổi, không phải repo đầy đủ.
