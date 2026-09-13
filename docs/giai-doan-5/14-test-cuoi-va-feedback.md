# TEST kín cuối và feedback G5

## 1. TEST intent/context

Candidate được khóa trước khi chạy: Qwen3-4B-Instruct-2507 Q8_0, adapter hard-v2-r16,
prompt v2 và policy v1. Bộ TEST private do leader giữ gồm 20 hội thoại × 3 lượt, không chứa
dữ liệu công ty và không có câu trùng/gần trùng TRAIN–DEV ở ngưỡng 0,90.

TEST chỉ chạy một lần. Kết quả full-state theo lượt đạt đúng 90%, nhưng chỉ 15/20 hội thoại
đúng toàn bộ chuỗi. Gate cuối vì vậy là **FAIL**. Kết quả không được diễn giải thành độ chính
xác pháp lý của câu trả lời.

Số aggregate và fingerprint nằm ở
[`evaluation/baselines/g5-intent-context-final-result-20260913.json`](../../evaluation/baselines/g5-intent-context-final-result-20260913.json).
Nội dung câu hỏi, gold label và raw output tiếp tục nằm ngoài Git.

Sau khi TEST trở thành regression đã mở, policy v2 được xây dựng bằng các bất biến tổng quát:
nhắc lại cùng procedure không phải switch, câu sửa/chuyển có ưu tiên cao hơn nhãn chào nhầm,
và giá trị scope đầu tiên không phải correction. Policy v2 giữ DEV ở 95% full-state; trên
regression đã mở đạt 98,33% theo lượt và 19/20 hội thoại. Số này chỉ dùng kiểm tra lỗi cũ,
không thay đổi kết luận FAIL và không thay cho holdout độc lập tiếp theo.

Candidate policy v2 tiếp tục được khóa trước khi chạy FINAL TEST V2 độc lập. Bộ V2 vẫn gồm
20 hội thoại × 3 lượt, loại trừ cả TRAIN, DEV và holdout V1. Lần chạy duy nhất đạt 73,33%
full-state, 74,88% field macro-F1 và 60% hội thoại đúng trọn chuỗi, nên gate tiếp tục **FAIL**.
V2 cho thấy model còn nhạy với diễn đạt tự nhiên của địa danh, câu làm rõ, câu chuyển chủ đề
và câu chưa đủ thông tin. Aggregate công khai nằm ở
[`evaluation/baselines/g5-intent-context-final-v2-result-20260913.json`](../../evaluation/baselines/g5-intent-context-final-v2-result-20260913.json);
raw output và gold label vẫn nằm ngoài Git.

Sau khi phân loại lỗi của cả hai TEST đã mở, policy v3 được kiểm tra lại trên DEV, V1 và V2.
Ba tập đều vượt ngưỡng đã khóa; riêng V2 regression đạt 96,67% full-state và 90% hội thoại.
Candidate v3 vì vậy đủ điều kiện bước vào **một holdout độc lập cuối**, nhưng chưa được gọi là
accepted cho đến khi holdout đó chạy xong. Chi tiết aggregate không chứa câu hỏi private nằm ở
[`evaluation/baselines/g5-intent-context-policy-v3-20260913.json`](../../evaluation/baselines/g5-intent-context-policy-v3-20260913.json).

Holdout V3 độc lập cuối đã chạy đúng một lần trên 20 hội thoại, 60 lượt và loại trừ TRAIN, DEV,
V1 cùng V2. Schema/semantic đạt 100%, dialogue act 93,33%, topic action 96,67%, nhưng full-state
chỉ đạt 81,67%, field macro-F1 93,12% và 13/20 hội thoại đúng trọn chuỗi (65%). Ba nhóm dưới gate
là clarification 33,33%, scope/date 50% và follow-up 58,33%. Gate cuối là **FAIL**. V3 đã được mở,
không chạy lại và không dùng để tinh chỉnh G5. Aggregate công khai tại
[`evaluation/baselines/g5-intent-context-final-v3-result-20260913.json`](../../evaluation/baselines/g5-intent-context-final-v3-result-20260913.json);
câu hỏi, gold và raw output vẫn ở ngoài Git.

## 2. Feedback người dùng

Mỗi câu trả lời hoàn tất ở Web G5 có hai đánh giá độc lập:

- Phù hợp / không phù hợp.
- Hài lòng / chưa hài lòng.

Người dùng có thể nhập lý do tối đa 1.000 ký tự, cập nhật hoặc xóa đánh giá của mình.
Backend chỉ cho chủ conversation đánh giá assistant message đã hoàn tất. Bản ghi giữ liên kết
message/user cùng snapshot provider, model, corpus version và prompt version nếu có.

Feedback chỉ đi vào dữ liệu review. Nó không tự trở thành nhãn pháp lý và không tự được đưa
vào fine-tune.

## 3. Xác minh

- Backend: 247 passed, 1 skipped trên PostgreSQL 16 tách biệt.
- Web: 15 passed; ESLint và production build đạt.
- Docker: migration `0004_g5_feedback` và 8 service healthy.
- E2E: đăng nhập, tạo conversation, Qwen/RAG trả `ANSWER` có nguồn, lưu/list/xóa feedback thành công.
