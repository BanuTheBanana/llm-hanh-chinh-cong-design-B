# Kết quả fine-tune full corpus

Ngày chạy: **14/09/2026**
Trạng thái: **TRAIN PASS, VALIDATION PASS, chưa mở TEST kín**.

## 1. Cấu hình đã chạy

- Base model: `Qwen/Qwen3-4B-Instruct-2507`.
- Revision: `cdbee75f17c01a7cc42f958dc650907174af0554`.
- QLoRA: NF4 double quantization, BF16, LoRA rank 16, seed 42.
- Một epoch, learning rate `2e-4`, max length 2304.
- TRAIN: 384 mẫu thuộc 24 thủ tục.
- VALIDATION: 40 mẫu thuộc 5 thủ tục.
- TEST: 40 mẫu thuộc 5 thủ tục khác, vẫn khóa riêng và không được đọc.

Trainer hoàn thành 48/48 optimizer step trong 5.177,74 giây. Train loss là `0.20696` và
validation loss là `0.00516`. Adapter có dung lượng 132.187.888 byte; toàn bộ hash artifact
khớp manifest.

## 2. Kết quả sinh câu trả lời trên VALIDATION

Base và adapter được chấm trên cùng 40 mẫu, cùng checkpoint, revision và cấu hình sinh.

| Chỉ số | Base | Adapter | Thay đổi |
|---|---:|---:|---:|
| Contract hợp lệ | 100% | 97,5% | -2,5 điểm % |
| Đúng trạng thái | 92,5% | 92,5% | 0 |
| Citation recall trên 20 ca ANSWER | 90% | 90% | 0 |
| Bao phủ nguyên văn claim | 75% | 90% | +15 điểm % |
| Abstention đúng trên 20 ca thiếu dữ liệu | 95% | 95% | 0 |
| Recall thông tin còn thiếu | 0% | 95% | +95 điểm % |
| Độ trễ trung bình | 5.318 ms | 7.526 ms | +2.208 ms |

Adapter cải thiện rõ khả năng đưa đúng nội dung evidence vào câu trả lời và nêu trường thông
tin còn thiếu. Tuy nhiên, adapter còn một output sai contract và ba ca sai trạng thái; độ trễ
cũng cao hơn base. Vì vậy adapter được giữ là **candidate đã train thành công**, chưa phải bản
phát hành cuối chỉ dựa trên loss.

## 3. Sửa công cụ đánh giá

Evaluator cũ giả định mọi mẫu đều có citation nên chia cho 0 ở ca `INSUFFICIENT_DATA`. Công cụ
đã được sửa để:

- chấm citation và claim coverage chỉ trên ca `ANSWER`;
- chấm abstention và missing-information recall riêng;
- kiểm tra liên kết adapter với đúng model, revision và training manifest;
- tiếp tục ghi `test_data_used=false` và không mở TEST.

## 4. Artifact private

- Adapter: `training/output/qwen3-4b-full-corpus-r16-seed42`.
- Kết quả adapter: `evaluation/reports/g5/full-corpus-qwen3-4b-r16-seed42-validation.json`.
- Kết quả base: `evaluation/reports/g5/full-corpus-qwen3-4b-base-validation.json`.

Các file này thuộc vùng Git-ignore. Bước tiếp theo là xử lý regression contract bằng verifier
và retry trên VALIDATION, khóa candidate, rồi mới chạy TEST kín đúng một lần. Không dùng TEST
để sửa model hoặc chọn lại tham số.
