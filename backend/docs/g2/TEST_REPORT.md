# G2 – Báo cáo kiểm thử tích hợp phạm vi synthetic

## Báo cáo cập nhật

| Trường | Nội dung |
|---|---|
| Ngày chạy | 09/09/2026 |
| Nhánh | `g2/integration` |
| Kết luận kỹ thuật | `G2_COMPLETED_SYNTHETIC_SCOPE` |
| Kết luận nghiệp vụ | Chưa đánh giá; nằm ngoài phạm vi G2 synthetic |
| Dữ liệu runtime | `synthetic-demo-v1`, `D0_SYSTEM_SMOKE`, hoàn toàn giả |

## Tổng

Lát cắt sau đã chạy thật từ trình duyệt tới PostgreSQL và quay lại Web:

```text
Web → Core Backend → retrieval fixture → EvidenceBundle
    → AI Service grounded v2 → Backend verifier → PostgreSQL → Web + source
```

Kết quả này chứng minh plumbing, contract, persistence và guardrail D0. Nó không
chứng minh độ đúng hành chính, không phải benchmark model thật và không thay thế
review dữ liệu thật ở mốc tiếp theo.

## Phân – bằng chứng đã chạy

| Phạm vi | Kết quả |
|---|---|
| Backend full suite với PostgreSQL 16 | `109 passed` |
| Backend Ruff check/format | Pass |
| AI Service test | `42 passed` |
| AI Service Ruff check/format | Pass |
| Web unit/component | `10 passed` |
| Web ESLint + production build | Pass |
| Offline grounded evaluation D0 | 8/8 case, strict safety pass |
| Data D0 synthetic publish gate | Pass: 3 source, 3 procedure, 24 fragment, 33 question |
| Retrieval D0 synthetic | DEV 23/23 và TEST 10/10 pass; Recall@5 = 1.0 |
| Data D1 technical preflight | Pass: 4 source, 1 procedure, 10 fragment, 10 question |
| Docker Compose G2 readiness | PostgreSQL/AI/Backend/Web healthy; corpus `synthetic-demo-v1` |
| API end-to-end smoke | Pass cho cả 3 thủ tục, gồm answer/binding/citation/history |
| Chromium G2 E2E | Pass: login, answer + source, reload vẫn còn grounding |
| OpenAPI/schema catalog regeneration | Khớp runtime Pydantic/FastAPI hiện tại |
| Repository hygiene/secret-pattern check | Pass |

Retrieval fixture hiện có 10 câu DEV; report chi tiết nằm tại
[`retrieval-fixture-report.json`](retrieval-fixture-report.json). Recall@5 và MRR
đều 1.0 trên fixture nhỏ được tạo để kiểm tra kỹ thuật. Latency thay đổi theo mỗi
run và được lưu trong artifact; không dùng số đó làm SLA hay kết luận chất lượng
D1.

Dataset phát triển đầy đủ hơn ở `data/demo_synthetic` có 23 DEV + 10 TEST; cả hai
split không có câu fail, Recall@5 = 1.0, MRR lần lượt 0.7595 và 0.75. Đây vẫn chỉ
là D0 hư cấu, không phải bằng chứng nghiệp vụ.

Grounded evaluation có 8 case giả bao phủ answer, empty evidence, ranking,
clarification, evidence không liên quan, hiệu lực, prompt injection và retrieval
failure. Report tại
[`evaluation/reports/offline-template-v1.md`](../../../evaluation/reports/offline-template-v1.md)
ghi prompt `g2-grounded-v2`, status accuracy/citation validity/abstention accuracy
đều 1.0 và unsafe-answer rate 0 trên chính fixture này.

## Hợp – kết luận

Phạm vi G2 synthetic đã đủ điều kiện nghiệm thu: dataset v1, retrieval, grounded
template, citation verifier, persistence, source rendering, Docker và regression
đều pass. Biên bản chính nằm tại
[`docs/giai-doan-2/NGHIEM-THU-G2.md`](../../../docs/giai-doan-2/NGHIEM-THU-G2.md).

Các mục sau chuyển sang mốc dữ liệu/model tiếp theo, không phải gate còn thiếu của
G2 synthetic:

- kiểm kê và ingest dataset thật công ty trong môi trường được phép;
- người nghiệp vụ review evidence/gold và đặt ngưỡng chất lượng;
- hosted adapter/live baseline nếu chính sách cho phép;
- local lightweight model và benchmark trên cùng gold set.

Không dùng key đã từng xuất hiện trong chat. Khi D1 và provider được duyệt, dùng
secret mới qua `.env` local hoặc GitHub secret, tuyệt đối không ghi vào report,
command, source code hay log.
