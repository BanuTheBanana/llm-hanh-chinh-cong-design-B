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
