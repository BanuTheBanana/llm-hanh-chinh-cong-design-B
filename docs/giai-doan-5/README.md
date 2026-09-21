# Giai đoạn 5 – fine-tune, intent/context và feedback

> Cập nhật 14/09/2026: grounded answer Qwen3-1.7B full-corpus đã được fine-tune,
> xuất GGUF và tích hợp vào runtime. Qwen3-4B intent/context vẫn là adapter riêng. Policy v3 đạt
> 100% full-state trên DEV, nhưng FINAL V3 độc lập cuối chỉ đạt 81,67% full-state và
> 65% hội thoại trọn chuỗi. G5 hoàn tất phần triển khai kỹ thuật nhưng không đạt
> nghiệm thu chất lượng intent/context.

G5 nâng hệ thống cơ bản thành bản thử nghiệm nội bộ trên 34 thủ tục đã duyệt. Hệ thống
vẫn lấy nguồn làm căn cứ, từ chối khi thiếu nguồn và không đưa dữ liệu công ty lên Git.

## Kết quả hiện tại

- Phạm vi: 34 thủ tục, 34 nguồn, 139 fragment đã duyệt.
- Model trả lời: Qwen3-1.7B Q8_0 + adapter full-corpus QLoRA r16. Model intent/context:
  Qwen3-4B Q8_0 + adapter QLoRA r16 riêng.
- Truy xuất: Exact/BM25 là tuyến chính, Qwen3 Embedding là fallback có kiểm soát.
- Nguồn cập nhật qua MCP, có review, publish, version và rollback.
- Context nhiều lượt được lưu trong PostgreSQL theo conversation.
- Người dùng có thể đánh giá hai trục phù hợp và hài lòng, kèm lý do; được sửa hoặc xóa.
- Docker G5 gồm 8 service tại `http://localhost:3005`.

Trạng thái chính xác là **runtime full-corpus đã tích hợp, acceptance intent/context kín trước đó
không đạt ngưỡng**. Đây không phải chứng nhận độ đúng pháp lý và chưa phải production.

## Tài liệu

- [24 - Guarded direct evidence sau intent/context](24-guarded-direct-evidence.md)
- [22 - Nâng cấp intent/context policy v8-v9 theo hướng lightweight](22-nang-cap-context-intent-policy-v8.md)
- [21 - Hồ sơ kỹ thuật chi tiết hệ thống hiện tại](21-ho-so-ky-thuat-he-thong-hien-tai.md)
- [20 - Xử lý tình huống thực tế nhiều ý theo hướng lightweight](20-xu-ly-tinh-huong-thuc-te-lightweight.md)

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
12. [Biên bản sẵn sàng fine-tune full corpus](15-san-sang-finetune-full-corpus.md)
13. [Kết quả fine-tune full corpus](16-ket-qua-finetune-full-corpus.md)
14. [Runbook chạy đêm so sánh model lightweight](17-runbook-chay-dem-lightweight.md)
15. [Kết quả so sánh model lightweight](18-ket-qua-so-sanh-lightweight-full-corpus.md)
16. [Biên bản tích hợp runtime full corpus](19-tich-hop-runtime-full-corpus.md)
17. [Hồ sơ kỹ thuật chi tiết hệ thống hiện tại](21-ho-so-ky-thuat-he-thong-hien-tai.md)
18. [Nâng cấp intent/context policy v8-v9 theo hướng lightweight](22-nang-cap-context-intent-policy-v8.md)
19. [Guarded direct evidence sau intent/context](24-guarded-direct-evidence.md)
