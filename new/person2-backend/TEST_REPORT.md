# Verification — backend + retrieval + mock AI

Thực hiện trong môi trường Linux, Python 3.12.

- `python -m pytest -q` tại person2-backend: **7 passed, 1 skipped**.
- 6 test nhóm retrieval/corpus: exact alias, đúng trường, citation, ambiguity/top_k, không tìm thấy, filters fail closed, follow-up/switch, multi-field thiếu evidence, fingerprint/hash.
- 1 test nhóm FastAPI với DB transport giả lập: auth, health, answer/retrieve, session header, state, ambiguity, no-match, invalid date/top_k, audit không chứa raw query/text. Gọi segmenter thật và BM25 thật.
- 1 test API PostgreSQL thật **SKIPPED**: TEST_DATABASE_URL chưa có. Môi trường không có Docker và không cho thiết lập PostgreSQL dưới user hệ thống; không khẳng định kết nối DB đã được kiểm thử.
- Corpus JSON thực tế: validate và build BM25 cho 42 records/289 fragments. Chạy 42 câu hỏi tên thủ tục + lệ phí; tất cả output EvidenceBundle/GroundedAnswer qua schema. Đây là smoke test hợp đồng, **không phải accuracy benchmark**.
- PostgreSQL DDL của 4 bảng được compile bằng SQLAlchemy dialect PostgreSQL. Đây không thay thế thực thi DDL/transaction trên PostgreSQL.
- Docker Compose/Dockerfile đã soạn, chưa build/run do môi trường không có Docker engine.
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
- PostgreSQL integration is still pending; run it with the disposable database described
	in the handoff before merge/deployment.
