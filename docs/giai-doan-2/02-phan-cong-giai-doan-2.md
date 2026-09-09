# Phân công Giai đoạn 2 – Dataset giả lập, RAG và Grounded AI

> Tài liệu giao việc chính thức cho Tú, Minh và Hoan.
> Cách trình bày: **Tổng → Phân → Hợp**.
> Trước khi dùng AI coding agent, mỗi thành viên phải đưa cho agent đường dẫn file
> này và yêu cầu đọc hết trước khi sửa code.

## Báo cáo cập nhật

| Trường | Nội dung |
|---|---|
| Cập nhật gần nhất | 09/09/2026 |
| Phiên bản | `v1.5` |
| Trạng thái | `G2_COMPLETED_SYNTHETIC_SCOPE` |
| Baseline bắt đầu | `main`, tag `g1-v1.0.0` |
| Thay đổi lần này | Nghiệm thu G2 bằng dataset v1 giả lập: 3 thủ tục/24 fragment/33 câu, full stack và regression pass |
| Dữ liệu được phép | G2 chỉ dùng D0 fixture; D1 công khai và D2 công ty chuyển sang mốc tiếp theo |

---

# PHẦN I – TỔNG: G2 PHẢI TẠO RA ĐIỀU GÌ?

## 1. Mục tiêu duy nhất

G2 phải chứng minh được một lát cắt kỹ thuật nhỏ chạy end-to-end:

```text
Người dùng đặt câu hỏi về thủ tục hư cấu
→ hệ thống tìm đúng đoạn từ fixture đã khóa phiên bản
→ AI chỉ dùng các đoạn đó để diễn giải
→ Backend từ chối citation giả
→ Web trả lời kèm nguồn có thể bấm kiểm tra
→ nhóm đo được lỗi nằm ở data, retrieval hay generation
```

G2 dùng grounded template offline để khóa luồng. Hosted API và model local là
baseline của mốc sau, không phải điều kiện nghiệm thu synthetic scope.

## 2. Phạm vi G2

### 2.1. Bắt buộc làm

- Có **3 thủ tục hư cấu** với tên/cảnh báo không thể nhầm là hướng dẫn thật.
- Lưu snapshot fixture, URL `.invalid`, thời điểm tạo, phạm vi, hash và provenance.
- Chuẩn hóa dữ liệu thành procedure record và fragment có thể truy hồi.
- Tạo **33 câu hỏi giả** cùng expected points, forbidden points và gold source.
- Làm exact/alias search và keyword/BM25 tối giản.
- Trả `EvidenceBundle` có fragment/source ID thật.
- AI Service diễn giải chỉ từ evidence và trả output máy đọc được.
- Backend kiểm tra citation trước khi lưu/trả Web.
- Hiển thị answer cùng nguồn; đo retrieval, citation, answer và latency.

### 2.2. Chưa làm

- Dataset nội bộ công ty `D2_COMPANY_REAL` khi chưa phân loại và phê duyệt.
- Crawl toàn bộ thủ tục hành chính Việt Nam.
- Qwen local, fine-tune, QLoRA hoặc quantization.
- Vector database, embedding, BGE-M3 hoặc reranker ngay từ đầu.
- Case Router, memory dài hạn, Procedure Engine đầy đủ, queue, Socket.IO.
- Tự động kết luận một nguồn còn hiệu lực nếu metadata chính thức không đủ.
- Tuyên bố hệ thống sẵn sàng production hoặc thay thế cán bộ chuyên môn.

## 3. Lát cắt kỹ thuật G2

```text
Tú
Nguồn chính thức
  → raw snapshot + source manifest
  → normalized procedure + fragments
  → gold questions
                    │
                    ▼
Minh
validate/ingest → exact/keyword/BM25 → EvidenceBundle
                    │
                    ▼
Hoan
AI Service → grounded prompt → template D0 / hosted provider được duyệt sau
           → GroundedAnswer + cited_fragment_ids
                    │
                    ▼
Minh + Hoan
Backend kiểm tra cited IDs ⊆ EvidenceBundle
  → lưu message/source metadata → Web hiển thị answer + nguồn
  → evaluation report
```

Nguyên tắc phân ranh:

- Tú quyết định **data nào được đưa vào corpus** sau review nguồn.
- Minh quyết định **evidence nào được retrieval trả về**.
- Hoan quyết định **AI được gọi thế nào và đo thế nào**.
- AI không được tự tìm web hoặc tự tạo URL trong luồng G2.

## 4. Công nghệ đã chốt

Giữ nguyên React + TypeScript, FastAPI, PostgreSQL và Docker Compose của G1.
Retrieval là module trong Core Backend ở G2, chưa tách microservice và chưa thêm
vector database.

Thứ tự retrieval:

```text
1. procedure code/title/alias exact match
2. lọc procedure/jurisdiction/as_of khi có dữ liệu
3. keyword hoặc BM25 trên fragment đã chuẩn hóa
4. top-k evidence
```

Sau baseline, chỉ thêm embedding/reranker nếu error analysis chứng minh bước 1–3
bỏ sót đáng kể.

