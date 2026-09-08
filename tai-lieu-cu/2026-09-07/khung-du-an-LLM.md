# Khung dự án Trợ lý hành chính công – Luật Đúng Lúc

> Tài liệu định hướng chung cho nhóm ba thành viên; LLM là một thành phần của toàn hệ thống.  
> Trạng thái: chốt tạm thời tại tháng 09/2026; sẽ hiệu chỉnh sau khi nhận và kiểm toán dữ liệu công ty.  
> Cách trình bày: **Tổng – Phân – Hợp**.

---

# PHẦN I – TỔNG: TOÀN CẢNH DỰ ÁN

## 1. Bài toán

Xây dựng một trợ lý hành chính công sử dụng LLM lightweight, có khả năng tiếp nhận thắc mắc của người dân, xác định đúng thủ tục, hướng dẫn hồ sơ–điều kiện–các bước–nơi nộp và trả lời gần thời gian thực dựa trên nguồn chính thức.

Theo định hướng cập nhật ngày 07/09/2026, **hành chính công là phạm vi sản phẩm chính**, không phải bước thử trước khi mở rộng thành chatbot pháp luật tổng quát. Sản phẩm không chỉ gồm model mà còn có định danh đa người dùng, lịch sử dài hạn theo từng hồ sơ thủ tục, backend API, queue, Socket.IO, RAG upload, Docker và web demo.

Sản phẩm không được định nghĩa là “chatbot đã ghi nhớ toàn bộ luật”. Sản phẩm được định nghĩa là:

> **Hệ thống trợ lý hành chính công có căn cứ, sử dụng generator 1.7B–4B để hiểu và diễn giải; thông tin thủ tục nằm trong Procedure Store/RAG có phiên bản; mọi hướng dẫn về giấy tờ, điều kiện, cơ quan, phí và thời hạn phải qua kiểm chứng.**
(Nghĩa là ko phải tạo ra chatbot học vẹt rồi trả lời mà phải biết suy nghĩ và đưa ra câu trả lời dựa vào nhiều yếu tố)
## 2. Mục tiêu sản phẩm

Hệ thống cần làm được sáu việc:

1. Hiểu câu hỏi và nhận diện các dữ kiện nghiệp vụ quan trọng của thủ tục.
2. Biết khi nào còn thiếu ngày, địa phương, vai trò, đối tượng hoặc giấy tờ có thể làm thay đổi hướng dẫn.
3. Tìm đúng thủ tục, phiên bản, đối tượng, địa phương, cơ quan thực hiện và căn cứ hỗ trợ.
4. Tổng hợp câu trả lời ngắn gọn, có checklist, bước tiếp theo, điều kiện và ngoại lệ.
5. Gắn từng hướng dẫn trọng yếu với evidence kiểm chứng được.
6. Hỏi lại, cảnh báo hoặc từ chối khi không đủ căn cứ. (Khi trong tình huống prompt người dùng nhập có những yếu tố tình huống ko chắc chắn và có thể gây ra plot twist thì phải hỏi lại 1-3 câu hỏi quan trọng để xác định thêm)

## 3. Workflow toàn hệ thống trước khi đi sâu vào LLM

LLM chỉ là một bộ phận trong hệ thống lớn. Luồng tổng quát:

```text
1. Nhận diện phiên hoặc tài khoản người dùng
→ 2. Nhận, lưu và xếp hàng tin nhắn
→ 3. Xác định conversation và case thủ tục đang hoạt động
→ 4. Dựng context từ facts, summary và tin nhắn liên quan
→ 5. Qwen hiểu ý định và tạo/cập nhật Case Card
→ 6. Backend kiểm tra schema và dữ kiện còn thiếu
→ 7. Thiếu dữ kiện quyết định thì hỏi lại và tạm dừng
→ 8. Đủ dữ kiện thì RAG tìm đúng phiên bản thủ tục
→ 9. Procedure Engine tính checklist và bước tiếp theo
→ 10. Qwen diễn giải kết quả thành câu trả lời tự nhiên
→ 11. Verifier kiểm tra từng hướng dẫn với evidence
→ 12. Lưu answer/memory delta và stream về giao diện
```

Đây là **workflow trả lời online**. Song song với nó có một **workflow quản trị tri thức** chạy khi công ty/admin cung cấp dữ liệu:

```text
Upload/import dữ liệu nguồn
→ kiểm tra file, quyền truy cập và provenance
→ parse/chuẩn hóa thành procedure schema
→ người quản trị kiểm tra và phê duyệt phiên bản
→ lưu Procedure Store + snapshot nguồn
→ chunk/embed/index vào RAG
→ chạy retrieval/evaluation smoke test
→ publish phiên bản để workflow trả lời được phép sử dụng
```

Upload dữ liệu mới **không đồng nghĩa fine-tune lại Qwen**. Phần lớn cập nhật nghiệp vụ đi qua Procedure Store/RAG; fine-tune chỉ dùng khi cần cải thiện hành vi chung như trích xuất Case Card, hỏi lại hoặc trả lời theo format.

