# Data Contract G3 giữa Tú và Minh – `g3-data-v1`

## Báo cáo cập nhật

| Trường | Nội dung |
|---|---|
| Ngày khóa | 09/09/2026 |
| Phiên bản schema | `g3-data-v1` |
| Trạng thái | `FROZEN_FOR_G3_C1` |
| Producer | Tú – Data & Gold Owner |
| Consumer | Minh – RAG & Backend Owner |
| Phân loại | `D2_COMPANY_REAL` |
| Machine schema | [`schema/data-contract-v1.schema.json`](schema/data-contract-v1.schema.json) |

## Tổng

Tú không giao Excel trực tiếp cho code ingest của Minh. Ranh giới bắt buộc là năm
file JSONL private:

```text
data/company_private/<dataset_version>/
├── source_manifest.jsonl
├── normalized/procedures.jsonl
├── normalized/fragments.jsonl
├── quarantine/conflicts.jsonl
└── gold/questions.jsonl
```

Quy tắc giao nhận:

```text
Tú: Excel → validate/normalize/review → JSONL g3-data-v1
                                         ↓
Minh: chỉ đọc JSONL → validate schema/reference/review → ingest corpus
```

Raw và mọi JSONL chứa nội dung công ty đều bị cấm commit. Chỉ code, schema, test
fixture hư cấu và report đã loại nội dung nhạy cảm được lên GitHub.

## 1. Quy ước chung

- UTF-8, không BOM, một JSON object trên một dòng, newline LF.
- Key theo `snake_case`; không có key ngoài schema.
- Mọi record có `record_type`, `schema_version="g3-data-v1"`, `dataset_version`.
- Chuỗi được NFC normalize, trim đầu/cuối và gom khoảng trắng ngoài bullet.
- Array thiếu dữ liệu dùng `[]`; scalar chưa biết dùng `null` nếu schema cho phép.
- Không dùng `"N/A"`, `"không rõ"`, `"đang cập nhật"` để thay cho `null`.
- Email người nhập không được xuất hiện trong bất kỳ file output nào.
- ID chỉ chứa chữ ASCII, số, `.`, `_`, `:`, `-` và dài tối đa 128 ký tự.
- Hash dùng SHA-256 chữ thường trên bytes/text đã quy định.
- File phải sort ổn định theo primary ID để build deterministic.

### ID deterministic

| ID | Quy tắc |
|---|---|
| `dataset_version` | Công ty cấp nếu có; tạm dùng `company-tthc-<workbook_sha8>-v1` |
| `source_id` | `d2_xlsx_<workbook_sha8>_r<row4>` |
| `procedure_id` | Ưu tiên mã thủ tục chính thức; nếu thiếu dùng `d2_title_<title_sha12>` |
| `fragment_id` | `<procedure_id>:<section_lower>:<ordinal3>` |
| `conflict_id` | `conflict:<procedure_id>:<sha8>` |
| `question_id` | `q_d2_<procedure_id_short>_<ordinal3>` |

`title_sha12` được tính từ title đã NFC + casefold + gom whitespace + bỏ dấu câu
cuối. Nếu sau review đổi title, phải giữ ID cũ trong `aliases` hoặc ghi migration;
không âm thầm tạo thủ tục mới.

## 2. Mapping 12 cột Excel

| Cột Excel | Đích | Quy tắc |
|---|---|---|
| Dấu thời gian | `SourceManifest.collected_at` | Chỉ là lúc nhập form; không dùng làm effective date |
| Địa chỉ email | DROP | Không hash để dùng lại, không log, không đưa normalized |
| Tên thủ tục hành chính | `ProcedureRecord.title`, aliases | Normalize; duplicate vào conflict register |
| Lĩnh vực | `category_code`, `category_label` | Map taxonomy; hai cách viết Giáo dục về một code |
| Hình thức nộp | `submission_methods` | `Trực tiếp→DIRECT`, `Trực tuyến→ONLINE`, `Cả hai→[DIRECT,ONLINE]` |
| Thành phần hồ sơ | `required_documents` + fragment | Tách bullet có kiểm soát; giữ text gốc trong fragment/source locator |
| Thời gian giải quyết | `processing_times` + fragment | Luôn giữ `raw_text`; chỉ parse số khi chắc chắn |
| Lệ phí | `fees` + fragment | Luôn giữ `raw_text`; `amount_vnd=null` nếu có nhiều điều kiện/không parse chắc |
| Địa điểm tiếp nhận | `receiving_authority` + jurisdiction | Không suy luận địa bàn ngoài text có sẵn |
| Ghi chú | fragment `OTHER` | Chỉ tạo khi có nội dung; không trộn vào field khác |
| File biểu mẫu | source/attachment pending | Chỉ dùng sau khi quyền truy cập, snapshot và hash được xác nhận |
| trạng thái | audit legacy only | `Xong` không đồng nghĩa `APPROVED_FOR_DEMO` |

