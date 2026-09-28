# Scripts

Chứa smoke test và script phát triển có thể chạy lặp lại. Không lưu secret, PII
hoặc dữ liệu công ty trong thư mục này.

## Smoke test hiện có

Khi `ai-service` đang chạy ở port mặc định:

```powershell
pwsh -File scripts/smoke-ai.ps1
```

Windows PowerShell 5:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/smoke-ai.ps1
```

Port tùy chỉnh:

```powershell
pwsh -File scripts/smoke-ai.ps1 -BaseUrl http://localhost:18001
```

Script kiểm tra `/health`, gọi `/internal/v1/generate` bằng dữ liệu giả
`D0_SYSTEM_SMOKE`, sau đó validate các trường bắt buộc của contract G1. Script trả
exit code khác `0` nếu có lỗi nên có thể đưa vào CI sau này.

## Smoke test API end-to-end

Khi PostgreSQL, Mock AI Service và Core Backend đều đang chạy:

```powershell
python scripts/smoke-e2e.py
```

Script dùng hai danh tính giả ngẫu nhiên và kiểm tra:

- health;
- login/session;
- tạo conversation;
- Backend gọi Mock AI;
- idempotent retry;
- lưu và tải lại history;
- user isolation;
- logout.

Script chỉ dùng `D0_SYSTEM_SMOKE`, không đọc dataset hoặc thông tin công ty.

CI còn build và khởi động toàn bộ Web → Backend → Mock AI → PostgreSQL
bằng Docker Compose trước khi chạy script này.

## Kiểm tra repository

```powershell
python scripts/check-repo-hygiene.py
```

Gate này chặn file `.env` cục bộ, private-key file và một số định dạng
token phổ biến bị commit nhầm. Đây là lớp bảo vệ tối thiểu; thành viên vẫn
không được đưa secret, PII hoặc dữ liệu công ty vào Git.

## Đánh giá corpus G3 nội bộ

Chỉ chạy trên máy nội bộ sau khi đã dựng stack local và cấu hình đường dẫn tới
release riêng tư:

```powershell
python scripts/evaluate-g3-private.py
```

Script từ chối endpoint không phải localhost, kiểm tra fingerprint corpus và
TEST lock trước khi chạy, rồi chỉ in số liệu tổng hợp. Nội dung câu hỏi, đáp án,
ID và evidence của dữ liệu công ty không được ghi ra terminal hoặc Git.

## Release gate G4

`evaluate-g4-release.py` hỗ trợ TEST_V2 và TEST_V3 đã khóa. TEST_V3 phải nằm ngoài
Git, qua validator dữ liệu và được leader duyệt trước. Lệnh yêu cầu đúng commit sạch,
hash corpus, cờ xác nhận và đường dẫn output/marker thuộc `evaluation/reports/` đang
được Git-ignore. Mỗi cặp marker/output chỉ được tạo một lần và kết quả chỉ chứa số
tổng hợp.

## Công cụ G5

- `demo-g5.ps1`: start/stop/status stack G5 riêng trên full corpus đã kiểm duyệt; khóa
  version/fingerprint và hash model, đồng thời nạp LoRA grounded-answer 1.7B và adapter
  intent full-38. Backend mặc định dùng `guarded_direct`: direct catalog khi procedure/field
  đã xác minh, hybrid khi còn chưa chắc.
  hash cho generation, embedding, intent model và intent adapter trước khi gọi Compose.
- `smoke-g5-intent-context.py`: gửi một câu D0 hư cấu qua provider intent local và kiểm
  procedure/field/evidence của output có đúng contract.
- `evaluate-g5-hybrid.py`: so Exact/BM25 với dense fallback trên DEV; TEST đã mở chỉ
  được chạy khi gắn cờ regression rõ ràng.
- `smoke-g5.py`: kiểm tra live vòng đời nguồn `PENDING → APPROVED → PUBLISHED → ROLLBACK`
  và câu trả lời Backend dùng đúng snapshot đã duyệt.
- `g5-source-update.py`: CLI quản trị registry MCP; token chỉ đọc từ biến môi trường.
- `load-g5.py`: bài tải nhỏ có giới hạn trên DEV, ghi output vào thư mục bị ignore.
- `evaluate-g5-opened-regression.py`: chấm TEST_V3 đã mở như regression, không gọi là
  holdout hoặc kết quả nghiệm thu độc lập.

Runbook đầy đủ: [docs/giai-doan-5/03-runbook-demo.md](../docs/giai-doan-5/03-runbook-demo.md).
