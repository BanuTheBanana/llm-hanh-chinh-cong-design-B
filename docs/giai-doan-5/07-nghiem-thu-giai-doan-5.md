# Nghiệm thu Giai đoạn 5

Cập nhật kỹ thuật: **13/09/2026**.

## Kết luận

**Chưa đóng nghiệm thu chất lượng G5.** Hệ thống đã chạy end-to-end và phần chức năng đã
hoàn thiện trên demo10, nhưng candidate intent/context không qua toàn bộ gate TEST kín đã khóa.

Kết quả TEST một lần trên 20 hội thoại, 60 lượt:

- Schema và semantic: 100%.
- Dialogue act và topic action: 95%.
- Joint state: 96,67%; full-state theo lượt: 90%.
- Field macro-F1: 98,04%.
- Hội thoại đúng trọn chuỗi: 15/20, tương đương 75%, dưới ngưỡng 90%.
- Clarification và correction/switch cùng đạt 66,67%, dưới ngưỡng nhóm 70%.

TEST này đã mở và chỉ được giữ làm regression. Không sửa theo đáp án rồi chạy lại.

## Phần kỹ thuật đã đạt

- Qwen3-4B + adapter QLoRA r16 phục vụ intent/context bằng llama.cpp local.
- State manager quản lý procedure, field, địa phương, ngày tra cứu, switch, reset và làm rõ.
- RAG Exact/BM25 có dense fallback, AnswerPlan/verifier và citation binding.
- MCP cập nhật nguồn có review, publish, version và rollback.
- Feedback hai trục có ownership, sửa/xóa và lưu provenance; không tự đưa vào fine-tune.
- Backend đạt 247 test, 1 skip; Web đạt 15 test, lint và production build.
- Docker G5 có 8 service healthy; E2E chat, grounding và feedback đã chạy thật.

## Phạm vi chưa đạt

- Chưa đạt độ bền context ở cả chuỗi hội thoại; lỗi tập trung ở clarification và correction/switch.
- Chưa phát hành 38 thủ tục còn lại trong corpus đầy đủ.
- Chưa có đánh giá pháp lý độc lập, RBAC quản trị thật, monitoring/alert, backup/restore và SLA tải lớn.
- Adapter là artifact nội bộ, chưa phải model production.

## Quyết định

Giữ candidate hiện tại làm **G5 internal development runtime**, không gắn nhãn accepted release.
Vòng cải thiện tiếp theo chỉ dùng TRAIN/DEV mới cho các hành vi hội thoại khó. Khi candidate mới
được khóa, Hoan tạo một holdout độc lập mới và chỉ chấm một lần; không tạo TEST sau từng lỗi.
