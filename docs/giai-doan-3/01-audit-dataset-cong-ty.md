# Audit đầu vào G3 – Workbook thủ tục hành chính của công ty

## Báo cáo cập nhật

| Trường | Nội dung |
|---|---|
| Cập nhật | 09/09/2026 |
| Phiên bản | `v1.2-local-preflight` |
| Trạng thái | `G3_C1_PREFLIGHT_PASS; HUMAN_REVIEW_REQUIRED` |
| Phân loại | `D2_COMPANY_REAL` |
| Cách chạy | Script local, không gọi API ngoài, chỉ báo count/hash/mã trạng thái |
| Dataset version | `company-tthc-9c38dde8-v1` |
| Workbook SHA-256 | `9c38dde8f496f853f72b5bf19d0c538d36503cfb52da1ec03d08bfcbfb9dec03` |

Raw workbook nằm trong `dataset/`; output nằm trong `data/company_private/`. Cả hai
đều private/ignored và không được commit hoặc gửi tới hosted API.

## Tổng

Workbook có 12 header được parser nhận diện ở cột 1–12. Việc giao diện Excel đang
hiển thị từ C đến K không có nghĩa file chỉ có chín cột: A/B có thể bị ẩn hoặc nằm
ngoài vùng đang nhìn, và còn cột L. Pipeline map theo tên header, không theo vị trí.

```text
Workbook private
→ 42 SourceManifest
→ 38 ProcedureRecord
→ 202 ProcedureFragment
→ 4 ConflictRecord OPEN
→ 40 GoldQuestion draft
→ schema/reference/PII/deterministic preflight PASS
```

Đây là bảng tri thức cho RAG, không phải dataset instruction/output để fine-tune.

## Phân

### 1. Kết quả local preflight đã xác minh

| Chỉ số | Kết quả |
|---|---:|
| Header nhận diện | 12/12 |
| Source row accounting | 42 |
| Procedure sau normalize | 38 |
| Fragment | 202 |
| Conflict mở | 4 |
| Gold draft | 40 |
| Deterministic rebuild | PASS |
| Workbook fingerprint | PASS |
| JSON Schema | PASS |
| Reference integrity | PASS |
| PII scan trên normalized output | PASS |
| Procedure chờ review | 38 |
| Gold chờ review lần hai | 40 |

`PII scan PASS` áp dụng cho output normalized, không có nghĩa raw workbook là dữ
liệu công khai. Parser nhận diện metadata email nhưng không đưa email vào snapshot,
ID, normalized JSONL, report hoặc prompt.

### 2. Mapping đầu vào

Pipeline nhận diện:

1. Dấu thời gian — chỉ là audit metadata, không phải ngày hiệu lực.
2. Địa chỉ email — DROP hoàn toàn.
3. Tên thủ tục hành chính.
4. Lĩnh vực.
5. Hình thức nộp.
6. Thành phần hồ sơ.
7. Thời gian giải quyết.
8. Lệ phí.
9. Địa điểm tiếp nhận.
10. Ghi chú.
11. File biểu mẫu.
12. Trạng thái legacy — không đồng nghĩa phê duyệt nghiệp vụ.

Parser vẫn có test cho biến thể chỉ gồm chín business column. Nếu tương lai xuất
hiện cột chưa mapping và cột đó có dữ liệu, build dừng bằng
`UNSUPPORTED_COLUMNS_WITH_DATA_AT_INDEX`, không bỏ dữ kiện im lặng.

### 3. Việc bắt buộc phải do con người quyết định

- Ai có quyền ký `APPROVED_FOR_DEMO` và `APPROVED_FOR_PRODUCTION`.
- Workbook/source nội bộ có đủ thẩm quyền làm bằng chứng hay cần URL/căn cứ bổ sung.
- Cách xử lý bốn conflict thực: merge, version hay keep separate.
- Procedure code, jurisdiction, effective date, issuing authority và freshness.
- Từng expected point/citation của 40 gold draft; reviewer phải khác author.

AI không được tự đổi `PENDING_REVIEW` hoặc `QUARANTINED` thành `APPROVED`.

### 4. Mức sẵn sàng

| Mục đích | Trạng thái |
|---|---|
| Preprocess workbook thật | PASS |
| Schema/reference/PII preflight | PASS |
| Conflict/provenance review | Chưa hoàn thành |
| Approved corpus cho RAG | Chưa có |
| Gold TEST đã khóa | Chưa có |
| RAG benchmark D2 | Chưa được phép chạy như nghiệm thu |
| Fine-tune | Chưa có bằng chứng cần; giữ zero-shot baseline |
| Production | Chưa sẵn sàng |

## Hợp

### Kết luận

G3-D01 đã hoàn thành trên workbook thật về mặt kỹ thuật. Bước kế tiếp không phải
chỉnh parser mà là review nghiệp vụ: xác nhận nguồn, xử lý bốn conflict, duyệt
approved subset và duyệt độc lập 40 gold question. Chỉ sau publish gate, Minh mới
mở ingest D2 và Hoan mới benchmark Qwen trên TEST thật.

### Câu hỏi cần mentor/công ty xác nhận

1. Ai hoặc vai trò nào được ký duyệt dữ liệu demo?
2. Workbook có được xem là nguồn nội bộ đã duyệt hay cần đối chiếu nguồn chính thức?
3. Bốn conflict sẽ do ai review?
4. Có được hiển thị nội dung nguồn nội bộ cho người dùng demo không?
5. Có được lưu normalized D2 trên server nội bộ, và retention/freshness là bao lâu?
