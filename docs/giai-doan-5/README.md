# Giai đoạn 5 – fine-tune, intent/context và feedback

> Cập nhật 13/09/2026: Qwen3-4B đã được fine-tune và tích hợp thật. Pipeline DEV đạt
> full-state 95%. TEST kín cuối đạt 90% theo lượt nhưng **chưa qua gate hội thoại**;
> vì vậy G5 đã hoàn thiện phần triển khai kỹ thuật nhưng chưa được nghiệm thu chất lượng cuối.

G5 nâng hệ thống cơ bản thành bản thử nghiệm nội bộ trên đúng 10 thủ tục đã duyệt. Hệ thống
vẫn lấy nguồn làm căn cứ, từ chối khi thiếu nguồn và không đưa dữ liệu công ty lên Git.

## Kết quả hiện tại

- Phạm vi: 10 thủ tục, 10 nguồn, 49 fragment đã duyệt.
- Model trả lời: Qwen3-1.7B Q8_0. Model intent/context: Qwen3-4B Q8_0 + adapter QLoRA r16.
- Truy xuất: Exact/BM25 là tuyến chính, Qwen3 Embedding là fallback có kiểm soát.
- Nguồn cập nhật qua MCP, có review, publish, version và rollback.
- Context nhiều lượt được lưu trong PostgreSQL theo conversation.
- Người dùng có thể đánh giá hai trục phù hợp và hài lòng, kèm lý do; được sửa hoặc xóa.
- Docker G5 gồm 8 service tại `http://localhost:3005`.

Trạng thái chính xác là **runtime G5 đã hoàn thiện, acceptance intent/context chưa đạt**.
Đây không phải chứng nhận độ đúng pháp lý, chưa phục vụ toàn bộ corpus và chưa phải production.

## Tài liệu

1. [Phạm vi và phần đã triển khai](01-pham-vi-va-thuc-hien.md)
2. [Kết quả thực nghiệm và quyết định model](02-ket-qua-thuc-nghiem.md)
3. [Runbook Docker và demo](03-runbook-demo.md)
4. [Biên bản nghiệm thu G5](07-nghiem-thu-giai-doan-5.md)
5. [Kế hoạch intent/context/fine-tune](08-ke-hoach-intent-context-finetune.md)
6. [Protocol đánh giá model](09-protocol-model-intent-context.md)
7. [Cơ sở nghiên cứu](10-co-so-nghien-cuu-intent-context.md)
8. [Kết quả chọn model](11-ket-qua-chon-model-intent-context.md)
9. [Tích hợp intent/context vào runtime](12-tich-hop-intent-context-runtime.md)
10. [Vòng nâng chất lượng intent/context](13-nang-chat-luong-intent-context.md)
11. [TEST kín và feedback](14-test-cuoi-va-feedback.md)