## 5. Năm contract phải khóa trước khi code

Tên field cuối cùng có thể điều chỉnh ở Checkpoint 0, nhưng không được bỏ metadata
kiểm chứng cốt lõi dưới đây.

### 5.1. `SourceManifest`

```json
{
  "source_id": "src_birth_140183_20260908",
  "source_url": "https://dichvucong.gov.vn/...",
  "source_domain": "dichvucong.gov.vn",
  "title": "Đăng ký khai sinh",
  "issuing_authority": "Cơ quan công bố trên trang nguồn",
  "jurisdiction": "NATIONAL_OR_EXPLICIT_LOCAL_SCOPE",
  "procedure_code": "140183",
  "retrieved_at": "2026-09-08T10:00:00+07:00",
  "effective_from": null,
  "effective_to": null,
  "status": "UNKNOWN_OR_CONFIRMED_FROM_SOURCE",
  "content_sha256": "hex-value",
  "raw_path": "data/demo_public/raw/...",
  "parser_version": "manual-v1",
  "review_status": "PENDING_OR_APPROVED",
  "usage": "D1_PUBLIC_DEMO"
}
```

Không biết giá trị nào thì ghi `null` hoặc `UNKNOWN`; không tự suy đoán ngày hiệu
lực, cơ quan, địa phương hay phạm vi áp dụng.

### 5.2. `ProcedureRecord`

```json
{
  "procedure_id": "birth_registration_demo",
  "title": "Đăng ký khai sinh",
  "aliases": ["làm giấy khai sinh", "khai sinh cho con"],
  "jurisdiction": "...",
  "applicant_scope": ["..."],
  "receiving_authority": ["..."],
  "submission_methods": ["..."],
  "required_documents": ["..."],
  "steps": ["..."],
  "fees": ["..."],
  "processing_time": ["..."],
  "legal_bases": ["..."],
  "source_ids": ["src_birth_140183_20260908"],
  "version": "2026-09-08"
}
```

Mỗi giá trị nghiệp vụ phải truy ngược được tới fragment/source. Không gộp quy
định quốc gia và biến thể địa phương vào một record mơ hồ.

### 5.3. `ProcedureFragment`

```json
{
  "fragment_id": "frag_birth_documents_001",
  "procedure_id": "birth_registration_demo",
  "section_type": "REQUIRED_DOCUMENTS",
  "text": "Nội dung đúng theo snapshot đã review...",
  "source_id": "src_birth_140183_20260908",
  "ordinal": 1,
  "content_sha256": "hex-value"
}
```

Fragment phải đủ ngữ cảnh để hiểu, nhưng không gom nguyên trang thành một đoạn.

### 5.4. `GoldQuestion`

```json
{
  "question_id": "q_birth_001",
  "question": "Tôi đã có CCCD, đăng ký khai sinh cho con còn cần gì?",
  "procedure_id": "birth_registration_demo",
  "facts": {"documents_owned": ["CCCD"]},
  "expected_status": "ANSWER",
  "expected_points": ["Nêu đúng giấy tờ còn cần theo source"],
  "forbidden_points": ["Không tự thêm giấy tờ không có căn cứ"],
  "gold_source_ids": ["src_birth_140183_20260908"],
  "gold_fragment_ids": ["frag_birth_documents_001"],
  "contains_pii": false,
  "split": "DEV",
  "author": "tu",
  "reviewer": "minh_or_hoan"
}
```

Gold không phải là một đoạn văn do LLM viết rồi coi là chân lý. Gold ưu tiên
expected facts/points, forbidden claims và evidence IDs để review được.

### 5.5. `EvidenceBundle` và `GroundedAnswer`

Minh giữ **Canonical EvidenceBundle** trong Backend với URL, retrieval score và
metadata phục vụ audit/UI. Trước khi gọi AI Service, Backend project nó thành
**GroundingContext** tối thiểu: query, bundle/corpus ID, fragment/source/procedure
ID, section, text và metadata phạm vi/hiệu lực cần thiết. Không gửi URL, score,
cookie, user ID hay history dài cho provider.

AI trả `answer`, `status`, `cited_fragment_ids`, `missing_information`; AI Service
gắn request/bundle/corpus/prompt/provider/model/usage/latency. Backend xác nhận ID
và hydrate URL từ bundle gốc. Contract máy đọc được đầy đủ nằm tại
[Grounded API Contract G2](../contracts-g2.md).

---

# PHẦN II – PHÂN: GIAO VIỆC CHI TIẾT

## 6. Tú – Data & Gold Set Owner

### 6.1. Mục tiêu của Tú

Biến một số trang công khai chính thức thành corpus nhỏ có nguồn gốc rõ ràng,
version được, không chứa PII và đủ sạch để Minh ingest, Hoan đánh giá.

Đây không phải nhiệm vụ “cào càng nhiều càng tốt”. Thành công của Tú được đo bằng
khả năng kiểm chứng và độ đúng của data, không phải số trang tải về.

### 6.2. Thứ tự ưu tiên nguồn

**Cấp 1 – nguồn thủ tục trực tiếp:**

