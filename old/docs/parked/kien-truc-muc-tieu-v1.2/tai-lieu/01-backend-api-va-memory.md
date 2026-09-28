# Module 01 – Backend, API và quản lý ngữ cảnh

> File chi tiết cho Product Platform: định danh, session, user/case/conversation, database, queue, context builder, API và realtime.  
> File trung tâm: [Workflow tổng quát](../00-workflow-tong-quat.md).  
> Cách trình bày: **Tổng → Phân → Hợp**.

## Báo cáo cập nhật

| Trường | Nội dung |
|---|---|
| Cập nhật gần nhất | 07/09/2026 |
| Phiên bản | `v1.2` |
| Trạng thái | Thiết kế triển khai MVP |
| Thay đổi lần này | Chốt Case thuộc User và quan hệ Conversation–Case là N–M qua message; hỗ trợ tiếp tục Case cũ từ conversation mới |
| Contract ảnh hưởng | `RequestContext`, `Message`, `CaseResolution`, `MessageCaseLink`, `CaseCard`, `MemoryDelta`, `AnswerPlan`, `VerificationResult` |

---

# PHẦN I – TỔNG: BACKEND LÀM GÌ?

## 1. Mục tiêu

Backend là bộ điều phối và source of truth của trạng thái sản phẩm. Nó phải trả lời chính xác:

```text
Ai đang gửi?
Thuộc tenant/session nào?
Đang nói trong conversation nào?
Tin nhắn hiện tại đang nói tới case thủ tục nào?
Đây là lượt số bao nhiêu?
Được phép đọc/ghi dữ liệu nào?
Phải chạy fast path hay AI pipeline?
Kết quả nào được phép lưu và gửi về web?
```

Qwen không được tự quản lý những việc này và không được truy cập thẳng database.

## 2. Phạm vi module

Bao gồm:

- identity, anonymous session, OTP và quyền truy cập;
- user, case, conversation, message và memory;
- transaction, outbox, queue, lock, retry và idempotency;
- Context Builder và Conversation Orchestrator;
- REST API, Socket.IO và lịch sử;
- tích hợp Case Router, Policy Router, RAG, Procedure Engine, Qwen và Verifier.

Không bao gồm chi tiết ingestion/RAG, huấn luyện model hay thuật toán verifier; chúng nằm ở tài liệu module tương ứng.

## 3. Workflow backend rút gọn

```text
HTTP message
→ auth + ownership
→ DB transaction: message + outbox
→ ACK cho frontend
→ queue
→ lock conversation
→ routing context + Case Router
→ load target-case context
→ Policy Router
→ AI/procedure pipeline
→ verify
→ DB transaction: answer + audit + memory
→ Socket.IO event
→ ACK queue job
```

Database là source of truth. Socket.IO chỉ là kênh realtime; khi reconnect, client phải sync lại từ database.

---

# PHẦN II – PHÂN: THIẾT KẾ CHI TIẾT

## 4. Identity và session

### 4.1. Hai chế độ người dùng

```text
Anonymous
→ visitor/session gắn với một trình duyệt
→ nhớ được khi quay lại trên trình duyệt đó trong TTL

Verified user
→ số điện thoại + OTP
→ user_id chính thức
→ đồng bộ lịch sử giữa thiết bị theo chính sách công ty
```

Tên và số điện thoại nhập tay không đủ để xác minh danh tính. Nếu cho phép truy cập lịch sử xuyên thiết bị, số điện thoại phải qua OTP hoặc cơ chế xác thực tương đương.

### 4.2. Cookie

Cookie chỉ chứa opaque session token:

```text
Name: __Host-session (production) hoặc tên cấu hình
HttpOnly: true
Secure: true ở production
SameSite: Lax hoặc Strict
Path: /
```

Không lưu họ tên, số điện thoại, CCCD, Case Card hoặc conversation trong cookie. Token phải đủ ngẫu nhiên và được hash trước khi lưu DB.

### 4.3. Quyền sở hữu

