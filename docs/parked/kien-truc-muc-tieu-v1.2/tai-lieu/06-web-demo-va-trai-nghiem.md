# Module 06 – Web demo và trải nghiệm người dùng

> File chi tiết cho frontend: màn hình, trạng thái, lịch sử conversation, evidence, upload admin và realtime; Case là chi tiết nội bộ của backend.  
> File trung tâm: [Workflow tổng quát](../00-workflow-tong-quat.md).  
> Cách trình bày: **Tổng → Phân → Hợp**.

## Báo cáo cập nhật

| Trường | Nội dung |
|---|---|
| Cập nhật gần nhất | 07/09/2026 |
| Phiên bản | `v1.1` |
| Trạng thái | Đặc tả web demo MVP; visual design chưa khóa |
| Thay đổi lần này | Bỏ UI My Cases/active-case; chốt một conversation có thể chứa nhiều case ẩn và backend tự route từng message |
| Contract ảnh hưởng | REST API v1, Socket.IO events, `AnswerPlan`, inline clarification/memory và upload state |

---

# PHẦN I – TỔNG: WEB PHẢI CHỨNG MINH ĐIỀU GÌ?

## 1. Mục tiêu

Web demo không chỉ là một ô chat. Nó phải giúp mentor nhìn thấy năm năng lực của sản phẩm:

1. Biết user/session nào đang sử dụng.
2. Giữ một lịch sử conversation tự nhiên trong khi backend vẫn tách đúng nhiều case nghiệp vụ.
3. Hiển thị hệ thống đang xử lý đến bước nào.
4. Trả checklist/bước tiếp theo cùng nguồn kiểm chứng.
5. Cho admin đưa dữ liệu vào RAG và theo dõi version/status.

## 2. Nguyên tắc ranh giới

Frontend:

- nhận input và gửi `client_request_id`;
- hiển thị dữ liệu/trạng thái backend trả về;
- giữ cursor/event offset phục vụ sync;
- hỗ trợ người dùng xác nhận/sửa facts.

Frontend không:

- tin cookie để tự quyết định user là ai;
- tự suy luận, tạo, chuyển hoặc quản lý Case;
- tự tính checklist;
- tự ghép citation;
- lưu secret/PII nhạy cảm trong localStorage;
- coi Socket.IO là source of truth.

## 3. Bố cục demo chính

```text
┌────────────────┬───────────────────────────┬────────────────────┐
│ Conversations  │ Chat + trạng thái xử lý   │ Chi tiết + Evidence│
│                │                           │                    │
└────────────────┴───────────────────────────┴────────────────────┘

Các trang Identity, Privacy, Upload/Admin và Operations là route/tab riêng.
```

Mobile có thể chuyển ba cột thành drawer/tab; desktop ưu tiên thấy chat và evidence/chi tiết hướng dẫn đồng thời. Không có menu Case riêng.

---

# PHẦN II – PHÂN: MÀN HÌNH VÀ LUỒNG

## 4. Bảy khu vực chức năng

### 4.1. Identity & Consent

- anonymous session status;
- tên hiển thị tùy chọn;
- số điện thoại + OTP nếu đăng nhập;
- consent lưu history/profile;
- thông báo rõ phạm vi và dữ liệu được lưu.

### 4.2. Chat

- message composer;
- lịch sử message;
- streaming answer;
- processing stages;
- citation/source links;
- nút copy, retry an toàn, xem chi tiết;
- clarification UI cho 1–3 câu hỏi.

### 4.3. Hướng dẫn thủ tục trong câu trả lời

- tên thủ tục đang được trả lời khi cần làm rõ;
- checklist giấy tờ đã khai/còn thiếu;
- điều kiện, nơi nộp, phí, thời hạn và bước tiếp theo;
- cảnh báo và nguồn tương ứng;
- hiển thị như các block của câu trả lời, không phải màn hình quản lý Case.

