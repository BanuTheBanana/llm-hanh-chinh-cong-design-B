# Kế hoạch nghiên cứu nền “Luật Đúng Lúc” — đã được thay thế về phạm vi

> **Trạng thái tài liệu:** Đây là bản nghiên cứu cũ theo giả định bao phủ pháp luật diện rộng. Phạm vi hiện hành đã đổi thành **trợ lý hỏi đáp và hướng dẫn thủ tục hành chính công**. Khi có mâu thuẫn, dùng `khung-du-an-LLM.md` và `kien-truc-he-thong-tro-ly-hanh-chinh-cong.md` làm tài liệu chuẩn. Các phần retrieval, grounding, đánh giá và lightweight bên dưới chỉ được giữ làm tài liệu tham khảo kỹ thuật; **không thực thi các quyết định phạm vi ở phần lịch sử dưới đây**.

> Phiên bản 2.1 – tài liệu lịch sử sau khi đối chiếu các nghiên cứu Legal LLM, Legal RAG và benchmark đến tháng 09/2026.

## Nội dung lịch sử — không còn là kế hoạch hiện hành

## 1. Các quyết định đã chốt

1. Hệ thống phải tiếp nhận câu hỏi thuộc **mọi lĩnh vực pháp luật Việt Nam**, không còn giới hạn ở luật lao động.
2. Phạm vi rộng được giải quyết chủ yếu bằng **kho luật toàn quốc có phiên bản thời gian + retrieval + MCP**, không bằng cách bắt model ghi nhớ mọi văn bản.
3. Chỉ dùng **một generator phổ quát 1.7B–4B** trong production; Qwen3-4B là ứng viên chính và ViLegalQwen3-1.7B là challenger bắt buộc. Không tạo model riêng cho từng bộ, ngành hoặc địa phương.
4. GPU mạnh của công ty được dùng ở giai đoạn offline để continued pretraining, distillation, tạo dữ liệu, huấn luyện retriever/verifier và chạy nhiều thí nghiệm. Nó không phải lý do để tăng model production lên 8B/14B.
5. Model lớn hơn chỉ được dùng làm **teacher hoặc baseline**, không tham gia sinh câu trả lời trong sản phẩm cuối.
6. Model cuối phải có bản Q4; Q5 là phương án an toàn nếu Q4 làm giảm độ chính xác pháp lý quá mức.
7. Mọi nhận định pháp lý phải gắn với evidence từ nguồn được phép. Không đủ dữ kiện hoặc không xác minh được nguồn thì hệ thống hỏi lại hoặc từ chối kết luận.
8. “Toàn bộ pháp luật Việt Nam” phải được định nghĩa và đo bằng **Coverage Contract**, không được tuyên bố chung chung.
9. Không train ngay khi nhận dữ liệu. Phải lập **Data Readiness Report**, tách dữ liệu thành knowledge corpus, CPT corpus, behavior/SFT corpus và evaluation corpus.
10. KPI trung tâm là **Grounded Joint Accuracy**, không phải một điểm MCQ, ROUGE hoặc cảm nhận câu trả lời trôi chảy.

Thông điệp sản phẩm:

> **Luật Đúng Lúc sử dụng một model 1.7B–4B nhẹ để giải đáp trên kho pháp luật Việt Nam đa lĩnh vực và đa cấp ban hành. Hệ thống lấy đúng quy phạm, đúng phiên bản, đúng thẩm quyền, gắn bằng chứng cho từng nhận định và biết khi nào chưa đủ căn cứ để kết luận.**

---

## 2. Định nghĩa phạm vi “toàn bộ pháp luật Việt Nam”

### 2.1. Coverage Contract

Trước khi thu thập hoặc train, nhóm và công ty phải ký duyệt một danh mục phạm vi có thể kiểm đếm. Bản dự kiến gồm:

- Văn bản quy phạm pháp luật ở trung ương.
- Văn bản của bộ, cơ quan ngang bộ và các cơ quan có thẩm quyền liên quan.
- Văn bản quy phạm pháp luật địa phương nếu công ty xác nhận nằm trong phạm vi.
- Văn bản đang có hiệu lực, chưa có hiệu lực và đã hết hiệu lực để trả lời theo thời điểm lịch sử.
- Các phiên bản sửa đổi, thay thế, bãi bỏ và văn bản hợp nhất.

Các collection hỗ trợ phải lưu riêng, không trộn với kho quy phạm:

- Thủ tục hành chính và biểu mẫu chính thức.
- Án lệ được công bố chính thức.
- Điều ước, tiêu chuẩn hoặc tài liệu hướng dẫn nếu công ty yêu cầu.
- Bản án hoặc quyết định cá biệt nếu có quyền sử dụng và đã xử lý dữ liệu cá nhân.

Không dùng làm căn cứ pháp lý cuối cùng:

- Dự thảo chưa được ban hành.
- Tin tức, blog và bài bình luận.
- Câu trả lời do teacher model tự tạo nhưng chưa đối chiếu nguồn.
- Tài liệu không xác định được nguồn hoặc giấy phép.

### 2.2. Coverage Manifest

Mỗi nguồn hoặc nhóm văn bản phải có manifest:

