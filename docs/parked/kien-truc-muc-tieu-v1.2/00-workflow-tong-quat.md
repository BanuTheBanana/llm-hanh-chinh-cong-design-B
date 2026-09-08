# Workflow tổng quát – Trợ lý hành chính công lightweight

> **File trung tâm của dự án.** Đọc file này trước khi đọc các tài liệu module.  
> Phạm vi: toàn bộ sản phẩm, từ người dùng gửi câu hỏi đến lúc trả lời, lưu ngữ cảnh, cập nhật tri thức và đánh giá hệ thống.  
> Cách trình bày: **Tổng → Phân → Hợp**.

## Báo cáo cập nhật

| Trường | Nội dung |
|---|---|
| Cập nhật gần nhất | 07/09/2026 |
| Phiên bản | `v1.2` |
| Trạng thái | Kiến trúc mục tiêu đã chốt tạm thời; sẽ hiệu chỉnh khi nhận dữ liệu và SLA từ công ty |
| Thay đổi lần này | Chốt mô hình kết hợp: Case thuộc User; Conversation và Case độc lập, liên kết N–M qua từng message; hỗ trợ truy vết case qua conversation khác |
| Ảnh hưởng | Backend, RAG/data, model, verifier/evaluation, hạ tầng và web demo |

### Quy tắc cập nhật tài liệu

Khi có yêu cầu hoặc quyết định mới:

1. Cập nhật file trung tâm này trước: mục quyết định, workflow hoặc contract bị ảnh hưởng.
2. Tăng phiên bản và thêm một dòng vào **Báo cáo cập nhật** ở đầu file này.
3. Cập nhật đúng file module liên quan và báo cáo thay đổi ở đầu module đó.
4. Nếu thay đổi schema/API, cập nhật cả producer, consumer, migration và contract test.
5. Không chép toàn bộ chi tiết module vào file trung tâm; file này chỉ giữ bức tranh chung và liên kết.
6. Quyết định cũ không còn hiệu lực được chuyển vào `docs/archive/`, không xóa mất lịch sử.

### Bản đồ tài liệu

| Tài liệu | Nguồn sự thật cho nội dung nào? |
|---|---|
| **File hiện tại** | Phạm vi, workflow toàn hệ thống, ranh giới module, contract chung, lộ trình và Definition of Done |
| [01 – Backend, API và memory](tai-lieu/01-backend-api-va-memory.md) | Định danh, session, user/case/conversation, database, queue, context, API và realtime |
| [02 – RAG và dữ liệu thủ tục](tai-lieu/02-rag-va-du-lieu-thu-tuc.md) | Data readiness, Procedure Store, ingestion, retrieval, reranker, version và evidence |
| [03 – Model LLM lightweight](tai-lieu/03-model-llm-lightweight.md) | Vai trò Qwen, structured output, prompting, SFT/QLoRA, quantization và inference |
| [04 – Kiểm chứng, an toàn và đánh giá](tai-lieu/04-kiem-chung-an-toan-va-danh-gia.md) | Evidence Gate, Procedure Engine, AnswerPlan, verifier, test set và metrics |
| [05 – Hạ tầng, triển khai và vận hành](tai-lieu/05-ha-tang-trien-khai-va-van-hanh.md) | Docker, biến môi trường, service topology, bảo mật, quan sát và benchmark tải |
| [06 – Web demo và trải nghiệm](tai-lieu/06-web-demo-va-trai-nghiem.md) | Màn hình, trạng thái UI, Socket.IO, lịch sử chat, citation và trang admin |

---

# PHẦN I – TỔNG: TOÀN CẢNH SẢN PHẨM

## 1. Bài toán

Xây dựng trợ lý hành chính công có thể:

- hiểu người dân đang muốn thực hiện thủ tục nào;
- nhớ đúng ngữ cảnh của từng người và từng hồ sơ qua nhiều ngày;
- tìm đúng phiên bản thủ tục theo đối tượng, địa phương và thời điểm;
- cho biết hồ sơ đã có, còn thiếu, nơi nộp, cách nộp, lệ phí, thời hạn và bước tiếp theo;
- gắn các hướng dẫn quan trọng với nguồn chính thức;
- hỏi lại hoặc không kết luận khi dữ kiện/bằng chứng chưa đủ;
- phản hồi nhanh trên tài nguyên giới hạn và phục vụ nhiều conversation đồng thời.

