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
