# Thay đổi G2 của Minh

Baseline: ZIP llm-hanh-chinh-cong-main.zip người dùng gửi. Không sửa các thư mục
web/, ai-service/, data/, scripts/, Compose hoặc CI chung. Không sửa migration G1.
Không cập nhật package dependencies; tiếp tục dùng uv.lock có sẵn.

## Đã sửa

- `backend/pyproject.toml`: pytest pythonpath, không đổi dependency.
- `backend/docs/TEST_REPORT.md`: liên kết tới báo cáo G2.
- `backend/README.md`
- `backend/app/chat.py`
- `backend/app/config.py`
- `backend/app/main.py`
- `backend/app/models.py`
- `backend/app/schemas.py`
- `backend/docs/openapi.json`
- `backend/migrations/env.py`
- `backend/tests/test_unit.py`

## Đã thêm

- `backend/docs/g2/CHANGELOG.md`
- `backend/docs/g2/TEST_REPORT.md`
- `backend/.env.example`
- `backend/app/rag/__init__.py`
- `backend/app/rag/cli.py`
- `backend/app/rag/corpus.py`
- `backend/app/rag/evaluation.py`
- `backend/app/rag/grounding.py`
- `backend/app/rag/models.py`
- `backend/app/rag/retrieval.py`
- `backend/app/rag/schemas.py`
- `backend/app/rag/store.py`
- `backend/docs/g2/README.md`
- `backend/docs/g2/contracts-g2.md`
- `backend/docs/g2/retrieval-fixture-report.json`
- `backend/docs/g2/schema-catalog.json`
- `backend/migrations/versions/0002_g2_rag.py`
- `backend/tests/fixtures/rag/README.md`
- `backend/tests/fixtures/rag/gold/questions.jsonl`
- `backend/tests/fixtures/rag/normalized/fragments.jsonl`
- `backend/tests/fixtures/rag/normalized/procedures.jsonl`
- `backend/tests/fixtures/rag/raw/snapshot.txt`
- `backend/tests/fixtures/rag/source_manifest.jsonl`
- `backend/tests/test_rag_integration.py`
- `backend/tests/test_rag_unit.py`

## Điểm ghép cần Hoan/Tú review

- Endpoint mới /internal/v1/generate-grounded, request/response trong schema-catalog.json.
- Public retrieval_filters và nullable grounding; G1 không cần gửi fields mới.
- Forward biến RAG_* trong Compose khi muốn bật G2 trong container.
- Bổ sung Web source display và corpora/gold D1 reviewed.
- Full PostgreSQL regression cần pass trước merge; mặc định RAG_ENABLED=false.
