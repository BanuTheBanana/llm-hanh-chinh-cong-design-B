# API Contract G1

> Trạng thái: `FROZEN_FOR_G1`  
> Cập nhật: 08/09/2026  
> Owner ghi nhận: Hoan; Tú và Minh cùng review.

Contract này là điểm nối giữa Web, Core Backend và AI Service. Muốn thay đổi phải báo cả ba thành viên và cập nhật consumer liên quan trong cùng pull request hoặc theo kế hoạch tương thích đã thống nhất.

## Quy ước chung

- Web: `http://localhost:3000`.
- Core API: `http://localhost:8000/api/v1`.
- AI internal API trong Compose: `http://ai-service:8001/internal/v1`.
- ID: UUID string.
- Timestamp: ISO 8601 UTC.
- Web gửi cookie bằng `credentials: include`.
- G1 dùng response synchronous, chưa dùng Socket.IO.

Lỗi chuẩn:

```json
{
  "error": {
    "code": "AI_SERVICE_TIMEOUT",
    "message": "AI đang phản hồi chậm. Vui lòng thử lại.",
    "request_id": "uuid"
  }
}
```

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

### Login demo

```json
{
  "display_name": "Hoan"
}
```

Backend đặt opaque session cookie `HttpOnly`, `SameSite=Lax`. Frontend không gửi `user_id` để chứng minh danh tính.

### Conversation

```json
{
  "id": "uuid",
  "title": "Cuộc trò chuyện mới",
  "created_at": "2026-09-08T02:00:00Z",
  "updated_at": "2026-09-08T02:00:00Z"
}
```

### Gửi message

```json
{
  "client_message_id": "uuid-do-web-tao",
  "content": "Xin chào, đây là tin nhắn kiểm thử."
}
```

Response:

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

`client_message_id` là idempotency key trong phạm vi conversation. Khi AI lỗi, user message vẫn được giữ và Core API trả lỗi chuẩn.

## Internal AI API

```text
POST /internal/v1/generate
GET  /health
```

Request:

```json
{
  "request_id": "uuid",
  "messages": [
    {"role": "user", "content": "Xin chào, đây là tin nhắn kiểm thử."}
  ],
  "max_output_tokens": 300
}
```

Response:

```json
{
  "request_id": "uuid",
  "text": "Đây là phản hồi mô phỏng cho câu hỏi của bạn.",
  "provider": "mock",
  "model": "mock-v1",
  "usage": {
    "input_tokens": 0,
    "output_tokens": 0
  },
  "latency_ms": 10
}
```

Mock modes: `success | error | timeout`, được điều khiển bằng cấu hình hoặc test override, không dùng câu lệnh bí mật trong prompt.

## Quy tắc bảo mật và ownership

- Core Backend lấy user từ session, không tin `user_id` từ client.
- Mọi conversation/message query phải kiểm tra ownership.
- Web không gọi AI Service trực tiếp.
- AI Service không truy cập PostgreSQL ứng dụng trong G1.
- Không log session token, secret hoặc dữ liệu nhạy cảm.
- G1 chỉ dùng dữ liệu giả `D0_SYSTEM_SMOKE`.
