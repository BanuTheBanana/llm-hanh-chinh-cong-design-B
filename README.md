# Trợ lý hành chính công – LLM lightweight

Monorepo của nhóm Tú, Minh và Hoan. Sản phẩm được triển khai theo các
lát cắt nhỏ có gate; không dựng toàn bộ RAG/model/memory cùng lúc.

## Trạng thái

**Giai đoạn 1 – Technical Vertical Slice đã hoàn tất trên `main` và được đóng
băng bằng tag `g1-v1.0.0`.**

```text
React Web → FastAPI Core Backend → FastAPI Mock AI Service
                   ↓
              PostgreSQL
```

GitHub Actions run
[`34197723998`](https://github.com/DOMEMON/llm-hanh-chinh-cong/actions/runs/34197723998)
đã pass 5/5 job tại commit `4b64f6f`:

- 9 Web unit/component test, lint và production build;
- 15 AI Service test, lint và lockfile check;
- 58 Backend test trên PostgreSQL 16;
- repository hygiene/secret-pattern gate;
- build bốn container từ môi trường sạch, API smoke và Playwright browser smoke.

API message round-trip trong run này là **56,33 ms** với Mock AI; đây chỉ là
baseline kỹ thuật CI, không phải SLA hay benchmark model thật.

G1 chưa có RAG, Qwen, fine-tune, Case, memory dài hạn, queue hay Socket.IO.

**Giai đoạn 2 đã hoàn tất theo phạm vi demo kỹ thuật bằng dữ liệu giả lập:**
Backend ingest/retrieve corpus version hóa, gọi grounded AI v2, kiểm tra
binding/citation, lưu nguồn và Web hiển thị nguồn qua Docker Compose overlay.
Corpus `synthetic-demo-v1` có 3 thủ tục hư cấu, 24 fragment và 33 câu hỏi
DEV/TEST; toàn bộ data gate, retrieval, API smoke và browser E2E đã pass.

“Dataset v1” là số phiên bản, còn phân loại an toàn của nó vẫn là
`D0_SYSTEM_SMOKE`. Dữ liệu thật công ty thuộc luồng riêng `D2_COMPANY_REAL`, chưa
nằm trong repository và không phải điều kiện nghiệm thu G2. Xem
[biên bản nghiệm thu G2](docs/giai-doan-2/NGHIEM-THU-G2.md). Kết quả này chỉ chứng
minh hệ thống RAG chạy đúng trên dữ liệu giả, không chứng minh độ đúng hành chính
ngoài đời.

**Giai đoạn 3 đã hoàn tất ở mức nền tảng kỹ thuật demo nội bộ:** từ workbook thật,
pipeline tạo một release 10 thủ tục/49 fragment, khóa 31 DEV + 9 TEST, chạy
exact/BM25 và Qwen3-1.7B Q8_0 local qua Backend/Web với citation và PostgreSQL
history. D2 được mount read-only, pin version/hash và không được gửi tới hosted API.
Routing tự nhiên đã qua gate 10/10 tên thủ tục trực tiếp và 10/10 mẫu hội thoại;
generation sai contract có retry và fallback trích xuất evidence kèm citation.
QLoRA chưa có căn cứ nên chưa thực hiện. Đây chưa phải chứng nhận đúng nghiệp vụ
hoặc production release; raw/derived company data không được commit lên GitHub.

**Giai đoạn 4 đã tích hợp nhưng không đạt gate đánh giá độc lập tại thời điểm chấm:**
hệ thống có intent theo field, AnswerPlan/verifier và context đa lượt; DEV đạt đầy đủ
nhưng TEST_V2 chỉ đạt 85% multi-turn và TEST_V3 mới bộc lộ lỗi câu nối tiếp dài. Sau khi
mở để phân tích, các bộ TEST này chỉ còn giá trị regression, không còn là holdout.

**Giai đoạn 5 đã hoàn tất phạm vi triển khai kỹ thuật nội bộ trên demo10:** model trả lời vẫn là
Qwen3-1.7B Q8_0; Qwen3 Embedding làm fallback; intent/context dùng Qwen3-4B Q8_0 với adapter
QLoRA r16 và policy có log. Hệ thống còn có MCP quản lý nguồn review/version/rollback, context
nhiều lượt và feedback hai trục. Tuy nhiên FINAL V3 độc lập cuối chỉ đạt 81,67% full-state và
65% hội thoại trọn chuỗi, nên **không đạt acceptance intent/context** và không phải release.
Corpus đầy đủ vẫn BLOCKED. Xem [biên bản nghiệm thu G5](docs/giai-doan-5/07-nghiem-thu-giai-doan-5.md).

**Giai đoạn 6 đang triển khai trên nhánh `g6/intent-context-quality`:** policy hybrid v4 đã sửa
các bất biến clarification/follow-up/scope và thêm fast path 0-token cho yêu cầu chắc chắn.
V1–V3 đã mở đều được giữ làm regression, không dùng làm nghiệm thu. Xem
[phạm vi và gate G6](docs/giai-doan-6/01-pham-vi-va-gate.md).

## Chạy nhanh

Yêu cầu Docker Engine/Desktop và Docker Compose v2:

```powershell
Copy-Item .env.example .env
docker compose --profile full up --build --detach --wait
python scripts/smoke-e2e.py
```

Mở `http://localhost:3000`. Dừng stack mà vẫn giữ volume local:

```powershell
docker compose --profile full down
```

Chỉ dùng dữ liệu giả `D0_SYSTEM_SMOKE`; không nhập PII hay dữ liệu công ty
vào bản G1. Xem runbook riêng trong [`web/`](web/README.md),
[`backend/`](backend/README.md) và [`ai-service/`](ai-service/README.md).

Chạy lát cắt G2/D0 có RAG và citation:

```powershell
docker compose -f compose.yaml -f compose.g2.yaml --profile full up --build --detach --wait
python scripts/smoke-g2.py
```

Khi chạy overlay Qwen local của G3, dùng smoke tương ứng (không dùng smoke G2 vốn
khóa `provider=template`):

```powershell
$env:G3_PRIVATE_DATASET_HOST_PATH = 'D:/duong-dan-noi-bo/<release-demo>'
docker compose -f compose.yaml -f compose.g3.local.yaml `
  --profile full up --build --detach --wait
```

Mở `http://localhost:3000`. Chỉ dùng release D2 đã duyệt cho demo; không sao chép
nội dung workbook vào log/chat ngoài. Readiness ở `http://localhost:8000/health/rag`.

Chạy G5 tại cổng riêng `3005` bằng script có kiểm tra corpus/model; xem lệnh đầy đủ và
hash artifact trong [runbook G5](docs/giai-doan-5/03-runbook-demo.md):

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\demo-g5.ps1 `
  -Action Start `
  -DatasetPath 'D:\duong-dan-rieng\company-demo10' `
  -GenerationModelPath 'D:\duong-dan-rieng\Qwen3-1.7B-Q8_0.gguf' `
  -EmbeddingModelPath 'D:\duong-dan-rieng\Qwen3-Embedding-0.6B-Q8_0.gguf' `
  -ReviewToken '<token-local-it-nhat-12-ky-tu>'
```

## Tài liệu trung tâm

1. [Phân công Minh/Tú: MCP thời gian thực và từ điển 38 thủ tục](docs/phan-cong-minh-tu-mcp-dictionary.md)
2. [Nghiệm thu Giai đoạn 5](docs/giai-doan-5/07-nghiem-thu-giai-doan-5.md)
2. [Lộ trình phát triển dài hạn](docs/lo-trinh-phat-trien-he-thong.md)
3. [Chiến lược từ nhỏ đến lớn](docs/00-chien-luoc-trien-khai-tu-nho-den-lon.md)
4. [Chiến lược và phân công Giai đoạn 3](docs/giai-doan-3/03-chien-luoc-va-phan-cong-giai-doan-3.md)
5. [Audit dataset công ty](docs/giai-doan-3/01-audit-dataset-cong-ty.md)
6. [Data contract G3 giữa Tú và Minh](docs/giai-doan-3/02-contract-data-g3.md)
7. [Runbook Qwen3-1.7B local](docs/giai-doan-3/04-runbook-qwen-local.md)
8. [Contract D2 Giai đoạn 3](docs/contracts-g3.md)
9. [Phân công Giai đoạn 2](docs/giai-doan-2/02-phan-cong-giai-doan-2.md)
10. [Biên bản nghiệm thu Giai đoạn 2](docs/giai-doan-2/NGHIEM-THU-G2.md)
11. [Chỉ mục Giai đoạn 2](docs/giai-doan-2/README.md)
12. [Grounded API contract G2](docs/contracts-g2.md)
13. [Phân công và nghiệm thu Giai đoạn 1](docs/01-phan-cong-giai-doan-1.md)
14. [API contract G1](docs/contracts-g1.md)
15. [Chỉ mục lưu trữ Giai đoạn 1](docs/giai-doan-1/README.md)

## Cấu trúc repository

```text
.
├── web/                 # React/TypeScript, Vitest, Playwright, Nginx
├── backend/             # FastAPI, PostgreSQL, SQLAlchemy, Alembic
├── ai-service/          # FastAPI, provider interface, MockProvider
├── source-service/      # MCP registry cho nguồn đã review và version hóa
├── training/            # Pipeline QLoRA/evaluation; artifact private không vào Git
├── data/demo_synthetic/ # Corpus D0 hoàn chỉnh để dev/test, không có giá trị pháp lý
├── data/demo_public/    # Spike D1 công khai; chưa publish khi review còn PENDING
├── evaluation/          # Fixture và report evaluation G2 offline
├── tools/data/          # Downloader bảo thủ và data quality validator
├── infra/docker/        # Ghi chú hạ tầng bổ trợ
├── scripts/             # Smoke và repository hygiene checks
├── docs/
│   ├── architecture/    # Sơ đồ tham khảo
│   ├── giai-doan-3/     # Audit, chiến lược và phân công G3 hiện tại
│   ├── giai-doan-2/     # Kế hoạch và nghiệm thu G2
│   ├── archive/         # Tài liệu cũ
│   └── parked/          # Target architecture chưa triển khai
├── .github/workflows/   # Regression G1 + technical gates G2
├── compose.yaml         # Full G1 stack và health dependencies
├── compose.g2.yaml      # Overlay D0: ingest fixture + bật grounded RAG
├── compose.g3.local.yaml # Overlay D2 private: Qwen local + mount read-only
├── compose.g5.yaml      # Overlay G5: embedding local + Source MCP
└── .env.example         # Cấu hình demo, không có secret thật
```

## Branch

| Vai trò | Branch |
|---|---|
| Baseline tích hợp G5 hiện tại | `main` (G1 được lưu tại tag `g1-v1.0.0`) |
| Bản G2 synthetic đã nghiệm thu | `g2/integration`, phát hành bằng tag `g2-v1.0.0` |
| Nền tảng G3 đã hoàn tất, chờ merge | `g3/integration` |
| G4 đã tích hợp, giữ kết quả gate lịch sử | `g4/integration` |
| Lịch sử tích hợp G5 trước khi đưa lên main | `g5/integration` |
| AI/evaluation G2 của Hoan | `g2/ai-eval-hoan` |
| Nhánh dữ liệu Tú đã nhập | `data/frontend-tu` |
| Nhánh RAG Minh đã nhập | `Minh-RAG_test` |
| Nhánh tích hợp lịch sử | `g1/integration` |
| Lịch sử Frontend của Tú | `g1/frontend-tu` |
| Lịch sử Backend của Minh | `g1/backend-minh` |
| Lịch sử AI/Integration của Hoan | `g1/ai-integration-hoan` |

Nhánh tạo nhầm `feature/frontend-tu` đã bị xóa sau khi xác nhận tree trùng
với `g1/frontend-tu`. Pull request #2 đã được review bằng CI và merge vào
`main`; source tiếp tục ở gốc repository để G2 nâng cấp trực tiếp.
