# Implementation note — Minh G2 spike

Minh đã đồng ý dùng bản đề xuất bên dưới làm baseline triển khai thử nghiệm trong
cuộc trò chuyện. Chưa ghi nhận review/merge approval của Tú và Hoan.

Code hiện có trong backend/app/rag/. Quyết định cụ thể khi triển khai:

- Persistence dùng bốn bảng rag_* và nullable JSONB messages.grounding/retrieval_filters.
- Chọn corpus active qua RAG_CORPUS_VERSION; không có admin activation endpoint.
- Fixture kỹ thuật có usage=D0_SYSTEM_SMOKE và domain fixture.invalid; validator
  chỉ nhận khi --allow-fixture được bật; runtime cần RAG_ALLOW_FIXTURES=true.
  Đây là ngoại lệ test-only có nhãn rõ, không phải dữ liệu D1 được review thật.
- GoldQuestion thêm optional filters để ghi filter thực sự đưa vào câu hỏi;
  procedure_id của gold không tự trở thành input retrieval (tránh lộ nhãn).
- MessageOutput.grounding nullable trong OpenAPI; runtime bỏ field null khi trả G1
  để giữ JSON shape cũ. GET history và POST pair trả grounding cho G2.
- RAG_CORPUS_UNAVAILABLE trả 503 khi chưa ingest/version sai/fixture bị tắt.
- RetrievalResult.needs_clarification là trạng thái nội bộ, không thêm vào
  EvidenceBundle gửi AI; ambiguity không gọi AI.
- Nguồn không rõ hiệu lực có thể xuất hiện khi không yêu cầu as_of, mang metadata
  UNKNOWN. Nếu có as_of thì cần cả hai đầu khoảng đã xác nhận; không suy diễn null.

Tài liệu gốc đề xuất được giữ bên dưới để review cùng consumer. Những phần viết
"chưa sửa code" mô tả thời điểm đề xuất; không phải trạng thái hiện tại.

---

# Đề xuất contract G2 — chờ xác nhận tại Checkpoint 0

**Trạng thái: DRAFT_FOR_REVIEW, không phải contract đã khóa.**

Bản này được soạn sau khi đọc ZIP `llm-hanh-chinh-cong-main.zip`, chiến lược trong
repo, `docs/contracts-g1.md` v1.2 và tài liệu phân công G2 người dùng gửi riêng.
Chưa sửa code runtime, migration, Web hoặc AI Service. Các field bổ sung dưới đây
là đề xuất để Tú, Minh, Hoan thống nhất; không tự coi là quyết định của cả nhóm.

## 1. Kết quả kiểm tra baseline

- Repo có Web, Backend, AI Service, Compose và G1 CI.
- Tài liệu repo ghi `G1_COMPLETED_ON_MAIN`, tag `g1-v1.0.0`, 58 backend tests trên
  PostgreSQL 16, full-stack/browser smoke tại CI run `34197723998`.
- Đây là thông tin trong repo; lượt kiểm tra này chưa xác minh lại GitHub run/tag.
  ZIP không chứa `.git`, nên không chứng thực được commit/tag bằng Git tại local.
- Đã chạy lại 39 tests trong `tests/test_unit.py` và `tests/test_config.py`: pass,
  bằng Python environment sẵn có. Chưa chạy lại PostgreSQL integration hoặc CI
  toàn hệ thống, không thay thế bằng chứng full regression trên môi trường locked.
- Không thấy contract G2, corpus D1, gold set hoặc code RAG trong ZIP.
- Bản repo tích hợp đã thay các quy ước từ gói backend ban đầu: AI_SERVICE_URL là
  **origin**, timeout là AI_REQUEST_TIMEOUT_SECONDS, CORS là WEB_ORIGIN,
  secure cookie là SESSION_COOKIE_SECURE. Phải kế thừa đúng các tên này.
- AI Service G1 từ chối field dư. Không được tự thêm evidence vào request generate
  G1 rồi cho rằng service của Hoan đã hỗ trợ.

