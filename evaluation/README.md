# G2 offline evaluation

## Báo cáo cập nhật

| Trường | Nội dung |
|---|---|
| Cập nhật gần nhất | 09/09/2026 |
| Phiên bản | `v0.2` |
| Trạng thái | `OFFLINE_FIXTURE_READY` |
| Dữ liệu | `D0_SYSTEM_SMOKE`, hoàn toàn giả lập |
| Candidate | `template`, không gọi mạng và không cần API key |

## Tổng

Harness này kiểm tra contract grounded, citation allowlist, abstention và khả năng
tạo báo cáo trước khi có data của Tú hoặc RAG của Minh. Kết quả fixture không phải
độ chính xác nghiệp vụ và không được dùng để quảng bá chất lượng sản phẩm.

Fixture D0 hiện có 8 case: answer, evidence rỗng, gold ở hạng 2, clarification,
evidence không liên quan, nguồn hết/chưa hiệu lực, prompt injection và retrieval
query-fail. Manifest giữ SHA-256 của chính file case để report truy đúng đầu vào.

## Chạy

Từ repository root:

```powershell
uv run --project ai-service --frozen python -m app.evaluation validate `
  --suite evaluation/fixtures/offline-smoke-v1/manifest.json

uv run --project ai-service --frozen python -m app.evaluation run `
  --suite evaluation/fixtures/offline-smoke-v1/manifest.json `
  --candidate template `
  --split DEV `
  --json-out evaluation/reports/offline-template-v1.json `
  --md-out evaluation/reports/offline-template-v1.md `
  --strict-safety
```

Không truyền API key vào câu lệnh. `template` không gọi provider bên ngoài.

## Metric

- Retrieval smoke: Recall@1, recall trong toàn bundle trả về, query-fail rate và
  MRR dựa trên thứ tự evidence trong fixture. Không gọi toàn bundle là một `k` cố
  định khi số fragment của từng case khác nhau.
- Output: status accuracy, citation ID validity và gold citation recall.
- Abstention: accuracy, unsafe-answer rate và over-abstention rate.
- Chuỗi: `lexical_expected_point_coverage` và `lexical_forbidden_claim_rate` chỉ là
  so khớp chuỗi đã chuẩn hóa, không phải đánh giá ngữ nghĩa.
- Runtime: latency p50/p95 (kể cả case lỗi), token usage và lỗi theo question ID.
- `citation_support_review=PENDING_HUMAN_REVIEW`: ID hợp lệ không chứng minh nội
  dung claim thực sự được nguồn hỗ trợ.

`--strict-safety` chặn lỗi schema/provider, citation ngoài evidence, answer khi
gold yêu cầu abstain và answer thiếu citation. Lexical forbidden-claim chỉ là
metric thông tin vì so khớp chuỗi không hiểu phủ định; nó không phải hard gate.
Harness chưa áp ngưỡng chất lượng retrieval/answer trước khi có baseline và mentor
duyệt.

## Thay fixture

Sau khi sửa `cases.jsonl`, tính lại SHA-256 và cập nhật manifest. Harness sẽ từ
chối chạy nếu file và hash không khớp. Khi Tú giao gold set thật, tạo suite mới
thuộc `D1_PUBLIC_DEMO`; không ghi đè fixture D0 này.