```text
authority
central_or_local
document_types
covered_time_range
official_source
expected_document_count
collected_count
parsed_count
verified_count
last_checked_at
source_health
```

Dashboard phải cho biết lĩnh vực/cơ quan nào đã đủ dữ liệu và chỗ nào còn thiếu. Đây là bằng chứng cho chữ “toàn bộ”.

### 2.3. Bốn trạng thái phục vụ

Hệ thống nhận câu hỏi ở mọi lĩnh vực nhưng kiểm soát độ sâu câu trả lời:

| Trạng thái | Hành vi |
|---|---|
| `LOOKUP_VERIFIED` | Tra cứu, giải thích và trích dẫn nguồn đã xác minh |
| `ANALYSIS_CONDITIONAL` | Phân tích tình huống, nêu rõ giả định và điều kiện áp dụng |
| `NEEDS_CLARIFICATION` | Hỏi thêm ngày, địa phương, vai trò hoặc dữ kiện có thể làm đảo kết luận |
| `EXPERT_REVIEW_REQUIRED` | Nguồn xung đột, bằng chứng thiếu hoặc vấn đề có rủi ro cao |

Mỗi lĩnh vực còn có maturity state:

```text
INDEXED → RETRIEVAL_TESTED → ANSWER_TESTED → ADVISORY_ENABLED
```

Một lĩnh vực chưa đạt `ADVISORY_ENABLED` vẫn được tra cứu có dẫn nguồn, nhưng không được kết luận chắc chắn như chuyên gia.

---

## 3. Trải nghiệm người dùng

### 3.1. Query Envelope và Case Card

Model chuyển câu hỏi thành dữ liệu có cấu trúc:

```json
{
  "intent": "scenario_analysis",
  "domains": ["labor", "social_insurance"],
  "valid_at": "2026-08-15",
  "known_at": "2026-09-03",
  "territories": ["VN", "TP.HCM"],
  "actors": ["employee", "employer"],
  "explicit_citations": [],
  "risk_level": "medium",
  "missing_decisive_facts": []
}
```

`domains` là multi-label vì một vụ việc có thể liên quan đồng thời nhiều lĩnh vực. Domain chỉ giúp ưu tiên retrieval, không được hard-filter nếu model chưa chắc chắn.

Người dùng được xác nhận các dữ kiện quan trọng trước khi hệ thống kết luận.

### 3.2. Cấu trúc câu trả lời

1. **Kết luận ngắn hoặc trạng thái chưa thể kết luận.**
2. **Dữ kiện, điều kiện và giả định đang sử dụng.**
3. **Căn cứ pháp lý cho từng nhận định.**
4. **Ngoại lệ hoặc thông tin có thể làm thay đổi kết quả.**
5. **Tối đa ba bước tiếp theo và trạng thái kiểm chứng.**

Không hiển thị phần trăm tự tin do model tự khai. Chỉ hiển thị trạng thái nguồn, dữ kiện và verifier.

---

## 4. Kiến trúc hệ thống

```text
Nguồn chính thức trung ương + địa phương
        ↓
Source Registry + Incremental Sync
        ↓
Raw Immutable Store
        ↓
Parser / Normalizer / Temporal Versioning
        ↓
Kho pháp luật chuẩn hóa
- Document index
- Provision index
- Legal relation table
- Coverage manifest
        ↓
MCP Gateway dạng read-only
        ↓
Query Router + Retrieval Planner
        ↓
Exact Search + BM25 + Dense Retrieval + Reranker
        ↓
Applicability Filter theo thời gian, lãnh thổ, chủ thể
        ↓
Evidence Bundle có source/version ID
        ↓
Generator chiến thắng bake-off 1.7B–4B, bản Q4/Q5
        ↓
Claim–Citation Verifier + Citation Renderer
        ↓
Trả lời / hỏi lại / yêu cầu chuyên gia
```

Nguyên tắc tránh hệ thống phình to:

- Không tạo model hoặc MCP server riêng cho từng bộ/ngành.
- Cơ quan ban hành và địa phương là metadata, không phải một model mới.
- Dùng một global index có partition/shard và metadata filter.
- Graph chỉ lưu quan hệ kiểm chứng được và mở rộng tối đa một hop.
- Evidence context bị giới hạn; không nhét hàng chục văn bản vào model.

---

## 5. Kho dữ liệu và temporal legal store

### 5.1. Schema tối thiểu

```text
canonical_document_id
document_version_id
provision_id
provision_version_id
document_number
document_type
issuer
authority_level
jurisdiction_path
domain_tags
applies_to
chapter / article / clause / point
text
promulgated_at
effective_from
effective_to
observed_from
observed_to
status
official_url
source_tier
content_hash
parse_quality
```

Kho dữ liệu phải append-only: văn bản mới không ghi đè phiên bản cũ.

- `valid_time`: quy định có hiệu lực trong thực tế khi nào.
- `system_time`: hệ thống đã thu thập và xác minh phiên bản đó khi nào.

### 5.2. Bốn kho dữ liệu và ba mức chất lượng

Không đổ toàn bộ dữ liệu công ty vào một lần train. Mỗi tài sản phải được gán đúng mục đích:

| Kho | Nội dung | Cách dùng |
|---|---|---|
| Knowledge corpus | Toàn văn luật, metadata, phiên bản, quan hệ sửa đổi/thay thế | Temporal RAG/MCP; là nguồn tri thức chính |
| CPT corpus | Văn bản pháp lý dài, đã làm sạch và khử trùng lặp | Pilot DAPT/CPT; không mặc định phải dùng |
| Behavior/SFT corpus | QA, tình huống, Case Card, tool call, claim–evidence, hỏi lại/từ chối | Dạy hành vi làm việc có căn cứ |
| Evaluation corpus | Ca kiểm thử kín, chia theo lĩnh vực, thời gian và rủi ro | Chỉ đánh giá; tuyệt đối không train |

Trong từng kho, dùng nhãn chất lượng:

| Tầng | Ý nghĩa |
|---|---|
| Bronze | Dữ liệu thô có provenance |
| Silver | Đã chuẩn hóa hoặc tổng hợp, vượt kiểm tra tự động |
| Gold | Được người có chuyên môn rà soát |

Xây một **Gold Core** nhỏ nhưng đáng tin cậy cho SFT cuối và đánh giá. Teacher output không bao giờ tự động trở thành Gold. Gold dùng cho train phải tách hoàn toàn khỏi Gold test.

### 5.3. Pipeline cập nhật

```text
Detect → Download → Hash → Parse → Normalize
→ Extract metadata → Link versions → Validate
→ Index → Verify → Activate
```

Văn bản mới chỉ được kích hoạt sau khi vượt kiểm tra schema, nguồn và metadata. Khi một phiên bản thay đổi, dependency graph đánh dấu các câu trả lời cache bị ảnh hưởng để kiểm tra lại.

---

## 6. Retrieval và MCP

### 6.1. Retrieval toàn lĩnh vực

1. Exact lookup nếu câu hỏi nêu số hiệu hoặc Điều/Khoản.
2. Tìm ứng viên ở document index.
3. Tìm Điều/Khoản/Điểm ở provision index.
4. Kết hợp BM25 và dense retrieval bằng rank fusion.
5. Rerank một tập ứng viên nhỏ.
6. Lọc theo hiệu lực, lãnh thổ, chủ thể và loại văn bản.
7. Mở rộng tối đa một hop theo quan hệ pháp lý.
8. Chỉ đưa khoảng 6–10 đoạn cần thiết vào generator.

Văn bản được chunk theo cấu trúc:

```text
Văn bản → Chương → Điều → Khoản → Điểm
```

Không cắt cố định theo số token làm mất cấu trúc pháp lý.

#### Reranker chốt tạm thời

Reranker không phải generator hay legal judge. Nó là model relevance nhỏ, nhận đồng thời `query + passage` và xuất một điểm dùng để sắp xếp lại tập candidate.

| Vai trò | Model | Quyết định |
|---|---|---|
| Dense retriever | `BAAI/bge-m3` | Tìm nhanh trên toàn kho |
| Reranker chính | `BAAI/bge-reranker-v2-m3` | Cross-encoder khoảng 568M, multilingual, Apache-2.0 |
| Challenger | `Qwen/Qwen3-Reranker-0.6B` | Instruction-aware, Apache-2.0; benchmark cùng BGE vì có thể chậm hơn |

Luồng khởi đầu:

```text
Metadata/time/authority filter
→ BM25 + BGE-M3
→ rank fusion, deduplicate, top 50
→ reranker
→ top 5–8 evidence cho generator
```

Exact lookup cho số hiệu hoặc Điều/Khoản được bảo vệ khỏi việc bị reranker loại bỏ. Reranker chỉ chấm semantic relevance; hiệu lực, thẩm quyền và phạm vi áp dụng vẫn do filter/verifier kiểm soát.

Fine-tune sau khi có zero-shot baseline bằng dữ liệu `query + positive passage + hard negatives`. Hard negatives ưu tiên:

- Điều gần nghĩa nhưng không hỗ trợ kết luận.
- Phiên bản cũ hoặc chưa có hiệu lực.
- Cùng số Điều thuộc văn bản khác.
- Sai đối tượng, địa phương hoặc thẩm quyền.
- Luật chung trong ca phải ưu tiên luật chuyên ngành.

Chạy bake-off trên cùng candidate pool: không reranker, BGE zero-shot, BGE fine-tuned, Qwen3-Reranker-0.6B zero-shot/LoRA. Đo `nDCG@10`, `MRR@10`, `Recall/F2@5`, `correct-version@k`, worst-domain và latency P50/P95.

### 6.2. Quan hệ pháp lý tối thiểu

```text
AMENDS
REPEALS
REPLACES
GUIDES
IMPLEMENTS
CITES
CONSOLIDATES
```

Quan hệ do LLM suy ra phải mang nhãn `unverified` và không được dùng làm căn cứ cuối cùng trước khi đối chiếu.

### 6.3. MCP tools thống nhất

```text
search_legal_provisions(
  query, valid_at, known_at, territories,
  issuers, document_types, top_k
)

get_provision_bundle(
  provision_version_ids, include_parent, include_neighbors
)

check_applicability(
  provision_version_ids, valid_at, territory, actors
)

trace_legal_changes(
  document_or_provision_id, relation_types, max_hops=1
)

get_corpus_status(
  authority, territory, collection
)
```