## 2. Quyết định cần khóa

| Chủ đề | Đề xuất | Consumer cần review |
|---|---|---|
| Endpoint grounded | POST /internal/v1/generate-grounded, tách generate G1 | Minh + Hoan |
| Request grounded | evidence_bundle, history, max_output_tokens | Minh + Hoan |
| Public output | Thêm nullable `grounding` vào MessageOutput | Minh + Tú + Hoan |
| Public input | Thêm optional `retrieval_filters`; request G1 vẫn hợp lệ | Minh + Tú |
| Status nguồn | UNKNOWN / CONFIRMED_FROM_SOURCE | Tú + Minh |
| Truy xuất theo thời điểm | Không suy diễn hiệu lực từ retrieved_at/null | Tú + Minh |
| Phiên bản corpus | corpus_version bất biến, chọn rõ bản active | Cả nhóm |
| Provenance nghiệp vụ | Bổ sung field_evidence vào ProcedureRecord | Tú + Minh |
| Domain, thủ tục, jurisdiction demo | Do nhóm/mentor cung cấp, không tự chọn | Tú + mentor |

Tài liệu G2 dùng các chuỗi như `PENDING_OR_APPROVED` và
`UNKNOWN_OR_CONFIRMED_FROM_SOURCE` để minh họa; đề xuất tách thành enum thực tế
như bên dưới. Các quyết định này cần xác nhận trước khi code sâu.

## 3. Tài liệu corpus và ingestion

Giữ cấu trúc đầu vào trong phân công G2:

```text
data/demo_public/
  source_manifest.jsonl
  raw/...
  normalized/procedures.jsonl
  normalized/fragments.jsonl
  gold/questions.jsonl
```

### 3.1. Quy ước chung

- JSONL UTF-8, mỗi dòng là một object; từ chối field dư để phát hiện lệch contract.
- source/procedure/fragment/question ID là string ổn định; request_id là UUID.
- Timestamp retrieved_at có timezone; effective dates và as_of là YYYY-MM-DD.
- Hash là SHA-256 lowercase 64 ký tự. Raw hash tính trên bytes snapshot chính xác.
- Fragment hash tính trên UTF-8 bytes của trường text **nguyên văn**; không trim,
  bỏ dấu hay thay line ending trước khi kiểm hash. Bản chuẩn hóa search tách riêng.
- Cùng ID trong file là lỗi, dù payload giống nhau. Nhập lại cả snapshot giống
  hệt là no-op; cùng version/ID nhưng payload khác là lỗi, không âm thầm overwrite.
- Validate toàn bộ corpus trước khi ghi trong một transaction. Không nhập một
  nửa corpus nếu hash/reference lỗi.
- raw_path tương đối với repo root, bắt buộc nằm trong dataset root đã chọn;
  từ chối path traversal, symlink trỏ ngoài root và URL thay cho local file.
- Corpus version gồm định danh version cùng hash canonical manifests/records và
  raw hashes; giữ phiên bản cũ phục vụ audit, không trộn record của hai corpus.

### 3.2. SourceManifest

Giữ tất cả field ở mục 5.1 tài liệu phân công.

| Field | Kiểu / quy tắc đề xuất |
|---|---|
| source_id, title, parser_version | String không blank |
| source_url | HTTPS URL trong allowlist do nhóm review; không crawler runtime |
| source_domain | Hostname chuẩn hóa, khớp source_url; không khớp bằng substring |
| issuing_authority, jurisdiction, procedure_code | String hoặc null khi chưa rõ |
| retrieved_at | Datetime có timezone |
| effective_from, effective_to | Date hoặc null; from không lớn hơn to |
| status | UNKNOWN hoặc CONFIRMED_FROM_SOURCE |
| content_sha256 | Hash raw snapshot |
| raw_path | Local relative path theo quy tắc trên |
| review_status | PENDING hoặc APPROVED |
| usage | D1_PUBLIC_DEMO |