- Cổng Dịch vụ công Quốc gia/Cơ sở dữ liệu quốc gia về thủ tục hành chính;
- trang công bố thủ tục của bộ, cơ quan hoặc địa phương có thẩm quyền.

**Cấp 2 – căn cứ pháp lý hỗ trợ:**

- `https://vbpl.vn/` – Cơ sở dữ liệu quốc gia về văn bản pháp luật;
- `https://vanban.chinhphu.vn/` – hệ thống văn bản Chính phủ;
- cổng văn bản chính thức của cơ quan ban hành nếu hai nguồn trên chưa đủ.

**Không dùng làm gold source:** blog, diễn đàn, mạng xã hội, bài SEO của công ty
luật, bài báo, câu trả lời từ chatbot hoặc snippet của công cụ tìm kiếm. Chúng chỉ
có thể gợi ý từ khóa để quay lại tìm nguồn chính thức.

### 6.3. Quy trình chọn 2–3 thủ tục

1. Lập bảng ứng viên, chưa crawl diện rộng.
2. Với mỗi ứng viên, ghi URL thủ tục, cơ quan, phạm vi, ngày truy cập và căn cứ.
3. Kiểm tra trang có đủ tối thiểu: đối tượng, hồ sơ, cách thực hiện, cơ quan, thời
   hạn/lệ phí nếu thủ tục có quy định.
4. Đánh dấu thông tin quốc gia và địa phương riêng biệt.
5. Trình cả nhóm và mentor chốt 2–3 thủ tục.
6. Spike trước bằng một thủ tục và khoảng 10 câu hỏi.
7. Chỉ mở rộng sau khi spike đã đi được tới answer kèm nguồn trên Web.

Các tên như đăng ký khai sinh, khai tử, cấp/cấp đổi thẻ căn cước chỉ là ứng viên;
không mặc định chốt nếu source hiện hành không đủ rõ hoặc mentor chọn phạm vi khác.

### 6.4. Quy tắc thu thập/crawl bắt buộc

- Chỉ crawl domain và URL pattern trong allowlist đã review.
- Kiểm tra điều khoản sử dụng, `robots.txt` và khả năng khai thác trước khi chạy.
- Dùng rate limit thấp, timeout, retry có backoff, cache và resume; không tạo tải
  lớn lên hệ thống nhà nước.
- Không vượt CAPTCHA, đăng nhập, anti-bot, paywall hoặc cơ chế hạn chế truy cập.
- Nếu trang chặn tự động, tải/xuất thủ công từ giao diện chính thức và ghi
  `parser_version=manual-v1`; không tìm cách lách chặn.
- Lưu bản gốc HTML/PDF trước khi parse; raw snapshot là bất biến, không overwrite.
- Tính SHA-256 cho từng snapshot và ghi `retrieved_at` có timezone.
- Nếu PDF là ảnh scan, OCR chỉ tạo derivative; vẫn giữ PDF gốc và ghi tool/version.
- Không crawl biểu mẫu đã điền hoặc dữ liệu hồ sơ công dân.
- Không đưa cookie, token, API key, số CCCD, số điện thoại, địa chỉ cá nhân vào repo.
- Mỗi thất bại phải được ghi URL, status/error và thời điểm; không im lặng bỏ qua.

Việc nội dung được truy cập công khai không tự động có nghĩa là được phép crawl
không giới hạn. Nếu điều khoản/robots không rõ, hỏi mentor hoặc chuyển sang tải
thủ công cho bộ demo nhỏ.

### 6.5. Chuẩn hóa dữ liệu

Với mỗi thủ tục:

1. giữ raw snapshot;
2. tạo source manifest;
3. trích các section nghiệp vụ thành `ProcedureRecord`;
4. chia thành fragment theo section;
5. liên kết mọi fragment với source ID;
6. review thủ công với trang gốc;
7. chỉ chuyển `review_status=APPROVED` khi người thứ hai kiểm tra.

Không được:

- tự điền trường còn thiếu bằng kiến thức của LLM;
- trộn hai phiên bản văn bản hoặc hai địa phương mà không ghi rõ;
- bỏ thông tin “không áp dụng”, ngoại lệ hoặc điều kiện đi kèm;
- sửa câu chữ làm thay đổi nghĩa thủ tục;
- coi `retrieved_at` là `effective_from`.

### 6.6. Tạo bộ câu hỏi đánh giá

Tổng ban đầu: **30–50 câu** cho 2–3 thủ tục; spike: khoảng **10 câu** cho một thủ
tục. Phân bố phải có nhiều loại lỗi, không chỉ câu hỏi dễ:

| Nhóm câu hỏi | Mục tiêu |
|---|---|
| Direct fact | Hỏi giấy tờ, nơi nộp, thời hạn, lệ phí có nêu trong source |
| Paraphrase | Cùng ý nhưng dùng từ đời thường, không dấu hoặc có lỗi gõ nhẹ |
| Có dữ kiện cá nhân giả | Ví dụ đã có một giấy tờ; hỏi còn thiếu gì |
| Thiếu dữ kiện | Đáp án đúng là hỏi lại hoặc nêu giới hạn |
| Ngoài corpus | Hệ thống phải `INSUFFICIENT_DATA`, không bịa |
| Bẫy sai | Câu hỏi chứa giả định trái nguồn để kiểm tra AI có hùa theo không |
| Phạm vi/thời điểm | Kiểm tra hệ thống có tôn trọng jurisdiction/version không |
| Nhiều lượt tối thiểu | Lượt sau dùng một phần lịch sử G1 nhưng vẫn chỉ hỏi một thủ tục |

