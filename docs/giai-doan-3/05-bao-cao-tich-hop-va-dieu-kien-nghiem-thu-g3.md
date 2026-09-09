# Báo cáo tích hợp và điều kiện nghiệm thu G3

## Báo cáo cập nhật

| Trường | Nội dung |
|---|---|
| Cập nhật | 09/09/2026 |
| Nhánh | `g3/integration` |
| Baseline | `main` tại `g2-v1.0.0` |
| Trạng thái code | `INTEGRATED_AND_REGRESSION_TESTED` |
| Trạng thái G3 | `NOT_ACCEPTED_YET` |
| Lý do | D2 đã preflight nhưng chưa qua review/governance, chưa có TEST khóa và chưa nối contract D2 runtime |

## Tổng

Ba phần code của Tú, Minh và Hoan đã được gom vào một nhánh tích hợp. Điều này
chứng minh pipeline, validator/retrieval fixture và local provider có thể phát
triển độc lập mà không phá G1/G2. Nó chưa chứng minh chatbot trả lời đúng trên
workbook công ty.

```text
Đã có code
├─ Tú: Excel → g3-data-v1 + validator + gold draft
├─ Minh: g3-data-v1 preflight + exact/BM25 + abstain
└─ Hoan: AI Service → Qwen3-1.7B local, output/citation guard

Chưa được phép nối D2 thật
└─ review nguồn/conflict → frozen TEST → ingest/version/rollback
   → D2 projection contract → benchmark → Web/RAG/Qwen E2E
```

## Phân

### 1. Trạng thái theo task

| Task | Trạng thái chính xác | Còn thiếu để đóng |
|---|---|---|
| G3-00 | `PARTIAL` | Quyền sử dụng, người duyệt, freshness và chính sách D2 chưa có sign-off |
| G3-D01 | `PASS_ON_REAL_WORKBOOK` | 42 source, 38 procedure, 202 fragment, 4 conflict, 40 gold draft; mọi preflight gate kỹ thuật PASS |
| G3-D02 | `BLOCKED_HUMAN_REVIEW` | Duyệt source/provenance và quyết định mọi conflict thực |
| G3-D03 | `DRAFT_GENERATOR_PASS` | Reviewer thứ hai duyệt expected point/citation và khóa TEST |
| G3-R01 | `PREFLIGHT_PASS_INGEST_BLOCKED` | Chốt D2 runtime projection rồi làm ingest idempotent/pin/rollback |
| G3-R02 | `FICTIONAL_TEST_PASS` | Đo routing/Recall@5 trên TEST D2 đã duyệt |
| G3-A01 | `PASS_D0_LOCAL` | Provider local, non-thinking và citation guard đã qua test |
| G3-A02 | `BLOCKED_BY_D03_R02` | Benchmark Qwen trên TEST thật, ghi quality/latency/TTFT/VRAM |
| G3-I01 | `BLOCKED_BY_D2_CONTRACT_AND_A02` | Web → RAG D2 → Qwen local E2E, không lộ internal URI |
| G3-A03 | `WAITING_FOR_ERROR_ANALYSIS` | ADR `NO_FINE_TUNE` hoặc `START_QLORA` dựa trên A02/I01 |
| G3-A04 | `CONDITIONAL_NOT_STARTED` | Chỉ làm nếu A03 cho phép |

### 2. Những khóa an toàn không được gỡ tạm

- Không đổi nhãn D2 thành D0/D1 để lách provider allowlist.
- Không tạo URL giả khi `public_url=null`.
- Không tự đổi `PENDING_REVIEW`/`QUARANTINED` thành `APPROVED`.
- Không bật lệnh ingest khi review register còn mở.
- Không dùng hosted API cho D2 nếu chưa có văn bản cho phép.
- Không công bố raw/derived workbook, gold thật hoặc internal URI trên Git/Web/log.

### 3. Regression đã chạy trên nhánh tích hợp

| Phạm vi | Kết quả |
|---|---:|
| Data pipeline fixture 12 cột + 9 cột | 6 passed |
| Backend toàn bộ với PostgreSQL test riêng | 140 passed, 1 skipped do quyền symlink Windows |
| AI Service | 63 passed |
| Web | 10 passed; lint và production build PASS trong Node 24 container |
| Repo hygiene | PASS; spreadsheet/private path/secret pattern bị chặn |
| D0 synthetic publish | PASS |
| D1 public preflight | PASS với warning review, không bị nhận nhầm là publish-ready |

Các con số trên chỉ chứng minh regression/code fixture, không thay kết quả D2 thật.

### 4. Checklist người có quyền cần thực hiện

Build và preflight workbook thật đã hoàn tất local. Không cần chạy lại trừ khi
workbook thay đổi. Output private hiện ở
`data/company_private/company-tthc-9c38dde8-v1/`.

Các lệnh dưới đây là runbook tái lập:

Từ repository, chạy ở máy nội bộ được phép:

```powershell
uv sync --project tools/data --group dev

uv run --project tools/data hcc-build-company-data `
  --excel "dataset/<workbook>.xlsx" `
  --output-root data/company_private `
  --verify-deterministic
```

Nếu lệnh báo `UNSUPPORTED_COLUMNS_WITH_DATA_AT_INDEX`, dừng và cập nhật mapping
qua change control. Khi build thành công, lấy `dataset_version` từ output rồi chạy:

```powershell
uv run --project tools/data hcc-validate-company-data `
  --dataset "data/company_private/<dataset_version>" `
  --schema docs/giai-doan-3/schema/data-contract-v1.schema.json `
  --mode preflight `
  --expected-source-count <SO_DONG_THUC> `
  --workbook "dataset/<workbook>.xlsx"
```

Sau đó người nghiệp vụ review private output. Chỉ khi validator `--mode publish`
PASS mới bàn giao version/hash/count cho Minh; không gửi nội dung D2 qua chat.

### 5. Bằng chứng cần nộp để đổi trạng thái G3 thành hoàn thành

Không cần nộp nội dung thủ tục, chỉ nộp báo cáo sanitized:

```text
Governance sign-off: PASS
Dataset version + workbook SHA-256: present
Deterministic rebuild: PASS
Schema/reference/PII publish gate: PASS
Open conflict in approved subset: 0
Gold second review + TEST freeze: PASS
RAG routing accuracy / Recall@5: measured and meets gate
Citation binding: 100%
Qwen JSON validity / grounded precision / abstention: measured
TTFT / tokens-per-second / p95 / peak VRAM: measured
D2 Web→RAG→Qwen local E2E: PASS
G1/G2 regression: PASS
Fine-tune ADR: signed
```

## Hợp

G3 hiện đạt **code-complete cho phần có thể làm bằng fixture**, chưa đạt
**release-complete trên D2**. Việc còn lại không phải “viết thêm vài dòng code” mà
là chuỗi gate có chủ sở hữu và bằng chứng. Khi nhóm cung cấp sanitized publish
report cùng quyết định contract D2, nhánh tích hợp mới được mở ingest và E2E thật.
