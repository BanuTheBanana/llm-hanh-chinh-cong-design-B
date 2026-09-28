# Phân công Giai đoạn 4 – đúng ý, đúng nguồn và hội thoại ngắn

| Trường | Nội dung |
|---|---|
| Ngày giao | 10/09/2026 |
| Baseline | `g3-v1.0.0` sau khi phát hành trên `main` |
| Phạm vi đầu | Corpus `demo10`, Qwen3-1.7B local |
| Mục tiêu | Sửa intent–evidence, kiểm nội dung quan trọng và hiểu câu hỏi nối tiếp trong một conversation |

Tài liệu nghiên cứu và lý do chọn phạm vi nằm tại [định hướng G4](00-nghien-cuu-va-dinh-huong-g4.md).

### Cập nhật 11/09/2026

- Hoan đã có implementation AnswerPlan/guard, test, Docker G4 riêng và benchmark
  local 0.6B/1.7B/4B. Giữ 1.7B mặc định; xem [bàn giao kỹ thuật](03-hoan-answer-plan-va-tich-hop.md)
  và [kết quả so sánh](04-ket-qua-so-sanh-qwen.md).
- G4-01 của Tú đã hoàn tất kỹ thuật và review: 80 DEV, 40 TEST_V2, 36 multi-turn,
  split 8/2 thủ tục, schema/validator/test đầy đủ; manifest v4 đã khóa bởi Hoan.
- G4-02/G4-04 của Minh đã được hợp nhất với G4-01 của Tú và G4-03/G4-05 của Hoan.
- DEV đã chấm đủ 80 scenario, gồm 16 scenario nhiều lượt; toàn bộ gate kỹ thuật DEV
  đạt. PostgreSQL, Qwen local, API và Chromium Docker đã qua smoke.
- Release candidate `00b2c03` đã được chấm TEST_V2 đúng một lần. Các gate tổng thể
  và claim trọng yếu đạt, nhưng multi-turn đạt 85%, thấp hơn ngưỡng 90%; vì vậy G4
  chưa được nghiệm thu phát hành. TEST_V2 tiếp tục khóa và không dùng để tuning.
- TEST_V3 của Tú đã được leader sửa contract/nhãn, khóa và chấm đúng một lần trên
  `824fd50`; kết quả 5% multi-turn nên tiếp tục không đạt. Candidate `439e1d7` đã
  sửa lớp câu nối tiếp tổng quát bằng fixture hư cấu/DEV và đang chờ TEST_V4 mới.

## Thứ tự triển khai

```text
G4-01 khóa bộ đánh giá
→ G4-02 sửa intent và retrieval theo field
→ G4-03 thêm AnswerPlan và kiểm claim
→ G4-04 thêm ngữ cảnh hội thoại ngắn
→ G4-05 tích hợp, benchmark và quyết định kỹ thuật tiếp theo
```

Không dùng TEST_V2 để sửa prompt, threshold hoặc code. Mọi thay đổi được chọn trên DEV rồi mới chạy TEST_V2 một lần cho bản phát hành.

## Phan Văn Tú – dữ liệu và bộ đánh giá

### G4-01 — Evaluation V2

**Đầu ra**

- Inventory coverage của 10 thủ tục theo: hồ sơ, phí, thời gian, nơi tiếp nhận, hình thức nộp và các bước.
- Danh sách field thiếu, nội dung mơ hồ và conflict cần review.
- Khoảng 120 scenario dự kiến: 80 DEV, 40 TEST_V2; có ít nhất 20 scenario nhiều lượt.
- Mỗi scenario có `scenario_group_id`, procedure/field kỳ vọng, fragment gold, ý bắt buộc, ý cấm và trạng thái kỳ vọng.
- Manifest version/hash; raw data, gold private và thông tin nội bộ không đưa lên Git.

**Done khi**

- Split theo nhóm tình huống/procedure family, không chia ngẫu nhiên paraphrase.
- Câu TEST_V2 và nhãn không xuất hiện trong prompt, training hoặc index phục vụ.
- Minh và Hoan review schema; reviewer thứ hai duyệt nhãn nghiệp vụ.
- Có script validate reference, split, trùng lặp và hash.

## Phạm Lê Minh – intent, retrieval và context Backend

### G4-02 — Field intent và evidence binding

**Đầu ra**

- Tách nhận diện thủ tục khỏi field người dùng hỏi.
- Nhận đúng biến thể như “nộp hồ sơ ở đâu”, “đến đâu làm”, “cần tới cơ quan nào”.
- Câu nhiều ý lấy evidence cho từng field; field thiếu đi qua trạng thái an toàn.
- Regression cho lỗi demo đã biết và các cách hỏi tương đương.

