> **G4:** đọc [hướng dẫn backend](docs/g4/README.md) trước khi chạy. Migration và
> fingerprint phục vụ đã thay đổi; kết quả nghiệm thu nằm trong
> `docs/giai-doan-4/07-nghiem-thu-giai-doan-4.md` ở thư mục gốc repository.

> **G2 Retrieval/RAG đã được tích hợp và sửa contract trên `g2/integration`.** Bắt đầu ở
> [docs/g2/README.md](docs/g2/README.md) để migrate lên `0002_g2_rag`, ingest,
> chạy evaluation và ghép grounded AI. G1 mặc định vẫn bật; RAG là opt-in.
> Các số liệu/trạng thái G1 bên dưới là baseline cũ, xem báo cáo G2 riêng.

# Core Backend G1

FastAPI + PostgreSQL + SQLAlchemy async + Alembic. Backend là source of truth cho
demo user, session, conversation và message; Web không gửi `user_id`, còn Backend
chỉ gọi AI Service qua internal API.

Contract duy nhất của monorepo: [`../docs/contracts-g1.md`](../docs/contracts-g1.md).
G1 chỉ dùng dữ liệu giả `D0_SYSTEM_SMOKE` và Mock AI, không phải hệ thống
xác thực hay tư vấn hành chính production.

## Chạy cả hệ thống – cách khuyến nghị

Từ repository root:

```powershell
Copy-Item .env.example .env
docker compose --profile full up --build --detach --wait
python scripts/smoke-e2e.py
```

Compose chờ PostgreSQL và AI Service healthy, chạy `alembic upgrade head`, sau
đó mới khởi động Backend. Không cần tự migrate thêm trong luồng này.

## Chạy riêng Backend khi phát triển

Yêu cầu Python 3.12, `uv`, PostgreSQL và AI Service:

```powershell
cd backend
uv sync --frozen
```

Backend đọc `backend/.env` theo UTF-8/UTF-8 BOM. Environment của process có
ưu tiên cao hơn file. Có hai cách cấu hình database:

```dotenv
# Cách 1: DSN đầy đủ; có giá trị thì ưu tiên hơn DB_*
DATABASE_URL=postgresql+asyncpg://app_user:change-me-local-only@127.0.0.1:5432/hanh_chinh_mvp

# Cách 2: hữu ích khi password có ký tự @, :, /, # hoặc %
# DATABASE_URL=
# DB_HOST=127.0.0.1
# DB_PORT=5432
# DB_NAME=hanh_chinh_mvp
# DB_USER=app_user
# DB_PASSWORD='change-me-local-only'

AI_SERVICE_URL=http://127.0.0.1:8001
AI_REQUEST_TIMEOUT_SECONDS=3
WEB_ORIGIN=http://localhost:3000
SESSION_COOKIE_SECURE=false
SESSION_TTL_SECONDS=86400
```

Không commit `backend/.env`. Có thể dựng riêng hai dependency từ repository root:

```powershell
docker compose up --detach --wait postgres ai-service
```

Kiểm tra cấu hình mà không in password/DSN:

```powershell
uv run --frozen python -m app.doctor --config-only
uv run --frozen python -m app.doctor
```

Lệnh thứ hai thực sự kết nối database và báo mã chẩn đoán như
`DB_NETWORK_ERROR`, `DB_AUTH_FAILED`, `DB_NOT_FOUND` hoặc `DB_TIMEOUT` mà không
in exception có thể chứa secret.

Migrate và chạy API:

```powershell
uv run --frozen alembic upgrade head
uv run --frozen uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log --log-config logging.json
```

- Health: `http://localhost:8000/health`
- Swagger: `http://localhost:8000/docs`
- OpenAPI: `http://localhost:8000/openapi.json`

## Environment Backend

