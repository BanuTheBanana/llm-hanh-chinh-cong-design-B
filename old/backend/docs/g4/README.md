# G4 backend — field retrieval và hội thoại ngắn

G4 giữ API của G3 nhưng bổ sung ba lớp: nhận diện field độc lập với tên thủ tục,
ngữ cảnh theo conversation và AnswerPlan kiểm chứng trước khi trả lời. Corpus công
ty, DEV và TEST_V2 chỉ dùng local; không commit vào Git hoặc gửi sang API bên ngoài.

## 1. Cấu hình

Runtime chỉ đọc bốn file corpus đã duyệt:

```text
<dataset>/source_manifest.jsonl
<dataset>/normalized/procedures.jsonl
<dataset>/normalized/fragments.jsonl
<dataset>/quarantine/conflicts.jsonl
```

Gold và `g4_eval` không được loader phục vụ mở. Fingerprint
`g4-serving-corpus-v1` chỉ phụ thuộc bốn nhóm trên.

```dotenv
RAG_ENABLED=true
G3_D2_ENABLED=true
G4_ANSWER_PLAN_ENABLED=true
RAG_CORPUS_VERSION=company-tthc-9c38dde8-v1-demo10-v1
G3_PRIVATE_DATASET_PATH=C:/private/company_private/demo10
G3_EXPECTED_ROWS=10
G3_CORPUS_SHA256=<hash từ validate-corpus>
RAG_TOP_K=5
```

Lấy fingerprint bằng:

```powershell
uv run --frozen python -m app.rag.g4.evaluation validate-corpus `
  --dataset "C:\private\company_private\demo10" `
  --version company-tthc-9c38dde8-v1-demo10-v1 `
  --expected-rows 10
```

## 2. Migration

Migration `0003_g4_context` thêm cột JSONB nullable `conversations.rag_context`.
Conversation cũ vẫn hợp lệ và bắt đầu với context trống.

```powershell
uv run --frozen alembic upgrade head
```

Khi rollback phải dừng backend G4 trước. Lệnh downgrade về `0002_g2_rag` chỉ xóa
context G4, không xóa lịch sử tin nhắn.

## 3. Contract đã triển khai

- `QueryContext`: thủ tục, field, địa phương và message nguồn của fact.
- `ConversationContext`: trạng thái theo đúng một conversation; reset khi đổi corpus.
- `AnswerPlan`: field cần trả lời, nguyên văn claim và evidence ID bắt buộc.
- `VerificationResult`: kết quả kiểm tra output Qwen; sai contract/claim thì backend
  dựng lại câu trả lời từ nguồn.

Context chỉ học từ tin nhắn người dùng. Lượt hỏi tiếp như “còn lệ phí?” kế thừa thủ
tục; tên thủ tục mới thay context cũ; địa phương không có căn cứ làm hệ thống abstain.
Retry idempotent không tạo thêm context, user/conversation khác không đọc được state.

## 4. Kiểm thử DEV

Evaluator DEV chấm cả một lượt và nhiều lượt, không đọc TEST_V2:

```powershell
uv run --frozen python -m app.rag.g4.evaluation evaluate-dev `
  --dataset "C:\private\company_private\demo10" `
  --version company-tthc-9c38dde8-v1-demo10-v1 `
  --expected-rows 10 `
  --dev "C:\private\company_private\demo10\g4_eval\scenario_dev.jsonl"
```

`scenario_dev.jsonl` phải đúng tên, không phải symlink, toàn bộ record thuộc DEV và
đã được review. Với scenario nhiều lượt, evaluator chỉ dùng các lượt user để tái tạo
context; text assistant trong bộ đánh giá không được dùng làm fact.

So sánh G3/G4 trên cùng 64 câu một lượt và chấm thêm toàn bộ 16 câu nhiều lượt:

```powershell
uv run --frozen python tools/compare_g4_dev.py `
  --dataset "C:\private\company_private\demo10" `
  --version company-tthc-9c38dde8-v1-demo10-v1 `
  --dev "C:\private\company_private\demo10\g4_eval\scenario_dev.jsonl"
```

## 5. Docker và smoke

Từ thư mục gốc repository:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/demo-g4.ps1 -Action Start
```

G4 chạy ở Web `3004`, Backend `8004`, AI service `8104`, llama.cpp `8084` và
PostgreSQL `55434`. Dataset/model được mount read-only. Các project G1/G2/G3 không
bị thay thế.

```powershell
uv run --directory backend --frozen python scripts/smoke-g4-multiturn.py `
  --dev "C:\private\company_private\demo10\g4_eval\scenario_dev.jsonl"
node scripts/smoke-g4-browser.mjs `
  "C:\private\company_private\demo10\g4_eval\scenario_dev.jsonl"
```

## 6. TEST_V2

Không dùng TEST_V2 để sửa code, prompt, model hay threshold. Chỉ leader/reviewer
chạy `scripts/evaluate-g4-release.py` một lần sau khi commit/config đã đóng băng.
Script yêu cầu acknowledgement, worktree sạch, commit/hash khớp, manifest `LOCKED`
và tạo marker local để ngăn chạy lại. Output chỉ có số liệu tổng hợp và nằm trong
`evaluation/reports/` đã được Git ignore.
