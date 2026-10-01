# Verification — backend + retrieval + mock AI

Kết quả Linux và kiểm tra grounding/state bên dưới là snapshot lịch sử trước Iteration 3. Kết quả Windows Docker/PostgreSQL mới nhất được ghi ở mục Iteration 3 cuối file.

Thực hiện trong môi trường Linux, Python 3.12.

- `python -m pytest -q` tại person2-backend: **7 passed, 1 skipped**.
- 6 test nhóm retrieval/corpus: exact alias, đúng trường, citation, ambiguity/top_k, không tìm thấy, filters fail closed, follow-up/switch, multi-field thiếu evidence, fingerprint/hash.
- 1 test nhóm FastAPI với DB transport giả lập: auth, health, answer/retrieve, session header, state, ambiguity, no-match, invalid date/top_k, audit không chứa raw query/text. Gọi segmenter thật và BM25 thật.
- 1 test API PostgreSQL thật **SKIPPED tại thời điểm báo cáo ban đầu**: TEST_DATABASE_URL chưa có. Kết quả PostgreSQL integration mới nhất nằm ở mục Iteration 3 bên dưới.
- Corpus JSON thực tế: validate và build BM25 cho 42 records/289 fragments. Chạy 42 câu hỏi tên thủ tục + lệ phí; tất cả output EvidenceBundle/GroundedAnswer qua schema. Đây là smoke test hợp đồng, **không phải accuracy benchmark**.
- PostgreSQL DDL của 4 bảng được compile bằng SQLAlchemy dialect PostgreSQL. Đây không thay thế thực thi DDL/transaction trên PostgreSQL.
- Docker Compose/Dockerfile đã soạn; thời điểm snapshot ban đầu chưa build/run do thiếu Docker engine.
- Không publish server online vì chưa có server/hosting đích.

Sau khi PostgreSQL test sẵn sàng: chạy tests/test_api_postgres.py theo README để kiểm tra kết nối, tạo bảng, seed snapshot, ghi/đọc state qua hai instance API và audit. Nên hoàn thành gate này trước khi merge/deploy ngoài localhost.

## Kiểm tra bổ sung sau khi hoàn thiện grounding/state

Windows, Python 3.12:

- `tests/test_grounding_state.py`: **15 passed**. Covers multi-field sufficiency,
	procedure/source-version consistency, citation binding, ambiguity/abstention, filter
	carry-over/reset, state replacement, and preservation of ambiguous candidate IDs.
- `py_compile` passed for the changed backend modules.
- Full backend suite in the project-local Python 3.12 venv: **22 passed, 1 skipped**.
  The skipped test is PostgreSQL integration because `TEST_DATABASE_URL` was unset.
- API mock-storage tests ran as part of that suite, including the strengthened audit
	assertions for useful metadata without raw query/answer/source text.
- The full Person 1 retrieval suite also passed: **30 passed**, including real segmenter
	integration tests. Python dependency install and test commands are documented in
	`../team-handoff/handoffs/PERSON2_TEST_HANDOFF.txt`.
- At that report date, PostgreSQL integration was pending. It has since passed in the disposable Docker test runner described below.

## Iteration 3 — Windows Docker/PostgreSQL (2026-10-01)

- Docker Desktop 4.92.0, Docker Engine 29.8.0, Compose 5.5.1; WSL2 backend.
- Pulled the standard official `postgres:16` image; runtime reported PostgreSQL 16.15 (Debian build). Compose kept the DB private to its network and published the API only on loopback.
- `docker compose up --build --detach --wait` completed; backend and PostgreSQL health checks passed. Persistent volume: `rag_postgres_data`.
- Host backend suite: **26 passed, 1 skipped** because the host process had no `TEST_DATABASE_URL`. Person 1 retrieval suite: **67 passed**.
- Formal `tests/test_api_postgres.py`: **1 passed** in a disposable Compose runner against a uniquely named isolated test database; the test database was dropped after the run.
- Live API journey verified two cookie-authenticated accounts sharing the same `session_id` without cross-account state access. Alice's state survived logout/login and a backend-container restart.
- Browser Vite journey against the live stack passed registration, Underthesea 9.5.0 interpretation trace, exact alias retrieval, ambiguity, low-confidence/no-match, jurisdiction mismatch, and multi-field diagnostics. Frontend `npm run build` passed.
- This remains a synthetic-corpus/mock-generator demo. It is not a legal-accuracy or public-security acceptance report.

## Iteration 4 — normalized evidence/grounding/state trace (2026-10-01)

- Activated the normalized local corpus in PostgreSQL: fingerprint `26eca8804426c22afb227fcbabc174a3e61d20907809561c90d00b965d91ecd9`, 42 procedures, 289 fragments. Schema/hash validation passed. The single source remains `draft` with no effective date; no authority claim is made.
- Added one-request dev-only answer/retrieve stage traces outside GroundedAnswer/EvidenceBundle. They report source/version/locator, sufficiency and missing requested sections, citation binding, mock generator status, carried filters, prior/current procedure state, and replacement/reset reason.
- Live Vite/API checks passed for normalized source provenance, a follow-up on `PROC-S01-R0003`, insufficient-data abstention for missing `eligibility`, marriage-to-birth correction replacement, and citation binding.
- Unit/mocked backend suite: **30 passed, 1 PostgreSQL test skipped on host**. Person 1 retrieval suite: **67 passed**. Frontend production build passed.
- Updated PostgreSQL integration test covers V4 source/citation/missing-field traces: **1 passed** in the isolated Docker runner against a disposable database, which was dropped after the run.
