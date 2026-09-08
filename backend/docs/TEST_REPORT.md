# Báo cáo kiểm tra Core Backend G1

> Cập nhật: 08/09/2026<br>
> Nhánh: `g1/integration`

## Kết quả local sau integration review

| Gate | Kết quả |
|---|---|
| `uvx uv==0.11.33 lock --check` | Pass |
| `uv sync --frozen` trên Python 3.12 | Pass |
| `python -m pytest tests/test_unit.py tests/test_config.py -q` | **36 passed** |
| `python -m pytest --collect-only -q` | **55 tests collected** |
| `ruff check .` | Pass |
| `ruff format --check .` | Pass |
| `python -m app.doctor --config-only` | `CONFIG_OK`, không in password/DSN |

36 test không cần database bao phủ:

- internal AI URL/schema, response validation và request-id correlation;
- network error, HTTP error và timeout 504;
- mapping các environment root dùng trong Compose;
- DSN cũ và chế độ `DB_*`, password có ký tự đặc biệt;
- UTF-8 BOM, environment override và cấu hình không hợp lệ;
- chẩn đoán DB không làm lộ exception/secret;
- input limits, CORS/error envelope và OpenAPI contract;
- provider adapter có thể nhận provider khác `mock` trong giai đoạn sau.

## PostgreSQL integration suite

19 integration test dùng PostgreSQL thật bao phủ:

- migration trong schema sạch;
- session hash/rotation/expiry/logout;
- authentication và ownership giữa hai user;
- persistence và thứ tự history;
- idempotency và concurrent message lock;
- AI success/error/timeout/malformed response;
- retry không nhân đôi message;
- context giới hạn 100 message.

Máy local hiện không có Docker/PostgreSQL nên chưa ghi nhận các test này
là pass tại local. Workflow `.github/workflows/g1-ci.yml` dựng PostgreSQL 16,
chạy toàn bộ 55 test và là bằng chứng chính thức.

## Gate toàn hệ thống

Sau khi các job thành phần pass, CI phải:

1. build Web, Backend và AI Service image;
2. khởi động PostgreSQL từ volume sạch;
3. chạy Alembic trước Uvicorn;
4. chờ cả bốn service healthy;
5. chạy API smoke: login, create, send, retry idempotent, reload, isolation, logout;
6. chạy Playwright browser smoke: cookie/CORS, chat, reload và user isolation.

Chỉ chuyển báo cáo này sang `VERIFIED` sau khi run CI của commit tích hợp
xanh. Không lấy offline SQL generation hoặc số test collected thay cho kết quả
PostgreSQL/runtime thật.
