# Biên bản sẵn sàng fine-tune full corpus

Ngày chốt: **14/09/2026**
Phạm vi: dữ liệu công ty hiện có, không giả định sẽ nhận thêm nguồn nội bộ.

## 1. Kết luận

Hệ thống đã **đủ điều kiện kỹ thuật và dữ liệu để bắt đầu một lần QLoRA chính thức**
cho tác vụ trả lời có evidence. TEST đã khóa riêng và chưa được dùng để chọn cấu hình.

Điều này không có nghĩa model sau train mặc nhiên đạt chất lượng. Adapter chỉ được chọn
sau khi vượt DEV và một lần TEST cuối theo contract/citation/safety.

## 2. Corpus đầu vào

- Release: `company-tthc-9c38dde8-v1-controlled-v1`.
- 34 thủ tục và 34 nguồn không conflict.
- 139 fragment được allowlist.
- 304/304 cặp thủ tục–field có quyết định.
- 139 field `APPROVED`; 112 `INSUFFICIENT_DATA`; 21 mơ hồ và 32 field thuộc thủ tục
  conflict được cách ly.
- Publish validator và allowlist validator: PASS, 0 lỗi.

## 3. SFT v1 đã khóa

| Split | Thủ tục | Mẫu | Ghi chú |
|---|---:|---:|---|
| TRAIN | 24 | 384 | 192 ca gốc, hai biến thể trình bày |
| VALIDATION | 5 | 40 | Một mẫu cho mỗi thủ tục–field |
| TEST | 5 | 40 | Lưu riêng, `LOCKED`, private gold |

- Ba split không trùng `procedure_id`.
- TEST không trùng nguyên câu hỏi với TRAIN/VALIDATION.
- TRAIN/VALIDATION mang đúng corpus version; trainer chặn version mismatch.
- Mẫu `ANSWER` luôn có citation nằm trong evidence.
- Mẫu thiếu/mơ hồ trả `INSUFFICIENT_DATA`, không citation và không bịa giá trị.
- TEST không nằm trong training bundle; manifest ghi `test_data_used=false`.

## 4. Model và môi trường

- Checkpoint: `Qwen/Qwen3-4B-Instruct-2507`.
- Revision khóa: `cdbee75f17c01a7cc42f958dc650907174af0554`.
- CUDA 12.8, BF16, PEFT và bitsandbytes hoạt động.
- Token preflight ở max length 2304 giữ đủ 384 TRAIN và 40 VALIDATION, không rơi mẫu.
- QLoRA smoke hai bước trên GPU: PASS; 8 TRAIN và 4 VALIDATION được chạy thật.
- Trainer dừng nếu có TEST, sai hash/version, citation sai hoặc mẫu vượt token budget.
- Bộ kiểm thử công cụ dữ liệu: 42/42 test PASS; Ruff PASS.

## 5. Artifact private

- Training bundle: `training/output/full-corpus-sft-v1-bundle`.
- Locked TEST: `D:\CODEFPT\OJT\Full_Corpus_SFT_V1_TEST_private`.
- Smoke artifact: `training/output/qwen3-4b-full-corpus-sft-v1-smoke-r16-2304`.

Các artifact trên bị chặn khỏi Git. Chỉ code, test giả lập, runbook và báo cáo thống kê
được phép commit.

## 6. Lệnh train chính thức

```powershell
training\.venv\Scripts\python training\train_qlora.py `
  --bundle training\output\full-corpus-sft-v1-bundle `
  --output training\output\qwen3-4b-full-corpus-r16-seed42 `
  --model Qwen/Qwen3-4B-Instruct-2507 `
  --revision cdbee75f17c01a7cc42f958dc650907174af0554 `
  --max-length 2304 --epochs 1 --learning-rate 0.0002 `
  --lora-rank 16 --seed 42
```

Sau train: chấm DEV, kiểm citation/abstention và tài nguyên; chỉ khi candidate được khóa
mới mở TEST đúng một lần. Không tạo TEST mới theo từng lỗi.