### 3.1. LLM đứng ở đâu?

Qwen làm ba việc chính:

1. Hiểu câu hỏi tự nhiên và trích xuất Case Card.
2. Hỗ trợ tạo truy vấn để tìm thủ tục phù hợp.
3. Diễn giải procedure bundle đã tìm được thành câu trả lời dễ hiểu.

Qwen không tự quản lý cookie, tài khoản, database, queue hoặc lịch sử; không tự coi kiến thức trong trọng số là nguồn chính thức; không tự quyết định checklist khi chưa có dữ liệu RAG.

### 3.2. Luồng AI/RAG bên trong workflow

```text
Câu hỏi
  ↓
Query Envelope / Case Card (chuyển câu query thành một hồ sơ truy vấn có hệ thống )
Ví dụ: “Tôi muốn đăng ký khai sinh cho con tại phường X, hiện có CCCD và giấy chứng sinh, cần làm gì tiếp?”
-> chuyển thành case Card: 

Vai trò: Cha/mẹ hoặc người đi đăng ký
Thủ tục: Đăng ký khai sinh
Địa phương: Phường X
Giấy tờ đã có: CCCD, giấy chứng sinh
Ngày yêu cầu: ngày hiện tại
Dữ kiện còn thiếu:
- Quan hệ của người đi đăng ký với trẻ
- Thông tin cư trú/hộ tịch cần thiết theo procedure version

  ↓
Lọc thời gian + thẩm quyền + phạm vi áp dụng
  ↓
Exact Search + BM25 + Dense Retrieval
-Exact search (tìm kiếm chính xác): ví dụ hỏi “Thủ tục đăng ký khai sinh trực tuyến tại TP.HCM” hoặc nêu một mã thủ tục cụ thể thì hệ thống ưu tiên tìm đúng procedure record.

-BM25 là thuật toán tính điểm và xếp hạng độ liên quan của văn bản trong tìm kiếm thông tin. Ví dụ với query “đăng ký khai sinh cần giấy tờ gì”, BM25 tập trung vào các từ khóa “đăng ký”, “khai sinh”, “giấy tờ”.

-Dense Retrieval tìm theo ý nghĩa thay vì chỉ khớp từ. Ví dụ “làm giấy khai sinh online cho bé” có thể gần nghĩa với procedure mang tên chính thức “đăng ký khai sinh trực tuyến”, dù câu chữ khác nhau.
  ↓
Reranker thủ tục + mở rộng dẫn chiếu có kiểm soát 
-Reranker dùng model fine-tune để ranking tài liệu lại vì BM25 và dense retrieval có thể xếp hạng và đưa ra 50 tài liệu nhưng chưa chắc 50 tài liệu này sẽ xài hết nên là cần rerank lại cái đoạn nào thực sự cần 

-Mở rộng dẫn chiếu có kiểm soát: từ procedure record có thể lấy thêm biểu mẫu, căn cứ pháp lý hoặc quy định địa phương được tham chiếu, nhưng chỉ mở rộng giới hạn để tránh context bị phình to.
  ↓
Evidence Pack tối thiểu nhưng đủ
Ví dụ một procedure bundle gồm: tên thủ tục, đối tượng, giấy tờ, các bước, cơ quan/nơi nộp, phí, thời hạn, phiên bản hiệu lực, biểu mẫu và URL chính thức. Qwen chỉ được hướng dẫn dựa trên các evidence này.
  ↓
Generator 1.7B–4B (QWEN)
  ↓
Claim–Citation Audit (kiểm tra từng hướng dẫn về giấy tờ, bước làm, nơi nộp, phí hoặc thời hạn có thật sự được evidence hỗ trợ hay không)
  ↓
Trả lời / hỏi lại / cảnh báo / chuyển chuyên gia
```

Nguyên tắc quan trọng nhất:

```text
Model học cách hiểu yêu cầu và diễn giải hướng dẫn.
Procedure Store/RAG lưu tri thức thủ tục và căn cứ hỗ trợ.
Backend quản lý người dùng, trạng thái hồ sơ và luồng xử lý xác định.
Verifier kiểm tra điều model phát biểu với evidence.
```
Cấu hình chốt tạm thời
Dense retriever: BGE-M3
Reranker chính: BGE-reranker-v2-m3
Reranker đối chứng: Qwen3-Reranker-0.6B
Candidate trước rerank: khoảng 50
Evidence sau rerank: khoảng 5–8
Fine-tune: query + positive + hard negatives hành chính công Việt Nam
## 4. Những quyết định đã chốt tạm thời

