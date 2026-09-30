# Frontend benchmark hành chính công

Giao diện React độc lập dành cho API Person 2 trên branch
`refactor/old-new-architecture`. Chỉ chứa UI và HTTP adapter. Không chứa code
backend, dữ liệu riêng, tài khoản, Docker, PostgreSQL, model hay logic nhận diện.

## Chạy local

Yêu cầu Node.js >= 20.19.

```bash
npm install
cp .env.example .env
npm run dev
```

Mở `http://localhost:5173`. Trên Windows có thể sao chép `.env.example`
thành `.env` bằng File Explorer. Đặt URL backend của **máy đang chạy** trong
`.env`:

```dotenv
VITE_API_BASE_URL=http://localhost:8000
```

Kiểm tra build bằng `npm run build`. Không commit `.env`; `.env.example` chỉ
chứa URL mặc định. Giao diện gọi `GET /health`, `POST /api/v1/answer`, và khi
chọn “Xem nguồn”, `POST /api/v1/retrieve`. Dữ liệu gửi gồm `query_text_raw`,
`filters`, `top_k`, và `session_id` ở các lượt sau. Session lấy từ header
`X-Conversation-Session-Id`; nút “Phiên mới” xóa session trong tab hiện tại.

Backend Person 2 hiện chưa có CORS middleware. `npm run dev` sử dụng Vite proxy
đến `VITE_API_BASE_URL` để tránh lỗi trình duyệt. Nếu phục vụ bản `dist/` tại
origin khác backend, backend phải cho phép origin đó hoặc đặt reverse proxy cùng
origin. Khi dùng CORS, backend cũng phải expose header
`X-Conversation-Session-Id` để browser giữ ngữ cảnh. Không cho API token/backend
secret vào biến `VITE_*` vì build sẽ công khai
biến này trong mã trình duyệt. Nếu bật `API_TOKEN` ở backend, cần một gateway
đáng tin cậy do bên triển khai quản lý; frontend này không lưu Bearer token.

Frontend chỉ hiển thị trạng thái và dữ liệu backend trả về. `clarification_needed`
dùng `clarification_prompt`; `insufficient_data` dùng nguyên `answer_text` an
toàn của backend; `answered` hiển thị `answer_text` và citations. “Xem nguồn”
hiển thị `EvidenceBundle`, không tự chọn thủ tục hay đánh giá citation.

Đối chiếu contract từ commit `728e13eeebe66d9aa93708c93ef74e6bbdfcf942`
của repository đích, tại `new/person2-backend/app/main.py` và `contracts/`.
Không sửa contract backend.