**Done khi**

- Ca “Đăng ký khai sinh nộp hồ sơ ở đâu?” chọn `receiving_authority`, không chọn `required_documents` chỉ vì có từ “hồ sơ”.
- Field accuracy và Recall@5 trên DEV đạt mục tiêu đã chốt hoặc có báo cáo lỗi còn lại.
- Không tăng Top-K để che lỗi intent; giữ Top-5 làm baseline và trần bundle 8 fragment.

### G4-04 — Ngữ cảnh hội thoại ngắn

**Đầu ra**

- Lưu thủ tục đang nói, địa phương đã nêu, field đang hỏi và câu làm rõ đang chờ trong đúng conversation.
- Mỗi fact có message nguồn; user/conversation khác không đọc được.
- Hiểu câu nối tiếp như “còn lệ phí?”, “bao lâu?” và hỏi lại khi thủ tục không rõ.

**Done khi**

- Scenario `hồ sơ → nơi nộp → lệ phí` giữ đúng một thủ tục sau refresh.
- Chuyển sang thủ tục khác cập nhật context đúng.
- Test cách ly user và conversation qua; không mở memory nhiều case xuyên conversation ở G4.

## Bùi Xuân Hoan – Qwen, kiểm chứng, đánh giá và tích hợp

### G4-03 — AnswerPlan và kiểm claim

**Đầu ra**

- AnswerPlan tối thiểu gồm field cần trả lời, giá trị/điều kiện và evidence ID.
- Backend render dữ kiện quan trọng: phí, thời gian, nơi nộp; Qwen chỉ diễn giải phần được cấp.
- Kiểm claim với evidence trước khi gửi; fallback trích xuất dùng đúng field và giữ nguyên điều kiện.

**Done khi**

- Không có claim phí/thời gian/nơi nộp ngoài AnswerPlan trong regression trọng yếu.
- Citation hợp lệ và nội dung claim được evidence hỗ trợ.
- Thiếu evidence thì hỏi lại hoặc từ chối theo contract; không dùng kiến thức model để bù.

### G4-05 — Tích hợp và thí nghiệm có đối chứng

**Đầu ra**

- Báo cáo trước/sau cho từng thay đổi, gồm chất lượng, fallback, lỗi, P50/P95 và bộ nhớ.
- Docker demo đi qua Web → Backend → RAG → Qwen → verifier → history.
- Đề xuất có số liệu về việc giữ BM25, thêm một dense retriever, thêm reranker hoặc thử Qwen 4B.

**Done khi**

- Regression G1–G3 vẫn qua.
- Demo hội thoại `hồ sơ → nơi nộp → lệ phí → đổi thủ tục → thiếu nguồn` hoạt động đúng.
- Không gộp thay model, quantization và retrieval trong một ablation.
- Fine-tune chỉ được mở thành task mới nếu model vẫn sai lặp lại khi đã nhận gold evidence đúng.

## Contract chung cần khóa trước khi code

Nhóm giữ schema G3 và chỉ bổ sung phần nhỏ cần cho G4:

```text
QueryContext: procedure_id, field_intents, jurisdiction, source_message_ids
ConversationContext: active_procedure_id, confirmed_jurisdiction, pending_clarification
AnswerPlan: requested_fields, claims, conditions, evidence_ids
VerificationResult: supported_claims, rejected_claims, final_status
```

Thay đổi không tương thích phải tăng schema version, cập nhật producer/consumer và contract test trong cùng PR.

## Gate hoàn thành G4

- Các lỗi demo đã khóa đều qua.
- Field accuracy và Recall@5 đạt ít nhất 90% trên phần có gold tương ứng.
- Ít nhất 90% ca đủ dữ liệu được reviewer xác nhận trả lời đủ ý và đúng nguồn.
- Không có lỗi trọng yếu về phí, thời gian, nơi nộp hoặc bỏ điều kiện làm đổi nghĩa trong bộ gate.
- Ít nhất 90% scenario hội thoại đúng toàn chuỗi; không lẫn user/conversation.
- Ca thiếu nguồn hoặc conflict không bị hệ thống tự kết luận.
- Docker demo và toàn bộ regression G1–G3 hoạt động từ môi trường sạch.

Các ngưỡng trên là tiêu chí nội bộ cần chốt trước khi mở TEST_V2, chưa phải số hệ thống đã đạt.
