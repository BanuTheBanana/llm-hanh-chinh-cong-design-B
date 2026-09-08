# API và thiết kế G1

## 3. Điểm chưa được quy định trong contract — cần Tú/Hoan review

Các endpoint/schema đã có được giữ nguyên. Các chi tiết contract chưa ghi được
triển khai với quy ước dưới đây; đây không phải nội dung đã được cả nhóm xác nhận.
Bản contract nguồn không bị chỉnh sửa, xem `contracts-g1.reference.md`.

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
bảng ngoài bốn bảng G1. Context gửi AI gồm các message completed và user message
đang xử lý; bỏ các failed/pending cũ chưa có câu trả lời. Nếu worker chết, pending
vẫn còn và có thể retry turn mới nhất. Không bảo đảm AI chỉ được gọi đúng một lần
khi crash xảy ra sau AI response nhưng trước DB commit; chỉ bảo đảm không nhân đôi
message đã lưu theo key. G1 chưa có side effect ngoài Mock AI.

Log có request_id, route template, method, HTTP status, latency_ms. Không log
request body, query string, cookie/token, DSN hoặc exception text. CORS có
credentials và kiểm tra Origin cho các request thay đổi dữ liệu. Response dùng
`Cache-Control: no-store`.

