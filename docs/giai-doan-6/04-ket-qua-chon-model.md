# Kết quả chọn model G6

## Cách so sánh

Bốn cấu hình được chạy trên cùng bộ DEV hư cấu gồm 60 lượt thuộc 20 hội thoại. Mọi cấu hình
đều dùng policy v4 và cùng fast path; 36 lượt rõ nghĩa đi tuyến 0-token, 24 lượt khó mới gọi
model. Bộ này chỉ đo intent/context, không đo độ đúng pháp lý của câu trả lời.

| Cấu hình | Đúng state | Đúng trọn hội thoại | Field macro-F1 | Nhóm thấp nhất | P95 | VRAM tăng | Qua gate |
|---|---:|---:|---:|---:|---:|---:|:---:|
| Qwen3-1.7B base | 58,33% | 40% | 98,44% | 0% | 2.417 ms | 2.262 MiB | Không |
| Qwen3.5-2B + LoRA pilot | 85% | 70% | 86,38% | 50% | 1.791 ms | 2.222 MiB | Không |
| Qwen3.5-2B + LoRA hard-v2 mới | 95% | 85% | 97,22% | 77,78% | 1.465 ms | 2.311 MiB | Không |
| Qwen3-4B + LoRA hard-v2 | 100% | 100% | 100% | 100% | 2.858 ms | 4.913 MiB | Có |

Fine-tune mới giúp Qwen3.5-2B tăng đúng state từ 85% lên 95%, đồng thời nhanh và nhẹ hơn
4B. Tuy vậy, model chỉ đạt 85% hội thoại và 77,78% ở nhóm correction/switch, thấp hơn gate
90% và 80%. Vì vậy không chọn 2B làm model chính ở G6.

## Quyết định

Chọn **Qwen3-4B + LoRA hard-v2 + policy v4** làm candidate để khóa và kiểm thử tích hợp.
Đây là cấu hình duy nhất qua toàn bộ gate đã định trước. Qwen3.5-2B được giữ làm phương án
nhẹ để nghiên cứu sau, không bị gọi là thất bại và cũng không thay model chính chỉ dựa vào tốc độ.

Số tổng hợp, hash model và hash adapter nằm tại
[`g6-model-comparison-20260914.json`](../../evaluation/baselines/g6-model-comparison-20260914.json).
Các file raw chứa từng câu không được đưa lên Git. Kết quả DEV chưa phải nghiệm thu FINAL.
