# Phân công triển khai Giai đoạn 1 – Technical Vertical Slice

> **Tài liệu thực thi cho Tú, Minh và Hoan.**  
> Mục tiêu: trong Giai đoạn 1, nhóm tạo được một web chat tối giản chạy end-to-end với Mock AI, lưu được lịch sử và không lẫn dữ liệu giữa người dùng.  
> Tài liệu chiến lược cấp trên: [00-chien-luoc-trien-khai-tu-nho-den-lon.md](00-chien-luoc-trien-khai-tu-nho-den-lon.md).  
> Cách trình bày: **Tổng → Phân → Hợp**.

## Báo cáo cập nhật

| Trường | Nội dung |
|---|---|
| Cập nhật gần nhất | 08/09/2026 |
| Phiên bản | `v1.2` |
| Trạng thái | `G1_VERIFIED_ON_INTEGRATION` |
| Phạm vi | Web + Core Backend + PostgreSQL + AI Service Mock |
| Ngoài phạm vi | RAG, model local, fine-tune, Case, memory dài hạn, queue, Socket.IO |
| Thay đổi lần này | Ghi nhận code của Tú, Minh và Hoan đã tích hợp; checklist G1 đã được CI kiểm tra trên môi trường sạch |

## Tiến độ thực thi G1

- [x] Khóa API contract G1.
- [x] Tạo và đồng bộ baseline cho ba branch.
- [x] Sắp xếp tài liệu vào `docs/`.
- [x] Hoan: Mock AI Service và failure modes.
- [x] Hoan: Compose/config/runbook/smoke AI.
- [x] Tú: Web React gọi Core API thật.
- [x] Minh: Core Backend, PostgreSQL và migration.
- [x] Cả nhóm: integration Web → Backend → AI → PostgreSQL.
- [x] Cả nhóm: nghiệm thu đủ G1-01 đến G1-12.

### Bằng chứng nghiệm thu

