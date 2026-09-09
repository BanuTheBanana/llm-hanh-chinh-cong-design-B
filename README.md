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

**Giai đoạn 3 đã bắt đầu ở checkpoint audit/strategy:** workbook công ty có 42
bản ghi và 38 tên thủ tục sau chuẩn hóa. Dữ liệu chưa được ingest vì có email,
duplicate xung đột và thiếu provenance/hiệu lực. Chiến lược đã chốt là preprocess
và RAG trước, sau đó chạy Qwen3-1.7B local zero-shot; QLoRA chỉ được mở bằng error
analysis. Raw và derived company data không được commit lên GitHub.

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

Mở `http://localhost:3000` và hỏi về “khai sinh Sao Mai”, “căn cước Ánh Trăng”
hoặc “khai tử Mây Trắng”; tên thủ tục có thể nằm trong một câu hỏi dài tự nhiên.
Đây là dataset D0 giả có cảnh báo rõ, không phải hướng dẫn hành chính thực tế. Readiness G2 ở
`http://localhost:8000/health/rag`.

## Tài liệu trung tâm

1. [Chiến lược từ nhỏ đến lớn](docs/00-chien-luoc-trien-khai-tu-nho-den-lon.md)
2. [Chiến lược và phân công Giai đoạn 3](docs/giai-doan-3/03-chien-luoc-va-phan-cong-giai-doan-3.md)
3. [Audit dataset công ty](docs/giai-doan-3/01-audit-dataset-cong-ty.md)
4. [Phân công Giai đoạn 2](docs/giai-doan-2/02-phan-cong-giai-doan-2.md)
5. [Biên bản nghiệm thu Giai đoạn 2](docs/giai-doan-2/NGHIEM-THU-G2.md)
6. [Chỉ mục Giai đoạn 2](docs/giai-doan-2/README.md)
7. [Grounded API contract G2](docs/contracts-g2.md)
8. [Phân công và nghiệm thu Giai đoạn 1](docs/01-phan-cong-giai-doan-1.md)
9. [API contract G1](docs/contracts-g1.md)
10. [Chỉ mục lưu trữ Giai đoạn 1](docs/giai-doan-1/README.md)

## Cấu trúc repository

```text
.
├── web/                 # React/TypeScript, Vitest, Playwright, Nginx
├── backend/             # FastAPI, PostgreSQL, SQLAlchemy, Alembic
├── ai-service/          # FastAPI, provider interface, MockProvider
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
└── .env.example         # Cấu hình demo, không có secret thật
```

## Branch

| Vai trò | Branch |
|---|---|
| Bản chính đã hoàn tất G1 | `main`, tag `g1-v1.0.0` |
| Bản G2 synthetic đã nghiệm thu | `g2/integration`, phát hành bằng tag `g2-v1.0.0` |
| Tích hợp G3 đang thực hiện | `g3/integration` |
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
