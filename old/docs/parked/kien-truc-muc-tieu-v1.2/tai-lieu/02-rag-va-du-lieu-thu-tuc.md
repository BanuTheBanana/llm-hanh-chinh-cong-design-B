# Module 02 – RAG và dữ liệu thủ tục hành chính

> File chi tiết cho Data/RAG: kiểm toán dữ liệu, Procedure Store, ingestion, retrieval, reranker, versioning và EvidenceBundle.  
> File trung tâm: [Workflow tổng quát](../00-workflow-tong-quat.md).  
> Cách trình bày: **Tổng → Phân → Hợp**.

## Báo cáo cập nhật

| Trường | Nội dung |
|---|---|
| Cập nhật gần nhất | 07/09/2026 |
| Phiên bản | `v1.0` |
| Trạng thái | Baseline thiết kế; chờ dữ liệu công ty để kiểm toán và benchmark |
| Thay đổi lần này | Hợp nhất chiến lược dữ liệu và RAG; tách Procedure Resolver, Procedure Store/Engine và Evidence Retriever |
| Contract ảnh hưởng | `ProcedureBundle`, `EvidenceBundle`, `CaseCard`, `AnswerPlan`, `index_version` |

---

# PHẦN I – TỔNG: RAG ĐƯỢC DÙNG ĐỂ LÀM GÌ?

## 1. Mục tiêu

RAG của dự án không phải “ném vài đoạn văn gần nghĩa cho Qwen”. Nó phải:

1. Chốt đúng thủ tục và đúng phiên bản.
2. Đọc được dữ liệu nghiệp vụ có cấu trúc.
3. Lấy đúng fragment nguồn cho từng hướng dẫn.
4. Loại thủ tục sai đối tượng, địa phương, thời điểm hoặc kênh nộp.
5. Cập nhật tri thức mà không cần fine-tune lại generator.

## 2. Ba trách nhiệm tách biệt

```text
Procedure Resolver
→ map ngôn ngữ người dân sang procedure_id + procedure_version_id

Procedure Store/Engine
→ đọc field chuẩn hóa và áp dụng rules/checklist

Evidence Retriever
→ lấy fragment nguồn tương ứng để citation và audit
```

Vector search chỉ dùng để chọn thủ tục/citation. Khi đã biết `procedure_version_id`, phí, thời hạn, giấy tờ và nơi nộp phải được đọc trực tiếp từ Procedure Store thay vì yêu cầu model “đọc hiểu rồi đoán”.

## 3. Workflow RAG tổng quát

### Offline – đưa tri thức vào hệ thống

```text
Nguồn công ty/chính thức
→ kiểm quyền, provenance, checksum, PII
→ lưu raw immutable
→ parse/OCR/normalize
→ tạo procedure versions + evidence fragments
→ review
→ chunk/embed/index staging
→ retrieval regression
→ activate atomically
```

### Online – lấy tri thức để trả lời

```text
CaseCard + query facet
→ exact/alias lookup + metadata filter
→ hybrid sparse/dense nếu cần
→ rerank động nếu còn mơ hồ
→ procedure version
→ đọc ProcedureBundle
→ lấy evidence theo field/claim
→ Evidence Gate
```

---

# PHẦN II – PHÂN: DỮ LIỆU VÀ PIPELINE

## 4. Data Readiness Report

Khi nhận dữ liệu công ty, không train/index ngay. Báo cáo đầu tiên phải có:

- nguồn gốc, chủ sở hữu, quyền dùng cho RAG/SFT/CPT/evaluation và phát hành;
- loại file, encoding, ngôn ngữ, OCR và lỗi parser;
- số procedure, version, lĩnh vực, cơ quan, cấp và địa phương;
- tỷ lệ có điều kiện, hồ sơ, bước, biểu mẫu, lệ phí, thời hạn và nơi nộp;
- ngày hiệu lực/hết hiệu lực, quan hệ thay thế/sửa đổi/bãi bỏ;
- exact/near duplicates, URL chết, snapshot và checksum;
- PII, bí mật nội bộ, retention và quyền xóa;
- khả năng chia train/dev/test không leakage;
- các trường bắt buộc còn thiếu và phương án bổ sung/review.

