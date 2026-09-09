# G3 của Minh — preflight validator và retrieval offline

Đây là validator/retrieval G3 và đường kích hoạt read-only cho demo nội bộ, không
phải importer production. Raw Excel không đi vào runtime; Backend chỉ đọc release
đã normalize, review và pin version/hash.

## Có gì mới

- `app/rag/g3/validator.py`: đọc đúng năm JSONL, schema Draft 2020-12 offline,
  reference, review, conflict, fragment hash, row accounting và PII pattern.
- `app/rag/g3/retrieval.py`: exact title/code/alias, category filter, BM25,
  field intent, abstention, evidence allowlist, evaluation từng câu không đưa gold ID vào query.
- `app/rag/g3/cli.py`: validate/query/evaluate chỉ in ID/count/error code,
  không in câu hỏi, title, text, source URI hay locator. `ingest` cố ý trả lỗi BLOCKED.
- Schema gốc được giữ nguyên; dependency jsonschema đã cập nhật cả pyproject và uv.lock.
- Test fixture được tạo bằng code hư cấu; không lấy nội dung Excel làm test.
- Test khóa runtime schema phải giống byte-for-byte với contract trong `docs/`.
- Fixture luôn ghi JSONL bằng LF trên Windows/Linux; test symlink chỉ skip khi Windows
  không cấp quyền tạo symlink.
- `.gitignore` chặn workbook/private data, repo hygiene chặn cả file force-add.

G3 giữ nguyên DB schema G1/G2 và bổ sung projection D2 versioned. Persistence corpus
chưa đưa vào PostgreSQL theo chủ ý: foundation dùng mount read-only và pin fingerprint
của năm JSONL. `accepted_procedure_ids` chỉ là qua review gate cục bộ;
`readiness=READY_FOR_DEMO` chỉ xuất hiện khi không còn procedure bị loại, conflict
mở hoặc gold chờ review trong release đã chọn.

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

## Activation, pin và rollback

Hiện `python -m app.rag.g3.cli ingest ...` trả
`INGEST_BLOCKED_REVIEW_REGISTER_G3_RV_001_002`, exit 1, không ghi DB.
G3 foundation chủ ý không chép D2 vào PostgreSQL: nó mount release private
read-only và kích hoạt bằng `RAG_CORPUS_VERSION` + `G3_CORPUS_SHA256` + row count.
Cùng version khác hash bị từ chối; rollback là đổi lại ba pin về release cũ đã
kiểm. Importer DB giao dịch vẫn là hạng mục production sau này.

## Regression trước khi merge

Dùng database PostgreSQL test riêng như backend/README.md, sau đó:

```powershell
uv run --frozen pytest -q
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv lock --check
```

Không in connection URL có password. Full suite bao gồm test migration/DB G1/G2;
không thể thay bằng test G3 offline. Kết quả lượt bàn giao nằm trong TEST_REPORT.md.