### 4.4. My Documents

Chỉ làm nếu công ty cho phép user upload tài liệu cá nhân:

- upload/status;
- quyền dùng và retention;
- xem/xóa;
- phân biệt `REPORTED` với `VERIFIED`.

Không trộn với kho tri thức admin.

### 4.5. Memory & Privacy

- xem fact hệ thống đang nhớ;
- nguồn message tạo fact;
- xác nhận, sửa hoặc yêu cầu quên;
- export/delete history theo policy;
- giải thích anonymous cookie và đăng nhập.

### 4.6. Knowledge Admin

- upload/import nguồn chính thức;
- metadata, checksum và provenance;
- ingestion state/error;
- procedure/index version;
- validation result;
- activate/rollback theo role.

### 4.7. Operations & Evaluation

- queue lag;
- active model/index/procedure version;
- stage latency và error rate;
- verifier/answer status;
- coverage và evaluation summary.

Trang này phục vụ demo/mentor/admin, không mở cho citizen.

## 5. Luồng chat

```text
User nhập message
→ frontend tạo client_request_id
→ POST message
→ nhận ACK/message_id
→ render user message trạng thái QUEUED
→ nhận Socket.IO processing events
→ stream assistant delta nếu có
→ nhận assistant.completed với AnswerPlan/evidence
→ render blocks theo type
→ cập nhật history và evidence/chi tiết của answer
```

Nếu POST timeout nhưng chưa biết server đã nhận chưa, frontend retry cùng `client_request_id`; không tạo ID mới.

## 6. Trạng thái trải nghiệm

Thông điệp người dùng dễ hiểu:

| Backend stage | UI copy gợi ý |
|---|---|
| `QUEUED` | Đã nhận câu hỏi |
| `RESOLVING_CASE` | Đang xác định nội dung bạn đang hỏi |
| `BUILDING_CONTEXT` | Đang xem lại thông tin liên quan |
| `RESOLVING_PROCEDURE` | Đang xác định thủ tục phù hợp |
| `RETRIEVING_EVIDENCE` | Đang tìm thông tin từ nguồn chính thức |
| `VERIFYING` | Đang kiểm tra lại hướng dẫn và nguồn |
| `COMPLETED` | Hiển thị câu trả lời |
| `FAILED` | Không thể hoàn tất; cho retry/sync |

Không hiển thị chain-of-thought hoặc nội dung prompt nội bộ.

## 7. Answer rendering

Frontend render `AnswerPlan.blocks`, không parse tùy tiện từ Markdown để tìm checklist/citation.

Block types đề xuất:

```text
INTRO
CLARIFICATION
DOCUMENT_CHECKLIST
CONDITIONS
FEES
PROCESSING_TIME
SUBMISSION_PLACE
NEXT_STEPS
WARNING
SOURCES
ESCALATION
```

Mỗi critical block hiển thị:

- dữ liệu canonical từ backend;
- điều kiện nếu có;
- trạng thái reported/confirmed/verified;
- source indicator mở evidence panel.

## 8. Evidence panel

Mỗi source item:

```text
Tên procedure/văn bản
Procedure/document version
Facet hoặc vị trí nguồn
Trích đoạn giới hạn cần thiết
Ngày hiệu lực và lần kiểm tra
URL chính thức
Verification status
```

Không để Qwen tự tạo URL. Click source gọi `GET /api/v1/evidence/{id}` sau kiểm quyền/phạm vi công khai.

Nếu source `unresolved/wrong_version/inapplicable`, answer không được hiển thị như đã xác minh.

## 9. Dữ kiện và checklist hiển thị trong câu trả lời

Frontend không hiển thị `case_id`, Case Card thô, Case Router status hoặc trang My Cases. Khi một fact/checklist liên quan trực tiếp đến câu trả lời, UI có thể hiển thị nhãn dễ hiểu và cho user sửa qua API memory; backend vẫn là source of truth.