Các field `applicant_scope`, `steps`, `legal_bases`, `effective_dates`,
`procedure_code`, `issuing_authority` không có cột nguồn tương ứng. Chúng phải là
`[]`/`null` và có trong `missing_fields` cho đến khi reviewer bổ sung nguồn.

## 3. `SourceManifest`

Một dòng Excel tạo một source row để audit; sau review có thể gộp nhiều source vào
một procedure. `source_uri` là URI nội bộ opaque, không chứa đường dẫn máy, email
hay secret. `public_url` chỉ có giá trị khi URL HTTPS đã được phép hiển thị.

Ví dụ hư cấu:

```json
{"record_type":"SOURCE_MANIFEST","schema_version":"g3-data-v1","dataset_version":"company-tthc-deadbeef-v1","source_id":"d2_xlsx_deadbeef_r0002","data_classification":"D2_COMPANY_REAL","source_type":"COMPANY_INTERNAL_WORKBOOK","title":"Bản ghi nội bộ cho Thủ tục Mẫu Alpha","source_uri":"company-internal://tthc/deadbeef/row/2","public_url":null,"issuing_authority":null,"jurisdiction":{"country_code":"VN","province":null,"district":null,"ward":null},"procedure_code":null,"collected_at":"2025-10-07T08:06:00+07:00","last_verified_at":null,"effective_from":null,"effective_to":null,"validity_status":"UNKNOWN","content_sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","raw_locator":{"workbook_sha256":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb","sheet":"Sheet mẫu","row_numbers":[2]},"parser_version":"g3-preprocess-v1","review":{"status":"PENDING_REVIEW","reviewer_role":null,"reviewed_at":null,"note":null}}
```

## 4. `ProcedureRecord`

Đây là record canonical. Danh sách business field có thể rỗng; field rỗng phải
được khai báo trong `missing_fields`. `field_evidence` chứa fragment IDs hỗ trợ
từng field, không chứa source IDs hay raw row IDs.

Quy tắc phí và thời gian:

```json
{
  "fees": [
    {"raw_text": "Không thu phí", "amount_vnd": 0, "condition": null}
  ],
  "processing_times": [
    {
      "raw_text": "Ba ngày làm việc trong trường hợp mẫu",
      "min_business_days": 3,
      "max_business_days": 3,
      "condition": "trường hợp mẫu"
    }
  ]
}
```

Nếu chuỗi là “tùy trường hợp” hoặc có nhiều mức phí, giữ `raw_text` và để số là
`null`; không ép parser tạo một con số sai.

`submission_methods` chỉ dùng `DIRECT`, `ONLINE`, `POSTAL`, `OTHER`. “Cả hai” là
hai phần tử `DIRECT` và `ONLINE`, không phải một enum riêng.

## 5. `ProcedureFragment`

Mỗi fragment chỉ nói một nhóm claim. Không chunk đơn thuần theo số ký tự nếu làm
đứt một giấy tờ và điều kiện đi kèm.

| `section_type` | Nguồn chính |
|---|---|
| `REQUIRED_DOCUMENTS` | Thành phần hồ sơ |
| `PROCESSING_TIME` | Thời gian giải quyết |
| `FEES` | Lệ phí |
| `RECEIVING_AUTHORITY` | Địa điểm tiếp nhận |
| `SUBMISSION_METHODS` | Hình thức nộp |
| `OTHER` | Ghi chú |

`source_locator` bắt buộc có sheet, row, column name/index và SHA-256 của raw cell.
Nó phục vụ audit nội bộ; Backend không trả row/path này ra Web.

## 6. `ConflictRecord`

Tạo conflict khi các row có cùng title normalized nhưng khác business field. Khi
`status=OPEN`, procedure tương ứng phải `QUARANTINED` và Minh không ingest.

