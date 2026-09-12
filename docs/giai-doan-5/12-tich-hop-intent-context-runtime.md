# Tích hợp intent/context vào runtime G5

Cập nhật: **13/09/2026**. Model intent/context đã được nối vào code G5, không thay đổi
stack G3.

## Luồng đã triển khai

```text
User message + state đã lưu + catalog thủ tục
                    ↓
AI Service /internal/v3/intent-context
                    ↓
Qwen3-4B-Instruct-2507 Q8_0 + LoRA r16
                    ↓ JSON KEEP / SET / CLEAR
Backend kiểm schema + candidate + evidence
                    ↓
Reducer đổi/reset state → RetrievalInput → RAG có nguồn
```

- State G4 được chuyển một lần sang `g5-context-state-v1`; đổi corpus tự reset state.
- Procedure chỉ được `SET` nếu có trong catalog đang phục vụ. Evidence phải dùng đúng
  message ID và là đoạn nguyên văn của câu người dùng hiện tại.
- Đổi procedure tự xóa field, địa phương và ngày phụ thuộc trước khi áp dụng patch mới.
- Cùng message ID chỉ được áp dụng một lần. User/conversation/corpus/revision vẫn do
  Backend sở hữu, không giao cho model.
- `GREET`, `OUT_OF_SCOPE` và `RESET` dùng phản hồi policy cố định; không gửi truy vấn vô
  nghĩa vào RAG.
- Nếu intent model timeout hoặc sai contract, G5 ghi log và quay về rule/context G4.
  Có thể tắt fallback để đánh giá riêng model; fallback không được tính là điểm model.

## Cách chạy

Overlay `compose.g5.yaml` thêm service `intent-model` và mount read-only base GGUF cùng
adapter. AI Service chỉ cho phép HTTP đến hostname local trong allowlist và phải bật riêng
quyền D2. Backend health kiểm endpoint intent là local, non-external và cho phép D2 trước
khi nhận stack G5 là sẵn sàng. Tham số cụ thể nằm trong
[runbook](03-runbook-demo.md).

## Bằng chứng hiện tại

- Unit/API: AI Service 75/75 test đạt; toàn bộ Backend 244 test đạt và 1 test được bỏ qua
  theo thiết kế. Test transaction PostgreSQL riêng xác minh direct, follow-up, switch và reset.
- Live provider smoke bằng Qwen3-4B Q8_0 + adapter seed 42 trả đúng procedure `p_birth`,
  field `fees`, JSON và evidence UUID.
- Full Docker có 8 service healthy: Web, Backend, PostgreSQL, AI Service, generation model,
  embedding model, intent model và source service. `/health/rag` xác nhận intent local,
  non-external và đúng model `Qwen3-4B-Intent-r16`.
- Live chat ba lượt đạt: câu đầu chọn đúng thủ tục và field phí; câu follow-up giữ thủ tục,
  chuyển sang thời gian; câu reset xóa context và không gọi RAG. Cả ba lời gọi intent trả
  thành công, không dùng fallback G4; hai câu nghiệp vụ trả evidence đúng field.
- Live switch riêng cũng đạt: context đổi từ fragment phí của khai sinh sang fragment phí
  của kết hôn có yếu tố nước ngoài; không giữ nhầm procedure cũ và không dùng fallback.
- Test đầy đủ đã phát hiện và sửa một hồi quy health: khi cờ G5 tắt, response G3 không còn
  bị thêm field G5. Compose merge, lint và cú pháp PowerShell đều đạt.

Đây là mốc **runtime integrated**, chưa phải nghiệm thu chất lượng. Điểm DEV vẫn dưới
ngưỡng 90%; bước sau là replay toàn DEV, phân tích lỗi và fine-tune vòng dữ liệu tiếp theo
trước một lần TEST kín cuối. Không tạo TEST mới liên tục và không dùng smoke live để thay
cho bộ đánh giá khóa.
