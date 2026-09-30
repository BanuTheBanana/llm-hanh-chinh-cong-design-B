# Phiếu đánh giá segmentation — cần người đọc điền

- Corpus/run:
- Backend và phiên bản:
- Số fragment đã xem thủ công:
- Loại nội dung đã xem: hồ sơ / phí / thời gian / căn cứ / khác.

| Fragment ID | Cụm gốc | Underthesea | Pyvi | Cách tách mong muốn | Lý do / ảnh hưởng truy hồi |
|---|---|---|---|---|---|
| | | | | | |

## Quyết định ban đầu

- Segmenter chọn và lý do:
- Cụm giữ nguyên thêm/bỏ và bằng chứng:
- Giới hạn chưa giải quyết:
- Người review/ngày:

Chỉ kết luận về những ví dụ đã kiểm tra. Chưa có nhãn gold thì không báo accuracy/F1. Cụm được ghép thành một token không tự động tốt hơn; cần kiểm tra retrieval ở giai đoạn tiếp theo.


## Review kỹ thuật 30/09/2026 — chỉ 3 câu synthetic

Đã chạy cả hai backend 2 lần/câu. Cả hai cho kết quả lặp nhất quán, 3/3 câu có khác biệt.

| Ví dụ | underthesea | pyvi | Nhận xét |
|---|---|---|---|
| Người dân | Người_dân | Người dân | Khác ranh giới token, chưa đủ cơ sở gọi là lỗi |
| Cụm từ | Cụm_từ | Cụm từ | Khác ranh giới, chưa có nhãn chuẩn |
| hộ kinh doanh | hộ kinh_doanh | hộ kinh_doanh | Đều giữ kinh_doanh, không tự bật protected phrase dài |
| người đại diện theo pháp luật | người đại_diện theo pháp_luật | người đại_diện theo pháp_luật | Không có căn cứ ghép toàn cụm thành một token |
| 60/2014/QH13 | 60/2014 / QH13 | 60 / 2014 / QH13 | Giữ ký tự nguồn nhưng chia khác; cần kiểm tra retrieval mã văn bản trên DEV |

Giữ underthesea làm mặc định tích hợp, protected_terms.txt vẫn rỗng.
Đây là review quan sát của trợ lý trên câu tự tạo, không phải duyệt thuật ngữ của chuyên gia/người sở hữu corpus.
Chưa có corpus thật/gold segmentation nên không báo accuracy/F1 hay chọn backend thắng.
Outputs cụ thể: verification/current/segmentation/.
