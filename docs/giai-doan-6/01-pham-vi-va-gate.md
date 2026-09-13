# Phạm vi và gate Giai đoạn 6

## Mục tiêu

G6 xây dựng bộ xử lý intent/context dạng hybrid cho trợ lý hành chính: luật xác định chỉ xử lý
tín hiệu chắc chắn, Qwen xử lý câu mơ hồ, còn Backend tiếp tục sở hữu conversation state. G6
không thay đổi nội dung nguồn pháp lý và không dùng điểm intent để tuyên bố câu trả lời đúng pháp luật.

## Các gói công việc

1. Phân loại lỗi V1–V3 đã mở và chuyển thành bất biến kỹ thuật, không sao chép câu TEST vào TRAIN.
2. Hoàn thiện fast path 0-token, model fallback và log lý do định tuyến.
3. Tạo TRAIN/DEV mới theo conversation; tách theo hội thoại, họ cách diễn đạt và thủ tục.
4. So sánh Qwen3-1.7B và Qwen3-4B đã fine-tune theo chất lượng, độ trễ và bộ nhớ.
5. Khóa đúng một candidate, chạy integration/Docker rồi mới tạo một FINAL holdout độc lập.

## Gate trước FINAL

- Schema và semantic: 100%.
- Full-state trên DEV mới: ít nhất 95%.
- Hội thoại đúng trọn chuỗi: ít nhất 90%.
- Field macro-F1: ít nhất 95%.
- Mỗi nhóm direct, follow-up, clarification, correction/switch, reset, scope/date và boundary:
  ít nhất 80%.
- P95 toàn tuyến mục tiêu không quá 3 giây; ca fast path phải không gọi model.
- Không trùng/gần trùng TRAIN–DEV và không dùng raw V1–V3 làm nhãn huấn luyện.

## Điều kiện kết thúc

FINAL chỉ chạy một lần sau khi candidate, prompt, policy, model hash và ngưỡng đã khóa. Nếu FAIL,
kết quả được giữ nguyên và G6 đóng ở trạng thái không đạt; không tạo TEST nối tiếp để đuổi điểm.

