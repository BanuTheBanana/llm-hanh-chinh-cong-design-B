# AI Service G1/G2 + local provider G3

FastAPI service nội bộ do Hoan phụ trách. G1 chỉ dùng `MockProvider`; không gọi
OpenAI, không host Qwen và không làm RAG.

Nền móng G2 bổ sung API grounded v2 và evaluation offline bằng `template`. G3
thêm `LocalGroundedProvider` cho llama.cpp/Qwen3-1.7B; không có hosted adapter
nào được bật và service không cần API key.

## API

- `GET /health`
- `POST /internal/v1/generate`
- `GET /internal/v2/health`
- `POST /internal/v2/generate`
- OpenAPI khi chạy local: `http://localhost:8001/docs`

Request/response chính thức nằm trong
[contract G1](../docs/contracts-g1.md#internal-ai-api).
Contract v2 nằm trong [contract G2](../docs/contracts-g2.md).

## Chạy local

Yêu cầu Python 3.11 trở lên và `uv`:

```powershell
cd ai-service
uv sync --frozen --extra test
uv run --frozen uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
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
| `GROUNDED_PROVIDER` | `template` | `template` hoặc `local`; G1 vẫn dùng mock |
| `MOCK_MODE` | `success` | `success`, `error` hoặc `timeout` |
| `MOCK_LATENCY_MS` | `10` | Độ trễ trước khi xử lý mock |
| `MOCK_TIMEOUT_SECONDS` | `5` | Thời gian giữ request ở timeout mode |

`timeout` cố ý giữ kết nối rồi trả HTTP 504. Khi kiểm thử tích hợp, đặt
`MOCK_TIMEOUT_SECONDS` lớn hơn timeout của Core Backend để Backend tự kích hoạt
nhánh timeout. Không dùng nội dung prompt để chuyển mode.

Response mock luôn ghi rõ đây chỉ là phản hồi mô phỏng kỹ thuật, không phải tư
vấn hành chính.

## Grounded API v2

V2 nhận một `GroundingContext` đã được Core Backend project từ EvidenceBundle.
Nó không nhận URL, retrieval score, cookie, user ID hoặc history dài. Response chỉ
có thể cite `fragment_id` đã nằm trong request.

Với `GROUNDED_PROVIDER=template`:

- evidence rỗng trả `INSUFFICIENT_DATA` mà không gọi model;
- chỉ nhận `D0_SYSTEM_SMOKE`; request D1 có evidence bị từ chối;
- bỏ qua fragment hết/chưa hiệu lực, không liên quan hoặc chứa marker chỉ dẫn;
- chọn fragment D0 phù hợp bằng lexical baseline, trả citation từ allowlist;
- mọi câu trả lời đều ghi rõ đây là mô phỏng, không phải hướng dẫn hành chính.

Hosted provider chưa được triển khai. Chỉ thêm sau khi mentor/công ty duyệt
provider và dữ liệu `D1_PUBLIC_DEMO`; không dùng key từng xuất hiện trong chat,
commit hoặc log.

Với `GROUNDED_PROVIDER=local`, xem
[runbook Qwen local](../docs/giai-doan-3/04-runbook-qwen-local.md). Provider chỉ
allowlist D2 khi `LOCAL_LLM_ALLOW_D2_COMPANY_DATA=true`, gọi endpoint HTTP local đã
allowlist, ép constrained JSON và kiểm tra lại schema/citation/thinking content.
HTTP client được reuse trong vòng đời ứng dụng và đóng khi shutdown.

## Evaluation offline

Từ repository root:

```powershell
uv run --project ai-service --frozen python -m app.evaluation validate `
  --suite evaluation/fixtures/offline-smoke-v1/manifest.json

uv run --project ai-service --frozen python -m app.evaluation run `
  --suite evaluation/fixtures/offline-smoke-v1/manifest.json `
  --candidate template --split DEV --strict-safety
```

Xem giải thích metric tại [`evaluation/README.md`](../evaluation/README.md).

## Chạy test

```powershell
cd ai-service
uv sync --frozen --extra test
uv run --frozen python -m pytest
uv run --frozen ruff check .
uv run --frozen ruff format --check .
```

Test bao phủ health, contract success, provider error/shape/metadata, timeout,
classification allowlist, validity, prompt-injection marker và validation.
