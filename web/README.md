# Web G1 – Trợ lý hành chính công

Frontend React + TypeScript + Vite cho lát cắt kỹ thuật Giai đoạn 1.

```text
Web :3000 → Core Backend :8000/api/v1 → Mock AI Service
                         ↓
                    PostgreSQL
```

Web chỉ gọi Core Backend và luôn gửi session cookie bằng `credentials: include`.
Không có local admin bypass hoặc câu trả lời AI hard-code trong luồng tích hợp.

## Yêu cầu

- Node.js `>=20.19.0` (khuyến nghị Node 24 LTS).
- Core Backend chạy tại URL được cấu hình bên dưới.

## Chạy phát triển

Từ thư mục `web/`:

```powershell
Copy-Item .env.example .env
npm ci
npm run dev
```

Mở `http://localhost:3000`. Vite dùng `strictPort`, nên sẽ báo lỗi thay vì âm thầm
đổi sang cổng khác và làm lệch CORS của Backend.

Biến môi trường duy nhất của G1:

```dotenv
VITE_API_BASE_URL=http://localhost:8000/api/v1
```

Đây là biến build-time. Không đưa secret vào biến có tiền tố `VITE_` vì nội dung
sẽ xuất hiện trong JavaScript gửi tới trình duyệt.

## Kiểm tra trước khi ghép nhánh

```powershell
npm test
npm run lint
npm run build
```

Test bao phủ API cookie/header, đăng nhập, tải hội thoại, pending message,
authoritative reload, retry giữ nguyên `client_message_id`, chống trộn history,
session hết hạn và logout lỗi.

Khi full Docker Compose stack đang chạy và Chromium của Playwright đã được cài:

```powershell
npx playwright install chromium
npm run test:e2e
```

Browser smoke test dùng API thật để kiểm tra cookie/CORS, gửi tin, reload
history, logout và cô lập người dùng.

## Chạy bằng Docker

Từ repository root, dùng full profile:

```powershell
docker compose --profile full up --build
```

Hoặc chỉ build frontend:

```powershell
docker build --build-arg VITE_API_BASE_URL=http://localhost:8000/api/v1 -t hanh-chinh-web ./web
docker run --rm -p 3000:3000 hanh-chinh-web
```

Image build static assets bằng Node, sau đó phục vụ bằng Nginx trên cổng `3000`.
Thay đổi `VITE_API_BASE_URL` yêu cầu build lại image.

## Contract và hành vi quan trọng

- Contract chuẩn duy nhất: [`../docs/contracts-g1.md`](../docs/contracts-g1.md).
- Web không nhận hoặc gửi `user_id`; danh tính lấy từ opaque session cookie.
- Conversation đang mở chỉ được nhớ bằng ID trong `sessionStorage`; nội dung luôn
  tải lại từ Backend sau refresh.
- Khi gửi tin, Web tạo một `client_message_id` và giữ nguyên ID đó cho đúng lần
  retry. Nếu người dùng sửa nội dung, lần gửi mới nhận ID mới.
- Khi AI lỗi, draft được giữ lại và Web tải lại user message mà Backend đã lưu.
- Request trả `401` xóa dữ liệu hội thoại khỏi UI và đưa về màn hình đăng nhập.
- Không gọi trực tiếp AI Service tại cổng `8001`.

## Giới hạn G1

Giai đoạn này chỉ dùng dữ liệu smoke giả lập. Chưa có RAG, Qwen, Case Router,
memory dài hạn, queue hoặc Socket.IO.
