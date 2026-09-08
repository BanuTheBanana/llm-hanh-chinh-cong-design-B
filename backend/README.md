# Backend Giai đoạn 1 — Minh

Gói `backend/` để ghép vào monorepo LLM. FastAPI + Pydantic + SQLAlchemy 2 async +
asyncpg + Alembic; PostgreSQL lưu users, sessions, conversations, messages.

**Trạng thái:** source Backend đã được đưa vào nhánh tích hợp cùng Web và AI Service.
Các kiểm tra PostgreSQL, migration online, Docker và end-to-end vẫn phải pass trước
khi đánh dấu Definition of Done G1 hoàn thành; xem `docs/TEST_REPORT.md`.

## 1. Chạy nhanh

Yêu cầu: Python 3.12, uv, PostgreSQL (ví dụ PostgreSQL 16), AI Service của Hoan.
Chạy các lệnh Python bên dưới từ thư mục `backend/`.

```bash
uv sync --frozen
cp ../.env.example .env
```

PowerShell: dùng `Copy-Item ..\.env.example .env` thay lệnh `cp`.
File root `.env.example` dùng hostname nội bộ của Compose. Nếu chạy Backend trực
tiếp trên máy host, sửa tối thiểu hai giá trị trong `backend/.env` thành:

```env
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/g1
AI_SERVICE_URL=http://localhost:8001
```

Nếu chưa có PostgreSQL local, dùng Docker trên máy của anh:

```bash
docker run --name minh-g1-postgres -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=g1 -p 127.0.0.1:5432:5432 -d postgres:16
docker exec minh-g1-postgres pg_isready -U postgres -d g1
```

Đợi `accepting connections`, rồi chạy:

```bash
uv run --frozen alembic upgrade head
uv run --frozen uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-access-log --log-config logging.json
```

- Swagger: http://localhost:8000/docs
- OpenAPI: http://localhost:8000/openapi.json
- Health kiểm tra database: http://localhost:8000/health
- AI Service phải cung cấp `POST /internal/v1/generate` theo file contract đính kèm.
- Backend vẫn khởi động khi AI chưa chạy; gửi message lúc đó trả lỗi 502 chuẩn và giữ user message.
- Không tự chạy migration lúc server khởi động: chạy migration một lần trước khi scale workers.

## 2. Environment

| Biến | Giá trị mẫu | Ý nghĩa |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/g1` | DSN PostgreSQL async |
| `AI_SERVICE_URL` | `http://localhost:8001` | Origin của AI Service; Backend nối `/internal/v1/generate` |
| `AI_REQUEST_TIMEOUT_SECONDS` | `10` | Deadline tổng và timeout HTTP |
| `SESSION_COOKIE_NAME` | `g1_session` | Tên cookie opaque |
| `SESSION_COOKIE_SECURE` | `false` | Đặt `true` khi dùng HTTPS |
| `SESSION_TTL_SECONDS` | `86400` | Session hết hạn sau 24 giờ |
| `WEB_ORIGIN` | `http://localhost:3000` | Origin duy nhất được phép gọi Core API ở G1 |

`.env` chỉ dùng local, không commit. Giá trị trong `.env.example` là thông tin demo.
Trong Compose của Hoan, dùng `postgres` làm database hostname và đặt
`AI_SERVICE_URL=http://ai-service:8001`. Không dùng `localhost` để gọi
container khác. Docker build context là `./backend`; Dockerfile được cung cấp.
Hoan có thể đặt healthcheck bằng Python urllib gọi `http://localhost:8000/health`.

Backend cần kết nối PostgreSQL trực tiếp hoặc pool ở **session mode**. Không dùng
PgBouncer transaction pooling với advisory lock ở G1.

## 3. Điểm chưa được quy định trong contract — cần Tú/Hoan review

Các endpoint/schema đã có được giữ nguyên. Contract duy nhất của cả monorepo nằm
tại [`../docs/contracts-g1.md`](../docs/contracts-g1.md); không giữ bản sao trong
Backend để tránh hai tài liệu lệch nhau.

