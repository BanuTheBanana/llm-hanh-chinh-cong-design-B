# Biên bản nghiệm thu nền tảng Giai đoạn 3

## Báo cáo cập nhật

| Trường | Nội dung |
|---|---|
| Cập nhật | 10/09/2026 |
| Nhánh | `g3/integration` |
| Baseline | `main` tại `g2-v1.0.0` |
| Trạng thái | `G3_TECHNICAL_FOUNDATION_COMPLETE` |
| Phạm vi | Demo nội bộ căn bản; chưa phải hệ thống production hoặc kết luận pháp lý |
| Fine-tune | `NO_FINE_TUNE_FOR_CURRENT_BASELINE` |

## Tổng

G3 đã hình thành một hệ thống căn bản chạy xuyên suốt:

```text
Workbook công ty
→ preprocess/validate/review local
→ corpus D2 demo read-only, khóa version + SHA-256
→ exact/BM25 + missing-field/abstain guard
→ Qwen3-1.7B Q8_0 chạy local
→ JSON/citation verifier + một retry sửa contract có kiểm soát
→ FastAPI + PostgreSQL history
→ React Web hiển thị câu trả lời và nguồn
```

Raw, normalized, gold và prompt/evidence thật không nằm trong Git. Dữ liệu D2
không đi qua Gemini, Groq, OpenAI hay provider hosted nào.

## Phân

### 1. Corpus demo thật đã khóa

| Thuộc tính sanitized | Giá trị |
|---|---:|
| Dataset version | `company-tthc-9c38dde8-v1-demo10-v1` |
| Corpus SHA-256 | `2875694a7cbb0238bfb4ebfdd562166b63f0851077ae824f62bbe234602b7d1e` |
| Source/procedure/fragment | 10 / 10 / 49 |
| DEV/TEST question | 31 / 9 |
| Open conflict/rejected procedure | 0 / 0 |
| Publish validation | PASS cho demo nội bộ |
| TEST lock SHA-256 | `5b01742e9098dc655352557964562baef6d43d9d1c25e7056d5336f974529357` |

Đây là subset nhỏ phục vụ dựng hệ thống. Nhãn `APPROVED_FOR_DEMO` chỉ xác nhận
được phép chạy demo nội bộ và qua gate cấu trúc; không đồng nghĩa toàn bộ nội dung
đã được cơ quan nghiệp vụ chứng nhận đúng pháp lý.

### 2. Kết quả DEV và TEST khóa

| Metric aggregate | DEV | TEST khóa cuối |
|---|---:|---:|
| Số câu | 31 | 9 |
| Routing accuracy | 86,67% | 100% |
| Retrieval Recall@5 | 70% | 75% |
| Status accuracy | 83,87% | 88,89% |
| Valid generation | 100% | 100% |
| Citation binding | 100% | 100% |
| Generation latency p50 | 613,792 ms | 611,455 ms |
| Generation latency p95 | 1.075,007 ms | 1.177,404 ms |
| External AI call | 0 | 0 |

Các metric chỉ đo routing/retrieval, contract, status và citation. Chúng chưa đo
đầy đủ tính đúng nghiệp vụ từng câu. TEST chỉ dùng cho lượt đánh giá cuối; không
dùng để sửa prompt, RAG hay model. Mọi cải tiến tiếp theo phải thực hiện trên DEV,
sau đó tạo một release/TEST lock mới theo change control.

#### Routing hardening sau kiểm thử thủ công

Kiểm thử người dùng phát hiện cách hỏi bỏ tiền tố `Thủ tục` bị đánh dấu mơ hồ dù
đã nêu đúng tên. Router đã được sửa trên DEV: sinh biến thể tên không có tiền tố
chung, loại từ chỉ intent khỏi query định tuyến, chọn top-1 chỉ khi vượt ngưỡng
điểm/khoảng cách và ưu tiên tên đầy đủ nhất khi hai tên lồng nhau.

