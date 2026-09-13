# Giai đoạn 6 – Intent/context bền vững và lightweight

G6 tiếp tục từ kết quả kỹ thuật G5 nhưng mở một chu kỳ chất lượng mới. Mục tiêu là làm context
nhiều lượt ổn định hơn, giảm số lần gọi model và giữ toàn bộ quyết định có thể kiểm tra được.

Trạng thái hiện tại:

- Đã phân tích aggregate lỗi FINAL V3 mà không đưa câu hỏi/gold private lên Git.
- Đã triển khai policy hybrid v4 và fast path 0-token cho yêu cầu chắc chắn.
- 102 AI Service test đã pass.
- V1–V3 đã mở đạt lần lượt 100%, 98,33% và 100% full-state khi dùng policy v4.
- Các số trên chỉ là regression. G6 chưa có FINAL TEST và chưa được nghiệm thu.

Tài liệu:

1. [Phạm vi và gate](01-pham-vi-va-gate.md)
2. [Phân tích lỗi G5](02-phan-tich-loi-g5.md)
3. [Kiến trúc và trạng thái triển khai](03-kien-truc-hybrid-v4.md)

