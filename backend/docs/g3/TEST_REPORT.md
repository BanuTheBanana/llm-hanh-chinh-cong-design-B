# Test report — 09/09/2026 (G3 technical foundation)

## Báo cáo cập nhật

| Trường | Nội dung |
|---|---|
| Trạng thái | PASS |
| Phạm vi | Backend G1/G2 regression + G3 D2 runtime |
| Dữ liệu test trong Git | Chỉ fixture hư cấu |

## Đã chạy

- Toàn bộ Backend với PostgreSQL test riêng: **143 passed, 1 skipped**.
- Skip là test symlink khi Windows không cấp quyền tạo symlink; path guard vẫn có
  test trên môi trường cho phép.
- Ruff check/format: PASS; migration Alembic thật chạy trong schema test riêng.
- G3 test bao phủ schema/reference/PII, review/conflict, retrieval/abstention,
  read-only runtime projection, immutable corpus hash và loại gold/TEST khỏi
  serving memory.
- Repo hygiene: PASS; 223 file được kiểm, không có workbook/private data/model/secret.

Benchmark D2 aggregate và E2E nằm trong
[biên bản nghiệm thu G3](../../../docs/giai-doan-3/05-bao-cao-tich-hop-va-dieu-kien-nghiem-thu-g3.md).
Không có question, answer, evidence, internal URI hoặc locator thật được ghi vào
report này.

## Giới hạn sau G3

- Foundation dùng private volume read-only + version/hash pin, chưa làm corpus DB
  importer production.
- Chất lượng nghiệp vụ chưa được chuyên gia/cơ quan chuyên môn chứng nhận.
- Dense retrieval/reranker, đủ 38 thủ tục và production operations thuộc giai đoạn sau.
- D2 vẫn bị cấm với hosted provider.
