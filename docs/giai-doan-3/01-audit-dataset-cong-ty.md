# Audit đầu vào G3 – Workbook thủ tục hành chính của công ty

## Báo cáo cập nhật

| Trường | Nội dung |
|---|---|
| Cập nhật | 09/09/2026 |
| Phiên bản | `v1.1-input-shape-correction` |
| Trạng thái | `INPUT_SHAPE_CORRECTED; LOCAL_PREFLIGHT_REQUIRED` |
| Phân loại | `D2_COMPANY_REAL` |
| Phạm vi xác nhận | Theo workbook nhóm bàn giao: 9 cột nghiệp vụ C–K, không có email/timestamp |
| Fingerprint và số liệu nội dung | Phải sinh lại bằng pipeline local; không dùng số liệu của audit v1.0 |

Raw workbook nằm trong `dataset/` và được `.gitignore` chặn. Không đổi tên, sửa
trực tiếp hay commit file gốc. Mọi output phát sinh từ nội dung công ty cũng phải
nằm dưới `data/company_private/`.

> Đính chính bắt buộc: audit v1.0 đã mô tả nhầm một bản xuất biểu mẫu 12 cột có
> email/timestamp. Đó không phải shape của workbook hiện tại. Các kết luận về email,
> timestamp, trạng thái `Xong`, số link, duplicate và SHA-256 trong bản cũ không được
> dùng làm bằng chứng cho file hiện tại.

## Tổng

Đây là bảng tri thức thủ tục hành chính, không phải dataset huấn luyện LLM. Nó là
đầu vào cho RAG sau khi được chuẩn hóa và review; không đưa thẳng vào Qwen để
fine-tune.

```text
Excel 9 cột private
→ nhận diện header + chặn cột chưa mapping
→ chuẩn hóa deterministic
→ ProcedureRecord + ProcedureFragment + conflict register
→ review nguồn/xung đột
→ gold DEV/TEST review độc lập
→ RAG
→ Qwen local zero-shot
```

## Phân

### 1. Shape đầu vào đã chốt

Nhóm xác nhận workbook có chín cột nghiệp vụ từ C đến K. Các cột đã nhìn rõ gồm:

1. Tên thủ tục hành chính.
2. Lĩnh vực.
3. Hình thức nộp.
4. Thành phần hồ sơ.
5. Thời gian giải quyết.
6. Lệ phí.
7. Địa điểm tiếp nhận hồ sơ trực tiếp (nếu có).
8. Ghi chú.
9. Cột K phải được nhận diện bằng đúng header khi chạy local.

Pipeline map theo tên header, không theo vị trí. Nếu cột K hoặc bất kỳ cột chưa có
mapping nào chứa dữ liệu, build phải dừng bằng
`UNSUPPORTED_COLUMNS_WITH_DATA_AT_INDEX`; một cột chỉ có header nhưng rỗng toàn bộ
có thể được bỏ. Biến thể đầu vào khác có email/timestamp vẫn được nhận diện, nhưng
email luôn bị DROP và timestamp không bao giờ được coi là ngày hiệu lực.

### 2. Những gì chỉ được kết luận sau local preflight

Không tái sử dụng các con số của audit cũ. Pipeline phải sinh báo cáo mới cho đúng
workbook hiện tại:

- SHA-256 nguyên file và `dataset_version`;
- số dòng nguồn thực, số dòng trống bị bỏ;
- số thủ tục sau normalize;
- phân bố lĩnh vực;
- số field thiếu theo loại;
- số nhóm title trùng/xung đột;
- số fragment và gold draft;
- schema/reference/PII/deterministic result.

Báo cáo chỉ chứa count/hash/error code, không chứa nội dung ô hoặc đường dẫn private.

### 3. Rủi ro nghiệp vụ vẫn còn dù file không có email

| Mức | Vấn đề | Cách xử lý |
|---|---|---|
| Blocker | Chưa có nguồn/căn cứ chính thức đã xác nhận | Source register hoặc reviewer nghiệp vụ xác nhận nguồn nội bộ |
| Blocker | Chưa có procedure code/version/effective date đáng tin cậy | Để `null` + `missing_fields`; không tự suy đoán |
| High | Phạm vi địa phương có thể chỉ nằm trong text | Tách `jurisdiction` và `receiving_authority`, review trước khi dùng |
| High | Tên trùng có thể chứa nội dung khác nhau | Tạo conflict `OPEN`, procedure `QUARANTINED`, con người quyết định |
| High | Cột chưa mapping có thể bị mất dữ liệu | Build fail-safe, bổ sung mapping qua change control |
| Medium | Lệ phí/thời gian có nhiều điều kiện | Giữ `raw_text`; số parse không chắc phải là `null` |
| Medium | Thành phần hồ sơ dài hoặc có ngoại lệ | Fragment theo field/nhóm nghĩa; reviewer kiểm tra không mất điều kiện |
| Medium | Nơi tiếp nhận hoặc field khác bị trống | Khai báo `missing_fields`; câu hỏi tương ứng phải abstain |

Không có email trong workbook hiện tại không đồng nghĩa dữ liệu tự động an toàn:
nội dung tự do vẫn phải qua PII/secret scan và review thủ công.

### 4. Trường còn thiếu so với RAG production

Nếu workbook không cung cấp thì giữ thiếu rõ ràng, không bịa:

- mã thủ tục chính thức và cơ quan ban hành;
- URL/snapshot nguồn được phép hiển thị;
- `jurisdiction` chuẩn hóa;
- ngày hiệu lực, hết hiệu lực và kiểm tra gần nhất;
- căn cứ pháp lý;
- đối tượng/điều kiện áp dụng;
- trình tự thực hiện;
- reviewer và trạng thái phê duyệt.

### 5. Mức sẵn sàng

| Mục đích | Trạng thái |
|---|---|
| Parser/validator trên fixture 9 cột | Sẵn sàng kỹ thuật |
| Build workbook thật | Chờ người được phép chạy local và xử lý header chưa mapping nếu có |
| RAG fixture | Sẵn sàng kỹ thuật |
| RAG company demo | Chờ approved subset và source review |
| Gold TEST | Chờ reviewer thứ hai và đóng băng theo procedure |
| Fine-tune | Chưa có bằng chứng cần thiết; tiếp tục zero-shot baseline |
| Production | Chưa sẵn sàng |

## Hợp

### Kết luận

Phần Tú được tách thành hai lớp:

- lớp kỹ thuật: parser/validator/gold draft, test 9 cột, kiểm soát PII, conflict và
  deterministic build;
- lớp nghiệp vụ: xác nhận cột K, nguồn, hiệu lực, conflict, approved subset và gold.

AI coding agent có thể hoàn tất lớp kỹ thuật nhưng không được tự ký lớp nghiệp vụ.
Sau khi người có quyền chạy pipeline và review output private, Minh mới mở ingest,
Hoan mới chạy benchmark Qwen trên D2.

### Câu hỏi cần công ty/mentor xác nhận

1. Header đầy đủ và ý nghĩa nghiệp vụ của cột K là gì?
2. Workbook này có phải nguồn nội bộ đã được duyệt không?
3. Ai được ký `APPROVED_FOR_DEMO` và `APPROVED_FOR_PRODUCTION`?
4. Có được lưu normalized D2 trong Git private hay chỉ máy/server nội bộ?
5. Có được gửi bất kỳ phần D2 nào ra hosted API không? Mặc định dự án là không.
6. Nguồn gốc, phạm vi và ngày kiểm tra gần nhất của từng thủ tục là gì?
7. Chính sách cập nhật/freshness và thu hồi corpus cũ là gì?
