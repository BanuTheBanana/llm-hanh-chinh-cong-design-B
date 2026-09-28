# Thí nghiệm QLoRA G5

Thư mục này chỉ chứa mã tái lập. Bundle SFT, adapter và báo cáo chi tiết là dữ liệu
private, phải nằm trong `training/output/` hoặc `evaluation/reports/` và không vào Git.
Pipeline cũ dùng TRAIN/VALIDATION tạo từ DEV đã duyệt. Với full corpus, dùng bundle
procedure-disjoint đã khóa riêng: TRAIN/VALIDATION nằm trong `training/output/`, còn
TEST nằm ngoài thư mục training và trainer không được phép mở.

Yêu cầu: Python 3.12, NVIDIA CUDA hỗ trợ BF16 và các gói trong
`requirements-gpu.txt`. Base mặc định được khóa ở revision đã ghi trong script.

```powershell
python -m venv training/.venv
training\.venv\Scripts\python -m pip install -r training\requirements-gpu.txt

training\.venv\Scripts\python training\train_qlora.py `
  --bundle evaluation\reports\g5\sft-local `
  --output training\output\qwen3-1.7b-r16 `
  --lora-rank 16 --epochs 1

training\.venv\Scripts\python training\evaluate_adapter.py `
  --bundle evaluation\reports\g5\sft-local `
  --adapter training\output\qwen3-1.7b-r16 `
  --one-variant-per-base `
  --output evaluation\reports\g5\adapter-validation-local.json
```

Không tự phát hành adapter chỉ vì loss giảm. So sánh contract, citation, bao phủ claim
và độ trễ với base; nếu citation hoặc safety giảm thì giữ model gốc.

## Full-corpus QLoRA

Checkpoint đã khóa:

- Model: `Qwen/Qwen3-4B-Instruct-2507`
- Revision: `cdbee75f17c01a7cc42f958dc650907174af0554`
- Max length: 2304; QLoRA NF4 double-quant, BF16, LoRA rank 16

Chạy preflight trước. Lệnh này kiểm hash/version/split, cấm TEST trong bundle, mã hóa
toàn bộ mẫu và kiểm CUDA/BF16 cùng checkpoint local:

```powershell
training\.venv\Scripts\python training\preflight_qlora.py `
  --bundle training\output\full-corpus-sft-v1-bundle `
  --model Qwen/Qwen3-4B-Instruct-2507 `
  --revision cdbee75f17c01a7cc42f958dc650907174af0554 `
  --max-length 2304
```

Chỉ khi preflight PASS mới chạy một candidate chính thức:

```powershell
training\.venv\Scripts\python training\train_qlora.py `
  --bundle training\output\full-corpus-sft-v1-bundle `
  --output training\output\qwen3-4b-full-corpus-r16-seed42 `
  --model Qwen/Qwen3-4B-Instruct-2507 `
  --revision cdbee75f17c01a7cc42f958dc650907174af0554 `
  --max-length 2304 --epochs 1 --learning-rate 0.0002 `
  --lora-rank 16 --seed 42
```

Không truyền thư mục TEST vào hai lệnh trên. Sau khi khóa candidate và kết quả DEV,
TEST chỉ được chạy đúng một lần để nghiệm thu; không dùng lỗi TEST để train lại.

## Chạy tuần tự các candidate lightweight

Batch đã kiểm smoke và có resume:

```powershell
cmd /c training\run-overnight-lightweight.bat
```

Lệnh trên chạy tuần tự Qwen3-1.7B, Qwen3.5-2B và kiểm/dùng lại Qwen3-4B đã hoàn thành;
sau đó chấm base và adapter trên cùng VALIDATION. Dùng tham số `smoke` chỉ để kiểm pipeline:

```powershell
cmd /c training\run-overnight-lightweight.bat smoke
```

Runner không nhận đường dẫn TEST, chặn sleep khi đang chạy, ghi log riêng và bỏ qua artifact đã
hoàn chỉnh sau khi kiểm model/revision/bundle/hash. Xem runbook tại
`docs/giai-doan-5/17-runbook-chay-dem-lightweight.md`.

## Intent/context đủ 38 thủ tục

Bundle private được sinh từ release 38 thủ tục đã qua validator, đồng thời giữ lại các ca D0
context cũ để hạn chế catastrophic forgetting. TRAIN và DEV dùng cách diễn đạt khác nhau,
không chứa TEST và chỉ nằm trong `training/output/`.

```powershell
backend\.venv\Scripts\python scripts\build-g7-full38-intent-context.py `
  --release 'D:\CODEFPT\OJT\tu_full_data_preprocessed\company-tthc-9c38dde8-v1-adjudicated-v1' `
  --output training\output\intent-context-full38-v1 `
  --expected-rows 42

training\.venv\Scripts\python training\preflight_intent_context.py `
  --train training\output\intent-context-full38-v1\train `
  --dev training\output\intent-context-full38-v1\dev `
  --model Qwen/Qwen3-4B-Instruct-2507 `
  --revision cdbee75f17c01a7cc42f958dc650907174af0554 `
  --max-length 2560 `
  --output training\output\intent-context-full38-v1\preflight.json
```

Để chạy toàn bộ quá trình qua đêm, dùng:

```powershell
cmd /c training\run-full38-intent-overnight.bat
```

Runner khóa Qwen3-4B, LoRA rank 16, seed 42, một epoch và learning rate `1e-4`; nó tự dừng
ba container model G5 để giải phóng GPU, ngăn Windows sleep, chạy lại preflight, fine-tune,
chuyển adapter sang GGUF và đánh giá trên DEV. Runner không tự khởi động lại stack demo sau
khi hoàn tất; dùng `scripts/demo-g5.ps1` để bật lại khi cần.
