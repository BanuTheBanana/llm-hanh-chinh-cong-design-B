# Hồ sơ kỹ thuật hệ thống LLM hành chính công hiện tại

Ngày lập: **15/09/2026**
Phạm vi: trạng thái hệ thống sau G3, G4 và các vòng phát triển G5 đến ngày lập tài liệu
Mục đích: cung cấp một tài liệu duy nhất để thành viên nhóm hiểu hệ thống đang có gì,
đã cải thiện bằng kỹ thuật nào, mức nào đã được kiểm chứng và phần nào chưa được nghiệm thu.

## 1. Kết luận điều hành

Hệ thống hiện là một ứng dụng RAG chạy local, có Web, Backend, PostgreSQL, ba dịch vụ
model, dịch vụ nguồn MCP, quản lý hội thoại nhiều lượt, kiểm chứng câu trả lời và thu thập
feedback. Runtime đang phục vụ release nội bộ gồm **34 thủ tục, 34 nguồn và 139 fragment**
đã được allowlist từ dữ liệu công ty.

Hệ thống đã tiến bộ từ tìm kiếm một câu đơn sang:

- nhận diện một hoặc nhiều trường thông tin trong cùng câu hỏi;
- giữ, đổi, xóa và làm rõ context theo từng conversation;
- sửa một số lỗi gõ và hiểu một số cách nói tương đương bằng lớp CPU nhẹ;
- dùng Exact/BM25 trước, dense embedding chỉ làm fallback có ngưỡng;
- tạo AnswerPlan từ fragment đã duyệt trước khi gọi model sinh;
- bắt buộc citation, kiểm tra nguyên văn claim và fallback trích xuất khi model không đạt;
- lưu feedback hai trục nhưng không tự biến feedback thành dữ liệu huấn luyện.

Tuy nhiên, trạng thái chính xác phải ghi là **hoàn tất tích hợp kỹ thuật, chưa đạt nghiệm
thu chất lượng intent/context**. FINAL TEST V3 độc lập chỉ đạt 81,67% full-state theo lượt
và 13/20 hội thoại đúng toàn chuỗi. Các policy mới hơn V3 đang giúp Web hoạt động tốt hơn
trên regression và tình huống thực tế, nhưng chưa có holdout độc lập mới nên chỉ được gọi
là runtime phát triển nội bộ.

## 2. Mục tiêu và ranh giới hệ thống

### 2.1. Mục tiêu hiện tại

Hệ thống trả lời câu hỏi về thủ tục hành chính dựa trên dữ liệu đã được duyệt, chạy local,
giữ được context hội thoại và chỉ phát biểu nội dung có evidence. Mục tiêu thiết kế là:

1. ưu tiên độ đúng nguồn và khả năng truy vết hơn văn phong tự do;
2. không bịa field mà corpus không có;
3. dùng model nhỏ nhất có thể nhưng vẫn vượt gate chất lượng;
4. có thể thay model mà không thay contract Backend;
5. dữ liệu TEST, corpus công ty và trọng số model không bị commit lên Git.

### 2.2. Những gì chưa được tuyên bố

- Chưa phải hệ thống tư vấn pháp lý hoàn chỉnh.
- Chưa chứng minh độ đúng pháp lý bằng reviewer độc lập trên toàn corpus.
- Chưa có SLA tải lớn, monitoring/alert và backup/restore production.
- Chưa có RBAC quản trị nguồn ở mức production.
- Chưa kết nối trực tiếp dữ liệu nhà nước realtime.
- Chưa chốt cấu hình lightweight cuối cho máy phổ thông.

## 3. Kiến trúc triển khai

### 3.1. Các service đang chạy

| Service | Vai trò | Công nghệ/cấu hình chính |
|---|---|---|
| Web | Đăng nhập, hội thoại, citation, feedback | React/TypeScript, build qua Nginx |
| Backend | API, state, retrieval, AnswerPlan, persistence | FastAPI, SQLAlchemy, Pydantic |
| PostgreSQL | User, session, conversation, message, context, feedback | PostgreSQL 16 |
| AI Service | Điều phối intent và generation provider | FastAPI, HTTP local-only |
| Generation model | Sinh đáp án có evidence | Qwen3-1.7B + QLoRA full-corpus, llama.cpp |
| Intent model | Phân tích câu mơ hồ thành patch JSON | Qwen3-4B-Instruct-2507 + LoRA hard-v2, llama.cpp |
| Embedding model | Semantic procedure routing fallback | Qwen3-Embedding-0.6B, llama.cpp embedding mode |
| Source Service | Registry cập nhật nguồn đã review qua MCP | Python MCP service, snapshot bất biến |

Tám service đều có health check. Model và corpus được bind mount read-only từ máy host;
PostgreSQL và registry nguồn dùng Docker volume. Các cổng public của demo chỉ bind vào
`127.0.0.1`.

### 3.2. Luồng end-to-end

