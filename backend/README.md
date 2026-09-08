# Core Backend G1

FastAPI + PostgreSQL + SQLAlchemy async + asyncpg + Alembic. Backend quản lý demo
user, session cookie, conversation, message và gọi AI Service qua HTTP synchronous.
API giữ nguyên contract G1. Chỉ dùng dữ liệu giả D0_SYSTEM_SMOKE.

## 1. Bắt đầu ở đâu?

| Tình huống | Đọc |
|---|---|
| Đã có PostgreSQL/container từ bản cũ | Mục 2 — giữ database hiện tại |
| Cài lần đầu, muốn database local bằng Docker | Mục 3 — môi trường mới |
| Đã cài PostgreSQL trực tiếp hoặc có server PostgreSQL | Mục 4 |
| Đã cấu hình database | Mục 5 — kiểm tra, migrate, chạy backend |
| Lỗi Docker, cổng, mật khẩu, URL | Mục 10 |
| Ghép Web và AI Service | Mục 7 và docs/API_AND_DESIGN.md |

Yêu cầu: Python 3.12, [uv](https://docs.astral.sh/uv/getting-started/installation/).
Cách Docker cần Docker Engine/Desktop đang chạy, Linux containers và Compose v2.
Docker chỉ cần cho database nếu chọn mục 3; backend chạy bằng Python trên máy.

**Quy ước:** mở terminal ngay trong thư mục `backend/` đã giải nén, có
`pyproject.toml`. Không phụ thuộc tên user Windows, thư mục Downloads hay ổ đĩa.
Lệnh `uv`, `docker` bên dưới dùng được trên PowerShell, Bash và zsh trừ nơi có ghi riêng.

**Trạng thái xác minh bản này:** 32 unit/contract/config tests pass. 18 integration
cases đã có nhưng chưa chạy được trên PostgreSQL trong môi trường bàn giao.
Chưa xác minh Docker build/Compose runtime hoặc Web + AI end-to-end. Xem
[TEST_REPORT](docs/TEST_REPORT.md); không coi toàn bộ G1 DoD đã hoàn thành.

## 2. Nâng cấp từ gói backend cũ — giữ dữ liệu

1. Dừng backend đang chạy bằng Ctrl+C.
2. Giải nén bản mới vào một thư mục riêng và copy `.env` cũ sang thư mục mới.
   Không copy `.venv`; không xóa database/container/volume.
3. Mở terminal trong `backend/` mới và chạy `uv sync --frozen`.
4. Tiếp tục dùng container/server cũ. **Không chạy Compose ở mục 3** nếu muốn giữ
   nguyên database đang dùng: Compose đó tạo volume riêng và không tự nhập dữ liệu cũ.
5. Kiểm tra và migrate theo mục 5. Migration vẫn là `0001_g1`, không có migration
   mới xóa hay thay cấu trúc dữ liệu trong bản cập nhật này.

DATABASE_URL cũ vẫn được hỗ trợ. Nếu muốn chuyển sang cấu hình từng trường, bỏ
DATABASE_URL khỏi `.env` (hoặc đặt rỗng), rồi điền DB_* theo mục 6.

Ví dụ riêng cho người đã dùng container `minh-g1-postgres-15432` trong hướng dẫn cũ:

```powershell
docker start minh-g1-postgres-15432
```

Với container đó, địa chỉ host là `127.0.0.1`, cổng `15432`, database `g1`.
Mật khẩu phải là mật khẩu thật của user trong database, không nhất thiết còn là
mật khẩu khởi tạo. Xem mục 10.3 nếu xác thực thất bại.

## 3. Cài mới bằng Docker Compose

### 3.1. Cài dependency, tạo cấu hình

```text
uv sync --frozen
```

PowerShell (chỉ tạo `.env` nếu chưa có):

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
notepad .env
```

Bash/zsh:

```bash
if [ ! -f .env ]; then cp .env.example .env; fi
```

Mở `.env` bằng editor. Với môi trường mới, dùng các giá trị demo mặc định hoặc đổi
DB_PORT/DB_NAME/DB_USER/DB_PASSWORD theo nhu cầu. Để DATABASE_URL rỗng khi dùng DB_*.

### 3.2. Khởi động Docker rồi PostgreSQL

Windows/macOS: mở Docker Desktop và đợi Engine chạy. Linux: khởi động Docker Engine
theo cách cài đặt của máy. Kiểm tra:

```text
docker version
docker compose version
```

`docker version` cần hiển thị phần Server. Sau đó:

```text
docker compose -f compose.db.yaml up -d --wait
```

Compose chỉ dựng **PostgreSQL**, không dựng Web hoặc AI Service. Không đặt tên
container cố định; dùng service `db` trong các lệnh để mọi người đều dùng được.
Mặc định cổng host là **15432**, cổng trong container vẫn là **5432**.

```text
docker compose -f compose.db.yaml ps
docker compose -f compose.db.yaml port db 5432
```

Service `db` cần healthy; port mặc định là `127.0.0.1:15432`.
Tiếp tục mục 5.

### 3.3. Dữ liệu được lưu ở đâu?

Compose dùng named volume `pgdata` thuộc project `COMPOSE_PROJECT_NAME` (mặc định
`g1-backend`). Giữ nguyên project name để dùng lại volume đó. `stop` và `down`
không kèm `-v` giữ named volume; **không dùng `down -v` nếu cần giữ dữ liệu**.

Đổi POSTGRES_USER/PASSWORD/DB qua `.env` không sửa user/mật khẩu/database trong
volume đã khởi tạo. Thay đổi những giá trị đó cần thao tác trong PostgreSQL,
không phải chỉ restart container. Xem mục 10.3.

## 4. Dùng PostgreSQL đã có, không cần Docker

Tạo một database (ví dụ `g1`) và user có quyền kết nối, tạo bảng/index trong schema
ứng dụng. Có thể dùng pgAdmin hoặc công cụ quản trị của server. Điền vào `.env`:

```dotenv
DB_HOST=127.0.0.1
DB_PORT=5432
DB_NAME=g1
DB_USER=your_database_user
DB_PASSWORD='your_database_password'
DATABASE_URL=
```

Các giá trị `your_*` là chỗ cần thay. Mục này dùng cổng 5432 làm ví dụ cho PostgreSQL
cài trực tiếp; luôn dùng cổng thật của server. Không chạy `compose.db.yaml` cho
server đã có. Với PostgreSQL hosted cần TLS, dùng DSN asyncpg đúng yêu cầu của
nhà cung cấp; không tự tắt xác minh TLS để xử lý lỗi kết nối.

## 5. Kiểm tra → migrate → chạy backend

### 5.1. Xem cấu hình an toàn

```text
uv run --frozen python -m app.doctor --config-only
```

In đường dẫn `.env`, chế độ DATABASE_URL hay DB_*, host, port, database và tên các
biến shell đang override. Không in mật khẩu hoặc URL query parameters.
`CONFIG_OK` chỉ xác nhận cấu trúc cấu hình, **chưa xác nhận mật khẩu đúng**.

### 5.2. Kiểm tra kết nối thật

```text
uv run --frozen python -m app.doctor
```

Cần thấy `DB_OK`. Nếu báo lỗi, xử lý theo mã ở mục 10 trước khi chạy Alembic.
Lệnh này chỉ đọc; không tạo bảng, thay mật khẩu hoặc xóa dữ liệu.

### 5.3. Tạo/cập nhật bảng

```text
uv run --frozen alembic upgrade head
uv run --frozen alembic current
```

Chỉ chạy lệnh tiếp theo khi lệnh trước thành công. Mong đợi `0001_g1 (head)`.
Migration tạo users, sessions, conversations, messages; Alembic quản lý thêm
alembic_version. Không chạy `downgrade base` để sửa lỗi kết nối: nó xóa bảng.

### 5.4. Khởi động API

```text
uv run --frozen uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log --log-config logging.json
```

Giữ terminal chạy, mở:

- [Health](http://localhost:8000/health) → `{"status":"ok"}` khi DB sẵn sàng.
- [Swagger](http://localhost:8000/docs) → thử API bằng trình duyệt.
- [OpenAPI](http://localhost:8000/openapi.json) → schema public API.

Cổng backend 8000 độc lập với cổng database 15432. Dùng `--host 0.0.0.0` nếu chạy
backend trong container; Dockerfile đã cấu hình như vậy.

### 5.5. Những lần chạy sau

Với Compose local:

```text
docker compose -f compose.db.yaml up -d --wait
uv run --frozen uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log --log-config logging.json
```

Với database cũ/cài trực tiếp: chỉ đảm bảo database chạy rồi chạy Uvicorn.
Không copy đè `.env`, tạo lại database hay reset migration mỗi lần chạy.
Dừng API bằng Ctrl+C; dừng Compose local bằng:

```text
docker compose -f compose.db.yaml stop
```

## 6. Cấu hình

Ứng dụng đọc `.env` cạnh `pyproject.toml`, theo đường dẫn thư mục backend, hỗ trợ
UTF-8 và UTF-8 BOM. Environment của tiến trình ưu tiên hơn `.env`.

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| DB_HOST | 127.0.0.1 | Địa chỉ PostgreSQL |
| DB_PORT | 15432 | Cổng PostgreSQL nhìn từ backend |
| DB_NAME | g1 | Database |
| DB_USER | postgres | Database user |
| DB_PASSWORD | postgres | Mật khẩu demo; thay theo database thực tế |
| DATABASE_URL | rỗng | Nếu có giá trị, ưu tiên hơn toàn bộ DB_* |
| COMPOSE_PROJECT_NAME | g1-backend trong .env.example | Namespace Compose/volume; giữ ổn định |
| AI_SERVICE_URL | http://localhost:8001/internal/v1 | Base URL, chưa gồm /generate |
| AI_TIMEOUT_SECONDS | 10 | Deadline tổng khi gọi AI |
| SESSION_COOKIE_NAME | g1_session | Tên cookie |
| SESSION_SECURE | false | Đặt true khi chạy HTTPS |
| SESSION_TTL_SECONDS | 86400 | Thời hạn session tính bằng giây |
| CORS_ORIGINS | ["http://localhost:3000"] | JSON array origin của Web |

Khuyến nghị dùng DB_* để mật khẩu có `@`, `/`, `:`, `#`, `%` không cần tự URL-encode.
Trong `.env`, đặt mật khẩu trong dấu nháy đơn nếu chứa `$` hoặc `#` để tránh nội suy
và comment. Không URL-encode giá trị DB_PASSWORD. SQLAlchemy tạo URL object trực tiếp.

Cách cũ vẫn dùng được:

```dotenv
DATABASE_URL=postgresql+asyncpg://postgres:postgres@127.0.0.1:15432/g1
```

Nếu dùng DATABASE_URL với mật khẩu có ký tự đặc biệt, phải URL-encode thành phần
mật khẩu. Không cấu hình đồng thời hai kiểu với thông tin khác nhau.

Compose local đọc DB_*; nó **không phân tích DATABASE_URL**. Vì vậy môi trường mới
ở mục 3 cần để DATABASE_URL rỗng. Nếu dùng URL cũ, chọn mục 2 hoặc 4.

`.env` chứa thông tin riêng, không commit hay gửi toàn bộ vào chat. File ví dụ chỉ
chứa giá trị demo. Các ví dụ không dùng thông tin MongoDB/Atlas.

## 7. Ghép Web và AI Service

API public: `http://localhost:8000/api/v1`.
Web gửi cookie bằng `credentials: "include"`; không gửi user_id để quyết định quyền.

| Method | Path sau /api/v1 | Input cơ bản |
|---|---|---|
| POST | /auth/login | {"display_name":"Demo User"} |
| POST | /auth/logout | Không cần body |
| GET | /auth/me | Không cần body |
| GET | /conversations | Không cần body |
| POST | /conversations | {} hoặc {"title":"Demo"} |
| GET | /conversations/{id}/messages | Không cần body |
| POST | /conversations/{id}/messages | client_message_id UUID và content |

Trong Swagger: login → tạo conversation → copy id → POST message với UUID mới →
GET messages. Thử cùng client_message_id để kiểm tra retry. Chưa có AI Service thì
login/conversation vẫn dùng được; gửi tin trả lỗi AI 502 và giữ user message.

Internal AI Service cần `POST /internal/v1/generate`, theo
[contract gốc](docs/contracts-g1.reference.md). Mock success/error/timeout thuộc
AI Service của nhóm. Backend không tự bịa assistant response khi AI chưa chạy.

Trong Compose chung do nhóm quản lý, backend nối PostgreSQL qua service hostname
và cổng nội bộ, ví dụ DB_HOST=postgres, DB_PORT=5432; AI_SERVICE_URL là
`http://ai-service:8001/internal/v1`. Nếu dùng DATABASE_URL thì phải cập nhật URL đó
thay vì chỉ DB_*. Không dùng 127.0.0.1 để gọi container khác.

Build context Docker backend là `./backend`. Chạy migration một lần trước khi
start/scale backend. Không dùng PgBouncer transaction pooling: khóa chống gửi đồng
thời hiện tại cần PostgreSQL session connection.

Xem [API và thiết kế](docs/API_AND_DESIGN.md) cho toàn bộ response/error codes,
quy ước cần review, ownership, session và idempotency. Demo login theo tên không
xác minh danh tính thật; chỉ dùng dữ liệu giả theo yêu cầu G1.

## 8. Tests

Không cần DB cho unit/contract/config tests:

```text
uv run --frozen pytest tests/test_unit.py tests/test_config.py -q
uv run --frozen ruff check .
uv run --frozen ruff format --check .
```

Integration suite cần database test riêng. Với Compose demo mặc định, tạo một lần:

```text
docker compose -f compose.db.yaml exec db createdb -U postgres g1_test
```

Nếu g1_test đã tồn tại thì bỏ qua bước tạo. Nếu thay DB_USER, thay `postgres` trong
lệnh bằng user thật. Với server/container cũ, tạo g1_test ở chính server đó.

PowerShell, cấu hình demo:

```powershell
$env:TEST_DATABASE_URL = 'postgresql+asyncpg://postgres:postgres@127.0.0.1:15432/g1_test'
uv run --frozen pytest -q
```

Bash/zsh:

```bash
export TEST_DATABASE_URL='postgresql+asyncpg://postgres:postgres@127.0.0.1:15432/g1_test'
uv run --frozen pytest -q
```

Sửa URL test theo thông tin thật nếu khác mặc định. TEST_DATABASE_URL là DSN đầy đủ,
không tự lấy DB_* và không dùng database g1 ứng dụng. User test cần CREATE SCHEMA.
Mỗi integration test tạo schema g1_test_UUID, chạy migration thật và dọn schema đó;
không truncate bảng ứng dụng. Thiếu TEST_DATABASE_URL sẽ báo lỗi thay vì âm thầm skip.

Kiểm tra migration sau khi kết nối thành công:

```text
uv run --frozen alembic check
```

## 9. File và thay đổi của bản cập nhật

- `app/config.py`: DB_* hoặc DATABASE_URL cũ; password ẩn trong repr; `.env` theo
  thư mục backend; UTF-8 BOM; URL.create cho mật khẩu đặc biệt.
- `app/doctor.py`: kiểm tra cấu hình/kết nối, phân loại lỗi, không in mật khẩu.
- `app/db.py`, `migrations/env.py`: dùng connection URL object; đóng migration
  engine trong finally.
- `compose.db.yaml`: database local có healthcheck, volume và cổng tùy chỉnh.
- `.env.example`: cấu hình thống nhất với Compose.
- `app/main.py`, `auth.py`, `chat.py`, `ai.py`, `models.py`, `schemas.py`: Core API
  theo G1; schema database và public API không đổi trong cập nhật này.
- `tests/`: unit, config và PostgreSQL integration.
- `uv.lock`: dependency lock; dùng `--frozen`.
- `Dockerfile`, `logging.json`: chạy backend trong container và request logging.
- `docs/`: contract gốc, OpenAPI, thiết kế và báo cáo kiểm thử.

## 10. Troubleshooting

### 10.1. Docker Engine chưa chạy

Lỗi `dockerDesktopLinuxEngine` / named pipe không tồn tại: mở Docker Desktop, đợi
Engine rồi chạy `docker version`. Nếu cần, dùng Troubleshoot → Restart Docker Desktop.
Nếu Docker báo lỗi WSL, PowerShell Administrator:

```powershell
wsl --update
wsl --shutdown
```

Lệnh shutdown dừng các phiên WSL; lưu công việc WSL trước. Mở lại Docker Desktop.
Nếu vẫn lỗi, xem thông báo của Docker Desktop; chưa chạy Alembic lúc này.

### 10.2. Bind port bị từ chối hoặc port đang được dùng

Chọn DB_PORT khác, ví dụ 15433, trong `.env`. Với Compose local, chạy lại:

```text
docker compose -f compose.db.yaml up -d --wait
```

Compose cập nhật ánh xạ port và dùng lại volume của cùng project.
Nếu DATABASE_URL đang có giá trị, cập nhật port trong URL hoặc bỏ URL để dùng DB_*.

Trên Windows, kiểm tra port đang dùng/dải dành riêng:

```powershell
Get-NetTCPConnection -LocalPort 15432 -ErrorAction SilentlyContinue
netsh interface ipv4 show excludedportrange protocol=tcp
```

Không xóa dải port hệ thống. Với container tạo thủ công, `docker start` không đổi
port; cần cấu hình container mới, giữ volume và dừng container cũ trước khi dùng
cùng dữ liệu. Không chạy hai PostgreSQL server trên một volume cùng lúc.

### 10.3. DB_AUTH_FAILED / InvalidPasswordError

Đã tới PostgreSQL nhưng xác thực không thành công. Kiểm tra host/port với doctor
để chắc đang gọi đúng database trước khi thay mật khẩu.

Với Compose demo:

```text
docker compose -f compose.db.yaml exec db psql -U postgres -d postgres
```

Với container cũ trong hướng dẫn trước:

```text
docker exec -it minh-g1-postgres-15432 psql -U postgres -d postgres
```

Nếu DB_USER không phải postgres, thay user trong lệnh bằng tài khoản quản trị đúng.
Khi vào psql, nhập:

```text
\password postgres
```

Thay tên user nếu cần. Nhập mật khẩu mong muốn hai lần (không hiện ký tự); thoát
bằng `\q`. Cập nhật DB_PASSWORD hoặc DATABASE_URL để khớp, rồi chạy doctor lại.
Nếu lệnh vào psql cũng bị chặn, cần tài khoản quản trị hợp lệ của database;
không tự tắt authentication hoặc xóa volume.

Đổi POSTGRES_PASSWORD trong cấu hình Docker không đổi mật khẩu đã lưu trong
volume cũ. Đây là lý do restart container có thể không giải quyết lỗi này.

Nếu psql local vào được nhưng backend vẫn lỗi, kiểm tra TCP bằng mật khẩu:

```text
docker compose -f compose.db.yaml exec db psql -h 127.0.0.1 -U postgres -d g1 -W -c "SELECT current_user, current_database();"
```

Với container cũ, thay tiền tố `docker compose ... exec db` bằng
`docker exec -it minh-g1-postgres-15432`. Dùng user/database thực tế nếu đã đổi.

### 10.4. CONFIG_ERROR / Could not parse SQLAlchemy URL

Chạy `uv run --frozen python -m app.doctor --config-only`. Khuyến nghị đặt
DATABASE_URL rỗng và dùng DB_*. DB_PORT phải là số, CORS_ORIGINS là JSON array.
Không copy dấu code fence hoặc nhãn dotenv vào file.

Biến môi trường shell ưu tiên hơn `.env`. Doctor chỉ ra **tên** biến override.
Nếu muốn bỏ DATABASE_URL override của phiên hiện tại:

PowerShell:

```powershell
Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue
```

Bash/zsh:

```bash
unset DATABASE_URL
```

Làm tương tự với từng DB_* đang override ngoài ý muốn. Không in/gửi cả môi trường
hoặc toàn bộ `.env` khi nhờ hỗ trợ.

### 10.5. DB_NETWORK_ERROR / DB_TIMEOUT / ConnectionRefusedError

Kiểm tra database có chạy và port mapping có khớp:

```text
docker compose -f compose.db.yaml ps
docker compose -f compose.db.yaml port db 5432
docker compose -f compose.db.yaml logs --tail 50 db
```

Với server khác, dùng công cụ quản trị tương ứng. Không dùng hostname service
Docker khi backend chạy trên Windows host; cũng không dùng localhost để gọi
container khác trong Compose chung.

### 10.6. DB_NOT_FOUND

Server đã phản hồi nhưng database DB_NAME chưa tồn tại. Tạo database đó bằng tài
khoản đủ quyền hoặc sửa DB_NAME về tên đã có. Alembic tạo bảng, không tạo database.

### 10.7. API trả 502 / AI_SERVICE_ERROR

Kiểm tra AI_SERVICE_URL, AI Service của nhóm và chế độ mock. Database khỏe không
đồng nghĩa AI đã chạy. Backend giữ user message; retry cùng client_message_id sau
khi AI hoạt động lại.

## 11. Tài liệu tham khảo

- [SQLAlchemy: URL.create và mật khẩu](https://docs.sqlalchemy.org/en/20/core/engines.html#creating-urls-programmatically)
- [Docker Compose: biến môi trường](https://docs.docker.com/compose/how-tos/environment-variables/variable-interpolation/)
- [PostgreSQL Docker image](https://hub.docker.com/_/postgres)

Trước khi chốt G1, nhóm cần chạy PostgreSQL integration suite, migration online,
Compose và Web → Core → AI smoke flow. Các quy ước bổ sung trong API_AND_DESIGN.md
vẫn cần nhóm review như bản bàn giao ban đầu.