Mỗi evidence trả về:

```text
evidence_id
version_id
exact_text
official_url
validity
jurisdiction
observed_at
snapshot_id
freshness_status
source_health
```

MCP chỉ là giao thức gọi công cụ. Tính cập nhật đến từ sync pipeline, versioning và live verification. Khi nguồn lỗi hoặc snapshot quá cũ, hệ thống hạ trạng thái xuống `not_currently_verified`.

---

## 7. Model và kế hoạch huấn luyện

### 7.1. Trần production

```text
Production generator: 1.7B–4B, chỉ một model dense
Teacher khi phát triển: có thể 8B–32B
Runtime: local, không phụ thuộc cloud LLM để sinh câu trả lời
```

Phạm vi luật rộng làm index lớn hơn, không bắt buộc generator lớn hơn. Model chỉ cần hiểu câu hỏi, lập kế hoạch retrieval, gọi tool, tổng hợp evidence và trả lời có kiểm chứng.

### 7.2. Ba ứng viên phát triển song song

| Nhánh | Quy trình | Mục tiêu |
|---|---|---|
| A – baseline chính | `Qwen3-4B-Instruct-2507 → mixed grounded SFT/QLoRA` | Có hệ thống chạy sớm, instruction/tool calling ổn định |
| B – challenger siêu nhẹ | `ViLegalQwen3-1.7B-Base → mixed grounded SFT/QLoRA` | Kiểm tra mức chất lượng có thể đạt với footprint nhỏ hơn |
| C – tận dụng GPU công ty | `Qwen3-4B-Base → Legal DAPT/CPT + general replay → mixed SFT` | Kiểm chứng giá trị thật của continued pretraining |

`VLSP2025-LegalSML/qwen3-4b-legal-pretrain` chỉ là benchmark bổ sung cho tới khi giấy phép sử dụng ngoài nghiên cứu được xác nhận.

Chọn model theo Pareto giữa Grounded Joint Accuracy, worst-domain, correct-version, latency và footprint. Chỉ chọn nhánh C nếu nó thắng A rõ ràng trên test khóa. Continued pretraining không mặc định tốt hơn Instruct.

### 7.3. Sử dụng tài nguyên công ty

Nên dùng GPU công ty để:

- Chạy bake-off các checkpoint 1.7B–4B trên cùng pipeline.
- Full-parameter DAPT/CPT cho nhánh B nếu đủ tài nguyên.
- Sinh dữ liệu nháp bằng teacher 8B/14B/32B.
- Distill hành vi và cấu trúc trả lời về student chiến thắng bake-off.
- Huấn luyện retriever, reranker hoặc NLI verifier nhỏ.
- Chạy nhiều cấu hình QLoRA và benchmark song song.
- Tạo hard-negative theo thời gian, lãnh thổ và văn bản gần giống.

Không dùng GPU công ty để biện minh cho model production lớn hơn.

Thông tin cần lấy từ công ty trước khi lên cấu hình train:

```text
Loại GPU, VRAM và số lượng GPU
Thời lượng/quota được sử dụng
Dung lượng lưu trữ và tốc độ I/O
Có Internet hay môi trường air-gapped
Framework/runtime được phép
Nguồn dữ liệu và quyền sử dụng
Thiết bị production mục tiêu
SLA latency và số người dùng đồng thời
```

### 7.4. Pipeline huấn luyện

#### Giai đoạn A – Baseline trước khi train lớn

Chạy cả `Qwen3-4B-Instruct-2507` và `ViLegalQwen3-1.7B` với cùng RAG, prompt và structured output để xác định lỗi đến từ model, retrieval, tool calling hay dữ liệu. Không chạy CPT lớn trước khi biết bottleneck.

#### Giai đoạn B – Legal DAPT/CPT

Thực hiện trên bản Base, sau đó mới SFT. Mục tiêu là học:

- Ngôn ngữ và cấu trúc pháp quy Việt Nam.
- Điều → Khoản → Điểm và tham chiếu chéo.
- Quan hệ sửa đổi, thay thế, bãi bỏ.
- Điều kiện, ngoại lệ và phạm vi áp dụng.
- Văn phong của nhiều lĩnh vực pháp lý.

Giữ một phần dữ liệu tiếng Việt tổng quát chất lượng cao để hạn chế catastrophic forgetting. Bắt đầu bằng pilot nhỏ; chỉ mở rộng khi downstream evaluation cùng cải thiện.

#### Giai đoạn C – Broad SFT và grounded SFT

Dữ liệu phải phủ:

- Domain routing và issue spotting đa nhãn.
- Case Card, ngày, chủ thể, địa phương và dữ kiện thiếu.
- Tạo truy vấn và gọi MCP đúng schema.
- Trả lời dựa trên evidence và gắn claim–citation.
- Hiệu lực theo thời gian và tình huống trước/sau sửa đổi.
- Thiếu nguồn, xung đột, từ chối và adversarial input.
- Câu hỏi giao thoa hai hoặc nhiều lĩnh vực.
- Evidence đúng nhưng có đoạn thừa hoặc nhiễu.
- Điều luật gần nghĩa nhưng sai thời điểm, sai thẩm quyền hoặc không áp dụng.
- Phiên bản cũ và mới cùng xuất hiện.
- Trường hợp không có đáp án trong evidence.

