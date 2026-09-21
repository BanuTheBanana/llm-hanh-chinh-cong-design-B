# Phân công mở rộng G5: MCP thời gian thực và từ điển 38 thủ tục

## 1. Mục tiêu chung

Giữ **G5 hiện tại làm baseline ổn định**. Hai phần việc dưới đây được phát triển độc lập,
không sửa dữ liệu gốc, không thay model đang fine-tune và không tự động thay nội dung đã
được duyệt trong corpus.

Luồng mục tiêu:

```text
Câu hỏi người dùng
  -> chuẩn hóa/từ điển
  -> nhận diện thủ tục + trường cần hỏi
  -> trả lời từ corpus local đã duyệt
  -> nếu thông tin dễ thay đổi hoặc local không đủ: hỏi người dùng có muốn kiểm tra hiện tại không
  -> chỉ khi người dùng đồng ý: gọi MCP tra cứu nguồn chính thức
  -> hiển thị kết quả, URL nguồn và thời điểm kiểm tra
```

Mỗi bạn làm trên branch riêng rồi tạo Pull Request vào `main`. Không commit `.env`, token,
workbook công ty, dữ liệu cá nhân, model, adapter hoặc thư mục `training/output`.

## 2. Phạm Lê Minh — MCP tra cứu thông tin hiện hành

### Điểm bắt đầu

Không viết lại MCP từ đầu. Repository đã có:

- `source-service/`: MCP registry nội bộ có review, publish, version và rollback;
- `backend/app/rag/g5/source_mcp.py`: MCP client và cơ chế chỉ nhận snapshot `PUBLISHED`;
- `backend/app/rag/catalog_policy.py`: danh sách thủ tục/trường cần đề nghị kiểm tra lại;
- `backend/app/rag/g5/intent_context.py`: trạng thái hội thoại và trường người dùng đang hỏi.

MCP hiện có là **MCP quản lý bản cập nhật đã review**, chưa phải công cụ tự tìm kiếm web.
Minh bổ sung một tool tra cứu thời gian thực riêng, không đổi ý nghĩa tool cũ.

### Branch và phạm vi file

- Branch đề nghị: `feature/minh-realtime-mcp`.
- Code service: `source-service/app/`.
- Client/orchestration: `backend/app/rag/g5/`.
- Test: `source-service/tests/` và `backend/tests/`.
- Tài liệu cấu hình: `.env.example` và `docs/giai-doan-5/`.

### Yêu cầu chức năng

1. Tạo tool đọc, ví dụ `lookup_current_procedure`, nhận tối thiểu:
   `procedure_id`, `procedure_name`, `field`, `jurisdiction` và `as_of`.
2. Chỉ tra cứu nguồn chính thức nằm trong allowlist. Giai đoạn đầu ưu tiên Cổng Dịch vụ
   công Quốc gia; không lấy blog, mạng xã hội hoặc kết quả tìm kiếm chung làm bằng chứng.
3. Backend chỉ gọi tool khi:
   - trường đang hỏi là thông tin dễ thay đổi như thời gian giải quyết hoặc nơi tiếp nhận;
   - hoặc corpus local không có đủ bằng chứng;
   - và người dùng đã trả lời đồng ý với câu hỏi kiểm tra thông tin hiện tại.
4. Trước khi người dùng đồng ý, hệ thống vẫn trả thông tin local đã duyệt và gắn nhãn đây
   là dữ liệu trong corpus. Không âm thầm gọi web.
5. Kết quả MCP phải có schema chặt chẽ, tối thiểu gồm:
   `status`, `procedure_id`, `field`, `value`, `source_url`, `source_title`,
   `jurisdiction`, `checked_at` và `retrieval_note`.
6. Không tìm thấy, timeout, sai schema, khác địa phương hoặc nguồn không được phép thì
   fail-safe về corpus local; không đoán và không ghi đè dữ liệu local.
7. Kết quả thời gian thực chỉ được hiển thị trực tiếp. Muốn đưa vào registry `PUBLISHED`
   vẫn phải qua luồng review hiện có.

### Câu xác nhận gợi ý

> Theo nguồn nội bộ đã duyệt, thông tin hiện có là: ... Thời gian hoặc nơi tiếp nhận có thể
> đã thay đổi. Bạn có muốn mình kiểm tra thông tin hiện tại trên Cổng Dịch vụ công Quốc gia không?

### Test bắt buộc

- Không gọi MCP khi người dùng chưa đồng ý.
- Gọi đúng một lần khi người dùng đồng ý trong lượt kế tiếp.
- Giữ đúng `procedure_id`, `field` và địa phương qua hội thoại nhiều lượt.
- Từ chối URL ngoài allowlist và kết quả khác địa phương.
- Timeout/sai schema/không tìm thấy phải quay về local an toàn.
- Phản hồi thành công phải có URL nguồn và `checked_at`.
- Tool thời gian thực không được tự tạo snapshot `PUBLISHED`.

### Điều kiện bàn giao

