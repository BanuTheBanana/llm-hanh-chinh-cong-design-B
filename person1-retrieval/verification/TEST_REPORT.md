# Kết quả kiểm thử bản hoàn chỉnh

- Python 3.12, Linux; chưa kiểm thử Windows.
- `python -m pytest -q`: **30 passed**, gồm 2 integration case gọi underthesea và pyvi thật. Không skip.
- Chạy corpus thật: 289 fragment; underthesea 9.5.0 và pyvi 0.1.1, mỗi backend 2 lần/fragment.
- 112/289 fragment có output khác nhau. Đây là khác biệt, không phải số lỗi.
- Số fragment có output không nhất quán giữa hai lần chạy: xem summary đi kèm.
- Không có gold segmentation: chưa đánh giá accuracy/F1, chưa chọn segmenter thắng.
- Test kỹ thuật gồm Unicode, input rỗng/sai kiểu, protected phrase/biên từ/cụm lồng nhau, lỗi backend, không lộ input trong exception wrapper, config fingerprint, input JSON lỗi, không sửa source, không ghi đè review và chống ô công thức CSV.
- Không kiểm thử PostgreSQL/BM25 vì ngoài phạm vi bước này.
- comparison CSV/JSONL chứa dữ liệu nguồn được tạo và kiểm tra local; không đóng vào gói code để tránh đưa lên repo. Chạy script với file JSON của anh sẽ xuất lại đầy đủ bảng review.
- `real_corpus_summary.json` chỉ gồm thống kê, môi trường và fingerprint; không có văn bản fragment.

Bản TODO không được tuyên bố pass: các hàm intentionally NotImplementedError cho người học điền. Giữ nguyên bộ test làm tiêu chí hoàn thành.
