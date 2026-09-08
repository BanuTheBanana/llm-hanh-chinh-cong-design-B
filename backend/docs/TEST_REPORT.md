# Báo cáo kiểm tra — Backend G1 cập nhật cấu hình

## Đã chạy

| Kiểm tra | Kết quả |
|---|---|
| `ruff check .` | Pass |
| `ruff format --check .` | Pass |
| `pytest tests/test_unit.py tests/test_config.py -q` | 32 passed |
| `python -m app.doctor --config-only` | CONFIG_OK, default DB_* port 15432 |
| `python -m app.doctor` khi không có PostgreSQL | DB_NETWORK_ERROR gọn, không traceback/mật khẩu |
| `alembic upgrade head --sql` | Sinh SQL PostgreSQL offline thành công |
| Python compileall | Pass |

14 config/diagnostic test cases mới kiểm tra: mật khẩu đặc biệt được giữ nguyên
qua URL object, hỗ trợ DATABASE_URL cũ và độ ưu tiên, URL trống dùng DB_*, từ chối
URL/driver/port sai, đọc UTF-8 BOM, shell override, phân loại SQLSTATE của lỗi
xác thực/database không tồn tại và lỗi mạng. 18 unit/contract cases trước đó vẫn pass.

## Chưa xác minh

18 PostgreSQL integration cases đã viết nhưng chưa chạy được trong môi trường
bàn giao vì không có Docker daemon/PostgreSQL server khả dụng. Không thay bằng
SQLite và không khẳng định migration online đã thành công. Integration fixtures
chạy migration thật trong schema PostgreSQL riêng khi có TEST_DATABASE_URL.

Chưa chạy Docker image build, Compose runtime, hoặc Web/AI end-to-end của nhóm.
Doctor đã được kiểm tra với lỗi network thực tế tại môi trường không có server;
không coi đó là kiểm chứng đường kết nối PostgreSQL thành công.

README có lệnh chạy từng gate trên máy người dùng. Nội dung báo cáo không khẳng
định lỗi mật khẩu trên máy người dùng đã được sửa chỉ nhờ tải bản cập nhật.

## Phạm vi bản cập nhật

Giữ schema/migration 0001_g1 và public API. Thêm cấu hình DB_* tương thích DSN cũ,
lệnh doctor, Compose chỉ cho DB local và hướng dẫn theo hai lộ trình database
hiện có/môi trường mới. Không đổi password hoặc truy cập database của người dùng.
