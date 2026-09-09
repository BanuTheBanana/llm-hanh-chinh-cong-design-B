# Công cụ dữ liệu G2

- `validate_dataset.py --mode preflight`: kiểm tra kỹ thuật draft; cảnh báo các
  gate review/phạm vi còn thiếu nhưng vẫn trả exit code 0 nếu cấu trúc nhất quán.
- `validate_dataset.py --mode publish`: cùng các kiểm tra trên nhưng biến review,
  độ đầy đủ và phạm vi 2–3 thủ tục/30–50 câu thành lỗi chặn publish.
- `build_synthetic_dataset.py`: tạo lại deterministic corpus D0 gồm 3 thủ tục,
  24 fragment và 33 câu hỏi; không truy cập Internet.
- `crawl_or_download.py`: chỉ tải một URL HTTPS thuộc allowlist, tôn trọng
  `robots.txt`, giới hạn dung lượng và không ghi đè snapshot cũ.
- `g3_pipeline`: parser, validator và gold-draft builder cho workbook công ty G3.
  Công cụ chỉ chạy local, output luôn nằm ở vùng `data/company_private/` bị ignore.
  Xem [hướng dẫn phần Tú](../../docs/giai-doan-3/04-huong-dan-pipeline-data-tu.md).

Không công cụ nào tự chuyển `review_status` sang `APPROVED`. Việc đó cần người
review thứ hai và mentor xác nhận phạm vi sử dụng.

Khi kiểm tra dữ liệu D0, phải truyền rõ:

```text
--dataset data/demo_synthetic --classification D0_SYSTEM_SMOKE
```