GitHub Actions run
[`34197723998`](https://github.com/DOMEMON/llm-hanh-chinh-cong/actions/runs/34197723998)
đã pass 5/5 job tại commit `4b64f6f` trên `g1/integration`:

- Web: 9 test, lint, production build và Playwright browser smoke;
- AI Service: 15 test, lint và lockfile check;
- Backend: 58 test với PostgreSQL 16 và migration từ database sạch;
- repository hygiene/secret-pattern gate;
- full Compose smoke, API smoke và browser smoke.

API message round-trip là 56,33 ms với Mock AI; Playwright smoke hoàn tất trong
2,0 giây. Hai số này chỉ là baseline của môi trường CI, không phải SLA hoặc
benchmark model thật. G1 đã đạt trên nhánh tích hợp nhưng chưa merge vào `main`.

---

# PHẦN I – TỔNG: CẢ NHÓM ĐANG XÂY GÌ?

## 1. Kết quả cuối G1

Người dùng có thể:

1. đăng nhập bằng danh tính demo;
2. tạo và mở một cuộc hội thoại;
3. gửi tin nhắn trên web;
4. nhận câu trả lời từ Mock AI;
5. tải lại trang mà vẫn thấy lịch sử;
6. chỉ xem được hội thoại thuộc tài khoản của mình;
7. thấy thông báo rõ ràng khi AI Service lỗi hoặc timeout.

Luồng bắt buộc phải chạy:

```text
Web React
  → Core Backend FastAPI
      → lưu user message vào PostgreSQL
      → gọi AI Service FastAPI
          → Mock provider tạo response
      → lưu assistant message vào PostgreSQL
  ← trả response cho Web
  ← refresh và tải lại history từ PostgreSQL
```

G1 thành công khi **toàn bộ đường ống chạy và kiểm thử được**. G1 chưa được dùng để kết luận chatbot trả lời hành chính chính xác.

## 2. Stack kỹ thuật chốt cho G1

| Khối | Công nghệ | Ghi chú |
|---|---|---|
| Web | React + TypeScript + Vite | Một trang chat responsive; chưa cần framework UI nặng |
| State/data fetching | React hooks + API client mỏng | Chưa cần Redux ở G1 |
| Core Backend | Python + FastAPI + Pydantic | REST API, session, orchestration |
| Database | PostgreSQL | Source of truth cho user, session, conversation, message |
| ORM/migration | SQLAlchemy 2 + Alembic + asyncpg | Migration phải chạy được từ môi trường sạch |
| AI Service | Python + FastAPI + Pydantic | Provider adapter; G1 chỉ bật `mock` |
| Test Python | pytest + HTTPX | Unit/API/integration tests tối thiểu |
| Test Web | Vitest + React Testing Library | Test các trạng thái quan trọng |
| Dev environment | Docker Compose + `.env` | Một lệnh dựng được hệ thống |

Phiên bản package cụ thể được khóa trong lockfile khi khởi tạo code; không để mỗi thành viên tự chọn một stack khác.

## 3. Ranh giới trách nhiệm

```text
Tú:   Web/UI
       │ chỉ gọi public Core API
       ▼
Minh: Core Backend + PostgreSQL
       │ chỉ gọi internal AI API
       ▼
Hoan: AI Service Mock + Docker Compose + contract/integration
```

Quy tắc:

- Web không gọi AI Service trực tiếp.
- Web không tự quyết định `user_id` hoặc quyền sở hữu conversation.
- Core Backend là nơi xác thực session và kiểm tra ownership.
- AI Service không truy cập database ứng dụng ở G1.
- Không dùng dữ liệu công ty hoặc PII trong G1; chỉ dùng `D0_SYSTEM_SMOKE`.
- Không thêm RAG, Qwen, Redis, Qdrant, Socket.IO hoặc Case Router trong G1.

## 4. Cấu trúc monorepo đề xuất

```text
LLM/
├── web/
├── backend/
├── ai-service/
├── infra/
│   └── docker/
├── scripts/
├── docs/
│   ├── 00-chien-luoc-trien-khai-tu-nho-den-lon.md
│   ├── 01-phan-cong-giai-doan-1.md
│   ├── contracts-g1.md
│   ├── architecture/
│   ├── archive/
│   └── parked/
├── compose.yaml
├── .env.example
└── README.md
```

Không tạo ba repository rời ở G1. Tách bằng folder, container và API contract là đủ.

## 5. Contract G1 đã khóa – bản tóm tắt

[`contracts-g1.md`](contracts-g1.md) là source of truth cho runtime G1. Phần
dưới chỉ tóm tắt để hiểu phân công; nếu có khác biệt thì ưu tiên contract.

### 5.1. Quy ước chung

- Public Core API: `http://localhost:8000/api/v1`.
- Internal AI API: `http://ai-service:8001/internal/v1` trong Compose.
- Web dev server: `http://localhost:3000`.
- ID dùng UUID dạng string.
- Thời gian trả về dạng ISO 8601 UTC.
- Web luôn gửi cookie bằng `credentials: include`.
- Lỗi dùng cùng một cấu trúc:

```json
{
  "error": {
    "code": "AI_SERVICE_TIMEOUT",
    "message": "AI đang phản hồi chậm. Vui lòng thử lại.",
    "request_id": "uuid"
  }
}
```

### 5.2. Public Core API

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

Đăng nhập demo:

```json
// POST /api/v1/auth/login
{
  "display_name": "Hoan"
}
```

Backend tạo hoặc lấy demo user, tạo opaque session ngẫu nhiên và đặt cookie `HttpOnly`, `SameSite=Lax`. Frontend không lưu `user_id` như bằng chứng xác thực.

Conversation:

```json
{
  "id": "uuid",
  "title": "Cuộc trò chuyện mới",
  "created_at": "2026-09-08T02:00:00Z",
  "updated_at": "2026-09-08T02:00:00Z"
}
```

Gửi message:

```json
// POST /api/v1/conversations/{id}/messages
{
  "client_message_id": "uuid-do-web-tao",
  "content": "Xin chào, đây là tin nhắn kiểm thử."
}
```

Response synchronous của G1:

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

`client_message_id` dùng để chống tạo trùng user message khi người dùng bấm retry. Nếu AI lỗi, user message vẫn phải tồn tại và Core API trả lỗi chuẩn; không tự bịa assistant message thành công.

### 5.3. Internal AI API

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

Mock phải có ba chế độ cấu hình để test: `success`, `error`, `timeout`. Không dùng nội dung prompt bí mật để kích hoạt lỗi.

## 6. Database tối thiểu

```text
users
- id
- display_name
- created_at

sessions
- id
- user_id
- token_hash
- expires_at
- created_at

conversations
- id
- user_id
- title
- created_at
- updated_at

messages
- id
- conversation_id
- client_message_id nullable
- role: user | assistant
- content
- status: pending | completed | failed
- request_id
- created_at
```

Ràng buộc tối thiểu:

- conversation luôn thuộc đúng một user;
- mọi truy vấn conversation/message phải lọc theo authenticated user;
- `client_message_id` của user message là unique trong một conversation;
- không nhận `user_id` từ request tạo conversation/message;
- migration `upgrade` chạy được trên database trống.

---

# PHẦN II – PHÂN: NHIỆM VỤ TỪNG THÀNH VIÊN

## 7. Tú – Frontend Owner

### 7.1. Nhiệm vụ chính

Xây giao diện để người dùng hoàn thành toàn bộ luồng G1 bằng Core API thật.

### 7.2. Deliverable

1. Khởi tạo `web/` bằng React + TypeScript + Vite.
2. Màn hình đăng nhập demo bằng `display_name`.
3. Layout chat gồm sidebar conversation và vùng messages.
4. Tạo conversation mới và mở conversation đã có.
5. Gửi message bằng `client_message_id` UUID.
6. Hiển thị user message, trạng thái đang chờ và assistant message.
7. Refresh trang vẫn gọi API để tải đúng history.
8. Các trạng thái: loading, empty, unauthorized, API error, AI timeout và retry.
9. Nút logout; sau logout không còn thấy dữ liệu user trước.
10. Một số test UI/API client quan trọng.

### 7.3. Yêu cầu bắt buộc

- Chỉ gọi URL backend qua biến môi trường `VITE_API_BASE_URL`.
- Mọi request xác thực dùng `credentials: "include"`.
- Không hard-code conversation hoặc response AI trong bản tích hợp.
- Không gọi `localhost:8001` và không biết cấu trúc nội bộ của AI Service.
- Không tin cache frontend hơn response backend.
- Khi POST message lỗi, giữ nội dung để user có thể retry; không tự thêm câu trả lời giả.
- Giao diện rõ ràng và dùng được trên laptop; chưa dành thời gian cho animation hoặc design system lớn.

### 7.4. Test Tú phải chứng minh

- Chưa đăng nhập thì chuyển về màn hình login.
- Login thành công thì thấy conversation list.
- Tạo conversation và gửi message thành công.
- Refresh vẫn thấy đúng messages.
- AI timeout hiển thị lỗi và cho retry.
- Logout xóa trạng thái UI và backend session.

### 7.5. Definition of Done của Tú

- Web chạy bằng command đã ghi trong README.
- Không còn dữ liệu mock cục bộ trong happy path tích hợp.
- TypeScript không có lỗi; test được chọn đều pass.
- Dùng đúng contract G1 và đã ghép thành công với backend của Minh.

### 7.6. Context giao cho AI coding agent của Tú

```text
Bạn đang hỗ trợ Tú triển khai Frontend cho Giai đoạn 1 của dự án trợ lý hành chính công.

Mục tiêu hiện tại chỉ là technical vertical slice, chưa làm RAG, Qwen, Case, memory dài hạn, Socket.IO hoặc UI phức tạp. Stack bắt buộc: React + TypeScript + Vite. Web chỉ gọi Core Backend tại VITE_API_BASE_URL, tuyệt đối không gọi AI Service trực tiếp.

Luồng cần có: đăng nhập demo bằng display_name → xem/tạo conversation → mở history → gửi message với client_message_id UUID → chờ response synchronous → hiển thị user/assistant message → refresh vẫn tải lại history. Request phải gửi cookie bằng credentials: include. Cần xử lý loading, empty, unauthorized, API error, AI timeout, retry và logout.

Trước khi sửa code, hãy đọc file docs/01-phan-cong-giai-doan-1.md và contract hiện có trong repo. Không tự thay API schema. Nếu contract thiếu hoặc mâu thuẫn, báo rõ cho Tú thay vì đoán. Chỉ sửa phạm vi web/ trừ khi Tú yêu cầu khác. Sau khi làm, chạy typecheck/test/build và báo file đã đổi, lệnh đã chạy, kết quả cùng blocker còn lại.
```

## 8. Minh – Core Backend và Database Owner

### 8.1. Nhiệm vụ chính

Xây Core API làm source of truth cho danh tính demo, session, conversation và message; gọi AI Service và bảo vệ ownership.

### 8.2. Deliverable

1. Khởi tạo `backend/` bằng FastAPI.
2. Cấu hình SQLAlchemy async, asyncpg và Alembic.
3. Migration cho bốn bảng tối thiểu.
4. Login/logout/me bằng opaque session cookie.
5. CRUD tối thiểu cho conversation.
6. List messages theo conversation có ownership guard.
7. POST message synchronous theo đúng contract.
8. Lưu user message trước khi gọi AI Service.
9. AI thành công thì lưu assistant message; AI lỗi thì không làm mất user message.
10. Chuẩn hóa error response và `request_id`.
11. API tests cho happy path, authentication, ownership, idempotency và AI failure.

### 8.3. Yêu cầu bắt buộc

- Session token phải ngẫu nhiên; database chỉ lưu hash, không lưu raw token.
- Cookie tối thiểu `HttpOnly`, `SameSite=Lax`; `Secure` cấu hình theo môi trường.
- Không lấy `user_id` từ frontend để quyết định quyền truy cập.
- User A truy cập conversation của User B phải nhận `404` hoặc `403` theo contract thống nhất, không rò nội dung.
- Nội dung rỗng hoặc vượt giới hạn phải bị từ chối.
- AI Service URL và timeout lấy từ environment.
- `client_message_id` phải giúp retry không tạo trùng user message.
- Log có `request_id`, route, status, latency; không log cookie/token.
- Chưa thêm Case hoặc memory schema ở G1.

### 8.4. Trình tự POST message

```text
1. Xác thực session
2. Kiểm tra conversation thuộc user
3. Validate content + client_message_id
4. Tạo/lấy lại user message theo idempotency key
5. Commit user message
6. Gọi AI Service với timeout
7. Nếu thành công: lưu assistant message và trả cặp message
8. Nếu lỗi: đánh dấu trạng thái phù hợp, giữ user message và trả error chuẩn
```

### 8.5. Test Minh phải chứng minh

- Migration chạy trên PostgreSQL trống.
- Login tạo session và `/auth/me` đọc đúng user.
- API chưa đăng nhập bị chặn.
- User A không đọc/ghi conversation User B.
- Gửi cùng `client_message_id` hai lần không tạo hai user messages.
- AI success lưu đủ hai messages.
- AI error/timeout vẫn giữ user message.

### 8.6. Definition of Done của Minh

- OpenAPI chạy và khớp contract đã khóa.
- Migration upgrade thành công từ database sạch.
- Backend tests pass.
- Ghép được với Web của Tú và AI Service của Hoan.
- Không có endpoint nào tin `user_id` do client tự khai báo.

### 8.7. Context giao cho AI coding agent của Minh

```text
Bạn đang hỗ trợ Minh triển khai Core Backend và PostgreSQL cho Giai đoạn 1 của dự án trợ lý hành chính công.

Stack bắt buộc: Python, FastAPI, Pydantic, SQLAlchemy 2 async, asyncpg, Alembic và PostgreSQL. Phạm vi chỉ gồm users, sessions, conversations, messages và orchestration synchronous tới AI Service. Chưa làm RAG, Case, memory summary, Redis, queue, Socket.IO, Qdrant hoặc model local.

Backend xác thực bằng opaque session cookie: raw token chỉ ở cookie, DB lưu token_hash. Frontend không được quyết định user_id. Mọi query conversation/message phải kiểm tra ownership. POST message nhận client_message_id và content, lưu user message trước khi gọi AI Service; nếu AI timeout/lỗi vẫn giữ user message; nếu thành công lưu assistant message. Chuẩn hóa error response có code/message/request_id.

Trước khi sửa code, hãy đọc docs/01-phan-cong-giai-doan-1.md, .env.example và contract trong repo. Không tự đổi schema/API khi chưa báo Minh. Chỉ sửa backend/ và migration liên quan trừ khi Minh yêu cầu khác. Viết pytest cho auth, isolation, idempotency, success và failure. Sau khi làm, chạy migration/test/lint phù hợp và báo file đã đổi, lệnh, kết quả, assumption và blocker.
```

## 9. Hoan – AI Service, Integration và Infrastructure Owner

### 9.1. Nhiệm vụ chính

Giữ contract chung, xây Mock AI Service, dựng môi trường tích hợp và đảm bảo sản phẩm end-to-end luôn chạy được.

### 9.2. Deliverable

1. Tạo `docs/contracts-g1.md` từ mục 5 và khóa với cả nhóm trước khi code sâu.
2. Khởi tạo `ai-service/` bằng FastAPI và provider interface.
3. Implement `MockProvider`, chưa tích hợp OpenAI ở bước đầu.
4. Implement `POST /internal/v1/generate` và `/health`.
5. Mock có cấu hình `success | error | timeout` để test.
6. Tạo/cập nhật `compose.yaml` cho web, backend, ai-service và postgres.
7. Hoàn thiện `.env.example`, không chứa secret thật.
8. Viết README/runbook: dựng mới, migrate, chạy, test, reset môi trường dev an toàn.
9. Tạo smoke test/script kiểm tra toàn luồng.
10. Chủ trì hai lần integration checkpoint và xử lý lệch contract.
11. Chuẩn bị demo script và ghi latency cơ bản.

### 9.3. Yêu cầu bắt buộc

- Provider nằm sau interface để G2/G3 có thể thêm `openai` hoặc `local` mà không đổi Core API.
- G1 mặc định `LLM_PROVIDER=mock` và không yêu cầu API key.
- AI Service validate role/content/max tokens nhưng không làm auth người dùng.
- Mock response ổn định, dễ nhận biết và không giả vờ là tư vấn hành chính chính xác.
- Error/timeout được kích hoạt bằng environment hoặc test dependency override, không bằng câu thần chú trong prompt.
- Compose có healthcheck và dependency hợp lý.
- Không đưa secret vào source control hoặc log.
- Hoan không ôm luôn code UI/backend; nhiệm vụ chính là giữ interface và ghép sản phẩm.

### 9.4. Test Hoan phải chứng minh

- `/health` hoạt động.
- Generate success khớp schema và trả `provider=mock`.
- Error mode trả lỗi dự đoán được.
- Timeout mode giúp backend test timeout.
- Từ môi trường sạch, Compose dựng đủ service.
- Smoke flow: login → create conversation → send → receive → reload history.

### 9.5. Definition of Done của Hoan

- Contract đã được Tú và Minh xác nhận.
- AI Service tests và smoke test pass.
- Một lệnh/runbook dựng được hệ thống.
- Không cần OpenAI key vẫn demo được G1.
- Có checklist và bằng chứng G1 pass/fail, không chỉ quay màn hình giao diện.

### 9.6. Context giao cho AI coding agent của Hoan

```text
Bạn đang hỗ trợ Hoan, người phụ trách AI Service Mock, integration và infrastructure cho Giai đoạn 1 của dự án trợ lý hành chính công.

Kiến trúc G1 gồm React Web → FastAPI Core Backend → FastAPI AI Service, Core Backend lưu PostgreSQL. AI Service có provider interface nhưng G1 chỉ implement MockProvider. Không làm RAG, OpenAI integration, Qwen, fine-tune, Case, Redis, queue hoặc Socket.IO.

Internal API bắt buộc là POST /internal/v1/generate với request_id, messages và max_output_tokens; response có request_id, text, provider=mock, model=mock-v1, usage và latency_ms. Mock cần success/error/timeout qua config hoặc dependency override. Hệ thống chạy bằng Docker Compose với web:3000, backend:8000, ai-service:8001 và PostgreSQL.

Hoan cũng giữ docs/contracts-g1.md, .env.example, compose.yaml, README/runbook và smoke test. Trước khi sửa, đọc docs/00-chien-luoc-trien-khai-tu-nho-den-lon.md và docs/01-phan-cong-giai-doan-1.md. Không tự sửa API contract mà chưa nêu tác động cho cả Tú và Minh. Không đặt secret thật vào file. Sau khi làm, chạy AI tests, Compose validation và smoke test; báo file đổi, lệnh, kết quả, latency cùng blocker.
```

---

# PHẦN III – HỢP: CÁCH BA PHẦN GHÉP LẠI

## 10. Thứ tự triển khai

### Checkpoint 0 – Khóa contract trước khi code sâu

**Kết quả: PASS.** Contract v1.2 phản ánh đúng implementation đã kiểm tra.

Cả ba cùng xác nhận:

- endpoint và JSON schema;
- cookie/session behavior;
- error codes;
- port và environment variables;
- ownership của folder/file.

Hoan ghi bản chốt vào `docs/contracts-g1.md`. Sau thời điểm này, thay đổi contract phải báo cả ba.

### Checkpoint 1 – Ba nhánh chạy độc lập

**Kết quả: PASS.** Code của cả ba owner đã được review và đưa vào nhánh tích hợp.

```text
Tú: Web chạy với temporary API stub cùng schema
Minh: Backend tests chạy với AI client giả cùng schema
Hoan: AI Service Mock và Compose chạy độc lập
```

Stub chỉ phục vụ phát triển song song và phải bị loại khỏi happy path khi tích hợp.

### Checkpoint 2 – Ghép Backend với AI Service

**Kết quả: PASS.** Backend integration tests kiểm tra success, error, timeout,
persistence, request ID và idempotency; live API smoke kiểm tra happy path,
idempotency và persistence xuyên service.

Minh và Hoan chứng minh:

- success lưu hai messages;
- timeout/error không làm mất user message;
- request ID đi xuyên hai service;
- schema thực tế khớp contract.

### Checkpoint 3 – Ghép Web với Core Backend

**Kết quả: PASS.** Playwright kiểm tra login/cookie/CORS, tạo chat, gửi message,
reload history, logout và user isolation trên full Compose stack.

Tú và Minh chứng minh:

- cookie/session hoạt động qua CORS dev;
- conversation và history lấy từ DB thật;
- gửi message nhận Mock AI response;
- refresh và logout đúng.

### Checkpoint 4 – Cả nhóm nghiệm thu G1

**Kết quả: PASS.** Checklist mục 12 có bằng chứng tự động hoặc review phạm vi.

Checklist đã chạy trên full Compose từ môi trường sạch; Playwright browser
smoke là demo thực thi tự động. Video thủ công chỉ quay khi mentor yêu cầu.

## 11. Phân chia ownership file

| Phạm vi | Owner | Người review chính |
|---|---|---|
| `web/**` | Tú | Hoan |
| `backend/**` | Minh | Hoan |
| `ai-service/**` | Hoan | Minh |
| `compose.yaml`, `.env.example`, runbook | Hoan | Tú + Minh |
| `docs/contracts-g1.md` | Cả nhóm; Hoan ghi bản chốt | Tú + Minh xác nhận |

Không sửa file thuộc owner khác mà không báo trước. Nếu cần thay contract, mở một thay đổi nhỏ riêng và ghi rõ người tiêu thụ bị ảnh hưởng.

### 11.1. Branch chính thức

| Thành viên | Branch làm việc |
|---|---|
| Tú | `g1/frontend-tu` |
| Minh | `g1/backend-minh` |
| Hoan | `g1/ai-integration-hoan` |
| Tích hợp G1 | `g1/integration` |

Quy trình:

```text
g1/frontend-tu ────────┐
g1/backend-minh ───────┼→ g1/integration (CI xanh) → PR → main
g1/ai-integration-hoan ┘
```

- Ba branch owner bắt đầu từ cùng baseline và đã được ghép/review trên
  `g1/integration`.
- Pull request duy nhất của lát cắt hoàn chỉnh đi từ `g1/integration` về `main`;
  không merge từng branch owner trực tiếp sau khi integration đã chốt.
- Chỉ merge PR khi toàn bộ gate CI xanh và nhóm đã review diff.
- Sau khi `main` nhận G1, tạo tag baseline rồi mới mở branch G2.
- Không dùng force-push lên `main` hoặc branch của thành viên khác.

## 12. Checklist nghiệm thu G1

| ID | Test | Kết quả cần có | Kết quả/Bằng chứng |
|---|---|---|---|
| G1-01 | Dựng từ môi trường sạch | Tất cả service healthy | **PASS** – full Compose smoke |
| G1-02 | Login demo | Có session cookie và `/me` đúng | **PASS** – API + browser smoke |
| G1-03 | Tạo conversation | Conversation thuộc user hiện tại | **PASS** – API + browser smoke |
| G1-04 | Gửi message | Lưu user và assistant message | **PASS** – Backend + API smoke |
| G1-05 | Refresh | History vẫn còn và đúng thứ tự | **PASS** – API + browser smoke |
| G1-06 | User isolation | User A không xem/sửa dữ liệu User B | **PASS** – Backend + API/browser smoke |
| G1-07 | Duplicate retry | Không tạo trùng user message | **PASS** – Backend + API smoke |
| G1-08 | AI error | User message không bị mất, UI báo lỗi | **PASS** – `ai-service/tests/test_api.py`, `backend/tests/test_api.py`, `web/src/App.test.tsx` |
| G1-09 | AI timeout | Backend timeout có kiểm soát, UI retry được | **PASS** – `ai-service/tests/test_api.py`, `backend/tests/test_api.py`, `web/src/App.test.tsx` |
| G1-10 | Logout | Session hết hiệu lực và UI về login | **PASS** – API + browser smoke |
| G1-11 | Secret check | Không có secret thật trong repo/log | **PASS** – repository hygiene gate |
| G1-12 | Scope check | Không kéo RAG/Case/queue/model local vào G1 | **PASS** – implementation scope review |

G1 chỉ được đánh dấu hoàn thành khi `G1-01` đến `G1-12` đều pass hoặc có ngoại lệ được mentor chấp nhận và ghi lại.

## 13. Kịch bản demo ngắn

```text
1. docker compose --profile full up --build --detach --wait
2. Mở web và đăng nhập bằng user A
3. Tạo conversation, gửi hai tin nhắn và nhận Mock AI response
4. Refresh để chứng minh history từ PostgreSQL
5. Đăng xuất, đăng nhập user B và chứng minh không thấy history user A
6. Đặt MOCK_MODE=error hoặc MOCK_MODE=timeout, chạy
   docker compose up --build --detach --force-recreate ai-service, rồi chứng
   minh message không mất và UI báo lỗi/retry
7. Hiển thị log request_id và latency cơ bản
8. Trả MOCK_MODE=success và recreate AI Service sau demo
```

## 14. Quy tắc dùng AI coding agent cho cả nhóm

1. Luôn đưa cho agent đường dẫn hai file `docs/00-chien-luoc...md` và `docs/01-phan-cong...md`.
2. Chỉ giao một deliverable có thể test trong mỗi lượt.
3. Yêu cầu agent đọc code hiện có trước khi sửa và không tự đổi contract.
4. Yêu cầu báo rõ assumptions, file đã sửa, command đã chạy và test result.
5. Không nhận code chỉ vì “trông hợp lý”; owner phải chạy lại test và review diff.
6. Không để agent thêm dependency/framework ngoài stack đã chốt nếu chưa giải thích nhu cầu.
7. Không dán secret, dataset công ty hoặc PII vào prompt của agent/provider bên ngoài.

## 15. Điểm dừng và bước tiếp theo

G1 đã pass trên `g1/integration`. Việc còn lại để đóng mốc:

- review pull request về `main`, chưa tự merge khi nhóm chưa xác nhận;
- sau khi merge, tạo tag/demo baseline và lưu link CI;
- không tiếp tục trang trí UI;
- chuyển sang G2: snapshot 2–3 thủ tục công khai, gold set 30–50 câu và RAG tối giản có trích nguồn.

G1 không cần dataset hành chính thật. Dataset công khai và RAG bắt đầu ở G2 sau khi đường ống G1 đã ổn định.