```text
User
  │
  ▼
Web ── cookie/session ──► Backend
                            │
                            ├─► nạp conversation state từ PostgreSQL
                            │
                            ├─► AI Service: normalize + intent/context
                            │       ├─ deterministic policy nếu chắc chắn
                            │       └─ Qwen3-4B intent nếu mơ hồ
                            │
                            ├─► Exact/alias/code → BM25
                            │       └─ dense Qwen3-Embedding-0.6B khi cần
                            │
                            ├─► Evidence Bundle + Source MCP published override
                            │
                            ├─► AnswerPlan kiểm tra đủ field/evidence
                            │
                            ├─► Qwen3-1.7B generation
                            │
                            ├─► verifier → retry một lần → extraction fallback
                            │
                            └─► lưu message/context/grounding → Web hiển thị citation
```

Backend là chủ sở hữu trạng thái và quyết định cuối. Model chỉ đề xuất patch hoặc câu trả
lời; model không được tự tạo user ID, conversation ID, message ID, corpus version hay nguồn.

## 4. Dữ liệu và corpus

### 4.1. Từ dữ liệu công ty đến release phục vụ

Dữ liệu đầu vào đầy đủ ban đầu có 42 dòng nguồn, ánh xạ thành 38 thủ tục và 202 fragment
trước kiểm duyệt. Pipeline không đưa toàn bộ dữ liệu đó thẳng vào RAG. Sau review:

- 34 thủ tục không conflict được đưa vào controlled release;
- 34 nguồn tương ứng được phép phục vụ;
- 139 fragment được allowlist;
- 4 thủ tục conflict bị quarantine;
- field thiếu hoặc mơ hồ giữ trạng thái không đủ dữ liệu.

Release hiện tại là `company-tthc-9c38dde8-v1-controlled-v1`. Corpus runtime được khóa
bằng version, số lượng nguồn và fingerprint SHA-256. Khi load corpus, Backend kiểm:

- schema từng JSONL;
- ID nguồn, thủ tục và fragment không trùng;
- fragment thuộc đúng source và procedure;
- source URL/domain hợp lệ;
- review status được phép;
- raw file tồn tại trong dataset root và khớp SHA-256;
- jurisdiction và procedure code không mâu thuẫn;
- fixture D0 không bị trộn với D2 thật.

Nếu một kiểm tra thất bại, corpus không được nạp và endpoint trả trạng thái không sẵn sàng,
thay vì âm thầm dùng dữ liệu lỗi.

### 4.2. Quyết định theo field

Pipeline có **304/304 quyết định procedure–field**:

- 139 field `APPROVED` có fragment phục vụ;
- 112 field `INSUFFICIENT_DATA`;
- 21 field mơ hồ;
- 32 field thuộc thủ tục conflict được cách ly.

Các field nghiệp vụ chuẩn gồm:

1. `receiving_authority` – nơi/cơ quan tiếp nhận;
2. `required_documents` – thành phần hồ sơ;
3. `fees` – lệ phí;
4. `processing_times` – thời gian giải quyết;
5. `submission_methods` – hình thức nộp;
6. `steps` – trình tự;
7. `legal_bases` – căn cứ pháp lý;
8. `applicant_scope` – đối tượng/phạm vi áp dụng.

Không có fragment cho field nào thì hệ thống phải trả `INSUFFICIENT_DATA`; không dùng LLM
để điền phần thiếu. Đây là cơ chế an toàn trung tâm của toàn pipeline.

## 5. Retrieval và chọn thủ tục

### 5.1. Tuyến lexical xác định

Tuyến đầu tiên chạy hoàn toàn trong Backend:

1. chuẩn hóa Unicode, chữ thường, khoảng trắng và dấu;
2. so exact tên thủ tục, alias và procedure code;
3. ưu tiên tên cụ thể dài hơn nếu tên thủ tục này chứa tên thủ tục khác;
4. nếu không exact, chạy BM25 trên tên, alias, code và category;
5. loại stopword mô tả field như “hồ sơ”, “lệ phí”, “thời gian” khỏi phần định danh thủ tục;
6. chỉ nhận BM25 winner khi vượt `ROUTING_MIN_SCORE`, chênh điểm tối thiểu và tỷ lệ
   so với ứng viên thứ hai;
7. nếu không đủ chắc chắn, yêu cầu làm rõ thay vì chọn đại.

Việc loại từ field khỏi procedure routing đã khắc phục lỗi từ chung như “hồ sơ” hoặc “số”
đẩy câu hỏi sang thủ tục không liên quan.

### 5.2. Dense fallback

`HybridProcedureRouter` dùng Qwen3-Embedding-0.6B khi câu không chứa exact alias và có ít
nhất hai token định danh sau khi bỏ stopword. Kỹ thuật đang dùng:

- embedding catalog thủ tục và cache theo corpus fingerprint;
- thêm instruction tiếng Việt vào query embedding;
- cosine similarity cho dense score;
- chuẩn hóa BM25 thành lexical score;
- fusion: `0.55 × dense + 0.45 × lexical`;
- chỉ nhận khi score tối thiểu 0,52 và margin với hạng hai tối thiểu 0,04.

