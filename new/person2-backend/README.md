# Backend + lexical retrieval + mock AI

Backend FastAPI/SQLAlchemy async từ scaffold new/, tái dùng interpretation, templates và citation verifier từ bản backend hcc cũ. SQLite/WSGI/mocked retrieval của bản cũ không được đưa vào. Retriever chạy BM25 thật trên fragment; generator giả lập chỉ trích nguyên văn evidence, không gọi LLM/API.

## Chạy nhanh Docker Desktop (PowerShell)

Giải nén gói, mở terminal ở `new/`:

```powershell
Copy-Item .env.rag.example .env.rag
# Lệnh sau giữ nguyên backend + PostgreSQL; không dựng frontend/LLM.
docker compose --env-file .env.rag -f infra/compose.rag.yaml up --build -d
docker compose --env-file .env.rag -f infra/compose.rag.yaml ps
Invoke-RestMethod http://localhost:8000/health
```

Swagger: http://localhost:8000/docs . Mặc định bind loopback. Đây là triển khai local; chưa có URL online.

Compose dùng database container riêng, không chiếm port 5432 trên host nên không đụng PostgreSQL anh đang chạy. Trong container, host là `postgres`, không phải `127.0.0.1`. Tên database mặc định `hanh_chinh_mvp`. DB dùng volume bền vững `rag_postgres_data`. Không chạy `down -v` nếu muốn giữ dữ liệu.

Lần đầu tự nạp 3 thủ tục/9 fragment **giả lập** khi `BOOTSTRAP_DEMO=true`. Tất cả output mock được gắn nhãn; chưa phải chatbot tư vấn pháp luật thật. ALLOW_DRAFT=true và ngưỡng BM25 chỉ là cấu hình demo chưa tune.

Gọi thử:

```powershell
$credentials = @{ username = 'demo_user'; password = 'replace-with-a-long-local-password' } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/v1/auth/register -ContentType 'application/json' -Body $credentials -SessionVariable hcc
$body = @{ query_text_raw = 'demo alpha lệ phí'; session_id = 'minh-demo' } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/v1/answer -WebSession $hcc -ContentType 'application/json; charset=utf-8' -Body $body
```

Mật khẩu tài khoản tối thiểu 12 ký tự. Backend lưu PBKDF2-SHA256 hash và token phiên đã hash; cookie HttpOnly/SameSite=Strict hết hạn sau 12 giờ. Mỗi request lấy account từ cookie; không nhận `account_id` từ body. State/audit dùng khóa account + session, nên cùng một `session_id` không chia sẻ context giữa hai account. Chỉ metadata audit được lưu, không lưu transcript câu hỏi/trả lời. Tài khoản tự đăng ký chỉ dành cho demo local; chưa bật rate limit hay xác minh email.

Thử tiếp `còn thời gian`, `demo chung lệ phí` (mơ hồ), `zzzzzzzz` (không có bằng chứng). Endpoint `/api/v1/retrieve` trả EvidenceBundle, `/api/v1/answer` trả GroundedAnswer. Session trả thêm ở header X-Conversation-Session-Id. `/api/v1/interpret`, `/api/v1/retrieve/trace`, và `/api/v1/answer/trace` chỉ hoạt động khi `ENABLE_DEV_TRACE=true`; các endpoint này trả trace chẩn đoán ngoài shared schemas và chỉ dùng ở loopback/dev.

Snapshot normalized hiện được nạp cục bộ: 42 procedure / 289 fragment, fingerprint `26eca8804426c22afb227fcbabc174a3e61d20907809561c90d00b965d91ecd9`. Nguồn duy nhất vẫn `draft`, chưa có effective date. `ALLOW_DRAFT=true` chỉ để đánh giá local; tuyệt đối chưa phải corpus pháp lý đã duyệt.

## Dùng PostgreSQL hiện có trên máy anh (không Docker DB)

Từ `new/person2-backend/`:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install -e ../person1-retrieval
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

.env.example đã có URL anh dùng: database hanh_chinh_mvp, user app_user, port 5432. PostgreSQL/service, role và database phải tồn tại, user phải được tạo bảng. App tạo các bảng rag_* còn thiếu nhưng không tạo database/role. Không in connection URL vào log. Đổi port/mật khẩu trong .env theo máy.

## Nhập corpus thật đã xuất JSON

Ba file: source_manifest.json, procedure_records.json, procedure_fragments.json. Script chấp nhận thiếu effective_date của bản nháp và chuyển thành null, jurisdiction='unknown' thành null; không tự tạo ngày pháp lý.

Local:

```powershell
.\.venv\Scripts\python.exe scripts/import_corpus.py C:\duong-dan\corpus_json
```

Docker, chạy từ `new/` (thay đường dẫn corpus bằng thư mục của anh):

