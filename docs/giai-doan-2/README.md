# Chỉ mục Giai đoạn 2 – Data, RAG và Grounded AI

## Báo cáo cập nhật

| Trường | Nội dung |
|---|---|
| Cập nhật gần nhất | 09/09/2026 |
| Phiên bản | `v1.4` |
| Trạng thái | `G2_I01_D0_TECHNICAL_PASS; G2_FINAL_BLOCKED_BY_D1_AND_HOSTED_APPROVAL` |
| Nhánh tích hợp | `g2/integration` |
| Baseline | `main`, tag `g1-v1.0.0` |
| Contract | [Grounded AI contract](../contracts-g2.md) |

## Tổng

G2 đang được làm theo hai checkpoint tách biệt:

```text
I01/D0 kỹ thuật: fixture giả → retrieval → grounded AI → verifier → Web + source
                          ĐÃ CHẠY END-TO-END

G2/D1 nghiệp vụ: nguồn công khai được review → 2–3 thủ tục → 30–50 gold questions
                 → hosted baseline được duyệt → báo cáo chất lượng
                          CHƯA ĐẠT
```

Vì vậy nhóm đã chứng minh được kiến trúc và contract chạy thật nhưng chưa được
tuyên bố chatbot trả lời hành chính chính xác. D0 dùng ba thủ tục hư cấu trong
`data/demo_synthetic`.

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

### Phần cố ý chưa mở khóa

- `data/demo_public` vẫn là draft một thủ tục; source và gold còn
  `PENDING_SECOND_REVIEW`.
- Nguồn hiện có chưa cung cấp đầy đủ thành phần hồ sơ và các bước thực hiện.
- Chưa đủ phạm vi 2–3 thủ tục và 30–50 câu hỏi.
- Hosted provider chưa được công ty duyệt; không dùng key đã từng dán trong chat.
- Chưa đánh giá độ đúng nghiệp vụ D1, nên chưa đặt ngưỡng chất lượng đẹp giả tạo.

### Chạy checkpoint D0

Từ repository root:

```powershell
docker compose -f compose.yaml -f compose.g2.yaml --profile full up --build --detach --wait
python scripts/smoke-g2.py
```

Mở `http://localhost:3000`; readiness ở `http://localhost:8000/health/rag`.

Kiểm tra data draft:

```powershell
python tools/data/validate_dataset.py --root . --mode preflight
python tools/data/validate_dataset.py --root . --mode publish
```

`preflight` phải pass. `publish` phải tiếp tục fail cho tới khi review và phạm vi
D1 thật sự đủ; không sửa validator để ép xanh.

## Hợp

Đọc theo thứ tự:

1. [Chiến lược trung tâm](../00-chien-luoc-trien-khai-tu-nho-den-lon.md).
2. [Phân công và task board G2](02-phan-cong-giai-doan-2.md).
3. [Contract grounded v2](../contracts-g2.md).
4. [Runbook Backend/RAG](../../backend/docs/g2/README.md).
5. [Data quality report](../../data/demo_public/reports/data-quality.md).
6. [Offline evaluation](../../evaluation/README.md).

Việc tiếp theo theo đúng thứ tự là review chéo spike, lấy nguồn chi tiết chính
thức, mở rộng D1, rồi mới xin duyệt và benchmark một hosted provider. Model local
lightweight vẫn thuộc G3 sau khi có cùng một gold set để so sánh công bằng.
