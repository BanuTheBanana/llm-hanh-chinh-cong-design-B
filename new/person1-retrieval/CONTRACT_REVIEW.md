# Person 1 technical review — 2026-09-30

Đã đối chiếu bản code thực tế với handoff `demo-corpus-v2`.

- `contracts/` là nguồn schema duy nhất; xóa 10 JSON trùng còn sót trong bản `new(2).rar`.
- Không đổi shape/schema active nào, không thêm thuộc tính vào EvidenceBundle.
- Input/query/filter/top_k và output được validate bằng Draft202012 + format checker.
- top_score/second_score là max evidence score của hai procedure khác nhau; margin = top-second.
- ambiguous không kèm evidence; candidates có ít nhất hai ID/tên phân biệt được.
- resolved evidence chỉ thuộc một procedure/source/version/effective_date; field section_type luôn có.
- top_k nhỏ có thể không chứa hết requested fields: Person 2 vẫn phải trả insufficient_data.
- null effective_date là “không biết”, không phải đã xác minh; production mặc định chặn unknown date/draft.
- scope không có metadata để kiểm chứng nên fail closed.
- Dense/fused chỉ dùng giá trị method đã có trong enum; fusion_method mô tả đúng thuật toán.

Đã thêm kiểm thử hồi quy Person 1/2 cho lựa chọn sau ambiguity và filter/topic reset.
Code đề xuất đã tương thích kỹ thuật; không ghi thay chữ ký của Minh hoặc Person 2.
Hai owner cần xác nhận semantics v1 ở README trước merge vào nhánh chung.

Thay đổi tại Person 2 chỉ gồm:
1. app/corpus.py re-export validator/fingerprint do Person 1 sở hữu để tránh hai implementation lệch nhau.
2. resolve_filters có keyword carry tùy chọn, giữ behavior cũ khi không truyền.
3. main.execute truyền carries_context để xử lý ordinal và reset topic đúng.
4. tests/test_person1_handoff.py kiểm tra chuỗi ambiguity → selection → new topic → absent.

Canonical fingerprint nay sắp cả fragment_ids (danh sách membership; ordinal vẫn nằm trong fragment).
Snapshot có fragment_ids trước đây không sắp có thể đổi fingerprint dù text không đổi: rebuild/reimport
thành snapshot mới bằng công cụ import hiện có; không sửa identity snapshot cũ trong database.


Cập nhật thay corpus: thêm bootstrap_data/settings và mount corpus; fields chuyển từ raw keyword inference sang requested_sections của retriever tại API để tránh đọc nhầm từ khóa trong tên procedure. Shapes của contracts không thay đổi.
