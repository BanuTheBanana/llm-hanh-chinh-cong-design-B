# Công cụ dữ liệu G2

- `validate_dataset.py --mode preflight`: kiểm tra kỹ thuật draft; cảnh báo các
  gate review/phạm vi còn thiếu nhưng vẫn trả exit code 0 nếu cấu trúc nhất quán.
- `validate_dataset.py --mode publish`: cùng các kiểm tra trên nhưng biến review,
  độ đầy đủ và phạm vi 2–3 thủ tục/30–50 câu thành lỗi chặn publish.
- `crawl_or_download.py`: chỉ tải một URL HTTPS thuộc allowlist, tôn trọng
  `robots.txt`, giới hạn dung lượng và không ghi đè snapshot cũ.

Không công cụ nào tự chuyển `review_status` sang `APPROVED`. Việc đó cần người
review thứ hai và mentor xác nhận phạm vi sử dụng.