Các trạng thái resolution:

- `RESOLVED_MERGE`: các row bổ sung cho cùng một phiên bản;
- `RESOLVED_VERSION`: cùng thủ tục nhưng khác thời điểm/phiên bản;
- `RESOLVED_KEEP_SEPARATE`: khác địa bàn/đối tượng dù tên giống;
- `OPEN`: chưa có quyết định.

`resolution`, `reviewer_role`, `reviewed_at` bắt buộc có khi đã resolved. Chỉ ghi
vai trò reviewer, không cần tên/email cá nhân trong dataset.

## 7. `GoldQuestion`

- `facts` chỉ chứa tình huống giả, không dùng hồ sơ công dân thật.
- `contains_pii` luôn `false`.
- `expected_points` phải được fragment hỗ trợ.
- `gold_source_ids` và `gold_fragment_ids` phải tồn tại trong cùng dataset version.
- `TEST` tách theo `procedure_id`, không lấy paraphrase của procedure đã dùng train.
- `author_role` và `reviewer_role` phải khác nhau ở gate cuối.
- Với `INSUFFICIENT_DATA`, gold IDs có thể rỗng.

## 8. Review gate và luật ingest

Minh chỉ ingest một procedure khi tất cả điều kiện đúng:

```text
procedure.review.status ∈ {APPROVED_FOR_DEMO, APPROVED_FOR_PRODUCTION}
AND mọi source được tham chiếu có review.status tương ứng
AND procedure không có conflict OPEN
AND schema/reference/hash validation pass
AND không phát hiện PII
```

`APPROVED_FOR_PRODUCTION` không tự suy ra từ `APPROVED_FOR_DEMO`. Trạng thái
`Xong` trong Excel không có giá trị tại review gate.

Nếu field nằm trong `missing_fields`, retrieval có thể tìm procedure nhưng không
được tạo evidence khẳng định cho field đó. Ví dụ thiếu `receiving_authority` thì
câu “nộp ở đâu?” phải trả `INSUFFICIENT_DATA` hoặc yêu cầu bổ sung phạm vi.

## 9. Invariants validator bắt buộc

1. Primary IDs unique trong từng file và không trùng khác record type.
2. `schema_version`/`dataset_version` đồng nhất toàn corpus.
3. Mọi fragment trỏ tới procedure/source tồn tại.
4. Mọi `field_evidence` và gold ID trỏ tới fragment/source tồn tại, đúng procedure.
5. Hash đúng bytes/text quy ước.
6. `effective_from <= effective_to` nếu cả hai có giá trị.
7. `min_business_days <= max_business_days` nếu cả hai có giá trị.
8. `amount_vnd` là integer không âm hoặc `null`.
9. Approved source/procedure có reviewer role và reviewed timestamp ngay trong `review`.
10. Conflict `OPEN` không đi vào corpus active.
11. Email/phone/CCCD pattern không có trong normalized/gold/report.
12. 42 raw row phải xuất hiện trong source accounting hoặc conflict/quarantine.

## 10. Handoff checklist

Tú bàn giao cho Minh bằng một manifest không chứa data content:

```text
dataset_version:
schema_version: g3-data-v1
workbook_sha256:
source_count:
procedure_count_by_review_status:
fragment_count:
conflict_open_count:
gold_count_by_split:
pii_scan: PASS/FAIL
schema_validation: PASS/FAIL
reference_validation: PASS/FAIL
deterministic_rebuild: PASS/FAIL
```

Minh phản hồi bằng ingest report:

```text
dataset_version:
corpus_version:
accepted_procedure_ids:
rejected_procedure_ids + reason codes:
source/fragment counts:
corpus_sha256:
ingest idempotency: PASS/FAIL
readiness: PASS/FAIL
```

## 11. Change control

Contract này frozen cho G3-C1. Nếu cần đổi:

1. Tạo đề xuất ghi field/enum/invariant thay đổi.
2. Tú xác nhận ảnh hưởng producer; Minh xác nhận ảnh hưởng importer/database.
3. Hoan xác nhận ảnh hưởng EvidenceBundle/evaluation nếu có.
4. Đổi `schema_version`; không âm thầm sửa format dưới tên `g3-data-v1`.
5. Cập nhật machine schema, fixture hư cấu và tests trong cùng commit.