Backend không tin `user_id`, `case_id` hoặc `conversation_id` từ frontend. Mỗi request phải xác minh:

```text
session còn hiệu lực
→ session thuộc user/tenant nào
→ conversation/case có thuộc đúng user/tenant đó không
→ action có đúng role không
```

Có thể dùng PostgreSQL Row-Level Security hoặc repository guard; contract test phải chứng minh cross-user và cross-tenant leakage bằng 0.

## 5. Mô hình user, case và conversation

```text
Tenant
└── User
    ├── Sessions
    ├── Conversations
    │   └── Messages ── link ── Cases
    └── Cases
        ├── Case facts
        ├── Case summaries
        └── Procedure states
```

- `Case`: một mục tiêu/hồ sơ hành chính kéo dài qua nhiều ngày.
- `Conversation`: một dòng chat người dùng nhìn thấy; có thể lần lượt đề cập nhiều case.
- `MessageCaseLink`: liên kết từng message với case chính và các case được tham chiếu.
- `CaseCard`: snapshot dữ kiện đã biết tại một thời điểm.
- `ProcedureState`: bước đang làm, điều kiện đã đạt, dữ kiện/giấy tờ thiếu và next action.

`Conversation.active_case_id` chỉ là gợi ý về case vừa được nói tới, không phải quan hệ sở hữu và không phải căn cứ tuyệt đối. Căn cứ của một lượt là `messages.primary_case_id`; nếu câu liên hệ nhiều hồ sơ thì dùng thêm `message_case_links` với vai trò `REFERENCED`.

Case nằm trong backend. Frontend không cần trang/danh sách Case riêng; người dùng chỉ thấy lịch sử conversation và nội dung hướng dẫn. Khi user đổi chủ đề, Case Router tạo case mới hoặc chọn case cũ. Nếu không chắc, hệ thống hỏi lại thay vì trộn facts.

Cardinality chính thức:

```text
User 1─N Conversations
User 1─N Cases
Conversation 1─N Messages
Message N─M Cases qua message_case_links

Conversation–Case là N–M suy ra qua Messages.
```

Nhờ đó:

- một conversation có thể chứa nhiều case;
- một case có thể được nhắc và tiếp tục trong nhiều conversation;
- xóa/đóng conversation không mặc định xóa Case;
- quyền truy cập Case luôn kiểm bằng `tenant_id + user_id`, không kiểm chỉ bằng conversation;
- `case_id` là định danh hồ sơ cụ thể, còn `procedure_code` chỉ là loại thủ tục.

Một user có thể có nhiều Case cùng `procedure_code`, ví dụ khai sinh cho hai người con. Case cần descriptor rút gọn như `subject_label`, `opened_at`, `status`, `last_activity_at` và summary; nếu không phân biệt chắc thì Case Router hỏi lại.

### 5.1. Case Router

Router nhận một `RoutingContext` nhỏ:

```text
current message
recent conversation turns
conversation.active_case_id như một hint
danh mục case rút gọn của đúng user trên mọi conversation:
  case_id + procedure title/code + subject label + status
  + opened_at/updated_at + short summary/aliases
```

Nó trả `CaseResolution`:

```json
{
  "status": "EXPLICIT_REFERENCE",
  "primary_case_id": "case_cccd_uuid",
  "referenced_case_ids": [],
  "create_new_case": false,
  "requires_clarification": false,
  "reason_codes": ["MENTIONED_PROCEDURE_CCCD"]
}
```

Các status:

```text
NEW_CASE
EXPLICIT_REFERENCE
ACTIVE_CASE_MATCH
ROUTER_MATCH
MULTI_CASE_REFERENCE
NO_CASE_REQUIRED
AMBIGUOUS
```

Quy tắc quan trọng:

- Nêu rõ “hồ sơ CCCD của tôi” có thể route thẳng tới case CCCD cũ.
- Nêu một mục tiêu mới như “tôi muốn làm khai sinh” tạo case mới nếu chưa có case phù hợp.
- Mở conversation mới rồi nói “tiếp tục hồ sơ CCCD hôm trước” vẫn tìm Case cũ trong user-wide case directory.
- Có hai Case cùng thủ tục thì không chọn chỉ bằng `procedure_code`; phải dựa thêm subject/thời gian/summary hoặc hỏi lại.
- “Tôi còn thiếu gì?” chỉ dùng active-case hint khi recent context đủ rõ; có nhiều ứng viên hợp lý thì phải hỏi lại.
- Một câu như “CCCD của tôi có dùng cho hồ sơ khai sinh không?” có case khai sinh là `PRIMARY` và case CCCD là `REFERENCED`.
- Chỉ sau khi resolution được xác nhận mới tải full facts/summary của case; không đưa tất cả case histories vào prompt.

## 6. RequestContext và message lifecycle

### 6.1. RequestContext

```json
{
  "schema_version": "1.0",
  "tenant_id": "tenant_uuid",
  "user_id": "user_uuid",
  "session_id": "session_uuid",
  "conversation_id": "conversation_uuid",
  "target_case_id": "case_uuid_or_null_after_routing",
  "referenced_case_ids": [],
  "case_resolution": "EXPLICIT_REFERENCE_or_other_status",
  "message_id": "message_uuid",
  "turn_seq": 42,
  "trace_id": "trace_uuid"
}
```

Trước Case Router, `target_case_id` là `null`; backend điền nó sau routing. Giá trị case do frontend gửi chỉ là hint và phải được kiểm tra ownership. Context sau resolution đi xuyên worker, AI pipeline, telemetry và audit.

### 6.2. Message

Mỗi message tối thiểu có:

```text
message_id
tenant_id / user_id / conversation_id
primary_case_id (nullable cho tới sau routing)
case_resolution
client_request_id
turn_seq
role
content
status
context_version
created_at / completed_at
```

Unique constraint đề xuất:

```text
(user_id, conversation_id, client_request_id)
(conversation_id, turn_seq)
```

Trạng thái:

```text
RECEIVED → QUEUED → PROCESSING → COMPLETED
                              ├→ FAILED
                              └→ CANCELLED
```

## 7. Transactional outbox và queue

### 7.1. Vì sao cần outbox?

Nếu API lưu message rồi crash trước khi publish queue, message sẽ bị “mắc kẹt”. Nếu publish trước rồi DB fail, worker có job không có dữ liệu. Giải pháp:

```text
Một DB transaction:
INSERT message
INSERT outbox_event
COMMIT

Outbox publisher:
đọc event chưa publish
→ publish Redis Stream
→ đánh dấu published
```

### 7.2. Thứ tự và song song

```text
Conversation A: A1 → A2 → A3 bắt buộc tuần tự
Conversation B: B1 → B2 bắt buộc tuần tự

A và B có thể xử lý song song.
```

Worker lấy distributed lock theo `conversation_id`, không khóa toàn cục. Inference server có thể continuous-batch các job từ nhiều conversation.

### 7.3. At-least-once và idempotency

Worker chỉ ACK sau khi transaction kết quả đã commit. Khi retry:

1. Kiểm tra message đã có kết quả hoàn chỉnh chưa.
2. Kiểm tra `turn_seq` có phải lượt kế tiếp không.
3. Không ghi duplicate answer/memory event.
4. Dùng exponential backoff có giới hạn.
5. Hết retry thì chuyển DLQ và phát `assistant.failed`.

Lock theo `conversation_id` bảo đảm thứ tự timeline. Nếu cùng một case được tham chiếu từ hai conversation đồng thời, cập nhật case dùng `case_version` optimistic concurrency hoặc lock ngắn theo `case_id`; khi conflict phải rebuild context và không ghi đè facts âm thầm.

## 8. Bộ nhớ dài hạn

### 8.1. Sáu tầng

| Tầng | Vai trò |
|---|---|
| Raw messages | Bản gốc theo retention policy |
| Recent window | Một số lượt gần nhất theo token budget |
| Case summary | Tóm tắt riêng từng case, có sequence range |
| Structured facts | Dữ kiện như địa phương, vai trò, giấy tờ đã khai |
| User profile | Tên xưng hô/ngôn ngữ/địa phương mặc định khi có consent |
| Procedure knowledge | Kho công khai riêng, không phải memory cá nhân |

