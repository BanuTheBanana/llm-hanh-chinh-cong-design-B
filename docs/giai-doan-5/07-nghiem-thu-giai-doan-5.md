# Nghiệm thu Giai đoạn 5

Cập nhật kỹ thuật: **13/09/2026**.

## Kết luận

**Chưa đóng nghiệm thu chất lượng G5.** Hệ thống đã chạy end-to-end và phần chức năng đã
hoàn thiện trên demo10, nhưng candidate intent/context không qua toàn bộ gate TEST kín đã khóa.

Kết quả TEST V1 một lần trên 20 hội thoại, 60 lượt:

- Schema và semantic: 100%.
- Dialogue act và topic action: 95%.
- Joint state: 96,67%; full-state theo lượt: 90%.
- Field macro-F1: 98,04%.
- Hội thoại đúng trọn chuỗi: 15/20, tương đương 75%, dưới ngưỡng 90%.
- Clarification và correction/switch cùng đạt 66,67%, dưới ngưỡng nhóm 70%.

TEST này đã mở và chỉ được giữ làm regression. Không sửa theo đáp án rồi chạy lại.

Policy v2 sau đó sửa được lỗi V1 trên regression đã mở, nhưng **FINAL TEST V2 độc lập vẫn
FAIL**. V2 đạt schema/semantic 100%, full-state 73,33%, field macro-F1 74,88% và chỉ
12/20 hội thoại đúng trọn chuỗi. Các nhóm yếu là boundary 40%, clarification 42,86% và
correction/switch 55,56%. Kết quả này cho thấy candidate chưa tổng quát hóa đủ với cách diễn
đạt tự nhiên. V2 cũng đã mở và tuyệt đối không được chạy lại để đổi kết luận.

Sau vòng sửa bất biến tổng quát, policy v3 đạt 100% full-state trên DEV và vượt gate trên hai
regression đã mở. Candidate được đóng băng rồi chạy **FINAL TEST V3 độc lập cuối đúng một lần**.
V3 đạt schema/semantic 100%, dialogue act 93,33%, topic action 96,67%, full-state 81,67%,
field macro-F1 93,12% và 13/20 hội thoại đúng trọn chuỗi (65%). Clarification đạt 33,33%,
scope/date 50% và follow-up 58,33%, đều dưới ngưỡng nhóm 70%. Do đó kết luận cuối G5 vẫn là
**FAIL acceptance intent/context**. V3 không được chạy lại hoặc dùng để điều chỉnh candidate G5.

## Phần kỹ thuật đã đạt

- Qwen3-4B + adapter QLoRA r16 phục vụ intent/context bằng llama.cpp local.
- State manager quản lý procedure, field, địa phương, ngày tra cứu, switch, reset và làm rõ.
- RAG Exact/BM25 có dense fallback, AnswerPlan/verifier và citation binding.
- MCP cập nhật nguồn có review, publish, version và rollback.
- Feedback hai trục có ownership, sửa/xóa và lưu provenance; không tự đưa vào fine-tune.
- Backend đạt 247 test, 1 skip; Web đạt 15 test, lint và production build.
- Docker G5 có 8 service healthy; E2E chat, grounding và feedback đã chạy thật.

## Phạm vi chưa đạt

- Chưa đạt độ bền context ở cả chuỗi hội thoại; lỗi tập trung ở boundary, clarification,
  correction/switch, nhận diện field và chuẩn hóa địa danh.
- Chưa phát hành 38 thủ tục còn lại trong corpus đầy đủ.
- Chưa có đánh giá pháp lý độc lập, RBAC quản trị thật, monitoring/alert, backup/restore và SLA tải lớn.
- Adapter là artifact nội bộ, chưa phải model production.

## Quyết định

Đóng G5 ở trạng thái **hoàn tất triển khai kỹ thuật nhưng không đạt nghiệm thu chất lượng
intent/context**. Giữ candidate hiện tại làm internal development runtime, không gắn nhãn
accepted release. Không tạo thêm holdout hoặc tinh chỉnh tiếp trong G5. Sai số V1–V3 chỉ được
chuyển thành backlog nghiên cứu cho giai đoạn sau; một chu kỳ mới phải có TRAIN/DEV, candidate
và protocol đánh giá mới được duyệt độc lập trước khi tạo TEST.
