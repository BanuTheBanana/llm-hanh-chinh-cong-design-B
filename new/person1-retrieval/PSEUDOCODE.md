# Pseudocode và thứ tự điền bản TODO

Hai phiên bản có cùng tên hàm/giao diện, cùng tests; bản TODO chủ động ném NotImplementedError đến khi anh điền. Không đọc bản hoàn chỉnh trước nếu muốn tự luyện.

## 1. normalize_text(text)

IF text không phải string: lỗi TypeError.
Chuẩn hóa Unicode về NFC.
Gom mọi khoảng trắng thành một space và bỏ khoảng trắng đầu/cuối.
RETURN text; giữ chữ hoa, dấu tiếng Việt, số, dấu câu.

## 2. load_protected_terms(path)

Đọc UTF-8 có hỗ trợ BOM. Với từng dòng: bỏ dòng rỗng và comment #.
RETURN tuple cụm từ, chưa tự chọn cụm nào cho người dùng.

## 3. SegmenterConfig.__post_init__

Kiểm tra backend trong underthesea/pyvi.
Kiểm tra mỗi cụm hợp lệ và không rỗng, chỉ từ và khoảng trắng.
Chuẩn hóa cụm, khử trùng không phân biệt hoa thường, sắp dài trước rồi alphabet.
Lưu tuple bất biến để index và query dùng cùng config.

## 4. _load_backend(name)

Lazy import backend được yêu cầu, cache kết quả.
underthesea: word_tokenize(text, format='text', use_token_normalize=False).
pyvi: ViTokenizer.tokenize(text).
Nếu thiếu dependency/model: báo SegmentationError; không tự chuyển sang split().

## 5. VietnameseSegmenter

INIT: lấy config; nếu có protected_terms, compile regex escape từng cụm, có biên từ.
_segment_chunk: bỏ qua đoạn trắng, gọi model, kiểm tra kết quả string, chuẩn hóa khoảng trắng. Lỗi không chứa văn bản nguồn.
segment:
  normalize input; nếu rỗng RETURN ''.
  không có cụm bảo vệ: gọi _segment_chunk toàn văn bản.
  có cụm: tìm các span khớp không chồng lấn, dài trước.
  tách đoạn trước span bằng model; span ghép bằng underscore giữ hoa/thường gốc.
  tách phần còn lại; nối các phần bằng space.
metadata: backend/version/normalization/terms/wrapper_version -> JSON canonical -> SHA-256.

## 6. segment(text) công khai

Tái sử dụng một instance mặc định, gọi instance.segment(text).
Nếu chọn config khác: truyền instance có config rõ ràng cho cả index và query.

## 7. load_fragments(path)

Đọc JSON array không rỗng. Mỗi object có fragment_id string không trùng và text string không rỗng.
Không in nội dung dữ liệu khi báo lỗi.
RETURN các object; không sửa file nguồn.

## 8. run_comparison

Validate repeats và limit. Load fragments, lấy tất cả hoặc N đầu.
Từ chối thư mục output có nội dung để không ghi đè review.
Tạo hai segmenter cùng danh sách cụm bảo vệ.
Warmup từng backend bằng câu giả lập, đo riêng.
FOR mỗi fragment:
  FOR mỗi backend:
    chạy repeats lần, đo thời gian, giữ output, đếm token, kiểm tra lặp nhất quán.
  so output hai backend; đánh dấu khác nhau, không gán đúng/sai.
Tổng hợp thời gian, counts, phiên bản, config fingerprint, SHA-256 input.
Xuất JSONL giữ nguyên text; CSV chống ô công thức; summary JSON không có văn bản nguồn.

## 9. CLI main

Đọc --input/--output/--protected-terms/--repeats/--limit.
Tạo tên thư mục run mới nếu không chỉ định output.
Load terms, gọi comparison; khi lỗi trả exit code 1; thành công code 0.

## Thứ tự kiểm thử

1. normalize + config + file từ điển.
2. core segmentation với backend giả để kiểm tra lỗi, span, biên cụm.
3. comparison bằng JSON giả lập và backend giả.
4. integration bằng hai model thật.
5. chạy fragment thật, đọc bảng review, không đánh đồng output khác với lỗi.

Lệnh: python -m pytest -q -m 'not integration', sau đó python -m pytest -q -m integration.
Bản TODO: các test đỏ là bài cần hoàn thành; không xóa assertion để làm xanh.