Đầu ra: `Data Readiness Report`, danh sách blocker, sample đã parse và đề xuất Coverage Contract.

## 5. Bốn kho dữ liệu

| Kho | Nội dung | Mục đích |
|---|---|---|
| Procedure knowledge | Thủ tục, điều kiện, hồ sơ, bước, cơ quan, phí, thời hạn, biểu mẫu, version | Source of truth nghiệp vụ |
| Supporting legal corpus | Văn bản căn cứ, Điều/Khoản/Điểm, metadata và version | Giải thích/citation khi cần |
| Behavior/SFT corpus | QA, Case Card, clarification, tool/output, claim–evidence | Dạy hành vi model |
| Evaluation corpus | Ca kín có gold answer/evidence | Chỉ dùng đánh giá |

Dữ liệu công bố thô đi vào kho tri thức trước; nó không tự động trở thành SFT sample.

## 6. Chất lượng Bronze, Silver, Gold

- `Bronze`: raw immutable, có provenance/checksum.
- `Silver`: đã parse/normalize hoặc synthetic, vượt kiểm tra tự động.
- `Gold`: đã được người có chuyên môn review.

Gold train và Gold evaluation phải tách biệt. Mỗi record giữ `source_snapshot_id`, parser version, reviewer và timestamps.

## 7. Procedure Coverage Contract

Không tuyên bố “hỗ trợ hành chính công” chung chung. Mỗi procedure cần manifest:

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

Maturity state:

```text
INDEXED → RETRIEVAL_TESTED → ANSWER_TESTED → ADVISORY_ENABLED
```

Chỉ `ADVISORY_ENABLED` được dùng để hướng dẫn đầy đủ. Procedure thiếu dữ liệu phải trả trạng thái giới hạn, không tự ghép.

## 8. Versioned Procedure Store

Đơn vị chính:

```text
Lĩnh vực → Procedure family → Procedure → Procedure version
```

Schema tối thiểu:

```text
procedure_code
procedure_family_id
procedure_version_id
service_domain
official_title
citizen_aliases
common_questions
negative_aliases
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
verified_at / verified_by
status
```

Store append-only: version mới không ghi đè version cũ. Chọn phiên bản tại `event_date`:

```text
valid_from <= event_date < valid_to
```

Nếu thiếu ngày và ngày làm đổi kết quả, trả `missing_decisive_fact=event_date`.

## 9. Citizen aliases

Tên chính thức thường khác câu người dân dùng. Mỗi procedure nên có:

```text
official_title
citizen_aliases
common_questions
common_misunderstandings
negative_aliases
```

Model lớn có thể sinh candidate offline, nhưng người review/rule phải duyệt. Alias không phải evidence và không được thay nội dung thủ tục.

## 10. Ingestion pipeline

### 10.1. Trạng thái upload

```text
UPLOADED → SCANNING → PARSING → NORMALIZING
→ REVIEW_PENDING → INDEXING → VALIDATING → ACTIVE

SCANNING/PARSING/INDEXING ─→ REJECTED hoặc FAILED
```

### 10.2. Các bước

1. Kiểm MIME thật, size, checksum và duplicate.
2. Malware scan, policy PII và quyền truy cập.
3. Lưu object gốc vào MinIO/S3, immutable.
4. Parse text/table; OCR nếu cần.
5. Chuẩn hóa mã thủ tục, cơ quan, địa phương, ngày và version relation.
6. Tạo Procedure Store record và evidence fragments.
7. Validation schema + business constraints.
8. Human/sample review.
9. Chunk/embed/index vào staging collection.
10. Smoke test + regression.
11. Activate alias/version atomically; invalidate cache.

## 11. Chunking có cấu trúc

Không cắt mù theo N token. Chunk theo facet nghiệp vụ:

```text
[Tên + mã thủ tục]
[Procedure version + địa phương + hiệu lực]
[Facet: điều kiện/hồ sơ/bước/phí/thời hạn/nơi nộp]
[Nội dung]
[Nguồn + vị trí + checksum]
```

