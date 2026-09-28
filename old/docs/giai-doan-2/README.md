# Chỉ mục Giai đoạn 2 – Data, RAG và Grounded AI

## Báo cáo cập nhật

| Trường | Nội dung |
|---|---|
| Cập nhật gần nhất | 09/09/2026 |
| Phiên bản | `v1.5` |
| Trạng thái | `G2_COMPLETED_SYNTHETIC_SCOPE` |
| Nhánh tích hợp | `g2/integration` |
| Baseline | `main`, tag `g1-v1.0.0` |
| Contract | [Grounded AI contract](../contracts-g2.md) |

## Tổng

G2 đã được chốt theo phạm vi demo kỹ thuật bằng dữ liệu giả lập:

```text
G2/D0: 3 fixture giả → retrieval → grounded template → verifier → Web + source
                              ĐÃ NGHIỆM THU

Sau G2: kiểm kê data công ty → review nghiệp vụ → hosted/local baseline
                              CHƯA BẮT ĐẦU
```

“Dataset v1” là phiên bản của corpus, không phải nhãn phân loại `D1`. Corpus
G2 vẫn là `D0_SYSTEM_SMOKE` trong `data/demo_synthetic`. Nhóm đã chứng minh kiến
trúc và contract chạy thật nhưng không tuyên bố chatbot trả lời hành chính chính
xác ngoài đời. Chi tiết xem [biên bản nghiệm thu](NGHIEM-THU-G2.md).

## Phân

### Phần đã hoàn thành kỹ thuật

- Bộ `data/demo_synthetic` hoàn chỉnh cho phát triển: 3 thủ tục hư cấu, 24
  fragment, 33 câu DEV/TEST; D0 publish gate và retrieval 33/33 pass.
- Tú: spike dữ liệu công khai được sửa đường dẫn, hash, provenance và nội dung
  theo PDF; technical preflight pass.
- Minh: ingest version hóa, exact/keyword/BM25 retrieval và canonical
  `EvidenceBundle` đã được ghép vào Core Backend.
- Hoan: grounded API v2, template D0, binding/citation verifier, evaluation,
  Compose overlay, Web source rendering và CI smoke đã được ghép.
- Full D0 flow đã qua API smoke và Chromium E2E, gồm tải lại lịch sử có nguồn.

### Phần chuyển sang mốc tiếp theo

- `data/demo_public` vẫn chỉ là spike tham khảo, không phải artifact nghiệm thu G2.
- Dataset thật công ty chưa được đưa vào repo; phải kiểm kê quyền dùng và PII trước.
- Hosted provider chưa được duyệt; không dùng key đã từng dán trong chat.
- Chưa đánh giá độ đúng nghiệp vụ trên dữ liệu thật.

### Chạy bản G2 đã nghiệm thu

Từ repository root:

```powershell
docker compose -f compose.yaml -f compose.g2.yaml --profile full up --build --detach --wait
python scripts/smoke-g2.py
```

Mở `http://localhost:3000`; readiness ở `http://localhost:8000/health/rag`.

Kiểm tra dataset G2:

```powershell
python tools/data/validate_dataset.py --root . --dataset data/demo_synthetic --classification D0_SYSTEM_SMOKE --mode publish
```

Lệnh phải pass không warning. Gate này xác nhận tính toàn vẹn fixture, không xác
nhận tính đúng pháp lý.

## Hợp

Đọc theo thứ tự:

1. [Chiến lược trung tâm](../00-chien-luoc-trien-khai-tu-nho-den-lon.md).
2. [Biên bản nghiệm thu G2](NGHIEM-THU-G2.md).
3. [Phân công và task board G2](02-phan-cong-giai-doan-2.md).
4. [Contract grounded v2](../contracts-g2.md).
5. [Runbook Backend/RAG](../../backend/docs/g2/README.md).
6. [Data quality report](../../data/demo_synthetic/reports/data-quality.md).
7. [Offline evaluation](../../evaluation/README.md).

Việc tiếp theo là kiểm kê dataset thật công ty trong môi trường được phép, lấy
review nghiệp vụ rồi benchmark hosted/local theo chính sách dữ liệu. Model local
lightweight vẫn thuộc G3; không ghi đè corpus G2 và không đẩy dữ liệu nội bộ lên
GitHub.
