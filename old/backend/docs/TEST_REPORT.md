> Báo cáo G2 mới: [g2/TEST_REPORT.md](g2/TEST_REPORT.md). Nội dung G1 bên dưới là lịch sử baseline.

# Báo cáo kiểm tra Core Backend G1

> Cập nhật: 08/09/2026<br>
> Bản chính: `main`; tag `g1-v1.0.0`<br>
> Trạng thái: `VERIFIED` tại commit `4b64f6f`<br>
> GitHub Actions: [`34197723998`](https://github.com/DOMEMON/llm-hanh-chinh-cong/actions/runs/34197723998)

## Kết quả local sau integration review

| Gate | Kết quả |
|---|---|
| `uvx uv==0.11.33 lock --check` | Pass |
| `uv sync --frozen` trên Python 3.12 | Pass |
| `python -m pytest tests/test_unit.py tests/test_config.py -q` | **39 passed** |
| `python -m pytest --collect-only -q` | **58 tests collected** |
| `ruff check .` | Pass |
| `ruff format --check .` | Pass |
| `python -m app.doctor --config-only` | `CONFIG_OK`, không in password/DSN |

39 test không cần database bao phủ:

- internal AI URL/schema, response validation và request-id correlation;
- network error, HTTP error và timeout 504;
- mapping các environment root dùng trong Compose;
- DSN cũ và chế độ `DB_*`, password có ký tự đặc biệt;
- UTF-8 BOM, environment override và cấu hình không hợp lệ;
- chẩn đoán DB không làm lộ exception/secret;
- input limits, CORS/error envelope và OpenAPI contract;
- Backend consumer chấp nhận tên provider tương lai; runtime AI Service G1 vẫn
  chỉ triển khai `mock`.

## PostgreSQL integration suite – VERIFIED

19 integration test dùng PostgreSQL thật bao phủ:

- migration trong schema sạch;
- session hash/rotation/expiry/logout;
- authentication và ownership giữa hai user;
- persistence và thứ tự history;
- idempotency và concurrent message lock;
- AI success/error/timeout/malformed response;
- retry không nhân đôi message;
- context giới hạn 100 message.

Workflow `.github/workflows/g1-ci.yml` đã dựng PostgreSQL 16, chạy migration
từ database sạch và pass **58/58 test Backend**. Đây là bằng chứng runtime
chính thức; kết quả local 39 test phía trên là vòng phản hồi nhanh bổ sung.

## Gate toàn hệ thống

CI đã pass toàn bộ chuỗi sau:

1. build Web, Backend và AI Service image;
2. khởi động PostgreSQL từ volume sạch;
3. chạy Alembic trước Uvicorn;
4. chờ cả bốn service healthy;
5. chạy API smoke: login, create, send, retry idempotent, reload, isolation, logout;
6. chạy Playwright browser smoke: cookie/CORS, chat, reload và user isolation.

Kết quả cuối: 5/5 job xanh, gồm full Compose, API smoke và Playwright browser
smoke. API message round-trip với Mock AI là **56,33 ms**; đây là baseline CI,
không phải SLA hoặc benchmark model thật. Không lấy offline SQL generation hay
số test collected thay cho kết quả PostgreSQL/runtime thật.
