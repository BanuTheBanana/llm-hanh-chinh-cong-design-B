# Runbook G3-A01 – Qwen3-1.7B local qua llama.cpp

## Báo cáo cập nhật

| Trường | Nội dung |
|---|---|
| Cập nhật | 09/09/2026 |
| Phạm vi | `G3-A01/A01-1` – runtime và provider adapter |
| Code adapter | `IMPLEMENTED_AND_TESTED` |
| Live llama.cpp trên máy hiện tại | `PASS_D0_END_TO_END` |
| Dữ liệu được phép ở checkpoint này | Chỉ `D0_SYSTEM_SMOKE` |
| Hosted API | Không dùng |
| Fine-tune | Chưa được mở |

## Tổng

Luồng chạy của checkpoint này:

```text
Backend/RAG D0
→ POST AI Service /internal/v2/generate
→ LocalGroundedProvider
→ llama-server trên máy host:8080
→ Qwen3-1.7B non-thinking + constrained JSON
→ validate schema + citation allowlist
→ Backend hydrate nguồn như G2
```

`compose.g3.local.yaml` chỉ thay provider grounded từ `template` sang `local`.
Nó không thay Web/Backend contract và không bật dữ liệu công ty. D2 vẫn bị API
schema từ chối cho đến khi cả nhóm duyệt một contract riêng.

## 1. Artifact phải khóa trước khi benchmark

Ghi lại manifest sau, không để trống rồi tuyên bố kết quả:

```text
model_repository: Qwen/Qwen3-1.7B-GGUF
api_model_alias: Qwen3-1.7B
model_revision: 90862c4b9d2787eaed51d12237eafdfe7c5f6077
model_file: Qwen3-1.7B-Q8_0.gguf
model_size_bytes: 1834426016
model_sha256: 061B54DAADE076B5D3362DAC252678D17DA8C68F07560BE70818CACE6590CB1A
model_license: Apache-2.0
quantization: Q8_0
llama_cpp_version_or_commit: 0.4.0-dev, build 10853, commit 9dcf84e5a
chat_template_sha256: F94F2AD6AC676D3B5D80453A6CC0D6C58760C6F613CF44550ADCBC62818EDE9D
context_tokens: 4096
max_output_tokens: 500
temperature: 0.7
top_p: 0.8
top_k: 20
min_p: 0.0
presence_penalty: 1.5
seed: 42
```

Q8_0 là reference chính thức có sẵn. Q5_K_M và Q4_K_M chỉ được benchmark sau khi
artifact đã được tạo/pin riêng; không đổi quant giữa các lượt nhưng giữ cùng tên
run.

## 2. Chuẩn bị một lần trên Windows

1. Cài một bản llama.cpp có CUDA và ghi chính xác version/commit.
2. Tải `Qwen3-1.7B-Q8_0.gguf` từ repository chính thức vào `models/`. Folder này
   đã bị Git ignore.
3. Tắt mạng hoặc áp dụng outbound firewall sau khi đủ binary/model; inference
   không cần hosted API.
4. Tính hash:

```powershell
$ProjectRoot = 'D:\CODEFPT\OJT\LLM'
Get-FileHash -Algorithm SHA256 `
  -LiteralPath "$ProjectRoot\models\Qwen3-1.7B-Q8_0.gguf"
Get-FileHash -Algorithm SHA256 `
  -LiteralPath "$ProjectRoot\ai-service\runtime\qwen3_nonthinking.jinja"
llama-server --version
```

Không commit file GGUF, cache tải model hoặc report chứa prompt/evidence công ty.

## 3. Chạy llama-server non-thinking

Qwen3 trên llama.cpp không có hard switch non-thinking đáng tin cậy qua request
OpenAI-compatible. Vì vậy server bắt buộc dùng template đã khóa trong repository:

```powershell
$ProjectRoot = 'D:\CODEFPT\OJT\LLM'
llama-server `
  -m "$ProjectRoot\models\Qwen3-1.7B-Q8_0.gguf" `
  --alias Qwen3-1.7B `
  --host 0.0.0.0 `
  --port 8080 `
  --jinja `
  --chat-template-file "$ProjectRoot\ai-service\runtime\qwen3_nonthinking.jinja" `
  -ngl 99 `
  -fa `
  -sm row `
  --temp 0.7 `
  --top-p 0.8 `
  --top-k 20 `
  --min-p 0.0 `
  --presence-penalty 1.5 `
  --seed 42 `
  -c 4096 `
  -n 500 `
  --no-context-shift
```

