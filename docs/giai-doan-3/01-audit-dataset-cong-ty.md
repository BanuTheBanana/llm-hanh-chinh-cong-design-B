# Audit đầu vào G3 – Workbook thủ tục hành chính của công ty

## Báo cáo cập nhật

| Trường | Nội dung |
|---|---|
| Ngày audit | 09/09/2026 |
| Phiên bản | `v1.0` |
| Trạng thái | `AUDITED_NOT_READY_FOR_RAG_OR_SFT` |
| Phân loại đề xuất | `D2_COMPANY_REAL` |
| Cách kiểm tra | Chỉ đọc workbook local; không gọi API ngoài |
| SHA-256 | `9c38dde8f496f853f72b5bf19d0c538d36503cfb52da1ec03d08bfcbfb9dec03` |

Raw workbook nằm trong `dataset/` và đã được chặn bởi `.gitignore`. Không đổi
tên, sửa trực tiếp hay commit file gốc. Mọi output phát sinh từ nội dung công ty
cũng phải nằm ở khu vực private/ignored cho tới khi công ty cho phép công bố.

## Tổng

Đây là **bảng tổng hợp tri thức thủ tục**, không phải dataset huấn luyện LLM. Nó
có thể trở thành đầu vào tốt cho RAG sau khi chuẩn hóa và xác minh, nhưng chưa đủ
điều kiện để đưa thẳng vào chatbot hoặc fine-tune Qwen.

```text
Excel gốc
→ bỏ cột định danh người nhập
→ chuẩn hóa Unicode/field/type
→ xử lý bản ghi trùng và xung đột
→ bổ sung nguồn, phiên bản, hiệu lực, phạm vi, reviewer
→ ProcedureRecord + ProcedureFragment
→ gold questions tách riêng
→ ingest RAG
```

## Phân

### 1. Thống kê cấu trúc

| Chỉ số | Kết quả |
|---|---:|
| Sheet | 1 |
| Dòng dữ liệu thực | 42 |
| Cột có nghĩa | 12 |
| Tên thủ tục exact | 40 |
| Tên thủ tục sau normalize | 38 |
| Nhãn lĩnh vực hiện có | 7 |
| Email người nhập khác nhau | 9 |
| Dòng có timestamp | 36/42 |
| Dòng thiếu nơi tiếp nhận | 10/42 |
| Dòng có ghi chú | 2/42 |
| Dòng có link biểu mẫu | 3/42 |
| Dòng trạng thái `Xong` | 42/42 |

Khoảng thời gian trong cột “Dấu thời gian” là 07/10/2025–18/10/2025. Đây chỉ
là thời gian nhập biểu mẫu, **không phải ngày hiệu lực hay ngày xác minh thủ tục**.

Các nhóm lĩnh vực:

| Nhãn hiện tại | Số dòng |
|---|---:|
| Hộ tịch | 6 |
| Lao động – Tiền lương | 1 |
| Văn hóa – Xã hội | 19 |
| Kinh tế – Hạ tầng và đô thị | 13 |
| Giáo dục và đào tạo – hai cách viết | 2 |
| Chứng thực – sao y | 1 |

### 2. Điểm tốt

- 42/42 dòng có tên thủ tục, lĩnh vực, hình thức nộp, thành phần hồ sơ, thời gian,
  lệ phí và trạng thái.
- Nội dung phủ nhiều nhóm hành chính công thực tế.
- Nhiều ô “Thành phần hồ sơ” khá chi tiết, phù hợp tách thành fragment theo field.
- Hình thức nộp đã có ba giá trị dễ chuẩn hóa: trực tiếp, trực tuyến, cả hai.
- Quy mô nhỏ, phù hợp làm baseline có thể kiểm tra thủ công trước khi mở rộng.

### 3. Vấn đề phải xử lý

