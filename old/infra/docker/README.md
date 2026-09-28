# Docker infrastructure — G1

Owner: Hoan. File Compose chính nằm tại repository root: `compose.yaml`.

## Các mức chạy

Compose dùng profile để ba thành viên có thể làm song song:

| Lệnh | Service được chạy | Dùng khi |
|---|---|---|
| `docker compose up --build -d` | `postgres`, `ai-service` | Hoan kiểm tra Mock AI độc lập |
| `docker compose --profile backend up --build -d` | Thêm `backend` | Ghép Backend → AI |
| `docker compose --profile full up --build -d` | Thêm `backend`, `web` | Kiểm thử end-to-end |

`postgres` và `ai-service` không nằm trong profile nên luôn sẵn sàng làm dependency.
`backend` và `web` nằm trong profile để vẫn có thể chạy từng lát; hiện cả hai đã có
code, Dockerfile và đã pass full-stack CI.

## Khởi động lần đầu

Yêu cầu Docker Desktop đã khởi động và `docker compose version` chạy được.

PowerShell:

```powershell
Copy-Item .env.example .env
docker compose config --quiet
docker compose --profile full up --build --detach --wait
docker compose ps
python scripts/smoke-e2e.py
```

Nếu máy dùng Windows PowerShell 5 thay vì PowerShell 7:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/smoke-ai.ps1
```

Địa chỉ từ máy host:

- Mock AI health: `http://localhost:8001/health`
- PostgreSQL: `localhost:5432`
- Core API khi bật profile: `http://localhost:8000`
- Web khi bật full profile: `http://localhost:3000`

Trong mạng Compose, container phải gọi nhau bằng service DNS:

- Backend → PostgreSQL: `postgres:5432`
- Backend dùng base origin `AI_SERVICE_URL=http://ai-service:8001`, sau đó gọi
  `${AI_SERVICE_URL}/internal/v1/generate`.

Không dùng `localhost` để một container gọi container khác.

## Kiểm tra và chẩn đoán

```powershell
docker compose config
docker compose ps
docker compose logs --tail 100 ai-service
docker compose logs --tail 100 postgres
```

Healthcheck có trên PostgreSQL, AI Service và Backend. Backend chỉ khởi động sau khi
PostgreSQL và AI Service healthy; Web chỉ khởi động sau khi Backend healthy.

Nếu port trên host bị chiếm, sửa port bên trái trong `.env`, ví dụ:

```dotenv
POSTGRES_PORT=55432
AI_SERVICE_PORT=18001
```

Service DNS/port trong container (`postgres:5432`, `ai-service:8001`) không thay đổi.
Các port host mặc định chỉ bind vào `127.0.0.1`, không công bố service ra mạng LAN.

Backend trong Compose nhận `DB_NAME`, `DB_USER` và `DB_PASSWORD` từ chính nhóm
`POSTGRES_*`, nên thay đổi được đồng bộ tự động. `DATABASE_URL` là override tùy
chọn; nếu tự đặt DSN này thì nó được ưu tiên và người vận hành phải bảo đảm nó
trỏ đúng database.

## Kiểm thử các Mock mode

Mặc định:

```dotenv
MOCK_MODE=success
```

Hai mode `error` và `timeout` phục vụ integration test. Sau khi đổi `.env`, recreate
AI Service để container nhận cấu hình mới:

```powershell
docker compose up --build -d --force-recreate ai-service
```

Với `timeout`, `MOCK_TIMEOUT_SECONDS` phải lớn hơn
`AI_REQUEST_TIMEOUT_SECONDS` để Backend cắt request trước và trả lỗi có kiểm soát.

## Dừng và reset

Dừng container nhưng giữ database:

```powershell
docker compose --profile full down
```

Lệnh sau xóa cả volume PostgreSQL và toàn bộ dữ liệu dev. Chỉ chạy khi đã xác nhận
không cần dữ liệu:

```powershell
docker compose --profile full down --volumes
```

Không đưa `.env`, secret, PII hoặc dataset công ty vào Git/log.
