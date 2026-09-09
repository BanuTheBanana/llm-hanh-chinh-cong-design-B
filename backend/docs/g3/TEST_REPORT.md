# Test report — 2026-09-09 (verified after integration review)

## Đã chạy

- Toàn bộ Backend với PostgreSQL test riêng: **140 passed, 1 skipped**.
- Riêng G3: **31 passed, 1 skipped** (fixture hư cấu, không dùng workbook).
- Test skip là kiểm tra symlink khi Windows không cấp quyền tạo symlink; production guard
  `Path.resolve().is_relative_to(root)` vẫn hiện diện và test chạy trên môi trường có quyền.
- Ruff check/format toàn Backend: PASS; backend lockfile check: PASS.
- Repository hygiene: PASS (206 file tại thời điểm kiểm); dataset/, company_private/ và
  workbook bị chặn, kể cả trường hợp cố force-add.
- Schema runtime G3 khớp byte-for-byte với machine contract canonical trong `docs/`.
- Offline retrieval fixture: hai thủ tục; DEV 2 câu, TEST 2 câu; routing accuracy 1.0, Recall@5 1.0 ở cả hai split. Chỉ là smoke test; không phải kết quả công ty hay nghiệm thu 95%.

## Chưa đạt / bị chặn

- Web/AI Service không thay đổi trong branch Minh; regression của hai module đó thuộc gate
  tích hợp sau khi Tú bàn giao corpus approved.
- Chưa có DB ingest/idempotency/pin/rollback D2. Lệnh ingest cố ý chặn theo REVIEW_REGISTER.
- Chưa chạy 42-row accounting, raw hash verification hoặc PII scan trên workbook thật.
- Chưa có company normalized/gold đã duyệt; không có retrieval quality report thật.
- Không chạy Qwen/local provider, không đánh giá generation, không mở hosted API.

## Bảo mật và phạm vi

Không mở/parse Raw Excel, không gửi raw hoặc derived company content vào API,
không commit/push mã hoặc dữ liệu. Các test PII dùng chuỗi giả và kiểm lỗi không echo input.
PII regex không bảo đảm nhận biết mọi PII hay biến thể cố tình làm rối. Reviewer vẫn
phải kiểm nghĩa dữ liệu, quyền hiển thị public_url và semantic support của evidence.

Branch đã được đối chiếu trên repository Git thật và nhập checkpoint contract `3721651`.
Không có raw/derived company data hoặc secret trong commit ứng viên.
