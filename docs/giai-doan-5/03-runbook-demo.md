# Runbook Docker và demo G5

## 1. Khởi động

Yêu cầu: Docker Desktop có GPU, corpus demo10 đã duyệt và hai file GGUF nằm ngoài Git.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\demo-g5.ps1 `
  -Action Start `
  -DatasetPath 'D:\duong-dan-rieng\company-demo10' `
  -GenerationModelPath 'D:\duong-dan-rieng\Qwen3-1.7B-Q8_0.gguf' `
  -EmbeddingModelPath 'D:\duong-dan-rieng\Qwen3-Embedding-0.6B-Q8_0.gguf' `
  -GenerationModelSha256 '061b54daade076b5d3362dac252678d17da8c68f07560be70818cace6590cb1a' `
  -EmbeddingModelSha256 '06507c7b42688469c4e7298b0a1e16deff06caf291cf0a5b278c308249c3e439' `
  -ReviewToken '<token-local-it-nhat-12-ky-tu>'
```

- Web: `http://localhost:3005`
- Backend: `http://localhost:8005`
- Source MCP: `http://localhost:8096/mcp`

Script kiểm tra loại đường dẫn, đuôi `.gguf`, SHA-256 khi được cung cấp và bắt buộc nhận
token local ít nhất 12 ký tự. Không commit token hoặc truyền nó qua giao diện người dùng.

## 2. Kịch bản demo ngắn

1. Đăng nhập, tạo conversation và hỏi hồ sơ của một thủ tục thuộc demo10.
2. Hỏi tiếp về thời gian, phí hoặc nơi nộp mà không lặp lại tên thủ tục.
3. Chỉ ra checklist, citation và phiên bản tri thức dưới câu trả lời.
4. Với phần quản trị, dùng `scripts/g5-source-update.py` để stage một bản kiểm thử, duyệt,
   publish, hỏi lại trên Web, sau đó rollback. Không dùng PII hoặc nội dung chưa được phép.

Smoke tự động cho vòng đời MCP:

```powershell
$env:G5_SOURCE_REVIEW_TOKEN = '<cùng-token-khi-start>'
uv run --project backend python scripts/smoke-g5.py `
  --dev 'D:\duong-dan-rieng\g4_eval\scenario_dev.jsonl' `
  --output evaluation/reports/g5/live-smoke-local.json
```

## 3. Kiểm tra và dừng

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\demo-g5.ps1 `
  -Action Status `
  -DatasetPath 'D:\duong-dan-rieng\company-demo10' `
  -GenerationModelPath 'D:\duong-dan-rieng\Qwen3-1.7B-Q8_0.gguf' `
  -EmbeddingModelPath 'D:\duong-dan-rieng\Qwen3-Embedding-0.6B-Q8_0.gguf' `
  -ReviewToken '<cùng-token-khi-start>'

powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\demo-g5.ps1 `
  -Action Stop `
  -DatasetPath 'D:\duong-dan-rieng\company-demo10' `
  -GenerationModelPath 'D:\duong-dan-rieng\Qwen3-1.7B-Q8_0.gguf' `
  -EmbeddingModelPath 'D:\duong-dan-rieng\Qwen3-Embedding-0.6B-Q8_0.gguf' `
  -ReviewToken '<cùng-token-khi-start>'
```

`Stop` giữ volume PostgreSQL và registry MCP. Chỉ xóa volume khi đã xác định rõ dữ liệu
có thể bỏ; runbook này không tự xóa dữ liệu.
