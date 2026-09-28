# Person 1 — lexical demo integration

src/person1_retrieval/segmenter.py: segmenter underthesea/pyvi từ bản hoàn chỉnh đã kiểm thử trước.
src/person1_retrieval/retriever.py: LexicalRetriever(corpus, segmenter, fingerprint, allow_draft, score_floor, margin_floor).

retrieve(RetrievalInput, state=None) -> EvidenceBundle theo contracts hiện tại. Backend tạo index từ snapshot PostgreSQL và truyền cùng segmenter cho query. Không có dense/fusion. Fusion_method hiện chỉ là lexical_bm25_procedure_max, không phải hybrid.

Top-2 được tính trên hai procedure khác nhau trước top_k; score=max fragment BM25 sau filters/section. Alias có thể bypass ngưỡng lexical khi rõ ràng, nhưng không bypass filters. Ngưỡng 0.5/0.15 là demo chưa tune. Cần benchmark procedure/field do Person 3 đánh giá.

Kiểm thử và lệnh chạy tại ../person2-backend/README.md. Chỉ gói code, không có dữ liệu công ty.