Summary là cache để dựng context, không phải source of truth. Fact phải truy được về `source_message_id`.

### 8.2. Fact lifecycle

```text
EXTRACTED → USER_CONFIRMED
          → CONFLICT
          → SUPERSEDED
```

Đối với giấy tờ người dùng tự khai, có thể dùng `REPORTED`; không tự gắn `VERIFIED` nếu hệ thống chưa thực sự kiểm chứng tài liệu.

### 8.3. MemoryDelta

Qwen chỉ được đề xuất:

```json
{
  "schema_version": "1.0",
  "case_id": "case_uuid",
  "add_facts": [
    {
      "key": "documents_owned",
      "value": "CCCD",
      "source_message_id": "msg_uuid",
      "confidence": null
    }
  ],
  "conflicts": [],
  "next_action": "ASK_PROCEDURE_INTENT"
}
```

Backend kiểm schema, allowlist field, provenance, normalization và conflict trước khi ghi.

## 9. Context Builder

Context được dựng hai pha.

### 9.1. Routing context

```text
Current message
+ vài recent turns
+ active-case hint
+ case directory rút gọn của đúng user
```

Pha này chỉ đủ để Case Router chọn/tạo/hỏi lại, không nạp full memory của mọi case.

### 9.2. Target-case context

Sau khi Case Router chốt `primary_case_id`, mỗi lượt chỉ ghép:

```text
1. System policy + output schema
2. Current user message
3. Target case/procedure state
4. Confirmed/reported facts liên quan
5. Unresolved questions và expected field
6. Recent messages vừa đủ
7. Relevant case summary
8. Evidence/ProcedureBundle đúng facet khi pipeline đã retrieval
```

Nếu có `referenced_case_ids`, chỉ lấy đúng facts được yêu cầu từ các case phụ và gắn namespace/provenance rõ; không merge chúng vào Case Card chính.

Không đưa toàn bộ raw history vào prompt. Baseline:

```text
typical context: 2K–6K tokens
hard cap ban đầu: 8K tokens
summary: có covered_from_seq / covered_to_seq
```

Summary worker lưu model/prompt version và source message IDs. Khi một fact bị user sửa, summary liên quan phải được refresh hoặc đánh dấu stale.

## 10. Case Router, Conversation Orchestrator và Policy Router

Orchestrator là state machine, không phải một prompt dài:

```text
BUILD_ROUTING_CONTEXT
→ RESOLVE_OR_CREATE_CASE
→ LOAD_TARGET_CASE_CONTEXT
→ SELECT_PROCESSING_ROUTE
→ EXTRACT_OR_VALIDATE_FACTS
→ CHECK_MISSING_FACTS
→ RESOLVE_PROCEDURE
→ FETCH_PROCEDURE_AND_EVIDENCE
→ BUILD_ANSWER_PLAN
→ GENERATE_OPTIONAL_TEXT
→ VERIFY
→ COMMIT
→ EMIT
```

Case Router trả lời **đang nói tới hồ sơ nào**. Policy Router trả lời **cần chạy pipeline nặng đến mức nào**. Policy Router MVP dùng rule dựa trên:

- target case/procedure đã được resolution chưa;
- hệ thống có đang chờ một field không;
- message có match alias/format của field đó không;
- exact procedure lookup có duy nhất một kết quả không;
- user hỏi facet nào;
- có conflict với fact cũ không.

Không gọi Qwen khi backend có thể cập nhật fact hoặc đọc một field đã biết bằng code.

## 11. Core API v1

### 11.1. Identity/session

```text
POST   /api/v1/auth/anonymous
POST   /api/v1/auth/otp/request
POST   /api/v1/auth/otp/verify
POST   /api/v1/auth/logout
GET    /api/v1/me
DELETE /api/v1/me/data
```

### 11.2. Conversation/message

