# Kết quả thực nghiệm G5

Các artifact chi tiết nằm trong `evaluation/reports/g5/`, được Git-ignore vì chứa dữ liệu
công ty. Báo cáo này chỉ ghi số tổng hợp.

## 1. Quyết định model

Qwen3-1.7B được chọn để thử QLoRA vì pilot G4 cho thấy cân bằng tốt hơn giữa contract,
độ trễ và VRAM so với 0.6B và 4B. Cấu hình thử: rank 16, một epoch, learning rate
`2e-4`, NF4 double quantization và BF16. Huấn luyện dùng 208 dòng TRAIN, đánh giá trong
quá trình huấn luyện dùng 40 dòng VALIDATION; không dùng TEST.
Base Hugging Face được khóa tại revision `70d244cc86ccca08cf5af4e1e306ecf908b1ad5e`;
model GGUF phục vụ được khóa bằng SHA-256 trong runbook Docker.

So sánh công bằng dưới đây lấy một biến thể cho mỗi scenario VALIDATION độc lập:

| Candidate | Contract | Citation recall | Bao phủ nguyên văn | Độ trễ trung bình |
|---|---:|---:|---:|---:|
| Qwen3-1.7B gốc | 10/10 | 10/10 | 8/10 | 4,90 giây |
| QLoRA rank 16 | 10/10 | 9/10 | 9/10 | 10,72 giây |

Adapter tăng một ca bao phủ nguyên văn nhưng giảm citation và làm độ trễ hơn gấp đôi.
Vì citation là chốt an toàn, G5 **không triển khai adapter**. Model phục vụ vẫn là
Qwen3-1.7B Q8_0 gốc. Việc hoàn thành thí nghiệm fine-tune không đồng nghĩa adapter bắt
buộc phải được phát hành.

## 2. Retrieval và hội thoại

| Bộ đánh giá | Kết quả |
|---|---|
| DEV 80 scenario | Routing, status và Recall@5 đều 80/80 |
| API multi-turn DEV | 16/16 chuỗi; 13 answer và 3 abstain an toàn |
| TEST_V3 đã mở, dùng lại làm regression | 40/40 field, routing, status, Recall@5, AnswerPlan và multi-turn; 0 lỗi claim trọng yếu |

TEST_V3 từng được dùng để phân tích lỗi nên kết quả 40/40 chỉ chứng minh **regression đã
được sửa**, không còn là holdout độc lập. Trên DEV hiện tại, tuyến Exact/BM25 đã đạt
80/80 và không có ca cần embedding; vì vậy chưa tuyên bố hybrid cải thiện tỷ lệ. Dense
fallback được giữ ở phạm vi hẹp và có unit test riêng cho ca semantic không khớp từ khóa.

## 3. MCP, Docker và tải nhỏ

- Smoke live xác nhận bản PENDING không xuất hiện; sau APPROVE/PUBLISH, Backend dùng đúng
  snapshot/version/checklist; ROLLBACK trả hệ thống về corpus gốc.
- G5 Docker có 7 service healthy: Web, Backend, PostgreSQL, AI Service, llama-server,
  embedding-server và Source Service.
- Bài tải nhỏ 12 request, concurrency 2: thành công 12/12, P50 khoảng `0,97 giây`, P95
  khoảng `1,58 giây`, throughput `1,83 request/giây`. Đây là phép đo local nhỏ, không phải SLA.

## 4. Kiểm thử mã nguồn

| Thành phần | Kết quả chốt |
|---|---:|
| Backend | 228 passed, 1 skipped |
| AI Service | 68 passed |
| Data tools | 16 passed |
| Source Service | 3 passed |
| Web | 12 passed; ESLint và production build sạch |

Ruff, kiểm tra schema/hash, repository hygiene và các smoke API được chạy riêng. Kết quả
độc lập cuối chặng vẫn cần một holdout mới do reviewer giữ kín.
