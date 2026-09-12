# Giai đoạn 5 – chuyên biệt hóa và cập nhật nguồn

> Ưu tiên mới theo mentor (12/09/2026): [kế hoạch fine-tune, intent và context trong
> 5 ngày làm việc](08-ke-hoach-intent-context-finetune.md). Yêu cầu model đã fine-tune
> thực sự xử lý intent/context chưa được nghiệm thu; kết quả demo10 dưới đây là mốc trước đó.

G5 nâng hệ thống cơ bản thành một bản **limited release nội bộ** trên đúng phạm vi dữ liệu
đã được duyệt. Hệ thống vẫn ưu tiên độ tin cậy: dùng nguồn làm căn cứ, từ chối khi thiếu
nguồn và không đưa dữ liệu công ty lên Git.

## Kết quả chốt

- Phạm vi phục vụ: 10 thủ tục, 10 nguồn, 49 fragment đã duyệt.
- Model phục vụ: Qwen3-1.7B Q8_0 gốc; adapter QLoRA đã thử nhưng không được triển khai.
- Truy xuất: Exact/BM25 là tuyến chính, Qwen3 Embedding là fallback có kiểm soát.
- Nguồn cập nhật: registry nội bộ qua MCP, có review, publish, version và rollback.
- Giao diện: hiển thị checklist, citation, phiên bản tri thức và thời điểm duyệt nguồn.
- Docker: một stack G5 riêng tại `http://localhost:3005`.

Trạng thái chính xác là **hoàn thành phạm vi kỹ thuật G5 trên demo10**. Đây chưa phải
chứng nhận độ đúng pháp lý, chưa phục vụ toàn bộ corpus và chưa phải production release.

## Tài liệu

1. [Phạm vi và phần đã triển khai](01-pham-vi-va-thuc-hien.md)
2. [Kết quả thực nghiệm và quyết định model](02-ket-qua-thuc-nghiem.md)
3. [Runbook Docker và demo](03-runbook-demo.md)
4. [Biên bản nghiệm thu G5](07-nghiem-thu-giai-doan-5.md)
5. [Kế hoạch theo yêu cầu mentor](08-ke-hoach-intent-context-finetune.md)
6. [Protocol model và intent/context](09-protocol-model-intent-context.md)
7. [Cơ sở nghiên cứu](10-co-so-nghien-cuu-intent-context.md)
8. [Kết quả chọn model intent/context](11-ket-qua-chon-model-intent-context.md)