```text
POST   /api/v1/conversations
GET    /api/v1/conversations
GET    /api/v1/conversations/{id}/messages
POST   /api/v1/conversations/{id}/messages
GET    /api/v1/me/memory
PATCH  /api/v1/me/memory/facts/{fact_id}
DELETE /api/v1/me/memory/facts/{fact_id}
```

Case CRUD là service/repository nội bộ trong MVP; frontend không cần quản lý thực thể kỹ thuật này. API privacy cho phép user xem/sửa/xóa dữ kiện mà không bắt họ hiểu `case_id`.

### 11.3. Evidence và admin knowledge

```text
GET    /api/v1/evidence/{evidence_id}
POST   /api/v1/admin/uploads
GET    /api/v1/admin/uploads/{id}/status
GET    /api/v1/admin/indexes
POST   /api/v1/admin/indexes/{version}/activate
```

Mọi mutation nhận `Idempotency-Key` hoặc `client_request_id`. Pagination dùng cursor, không tải toàn bộ lịch sử trong một response.

## 12. Response envelope

```json
{
  "request_id": "trace_uuid",
  "data": {},
  "error": null,
  "meta": {
    "schema_version": "1.0"
  }
}
```

Error code máy đọc được, ví dụ:

```text
AUTH_REQUIRED
FORBIDDEN_RESOURCE
INVALID_MESSAGE
CONVERSATION_BUSY
RATE_LIMITED
PIPELINE_TIMEOUT
INSUFFICIENT_EVIDENCE
INTERNAL_ERROR
```

Không trả stack trace, prompt nội bộ hoặc secret cho client.

## 13. Socket.IO

Event đề xuất:

```text
message.ack
message.status
assistant.delta
assistant.completed
assistant.failed
history.sync
upload.status
```

Room:

```text
user:{user_id}
conversation:{conversation_id}
```

Chỉ join room sau auth + ownership. Mỗi event cần `event_seq`, `message_id`, `conversation_id` và `trace_id`. Frontend giữ `last_event_seq`; khi mất event hoặc reconnect thì gọi history API để đồng bộ.

## 14. Data model tối thiểu

```text
tenants
users
sessions
otp_challenges
cases
conversations
messages
message_case_links
case_facts
case_summaries
procedure_states
memory_events
message_jobs
outbox_events
evidence_audits
access_audits
```

Các bảng tri thức như procedures/document_versions/index_versions thuộc module RAG nhưng liên kết qua ID, không foreign-key xuyên service nếu sau này tách service.

Quan hệ chính:

```text
User 1─N Conversations
User 1─N Cases
Conversation 1─N Messages
Message N─M Cases qua message_case_links
Case 1─N Facts / Summaries / ProcedureStates
Conversation.active_case_id ─→ Case (nullable hint)
```

Case không bị cascade-delete chỉ vì một conversation bị xóa/ẩn. Retention/delete phải xử lý liên kết, message và Case theo policy rõ ràng để không vô tình xóa hồ sơ vẫn được conversation khác tham chiếu.

## 15. Transaction boundary quan trọng

### Nhận message

```text
transaction:
  authorize
  allocate turn_seq
  insert message
  insert outbox event
commit
```

### Hoàn thành message

```text
transaction:
  compare expected context_version
  compare/lock target case_version nếu có mutation
  persist CaseResolution + message_case_links
  insert assistant message
  insert evidence audit
  apply validated memory delta
  update procedure state
  mark user message COMPLETED
  insert realtime outbox event
commit
```

Optimistic version giúp phát hiện context thay đổi khi hai tab cùng thao tác.

## 16. Privacy và security

- Mã hóa transport bằng HTTPS/TLS.
- Secret không ghi trong source/log; production dùng secret manager.
- Log redact số điện thoại, CCCD, token và tài liệu cá nhân.
- Phân quyền admin upload/activate index.
- Rate limit theo session/user/IP có cân nhắc NAT.
- CSRF protection nếu dùng cookie auth cho mutation.
- File user và knowledge admin phải tách namespace/quyền.
- Có export/delete và retention job theo chính sách công ty.
- Audit mọi lần xem evidence hoặc thay đổi knowledge version.