| Hạng mục | Quyết định hiện tại |
|---|---|
| Phạm vi | Hỏi đáp và hướng dẫn thủ tục hành chính công; ngoài phạm vi phải nói rõ và chuyển hướng an toàn |
| Generator | Một model dense 1.7B–4B; không tạo model riêng cho từng bộ/ngành |
| Ứng viên chính | Qwen3-4B-Instruct-2507 |
| Challenger | ViLegalQwen3-1.7B-Base sau grounded SFT/QLoRA |
| Nhánh nghiên cứu | Qwen3-4B-Base → CPT/DAPT → mixed SFT |
| Model lớn | Chỉ dùng offline làm teacher hoặc baseline |
| Tri thức nghiệp vụ | Procedure Store/RAG có phiên bản; văn bản pháp luật chỉ là căn cứ hỗ trợ |
| Fine-tuning | Ưu tiên QLoRA để thử nhanh; full fine-tuning chỉ khi có bằng chứng cần thiết |
| Lượng tử hóa | Xuất BF16, Q5 và Q4; production chọn bản vượt quality gate |
| Runtime | Cục bộ; RTX 5060 Ti 16GB là máy tham chiếu của nhóm |
| KPI trung tâm | Grounded Joint Accuracy |
| Phạm vi MVP | Một nhóm thủ tục hành chính công đại diện, có thể đo đầy đủ từ đầu đến cuối |
| Multi-user | Cách ly bằng `user_id → case_id → conversation_id`; không trộn lịch sử |
| Long-term context | Raw messages + Case Card + structured facts + case summary có provenance |
| Realtime/queue | Socket.IO để stream; xử lý tuần tự trong một conversation, song song giữa users |
| Hạ tầng MVP | FastAPI, PostgreSQL, Redis, Qdrant, MinIO và model server qua Docker Compose |

Sơ đồ và contract hệ thống chi tiết nằm trong `kien-truc-he-thong-tro-ly-hanh-chinh-cong.md`.

## 5. Điều chưa được chốt

Các nội dung sau phải đợi dữ liệu và yêu cầu chính thức từ công ty:

- Danh mục thủ tục hành chính, lĩnh vực dịch vụ công, cấp cơ quan và địa phương có trong MVP.
- Dữ liệu có đủ điều kiện, thành phần hồ sơ, biểu mẫu, phí, thời hạn, nơi/kênh nộp và lịch sử phiên bản hay không.
- Quyền sử dụng dữ liệu cho CPT, SFT, RAG và phát hành model.
- Chất lượng metadata về hiệu lực và quan hệ sửa đổi/thay thế.
- Cấu hình GPU, quota huấn luyện, target hardware và SLA production.
- Model chiến thắng giữa 1.7B và 4B.
- Có cần CPT hoặc full fine-tuning hay không.
- Ngưỡng latency, độ chính xác và mức rủi ro được công ty chấp nhận.

---

# PHẦN II – PHÂN: CHIẾN LƯỢC TỪNG THÀNH PHẦN

## 6. Phạm vi và Procedure Coverage Contract

“Hỗ trợ hành chính công” phải được giới hạn bằng một danh mục thủ tục có thể kiểm đếm, không tuyên bố chung chung:

```text
service_domain
procedure_code
procedure_title
competent_authority
jurisdiction
submission_channels
covered_version_range
required_fields_complete
documents_complete
steps_complete
fees_and_time_complete
forms_complete
legal_basis_complete
verified_status
last_checked_at
source_health
```

Mỗi thủ tục hoặc nhóm thủ tục có maturity state:

```text
INDEXED → RETRIEVAL_TESTED → ANSWER_TESTED → ADVISORY_ENABLED
```

Thủ tục chưa đạt `ADVISORY_ENABLED` chỉ được hiển thị như dữ liệu tham khảo hoặc thông báo chưa hỗ trợ; hệ thống không tự ghép quy trình thiếu dữ liệu.

## 7. Chiến lược dữ liệu (đợi gửi data)

### 7.1. Việc đầu tiên khi nhận dữ liệu

Không train ngay. Nhóm phải lập `Data Readiness Report` gồm:

- Nguồn gốc, quyền sử dụng và mức độ authoritative.
- Loại dữ liệu, định dạng và encoding.
- Số lượng thủ tục, phiên bản, cơ quan, địa phương, thành phần hồ sơ, bước xử lý, biểu mẫu và căn cứ pháp lý.
- Tỷ lệ có ngày ban hành, hiệu lực, hết hiệu lực và cơ quan ban hành.
- Khả năng nối văn bản sửa đổi, thay thế, bãi bỏ và hợp nhất.
- Trùng lặp exact/near-duplicate và lỗi OCR/parser.
- URL chết, nội dung web khác snapshot và checksum.
- PII, bí mật nội bộ và chính sách retention.
- Khả năng tạo train/dev/test mà không rò rỉ.

### 7.2. Tách dữ liệu thành bốn kho

