# Module 04 – Kiểm chứng, an toàn và đánh giá

> File chi tiết cho quality layer: Evidence Gate, Procedure Engine, AnswerPlan, verifier, abstention, test set và quality gates.  
> File trung tâm: [Workflow tổng quát](../00-workflow-tong-quat.md).  
> Cách trình bày: **Tổng → Phân → Hợp**.

## Báo cáo cập nhật

| Trường | Nội dung |
|---|---|
| Cập nhật gần nhất | 07/09/2026 |
| Phiên bản | `v1.0` |
| Trạng thái | Thiết kế quality gate cho MVP |
| Thay đổi lần này | Hợp nhất kiểm tra Case Card, Evidence Gate, Procedure Engine, AnswerPlan, Claim–Citation Audit và evaluation |
| Contract ảnh hưởng | `CaseCard`, `ProcedureBundle`, `EvidenceBundle`, `AnswerPlan`, `ExpectedClaimSet`, `ModelAnswer`, `VerificationResult` |

---

# PHẦN I – TỔNG: TẠI SAO CẦN LỚP KIỂM CHỨNG?

## 1. Mục tiêu

Không có một model khác có thể nhìn câu trả lời của Qwen rồi bảo đảm tuyệt đối đúng. Cách đáng tin cậy hơn là biến nội dung quan trọng thành dữ liệu có cấu trúc và kiểm ở nhiều thời điểm:

```text
Case Card validation
→ Evidence Gate trước khi kết luận
→ Procedure Engine tính bằng rules/data
→ AnswerPlan + ExpectedClaimSet
→ Qwen diễn giải có giới hạn
→ Verifier kiểm output
→ ANSWER / CLARIFY / ABSTAIN / ESCALATE
```

Mục tiêu không phải “zero hallucination” bằng lời hứa, mà là:

- giảm diện tích model được phép tự do sinh;
- phát hiện claim không có nguồn;
- chặn sai số, sai phiên bản, sai địa phương hoặc sai điều kiện;
- đo được tỷ lệ lỗi và quyền không trả lời.

## 2. Ba lớp quyết định

| Lớp | Câu hỏi |
|---|---|
| Case validation | Dữ kiện user/case có đủ và nhất quán chưa? |
| Evidence/Procedure | Có procedure version và nguồn đủ để tính kết quả không? |
| Answer verification | Nội dung sắp gửi có đúng với kết quả và nguồn không? |

## 3. KPI trung tâm

```text
Grounded Joint Accuracy =
kết luận đúng
AND mọi claim trọng yếu được evidence hỗ trợ
AND đúng version, thời điểm, thẩm quyền, địa phương và đối tượng
```

KPI này luôn báo cáo cùng critical error rate và P95 latency.

---

# PHẦN II – PHÂN: CÁC CỔNG KIỂM TRA

## 4. Case Card validation

### 4.1. Schema check

- JSON hợp lệ và đúng schema version.
- Enum/type/format hợp lệ.
- Cho phép `null/unknown` thay vì ép điền.
- Field chỉ nằm trong allowlist.

### 4.2. Provenance check

Mọi fact trích từ hội thoại phải có `source_message_id`. Fact được model suy ra nhưng user chưa nói rõ không được ghi thành `USER_CONFIRMED`.

### 4.3. Business validation

- procedure candidate có trong Coverage Manifest không;
- jurisdiction có hợp lệ/đủ cấp không;
- date có thể parse và nằm trong phạm vi hợp lý không;
- role/applicant type có phù hợp procedure candidate không;
- fact mới có conflict fact cũ không;
- có thiếu `missing_decisive_facts` nào làm đổi kết luận không.

Nếu thiếu, backend tạo 1–3 câu hỏi quan trọng nhất. Không hỏi hết mọi field khi chúng chưa cần cho facet hiện tại.

## 5. Evidence Gate

Evidence Gate chạy trước Procedure Engine và generation:

```text
procedure_version tồn tại và ACTIVE?
đúng event_date?
đúng jurisdiction / authority / applicant / channel?
facet user hỏi có dữ liệu đầy đủ?
evidence thuộc allowlist và checksum/source hợp lệ?
có nguồn xung đột hoặc version chưa giải quyết?
required facts đã đủ cho kết luận này?
```

Đầu ra:

```json
{
  "status": "PASS",
  "procedure_version_id": "...",
  "covered_facets": ["required_documents", "submission_place"],
  "missing_facets": [],
  "conflicts": [],
  "reason_codes": []
}
```

Không dùng confidence do Qwen tự khai làm điều kiện PASS.

## 6. Procedure Engine

Procedure Engine dùng schema/rules xác định, không dùng generation tự do.

Ví dụ:

```text
required_documents(case conditions)
− documents_owned/reported
= missing_documents
```

Nhưng phải hỗ trợ:

- tài liệu bắt buộc và có điều kiện;
- quan hệ OR/AND;
- ngoại lệ và trường hợp thay thế;
- kênh trực tuyến/trực tiếp;
- địa phương/cấp cơ quan;
- event date và procedure version;
- bước đã hoàn thành và bước tiếp theo.

Đầu ra:

```json
{
  "procedure_version_id": "...",
  "route": "ANSWER",
  "required_documents": [],
  "conditional_documents": [],
  "missing_documents": [],
  "submission_place": {},
  "fees": [],
  "processing_time": {},
  "next_steps": [],
  "expected_claims": [],
  "evidence_coverage": {}
}
```

`documents_owned` do user khai mang trạng thái `REPORTED`; UI không gọi là “đã xác minh” nếu chưa có quy trình xác minh file.

## 7. AnswerPlan

Critical facts được render bởi backend:

- hồ sơ bắt buộc/có điều kiện;
- điều kiện/ngoại lệ;
- phí/lệ phí;
- thời hạn;
- cơ quan, địa điểm và kênh nộp;
- biểu mẫu;
- citation/version.

Qwen chỉ sinh intro hoặc giải thích ngắn khi cần.

```json
{
  "answer_status": "ANSWER_VERIFIED",
  "blocks": [
    {"type": "INTRO", "rendered_by": "QWEN"},
    {"type": "DOCUMENT_CHECKLIST", "rendered_by": "BACKEND"},
    {"type": "NEXT_STEPS", "rendered_by": "BACKEND"},
    {"type": "SOURCES", "rendered_by": "BACKEND"}
  ],
  "expected_claim_ids": ["C1", "C2", "C3"]
}
```

Nếu template đủ rõ, có thể trả lời mà không gọi Qwen lần hai.

## 8. ExpectedClaimSet

Mỗi claim trọng yếu được tạo trước từ Procedure Engine:

```json
{
  "claim_id": "C1",
  "claim_type": "REQUIRED_DOCUMENT",
  "canonical_value": "Giấy chứng sinh",
  "conditions": ["applicant_role in ['father','mother']"],
  "evidence_ids": ["ev_doc_02"],
  "criticality": "HIGH",
  "required_in_answer": true
}
```

ExpectedClaimSet cho biết model được phép nói gì và claim nào bắt buộc xuất hiện. Nó làm kiểm chứng đơn giản hơn so với phân tích một đoạn văn hoàn toàn tự do.

## 9. ModelAnswer

```json
{
  "schema_version": "1.0",
  "answer_status": "ANSWER_VERIFIED",
  "intro": "Bạn đã có CCCD...",
  "claims": [
    {
      "claim_id": "C1",
      "text": "Bạn cần chuẩn bị giấy chứng sinh.",
      "evidence_ids": ["ev_doc_02"]
    }
  ],
  "memory_delta": null
}
```

Citation hiển thị cho user được backend ánh xạ từ `evidence_id`; model không tự viết URL hoặc tên nguồn ngoài bundle.

## 10. Verifier cascade

Chạy rẻ và xác định trước, semantic sau:

### Tầng 1 – Schema

- parse được;
- status/claim IDs/evidence IDs đúng type và allowlist.

### Tầng 2 – Exact value

- phí, số ngày, biểu mẫu, cơ quan, địa chỉ, giấy tờ khớp canonical value;
- không tự thêm số liệu hoặc required item.

