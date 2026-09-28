# Chạy backend + retrieval, mock AI

Từ thư mục này (`new/`), PowerShell:

```powershell
Copy-Item .env.rag.example .env.rag
docker compose --env-file .env.rag -f infra/compose.rag.yaml up --build -d
Invoke-RestMethod http://localhost:8000/health
```

Mở http://localhost:8000/docs . POST /api/v1/answer:

```json
{"query_text_raw":"demo alpha lệ phí","session_id":"minh-demo","top_k":5}
```

Mặc định tự tạo corpus giả lập để demo. Truy hồi BM25 thật; AI mock trích nguyên văn evidence. Không cần API key/LLM/frontend. Cấu hình mặc định chỉ bind localhost.

Nếu dùng PostgreSQL đang chạy trên máy anh, xem person2-backend/README.md mục “Dùng PostgreSQL hiện có”. URL mặc định trong .env.example đã trỏ hanh_chinh_mvp, app_user, port 5432. Nếu chạy Compose, host DB phải là postgres; không dùng 127.0.0.1 từ container backend.

Gói này gồm các file thay đổi theo cấu trúc `new/`. Chép vào repo, đồng bộ contracts theo CONTRACT_CHANGES.md. Không xóa frontend/person3 hoặc code ngoài gói. Không chứa Excel/corpus công ty. Hướng dẫn nhập ba JSON thật và kiểm thử nằm trong person2-backend/README.md.

Chưa có triển khai online: cần server/hosting đích. Docker build và kết nối PostgreSQL thật phải kiểm tra trên máy đích; xem TEST_REPORT.md.