Phạm vi chính là **hỏi đáp và hướng dẫn thủ tục hành chính công**, không phải chatbot giải đáp toàn bộ pháp luật Việt Nam.

## 2. Định nghĩa sản phẩm

Sản phẩm không phải chỉ là một model đã fine-tune. Nó gồm ba lớp:

```text
LỚP TRẢI NGHIỆM
Web + phiên/đăng nhập + lịch sử conversation + hướng dẫn/checklist + nguồn trích dẫn

LỚP ĐIỀU PHỐI
Backend API + Case Router + queue + memory/context + workflow + realtime

LỚP AI VÀ TRI THỨC
Procedure Store + adaptive RAG + Procedure Engine + Qwen + verifier
```

Vai trò cốt lõi:

```text
Backend nhớ và điều phối.
Procedure Store giữ sự thật nghiệp vụ có phiên bản.
RAG tìm đúng thủ tục và bằng chứng.
Procedure Engine tính kết quả có cấu trúc.
Qwen hiểu ngôn ngữ và diễn đạt.
Verifier kiểm tra trước khi công bố.
```

## 3. “Lightweight” nghĩa là gì?

Không chỉ là model ít tham số. Hệ thống lightweight phải đồng thời:

- dùng ít VRAM/RAM và có artifact triển khai gọn;
- có TTFT và latency P95 thấp;
- giảm số lần gọi model và số token mỗi lượt;
- phục vụ được nhiều conversation trên cùng hạ tầng;
- không đánh đổi bằng lỗi nghiêm trọng hoặc claim không có nguồn.

Hướng chốt tạm thời:

```text
Qwen3-4B-Instruct-2507 non-thinking
+ rule-based Policy Router
+ versioned Procedure Store
+ adaptive hybrid retrieval
+ Procedure Engine
+ AnswerPlan/backend rendering
+ Evidence Gate + deterministic Verifier
+ context ngắn + cache + continuous batching
```

## 4. Các nguyên tắc bất biến

1. Qwen không tự nhớ người dùng; backend mới là nơi lưu memory.
2. Cookie chỉ chứa token phiên, không chứa PII, lịch sử hoặc Case Card.
3. Case thuộc User, không thuộc riêng Conversation; một conversation có nhiều case và một case có thể tiếp tục qua nhiều conversation.
4. Cùng một conversation xử lý tuần tự; các conversation khác được chạy song song.
5. Tri thức thủ tục thay đổi nằm trong Procedure Store/RAG, không dựa vào trọng số model.
6. Critical facts như giấy tờ, phí, thời hạn và cơ quan phải đến từ dữ liệu đã duyệt.
7. Structured output bảo đảm đúng hình dạng, không bảo đảm đúng sự thật.
8. Không có evidence phù hợp thì hỏi lại, từ chối hoặc chuyển hỗ trợ.
9. Cập nhật dữ liệu thủ tục không đồng nghĩa fine-tune lại Qwen.
10. Mọi lựa chọn model, quantization và reranker phải thắng trên evaluation end-to-end.

---

# PHẦN II – PHÂN: WORKFLOW VÀ CÁC KHỐI

## 5. Workflow A – Một lượt hỏi đáp online

```text
1. Người dùng nhập câu hỏi
   ↓
2. Frontend gửi message + client_request_id
   ↓
3. Backend xác thực session và quyền sở hữu conversation
   ↓
4. Backend lưu message + outbox event trong cùng transaction
   ↓
5. Queue giao job; worker khóa theo conversation_id
   ↓
6. Routing Context Builder lấy recent messages, active-case hint và danh mục case rút gọn
   ↓
7. Case Router gắn message với case cũ, tạo case mới hoặc yêu cầu làm rõ
   ↓
8. Backend tải facts, summary và procedure state của target case đã chốt
   ↓
9. Policy Router chọn FAST / STANDARD / COMPLEX / OUT_OF_SCOPE
   ↓
10. Cần hiểu ngôn ngữ mơ hồ thì Qwen tạo/cập nhật Case Card có schema
   ↓
11. Backend validate Case Card, conflict và missing decisive facts
   ├─ Thiếu dữ kiện → tạo câu hỏi làm rõ → kiểm tra → trả về
   └─ Đủ dữ kiện → tiếp tục
   ↓
12. Procedure Resolver chốt procedure_id + procedure_version_id
   ↓
13. Procedure Store trả dữ liệu cấu trúc; Evidence Retriever lấy nguồn
   ↓
14. Evidence Gate kiểm hiệu lực, địa phương, đối tượng, facet và xung đột
   ├─ Không đạt → CLARIFY / ABSTAIN / ESCALATE
   └─ Đạt → tiếp tục
   ↓
15. Procedure Engine tính checklist, missing documents và next steps
   ↓
16. Tạo AnswerPlan + ExpectedClaimSet
   ↓
17. Backend render critical facts; Qwen chỉ diễn giải phần cần thiết
   ↓
18. Verifier kiểm schema, exact value, citation, completeness và condition
   ├─ Sai → rewrite tối đa một lần
   └─ Vẫn sai → bỏ claim hoặc fail closed
   ↓
19. Commit answer, message–case links, audit và memory delta; ACK job
   ↓
20. Socket.IO stream trạng thái/kết quả; frontend có thể sync lại từ DB
```

