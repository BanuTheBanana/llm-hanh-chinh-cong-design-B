# Person 1 — Bước 1: Vietnamese segmentation (bản hoàn chỉnh)

Phạm vi: `segment(text)`, so sánh underthesea/pyvi, cụm giữ nguyên tùy chọn, test và bảng kiểm tra. Chưa gồm importer PostgreSQL, snapshot builder, BM25, dense, fusion hay EvidenceBundle. Không sửa backend hoặc contracts của team.

## Đặt vào repo

Giải nén, lấy nội dung `new/person1-retrieval/` đặt vào đúng thư mục tương ứng trong repo. Hai file rỗng `segmenter.py` và `__init__.py` đang ở gốc track trong new.rar có thể xóa sau khi xác nhận còn rỗng; code thật nằm trong `src/person1_retrieval/`. Không chép bản TODO đè lên bản hoàn chỉnh.

## Chạy trên Windows PowerShell — Python 3.12

Từ gốc repo:

```powershell
cd new/person1-retrieval
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest -q
```

Không cần activate môi trường. Lần cài cần Internet để tải thư viện; code không gửi nội dung corpus đến API.

Thử ba fragment giả lập kèm theo:

```powershell
.\.venv\Scripts\python.exe scripts/compare_segmenters.py --input tests/sample_fragments.json
```

Để thử thật: copy file `procedure_fragments.json` đã xuất từ Excel vào `data/local/`, rồi:

```powershell
.\.venv\Scripts\python.exe scripts/compare_segmenters.py --repeats 2
```

Script mặc định đọc file trong data/local. Mỗi lần tự tạo thư mục reports/run_... mới. Tham số `--limit 20` chỉ chạy 20 dòng đầu (không phải mẫu ngẫu nhiên đại diện). `--output reports/my_run` chỉ nhận thư mục rỗng/mới để tránh mất ghi chú đánh giá.

## Đọc kết quả

- `comparison.csv`: mở Excel xem nguyên văn, hai kết quả, latency, số token, cờ khác nhau và cột review_notes trống để ghi nhận xét.
- `comparison.jsonl`: cùng nội dung nhưng giữ nguyên chuỗi chính xác. CSV có thêm dấu nháy đơn ở ô bắt đầu bằng =,+,-,@ để tránh Excel chạy công thức.
- `summary.json`: số fragment, số kết quả khác nhau, timing, phiên bản và fingerprint cấu hình. Timing đã tách warmup, tính median các lần chạy trên mỗi fragment.

**Hai output khác nhau không có nghĩa một bên sai. Không có gold tokenization nên chưa tính accuracy/F1, chưa tuyên bố segmenter thắng.** Xem các lỗi tách/gộp ảnh hưởng thuật ngữ rồi xác định chính sách với nhóm. Kiểm thử code pass không phải độ chính xác pháp lý 100%.

## Cụm giữ nguyên

Mặc định danh sách rỗng. Thêm cụm đã có bằng chứng cần bảo vệ vào `configs/protected_terms.txt` (mỗi dòng một cụm), rồi chạy:

```powershell
.\.venv\Scripts\python.exe scripts/compare_segmenters.py --protected-terms configs/protected_terms.txt
```

`protected_terms.example.txt` chỉ là minh họa. Khi bật, wrapper tìm cụm trong văn bản trước khi gọi model, ưu tiên cụm dài hơn, ghép bằng dấu gạch dưới; phần còn lại được model tách. Cách này thay đổi ngữ cảnh ở biên cụm, nên cần so lại với baseline. Không nối tất cả thuật ngữ dài một cách mặc định.

## Backend Person 2 gọi thế nào?

Sau khi cài package trong cùng môi trường backend (từ person2-backend dùng `python -m pip install -e ../person1-retrieval`):

```python
from person1_retrieval import segment
result = segment('Người dân nộp hồ sơ.')
```

Hàm trên dùng underthesea và không có cụm ép; đây là mặc định tích hợp tạm thời, không phải kết luận benchmark. Để index/query dùng cùng cấu hình:

```python
from person1_retrieval import VietnameseSegmenter, SegmenterConfig
from person1_retrieval.segmenter import load_protected_terms

engine = VietnameseSegmenter(SegmenterConfig(
    backend='pyvi',
    protected_terms=load_protected_terms('configs/protected_terms.txt'),
))
segmented_corpus = engine.segment(fragment_text)
segmented_query = engine.segment(query_text)
metadata = engine.metadata()
```

Dùng chung engine/config cho cả hai phía. Lưu metadata với index; đổi backend, phiên bản hoặc từ điển thì phải rebuild index. `config_fingerprint` định danh config và phiên bản package, chưa hash byte trọng số model/dependency toàn bộ. Nội dung `text` gốc trong corpus không bị chỉnh sửa. Wrapper chuẩn hóa NFC và khoảng trắng; không bỏ dấu, viết thường hay xóa số/dấu câu. Model vẫn có thể thay đổi ký tự — phải xem bảng so sánh trước khi chốt.

## Bố cục và phụ thuộc

`src/person1_retrieval/segmenter.py`: logic dùng chung. `comparison.py`: đọc JSON, chạy hai backend, xuất báo cáo. `scripts/compare_segmenters.py`: CLI. `tests/`: kiểm tra kỹ thuật và model thật. `PSEUDOCODE.md`: luồng và bài tập tương ứng bản TODO.

`requirements.txt` pin các thư viện chính; `requirements-tested-linux.txt` ghi toàn bộ môi trường đã kiểm thử để tham khảo, không ép mọi wheel Linux lên Windows. Chưa chạy Windows trong môi trường này.

Bộ code không kèm Excel/JSON công ty. data/local và reports đã có gitignore; báo cáo so sánh chứa văn bản nguồn nên giữ local. Dữ liệu giả lập trong tests có thể commit.

## Bước tiếp theo

Điền segmentation_review.md sau khi xem output; chốt lựa chọn ban đầu và bàn giao segment(). Sau đó mới hoàn thiện schema/corpus validation/snapshot và BM25. PostgreSQL của team không cần đổi ở bước này.

## Tài liệu API đã đối chiếu

- https://github.com/undertheseanlp/underthesea (word_tokenize)
- https://undertheseanlp.github.io/underthesea/docs/next/api/word-tokenize
- https://github.com/trungtv/pyvi (ViTokenizer.tokenize)
