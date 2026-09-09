# Pipeline dữ liệu G3 – phần Tú

## Báo cáo cập nhật

| Trường | Nội dung |
|---|---|
| Cập nhật gần nhất | 09/09/2026 |
| Phiên bản công cụ | `g3-preprocess-v3` |
| Contract | `g3-data-v1` |
| Trạng thái kỹ thuật | Workbook thật preflight PASS; chờ review nghiệp vụ |
| Phân loại dữ liệu | `D2_COMPANY_REAL`, chỉ xử lý local |

## Tổng

Pipeline thay thế script thử nghiệm đã đẩy nhầm lên `main`. Nó đọc Excel tại máy
người chạy, loại hoàn toàn cột email khỏi output, tạo năm file JSONL đúng contract
và không tự phê duyệt dữ liệu.

```text
Excel private
→ build deterministic
→ JSONL private PENDING/QUARANTINED
→ preflight schema/reference/PII
→ người nghiệp vụ xử lý conflict và duyệt nguồn
→ Hoan review gold, khóa TEST
→ publish gate
→ Minh ingest approved subset
```

Code và test hư cấu được phép commit. Excel, normalized JSONL, gold thật và báo cáo
có nội dung công ty phải nằm dưới `data/company_private/`, đã được `.gitignore` chặn.

## Chạy công cụ

Từ thư mục repository:

```powershell
uv sync --project tools/data --group dev

uv run --project tools/data hcc-build-company-data `
  --excel "dataset/<ten-workbook>.xlsx" `
  --output-root data/company_private `
  --expected-workbook-sha256 9c38dde8f496f853f72b5bf19d0c538d36503cfb52da1ec03d08bfcbfb9dec03 `
  --verify-deterministic

uv run --project tools/data hcc-validate-company-data `
  --dataset data/company_private/company-tthc-9c38dde8-v1 `
  --schema docs/giai-doan-3/schema/data-contract-v1.schema.json `
  --mode preflight `
  --expected-source-count 42 `
  --workbook "dataset/<ten-workbook>.xlsx"
```

Lệnh chỉ in trạng thái, version, count và mã lỗi; không in nội dung ô Excel.

## Các file private được tạo

```text
data/company_private/<dataset_version>/
├── source_manifest.jsonl
├── normalized/procedures.jsonl
├── normalized/fragments.jsonl
├── quarantine/conflicts.jsonl
├── gold/questions.jsonl
├── reports/data-quality.json
└── DATA_CARD.md
```

`gold/questions.jsonl` mới chỉ là bản nháp bán tự động. Mọi câu đều mang
`reviewer_role=PENDING_SECOND_REVIEW`; không được dùng TEST chính thức trước khi
Hoan/người thứ hai kiểm từng expected point và citation.

## Phân

### Parser chịu trách nhiệm

- nhận diện 12 header của workbook thật, không phụ thuộc cột đang được Excel hiển thị;
- luôn loại email khỏi output; timestamp chỉ là metadata audit;
- dừng với `UNSUPPORTED_COLUMNS_WITH_DATA_AT_INDEX` nếu cột chưa có mapping chứa
  dữ liệu; chỉ bỏ qua cột có header nhưng rỗng toàn bộ;
- bỏ dòng trống trong used range;
- không xuất email;
- NFC normalize và tạo ID/hash ổn định;
- tạo source, procedure và fragment theo đúng machine schema;
- chỉ parse phí/thời gian khi biểu thức đủ chắc chắn;
- đưa title trùng nhưng business field khác vào conflict `OPEN`;
- để field không có nguồn thành `[]`/`null` và khai báo `missing_fields`;
- giữ record thường ở `PENDING_REVIEW`, conflict ở `QUARANTINED`.

### Validator chịu trách nhiệm

- JSON Schema Draft 2020-12 và format ngày/URI;
- UTF-8 không BOM, newline LF;
- ID, dataset version và classification đồng nhất;
- kiểm tra reference procedure/source/fragment/gold/conflict;
- kiểm tra hash fragment và fingerprint workbook khi được truyền vào;
- scan email, số điện thoại, CCCD và dạng API key phổ biến;
- kiểm tra split theo `procedure_id` không rò TRAIN/DEV/TEST;
- chặn publish khi procedure/gold chưa có review độc lập.

### Con người vẫn phải làm

1. Xác nhận quyền dùng và nguồn gốc workbook.
2. Quyết định bốn nhóm conflict: merge, version hay keep separate.
3. Bổ sung nguồn, mã thủ tục, hiệu lực, địa bàn và vai trò reviewer.
4. Duyệt từng thủ tục trước khi đổi sang `APPROVED_FOR_DEMO`.
5. Duyệt gold bằng người khác author và đóng băng TEST.

Không sửa trực tiếp output để “cho validator xanh” nếu chưa có quyết định nghiệp vụ.

## Hợp – điều kiện bàn giao Minh

Chỉ chạy `--mode publish` sau review. Bàn giao khi lệnh trả `PASS`, deterministic
rebuild pass, 42 nguồn được accounting, không conflict mở trong approved subset,
PII sạch và gold references hợp lệ. Nếu chưa đạt, Minh chỉ dùng fixture hư cấu để
phát triển importer, không ingest corpus công ty.