### 5.1. Case Router

`Conversation` là dòng chat người dùng nhìn thấy; `Case` là hồ sơ nghiệp vụ ẩn thuộc User và do backend quản lý. Một conversation có thể lần lượt nói về CCCD, khai sinh và khai tử; đồng thời một case CCCD có thể được tiếp tục ở conversation khác.

Mô hình quan hệ được chốt:

```text
User 1 ── N Conversations
User 1 ── N Cases
Conversation 1 ── N Messages
Message N ── M Cases qua message_case_links

Suy ra:
Conversation N ── M Cases qua các message
```

Case có `case_id` ổn định xuyên conversation. `procedure_code` không phải định danh Case, vì một user có thể có hai hồ sơ cùng thủ tục, ví dụ đăng ký khai sinh cho hai người con khác nhau. Khi đó Case Router phải dùng thêm subject/nhãn, thời gian, trạng thái và summary; không xác định chắc hồ sơ nào thì hỏi lại.

Mỗi lượt tạo một `CaseResolution`:

```text
NEW_CASE              → mục tiêu mới, tạo case
EXPLICIT_REFERENCE    → user gọi rõ case/procedure cũ
ACTIVE_CASE_MATCH     → tiếp nối case gần nhất và tín hiệu đủ rõ
ROUTER_MATCH          → khớp một case cũ bằng alias/summary
MULTI_CASE_REFERENCE  → một câu liên quan nhiều case
NO_CASE_REQUIRED      → chào hỏi/câu hệ thống không cần case
AMBIGUOUS             → không đủ chắc chắn, phải hỏi lại
```

`conversation.active_case_id` chỉ là gợi ý gần nhất trong conversation đó. Căn cứ thực sự của một lượt là `message.primary_case_id`; case phụ nằm trong `message_case_links`. Case Router tìm trong các case của đúng User, kể cả case được tạo ở conversation khác. Nếu user hỏi “tôi còn thiếu gì?” khi có nhiều case có thể phù hợp, hệ thống không tự chọn.

### 5.2. Policy Router

| Route | Khi dùng | Đường xử lý |
|---|---|---|
| `FACT_UPDATE` | Đang chờ một field và user cung cấp đúng field đó | Rule → validate → memory delta |
| `SIMPLE_PROCEDURE_FACT` | Đã biết procedure version, hỏi một field như lệ phí | Procedure Store → evidence → template |
| `CLEAR_INTENT` | Có mã/tên thủ tục rõ | Exact lookup → validate |
| `AMBIGUOUS` | Mơ hồ hoặc chưa biết case | Qwen extraction hoặc clarification |
| `CASE_SPECIFIC` | Hỏi checklist theo hoàn cảnh | Qwen → retrieval → engine |
| `COMPLEX` | Nhiều thủ tục/điều kiện gần nhau | Hybrid retrieval + rerank giới hạn |
| `OUT_OF_SCOPE` | Không thuộc hành chính công | Phản hồi phạm vi/chuyển hỗ trợ |

MVP dùng router bằng rule. Chỉ thử learned router sau khi có log được gắn nhãn.

### 5.3. Fast path vẫn phải grounded

Fast path không được lấy tri thức từ “trí nhớ” của Qwen. Nó đọc bản ghi Procedure Store đã được duyệt, lấy evidence tương ứng và render bằng code/template.

## 6. Workflow B – Quản trị và cập nhật tri thức