Văn bản căn cứ chunk theo `Văn bản → Điều → Khoản → Điểm`. Bảng/list phải giữ heading và quan hệ điều kiện.

Mỗi fragment tối thiểu có:

```text
evidence_id
procedure_version_id hoặc legal_document_version_id
facet
text
source_locator
official_url
valid_from / valid_to
jurisdiction / authority
checksum
index_version
```

## 12. Procedure Resolver

### 12.1. Thứ tự tìm

```text
1. Exact procedure code
2. Exact normalized title/form/agency
3. Citizen alias/common question
4. Metadata filter
5. BM25 + dense retrieval
6. Rank fusion/dedup
7. Reranker nếu còn nhiều candidate gần nhau
8. Applicability check và chốt version
```

Metadata filter gồm:

```text
event_date
applicant_type
jurisdiction
competent_authority level
submission_channel
procedure status
index/procedure version status
```

Nếu exact/filter còn đúng một record hợp lệ, bỏ reranker.

## 13. Hybrid retrieval baseline

Baseline:

```text
Exact/metadata
+ BM25
+ BGE-M3 dense
→ RRF/rank fusion
→ BGE-reranker-v2-m3 trên tập nhỏ khi cần
```

Challenger cần benchmark:

- `gte-multilingual-base` cho retriever nhỏ hơn;
- `Qwen3-Reranker-0.6B` cho instruction-aware reranking.

Không chọn theo kích thước hoặc leaderboard. Chọn theo gold set hành chính tiếng Việt và end-to-end latency.

## 14. Rerank động

| Tình huống | Chính sách |
|---|---|
| Exact + filter còn một bản hợp lệ | Bỏ reranker |
| Top-1 hybrid rõ và vượt ngưỡng hiệu chỉnh | Có thể bỏ reranker |
| Nhiều thủ tục gần tên/khác đối tượng | Rerank top 10–20 |
| Ca khó, recall chưa đủ | Benchmark top 50 |

Các con số là ma trận thử nghiệm, không phải cấu hình production đã chốt.

Hard negatives quan trọng:

- thủ tục gần tên nhưng khác đầu ra/đối tượng;
- version đã hết hiệu lực;
- đúng tên nhưng sai địa phương/cấp cơ quan;
- online và trực tiếp bị nhầm;
- biểu mẫu/căn cứ không thuộc version;
- fragment giống từ khóa nhưng thiếu điều kiện quyết định.

## 15. Evidence Retriever và EvidenceBundle

Khi procedure đã chốt, retriever lấy evidence theo facet/field thay vì search toàn kho lại.

```json
{
  "schema_version": "1.0",
  "procedure_version_id": "proc_ver_uuid",
  "index_version": "2026-09-07.1",
  "fragments": [
    {
      "evidence_id": "ev_uuid",
      "facet": "required_documents",
      "text": "...",
      "source_locator": "Mục 3.2",
      "official_url": "https://...",
      "valid_from": "2026-01-01",
      "valid_to": null,
      "checksum": "sha256:..."
    }
  ]
}
```

Evidence bundle phải tối thiểu nhưng đủ facet user hỏi và claims dự kiến; không đưa top-k dài vào context chỉ vì đã retrieve được.

## 16. Cache và version invalidation

| Cache | Key |
|---|---|
| Procedure record | `procedure_version_id` |
| Checklist | version + jurisdiction + applicant + channel + relevant facts hash |
| Retrieval | normalized query + filters + index version |
| Embedding | public text hash + embedding model version |

Khi activate version mới:

- đổi active pointer atomically;
- invalidate theo procedure/index version;
- không xóa ngay version cũ để còn audit/rollback;
- đánh dấu answer cache cũ stale.

## 17. Chống leakage khi tạo tập dữ liệu

- Không random split từng câu QA.
- Gom các version vào `procedure_family_id`.
- Gom paraphrase cùng ca vào `scenario_group_id`.
- Exact hash + semantic dedup giữa train/dev/test.
- Temporal holdout: dữ liệu sau T0 chỉ thêm vào RAG ở T1.
- Private test không dùng chọn prompt, threshold hoặc checkpoint.