Không sampling theo tần suất thô vì lĩnh vực nhiều văn bản sẽ lấn át lĩnh vực ít dữ liệu. Cần quota tối thiểu và sampling cân bằng theo lĩnh vực, cấp ban hành, loại văn bản, địa phương, tác vụ và rủi ro.

Chạy broad multi-task SFT trước, sau đó grounded SFT. Thử các tỉ lệ legal/general với cùng token budget; không mặc định legal-only. Hard negative ưu tiên điều luật gần nghĩa, cùng số điều ở văn bản khác và phiên bản đã hết hiệu lực.

#### Giai đoạn D – Gold polishing và distillation

Kết thúc SFT bằng một vòng **gold polishing** trên tập nhỏ đã được chuyên gia duyệt, đồng thời replay một phần dữ liệu giai đoạn trước để tránh quên kỹ năng. Distillation là tùy chọn và chỉ dùng dữ liệu đã kiểm chứng.

Teacher lớn chỉ nhận evidence đã xác minh và sinh:

```text
domains
Case Card
missing facts
tool-call plan
claims + evidence IDs
answer status
short answer
```

Mỗi mẫu teacher phải qua kiểm tra JSON, ID nguồn, ngày hiệu lực, số liệu, verifier ngữ nghĩa và human sampling. Chỉ distill chuỗi có thể kiểm chứng như:

```text
fact → rule → provision → conclusion
```

Không distill chain-of-thought dài hoặc kiến thức pháp lý không có nguồn.

#### Giai đoạn E – Chọn QLoRA hay full fine-tuning

- DAPT/CPT: thử full-parameter nếu cụm GPU cho phép.
- SFT vòng lặp: ưu tiên QLoRA để thử nhanh.
- SFT cuối: chỉ so sánh full fine-tuning nếu có lý do và ngân sách.
- Không tạo adapter riêng cho từng bộ/ngành trong phiên bản đầu.

---

## 8. Lượng tử hóa và tiêu chí lightweight

### 8.1. Quy trình

```text
Base hoặc DAPT model
→ SFT/LoRA
→ Merge adapter
→ Lưu master BF16
→ Quantize cho runtime
→ Benchmark lại toàn bộ
```

Xuất tối thiểu:

- BF16: mốc chất lượng.
- Q5_K_M hoặc INT8: phương án an toàn.
- Q4_K_M: ứng viên CPU/GGUF.
- AWQ/GPTQ INT4: ứng viên GPU nếu runtime hỗ trợ.

`load_in_4bit` khi QLoRA chỉ giúp tiết kiệm VRAM lúc train; nó chưa phải artifact production cuối.

Calibration set phải phủ nhiều lĩnh vực và chứa tiếng Việt có dấu, bảng, số hiệu, ngày tháng, mức tiền, tỷ lệ và trích dẫn.

### 8.2. Lightweight gate

Các ngưỡng dưới đây là mục tiêu ban đầu, sẽ hiệu chỉnh sau baseline:

```text
Generator: không quá 4B
Artifact Q4/Q5: ưu tiên không quá 5 GB
Peak VRAM generator: ưu tiên không quá 8 GB tại context vận hành
Không dùng cloud LLM để sinh câu trả lời production
Q4 giảm macro correctness không quá 2 điểm phần trăm so với BF16
Không làm tăng critical error hoặc citation hallucination
```

Phải báo cáo hai lớp:

- **Model footprint:** file, VRAM, TTFT, token/giây.
- **End-to-end footprint:** model, embedding, reranker, vector DB, MCP, KV cache và latency tổng.

Nếu Q4 không đạt quality gate thì dùng Q5. Lightweight không có nghĩa chọn bản nhỏ nhất bất chấp độ đúng.

RTX 5060 Ti 16 GB tại nhóm được dùng làm máy tham chiếu cho inference, regression và QLoRA nhỏ. GPU công ty dùng cho train nặng; model cuối vẫn phải chạy được trên máy tham chiếu.

---

## 9. Structured output, verifier và an toàn

### 9.1. Output nội bộ

```json
{
  "query_envelope": {},
  "missing_facts": [],
  "tool_calls": [],
  "claims": [
    {
      "text": "Nhận định pháp lý",
      "evidence_ids": ["S1"],
      "verification": "pending"
    }
  ],
  "exceptions": [],
  "next_actions": [],
  "answer_status": "pending_verification"
}
```

JSON Schema hoặc grammar-constrained decoding bảo đảm cú pháp. Backend ánh xạ `S1` sang URL, số hiệu, phiên bản và đoạn nguồn thật; model không tự viết URL.

### 9.2. Verifier tầng 1 – xác định bằng code

- Evidence ID và Điều/Khoản có tồn tại.
- Nguồn thuộc allowlist.
- Văn bản có hiệu lực tại `valid_at`.
- Lãnh thổ, chủ thể và authority level phù hợp.
- Ngày, số tiền, tỷ lệ hoặc thời hạn quan trọng có nguồn hỗ trợ.
- Không trộn bản cũ và bản mới mà không cảnh báo.