| Kho | Ví dụ | Công dụng |
|---|---|---|
| Procedure knowledge | Thủ tục, điều kiện, hồ sơ, bước, cơ quan, địa điểm/kênh nộp, phí, thời hạn, biểu mẫu, phiên bản | Procedure Store/RAG |
| Supporting legal corpus | Văn bản căn cứ, metadata, Điều/Khoản/Điểm và phiên bản | Giải thích/citation khi cần |
| Behavior/SFT corpus | QA, tình huống, Case Card, tool call, claim–evidence | Dạy hành vi |
| Evaluation corpus | Ca kín có đáp án và evidence gold | Đánh giá duy nhất |

Một bản công bố thủ tục hoặc văn bản pháp luật thô có giá trị đầu tiên đối với kho tri thức. Nó không tự động trở thành dữ liệu SFT.

### 7.3. Bronze, Silver và Gold

- `Bronze`: dữ liệu thô có provenance.
- `Silver`: đã chuẩn hóa hoặc sinh tổng hợp, vượt kiểm tra tự động.
- `Gold`: được người có chuyên môn rà soát.

Cần xây `Gold Core` nhỏ nhưng đáng tin cậy. Gold dùng để train phải tách khỏi Gold dùng để đánh giá.

### 7.4. Chống leakage

- Không random split từng câu QA.
- Gom cùng thủ tục và các phiên bản vào một `procedure_family_id`; văn bản căn cứ dùng `document_family_id`.
- Gom paraphrase cùng tình huống vào một `scenario_group_id`.
- Exact hash và semantic dedup giữa train/dev/test.
- Có temporal holdout: phiên bản thủ tục/văn bản mới chỉ được thêm vào RAG sau mốc T0.
- Giữ private test khóa; không dùng nó để chọn prompt hoặc checkpoint.

## 8. Versioned Procedure Store và kho căn cứ pháp lý

Đơn vị dữ liệu chính là một phiên bản thủ tục hành chính:

```text
Lĩnh vực dịch vụ công → Thủ tục → Phiên bản → Điều kiện/Hồ sơ/Bước thực hiện
```

Mỗi `procedure_version` cần tối thiểu:

```text
procedure_code
procedure_version_id
service_domain
title
applicant_types
eligibility_conditions
required_facts
required_documents + conditions
steps
competent_authority
jurisdiction_rules
submission_channels
submission_locations
forms
fees
processing_time
result_type
legal_basis_ids
valid_from / valid_to
official_url
source_snapshot_id
verified_at
```

Văn bản căn cứ được lưu ở kho phụ theo cấu trúc `Văn bản → Điều → Khoản → Điểm` để dẫn nguồn và giải thích khi cần. Cả hai kho đều append-only; phiên bản mới không ghi đè phiên bản cũ.

Khi chọn thủ tục áp dụng tại thời điểm người dùng hỏi hoặc thực hiện hồ sơ:

```text
effective_from <= event_date < effective_to
```

Nếu thiếu ngày và ngày có thể làm đảo kết luận, hệ thống phải hỏi lại.

## 9. Retrieval

### 9.1. Baseline bắt buộc

1. Exact lookup cho mã/tên thủ tục, biểu mẫu và cơ quan thực hiện.
2. Metadata filter theo thời gian, đối tượng, thẩm quyền, địa phương và kênh nộp.
3. BM25 cho từ khóa và định danh chính xác.
4. Dense retrieval cho tương đồng ngữ nghĩa.
5. Rank fusion để hợp nhất candidate.
6. Reranker đã fine-tune bằng hard negatives từ dữ liệu hành chính công Việt Nam.
7. Mở rộng có kiểm soát sang biểu mẫu, quy định địa phương hoặc văn bản căn cứ.
8. Đóng gói một `procedure bundle` đủ điều kiện, hồ sơ, bước, nơi nộp, phí, thời hạn và citation cần thiết.

### 9.2. Chunking

Không cắt mù theo số token. Embedding text nên có breadcrumb ngắn:

```text
[Tên thủ tục + mã thủ tục]
[Phiên bản + phạm vi địa phương]
[Mục: điều kiện/hồ sơ/bước/phí/thời hạn]
[Nội dung]
[Nguồn chính thức]
```

### 9.3. Hard negatives

Các negative quan trọng:

- Thủ tục gần tên nhưng khác đối tượng hoặc kết quả đầu ra.
- Phiên bản thủ tục đã hết hiệu lực.
- Cùng tên thủ tục nhưng sai cấp cơ quan hoặc địa phương.
- Hướng dẫn trực tiếp khi người dùng hỏi nộp trực tuyến và ngược lại.
- Biểu mẫu hoặc văn bản căn cứ không thuộc phiên bản đang áp dụng.
- Evidence có từ khóa giống nhưng thiếu điều kiện quyết định.

Reranker tổng quát, hybrid search và top-k lớn không mặc định tốt hơn. Mọi thành phần phải qua ablation.

### 9.4. Reranker chốt tạm thời

Reranker là model chuyên chấm độ liên quan của từng cặp `query ↔ passage`. Nó không sinh câu trả lời, không kết luận pháp lý và không thay thế bộ lọc hiệu lực.

Phân biệt hai model trong retrieval:

```text
BAAI/bge-m3
→ bi-encoder dùng để tìm nhanh trên toàn kho

BAAI/bge-reranker-v2-m3
→ cross-encoder đọc đồng thời query và passage
→ xuất một relevance score để sắp xếp lại candidate
```

Các ứng viên:

| Vai trò | Model | Lý do |
|---|---|---|
| Baseline chính | `BAAI/bge-reranker-v2-m3` | Khoảng 568M, multilingual, Apache-2.0, inference nhanh và đã được dùng trong pipeline retrieval luật Việt Nam |
| Challenger | `Qwen/Qwen3-Reranker-0.6B` | Multilingual, instruction-aware, Apache-2.0; có tiềm năng chính xác hơn nhưng decoder thường chậm hơn |

Luồng runtime khởi đầu:

```text
Lọc thời gian/thẩm quyền
→ BM25 + BGE-M3
→ rank fusion và deduplicate
→ giữ khoảng 50 candidate
→ BGE rerank từng cặp query–passage
→ giữ khoảng 5–8 evidence
→ generator trả lời
```

Nếu câu hỏi nêu rõ số hiệu hoặc Điều/Khoản, exact match phải được bảo vệ hoặc đi theo nhánh lookup riêng; không để reranker vô tình loại bỏ căn cứ được gọi đích danh.

### 9.5. Fine-tune reranker

Không fine-tune trước khi có zero-shot baseline. Dữ liệu huấn luyện dùng dạng:

```json
{
  "query": "Câu hỏi hoặc tình huống pháp lý",
  "pos": ["Điều/Khoản thực sự liên quan và áp dụng"],
  "neg": [
    "Điều gần nghĩa nhưng không hỗ trợ kết luận",
    "Phiên bản đã hết hiệu lực",
    "Cùng số Điều nhưng thuộc văn bản khác",
    "Quy định sai đối tượng hoặc thẩm quyền"
  ]
}
```

Mỗi query dự kiến có 1–3 positive và 5–15 negatives gồm random negatives và hard negatives từ kết quả BM25/dense. Split theo `document_family_id` và thời gian; không để phiên bản hoặc paraphrase của cùng một ca lọt sang test.

Thiết lập thử nghiệm ban đầu trên RTX 5060 Ti 16GB:

- BGE: max length 384–512, micro-batch 1–2, gradient accumulation, 1–2 epoch; thử full fine-tuning và chỉ dùng LoRA nếu cần.
- Qwen reranker: ưu tiên LoRA/QLoRA, max length 512–1024, micro-batch 1; không train ở context 32K.
- Công ty có thể dùng GPU mạnh hơn để chạy nhiều seed/config song song, nhưng artifact production vẫn phải đạt lightweight gate.

### 9.6. Bake-off reranker

So sánh trên cùng một candidate pool:

1. Không reranker.
2. BGE zero-shot.
3. BGE đã fine-tune pháp lý Việt Nam.
4. Qwen3-Reranker-0.6B zero-shot và LoRA.

Đo `nDCG@10`, `MRR@10`, `Recall/F2@5`, `correct-version@k`, worst-domain và latency P50/P95. Chỉ đưa reranker vào production nếu nó cải thiện retrieval end-to-end; không chọn chỉ dựa trên benchmark tổng quát.

## 10. MCP và công cụ

MCP gateway chỉ read-only trong phiên bản đầu:

```text
search_legal_provisions(...)
get_provision_bundle(...)
check_applicability(...)
trace_legal_changes(...)
get_corpus_status(...)
```

Model chỉ phát `evidence_id`. Backend chịu trách nhiệm ánh xạ thành tên văn bản, số Điều/Khoản, phiên bản, exact text và URL thật.

## 11. Model và huấn luyện

### 11.1. Ba nhánh bake-off

```text
M0: ViLegalQwen3-1.7B-Base
    → mixed grounded SFT/QLoRA
    → Temporal RAG

M1: Qwen3-4B-Instruct-2507
    → mixed grounded SFT/QLoRA
    → Temporal RAG

M2: Qwen3-4B-Base
    → pilot CPT/DAPT + general replay
    → mixed grounded SFT
    → Temporal RAG
```

M2 chỉ được mở rộng nếu pilot thắng M1 trên test kín. Không chọn model theo tên, kích thước hoặc một benchmark đơn lẻ.

### 11.2. Curriculum huấn luyện

```text
Stage 0 — Baseline không train
Stage 1 — Broad multi-task SFT
Stage 2 — Grounded SFT
Stage 3 — Gold polishing + replay
Stage 4 — CPT/distillation nếu ablation chứng minh cần
Stage 5 — Merge và quantize
```

Broad SFT dạy:

- Hiểu lệnh và tiếng Việt tổng quát.
- Domain routing và issue spotting.
- Trích ngày, chủ thể, địa phương và dữ kiện thiếu.
- Tool calling và structured output.
- Tóm tắt, QA và đối thoại.