Embedding timeout, HTTP lỗi, vector không hữu hạn hoặc sai dimension đều trả `None` và quay
về lexical route. Dense retrieval không được làm endpoint RAG ngừng hoạt động.

Trong DEV hiện tại Exact/BM25 đã đạt toàn bộ ca nên chưa được phép tuyên bố dense cải thiện
tỷ lệ tổng. Dense chỉ có unit test riêng cho cách diễn đạt semantic không khớp từ khóa.

## 6. Intent và context: cấu trúc kỹ thuật

### 6.1. Vì sao cách cũ chưa đủ

Phiên bản đầu dựa nhiều vào regex/từ khóa, phù hợp câu đơn nhưng yếu với:

- một câu hỏi nhiều field;
- câu nối tiếp như “còn bao lâu?”;
- phủ định và sửa lời trước;
- đổi thủ tục trong cùng conversation;
- câu trả lời ngắn cho câu hỏi làm rõ;
- địa điểm kể trong hoàn cảnh so với jurisdiction pháp lý;
- lỗi gõ và cách nói đời thường.

Do đó G5 chuyển sang dialogue state tracking có schema và patch từng lượt.

### 6.2. Contract intent/context

Model/policy phải trả `g5-intent-context-v2`, gồm:

- `dialogue_act`: `ASK_INFORMATION`, `PROVIDE_CLARIFICATION`, `CORRECT_CONTEXT`,
  `RESET_CONTEXT`, `GREET` hoặc `OUT_OF_SCOPE`;
- `topic_action`: `KEEP`, `SWITCH`, `RESET` hoặc `UNRESOLVED`;
- patch cho bốn slot: `procedure_id`, `field_intents`, `jurisdiction`, `as_of`;
- mỗi slot dùng thao tác `KEEP`, `SET` hoặc `CLEAR`;
- `SET/CLEAR` phải có evidence là đoạn nguyên văn trong user message hiện tại.

Backend kiểm thêm các bất biến ngoài JSON Schema:

- procedure `SET` phải nằm trong catalog đang phục vụ;
- `SWITCH` bắt buộc có procedure `SET`;
- procedure `SET` chỉ hợp lệ với `SWITCH`;
- `RESET_CONTEXT` và topic `RESET` phải đồng nhất;
- `GREET/OUT_OF_SCOPE` không được sửa state;
- clarification phải điền đúng slot đang pending;
- evidence không được trỏ message khác hoặc quote ngoài câu người dùng.

### 6.3. State được lưu

`g5-context-state-v1` lưu theo từng conversation:

- `corpus_version`;
- `procedure_id`;
- danh sách `field_intents`;
- `jurisdiction`;
- ngày tra cứu `as_of`;
- `pending_clarification`;
- `source_message_ids` cho biết mỗi slot đến từ lượt nào;
- tối đa 64 `applied_message_ids` để chống áp dụng trùng;
- `revision` tăng sau mỗi lượt được áp dụng.

Nếu corpus version thay đổi, state cũ tự reset để không truy vấn ID của catalog khác. State
G4 được migrate sang G5 một lần. Cùng message ID không được reducer áp dụng hai lần, bảo đảm
retry API không nhân đôi thay đổi context.

Khi đổi procedure, reducer tự xóa field, jurisdiction, ngày và pending clarification phụ
thuộc thủ tục cũ trước khi áp patch mới. Cách này ngăn “kết hôn” kế thừa phí hoặc nơi nộp
của “khai sinh”.

## 7. Những kỹ thuật đã dùng để cải thiện intent/context

### 7.1. Deterministic-first, model-last

Runtime hiện không gọi Qwen cho mọi câu. `resolve_high_confidence_without_model` xử lý trực
tiếp các ca có bằng chứng chắc chắn:

- reset rõ ràng;
- lời xác nhận ngắn khi đang có context;
- procedure và field xuất hiện rõ;
- đổi chủ đề có tín hiệu rõ;
- nhắc lại cùng procedure;
- yêu cầu toàn bộ field;
- địa điểm chỉ được kể như hoàn cảnh.

Tuyến này tạo patch đúng contract, có evidence và ghi `policy_actions`. Chi phí intent của
câu rõ ràng là 0 input token, 0 output token và thường chỉ vài mili giây. Qwen3-4B chỉ xử lý
ca mơ hồ hơn. Đây là tối ưu quan trọng cho latency và giảm tải, dù service 4B vẫn đang được
nạp trong cấu hình nghiên cứu.

### 7.2. Compact schema và constrained decoding

Trước đây model phải tự sinh cả evidence object dài nên có thể chạm trần 384 token và không
đóng được JSON. Phiên bản hiện tại cho model sinh schema compact chỉ gồm act, action, op và
value. AI Service đáng tin cậy gắn message ID cùng evidence quote sau đó.

llama.cpp được gọi với:

- `response_format` chứa JSON Schema;
- non-thinking mode;
- temperature 0;
- top-k 1;
- seed 42;
- output intent bị giới hạn ở 192 token tại AI Service.

