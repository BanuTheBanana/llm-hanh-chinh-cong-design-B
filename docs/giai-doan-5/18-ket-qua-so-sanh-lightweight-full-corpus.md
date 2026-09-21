# Kết quả so sánh model lightweight trên full corpus

Ngày chạy: **14/09/2026**
Trạng thái: **ba candidate PASS trên TRAIN/VALIDATION; TEST kín chưa được mở**.

## 1. Điều kiện chung

- Cùng bundle: 384 mẫu TRAIN, 40 mẫu VALIDATION; split theo `procedure_id`.
- Cùng QLoRA rank 16, seed 42, một epoch, learning rate `2e-4`, max length 2304.
- Cùng prompt, contract, chế độ non-thinking và cấu hình sinh xác định.
- Mỗi base và adapter được chấm trên đúng cùng 40 mẫu VALIDATION.
- Peak VRAM là số của riêng process PyTorch; không dùng tổng VRAM desktop.
- Tất cả manifest đều ghi `test_data_used=false`.

## 2. Kết quả adapter

| Chỉ số | Qwen3-1.7B | Qwen3.5-2B | Qwen3-4B |
|---|---:|---:|---:|
| Contract hợp lệ | 97,5% | 97,5% | 97,5% |
| Đúng trạng thái | **95%** | 90% | 92,5% |
| Citation recall | **95%** | **95%** | 90% |
| Bao phủ claim | **95%** | **95%** | 90% |
| Abstention đúng | **95%** | 85% | **95%** |
| Recall thông tin thiếu | **95%** | 85% | **95%** |
| Độ trễ trung bình | 5,72 giây | **4,70 giây** | 7,13 giây |
| P95 | 9,32 giây | **6,93 giây** | 11,41 giây |
| Peak VRAM inference | 3,22 GB | **2,04 GB** | 3,71 GB |
| Kích thước artifact | 81,22 MB | **63,68 MB** | 143,62 MB |
| Thời gian train | **388 giây** | 1.058 giây | 5.178 giây |

Qwen3.5-2B nhanh và dùng ít VRAM inference nhất nhưng thấp hơn 1.7B 5 điểm phần trăm ở
đúng trạng thái và 10 điểm ở abstention/nhận biết thông tin thiếu. Qwen3-4B không tạo lợi thế chất lượng
trên VALIDATION này, đồng thời chậm hơn và artifact lớn hơn.

## 3. Quyết định

Chọn **Qwen3-1.7B + QLoRA r16 seed 42** làm candidate lightweight để khóa runtime và chuẩn bị
TEST kín. Candidate này đạt chất lượng cao nhất hoặc đồng hạng trên mọi chỉ số nội dung, trong
khi nhẹ hơn đáng kể so với 4B.

Quyết định này chỉ có hiệu lực ở mức DEV/VALIDATION. Chưa gọi 1.7B là model phát hành cuối cho
đến khi:

1. gắn verifier, retry một lần và fallback trích xuất an toàn vào đúng runtime candidate;
2. kiểm tra lại hash model, adapter, corpus, prompt và cấu hình decode;
3. chạy smoke end-to-end không mở gold TEST;
4. khóa candidate rồi mới mở TEST kín đúng một lần.

## 4. Artifact private

- Tổng hợp: `training/output/overnight-lightweight/full/summary.json`.
- Adapter thắng: `training/output/qwen3-1.7b-full-corpus-r16-seed42`.
- Log: `training/output/overnight-lightweight/full/logs/`.
- Báo cáo chi tiết từng model: `evaluation/reports/g5/overnight-*-validation.json`.

Artifact và output chi tiết nằm trong Git-ignore. Không dùng lỗi TEST để fine-tune hoặc chọn lại
candidate.

## 5. Cập nhật khóa runtime

Ngày 14/09/2026, ba điều kiện runtime đầu tiên đã hoàn tất: adapter được xuất GGUF và gắn vào
llama.cpp, hash/corpus/decode được khóa, smoke end-to-end đạt PASS. Candidate vẫn chưa được gọi
là bản phát hành cuối vì TEST kín chưa mở.