| Gate sau sửa | Kết quả |
|---|---:|
| Gọi tên tự nhiên trực tiếp trên 10 thủ tục | 10/10 route đúng |
| Mẫu hội thoại `Tôi muốn làm ...` trên 10 thủ tục | 10/10 route đúng |
| Hai câu đăng ký khai sinh từng thất bại | 2/2 `ANSWER`, có citation |
| Câu thiếu tên thủ tục | `NEED_CLARIFICATION`, 0 nguồn |
| Câu ngoài corpus | `INSUFFICIENT_DATA`, 0 nguồn |

Các số TEST trong bảng trên là kết quả khóa trước lần hardening và **không được
chạy lại để chỉnh router**. Muốn công bố metric TEST sau thay đổi phải tạo
`TEST_V2` mới theo change control; việc này không làm mất giá trị của gate chức
năng G3 nhưng ngăn tuyên bố quá mức về chất lượng tổng quát.

### 3. E2E thật

Một câu `ANSWER` thuộc DEV đã chạy qua Web contract → Backend → RAG D2 → Qwen
local → verifier → PostgreSQL history:

| Gate | Kết quả |
|---|---:|
| Answer + citation | PASS, 1 citation |
| Classification/provider | `D2_COMPANY_REAL` / `local` |
| History sau reload contract | 2 message |
| Internal URI/raw locator lộ ra response | false |
| Lượt quan sát E2E cuối | 0,777 giây |

### 4. Cổng chống data leakage

- D2 chỉ được bật bằng `LOCAL_LLM_ALLOW_D2_COMPANY_DATA=true` trên provider local.
- Health của Backend bắt buộc `external_calls_enabled=false` và AI allowlist có D2.
- Corpus mount read-only; version, số dòng và corpus SHA-256 đều phải khớp.
- `public_url=null` được giữ nguyên; không tạo URL giả và không trả internal URI/locator.
- Backend chỉ gửi query + tối đa 8 fragment cần thiết, không gửi user/cookie/history.
- Log chỉ chứa request ID, classification, count, latency và mã lỗi; không chứa body.
- TEST khóa theo procedure và SHA-256; chat người dùng không tự trở thành train data.
- Runtime chat loại gold/TEST khỏi memory/index sau bước xác minh release.
- `.gitignore` và repository hygiene chặn workbook/private output/model/secret.

### 5. Regression cuối

| Module | Kết quả |
|---|---:|
| Backend + PostgreSQL migration thật | 149 passed, 1 Windows symlink skip |
| AI Service | 65 passed |
| Data G3 pipeline/release | 7 passed |
| Web | 11 passed; lint + production build PASS |
| Docker Compose + D2 readiness | PASS |
| Repository hygiene/secret/private-file scan | PASS, 223 file được kiểm |

VRAM snapshot sau benchmark là 6.724/16.311 MiB của toàn GPU; do Windows không
cho tách per-process nên đây chỉ là capacity observation, không phải peak model.

### 6. Quyết định không fine-tune ở G3

Qwen3-1.7B Q8_0 đã đạt 100% response contract và citation binding sau guard/retry.
Sai số còn lại hiện liên quan nhiều đến data/routing/retrieval/status hơn là bằng
chứng model thiếu kiến thức nền, vì model chỉ được phép diễn giải evidence. Do đó
fine-tune lúc này tăng chi phí và rủi ro leakage nhưng chưa có bằng chứng sẽ sửa
đúng bottleneck. G3 chốt zero-shot local; QLoRA chỉ được xem lại sau khi DEV được
review nghiệp vụ và error analysis chứng minh lỗi diễn giải lặp lại.

## Hợp

G3 hoàn tất với nghĩa **nền tảng kỹ thuật căn bản có thể sử dụng và phát triển
tiếp**: có dữ liệu thật theo subset, RAG, Qwen local, API, database, Web, citation,
health, Docker và gate chống leakage. Các việc như mở rộng đủ 38 thủ tục, semantic
review, dense retrieval/reranker, case/memory dài hạn, queue/Socket.IO, monitoring,
auth thật và production deployment thuộc giai đoạn sau, không phải lỗi còn dang dở
của lát cắt nền tảng này.