Provider parse bằng Pydantic, kiểm semantic, áp policy và retry tối đa một lần. Timeout hoặc
contract lỗi có thể quay về deterministic G4 fallback nếu cờ fallback bật. Fallback được log
riêng và không được tính là điểm của model.

### 7.3. Nhận diện multi-intent

Field detector dùng tập cue theo từng field và so theo biên token, tránh substring ngẫu nhiên.
Một câu có thể tạo nhiều field cùng lúc. Ví dụ câu hỏi hồ sơ, nơi nộp, online, thời gian và phí
sẽ tạo năm field; retrieval bắt buộc lấy evidence cho từng field.

Với “tất cả mọi thứ”, policy tạo danh sách tám field chuẩn, sau đó Backend lọc theo
`field_evidence` thực sự có ở procedure hiện tại. Nhờ vậy khai sinh trả năm field có dữ liệu
và năm citation, thay vì thất bại vì ba field không tồn tại.

### 7.4. Phân biệt địa điểm kể chuyện và jurisdiction

Một câu như “Tôi đang ở phường Tăng Nhơn Phú, vừa có con...” chứa địa điểm nhưng không nhất
thiết yêu cầu kiểm tra phạm vi pháp lý. Policy dùng hai lớp tín hiệu:

- regex phát hiện tên cấp hành chính;
- regex “incidental location” phát hiện cấu trúc người dùng đang ở/sống/cư trú tại địa điểm.

Địa điểm kể chuyện không tự biến thành legal filter. Nếu người dùng hỏi rõ “thủ tục này có áp
dụng ở quận X không”, jurisdiction mới được chuyển cho retrieval; scope không tồn tại trong
nguồn sẽ abstain.

### 7.5. Chuyển chủ đề và nhắc lại chủ đề

Policy xử lý các tín hiệu “đổi sang”, “chuyển hẳn sang”, “quay lại”, “không phải... mà là”.
Procedure mới chỉ được chọn khi catalog có một ứng viên duy nhất. Khi người dùng chỉ nhắc lại
cùng procedure mà không hỏi field, field cũ được clear và hệ thống hỏi người dùng muốn xem
mục nào; điều này ngăn reuse field cũ ngoài ý muốn.

### 7.6. Chuẩn hóa lỗi gõ và cách nói tương đương

`query_normalizer.py` tạo một bản routing-only; câu gốc vẫn được lưu và hiển thị. Pipeline:

1. Unicode NFD, bỏ dấu cho việc so khớp, chữ thường và chuẩn hóa dấu câu;
2. chuẩn hóa chữ viết tắt được duyệt như CCCD/CMND;
3. mở rộng cụm nghĩa rõ: “qua mạng” → “trực tuyến”, “chờ bao lâu” → “thời gian”,
   “tốn tiền” → “lệ phí”, “nộp chỗ nào” → “nơi tiếp nhận”;
4. RapidFuzz so token với từ điển nghiệp vụ và từ dài lấy động từ catalog;
5. Levenshtein tối đa 1 ký tự cho token ngắn, 2 cho token dài;
6. yêu cầu cùng ký tự đầu, score tối thiểu 80 và chênh ứng viên tối thiểu 8;
7. bảo vệ số, từ ngắn mơ hồ và các từ hội thoại thông dụng.

Thiết kế bảo thủ này sửa được `khai sih`/`kha sin` nhưng không tiếp tục sửa sai `đúng` thành
`đang`, `cơ quan` thành `cơ qua` hoặc `ngữ cảnh` thành `ngữ can`. Nếu không chắc chắn, hệ
thống giữ nguyên và chuyển sang model/làm rõ.

### 7.7. Evidence provenance và bounded quote

Mỗi slot được `SET/CLEAR` giữ ID message nguồn. Với câu dài hơn 300 ký tự, AI Service chọn
một cửa sổ nguyên văn liên quan nhất thay vì cắt tùy ý hoặc để model diễn giải lại. Backend
kiểm quote là substring thật của user message. Nhờ đó có thể audit tại sao state thay đổi.

## 8. RAG có nguồn và AnswerPlan

### 8.1. Evidence Bundle

Sau khi xác định procedure và field, retrieval chỉ lấy fragment:

- thuộc đúng procedure;
- nằm trong allowlist của field;
- không thuộc field được đánh dấu thiếu;
- đúng jurisdiction nếu có filter;
- còn hiệu lực tại `as_of` nếu người dùng yêu cầu ngày cụ thể.

Bundle chứa query, corpus version, data classification, evidence ID và metadata nguồn.
Không có evidence thì Backend trả `NEED_CLARIFICATION` hoặc `INSUFFICIENT_DATA` trước khi
gọi generation model.

### 8.2. AnswerPlan

AnswerPlan là lớp trung gian server-owned. Với từng requested field, Backend yêu cầu tập
fragment lấy được phải khớp chính xác manifest `field_evidence`. Plan chỉ có ba trạng thái:

- `ANSWER`: đủ toàn bộ field và evidence;
- `NEED_CLARIFICATION`: chưa biết field người dùng muốn hỏi;
- `INSUFFICIENT_DATA`: thiếu nguồn, sai hiệu lực hoặc evidence không đầy đủ.

Nếu một field thiếu, plan không trộn các claim còn lại thành câu trả lời có vẻ hoàn chỉnh.
Nếu nội dung render vượt ngân sách 8.000 ký tự, hệ thống abstain thay vì cắt mất điều kiện phí,
thời gian hoặc fragment ở cuối.

### 8.3. Verifier, retry và extraction fallback

Generation model nhận evidence và AnswerPlan, nhưng output vẫn phải qua verifier:

- status model phải bằng status plan;
- tập citation phải bằng tập fragment của plan;
- nội dung claim phải khớp một trong các dạng render đã duyệt sau chuẩn hóa khoảng trắng;
- số, điều kiện và dấu câu trong claim không được tự thay đổi.

Nếu candidate đầu không đạt, provider retry một lần. Nếu vẫn không đạt, Backend render
trực tiếp từ AnswerPlan theo extraction fallback. Web hiển thị rõ candidate hay fallback,
không giấu việc model thất bại.

## 9. Fine-tune model sinh câu trả lời

### 9.1. Chuẩn bị SFT full corpus

Controlled release được chuyển thành SFT v1 với split theo procedure, không chỉ tách ngẫu
nhiên theo câu:

| Split | Số procedure | Số mẫu render | Vai trò |
|---|---:|---:|---|
| TRAIN | 24 | 384 | Huấn luyện |
| VALIDATION | 5 | 40 | Chọn candidate |
| TEST | 5 | 40 | Gold private, khóa riêng |

TRAIN dùng hai biến thể trình bày; VALIDATION/TEST mỗi cặp procedure–field chỉ dùng một mẫu.
Ba split không trùng procedure. Trainer từ chối chạy nếu bundle có TEST, sai version/hash,
citation sai hoặc input vượt max length.

### 9.2. Kỹ thuật huấn luyện

Các candidate dùng QLoRA:

- base weight lượng tử NF4 và giữ đông;
- double quantization;
- BF16 compute;
- LoRA rank 16;
- seed 42;
- một epoch;
- learning rate `2e-4`;
- max length 2304;
- non-thinking prompt và contract giống nhau.

QLoRA cho phép thử nhiều model trên GPU cá nhân mà không fine-tune toàn bộ trọng số. Artifact
adapter, revision base, manifest và hash được khóa để tái lập.

### 9.3. Kết quả so sánh generation candidate

| Chỉ số VALIDATION | Qwen3-1.7B | Qwen3.5-2B | Qwen3-4B |
|---|---:|---:|---:|
| Contract hợp lệ | 97,5% | 97,5% | 97,5% |
| Đúng trạng thái | **95%** | 90% | 92,5% |
| Citation recall | **95%** | **95%** | 90% |
| Bao phủ claim | **95%** | **95%** | 90% |
| Abstention đúng | **95%** | 85% | **95%** |
| P95 | 9,32 giây | **6,93 giây** | 11,41 giây |
| Peak VRAM inference | 3,22 GB | **2,04 GB** | 3,71 GB |

Qwen3-1.7B + QLoRA r16 được chọn làm generation candidate vì chất lượng tổng thể cao nhất
hoặc đồng hạng, nhẹ hơn 4B. Adapter đã xuất F16 GGUF và được gắn vào llama.cpp runtime.
TEST generation kín vẫn không được dùng để chọn lại cấu hình.

## 10. Fine-tune model intent/context

Intent/context là task khác generation nên không tái sử dụng adapter full-corpus. Bộ huấn
luyện intent hard-v2 gồm 252 ca D0 hư cấu đã review, DEV gồm 60 ca, tập trung vào direct,
follow-up, correction/switch, reset, scope/date và boundary.

Qwen3-4B + LoRA r16 được chọn sau pilot vì vượt Qwen3.5-2B về joint/full state. Kết quả DEV:

| Cấu hình | Joint state | Full state | P95 |
|---|---:|---:|---:|
| Adapter vòng đầu | 75,00% | 63,33% | 2,52 giây |
| Hard-v2 model thuần | 98,33% | 86,67% | 3,12 giây |
| Hard-v2 + policy v1 | 98,33% | 95,00% | 3,14 giây |

Policy làm tăng điểm pipeline nhưng báo cáo luôn tách điểm model thuần và pipeline. Sau đó ba
holdout độc lập V1–V3 đều không qua toàn bộ gate hội thoại; V3 cuối đạt:

- schema/semantic: 100%;
- dialogue act: 93,33%;
- topic action: 96,67%;
- full-state theo lượt: 81,67%;
- field macro-F1: 93,12%;
- hội thoại đúng toàn chuỗi: 13/20, tương đương 65%.

Vì vậy model intent 4B hiện là internal candidate, không phải accepted release. V1–V3 đã mở
chỉ còn giá trị regression và không được dùng làm TEST lại.