`0.0.0.0` chỉ để container Docker Desktop gọi được máy host. Giới hạn bằng
Windows Firewall, không port-forward trên router và không công bố cổng 8080 ra
Internet. Provider còn có hostname allowlist, `trust_env=false` và không follow
redirect; đây là defense-in-depth, không thay firewall.

Kiểm tra runtime:

```powershell
Invoke-RestMethod http://127.0.0.1:8080/health
nvidia-smi
```

Nếu response có `reasoning_content` hoặc thẻ `<think>`, AI Service sẽ từ chối nó
thay vì lưu/hiển thị ra ngoài.

## 4. Chạy toàn hệ thống với D0

Từ repository root:

```powershell
Copy-Item .env.example .env
docker compose `
  -f compose.yaml `
  -f compose.g2.yaml `
  -f compose.g3.local.yaml `
  --profile full up --build --detach --wait
python scripts/smoke-g3-local.py
```

Health đúng:

```powershell
Invoke-RestMethod http://127.0.0.1:8001/internal/v2/health
```

Kỳ vọng `provider=local`, `external_calls_enabled=false`. Nếu llama-server chưa
chạy, health metadata vẫn lên nhưng generate phải trả lỗi provider; vì vậy smoke
generate mới là readiness cuối.

## 5. Guardrail đã implement

- chỉ cho phép hostname local đã cấu hình, HTTP, không credential/query/fragment;
- reuse một HTTP client pool trong vòng đời FastAPI và đóng khi shutdown;
- timeout/output cap/prompt character cap rõ ràng;
- sampling non-greedy theo baseline Qwen non-thinking;
- gửi JSON Schema cho constrained generation rồi vẫn validate lại bằng Pydantic;
- envelope HTTP 200 sai cấu trúc được map về `AI_PROVIDER_INVALID_RESPONSE`;
- citation ngoài EvidenceBundle bị từ chối;
- thinking content bị từ chối;
- chỉ `D0_SYSTEM_SMOKE` được phép trong A01.

Giới hạn `LOCAL_LLM_MAX_PROMPT_CHARACTERS` là guard thô, không phải tokenizer.
Minh vẫn phải trả top 3–5 fragment gọn; benchmark A02 phải ghi prompt token thực
từ `usage` và phân loại request vượt budget.

## 6. Gate đóng G3-A01 và mở A02

G3-A01 chỉ được ký hoàn tất khi:

1. toàn bộ AI Service test/lint/format pass;
2. llama-server thật chạy với template non-thinking đã hash;
3. D0 smoke đi Web → Backend/RAG → Qwen → citation → history thành công;
4. không có thinking content/citation giả/external endpoint;
5. manifest artifact được điền bằng giá trị đo thật.

G3-A02 vẫn chờ `G3-D03` và `G3-R02`. Không dùng D0 smoke để kết luận chất lượng
dữ liệu thật, không quyết định QLoRA trước error analysis.

## 7. Kết quả nghiệm thu trên máy Hoan ngày 09/09/2026

| Gate | Kết quả |
|---|---|
| AI Service test | `63 passed` |
| Ruff lint/format | `PASS` |
| Compose G3 config | `PASS` |
| llama.cpp + Vulkan trên RTX 5060 Ti 16 GB | `PASS` |
| Ba câu D0 qua Backend → RAG → Qwen local | `PASS` |
| Citation và PostgreSQL history | `PASS` |
| Hosted/external AI call | `DISABLED` |

Một lượt quan sát kỹ thuật trực tiếp ghi nhận request cold khoảng `10.486 s`; request
warm dùng prompt cache khoảng `0.511 s`, tốc độ sinh khoảng `114–126 token/s`. Đây chỉ
là smoke observation, **không phải** p50/p95 benchmark và không được dùng để kết luận
A02. Benchmark chính thức phải dùng bộ gold đã duyệt, warm-up cố định và nhiều lượt đo.

## Nguồn chính

- [Qwen3 llama.cpp guide](https://github.com/QwenLM/Qwen3/blob/main/docs/source/run_locally/llama.cpp.md)
- [Qwen3 non-thinking template gốc](https://github.com/QwenLM/Qwen3/blob/main/docs/source/assets/qwen3_nonthinking.jinja)
- [Qwen3-1.7B-GGUF chính thức](https://huggingface.co/Qwen/Qwen3-1.7B-GGUF)
- [llama.cpp server](https://github.com/ggml-org/llama.cpp/tree/master/tools/server)
