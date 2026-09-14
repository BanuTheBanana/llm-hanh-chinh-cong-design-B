# Phân công tiền xử lý full data – Minh và Tú

Ngày giao: **14/09/2026**  
Người duyệt cuối: **Bùi Xuân Hoan**

## 1. Mục tiêu chung

Chuẩn hóa toàn bộ dữ liệu công ty theo cùng contract đã dùng cho bộ 10 thủ tục trước đây.
Đầu vào hiện được thống kê khoảng **42 nguồn, 38 thủ tục và 202 fragment**. Đây là số để
đối chiếu đầu vào, không được ép đầu ra phải giữ đúng 202 fragment nếu quá trình tách lại có lý do.

Kết quả cuối phải cho biết rõ:

- Thủ tục và field nào đủ dữ liệu.
- Nội dung nào thiếu, mơ hồ hoặc mâu thuẫn.
- Fragment nào thuộc nguồn, thủ tục và field nào.
- Phần nào có thể chuyển cho Hoan review; phần nào phải giữ trong quarantine.

## 2. Nguyên tắc bắt buộc

1. Không tự bổ sung thông tin không có trong nguồn.
2. Luôn giữ `raw_text` để Hoan đối chiếu với dữ liệu ban đầu.
3. Không hiểu ô trống là “không có”; phải ghi là thiếu dữ liệu.
4. Giá trị ngắn hoặc khó hiểu như `0.0`, `05` phải gắn cờ review, không tự diễn giải.
5. Hai nguồn nói khác nhau phải tạo conflict; không tự chọn một nguồn đúng.
6. Không sửa trực tiếp file dữ liệu gốc.
7. Không đưa raw data, dữ liệu công ty hoặc file review private lên GitHub.
8. Code, schema, validator và fixture giả lập được phép push; báo cáo công khai không chứa
   nội dung dữ liệu công ty.

Các field cần kiểm tra cho từng thủ tục:

- `receiving_authority`: nơi/cơ quan tiếp nhận.
- `submission_methods`: hình thức nộp.
- `required_documents`: thành phần hồ sơ.
- `fees`: lệ phí.
- `processing_times`: thời gian giải quyết.
- `steps`: trình tự thực hiện.
- `legal_bases`: căn cứ pháp lý.
- `applicant_scope`: đối tượng hoặc phạm vi người thực hiện.

## 3. Phần việc của Phan Văn Tú

### Nhiệm vụ chính: chuẩn hóa nội dung nghiệp vụ

1. Lập inventory đủ 42 nguồn và 38 thủ tục; ghi nguồn nào tạo ra thủ tục nào.
2. Chuẩn hóa Unicode NFC, khoảng trắng, xuống dòng và tên trường; không thay đổi ý nghĩa.
3. Gán `source_id` và `procedure_id` ổn định, không trùng.
4. Mapping nội dung từng thủ tục vào tám field ở trên.
5. Giữ đồng thời giá trị đã chuẩn hóa và `raw_text` tương ứng.
6. Tách fragment theo đúng một thủ tục và một `section_type`; không gộp các field khác nghĩa
   vào cùng fragment.
7. Ghi lại coverage theo từng thủ tục/field.
8. Đưa nội dung thiếu, mơ hồ hoặc xung đột vào danh sách review; ghi lý do cụ thể và nguồn liên quan.
9. Tự kiểm tra lại một lượt bằng cách đối chiếu fragment với raw data trước khi bàn giao.

### Đầu ra Tú cần gửi cho Hoan

```text
tu_full_data_preprocessed/
├── source_manifest.jsonl
├── normalized/
│   ├── procedures.jsonl
│   └── fragments.jsonl
├── quarantine/
│   └── conflicts.jsonl
├── coverage-report.json
├── review-required.jsonl
└── 01-bao-cao-tien-xu-ly-tu.md
```

Báo cáo của Tú cần ghi ngắn gọn:

- Số nguồn, thủ tục và fragment đã xử lý.
- Coverage của tám field: có bao nhiêu trên tổng 38 thủ tục.
- Danh sách procedure ID còn thiếu field.
- Số trường hợp mơ hồ, conflict và lý do cần Hoan quyết định.
- File nào đã hoàn thành, file nào còn chờ review.

### Tú được coi là hoàn thành khi

- 42 nguồn và 38 thủ tục đầu vào đều được đối chiếu, không mất dòng im lặng.
- Mỗi fragment truy ngược được về đúng source, procedure, field và `raw_text`.
- Không còn nội dung mơ hồ bị tự chuyển thành giá trị chắc chắn.
- Coverage report khớp dữ liệu normalized.
- Gói bàn giao không chứa file TEST hoặc đáp án đánh giá.

## 4. Phần việc của Phạm Lê Minh

### Nhiệm vụ chính: pipeline kỹ thuật và kiểm tra dữ liệu

Minh có thể làm code bằng fixture giả lập trước, không cần chờ Tú hoàn thành toàn bộ nội dung.

1. Rà lại data contract và JSON Schema cho:
   - `source_manifest.jsonl`;
   - `normalized/procedures.jsonl`;
   - `normalized/fragments.jsonl`;
   - `quarantine/conflicts.jsonl`;
   - coverage report và manifest phiên bản.