| Biến | Mặc định local | Ý nghĩa |
|---|---|---|
| `DATABASE_URL` | rỗng | DSN `postgresql+asyncpg`; nếu có sẽ ưu tiên hơn `DB_*` |
| `DB_HOST` | `127.0.0.1` | Host PostgreSQL khi không dùng DSN |
| `DB_PORT` | `15432` | Port PostgreSQL khi không dùng DSN |
| `DB_NAME` | `g1` | Database name |
| `DB_USER` | `postgres` | Database user |
| `DB_PASSWORD` | `postgres` | Password local demo; không dùng cho production |
| `AI_SERVICE_URL` | `http://localhost:8001` | Origin; Backend dùng v1 cho G1 hoặc `/internal/v2/generate` khi RAG bật |
| `RAG_ENABLED` | `false` | Bật retrieval + grounded flow G2 |
| `RAG_CORPUS_VERSION` | rỗng | Version corpus immutable đã ingest; bắt buộc khi bật RAG |
| `RAG_TOP_K` | `5` | Số fragment, giới hạn 1–8 |
| `RAG_ALLOW_FIXTURES` | `false` | Chỉ opt-in D0; cấu hình production bị từ chối |
| `G3_D2_ENABLED` | `false` | Bật corpus D2 private read-only; yêu cầu RAG và các pin bên dưới |
| `G3_PRIVATE_DATASET_PATH` | rỗng | Thư mục 5 JSONL private, không nằm trong Git |
| `G3_EXPECTED_ROWS` | `10` | Số source row của release demo đã khóa |
| `G3_CORPUS_SHA256` | rỗng | Fingerprint bắt buộc; cùng version khác hash bị từ chối |
| `G3_ALLOW_PRODUCTION` | `false` | Fail-closed, release demo không chạy production mặc định |
| `GROUNDED_MAX_OUTPUT_TOKENS` | `500` | Ngân sách output AI v2, giới hạn 32–2048 |
| `AI_REQUEST_TIMEOUT_SECONDS` | `10` | Deadline tổng khi gọi AI |
| `SESSION_COOKIE_NAME` | `g1_session` | Tên opaque cookie |
| `SESSION_COOKIE_SECURE` | `false` | Phải `true` khi chạy HTTPS |
| `SESSION_TTL_SECONDS` | `86400` | Tuổi thọ session |
| `WEB_ORIGIN` | `http://localhost:3000` | Browser origin được phép |

Trong Docker Compose chung, root config ghi đè database host thành `postgres`
và AI host thành `ai-service`; không dùng `localhost` để gọi container khác.

## Hành vi quan trọng

1. Session token được tạo ngẫu nhiên; database chỉ lưu SHA-256 hash.
2. Mọi conversation/message query đều kiểm tra ownership.
3. PostgreSQL advisory lock bảo đảm mỗi conversation chỉ có một generation
   đang chạy, kể cả khi có nhiều Backend worker.
4. User message `pending` được commit trước khi gọi AI; không giữ database
   transaction mở trong lúc chờ network.
5. AI thành công thì lưu user + assistant `completed`; lỗi/timeout thì giữ
   user message `failed`, không tạo assistant giả.
6. `client_message_id` là idempotency key trong một conversation. Retry cùng
   key/nội dung không tạo thêm user message.
7. Luồng G1 gửi tối đa 100 message gần nhất; luồng grounded G2 chỉ gửi query và
   evidence projection tối thiểu, không gửi chat history sang AI Service.
8. Log chỉ ghi `request_id`, route template, method, status, latency và loại lỗi;
   không ghi body, cookie, token, DSN hay exception text.

Login G1 chỉ nhận `display_name`, do đó không xác minh danh tính người thật.
Nó chỉ phù hợp smoke/demo bằng D0, tuyệt đối không nhập PII thật.

## Test

Unit/config test không cần database:

```powershell
uv run --frozen python -m pytest tests/test_unit.py tests/test_config.py -q
uv run --frozen ruff check .
uv run --frozen ruff format --check .
```

Toàn bộ suite cần PostgreSQL test riêng:

```powershell
$env:TEST_DATABASE_URL='postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/g1_test'
uv run --frozen python -m pytest
```

Fixture tạo schema ngẫu nhiên, chạy migration thật và xóa schema test khi xong;
không truncate hay reset database phát triển. CI là gate chính thức cho full suite.

## Cấu trúc

- `app/main.py`: routes, CORS, error envelope, tracing và health.
- `app/auth.py`: hash token và xác thực session.
- `app/chat.py`: ownership, lock, persistence, retry và orchestration AI.
- `app/ai.py`: internal AI client và timeout/schema guard.
- `app/config.py`: cấu hình DSN/`DB_*` và secret-safe URL.
- `app/doctor.py`: chẩn đoán cấu hình/kết nối an toàn.
- `migrations/`: Alembic migration bốn bảng G1.
- `tests/`: unit, config và PostgreSQL integration tests.
- `docs/TEST_REPORT.md`: bằng chứng test cập nhật.