## 11. Cập nhật nguồn qua MCP

Source Service không cho Backend đọc tùy ý Internet. Nó quản lý snapshot theo cặp
`procedure_id + field` với vòng đời:

```text
STAGE → PENDING_REVIEW → APPROVE → APPROVED → PUBLISH → PUBLISHED
                       └─ REJECT
PUBLISHED mới thay bản cũ; bản cũ thành SUPERSEDED và có thể ROLLBACK.
```

Kỹ thuật an toàn:

- mutation yêu cầu reviewer token dài tối thiểu và so bằng HMAC-safe comparison;
- snapshot bất biến, có version, content SHA-256, reviewer và timestamp;
- PII scanner chặn email, điện thoại và mẫu dữ liệu nhạy cảm;
- procedure phải nằm trong allowlist corpus;
- MCP không được tạo field mới không tồn tại trong base corpus;
- Backend chỉ cho hostname local trong allowlist, không follow redirect;
- chỉ snapshot `PUBLISHED` và còn hiệu lực mới được dùng;
- lỗi MCP trả về corpus read-only đang duyệt, không làm hỏng câu trả lời.

MCP hiện là registry nội bộ thử nghiệm quy trình review/publish/rollback, chưa phải nguồn pháp
lý realtime từ cơ quan nhà nước.

## 12. PostgreSQL, hội thoại và idempotency

Các bảng chính:

- `users`: người dùng demo;
- `sessions`: chỉ lưu hash token và thời hạn;
- `conversations`: ownership, title và `rag_context` JSONB;
- `messages`: user/assistant, request ID, status, grounding và retrieval filters;
- `message_feedback`: hai nhãn feedback cùng provenance model/corpus/prompt.

Unique constraint trên `conversation_id + client_message_id` chống gửi trùng từ Web. Unique
constraint trên `conversation_id + request_id + role` chống tạo lại assistant response. Message
có `pending/completed/failed`, cho phép retry mà không làm mất lượt người dùng.

Backend commit/release transaction sau retrieval trước khi gọi model ngoài tiến trình, tránh
giữ transaction database trong suốt thời gian inference.

## 13. Feedback người dùng

Mỗi assistant message hoàn tất có hai trục độc lập:

- phù hợp / không phù hợp;
- hài lòng / chưa hài lòng;
- lý do tùy chọn tối đa 1.000 ký tự.

Chỉ chủ conversation được tạo, sửa, xem hoặc xóa feedback của message đó. Bản ghi giữ provider,
model, corpus version và prompt version để phân tích lỗi theo đúng snapshot runtime.

Feedback không tự trở thành gold label và không tự đi vào fine-tune. Quy trình đúng là export
vùng review, ẩn thông tin nhạy cảm, reviewer gán nhãn rồi mới đưa vào TRAIN của vòng sau.

## 14. Web và khả năng quan sát câu trả lời

Web hiện hỗ trợ:

- đăng nhập và session cookie;
- danh sách conversation và lịch sử message;
- retry lượt failed bằng client message ID cũ;
- trạng thái `ANSWER`, `NEED_CLARIFICATION`, `INSUFFICIENT_DATA`;
- checklist field đã kiểm chứng;
- citation gồm source title và fragment ID;
- corpus/knowledge version và thời điểm nguồn được duyệt;
- chỉ mở URL nguồn sau khi kiểm tra scheme an toàn;
- hiển thị candidate pass hay extraction fallback;
- form feedback hai trục.

Web hiện ưu tiên hiển thị đầy đủ citation. Bố cục chưa tối ưu cho câu nhiều field và màn hình
rộng; đây là vấn đề presentation, không được giải quyết bằng cách bỏ fragment ID.

## 15. Bảo mật và fail-safe

Các chốt đã có:

- CORS chỉ cho origin cấu hình;
- session token chỉ lưu hash trong database;
- cookie HttpOnly, SameSite Lax; Secure bật theo môi trường;
- mọi conversation/message/feedback đều kiểm ownership;
- model provider, embedding và MCP chỉ cho HTTP hostname local trong allowlist;
- không follow redirect và không dùng proxy môi trường;
- corpus/model mount read-only;
- PII scanner trước retrieval/source staging;
- source hash, corpus fingerprint, model revision và adapter hash được khóa;
- D0 fixture bị cấm ở production;
- dữ liệu D2 cần bật quyền rõ ràng;
- lỗi model, embedding hoặc MCP có fallback/abstention cụ thể.

Phần còn thiếu cho production gồm quản trị secret chuẩn, RBAC reviewer, TLS/reverse proxy,
audit log tập trung, rate limit, backup/restore định kỳ và quy trình ứng phó sự cố.

## 16. Trạng thái lightweight

Runtime hiện nạp ba model:

1. Qwen3-1.7B generation;
2. Qwen3-4B intent;
3. Qwen3-Embedding-0.6B.

Do đó không nên lấy máy 16 GB VRAM hiện tại làm định nghĩa lightweight chung. Những gì đã nhẹ:

- Exact/BM25 và deterministic intent chạy CPU;
- câu rõ không gọi intent LLM;
- generation candidate đã giảm từ 4B xuống 1.7B;
- embedding chỉ 0.6B và cache catalog;
- QLoRA/quantization giảm chi phí huấn luyện và phục vụ.

Những gì chưa nhẹ:

- intent 4B vẫn phải resident để xử lý câu mơ hồ;
- ba model service đồng thời làm tăng VRAM/RAM và thời gian khởi động;
- chưa benchmark cấu hình chạy tuần tự/offload cho máy không có GPU 16 GB.

Đích nghiên cứu tiếp theo là thay intent 4B bằng 1.7B/2B đã fine-tune hoặc dùng một model chung
được multiplex theo task, nhưng chỉ thực hiện nếu holdout chứng minh không giảm chất lượng.

## 17. Kết quả kiểm thử hiện tại

Sau vòng chuẩn hóa lỗi gõ và multi-intent ngày 15/09:

- mã runtime hiện khai báo `POLICY_VERSION = g6-intent-context-policy-v9`;
- đây là nhãn policy phát triển nội bộ mới hơn policy v3 đã chạy FINAL TEST V3, **không phải**
  một lần nghiệm thu độc lập mới và không được dùng để thay thế kết quả 81,67% đã ghi nhận;

- AI Service: **125 test pass**, Ruff pass;
- Backend: **254 test pass, 1 skip có chủ đích**, test dùng PostgreSQL 16 schema riêng;
- Docker: **8/8 container healthy**;
- Backend `/health`: `ok`;
- Web G5: `http://127.0.0.1:3005`.

Các ca runtime đã kiểm:

| Ca | Kết quả |
|---|---|
| `Tôi muốn làm giấy khai sih cho em bé` | Nhận đúng khai sinh, hỏi field cần tra cứu |
| `Tất cả mọi thứ` | Trả 5 field có dữ liệu, 5 citation |
| `Nộp qua mạng được không và chờ bao lâu?` | Giữ context, trả 2 field, 2 citation |
| `Nộp chỗ nào và có tốn tiền không?` | Trả nơi tiếp nhận và lệ phí, 2 citation |
| Câu dài khai sinh hỏi 5 ý | Đúng procedure, đủ 5 field/evidence |
| Chuyển từ khai sinh sang kết hôn | Không trộn fragment procedure cũ |
| Reset | Xóa state, không gọi RAG vô nghĩa |

Các số test code chứng minh regression kỹ thuật, không thay thế holdout chất lượng độc lập.

## 18. Các hạn chế đã quan sát trực tiếp

### 18.1. Câu xác nhận lại

`Vậy là giấy khai sinh chỉ có 8 nghìn một bản thôi hả?` hiện có thể bị coi là topic-only và
quay lại hỏi field. Hệ thống cần dialogue act xác nhận/đối chiếu claim trước, sau đó trả:
“bản chính không thu phí; bản sao 8.000 đồng/bản”.

### 18.2. Phép trừ hồ sơ người dùng đã có

`Tôi có căn cước rồi thì còn bổ sung gì nữa?` hiện nhận đúng field hồ sơ nhưng có thể trả lại
cả danh sách. State hiện lưu procedure/field/scope/date, chưa lưu fact inventory như
`documents_already_have`. Vì vậy chưa thể tính chính xác tập giấy tờ còn thiếu.

### 18.3. Coreference dài

Các từ “cái đó”, “bản kia”, “trường hợp của tôi”, hoặc quay lại một claim cách nhiều lượt chưa
có entity/claim memory rõ ràng. Chỉ mở rộng regex sẽ không giải quyết triệt để.

### 18.4. Thiếu dữ liệu nguồn

Nhiều thủ tục không có `steps`, `legal_bases`, `applicant_scope`. Đây là lỗi coverage nguồn,
không phải lỗi model. Hệ thống phải tiếp tục abstain đến khi có snapshot được reviewer duyệt.

## 19. Kế hoạch cải thiện tiếp theo

### Ưu tiên 1 – Context factual và xác nhận claim

Mở rộng state bằng cấu trúc có provenance:

- `last_answered_claims`: field, value hash, fragment IDs và lượt trả lời;
- `user_facts`: loại giấy tờ đã có, đối tượng, địa điểm, quan hệ và evidence message;
- dialogue act `CONFIRM_CLAIM`/`CORRECT_CLAIM` hoặc policy tương đương;
- resolver cho “đó/kia/cái này/bản này” dựa trên claim gần nhất, không dựa toàn lịch sử;
- phép set difference giữa required documents và documents already have.

Mọi fact phải có message ID, có TTL hoặc reset khi đổi procedure, và không được ghi vào trọng số
model. Cần test phủ định như “tôi chưa có CCCD” để không ghi nhầm là đã có.

### Ưu tiên 2 – Bộ dữ liệu intent/context vòng mới

