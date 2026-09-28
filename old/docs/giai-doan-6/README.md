# Giai đoạn 6 – Intent/context bền vững và lightweight

G6 tiếp tục từ kết quả kỹ thuật G5 nhưng mở một chu kỳ chất lượng mới. Mục tiêu là làm context
nhiều lượt ổn định hơn, giảm số lần gọi model và giữ toàn bộ quyết định có thể kiểm tra được.

Trạng thái cuối: **hoàn tất kỹ thuật, nghiệm thu FAIL**.

- Đã phân tích aggregate lỗi FINAL V3 mà không đưa câu hỏi/gold private lên Git.
- Đã triển khai policy hybrid v4 và fast path 0-token cho yêu cầu chắc chắn.
- 107 AI Service test và Ruff đã pass.
- V1–V3 đã mở đạt lần lượt 100%, 98,33% và 100% full-state khi dùng policy v4.
- Đã fine-tune lại Qwen3.5-2B trên 252 mẫu TRAIN và so sánh bốn cấu hình cùng một DEV mới.
- Qwen3-4B + LoRA hard-v2 là cấu hình duy nhất qua toàn bộ gate nên được chọn để kiểm thử tích hợp.
- FINAL độc lập duy nhất đạt 83,33% full-state, 60% hội thoại và 90,74% field macro-F1;
  thấp hơn gate đã khóa. Không chạy lại hoặc tinh chỉnh tiếp trong G6.

Tài liệu:

1. [Phạm vi và gate](01-pham-vi-va-gate.md)
2. [Phân tích lỗi G5](02-phan-tich-loi-g5.md)
3. [Kiến trúc và trạng thái triển khai](03-kien-truc-hybrid-v4.md)
4. [Kết quả chọn model](04-ket-qua-chon-model.md)
5. [Nghiệm thu Giai đoạn 6](05-nghiem-thu-giai-doan-6.md)