Quy tắc gold:

- mọi expected point phải có `gold_fragment_ids` hỗ trợ;
- ghi cả `forbidden_points` cho sai lầm nguy hiểm;
- tên/ngày/địa chỉ trong tình huống phải hoàn toàn giả và không nhận diện cá nhân;
- AI được dùng để đề xuất biến thể câu hỏi nhưng Tú phải tự đối chiếu source;
- không cho AI tự sinh đáp án rồi tự duyệt;
- chia `TRAIN/DEV/TEST` trước khi chỉnh prompt; tập TEST không dùng để tối ưu prompt;
- Tú là author chính; Minh hoặc Hoan phải là reviewer.

### 6.7. Deliverable của Tú

```text
data/demo_public/
├── README.md
├── source_manifest.jsonl
├── raw/
│   └── <procedure>/<retrieved-date>/...
├── normalized/
│   ├── procedures.jsonl
│   └── fragments.jsonl
├── gold/
│   └── questions.jsonl
└── reports/
    └── data-quality.md

tools/data/
├── crawl_or_download...
├── normalize...
└── validate_dataset...
```

Tên script/ngôn ngữ có thể thay đổi sau Checkpoint 0; contract và kết quả kiểm
tra không được thay đổi tùy ý.

### 6.8. Test Tú phải chứng minh

- Mọi `source_id`, `procedure_id`, `fragment_id`, `question_id` là duy nhất.
- Domain nằm trong allowlist và URL dùng HTTPS nếu nguồn hỗ trợ.
- File raw tồn tại và hash khớp manifest.
- Mọi fragment trỏ tới source và procedure tồn tại.
- Mọi gold source/fragment tồn tại trong corpus.
- Mọi câu hỏi có `contains_pii=false`, author, reviewer và split.
- Không có trường bắt buộc bị LLM bịa; trường chưa rõ là `null/UNKNOWN`.
- Chạy validator hai lần cho cùng snapshot cho kết quả ổn định.

### 6.9. Definition of Done của Tú

- Một-procedure spike được hai thành viên còn lại review và ingest thành công.
- Bộ 2–3 thủ tục có raw snapshot, manifest, normalized data và quality report.
- Có 30–50 gold questions được review chéo.
- Không PII, không nguồn không chính thức, không vượt giới hạn truy cập.
- Minh có thể ingest chỉ bằng README/command, không cần hỏi Tú cách sửa file tay.

### 6.10. Context giao nguyên khối cho AI agent của Tú

```text
Bạn đang hỗ trợ Tú, Data & Gold Set Owner của Giai đoạn 2 trong dự án trợ lý
hành chính công. Trước khi làm, hãy đọc hết:
- docs/00-chien-luoc-trien-khai-tu-nho-den-lon.md
- docs/giai-doan-2/02-phan-cong-giai-doan-2.md

Mục tiêu đầu tiên chỉ là spike MỘT thủ tục công khai chính thức và khoảng 10 câu
hỏi đánh giá; không crawl toàn Việt Nam. Nguồn ưu tiên là Cổng Dịch vụ công/CSDL
thủ tục hành chính chính thức; vbpl.vn và vanban.chinhphu.vn dùng làm căn cứ pháp
lý hỗ trợ. Không dùng blog, báo, công ty luật, search snippet hoặc output LLM làm
gold source.

Trước khi crawl, lập allowlist và kiểm tra terms/robots. Crawler phải rate-limit,
timeout, retry/backoff, cache/resume, lưu raw snapshot bất biến, SHA-256,
retrieved_at và log lỗi. Không vượt CAPTCHA, đăng nhập hoặc anti-bot; nếu bị chặn,
dừng và đề xuất tải thủ công. Không thu thập PII hay dữ liệu công ty.

Chuẩn hóa theo SourceManifest, ProcedureRecord và ProcedureFragment đã chốt.
Không biết thì ghi null/UNKNOWN, không được suy diễn. Mọi field nghiệp vụ phải
truy ngược tới fragment/source. Câu hỏi có expected_points, forbidden_points,
gold_source_ids, gold_fragment_ids, split và contains_pii=false. Bạn có thể đề
xuất câu hỏi nhưng Tú phải review thủ công; không tự sinh gold answer rồi tự duyệt.

Chỉ sửa data/demo_public/**, tools/data/** và tài liệu data G2 trừ khi Tú yêu cầu
khác. Trước khi kết thúc, chạy validator và báo: URL đã dùng, điều khoản/robots đã
kiểm tra, file/hash, số record, số lỗi, test, assumption và blocker.
```

## 7. Minh – Retrieval/RAG Backend Owner

### 7.1. Mục tiêu của Minh

