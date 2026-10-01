# Frontend benchmark hành chính công

Giao diện React độc lập dành cho API Person 2. Tài khoản và phân quyền hội thoại
được xác thực ở backend; trình duyệt không gửi account ID để quyết định quyền truy cập.

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

During Vite development, `Mở fixture sandbox cục bộ` exercises the four answer/
error states without a backend. Its A/B fixture accounts are browser-only and do
not provide security or call the API. Live accounts use the backend's username /
password flow. Fixture output is synthetic, never legal guidance, and the health
indicator still reports the actual backend/database state.

Kiểm tra build bằng `npm run build`. Không commit `.env`; `.env.example` chỉ
chứa URL mặc định. Giao diện gọi `/api/v1/auth/*` để đăng nhập/đăng xuất,
`POST /api/v1/answer`, và khi chọn “Xem nguồn”, `POST /api/v1/retrieve`. Các API
bảo vệ dùng cookie HttpOnly, SameSite=Strict. Conversation state và audit được
phân vùng theo account ở backend; raw transcript không được lưu. Nút “Phiên mới”
xóa session đang hoạt động trong tab.

Trong phiên Vite, bật `Trace phát triển V2–V4` để xem raw/normalized/segmented query,
filters, requested sections, prior-state summary, source provenance, sufficiency,
citation binding, generator state, carried filters và state replacement reason.
Backend mặc định tắt endpoint trace; chỉ bật `ENABLE_DEV_TRACE=true` trên môi
trường local loopback. Với `Xem nguồn`, cùng toggle hiển thị exact/lexical mode,
ranked candidates, BM25 scores, top-two margin và confidence. Diagnostics được
trả ngoài GroundedAnswer/EvidenceBundle.

Backend Person 2 hiện chưa có CORS middleware. `npm run dev` sử dụng Vite proxy
đến `VITE_API_BASE_URL` để tránh lỗi trình duyệt. Nếu phục vụ bản `dist/` tại
origin khác backend, đặt reverse proxy cùng origin hoặc cấu hình CORS có credential
cẩn thận; không dùng wildcard origin. Không đưa secret vào biến `VITE_*` vì build
sẽ công khai biến này trong mã trình duyệt. Đặt `AUTH_COOKIE_SECURE=true` khi
chạy sau HTTPS. Mở đăng ký tài khoản chỉ phù hợp cho demo local; trước public
deployment cần giới hạn đăng ký, thêm rate limit và rà soát CSRF/origin policy.

Frontend chỉ hiển thị trạng thái và dữ liệu backend trả về. `clarification_needed`
dùng `clarification_prompt`; `insufficient_data` dùng nguyên `answer_text` an
toàn của backend; `answered` hiển thị `answer_text` và citations. “Xem nguồn”
hiển thị `EvidenceBundle`, không tự chọn thủ tục hay đánh giá citation.

Đối chiếu contract từ commit `728e13eeebe66d9aa93708c93ef74e6bbdfcf942`
của repository đích, tại `new/person2-backend/app/main.py` và `contracts/`.
Không sửa contract backend.