Validator có thể kiểm tra nguồn PENDING nhưng runtime corpus chỉ nhận nguồn
APPROVED. APPROVED là kết quả review do người chịu trách nhiệm cung cấp; Backend
không tự nâng trạng thái. Schema không chứng minh nguồn đúng pháp lý/không PII.

### 3.3. ProcedureRecord

Giữ các field đã nêu trong tài liệu G2, đặc biệt aliases, source_ids, jurisdiction
và version. Không trộn quốc gia/địa phương vào một procedure record.

Đề xuất bổ sung `field_evidence` để đáp ứng yêu cầu mỗi giá trị nghiệp vụ truy
ngược được nguồn, vì schema mẫu hiện tại chưa có liên kết mức field/value:

```json
{
  "field_evidence": {
    "required_documents": [["frag_demo_documents_001"]],
    "fees": [["frag_demo_fees_001"]]
  }
}
```

Với mỗi array nghiệp vụ, field_evidence có cùng số phần tử; vị trí i chứa danh
sách fragment IDs hỗ trợ giá trị thứ i. Áp dụng applicant_scope,
receiving_authority, submission_methods, required_documents, steps, fees,
processing_time, legal_bases. Danh sách rỗng nghĩa chưa có dữ liệu, không có nghĩa
thủ tục không yêu cầu/không thu phí. Fragment phải thuộc procedure và source_ids.

Procedure code dùng SourceManifest.procedure_code; nếu nhiều source liên quan có
code khác nhau, ingest từ chối bản nhập mơ hồ thay vì chọn tùy ý.

### 3.4. ProcedureFragment

Giữ fragment_id, procedure_id, section_type, text, source_id, ordinal,
content_sha256. Ordinal là integer không âm, thứ tự ổn định trong source/section.
Đề xuất section_type enum: OVERVIEW, APPLICANT_SCOPE, RECEIVING_AUTHORITY,
SUBMISSION_METHODS, REQUIRED_DOCUMENTS, STEPS, FEES, PROCESSING_TIME,
LEGAL_BASES, OTHER. Raw text không bị sửa bởi chuẩn hóa search.

### 3.5. GoldQuestion

Giữ schema mục 5.4 tài liệu G2, status enum ANSWER/NEED_CLARIFICATION/
INSUFFICIENT_DATA, split TRAIN/DEV/TEST. Author và reviewer khác nhau; source và
fragment tham chiếu tồn tại; contains_pii phải false. Đây là khai báo và gate
review, không phải kết luận phát hiện PII tự động hoàn hảo.

Gold nằm trong evaluation input, không nhập vào DB runtime. Fixture giả ở
backend/tests chỉ là test kỹ thuật, không được gắn là nguồn công khai đã review
hoặc kết quả chất lượng thực tế. Không tự tạo gold nghiệp vụ thay Tú.

## 4. Retrieval

Input nội bộ giữ mẫu G2:

```json
{
  "query": "cau hoi demo",
  "top_k": 5,
  "filters": {"procedure_id": null, "jurisdiction": null, "as_of": null}
}
```

- top_k: integer 1–20; default 5. Query không blank, tối đa 10.000 ký tự.
- Chọn một corpus_version active trước retrieval; pin bản đó suốt request.
- Unicode NFC, lowercase, bỏ dấu/đ→d cho search phụ; không sửa raw text.
- Exact code/title/alias trước, tiếp theo BM25 trên fragment. Giữ tie-break ổn
  định bằng fragment_id. Điểm chỉ xếp hạng, không phải xác suất đúng pháp lý.
- Filter áp dụng trước xếp hạng, không fallback sang jurisdiction khác.
- Nếu alias exact khớp nhiều địa phương và chưa đủ filter: hỏi rõ phạm vi,
  không chọn một địa phương tùy ý.
