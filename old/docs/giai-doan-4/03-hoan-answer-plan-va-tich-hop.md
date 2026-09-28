# G4 — Phần Hoan: AnswerPlan, kiểm chứng và tích hợp

> Cập nhật 11/09/2026: tài liệu này ghi kết quả trước khi ghép code Minh. QueryContext,
> field retrieval và conversation context hiện đã được nối vào AnswerPlan; DEV đạt
> toàn bộ gate kỹ thuật. Kết quả nghiệm thu cuối nằm ở `07-nghiem-thu-giai-doan-4.md`.

Ngày thực hiện: 10–11/09/2026. Nhánh: `g4/integration`.

## 1. Đã triển khai

| Đầu việc | Kết quả |
|---|---|
| G4-03 — AnswerPlan | Backend xác định trường cần trả lời và tạo claim từ evidence được truy hồi, đối chiếu `field_evidence` của thủ tục đã duyệt. |
| Kiểm chứng | Giữ kiểm tra contract/binding/citation G3; bổ sung kiểm tra đủ toàn bộ claim, điều kiện và đúng nhóm trường. |
| Trả lời an toàn | Backend dựng câu trả lời từ nguyên văn nguồn; không cho Qwen tự thêm số tiền, thời hạn, địa điểm. |
| Thiếu dữ liệu | Thiếu một fragment điều kiện, thiếu trường, lẫn thủ tục, sai thời điểm hoặc quá dài thì không kết luận đầy đủ. |
| Theo dõi | Lưu `verification` cùng câu trả lời; log chỉ chứa mã lý do và số liệu, không chứa nội dung công ty. Web phân biệt trường hợp phải trích xuất thay câu model. |
| G4-05 — Tích hợp bước đầu | Có bộ chạy DEV cố định, so sánh Qwen, smoke Docker và regression. Nghiệm thu TEST_V2/hội thoại còn chờ Tú và Minh. |

Sửa thêm hai lỗi kỹ thuật: fallback G3 không còn cắt giữa nội dung bằng dấu `…`;
module provider không còn lỗi import vòng khi chạy evaluator độc lập.

## 2. Luồng mới

`Retrieval → AnswerPlan → Qwen → kiểm tra → backend dựng nội dung → Web/lịch sử`.

Nếu plan thiếu thông tin, không gọi Qwen. Nếu plan đủ nhưng model lỗi, timeout,
sai citation hoặc chưa kiểm chứng được lời diễn đạt, backend vẫn có thể trích xuất
đầy đủ từ plan. Không chuyển sang trả lời tự do bằng kiến thức của model.

Giữ nguyên API AI `/internal/v2/generate` và prompt G3 để không làm thay đổi baseline.
Chỉ bổ sung metadata tùy chọn `grounding.verification` ở Backend/Web.
G4 được bật riêng bằng `G4_ANSWER_PLAN_ENABLED=true`; mặc định vẫn tắt.

## 3. Contract bàn giao cho Minh

Hàm `build_answer_plan(bundle, fields=..., field_evidence=...)` nhận:

- `fields`: danh sách trường đã phân tích từ QueryContext. Dùng tên G3 như `fees`,
  `processing_times`, `receiving_authority`, `required_documents`.
- `field_evidence`: mapping từ procedure đã duyệt, **không lấy từ câu hỏi hay output Qwen**.
- `bundle`: evidence hiện tại đã gắn procedure, source, section và hiệu lực.

`AnswerPlan` phiên bản `g4-answer-plan-v1` gồm `requested_fields`, `claims`,
`status`, `missing_fields`, `reason`. Mỗi claim có `field`, `value`, `conditions`,
`evidence_ids`. `value` giữ cả nguyên văn điều kiện; `conditions=null` nghĩa là
chưa tách điều kiện thành cấu trúc, **không có nghĩa nguồn không có điều kiện**.

`VerificationResult` dùng policy `full-claim-exact-v1`, có `candidate_checked`,
`candidate_passed`, `fallback_used`, `reasons`. Trạng thái cuối nằm ở `grounding.status`;
các claim và citation cuối được lấy từ plan, không lấy từ nội dung model tự viết.
Đây là contract triển khai hiện tại, cụ thể hóa contract dự kiến trong file phân công.

