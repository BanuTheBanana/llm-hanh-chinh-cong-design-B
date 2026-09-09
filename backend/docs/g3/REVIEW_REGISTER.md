# Review register — Minh, G3

Ngày: 2026-09-09. Chưa có quyết định thay mặt Tú/Hoan/người nghiệp vụ.
Không chứa dữ liệu workbook; mọi mục dưới đây là vấn đề contract/kỹ thuật.

| ID | Trạng thái / owner | Vấn đề và việc cần chốt | Hành vi hiện tại |
|---|---|---|---|
| G3-RV-001 | OPEN — Tú + Minh | `SourceManifest.content_sha256` chưa định nghĩa bytes đầu vào, serialization row, xử lý email/timestamp/null. `raw_cell_sha256` chưa có quy ước chuyển kiểu ô thành bytes. Năm JSONL không chứa preimage để Minh tự xác minh raw hashes. Chốt quy ước và cách xác nhận ở bước local của Tú; cập nhật contract qua change control. | Chỉ xác minh hash UTF-8 của fragment; không tuyên bố raw hash PASS. Chặn ingest, không có cờ bỏ qua. |
| G3-RV-002 | OPEN — Minh + Hoan + Tú | G2 DataClassification chỉ D0/D1, citation bắt URL; G3 D2 có `public_url=null`, jurisdiction object, review và field_evidence khác G2. Cần thống nhất version projection/citation và provider local allowlist. | Module G3 offline riêng; không đổi classification thành D0/D1, không tạo URL giả, không nối vào Web/AI. |
| G3-RV-003 | RESOLVED — Hoan | Branch upload ban đầu dựa trên `main` cũ và làm mất tài liệu G3 trong diff. | Đã merge checkpoint contract `3721651`, phục hồi tài liệu/schema canonical và review trên repository Git thật. |
| G3-RV-004 | OPEN — Tú + reviewer nghiệp vụ | Chưa nhận đủ năm JSONL approved và gold DEV/TEST đã review. Không đọc raw để làm thay preprocessing/gold. | Fixture hoàn toàn hư cấu. Không có kết quả 42/42 trên workbook thật, không có điểm retrieval công ty. |
| G3-RV-005 | PARTIAL — Tú + Minh | `field_evidence` G3 là danh sách fragment theo field, không ánh xạ từng item như G2. Granularity hỗ trợ claim vẫn cần Tú/reviewer kiểm tra trên output thật. | Validator đã khóa reference/section/business-field và tính nhất quán `missing_fields` cho code/authority/jurisdiction/effective/public URL. Không tự chứng nhận semantic entailment. |
| G3-RV-006 | OPEN — nhóm | Governance, người có quyền approve, chính sách freshness chưa có bằng chứng ký duyệt trong input. | Không tự approve, không dùng UNKNOWN như CURRENT khi hỏi ngày cụ thể. |
| G3-RV-007 | RESOLVED — Hoan | Cần PostgreSQL test riêng để chạy toàn bộ Backend regression. | Đã chạy bằng database test riêng trên Docker: 140 passed, 1 skipped. Việc ingest/idempotency/rollback D2 vẫn bị chặn độc lập bởi RV-001/RV-002/RV-004. |

Các quy tắc bảo thủ cần review: source_uri chỉ company-internal opaque; public_url không query/fragment/credentials; source accounting không trùng raw row; mọi OPEN conflict phải có candidate QUARANTINED và mọi procedure dùng source đang conflict đều bị loại; DEV và TEST tách hoàn toàn procedure; field missing không đồng thời có value/evidence. Schema g3-data-v1 được giữ nguyên byte-for-byte; validator bổ sung gate, không tự sửa producer output.

Sau khi RV-001/RV-002 được chốt mới nối importer vào transactional store, kiểm pin/idempotency/rollback và mở đường D2 local. Không bỏ câu lệnh chặn để demo cho nhanh.