```powershell
docker compose --env-file .env.rag -f infra/compose.rag.yaml cp C:\duong-dan\corpus_json backend:/tmp/corpus_json
docker compose --env-file .env.rag -f infra/compose.rag.yaml exec backend python scripts/import_corpus.py /tmp/corpus_json
```

Import validate schema, IDs, liên kết, hash fragment; snapshot JSONB bất biến theo fingerprint và active pointer được ghi trong một transaction. API nhận snapshot mới ở request tiếp theo và rebuild index. Lưu cả corpus thành JSONB trong một bảng snapshot là lựa chọn MVP; không có bảng riêng procedure/fragment. Hash nguồn chỉ được lưu, chưa đối chiếu byte Excel vì importer này chỉ nhận JSON.

ALLOW_DRAFT=true chỉ cho chạy integration với corpus chưa duyệt. Khi tắt, draft và nguồn chưa có ngày hiệu lực không được truy hồi; corpus giả lập mặc định khi ấy không trả evidence. Metadata null không được diễn giải là đã xác minh.

## Quy tắc retrieval và hội thoại

- Dùng cùng segmenter config cho corpus/query; mặc định underthesea 9.5.0. Index BM25 trong RAM, không cần vector DB.
- Exact code/name/alias trước, vẫn lọc section khi câu hỏi nêu rõ. Alias trùng nhiều thủ tục tạo ambiguity.
- Top-2 là hai **procedure khác nhau**, score procedure=max BM25 fragment phù hợp. Tính trước top_k. Exact match có thể resolved dù score thấp; đây là routing xác định, không xác suất.
- BM25_SCORE_FLOOR=0.5 và BM25_MARGIN=0.15 **chưa tune**; không so sánh với dense cosine. Chỉ dùng demo, cần Person 3 tune trước acceptance.
- Bộ lọc jurisdiction so exact không phân biệt hoa/thường. Nguồn có effective_date tương lai bị loại. Bộ lọc ngày loại nguồn không rõ ngày; superseded_by được xét theo ngày thay thế. scope chưa có metadata nên fail closed trả low_confidence.
- Follow-up chỉ hỗ trợ tiền tố rõ như 'còn', 'vậy', 'thế', 'thủ tục đó', 'cái đó'. Câu mới không có tiền tố không kế thừa state; tên/alias hiện tại ưu tiên hơn thủ tục cũ. Không phải bộ hiểu intent hoàn chỉnh.
- Grounding xét section_type thật thay vì đoán từ nội dung. Citation verifier được tái dùng từ code cũ; mock chỉ sao chép evidence nên không bịa nội dung.
- Audit chỉ lưu IDs, fingerprint, top-2/margin/status và metadata; không lưu câu hỏi/văn bản nguồn. Mỗi request retrieve/answer thành công đều ghi audit; input lỗi validation không phải truy vấn retrieval.
- API giới hạn query 4000 ký tự, top_k 1..20. Ghi state và audit cùng transaction; PostgreSQL advisory lock serialize cùng session.

## Contract thay đổi (đã cập nhật trong gói)

source_manifest.effective_date, evidence.effective_date, procedure_record.jurisdiction nhận null. Evidence có section_type bắt buộc. Các track còn lại phải đồng bộ thư mục contracts này. Không thêm field vào RetrievalInput/EvidenceBundle/GroundedAnswer. Fixtures thật phải theo schema mới. Version đề xuất của thay đổi: demo-corpus-v2, xem CONTRACT_CHANGES.md.

## Kiểm thử

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-test.txt
.\.venv\Scripts\python.exe -m pytest -q
```

PostgreSQL integration: chỉ dùng **database test riêng/rỗng**, không dùng database chứa dữ liệu thật vì test seed và đổi state:

```powershell
$env:TEST_DATABASE_URL='postgresql+asyncpg://app_user:YOUR_PASSWORD@127.0.0.1:5432/hanh_chinh_test'
.\.venv\Scripts\python.exe -m pytest -q tests/test_api_postgres.py
```

Không đặt biến thì test PostgreSQL được skip. Xem TEST_REPORT.md để phân biệt các kiểm thử đã chạy.

## Giới hạn triển khai

`create_all` chỉ bootstrap bảng còn thiếu, không phải Alembic migration cho schema cũ. Chạy một worker cho demo. Local Docker verification: Docker Desktop 4.92.0 / Engine 29.8.0 / Compose 5.5.1; official `postgres:16` resolved to PostgreSQL 16.15. Compose health, isolated PostgreSQL integration, account isolation, and backend restart persistence passed; see `TEST_REPORT.md`. PostgreSQL is internal to the Compose network; only the API is published on loopback.

Trước public hosting, bật cookie Secure qua HTTPS, tắt tự đăng ký và trace, thêm rate limit, rà soát CSRF/origin và không đưa database ra Internet. Corpus hiện là demo/draft và generator còn mock; không dùng để tư vấn pháp luật thật.
