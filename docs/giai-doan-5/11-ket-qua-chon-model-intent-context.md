# Kết quả chọn model cho intent/context

Ngày chạy: **12/09/2026**. Kết luận ngắn: chọn
**Qwen3-4B-Instruct-2507** làm checkpoint chính để tiếp tục fine-tune và tích hợp
intent/context. **Qwen3.5-2B** giữ làm phương án nhẹ hơn. Qwen3-1.7B bị loại khỏi nhánh
intent/context mới.

Đây là quyết định chọn model từ pilot, **chưa phải nghiệm thu intent/context**.

## Phạm vi thử nghiệm

- 120 mẫu TRAIN và 60 ca DEV hư cấu D0; không dùng dữ liệu công ty, không dùng TEST kín.
- TRAIN và DEV không trùng ID hoặc câu hỏi y hệt; cả hai đã khóa SHA-256.
- Cùng prompt, schema JSON, context 4096, non-thinking, temperature 0, Q8_0 và máy
  RTX 5060 Ti 16 GB.
- Fine-tune QLoRA NF4/BF16, rank 16, một epoch. Hai ứng viên tốt nhất từ baseline
  được fine-tune cùng dữ liệu; winner được chạy lại với seed 7.
- `joint patch` là so thao tác JSON chính xác. `joint state` mới là chỉ số chính: áp dụng
  quy tắc Backend tự xóa field/scope/date khi đổi thủ tục rồi so trạng thái cuối.

## Baseline chưa fine-tune

| Model | Schema hợp lệ | Dialogue act | Topic | Joint state | Full state | P95 | VRAM tăng |
|---|---:|---:|---:|---:|---:|---:|---:|
| Qwen3-1.7B | 100% | 70,00% | 45,00% | 6,67% | 3,33% | 2,44 s | 2.266 MiB |
| Qwen3-4B-Instruct-2507 | 100% | 68,33% | 75,00% | **56,67%** | **46,67%** | 4,55 s | 4.751 MiB |
| Qwen3.5-2B | 98,33% | 70,00% | 46,67% | 8,33% | 8,33% | 3,36 s | **2.053 MiB** |

Qwen3-4B dẫn rõ về hiểu trạng thái trước khi fine-tune. Hai model 4B và 2B được giữ lại
cho pilot QLoRA; 1.7B không đủ chất lượng cho nhiệm vụ mới.

## Sau fine-tune intent/context

| Model | Seed | Schema/ngữ nghĩa | Dialogue act | Topic | Joint patch | Joint state | Full state | P95 | VRAM tăng |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Qwen3-4B + LoRA r16 | 42 | 100% / 100% | **91,67%** | **93,33%** | 56,67% | **75,00%** | **63,33%** | 2,52 s | 4.843 MiB |
| Qwen3.5-2B + LoRA r16 | 42 | 100% / 100% | 76,67% | 91,67% | 53,33% | 61,67% | 41,67% | **1,62 s** | **2.332 MiB** |
| Qwen3-4B + LoRA r16 | 7 | 100% / 100% | 90,00% | 85,00% | 56,67% | 71,67% | 58,33% | 2,61 s | 4.908 MiB |

Seed 7 vẫn giữ Qwen3-4B trên Qwen3.5-2B về chất lượng. Fine-tune tăng joint state của
4B từ 56,67% lên 75,00% ở seed 42; kết quả không chỉ dựa vào training loss. Qwen3.5-2B
nhanh và tiết kiệm VRAM hơn, nhưng chênh full-state 21,66 điểm phần trăm nên quy tắc
quality-first không cho chọn model nhỏ hơn.

## Quyết định và giới hạn

- Checkpoint phát triển: `Qwen/Qwen3-4B-Instruct-2507`, revision
  `cdbee75f17c01a7cc42f958dc650907174af0554`.
- Adapter pilot đang tốt nhất: seed 42, SHA-256 GGUF bắt đầu bằng `f081fee9`.
- Qwen3.5-2B là fallback khi thiết bị yếu hơn; chưa phải model chính.
- Cả hai bản fine-tune đều dưới ngưỡng joint state 90%. Không đưa pilot này vào Web rồi
  gọi là đã hoàn thiện.
- DEV là fixture hư cấu nhỏ theo từng lượt, chưa chứng minh hội thoại replay đầy đủ,
  độ đúng pháp lý hoặc khả năng tổng quát trên dữ liệu công ty.

Bước tiếp theo là bổ sung dữ liệu đã review cho lỗi follow-up, sửa/đổi thủ tục,
scope/date và boundary; nối output đã kiểm chứng vào luồng chat; sau đó mới chạy replay
hội thoại và một TEST kín duy nhất. Số tổng hợp có fingerprint nằm tại
[`evaluation/baselines/g5-intent-context-pilot-20260912.json`](../../evaluation/baselines/g5-intent-context-pilot-20260912.json).