Grounded SFT dạy:

- Chỉ sử dụng evidence được cung cấp.
- Gắn claim với evidence ID.
- Phân biệt evidence đúng, nhiễu và không áp dụng.
- Hỏi lại hoặc từ chối khi chưa đủ căn cứ.
- Xử lý phiên bản cũ/mới và nguồn xung đột.

### 11.3. Synthetic data và teacher

```text
Điều luật thật
→ teacher tạo tình huống khi đã nhìn thấy evidence
→ backend kiểm tra ID/ngày/trích dẫn
→ teacher khác sửa hoặc phản biện
→ verifier chấm consistency
→ chuyên gia kiểm tra mẫu
→ mẫu đạt chuẩn mới được đưa vào SFT
```

Không distill “kiến thức trong đầu teacher” và không lưu chain-of-thought dài. Chỉ lưu cấu trúc kiểm chứng được:

```json
{
  "material_facts": [],
  "missing_facts": [],
  "applicable_provisions": [],
  "conditions": [],
  "conclusion": "",
  "answer_status": ""
}
```

### 11.4. General replay

Không dùng 100% legal data theo mặc định. Pilot với cùng token budget:

```text
SFT: 100/0, 75/25, 50/50 legal/general
CPT: 98/2, 90/10, 75/25 legal/general
```

Đây là dải thí nghiệm, không phải tỉ lệ tối ưu đã chốt.

## 12. Lượng tử hóa và lightweight

Lightweight được đo ở thời điểm triển khai, không phải bằng loại GPU dùng để huấn luyện.

```text
Checkpoint tốt nhất
→ merge adapter
→ lưu master BF16
→ xuất Q5/INT8
→ xuất Q4/AWQ/GPTQ
→ benchmark lại toàn bộ quality và safety
```

Phải đo hai lớp:

- `Model footprint`: kích thước file, VRAM, TTFT, token/giây.
- `End-to-end footprint`: generator, embedding, reranker, vector DB, MCP, KV cache và latency P95.

Q4 chỉ được chọn nếu không làm tăng critical error hoặc citation hallucination. Nếu không đạt, dùng Q5.

## 13. Claim–Citation Audit và an toàn

Mỗi claim quan trọng phải có `evidence_id`. Verifier kiểm bốn tầng:

1. Nguồn có thật và thuộc allowlist.
2. Fragment được trích có thật.
3. Fragment thực sự hỗ trợ claim.
4. Văn bản đúng thời điểm, thẩm quyền và phạm vi áp dụng.

Trạng thái citation:

```text
verified
unresolved
misquoted
unsupported
wrong_version
inapplicable
```

Khi audit thất bại:

1. Sửa đúng claim lỗi tối đa một lần.
2. Nếu vẫn lỗi, bỏ claim hoặc chuyển sang trạng thái an toàn.
3. Ca rủi ro cao phải yêu cầu human review.

Trạng thái đầu ra:

```text
ANSWER_VERIFIED
ASK_CLARIFICATION
INSUFFICIENT_EVIDENCE
CONFLICT_DETECTED
HIGH_RISK_ESCALATION
```

## 14. Đánh giá

### 14.1. Bốn chế độ đánh giá

1. Model closed-book.
2. Model nhận oracle/gold evidence.
3. Model nhận evidence từ retriever thật.
4. Retriever + temporal filter + verifier.

Cách này phân biệt lỗi do model, retrieval, versioning hay verifier.

### 14.2. KPI trung tâm

```text
Grounded Joint Accuracy =
kết luận đúng
AND mọi claim trọng yếu được evidence hỗ trợ
AND căn cứ đúng phiên bản, hiệu lực, thẩm quyền và phạm vi áp dụng
```

### 14.3. Các metric bắt buộc

- Retrieval Recall@5/10/100, F2, MRR/nDCG và exact-span precision/recall.
- Correct-version@k, jurisdiction/authority accuracy và wrong-document rate.
- Answer accuracy với gold evidence và retrieved evidence.
- Citation existence, support, coverage và temporal accuracy.
- Unsupported material claim rate.
- Abstention precision/recall và unsafe answer rate.
- JSON/tool-call validity.
- Macro, worst-domain và P10-domain; không chỉ micro average.
- VRAM, TTFT, token/giây và latency P50/P95.
- Suy giảm giữa BF16, Q5 và Q4.

### 14.4. Test đặc biệt

- Thiếu dữ kiện quyết định.
- Tiền đề sai hoặc số Điều bị người dùng nêu sai.
- Văn bản hết hiệu lực hoặc chưa có hiệu lực.
- Cùng điều luật nhưng khác phiên bản.
- Nguồn xung đột.
- Luật chung và luật chuyên ngành.
- Trung ương và địa phương.
- Evidence gần nghĩa nhưng không hỗ trợ claim.
- Prompt injection nằm trong tài liệu retrieval.
- Câu hỏi rủi ro cao về hình sự, thuế, đất đai hoặc thời hạn tố tụng.