- Test mới pass; test G5 cũ không regress.
- Có hướng dẫn chạy local và các biến môi trường mới trong `.env.example`.
- Có ít nhất ba bản ghi demo: thành công, không tìm thấy và nguồn sai địa phương.
- Pull Request mô tả rõ giới hạn: đây là tra cứu hỗ trợ, chưa phải xác nhận pháp lý.

## 3. Phan Văn Tú — từ điển từ đồng nghĩa cho 38 thủ tục

### Mục đích

Từ điển giúp normalize và tạo ứng viên cho bộ phân loại/retrieval. Từ điển **không được tự
quyết định thủ tục chỉ từ một từ chung chung** như “đăng ký”, “hỗ trợ”, “giấy”, “mất” hoặc
“trợ cấp”.

### Branch và đầu ra

- Branch đề nghị: `data/tu-procedure-dictionary`.
- Tạo file: `data/demo_public/procedure_dictionary.json` nếu nội dung hoàn toàn công khai;
  nếu được trích từ workbook nội bộ thì chỉ nộp schema và bản đã được duyệt, không commit
  nguyên văn dữ liệu riêng tư.
- Tạo tài liệu nguồn/review: `docs/giai-doan-5/procedure-dictionary-review.md`.

Mỗi một trong 38 thủ tục có một object theo cấu trúc:

```json
{
  "procedure_id": "id-on-dinh-cua-he-thong",
  "canonical_name": "Tên thủ tục chuẩn",
  "aliases": ["tên rút gọn", "cách gọi tương đương"],
  "situation_phrases": ["cách người dân thường mô tả tình huống"],
  "distinctive_terms": ["cụm từ đủ đặc trưng"],
  "required_qualifiers": ["từ cần có nếu alias dễ nhập nhằng"],
  "excluded_phrases": ["cụm dễ dẫn sang thủ tục khác"],
  "common_typos": {"từ sai": "từ đúng"},
  "confusable_with": ["procedure_id-khac"],
  "source": "nguồn dùng để xác lập tên chuẩn",
  "review_status": "REVIEWED"
}
```

### Quy tắc biên soạn

1. `canonical_name` và `procedure_id` phải khớp catalog đang chạy; không tự đổi ID.
2. Ưu tiên cụm từ người dân thật sự dùng, ví dụ cách nói theo hoàn cảnh, nhưng không thêm
   suy diễn làm thay đổi ý nghĩa pháp lý.
3. Alias chung chung phải đi kèm `required_qualifiers` hoặc chỉ dùng để tăng điểm ứng viên,
   không dùng làm exact match.
4. Với các cặp gần nhau, ghi rõ `confusable_with` và `excluded_phrases`.
5. Typo chỉ sửa khi ánh xạ có một nghĩa rõ ràng; không sửa một từ tiếng Việt hợp lệ thành
   thuật ngữ khác chỉ vì gần về ký tự.
6. Không nhét thời gian, lệ phí, nơi nộp hay thành phần hồ sơ vào alias của tên thủ tục.
7. Mỗi entry phải được một thành viên khác review trước khi đặt `REVIEWED`.

### Kiểm tra bắt buộc

- Đủ đúng 38 `procedure_id`, không trùng ID và không trùng alias sau khi bỏ dấu/lowercase.
- Mỗi thủ tục có tối thiểu hai alias/cách nói và hai câu tình huống, trừ khi có giải thích.
- Có danh sách các cặp dễ nhầm và câu negative test cho từng cặp.
- Chạy thử cả câu tên đầy đủ, câu rút gọn, câu tình huống, typo và câu chuyển chủ đề.
- Không làm giảm các test khóa procedure/context hiện có.

### Điều kiện bàn giao

- JSON hợp lệ, UTF-8, có script validator hoặc unit test.
- Có bảng coverage 38/38 và danh sách entry còn cần mentor xác nhận.
- Pull Request chỉ chứa từ điển, validator/test và tài liệu review; không sửa policy/model.

## 4. Cách ghép hai phần sau khi hoàn thành

1. Merge từ điển trước và chạy regression intent/context.
2. Merge MCP sau, mặc định tắt bằng feature flag.
3. Chạy bộ test hội thoại có đổi thủ tục, câu hỏi ngắn nối tiếp và trường thời gian/nơi nộp.
4. Chỉ bật MCP trong demo sau khi xác nhận consent, allowlist, citation và fallback đều pass.
5. Đo riêng ba nhóm: độ đúng chọn thủ tục, độ đúng trường và tỷ lệ tra cứu MCP hợp lệ;
   không gộp chúng thành một con số duy nhất.

## 5. Phần Hoan giữ để tích hợp

- Chốt contract giữa dictionary, intent/context và MCP.
- Cấp feature flag và biến môi trường; không chia sẻ token thật qua Git.
- Review Pull Request, chạy regression và quyết định bật/tắt trong Docker G5.
- Đối chiếu kết quả với baseline G5 trước khi đưa vào báo cáo hoặc demo.
