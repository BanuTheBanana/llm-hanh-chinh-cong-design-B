# Chiến lược triển khai từ nhỏ đến lớn – Trợ lý hành chính công

> **Đây là kế hoạch thực thi đang có hiệu lực.**  
> Mục tiêu: giúp nhóm ba người tạo được sản phẩm chạy thật sớm, sau đó tăng dần độ chính xác, tính lightweight và các tính năng hệ thống qua từng cổng nghiệm thu.  
> Các kiến trúc Case/RAG/queue/verifier đầy đủ trước đây được giữ làm **Target Architecture / Backlog**, không triển khai đồng thời ở giai đoạn đầu.  
> Cách trình bày: **Tổng → Phân → Hợp**.

## Báo cáo cập nhật

| Trường | Nội dung |
|---|---|
| Cập nhật gần nhất | 09/09/2026 |
| Phiên bản | `v1.9` |
| Trạng thái | `G1_COMPLETED_ON_MAIN`; `G2_I01_D0_TECHNICAL_PASS`; G2/D1 chưa nghiệm thu |
| Nguồn thay đổi | Phản hồi của người có kinh nghiệm: thu nhỏ phạm vi, tạo bot chạy được trước, tách UI/Backend/AI qua API, thêm tính năng theo thứ tự |
| Thay đổi lần này | Bổ sung corpus D0 hoàn chỉnh 3 thủ tục/33 câu để nhóm tiếp tục phát triển khi nguồn D1 khó truy cập; D1 và hosted vẫn giữ sau review/approval |

Tài liệu chi tiết trước đây đã được cất tại [Target Architecture v1.2](parked/kien-truc-muc-tieu-v1.2/00-workflow-tong-quat.md). Chỉ mở lại từng module khi backlog có trigger; sơ đồ nằm trong [`architecture/`](architecture/README.md).

Hồ sơ thực thi và nghiệm thu G1: [Phân công Giai đoạn 1 – Tú, Minh, Hoan](01-phan-cong-giai-doan-1.md).
Kế hoạch thực thi hiện tại: [Phân công Giai đoạn 2 – Data, RAG và Hosted AI baseline](giai-doan-2/02-phan-cong-giai-doan-2.md).
Trọng tâm đang làm là hoàn tất D1/Gate G2 trong mục **NOW**; lát cắt D0 đã chạy.

### Bằng chứng hoàn thành G1