Biến corpus đã được Tú duyệt thành EvidenceBundle nhỏ, đúng nguồn và có thể đo;
nối retrieval vào luồng POST message hiện có mà không phá auth, history,
idempotency và error handling của G1.

### 7.2. Phạm vi công việc

1. Khóa schema với Tú và Hoan; chuẩn bị fixture giả đúng schema để làm song song.
2. Viết validation/ingestion idempotent cho manifest, procedures và fragments.
3. Thêm migration/table tối thiểu cho sources, procedures, fragments và ingestion
   runs nếu cần; không đưa gold test vào DB runtime production.
4. Exact lookup theo procedure code/title/alias.
5. Keyword hoặc BM25 đơn giản trên fragment; chuẩn hóa Unicode, viết hoa/thường
   và có phương án xử lý câu không dấu nhưng không làm mất raw text.
6. Hỗ trợ filter tối thiểu: `procedure_id`, `jurisdiction`, `as_of` khi metadata có.
7. Trả top-k EvidenceBundle đúng contract.
8. Nối retrieval trước AI Service trong POST message.
9. Khi không có evidence đủ điều kiện, trả trạng thái thiếu dữ liệu, không để model
   trả lời bằng kiến thức riêng.
10. Sau AI response, kiểm tra `cited_fragment_ids` là tập con của evidence đúng
    request; loại/từ chối response có citation giả.
11. Mở rộng response public theo hướng backward-compatible để Web có answer và
    source metadata; phối hợp Hoan cập nhật contract.

### 7.3. Không thuộc nhiệm vụ G2 của Minh

- Tự crawl hoặc tự sửa nội dung nguồn để retrieval “đẹp” hơn.
- Tự tạo expected answer/gold source thay Tú.
- Tách RAG thành microservice riêng.
- Thêm Qdrant, Elasticsearch, graph database hoặc reranker khi chưa có số liệu.
- Tự động đánh giá tính pháp lý/hiệu lực bằng suy luận của LLM.

### 7.4. Retrieval contract tối thiểu

Input nội bộ:

```json
{
  "query": "Tôi cần làm giấy khai sinh",
  "top_k": 5,
  "filters": {
    "procedure_id": null,
    "jurisdiction": null,
    "as_of": "2026-09-08"
  }
}
```

Output là EvidenceBundle ở mục 5.5. `score` chỉ dùng để xếp hạng trong cùng một
retriever; không trình bày nó như xác suất đúng pháp lý.

### 7.5. Deliverable của Minh

- G2 data schema/migration và ingest command có README.
- Validator phía Backend từ chối broken references/duplicate IDs.
- Retrieval module exact + keyword/BM25 và unit tests.
- Integration vào luồng message với no-evidence behavior.
- Citation ID allowlist validator.
- Báo cáo retrieval trên gold set: Recall@k, MRR hoặc metric tương đương, query
  latency p50/p95 và danh sách lỗi.

### 7.6. Test Minh phải chứng minh

- Ingest một snapshot hai lần không nhân đôi dữ liệu.
- Snapshot có broken reference/hash/schema bị từ chối rõ ràng.
- Exact alias tìm đúng procedure.
- Gold fragment xuất hiện trong top-k ở các câu spike đã định nghĩa.
- Filter không làm lẫn địa phương/phiên bản.
- Không có hit thì không gọi generation như thể đã có căn cứ.
- AI trả một fragment ID ngoài evidence thì Backend chặn.
- Auth, user isolation, message persistence và idempotency G1 vẫn pass.
- Có latency riêng cho ingest/retrieval/orchestration, không trộn thành một số mơ hồ.

### 7.7. Definition of Done của Minh

- Tú có thể đưa dataset đã validate vào bằng một command được tài liệu hóa.
- Cùng query và corpus version cho kết quả ổn định.
- EvidenceBundle luôn trỏ tới source/fragment tồn tại.
- Retrieval report chỉ rõ từng câu fail; không chỉ đưa điểm trung bình.
- Toàn bộ Backend/G1 regression tests pass.

### 7.8. Context giao nguyên khối cho AI coding agent của Minh

```text
Bạn đang hỗ trợ Minh, Retrieval/RAG Backend Owner của Giai đoạn 2. Trước khi sửa,
đọc hết docs/00-chien-luoc-trien-khai-tu-nho-den-lon.md,
docs/giai-doan-2/02-phan-cong-giai-doan-2.md, docs/contracts-g1.md và code Backend.

G2 chỉ có 2–3 thủ tục, nên retrieval nằm trong Core Backend. Hãy làm fixture đúng
contract để phát triển song song; không chờ crawler hoàn tất. Pipeline tối thiểu:
validate/ingest idempotent → exact code/title/alias → keyword hoặc BM25 fragment
→ top-k EvidenceBundle → gọi AI Service → kiểm tra cited_fragment_ids là tập con
của evidence. Không evidence thì trả INSUFFICIENT_DATA, không để model trả lời từ
kiến thức riêng.

Không tự sửa data nghiệp vụ, không dùng blog làm nguồn, không thêm vector DB,
embedding, BGE-M3, reranker, Case, queue hay microservice mới. Giữ nguyên auth,
ownership, history, idempotency và error contract G1. Mọi migration phải chạy được
từ DB sạch và upgrade từ G1.

Chỉ sửa backend/**, migration/test liên quan và tài liệu RAG G2 trừ khi Minh yêu
cầu khác. Trước khi kết thúc, chạy migration, unit/integration/regression tests;
báo diff, command, Recall@k/MRR, latency, query fail, assumption và blocker.
```