Phân biệt rõ:

```text
Đã khai báo       = REPORTED
Đã xác nhận       = USER_CONFIRMED
Có mâu thuẫn       = CONFLICT
Không còn dùng     = SUPERSEDED
Hệ thống xác minh  = VERIFIED (chỉ khi thật sự có quy trình xác minh)
```

Field thiếu chỉ hiển thị dưới dạng câu hỏi làm rõ theo thứ tự quan trọng. User có thể sửa fact; frontend gửi mutation, không tự sửa local source of truth.

## 10. Multi-case UX

Việc tạo/chọn case diễn ra ngầm ở backend. Nếu user nói rõ mục tiêu, frontend không hỏi họ tạo hay chuyển Case. Ví dụ trong cùng một conversation:

```text
Tuần 1: “Tôi muốn cấp lại CCCD.”
Tuần 2: “Tôi muốn đăng ký khai sinh cho con.”
Tháng sau: “Tôi muốn làm giấy khai tử.”
Sau đó: “Hồ sơ CCCD của tôi còn thiếu gì?”
```

Frontend vẫn hiển thị một timeline chat. Backend liên kết từng message với đúng case và tải đúng memory. Chỉ khi câu hỏi thật sự mơ hồ mới hiện clarification tự nhiên:

```text
“Bạn đang hỏi về thủ tục cấp lại CCCD, đăng ký khai sinh
hay đăng ký khai tử?”
```

Không dùng từ kỹ thuật “Case”, “active case”, “switch case” với người dân.

## 11. Clarification UX

- hỏi tối đa 1–3 decisive facts;
- ưu tiên control có cấu trúc nếu enum rõ, nhưng luôn có đường nhập tự do;
- giải thích ngắn vì sao cần dữ kiện;
- không bắt user nhập lại fact đã có;
- câu trả lời của user vẫn được lưu như một message bình thường.

## 12. Socket.IO contract

Event chung:

```json
{
  "event_seq": 101,
  "event_type": "message.status",
  "conversation_id": "conv_uuid",
  "message_id": "msg_uuid",
  "trace_id": "trace_uuid",
  "payload": {},
  "created_at": "2026-09-07T10:00:00Z"
}
```

Event types:

```text
message.ack
message.status
assistant.delta
assistant.completed
assistant.failed
history.sync
upload.status
```

Client giữ `last_event_seq`. Khi gap/reconnect:

1. dừng áp dụng delta không chắc chắn;
2. gọi REST history sync;
3. reconcile theo message ID/status;
4. tiếp tục từ offset mới.

## 13. REST state management

REST dùng cho:

- bootstrap identity/session;
- danh sách conversation;
- history pagination;
- submit mutation;
- full answer/evidence;
- reconnect sync;
- upload/admin actions.

Socket dùng cho cập nhật nhanh, không thay REST/source of truth.

## 14. Loading, empty và error states

Phải thiết kế trước:

- chưa có conversation;
- anonymous session mới;
- message queued lâu;
- Socket disconnected nhưng REST còn hoạt động;
- pipeline timeout/failed;
- clarification required;
- insufficient evidence/out of scope;
- no active procedure/index;
- upload rejected/failed;
- user không có quyền admin;
- evidence URL/source unavailable.

Không dùng một thông báo chung “Có lỗi xảy ra” cho mọi tình huống; hiển thị mã/lựa chọn hành động phù hợp nhưng không lộ internals.

## 15. Privacy trên frontend

- không lưu access token/PII nhạy cảm trong localStorage nếu dùng HttpOnly cookie;
- không đưa raw message/phone/CCCD vào analytics;
- che dữ liệu nhạy cảm trong preview/log lỗi;
- confirm trước delete/export/logout trên shared device;
- CSP, output escaping và URL allowlist chống XSS;
- upload kiểm type/size ở client chỉ để UX, server vẫn validate lại.

