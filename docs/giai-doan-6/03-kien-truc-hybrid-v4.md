# Kiến trúc hybrid intent/context v4

Luồng xử lý G6:

```text
Câu hiện tại + state + procedure catalog
                 |
        Bộ phát hiện chắc chắn
          /                 \
  rõ và an toàn          mơ hồ/scope/date/pending
       |                         |
Fast path 0-token          Qwen3-4B + LoRA
       \                         /
        Policy v4 + contract verifier
                     |
          Backend state reducer
                     |
             Retrieval/AnswerPlan
```

Fast path hiện xử lý reset rõ, acknowledgement có context, procedure/field có tín hiệu chắc và
follow-up field rõ. Nó từ chối xử lý nhanh nếu có pending clarification, ngày, địa phương, dấu hiệu
ngoài phạm vi hoặc không đủ bằng chứng. Các quyết định đều ghi `policy_actions`; không có luật nào
tự tạo câu trả lời pháp lý.

Phiên bản `g6-intent-context-policy-v4` đã có test cho false clarification, false greeting,
field phụ, CLEAR không có căn cứ, correction địa bàn và định tuyến 0-token. Toàn bộ 102 AI Service
test và Ruff đã pass tại nhánh `g6/intent-context-quality`.

Ba regression mở cho thấy lỗi G5 không tái diễn đáng kể: V1 100%, V2 98,33% và V3 100%
full-state. Đây chưa phải bằng chứng tổng quát hóa. Bước tiếp theo bắt buộc là tạo DEV mới trước
khi quyết định có cần fine-tune thêm hoặc đổi xuống model 1.7B hay không.