### 9.3. Verifier tầng 2 – kiểm tra ngữ nghĩa

NLI classifier nhỏ kiểm tra từng cặp `claim ↔ evidence`:

```text
SUPPORTED
CONTRADICTED
INSUFFICIENT_EVIDENCE
```

Nếu một claim không đạt:

1. Sinh lại tối đa một lần.
2. Nếu vẫn không đạt, bỏ claim hoặc chuyển trạng thái sang hỏi lại/chuyên gia.

Reranker và verifier không dùng chung nhiệm vụ:

```text
Reranker trước generation:
"Passage này có liên quan đến query không?"

Verifier sau generation:
"Passage này có thực sự hỗ trợ claim đã viết không?"
```

Có thể dùng backbone gần nhau trong thí nghiệm, nhưng phải train và đánh giá bằng hai nhãn, hai dataset và hai quality gate riêng.

### 9.4. Critical errors

Một ca bị đánh trượt ngay nếu:

- Bịa văn bản, Điều/Khoản hoặc URL.
- Dùng văn bản sai hiệu lực mà không cảnh báo.
- Kết luận chắc chắn khi evidence thiếu hoặc mâu thuẫn.
- Đề xuất hành động có nguy cơ gây hậu quả pháp lý nghiêm trọng mà không chuyển chuyên gia.
- Làm lộ dữ liệu nhạy cảm.

Prompt injection trong tài liệu luôn được coi là dữ liệu, không phải instruction.

---

## 10. Kế hoạch đánh giá toàn lĩnh vực

### 10.1. Ma trận test

```text
Lĩnh vực
× loại tác vụ
× độ khó
× trạng thái thời gian
× cấp ban hành/địa phương
× mức độ rủi ro
```

Không cần phủ toàn bộ tích tổ hợp. Mỗi lĩnh vực cấp cao tối thiểu phải có:

- Một ca tra cứu trực tiếp.
- Một ca phân tích tình huống.
- Một cặp trước/sau thay đổi luật.
- Một ca thiếu bằng chứng hoặc cần hỏi lại.
- Một ca adversarial.

Bộ test tự động nên có quy mô đủ lớn để phủ mọi lĩnh vực trong Coverage Contract. Gold set chuyên gia được lấy mẫu phân tầng, tăng trọng số cho các lĩnh vực rủi ro cao. Quy mô cuối cùng phụ thuộc số lĩnh vực và nguồn lực chuyên gia do công ty cung cấp.

### 10.2. Ablation bắt buộc

| Cấu hình | Mục đích |
|---|---|
| Model closed-book | Đo kiến thức tham số; không dùng làm chất lượng sản phẩm |
| Model + oracle/gold evidence | Tách lỗi reasoning khỏi lỗi retrieval |
| Model + retrieval thật | Đo pipeline RAG end-to-end |
| Retrieval + temporal filter + verifier | Đo giá trị của hệ thống an toàn đầy đủ |
| ViLegalQwen3-1.7B so với Qwen3-4B | Chọn Pareto chất lượng/footprint |
| Instruct + QLoRA so với Base + DAPT + SFT | Đo giá trị thật của CPT |
| Không/có breadcrumb, reranker và hard negative | Quy lỗi từng thành phần retrieval |
| BGE reranker so với Qwen3-Reranker-0.6B | Chọn Pareto retrieval quality/latency |
| BF16 so với Q5/Q4 | Đo suy giảm do lượng tử hóa |

### 10.3. Metrics

Mỗi metric phải báo cáo:

```text
Micro
Macro theo lĩnh vực
Worst-domain
P10-domain
```

Các metric chính:

- Router Macro-F1 và multi-label exact match.
- Retrieval Recall@5/10 và complete-evidence recall.
- Đúng phiên bản, hiệu lực, lãnh thổ và thẩm quyền.
- Tool selection và argument exact match.
- JSON/schema validity.
- Citation existence, entailment và claim coverage.
- Độ đúng kết luận, điều kiện và ngoại lệ.
- Abstention precision/recall tại một coverage cố định.
- Unsupported material claim rate.
- Freshness latency.
- Model size, RAM/VRAM, TTFT, token/giây và P95 latency.
- Mức suy giảm từng metric sau lượng tử hóa.

KPI tổng hợp trung tâm:

```text
Grounded Joint Accuracy =
kết luận đúng
AND mọi claim trọng yếu được evidence hỗ trợ
AND căn cứ đúng phiên bản, hiệu lực, thẩm quyền và phạm vi áp dụng
```

Không gộp mọi hành vi an toàn thành một nhãn từ chối. Theo dõi riêng:

```text
ASK_CLARIFICATION
INSUFFICIENT_EVIDENCE
CONFLICT_DETECTED
HIGH_RISK_ESCALATION
ANSWER_VERIFIED
```

Micro score không được dùng một mình vì lĩnh vực nhiều dữ liệu có thể che lỗi ở lĩnh vực ít dữ liệu. Nếu một lĩnh vực không đạt quality gate, hệ thống tự hạ xuống `LOOKUP_VERIFIED` thay vì che giấu bằng điểm trung bình.

### 10.4. Temporal T0/T1 test