GitHub Actions run
[`34197723998`](https://github.com/DOMEMON/llm-hanh-chinh-cong/actions/runs/34197723998)
đã pass 5/5 job tại commit `4b64f6f` trên `g1/integration`:

- 9 test Web, lint và production build;
- 15 test AI Service, lint và lockfile check;
- 58 test Backend với PostgreSQL 16;
- repository hygiene/secret-pattern gate;
- build bốn container từ môi trường sạch, API smoke và Playwright browser smoke.

API message round-trip với Mock AI trong run này là 56,33 ms. Đây là baseline
kỹ thuật CI, không phải SLA và không phản ánh tốc độ hay chất lượng model thật.
Pull request #2 đã được merge vào `main`; tag `g1-v1.0.0` giữ snapshot G1.

## Cách dùng file này

1. Cả nhóm chỉ nhìn mục **Đang làm ngay** để triển khai.
2. Không kéo việc từ giai đoạn sau lên khi gate hiện tại chưa đạt.
3. Mỗi tính năng mới phải trả lời được: giải quyết lỗi/yêu cầu nào, ai làm, test nào chứng minh hoàn thành.
4. Khi thay đổi hướng, cập nhật báo cáo ở đầu file trước rồi mới sửa phần liên quan.
5. Tài liệu Target Architecture chỉ được mở lại khi một trigger trong backlog xuất hiện.

---

# PHẦN I – TỔNG: TƯ DUY LẠI DỰ ÁN

## 1. Chẩn đoán thẳng

Kiến trúc đã thảo luận trước đây hợp lý như một **hệ thống đích**, nhưng quá lớn để trở thành backlog triển khai cùng lúc cho ba intern:

```text
Web + đăng nhập + history + Case Router + memory dài hạn
+ queue + outbox + Socket.IO
+ Procedure Store + hybrid RAG + reranker
+ Qwen + fine-tune + quantization
+ Evidence Gate + Procedure Engine + verifier
+ upload/admin + Docker + observability
```

Nếu chia ngay theo từng khối lớn, mỗi người có thể làm một phần riêng nhưng sau nhiều tuần vẫn chưa có sản phẩm end-to-end. Rủi ro lớn nhất không phải thiếu ý tưởng; đó là **không có lát cắt nào chạy hoàn chỉnh để đo và demo**.

## 2. Ý chính rút ra từ cuộc trao đổi

Lời khuyên đúng và nên áp dụng:

1. Tạo một bot có thể nhận câu hỏi và trả response trước.
2. Dùng một luồng nhỏ chạy từ giao diện đến database và AI, chưa đòi độ chính xác nghiệp vụ ở bản đầu.
3. Tách UI, Backend và AI bằng API để có thể thay đổi độc lập.
4. Dùng provider/API đã có để ráp luồng nhanh; tự host model sau.
5. Thêm từng tính năng theo thứ tự: dễ và cốt lõi trước, khó hoặc trang trí sau.
6. Mỗi giai đoạn phải tạo ra bản demo chạy được, không để ba nhánh phát triển rời nhau quá lâu.

Hai điều cần hiểu có điều kiện:

- “Bot trả lời đại” chỉ là **technical baseline nội bộ**, không được gọi là sản phẩm hành chính chính xác.
- “Dùng OpenAI API trước” chỉ áp dụng khi công ty cho phép dữ liệu đi tới provider bên ngoài. Nếu chưa được phép, dùng mock provider hoặc model local nhỏ để ráp luồng.

## 3. Đích cuối không thay đổi

Sau các giai đoạn, sản phẩm vẫn hướng tới:

- hỏi đáp thủ tục hành chính công dựa trên dữ liệu công ty/chính thức;
- có nguồn và biết khi nào không đủ căn cứ;
- lưu user và lịch sử chat theo yêu cầu;
- dùng model local lightweight ở artifact cuối nếu đây là tiêu chí công ty;
- chạy nhanh trên target hardware và có số liệu đánh giá.

Điều thay đổi là **thứ tự xây**, không phải bỏ đích đến.

## 4. Kiến trúc nhỏ nhất để bắt đầu

Chỉ giữ ba ranh giới ứng dụng và một database:

```text
┌──────────────┐       HTTP       ┌────────────────┐
│ Web/UI       │ ───────────────→ │ Core Backend   │
│ host riêng   │                  │ API host riêng │
└──────────────┘                  └───────┬────────┘
                                         │
                              ┌──────────┴──────────┐
                              │                     │
                              ▼                     ▼
                     ┌────────────────┐    ┌────────────────┐
                     │ PostgreSQL     │    │ AI Service     │
                     │ user + history │    │ API host riêng │
                     └────────────────┘    └───────┬────────┘
                                                  ▼
                                      Mock / approved hosted API
                                      → local lightweight model sau
```

Đây là **ba deployable boundaries thô**, không phải hàng chục microservice:

- `web`: chỉ giao diện.
- `backend`: auth/session tối thiểu, conversation, message, history và orchestration.
- `ai-service`: một API ổn định che giấu provider/model ở phía sau.
- `postgres`: dữ liệu ứng dụng.

Có thể để chung monorepo và chạy bằng Docker Compose. “Tách riêng” nghĩa là có API/interface rõ, không bắt buộc dựng Kubernetes hoặc hạ tầng phân tán.

## 5. Cách kiến trúc lớn dần

```text
M0 – Technical slice
Web → Backend → AI provider; PostgreSQL lưu user/history

M1 – Domain baseline
M0 + dữ liệu hành chính nhỏ + retrieval đơn giản + nguồn

M2 – Lightweight local
M1 + model local ≤2B ưu tiên + quantization + benchmark

M3 – Accuracy improvements
M2 + retrieval/reranker/rules/verifier theo lỗi thực tế

M4 – Product features
M3 + memory/case/queue/streaming/upload khi có nhu cầu đã chứng minh

M5 – Production hardening
M4 + security, observability, load/recovery và deployment hoàn chỉnh
```

Mỗi mốc phải chạy được độc lập. Không đợi M5 mới tích hợp.

## 5.1. Chiến lược dữ liệu và model đã chốt

Không dùng một loại dữ liệu cho mọi mục đích. Dự án tách rõ ba lớp:

| Lớp | Mục đích | Nguồn | Model được phép dùng |
|---|---|---|---|
| `D0_SYSTEM_SMOKE` | Kiểm tra Web/API/DB/history/error | Câu hỏi và response giả do nhóm tạo | Mock; hosted API nếu đã duyệt |
| `D1_PUBLIC_DEMO` | Làm RAG và đo chất lượng ban đầu | Snapshot từ nguồn hành chính công chính thức + tình huống giả | Hosted API được duyệt và model local |
| `D2_COMPANY_REAL` | Phát triển/đánh giá sản phẩm thật | Dataset công ty sau khi phân loại | Chỉ hạ tầng/model được công ty phê duyệt; mặc định local nếu chưa có quyền gửi ra ngoài |

Luồng chuyển đổi:

```text
D0: Mock ráp hệ thống
→ D1: dữ liệu công khai + hosted API tạo baseline
→ D1: chạy lại cùng bộ test bằng model local để so sánh công bằng
→ D2: dữ liệu công ty chỉ vào pipeline đã được duyệt
→ fine-tune chỉ khi đánh giá chứng minh thật sự cần
```

Các nguyên tắc bắt buộc:

1. Không chờ dataset công ty mới dựng Web, Backend, Database và AI Service.
2. Không upload toàn bộ corpus lên hosted LLM. Backend/RAG chỉ gửi câu hỏi cùng phần evidence tối thiểu cần thiết.
3. Không gửi dữ liệu thật, dữ liệu nội bộ hoặc PII ra provider ngoài khi chưa có phê duyệt bằng văn bản.
4. “Model local” không tự động có nghĩa là an toàn: vẫn cần phân quyền, kiểm soát log, mã hóa, backup và kiểm soát kết nối ra ngoài.
5. Cùng một bộ `D1_PUBLIC_DEMO` phải được dùng để so sánh hosted và local; không thay câu hỏi giữa hai lần benchmark.
6. Hosted API là scaffolding/baseline, không phải artifact cuối nếu tiêu chí nghiệm thu yêu cầu lightweight self-hosted.

AI Service giữ provider boundary để sau này đổi provider mà không sửa Web/Core
Backend. Runtime G1 hiện chỉ triển khai `mock`; `openai` và `local` là adapter
tương lai, chưa thể bật chỉ bằng cách đổi biến môi trường:

```env
LLM_PROVIDER=mock
# G1 chỉ hỗ trợ mock; openai/local thuộc G2/G3 nếu được triển khai và phê duyệt.
```

---

# PHẦN II – PHÂN: TỪNG GIAI ĐOẠN

## 6. Giai đoạn 0 – Khóa lát cắt đầu tiên

### 6.1. Kết quả cần có

Một trang scope một màn hình, được mentor/công ty xác nhận:

```text
Lần demo đầu có:
- giao diện đăng nhập/demo identity tối giản;
- một màn hình chat;
- tạo/mở conversation;
- gửi câu hỏi và nhận câu trả lời;
- lưu và tải lại lịch sử;
- Web, Backend, AI tách qua API.

Lần demo đầu chưa cam kết:
- trả lời hành chính chính xác;
- model local;
- RAG/citation;
- memory/case dài hạn;
- realtime/queue;
- tải tài liệu hoặc dashboard admin.
```

### 6.2. Các câu phải hỏi mentor/công ty

1. Bản đầu chỉ chứng minh chat end-to-end, history và service separation có được chấp nhận không?
2. Đăng nhập bản đầu cần thật hay dùng seeded demo account/anonymous session?
3. Có được phép gọi hosted LLM API với dữ liệu demo không?
4. Nếu không, nhóm được dùng mock/local small model cho technical slice không?
5. Những thủ tục nào được chọn làm 2–3 phạm vi mẫu ở giai đoạn RAG?
6. “Lightweight” được nghiệm thu theo tham số, VRAM, tốc độ, chi phí hay tất cả?
7. Artifact cuối có bắt buộc self-host/offline không?
8. Thời hạn và hình thức demo ở từng mốc là gì?

### 6.3. Gate G0

- Mentor đồng ý phạm vi demo đầu và danh sách “chưa làm”.
- Chốt ba API boundary.
- Mỗi thành viên biết deliverable tuần/lượt hiện tại.
- Không còn tranh luận Case, reranker hay quantization trước khi technical slice chạy.

## 7. Giai đoạn 1 – Technical vertical slice

### 7.1. Mục tiêu

Chứng minh một câu hỏi đi xuyên toàn hệ thống và được lưu lại:

```text
Login/demo identity
→ mở chat
→ POST message
→ Backend lưu user message
→ Backend gọi AI Service
→ AI Service gọi MockProvider
→ Backend lưu assistant message
→ Web hiển thị answer
→ refresh vẫn còn history
```

### 7.2. Chỉ triển khai

Web:

- form đăng nhập tối giản hoặc seeded demo account;
- danh sách conversation;
- khung message và ô nhập;
- loading/error/retry cơ bản.

Backend:

- session/login tối thiểu;
- CRUD conversation cần thiết;
- POST message dạng synchronous;
- lưu user/assistant messages;
- timeout và error mapping;
- log `request_id`, latency và provider status.

AI Service:

- `POST /internal/v1/generate`;
- provider boundary ổn định; G1 chỉ triển khai adapter `mock`;
- không để Web gọi provider trực tiếp;
- secret chỉ nằm ở server.

Database tối thiểu:

```text
users
sessions
conversations
messages
```

### 7.3. Chưa triển khai

- Case/Case Router/Memory summary.
- Redis queue, transactional outbox và Socket.IO streaming.
- RAG, Qdrant, reranker và Procedure Store.
- Fine-tune/quantize/self-host.
- OTP, multi-device sync và admin upload.
- Verifier nhiều tầng.

### 7.4. API tối thiểu

Public backend:

```text
POST /api/v1/auth/login
POST /api/v1/auth/logout
GET  /api/v1/auth/me
GET  /api/v1/conversations
POST /api/v1/conversations
GET  /api/v1/conversations/{id}/messages
POST /api/v1/conversations/{id}/messages
GET  /health
```

Internal AI:

```text
POST /internal/v1/generate
GET  /health
```

Request giữa Backend và AI:

```json
{
  "request_id": "uuid",
  "messages": [
    {"role": "user", "content": "Tôi cần làm giấy khai sinh."}
  ],
  "max_output_tokens": 300
}
```

Response:

```json
{
  "request_id": "uuid",
  "text": "...",
  "provider": "mock",
  "model": "mock-v1",
  "usage": {"input_tokens": 0, "output_tokens": 0},
  "latency_ms": 0
}
```

### 7.5. Gate G1

**Trạng thái: PASS trên `g1/integration`.** Bằng chứng là run CI nêu ở đầu tài
liệu; browser smoke là demo thực thi tự động. Video trình bày riêng có thể quay
khi báo cáo mentor nhưng không còn là điều kiện kỹ thuật chưa kiểm tra.

- Một command/runbook dựng được toàn bộ môi trường dev.
- User đăng nhập/demo identity, gửi câu hỏi và nhận answer.
- Refresh hoặc đăng nhập lại vẫn thấy đúng history.
- User A không xem được history User B.
- Provider lỗi/timeout không làm mất user message.
- Web, Backend và AI Service có thể thay độc lập qua contract.
- Có browser smoke tự động và log latency; video trình bày quay thêm nếu mentor cần.

Đây là gate kỹ thuật, chưa phải gate độ chính xác hành chính.

### 7.6. Dataset smoke cho G1

G1 chưa cần tài liệu thủ tục thật. Nhóm tự tạo khoảng 10–20 test case không chứa PII để kiểm tra:

- câu hỏi ngắn/dài, có dấu/không dấu;
- hai message liên tiếp và tải lại history;
- hai user hoạt động độc lập;
- input rỗng hoặc sai định dạng;
- provider timeout/lỗi và thao tác retry;
- provider trả response thành công.

Các test này chỉ chứng minh **hệ thống chạy đúng**, không chứng minh câu trả lời hành chính đúng.

## 8. Giai đoạn 2 – Domain/RAG baseline nhỏ

### 8.1. Mục tiêu

Biến chatbot kỹ thuật thành trợ lý có căn cứ trên một phạm vi nhỏ có thể đo:

- chọn 2–3 thủ tục đại diện;
- trước mắt dùng snapshot dữ liệu công khai từ nguồn hành chính chính thức; chỉ dùng dữ liệu công ty khi đã phân loại và được phép;
- tạo một gold set nhỏ khoảng 30–50 câu hỏi ban đầu;
- trả câu trả lời kèm nguồn;
- biết nói chưa đủ dữ liệu thay vì bịa nguồn.

Số lượng trên là đề xuất khởi đầu, cần mentor duyệt.

### 8.1.1. Nguồn dataset demo ban đầu

Chọn 2–3 thủ tục có trang công khai chính thức, ví dụ đăng ký khai sinh, cấp lại thẻ căn cước và đăng ký khai tử. Với mỗi nguồn phải lưu:

```json
{
  "procedure_id": "birth_registration_demo",
  "title": "Đăng ký khai sinh",
  "source_url": "https://official.example/...",
  "retrieved_at": "YYYY-MM-DD",
  "jurisdiction": "phạm vi áp dụng",
  "usage": "PUBLIC_DEMO_ONLY"
}
```

Không coi snapshot demo là dữ liệu production luôn đúng. Thủ tục có thể thay đổi theo thời gian và địa phương; vì vậy phải khóa phiên bản, ngày lấy và phạm vi áp dụng.

Từ các snapshot này, nhóm tự viết 30–50 tình huống giả, kèm:

- `procedure_id` đúng;
- các ý bắt buộc trong câu trả lời;
- `gold_source_ids` hỗ trợ các ý đó;
- trường hợp cố ý thiếu dữ kiện để kiểm tra khả năng hỏi lại/từ chối;
- xác nhận `contains_pii=false`.

Không dùng tên, CCCD, số điện thoại, hồ sơ hay tình huống thật của công dân.

### 8.1.2. Cấu trúc thư mục đề xuất

```text
data/
└── demo_public/
    ├── README.md
    ├── source_manifest.jsonl
    ├── raw/<procedure>/<retrieved-date>/...
    ├── normalized/
    │   ├── procedures.jsonl
    │   └── fragments.jsonl
    ├── gold/questions.jsonl
    └── reports/data-quality.md

tools/data/
└── crawler/downloader, normalizer và validator
```

Gold lưu expected points, forbidden points và source/fragment IDs; không dùng một
đoạn văn do LLM sinh làm `expected_answer` rồi coi đó là chân lý.

### 8.2. Retrieval đơn giản trước

Thứ tự:

```text
1. JSON/SQL records được chuẩn hóa tối thiểu
2. Exact title/code/alias lookup
3. Keyword/PostgreSQL full-text hoặc BM25 đơn giản
4. Chỉ thêm embedding/vector DB khi baseline bỏ sót nhiều
5. Chỉ thêm reranker khi candidate ranking là bottleneck đo được
```

Không dựng toàn bộ hybrid RAG, temporal graph và ingestion platform ngay từ đầu.

### 8.3. Output tối thiểu

```json
{
  "answer": "...",
  "sources": [
    {
      "title": "...",
      "url": "https://official...",
      "fragment_id": "..."
    }
  ],
  "status": "ANSWER_OR_INSUFFICIENT_DATA"
}
```

### 8.4. Đo riêng plumbing và quality

```text
Retrieval: đúng tài liệu có nằm trong top-k không?
Citation: URL/fragment có thật và hỗ trợ câu trả lời không?
Answer: ý chính, giấy tờ, phí/thời gian có đúng không?
Latency: từng stage và end-to-end mất bao lâu?
```

### 8.5. Gate G2

- 2–3 thủ tục demo đã có source và phạm vi công bố rõ.
- Gold set khóa version và tách khỏi prompt tuning.
- Mỗi answer có source thật hoặc trạng thái thiếu dữ liệu.
- Có bảng baseline retrieval, answer quality và latency.
- Nhóm biết bottleneck nằm ở data, retrieval hay generation.

Ngưỡng phần trăm chỉ chốt sau baseline cùng mentor; không tự tuyên bố đạt production.

## 9. Giai đoạn 3 – Model local lightweight

### 9.1. Mục tiêu

Thay provider bên ngoài bằng model local mà không sửa contract grounded giữa Core
Backend và AI Service:

```text
GROUNDED_PROVIDER=hosted
→ GROUNDED_PROVIDER=local

POST /internal/v2/generate giữ nguyên.
```

`POST /internal/v1/generate` và `LLM_PROVIDER=mock` chỉ được giữ để chạy regression
G1; chúng không phải contract cho luồng hành chính công grounded từ G2 trở đi.

### 9.2. Chiến lược model

Theo hướng giảm rủi ro triển khai:

1. Bắt đầu với model instruct khoảng 0.5B–2B.
2. Chạy zero-shot/prompt baseline trước khi fine-tune.
3. Benchmark BF16/FP16 nếu vừa, sau đó Q8/Q5/Q4 phù hợp runtime.
4. Chỉ dùng 4B như quality ceiling/challenger khi phần cứng và thời gian cho phép.
5. Chỉ QLoRA/SFT khi error analysis chứng minh model là bottleneck.

Không chốt “dưới 2B luôn tốt hơn”. `≤2B` là default để triển khai nhanh; quyết định cuối dựa trên:

```text
độ chính xác
VRAM/RAM
TTFT và latency P95
tokens/second
tỷ lệ timeout/OOM
khả năng chạy trên target deployment
```

### 9.3. Hosted API có vai trò gì?

- scaffolding để Web/Backend hoàn thiện sớm;
- baseline chất lượng/latency;
- có thể làm teacher sinh candidate nếu công ty cho phép;
- không được dùng để tuyên bố đã hoàn thành tiêu chí local lightweight.

Khi dùng hosted API ở bản thử:

- chỉ gửi dữ liệu công khai/giả lập đã được phê duyệt;
- chỉ gửi context/evidence tối thiểu, không gửi cả kho dữ liệu;
- backend của dự án tự quản lý history, tránh phụ thuộc hosted conversation state nếu không cần;
- cấu hình không lưu application state nếu provider hỗ trợ, nhưng không được hiểu nhầm rằng cấu hình này thay thế phê duyệt dữ liệu của công ty;
- không ghi API key, prompt chứa dữ liệu hoặc response nhạy cảm vào log.

### 9.4. Gate G3

- Model local chạy sau cùng AI Service contract.
- Artifact vừa target hardware và không OOM trong test.
- Có so sánh local small model với hosted baseline trên cùng gold set.
- Có quality–latency–VRAM report, không chỉ ảnh chụp chatbot.
- Fine-tune/quantization chỉ được giữ nếu cải thiện trade-off có số liệu.

## 10. Giai đoạn 4 – Tăng độ chính xác theo lỗi thật

Không bật tất cả kỹ thuật cùng lúc. Dùng bảng quyết định:

| Lỗi quan sát được | Cải tiến nhỏ nhất nên thử |
|---|---|
| Không tìm thấy đúng thủ tục | Alias/metadata/exact trước, sau đó dense retrieval |
| Top-k có đáp án nhưng xếp sai | Reranker trên top nhỏ |
| Sai giấy tờ/phí/thời hạn | Structured procedure fields + backend render |
| Bịa nguồn/claim | Evidence check + claim/source mapping |
| Không biết hỏi lại | Clarification rules, sau đó grounded SFT |
| Context quá dài/chậm | Chọn evidence, giới hạn history/output |
| Nhiều user làm nghẽn | Concurrency/batching; queue chỉ khi cần |

Mỗi cải tiến phải chạy ablation:

```text
baseline
vs
baseline + đúng một thay đổi
```

### Gate G4

- Lỗi lớn nhất giảm trên private regression set.
- Không làm latency/VRAM/critical error xấu quá ngưỡng đã thống nhất.
- Biết thành phần nào tạo ra cải thiện; rollback được.

## 11. Giai đoạn 5 – Thêm tính năng sản phẩm theo trigger

Các tính năng cũ không bị bỏ, nhưng chỉ mở lại khi có lý do cụ thể:

| Tính năng | Chỉ mở khi |
|---|---|
| Case/Case Router | History đơn giản không đủ phân biệt nhiều hồ sơ và đây là yêu cầu demo đã xác nhận |
| Memory summary dài hạn | Context/history thực tế vượt budget hoặc user quay lại nhiều ngày là use case bắt buộc |
| Redis queue/outbox | Có concurrency, job dài, retry/mất message mà synchronous flow không đáp ứng |
| Socket.IO streaming | P95 đủ lâu để UX cần stream hoặc mentor yêu cầu realtime |
| Procedure Store versioned | Dữ liệu có version/thời gian và baseline trả sai hiệu lực |
| Reranker | Retrieval top-k có đúng tài liệu nhưng ranking thường sai |
| Procedure Engine | Checklist có điều kiện không thể đảm bảo bằng text generation |
| Verifier nhiều tầng | Citation/critical claim errors vẫn vượt gate |
| OTP/multi-device | Identity thật và khôi phục lịch sử xuyên thiết bị được yêu cầu |
| Admin upload/index | Có người vận hành và quy trình cập nhật nguồn thật |
| Dashboard operations | Có đủ telemetry và stakeholder thật sự sử dụng |

Mỗi lần chỉ thêm một capability end-to-end, có test và demo riêng.

## 12. Giai đoạn 6 – Production hardening

Chỉ bắt đầu khi core answer + local model + domain baseline đã đạt gate:

- secret manager, TLS, least privilege và PII policy;
- migrations, backup/restore và rollback;
- rate limit, timeout, retry, load test;
- monitoring/alert theo stage;
- model/index/data versioning;
- deployment reproducible;
- security và prompt-injection tests;
- retention/export/delete nếu lưu dữ liệu người dùng thật.

### Gate G5/G6

- Demo/release chạy ổn định từ môi trường sạch.
- Không lẫn dữ liệu giữa user.
- Có rollback model/app/data.
- Đạt SLA và quality gate do công ty phê duyệt.

---

# PHẦN III – HỢP: KẾ HOẠCH LÀM VIỆC

## 13. Bảng Now – Next – Later – Parked

### NOW – Hoàn tất dữ liệu D1 và Gate G2

1. Giữ checkpoint D0 trên `g2/integration` chạy xanh và không nhập dữ liệu thật
   vào `data/demo_synthetic`.
2. Review chéo spike đăng ký khai sinh; lấy nguồn chi tiết chính thức có thành
   phần hồ sơ và trình tự, không suy đoán các field còn thiếu.
3. Mở rộng thành 2–3 thủ tục và 30–50 tình huống giả có gold source, reviewer
   độc lập và TEST split đóng băng.
4. Chạy retrieval/evaluation trên D1 và phân tích lỗi theo từng câu.
5. Xin công ty duyệt provider + loại dữ liệu trước khi thêm hosted baseline.

### NEXT – Sau khi D1 và hosted baseline được duyệt

1. So sánh template/hosted trên cùng gold set và chốt ngưỡng Gate G2 với mentor.
2. Nhận, kiểm kê và phân loại dataset công ty; không tự động đưa D2 ra provider ngoài.
3. Phân tích lỗi để quyết định có cần embedding/vector search hay chưa.
4. Chốt quyết định G3 và baseline để model local phải vượt qua.

### LATER – Sau khi G2 đạt

1. Model local ≤2B đầu tiên.
2. Quantization/benchmark.
3. Cải thiện RAG/model theo error analysis.
4. Hoàn thiện Docker/deployment demo.

### PARKED – Không triển khai lúc này

- Case Router N–M và cross-conversation memory.
- Summary nhiều tháng và memory graph.
- Transactional outbox, Redis Streams, DLQ phức tạp.
- Socket.IO event/recovery đầy đủ.
- Hybrid RAG + nhiều retriever/reranker ngay từ đầu.
- Full Procedure Engine/AnswerPlan/ExpectedClaimSet.
- Verifier semantic nhiều tầng.
- OTP, tài liệu cá nhân, admin upload/index activation.
- Speculative decoding, autoscaling, Kubernetes.
- Dashboard màu mè và các trang phụ.

## 14. Ownership G1 đã hoàn tất và chuyển giao sang G2

| Người | Ownership | Deliverable tích hợp |
|---|---|---|
| A – Frontend | Login/demo identity, conversation list, chat và error/loading | Gọi Core API thật, không dùng data mock sau khi tích hợp |
| B – Backend | DB schema, auth/session tối thiểu, conversation/message APIs | Lưu history và gọi AI Service thật |
| C – AI/Integration | AI Service contract, provider boundary và telemetry | Mock G1 chạy sau contract ổn định |

Cả nhóm:

- giữ JSON contracts đồng bộ với consumer;
- tích hợp hằng ngày trên branch tích hợp;
- giữ `main` chạy xanh; phát triển phase mới trên branch riêng;
- review chéo và ghi bug chung;
- không để mỗi người làm “module hoàn hảo” hai tuần rồi mới ghép.

Trong Giai đoạn 2:

- **Tú – Data & Gold Set Owner:** danh sách nguồn chính thức, snapshot bất biến,
  chuẩn hóa thủ tục, câu hỏi và expected points/gold source;
- **Minh – Retrieval/RAG Backend Owner:** kiểm tra và ingest data, exact/keyword/BM25,
  Evidence Bundle, nối RAG vào Backend và kiểm tra source ID;
- **Hoan – AI Service, Evaluation & Integration Owner:** hosted-provider adapter được duyệt,
  grounded prompt/output, evaluation harness, Compose/CI và demo end-to-end;
- cả nhóm review chéo gold set; người viết một câu hỏi không tự mình là người duyệt cuối;
- chi tiết path, task ID, contract, checkpoint và Definition of Done nằm trong
  [kế hoạch G2](giai-doan-2/02-phan-cong-giai-doan-2.md).

## 15. Contract cần khóa đầu tiên

Contract G1 tiếp tục ổn định. Trước khi code G2, khóa thêm năm schema nhỏ:

```text
SourceManifest
ProcedureRecord
ProcedureFragment
GoldQuestion
EvidenceBundle + GroundedAnswer
```

Không mở CaseCard, memory dài hạn, Procedure Engine đầy đủ hay verifier semantic nhiều
tầng ở G2. `EvidenceBundle` G2 chỉ là danh sách fragment truy hồi có ID và metadata
nguồn; nó chưa phải toàn bộ Target Architecture trước đây.

## 16. Quy tắc quản trị phạm vi

Một task chỉ được đưa vào sprint khi trả lời đủ:

```text
1. Nó phục vụ gate nào?
2. Nếu không làm thì bản demo hiện tại có thất bại không?
3. Input/output contract là gì?
4. Ai sở hữu?
5. Test nào chứng minh done?
6. Có phương án đơn giản hơn không?
```

Nếu câu 1 hoặc 2 không rõ, chuyển task sang `PARKED`.

Giới hạn công việc:

- mỗi người tối đa một task chính đang làm;
- task nên hoàn tất/tích hợp trong 1–2 ngày;
- cuối ngày branch tích hợp phải chạy; `main` chỉ nhận thay đổi đã review;
- demo end-to-end ít nhất mỗi tuần, tốt hơn là mỗi 1–2 ngày ở giai đoạn đầu.

## 17. Tiêu chí đánh giá theo từng mốc

| Mốc | Đo gì | Không dùng để kết luận gì |
|---|---|---|
| G1 Technical | End-to-end success, history, isolation, error/latency | Chưa kết luận độ chính xác hành chính |
| G2 Domain | Retrieval, citation, answer correctness, abstention | Chưa kết luận local lightweight |
| G3 Local model | Quality gap, VRAM, TTFT, P95, throughput/OOM | Không chọn chỉ bằng số tham số |
| G4 Improvement | Ablation và regression | Không cộng nhiều thay đổi rồi đo chung |
| G5/G6 Product | Task success, security, reliability, SLA | Không tuyên bố production nếu chưa có acceptance |

## 18. Rủi ro và biện pháp

| Rủi ro | Biện pháp |
|---|---|
| Hosted API không được phép nhận dữ liệu công ty | Xin phê duyệt; dùng mock hoặc local small model với data giả |
| Dữ liệu công khai thay đổi theo thời gian/địa phương | Lưu snapshot, source URL, ngày lấy, phạm vi áp dụng và version của gold set |
| Vô tình đưa PII/dữ liệu nội bộ vào API ngoài | Phân loại dữ liệu, allowlist dataset, redact PII và chặn request không được duyệt |
| Cho rằng self-host mặc nhiên an toàn | Kiểm soát access, log, encryption, backup, telemetry và network egress |
| API baseline tốt nhưng local model yếu | Giữ provider adapter; đo gap; cải thiện RAG/SFT hoặc báo trade-off bằng số liệu |
| Nhóm lại kéo kiến trúc parked vào sớm | Mọi task phải gắn Gate/trigger |
| Ba service làm riêng không tích hợp | Contract test + integration hằng ngày |
| RAG phức tạp trước khi có gold data | Exact/keyword baseline và error analysis trước |
| Fine-tune tốn thời gian nhưng không tăng chất lượng | Baseline/oracle test trước; pilot nhỏ; stop rule |
| Giao diện chiếm quá nhiều công sức | Một chat page đủ dùng; styling sau Gate G2/G3 |
| Mentor thay yêu cầu | Ghi acceptance từng mốc; ưu tiên capability có thể demo độc lập |

## 19. Quyết định chốt hiện tại

```text
1. Không implement kiến trúc đầy đủ ngay.
2. Bắt đầu bằng technical vertical slice có Web + Backend + AI Service + PostgreSQL.
3. Tách API boundary nhưng chưa dựng hệ microservice phức tạp.
4. Dùng mock hoặc hosted API được phê duyệt trước; không self-host ở bước đầu.
5. Sau khi chat/history chạy, thêm domain data + RAG tối giản + evaluation.
6. Sau đó mới thay bằng model local ≤2B ưu tiên và benchmark với challenger.
7. Chỉ fine-tune, rerank, queue, Case, verifier khi lỗi/yêu cầu tạo trigger rõ.
8. Mỗi giai đoạn phải qua gate và luôn giữ một bản demo chạy được.
9. Dataset được tách thành D0 smoke, D1 public demo và D2 company real; không trộn ranh giới sử dụng.
10. OpenAI/hosted API chỉ chạy D0/D1 đã được duyệt; D2 mặc định chỉ chạy trong hạ tầng công ty được phê duyệt.
11. Hosted và local phải được benchmark trên cùng một gold set D1 trước khi quyết định model hoặc fine-tune.
```

## 20. Việc làm tiếp theo

1. Giữ tag `g1-v1.0.0` và bằng chứng CI làm mốc so sánh.
2. Quay demo ngắn cho mentor nếu cần; dùng số 56,33 ms đúng với chú thích
   “Mock CI baseline”, không gọi đó là SLA/model benchmark.
3. Nhờ reviewer thứ hai kiểm tra source, fragment và 10 gold question hiện có.
4. Lấy nguồn chi tiết chính thức rồi mở rộng `data/demo_public/` lên 2–3 thủ tục,
   30–50 câu; chỉ khi đó mới cho `--mode publish` pass.
5. Chạy retrieval + grounded evaluation D1 và chốt ngưỡng với mentor.
6. Xin phê duyệt hosted provider; dùng secret mới qua `.env`/secret store, tuyệt
   đối không tái sử dụng key đã xuất hiện trong chat.

## 21. Câu trình bày với mentor

> **Nhóm đề xuất không triển khai toàn bộ kiến trúc cùng lúc. Mốc đầu tiên là một vertical slice gồm Web, Core Backend, PostgreSQL và AI Service tách API: đăng nhập/demo identity, chat, lưu lịch sử và nhận phản hồi end-to-end. Hosted hoặc mock model chỉ dùng để khóa luồng. Sau đó nhóm thêm dữ liệu hành chính và RAG có đánh giá, rồi mới thay bằng model local lightweight và mở từng tính năng nâng cao dựa trên lỗi thực tế. Mỗi mốc có demo và tiêu chí nghiệm thu riêng.**

## 22. Definition of Done của chiến lược

Chiến lược này được xem là hoạt động đúng khi:

- team luôn biết duy nhất mốc nào đang làm;
- `main` có vertical slice chạy xanh và tag `g1-v1.0.0` để quay lại;
- mỗi phase tạo một demo và báo cáo đo lường;
- không triển khai feature parked nếu chưa có trigger;
- local lightweight vẫn được hoàn thành, không bị hosted API thay thế;
- kiến trúc nâng cao được tái sử dụng có chọn lọc, không bị mất.
