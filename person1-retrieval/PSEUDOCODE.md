# Luồng Person 1

1. Đọc ba exports → schema validation → unique IDs → links → nguồn nhất quán → text SHA-256 → supersession không vòng.
2. Canonical sort → SHA-256 snapshot; bảo toàn metadata nguồn, không tự điền ngày/đơn vị/hashes còn thiếu.
3. Cùng một VietnameseSegmenter cho corpus/query → BM25 token counts, DF, IDF và average document length.
4. Nếu dense: encoder local → vectors của fragment (name + text), vectors procedure (name + aliases + codes); normalize L2.
5. Query → validate RetrievalInput, kiểm tra query segmentation đúng config index.
6. Exact names/codes/correction → nếu chưa có thì thử ordinal từ unresolved_references → follow-up prior.
7. Lọc status/date/supersession/jurisdiction/scope, procedure restriction và requested sections.
8. BM25 / cosine / RRF → max eligible fragment score của mỗi procedure → sort top hai procedure khác nhau.
9. Exact/state choice hợp lệ được vượt threshold; trường hợp khác so score floor + top-two margin.
10. Ambiguous: trả các procedure candidates, không evidence. Low confidence: không evidence.
11. Resolved: chọn ít nhất một hit cho mỗi requested field trước, rồi bổ sung đến top_k.
12. Gắn source_id, version, effective_date, locator, section_type; validate EvidenceBundle.
13. Log snapshot, method, scores, status, latency, count; không log văn bản query/source.
14. Evaluator tách procedure khỏi field; DEV grid chọn config đề xuất, TEST chỉ đo sau khi freeze.

Các file `.py` là bản triển khai chạy được. Không có bản TODO trong lần bàn giao này.