## 18. Metrics RAG

```text
procedure top-1 accuracy
Recall@5/10/50/100
MRR@10 / nDCG@10
correct-version@k
jurisdiction/authority accuracy
facet coverage
wrong-document rate
evidence exact-span precision/recall
retrieval/rerank latency P50/P95
index freshness and source health
```

Báo cáo macro, worst-domain và từng error bucket; không chỉ micro average.

---

# PHẦN III – HỢP: KẾ HOẠCH VÀ NGHIỆM THU

## 19. Thứ tự triển khai

### R0 – Audit dữ liệu

- Data Readiness Report.
- Coverage Contract/Manifest.
- Canonical IDs, provenance và license matrix.

### R1 – Procedure Store

- Schema versioned/append-only.
- Parser/normalizer và sample Gold.
- Version/effectivity và source snapshot.

### R2 – Ingestion skeleton

- Upload → object store → queue → parser → staging.
- Validation, activation và rollback.

### R3 – Retrieval baseline

- Exact/alias/metadata.
- BM25 + BGE-M3 + fusion.
- Gold routing/evidence set.

### R4 – Reranker và EvidenceBundle

- Zero-shot baseline rồi mới fine-tune.
- Dynamic rerank top 10/20/50.
- Field-to-evidence mapping.

### R5 – Hardening

- Incremental update, cache invalidation và source-health monitor.
- Temporal T0/T1, prompt-injection corpus và rollback drill.

## 20. Bake-off bắt buộc

| Nhánh | Retriever | Reranker | Câu hỏi |
|---|---|---|---|
| A | BM25 | Không | Lexical baseline mạnh đến đâu? |
| B | BGE-M3 | Không | Dense tăng recall bao nhiêu? |
| C | BM25 + BGE-M3 | BGE v2 m3 | Quality/latency end-to-end? |
| D | mGTE + BM25 | mGTE reranker | Retriever nhỏ có đủ tốt và nhanh hơn? |
| E | Baseline hybrid | Qwen3 reranker 0.6B | Instruction reranking có đáng chi phí? |

Mỗi nhánh chạy cùng candidate pool/split và ghi dataset/index/model version.

## 21. Quality gate

- Mọi procedure field truy được về snapshot nguồn.
- Không dùng version staging/inactive để trả lời.
- Exact code/title không bị reranker loại nhầm.
- Correct-version và jurisdiction đạt ngưỡng đã chốt.
- Retrieval đạt recall gate trên từng domain, không chỉ trung bình.
- Evidence bundle đủ facet và không chứa nguồn ngoài allowlist.
- Activate/rollback atomic; cache không phục vụ version stale.
- Một procedure mới có thể publish mà không fine-tune Qwen.

## 22. Definition of Done module

- Data Readiness Report được nhóm/công ty duyệt.
- Procedure Store schema, migration và sample data hoàn chỉnh.
- Raw snapshot immutable, provenance/checksum đầy đủ.
- Ingestion staging → validate → activate → rollback chạy được.
- Procedure Resolver có exact/alias/filter/hybrid/rerank động.
- EvidenceBundle schema và field-to-evidence mapping hoạt động.
- Có gold retrieval set, benchmark và error analysis.
- Có monitoring freshness, URL/source health và index version.

## 23. Tài liệu nghiên cứu chính

- [BGE-M3](https://aclanthology.org/2024.findings-acl.137/)
- [Vietnamese IR across domains](https://aclanthology.org/2026.findings-eacl.110/)
- [Vietnamese legal retrieval pipeline](https://aclanthology.org/2025.vlsp-1.17.pdf)
- [Public-service labels gần ngôn ngữ người dân](https://aclanthology.org/2026.propor-1.13/)
- [mGTE](https://aclanthology.org/2024.emnlp-industry.103/)
- [Qdrant hybrid queries](https://qdrant.tech/documentation/search/hybrid-queries/)