## 15. Phân chia ba luồng công việc

Đây là phân chia theo ownership, không tạo ba hệ thống tách rời.

### Thành viên A – Data, Procedure Store và RAG

- Data inventory, Data Readiness Report và license/provenance.
- Parser, normalizer, canonical ID và checksum.
- Version/effectivity, relation table và Coverage Manifest.
- Kho quy trình hành chính, checklist, thẩm quyền và biểu mẫu.
- BGE-M3, hybrid retrieval, reranker và temporal test data.

### Thành viên B – AI Core và Evaluation

- Case Card, memory delta và structured output.
- Baseline 1.7B/4B và QLoRA.
- Dataset SFT, general replay, synthetic pipeline và gold polishing.
- Structured output, semantic NLI verifier và abstention.
- Benchmark, quantization và performance profiling.

### Thành viên C – Product Platform và Web

- Identity/session, anonymous cookie và OTP.
- PostgreSQL schema, Redis queue/lock và transactional outbox.
- FastAPI, Socket.IO, API contract và context orchestration.
- Lịch sử, case memory, summary worker và multi-user isolation.
- Web demo, upload, evidence panel, Docker và `.env.example`.

### Việc cả nhóm cùng chịu trách nhiệm

- Chốt schema giao tiếp giữa ba luồng ngay từ đầu.
- Review chéo pull request và dữ liệu Gold.
- Giữ private evaluation set bất biến.
- Demo end-to-end hàng tuần; không đợi từng phần “hoàn hảo” mới ghép.
- Mọi kết quả thí nghiệm ghi cùng commit, dataset version, seed và config.

## 16. Hợp đồng giao tiếp giữa các phần

Sáu schema phải được khóa sớm:

```text
RequestContext
Message
QueryEnvelope
MemoryDelta
EvidenceBundle
ModelAnswer
```

Mỗi thay đổi schema cần:

1. Version mới.
2. Migration hoặc backward compatibility.
3. Contract test.
4. Thông báo cho hai luồng còn lại.

---

# PHẦN III – HỢP: KẾ HOẠCH THỰC HIỆN CHUNG

## 17. Lộ trình theo cổng nghiệm thu

### Giai đoạn 0A – Walking skeleton của sản phẩm

- Anonymous session và cookie an toàn.
- Tạo conversation/case, lưu message vào PostgreSQL.
- Queue một worker và stream mock response qua Socket.IO.
- Refresh hoặc đăng nhập lại vẫn xem đúng lịch sử của chính người dùng.
- Dựng khung bảy khu vực web demo.

**Gate:** hai người dùng chạy đồng thời không lẫn dữ liệu; message trong cùng conversation không đảo thứ tự.

### Giai đoạn 0 – Xác nhận đầu vào

- Nhận dữ liệu và tài nguyên công ty.
- Lập Data Readiness Report.
- Chốt Procedure Coverage Contract, target hardware và SLA.
- Tạo private evaluation set ban đầu.

**Gate:** biết rõ dữ liệu nào dùng cho RAG, CPT, SFT và test; quyền sử dụng rõ ràng.

### Giai đoạn 1 – Procedure Store và versioned index

- Raw immutable store.
- Parse thủ tục thành điều kiện, hồ sơ, bước, cơ quan, địa điểm/kênh nộp, phí, thời hạn và biểu mẫu.
- Nối phiên bản thủ tục với căn cứ pháp lý và quan hệ thay thế/hết hiệu lực tối thiểu.
- Coverage dashboard.

**Gate:** truy ngược được mọi fragment về nguồn và phiên bản chính xác.

### Giai đoạn 2 – Evaluation-first baseline

- Dựng DRiLL-style retrieval baseline.
- Chạy M0 và M1 chưa fine-tune trên cùng evidence.
- Đo oracle evidence và real retrieval.

**Gate:** biết bottleneck chính nằm ở data, retrieval hay generator.

### Giai đoạn 3 – Grounded model

- Broad SFT → grounded SFT → gold polishing.
- So sánh ViLegalQwen3-1.7B và Qwen3-4B.
- Pilot CPT nhánh M2 nếu dữ liệu phù hợp.

**Gate:** model thắng baseline trên Grounded Joint Accuracy và không tăng critical errors.

### Giai đoạn 4 – Audit và freshness

- Citation verifier bốn tầng.
- MCP, cache invalidation và incremental update.
- Temporal T0/T1 test.

**Gate:** hệ thống fail closed khi nguồn không được xác minh.

### Giai đoạn 5 – Compression và pilot

- Xuất BF16, Q5 và Q4.
- Benchmark trên RTX 5060 Ti 16GB và target production.
- Expert blind review, security và PII test.

**Gate:** vượt quality, safety và lightweight gate.

## 18. Definition of Done cho MVP

MVP chỉ được xem là hoàn thành khi:

- Có định danh phiên, lịch sử lâu dài và cách ly ngữ cảnh nhiều người dùng.
- Một người có thể quản lý hai case riêng như CCCD và khai sinh mà không bị trộn memory.
- Message cùng conversation được xử lý tuần tự, retry không tạo câu trả lời trùng.
- Socket mất kết nối có thể đồng bộ lại từ database.
- Web demo hiển thị chat, Case Card/checklist, evidence, lịch sử và trạng thái upload RAG.
- Có phạm vi thủ tục được công bố bằng Procedure Coverage Manifest.
- Có thể truy xuất đúng thủ tục, đối tượng, địa phương và phiên bản tại ngày được hỏi; căn cứ pháp lý đi kèm khi cần.
- Mọi claim trọng yếu trong câu trả lời đều có citation đã audit.
- Hệ thống hỏi lại khi thiếu dữ kiện quyết định.
- Có ít nhất ba nhóm thủ tục hành chính và một tình huống cần phân biệt hai thủ tục gần nhau trong demo.
- Có ca thay đổi ngày làm thay đổi evidence hoặc kết luận.
- Có ca thêm/cập nhật thủ tục trong RAG mà không fine-tune lại model.
- Có so sánh 1.7B với 4B và BF16 với Q5/Q4.
- Có báo cáo macro, worst-domain, latency và critical errors.
- Model production chạy cục bộ trên target hardware đã thống nhất.

## 19. Những việc không làm ở MVP

- Model hoặc adapter riêng cho từng bộ/ngành/tỉnh.
- Multi-agent debate cho mọi truy vấn.
- Knowledge graph khái niệm toàn diện hoặc GNN trước khi baseline chứng minh cần.
- GRPO/RL phức tạp trước khi SFT đạt trần rõ ràng.
- Đưa toàn bộ kho thủ tục và văn bản căn cứ vào long context.
- Dự đoán chắc chắn kết quả tranh chấp.
- Tự nộp hồ sơ hoặc thực hiện hành động pháp lý thay người dùng.
- Tuyên bố “không hallucinate” hoặc “bao phủ toàn bộ” khi chưa có số liệu.

## 20. Việc nhóm làm ngay

1. Review và chốt `kien-truc-he-thong-tro-ly-hanh-chinh-cong.md` với công ty.
2. Khóa sáu schema `RequestContext`, `Message`, `QueryEnvelope`, `MemoryDelta`, `EvidenceBundle`, `ModelAnswer`.
3. Vẽ wireframe bảy khu vực web và chốt API v1.
4. Tạo Docker Compose skeleton từ `.env.example`.
5. Dựng walking skeleton: session → message DB → queue → mock worker → Socket.IO → history.
6. Chuẩn bị `Data Readiness Report`, `Procedure Coverage Contract` và private pilot test.
7. Sau đó mới gắn Case Card, RAG, Qwen và verifier lần lượt vào skeleton.
8. Thực hiện bake-off kiến trúc v0.3: thêm `Policy Router`, `Evidence Gate`, `AnswerPlan + ExpectedClaimSet`; tách `Procedure Resolver`, `Procedure Store/Engine` và `Evidence Retriever`; đo chất lượng lẫn độ trễ trên RTX 5060 Ti 16GB trước khi chọn cấu hình production.

## 21. Câu chốt chung của nhóm

> **Mục tiêu là một trợ lý hành chính công lightweight: hiểu người dùng đang làm thủ tục nào, nhớ đúng ngữ cảnh từng case, tìm đúng phiên bản quy trình và hướng dẫn bước tiếp theo bằng dữ liệu chính thức đã kiểm chứng.**

## 22. Nguồn nghiên cứu định hướng

- [Báo cáo nghiên cứu tối ưu kiến trúc lightweight](nghien-cuu-toi-uu-kien-truc-lightweight.md)
- [ViLegalLM](https://aclanthology.org/2026.findings-acl.1801/)
- [VLSP 2025 LegalSLM – Bosch](https://aclanthology.org/2025.vlsp-1.22/)
- [MinLegal](https://aclanthology.org/2025.vlsp-1.24.pdf)
- [DRiLL Vietnamese Legal Retrieval](https://aclanthology.org/2025.vlsp-1.20.pdf)
- [LawInstruct](https://aclanthology.org/2025.findings-naacl.7/)
- [Lawyer LLaMA](https://arxiv.org/abs/2305.15062)
- [LegalBench-RAG](https://arxiv.org/abs/2408.10343)
- [Temporal Misgrounding in Legal RAG](https://arxiv.org/abs/2608.09393)
- [PLawBench](https://aclanthology.org/2026.acl-long.458/)
- [Hallucination-Free? Assessing Legal RAG Tools](https://nlp.stanford.edu/~manning/papers/Magesh-Hallucination%E2%80%90Free-2025.pdf)

---

Tài liệu chi tiết kỹ thuật và các ngưỡng nghiệm thu nằm trong `ke-hoach-du-an-luat-dung-luc.md`.
