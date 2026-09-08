# AI Service G1

FastAPI service nội bộ do Hoan phụ trách. G1 chỉ dùng `MockProvider`; không gọi
OpenAI, không host Qwen và không làm RAG.

## API

- `GET /health`
- `POST /internal/v1/generate`
- OpenAPI khi chạy local: `http://localhost:8001/docs`

Request/response chính thức nằm trong
[contract G1](../docs/contracts-g1.md#internal-ai-api).

## Chạy local

Yêu cầu Python 3.11 trở lên:

```powershell
cd ai-service
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[test]"
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

Hoặc chạy container từ thư mục gốc repository:

```powershell
docker build -t llm-hcc-ai-service ./ai-service
docker run --rm -p 8001:8001 -e LLM_PROVIDER=mock llm-hcc-ai-service
```

## Cấu hình MockProvider

| Biến | Mặc định | Ý nghĩa |
|---|---:|---|
| `APP_ENV` | `development` | Tên môi trường |
| `LOG_LEVEL` | `INFO` | Mức log |
| `LLM_PROVIDER` | `mock` | G1 chỉ hỗ trợ `mock` |
| `MOCK_MODE` | `success` | `success`, `error` hoặc `timeout` |
| `MOCK_LATENCY_MS` | `10` | Độ trễ trước khi xử lý mock |
| `MOCK_TIMEOUT_SECONDS` | `5` | Thời gian giữ request ở timeout mode |

`timeout` cố ý giữ kết nối rồi trả HTTP 504. Khi kiểm thử tích hợp, đặt
`MOCK_TIMEOUT_SECONDS` lớn hơn timeout của Core Backend để Backend tự kích hoạt
nhánh timeout. Không dùng nội dung prompt để chuyển mode.

Response mock luôn ghi rõ đây chỉ là phản hồi mô phỏng kỹ thuật, không phải tư
vấn hành chính.

## Chạy test

```powershell
cd ai-service
python -m pip install -e ".[test]"
python -m pytest
```

Test bao phủ health, contract success, provider error, timeout và validation.