### Tầng 3 – Applicability và citation

- evidence tồn tại;
- đúng procedure version, event date, jurisdiction, authority và facet;
- source fragment/checksum hợp lệ.

### Tầng 4 – Completeness và condition

- claim bắt buộc có mặt;
- claim điều kiện chỉ xuất hiện khi condition đúng;
- không bỏ sót ngoại lệ quan trọng;
- không biến `REPORTED` thành `VERIFIED`.

### Tầng 5 – Semantic entailment tùy chọn

Chỉ kiểm phần văn tự do còn lại. Model semantic/NLI nhỏ là lớp hỗ trợ, không thay các check xác định phía trên.

## 11. Khi verifier thất bại

```text
Lỗi format/diễn đạt có thể sửa
→ rewrite tối đa 1 lần bằng error codes cụ thể

Lỗi critical claim/evidence
→ backend bỏ block/claim lỗi hoặc chuyển fail closed

Nguồn thiếu/xung đột/ngoài coverage
→ CLARIFY / INSUFFICIENT_EVIDENCE / ESCALATE
```

Không loop generation vô hạn. Mọi lần rewrite và lý do reject phải được audit.

## 12. Trạng thái chuẩn

```text
ANSWER_VERIFIED
ASK_CLARIFICATION
INSUFFICIENT_EVIDENCE
CONFLICT_DETECTED
OUT_OF_SCOPE
HIGH_RISK_ESCALATION
```

Citation status:

```text
verified
unresolved
misquoted
unsupported
wrong_version
inapplicable
```

## 13. Phân loại critical errors

Lỗi critical gồm:

- sai procedure hoặc version;
- sai đối tượng, địa phương, cấp/cơ quan;
- sai/mất giấy tờ bắt buộc hoặc điều kiện quyết định;
- sai phí, thời hạn, nơi/kênh nộp;
- citation không tồn tại hoặc không hỗ trợ claim;
- dùng nguồn hết hiệu lực;
- trả lời chắc chắn khi evidence không đủ/xung đột;
- trộn facts giữa user/case;
- tiết lộ PII hoặc thực hiện instruction injection từ tài liệu.

## 14. An toàn và prompt injection

- Retrieved text là dữ liệu, không phải instruction.
- Chỉ nguồn allowlist/ACTIVE được dùng.
- Tool/RAG read-only trong MVP.
- Không để model tạo raw SQL, URL fetch tùy ý hoặc gọi endpoint ngoài allowlist.
- Strip/label instruction-like text trong tài liệu nhưng vẫn lưu raw để audit.
- Tách system policy khỏi user/evidence bằng delimiters.
- Log và test prompt injection ở cả user message lẫn upload.

## 15. Thiết kế evaluation set

### 15.1. Đơn vị gold

Mỗi case test nên có:

```text
scenario_group_id
procedure_family_id
event_date / jurisdiction / applicant role
conversation turns
gold Case Card per turn
gold missing decisive facts
gold procedure version
gold ProcedureBundle fields
gold evidence IDs/spans
gold ExpectedClaimSet
allowed answer statuses
risk level
```

### 15.2. Split

- split theo procedure/document family và scenario group;
- semantic/exact dedup;
- temporal holdout T0/T1;
- private test khóa;
- Gold train khác Gold evaluation.

### 15.3. Test buckets

- câu rõ, câu mơ hồ và ngôn ngữ đời thường;
- thiếu decisive facts;
- user nêu premise/mã thủ tục sai;
- hai procedure gần tên;
- version hết hiệu lực/chưa hiệu lực;
- trung ương và địa phương;
- online và trực tiếp;
- evidence nhiễu/thiếu/xung đột;
- multi-turn và quay lại ngày hôm sau;
- user sửa fact;
- prompt injection;
- concurrency/cross-user leakage;
- quantization regression.

## 16. Bốn chế độ đánh giá

