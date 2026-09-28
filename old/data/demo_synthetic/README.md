# Dataset D0 giả lập – phát triển RAG

## Báo cáo cập nhật

| Trường | Nội dung |
|---|---|
| Phiên bản | `synthetic-demo-v1` |
| Phân loại | `D0_SYSTEM_SMOKE` |
| Quy mô | 3 nguồn, 3 thủ tục, 24 fragment, 33 câu hỏi |
| Mục đích | Phát triển, integration test và demo kỹ thuật |
| Giá trị pháp lý | Không có |

## Tổng

Toàn bộ tên cơ quan, biểu mẫu, phí, thời gian và căn cứ trong thư mục này đều hư
cấu. Dataset giúp nhóm hoàn thiện RAG khi website thật bị lỗi nhưng tuyệt đối
không được dùng để trả lời công dân hoặc đánh giá độ đúng hành chính.

Ba thủ tục giả lập:

- Đăng ký khai sinh Sao Mai;
- Cấp thẻ căn cước Ánh Trăng;
- Đăng ký khai tử Mây Trắng.

Mỗi thủ tục có đủ 8 nhóm thông tin: đối tượng, nơi tiếp nhận, cách nộp, hồ sơ,
các bước, phí, thời gian và căn cứ giả. Mọi câu trả lời từ Web phải giữ cảnh báo
`BẢN MÔ PHỎNG D0 - KHÔNG PHẢI HƯỚNG DẪN`.

## Phân

```text
source_manifest.jsonl          3 nguồn fixture.invalid
raw/                           3 snapshot văn bản giả
normalized/procedures.jsonl    3 procedure record
normalized/fragments.jsonl    24 fragment có SHA-256
gold/questions.jsonl          23 DEV + 10 TEST
fixtures/                      bundle/request/answer contract mẫu
```

`review_status=APPROVED` ở đây chỉ có nghĩa fixture đã qua kiểm tra kỹ thuật;
không phải chuyên gia hay cơ quan nhà nước phê duyệt nội dung.

## Hợp

Tạo lại dữ liệu deterministically:

```powershell
python tools/data/build_synthetic_dataset.py
```

Nghiệm thu schema/hash/reference/completeness:

```powershell
python tools/data/validate_dataset.py --root . `
  --dataset data/demo_synthetic `
  --classification D0_SYSTEM_SMOKE `
  --mode publish
```

Đánh giá retrieval từ thư mục `backend/`:

```powershell
uv run --frozen python -m app.rag.cli evaluate `
  --repo-root .. `
  --dataset data/demo_synthetic `
  --version synthetic-demo-v1 `
  --allow-domain fixture.invalid `
  --allow-fixture `
  --split DEV `
  --top-k 5
```

Dataset D1 thật tiếp tục nằm riêng ở `data/demo_public`; không sao chép nhãn
`APPROVED` hoặc dữ kiện từ D0 sang D1.
