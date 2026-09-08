# G2 của Minh — hướng dẫn triển khai và bàn giao

## 1. Đã có gì?

Code được mở rộng trên ZIP monorepo G1 do Minh gửi, giữ các chỉnh sửa tích hợp của
nhóm (AI_SERVICE_URL là origin, WEB_ORIGIN, SESSION_COOKIE_SECURE và giới hạn
history 100 messages). Chỉ thay/thêm `backend/**`; không tự sửa data của Tú,
AI Service/Web/Compose/CI của Hoan.

Pipeline:

1. Validate JSONL, raw/fragment SHA-256, reference, review state, allowlist và provenance.
2. Ingest transaction vào corpus version bất biến; nhập lại cùng snapshot là no-op.
3. Exact code/title/alias → BM25 fragment; chuẩn hóa Unicode/không dấu cho search.
4. Filter procedure_id/jurisdiction/as_of, top-k ổn định.
5. Không evidence thì abstain; có ambiguity thì hỏi phạm vi; cả hai không gọi AI.
6. Có evidence thì gọi grounded endpoint và kiểm tra IDs/correlation trước khi lưu.
7. Lưu grounding cùng message; retry thành công trả snapshot đã lưu, kể cả khi corpus active đổi.
8. CLI đánh giá Recall@k/MRR, p50/p95, từng query fail và corpus hash/split.

**Mặc định RAG_ENABLED=false**. Migration G2 vẫn cần chạy khi dùng code mới,
vì ORM có hai cột mới. G1 API và generate endpoint vẫn hoạt động theo baseline.

Bản này là phần Backend của Minh. Chưa phải toàn bộ sản phẩm G2: cần data/gold
được Tú review, grounded endpoint của Hoan và phần hiển thị nguồn trên Web.

## 2. Đọc trước khi nâng cấp

- Giữ `.env`, database và volume hiện tại; không ghi đè bằng giá trị ví dụ.
- Dừng backend cũ, đặt source mới vào repo/worktree riêng để review.
- ZIP không có metadata Git của tag; đối chiếu thay đổi trong CHANGELOG.md.
- Chạy migration một lần trước khi khởi động backend mới.
- Không downgrade để sửa kết nối. Downgrade G2 giữ G1 text nhưng xóa corpus và
  metadata grounding; không dùng khi cần giữ nguồn đã lưu.

## 3. Cài đặt backend local

Mở terminal trong thư mục `backend/` của monorepo:

```text
uv sync --frozen
```

Nếu chưa có `.env`, PowerShell:

```powershell
Copy-Item .env.example .env
```

Bash/zsh:

```bash
cp .env.example .env
```

Chỉ copy một lần. Chỉnh DB_* theo PostgreSQL thật. `.env.example` mới là ví dụ
backend local nối root Compose: user app_user, DB hanh_chinh_mvp, host port15432.
Phải khớp POSTGRES_USER/DB/PASSWORD/PORT trong `.env` tại repo root. Nếu root vẫn
POSTGRES_PORT=5432 thì backend DB_PORT=5432; hoặc đổi root port thành15432 khi bị
Windows chiếm cổng. Container luôn dùng PostgreSQL port5432 ở bên trong.

Ở repo root, có thể chạy database đã cấu hình bằng:

```text
docker compose up -d postgres
```

Quay vào backend rồi kiểm tra:

```text
uv run --frozen python -m app.doctor
uv run --frozen alembic upgrade head
uv run --frozen alembic current
```

Mong đợi revision `0002_g2_rag (head)`. Nếu doctor báo authentication/network,
xử lý theo README G1 trước. Đổi POSTGRES_PASSWORD trong `.env` không thay mật khẩu
đã lưu trong volume. Không cần Atlas, vector database hoặc hosted key cho phần này.

## 4. Chạy thử retrieval mà không cần PostgreSQL/AI

Fixture nằm ở backend/tests/fixtures/rag, gồm một thủ tục hoàn toàn giả, 3 fragment,
10 câu DEV. `fixture.invalid` không được truy cập mạng. Không dùng fixture để tư
vấn hành chính hoặc báo điểm domain. Nhãn review/author/reviewer đều là giá trị test.

