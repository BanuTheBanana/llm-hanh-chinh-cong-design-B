# Biên bản nghiệm thu Giai đoạn 2 – RAG bằng dữ liệu giả lập

## Báo cáo cập nhật

| Trường | Nội dung |
|---|---|
| Cập nhật gần nhất | 09/09/2026 |
| Phiên bản | `v1.0` |
| Trạng thái | `G2_COMPLETED_SYNTHETIC_SCOPE` |
| Nhánh nghiệm thu | `g2/integration` |
| Corpus | `synthetic-demo-v1` |
| Phân loại dữ liệu | `D0_SYSTEM_SMOKE` |

## Tổng

Giai đoạn 2 được nghiệm thu theo phạm vi **demo kỹ thuật bằng dữ liệu giả lập**:

```text
Web → Core Backend → RAG → EvidenceBundle → Grounded AI template
                 → citation verifier → PostgreSQL → Web hiển thị nguồn
```

Tên gọi “dataset v1 của G2” là **phiên bản dataset**, không phải phân loại `D1`.
Trong quy ước an toàn của dự án:

- `D0_SYSTEM_SMOKE`: dữ liệu hư cấu để kiểm thử hệ thống – chính là corpus G2;
- `D1_PUBLIC_DEMO`: snapshot công khai chính thức – là bước nâng cấp tùy chọn;
- `D2_COMPANY_REAL`: dữ liệu thật công ty – chỉ nhập sau khi kiểm kê quyền dùng,
  PII, nơi lưu và chính sách gửi ra model.

Dữ liệu công ty không nằm trong artifact G2 này và không được tự động commit lên
GitHub. G2 chứng minh kiến trúc chạy đúng; **không chứng minh tư vấn hành chính
đúng ngoài đời và chưa phải sản phẩm production**.

## Phân

### 1. Dataset do Tú phụ trách

`data/demo_synthetic` đã đủ để nghiệm thu:

| Thành phần | Kết quả |
|---|---:|
| Nguồn giả lập có snapshot/hash | 3 |
| Thủ tục hư cấu | 3 |
| Business field mỗi thủ tục | 8/8 |
| Fragment có provenance | 24 |
| Gold question | 33 |
| DEV / TEST | 23 / 10 |
| PII | 0 |
| Validator `publish` D0 | PASS, 0 warning |

Ba thủ tục được cố ý đặt tên hư cấu: khai sinh Sao Mai, căn cước Ánh Trăng và
khai tử Mây Trắng. Mọi câu trả lời đều phải hiển thị cảnh báo mô phỏng.

### 2. Retrieval/RAG do Minh phụ trách

- Ingest corpus có version và idempotency.
- Exact title/code/alias kết hợp keyword/BM25.
- Nhận diện tên thủ tục trong câu hỏi tự nhiên dài.
- Trả `NEED_CLARIFICATION` khi câu hỏi có thể thuộc nhiều thủ tục.
- Trả `INSUFFICIENT_DATA` khi corpus không có bằng chứng.
- Chỉ tạo `EvidenceBundle` từ source/fragment đã ingest.

Kết quả retrieval trên máy nghiệm thu:

| Split | Số câu | Recall@5 | MRR | Câu fail |
|---|---:|---:|---:|---:|
| DEV | 23 | 1.00 | 0.7595 | 0 |
| TEST đóng băng | 10 | 1.00 | 0.7500 | 0 |

Đây là metric retrieval trên corpus giả nhỏ, không được dùng làm số đo độ chính
xác pháp lý.

### 3. Grounded AI và tích hợp do Hoan phụ trách

- AI Service nhận contract `/internal/v2/generate` thay vì truy cập database.
- Template D0 chỉ diễn giải evidence và không gọi dịch vụ bên ngoài.
- Backend xác nhận mọi citation nằm trong đúng `EvidenceBundle` của request.
- Answer và nguồn được lưu cùng message; tải lại trang vẫn còn history/source.
- G1 identity/history/isolation vẫn hoạt động sau khi bật overlay G2.
- Hosted API không phải điều kiện nghiệm thu phạm vi giả lập và chưa được dùng.

### 4. Bằng chứng kiểm thử ngày 09/09/2026

| Gate | Kết quả |
|---|---|
| Data build + D0 publish validation | PASS |
| Backend | 109 test PASS; Ruff check/format PASS |
| AI Service | 42 test PASS; Ruff check/format PASS |
| Web | 10 test PASS; ESLint PASS; production build PASS |
| G1 browser regression | PASS |
| G2 API smoke, 3/3 thủ tục + history | PASS |
| G2 Chromium source + reload E2E | PASS |
| Docker health | Web, Backend, AI Service, PostgreSQL healthy |

Lệnh demo:

```powershell
docker compose -f compose.yaml -f compose.g2.yaml --profile full up --build --detach --wait
python scripts/smoke-g2.py
```

Mở `http://localhost:3000`.

## Hợp

### Kết luận nghiệm thu

G2 **hoàn thành trong phạm vi synthetic technical demo** vì đã có đủ dataset v1,
RAG, grounded output, citation verifier, persistence, Web source rendering, Docker
và regression tests.

Các việc sau không phải lỗi còn sót của G2 mà là đầu vào cho mốc tiếp theo:

1. Lập biên bản kiểm kê dataset thật của công ty: format, license/quyền dùng,
   PII, phiên bản, nơi lưu, ai được truy cập và có được gửi ra hosted API không.
2. Tạo pipeline import riêng; không ghi đè `data/demo_synthetic`.
3. Có người nghiệp vụ duyệt gold/evidence trước khi tuyên bố độ đúng hành chính.
4. Benchmark hosted hoặc model local trên cùng gold set được duyệt.
5. Chọn model lightweight và chỉ fine-tune khi error analysis chứng minh cần thiết.

Artifact chi tiết nằm tại:

- `data/demo_synthetic/reports/data-quality.md`;
- `data/demo_synthetic/reports/retrieval-dev.json`;
- `data/demo_synthetic/reports/retrieval-test.json`;
- `backend/docs/g2/TEST_REPORT.md`;
- `docs/contracts-g2.md`.