## 16. Accessibility và ngôn ngữ

- keyboard navigation và focus cho composer/dialog;
- status streaming dùng `aria-live` hợp lý, tránh đọc từng token gây nhiễu;
- contrast và trạng thái không chỉ dựa vào màu;
- tiếng Việt rõ, tránh jargon pháp lý/kỹ thuật;
- ngày, tiền và địa danh theo định dạng nhất quán;
- citation và cảnh báo đọc được trên mobile.

## 17. Demo script đề xuất

1. User A mở một conversation và hỏi về cấp lại CCCD; hệ thống trả lời có nguồn.
2. Trong cùng conversation, user chuyển sang đăng ký khai sinh; backend tự tạo/chọn case mới.
3. User tiếp tục hỏi khai tử; backend giữ case thứ ba độc lập.
4. User hỏi lại “Hồ sơ CCCD của tôi còn thiếu gì?”; hệ thống phục hồi đúng facts CCCD.
5. User hỏi mơ hồ “Tôi còn thiếu gì?”; hệ thống yêu cầu chọn thủ tục bằng ngôn ngữ tự nhiên.
6. Refresh/ngày hôm sau: một timeline chat vẫn còn và routing vẫn đúng.
7. Mở User B ở trình duyệt khác và chứng minh cách ly.
8. Admin upload procedure version mới, xem staging/test/activate.
9. Hỏi lại và chứng minh source/version mới được dùng.
10. Ngắt Socket rồi reconnect/history sync.

---

# PHẦN III – HỢP: TRIỂN KHAI VÀ NGHIỆM THU

## 18. Thứ tự triển khai

### W0 – Design contract

- Route map và low-fidelity wireframe.
- REST/Socket types và AnswerPlan blocks.
- Empty/loading/error states.

### W1 – Walking skeleton

- Anonymous session.
- Conversation list + chat composer/history.
- POST message, ACK và mock stream.
- Refresh/history sync.

### W2 – Case routing ẩn và memory

- Backend route nhiều case trong một conversation; frontend không có Case CRUD.
- Inline clarification và memory fact confirm/edit/forget bằng ngôn ngữ người dùng.

### W3 – Answer và evidence

- Structured blocks, checklist, next step và sources.
- Clarification/abstain/escalation states.

### W4 – Admin/operations

- Upload status, version activate/rollback.
- Coverage/latency/queue/verifier dashboard tối thiểu.

### W5 – Hardening

- OTP/consent/privacy.
- Responsive/accessibility/security/E2E tests.

## 19. Test bắt buộc

- retry POST dùng cùng client request ID;
- duplicate/out-of-order Socket events;
- reconnect có event gap;
- refresh giữa lúc message processing;
- user đổi chủ đề hoặc nhắc lại case cũ trong lúc job trước đang chạy;
- evidence/answer status không nhất quán;
- permission denied cho admin route;
- delete/export/logout;
- long text, Unicode tiếng Việt và mobile layout;
- XSS/prompt-like content hiển thị như text an toàn.

## 20. Quality gate frontend

- UI giữ đúng một conversation timeline; answer không dùng nhầm memory giữa các case backend.
- State cuối sau reconnect khớp database.
- Critical facts/citation render từ structured response.
- Không hiển thị answer failed verifier như verified.
- User phân biệt được reported và verified.
- Không lộ token/PII trong storage/log/URL.
- Luồng demo hoàn thành được bằng keyboard và mobile cơ bản.

## 21. Definition of Done module

- Bảy khu vực có route/role rõ ràng.
- Chat/history/reconnect chạy end-to-end.
- Multi-case routing diễn ra trong backend; frontend chỉ hiển thị clarification/answer và memory controls cần thiết.
- Có đầy đủ loading/empty/error/clarification states.
- Admin upload/version flow hoạt động theo quyền.
- E2E test bao phủ demo script và privacy basics.
