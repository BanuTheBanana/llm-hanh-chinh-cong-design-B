# API Contract G1

> Trạng thái: `VERIFIED_ON_MAIN`; đóng băng tại tag `g1-v1.0.0`<br>
> Phiên bản: `v1.2`<br>
> Cập nhật: 08/09/2026<br>
> Runtime đã kiểm tra: commit `4b64f6f`, GitHub Actions run
> [`34197723998`](https://github.com/DOMEMON/llm-hanh-chinh-cong/actions/runs/34197723998)<br>
> Owner ghi nhận: Hoan; Web của Tú và Backend của Minh là consumer.

Đây là contract duy nhất giữa Web, Core Backend và AI Service trong G1.
Không tạo bản sao trong folder service. Thay đổi schema phải cập nhật consumer,
test và tài liệu trong cùng pull request hoặc có kế hoạch tương thích.

## Quy ước chung

- Web mặc định: `http://localhost:3000`.
- Public Core API mặc định: `http://localhost:8000/api/v1`.
- AI Service origin trong Compose: `http://ai-service:8001`.
- Internal generate route: `/internal/v1/generate`.
- ID và `request_id`: UUID string.
- Timestamp: ISO 8601 UTC.
- Web luôn gửi cookie bằng `credentials: "include"`.
- G1 dùng response synchronous, chưa có Socket.IO/queue.
- Input model từ chối field dư.

Lỗi public chuẩn:

```json
{
  "error": {
    "code": "AI_SERVICE_TIMEOUT",
    "message": "AI đang phản hồi chậm. Vui lòng thử lại.",
    "request_id": "uuid"
  }
}
```

Với request đi vào application handler, Core Backend cũng trả `X-Request-ID`
cùng giá trị và `Cache-Control: no-store`. CORS preflight bị middleware từ chối
là ngoại lệ: browser có thể nhận plain-text error mà không có hai header này.

## Public Core API

```text
POST /api/v1/auth/login
POST /api/v1/auth/logout
GET  /api/v1/auth/me
GET  /api/v1/conversations
POST /api/v1/conversations
GET  /api/v1/conversations/{conversation_id}/messages
POST /api/v1/conversations/{conversation_id}/messages
GET  /health
```

### Authentication demo

Login request, `display_name` được trim và có 1–100 ký tự:

```json
{"display_name": "Hoan"}
```

`POST /auth/login` trả `200`:

```json
{"id": "uuid", "display_name": "Hoan"}
```

Backend tạo opaque session token ngẫu nhiên, database chỉ lưu hash, và đặt
cookie `g1_session`, `HttpOnly`, `SameSite=Lax`, Path `/`. `Secure` phụ thuộc
environment. Frontend không gửi `user_id` để chứng minh danh tính.

- `GET /auth/me`: `200` với schema user trên hoặc `401 UNAUTHORIZED`.
- `POST /auth/logout`: `204`, body rỗng; gọi lặp lại vẫn an toàn.

Login bằng tên không xác minh con người thật. Cùng một `display_name` ánh xạ
vào cùng demo user và có thể thấy lại lịch sử của user đó; bất kỳ ai biết tên
đều có thể nhập lại. Đây không phải authentication và tuyệt đối không dùng với
PII/dữ liệu thật.

### Conversation

`POST /conversations` nhận `{}` hoặc title 1–200 ký tự:

```json
{"title": "Cuộc trò chuyện mới"}
```

Response `201`:

```json
{
  "id": "uuid",
  "title": "Cuộc trò chuyện mới",
  "created_at": "2026-09-08T02:00:00Z",
  "updated_at": "2026-09-08T02:00:00Z"
}
```

`GET /conversations` trả array trực tiếp, conversation mới cập nhật đứng
trước. G1 chưa phân trang.

### Message

`GET /conversations/{id}/messages` trả array cũ trước, bao gồm cả
`pending | completed | failed`.

Request gửi message; `content` sau trim có 1–10.000 ký tự:

```json
{
  "client_message_id": "uuid-do-web-tao",
  "content": "Xin chào, đây là tin nhắn kiểm thử."
}
```

Response thành công `200`:

```json
{
  "user_message": {
    "id": "uuid",
    "conversation_id": "uuid",
    "role": "user",
    "content": "Xin chào, đây là tin nhắn kiểm thử.",
    "status": "completed",
    "created_at": "2026-09-08T02:00:00Z"
  },
  "assistant_message": {
    "id": "uuid",
    "conversation_id": "uuid",
    "role": "assistant",
    "content": "Đây là phản hồi mô phỏng...",
    "status": "completed",
    "created_at": "2026-09-08T02:00:01Z"
  }
}
```

Quy tắc idempotency:

- `client_message_id` unique trong một conversation;
- retry cùng ID và cùng content sau khi thành công trả lại cặp đã lưu,
  không gọi AI lại;
- cùng ID nhưng content khác trả `409 IDEMPOTENCY_CONFLICT`;
- retry failed turn mới nhất tái sử dụng user message; failed turn cũ sau khi đã
  có turn mới trả `409 RETRY_OUT_OF_ORDER`;
- khi AI lỗi/timeout, user message vẫn được lưu `failed`, không bịa
  assistant message thành công.

## Public error codes

| HTTP | Code | Ý nghĩa cho client |
|---:|---|---|
| 401 | `UNAUTHORIZED` | Đăng nhập lại và xóa workspace UI |
| 403 | `FORBIDDEN_ORIGIN` | Origin browser không khớp `WEB_ORIGIN` |
| 404 | `NOT_FOUND` | Conversation không tồn tại hoặc không thuộc user |
| 404/405 | `HTTP_ERROR` | Route không tồn tại hoặc HTTP method không được hỗ trợ |
| 409 | `MESSAGE_IN_PROGRESS` | Conversation đang xử lý turn khác |
| 409 | `IDEMPOTENCY_CONFLICT` | ID cũ bị dùng với content khác |
| 409 | `RETRY_OUT_OF_ORDER` | Không retry failed turn cũ sau turn mới |
| 422 | `VALIDATION_ERROR` | Input sai/rỗng/quá dài/có field dư |
| 500 | `INTERNAL_ERROR` | Lỗi Core; tra log bằng request ID |
| 502 | `AI_SERVICE_ERROR` | Network/HTTP/schema AI không hợp lệ |
| 503 | `DATABASE_UNAVAILABLE` | Health không truy cập được DB |
| 504 | `AI_SERVICE_TIMEOUT` | AI vượt deadline; UI cho retry |

## Internal AI API

```text
POST /internal/v1/generate
GET  /health
```

Generate request:

```json
{
  "request_id": "uuid",
  "messages": [
    {"role": "user", "content": "Xin chào, đây là tin nhắn kiểm thử."}
  ],
  "max_output_tokens": 300
}
```

Ràng buộc:

- 1–100 messages; Backend gửi tối đa 100 message gần nhất theo thứ tự;
- role: `system | user | assistant`;
- content không blank, tối đa 16.000 ký tự;
- `max_output_tokens`: integer 1–4.096.

Core G1 lấy `max_output_tokens` từ `LLM_MAX_OUTPUT_TOKENS`, mặc định 300 và
cũng bị giới hạn 1–4.096.

Response:

```json
{
  "request_id": "uuid",
  "text": "Đây là phản hồi mô phỏng cho câu hỏi của bạn.",
  "provider": "mock",
  "model": "mock-v1",
  "usage": {"input_tokens": 0, "output_tokens": 0},
  "latency_ms": 10
}
```

`provider` là string không blank để tương thích adapter tương lai; implementation
G1 chỉ chấp nhận `LLM_PROVIDER=mock`. Mock modes `success | error | timeout`
được điều khiển bằng environment/test override, không bằng câu lệnh bí mật
trong prompt.

### Internal AI error codes

| HTTP | Code | Ý nghĩa với Core Backend |
|---:|---|---|
| 422 | `VALIDATION_ERROR` | Request nội bộ sai schema/giới hạn |
| 503 | `AI_PROVIDER_ERROR` | Provider chạy nhưng trả lỗi có kiểm soát |
| 503 | `AI_PROVIDER_UNAVAILABLE` | Provider cấu hình chưa được triển khai |
| 504 | `AI_SERVICE_TIMEOUT` | Provider vượt thời gian chờ |

Core giữ lỗi 504 thành public `504 AI_SERVICE_TIMEOUT`. Network error, HTTP
error khác 504, JSON/schema sai hoặc request ID không khớp được chuẩn hóa thành
public `502 AI_SERVICE_ERROR`.

## Health contracts

Core Backend, chỉ phụ thuộc database:

```json
{"status": "ok"}
```

AI Service:

```json
{"status": "ok", "service": "ai-service", "provider": "mock"}
```

## Cấu hình nối service

- `AI_SERVICE_URL` là origin, ví dụ `http://ai-service:8001`; không kèm
  `/internal/v1` hay `/generate`.
- Backend nối chính xác `/internal/v1/generate`.
- `AI_REQUEST_TIMEOUT_SECONDS` điều khiển deadline của Backend.
- `LLM_MAX_OUTPUT_TOKENS` điều khiển giới hạn output Core gửi sang AI Service.
- `WEB_ORIGIN` phải khớp chính xác scheme/host/port mà browser mở.
- Web chỉ đọc `VITE_API_BASE_URL`; không gọi AI Service trực tiếp.
- Nếu đổi `WEB_PORT` hoặc `BACKEND_PORT`, phải đổi đồng bộ `WEB_ORIGIN` và
  `VITE_API_BASE_URL` vì các URL trên chỉ là default local.

PostgreSQL trong Compose dùng `POSTGRES_DB`, `POSTGRES_USER` và
`POSTGRES_PASSWORD` để tạo database; Backend nhận chính các giá trị này qua
`DB_NAME`, `DB_USER`, `DB_PASSWORD`, với host `postgres` và port `5432`.
`DATABASE_URL` là override tùy chọn, được ưu tiên khi khác rỗng; nếu đặt thì
người vận hành chịu trách nhiệm để DSN trỏ đúng database.

## Bảo mật và ownership

- Core Backend lấy user từ session, không tin `user_id` từ client.
- Mọi conversation/message query kiểm tra ownership; cross-user trả 404 để
  không rò sự tồn tại.
- AI Service không truy cập PostgreSQL ứng dụng trong G1.
- Không log session token, secret, request body, DSN hay exception text.
- G1 chỉ dùng dữ liệu giả `D0_SYSTEM_SMOKE`.