Tất cả lệnh bên dưới chạy trong **backend/**; --dataset là đường dẫn tương đối
với **repo root**, không phải với terminal cwd.

```text
uv run --frozen python -m app.rag.cli validate --dataset backend/tests/fixtures/rag --version fixture-v1 --allow-domain fixture.invalid --allow-fixture
```

```text
uv run --frozen python -m app.rag.cli query --dataset backend/tests/fixtures/rag --version fixture-v1 --allow-domain fixture.invalid --allow-fixture --query "le phi" --top-k 5
```

```text
uv run --frozen python -m app.rag.cli evaluate --dataset backend/tests/fixtures/rag --version fixture-v1 --allow-domain fixture.invalid --allow-fixture --split DEV --top-k 5 --output docs/g2/retrieval-fixture-report.json
```

CLI validate/query/evaluate dùng corpus file đã kiểm tra, không đọc DB và không
cần AI. Ingest mới cần PostgreSQL. Có --repo-root để chỉ định repo root khác.

## 5. Ingest và bật G2 runtime

Sau migration:

```text
uv run --frozen python -m app.rag.cli ingest --dataset backend/tests/fixtures/rag --version fixture-v1 --allow-domain fixture.invalid --allow-fixture
```

Chạy hai lần: lần đầu inserted=true, lần sau inserted=false. Cùng version nhưng
payload/hash khác bị từ chối; muốn nhập bản mới thì dùng version mới. Ingest dùng
transaction và advisory lock theo version, không ghi một nửa corpus.

Trong backend/.env, thử fixture local:

```dotenv
RAG_ENABLED=true
RAG_CORPUS_VERSION=fixture-v1
RAG_TOP_K=5
RAG_ALLOW_FIXTURES=true
AI_SERVICE_URL=http://localhost:8001
```

AI_SERVICE_URL là origin, không có /internal/v1. Khởi động:

```text
uv run --frozen uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log --log-config logging.json
```

[Swagger](http://localhost:8000/docs): login demo → tạo conversation → gửi message.
Câu không có match (ví dụ quantumxyz) trả grounding.status=INSUFFICIENT_DATA mà
không gọi AI. Câu có evidence cần grounded API ở mục 7. AI Service G1 trong ZIP
chưa có endpoint đó nên lúc này trả 502; backend không fallback sang generate G1.

Mỗi lần đổi env active corpus/RAG mode cần restart backend. Phiên bản corpus của
mỗi request được load/pin một lần; history/replay dùng grounding đã lưu.

## 6. Nhận dữ liệu reviewed từ Tú

Cấu trúc do Tú cung cấp:

```text
data/demo_public/
  source_manifest.jsonl
  raw/...
  normalized/procedures.jsonl
  normalized/fragments.jsonl
  gold/questions.jsonl
```

Xem contracts-g2.md và schema-catalog.json. Điểm cần Tú ghép:

- Giữ raw bytes, raw_path tương đối với repo root và nằm trong dataset root.
- Source usage=D1_PUBLIC_DEMO, review_status=APPROVED sau review người thật.
- Source domain và URL host phải khớp chính xác, nằm trong allowlist đã review.
- Procedure.field_evidence trỏ từng giá trị nghiệp vụ tới fragment cùng procedure.
- Không gộp jurisdiction khác nhau vào cùng procedure; null vẫn là chưa biết.
- Fragment hash tính trên UTF-8 text nguyên văn, không qua normalize search.
- Gold reviewer khác author; expected ANSWER cần gold fragment/source; không nhập
  gold vào runtime DB. Gold.filters là input lọc nếu scenario có, gold.procedure_id
  chỉ là nhãn đúng để đánh giá, không tự đưa vào retrieval.

Ví dụ lệnh (chỉ dùng domain/version sau khi nhóm đã chọn):

```text
uv run --frozen python -m app.rag.cli ingest --dataset data/demo_public --version d1-v1 --allow-domain dichvucong.gov.vn
```

Thêm --allow-domain cho từng host thực tế được review. Không có crawler hoặc
fetch URL trong CLI. Không bật --allow-fixture với corpus D1. Đổi runtime:

```dotenv
RAG_CORPUS_VERSION=d1-v1
RAG_ALLOW_FIXTURES=false
```

Đánh giá DEV/TEST cùng corpus version:

```text
uv run --frozen python -m app.rag.cli evaluate --dataset data/demo_public --version d1-v1 --allow-domain dichvucong.gov.vn --split DEV --top-k 5 --output docs/g2/retrieval-dev.json
```

CLI không chỉnh prompt/retriever. Khóa TEST trước khi tuning; không dùng điểm TEST
để tối ưu rồi báo lại cùng split. Báo cáo fixture kèm theo không thay thế báo cáo D1.

## 7. Interface để Hoan ghép AI Service

Endpoint Hoan cần triển khai:

```text
POST /internal/v1/generate-grounded
```

Request là object có evidence_bundle, history (tối đa10 messages demo trước turn
hiện tại), max_output_tokens. Bundle có request_id/query/corpus_version/evidence.
Response GroundedAnswer có request_id, answer, status, cited_fragment_ids,
missing_information, provider, model, usage, latency_ms. Schema chính xác ở
schema-catalog.json; HTTPX contract test ở tests/test_rag_unit.py.

AI không tự thêm source URL. Backend resolve source metadata từ bundle đã pin,
kiểm request_id và citation allowlist. Citation lỗi → 502 AI_CITATION_INVALID;
malformed/HTTP lỗi khác → 502 AI_SERVICE_ERROR; timeout → 504 AI_SERVICE_TIMEOUT.
Corpus chưa sẵn sàng → 503 RAG_CORPUS_UNAVAILABLE. User message vẫn được giữ.

Kiểm ID chỉ chứng minh nguồn có trong evidence, không chứng minh mọi câu trong
answer được nguồn hỗ trợ. Hoan/Tú còn phải review claim support và forbidden points.
History/evidence là dữ liệu, không phải instruction có quyền ghi đè prompt.
Hosted chỉ bật khi provider và loại dữ liệu đã được công ty/mentor duyệt.

## 8. Interface để Web ghép nguồn

POST input G1 vẫn hợp lệ. Có thể thêm:

```json
{
  "client_message_id": "00000000-0000-4000-8000-000000000001",
  "content": "le phi",
  "retrieval_filters": {"procedure_id": null, "jurisdiction": null, "as_of": null}
}
```

POST response vẫn user_message + assistant_message. Assistant G2 có thêm grounding:
status, corpus_version, sources, missing_information. GET history trả cùng metadata.
Trường Message.status vẫn pending/completed/failed, khác với grounding.status.
G1/null grounding được bỏ khỏi JSON để giữ shape cũ; OpenAPI mô tả field optional.

Source gồm fragment_id/source_id/title/url/metadata. Web dùng nguồn trong grounding,
không tự tìm URL từ output AI. Retry giữ cùng content và filters; cùng key nhưng
filter khác trả IDEMPOTENCY_CONFLICT. Khi có turn khác đang xử lý giữ behavior409.

as_of chỉ dùng được với nguồn CONFIRMED_FROM_SOURCE có đủ khoảng ngày bao phủ.
Nguồn chưa rõ hiệu lực không bị giả định hiện hành. Nếu bỏ as_of, snapshot reviewed
có thể trả về cùng metadata UNKNOWN; UI nên hiển thị giới hạn này.

## 9. Tests và kiểm tra migration

Offline:

```text
uv run --frozen pytest tests/test_unit.py tests/test_config.py tests/test_rag_unit.py -q
uv run --frozen ruff check .
uv run --frozen ruff format --check .
```

Full suite cần PostgreSQL test riêng. Tạo database test bằng user có CREATE SCHEMA,
ví dụ ở repo root với các giá trị demo G1:

```text
docker compose exec postgres createdb -U app_user g2_test
```

Trong backend/, PowerShell:

```powershell
$env:TEST_DATABASE_URL='postgresql+asyncpg://app_user:change-me-local-only@127.0.0.1:15432/g2_test'
uv run --frozen pytest -q
```

Bash/zsh:

```bash
export TEST_DATABASE_URL='postgresql+asyncpg://app_user:change-me-local-only@127.0.0.1:15432/g2_test'
uv run --frozen pytest -q
```

Thay credential/port theo server thật; mật khẩu đặc biệt trong DSN cần URL encode.
RAG_ENABLED nên false ở environment chạy regression; G2 tests tự override config.
Mỗi fixture tạo schema riêng, chạy migration thật rồi xóa schema đó.
Có test downgrade chỉ trong schema test → tạo history G1 → upgrade G2 →
kiểm history giữ nguyên và Alembic metadata không lệch. Không chạy downgrade trên DB app.

## 10. Ghép Compose/CI chung

Root Compose hiện chưa forward các biến RAG_*. Chỉ đặt RAG_ENABLED trong root .env
không tự bật nó trong container. Hoan cần thêm vào environment của backend:

```yaml
RAG_ENABLED: ${RAG_ENABLED:-false}
RAG_CORPUS_VERSION: ${RAG_CORPUS_VERSION:-}
RAG_TOP_K: ${RAG_TOP_K:-5}
RAG_ALLOW_FIXTURES: ${RAG_ALLOW_FIXTURES:-false}
```

Minh không sửa Compose/CI của Hoan trong gói này. Có thể ingest bằng local backend
vào cùng PostgreSQL trước, rồi bật container backend đã được Hoan cấu hình.
Container DB_HOST=postgres, DB_PORT=5432; local backend dùng port publish trên host.
Hoan cần grounded route và Web source rendering để chạy full G2 smoke.

Workflow G1 hiện chạy PR vào main, nhưng push trigger chỉ main/g1/**. Nhánh g2/**
cần PR hoặc Hoan mở rộng trigger. Không có hosted calls trong backend tests;
HTTPX transport mock dùng cho cả G1 và G2. Live evaluation là phần Hoan.

## 11. Giới hạn và các gate còn lại

- Chưa có corpus D1/gold thật → chưa có chỉ số retrieval thực tế.
- Chưa chạy PostgreSQL integration trong môi trường bàn giao → cần full regression,
  migration online trên DB sạch và nâng cấp G1 trước khi merge.
- Chưa có grounded AI/Web source integration → chưa nghiệm thu G2 end-to-end.
- BM25 lexical là baseline nhỏ, chưa có stopword tuning, typo correction hay semantic
  retrieval. Không dùng score như xác suất đúng pháp lý; sửa lỗi theo DEV report.
- Runtime load corpus nhỏ từ DB mỗi request, chưa cache/index service riêng.
- Scope vẫn 2–3 thủ tục, spike1 thủ tục; không vector DB, embedding, Qwen hoặc queue.
