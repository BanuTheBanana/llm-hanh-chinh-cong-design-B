# demo-corpus-v2

- source_manifest.effective_date: string date hoặc null; field vẫn required.
- procedure_record.jurisdiction: string hoặc null.
- evidence.effective_date: string date hoặc null.
- evidence.section_type: enum giống procedure_fragment, required.
- Corpus chưa duyệt giữ draft. Null không có nghĩa hợp lệ/vẫn hiệu lực.
- Không đổi RetrievalInput, EvidenceBundle, GroundedAnswer hay ConversationState.
- top_score/second_score tính trên hai procedure khác nhau; procedure score=max fragment BM25 sau filters/section. Exact-match routing được ưu tiên trước ngưỡng lexical. Các threshold hiện chưa được calibration.
- Lý do: Excel không cung cấp ngày hiệu lực chắc chắn; backend phải biết loại section thay vì suy từ nội dung.
- Các track cần cập nhật schema/fixtures cùng lần tích hợp. Không coi gói demo là nghiệm thu độ chính xác.