---

# PHẦN III – HỢP: TRIỂN KHAI VÀ NGHIỆM THU

## 17. Thứ tự triển khai

### B0 – Schema và repository

- Tạo migration cho identity, case, conversation, messages, message_case_links và outbox.
- Định nghĩa Pydantic/JSON Schema cho contract v1.
- Viết ownership guard và repository tests.

### B1 – Walking skeleton

- Anonymous session.
- POST message lưu DB.
- Outbox → Redis Stream → mock worker.
- Socket event và history after refresh.

### B2 – Ordering và reliability

- `turn_seq`, conversation lock, idempotency và retry.
- DLQ, timeout, cancellation và reconnect sync.

### B3 – Case và memory

- Case Router/CaseResolution, Case Card, facts, summary và Context Builder hai pha.
- Một conversation chứa ít nhất ba case độc lập và route lại được case cũ.
- Một conversation mới truy vết và tiếp tục được Case đã tạo ở conversation trước.
- Hai Case cùng procedure code vẫn được phân biệt hoặc yêu cầu làm rõ.

### B4 – AI integration

- Policy Router và interfaces tới RAG/model/verifier.
- Commit AnswerPlan, evidence audit và memory delta an toàn.

### B5 – Hardening

- OTP, consent, RLS/guard, retention, export/delete.
- Load/security/failure tests và telemetry.

## 18. Quality gate backend

| Hạng mục | Điều kiện nghiệm thu |
|---|---|
| Multi-user | Cross-user/cross-tenant leakage = 0 |
| Ordering | Không đảo lượt trong cùng conversation |
| Idempotency | Retry/two tabs không tạo duplicate message/answer |
| Reliability | Worker chết trước/sau commit đều recovery đúng |
| Memory | Fact có provenance; conflict không bị ghi đè âm thầm |
| Case routing | Mỗi message gắn đúng primary/referenced cases; mơ hồ phải hỏi lại |
| Resume | Trong cùng conversation, quay lại đúng case cũ và next action qua nhiều ngày |
| Context | Không vượt budget; không đưa dữ liệu case khác |
| Socket | Reconnect/replay đúng; room authorization đúng |
| Privacy | Cookie/log/API không rò PII/secret |
| Performance | Queue wait và API P95 đạt SLA được chốt |

## 19. Test bắt buộc

1. Hai user hỏi đồng thời với dữ kiện gần giống nhau.
2. Trong một conversation: hỏi CCCD → khai sinh → khai tử → quay lại hỏi CCCD.
3. Hai tab gửi cùng `client_request_id`.
4. Gửi A2 khi A1 vẫn đang xử lý.
5. Worker chết trước ACK và sau DB commit.
6. Socket ngắt rồi reconnect từ `last_event_seq`.
7. User sửa một fact đã xác nhận.
8. Summary bỏ sót hoặc bóp méo fact.
9. Cookie hết hạn/bị thu hồi hoặc thiết bị dùng chung.
10. User yêu cầu export/xóa dữ liệu.
11. Một message liên hệ hai case nhưng facts không bị merge.
12. Hai conversation đồng thời cập nhật cùng case và tạo conflict `case_version`.
13. Conversation mới hỏi “tiếp tục hồ sơ hôm trước” và resume đúng Case cũ.
14. User có hai hồ sơ khai sinh khác nhau; câu không nêu subject phải hỏi lại.

## 20. Definition of Done module

- API contract v1 và migration chạy tự động.
- Ownership guard có integration tests.
- Message + outbox atomic.
- CaseResolution và message_case_links được persist/audit.
- Queue theo conversation, retry idempotent và DLQ hoạt động.
- Context Builder hai pha có token budget, namespace và provenance.
- Memory delta chỉ được commit sau validation.
- REST history và Socket.IO recovery thống nhất.
- Trace xuyên suốt từ HTTP đến answer/audit.
- Có tài liệu chạy local, seed data và test command.
