# Thí nghiệm QLoRA G5

Thư mục này chỉ chứa mã tái lập. Bundle SFT, adapter và báo cáo chi tiết là dữ liệu
private, phải nằm trong `training/output/` hoặc `evaluation/reports/` và không vào Git.
Pipeline dùng duy nhất TRAIN/VALIDATION tạo từ DEV đã duyệt; TEST bị cấm.

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