Adapter keyword hiện tại chỉ bảo vệ đầu ra. Nó không thay việc G4-02 của Minh,
không sửa retrieval và không giải quyết việc nhớ thủ tục qua câu hỏi tiếp nối.
Adapter loại tên thủ tục đã khớp trước khi nhận diện field, tránh nhầm từ như
“chi phí” trong tên thành ý hỏi lệ phí. Minh có thể truyền `fields` trực tiếp vào
`answer_with_plan(...)` sau khi QueryContext sẵn sàng.

## 4. Giới hạn cần hiểu đúng

Đây là **bộ kiểm tra nguyên văn bảo thủ**, chưa phải mô hình đánh giá ngữ nghĩa.
Một câu diễn đạt lại đúng vẫn có thể bị chuyển sang trích xuất. Không được lấy
`candidate_passed=false` để kết luận model sai pháp lý.

Trên DEV hiện tại, 24/31 plan có đủ evidence. Sáu ca bị chặn vì thiếu evidence
cho trường được yêu cầu, chủ yếu liên quan nơi nộp; một ca chưa xác định được intent.
Trạng thái sau lớp bảo vệ khớp gold 24/31. Vì vậy **chưa bật G4 thay thế G3 mặc định**,
và không tuyên bố chất lượng toàn hệ thống đã tăng hay đã đạt gate G4.

Điều cần ghép tiếp:

- Minh: QueryContext đúng trường, retrieval đủ các fragment điều kiện; conversation context.
- Tú/reviewer: DEV_V2/TEST_V2 và đánh giá đủ ý, giữ điều kiện, đúng phạm vi nghiệp vụ.
- Hoan khi ghép xong: chạy lại gate; chỉ nới kiểm tra paraphrase khi có bằng chứng kiểm chứng được.

## 5. Kiểm thử và chạy lại

Test giả lập mới: `backend/tests/test_answer_plan.py` và
`ai-service/tests/test_benchmark_boundary.py`. Không dùng dữ liệu công ty trong test Git.
Có kiểm tra bỏ điều kiện, sửa số tiền, thêm địa điểm, giả citation, sai request,
timeout, fragment thiếu, nhiều trường, hết hiệu lực, text quá dài và import độc lập.

Smoke riêng: `scripts/smoke-g4-private.py`, đọc fixture DEV trong thư mục ignored.
Smoke gồm bốn câu tự chứa đủ ngữ cảnh, không phải kiểm thử khả năng nhớ hội thoại.
Kiểm tra nội dung bằng plan, nguồn, idempotency, lưu/tải lịch sử, cô lập người dùng,
CORS và Web. `scripts/smoke-g4-browser.mjs` đã qua Chromium thật: đăng nhập,
gửi hai câu DEV, hiển thị nội dung/nguồn và tải lại lịch sử.

Regression cuối: Backend 188 pass/1 skip; AI Service 68 pass; data tools 7 pass;
Web 12 pass, lint/build qua. Các số này là test kỹ thuật, không phải accuracy nghiệp vụ.

Mở G4 riêng, từ thư mục gốc repo:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/demo-g4.ps1 -Action Start
# Sau khi tạo xong, có thể Start/Stop nhóm hanh-chinh-g4 trong Docker Desktop.
# Web: http://localhost:3004
powershell -ExecutionPolicy Bypass -File scripts/demo-g4.ps1 -Action Stop
```

Có thể truyền `-DatasetPath`, `-ModelPath`, `-ModelName` nếu máy khác vị trí lưu.
Model hỗ trợ trong script: Qwen3-1.7B và Qwen3-4B-Instruct-2507.
Script dùng project/port/volume G4 riêng, không xóa hay thay nhóm G1/G2/G3.
Model và dataset được mount read-only; không đưa lên Git.

Kết quả chọn model được ghi riêng trong [báo cáo so sánh Qwen](04-ket-qua-so-sanh-qwen.md).
