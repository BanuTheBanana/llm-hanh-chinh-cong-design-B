# Xử lý tình huống thực tế nhiều ý theo hướng lightweight

Ngày kiểm tra: 15/09/2026

## 1. Vấn đề đã phát hiện

Câu hỏi thực tế có địa điểm và năm yêu cầu cùng lúc từng bị từ chối dù đã nêu rõ
thủ tục. Trace cho thấy Qwen intent sinh đủ 384 token ở cả hai lần gọi nhưng vẫn
không hoàn tất contract JSON. Backend phải chạy fallback đơn giản, làm mất thủ tục,
các field cần hỏi và hiểu sai địa chỉ kể trong hoàn cảnh thành bộ lọc jurisdiction.

## 2. Kiến trúc đã áp dụng

Luồng mới dùng chiến lược `deterministic-first, model-last`:

1. Chuẩn hóa câu hỏi và phát hiện tất cả field được hỏi.
2. So khớp duy nhất thủ tục bằng các từ phân biệt, không đếm trùng từ.
3. Nếu câu rõ ràng, tạo intent patch trực tiếp; không gọi Qwen intent.
4. Nếu câu mơ hồ, gọi Qwen với JSON Schema rút gọn và constrained generation.
5. AI Service tự gắn message ID và trích đoạn nguyên văn; model không phải lặp lại
   câu hỏi trong nhiều evidence object.
6. Backend giữ context, lấy một fragment bắt buộc cho mỗi field và tạo AnswerPlan.
7. Verifier kiểm tra toàn bộ nội dung và citation. Nếu Qwen diễn giải sai, hệ thống
   chuyển sang trích xuất evidence an toàn.

Cách này giữ vai trò của model ở phần hiểu ngôn ngữ mơ hồ nhưng chuyển các quyết
định chắc chắn sang code nhỏ, nhanh và kiểm thử được.

## 3. Các lỗi cụ thể đã sửa

- Câu dài có nhiều field không còn chạm trần contract 384 token.
- Phân biệt địa chỉ kể trong hoàn cảnh với câu hỏi về phạm vi pháp lý.
- Nhận đủ hồ sơ, nơi nộp, hình thức nộp, thời gian và lệ phí trong cùng một lượt.
- Sửa nhầm “học cấp 2” thành thủ tục “Hồ sơ cấp số nhà” do đếm trùng từ “số”.
- Không coi “chuyển sang trường khác” trong câu đầu là sửa context cũ.
- Nhận thêm các cách nói tự nhiên như “hồ sơ cần chuẩn bị”, “qua mạng”,
  “tốn khoản nào”, “xử lý trong bao lâu”.
- Không tự chọn một thủ tục khi người dùng nói chưa rõ mình thuộc thủ tục nào.
- Evidence của câu trên 300 ký tự được chọn thành đoạn nguyên văn có liên quan và
  vẫn tuân thủ giới hạn contract.

## 4. Kết quả runtime trên full corpus

Tình huống khai sinh gồm năm yêu cầu:

- Intent: đúng thủ tục và đủ 5/5 field.
- Chi phí intent: 0 input token, 0 output token, khoảng 2 ms.
- End-to-end: trạng thái `ANSWER`, khoảng 1,0 giây.
- Evidence: đúng 5 fragment, mỗi field có fragment ID riêng.

Ba câu dài đã chạy thành công end-to-end:

| Tình huống | Thủ tục | Field | Citation | Trạng thái |
|---|---|---:|---:|---|
| Vừa có con, hỏi toàn bộ thông tin khai sinh | Đăng ký khai sinh | 5/5 | 5 | ANSWER |
| Kết hôn với người nước ngoài | Kết hôn có yếu tố nước ngoài | 5/5 | 5 | ANSWER |
| Học sinh cấp 2 muốn chuyển trường | Chuyển trường THCS | 5/5 | 5 | ANSWER |

Kiểm tra hội thoại nối tiếp trên cùng conversation:

1. Lượt đầu hỏi hồ sơ và thời gian đăng ký khai sinh: đúng 2/2 field, 2 citation.
2. Lượt sau hỏi “Còn lệ phí và hồ sơ cần chuẩn bị thì sao?”: vẫn giữ đúng thủ tục
   khai sinh, đúng 2/2 field và 2 citation.

Web hiện giữ cách hiển thị toàn bộ citation tương ứng với các field được trả lời. Việc gom
nhóm và rút gọn cách trình bày citation chỉ là thay đổi giao diện về sau, không được làm mất
fragment ID hoặc quan hệ field--fragment.