## 8. Hoan – AI Service, Evaluation & Integration Owner

### 8.1. Mục tiêu của Hoan

Bổ sung grounded API v2 song song với Mock API v1, xây evaluation offline bằng
template D0. Output phải bám evidence, đo được và không làm hỏng G1. Hosted/local
provider được giữ sau cùng interface nhưng chuyển sang mốc sau G2.

### 8.2. Phạm vi công việc

1. Chốt G2 contract với Tú/Minh và giữ version thay đổi.
2. Tạo fixture EvidenceBundle để làm AI Service/evaluation ngay sau Checkpoint 0.
3. Giữ provider interface độc lập; không để chi tiết runtime rò sang Backend.
4. G2 không cần API key và không thực hiện external call.
5. Prompt bắt buộc: chỉ trả lời từ evidence, không tự tạo nguồn, nếu thiếu thì
   `NEED_CLARIFICATION` hoặc `INSUFFICIENT_DATA`.
6. Parse/validate GroundedAnswer; output sai schema phải fail có kiểm soát.
7. Cấu hình timeout và ánh xạ lỗi provider có kiểm soát.
8. Viết evaluation harness chạy gold fixture cho template baseline.
9. Ghi provider/model/version, latency, token usage, error rate và request ID.
10. Phối hợp Minh nối EvidenceBundle; phối hợp phần Web chỉ ở mức hiển thị nguồn
    tối thiểu, không redesign UI.
11. Cập nhật Compose, `.env.example`, runbook và CI; toàn bộ G2 chạy offline.

### 8.3. Điều kiện dùng hosted API ở mốc sau

- Chỉ gửi câu hỏi và evidence thuộc phân loại được công ty cho phép.
- Không gửi dataset công ty, PII, cookie, history thật hoặc raw corpus đầy đủ.
- Công ty/mentor phải xác nhận provider được dùng và loại dữ liệu được phép gửi.
- Nếu chưa được duyệt hoặc hết quota, hệ thống vẫn chạy bằng MockProvider/template.
- Ghi rõ hosted baseline không phải model lightweight cuối cùng.

### 8.4. Evaluation tối thiểu

Đo tách tầng:

| Tầng | Metric/bằng chứng |
|---|---|
| Data | schema/reference/hash/PII validation |
| Retrieval | Recall@k, MRR, query fail và latency |
| Citation | ID validity phải 100%; manual support review trên gold |
| Answer | expected-point coverage, forbidden-claim rate, abstention behavior |
| Runtime | p50/p95 latency, tokens/request, timeout, 429/5xx |
| Regression | G1 auth/history/isolation/idempotency và full-stack smoke |

Không dùng cùng tập TEST để chỉnh prompt rồi báo điểm. Khi thêm hosted/local model
ở mốc sau, các model phải chạy trên cùng corpus version, split và retrieval output.

### 8.5. Deliverable của Hoan

- Provider boundary và template D0 an toàn.
- Grounded prompt/output parser cùng tests.
- Evaluation CLI/report có per-question result, không chỉ điểm trung bình.
- Báo cáo template baseline và format sẵn cho candidate sau.
- Compose/runbook/CI và smoke end-to-end answer + sources.
- Bảng bottleneck: data, retrieval, generation hay provider/runtime.

### 8.6. Test Hoan phải chứng minh

- Mock/template cùng tuân thủ interface nội bộ.
- Evidence rỗng không tạo câu trả lời khẳng định.
- Prompt injection nằm trong question/evidence không được biến thành instruction.
- Output malformed/timeout/provider failure được xử lý dự đoán được.
- Citation ngoài allowlist evidence bị phát hiện trước khi công bố.
- Secret không xuất hiện trong source, log hoặc evaluation artifact.
- Evaluation có thể chạy offline bằng mock/template trong CI.
- Full Compose smoke giữ history và hiển thị source sau refresh.

### 8.7. Definition of Done của Hoan

- Một lệnh hoặc runbook chạy được evaluation có tái lập.
- Có báo cáo so sánh và lỗi theo từng question ID.
- Toàn bộ G2 chạy offline, không cần key hoặc dịch vụ bên thứ ba.
- G1 CI/regression và G2 smoke đều xanh.
- Nhóm có bằng chứng để quyết định bước tiếp theo, không chọn model theo cảm giác.

### 8.8. Context giao nguyên khối cho AI coding agent của Hoan