- Nếu as_of có giá trị: chỉ nhận nguồn có khoảng hiệu lực đủ chứng minh bao phủ
  ngày đó. Null không tự mang nghĩa hiệu lực vô hạn. Chưa biết thì loại khỏi
  kết quả theo thời điểm và abstain khi không còn bằng chứng.
- Nếu as_of rỗng: tìm trong snapshot reviewed, trả metadata UNKNOWN nếu chưa rõ
  hiệu lực; không diễn giải snapshot thành khẳng định "hiện hành".
- Mốc no-hit: không có candidate hợp lệ hoặc không có lexical match. Không đặt
  threshold chất lượng tùy ý trước baseline; ngưỡng sẽ điều chỉnh bằng DEV.

### EvidenceBundle

Giữ request_id, query, evidence. Đề xuất thêm corpus_version để tái lập và audit.
Mỗi item giữ fragment_id, source_id, title, url, text, score, metadata. Metadata
bổ sung procedure_id, jurisdiction, source status, effective_from/to, retrieved_at,
procedure version và fragment hash. URL/title/text do Backend lấy từ corpus.

## 5. Internal grounded API — đề xuất mới

Giữ nguyên `/internal/v1/generate` của G1. Endpoint mới do Hoan triển khai:

```text
POST /internal/v1/generate-grounded
```

Request:

```json
{
  "evidence_bundle": {
    "request_id": "00000000-0000-4000-8000-000000000001",
    "corpus_version": "synthetic-fixture-v1",
    "query": "cau hoi gia de test",
    "evidence": []
  },
  "history": [],
  "max_output_tokens": 300
}
```

Ví dụ trên minh họa shape, không phải request có bằng chứng để tạo ANSWER.
Backend không gọi generation khi evidence rỗng. Hoan cũng phải xử lý defensively
nếu nhận evidence rỗng. History chỉ gồm lượt demo được phép, giới hạn 10 messages,
không gửi user_id/session/cookie hoặc lịch sử thật sang provider. History là ngữ
cảnh câu hỏi, không phải nguồn pháp lý. Chưa được duyệt hosted thì dùng mock/template.

Response dùng GroundedAnswer trong tài liệu G2:
request_id, answer, status, cited_fragment_ids, missing_information, provider,
model, usage và latency_ms. Provider/model string không blank; usage không âm;
status chỉ ANSWER/NEED_CLARIFICATION/INSUFFICIENT_DATA. Không nhận URL do AI tạo
làm metadata nguồn. ANSWER cần answer không blank và ít nhất một citation.

Backend kiểm tra:

1. UUID response khớp request hiện tại.
2. cited_fragment_ids duy nhất và là tập con của chính bundle đã gửi.
3. ANSWER có evidence/citation; không được nhận câu trả lời khẳng định khi bundle rỗng.
4. Resolve nguồn từ bundle đã pin; không tra nhầm corpus mới thay giữa request.
5. ID hợp lệ không chứng minh claim được nguồn hỗ trợ; vẫn cần review support trên gold.

Lỗi timeout/network/schema giữ error contract G1. Đề xuất thêm
`502 AI_CITATION_INVALID` cho ID ngoài bundle; user message giữ failed,
không lưu assistant như một answer hợp lệ.

## 6. Public API và persistence

Không đổi endpoint hoặc các field hiện tại. Đề xuất input bổ sung optional:

```json
{
  "client_message_id": "00000000-0000-4000-8000-000000000002",
  "content": "cau hoi demo",
  "retrieval_filters": {"procedure_id": null, "jurisdiction": null, "as_of": null}
}
```

G1 request không có filters vẫn hợp lệ. top_k do Backend config, Web không tự chọn
corpus hay evidence. Ownership luôn dựa session.

Đề xuất MessageOutput thêm `grounding: null | object`:

```json
{
  "grounding": {
    "status": "INSUFFICIENT_DATA",
    "corpus_version": "synthetic-fixture-v1",
    "sources": [],
    "missing_information": []
  }
}
```

