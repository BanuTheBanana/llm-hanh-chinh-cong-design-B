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
Giai đoạn 2 mới bắt đầu dữ liệu thủ tục công khai và RAG tối giản.

## Chạy nhanh G1

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

## Tài liệu trung tâm

1. [Chiến lược từ nhỏ đến lớn](docs/00-chien-luoc-trien-khai-tu-nho-den-lon.md)
2. [Phân công và nghiệm thu Giai đoạn 1](docs/01-phan-cong-giai-doan-1.md)
3. [API contract G1](docs/contracts-g1.md)
4. [Chỉ mục lưu trữ Giai đoạn 1](docs/giai-doan-1/README.md)

## Cấu trúc repository

```text
.
├── web/                 # React/TypeScript, Vitest, Playwright, Nginx
├── backend/             # FastAPI, PostgreSQL, SQLAlchemy, Alembic
├── ai-service/          # FastAPI, provider interface, MockProvider
├── infra/docker/        # Ghi chú hạ tầng bổ trợ
├── scripts/             # Smoke và repository hygiene checks
├── docs/
│   ├── architecture/    # Sơ đồ tham khảo
│   ├── archive/         # Tài liệu cũ
│   └── parked/          # Target architecture chưa triển khai
├── .github/workflows/   # Năm gate CI G1
├── compose.yaml         # Full G1 stack và health dependencies
└── .env.example         # Cấu hình demo, không có secret thật
```

## Branch

| Vai trò | Branch |
|---|---|
| Bản chính đã hoàn tất G1 | `main`, tag `g1-v1.0.0` |
| Nhánh tích hợp lịch sử | `g1/integration` |
| Lịch sử Frontend của Tú | `g1/frontend-tu` |
| Lịch sử Backend của Minh | `g1/backend-minh` |
| Lịch sử AI/Integration của Hoan | `g1/ai-integration-hoan` |

Nhánh tạo nhầm `feature/frontend-tu` đã bị xóa sau khi xác nhận tree trùng
với `g1/frontend-tu`. Pull request #2 đã được review bằng CI và merge vào
`main`; source tiếp tục ở gốc repository để G2 nâng cấp trực tiếp.
