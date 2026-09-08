# Báo cáo kiểm tra — Backend G1

Ngày: 08/09/2026. Đầu vào: hai tài liệu phân công và contract G1 người dùng gửi.

## Cập nhật sau integration review

Backend đã được đồng bộ với tên biến môi trường và AI route của monorepo, bổ sung
kiểm tra HTTP 504, provider linh hoạt, giới hạn context 100 messages và log lỗi đã
redact. Kết quả kiểm tra sau thay đổi:

| Lệnh | Kết quả |
|---|---|
| `ruff check .` | Pass |
| `ruff format --check .` | Pass, 15 files formatted |
| `python -m compileall -q app migrations tests` | Pass |
| `python -m pytest tests/test_unit.py -q` | 22 passed |
| `python -m pytest --collect-only -q` | 41 tests collected |

Unit suite trên được chạy trong virtual environment tạm với Python 3.11 và các
dependency tương thích vì máy tích hợp chưa có Python 3.12/uv. Gate chính thức vẫn
cần chạy lại bằng Python 3.12 với `uv sync --frozen`; các kiểm tra PostgreSQL và
end-to-end trong phần dưới vẫn chưa được tính là pass.

## Đã chạy thành công

| Lệnh (trong backend/) | Kết quả |
|---|---|
| `uv lock`, `uv sync --frozen` | Resolve/cài dependency thành công; uv.lock đã có hash |
| `.venv/bin/ruff check .` | All checks passed |
| `.venv/bin/ruff format --check .` | Source đã được format |
| `.venv/bin/python -m pytest tests/test_unit.py -q` | 18 passed |
| `.venv/bin/python -m pytest --collect-only -q` | Thu thập được unit và integration tests |
| `.venv/bin/alembic upgrade head --sql` | Sinh SQL migration PostgreSQL offline thành công |
| `.venv/bin/python -m compileall -q app migrations tests` | Thành công |

Unit suite kiểm tra AI request schema/URL, response success, HTTP/network error,
timeout transport và deadline tổng, JSON/schema sai, request_id không khớp,
response trống; giới hạn input và từ chối user_id; error envelope/CORS;
endpoint và response schema OpenAPI.

## Chưa xác minh — không được tính là pass

18 integration cases cần PostgreSQL thật: session hash/rotation/expiry/logout,
authentication, ownership đọc/ghi, user/assistant persistence, history sau login lại,
idempotency, gửi đồng thời, giữ message khi AI error/timeout/malformed response và
retry không trùng. Mỗi fixture chạy migration thật vào PostgreSQL schema sạch.

Môi trường không có Docker/PostgreSQL server. Cài qua apt thất bại vì không hỗ trợ
chuyển user/group hệ thống. Thử binary PostgreSQL đóng gói riêng cũng không khởi
động được vì môi trường chỉ có root và không tạo được user chạy PostgreSQL.
Không thay PostgreSQL bằng SQLite và không sửa PostgreSQL để bỏ kiểm tra hệ thống.

Chưa chạy online `alembic upgrade head`/`alembic check`, Docker image build hoặc
integration với Web/AI Service của nhóm. Offline SQL generation không thay thế
online migration test. Hướng dẫn chạy các gate còn lại nằm trong README.

## Kết luận phạm vi

Source backend đã được bàn giao, nhưng chưa thể xác nhận toàn bộ Definition of Done
của Minh/G1 trước khi chạy các gate PostgreSQL và end-to-end bên trên.