ANSWER có sources là các citation đã xác minh: fragment_id, source_id, title,
url và metadata phạm vi/thời điểm. Message cũ hoặc user message có grounding=null.
Message.status vẫn pending/completed/failed; không dùng ANSWER thay cho trạng thái
persistence. POST pair và GET history cùng trả grounding để refresh vẫn thấy nguồn.

No-evidence là kết quả nghiệp vụ hợp lệ: HTTP 200, assistant text giải thích chưa
đủ dữ liệu, grounding.status=INSUFFICIENT_DATA, sources=[]; không gọi AI.
NEED_CLARIFICATION có câu hỏi làm rõ và missing_information, không bịa câu trả lời.

Idempotency dùng content + normalized filters: cùng key nhưng filter đổi là 409.
Cặp thành công trả đúng bản đã lưu dù corpus active đã đổi; retry failed giữ user
message và dùng bundle/request_id mới, lưu provenance lần thành công. Giữ behavior
RETRY_OUT_OF_ORDER và MESSAGE_IN_PROGRESS của G1.

## 7. Database/migration đề xuất

- Không sửa migration G1 đã chạy.
- Migration `0002_g2_rag`: sources, procedures, fragments có key theo corpus version;
  ingestion_runs quản lý corpus hash/version và trạng thái hoàn thành.
- Thêm nullable JSONB metadata cho message (filters/provenance/grounding) hoặc
  bảng message_grounding liên kết 1:1; quyết định vật lý này thuộc Backend và
  không đổi wire contract trên. Ưu tiên ít bảng cho G2.
- Sources/fragment của bản cũ bất biến; message chứa đủ snapshot metadata để
  không mất nguồn khi active corpus đổi. Gold không vào runtime DB.
- Ingest CLI không là public upload endpoint, không fetch raw URL từ mạng.
- G1 mode là mặc định cho regression; chỉ bật RAG bằng config sau migration và
  khi Hoan đã hỗ trợ grounded contract. Không fallback sang AI tự trả lời khi
  RAG mode không tìm thấy corpus/evidence.

## 8. Acceptance và thứ tự triển khai sau khi khóa

1. Schemas + fixture tổng hợp có nhãn test-only, hash/reference validation tests.
2. Migration trên DB trống và upgrade từ G1 có dữ liệu.
3. Ingest cùng snapshot 2 lần, corruption/duplicate/version-conflict rollback.
4. Exact/alias/no-diacritic/BM25; filter jurisdiction/as_of; deterministic ties.
5. No evidence không gọi AI; citation sai request/ID bị chặn.
6. Persist grounding và filters; replay/history/ownership/concurrent retry tests.
7. Chạy toàn bộ G1 regression cùng PostgreSQL 16, giữ existing CI gate.
8. CLI evaluation trên gold do Tú review, ghi corpus version/split, Recall@k,
   MRR, p50/p95, per-query failures. Đo ingest/retrieval/orchestration riêng.
9. Hoan ghép grounded endpoint, Web source rendering, offline template evaluation;
   hosted chỉ khi mentor/công ty duyệt provider và dữ liệu.

Không báo điểm retrieval thật trước khi có corpus/gold review. Không dùng TEST để
tối ưu prompt/retriever. Không thêm embedding/vector DB/model local trong spike.

## 9. Phạm vi cần xác nhận ngay

Để Minh bắt đầu bằng fixture mà không chờ data thật, cần thống nhất các đề xuất
mục 2–6. Tên thủ tục, domain allowlist và provider thực tế vẫn do nhóm/mentor chốt;
fixture không thay thế các phê duyệt đó.

Tài liệu phân công G2 mục 5, 7.2 và Checkpoint 0 yêu cầu khóa schema trước khi code.
Do đó bản này là kết quả chuẩn bị để review, không tự đổi nhãn thành FROZEN hoặc
khẳng định đã có sự đồng ý của Tú/Hoan. Chưa sửa code runtime trong repo được gửi.