```text
1. Admin/công ty upload hoặc import dữ liệu
→ 2. Validate loại file, kích thước, checksum, quyền sử dụng và PII
→ 3. Lưu bản gốc immutable vào object storage
→ 4. Parse/OCR và chuẩn hóa metadata
→ 5. Map thành Procedure Store schema có phiên bản
→ 6. Review và phê duyệt
→ 7. Chunk theo cấu trúc nghiệp vụ; embed/index vào staging
→ 8. Chạy smoke test, retrieval regression và source audit
→ 9. Activate index_version/procedure_version bằng thao tác atomic
→ 10. Invalidate cache liên quan và theo dõi lỗi sau publish
```

Chỉ version `ACTIVE` mới được workflow trả lời sử dụng. Phải rollback được về version trước.

## 7. Workflow C – Nhớ ngữ cảnh qua nhiều ngày

```text
Raw messages trong PostgreSQL
        ↓
Case Router chốt target case cho lượt hiện tại
        ↓
Facts có provenance + Case Card của target case
        ↓
Summary riêng cho từng case, có sequence range
        ↓
Context Builder chọn phần liên quan theo token budget
        ↓
Qwen nhận context vừa đủ cho lượt hiện tại
```

Ví dụ:

```text
Ngày 1–5: Case A – cấp lại CCCD
Ngày 10–20: Case B – đăng ký khai sinh
```

Các lượt này có thể nằm trong cùng một conversation hoặc nhiều conversation khác nhau. Case vẫn có facts, summary và procedure state riêng ở cấp User. Khi user mở conversation mới và nhắc “hồ sơ CCCD hôm trước”, backend vẫn route tới Case cũ; nếu có nhiều hồ sơ phù hợp thì hỏi user xác định thêm.

## 8. Workflow D – Huấn luyện và phát hành model

```text
Data readiness + license check
→ tạo train/dev/private test không leakage
→ baseline không fine-tune
→ grounded SFT/QLoRA pilot
→ đánh giá oracle evidence và retrieved evidence
→ merge adapter, lưu master BF16
→ xuất Q5/Q4/AWQ candidates
→ chạy lại quality + safety + latency benchmark
→ chỉ phát hành artifact vượt mọi gate
```

Fine-tune tập trung vào hành vi: Case Card, clarification, grounded answer, claim–evidence, structured output và abstention. Không fine-tune để model học thuộc thủ tục có thể thay đổi.

## 9. Workflow E – Đánh giá và giám sát

Đánh giá tách nguyên nhân lỗi bằng bốn chế độ:

1. Model closed-book.
2. Model với oracle/gold evidence.
3. Model với evidence từ retriever thật.
4. Pipeline đầy đủ với temporal filter, Procedure Engine và verifier.

Runtime phải ghi stage latency và version:

```text
trace_id
model_version
prompt/schema_version
procedure_version_id
index_version
router_ms / retrieval_ms / rerank_ms
TTFT / total_latency_ms
verifier_result
answer_status
```

## 10. Ranh giới trách nhiệm

| Khối | Chịu trách nhiệm | Không chịu trách nhiệm |
|---|---|---|
| Frontend | Nhập liệu, trạng thái, lịch sử, case, evidence | Không xác thực ownership hoặc tự tính thủ tục |
| Backend/API | Identity, quyền, DB, queue, orchestration | Không để LLM truy cập DB trực tiếp |
| Context Builder | Chọn đúng memory theo budget | Không dùng summary làm nguồn thủ tục |
| Policy Router | Chọn đường xử lý | Không tự kết luận nội dung thủ tục |
| Qwen | Hiểu ngôn ngữ, structured extraction, diễn giải | Không tự nhớ user hoặc làm source of truth |
| Procedure Resolver | Chọn đúng procedure/version | Không tự sinh checklist |
| Procedure Store | Dữ liệu thủ tục đã duyệt, có phiên bản | Không chứa lịch sử cá nhân |
| Evidence Retriever | Lấy fragment nguồn cho claim/facet | Không tự quyết định điều kiện nghiệp vụ |
| Procedure Engine | Tính checklist, conditions, next step | Không suy đoán bằng văn bản tự do |
| Evidence Gate/Verifier | Chặn evidence/output không đạt | Không thay cán bộ ở ca vượt phạm vi |
| PostgreSQL | Source of truth cho app state/audit | Không dùng context window làm database |
| Redis | Queue, lock, cache, realtime adapter | Không là source of truth dài hạn |

## 11. Contract dùng chung

Các schema phải được version hóa sớm:

