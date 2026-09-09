# G3 của Minh — preflight validator và retrieval offline

Đây là bản chuẩn bị G3-R01/R02, chưa phải importer production hay G3 đã nghiệm thu.
Đọc REVIEW_REGISTER.md trước khi tích hợp. Đã đọc ba tài liệu G3, machine schema,
contract G2 và code RAG hiện có. Raw Excel không được mở/parse/gửi API trong lượt này.

## Có gì mới

- `app/rag/g3/validator.py`: đọc đúng năm JSONL, schema Draft 2020-12 offline,
  reference, review, conflict, fragment hash, row accounting và PII pattern.
- `app/rag/g3/retrieval.py`: exact title/code/alias, category filter, BM25,
  field intent, abstention, evidence allowlist, evaluation từng câu không đưa gold ID vào query.
- `app/rag/g3/cli.py`: validate/query/evaluate chỉ in ID/count/error code,
  không in câu hỏi, title, text, source URI hay locator. `ingest` cố ý trả lỗi BLOCKED.
- Schema gốc được giữ nguyên; dependency jsonschema đã cập nhật cả pyproject và uv.lock.
- Test fixture được tạo bằng code hư cấu; không lấy nội dung Excel làm test.
- `.gitignore` chặn workbook/private data, repo hygiene chặn cả file force-add.

Không sửa G1/G2 API, DB migrations hoặc provider. Chưa implement persistence,
activation/rollback D2 vì hash contract và G2→D2 projection chưa khóa.
Fingerprint deterministic của năm JSONL phục vụ so sánh preflight, không phải bằng chứng
idempotent DB ingest. `accepted_procedure_ids` chỉ là qua review gate cục bộ;
`readiness=BLOCKED` mới là trạng thái tổng thể.

## Áp dụng gói thay đổi vào repository thật (PowerShell)

Chạy trong clone dự án của anh, không phải một thư mục ZIP không có Git:

```powershell
git status --short
git fetch origin --tags
git switch g3/rag-minh
```

Nếu branch chỉ tồn tại trên remote, dùng `git switch --track origin/g3/rag-minh`.
Nếu chưa có branch cả local/remote, sau khi xác minh tag baseline:

```powershell
git show --no-patch g2-v1.0.0
git switch -c g3/rag-minh g2-v1.0.0
```

Không reset hay ghi đè thay đổi đang làm. Gói ZIP bàn giao chỉ có file mới/thay đổi;
so sánh trước khi chép cùng đường dẫn, nhất là `.gitignore`, pyproject, uv.lock và
hygiene script. Không kèm Excel, company JSONL, secrets, venv hoặc Git history.
Nếu baseline khác bản ZIP, review/merge từng diff thay vì thay toàn bộ backend.

## Cài và thử fixture

Từ `backend/`:

```powershell
uv sync --frozen
uv run --frozen pytest tests/test_g3.py -q
uv run --frozen python -c "import runpy; from pathlib import Path; m=runpy.run_path('tests/test_g3.py'); m['write_dataset'](Path('tests/fixtures/g3-fictional'), m['fixture_groups']())"
uv run --frozen python -m app.rag.g3.cli validate --dataset tests/fixtures/g3-fictional --version fictional-g3-v1 --expected-rows 2
uv run --frozen python -m app.rag.g3.cli query --dataset tests/fixtures/g3-fictional --version fictional-g3-v1 --expected-rows 2 --query "Mẫu Alpha nộp ở đâu?"
uv run --frozen python -m app.rag.g3.cli evaluate --dataset tests/fixtures/g3-fictional --version fictional-g3-v1 --expected-rows 2 --split DEV
uv run --frozen python -m app.rag.g3.cli evaluate --dataset tests/fixtures/g3-fictional --version fictional-g3-v1 --expected-rows 2 --split TEST
```

Fixture là dữ liệu hư cấu mang nhãn D2 chỉ để test schema frozen. Hai thủ tục,
bốn câu hỏi, không chứng minh gate 95% trên dữ liệu công ty.

## Tú bàn giao dữ liệu thật

Chỉ thực hiện trên máy/hạ tầng được phép của công ty. Đặt đủ năm JSONL ở
`data/company_private/<dataset_version>/`, không chuyển vào chat/AI hay Git.
Năm tên file giống contract: source_manifest.jsonl, normalized/procedures.jsonl,
normalized/fragments.jsonl, quarantine/conflicts.jsonl, gold/questions.jsonl.
Từ backend, chạy preflight với version thật của Tú:

```powershell
$datasetVersion = 'THAY_BANG_VERSION_TU_BAN_GIAO'
uv run --frozen python -m app.rag.g3.cli validate --dataset "../data/company_private/$datasetVersion" --version $datasetVersion
```

Mặc định expected rows = 42. Đây chỉ là kiểm đếm các locator đã khai báo; cần Tú
xác nhận accounting với raw và deterministic rebuild ở máy local. Không giảm
expected rows để che source bị mất. Không tự đổi PENDING/QUARANTINED thành APPROVED.
PII regex là tripwire, có thể false positive/negative; không thay human review/DLP.
Không gửi output chứa ID công ty ra ngoài nếu chưa có quyền công bố.

## Ingest, pin và rollback

Hiện `python -m app.rag.g3.cli ingest ...` trả
`INGEST_BLOCKED_REVIEW_REGISTER_G3_RV_001_002`, exit 1, không ghi DB.
Chưa có thủ tục activation/rollback D2 được chứng minh. G2 vẫn dùng corpus pin cũ;
không trỏ RAG_CORPUS_VERSION vào version G3 và không đổi RAG_ENABLED để thử D2.
Sau sign-off, nối vào store giao dịch hiện có, thêm test ingest lặp không đổi,
version cũ khác hash bị từ chối, load kiểm hash, rollback bằng pin corpus đã được kiểm.

## Regression trước khi merge

Dùng database PostgreSQL test riêng như backend/README.md, sau đó:

```powershell
uv run --frozen pytest -q
uv run --frozen ruff check app/rag/g3 tests/test_g3.py
uv lock --check
```

Không in connection URL có password. Full suite bao gồm test migration/DB G1/G2;
không thể thay bằng 29 test G3 offline. Kết quả lượt bàn giao nằm trong TEST_REPORT.md.
