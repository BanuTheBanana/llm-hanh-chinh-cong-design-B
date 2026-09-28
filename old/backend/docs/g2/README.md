# Backend/RAG G2

## Báo cáo cập nhật

| Trường | Nội dung |
|---|---|
| Cập nhật | 09/09/2026 |
| Trạng thái kỹ thuật | D0 offline integrated; D1 pending review |
| AI contract | `g2-grounded-v0.2`, prompt `g2-grounded-v2` |
| Endpoint AI | `POST /internal/v2/generate` |
| Corpus chạy Compose G2 | `synthetic-demo-v1`, `D0_SYSTEM_SMOKE` |

## Tổng quan

Luồng G2 hiện tại:

```text
message
→ Backend retrieval trên corpus đã ingest/version hóa
→ Canonical EvidenceBundle (giữ URL, score, metadata trong Backend)
→ allowlist projection (bỏ URL, score, metadata và chat history)
→ AI Service /internal/v2/generate
→ kiểm tra request/bundle/corpus/classification/prompt/citation
→ hydrate nguồn từ bundle gốc
→ lưu answer + grounding trong PostgreSQL
→ Web hiển thị câu trả lời và nguồn HTTPS
```

Retrieval không được trộn nhiều procedure trong một bundle. Nếu nhiều procedure
cùng khớp mà chưa có filter rõ, Backend trả `NEED_CLARIFICATION`. Evidence rỗng
được short-circuit, không gọi AI.

## Chạy D0 end-to-end

Từ repository root:

```powershell
docker compose -f compose.yaml -f compose.g2.yaml --profile full up --build --detach --wait
python scripts/smoke-g2.py
```

Mở `http://localhost:3000`. D0 gồm ba thủ tục hư cấu trong
`data/demo_synthetic`; câu trả lời phải hiện cảnh báo mô phỏng và citation.
Kiểm tra readiness tại
`http://localhost:8000/health/rag`.

Tắt stack:

```powershell
docker compose -f compose.yaml -f compose.g2.yaml --profile full down --volumes --remove-orphans
```

## CLI corpus

Chạy từ `backend/` hoặc dùng đường dẫn tương đương:

```powershell
uv run --frozen python -m app.rag.cli validate `
  --repo-root .. `
  --dataset data/demo_synthetic `
  --version synthetic-demo-v1 `
  --allow-domain fixture.invalid `
  --allow-fixture
```

Các lệnh khác: `ingest`, `query`, `evaluate`. `top_k` nằm trong 1–8.

## Biến môi trường

| Biến | Ý nghĩa |
|---|---|
| `RAG_ENABLED` | Bật luồng grounded thay cho G1 mock |
| `RAG_CORPUS_VERSION` | Version immutable đã ingest |
| `RAG_TOP_K` | 1–8 |
| `RAG_ALLOW_FIXTURES` | Chỉ cho D0; bị cấm ở production |
| `GROUNDED_MAX_OUTPUT_TOKENS` | 32–2048 |
| `AI_SERVICE_URL` | Origin AI Service; Backend tự dùng route v2 |

## Gate D1 chưa đạt

`data/demo_public` mới là spike một thủ tục và toàn bộ source/gold còn chờ người
thứ hai review. Runtime validator cố ý từ chối `PENDING`; template provider cũng
cố ý chỉ nhận D0. Không đổi hai guard này để ép demo D1 chạy. Hosted adapter chỉ
được thêm sau khi công ty duyệt provider, loại dữ liệu và secret mới được đặt
trực tiếp trong `.env` local/secret store.

Contract canonical: [docs/contracts-g2.md](../../../docs/contracts-g2.md).
