# Topic gate độc lập theo lượt hiện tại (16/09/2026)

## Vấn đề và nguyên tắc

Luồng G5 trước đây cho model intent chọn `procedure_id`, rồi Backend truy hồi với thủ tục hiện hành. Hybrid embedding chỉ chạy ở fallback legacy khi chưa có `procedure_id`; nó không giúp trường hợp hội thoại đang ở thủ tục A nhưng người dùng ngầm mở thủ tục B. Ngược lại, cho semantic retrieval tự do ghi đè context sẽ biến tên một *giấy tờ* trong hồ sơ thành yêu cầu làm một *thủ tục* mới.

`backend/app/rag/g5/topic_gate.py` đưa vào một phép đo độc lập trên **lượt người dùng hiện tại** trước khi áp model patch:

1. Ưu tiên nguyên văn tên thủ tục có dấu; dùng tên/mã/alias trong catalog đã duyệt. So khớp full title được ưu tiên hơn biến thể rút gọn của tiêu đề khác.
2. Khi một tiêu đề ngắn nằm trong tiêu đề của biến thể cụ thể, so các từ phân biệt trong lượt hiện tại. Ví dụ, “đăng ký kết hôn” + “nước ngoài” chọn biến thể có yếu tố nước ngoài; cụm bị phủ định không được cộng điểm.
3. Dấu tiếng Việt ở từ khóa pháp lý không bị tùy tiện xem là đồng nghĩa. “Sổ nhà” không đồng nhất với “số nhà”; một ứng viên chỉ giống sau khi bỏ dấu bị chặn nếu hai từ có dấu khác nhau. Câu không dấu vẫn có thể được truy hồi, nhưng cần đánh giá độ chính xác riêng.
4. Với yêu cầu mở thủ tục mới mà exact không nhận diện, embedding/BM25 hiện có được dùng như **ứng viên**, chỉ SWITCH khi score ≥ 0,70, lexical ≥ 0,35, dense ≥ 0,55 và router đã đạt ngưỡng margin nội bộ. Đây là ngưỡng bảo thủ ban đầu, **chưa tối ưu trên holdout**.
5. Nếu đã có thủ tục A nhưng người dùng yêu cầu thủ tục mới không xác định chắc, trả câu hỏi làm rõ và xóa các slot/evidence phụ thuộc A. Không trả hồ sơ A cho câu hỏi mới. Nếu câu là kiểm kê giấy tờ còn thiếu của A, giữ A và chặn model đổi nhầm vì tên giấy tờ.

`backend/app/chat.py` gọi gate trong nhánh G5 chính; `backend/app/rag/g5/intent_context.py` giảm state theo kết quả gate. Bộ model intent, answer plan, provenance và corpus không đổi. Không tải mô hình mới hay gửi D2 ra ngoài.

## Phân loại kết quả

| Gate | Backend thực hiện |
| --- | --- |
| `SWITCH` | Kiểm tra candidate thuộc catalog duyệt; đặt `procedure_id` mới với quote nguyên văn câu người dùng, xóa các dữ kiện phụ thuộc thủ tục cũ; các field hỏi trong câu hiện tại vẫn được xử lý. |
| `KEEP` | Không ép model đổi thủ tục; riêng câu kiểm kê giấy tờ hoặc nêu lại thủ tục hiện hành thì chặn một `SWITCH` mâu thuẫn. |
| `CLARIFY` | Không truy hồi; xóa procedure/field/jurisdiction/as_of và episodic memory cũ, đặt `pending_clarification=procedure_id`, hỏi người dùng nói rõ thủ tục. |

## Kiểm thử đã chạy

- 69 test Backend liên quan G3/G5 qua, 1 test skip; Ruff qua trên file sửa.
- Phép kiểm tra 34/34 tên đầy đủ trong corpus duyệt chọn đúng ID tương ứng. Đây là **sanity check tên catalog**, không phải holdout alias/ngôn ngữ tự nhiên.
- API runtime sau rebuild: `đăng ký khai sinh → nộp ở đâu và mất bao lâu` trả lời và grounding thành công; chuỗi `kết hôn nước ngoài → xin cấp sổ nhà → xin cấp số nhà` lần lượt xử lý thủ tục cụ thể, hỏi làm rõ, rồi chọn thủ tục cấp **số** nhà.
- `scripts/evaluate-g5-topic-gate.py` đọc JSONL có nhãn, trả confusion matrix, case ID lỗi và p50/p95 mà không xuất nguyên văn câu hỏi. Suite mở `evaluation/fixtures/g5-topic-gate-opened-regression-v1.jsonl` đạt 7/7 trên corpus duyệt với embedding local; **đây là regression đã thấy**, không phải holdout độc lập.

## Chưa được chứng minh / bước tiếp

Chưa thể gọi đây là hệ thống “tốt nhất” hay claim độ chính xác tổng quát. Cần một holdout độc lập nhiều lượt, có nhãn `KEEP/SWITCH/CLARIFY`, gold procedure/field/evidence; báo cáo false-switch, missed-switch, Recall@k, citation accuracy, p95 latency theo từng nhóm lỗi. Đặc biệt phải thử câu không dấu, lỗi gõ, biến thể thủ tục gần nhau, nhắc giấy tờ của thủ tục khác, và yêu cầu ngoài catalog. Chỉ sau baseline đó mới A/B query rewrite, RRF/reranker và DEk21 so với embedding hiện hành; không đổi nhiều tầng cùng lúc.
