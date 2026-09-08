# G2 Backend — kết quả kiểm tra

## Đã chạy trên bản bàn giao

| Lệnh / kiểm tra | Kết quả |
|---|---|
| uv sync --frozen | Cài đúng lockfile của repo; không thêm dependency |
| uv run --frozen pytest tests/test_unit.py tests/test_config.py tests/test_rag_unit.py -q | 68 passed |
| uv run --frozen ruff check . | Pass |
| uv run --frozen ruff format --check . | Pass |
| python compileall app/migrations/tests | Pass |
| alembic upgrade head --sql | Sinh SQL từ DB trống đến G2 thành công |
| alembic upgrade 0001_g1:head --sql | Sinh SQL nâng cấp G1→G2 thành công |
| pytest collection | 95 cases: 68 offline + 27 cần PostgreSQL |
| scripts/check-repo-hygiene.py | Pass trên checkout local tạm, không phát hiện common secret patterns |

Có thêm pythonpath=["."] trong pytest config để cả `uv run pytest` lẫn
`uv run python -m pytest` import app đúng khi chạy từ backend/.

68 offline cases gồm 39 baseline unit/config và 29 G2 cases. Đã kiểm tra hashes,
reference/provenance, path traversal, fixture opt-in, domain allowlist, exact/
alias/không dấu, BM25, scope/time filters, ambiguity, no-hit không gọi AI,
request ID/citation allowlist, HTTP errors/timeout/schema và evaluation fixture.

## Kết quả fixture retrieval (không phải chất lượng nghiệp vụ)

Corpus synthetic fixture-v1: 1 thủ tục giả, 3 fragment, 10 câu DEV, 7 câu có gold
fragment để tính recall/MRR. Các case còn lại kiểm tra no-hit/filter.

- Recall@5: 1.0.
- MRR: 1.0.
- Query fail trong run này: 0/10.
- p50: khoảng 0.0703 ms; p95: khoảng 0.4242 ms.
- Đo retrieval in-memory trong một run, không gồm ingest/DB load/generation/network.

Raw result từng question ID và corpus SHA-256 trong retrieval-fixture-report.json.
Các câu hỏi được tạo để kiểm tra kỹ thuật; không được dùng điểm này để tuyên bố
độ chính xác hành chính hoặc làm threshold G2. Chưa có corpus/gold D1 của Tú.

## Chưa chạy — không tính là pass

27 PostgreSQL tests gồm 19 baseline và 8 G2 integration cases. G2 cases kiểm tra
idempotent/concurrent ingest, version conflict, corpus pinning, source persistence,
retry/filter conflict, isolation, no-evidence, AI failure, citation retry và
migration G1 history→G2 giữ nguyên. Cần chạy cùng PostgreSQL16 trước merge.

Môi trường bàn giao không có PostgreSQL server hoặc Docker khả dụng. Không dùng
SQLite để thay thế các gate cần PostgreSQL. Offline SQL generation không chứng
minh migration online hoặc transaction/advisory lock đã pass.

Chưa chạy hosted AI, Compose full-stack hoặc Web source rendering G2. Repo hiện
chỉ có AI endpoint G1; Hoan cần bổ sung generate-grounded. Nguồn D1/gold reviewed,
provider approval và end-to-end G2 là các phụ thuộc còn lại.

Ingest latency/orchestration latency đã có instrumentation, nhưng chưa có số đo
thành công với PostgreSQL/AI thật trong lượt này. Không điền số giả vào report.

## Bằng chứng G1 cũ

Repo đầu vào ghi G1 đã đạt 58 backend tests trên PostgreSQL và full-stack CI tại
run34197723998. Đây là baseline của nhóm trước thay đổi G2, không phải kết quả
regression G2 mới. Cần chạy lại suite đầy đủ dù baseline cũ đã xanh.