1. `Closed-book`: đo kiến thức/hành vi raw model, không dùng làm production truth.
2. `Oracle evidence`: cô lập năng lực hiểu/diễn đạt model.
3. `Retrieved evidence`: thêm lỗi retriever.
4. `Full pipeline`: thêm temporal filter, Procedure Engine, gate và verifier.

So sánh bốn chế độ giúp biết lỗi nằm ở model, retrieval, rules, versioning hay verifier.

## 17. Metrics theo tầng

### Case/memory

```text
field precision/recall/F1
missing-fact accuracy
case routing / correct-resume rate
unsupported-memory rate
summary faithfulness / critical-fact retention
```

### Retrieval

```text
top-1, Recall@k, MRR/nDCG
correct-version@k
jurisdiction/authority accuracy
evidence span precision/recall
```

### Procedure/answer

```text
conditional checklist accuracy
critical-value exact accuracy
answer accuracy with gold/retrieved evidence
supported-claim precision
citation existence/support/coverage/temporal accuracy
unsupported material claim rate
```

### Selective safety

```text
clarification precision/recall
abstention precision/recall
risk–coverage curve
unsafe answer rate
critical error rate
```

### System

```text
Grounded Joint Accuracy
end-to-end task success
P50/P95/P99 latency
throughput, VRAM, timeout/OOM
```

Mọi metric báo cáo macro, worst-domain và theo risk bucket.

---

# PHẦN III – HỢP: QUY TRÌNH CHẤT LƯỢNG

## 18. Evaluation-first workflow

```text
Khóa schema + error taxonomy
→ tạo private pilot set nhỏ nhưng đại diện
→ đo từng component baseline
→ chạy end-to-end
→ phân loại lỗi theo owner
→ chỉ thay một biến/ablation
→ ghi commit + dataset + model + index + config
→ regression trước merge/release
```

## 19. Quality gates đề xuất

Ngưỡng số cụ thể phải do nhóm/mentor chốt sau baseline. Tuy nhiên rule gate là bắt buộc:

- cross-user/case leakage phải bằng 0;
- critical claim phải có evidence đã verify;
- wrong-version/inapplicable critical claim không được phát ra;
- quantized artifact không được làm tăng critical error vượt ngưỡng;
- cấu hình nhanh hơn chỉ được chọn khi quality gate vẫn đạt;
- không có coverage/evidence thì fail closed;
- mỗi release phải chạy private regression set bất biến.

## 20. Ma trận ablation

| ID | Thay đổi | Mục tiêu |
|---|---|---|
| A0 | Luôn Qwen + hybrid + rerank | Baseline đối chứng |
| A1 | + rule Policy Router | Giảm model calls/P95? |
| A2 | + exact/filter/dynamic rerank | Giữ recall với latency thấp hơn? |
| A3 | + Procedure Engine/AnswerPlan | Giảm critical-value errors? |
| A4 | + Evidence Gate/verifier | Giảm unsupported/wrong-version claim? |
| A5 | + cache/context cap | Giảm warm latency mà không mất quality? |
| A6 | + grounded SFT | Model behavior cải thiện đủ đáng train? |
| A7 | + semantic verifier | Bắt thêm lỗi hay tăng false reject? |

## 21. Error ownership

| Error bucket | Owner chính |
|---|---|
| Sai user/case/context | Backend |
| Sai procedure/version/evidence | Data/RAG |
| Sai checklist/condition | Procedure Engine + data |
| Sai extraction/diễn đạt | Model |
| Claim lọt kiểm tra | Verifier |
| UI hiển thị sai/thiếu nguồn | Frontend |
| Timeout/OOM/queue lag | Infra + backend/model |

Không dùng “LLM trả lời sai” làm một bucket chung.

## 22. Definition of Done module

- Có schema cho Evidence Gate, AnswerPlan, claim và VerificationResult.
- Verifier exact/applicability/completeness chạy bằng code.
- Có fail-closed state và rewrite tối đa một lần.
- Private evaluation set tách leakage và có temporal cases.
- Dashboard/report tách metric theo component và error bucket.
- Quantization/retriever/model release đều chạy cùng regression suite.
- Mỗi answer production lưu audit đủ để tái hiện procedure/evidence/model version.