```text
Bạn đang hỗ trợ Hoan, AI Service, Evaluation & Integration Owner của Giai đoạn 2.
Trước khi sửa, đọc hết docs/00-chien-luoc-trien-khai-tu-nho-den-lon.md,
docs/giai-doan-2/02-phan-cong-giai-doan-2.md, docs/contracts-g1.md, AI Service,
Backend client, Compose và CI hiện có.

G2 dùng provider boundary hiện có với template D0 hoàn toàn offline. Không gửi
PII, dataset công ty, raw corpus hoặc secret vào prompt/log/repo. Provider
SDK/schema không được rò sang Backend. Grounded prompt
chỉ cho phép dùng EvidenceBundle; output gồm answer, status, cited_fragment_ids và
missing_information. Evidence rỗng hoặc thiếu căn cứ phải abstain. Output sai
schema phải fail có kiểm soát.

Viết evaluation harness chạy template trên corpus/gold split D0. Đo
retrieval, citation validity/support, expected points, forbidden claims,
abstention, p50/p95 latency, token usage và lỗi theo từng question. CI dùng mock;
không có live API trong G2. Không làm Qwen local, fine-tune, quantization, Case,
queue, vector DB hay redesign Web trong G2.

Chỉ sửa ai-service/**, evaluation/**, Compose/CI/runbook và phần integration được
Hoan sở hữu. Trước khi kết thúc, chạy tests/smoke/eval; báo file, command, result,
chi phí/quota quan sát được, assumption, risk và blocker.
```

---

# PHẦN III – HỢP: LÀM SONG SONG VÀ GHÉP NHÓM

## 9. Task board chính thức

| ID | Owner | Task | Phụ thuộc | Output kiểm tra được |
|---|---|---|---|---|
| G2-00 | Cả nhóm | Chốt 3 thủ tục hư cấu, allowlist và năm schema | Không | Biên bản/contract được cả ba xác nhận |
| G2-D01 | Tú | Source register và one-procedure snapshot | G2-00 | Raw + manifest + hash |
| G2-D02 | Tú | Normalize procedure/fragments | G2-D01 | Validator pass |
| G2-D03 | Tú | Khoảng 10 câu hỏi spike | G2-D02 | Gold được review chéo |
| G2-R01 | Minh | Migration + ingest từ fixture | G2-00 | Ingest idempotent pass |
| G2-R02 | Minh | Exact + keyword/BM25 retrieval | G2-R01 | EvidenceBundle + tests |
| G2-A01 | Hoan | Grounded contract/prompt bằng fixture | G2-00 | Schema tests pass |
| G2-A02 | Hoan | Evaluation harness offline | G2-A01 | Report trên fixture |
| G2-I01 | Cả nhóm | Ghép one-procedure end-to-end | D03/R02/A02 | Web answer + source |
| G2-D04 | Tú | Mở rộng 3 thủ tục, 33 câu | G2-I01 | Dataset/gold v1 validated |
| G2-R03 | Minh | Retrieval report và sửa lỗi đo được | G2-D04 | Per-query report |
| G2-A03 | Hoan | Hosted baseline | G2-I01 | Chuyển sang mốc sau G2 |
| G2-I02 | Hoan chủ trì | Full G2 integration/CI/demo | D04/R03 | Gate G2 evidence |

Tiến độ tại 09/09/2026:

- `G2-D01/D02/D03/D04`: **DONE_D0** – 3 nguồn, 3 thủ tục, 24 fragment và 33
  câu DEV/TEST; hash/schema/provenance/publish gate đều pass.
- `G2-R01/R02`: **IMPLEMENTED_AND_TESTED_D0** – ingest idempotent, retrieval,
  ambiguity guard và EvidenceBundle đã chạy trong Core Backend.
- `G2-A01/A02`: **IMPLEMENTED_AND_TESTED_D0** – route/schema/prompt v2, template
  D0, evaluation 8 case và strict safety pass.
- `G2-I01`: **D0_TECHNICAL_PASS** – Docker Compose, API smoke, Web source rendering
  và Chromium reload-history E2E pass bằng fixture giả.
- `G2-R03`: **DONE_D0** – DEV 23/23 và TEST 10/10; Recall@5 = 1.0, không câu fail.
- `G2-A03`: **MOVED_TO_NEXT_MILESTONE** – không dùng key/provider thật trước khi
  công ty duyệt provider và loại dữ liệu.
- `G2-I02`: **DONE_SYNTHETIC_SCOPE** – full stack, smoke, citation, persistence,
  G1 regression và Chromium G2 E2E pass. Xem `NGHIEM-THU-G2.md`.

## 10. Cách làm song song, không ai phải chờ

Ba nhánh đã được ghép và nghiệm thu. Việc song song tiếp theo là:

```text
Tú:   kiểm kê cấu trúc/quyền dùng dataset công ty, không commit dữ liệu nội bộ
Minh: thiết kế import adapter và chạy retrieval trên sample đã được duyệt
Hoan: giữ G2 regression xanh, chuẩn bị hosted/local adapter theo chính sách
```

Không ép `publish` pass bằng cách tự điền dữ kiện nguồn không có hoặc tự duyệt
gold. Không để hosted key trở thành điều kiện duy trì D0.

## 11. Checkpoint

### Checkpoint 0 – Scope/contract lock