| Điểm bổ sung | Quy ước hiện tại |
|---|---|
| Login / me response | `200 {"id":"uuid","display_name":"Minh"}` |
| Logout | `204`, body rỗng, lặp lại vẫn được; hủy session và xóa cookie |
| Tên cookie | `g1_session`, Path `/`, HttpOnly, SameSite=Lax, TTL 24 giờ |
| Demo identity | Trim display_name; phân biệt hoa/thường; cùng tên vào cùng demo user |
| POST conversation body | `{}` hoặc `{"title":"..."}`; response 201 theo schema conversation |
| GET conversation list | Array trực tiếp, mới cập nhật trước; chưa phân trang G1 |
| GET message list | Array trực tiếp, cũ trước; bao gồm pending/failed |
| POST message thành công | 200 theo cặp user_message/assistant_message đã khóa |
| Không có quyền conversation | 404 giống conversation không tồn tại |
| Giới hạn | display_name 1–100; title 1–200; content 1–10.000 ký tự sau trim |
| Field dư / UUID sai / rỗng / quá dài | 422, không lưu message |
| Retry thành công trước đó | Trả đúng cặp đã lưu, không gọi AI lại |
| Cùng key, nội dung khác | 409 IDEMPOTENCY_CONFLICT |
| Đang có generation trong conversation | 409 MESSAGE_IN_PROGRESS; retry cùng key khi request trước kết thúc |
| Retry failed/pending mới nhất | Gọi AI lại với cùng user message; request_id của lần thử mới |
| Retry failed/pending cũ sau một turn mới | 409 RETRY_OUT_OF_ORDER; gửi nội dung bằng key mới |
| `/health` | 200 `{"status":"ok"}` nếu DB kết nối được; không phụ thuộc AI |
| Request tracing | Backend tạo UUID mỗi HTTP request; trả `X-Request-ID` |

Login demo bằng tên **không xác minh danh tính người thật**. Người biết tên demo có
thể đăng nhập cùng tài khoản đó. Chỉ dùng dữ liệu giả D0_SYSTEM_SMOKE như tài liệu
phân công; không coi đây là login production. Isolation ở đây là quyền đọc/ghi dựa
trên session của demo user đã đăng nhập.

## 4. Public API để Tú ghép Web

Tất cả request cần cookie phải dùng `credentials: "include"`.

```javascript
const base = import.meta.env.VITE_API_BASE_URL; // http://localhost:8000/api/v1
await fetch(`${base}/auth/login`, {
  method: "POST", credentials: "include",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ display_name: "Minh" }),
});
const created = await fetch(`${base}/conversations`, {
  method: "POST", credentials: "include",
  headers: { "Content-Type": "application/json" }, body: JSON.stringify({}),
});
const conversation = await created.json();
const payload = { client_message_id: crypto.randomUUID(), content: "D0_SYSTEM_SMOKE" };
const sent = await fetch(`${base}/conversations/${conversation.id}/messages`, {
  method: "POST", credentials: "include",
  headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
});
// Kiểm tra sent.ok trước khi dùng response như một cặp message.
// Nếu lỗi mạng/502/504: giữ payload và dùng lại chính client_message_id khi retry.
// Nếu 409 MESSAGE_IN_PROGRESS: đợi request hiện tại xong rồi retry.
```

| Method | Path (sau `/api/v1`) |
|---|---|
| POST | `/auth/login` |
| POST | `/auth/logout` |
| GET | `/auth/me` |
| GET, POST | `/conversations` |
| GET, POST | `/conversations/{conversation_id}/messages` |

Mọi lỗi có dạng:

```json
{"error":{"code":"AI_SERVICE_TIMEOUT","message":"AI đang phản hồi chậm. Vui lòng thử lại.","request_id":"uuid"}}
```

| HTTP | Code | Xử lý |
|---|---|---|
| 401 | UNAUTHORIZED | Đăng nhập lại |
| 403 | FORBIDDEN_ORIGIN | Kiểm tra origin của Web và CORS config |
| 404 | NOT_FOUND | Conversation không tồn tại hoặc không thuộc user |
| 409 | MESSAGE_IN_PROGRESS | Đợi rồi retry |
| 409 | IDEMPOTENCY_CONFLICT | Không tái dùng key cho nội dung khác |
| 409 | RETRY_OUT_OF_ORDER | Gửi thành turn mới với key mới |
| 422 | VALIDATION_ERROR | Sửa dữ liệu đầu vào |
| 502 | AI_SERVICE_ERROR | Lỗi kết nối/HTTP/schema từ AI; giữ nội dung và retry |
| 504 | AI_SERVICE_TIMEOUT | AI quá deadline; giữ nội dung và retry |
| 503 | DATABASE_UNAVAILABLE | Healthcheck DB không đạt |
| 500 | INTERNAL_ERROR | Lỗi hệ thống; dùng request_id để tra log |

## 5. Persistence và idempotency