| Mức | Vấn đề | Ảnh hưởng | Xử lý bắt buộc |
|---|---|---|---|
| Blocker | Có email người nhập ở 42/42 dòng | Rò PII/metadata nhân sự | Loại khỏi mọi normalized, log, prompt và report |
| Blocker | Không có URL/căn cứ nguồn chính thức | Không kiểm tra được claim/citation | Yêu cầu source register hoặc reviewer nghiệp vụ xác nhận |
| Blocker | Không có procedure code/version/effective date | Nhầm thủ tục hoặc trả thông tin cũ | Bổ sung mã ổn định, phiên bản và thời gian hiệu lực |
| High | 4 nhóm tên sau normalize bị trùng và nội dung xung đột | Ingest trùng, retrieval trả hai đáp án | Review từng cặp; merge hoặc version, không tự chọn |
| High | Phạm vi địa phương chưa thành field rõ | Có thể áp dụng nhầm nơi | Tách jurisdiction/receiving authority |
| High | Lệ phí vừa string vừa number | So sánh/checklist sai | Parse thành cấu trúc amount/currency/condition/raw_text |
| Medium | Hai cách viết lĩnh vực Giáo dục | Filter bị tách | Map vào taxonomy canonical |
| Medium | 6 dòng thiếu timestamp nhập | Audit trail không hoàn chỉnh | Giữ null; không tự điền |
| Medium | 10 dòng thiếu nơi tiếp nhận | Không thể trả lời “nộp ở đâu” | `missing_fields` và abstain cho claim này |
| Medium | Dấu `?` đang được dùng như bullet ở một số ô | Chunk/answer xấu | Chuẩn hóa thành danh sách, kiểm tra không mất câu |
| Medium | 6 ô hồ sơ dài hơn 1.000 ký tự | Retrieval field lớn, khó cite chính xác | Tách theo nhóm giấy tờ/trường hợp ngoại lệ |
| Medium | 3 link Google Drive biểu mẫu | Quyền truy cập/phiên bản không bảo đảm | Tải snapshot khi được phép, hash và gắn source ID |
| Low | 100 dòng trống trong used range | Parser dễ tạo record rỗng | Bỏ dòng rỗng có kiểm thử |

Bốn nhóm trùng/xung đột nằm ở các dòng Excel:

1. Trợ cấp hưu trí xã hội: 9 và 21.
2. Xác định mức độ khuyết tật: 10 và 24.
3. Trợ cấp thờ cúng liệt sĩ: 12 và 16.
4. Trợ cấp khi người có công từ trần: 15 và 20.

Không được hợp nhất chỉ bằng fuzzy matching. Một cặp có thể là bản cập nhật,
khác cấp xử lý hoặc khác đối tượng áp dụng.

### 4. Trường còn thiếu so với contract RAG

Workbook chưa có các field sau:

- `procedure_id`/mã thủ tục ổn định;
- `source_id`, `source_url`, tên cơ quan ban hành;
- `jurisdiction` chuẩn hóa;
- `effective_from`, `effective_to`, `last_verified_at`;
- căn cứ pháp lý;
- đối tượng/điều kiện áp dụng tách riêng;
- trình tự thực hiện tách riêng;
- kết quả đầu ra của thủ tục;
- reviewer và `review_status`;
- hash/snapshot của biểu mẫu đính kèm.

Nếu công ty không có URL công khai nhưng coi bảng là nguồn nội bộ đã duyệt, cần
thêm `source_type=COMPANY_APPROVED_INTERNAL`, tên người/vai trò duyệt và version.
Giao diện phải hiển thị đúng loại nguồn nội bộ, không giả URL chính thức.

### 5. Mức sẵn sàng

| Mục đích | Sẵn sàng? | Lý do |
|---|---|---|
| Viết parser/preprocessor | Có | Schema và lỗi đã nhìn thấy rõ |
| RAG thử nghiệm private | Có điều kiện | Chỉ dùng record đã loại PII và đánh dấu unverified |
| Demo như hướng dẫn thật | Chưa | Thiếu provenance/effective/reviewer |
| Tạo gold evaluation | Có điều kiện | Cần reviewer khác người viết answer |
| Fine-tune trực tiếp từ Excel | Không | Không có instruction-output pairs; dễ học thuộc dữ kiện chưa kiểm chứng |
| Production | Không | Chưa có governance, nghiệp vụ và freshness policy |

## Hợp

### Kết luận

Dataset cần **preprocessing chuyên sâu ở tầng dữ liệu**, nhưng chưa cần fine-tune
model. Thứ tự đúng là:

1. Bảo vệ raw và lập source register.
2. Tạo preprocessor deterministic, không dùng Qwen để “tự sửa sự thật”.
3. Tú cùng người nghiệp vụ xử lý 4 nhóm xung đột và bổ sung provenance.
4. Minh ingest các record `APPROVED`; record thiếu field vẫn lưu nhưng claim tương
   ứng phải abstain.
5. Tạo gold set và chạy template/RAG baseline.
6. Hoan chạy Qwen3-1.7B local zero-shot rồi phân tích lỗi.
7. Chỉ tạo SFT/QLoRA dataset khi generation vẫn là bottleneck.

### Câu hỏi cần công ty xác nhận

1. Bảng này có phải nguồn nội bộ đã được nghiệp vụ duyệt không?
2. Có được lưu normalized content trong Git private hay chỉ ở máy/server nội bộ?
3. Có được gửi bất kỳ phần nào ra hosted API không? Mặc định của dự án là không.
4. 4 cặp trùng là bản cập nhật, khác địa bàn hay nhập trùng?
5. Nguồn gốc/căn cứ và ngày kiểm tra gần nhất của từng thủ tục là gì?
6. Ai có quyền ký `APPROVED_FOR_DEMO` và `APPROVED_FOR_PRODUCTION`?
7. 3 file biểu mẫu Google Drive có được tải, lưu snapshot và phân phối nội bộ không?