- Mentor xác nhận phạm vi thủ tục và D1.
- Cả nhóm xác nhận schema, path, branch và reviewer.
- Chưa code sâu nếu field bắt buộc còn mâu thuẫn.

### Checkpoint 1 – One-procedure spike

- Tú: một snapshot reviewed + normalized fragments + khoảng 10 câu.
- Minh: ingest + retrieval top-k.
- Hoan: grounded output + offline evaluation.
- Demo được answer/source hoặc abstain đúng.

Luồng D0 đã chạy end-to-end. Chỉ mở rộng corpus D1 sau khi spike nguồn thật qua
review chéo; không coi D0 là phê duyệt dữ liệu nghiệp vụ.

### Checkpoint 2 – Dataset/gold v1 – DONE

- 2–3 thủ tục, 30–50 câu và review chéo.
- Frozen corpus version và TEST split.
- Data quality gate pass.

### Checkpoint 3 – Baseline và error analysis – DONE TRÊN D0

- Chạy retrieval + template trên cùng test setup; hosted chuyển sang mốc sau.
- Liệt kê từng lỗi và chủ sở hữu sửa.
- Cùng mentor chốt ngưỡng phần trăm sau baseline, không chọn số đẹp trước.

### Checkpoint 4 – Nghiệm thu G2 – DONE

- Full stack chạy qua Docker Compose.
- Trả nguồn đúng hoặc thiếu dữ liệu; không citation giả.
- G1 regression xanh.
- Có báo cáo retrieval/latency kỹ thuật và quyết định đầu vào G3.

## 12. Branch và ownership file đề xuất

Tạo branch sau khi commit kế hoạch/contract G2 làm baseline chung:

| Người | Branch | Phạm vi chính |
|---|---|---|
| Tú | `data/frontend-tu` (đã nhập) | `data/demo_public/**`, `tools/data/**`, docs data |
| Minh | `Minh-RAG_test` (đã nhập) | `backend/**`, migration và docs retrieval |
| Hoan | `g2/ai-eval-hoan` | `ai-service/**`, `evaluation/**`, Compose/CI |
| Tích hợp | `g2/integration` | Đang chứa checkpoint D0 đã kiểm thử |

Contract G2 là file chung. Người muốn đổi schema phải nêu migration/consumer bị
ảnh hưởng và được hai người còn lại đồng ý trước khi merge.

## 13. Review chéo

| Nội dung | Author chính | Reviewer bắt buộc |
|---|---|---|
| Nguồn/normalized data | Tú | Minh |
| Gold expected/forbidden/source | Tú | Hoan; Minh kiểm tra retrieval IDs |
| Ingestion/retrieval | Minh | Tú kiểm tra nghĩa data; Hoan kiểm tra contract |
| Prompt/output/provider | Hoan | Minh kiểm tra evidence contract |
| Evaluation report | Hoan | Tú kiểm tra gold; Minh kiểm tra retrieval metric |
| G2 integration | Hoan chủ trì | Tú + Minh chạy lại |

## 14. Gate G2

Các điều kiện không thương lượng:

- Source/reference/schema/hash validation pass.
- Không PII và không dữ liệu công ty trong fixture/hosted request.
- Mọi citation ID trong answer thuộc evidence của đúng request: **100%**.
- Test split không bị dùng để chỉnh prompt.
- Không evidence thì không trả câu khẳng định như có căn cứ.
- G1 auth/history/isolation/idempotency regression pass.
- Có raw result theo từng câu, không chỉ báo một điểm trung bình.

Kết quả D0: Recall@5 = 1.0 trên DEV/TEST, citation binding 100% trong smoke/E2E
và không có câu retrieval fail. Các số này chỉ là gate kỹ thuật; ngưỡng nghiệp vụ
sẽ được chốt lại trên dữ liệu thật cùng người duyệt chuyên môn.

## 15. Câu hỏi phải xác nhận với mentor trước Checkpoint 0

1. Hai hoặc ba thủ tục cụ thể nào thuộc phạm vi demo?
2. Phạm vi quốc gia hay một địa phương cụ thể?
3. Có cho phép tải/crawl snapshot công khai; có quy định pháp chế/nội bộ riêng?
4. Provider hosted nào được phép và chỉ D1 có được gửi ra ngoài không?
5. Ai là người nghiệp vụ duyệt normalized data/gold cuối cùng?
6. Mức demo mong muốn: nội bộ, khách hàng thử nghiệm hay công khai?
7. Sau baseline, tiêu chí ưu tiên là độ đúng, latency, chi phí hay khả năng offline?

## 16. Kết luận phân công

```text
Tú   chịu trách nhiệm: nguồn có đáng tin và gold có kiểm chứng không?
Minh chịu trách nhiệm: hệ thống có tìm đúng evidence và chặn source giả không?
Hoan chịu trách nhiệm: AI có bám evidence, đo được và ghép toàn hệ thống không?
```

Nếu ba phần này cùng đạt, G2 thành công và nhóm mới có dữ liệu thực nghiệm để quyết
định G3 dùng model local nào. Nếu chưa đạt, chưa fine-tune Qwen và chưa thêm kiến
trúc phức tạp để che lấp lỗi nền tảng.