1. Khóa dữ liệu train và trọng số tại `T0`.
2. Giữ kín một tập văn bản ban hành hoặc thay đổi sau `T0`.
3. Tại `T1`, chỉ bổ sung chúng vào MCP/RAG.
4. Kiểm thử cùng câu hỏi khi MCP bật và tắt.
5. Không fine-tune lại model.

Phải kiểm tra luật mới, sửa đổi một phần, thay thế, bãi bỏ, chưa có hiệu lực, điều khoản chuyển tiếp và cùng tình huống ở hai phía ngày hiệu lực.

Đo chuỗi thời gian:

```text
published_at
→ detected_at
→ indexed_at
→ verified_at
→ first_correct_answer_at
```

Train/test phải tách theo document family và thời gian, không random đơn thuần.

---

## 11. Lộ trình theo cổng nghiệm thu

### Giai đoạn 0 – Xác nhận đầu vào công ty

- Lấy thông số tài nguyên train và production.
- Chốt Coverage Contract.
- Chốt nguồn, license và phạm vi trung ương/địa phương.
- Chốt SLA và định nghĩa “lightweight”.

**Gate:** có inventory nguồn, quyền sử dụng và target hardware rõ ràng.

### Giai đoạn 1 – Corpus và temporal index

- Xây Source Registry và raw immutable store.
- Parse theo Văn bản → Chương → Điều → Khoản → Điểm.
- Xây versioning, validity và quan hệ sửa đổi tối thiểu.
- Tạo coverage dashboard.

**Gate:** có thể kiểm đếm độ phủ; lỗi parse không bị bỏ qua âm thầm.

### Giai đoạn 2 – Evaluation-first baseline

- Tạo taxonomy và tập test khóa trước khi train lớn.
- Chạy Instruct + structured RAG baseline.
- Đo macro/worst-domain để tìm bottleneck.

**Gate:** retrieval và temporal selection đạt ngưỡng cơ sở trước khi đầu tư CPT.

### Giai đoạn 3 – Model 1.7B–4B toàn lĩnh vực

- QLoRA nhánh Instruct.
- Pilot DAPT trên nhánh Base.
- Distill dữ liệu đã kiểm chứng từ teacher.
- So sánh hai nhánh trên cùng test khóa.

**Gate:** model được chọn phải thắng baseline và không tạo thêm critical error.

### Giai đoạn 4 – MCP, verifier và freshness

- Hoàn thiện MCP read-only tools.
- Tích hợp constrained decoding.
- Xây verifier xác định và NLI verifier.
- Vô hiệu hóa cache khi luật đổi.

**Gate:** vượt T0/T1 test và fail closed khi nguồn không xác minh được.

### Giai đoạn 5 – Quantization và pilot

- Xuất BF16, Q5 và Q4.
- Benchmark trên RTX 5060 Ti 16 GB và thiết bị production của công ty.
- Expert blind review theo mẫu phân tầng.
- Security, prompt-injection và PII test.

**Gate:** vượt quality, safety và lightweight gate.

### Giai đoạn 6 – Mở rộng độ sâu

- Tất cả lĩnh vực trước hết đạt `INDEXED` và `LOOKUP_VERIFIED`.
- Lần lượt nâng lĩnh vực lên `ANSWER_TESTED` và `ADVISORY_ENABLED` dựa trên benchmark.
- Không chia thành nhiều model; chỉ thêm dữ liệu, config, synonym, risk rule và test theo lĩnh vực.

---

## 12. Demo và deliverables

### 12.1. Demo cuối

Demo phải chứng minh cả độ rộng và chiều sâu:

1. Hỏi ba tình huống thuộc ba lĩnh vực khác nhau.
2. Hỏi một tình huống giao thoa nhiều lĩnh vực.
3. Cho hệ thống phát hiện ngày hoặc địa phương còn thiếu.
4. Mở evidence graph `fact → rule → provision → conclusion`.
5. Đổi ngày sự việc để nguồn hoặc kết luận thay đổi.
6. Thêm một văn bản sau `T0` qua MCP; model trả lời đúng mà không train lại.
7. Tắt MCP; model hạ trạng thái thay vì bịa.
8. Hiển thị coverage dashboard và bảng BF16/Q5/Q4.

### 12.2. Deliverables

- Model 1.7B–4B chiến thắng bake-off, gồm master và bản deploy Q4/Q5.
- Model card, data card và báo cáo license.
- Source Registry, Coverage Contract và coverage dashboard.
- Raw/normalized legal corpus có provenance và versioning.
- Document index, provision index và relation table.
- MCP server read-only.
- Router, retriever, reranker và verifier.
- Bộ test toàn lĩnh vực và gold set được rà soát.
- Báo cáo ablation, macro/worst-domain, quantization và hiệu năng.
- Demo UI/video và hướng dẫn triển khai.

---

## 13. Rủi ro và phần không làm