2. Hoàn thiện lệnh preprocess/validate chạy deterministic: cùng đầu vào phải tạo cùng ID và
   cùng kết quả.
3. Validator phải kiểm tra:
   - JSON, UTF-8 và Unicode NFC;
   - ID trùng;
   - source/procedure/fragment reference bị gãy;
   - `section_type` không hợp lệ;
   - fragment rỗng hoặc thiếu `raw_text`;
   - content hash và manifest hash;
   - thủ tục bị mất giữa raw và normalized;
   - fragment gắn sai procedure hoặc field;
   - dữ liệu mơ hồ nhưng không được gắn cờ;
   - conflict không có đủ hai nguồn/giá trị cần đối chiếu.
4. Tạo coverage checker cho đủ tám field và xuất danh sách thiếu theo `procedure_id`.
5. Viết test bằng dữ liệu giả lập cho cả ca đúng và các ca lỗi ở mục 3.
6. Viết README gồm đúng lệnh cài môi trường, preprocess, validate và tạo báo cáo.
7. Khi nhận gói normalized của Tú, chạy validator và phân loại rõ:
   - lỗi dữ liệu để Tú sửa;
   - lỗi tool/schema để Minh sửa;
   - trường hợp nghiệp vụ cần Hoan quyết định.
8. Tạo manifest có version, số lượng file/dòng, SHA-256 và trạng thái `PENDING_REVIEW`.
   Minh không tự chuyển thành `APPROVED` hoặc `LOCKED`.

### Đầu ra Minh cần gửi cho Hoan

```text
Code trên branch riêng:
├── schema cho full corpus
├── preprocess/validator/coverage CLI
├── test dùng fixture giả lập
└── README cách chạy

Gói báo cáo local:
├── validation-report.json
├── corpus-manifest.json
└── 01-bao-cao-validator-minh.md
```

Báo cáo của Minh cần ghi:

- Các kiểm tra validator đã triển khai.
- Số test pass/fail.
- Số lỗi phát hiện trong gói Tú bàn giao, chia theo loại.
- Lỗi nào Tú cần sửa, lỗi nào Minh đã sửa trong tool.
- Hash và trạng thái của gói chờ Hoan review.

### Minh được coi là hoàn thành khi

- Tool chạy được từ môi trường sạch theo README.
- Test không sử dụng dữ liệu công ty và có đủ ca lỗi chính.
- Validator không bỏ qua reference gãy, duplicate, hash sai, field sai hoặc mất thủ tục.
- Báo cáo validation được tạo tự động, không sửa số bằng tay.
- Manifest cuối vẫn là `PENDING_REVIEW`, chưa tự duyệt thay Hoan.

## 5. Cách Tú và Minh phối hợp

```text
Tú lập inventory và chuẩn hóa nội dung
                ↓
Minh chạy schema/validator/coverage
        ↙               ↘
Lỗi dữ liệu trả Tú     Lỗi tool Minh sửa
        \               /
         Gói PENDING_REVIEW
                ↓
        Hoan đối chiếu và duyệt
```

- Tú không cần chờ Minh để bắt đầu inventory và mapping field.
- Minh không cần chờ Tú để viết schema, validator và test giả lập.
- Khi ghép lần đầu, hai bạn không tự xóa dữ liệu chỉ để validator pass.
- Mọi trường hợp không thống nhất được phải ghi vào `review-required.jsonl` để Hoan quyết định.

## 6. Phần Hoan sẽ làm sau khi nhận bàn giao

1. Đối chiếu báo cáo Tú với báo cáo validator của Minh.
2. Review các trường thiếu, mơ hồ và conflict.
3. Chọn `APPROVED`, `INSUFFICIENT_DATA`, `CONFLICT` hoặc `QUARANTINED` cho từng trường hợp.
4. Chạy lại validator, khóa version và SHA-256.
5. Chỉ phần đã duyệt mới được đưa vào kho phục vụ; phần còn lại tiếp tục cách ly.

## 7. Tin nhắn ngắn để giao việc

### Gửi Tú

> Tú giúp mình chuẩn hóa toàn bộ 42 nguồn/38 thủ tục theo contract bộ 10 thủ tục cũ. Mapping
> đủ tám field, giữ raw_text, tách fragment đúng source/procedure/field và làm coverage report.
> Ô trống, giá trị mơ hồ hoặc nguồn mâu thuẫn thì gắn cờ review, không tự đoán. Gửi lại gói
> normalized, quarantine, coverage và báo cáo số lượng; không push raw data công ty lên GitHub.

### Gửi Minh

> Minh giúp mình hoàn thiện schema, pipeline preprocess, validator và coverage checker cho full
> corpus. Làm test bằng fixture giả lập trước; kiểm duplicate, reference, field, raw_text, hash,
> mất thủ tục và conflict. Khi nhận gói Tú thì chạy validation, phân loại lỗi dữ liệu/lỗi tool và
> tạo manifest PENDING_REVIEW. Chỉ push code, schema, test và README; không push data công ty.