```text
RequestContext
Message
CaseResolution
MessageCaseLink
CaseCard
MemoryDelta
ProcedureBundle
EvidenceBundle
AnswerPlan
ExpectedClaimSet
ModelAnswer
VerificationResult
```

`RequestContext` tối thiểu:

```json
{
  "tenant_id": "tenant_uuid",
  "user_id": "user_uuid",
  "session_id": "session_uuid",
  "conversation_id": "conversation_uuid",
  "target_case_id": "case_uuid_or_null_after_routing",
  "referenced_case_ids": [],
  "case_resolution": "ACTIVE_CASE_MATCH_or_other_status",
  "message_id": "message_uuid",
  "turn_seq": 42,
  "trace_id": "trace_uuid"
}
```

Mỗi breaking change cần schema version mới, migration/backward compatibility và contract test.

## 12. Trạng thái đầu ra chuẩn

```text
ANSWER_VERIFIED
ASK_CLARIFICATION
INSUFFICIENT_EVIDENCE
CONFLICT_DETECTED
OUT_OF_SCOPE
HIGH_RISK_ESCALATION
```

Frontend không suy luận trạng thái từ văn bản; backend phải trả mã trạng thái máy đọc được.

## 13. Quyết định đã chốt tạm thời

| Hạng mục | Quyết định |
|---|---|
| Generator | `Qwen3-4B-Instruct-2507`, non-thinking; 1.7B là challenger |
| Model lớn | Chỉ dùng offline teacher hoặc baseline |
| Retriever baseline | BGE-M3 + BM25 + exact/metadata filter |
| Reranker baseline | BGE-reranker-v2-m3; chỉ chạy động khi cần |
| Store | Versioned Procedure Store, append-only |
| Critical output | Procedure Engine + backend render |
| Model output | JSON Schema/grammar constrained |
| Context | Typical 2K–6K, hard cap 8K ban đầu |
| Runtime | vLLM/WSL2 cho concurrency; llama.cpp Windows để benchmark/fallback |
| Quantization | BF16 baseline; so sánh Q5/Q4/AWQ bằng quality gate |
| App stack | FastAPI, PostgreSQL, Redis, Qdrant, MinIO, Socket.IO |
| Conversation–case | Case thuộc User; conversations và cases độc lập, liên kết N–M qua message; hỗ trợ một conversation nhiều case và một case nhiều conversation |
| Queue | Tuần tự trong conversation, song song giữa conversations |
| KPI chính | Grounded Joint Accuracy + critical error + P95 latency |

## 14. Nội dung còn phải xác nhận với công ty

1. Danh sách thủ tục và địa phương bắt buộc cho MVP.
2. Cấu trúc, chất lượng, quyền dùng và tần suất cập nhật dữ liệu.
3. Chính sách PII, consent, retention, export và delete.
4. Đăng nhập bắt buộc hay cho phép anonymous; nhà cung cấp OTP.
5. Số user đồng thời, timeout, SLA latency và target production hardware.
6. Upload chỉ dành cho admin hay có kho tài liệu riêng của user.
7. Yêu cầu multi-tenant giữa đơn vị/cơ quan.
8. Mức human review và người chịu trách nhiệm duyệt procedure version.

---

# PHẦN III – HỢP: KẾ HOẠCH CHUNG

## 15. Lộ trình theo cổng nghiệm thu

### Giai đoạn 0 – Contract và walking skeleton

- Khóa schema v1 và API v1.
- Anonymous session, conversation, case ẩn, message và message–case links trong DB.
- Transactional outbox → queue → mock worker.
- Socket.IO stream và history sync sau refresh.
- Khung web demo.

**Gate:** hai user không lẫn dữ liệu; message cùng conversation không đảo thứ tự hoặc nhân đôi.

### Giai đoạn 1 – Data và Procedure Store

- Data Readiness Report và Coverage Contract.
- Parser/normalizer, procedure version, provenance và snapshot.
- Staging → validate → activate → rollback.

**Gate:** mọi field/fragment truy ngược được về nguồn và version.

### Giai đoạn 2 – Case, memory và RAG baseline

- Case Router, CaseResolution, Case Card, structured facts và summary riêng từng case.
- Exact + metadata + BM25 + dense retrieval.
- Procedure Resolver và EvidenceBundle.

**Gate:** một conversation chứa nhiều case và một case đi qua nhiều conversation vẫn route/resume đúng; procedure top-1 và correct-version đạt ngưỡng pilot.

### Giai đoạn 3 – Procedure Engine và kiểm chứng