- Không tái dùng V1–V3 làm TEST.
- Chuyển lỗi đã biết thành TRAIN/DEV có review.
- Tạo nhóm paraphrase, typo, xác nhận claim, hồ sơ đã có, correction và long-context.
- Chia theo conversation/template/procedure để tránh leakage.
- Khóa candidate trước rồi tạo một holdout mới do reviewer giữ.

### Ưu tiên 3 – Chốt kiến trúc lightweight

Benchmark trên cùng workload và cùng API:

- deterministic + intent 1.7B;
- deterministic + intent 2B;
- deterministic + intent 4B hiện tại;
- một model 1.7B/2B dùng chung intent và generation;
- CPU/GPU offload và load-on-demand nếu cần.

Gate phải gồm full-state, conversation exact match, field macro-F1, citation, abstention,
P50/P95, peak RAM/VRAM, kích thước artifact và cold-start. Chọn model nhỏ nhất vượt tất cả
ngưỡng bắt buộc, không chọn chỉ vì loss thấp hoặc chạy được trên máy hiện tại.

### Ưu tiên 4 – Vận hành

- backup/restore PostgreSQL và Source Service;
- log rotation cho Docker;
- metrics theo stage: normalization, intent, retrieval, generation, verifier;
- cảnh báo tỷ lệ fallback/abstention tăng;
- giao diện gom citation theo field;
- quy trình review feedback trước khi đưa vào dữ liệu.

## 20. Bản đồ mã nguồn

| Hạng mục | Tệp/thư mục chính |
|---|---|
| Query normalization | `ai-service/app/query_normalizer.py` |
| Intent policy | `ai-service/app/intent_context_policy.py` |
| Intent provider | `ai-service/app/providers/local_intent_context.py` |
| Intent prompt | `ai-service/app/prompts/intent-context-v2.txt` |
| Context contract/reducer | `backend/app/rag/g5/intent_context.py` |
| Legacy context fallback | `backend/app/rag/g4/context.py` |
| Exact/BM25 retrieval | `backend/app/rag/g3/retrieval.py` |
| Dense hybrid router | `backend/app/rag/g5/hybrid.py` |
| Corpus validation | `backend/app/rag/corpus.py`, `backend/app/rag/g3/validator.py` |
| AnswerPlan/verifier | `backend/app/rag/answer_plan.py` |
| Grounding orchestration | `backend/app/rag/grounding.py`, `planned_grounding.py` |
| Source MCP binding | `backend/app/rag/g5/source_mcp.py` |
| Source registry | `source-service/app/store.py`, `server.py` |
| Persistence/API | `backend/app/models.py`, `main.py` |
| Web | `web/src/App.tsx`, `web/src/services/api.ts` |
| Full-corpus SFT | `tools/data/g5_pipeline/full_corpus_sft.py` |
| QLoRA generation | `training/train_qlora.py` |
| QLoRA intent | `training/train_intent_context_qlora.py` |
| Batch benchmark | `training/overnight_runner.py`, `evaluate_adapter.py` |
| Docker runtime | `compose.yaml`, `compose.g4.docker.yaml`, `compose.g5.yaml` |

## 21. Tài liệu liên quan

- [Kế hoạch intent/context và fine-tune](08-ke-hoach-intent-context-finetune.md)
- [Protocol model intent/context](09-protocol-model-intent-context.md)
- [Kết quả chọn model intent/context](11-ket-qua-chon-model-intent-context.md)
- [Tích hợp runtime intent/context](12-tich-hop-intent-context-runtime.md)
- [Nâng chất lượng intent/context](13-nang-chat-luong-intent-context.md)
- [TEST kín và feedback](14-test-cuoi-va-feedback.md)
- [Sẵn sàng fine-tune full corpus](15-san-sang-finetune-full-corpus.md)
- [Kết quả fine-tune full corpus](16-ket-qua-finetune-full-corpus.md)
- [So sánh model lightweight](18-ket-qua-so-sanh-lightweight-full-corpus.md)
- [Tích hợp runtime full corpus](19-tich-hop-runtime-full-corpus.md)
- [Xử lý tình huống thực tế](20-xu-ly-tinh-huong-thuc-te-lightweight.md)

## 22. Trạng thái bàn giao

Hệ thống có thể tiếp tục dùng để demo và phát triển nội bộ với dữ liệu đã duyệt. Retrieval,
grounding, citation, feedback và fine-tune pipeline đã có nền kỹ thuật tốt. Điểm nghẽn chính
không còn là “có chạy được hay không”, mà là:

1. context factual và xác nhận claim chưa đủ sâu;
2. intent/context chưa qua holdout độc lập;
3. corpus thiếu một số field;
4. cấu hình ba model chưa đạt định nghĩa lightweight tổng quát.

Mọi báo cáo tiếp theo phải tách rõ bốn khái niệm: **model thuần**, **model + policy**,
**regression đã mở** và **holdout độc lập**. Chỉ holdout mới sau khi candidate được khóa mới
có quyền thay đổi kết luận nghiệm thu.
