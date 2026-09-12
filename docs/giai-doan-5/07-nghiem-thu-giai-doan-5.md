# Nghiệm thu Giai đoạn 5

Ngày nghiệm thu kỹ thuật: **12/09/2026**.

## Kết luận

**G5 đạt ở phạm vi limited release nội bộ trên demo10.** Toàn bộ năng lực kỹ thuật đã
được ghép thành một hệ thống chạy thật: Qwen local, truy xuất có dense fallback, hội thoại
nhiều lượt, AnswerPlan/verifier, MCP cập nhật nguồn có review/rollback, checklist trên Web,
PostgreSQL và Docker G5 riêng.

Quyết định này không đổi thành “production-ready” hoặc “đúng pháp lý toàn diện”. G5 chỉ
phục vụ 10 thủ tục đã duyệt. Corpus 38 thủ tục còn BLOCKED; TEST_V3 đã mở chỉ là regression;
chưa có holdout độc lập mới để xác nhận ngưỡng tổng quát hóa ≥90%.

## Gate đã đạt

- Audit khóa đúng phạm vi 10 thủ tục/49 fragment; dữ liệu đầy đủ chưa duyệt không được phục vụ.
- Bundle SFT tách TRAIN/VALIDATION theo thủ tục, khóa hash và xác nhận không dùng TEST.
- Thí nghiệm QLoRA hoàn tất; adapter kém an toàn/tốc độ hơn nên bị loại có căn cứ.
- Giữ Qwen3-1.7B Q8_0 làm model phục vụ nhẹ trên máy đích.
- DEV retrieval 80/80; API multi-turn 16/16; regression TEST_V3 đã mở 40/40.
- Bản cập nhật MCP chỉ được dùng sau review/publish; sai hash, chưa hiệu lực hoặc lỗi tool
  đều quay về corpus gốc; rollback đã qua smoke live.
- Bài tải nhỏ thành công 12/12; toàn bộ 7 container G5 healthy.
- Unit/integration test, lint, build Web và repository hygiene đạt.

## Việc không giả định là đã đạt

- Chưa phát hành 38 thủ tục trong corpus đầy đủ.
- Chưa kết nối feed/API hành chính bên ngoài được cấp quyền; MCP hiện là registry nội bộ.
- Chưa có RBAC quản trị thật, audit database tập trung, monitoring/alert, backup/restore
  production hoặc SLA tải lớn.
- Chưa có đánh giá nghiệp vụ độc lập cuối chặng trên câu hỏi hoàn toàn chưa thấy.
- Adapter QLoRA chỉ là artifact thí nghiệm private, không phải model phát hành.

## Quyết định chuyển giai đoạn

Có thể chuyển sang G6 – sản phẩm thử nghiệm nội bộ – mà không tạo TEST mới sau mỗi lỗi.
Trước khi mở rộng người dùng hoặc corpus, cần reviewer độc lập giữ một holdout mới, duyệt
thêm nguồn và chốt RBAC/giám sát/backup. Các file công ty, bundle SFT, output model và báo
cáo chi tiết tiếp tục nằm ngoài Git.