- Evidence Gate.
- Checklist/condition/next-step engine.
- AnswerPlan + ExpectedClaimSet.
- Backend render critical facts và deterministic verifier.

**Gate:** critical-value exact accuracy đạt ngưỡng; pipeline fail closed khi nguồn không đủ.

### Giai đoạn 4 – Qwen và tối ưu lightweight

- Structured extraction/generation.
- Grounded SFT/QLoRA nếu baseline chứng minh cần.
- BF16/Q5/Q4/AWQ và runtime bake-off.
- Context/output cap, cache và continuous batching.

**Gate:** artifact production thắng baseline trên quality, safety và end-to-end latency.

### Giai đoạn 5 – Hardening và pilot

- OTP, consent, retention, export/delete.
- DLQ, retry, observability, security/load test.
- Expert blind review và deployment profile.

**Gate:** đạt Definition of Done và SLA do công ty phê duyệt.

## 16. Phân công nhóm ba người

| Luồng | Ownership chính | Phối hợp bắt buộc |
|---|---|---|
| A – Data/RAG | Data readiness, Procedure Store, ingestion, retrieval, reranker | Với B cho eval/hard negatives; với C cho API/index lifecycle |
| B – AI/Quality | Qwen, structured output, SFT, verifier, benchmark | Với A cho evidence; với C cho ModelGateway/telemetry |
| C – Product Platform | Backend, memory, queue, Socket.IO, web, Docker | Với A/B cho schema và end-to-end integration |

Cả nhóm cùng khóa contract, review Gold data, giữ private test và demo end-to-end hằng tuần.

## 17. Definition of Done cho MVP

MVP hoàn thành khi:

- định danh, session và quyền truy cập hoạt động đúng;
- một conversation có thể chứa case CCCD, khai sinh và khai tử; một case cũ vẫn được truy vết từ conversation mới mà không trộn memory;
- lịch sử tồn tại qua refresh/ngày hôm sau;
- message tuần tự trong conversation và retry idempotent;
- có Procedure Coverage Manifest công khai phạm vi;
- retrieval chốt đúng procedure, địa phương và version;
- Procedure Engine tạo đúng checklist có điều kiện;
- mọi claim trọng yếu có citation đã kiểm tra;
- thiếu facts/evidence thì hệ thống hỏi lại hoặc không kết luận;
- web hiển thị chat/history, checklist theo câu trả lời, source và upload status; không bắt user quản lý thực thể Case;
- thêm procedure version mới không cần fine-tune model;
- có benchmark 1.7B/4B, BF16/Q5/Q4 và end-to-end P50/P95;
- production artifact chạy trên target hardware đã thống nhất;
- có security, PII, concurrency, failure-recovery và regression test.

## 18. Không làm trong MVP

- Model/adapter riêng cho từng bộ, ngành hoặc tỉnh.
- Multi-agent debate cho mọi truy vấn.
- Knowledge graph toàn diện hoặc GNN khi chưa có baseline chứng minh cần.
- GRPO/RL phức tạp trước grounded SFT.
- Đưa toàn bộ kho thủ tục vào long context.
- Dùng confidence tự khai của Qwen làm chốt an toàn duy nhất.
- Tự nộp hồ sơ hay thực hiện hành động hành chính thay người dùng.
- Tuyên bố bao phủ toàn bộ hoặc không hallucination khi chưa có số liệu.

## 19. Việc cần làm ngay

1. Xác nhận bộ tài liệu và ownership với cả nhóm.
2. Khóa các schema/contract v1 được liệt kê tại mục 11.
3. Dựng walking skeleton backend + web + queue + mock worker.
4. Nhận dữ liệu công ty và lập Data Readiness Report.
5. Tạo Procedure Store tối thiểu và private test cho ba nhóm thủ tục demo.
6. Gắn lần lượt Policy Router → RAG → Procedure Engine → Qwen → Verifier.
7. Chỉ tối ưu model sau khi telemetry chỉ ra bottleneck thực sự.

## 20. Câu chốt để báo cáo

> **Đây là một hệ thống trợ lý hành chính công, không phải chỉ là một LLM. Backend giữ đúng người, đúng hồ sơ và đúng thứ tự; Procedure Store/RAG cung cấp dữ liệu đang áp dụng; Procedure Engine tính kết quả; Qwen hiểu và diễn đạt; Verifier chỉ cho phép câu trả lời có căn cứ được gửi tới người dùng.**