| Rủi ro | Kiểm soát |
|---|---|
| “Toàn bộ” nhưng thiếu nguồn | Coverage Contract, manifest và dashboard |
| Ngành nhiều dữ liệu lấn át ngành nhỏ | Balanced sampling, macro và worst-domain gate |
| DAPT làm giảm instruction following | Train từ Base rồi SFT; luôn so với nhánh Instruct |
| Teacher hallucination | Evidence-only generation, verifier và human sampling |
| Model nhớ luật cũ chống lại evidence mới | Evidence-first, bắt buộc citation và temporal RAG |
| Trộn bản cũ/mới | Bitemporal store và applicability filter |
| Citation bịa | Backend quản lý source ID, model không viết URL |
| Legal-pretrain ngoài không rõ license | Chỉ benchmark đến khi được phép |
| Q4 làm sai số/ngày/Điều | Calibration đa lĩnh vực; fallback Q5 |
| Model nhẹ nhưng stack nặng | Đo cả model và end-to-end footprint |
| Có GPU nên thí nghiệm quá lớn | Mỗi giai đoạn có go/no-go gate |
| Câu hỏi giao thoa lĩnh vực | Router multi-label và global retrieval fallback |

Không làm trong phiên bản đầu:

- Model/adapter riêng cho từng bộ hoặc tỉnh.
- Knowledge graph khái niệm toàn diện.
- Multi-agent debate.
- Tự giải quyết xung đột pháp lý cần diễn giải chuyên sâu.
- Dự đoán kết quả tranh chấp.
- Tự nộp hồ sơ hoặc thực hiện thủ tục thay người dùng.
- What-if UI phức tạp trước khi retrieval toàn corpus đạt chuẩn.

---

## 14. Việc cần làm ngay

1. Nhận inventory/dataset và lập `Data Readiness Report`: provenance, license, schema, độ phủ, trùng lặp, PII, phiên bản và evidence span.
2. Xin công ty danh sách GPU, VRAM, quota, storage và môi trường chạy.
3. Hỏi rõ phạm vi có gồm văn bản địa phương, án lệ, thủ tục và bản án hay không.
4. Chốt target hardware/SLA production để khóa tiêu chí lightweight.
5. Tạo Coverage Contract, taxonomy lĩnh vực và private evaluation set trước khi train.
6. Dựng DRiLL-style baseline: hierarchical breadcrumb + BM25/BGE-M3 + reranker/hard negatives.
7. Chạy cùng pipeline với `ViLegalQwen3-1.7B` và `Qwen3-4B-Instruct-2507`.
8. Chỉ sau khi biết bottleneck mới quyết định CPT, distillation, full fine-tuning và quy mô synthetic data.

### Tài liệu tham khảo chính

- [Qwen3-4B-Instruct-2507](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507)
- [Qwen3-4B-Base](https://huggingface.co/Qwen/Qwen3-4B-Base)
- [ViLegalLM – Vietnamese Legal Models and Corpus](https://aclanthology.org/2026.findings-acl.1801/)
- [LawInstruct](https://aclanthology.org/2025.findings-naacl.7/)
- [Lawyer LLaMA](https://arxiv.org/abs/2305.15062)
- [MinLegal tại VLSP 2025](https://aclanthology.org/2025.vlsp-1.24.pdf)
- [DRiLL – Vietnamese Legal Retrieval](https://aclanthology.org/2025.vlsp-1.20.pdf)
- [BGE-reranker-v2-m3](https://huggingface.co/BAAI/bge-reranker-v2-m3)
- [FlagEmbedding – Fine-tune Reranker](https://github.com/FlagOpen/FlagEmbedding/blob/master/examples/finetune/reranker/README.md)
- [Qwen3-Reranker-0.6B](https://huggingface.co/Qwen/Qwen3-Reranker-0.6B)
- [Qwen3 Embedding/Reranker – Training with SWIFT](https://github.com/QwenLM/Qwen3-Embedding/blob/main/docs/training/SWIFT.md)
- [LegalBench-RAG](https://arxiv.org/abs/2408.10343)
- [Temporal Misgrounding in Legal RAG](https://arxiv.org/abs/2608.09393)
- [PLawBench](https://aclanthology.org/2026.acl-long.458/)
- [Hallucination-Free? Assessing Legal RAG Tools](https://nlp.stanford.edu/~manning/papers/Magesh-Hallucination%E2%80%90Free-2025.pdf)
- [VLSP 2025 LegalSLM](https://vlsp.org.vn/node/184)
- [VLSP qwen3-4b-legal-pretrain](https://huggingface.co/VLSP2025-LegalSML/qwen3-4b-legal-pretrain)
- [VLegal-Bench](https://arxiv.org/abs/2512.14554)
- [VLQA](https://arxiv.org/abs/2507.19995)
- [ALQAC](https://alqac.github.io/)
- [Cơ sở dữ liệu quốc gia về văn bản pháp luật](https://vbpl.vn/)
- [Model Context Protocol](https://modelcontextprotocol.io/specification/)
- [Hugging Face PEFT – Quantization](https://huggingface.co/docs/peft/developer_guides/quantization)
- [Hugging Face Transformers – Quantization](https://huggingface.co/docs/transformers/main_classes/quantization)

### Câu pitch

> **Một hệ thống pháp lý lightweight dùng generator 1.7B–4B, được huấn luyện bằng tài nguyên lớn nhưng triển khai cục bộ, có thể giải đáp trên kho pháp luật Việt Nam toàn lĩnh vực bằng đúng quy phạm, đúng phiên bản, đúng thẩm quyền và bằng chứng kiểm chứng được.**
