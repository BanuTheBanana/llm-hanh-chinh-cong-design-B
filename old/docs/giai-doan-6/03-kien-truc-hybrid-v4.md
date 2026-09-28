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
field phụ, CLEAR không có căn cứ, correction địa bàn và định tuyến 0-token. Toàn bộ 107 AI Service
test và Ruff đã pass tại nhánh `g6/intent-context-quality`.

Ba regression mở cho thấy lỗi G5 không tái diễn đáng kể: V1 100%, V2 98,33% và V3 100%
full-state. Bộ DEV độc lập sau đó cho thấy Qwen3-4B đạt 100% state và 100% hội thoại; bản
Qwen3.5-2B fine-tune mới đạt 95% state nhưng chỉ 85% hội thoại. Vì vậy 4B được chọn cho bước
khóa candidate và kiểm thử tích hợp. Đây vẫn chưa phải kết quả FINAL.