1. Xác thực session qua SHA-256 hash của token ngẫu nhiên 32 bytes.
2. Kiểm tra ownership trước khi truy cập lịch sử hoặc lấy khóa.
3. Lấy PostgreSQL advisory lock cho conversation, áp dụng xuyên nhiều workers.
4. Lấy lại message theo unique `(conversation_id, client_message_id)` hoặc tạo mới.
5. Commit user message `pending` trước khi gọi AI. Không giữ transaction DB mở khi chờ AI.
6. AI trả đúng schema và request_id: commit user `completed` cùng assistant `completed`.
7. AI lỗi/timeout: commit user `failed`, không tạo assistant giả.
8. Luôn nhả khóa; nếu nhả khóa lỗi thì hủy connection, không đưa khóa còn giữ về pool.

Assistant được liên kết với user turn bằng `(conversation_id, request_id)`;
unique `(conversation_id, request_id, role)` là lớp bảo vệ thứ hai. Không cần thêm
bảng ngoài bốn bảng G1. Context gửi AI gồm tối đa 100 message gần nhất: các message
completed và user message đang xử lý; bỏ các failed/pending cũ. Nếu worker chết, pending
vẫn còn và có thể retry turn mới nhất. Không bảo đảm AI chỉ được gọi đúng một lần
khi crash xảy ra sau AI response nhưng trước DB commit; chỉ bảo đảm không nhân đôi
message đã lưu theo key. G1 chưa có side effect ngoài Mock AI.

Log có request_id, route template, method, HTTP status, latency_ms. Không log
request body, query string, cookie/token, DSN hoặc exception text. CORS có
credentials và kiểm tra Origin cho các request thay đổi dữ liệu. Response dùng
`Cache-Control: no-store`.

## 6. Chạy tests

Unit/contract checks, không cần PostgreSQL hoặc AI Service:

```bash
uv run --frozen pytest tests/test_unit.py -q
uv run --frozen ruff check .
uv run --frozen ruff format --check .
```

Integration tests dùng PostgreSQL thật, AI HTTP response được mock bằng HTTPX
transport. Dùng database test riêng; test tự tạo schema `g1_test_<uuid>`, chạy
Alembic vào schema trống, rồi xóa chính schema đó sau mỗi test. Không truncate
bảng ứng dụng. Database user test cần quyền CREATE SCHEMA.

```bash
docker exec minh-g1-postgres createdb -U postgres g1_test
```

Bash:

```bash
export TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/g1_test
uv run --frozen pytest -q
```

PowerShell:

```powershell
$env:TEST_DATABASE_URL = 'postgresql+asyncpg://postgres:postgres@localhost:5432/g1_test'
uv run --frozen pytest -q
```

Không đặt `TEST_DATABASE_URL` thì integration test báo lỗi cấu hình rõ ràng; không
âm thầm skip và không tự dùng database thật. Unit suite vẫn chạy riêng được.

Migration trên database ứng dụng:

```bash
uv run --frozen alembic upgrade head
uv run --frozen alembic current
uv run --frozen alembic check
```

Có downgrade nhưng `alembic downgrade base` xóa bốn bảng và dữ liệu; chỉ dùng với
DB test/dev có thể bỏ. Không đưa lệnh reset vào luồng chạy mặc định.

## 7. Cấu trúc source

- `app/main.py`: route, error handlers, CORS, tracing, health.
- `app/auth.py`: token hashing và xác thực session.
- `app/chat.py`: ownership, khóa PostgreSQL, retry và orchestration.
- `app/ai.py`: HTTP client, deadline, validate internal AI response.
- `app/models.py`, `app/db.py`: schema SQLAlchemy và session async.
- `app/config.py`, `app/schemas.py`, `app/errors.py`: config, validation, lỗi.
- `migrations/`: Alembic migration bốn bảng, hỗ trợ online/offline.
- `tests/`: unit và integration cases.
- `uv.lock`: khóa toàn bộ dependency; dùng `--frozen` khi cài/chạy.
- `Dockerfile`, `.dockerignore`, `logging.json`: cấu hình để ghép hạ tầng an toàn.
- `docs/openapi.json`: OpenAPI xuất từ app hiện tại.
- `docs/TEST_REPORT.md`: bằng chứng kiểm tra và blocker.

## 8. Các bước còn lại để chốt DoD với nhóm

1. Chạy PostgreSQL integration suite và `alembic check` trên máy/CI có PostgreSQL.
2. Xác nhận Compose chạy migration trước khi Backend bắt đầu nhận traffic.
3. Ghép AI Service thật và Web: login → create → send → reload.
4. Đổi sang user khác để xác nhận không đọc được conversation cũ; test AI error và
   timeout mode bằng cấu hình service của Hoan.
