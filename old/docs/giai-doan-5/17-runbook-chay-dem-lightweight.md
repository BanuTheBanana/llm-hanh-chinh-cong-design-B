# Runbook chạy đêm so sánh model lightweight

Ngày chuẩn bị: **14/09/2026**
Trạng thái smoke: **PASS cả ba candidate; resume PASS; TEST không được dùng**.

## 1. Candidate đã khóa

| Vai trò | Model | Revision |
|---|---|---|
| Nhẹ | `Qwen/Qwen3-1.7B` | `70d244cc86ccca08cf5af4e1e306ecf908b1ad5e` |
| Cân bằng | `Qwen/Qwen3.5-2B` | `15852e8c16360a2fea060d615a32b45270f8a8fc` |
| Mốc chất lượng | `Qwen/Qwen3-4B-Instruct-2507` | `cdbee75f17c01a7cc42f958dc650907174af0554` |

Ba model đều đã có đủ checkpoint trong cache local. Qwen3-4B đã full fine-tune; batch sẽ kiểm
hash và dùng lại artifact này, không train lại. Batch sẽ full fine-tune 1.7B và 2B tuần tự, sau
đó chấm base/adapter trên cùng VALIDATION cho cả ba model.

## 2. Cách chạy tối nay

Mở file sau bằng double-click:

`training/run-overnight-lightweight.bat`

Không truyền tham số. Từ terminal có thể chạy:

```powershell
cmd /c training\run-overnight-lightweight.bat
```

Không đóng cửa sổ batch, không restart/tắt máy. Có thể dùng Chrome nhẹ; tránh game, render,
Docker model hoặc ứng dụng CUDA khác. Runner yêu cầu còn ít nhất 20 GiB, chặn sleep trong thời
gian process hoạt động và tự khôi phục khi kết thúc. Máy hiện còn khoảng 235 GiB ở ổ D; sleep
và hibernate khi cắm điện cũng đang tắt.

## 3. Cơ chế an toàn

- Chạy tuần tự, không nạp hai model cùng lúc.
- Mỗi candidate đều preflight hash, corpus version, tokenizer, token budget và CUDA/BF16.
- TRAIN/VALIDATION cố định; TEST không có tham số hoặc đường dẫn trong runner.
- Mỗi output gắn model, revision, bundle hash và `test_data_used=false`.
- Không ghi đè candidate hoàn chỉnh. Chạy lại sẽ kiểm hash và resume bằng cách bỏ qua phần xong.
- Output dở không có manifest được đổi tên thành `.incomplete-<thời gian>` trước khi train lại.
- Candidate lỗi được ghi `FAIL`; runner vẫn chuyển sang model tiếp theo.
- Log và artifact private đều nằm trong vùng Git-ignore.

## 4. Nơi xem kết quả

- Tổng hợp: `training/output/overnight-lightweight/full/summary.json`.
- Log: `training/output/overnight-lightweight/full/logs/`.
- Preflight: `training/output/overnight-lightweight/full/preflight/`.
- Adapter: `training/output/<model>-full-corpus-r16-seed42/`.
- Kết quả sinh câu trả lời: `evaluation/reports/g5/overnight-*-validation.json`.

Các phép đo gồm train/eval loss, runtime, peak CUDA allocated/reserved của chính process,
kích thước artifact, contract, status, citation, claim coverage, abstention, missing-information
recall và P50/P95 inference. VRAM tổng của desktop không được dùng để kết luận model nặng nhẹ.

## 5. Việc làm sáng hôm sau

Không mở TEST ngay. Trước hết kiểm `summary.json`, so chất lượng và tài nguyên theo quy tắc:
candidate nhỏ hơn được chọn khi đạt các gate safety/contract và chênh chất lượng không quá hai
điểm phần trăm. Sau khi khóa model, verifier/retry và cấu hình runtime mới chạy TEST kín đúng một
lần. Không lấy lỗi TEST để fine-tune lại.
