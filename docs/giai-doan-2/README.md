# Chỉ mục Giai đoạn 2 – Data, RAG và Hosted AI baseline

## Báo cáo cập nhật

| Trường | Nội dung |
|---|---|
| Cập nhật gần nhất | 09/09/2026 |
| Phiên bản | `v1.2` |
| Trạng thái | `HOAN_OFFLINE_READY; DATA_RAG_BRANCHES_UNDER_REVIEW` |
| Baseline | `main`, tag `g1-v1.0.0` |
| Tài liệu thực thi | [Phân công Giai đoạn 2](02-phan-cong-giai-doan-2.md) |
| Contract G2 | [Grounded AI contract](../contracts-g2.md) |

## Tổng

G2 biến chatbot kỹ thuật dùng Mock AI của G1 thành một bản demo hành chính công
phạm vi nhỏ, trả lời từ dữ liệu công khai chính thức và hiển thị được nguồn:

```text
Nguồn chính thức → snapshot/chuẩn hóa → retrieval → evidence
→ AI Service diễn giải có trích dẫn → Backend kiểm tra → Web hiển thị
```

Ba ownership chính:

- Tú: data công khai và gold questions;
- Minh: retrieval/RAG trong Core Backend;
- Hoan: AI Service, evaluation và integration.

## Phân

G2 chỉ làm 2–3 thủ tục được mentor duyệt, 30–50 câu hỏi đánh giá, retrieval tối
giản và một hosted baseline được phép dùng với dữ liệu `D1_PUBLIC_DEMO`.

G2 chưa làm model local, fine-tune, Case/memory dài hạn, Redis/queue, vector DB,
reranker hoặc crawl diện rộng. Các phần đó chỉ được mở theo kết quả đo sau G2.

## Hợp

Thứ tự đọc và làm:

1. đọc [chiến lược trung tâm](../00-chien-luoc-trien-khai-tu-nho-den-lon.md);
2. đọc toàn bộ [phân công G2](02-phan-cong-giai-doan-2.md);
3. cả nhóm khóa scope và năm schema G2;
4. thực hiện spike một thủ tục trước;
5. chỉ mở rộng khi checkpoint một thủ tục đã chạy end-to-end.

Nền móng Hoan đã có:

- [Grounded API contract G2](../contracts-g2.md);
- API v2 + template offline trong [`ai-service/`](../../ai-service/README.md);
- [evaluation fixture và cách chạy](../../evaluation/README.md).
