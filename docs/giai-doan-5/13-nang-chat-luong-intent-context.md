# Nâng chất lượng intent/context vòng 2

Cập nhật: **13/09/2026**. Mục tiêu vòng này là vượt ngưỡng context DEV bằng một thay đổi có giới
hạn, không tạo thêm TEST sau mỗi lỗi và không dùng dữ liệu công ty để làm đẹp điểm.

## Đã thực hiện

- Phân tích lỗi của adapter vòng đầu theo sáu nhóm: direct, follow-up, correction/switch, reset,
  scope/date và boundary.
- Tạo TRAIN hard-v2 gồm 252 ca D0 hư cấu, không trùng ID hoặc câu nguyên văn với 60 ca DEV.
- Fine-tune QLoRA NF4/BF16, rank 16, seed 42 trong 1,5 epoch trên Qwen3-4B-Instruct-2507.
- Xuất adapter F16 GGUF bằng công cụ chính thức của llama.cpp và đo bằng đúng runtime llama.cpp.
- Giữ prompt v2 ngắn. Một prompt dài hơn đã được thử và loại vì làm full-state giảm từ 86,67%
  xuống 85,00%.
- Thêm policy v1 sau model để xử lý các bất biến trạng thái; mọi lần policy can thiệp đều được
  evaluator ghi lại. Policy không tự đoán giá trị slot.

Thiết kế QLoRA phù hợp vòng này vì base 4-bit được giữ đông và chỉ adapter được học, giúp giảm bộ
nhớ so với fine-tune toàn bộ tham số. Cách làm dựa trên [QLoRA](https://arxiv.org/abs/2305.14314)
và [LoRA](https://arxiv.org/abs/2106.09685), nhưng quyết định triển khai dựa vào DEV chạy thật,
không dựa vào training loss.

## Kết quả

| Chỉ số trên 60 DEV | Adapter vòng đầu | Hard-v2 model thuần | Hard-v2 + policy |
|---|---:|---:|---:|
| Schema/ngữ nghĩa | 100% / 100% | 100% / 100% | 100% / 100% |
| Dialogue act | 91,67% | 93,33% | **100%** |
| Topic action | 93,33% | 95,00% | **96,67%** |
| Joint state | 75,00% | **98,33%** | **98,33%** |
| Full state | 63,33% | 86,67% | **95,00%** |
| P95 | 2,52 s | 3,12 s | 3,14 s |

Direct, follow-up, reset và scope/date đạt 100% full-state ở pipeline cuối. Correction/switch đạt
87,5% và boundary đạt 80%; đây là hai nhóm cần theo dõi trên TEST kín, không tiếp tục sửa theo DEV.
Mức dùng GPU tăng khoảng 4.879 MiB, vẫn trong ngân sách model intent đã đặt.

## Quyết định

Chọn `Qwen3-4B-Intent-hard-v2-r16` + prompt v2 + policy v1 cho runtime G5. Base và adapter đều
mount read-only, không commit trọng số lên Git. Fingerprint và số liệu tóm tắt nằm tại
[`evaluation/baselines/g5-intent-context-quality-round2-20260913.json`](../../evaluation/baselines/g5-intent-context-quality-round2-20260913.json).

TEST kín chưa được mở. Bước tiếp theo là khóa candidate, chạy integration/smoke, sau đó mới nghiệm
thu TEST một lần. Kết quả intent/context không được diễn giải thành độ chính xác pháp lý của câu trả lời.

## Xác minh Docker và PostgreSQL

Docker Desktop đã được xác minh là có sẵn và daemon đã được khởi động lại; không cần cài mới.
PostgreSQL 16 được chạy bằng container riêng thay vì cài trực tiếp lên Windows. Toàn bộ Backend suite
đạt **244 passed, 1 skipped** trên database test tách biệt.

Stack G5 sau khi build lại có đủ 8 service healthy: Web, Backend, PostgreSQL, AI Service, generation
model, embedding model, intent model và source service. Web trả HTTP 200; Backend, RAG và endpoint
intent đều báo `ok`, đúng model `Qwen3-4B-Intent-hard-v2-r16`. Smoke trực tiếp qua intent container
trả đúng `p_birth`, field `fees` và evidence nguyên văn. Web G5 đang phục vụ tại
`http://localhost:3005`.
