# Giai đoạn 3 – Dữ liệu công ty, RAG thật và Qwen local lightweight

## Báo cáo cập nhật

| Trường | Nội dung |
|---|---|
| Cập nhật gần nhất | 09/09/2026 |
| Phiên bản | `v1.1` |
| Trạng thái | `G3_C1_TOOLING_READY_HUMAN_REVIEW_REQUIRED` |
| Baseline | `main`, tag `g2-v1.0.0` |
| Nhánh tích hợp | `g3/integration` |
| Model baseline đề xuất | `Qwen/Qwen3-1.7B`, local, non-thinking |
| Quyết định fine-tune | `NOT_YET_JUSTIFIED` |
| Dữ liệu | `D2_COMPANY_REAL`, không đưa lên GitHub |

Đọc trước: [audit dataset công ty](01-audit-dataset-cong-ty.md),
[data contract Tú–Minh](02-contract-data-g3.md),
[contract G2](../contracts-g2.md) và
[chiến lược trung tâm](../00-chien-luoc-trien-khai-tu-nho-den-lon.md).

---

# PHẦN I – TỔNG

## 1. Quyết định chiến lược

Không dùng chuỗi:

```text
Excel → fine-tune Qwen → chatbot
```

Chuỗi G3 đúng là:

```text
Excel raw bất biến, private
→ deterministic preprocessing + PII removal
→ human conflict/source review
→ normalized ProcedureRecord/Fragment version hóa
→ RAG baseline trên record APPROVED
→ gold DEV/TEST đóng băng
→ Qwen3-1.7B local zero-shot
→ đánh giá data / retrieval / generation / runtime riêng
→ chỉ QLoRA nếu generation là bottleneck
→ quantize và benchmark artifact cuối
```

Lý do: kiến thức như giấy tờ, phí, thời gian và cơ quan tiếp nhận có thể thay đổi.
Các dữ kiện đó phải nằm trong RAG để cập nhật và truy vết, không nên được “nhồi”
vào trọng số model. Fine-tune, nếu có, chỉ dạy **hành vi**: đọc evidence, hỏi lại,
từ chối khi thiếu nguồn, xuất JSON và gắn citation đúng.

## 2. Chốt model

### 2.1. Baseline chính

Chọn `Qwen/Qwen3-1.7B` trước, không tìm một checkpoint “2B” mơ hồ. Model card
chính thức ghi 1,7B tham số, 28 lớp và context 32.768 token; Hugging Face có thể
hiển thị kích thước làm tròn là 2B. Qwen3 hỗ trợ thinking/non-thinking trong cùng
model. Với chatbot thủ tục, mặc định **non-thinking** để giảm latency và tránh
phần suy luận dài không cần thiết.

Nguồn chính thức:

- [Qwen3-1.7B model card](https://huggingface.co/Qwen/Qwen3-1.7B)
- [Qwen3 repository và hướng dẫn local](https://github.com/QwenLM/Qwen3)
- [Qwen3 llama.cpp guide](https://github.com/QwenLM/Qwen3/blob/main/docs/source/run_locally/llama.cpp.md)

### 2.2. Runtime

G3 dùng `llama.cpp` server làm runtime chuẩn cho máy dev:

- hỗ trợ Windows/NVIDIA CUDA và GGUF quantization;
- footprint nhỏ, ít phụ thuộc;
- có OpenAI-compatible endpoint local;
- AI Service chỉ cần thêm `LocalGroundedProvider`, Backend/Web không đổi contract.

Ollama có thể dùng để thử tay, nhưng kết quả nghiệm thu phải khóa rõ model digest,
GGUF quant, context và tham số. Trên server Linux nhiều người dùng, có thể benchmark
vLLM sau; không đổi provider contract chỉ để thay runtime.

### 2.3. Precision/quantization ladder

Chạy cùng TEST set theo thứ tự:

1. BF16/FP16 hoặc Q8 làm quality reference nếu môi trường chạy được.
2. Q5_K_M.
3. Q4_K_M làm ứng viên lightweight chính.

Qwen hướng dẫn GGUF có các preset Q8_0, Q5_K_M và Q4_K_M, đồng thời cảnh báo
quantization thấp có thể giảm độ chính xác; vì vậy không chọn Q4 chỉ dựa trên dung
lượng file. Xem [hướng dẫn quantization chính thức](https://github.com/QwenLM/Qwen3/blob/main/docs/source/quantization/llama.cpp.md).

### 2.4. Khả năng trên RTX 5060 Ti 16 GB

Máy đã được xác nhận có RTX 5060 Ti 16 GB. Ước tính trước benchmark:

- 1,7B BF16 riêng trọng số khoảng 3,4 GB;
- Q4 riêng trọng số xấp xỉ 1 GB, cộng runtime/KV cache;
- inference context 4K–8K có dư địa tốt trên 16 GB;
- QLoRA 4-bit 1,7B có khả năng chạy với batch nhỏ, gradient checkpointing và
  sequence length được kiểm soát;
- full fine-tune không phải lựa chọn mặc định vì optimizer/gradient làm bộ nhớ
  lớn hơn nhiều trọng số inference.

Đây là ước tính, không phải kết quả nghiệm thu. G3 phải đo peak VRAM, TTFT,
tokens/second và p95 end-to-end trên đúng máy.

## 3. Fine-tune hay không?

### Quyết định hiện tại: chưa fine-tune

42 dòng Excel không phải 42 mẫu SFT. Nó không có cặp instruction/output được
review, có dữ kiện xung đột và thiếu provenance. Fine-tune ngay sẽ làm model học
thuộc dữ liệu chưa xác minh, khó cập nhật và có thể tăng hallucination.

### Chỉ mở QLoRA khi đủ cả bốn điều kiện

1. Data gate và retrieval gate đã đạt.
2. Prompt/schema/constrained output đã được tối ưu nhưng lỗi generation còn đáng kể.
3. Có tập SFT dạy hành vi và tập TEST theo `procedure_id` chưa từng dùng để train.
4. Có baseline trước/sau để chứng minh quality–latency–VRAM tốt hơn.

Nếu cần fine-tune, dùng QLoRA/LoRA trên Hugging Face checkpoint, không train file
GGUF. Hugging Face PEFT khuyến nghị `target_modules="all-linear"` cho kiểu QLoRA;
NF4 là lựa chọn 4-bit dành cho training. Tham khảo
[PEFT LoRA](https://huggingface.co/docs/peft/main/package_reference/lora) và
[Transformers bitsandbytes](https://huggingface.co/docs/transformers/quantization/bitsandbytes).

Sau training mới merge adapter khi cần, rồi export/quantize GGUF cho inference.

---

# PHẦN II – PHÂN

## 4. Checkpoint và gate

### G3-C0 – Governance và scope lock

Output:

- raw workbook fingerprint và storage policy;
- câu trả lời của công ty về quyền dùng/redistribute/hosted/PII;
- chốt 8–10 thủ tục ưu tiên để review nghiệp vụ sâu;
- schema extension và Definition of Done được cả nhóm đọc.

Gate: chưa có quyền thì không đẩy raw/derived content lên Git hoặc API ngoài.

### G3-C1 – Preprocess deterministic

Output private:

```text
data/company_private/<dataset_version>/
├── source_manifest.jsonl
├── normalized/procedures.jsonl
├── normalized/fragments.jsonl
├── quarantine/conflicts.jsonl
├── gold/questions.jsonl
└── reports/data-quality.json
```

Code parser/validator được commit; dữ liệu output tiếp tục ignored. Mỗi record có:

- stable `procedure_id`;
- `source_id`, `dataset_version`, raw row reference và hash;
- title/alias/category/submission method;
- documents, processing time, fee, receiving authority;
- jurisdiction/effective dates hoặc `null` rõ ràng;
- `missing_fields`, `review.status`, reviewer role và last verified time.

Gate:

- email không xuất hiện trong normalized/log/report;
- 42 input row được accounting đủ: approved, pending hoặc quarantined;
- không record rỗng, không reference gãy;
- 4 nhóm duplicate có quyết định con người;
- chạy lại cùng raw phải sinh cùng output/hash.

### G3-C2 – RAG baseline dữ liệu công ty

Trước mắt giữ exact/alias + BM25. Dataset chỉ khoảng 38 thủ tục nên chưa cần vector
DB/reranker nếu baseline chưa chứng minh thiếu recall.

Gate đề xuất:

- chỉ ingest record `APPROVED_FOR_DEMO`;
- procedure routing accuracy ≥ 95% trên TEST;
- Recall@5 ≥ 95%;
- citation binding = 100%;
- query về field thiếu phải abstain/ask, không suy đoán;
- báo cáo từng câu và latency, không chỉ điểm trung bình.

### G3-C3 – Qwen local zero-shot

AI Service gọi local model server, chỉ truyền question + evidence tối thiểu. Không
truyền email, toàn bộ workbook, cookie hoặc history dài.

Cấu hình baseline khởi đầu:

| Biến | Giá trị ban đầu |
|---|---|
| Model | `Qwen/Qwen3-1.7B` |
| Mode | non-thinking |
| Context | 4.096; thử thêm 8.192 nếu cần |
| Evidence | top 3–5 fragment, giới hạn token |
| Output | tối đa 300–500 token |
| Sampling | không greedy; benchmark cấu hình non-thinking theo model card |
| Schema | `GroundedAnswer` hiện có |
| External network | off trong inference |

Gate đề xuất:

- JSON/schema validity ≥ 99%;
- cited IDs hợp lệ = 100%;
- grounded claim precision ≥ 95% trên phần đã human-review;
- clarification/insufficient behavior ≥ 90%;
- không lộ PII hoặc instruction trong evidence;
- peak VRAM < 12 GB để còn headroom;
- p95 end-to-end và TTFT được ghi số thực; mục tiêu thử ban đầu p95 ≤ 3 giây
  cho answer ngắn, sau đó chốt SLA với mentor.

Không dùng các ngưỡng trên để tuyên bố độ đúng pháp lý toàn quốc; chúng là gate
kỹ thuật cho phạm vi đã review.

### G3-C4 – Error analysis và quyết định fine-tune

Gắn mỗi lỗi vào đúng một primary owner:

```text
DATA_MISSING / DATA_CONFLICT / DATA_STALE
ROUTING_ERROR / RETRIEVAL_MISS / RANKING_ERROR
GENERATION_OMISSION / UNSUPPORTED_CLAIM / BAD_JSON / BAD_CITATION
RUNTIME_OOM / TIMEOUT / SLOW_TTFT
```

- Lỗi data → sửa data/review, không fine-tune.
- Lỗi retrieval → sửa index/query/filter, không fine-tune.
- Lỗi schema có thể chặn bằng parser/grammar → sửa constrained output trước.
- Chỉ nhóm generation còn lại mới là bằng chứng cho QLoRA.

### G3-C5 – QLoRA tùy điều kiện

Nếu C4 cho phép:

- tạo dữ liệu OpenAI messages/ShareGPT theo đúng grounded contract;
- split theo `procedure_id`, không random các paraphrase cùng thủ tục;
- TEST đóng băng và người tạo mẫu không tự duyệt kết quả cuối;
- ưu tiên vài trăm mẫu chất lượng cao, gồm answer/clarify/insufficient/injection,
  hơn hàng nghìn mẫu tự sinh không review;
- QLoRA NF4, batch nhỏ, gradient accumulation/checkpointing, cutoff 2K–4K;
- chạy ablation base vs LoRA/QLoRA và Q8/Q5/Q4;
- loại adapter nếu không cải thiện có ý nghĩa hoặc làm tăng unsupported claims.

## 5. Phân công Tú – Data & Gold Owner

Branch: `g3/data-tu`

### Công việc

1. Không sửa file Excel gốc; ghi hash và version.
2. Lập mapping 12 cột Excel → schema chuẩn.
3. Loại email khỏi normalized data; timestamp chỉ giữ ở audit metadata nếu cần.
4. Normalize NFC, khoảng trắng, bullet, category, submission method, fee/time.
5. Lập `conflicts.jsonl` cho 4 nhóm duplicate; hỏi người nghiệp vụ, không tự chọn.
6. Bổ sung source/procedure code/jurisdiction/effective/reviewer hoặc để `null` +
   `PENDING_REVIEW`, không bịa.
7. Chọn 8–10 thủ tục ưu tiên phủ Hộ tịch, Văn hóa–Xã hội, Kinh tế–Hạ tầng và ít
   nhất một lĩnh vực khác.
8. Tạo câu hỏi paraphrase, thiếu dữ kiện, ngoài phạm vi và prompt injection.
9. Tách DEV/TEST theo procedure; đóng băng TEST sau review.
10. Viết data card và báo cáo toàn bộ input row đi đâu.

### Deliverable

- mapping/schema note;
- private normalized dataset + manifest/hash;
- conflict/review register;
- gold DEV/TEST có reviewer;
- data-quality report không chứa email/nội dung không được công bố.

### Definition of Done

- PII scan sạch;
- deterministic build;
- 42/42 row accounted;
- duplicate resolution có chữ ký/vai trò reviewer;
- mọi gold answer point trỏ được về fragment/source;
- không đưa raw hoặc derived company content vào commit/AI chat.

### Context giao AI agent cho Tú

```text
Đọc docs/giai-doan-3/01-audit-dataset-cong-ty.md và file phân công này. Chỉ viết
code parser/validator; raw và output company phải nằm ở path ignored. Không in,
log hoặc commit email. Không dùng LLM/API ngoài để sửa dữ kiện. Chuẩn hóa phải
deterministic và tạo quarantine cho conflict/missing provenance. Không tự chuyển
PENDING thành APPROVED. Trước khi kết thúc, chứng minh 42/42 input row được
accounting, PII scan sạch, build lặp lại cùng hash và gold references hợp lệ.
```

## 6. Phân công Minh – RAG & Backend Owner

Branch: `g3/rag-minh`

### Công việc

1. Implement consumer của `g3-data-v1` cùng Tú; không để importer đọc Excel hay
   phụ thuộc tên cột tùy tiện.
2. Viết CLI import/validate từ normalized private path, không upload raw Excel.
3. Chỉ ingest record đúng version và review status cho phép.
4. Version corpus mới; hỗ trợ rollback và idempotent ingest.
5. Procedure router theo title/code/alias/category; field intent cho hồ sơ/phí/
   thời gian/nơi nộp/hình thức.
6. Giữ exact/BM25 baseline; chỉ thử dense retrieval nếu report chỉ ra recall miss.
7. Với field null hoặc conflict, trả `INSUFFICIENT_DATA`/`NEED_CLARIFICATION`.
8. Không biến row number/email thành citation hiển thị cho người dùng.
9. Chạy per-query evaluation và phân loại lỗi retrieval.
10. Giữ G1/G2 regression xanh.

### Deliverable

- importer/validator và migration nếu thật sự cần;
- corpus readiness theo version/review status;
- retrieval report DEV/TEST;
- unit/integration/security tests;
- runbook rollback và ingest private data.

### Definition of Done

- ingest idempotent, pin đúng corpus;
- source/fragment/reference integrity 100%;
- TEST routing/Recall@5 đạt gate hoặc có danh sách fail rõ;
- missing/conflict không sinh claim;
- không PII trong DB công bố, logs, response hay test artifact.

### Context giao AI agent cho Minh

```text
Đọc audit, chiến lược G3, contracts-g2 và backend/app/rag. Dữ liệu công ty không
được commit hoặc gửi ra mạng. Import chỉ nhận normalized schema đã validate;
APPROVED và PENDING phải tách rõ. Giữ corpus version/idempotency/rollback. Ưu tiên
exact+BM25 cho corpus nhỏ, chưa thêm vector DB nếu không có measured miss. Mọi
answer evidence phải trace về fragment/source; missing hoặc conflict phải abstain.
Chạy full Backend suite và G1/G2 regression trước khi bàn giao.
```

## 7. Phân công Hoan – Local Model, Evaluation & Integration Owner

Branch: `g3/model-hoan`

### Công việc

1. Thêm `LocalGroundedProvider` sau interface v2; không sửa Web/Backend contract.
2. Dựng Qwen3-1.7B local server; khóa model revision/digest và runtime version.
3. Mặc định non-thinking, context/output cap và timeout rõ.
4. Không gửi network trong lúc inference; không log prompt/evidence nhạy cảm.
5. Validate JSON, citation và data classification như template G2.
6. Benchmark BF16/Q8 reference và Q5/Q4 candidate khi khả thi.
7. Ghi TTFT, tokens/s, p50/p95, peak VRAM, error/OOM và quality per question.
8. So sánh template vs Qwen zero-shot trên cùng retrieval output.
9. Chủ trì error review và viết quyết định `NO_FINETUNE` hoặc `START_QLORA`.
10. Nếu QLoRA được mở: chuẩn bị config/reproducibility, train trên resource được
    duyệt, không dùng TEST để chọn checkpoint.

### Deliverable

- local-provider adapter + config mẫu không có secret;
- model manifest/checksum/license note;
- benchmark report có raw per-case result nhưng không chứa PII;
- Docker/runbook kết nối AI Service tới host model;
- fine-tune decision record;
- QLoRA adapter/config/report chỉ khi gate C4 cho phép.

### Definition of Done

- local Qwen chạy end-to-end với Web/RAG/history/source;
- không external call, không citation giả, không PII leak;
- quality/runtime/VRAM report tái lập;
- G1/G2 regression vẫn xanh;
- có quyết định fine-tune dựa trên lỗi, không dựa trên cảm giác.

### Context giao AI agent cho Hoan

```text
Đọc audit dataset, chiến lược G3, contracts-g2 và AI Service hiện có. Thêm local
provider sau GroundedProvider; không làm Backend/Web biết llama.cpp hay Qwen.
Chạy Qwen3-1.7B local non-thinking zero-shot trước. Chỉ gửi question + evidence
tối thiểu, không log nội dung company/PII và không gọi hosted API. Khóa model
revision, quant, context, seed/sampling và runtime. Đo schema/citation/grounding,
TTFT, tokens/s, p95 và peak VRAM trên cùng TEST. Không bắt đầu QLoRA cho đến khi
error analysis chứng minh generation là bottleneck và TEST được đóng băng.
```

---

# PHẦN III – HỢP

## 8. Thứ tự phối hợp

```text
Ngày đầu:
Tú audit/mapping ───────┐
Minh schema/import stub ├→ khóa contract C0
Hoan local runtime spike┘

Sau C0:
Tú preprocess + review → Minh ingest/retrieval → Hoan Qwen/eval
          ↑                    │                   │
          └──── error data ────┴── error report ──┘
```

Không ai cần chờ hoàn toàn:

- Tú làm parser và mapping trên workbook private.
- Minh dùng D0/fixture cùng schema để viết importer/tests.
- Hoan dùng EvidenceBundle G2 để dựng local provider.
- Chỉ tích hợp với company corpus sau khi data gate pass.

## 9. Task board

| ID | Owner | Task | Gate phụ thuộc | Output |
|---|---|---|---|---|
| G3-00 | Cả nhóm | Xác nhận governance/scope/schema | Không | Decision record |
| G3-D01 | Tú | Mapping + PII-safe deterministic preprocessor | G3-00 | Build report |
| G3-D02 | Tú | Conflict/provenance review | D01 | Approved subset |
| G3-D03 | Tú | Gold DEV/TEST theo procedure | D02 | Frozen test set |
| G3-R01 | Minh | Private normalized importer | G3-00 | Idempotent ingest |
| G3-R02 | Minh | Routing/BM25/missing-field guard | D02/R01 | Retrieval report |
| G3-A01 | Hoan | Qwen3-1.7B local provider | G3-00 | API contract pass |
| G3-A02 | Hoan | Zero-shot quant/latency/quality benchmark | D03/R02/A01 | Report |
| G3-I01 | Cả nhóm | Web→RAG→Qwen local E2E | R02/A02 | Demo + regression |
| G3-A03 | Hoan | Fine-tune decision | I01 | ADR |
| G3-A04 | Hoan | QLoRA experiment nếu được duyệt | A03=`START_QLORA` | Adapter + ablation |

### Trạng thái phần Tú sau đợt sửa 09/09/2026

| Task | Trạng thái | Bằng chứng/việc còn lại |
|---|---|---|
| G3-D01 – parser/validator | `TECHNICALLY_COMPLETE` | Test hư cấu chứng minh schema, reference, PII, conflict và deterministic; cần Tú chạy local trên workbook thật |
| G3-D02 – conflict/provenance | `BLOCKED_HUMAN_REVIEW` | Bốn nhóm conflict và nguồn/hiệu lực phải do người nghiệp vụ quyết định |
| G3-D03 – gold DEV/TEST | `DRAFT_GENERATOR_COMPLETE` | Gold đúng schema và split theo procedure; Hoan/người thứ hai phải duyệt expected point/citation rồi khóa TEST |

Chi tiết lệnh chạy và ranh giới bảo mật nằm trong
[hướng dẫn pipeline phần Tú](04-huong-dan-pipeline-data-tu.md). Không được coi
`PENDING_REVIEW` hoặc gold draft là corpus đã sẵn sàng ingest.

## 10. Review chéo

| Artifact | Author | Reviewer |
|---|---|---|
| Mapping/normalized data | Tú | Minh kiểm schema; người nghiệp vụ kiểm nghĩa |
| Gold questions | Tú | Hoan; TEST do reviewer khác khóa |
| Import/retrieval | Minh | Tú kiểm row/source mapping; Hoan kiểm bundle |
| Local provider/prompt | Hoan | Minh kiểm contract/citation |
| Benchmark/error labels | Hoan | Tú kiểm data errors; Minh kiểm retrieval errors |
| Quyết định QLoRA | Hoan | Cả nhóm + mentor |

## 11. Definition of Done của G3

G3 chỉ hoàn thành khi:

- company dataset có version, governance và approved subset;
- raw/derived company content không lọt lên Git hoặc provider ngoài;
- RAG trả đúng evidence hoặc abstain cho field thiếu/xung đột;
- Qwen3-1.7B chạy local end-to-end sau provider boundary;
- citation binding 100%, có quality/runtime/VRAM report;
- G1/G2 regression xanh;
- có quyết định định lượng về QLoRA;
- nếu QLoRA không giúp, dự án giữ base model thay vì cố dùng bản fine-tune.

## 12. Việc bắt đầu ngay

1. Tú chạy công cụ `G3-D01` trên máy local, giữ output private và bàn giao báo cáo
   count/hash; implementation parser/validator đã hoàn tất.
2. Minh làm `G3-R01`: importer từ normalized fixture theo schema khóa.
3. Hoan làm `G3-A01`: local model server spike và provider adapter.
4. Người nghiệp vụ xử lý `G3-D02`; Hoan/người thứ hai review gold `G3-D03`.
5. Cả nhóm hỏi công ty bảy câu governance trong file audit.
6. Chưa tải model hoặc train bằng dataset công ty trên cloud ngoài khi chưa có
   xác nhận chính sách.