Hai câu cố ý không nêu đủ thủ tục đều giữ `UNRESOLVED` hoặc
`NEED_CLARIFICATION`, không tự chọn nguồn để trả lời.

Với câu phải gọi model, contract rút gọn cho kết quả hợp lệ ngay lần đầu với 92
output token thay vì chạm trần 384 token hai lần như trước.

Sau lần build cuối, 8/8 container G5 đều healthy. AI Service có 115 test qua; Backend có
248 test qua và 1 test được skip khi chạy với PostgreSQL test riêng. Hai request runtime cuối
đều trả HTTP 200 và log không có lỗi provider.

## 5. Giới hạn còn lại

- Full corpus 34 thủ tục không có dữ liệu `steps`, `legal_bases` và
  `applicant_scope`; hệ thống phải từ chối các ý này thay vì bịa.
- Bộ tình huống runtime hiện dùng để khóa lỗi, chưa thay thế TEST kín có reviewer.
- Qwen 4B intent vẫn được nạp cho trường hợp mơ hồ. Cần benchmark với model nhỏ đã
  fine-tune trước khi chốt kiến trúc lightweight cuối cùng.
- Câu trả lời nhiều ý hiện ưu tiên liệt kê đầy đủ và citation đầy đủ; Web sẽ được
  trình bày gọn hơn ở bước UI sau.

## 6. Cơ sở kỹ thuật tham khảo

- llama.cpp hỗ trợ JSON Schema/GBNF để giới hạn output trong lúc sinh:
  https://github.com/ggml-org/llama.cpp/blob/master/grammars/README.md
- Tài liệu llama-server mô tả `response_format` với schema-constrained JSON:
  https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md
- Nghiên cứu về structured generation cho thấy constrained decoding đảm bảo cấu
  trúc nhưng chất lượng ngữ nghĩa vẫn cần policy và validation riêng:
  https://arxiv.org/abs/2501.10868

## 7. Điều kiện nghiệm thu hạng mục

Chỉ chốt khi câu nhiều ý, câu nối tiếp, chuyển chủ đề, câu mơ hồ và câu thiếu dữ
liệu đều chạy regression; câu trả lời phải đúng procedure, đủ field có dữ liệu,
không trộn nguồn, citation khớp fragment và không bịa field còn thiếu.

## 8. Chuẩn hóa lỗi gõ và cách nói tương đương

Đã bổ sung một lớp chuẩn hóa chỉ dùng cho routing; câu gốc của người dùng vẫn được
giữ nguyên để hiển thị và audit. Luồng hiện tại gồm:

1. Chuẩn hóa Unicode, dấu câu và chữ viết tắt đã duyệt.
2. Thay thế một số cụm đồng nghĩa có nghĩa nghiệp vụ rõ ràng, ví dụ `qua mạng` sang
   `trực tuyến`, `chờ bao lâu` sang `thời gian`, `tốn tiền` sang `lệ phí`.
3. Dùng RapidFuzz sửa token theo từ điển nghiệp vụ và tên thủ tục đang có trong
   catalog. Chỉ nhận kết quả khi cùng ký tự đầu, khoảng cách chỉnh sửa nhỏ, điểm đủ
   cao và ứng viên tốt nhất tách biệt rõ với ứng viên thứ hai.
4. Bảo vệ các từ hội thoại thông dụng, số và từ ngắn mơ hồ; nếu không chắc thì giữ
   nguyên và để model hoặc câu hỏi làm rõ xử lý.

Đợt thử đầu đã khóa được các regression quan trọng: không còn sửa `đúng` thành
`đang`, `cơ quan` thành `cơ qua`, `ngữ cảnh` thành `ngữ can`; vẫn nhận được
`khai sih`/`kha sin`, `qua mạng`, `chờ bao lâu` và `tất cả mọi thứ`.

Kết quả kiểm tra sau tích hợp:

- AI Service: 124 test qua, lint qua.
- Backend: 252 test qua, 1 test skip có chủ đích; lint phần liên quan qua.
- Runtime Docker: 8/8 container healthy.
- Chuỗi `khai sih` -> `tất cả mọi thứ`: nhận đúng khai sinh, trả 5 field có dữ
  liệu với 5 citation.
- Chuỗi `khai sinh` -> `nộp qua mạng ... chờ bao lâu`: giữ đúng context, trả hình
  thức nộp và thời gian với 2 citation.

Đây là lớp nhẹ chạy CPU, không nạp thêm LLM. Khi mở rộng, từ điển phải được sinh
từ catalog và lỗi thật đã review; không tự động học mọi phép sửa từ log người dùng.
