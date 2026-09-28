# Phạm vi và phần đã thực hiện của G5

Ngày chốt: **12/09/2026**.

## 1. Phạm vi sau audit

Audit không cho phép mở rộng corpus chỉ để đủ số lượng. Kết quả thực tế:

| Bộ dữ liệu | Nguồn | Thủ tục | Fragment | Quyết định |
|---|---:|---:|---:|---|
| Demo đã duyệt | 10 | 10 | 49 | Được phục vụ trong G5 |
| Corpus đầy đủ | 42 | 38 | 202 | BLOCKED; chưa thủ tục nào đủ điều kiện phát hành |

Corpus đầy đủ còn 34 thủ tục chờ review và 4 thủ tục có conflict/quarantine. Vì vậy G5
giữ nguyên demo10 thay cho mục tiêu dự kiến 20–30 thủ tục. Đây là quyết định chất lượng,
không phải thiếu bước triển khai.

## 2. Dữ liệu huấn luyện không rò rỉ TEST

Pipeline G5 chỉ nhận `scenario_dev.jsonl` đã duyệt. Từ 62 scenario có đáp án, pipeline
chia theo `procedure_id`, sau đó mới tạo biến thể thứ tự evidence:

| Split | Scenario gốc độc lập | Thủ tục | Dòng đã render |
|---|---:|---:|---:|
| TRAIN | 52 | 6 | 208 |
| VALIDATION | 10 | 2 | 40 |

Bốn biến thể của một scenario không được tính là bốn dữ kiện độc lập. TRAIN và
VALIDATION không chung thủ tục. TEST_V2/TEST_V3 không được đưa vào bundle, prompt huấn
luyện hoặc index phục vụ. Script huấn luyện kiểm tra lại schema, hash và split ngay
trước khi nạp model.

## 3. Năng lực đã bổ sung

Luồng trả lời của G5:

```text
Người dùng → Web → Backend → context/intent → Exact/BM25
                                      └─ chưa xác định → embedding fallback
                              → evidence + bản nguồn MCP đã publish
                              → AnswerPlan → Qwen → verifier/fallback
                              → câu trả lời + checklist + citation + version
```

- Sửa quy tắc hội thoại tổng quát để câu nối tiếp dài vẫn giữ đúng thủ tục và field;
  dữ kiện chỉ kế thừa trong cùng conversation.
- Tích hợp Qwen3 Embedding 0.6B local. Tuyến exact/context vẫn được ưu tiên; lỗi hoặc kết
  quả dense không chắc chắn thì quay về cơ chế cũ, không làm hỏng endpoint.
- Thêm Source Service dùng MCP với đúng hai tool: đọc bản cập nhật đã publish và quản lý
  vòng đời `STAGE → APPROVE → PUBLISH → ROLLBACK/REJECT`.
- Mỗi snapshot bất biến, có version, SHA-256, người duyệt và mốc thời gian. Backend tự
  kiểm hash, field, thủ tục, trạng thái, khoảng hiệu lực trước khi thay evidence.
- Bản chưa duyệt, bản tương lai, bản sai hash hoặc lỗi MCP không được dùng. Hệ thống quay
  về corpus đã duyệt đang mount read-only.
- Web hiển thị checklist đã kiểm chứng, nguồn, phiên bản tri thức và thời điểm nguồn được
  duyệt; PostgreSQL tiếp tục lưu history/context.

MCP hiện kết nối **registry nội bộ đã review**, chưa kết nối trực tiếp cổng dữ liệu nhà
nước. Kịch bản cập nhật trong smoke là dữ liệu kiểm thử cơ chế, không phải nguồn realtime.
