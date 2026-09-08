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

Smoke test end-to-end Web → Backend → AI → PostgreSQL sẽ được thêm khi contract
response của login/conversation và code Backend đã sẵn sàng.
