# Guarded direct evidence sau intent/context

## Quyết định kiến trúc

Runtime dùng `G8_EVIDENCE_MODE=guarded_direct`. Đây không phải bỏ toàn bộ RAG.
Hệ thống tách hai bài toán:

1. **Xác định procedure và field**: ưu tiên tên/alias chính xác, conversation state và
   luật current-turn; hybrid lexical+dense chỉ xác minh hoặc tìm procedure khi chưa chắc.
2. **Lấy evidence**: khi procedure và field đã được xác minh, đọc thẳng các fragment từ
   `procedure.field_evidence`; không xếp hạng lại trên toàn corpus.

Nếu procedure chưa rõ, field chưa rõ, nguồn thiếu, địa bàn không khớp hoặc nguồn hết hiệu
lực, hệ thống dừng ở `NEED_CLARIFICATION`/`INSUFFICIENT_DATA`. AnswerPlan, citation và
verifier vẫn bắt buộc ở cả hai nhánh.

## Luồng quyết định

```text
User turn + conversation state
        |
        v
Intent/context + deterministic current-turn guards
        |
        +-- procedure/field tin cậy --> direct catalog --> AnswerPlan --> verifier
        |
        +-- procedure chưa chắc ----> hybrid verifier
                                      |-- đủ ngưỡng --> direct catalog
                                      `-- không đủ ---> hỏi làm rõ
```

Các tín hiệu được coi là procedure tin cậy:

- bộ lọc procedure do backend cung cấp;
- tên/alias catalog xuất hiện rõ trong lượt hiện tại;
- hybrid đồng thuận ở ngưỡng cao;
- follow-up giữ nguyên procedure đã xác minh trong conversation state.

Một procedure chỉ do model tự đoán nhưng chưa được topic gate xác minh không được đi vào
direct catalog.

Hybrid switch yêu cầu đồng thời điểm tổng tối thiểu `0,70`, lexical tối thiểu `0,35` và
dense tối thiểu `0,50`. Dense không được dùng như một veto tuyệt đối khi lexical đã rất
mạnh; điều này hỗ trợ cách nói rút gọn như “tạm ngừng hộ kinh doanh” nhưng vẫn chặn ứng
viên chỉ gần nghĩa mà không có bằng chứng từ khóa.

## Bảo vệ context

- Câu sửa như “bỏ X, thực sự cần Y” chỉ đối chiếu phần mục tiêu dương `Y`.
- Từ field ngắn như “hồ sơ”, “lệ phí” chỉ cập nhật field và giữ procedure hiện tại.
- Nếu chưa có procedure mà người dùng chỉ trả lời “hồ sơ”, hệ thống hỏi lại thay vì chọn
  thủ tục có chữ “HỒ SƠ” trong tên.
- Field cue có độ chính xác cao ở lượt hiện tại được ưu tiên hơn danh sách field do model
  suy đoán.
- Khi đổi procedure, các field, địa bàn, mốc thời gian và episodic memory cũ bị xóa.

## Cấu hình và rollback

Ba chế độ được giữ để đo ablation và rollback:

- `hybrid_retrieval`: cách cũ, luôn truy xuất/xếp hạng evidence;
- `direct_catalog`: ép đọc trực tiếp, chỉ dùng cho thử nghiệm có input đã khóa;
- `guarded_direct`: chế độ runtime mặc định của G5 hiện tại.

Đổi `G8_EVIDENCE_MODE=hybrid_retrieval` và restart backend để rollback mà không đổi model,
dataset hay schema lưu trữ.

Adapter intent mặc định của `scripts/demo-g5.ps1` là
`training/output/qwen3-4b-intent-full38-v1-r16/adapter-f16.gguf`.

## Kiểm thử

Regression bắt buộc gồm:

- direct catalog không phụ thuộc độ giống câu hỏi và không lộ locator nội bộ;
- thiếu procedure/field hoặc fragment thì fail closed;
- correction có cả tên cũ và tên mới chọn đúng tên mới;
- follow-up field giữ procedure hiện tại;
- procedure chưa xác minh vẫn đi hybrid;
- procedure đã xác minh và field rõ mới chuyển sang direct catalog.

Bộ TEST 60 ca đã được mở chỉ còn giá trị regression, không được trình bày như TEST độc lập
hoặc kết quả nghiệm thu cuối.
